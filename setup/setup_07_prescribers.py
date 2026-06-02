"""
setup_07_prescribers.py — Médico Prescritor (v2: 1 CPF + N conselhos).

Modelo:
  - Prescriber = pessoa (CPF único)
  - Child table `councils[]` com N registros profissionais (CRM, CRO, etc.)
  - 1 médico pode ter múltiplos CRMs (1 CPF + N conselhos)
  - SO/Patient apontam: prescriber + prescriber_council_row (qual CRM)

Cria:
  1. DocType Prescriber Council (child table)
  2. DocType Prescriber (com child)
  3. Custom Fields:
     - Patient.default_prescriber, Patient.default_council_label
     - Sales Order Patient.prescriber, .prescriber_council_row, .prescriber_council
  4. Server Scripts:
     - Prescriber Before Save: CPF + unicidade global de conselhos
     - SO Before Save: valida prescriber + council_row referenciado
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section
from lib.payloads_prescribers import (
    PRESCRIBER,
    PRESCRIBER_COUNCIL,
    PRESCRIBER_CUSTOM_FIELDS,
)


SCRIPT_VALIDATE_PRESCRIBER = r'''
# Prescriber -- Before Save (v2 com child councils)
# 1) CPF: 11 dígitos não triviais.
# 2) Cada council em councils[]: se Outro, exige council_other.
# 3) Unicidade GLOBAL: (council_type, council_number, council_state) único
#    no banco todo, contando inclusive linhas de OUTROS Prescribers.
# 4) No máximo 1 council com is_primary=1.

if doc.cpf:
    digits = "".join(c for c in doc.cpf if c.isdigit())
    if len(digits) != 11:
        frappe.throw("CPF precisa ter 11 digitos. Recebido: " + str(doc.cpf))
    if digits == digits[0] * 11:
        frappe.throw("CPF invalido (todos os digitos iguais).")
    doc.cpf = digits

councils = doc.get("councils") or []
if not councils:
    frappe.throw("Cadastre pelo menos 1 conselho profissional.")

primary_count = 0
for c in councils:
    if c.get("council_type") == "Outro" and not c.get("council_other"):
        frappe.throw("Quando Tipo = 'Outro', informe a sigla em 'Sigla (se Outro)'.")
    if c.get("council_number"):
        c.council_number = str(c.council_number).strip()
    if int(c.get("is_primary") or 0) == 1:
        primary_count = primary_count + 1

if primary_count > 1:
    frappe.throw("Marque no máximo 1 conselho como Principal.")

# Unicidade global: (council_type, number, state) único entre TODAS as linhas
# de TODOS os Prescribers (não só desse doc).
for c in councils:
    ct = c.get("council_type")
    cn = c.get("council_number")
    cs = c.get("council_state")
    if not ct or not cn or not cs:
        continue
    # Acha linhas de Prescriber Council com mesmos valores
    existing = frappe.db.sql(
        """
        select pc.parent, pc.name
        from `tabPrescriber Council` pc
        where pc.council_type = %s
          and pc.council_number = %s
          and pc.council_state = %s
          and pc.parent != %s
        limit 1
        """,
        (ct, cn, cs, doc.name or ""),
        as_dict=True,
    )
    if existing:
        frappe.throw(
            "Conselho " + ct + "-" + cs + " " + str(cn) +
            " ja cadastrado em outro Prescriber: " + existing[0].parent
        )
'''.strip()


SCRIPT_VALIDATE_SO_PRESCRIBER = r'''
# Sales Order -- Before Save: valida prescriber + council_row de cada linha.

patients = doc.get("fp_patients") or []
for p in patients:
    prescriber_name = p.get("prescriber")
    if not prescriber_name:
        continue

    if not frappe.db.exists("Prescriber", prescriber_name):
        frappe.throw("Prescriber " + str(prescriber_name) + " nao existe.")

    council_row_id = p.get("prescriber_council_row")
    if not council_row_id:
        # Sem council escolhido: valida que Prescriber tem pelo menos 1 ativo.
        actives = frappe.db.sql(
            """
            select count(*) from `tabPrescriber Council`
            where parent = %s and (council_status = 'Ativo' or council_status is null)
            """,
            (prescriber_name,),
        )[0][0]
        if not actives:
            frappe.throw(
                "Prescriber " + prescriber_name +
                " nao tem nenhum conselho Ativo cadastrado."
            )
        continue

    # Confere council_row pertence ao Prescriber e esta Ativo.
    council = frappe.db.get_value(
        "Prescriber Council", council_row_id,
        ["parent", "council_type", "council_number", "council_state", "council_status"],
        as_dict=True,
    )
    if not council:
        frappe.throw("Conselho " + str(council_row_id) + " nao encontrado.")
    if council.parent != prescriber_name:
        frappe.throw(
            "Conselho " + str(council_row_id) + " nao pertence ao Prescriber " +
            prescriber_name + "."
        )
    if council.council_status == "Cassado":
        frappe.throw(
            "Conselho " + str(council.council_type) + "-" +
            str(council.council_state) + " " + str(council.council_number) +
            " do Prescriber " + prescriber_name + " esta Cassado."
        )

    # Atualiza fetch de exibicao prescriber_council
    p.prescriber_council = (
        str(council.council_type) + "-" + str(council.council_state) +
        " " + str(council.council_number)
    )
'''.strip()


def install() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1

    errors = 0

    log_section("1/5 — DocType Prescriber Council (child)")
    try:
        client.create_doctype(PRESCRIBER_COUNCIL)
    except Exception as exc:
        log_error(f"Prescriber Council: {exc}")
        return 1

    log_section("2/5 — DocType Prescriber (parent)")
    try:
        client.create_doctype(PRESCRIBER)
    except Exception as exc:
        log_error(f"Prescriber: {exc}")
        return 1

    log_section(f"3/5 — Custom Fields ({len(PRESCRIBER_CUSTOM_FIELDS)})")
    for field in PRESCRIBER_CUSTOM_FIELDS:
        try:
            client.create_custom_field(field)
        except Exception as exc:
            log_error(f"  {field['dt']}.{field['fieldname']}: {exc}")
            errors += 1

    log_section("4/5 — Server Script: Prescriber - Validate (Before Save)")
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

    log_section("5/5 — Server Script: SO - Validate Prescriber Lines (Before Save)")
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
        log_ok("Módulo Prescriber (v2 com child councils) instalado.")
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

    log_section("Removendo DocType Prescriber Council (child)")
    try:
        client.delete_doctype("Prescriber Council")
    except Exception as exc:
        log_error(f"Prescriber Council: {exc}")

    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
