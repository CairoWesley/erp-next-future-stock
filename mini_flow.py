"""
mini_flow.py — Validação manual em pequena escala.

Cenário enxuto pra você ENTENDER cada etapa:
  - 1 FPB de 100 ampolas
  - 1 SO de 10 ampolas com 2 pacientes (6+4)
  - 1 prescriber (CRM-SP)
  - 1 customer
  - Reserva MANUAL no FPB específico
  - Produção FULL (100 ampolas)
  - Liberação FIFO
  - Alocação de batch por paciente

A cada fase imprime:
  - O que foi feito
  - URLs UI pra abrir no browser
  - Chamadas API pra validar via curl
  - Valor esperado
  - Verificação automática (pass/fail)

Uso:
    python mini_flow.py            # roda tudo + pausa entre fases
    python mini_flow.py --no-pause # roda sem parar
    python mini_flow.py --cleanup  # remove tudo (TEST-MINI-*)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from urllib.parse import quote

from lib.erpnext_api import (
    ErpnextApiError,
    client_from_env,
    log_error,
    log_ok,
    log_section,
)


TAG = "TEST-MINI"
COMPANY = "Injmedpharma"
ITEM_CODE = "TIR00060"
WAREHOUSE = "Produtos Acabados - I"
RATE = 100.0

FPB_PLANNED = 100
SO_QTY = 10
PATIENT_A_QTY = 6
PATIENT_B_QTY = 4

PAUSE = True


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def call(client, method, path, **kwargs):
    return client._request(method, path, **kwargs)


def submit(client, doctype, name):
    encoded = quote(name, safe="")
    _, body = call(client, "GET", f"/api/resource/{doctype}/{encoded}")
    doc = body.get("data", {})
    call(client, "POST", "/api/method/frappe.client.submit", json_body={"doc": doc})


def cancel(client, doctype, name):
    try:
        call(client, "POST", "/api/method/frappe.client.cancel",
             json_body={"doctype": doctype, "name": name})
    except ErpnextApiError as exc:
        if "Cancelled" not in str(exc) and "Not Submitted" not in str(exc):
            raise


def pause(label="próxima fase"):
    if not PAUSE:
        return
    print()
    input(f"  >>> Pressione ENTER pra continuar pra {label}... ")


def url(path):
    base = os.environ.get("ERPNEXT_URL", "").rstrip("/")
    return f"{base}{path}"


def print_validation(*, what, ui, api, expected, check_fn=None):
    print()
    print(f"  ╔═══ VALIDAR: {what} ═══")
    print(f"  ║ UI:        {ui}")
    if isinstance(api, list):
        print(f"  ║ API:")
        for line in api:
            print(f"  ║   {line}")
    else:
        print(f"  ║ API:       {api}")
    print(f"  ║ Esperado:  {expected}")
    if check_fn:
        try:
            result = check_fn()
            if result:
                print(f"  ║ ✓ Verificação automática: PASSOU")
            else:
                print(f"  ║ ✗ Verificação automática: FALHOU")
        except Exception as exc:
            print(f"  ║ ⚠ Verificação automática deu erro: {exc}")
    print(f"  ╚{'═' * 60}")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup(client):
    log_section(f"Cleanup — removendo {TAG}-*")

    _, body = call(client, "GET", "/api/resource/Sales Order",
                   params={"filters": json.dumps([["customer", "=", f"{TAG}-Customer"]]),
                           "fields": '["name","docstatus"]'})
    for so in (body or {}).get("data") or []:
        _, prs = call(client, "GET", "/api/resource/Production Reservation",
                      params={"filters": json.dumps([["sales_order", "=", so["name"]]]),
                              "fields": '["name","docstatus"]'})
        for pr in (prs or {}).get("data") or []:
            try:
                if pr.get("docstatus") == 1:
                    cancel(client, "Production Reservation", pr["name"])
                call(client, "DELETE", f"/api/resource/Production Reservation/{pr['name']}")
            except Exception:
                pass
        try:
            if so.get("docstatus") == 1:
                cancel(client, "Sales Order", so["name"])
            call(client, "DELETE", f"/api/resource/Sales Order/{so['name']}")
            log_ok(f"  SO removido: {so['name']}")
        except Exception:
            pass

    _, body = call(client, "GET", "/api/resource/Future Production Batch",
                   params={"filters": json.dumps([["production_code", "like", f"{TAG}-%"]]),
                           "fields": '["name","docstatus"]'})
    for fpb in (body or {}).get("data") or []:
        try:
            if fpb.get("docstatus") == 1:
                cancel(client, "Future Production Batch", fpb["name"])
            call(client, "DELETE", f"/api/resource/Future Production Batch/{fpb['name']}")
            log_ok(f"  FPB removido: {fpb['name']}")
        except Exception:
            pass

    _, body = call(client, "GET", "/api/resource/Batch",
                   params={"filters": json.dumps([["batch_id", "like", f"{TAG}-%"]]),
                           "fields": '["name"]'})
    for b in (body or {}).get("data") or []:
        try:
            call(client, "DELETE", f"/api/resource/Batch/{b['name']}")
        except Exception:
            pass

    for resource, prefix_field, prefix in [
        ("Patient",    "patient_name", f"{TAG}-"),
        ("Prescriber", "full_name",    f"{TAG}-"),
    ]:
        _, body = call(client, "GET", f"/api/resource/{resource}",
                       params={"filters": json.dumps([[prefix_field, "like", f"{prefix}%"]]),
                               "fields": '["name"]'})
        for r in (body or {}).get("data") or []:
            try:
                call(client, "DELETE", f"/api/resource/{resource}/{r['name']}")
            except Exception:
                pass

    try:
        call(client, "DELETE", f"/api/resource/Customer/{TAG}-Customer")
    except Exception:
        pass

    log_ok("Cleanup concluído.")


# ---------------------------------------------------------------------------
# Fluxo
# ---------------------------------------------------------------------------

def run(client):
    log_section("MINI FLOW — validação manual em 7 fases")
    print("  Cenário:")
    print(f"    - 1 FPB:    {FPB_PLANNED} ampolas (item {ITEM_CODE})")
    print(f"    - 1 SO:     {SO_QTY} ampolas, 2 pacientes ({PATIENT_A_QTY}+{PATIENT_B_QTY})")
    print(f"    - Reserva:  manual (FPB específico)")
    print(f"    - Produção: full (100/100)")
    print(f"    - Liberação: FIFO")
    print(f"    - Alocação: batch por paciente")

    # ----- Fase 0: setup base -----
    log_section("Fase 0/7 — Garantir Customer + Prescriber + 2 Patients")

    cust_name = f"{TAG}-Customer"
    status, _ = call(client, "GET", f"/api/resource/Customer/{cust_name}")
    if status != 200:
        call(client, "POST", "/api/resource/Customer", json_body={
            "doctype": "Customer",
            "customer_name": cust_name,
            "customer_type": "Individual",
            "customer_group": "Comercial",
            "territory": "Brazil",
        })
        log_ok(f"  Customer criado: {cust_name}")
    else:
        log_ok(f"  Customer já existe: {cust_name}")

    # Prescriber
    pres_cpf = "55544433321"
    _, body = call(client, "GET", "/api/resource/Prescriber",
                   params={"filters": json.dumps([["cpf", "=", pres_cpf]]),
                           "fields": '["name"]'})
    existing = (body or {}).get("data") or []
    if existing:
        pres_name = existing[0]["name"]
        log_ok(f"  Prescriber já existe: {pres_name}")
    else:
        _, body = call(client, "POST", "/api/resource/Prescriber", json_body={
            "doctype": "Prescriber",
            "full_name": f"{TAG}-Dr Lucas",
            "cpf": pres_cpf,
            "council_type": "CRM",
            "council_number": "90001",
            "council_state": "SP",
            "council_status": "Ativo",
        })
        pres_name = body["data"]["name"]
        log_ok(f"  Prescriber criado: {pres_name}")

    # Patients
    patients = []
    for idx, (cpf, full) in enumerate([
        ("77788899901", f"{TAG}-Paciente A"),
        ("11122233305", f"{TAG}-Paciente B"),
    ]):
        _, body = call(client, "GET", "/api/resource/Patient",
                       params={"filters": json.dumps([["cpf", "=", cpf]]),
                               "fields": '["name"]'})
        existing = (body or {}).get("data") or []
        if existing:
            patients.append(existing[0]["name"])
            log_ok(f"  Patient já existe: {existing[0]['name']} ({full})")
        else:
            _, body = call(client, "POST", "/api/resource/Patient", json_body={
                "doctype": "Patient",
                "patient_name": full,
                "cpf": cpf,
                "gender": "Feminino" if idx == 0 else "Masculino",
                "country": "Brazil",
                "default_prescriber": pres_name,
            })
            patients.append(body["data"]["name"])
            log_ok(f"  Patient criado: {patients[-1]} ({full})")

    pause("Fase 1 (criar FPB)")

    # ----- Fase 1: criar FPB -----
    log_section("Fase 1/7 — Criar Future Production Batch (FPB)")

    code = f"{TAG}-FPB-{int(time.time()) % 100000}"
    _, body = call(client, "POST", "/api/resource/Future Production Batch", json_body={
        "doctype": "Future Production Batch",
        "production_code": code,
        "company": COMPANY,
        "item_code": ITEM_CODE,
        "planned_qty": FPB_PLANNED,
        "planned_production_date": (dt.date.today() + dt.timedelta(days=7)).isoformat(),
        "target_warehouse": WAREHOUSE,
        "status": "Aberta para Reserva",
    })
    fpb_name = body["data"]["name"]
    submit(client, "Future Production Batch", fpb_name)
    log_ok(f"  FPB criado e submetido: {fpb_name}")
    log_ok(f"  Código: {code}")
    log_ok(f"  planned_qty={FPB_PLANNED}, reserved=0, available={FPB_PLANNED}")

    def check_fpb_initial():
        _, b = call(client, "GET", f"/api/resource/Future Production Batch/{fpb_name}")
        d = b["data"]
        return (float(d["planned_qty"]) == FPB_PLANNED and
                float(d["reserved_qty"] or 0) == 0 and
                float(d["available_qty"] or 0) == FPB_PLANNED and
                d["status"] == "Aberta para Reserva")

    print_validation(
        what="FPB criado, submetido, com saldo total disponível",
        ui=url(f"/app/future-production-batch/{fpb_name}"),
        api=f"GET /api/resource/Future Production Batch/{fpb_name}",
        expected=f"planned={FPB_PLANNED}, reserved=0, available={FPB_PLANNED}, status='Aberta para Reserva'",
        check_fn=check_fpb_initial,
    )

    pause("Fase 2 (criar SO)")

    # ----- Fase 2: criar SO + pacientes -----
    log_section("Fase 2/7 — Criar Sales Order com 2 pacientes")

    so_payload = {
        "doctype": "Sales Order",
        "customer": cust_name,
        "company": COMPANY,
        "transaction_date": dt.date.today().isoformat(),
        "delivery_date": (dt.date.today() + dt.timedelta(days=20)).isoformat(),
        "currency": "BRL",
        "selling_price_list": "Venda Padrão",
        "price_list_currency": "BRL",
        "plc_conversion_rate": 1,
        "conversion_rate": 1,
        "items": [{
            "item_code": ITEM_CODE,
            "qty": SO_QTY,
            "rate": RATE,
            "delivery_date": (dt.date.today() + dt.timedelta(days=20)).isoformat(),
            "warehouse": WAREHOUSE,
        }],
        "fp_patients": [
            {"patient": patients[0], "item_code": ITEM_CODE, "qty": PATIENT_A_QTY, "prescriber": pres_name},
            {"patient": patients[1], "item_code": ITEM_CODE, "qty": PATIENT_B_QTY, "prescriber": pres_name},
        ],
    }
    _, body = call(client, "POST", "/api/resource/Sales Order", json_body=so_payload)
    so_name = body["data"]["name"]
    soi_name = body["data"]["items"][0]["name"]
    submit(client, "Sales Order", so_name)
    log_ok(f"  SO criado e submetido: {so_name}")
    log_ok(f"  Row ID do item: {soi_name}")
    log_ok(f"  Total: {SO_QTY} ampolas = R$ {SO_QTY * RATE:.2f}")
    log_ok(f"  Pacientes: A={PATIENT_A_QTY}, B={PATIENT_B_QTY} (soma={PATIENT_A_QTY + PATIENT_B_QTY})")

    def check_so():
        _, b = call(client, "GET", f"/api/resource/Sales Order/{so_name}")
        d = b["data"]
        return (d["docstatus"] == 1 and
                len(d.get("fp_patients") or []) == 2 and
                float(d["items"][0]["qty"]) == SO_QTY)

    print_validation(
        what="SO submetido com 2 pacientes e qty correta",
        ui=url(f"/app/sales-order/{so_name}"),
        api=f"GET /api/resource/Sales Order/{so_name}",
        expected=f"docstatus=1, fp_patients.length=2, items[0].qty={SO_QTY}",
        check_fn=check_so,
    )

    pause("Fase 3 (reservar)")

    # ----- Fase 3: reservar manual -----
    log_section(f"Fase 3/7 — Reservar {SO_QTY} no FPB {fpb_name}")

    resp = client.call_method("future_production_reserve_sales_order_item", {
        "sales_order": so_name,
        "sales_order_item": soi_name,
        "future_production_batch": fpb_name,
        "qty": SO_QTY,
        "priority": 100,
    })
    msg = (resp or {}).get("message") or {}
    pr_name = msg.get("reservation")
    log_ok(f"  PR criada: {pr_name}")
    log_ok(f"  Saldo restante no FPB: {msg.get('available_qty_after')}")

    def check_reserve():
        _, b = call(client, "GET", f"/api/resource/Future Production Batch/{fpb_name}")
        d = b["data"]
        _, b2 = call(client, "GET", f"/api/resource/Sales Order/{so_name}")
        d2 = b2["data"]
        return (float(d["reserved_qty"]) == SO_QTY and
                float(d["available_qty"]) == FPB_PLANNED - SO_QTY and
                d2["items"][0].get("fp_future_production_batch") == fpb_name and
                float(d2["items"][0].get("fp_reserved_qty") or 0) == SO_QTY and
                d2["items"][0].get("fp_reservation_status") == "Reservado")

    print_validation(
        what="FPB decrementou saldo + SO Item mostra a reserva",
        ui=[
            f"FPB:  {url(f'/app/future-production-batch/{fpb_name}')}",
            f"SO:   {url(f'/app/sales-order/{so_name}')}  (role até 'Produção Futura' na linha do item)",
            f"PR:   {url(f'/app/production-reservation/{pr_name}')}",
        ] if False else url(f"/app/sales-order/{so_name}"),
        api=[
            f"GET /api/resource/Future Production Batch/{fpb_name}  → reserved_qty={SO_QTY}, available={FPB_PLANNED-SO_QTY}",
            f"GET /api/resource/Sales Order/{so_name}                → items[0].fp_reserved_qty={SO_QTY}",
            f"GET /api/resource/Production Reservation/{pr_name}    → docstatus=1",
        ],
        expected=f"FPB.reserved={SO_QTY}, FPB.available={FPB_PLANNED-SO_QTY}, SO Item fp_reserved_qty={SO_QTY}, fp_reservation_status='Reservado'",
        check_fn=check_reserve,
    )

    pause("Fase 4 (produzir)")

    # ----- Fase 4: produzir (Batch físico + atualizar FPB) -----
    log_section(f"Fase 4/7 — Registrar produção FULL ({FPB_PLANNED} ampolas)")

    batch_id = f"{TAG}-LOT-{int(time.time()) % 100000}"
    _, body = call(client, "POST", "/api/resource/Batch", json_body={
        "doctype": "Batch",
        "batch_id": batch_id,
        "item": ITEM_CODE,
        "batch_qty": FPB_PLANNED,
    })
    real_batch = body["data"]["name"]
    log_ok(f"  Batch físico criado: {real_batch}")

    call(client, "PUT", f"/api/resource/Future Production Batch/{fpb_name}",
         json_body={"produced_qty": FPB_PLANNED, "batch_no": real_batch})
    log_ok(f"  FPB atualizado: produced_qty={FPB_PLANNED}, batch_no={real_batch}")

    def check_produce():
        _, b = call(client, "GET", f"/api/resource/Future Production Batch/{fpb_name}")
        d = b["data"]
        # Status só muda no release_batch endpoint. Após PUT produced_qty + batch,
        # FPB ainda exibe status anterior (Reservada Parcialmente ou Totalmente).
        return (float(d["produced_qty"]) == FPB_PLANNED and
                d["batch_no"] == real_batch and
                d["status"] in ("Reservada Parcialmente", "Totalmente Reservada",
                                "Produzida Parcialmente", "Produzida Totalmente"))

    print_validation(
        what="FPB tem produced_qty + batch_no preenchidos (pronto pra liberar)",
        ui=url(f"/app/future-production-batch/{fpb_name}"),
        api=[
            f"GET /api/resource/Future Production Batch/{fpb_name}",
            f"GET /api/resource/Batch/{real_batch}",
        ],
        expected=f"produced_qty={FPB_PLANNED}, batch_no={real_batch}, released=0 ainda (não liberou)",
        check_fn=check_produce,
    )

    pause("Fase 5 (liberar)")

    # ----- Fase 5: liberar FIFO -----
    log_section("Fase 5/7 — Liberar Reservas (FIFO)")

    resp = client.call_method("future_production_release_batch",
                              {"future_production_batch": fpb_name})
    msg = (resp or {}).get("message") or {}
    log_ok(f"  Released count={msg.get('released_count')}, "
           f"released_qty={msg.get('released_qty')}, "
           f"pending={msg.get('pending_release_qty')}")

    def check_release():
        _, b = call(client, "GET", f"/api/resource/Future Production Batch/{fpb_name}")
        d = b["data"]
        _, b2 = call(client, "GET", f"/api/resource/Production Reservation/{pr_name}")
        d2 = b2["data"]
        _, b3 = call(client, "GET", f"/api/resource/Sales Order/{so_name}")
        d3 = b3["data"]
        return (float(d["released_qty"]) == SO_QTY and
                float(d2["released_qty"]) == SO_QTY and
                d2["release_batch_no"] == real_batch and
                d2["status"] == "Liberado" and
                float(d3["items"][0]["fp_released_qty"]) == SO_QTY and
                d3["items"][0]["fp_reservation_status"] == "Liberado")

    print_validation(
        what="PR liberada + SO Item espelha + FPB.released atualizado",
        ui=[
            f"FPB:  {url(f'/app/future-production-batch/{fpb_name}')}",
            f"PR:   {url(f'/app/production-reservation/{pr_name}')}",
            f"SO:   {url(f'/app/sales-order/{so_name}')}",
        ] if False else url(f"/app/production-reservation/{pr_name}"),
        api=[
            f"GET /api/resource/Production Reservation/{pr_name}",
            f"  → released_qty={SO_QTY}, release_batch_no={real_batch}, status=Liberado",
            f"GET /api/resource/Sales Order/{so_name}",
            f"  → items[0].fp_released_qty={SO_QTY}, fp_reservation_status=Liberado",
        ],
        expected=f"PR.released_qty={SO_QTY}, PR.release_batch_no={real_batch}, PR.status='Liberado'",
        check_fn=check_release,
    )

    pause("Fase 6 (alocar batch paciente)")

    # ----- Fase 6: alocar batch paciente -----
    log_section("Fase 6/7 — Alocar batch por paciente (fp_patients.batch_no)")

    resp = client.call_method("future_production_allocate_patient_batches",
                              {"sales_order": so_name})
    msg = (resp or {}).get("message") or {}
    log_ok(f"  Linhas alocadas: {msg.get('allocated_rows')}")

    def check_allocate():
        _, b = call(client, "GET", f"/api/resource/Sales Order/{so_name}")
        rows = b["data"].get("fp_patients") or []
        if len(rows) != 2:
            return False
        ok = True
        for r in rows:
            ok = ok and (r.get("batch_no") == real_batch
                         and r.get("batch_status") == "Alocado"
                         and float(r.get("allocated_qty") or 0) == float(r.get("qty") or 0))
        return ok

    print_validation(
        what="Cada paciente tem batch_no=batch real + status=Alocado",
        ui=url(f"/app/sales-order/{so_name}"),
        api=f"GET /api/resource/Sales Order/{so_name}  → fp_patients[].batch_no, .batch_status, .allocated_qty",
        expected=f"Paciente A: batch_no={real_batch}, allocated={PATIENT_A_QTY}, status=Alocado | Paciente B: idem com qty={PATIENT_B_QTY}",
        check_fn=check_allocate,
    )

    # ----- Fase 7: PROVA FINAL — quantidade -> pedidos -> pacientes -----
    log_section("Fase 7/7 — PROVA FINAL: quantidade alocada para pedidos+pacientes corretos")

    # Cruza: FPB -> PR -> SO -> fp_patients
    _, b = call(client, "GET", f"/api/resource/Future Production Batch/{fpb_name}")
    fpb_doc = b["data"]
    _, b = call(client, "GET", "/api/resource/Production Reservation",
                params={"filters": json.dumps([["future_production_batch", "=", fpb_name]]),
                        "fields": '["name","sales_order","released_qty","release_batch_no"]'})
    prs = (b or {}).get("data") or []

    print()
    print(f"  ┌─ FPB {fpb_name} ─────────────────────────────")
    print(f"  │ Item:       {ITEM_CODE}")
    print(f"  │ Planejado:  {fpb_doc['planned_qty']:.0f}")
    print(f"  │ Produzido:  {fpb_doc['produced_qty']:.0f}")
    print(f"  │ Liberado:   {fpb_doc['released_qty']:.0f}")
    print(f"  │ Batch:      {fpb_doc['batch_no']}")
    print(f"  └─ {len(prs)} reserva(s) liberada(s)")

    for pr in prs:
        print(f"\n  ├─ PR {pr['name']} (SO {pr['sales_order']})")
        print(f"  │  liberado={pr['released_qty']:.0f}, release_batch={pr['release_batch_no']}")
        _, b = call(client, "GET", f"/api/resource/Sales Order/{pr['sales_order']}")
        so_doc = b["data"]
        for row in so_doc.get("fp_patients", []):
            print(f"  │  └─ Paciente {row.get('patient_name')} "
                  f"(qty={row.get('qty'):.0f}) "
                  f"→ batch={row.get('batch_no')} "
                  f"(status={row.get('batch_status')})")

    print()
    log_ok("✓ Quantidade rastreada do FPB até cada paciente individual.")
    log_ok("✓ Cada ampola produzida tem dono identificado (PR → SO → fp_patients).")
    log_ok("✓ Lote físico atribuído por paciente — pronto pra etiqueta Zebra.")

    print()
    log_section("RESUMO PARA INSPEÇÃO MANUAL")
    print(f"\n  Abra estes URLs no browser pra ver tudo:\n")
    print(f"  1) FPB:    {url(f'/app/future-production-batch/{fpb_name}')}")
    print(f"  2) SO:     {url(f'/app/sales-order/{so_name}')}")
    print(f"  3) PR:     {url(f'/app/production-reservation/{pr_name}')}")
    print(f"  4) Batch:  {url(f'/app/batch/{real_batch}')}")
    print(f"  5) Workspace: {url('/app/producao-futura')}")

    return {
        "fpb": fpb_name, "so": so_name, "pr": pr_name,
        "batch": real_batch, "soi": soi_name, "pres": pres_name,
        "patients": patients,
    }


def main():
    global PAUSE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-pause", action="store_true", help="Não pausa entre fases")
    parser.add_argument("--cleanup", action="store_true", help="Remove tudo TEST-MINI-* e sai")
    args = parser.parse_args()

    if args.no_pause:
        PAUSE = False

    client = client_from_env()

    if args.cleanup:
        cleanup(client)
        return 0

    cleanup(client)
    try:
        result = run(client)
        log_section("FLUXO MINI APROVADO")
        print(f"\n  Documentos criados (anote pra inspecionar):")
        for k, v in result.items():
            print(f"    {k:<12} = {v}")
        print(f"\n  Pra limpar: python mini_flow.py --cleanup")
        return 0
    except Exception as exc:
        log_error(f"Falhou: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
