"""
Definições do módulo Dispensação + Etiqueta Zebra.

  - DocType Dispensation: cada ato físico de entrega de ampola(s) ao paciente
  - Custom Field Sales Order Patient.dispensation (espelho)
  - Server Scripts (endpoints):
      future_production_create_dispensations_from_so
      future_production_generate_zpl_label
"""

from __future__ import annotations

import os


MODULE = os.environ.get("ERPNEXT_MODULE", "Manufacturing")


def _full_perm(role: str) -> dict:
    return {"role": role, "read": 1, "write": 1, "create": 1, "delete": 1,
            "submit": 1, "cancel": 1, "amend": 1,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1}


def _operator_perm(role: str) -> dict:
    return {"role": role, "read": 1, "write": 1, "create": 1, "submit": 1,
            "report": 1, "export": 1, "print": 1, "email": 1}


def _reader_perm(role: str) -> dict:
    return {"role": role, "read": 1, "report": 1, "export": 1, "print": 1}


# ---------------------------------------------------------------------------
# Dispensation — DocType submetível
# ---------------------------------------------------------------------------

STATUS_DISPENSATION = "\n".join([
    "Rascunho",
    "Pendente",
    "Dispensado",
    "Cancelado",
])

LABEL_TEMPLATES = "\n".join([
    "50x30mm",
    "100x50mm",
])


