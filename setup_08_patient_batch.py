"""
setup_08_patient_batch.py — adiciona alocação de lote por paciente.

Cria:
  1. Custom Fields no Sales Order Patient (batch_no, allocated_qty, batch_status)
  2. Server Script endpoint future_production_allocate_patient_batches:
       - Para cada item do SO, percorre as PRs já liberadas em ordem FIFO
       - Distribui release_batch_no para cada linha de fp_patients até
         esgotar o released_qty da PR
       - Marca batch_status conforme alocação total/parcial
  3. Server Script extensão do release_batch para auto-chamar o allocator
     dos SOs afetados pela liberação.

Uso:
    python setup_08_patient_batch.py
    python setup_08_patient_batch.py --uninstall
"""

from __future__ import annotations

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section
from lib.payloads_patient_batch import PATIENT_BATCH_CUSTOM_FIELDS


SCRIPT_API_ALLOCATE_PATIENT_BATCHES = r'''
# /api/method/future_production_allocate_patient_batches
# Distribui lotes físicos (batch_no) entre as linhas fp_patients de um SO,
# baseado nas Production Reservations já liberadas. Ordem dentro de cada item:
# FIFO da linha fp_patients (idx asc).

data = frappe.form_dict
so_name = data.get("sales_order")
if not so_name:
    frappe.throw("sales_order é obrigatório.")

so = frappe.get_doc("Sales Order", so_name)
if so.docstatus != 1:
    frappe.throw("Sales Order precisa estar submetido.")

patients = so.get("fp_patients") or []
if not patients:
    frappe.response["message"] = {
        "sales_order": so_name,
        "allocated_rows": 0,
        "message": "SO sem fp_patients — nada a alocar.",
    }
else:
    # Agrupa patient rows por item_code, mantendo ordem (idx).
    rows_by_item = {}
    for row in patients:
        rows_by_item.setdefault(row.item_code, []).append(row)

    # Busca PRs por (so, item_code), FIFO igual ao release.
    allocated_rows = 0
    items_processed = []

    for item_code, rows in rows_by_item.items():
        prs = frappe.db.sql(
            """
            select pr.name, pr.sales_order_item, pr.released_qty,
                   pr.release_batch_no, pr.reserved_qty, soi.qty as soi_qty
            from `tabProduction Reservation` pr
            inner join `tabSales Order Item` soi on soi.name = pr.sales_order_item
            where pr.sales_order = %s
              and pr.docstatus = 1
              and soi.item_code = %s
              and coalesce(pr.released_qty, 0) > 0
              and pr.release_batch_no is not null
            order by coalesce(pr.priority, 100) asc,
                     pr.reservation_date asc,
                     pr.creation asc
            """,
            (so_name, item_code),
            as_dict=True,
        )

        if not prs:
            continue

        # Pool de released qty disponível por batch (FIFO).
        pool = []
        for pr in prs:
            pool.append({
                "batch": pr.release_batch_no,
                "available": float(pr.released_qty or 0),
            })

        # Distribui para cada paciente em ordem.
        item_alloc_count = 0
        for row in rows:
            requested = float(row.qty or 0)
            already_alloc = float(row.allocated_qty or 0)
            need = requested - already_alloc

            if need <= 0:
                # Já totalmente alocado.
                continue

            # Pega o primeiro batch com saldo.
            assigned_batch = None
            taken = 0.0
            for bucket in pool:
                available = float(bucket["available"])
                if available <= 0:
                    continue
                if assigned_batch is None:
                    assigned_batch = bucket["batch"]
                if assigned_batch == bucket["batch"]:
                    grab = min(available, need - taken)
                    bucket["available"] = available - grab
                    taken = taken + grab
                    if taken >= need:
                        break

            if taken <= 0:
                # Nenhum batch tem saldo — fica pendente.
                continue

            new_alloc = already_alloc + taken
            if new_alloc >= requested - 0.001:
                new_status = "Alocado"
                new_alloc = requested  # arredonda
            else:
                new_status = "Parcialmente Alocado"

            # Atualiza a linha child.
            frappe.db.set_value("Sales Order Patient", row.name, {
                "batch_no": assigned_batch,
                "allocated_qty": new_alloc,
                "batch_status": new_status,
            }, update_modified=False)

            allocated_rows = allocated_rows + 1
            item_alloc_count = item_alloc_count + 1

        items_processed.append({
            "item_code": item_code,
            "patient_rows": len(rows),
            "allocated_rows": item_alloc_count,
        })

    frappe.response["message"] = {
        "sales_order": so_name,
        "allocated_rows": allocated_rows,
        "items": items_processed,
    }
'''.strip()


SCRIPT_API_ALLOCATE_AFTER_RELEASE = r'''
# Server Script (DocType Event) — chamado após release_batch atualizar PRs.
# Para cada Sales Order afetado (com PRs do FPB liberadas agora), chama o
# allocator de pacientes. Roda como "Production Reservation - After Save"
# disparado quando release_batch_no muda — sinaliza release.
#
# Não usamos DocType Event porque release_batch usa frappe.db.set_value
# (não dispara hooks). Esta lógica é integrada DIRETAMENTE dentro do
# release_batch via patch do setup_03 num release futuro. Por ora,
# o smoke test chama o allocator manualmente após release_batch.
pass
'''.strip()


def install() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error(
            "Server Scripts desabilitados — habilite no bench."
        )
        return 1

    errors = 0

    log_section("1/2 — Custom Fields em Sales Order Patient")
    for field in PATIENT_BATCH_CUSTOM_FIELDS:
        try:
            client.create_custom_field(field)
        except Exception as exc:
            log_error(f"Custom Field {field['dt']}.{field['fieldname']}: {exc}")
            errors += 1

    log_section("2/2 — Server Script endpoint future_production_allocate_patient_batches")
    try:
        client.upsert_server_script({
            "name": "future_production_allocate_patient_batches",
            "script_type": "API",
            "api_method": "future_production_allocate_patient_batches",
            "allow_guest": 0,
            "enabled": 1,
            "script": SCRIPT_API_ALLOCATE_PATIENT_BATCHES,
        })
    except Exception as exc:
        log_error(f"Allocate endpoint: {exc}")
        errors += 1

    if errors == 0:
        log_ok("Módulo Batch-por-Paciente instalado.")
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()

    log_section("Removendo Server Script allocate_patient_batches")
    try:
        client.delete_server_script("future_production_allocate_patient_batches")
    except Exception as exc:
        log_error(f"{exc}")

    log_section("Removendo Custom Fields")
    for field in reversed(PATIENT_BATCH_CUSTOM_FIELDS):
        try:
            client.delete_custom_field(field["dt"], field["fieldname"])
        except Exception as exc:
            log_error(f"{field['dt']}.{field['fieldname']}: {exc}")

    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
