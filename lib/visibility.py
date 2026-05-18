"""
lib/visibility.py — Funções de inspeção do estado do sistema.

Usado pelo smoke_test_large.py e pelo CLI tools/visibility_snapshot.py.
Imprime tabelas de FPBs, PRs, SOs e pendências para o operador validar
visualmente cada fase do processo.
"""

from __future__ import annotations

import json
from typing import Any

from lib.erpnext_api import log_ok, log_section


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(client, path: str, **params):
    return client._request("GET", path, params=params or None)


def _table(headers: list[str], rows: list[list[Any]], widths: list[int]) -> str:
    sep_line = "  +" + "+".join("-" * (w + 2) for w in widths) + "+"
    out = [sep_line]
    header_line = "  | " + " | ".join(
        f"{str(h)[:w]:<{w}}" for h, w in zip(headers, widths)
    ) + " |"
    out.append(header_line)
    out.append(sep_line)
    for r in rows:
        line = "  | " + " | ".join(
            f"{str(cell)[:w]:<{w}}" for cell, w in zip(r, widths)
        ) + " |"
        out.append(line)
    out.append(sep_line)
    return "\n".join(out)


def _fmt(value: Any, decimals: int = 0) -> str:
    if value is None or value == "":
        return "-"
    try:
        v = float(value)
        if decimals == 0:
            return f"{v:.0f}"
        return f"{v:.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# FPB visibility
# ---------------------------------------------------------------------------

def list_fpbs(
    client,
    item_code: str | None = None,
    code_prefix: str | None = None,
    only_with_balance: bool = False,
) -> list[dict]:
    """Lista FPBs submetidos com filtros opcionais."""
    filters: list[list] = [["docstatus", "=", 1]]
    if item_code:
        filters.append(["item_code", "=", item_code])
    if code_prefix:
        filters.append(["production_code", "like", f"{code_prefix}%"])
    if only_with_balance:
        filters.append(["available_qty", ">", 0])

    _, body = _get(
        client,
        "/api/resource/Future Production Batch",
        fields=json.dumps([
            "name", "production_code", "item_code", "status",
            "planned_qty", "reserved_qty", "available_qty",
            "produced_qty", "released_qty", "pending_release_qty",
            "planned_production_date", "batch_no",
        ]),
        filters=json.dumps(filters),
        order_by="planned_production_date asc, creation asc",
        limit_page_length=500,
    )
    return (body or {}).get("data") or []


def print_fpb_table(fpbs: list[dict], title: str = "Future Production Batches") -> None:
    log_section(title)
    if not fpbs:
        print("  (vazio)")
        return

    rows = []
    totals = {"planned": 0.0, "reserved": 0.0, "available": 0.0,
              "produced": 0.0, "released": 0.0, "pending": 0.0}
    for f in fpbs:
        rows.append([
            f.get("name", ""),
            f.get("production_code", ""),
            f.get("item_code", ""),
            _fmt(f.get("planned_qty")),
            _fmt(f.get("reserved_qty")),
            _fmt(f.get("available_qty")),
            _fmt(f.get("produced_qty")),
            _fmt(f.get("released_qty")),
            _fmt(f.get("pending_release_qty")),
            (f.get("status") or "")[:22],
            (f.get("batch_no") or "-")[:20],
        ])
        for k, key in (("planned", "planned_qty"), ("reserved", "reserved_qty"),
                       ("available", "available_qty"), ("produced", "produced_qty"),
                       ("released", "released_qty"), ("pending", "pending_release_qty")):
            try:
                totals[k] += float(f.get(key) or 0)
            except (TypeError, ValueError):
                pass

    print(_table(
        ["FPB", "Código", "Item", "Plan", "Reserv", "Disp",
         "Prod", "Liber", "Pend", "Status", "Batch"],
        rows,
        [18, 20, 10, 6, 6, 6, 6, 6, 5, 22, 20],
    ))
    print(f"\n  TOTAL ({len(fpbs)} FPBs):")
    print(f"    planned   = {totals['planned']:>10.0f}")
    print(f"    reserved  = {totals['reserved']:>10.0f}")
    print(f"    available = {totals['available']:>10.0f}")
    print(f"    produced  = {totals['produced']:>10.0f}")
    print(f"    released  = {totals['released']:>10.0f}")
    print(f"    pending   = {totals['pending']:>10.0f}")


