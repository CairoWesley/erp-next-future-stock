"""
diagnose.py — inspeciona o estado atual do ERPNext relacionado ao módulo
Reserva de Produção Futura.

Lista:
  - Companies cadastradas
  - Warehouses cadastrados (para target_warehouse)
  - Items com Maintain Stock = 1
  - Customers
  - Future Production Batches existentes
  - Production Reservations existentes
  - Sales Orders submetidos
  - Server Scripts do módulo (status enabled)
"""

from __future__ import annotations

import json

from lib.erpnext_api import client_from_env, log_section


def _list(client, doctype: str, *, fields: list[str], filters=None, limit: int = 10,
          order_by: str = "modified desc") -> list[dict]:
    params = {
        "fields": json.dumps(fields),
        "limit_page_length": limit,
        "order_by": order_by,
    }
    if filters:
        params["filters"] = json.dumps(filters)
    _, body = client._request("GET", f"/api/resource/{doctype}", params=params)
    return (body or {}).get("data") or []


def _print_table(rows: list[dict], cols: list[str]) -> None:
    if not rows:
        print("  (nenhum)")
        return
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    header = "  | ".join(c.ljust(widths[c]) for c in cols)
    print(f"  {header}")
    print(f"  {'-' * len(header)}")
    for r in rows:
        line = "  | ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols)
        print(f"  {line}")


def main() -> int:
    client = client_from_env()

    log_section("Companies")
    rows = _list(client, "Company", fields=["name", "abbr", "country"])
    _print_table(rows, ["name", "abbr", "country"])

    log_section("Warehouses (até 20)")
    rows = _list(client, "Warehouse",
                 fields=["name", "company", "is_group", "disabled"],
                 filters=[["disabled", "=", 0]], limit=20, order_by="name asc")
    _print_table(rows, ["name", "company", "is_group"])

    log_section("Items com estoque (até 15)")
    rows = _list(client, "Item",
                 fields=["name", "item_name", "stock_uom", "has_batch_no", "disabled"],
                 filters=[["disabled", "=", 0], ["is_stock_item", "=", 1]],
                 limit=15, order_by="creation desc")
    _print_table(rows, ["name", "item_name", "stock_uom", "has_batch_no"])

    log_section("Customers (até 10)")
    rows = _list(client, "Customer",
                 fields=["name", "customer_name", "customer_group", "disabled"],
                 filters=[["disabled", "=", 0]], limit=10, order_by="creation desc")
    _print_table(rows, ["name", "customer_name", "customer_group"])

    log_section("Sales Orders submetidos (até 10)")
    rows = _list(client, "Sales Order",
                 fields=["name", "customer", "status", "grand_total", "transaction_date"],
                 filters=[["docstatus", "=", 1]],
                 limit=10, order_by="creation desc")
    _print_table(rows, ["name", "customer", "status", "grand_total", "transaction_date"])

    log_section("Future Production Batches existentes")
    try:
        rows = _list(client, "Future Production Batch",
                     fields=["name", "production_code", "item_code", "planned_qty",
                             "reserved_qty", "available_qty", "produced_qty",
                             "released_qty", "status", "docstatus"],
                     limit=20)
        _print_table(rows, ["name", "production_code", "item_code", "planned_qty",
                            "reserved_qty", "available_qty", "produced_qty",
                            "released_qty", "status"])
    except Exception as exc:
        print(f"  ERRO: {exc}")

    log_section("Production Reservations existentes")
    try:
        rows = _list(client, "Production Reservation",
                     fields=["name", "sales_order", "customer", "item_code",
                             "future_production_batch", "reserved_qty",
                             "released_qty", "pending_qty", "status", "docstatus"],
                     limit=20)
        _print_table(rows, ["name", "sales_order", "customer", "item_code",
                            "future_production_batch", "reserved_qty",
                            "released_qty", "pending_qty", "status"])
    except Exception as exc:
        print(f"  ERRO: {exc}")

    log_section("Server Scripts do módulo")
    rows = _list(client, "Server Script",
                 fields=["name", "script_type", "doctype_event", "api_method",
                         "reference_doctype", "disabled"],
                 filters=[["name", "like", "%future_production%"]],
                 limit=20, order_by="name asc")
    _print_table(rows, ["name", "script_type", "doctype_event", "api_method", "disabled"])
    rows = _list(client, "Server Script",
                 fields=["name", "script_type", "doctype_event", "reference_doctype", "disabled"],
                 filters=[["reference_doctype", "in",
                          ["Future Production Batch", "Production Reservation"]]],
                 limit=20, order_by="name asc")
    _print_table(rows, ["name", "script_type", "doctype_event", "reference_doctype", "disabled"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
