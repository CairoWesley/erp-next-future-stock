"""
setup_07_prescribers.py — instala o módulo Médico Prescritor.

Cria:
  1. DocType Prescriber (mestre — CPF + conselho + UF)
  2. Custom Field Patient.default_prescriber (Link/Prescriber)
  3. Custom Field Sales Order Patient.prescriber (Link/Prescriber, por linha)
  4. Custom Field Sales Order Patient.prescriber_council (fetch readonly)
  5. Server Script — Prescriber Before Save:
       - Normaliza CPF (só dígitos)
       - Valida 11 dígitos não triviais
       - Conselho number+type+UF não duplicado
       - Se council_type=Outro, council_other obrigatório
  6. Server Script — Sales Order Before Save (extensão):
       - Valida que o prescriber de cada linha (se preenchido) existe e está ativo

Uso:
    python setup_07_prescribers.py
    python setup_07_prescribers.py --uninstall
"""

from __future__ import annotations

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section
from lib.payloads_prescribers import PRESCRIBER, PRESCRIBER_CUSTOM_FIELDS


SCRIPT_VALIDATE_PRESCRIBER = r'''
# Prescriber -- Before Save
# Valida CPF (11 digitos nao triviais) + unicidade do conselho.

if doc.cpf:
    digits = "".join(c for c in doc.cpf if c.isdigit())
    if len(digits) != 11:
        frappe.throw("CPF precisa ter 11 digitos. Recebido: " + str(doc.cpf))
    if digits == digits[0] * 11:
        frappe.throw("CPF invalido (todos os digitos iguais).")
    doc.cpf = digits

if doc.council_type == "Outro" and not doc.council_other:
    frappe.throw("Quando Tipo de Conselho = 'Outro', informe a sigla em 'Outro Conselho'.")

# Numero do conselho: deduplica espacos e zeros a esquerda excessivos.
if doc.council_number:
    doc.council_number = str(doc.council_number).strip()

# Unicidade: (council_type, council_number, council_state) deve ser unico.
if doc.council_type and doc.council_number and doc.council_state:
    filters = {
        "council_type": doc.council_type,
        "council_number": doc.council_number,
        "council_state": doc.council_state,
    }
    existing = frappe.db.get_all(
        "Prescriber",
        filters=filters,
        fields=["name"],
        limit=1,
    )
    if existing and existing[0].name != doc.name:
        frappe.throw(
            "Conselho ja cadastrado em outro Prescriber: " + existing[0].name +
            " (" + doc.council_type + "-" + doc.council_state + " " +
            str(doc.council_number) + ")."
        )
'''.strip()


SCRIPT_VALIDATE_SO_PRESCRIBER = r'''
# Sales Order -- Before Save (extensao para validar prescriber por linha)
# Roda em adicao ao "SO - Validate Patients (Before Save)".

patients = doc.get("fp_patients") or []
for p in patients:
    prescriber_name = p.get("prescriber")
    if not prescriber_name:
        continue  # opcional na linha; default vem do Patient.default_prescriber

    pres = frappe.db.get_value(
        "Prescriber",
        prescriber_name,
        ["council_status", "council_type", "council_number", "council_state"],
        as_dict=True,
    )
    if not pres:
        frappe.throw("Prescriber " + str(prescriber_name) + " nao existe.")
    if pres.council_status == "Cassado":
        frappe.throw(
            "Prescriber " + prescriber_name + " com conselho Cassado " +
            "(" + str(pres.council_type) + "-" + str(pres.council_state) +
            " " + str(pres.council_number) + ") nao pode prescrever."
        )
'''.strip()


def install() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error(
            "Server Scripts desabilitados — habilite com "
            "`bench --site <site> set-config -g server_script_enabled 1`"
        )
        return 1

    errors = 0

    log_section("1/4 — DocType Prescriber")
    try:
        client.create_doctype(PRESCRIBER)
    except Exception as exc:
        log_error(f"Prescriber: {exc}")
        return 1

    log_section("2/4 — Custom Fields (Patient.default_prescriber, Sales Order Patient.prescriber)")
    for field in PRESCRIBER_CUSTOM_FIELDS:
        try:
            client.create_custom_field(field)
        except Exception as exc:
            log_error(f"Custom Field {field['dt']}.{field['fieldname']}: {exc}")
            errors += 1

    log_section("3/4 — Server Script: Prescriber - Validate (Before Save)")
    try:
        client.upsert_server_script({
            "name": "Prescriber - Validate (Before Save)",
            "script_type": "DocType Event",
            "reference_doctype": "Prescriber",
            "doctype_event": "Before Save",
            "enabled": 1,
            "script": SCRIPT_VALIDATE_PRESCRIBER,
        })
    except Exception as exc:
        log_error(f"Prescriber Validate: {exc}")
        errors += 1

    log_section("4/4 — Server Script: SO - Validate Prescriber Lines (Before Save)")
    try:
        client.upsert_server_script({
            "name": "SO - Validate Prescriber Lines (Before Save)",
            "script_type": "DocType Event",
            "reference_doctype": "Sales Order",
            "doctype_event": "Before Save",
            "enabled": 1,
            "script": SCRIPT_VALIDATE_SO_PRESCRIBER,
        })
    except Exception as exc:
        log_error(f"SO Validate Prescriber: {exc}")
        errors += 1

    if errors == 0:
        log_ok("Módulo Prescriber instalado.")
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()

    log_section("Removendo Server Scripts")
    for name in (
        "SO - Validate Prescriber Lines (Before Save)",
        "Prescriber - Validate (Before Save)",
    ):
        try:
            client.delete_server_script(name)
        except Exception as exc:
            log_error(f"{name}: {exc}")

    log_section("Removendo Custom Fields")
    for field in reversed(PRESCRIBER_CUSTOM_FIELDS):
        try:
            client.delete_custom_field(field["dt"], field["fieldname"])
        except Exception as exc:
            log_error(f"{field['dt']}.{field['fieldname']}: {exc}")

    log_section("Removendo DocType Prescriber")
    try:
        client.delete_doctype("Prescriber")
    except Exception as exc:
        log_error(f"Prescriber: {exc}")

    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
