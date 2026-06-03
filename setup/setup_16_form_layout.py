"""
setup_16_form_layout.py — força visibilidade total nos forms críticos
Injemedpharma.

Convenção: nada de seção colapsada por default. Operador precisa enxergar
tudo (vendedor, taxas, termos, endereço, contato, pagamento) sem clicar
em "expandir".

Aplica Property Setters em sections/fields de:
    - Customer
    - Sales Order
    - Delivery Note
    - Sales Invoice
    - Payment Entry
    - Item
    - Patient (já parcialmente exposto via setup_06)
    - Prescriber

Operação: cada entry vira 1 Property Setter `(doc_type, field_name, property)`.

Idempotente. `--uninstall` remove todos PSs criados.

Uso:
    python setup/setup_16_form_layout.py
    python setup/setup_16_form_layout.py --uninstall
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


# Cada entry: (doc_type, field_name, property_name, value, property_type)
# property_type quase sempre "Check" pra hidden/collapsible (0 ou 1).

OVERRIDES: list[tuple[str, str, str, str, str]] = [
    # =================================================================
    # Customer — vendedor + taxas + pagamento + crédito tudo visível
    # =================================================================
    ("Customer", "sales_team_section_break", "collapsible", "0", "Check"),
    ("Customer", "sales_team_section_break", "hidden", "0", "Check"),
    ("Customer", "accounting_tab", "hidden", "0", "Check"),
    ("Customer", "credit_limit_section", "collapsible", "0", "Check"),
    ("Customer", "payment_terms_section", "collapsible", "0", "Check"),
    ("Customer", "tax_section", "collapsible", "0", "Check"),
    ("Customer", "tax_section", "hidden", "0", "Check"),
    ("Customer", "address_contacts", "collapsible", "0", "Check"),
    ("Customer", "address_contacts", "hidden", "0", "Check"),
    ("Customer", "more_info", "collapsible", "0", "Check"),
    ("Customer", "internal_customer_section", "collapsible", "1", "Check"),  # esse pode ficar colapsado
    ("Customer", "primary_address_section", "collapsible", "0", "Check"),

    # =================================================================
    # Sales Order — vendedor + taxas + termos + frete + pricing visível
    # =================================================================
    ("Sales Order", "sales_team_section_break", "collapsible", "0", "Check"),
    ("Sales Order", "sales_team_section_break", "hidden", "0", "Check"),
    ("Sales Order", "taxes_section", "collapsible", "0", "Check"),
    ("Sales Order", "section_break_48", "collapsible", "0", "Check"),  # additional discount
    ("Sales Order", "terms_section_break", "collapsible", "0", "Check"),
    ("Sales Order", "section_break_82", "collapsible", "0", "Check"),  # pricing rules
    ("Sales Order", "section_break_47", "collapsible", "0", "Check"),  # totals
    ("Sales Order", "more_info", "collapsible", "0", "Check"),
    ("Sales Order", "address_and_contact", "collapsible", "0", "Check"),
    ("Sales Order", "printing_settings", "collapsible", "0", "Check"),
    ("Sales Order", "packing_list", "collapsible", "1", "Check"),  # raro, deixa colapsado
    ("Sales Order", "recurring_section", "hidden", "1", "Check"),
    ("Sales Order", "fp_patients", "hidden", "0", "Check"),
    ("Sales Order", "fp_patients_section", "collapsible", "0", "Check"),

    # =================================================================
    # Delivery Note — endereço de entrega + transporte sempre visíveis
    # =================================================================
    ("Delivery Note", "address_and_contact", "collapsible", "0", "Check"),
    ("Delivery Note", "transporter_info", "collapsible", "0", "Check"),
    ("Delivery Note", "transporter_info", "hidden", "0", "Check"),
    ("Delivery Note", "taxes_section", "collapsible", "0", "Check"),
    ("Delivery Note", "terms_section_break", "collapsible", "0", "Check"),
    ("Delivery Note", "section_break_47", "collapsible", "0", "Check"),
    ("Delivery Note", "more_info", "collapsible", "0", "Check"),
    ("Delivery Note", "printing_settings", "collapsible", "0", "Check"),

    # =================================================================
    # Sales Invoice — taxas + pagamento + termos sempre visíveis
    # =================================================================
    ("Sales Invoice", "address_and_contact", "collapsible", "0", "Check"),
    ("Sales Invoice", "taxes_section", "collapsible", "0", "Check"),
    ("Sales Invoice", "terms_section_break", "collapsible", "0", "Check"),
    ("Sales Invoice", "payments_section", "collapsible", "0", "Check"),
    ("Sales Invoice", "payment_schedule_section", "collapsible", "0", "Check"),
    ("Sales Invoice", "more_info", "collapsible", "0", "Check"),
    ("Sales Invoice", "printing_settings", "collapsible", "0", "Check"),

    # =================================================================
    # Payment Entry — toda info contábil + referências visíveis
    # =================================================================
    ("Payment Entry", "section_break_12", "collapsible", "0", "Check"),  # payment from
    ("Payment Entry", "section_break_34", "collapsible", "0", "Check"),  # references
    ("Payment Entry", "deductions_or_loss_section", "collapsible", "0", "Check"),
    ("Payment Entry", "section_break_43", "collapsible", "0", "Check"),  # totals
    ("Payment Entry", "section_break_60", "collapsible", "0", "Check"),  # accounting

    # =================================================================
    # Item — info comercial + estoque + tax + price visíveis
    # =================================================================
    ("Item", "section_break_11", "collapsible", "0", "Check"),  # description
    ("Item", "section_break_22", "collapsible", "0", "Check"),  # inventory
    ("Item", "inventory_section", "collapsible", "0", "Check"),
    ("Item", "unit_of_measure_conversion", "collapsible", "0", "Check"),
    ("Item", "section_break_32", "collapsible", "0", "Check"),  # variants
    ("Item", "purchasing_tab", "hidden", "0", "Check"),
    ("Item", "supplier_details", "collapsible", "0", "Check"),
    ("Item", "section_break_45", "collapsible", "0", "Check"),  # foreign trade
    ("Item", "sales_details", "collapsible", "0", "Check"),
    ("Item", "tax", "collapsible", "0", "Check"),
    ("Item", "manufacturing", "collapsible", "0", "Check"),
    ("Item", "manufacturing_tab", "hidden", "0", "Check"),
    ("Item", "website_section", "collapsible", "1", "Check"),  # raro, mantém

    # =================================================================
    # Patient — dados clínicos + contato + responsável visíveis
    # =================================================================
    ("Patient", "more_info", "collapsible", "0", "Check"),
    ("Patient", "contact_details", "collapsible", "0", "Check"),
    ("Patient", "personal_and_social_history", "collapsible", "0", "Check"),
    ("Patient", "occupation_section", "collapsible", "1", "Check"),

    # =================================================================
    # Prescriber — councils child + speciality + contato visíveis
    # =================================================================
    ("Prescriber", "councils", "hidden", "0", "Check"),
    ("Prescriber", "councils", "collapsible", "0", "Check"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert_property_setter(
    c: ErpnextClient,
    doc_type: str,
    field_name: str,
    property_name: str,
    value: str,
    property_type: str = "Data",
) -> bool:
    """Retorna True se aplicado, False se field não existe (skip silencioso)."""
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
    label = f"{doc_type}.{field_name}.{property_name}"
    try:
        if existing:
            c._request(
                "PUT",
                f"/api/resource/Property Setter/{quote(existing, safe='')}",
                json_body=payload,
            )
            log_ok(f"PS {label} = {value!r} (atualizado)")
        else:
            c._request("POST", "/api/resource/Property Setter", json_body=payload)
            log_ok(f"PS {label} = {value!r} (criado)")
        return True
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        # Field não existe nesse DocType (ex: nome de section variou entre versões)
        if "does not exist" in msg or "valid name" in msg or "valid fieldname" in msg:
            log_skip(f"PS {label} — field não existe (versão ERPNext diferente)")
            return False
        log_error(f"PS {label}: {exc}")
        return False


def _delete_property_setter(
    c: ErpnextClient,
    doc_type: str,
    field_name: str,
    property_name: str,
) -> bool:
    existing = c.property_setter_exists(doc_type, field_name, property_name)
    if not existing:
        return False
    c._request("DELETE", f"/api/resource/Property Setter/{quote(existing, safe='')}")
    return True


# ---------------------------------------------------------------------------
# install / uninstall
# ---------------------------------------------------------------------------

def install() -> int:
    log_section("Form Layout — todos campos críticos visíveis")
    c = client_from_env()
    user = c.ping()
    log_ok(f"Conectado como {user}")

    applied = 0
    skipped = 0
    failed = 0

    current_dt = None
    for dt, fn, prop, value, ptype in OVERRIDES:
        if dt != current_dt:
            log_section(f"DocType: {dt}")
            current_dt = dt
        try:
            ok = _upsert_property_setter(c, dt, fn, prop, value, ptype)
            if ok:
                applied += 1
            else:
                skipped += 1
        except Exception as exc:  # noqa: BLE001
            log_error(f"{dt}.{fn}.{prop}: {exc}")
            failed += 1

    log_section("Resumo")
    log_ok(f"Aplicados: {applied}")
    log_ok(f"Pulados (field ausente): {skipped}")
    if failed:
        log_error(f"Com erro: {failed}")
        return 1
    return 0


def uninstall() -> int:
    log_section("Form Layout — removendo Property Setters")
    c = client_from_env()
    removed = 0
    for dt, fn, prop, _value, _ptype in OVERRIDES:
        try:
            if _delete_property_setter(c, dt, fn, prop):
                removed += 1
                log_ok(f"PS {dt}.{fn}.{prop} removido")
        except Exception as exc:  # noqa: BLE001
            log_error(f"{dt}.{fn}.{prop}: {exc}")
    log_ok(f"Total removidos: {removed}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args(argv)
    return uninstall() if args.uninstall else install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
