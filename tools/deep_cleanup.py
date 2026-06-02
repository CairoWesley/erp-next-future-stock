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


def find_all(client, doctype: str, field: str) -> list[dict]:
    """Lista TODOS os docs do doctype (modo --all = 100%)."""
    try:
        _, body = call(client, "GET", f"/api/resource/{doctype}",
                       params={"fields": json.dumps(["name", "docstatus", field]),
                               "limit_page_length": 0})
        return (body or {}).get("data") or []
    except ErpnextApiError as exc:
        log_error(f"  Falha listar {doctype}: {exc}")
        return []


def find(client, doctype: str, field: str, prefixes: list[str], all_mode: bool) -> list[dict]:
    if all_mode:
        return find_all(client, doctype, field)
    return find_by_prefix(client, doctype, field, prefixes)


def delete_doc(client, doctype: str, name: str, submitted: bool):
    try:
        if submitted:
            cancel(client, doctype, name)
        call(client, "DELETE", f"/api/resource/{doctype}/{quote(name, safe='')}")
        return True
    except ErpnextApiError as exc:
        log_error(f"    Falha {doctype}/{name}: {exc}")
        return False


def cleanup(client, prefixes: list[str], all_mode: bool = False) -> dict:
    counts = {}

    # 1. Production Reservations (dependem de SO e FPB)
    log_section("1/7 — Production Reservations")
    sos = find(client, "Sales Order", "customer", prefixes, all_mode)
    sos_names = [s["name"] for s in sos]
    if all_mode:
        prs = find_all(client, "Production Reservation", "name")
    elif sos_names:
        _, body = call(client, "GET", "/api/resource/Production Reservation",
                       params={"filters": json.dumps([["sales_order", "in", sos_names]]),
                               "fields": '["name","docstatus"]',
                               "limit_page_length": 5000})
        prs = (body or {}).get("data") or []
    else:
        prs = []
    log_ok(f"  Encontradas {len(prs)} PRs")
    deleted = 0
    for pr in prs:
        if delete_doc(client, "Production Reservation", pr["name"], pr.get("docstatus") == 1):
            deleted += 1
    counts["Production Reservation"] = deleted

    # 1b. Dispensações — apagar antes dos SOs (referenciam SOs)
    log_section("1b/7 — Dispensacoes")
    if all_mode:
        disps = find_all(client, "Dispensacao", "name")
    elif sos_names:
        _, body = call(client, "GET", "/api/resource/Dispensacao",
                       params={"filters": json.dumps([["sales_order", "in", sos_names]]),
                               "fields": '["name","docstatus"]',
                               "limit_page_length": 5000})
        disps = (body or {}).get("data") or []
    else:
        disps = []
    log_ok(f"  Encontradas {len(disps)} Dispensacoes")
    deleted = 0
    for d in disps:
        if delete_doc(client, "Dispensacao", d["name"], d.get("docstatus") == 1):
            deleted += 1
    counts["Dispensacao"] = deleted

    # 2. Sales Orders
    log_section("2/7 — Sales Orders")
    deleted = 0
    for s in sos:
        if delete_doc(client, "Sales Order", s["name"], s.get("docstatus") == 1):
            deleted += 1
    counts["Sales Order"] = deleted

    # 3. Future Production Batches (por production_code)
    log_section("3/7 — Future Production Batches")
    fpbs = find(client, "Future Production Batch", "production_code", prefixes, all_mode)
    deleted = 0
    for f in fpbs:
        if delete_doc(client, "Future Production Batch", f["name"], f.get("docstatus") == 1):
            deleted += 1
    counts["Future Production Batch"] = deleted

    # 4. Batches físicos
    log_section("4/7 — Batches físicos")
    batches = find(client, "Batch", "batch_id", prefixes, all_mode)
    deleted = 0
    for b in batches:
        if delete_doc(client, "Batch", b["name"], False):
            deleted += 1
    counts["Batch"] = deleted

    # 5. Patients (por patient_name)
    log_section("5/7 — Patients")
    patients = find(client, "Patient", "patient_name", prefixes, all_mode)
    deleted = 0
    for p in patients:
        if delete_doc(client, "Patient", p["name"], False):
            deleted += 1
    counts["Patient"] = deleted

    # 6. Prescribers (por full_name)
    log_section("6/7 — Prescribers")
    pres_list = find(client, "Prescriber", "full_name", prefixes, all_mode)
    deleted = 0
    for p in pres_list:
        if delete_doc(client, "Prescriber", p["name"], False):
            deleted += 1
    counts["Prescriber"] = deleted

    # 7. Customers (por customer_name)
    log_section("7/7 — Customers")
    custs = find(client, "Customer", "customer_name", prefixes, all_mode)
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
    parser.add_argument("--all", action="store_true",
                        help="Apaga TODOS os registros (100%%), ignorando prefixos. Mantem a Company.")
    args = parser.parse_args()

    prefixes = args.tag if args.tag else TAGS

    client = client_from_env()

    log_section("Deep Cleanup")
    if args.all:
        print("  MODO --all: vai apagar TODOS os registros (100%) de")
        print("  PR / Dispensacao / SO / FPB / Batch / Patient / Prescriber / Customer.")
        print("  A Company (empresa) NAO e tocada. ACAO IRREVERSIVEL.")
    else:
        print(f"  Prefixos: {prefixes}")
        print("  Vai apagar PR/Dispensacao/SO/FPB/Batch/Patient/Prescriber/Customer")
        print("  que comecem com esses prefixos.")
    print()

    if not args.yes:
        ans = input("  Confirma? (digite 'sim'): ")
        if ans.strip().lower() not in ("sim", "yes", "y"):
            print("  Cancelado.")
            return 0

    counts = cleanup(client, prefixes, args.all)

    log_section("RESUMO")
    total = 0
    for k, v in counts.items():
        print(f"  {k:<35} {v} removido(s)")
        total += v
    print(f"  {'TOTAL':<35} {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
