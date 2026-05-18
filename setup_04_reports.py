"""
setup_04_reports.py — cria os 4 Reports operacionais (seção 20).

Tipo: Report Builder (criados via API com filtros e colunas padrão).
O usuário pode reordenar colunas, salvar variações e exportar normalmente.

Reports criados:
  1. Mapa de Produção Futura          (ref Future Production Batch)
  2. Reservas por Produção            (ref Production Reservation)
  3. Pedidos Pendentes de Liberação   (ref Production Reservation, filtro pending_qty > 0)
  4. Risco de Produção                (ref Future Production Batch, filtro de risco)

Uso:
    python setup_04_reports.py
    python setup_04_reports.py --uninstall
"""

from __future__ import annotations

import json
import os
import sys

from lib.erpnext_api import client_from_env, log_error, log_section


MODULE = os.environ.get("ERPNEXT_MODULE", "Manufacturing")


def _report(
    name: str,
    ref_doctype: str,
    *,
    columns: list[list[str]],
    filters: list[list] | None = None,
    sort_by: str = "modified",
    sort_order: str = "DESC",
) -> dict:
    """Monta o payload de um Report Builder."""
    json_config = {
        "columns": columns,
        "filters": filters or [],
        "sort_by": sort_by,
        "sort_order": sort_order,
        "sort_by_next": "",
        "sort_order_next": "ASC",
    }
    return {
        "doctype": "Report",
        "name": name,
        "report_name": name,
        "ref_doctype": ref_doctype,
        "report_type": "Report Builder",
        "is_standard": "No",
        "module": MODULE,
        "disabled": 0,
        "json": json.dumps(json_config, ensure_ascii=False),
    }


REPORTS = [
    # 20.1 — Mapa de Produção Futura
    _report(
        "Mapa de Produção Futura",
        "Future Production Batch",
        columns=[
            ["name", "Future Production Batch"],
            ["production_code", "Future Production Batch"],
            ["item_code", "Future Production Batch"],
            ["item_name", "Future Production Batch"],
            ["planned_production_date", "Future Production Batch"],
            ["planned_qty", "Future Production Batch"],
            ["reserved_qty", "Future Production Batch"],
            ["available_qty", "Future Production Batch"],
            ["produced_qty", "Future Production Batch"],
            ["released_qty", "Future Production Batch"],
            ["pending_release_qty", "Future Production Batch"],
            ["status", "Future Production Batch"],
        ],
        sort_by="planned_production_date",
        sort_order="ASC",
    ),

    # 20.2 — Reservas por Produção
    _report(
        "Reservas por Produção",
        "Production Reservation",
        columns=[
            ["future_production_batch", "Production Reservation"],
            ["sales_order", "Production Reservation"],
            ["customer", "Production Reservation"],
            ["item_code", "Production Reservation"],
            ["reserved_qty", "Production Reservation"],
            ["released_qty", "Production Reservation"],
            ["pending_qty", "Production Reservation"],
            ["priority", "Production Reservation"],
            ["status", "Production Reservation"],
        ],
        filters=[
            ["Production Reservation", "docstatus", "=", 1],
        ],
        sort_by="future_production_batch",
        sort_order="ASC",
    ),

    # 20.3 — Pedidos Pendentes de Liberação
    _report(
        "Pedidos Pendentes de Liberação",
        "Production Reservation",
        columns=[
            ["sales_order", "Production Reservation"],
            ["customer", "Production Reservation"],
            ["item_code", "Production Reservation"],
            ["reserved_qty", "Production Reservation"],
            ["released_qty", "Production Reservation"],
            ["pending_qty", "Production Reservation"],
            ["future_production_batch", "Production Reservation"],
            ["status", "Production Reservation"],
            ["priority", "Production Reservation"],
        ],
        filters=[
            ["Production Reservation", "docstatus", "=", 1],
            ["Production Reservation", "pending_qty", ">", 0],
            ["Production Reservation", "status", "in", ["Reservado", "Parcialmente Liberado"]],
        ],
        sort_by="priority",
        sort_order="ASC",
    ),

    # 20.4 — Risco de Produção
    _report(
        "Risco de Produção",
        "Future Production Batch",
        columns=[
            ["name", "Future Production Batch"],
            ["production_code", "Future Production Batch"],
            ["item_code", "Future Production Batch"],
            ["planned_production_date", "Future Production Batch"],
            ["planned_qty", "Future Production Batch"],
            ["reserved_qty", "Future Production Batch"],
            ["produced_qty", "Future Production Batch"],
            ["status", "Future Production Batch"],
            ["work_order", "Future Production Batch"],
        ],
        filters=[
            ["Future Production Batch", "docstatus", "=", 1],
            ["Future Production Batch", "status", "not in", [
                "Produzida Totalmente",
                "Liberada Totalmente",
                "Cancelada",
            ]],
            ["Future Production Batch", "planned_production_date", "<", "Today"],
        ],
        sort_by="planned_production_date",
        sort_order="ASC",
    ),
]


def install() -> int:
    client = client_from_env()
    errors = 0
    for payload in REPORTS:
        log_section(f"Report: {payload['name']}")
        try:
            client.upsert_report(payload)
        except Exception as exc:
            log_error(f"{payload['name']}: {exc}")
            errors += 1
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()
    for payload in reversed(REPORTS):
        log_section(f"Removendo Report: {payload['name']}")
        try:
            client.delete_report(payload["name"])
        except Exception as exc:
            log_error(f"{payload['name']}: {exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