# ---------------------------------------------------------------------------
# Production Reservation visibility
# ---------------------------------------------------------------------------

def list_prs_by_fpbs(client, fpb_names: list[str]) -> list[dict]:
    if not fpb_names:
        return []
    _, body = _get(
        client,
        "/api/resource/Production Reservation",
        fields=json.dumps([
            "name", "sales_order", "customer", "future_production_batch",
            "item_code", "reserved_qty", "released_qty", "pending_qty",
            "status", "priority", "release_batch_no",
        ]),
        filters=json.dumps([["future_production_batch", "in", fpb_names]]),
        order_by="future_production_batch asc, priority asc, creation asc",
        limit_page_length=2000,
    )
    return (body or {}).get("data") or []


def print_pr_table(prs: list[dict], title: str = "Production Reservations") -> None:
    log_section(title)
    if not prs:
        print("  (vazio)")
        return

    rows = []
    totals = {"reserved": 0.0, "released": 0.0, "pending": 0.0}
    for p in prs:
        rows.append([
            p.get("name", ""),
            (p.get("future_production_batch") or "")[:18],
            (p.get("sales_order") or "")[:22],
            (p.get("customer") or "")[:18],
            _fmt(p.get("reserved_qty")),
            _fmt(p.get("released_qty")),
            _fmt(p.get("pending_qty")),
            (p.get("status") or "")[:22],
            (p.get("release_batch_no") or "-")[:18],
        ])
        for k, key in (("reserved", "reserved_qty"), ("released", "released_qty"),
                       ("pending", "pending_qty")):
            try:
                totals[k] += float(p.get(key) or 0)
            except (TypeError, ValueError):
                pass

    print(_table(
        ["PR", "FPB", "SO", "Cliente",
         "Reserv", "Liber", "Pend", "Status", "Release Batch"],
        rows,
        [18, 18, 22, 18, 6, 6, 5, 22, 18],
    ))
    print(f"\n  TOTAL ({len(prs)} PRs):")
    print(f"    reserved = {totals['reserved']:>10.0f}")
    print(f"    released = {totals['released']:>10.0f}")
    print(f"    pending  = {totals['pending']:>10.0f}")


# ---------------------------------------------------------------------------
# Pendências (PRs com pending > 0)
# ---------------------------------------------------------------------------

def list_pending_prs(client) -> list[dict]:
    _, body = _get(
        client,
        "/api/resource/Production Reservation",
        fields=json.dumps([
            "name", "sales_order", "customer", "future_production_batch",
            "item_code", "reserved_qty", "released_qty", "pending_qty",
            "status", "priority",
        ]),
        filters=json.dumps([
            ["docstatus", "=", 1],
            ["pending_qty", ">", 0],
        ]),
        order_by="priority asc, creation asc",
        limit_page_length=2000,
    )
    return (body or {}).get("data") or []


# ---------------------------------------------------------------------------
# Sales Order summary
# ---------------------------------------------------------------------------

def list_sos_by_prefix(client, customer_prefix: str) -> list[dict]:
    _, body = _get(
        client,
        "/api/resource/Sales Order",
        fields=json.dumps([
            "name", "customer", "transaction_date", "delivery_date",
            "status", "docstatus", "grand_total",
        ]),
        filters=json.dumps([["customer", "like", f"{customer_prefix}%"]]),
        order_by="creation asc",
        limit_page_length=500,
    )
    return (body or {}).get("data") or []


def print_so_table(sos: list[dict], title: str = "Sales Orders") -> None:
    log_section(title)
    if not sos:
        print("  (vazio)")
        return

    rows = []
    total_value = 0.0
    for s in sos:
        rows.append([
            s.get("name", ""),
            (s.get("customer") or "")[:20],
            s.get("transaction_date") or "-",
            s.get("delivery_date") or "-",
            (s.get("status") or "")[:18],
            _fmt(s.get("grand_total"), 2),
        ])
        try:
            total_value += float(s.get("grand_total") or 0)
        except (TypeError, ValueError):
            pass

    print(_table(
        ["SO", "Cliente", "Data", "Entrega", "Status", "Total R$"],
        rows,
        [22, 20, 12, 12, 18, 12],
    ))
    print(f"\n  TOTAL ({len(sos)} SOs): R$ {total_value:,.2f}")


