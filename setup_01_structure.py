"""
setup_01_structure.py — cria a estrutura de dados do módulo.

Cria:
  1. DocType Future Production Batch
  2. DocType Production Reservation
  3. Custom Fields no Sales Order Item (prefixo fp_)

Idempotente: se já existe, pula. (Para reinstalar, rode --uninstall antes.)

Uso:
    python setup_01_structure.py
    python setup_01_structure.py --uninstall
"""

from __future__ import annotations

import sys

from lib.erpnext_api import client_from_env, log_error, log_section
from lib.payloads import (
    FUTURE_PRODUCTION_BATCH,
    PRODUCTION_RESERVATION,
    SALES_ORDER_ITEM_FIELDS,
)


def install() -> int:
    client = client_from_env()

    log_section("1/3 — DocType Future Production Batch")
    try:
        client.create_doctype(FUTURE_PRODUCTION_BATCH)
    except Exception as exc:
        log_error(f"Future Production Batch: {exc}")
        return 1

    log_section("2/3 — DocType Production Reservation")
    try:
        client.create_doctype(PRODUCTION_RESERVATION)
    except Exception as exc:
        log_error(f"Production Reservation: {exc}")
        return 1

    log_section("3/3 — Custom Fields em Sales Order Item")
    errors = 0
    for field in SALES_ORDER_ITEM_FIELDS:
        try:
            client.create_custom_field(field)
        except Exception as exc:
            log_error(f"Custom Field {field['dt']}.{field['fieldname']}: {exc}")
            errors += 1
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()

    log_section("Removendo Custom Fields de Sales Order Item")
    for field in reversed(SALES_ORDER_ITEM_FIELDS):
        try:
            client.delete_custom_field(field["dt"], field["fieldname"])
        except Exception as exc:
            log_error(f"Falha ao remover {field['dt']}.{field['fieldname']}: {exc}")

    log_section("Removendo DocType Production Reservation")
    try:
        client.delete_doctype("Production Reservation")
    except Exception as exc:
        log_error(f"Falha ao remover Production Reservation: {exc}")

    log_section("Removendo DocType Future Production Batch")
    try:
        client.delete_doctype("Future Production Batch")
    except Exception as exc:
        log_error(f"Falha ao remover Future Production Batch: {exc}")

    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
