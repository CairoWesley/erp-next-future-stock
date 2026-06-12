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
# mostra na lista (in_list_view=1): Código(title) + Planejada + Reservada + Disponível
LIST_FIELDS = [("planned_qty", 2), ("reserved_qty", 2), ("available_qty", 2)]
# tira da lista (fica no form). Status + Produto + Data fora.
HIDE_FROM_LIST = ["planned_production_date", "status", "item_code"]
COLUMN_WIDTHS = {"planned_qty": 2, "reserved_qty": 2, "available_qty": 2}

# Client Script (List) — esconde a coluna ID (name)
CLIENT_SCRIPT_NAME = "Future Production Batch - List Clean"
CLIENT_SCRIPT = (
    "frappe.listview_settings['Future Production Batch'] = "
    "Object.assign(frappe.listview_settings['Future Production Batch'] || {}, "
    "{ hide_name_column: true });"
)


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
    for field, cols in COLUMN_WIDTHS.items():
        try:
            _upsert_ps(c, field, "columns", "Int", cols)
        except Exception as exc:  # noqa: BLE001
            log_error(f"{field}.columns: {exc}")
    # Client Script (List): esconde coluna ID
    try:
        enc = CLIENT_SCRIPT_NAME.replace(" ", "%20")
        if c._request("GET", "/api/resource/Client Script/" + enc)[1] is not None:
            c._request("DELETE", "/api/resource/Client Script/" + enc)
        c._request("POST", "/api/resource/Client Script", json_body={
            "doctype": "Client Script", "name": CLIENT_SCRIPT_NAME,
            "dt": DOCTYPE, "view": "List", "enabled": 1, "script": CLIENT_SCRIPT})
        log_ok("Client Script (esconde coluna ID) pronto.")
    except Exception as exc:  # noqa: BLE001
        log_error(f"Client Script ID: {exc}")
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
