"""
setup_18_receita_attach.py — Custom Fields pra anexar receita PDF na linha do paciente do SO.

Cria 3 Custom Fields em Sales Order Patient:
  - receita                (Attach)  — URL do arquivo PDF
  - receita_original_name  (Data)    — nome original do arquivo no validacao_receita
  - receita_status         (Select)  — status assinatura digital

Upload do PDF: usar endpoint nativo Frappe /api/method/upload_file.
n8n monta multipart:
  POST /api/method/upload_file
    file:        <pdf bytes>
    is_private:  1
    folder:      "Home/Receitas"  (opcional)
    doctype:     "Sales Order Patient"
    docname:     "<row_name>"
    fieldname:   "receita"
Frappe cria File doc + popula automaticamente o campo receita na row.

Pra achar row_name pelo CPF:
  GET /api/resource/Sales Order Patient?filters=[
    ["parent","=","<SO>"],["patient","=","<Patient name>"]
  ]&fields=["name","item_code"]

Uso:
    python setup/setup_18_receita_attach.py
    python setup/setup_18_receita_attach.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


CUSTOM_FIELDS = [
    {
        "dt": "Sales Order Patient",
        "fieldname": "receita",
        "label": "Receita (PDF)",
        "fieldtype": "Attach",
        "insert_after": "qty",
        "allow_on_submit": 1,
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "receita_original_name",
        "label": "Nome Original Receita",
        "fieldtype": "Data",
        "read_only": 1,
        "insert_after": "receita",
        "allow_on_submit": 1,
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "receita_status",
        "label": "Status Assinatura Digital",
        "fieldtype": "Select",
        "options": "\nnao_verificado\nverificando\nvalida\ninvalida\nsem_assinatura\nerro",
        "read_only": 1,
        "insert_after": "receita_original_name",
        "allow_on_submit": 1,
    },
]


SCRIPT_ATTACH_RECEITA_LEGACY_UNUSED = r'''
# /api/method/future_production_attach_receita
# Anexa receita PDF a linha fp_patients de um Sales Order.

import base64

data = frappe.form_dict
if not data:
    frappe.throw("Payload vazio.")

if isinstance(data, str):
    data = frappe.parse_json(data)

so_name = data.get("sales_order")
patient_cpf = "".join(ch for ch in (data.get("patient_cpf") or "") if ch.isdigit())
item_code = data.get("item_code") or ""
file_name = data.get("file_name") or "receita.pdf"
b64 = data.get("file_data_base64") or ""
is_private = int(data.get("is_private") or 1)
receita_original = data.get("receita_original_name") or file_name
receita_status = data.get("receita_status") or ""

if not so_name:
    frappe.throw("sales_order obrigatorio.")
if not patient_cpf:
    frappe.throw("patient_cpf obrigatorio.")
if not b64:
    frappe.throw("file_data_base64 obrigatorio.")

# Acha patient pelo CPF
pat_name = frappe.db.get_value("Patient", {"cpf": patient_cpf}, "name")
if not pat_name:
    frappe.throw("Patient com CPF " + patient_cpf + " nao encontrado.")

# Acha row fp_patients no SO
filters = {"parent": so_name, "patient": pat_name}
if item_code:
    filters["item_code"] = item_code

rows = frappe.db.get_all(
    "Sales Order Patient",
    filters=filters,
    fields=["name", "item_code"],
    limit=5,
)
if not rows:
    frappe.throw("Linha Sales Order Patient nao encontrada (SO=" + so_name +
                 " patient=" + pat_name + ").")
if len(rows) > 1 and not item_code:
    frappe.throw("Multiplas linhas pra esse patient. Especifique item_code. "
                 "item_codes: " + str([r.item_code for r in rows]))

row_name = rows[0].name

# Decoda base64
try:
    content = base64.b64decode(b64)
except Exception as exc:
    frappe.throw("Falha decodificar base64: " + str(exc))

# Salva File via frappe.utils.file_manager.save_file
from frappe.utils.file_manager import save_file
saved = save_file(
    fname=file_name,
    content=content,
    dt="Sales Order Patient",
    dn=row_name,
    folder=None,
    decode=False,
    is_private=is_private,
    df="receita",
)

# Atualiza campos receita + receita_original_name + receita_status
file_url = saved.file_url if hasattr(saved, "file_url") else saved.get("file_url")
updates = {"receita": file_url, "receita_original_name": receita_original}
if receita_status:
    updates["receita_status"] = receita_status

# child DocType update requer SQL direto OR update via parent
# Tenta direct set_value primeiro
try:
    for fld, val in updates.items():
        frappe.db.set_value("Sales Order Patient", row_name, fld, val,
                            update_modified=False)
except Exception:
    # Fallback: load parent + persist
    so_doc = frappe.get_doc("Sales Order", so_name)
    for r in so_doc.fp_patients:
        if r.name == row_name:
            for fld, val in updates.items():
                setattr(r, fld, val)
            break
    so_doc.save(ignore_permissions=True)

frappe.response["message"] = {
    "ok": True,
    "sales_order": so_name,
    "sales_order_patient_row": row_name,
    "file_url": file_url,
    "file_name": file_name,
}
'''.strip()


def install() -> int:
    client = client_from_env()
    log_section("Custom Fields (Sales Order Patient) — receita")
    for cf in CUSTOM_FIELDS:
        try:
            client.create_custom_field(cf)
        except Exception as exc:
            log_error(f"Custom Field {cf['fieldname']}: {exc}")
    log_ok("Upload do PDF: usar endpoint nativo /api/method/upload_file")
    return 0


def uninstall() -> int:
    client = client_from_env()
    # remove server script legado se existir
    try:
        client.delete_server_script("future_production_attach_receita")
    except Exception:
        pass
    for cf in reversed(CUSTOM_FIELDS):
        try:
            client.delete_custom_field(cf["dt"], cf["fieldname"])
        except Exception as exc:
            log_error(f"{cf['fieldname']}: {exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