DISPENSATION = {
    "doctype": "DocType",
    "name": "Dispensation",
    "module": MODULE,
    "custom": 1,
    "is_submittable": 1,
    "track_changes": 1,
    "allow_rename": 0,
    "autoname": "naming_series:",
    "title_field": "patient_name",
    "search_fields": "patient_name,cpf,batch_no,sales_order",
    "sort_field": "modified",
    "sort_order": "DESC",
    "document_type": "Document",
    "fields": [
        # ----- Identificação -----
        {
            "fieldname": "naming_series",
            "label": "Série",
            "fieldtype": "Select",
            "options": "DISP-.YYYY.-.#####",
            "default": "DISP-.YYYY.-.#####",
            "reqd": 1,
        },
        {
            "fieldname": "status",
            "label": "Status",
            "fieldtype": "Select",
            "options": STATUS_DISPENSATION,
            "default": "Pendente",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "allow_on_submit": 1,
        },

        # ----- Origem -----
        {
            "fieldname": "section_origin",
            "label": "Origem",
            "fieldtype": "Section Break",
        },
        {
            "fieldname": "sales_order",
            "label": "Sales Order",
            "fieldtype": "Link",
            "options": "Sales Order",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
        },
        {
            "fieldname": "sales_order_patient_row",
            "label": "Linha de Paciente (row id)",
            "fieldtype": "Data",
            "description": "Row name da tabela fp_patients no SO de origem.",
        },
        {"fieldname": "column_break_orig", "fieldtype": "Column Break"},
        {
            "fieldname": "customer",
            "label": "Cliente",
            "fieldtype": "Link",
            "options": "Customer",
            "fetch_from": "sales_order.customer",
            "read_only": 1,
        },

        # ----- Paciente -----
        {"fieldname": "section_patient", "label": "Paciente", "fieldtype": "Section Break"},
        {
            "fieldname": "patient",
            "label": "Paciente",
            "fieldtype": "Link",
            "options": "Patient",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
        },
        {
            "fieldname": "patient_name",
            "label": "Nome",
            "fieldtype": "Data",
            "fetch_from": "patient.patient_name",
            "read_only": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "cpf",
            "label": "CPF",
            "fieldtype": "Data",
            "fetch_from": "patient.cpf",
            "read_only": 1,
            "in_list_view": 1,
        },
        {"fieldname": "column_break_pat", "fieldtype": "Column Break"},
        {
            "fieldname": "patient_mobile",
            "label": "Celular",
            "fieldtype": "Data",
            "fetch_from": "patient.mobile",
            "read_only": 1,
        },
        {
            "fieldname": "patient_email",
            "label": "E-mail",
            "fieldtype": "Data",
            "fetch_from": "patient.email",
            "read_only": 1,
        },

        # ----- Prescritor -----
        {"fieldname": "section_pres", "label": "Prescritor", "fieldtype": "Section Break"},
        {
            "fieldname": "prescriber",
            "label": "Médico",
            "fieldtype": "Link",
            "options": "Prescriber",
        },
        {
            "fieldname": "prescriber_name",
            "label": "Nome do Médico",
            "fieldtype": "Data",
            "fetch_from": "prescriber.full_name",
            "read_only": 1,
        },
        {"fieldname": "column_break_pres", "fieldtype": "Column Break"},
        {
            "fieldname": "prescriber_council",
            "label": "Conselho",
            "fieldtype": "Data",
            "fetch_from": "prescriber.council_type",
            "read_only": 1,
        },
        {
            "fieldname": "prescriber_number",
            "label": "Nº Conselho",
            "fieldtype": "Data",
            "fetch_from": "prescriber.council_number",
            "read_only": 1,
        },
        {
            "fieldname": "prescriber_state",
            "label": "UF Conselho",
            "fieldtype": "Data",
            "fetch_from": "prescriber.council_state",
            "read_only": 1,
        },

        # ----- Produto / Lote -----
        {"fieldname": "section_product", "label": "Produto", "fieldtype": "Section Break"},
        {
            "fieldname": "item_code",
            "label": "Item",
            "fieldtype": "Link",
            "options": "Item",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "item_name",
            "label": "Nome do Item",
            "fieldtype": "Data",
            "fetch_from": "item_code.item_name",
            "read_only": 1,
        },
        {
            "fieldname": "qty",
            "label": "Quantidade Dispensada",
            "fieldtype": "Float",
            "reqd": 1,
            "non_negative": 1,
            "in_list_view": 1,
        },
        {"fieldname": "column_break_prod", "fieldtype": "Column Break"},
        {
            "fieldname": "batch_no",
            "label": "Lote",
            "fieldtype": "Link",
            "options": "Batch",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "batch_expiry",
            "label": "Validade",
            "fieldtype": "Date",
            "fetch_from": "batch_no.expiry_date",
            "read_only": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "batch_manufacturing",
            "label": "Fabricação",
            "fieldtype": "Date",
            "fetch_from": "batch_no.manufacturing_date",
            "read_only": 1,
        },

        # ----- Dispensação -----
        {"fieldname": "section_disp", "label": "Dispensação", "fieldtype": "Section Break"},
        {
            "fieldname": "dispensed_at",
            "label": "Data/Hora Dispensação",
            "fieldtype": "Datetime",
            "default": "now",
            "allow_on_submit": 1,
        },
        {
            "fieldname": "pharmacist",
            "label": "Farmacêutico Responsável",
            "fieldtype": "Link",
            "options": "User",
            "default": "__user",
        },
        {"fieldname": "column_break_disp", "fieldtype": "Column Break"},
        {
            "fieldname": "signature",
            "label": "Assinatura do Paciente",
            "fieldtype": "Attach Image",
            "allow_on_submit": 1,
        },

        # ----- Etiqueta -----
        {"fieldname": "section_label", "label": "Etiqueta Zebra", "fieldtype": "Section Break"},
        {
            "fieldname": "label_template",
            "label": "Template Etiqueta",
            "fieldtype": "Select",
            "options": LABEL_TEMPLATES,
            "default": "50x30mm",
        },
        {
            "fieldname": "printed",
            "label": "Etiqueta Impressa",
            "fieldtype": "Check",
            "default": 0,
            "in_list_view": 1,
            "allow_on_submit": 1,
        },
        {"fieldname": "column_break_lab", "fieldtype": "Column Break"},
        {
            "fieldname": "printed_at",
            "label": "Data Impressão",
            "fieldtype": "Datetime",
            "read_only": 1,
            "allow_on_submit": 1,
        },
        {
            "fieldname": "zpl_preview",
            "label": "ZPL Gerado (preview)",
            "fieldtype": "Code",
            "options": "Text",
            "read_only": 1,
            "allow_on_submit": 1,
            "description": "ZPL último gerado. Use o botão 'Imprimir Etiqueta Zebra'.",
        },

        # ----- Observações -----
        {"fieldname": "section_notes", "label": "Observações", "fieldtype": "Section Break"},
        {
            "fieldname": "notes",
            "label": "Observações",
            "fieldtype": "Small Text",
        },
    ],
    "permissions": [
        _full_perm("System Manager"),
        _operator_perm("Sales User"),
        _operator_perm("Sales Manager"),
        _operator_perm("Stock User"),
        _reader_perm("Manufacturing User"),
    ],
}


# ---------------------------------------------------------------------------
# Custom Field em Sales Order Patient: espelho da dispensação
# ---------------------------------------------------------------------------

DISPENSATION_SOP_FIELDS = [
    {
        "dt": "Sales Order Patient",
        "fieldname": "dispensation",
        "label": "Dispensação",
        "fieldtype": "Link",
        "options": "Dispensation",
        "insert_after": "batch_status",
        "read_only": 1,
        "in_list_view": 0,
        "description": "Documento de dispensação criado para esta linha.",
    },
]