# ---------------------------------------------------------------------------
# Hints de visibilidade — URLs UI + endpoints API
# ---------------------------------------------------------------------------

def print_visibility_hints(
    erp_url: str,
    *,
    item_code: str | None = None,
    code_prefix: str | None = None,
    fpb_names: list[str] | None = None,
    so_names: list[str] | None = None,
) -> None:
    log_section("VISIBILIDADE — APIs e URLs para inspecionar agora")

    base = erp_url.rstrip("/")

    print("\n  ╔══════════════════════════════════════════════════════════╗")
    print("    1) FPBs (Lotes de Produção Futura)")
    print("  ╚══════════════════════════════════════════════════════════╝\n")

    api_filters = [["docstatus", "=", 1]]
    if item_code:
        api_filters.append(["item_code", "=", item_code])
    if code_prefix:
        api_filters.append(["production_code", "like", f"{code_prefix}%"])

    print(f"  UI Lista:      {base}/app/future-production-batch")
    if code_prefix:
        print(f"                 filtro production_code LIKE '{code_prefix}%'")
    print(f"  UI Workspace:  {base}/app/producao-futura")
    print(f"  API:")
    print(f"    GET {base}/api/resource/Future Production Batch")
    print(f"      ?fields=[\"name\",\"production_code\",\"planned_qty\",\"available_qty\",\"status\"]")
    print(f"      &filters={json.dumps(api_filters)}")

    if fpb_names:
        print(f"\n  Detalhe de FPB específico (UI):")
        for name in fpb_names[:3]:
            print(f"    {base}/app/future-production-batch/{name}")
        if len(fpb_names) > 3:
            print(f"    ... e mais {len(fpb_names) - 3}")

    print("\n  ╔══════════════════════════════════════════════════════════╗")
    print("    2) Reservas (PRs)")
    print("  ╚══════════════════════════════════════════════════════════╝\n")

    print(f"  UI Lista:      {base}/app/production-reservation")
    if fpb_names:
        pr_filter = [["future_production_batch", "in", fpb_names]]
        print(f"                 filtro future_production_batch in [...]")
        print(f"  API:")
        print(f"    GET {base}/api/resource/Production Reservation")
        print(f"      ?filters={json.dumps(pr_filter)}")

    print("\n  ╔══════════════════════════════════════════════════════════╗")
    print("    3) Pedidos de Venda (SOs)")
    print("  ╚══════════════════════════════════════════════════════════╝\n")

    print(f"  UI Lista:      {base}/app/sales-order")
    if so_names:
        print(f"  Detalhe (3 primeiros):")
        for name in so_names[:3]:
            print(f"    {base}/app/sales-order/{name}")

    print("\n  ╔══════════════════════════════════════════════════════════╗")
    print("    4) Pendências de Liberação (Report)")
    print("  ╚══════════════════════════════════════════════════════════╝\n")

    print(f"  UI Report:     {base}/app/query-report/Pedidos%20Pendentes%20de%20Liberação")
    print(f"  API Pendentes:")
    print(f"    GET {base}/api/resource/Production Reservation")
    print(f"      ?filters=[[\"docstatus\",\"=\",1],[\"pending_qty\",\">\",0]]")
    print(f"      &fields=[\"name\",\"sales_order\",\"future_production_batch\",\"pending_qty\"]")

    print("\n  ╔══════════════════════════════════════════════════════════╗")
    print("    5) Saldo por Lote (Report nativo)")
    print("  ╚══════════════════════════════════════════════════════════╝\n")

    print(f"  UI Report:     {base}/app/query-report/Saldo%20por%20Lote")
    print(f"  UI Stock:      {base}/app/stock-balance")
    if item_code:
        print(f"                 filtro item_code={item_code}")
