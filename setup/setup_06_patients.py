"""
setup_06_patients.py — instala o módulo Lote × Pacientes.

Cria:
  1. DocType Patient (cadastro mestre — CPF, contato, endereço)
  2. DocType Sales Order Patient (child table)
  3. Custom Fields em Sales Order (seção + tabela de pacientes)
  4. Server Script — Validação no Sales Order Before Save:
     - Para cada item, soma de qty dos pacientes deve = qty do item
     - CPF válido (11 dígitos, sem repetição trivial)
     - Item do paciente precisa existir no SO

Uso:
    python setup_06_patients.py
    python setup_06_patients.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section
from lib.payloads_patients import (
    PATIENT,
    SALES_ORDER_PATIENT,
    SALES_ORDER_PATIENT_FIELDS,
)


SCRIPT_VALIDATE_SO_PATIENTS = r'''
# Sales Order -- Before Save
# Valida que os pacientes vinculados batem com os itens do pedido.

patients = doc.get("fp_patients") or []
if patients:
    def only_digits(s):
        return "".join(c for c in (s or "") if c.isdigit())

    item_codes_in_so = [r.item_code for r in (doc.items or [])]

    for p in patients:
        who = str(p.patient_name or p.patient or "paciente")
        cpf = only_digits(p.cpf)
        if cpf:
            if len(cpf) != 11:
                frappe.throw("CPF invalido para " + who + ": precisa ter 11 digitos.")
            if cpf == cpf[0] * 11:
                frappe.throw("CPF invalido para " + who + ": digitos repetidos.")

        if p.item_code not in item_codes_in_so:
            frappe.throw(
                "Item " + str(p.item_code) + " do paciente " + who +
                " nao esta nos itens do pedido."
            )

        if not p.qty or float(p.qty) <= 0:
            frappe.throw("Quantidade do paciente " + who + " deve ser maior que zero.")

    by_item_patients = {}
    for p in patients:
        by_item_patients[p.item_code] = by_item_patients.get(p.item_code, 0) + float(p.qty or 0)

    for row in (doc.items or []):
        sum_patients = by_item_patients.get(row.item_code, 0)
        if sum_patients > 0 and abs(sum_patients - float(row.qty or 0)) > 0.001:
            frappe.throw(
                "Item " + str(row.item_code) + ": qty do pedido (" +
                str(row.qty) + ") diferente da soma das ampolas dos pacientes (" +
                str(sum_patients) + ")."
            )
'''.strip()


SCRIPT_VALIDATE_PATIENT_CPF = r'''
# Patient -- Before Save
# Valida CPF (11 digitos nao triviais) e normaliza armazenando apenas digitos.

if doc.cpf:
    digits = "".join(c for c in doc.cpf if c.isdigit())
    if len(digits) != 11:
        frappe.throw("CPF precisa ter 11 digitos. Recebido: " + str(doc.cpf))
    if digits == digits[0] * 11:
        frappe.throw("CPF invalido (todos os digitos iguais).")
    doc.cpf = digits
'''.strip()


def install() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados — habilite com "
                  "`bench --site <site> set-config -g server_script_enabled 1`")
        return 1

    log_section("1/5 — DocType Patient")
    try:
        client.create_doctype(PATIENT)
    except Exception as exc:
        log_error(f"Patient: {exc}")
        return 1

    log_section("2/5 — DocType Sales Order Patient (child table)")
    try:
        client.create_doctype(SALES_ORDER_PATIENT)
    except Exception as exc:
        log_error(f"Sales Order Patient: {exc}")
        return 1

    log_section("3/5 — Custom Fields em Sales Order")
    errors = 0
    for field in SALES_ORDER_PATIENT_FIELDS:
        try:
            client.create_custom_field(field)
        except Exception as exc:
            log_error(f"Custom Field {field['fieldname']}: {exc}")
            errors = errors + 1

    log_section("4/5 — Server Script: SO - Validate Patients (Before Save)")
    try:
        client.upsert_server_script({
            "name": "SO - Validate Patients (Before Save)",
            "script_type": "DocType Event",
            "reference_doctype": "Sales Order",
            "doctype_event": "Before Save",
            "enabled": 1,
            "script": SCRIPT_VALIDATE_SO_PATIENTS,
        })
    except Exception as exc:
        log_error(f"SO Validate Patients: {exc}")
        errors = errors + 1

    log_section("5/5 — Server Script: Patient - Validate CPF")
    try:
        client.upsert_server_script({
            "name": "Patient - Validate CPF (Before Save)",
            "script_type": "DocType Event",
            "reference_doctype": "Patient",
            "doctype_event": "Before Save",
            "enabled": 1,
            "script": SCRIPT_VALIDATE_PATIENT_CPF,
        })
    except Exception as exc:
        log_error(f"Patient Validate CPF: {exc}")
        errors = errors + 1

    if errors == 0:
        log_ok("Módulo Pacientes instalado.")
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()

    log_section("Removendo Server Scripts")
    for name in ("SO - Validate Patients (Before Save)", "Patient - Validate CPF (Before Save)"):
        try:
            client.delete_server_script(name)
        except Exception as exc:
            log_error(f"{name}: {exc}")

    log_section("Removendo Custom Fields em Sales Order")
    for field in reversed(SALES_ORDER_PATIENT_FIELDS):
        try:
            client.delete_custom_field(field["dt"], field["fieldname"])
        except Exception as exc:
            log_error(f"{field['fieldname']}: {exc}")

    log_section("Removendo DocType Sales Order Patient")
    try:
        client.delete_doctype("Sales Order Patient")
    except Exception as exc:
        log_error(f"Sales Order Patient: {exc}")

    log_section("Removendo DocType Patient")
    try:
        client.delete_doctype("Patient")
    except Exception as exc:
        log_error(f"Patient: {exc}")

    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
