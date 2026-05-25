"""
Definições do módulo Dispensação + Etiqueta Zebra (v2).

Modelo:
  - 1 Sales Order → 1 Dispensation (a entrega completa do pedido)
  - Dispensation tem child table `Dispensation Patient`:
      cada linha = 1 paciente que recebeu N ampolas do lote X
  - Cada linha do child gera 1 etiqueta Zebra
  - Existe também botão "imprimir todas" que envia ZPL múltiplo
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


STATUS_DISPENSATION = "\n".join([
    "Rascunho",
    "Pendente",
    "Parcialmente Dispensado",
    "Dispensado",
    "Cancelado",
])

LABEL_TEMPLATES = "\n".join([
    "50x30mm",
    "100x50mm",
])


# ---------------------------------------------------------------------------
# Dispensation Patient — child table
# ---------------------------------------------------------------------------

DISPENSATION_PATIENT = {
    "doctype": "DocType",
    "name": "Dispensation Patient",
    "module": MODULE,
    "custom": 1,
    "istable": 1,
    "editable_grid": 1,
    "sort_field": "modified",
    "sort_order": "DESC",
    "fields": [
        # Patient
        {
            "fieldname": "patient",
            "label": "Paciente",
            "fieldtype": "Link",
            "options": "Patient",
            "reqd": 1,
            "in_list_view": 1,
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
        {
            "fieldname": "mobile",
            "label": "Celular",
            "fieldtype": "Data",
            "fetch_from": "patient.mobile",
            "read_only": 1,
        },

        # Prescriber
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

        # Produto
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
            "label": "Qtd",
            "fieldtype": "Float",
            "reqd": 1,
            "non_negative": 1,
            "in_list_view": 1,
        },

        # Batch
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

        # Sales Order Patient origem
        {
            "fieldname": "sales_order_patient_row",
            "label": "SOP Row",
            "fieldtype": "Data",
            "read_only": 1,
            "hidden": 1,
        },

        # Etiqueta individual
        {
            "fieldname": "printed",
            "label": "Etiq. Impressa",
            "fieldtype": "Check",
            "default": 0,
            "in_list_view": 1,
        },
        {
            "fieldname": "printed_at",
            "label": "Impressa em",
            "fieldtype": "Datetime",
            "read_only": 1,
        },
        {
            "fieldname": "signature",
            "label": "Assinatura",
            "fieldtype": "Attach Image",
        },
        {
            "fieldname": "row_notes",
            "label": "Obs",
            "fieldtype": "Small Text",
        },
    ],
}


# ---------------------------------------------------------------------------
# Dispensation — DocType principal
# ---------------------------------------------------------------------------

DISPENSATION = {
    "doctype": "DocType",
    "name": "Dispensation",
    "module": MODULE,
    "custom": 1,
    "is_submittable": 1,
    "track_changes": 1,
    "allow_rename": 0,
    "autoname": "naming_series:",
    "title_field": "sales_order",
    "search_fields": "sales_order,customer",
    "sort_field": "modified",
    "sort_order": "DESC",
    "document_type": "Document",
    "fields": [
        # Section explícita no topo (Frappe v15 às vezes não renderiza
        # campos antes da primeira Section Break)
        {"fieldname": "section_header", "label": "Identificação", "fieldtype": "Section Break"},
        {
            "fieldname": "naming_series",
            "label": "Série",
            "fieldtype": "Select",
            "options": "DISP-.YYYY.-.#####",
            "default": "DISP-.YYYY.-.#####",
            "reqd": 1,
        },
        {"fieldname": "column_break_header", "fieldtype": "Column Break"},
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

        # Origem
        {"fieldname": "section_origin", "label": "Origem", "fieldtype": "Section Break"},
        {
            "fieldname": "sales_order",
            "label": "Sales Order",
            "fieldtype": "Link",
            "options": "Sales Order",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "description": "1 Sales Order = 1 Dispensation (a entrega do pedido). Unicidade validada no endpoint.",
        },
        {
            "fieldname": "delivery_note",
            "label": "Nota de Entrega",
            "fieldtype": "Link",
            "options": "Delivery Note",
        },
        {"fieldname": "column_break_orig", "fieldtype": "Column Break"},
        {
            "fieldname": "customer",
            "label": "Cliente",
            "fieldtype": "Link",
            "options": "Customer",
            "fetch_from": "sales_order.customer",
            "read_only": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "customer_name",
            "label": "Nome do Cliente",
            "fieldtype": "Data",
            "fetch_from": "customer.customer_name",
            "read_only": 1,
        },

        # Dispensação
        {"fieldname": "section_disp", "label": "Dispensação", "fieldtype": "Section Break"},
        {
            "fieldname": "dispensed_at",
            "label": "Data/Hora",
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
            "fieldname": "total_qty",
            "label": "Total de Ampolas",
            "fieldtype": "Float",
            "read_only": 1,
        },
        {
            "fieldname": "total_patients",
            "label": "Total de Pacientes",
            "fieldtype": "Int",
            "read_only": 1,
        },

        # Pacientes (child table)
        {"fieldname": "section_patients", "label": "Pacientes da Entrega", "fieldtype": "Section Break"},
        {
            "fieldname": "patients",
            "label": "Pacientes",
            "fieldtype": "Table",
            "options": "Dispensation Patient",
            "reqd": 1,
        },

        # Etiqueta
        {"fieldname": "section_label", "label": "Etiquetas Zebra", "fieldtype": "Section Break"},
        {
            "fieldname": "label_template",
            "label": "Template Etiqueta",
            "fieldtype": "Select",
            "options": LABEL_TEMPLATES,
            "default": "50x30mm",
        },
        {
            "fieldname": "all_printed",
            "label": "Todas Etiquetas Impressas",
            "fieldtype": "Check",
            "default": 0,
            "read_only": 1,
            "in_list_view": 1,
            "allow_on_submit": 1,
        },
        {"fieldname": "column_break_lab", "fieldtype": "Column Break"},
        {
            "fieldname": "printed_count",
            "label": "Etiquetas Impressas / Total",
            "fieldtype": "Data",
            "read_only": 1,
            "allow_on_submit": 1,
        },

        # Observações
        {"fieldname": "section_notes", "label": "Observações", "fieldtype": "Section Break"},
        {
            "fieldname": "notes",
            "label": "Observações Gerais",
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
# Custom Field — Sales Order.dispensation (espelho 1:1)
# ---------------------------------------------------------------------------

DISPENSATION_SO_FIELDS = [
    {
        "dt": "Sales Order",
        "fieldname": "dispensation",
        "label": "Dispensação",
        "fieldtype": "Link",
        "options": "Dispensation",
        "insert_after": "fp_patients",
        "read_only": 1,
        "allow_on_submit": 1,
        "description": "Documento de entrega/dispensação criado pra este pedido.",
    },
]
