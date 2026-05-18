"""
tools/deep_cleanup.py — Remove TODOS documentos de teste do banco.

Procura por prefixos comuns de teste (TEST-*, DEMO-*) em todas as entidades
e remove em ordem de dependência (PR → SO → FPB → Batch → Patient →
Prescriber → Customer).

Uso:
    python tools/deep_cleanup.py             # confirma antes
    python tools/deep_cleanup.py --yes       # roda sem confirmar
    python tools/deep_cleanup.py --tag X     # tag específica
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import quote

sys.path.insert(0, ".")

from lib.erpnext_api import (
    ErpnextApiError,
    client_from_env,
    log_error,
    log_ok,
    log_section,
)


TAGS = ["TEST-", "DEMO-"]


def call(client, method, path, **kwargs):
    return client._request(method, path, **kwargs)


def cancel(client, doctype, name):
    try:
        call(client, "POST", "/api/method/frappe.client.cancel",
             json_body={"doctype": doctype, "name": name})
    except ErpnextApiError as exc:
        msg = str(exc)
        if "Cancelled" in msg or "Not Submitted" in msg or "已" in msg:
            pass
        else:
            raise


def find_by_prefix(client, doctype: str, field: str, prefixes: list[str]) -> list[dict]:
    """Acha docs onde `field` começa com qualquer prefixo."""
    or_filters = json.dumps([[field, "like", f"{p}%"] for p in prefixes])
    try:
        _, body = call(client, "GET", f"/api/resource/{doctype}",
                       params={"or_filters": or_filters,
                               "fields": json.dumps(["name", "docstatus", field]),
                               "limit_page_length": 1000})
        return (body or {}).get("data") or []
    except ErpnextApiError as exc:
        log_error(f"  Falha listar {doctype}: {exc}")
        return []


def delete_doc(client, doctype: str, name: str, submitted: bool):
    try:
        if submitted:
            cancel(client, doctype, name)
        call(client, "DELETE", f"/api/resource/{doctype}/{quote(name, safe='')}")
        return True
    except ErpnextApiError as exc:
        log_error(f"    Falha {doctype}/{name}: {exc}")
        return False


def cleanup(client, prefixes: list[str]) -> dict:
    counts = {}

    # 1. Production Reservations (dependem de SO e FPB)
    log_section("1/7 — Production Reservations")
    # Acha PRs de SOs com prefixo
    sos = find_by_prefix(client, "Sales Order", "customer", prefixes)
    sos_names = [s["name"] for s in sos]
    if sos_names:
        _, body = call(client, "GET", "/api/resource/Production Reservation",
                       params={"filters": json.dumps([["sales_order", "in", sos_names]]),
                               "fields": '["name","docstatus"]',
                               "limit_page_length": 2000})
        prs = (body or {}).get("data") or []
        log_ok(f"  Encontradas {len(prs)} PRs ligadas a SOs de teste")
        deleted = 0
        for pr in prs:
            if delete_doc(client, "Production Reservation", pr["name"], pr.get("docstatus") == 1):
                deleted += 1
        counts["Production Reservation"] = deleted

    # 2. Sales Orders
    log_section("2/7 — Sales Orders")
    deleted = 0
    for s in sos:
        if delete_doc(client, "Sales Order", s["name"], s.get("docstatus") == 1):
            deleted += 1
    counts["Sales Order"] = deleted

    # 3. Future Production Batches (por production_code)
    log_section("3/7 — Future Production Batches")
    fpbs = find_by_prefix(client, "Future Production Batch", "production_code", prefixes)
    deleted = 0
    for f in fpbs:
        if delete_doc(client, "Future Production Batch", f["name"], f.get("docstatus") == 1):
            deleted += 1
    counts["Future Production Batch"] = deleted

    # 4. Batches físicos
    log_section("4/7 — Batches físicos")
    batches = find_by_prefix(client, "Batch", "batch_id", prefixes)
    deleted = 0
    for b in batches:
        if delete_doc(client, "Batch", b["name"], False):
            deleted += 1
    counts["Batch"] = deleted

    # 5. Patients (por patient_name)
    log_section("5/7 — Patients")
    patients = find_by_prefix(client, "Patient", "patient_name", prefixes)
    deleted = 0
    for p in patients:
        if delete_doc(client, "Patient", p["name"], False):
            deleted += 1
    counts["Patient"] = deleted

    # 6. Prescribers (por full_name)
    log_section("6/7 — Prescribers")
    pres_list = find_by_prefix(client, "Prescriber", "full_name", prefixes)
    deleted = 0
    for p in pres_list:
        if delete_doc(client, "Prescriber", p["name"], False):
            deleted += 1
    counts["Prescriber"] = deleted

    # 7. Customers (por customer_name)
    log_section("7/7 — Customers")
    custs = find_by_prefix(client, "Customer", "customer_name", prefixes)
    deleted = 0
    for c in custs:
        if delete_doc(client, "Customer", c["name"], False):
            deleted += 1
    counts["Customer"] = deleted

    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true",
                        help="Pula confirmação")
    parser.add_argument("--tag", action="append",
                        help="Prefixo adicional (pode repetir). Default: TEST-, DEMO-")
    args = parser.parse_args()

    prefixes = args.tag if args.tag else TAGS

    client = client_from_env()

    log_section("Deep Cleanup")
    print(f"  Prefixos: {prefixes}")
    print("  Vai apagar PR/SO/FPB/Batch/Patient/Prescriber/Customer")
    print("  que comecem com esses prefixos.")
    print()

    if not args.yes:
        ans = input("  Confirma? (digite 'sim'): ")
        if ans.strip().lower() not in ("sim", "yes", "y"):
            print("  Cancelado.")
            return 0

    counts = cleanup(client, prefixes)

    log_section("RESUMO")
    total = 0
    for k, v in counts.items():
        print(f"  {k:<35} {v} removido(s)")
        total += v
    print(f"  {'TOTAL':<35} {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
