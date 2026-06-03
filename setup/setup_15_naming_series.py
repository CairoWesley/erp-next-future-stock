"""
setup_15_naming_series.py — força autoname auto-incremental (puro número
zero-padded) em todos DocTypes operacionais.

Convenção Injemedpharma: nada de prefixo, nada de ano. Só sequência:
    00001, 00002, 00003, ...

Cada DocType tem seu próprio contador (Customer 00001 != Patient 00001).

## Estratégia por categoria

DocTypes CUSTOM (sem hook nativo de naming):
    - Aplica Property Setter `autoname = format:{#####}` no DocType.
    - Override total. Funciona direto.
    - Ex: Future Production Batch, Production Reservation, Prescriber, Dispensacao

DocTypes NATIVOS com field `naming_series`:
    - Property Setter no field: options = ".#####" + default = ".#####"
    - Usuário enxerga single option no dropdown e ela vira a default.
    - Ex: Sales Order, Delivery Note, Sales Invoice, Payment Entry, Stock Entry, Patient

DocTypes NATIVOS com Settings master (cust_master_name):
    - Configura Settings pra usar Naming Series ao invés de Document Name.
    - + Property Setter no field naming_series.
    - Ex: Customer (Selling Settings.cust_master_name = "Naming Series")

DocTypes auxiliares (Address, Contact, Sales Person):
    - Naming hardcoded em Python — Property Setter ignorado.
    - Deixados com naming default do ERPNext (não impacta operação).

Idempotente. Registros existentes mantêm o nome antigo.

Uso:
    python setup/setup_15_naming_series.py
    python setup/setup_15_naming_series.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import sys
from urllib.parse import quote

from lib.erpnext_api import (
    ErpnextClient,
    client_from_env,
    log_creating,
    log_error,
    log_ok,
    log_section,
    log_skip,
)


# Custom DocTypes (criados por nós) — aceitam autoname Property Setter direto.
CUSTOM_DOCTYPES: list[str] = [
    "Future Production Batch",
    "Production Reservation",
    "Prescriber",
    "Dispensacao",
]

# Nativos com field `naming_series` — config via Property Setter no field.
NATIVE_WITH_NAMING_SERIES: list[str] = [
    "Sales Order",
    "Delivery Note",
    "Sales Invoice",
    "Payment Entry",
    "Stock Entry",
    "Patient",
    "Customer",  # também precisa Selling Settings (abaixo)
    "Item",      # SKU auto-gerado, requer Stock Settings (abaixo)
]

# Settings singletons que precisam apontar pra Naming Series.
SETTINGS_OVERRIDES: list[tuple[str, dict]] = [
    ("Selling Settings", {"cust_master_name": "Naming Series"}),
    ("Stock Settings", {"item_naming_by": "Naming Series"}),
]

AUTONAME_VALUE = "format:{#####}"
SERIES_PATTERN = ".#####"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert_property_setter(
    c: ErpnextClient,
    doc_type: str,
    property_name: str,
    value: str,
    property_type: str = "Data",
    field_name: str = "",
) -> None:
    existing = c.property_setter_exists(doc_type, field_name, property_name)
    payload = {
        "doctype": "Property Setter",
        "doctype_or_field": "DocField" if field_name else "DocType",
        "doc_type": doc_type,
        "field_name": field_name or None,
        "property": property_name,
        "value": value,
        "property_type": property_type,
    }
    label = f"{doc_type}.{field_name or '<doctype>'}.{property_name}"
    if existing:
        log_creating(f"Atualizando Property Setter {label}")
        c._request(
            "PUT",
            f"/api/resource/Property Setter/{quote(existing, safe='')}",
            json_body=payload,
        )
        log_ok(f"Property Setter {label} atualizado")
        return
    log_creating(f"Property Setter {label} = {value!r}")
    c._request("POST", "/api/resource/Property Setter", json_body=payload)
    log_ok(f"Property Setter {label} criado")


def _delete_property_setter(
    c: ErpnextClient,
    doc_type: str,
    property_name: str,
    field_name: str = "",
) -> bool:
    existing = c.property_setter_exists(doc_type, field_name, property_name)
    if not existing:
        log_skip(
            f"Property Setter {doc_type}.{field_name or '<doctype>'}.{property_name} não existe"
        )
        return False
    log_creating(
        f"Removendo Property Setter {doc_type}.{field_name or '<doctype>'}.{property_name}"
    )
    c._request("DELETE", f"/api/resource/Property Setter/{quote(existing, safe='')}")
    log_ok(f"Property Setter {doc_type}.{field_name or '<doctype>'}.{property_name} removido")
    return True


def _update_singleton(c: ErpnextClient, doctype: str, updates: dict) -> None:
    log_creating(f"Atualizando {doctype}: {updates}")
    c._request(
        "PUT",
        f"/api/resource/{quote(doctype, safe='')}/{quote(doctype, safe='')}",
        json_body=updates,
    )
    log_ok(f"{doctype} atualizado")


# ---------------------------------------------------------------------------
# install / uninstall
# ---------------------------------------------------------------------------

def install() -> int:
    log_section("Naming Series — auto-increment puro (format:{#####})")
    c = client_from_env()
    user = c.ping()
    log_ok(f"Conectado como {user}")

    failed: list[str] = []

    # 1) Custom DocTypes — autoname Property Setter no DocType
    log_section("1/3 — DocTypes custom (autoname override)")
    for dt in CUSTOM_DOCTYPES:
        try:
            _upsert_property_setter(c, dt, "autoname", AUTONAME_VALUE)
        except Exception as exc:  # noqa: BLE001
            log_error(f"{dt}: {exc}")
            failed.append(dt)

    # 2) Nativos com field naming_series — Property Setter no field
    log_section("2/3 — DocTypes nativos com field naming_series")
    for dt in NATIVE_WITH_NAMING_SERIES:
        try:
            _upsert_property_setter(
                c, dt, "options", SERIES_PATTERN,
                property_type="Text", field_name="naming_series",
            )
            _upsert_property_setter(
                c, dt, "default", SERIES_PATTERN,
                property_type="Text", field_name="naming_series",
            )
        except Exception as exc:  # noqa: BLE001
            log_error(f"{dt}: {exc}")
            failed.append(dt)

    # 3) Settings singletons
    log_section("3/3 — Settings singletons")
    for singleton, updates in SETTINGS_OVERRIDES:
        try:
            _update_singleton(c, singleton, updates)
        except Exception as exc:  # noqa: BLE001
            log_error(f"{singleton}: {exc}")
            failed.append(singleton)

    log_section("Resumo")
    if failed:
        log_error(f"Com erro: {', '.join(failed)}")
        return 1

    log_ok(f"{len(CUSTOM_DOCTYPES)} customs + {len(NATIVE_WITH_NAMING_SERIES)} nativos + {len(SETTINGS_OVERRIDES)} settings")
    log_ok("Próximos registros saem no formato 00001, 00002, ...")
    return 0


def uninstall() -> int:
    log_section("Naming Series — removendo overrides")
    c = client_from_env()

    for dt in CUSTOM_DOCTYPES:
        try:
            _delete_property_setter(c, dt, "autoname")
        except Exception as exc:  # noqa: BLE001
            log_error(f"{dt}: {exc}")

    for dt in NATIVE_WITH_NAMING_SERIES:
        for prop in ("options", "default"):
            try:
                _delete_property_setter(c, dt, prop, field_name="naming_series")
            except Exception as exc:  # noqa: BLE001
                log_error(f"{dt}.{prop}: {exc}")

    # Settings: reverte cust_master_name pro default
    try:
        _update_singleton(c, "Selling Settings", {"cust_master_name": "Customer Name"})
    except Exception as exc:  # noqa: BLE001
        log_error(f"Selling Settings: {exc}")

    log_ok("Overrides removidos. ERPNext volta ao naming series padrão.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args(argv)
    return uninstall() if args.uninstall else install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
