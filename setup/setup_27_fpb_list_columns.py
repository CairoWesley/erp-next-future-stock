"""
setup_27_fpb_list_columns.py — mostra Reservada + Disponível na lista do FPB.

Adiciona as colunas "Quantidade Reservada" (reserved_qty) e "Quantidade
Disponível" (available_qty) na List View de Future Production Batch, via
Property Setter (in_list_view=1). Idempotente.

Uso:
    python setup/setup_27_fpb_list_columns.py
    python setup/setup_27_fpb_list_columns.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section

DOCTYPE = "Future Production Batch"
# (fieldname, columns width) — mostra na lista
LIST_FIELDS = [("reserved_qty", 1), ("available_qty", 1)]
# tira da lista pra caber as quantidades (Frappe limita o total de colunas)
HIDE_FROM_LIST = ["planned_production_date"]


def _upsert_ps(c, field, prop, ptype, value):
    existing = c.property_setter_exists(DOCTYPE, field, prop)
    if existing:
        c._request("PUT", "/api/resource/Property Setter/" + existing.replace(" ", "%20"),
                   json_body={"value": str(value)})
        log_ok(f"PS {DOCTYPE}.{field}.{prop} = {value} (atualizado)")
    else:
        c._request("POST", "/api/resource/Property Setter", json_body={
            "doctype": "Property Setter", "doctype_or_field": "DocField",
            "doc_type": DOCTYPE, "field_name": field, "property": prop,
            "property_type": ptype, "value": str(value)})
        log_ok(f"PS {DOCTYPE}.{field}.{prop} = {value} (criado)")


def install() -> int:
    c = client_from_env()
    log_section("Colunas Reservada + Disponível na lista do FPB")
    rc = 0
    for field, cols in LIST_FIELDS:
        try:
            _upsert_ps(c, field, "in_list_view", "Check", 1)
            if cols:
                _upsert_ps(c, field, "columns", "Int", cols)
        except Exception as exc:  # noqa: BLE001
            log_error(f"{field}: {exc}")
            rc = 1
    for field in HIDE_FROM_LIST:
        try:
            _upsert_ps(c, field, "in_list_view", "Check", 0)
        except Exception as exc:  # noqa: BLE001
            log_error(f"{field}: {exc}")
    # limpa cache pra refletir na lista
    try:
        c._request("POST", "/api/method/frappe.client.get_count",
                   json_body={"doctype": DOCTYPE})
    except Exception:
        pass
    return rc


def uninstall() -> int:
    c = client_from_env()
    for field, _ in LIST_FIELDS:
        for prop in ("in_list_view", "columns"):
            ex = c.property_setter_exists(DOCTYPE, field, prop)
            if ex:
                try:
                    c._request("DELETE", "/api/resource/Property Setter/" + ex.replace(" ", "%20"))
                except Exception as exc:  # noqa: BLE001
                    log_error(f"{field}.{prop}: {exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
