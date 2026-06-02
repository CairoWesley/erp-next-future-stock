"""
setup_09_form_visibility.py — adiciona Custom Fields fetch_from no
Sales Order Patient pra mostrar dados completos de Patient + Prescriber +
Batch direto na linha (sem precisar clicar no link).

Campos adicionados (todos read-only, populam automaticamente):
  Do Patient:
    - patient_gender, patient_birth_date, patient_email,
      patient_city, patient_state
  Do Prescriber:
    - prescriber_full_name, prescriber_number,
      prescriber_state, prescriber_status
  Do Batch:
    - batch_expiry_date, batch_manufacturing_date

Uso:
    python setup_09_form_visibility.py
    python setup_09_form_visibility.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section
from lib.payloads_form_visibility import FORM_VISIBILITY_FIELDS


def install() -> int:
    client = client_from_env()

    log_section(f"Adicionando {len(FORM_VISIBILITY_FIELDS)} Custom Fields de visibilidade")
    errors = 0
    for field in FORM_VISIBILITY_FIELDS:
        try:
            client.create_custom_field(field)
        except Exception as exc:
            log_error(f"{field['dt']}.{field['fieldname']}: {exc}")
            errors += 1

    if errors == 0:
        log_ok("Form visibility instalada.")
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()
    log_section("Removendo Form Visibility")
    for field in reversed(FORM_VISIBILITY_FIELDS):
        try:
            client.delete_custom_field(field["dt"], field["fieldname"])
        except Exception as exc:
            log_error(f"{field['dt']}.{field['fieldname']}: {exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
