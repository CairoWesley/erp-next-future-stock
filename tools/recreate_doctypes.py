"""
recreate_doctypes.py — limpa documentos de teste e recria os 2 DocTypes
com o novo schema (allow_on_submit nos campos calculados).
"""

from __future__ import annotations

import json

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section
from lib.payloads import FUTURE_PRODUCTION_BATCH, PRODUCTION_RESERVATION


def cancel_and_delete(client, doctype: str, name: str) -> None:
    s, body = client._request("GET", f"/api/resource/{doctype}/{name.replace(' ', '%20')}")
    if s != 200:
        return
    docstatus = body.get("data", {}).get("docstatus", 0)
    if docstatus == 1:
        try:
            client._request("POST", "/api/method/frappe.client.cancel",
                            json_body={"doctype": doctype, "name": name})
        except Exception as exc:
            log_error(f"  cancel({doctype}:{name}) → {exc}")
    try:
        client._request("DELETE", f"/api/resource/{doctype}/{name.replace(' ', '%20')}")
        log_ok(f"  deletado: {doctype} {name}")
    except Exception as exc:
        log_error(f"  delete({doctype}:{name}) → {exc}")


def list_all(client, doctype: str) -> list[dict]:
    _, body = client._request("GET", f"/api/resource/{doctype}",
                              params={"fields": '["name","docstatus"]',
                                      "limit_page_length": 200})
    return (body or {}).get("data") or []


def main() -> int:
    c = client_from_env()

    log_section("1. Cancela+deleta Production Reservations existentes")
    for d in list_all(c, "Production Reservation"):
        cancel_and_delete(c, "Production Reservation", d["name"])

    log_section("2. Cancela+deleta Future Production Batches existentes")
    for d in list_all(c, "Future Production Batch"):
        cancel_and_delete(c, "Future Production Batch", d["name"])

    log_section("3. Deleta DocType Production Reservation")
    try:
        c.delete_doctype("Production Reservation")
    except Exception as exc:
        log_error(f"  {exc}")

    log_section("4. Deleta DocType Future Production Batch")
    try:
        c.delete_doctype("Future Production Batch")
    except Exception as exc:
        log_error(f"  {exc}")

    log_section("5. Recria DocType Future Production Batch (novo schema)")
    c.create_doctype(FUTURE_PRODUCTION_BATCH)

    log_section("6. Recria DocType Production Reservation (novo schema)")
    c.create_doctype(PRODUCTION_RESERVATION)

    log_ok("DocTypes recriados com allow_on_submit nos campos calculados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
