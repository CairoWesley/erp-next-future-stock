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
    "25x60mm",
    "30x60mm",
    "50x30mm",
    "100x50mm",
    "Receituario 100x50mm",
])


# ---------------------------------------------------------------------------
# Dispensation Patient — child table
# ---------------------------------------------------------------------------

DISPENSATION_PATIENT = {
    "doctype": "DocType",
    "name": "Dispensacao Paciente",
    "module": MODULE,
    "custom": 1,
    "istable": 1,
    "editable_grid": 1,
    "fields": [
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
            "in_list_view": 1,
        },
        {
            "fieldname": "cpf",
            "label": "CPF",
            "fieldtype": "Data",
            "in_list_view": 1,
        },
        {
            "fieldname": "mobile",
            "label": "Celular",
            "fieldtype": "Data",
        },
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
        },
        {
            "fieldname": "prescriber_council",
            "label": "Conselho",
            "fieldtype": "Data",
        },
        {
            "fieldname": "prescriber_number",
            "label": "Nº Conselho",
            "fieldtype": "Data",
        },
        {
            "fieldname": "prescriber_state",
            "label": "UF Conselho",
            "fieldtype": "Data",
        },
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
        },
        {
            "fieldname": "qty",
            "label": "Qtd",
            "fieldtype": "Float",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "ph",
            "label": "pH",
            "fieldtype": "Float",
            "precision": "2",
            "in_list_view": 1,
        },
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
            "in_list_view": 1,
        },
        {
            "fieldname": "batch_manufacturing",
            "label": "Fabricação",
            "fieldtype": "Date",
        },
        {
            "fieldname": "sales_order_patient_row",
            "label": "SOP Row",
            "fieldtype": "Data",
        },
        {
            "fieldname": "printed",
            "label": "Impressa",
            "fieldtype": "Check",
            "default": 0,
            "in_list_view": 1,
        },
        {
            "fieldname": "printed_at",
            "label": "Impressa em",
            "fieldtype": "Datetime",
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
    "name": "Dispensacao",
    "module": MODULE,
    "custom": 1,
    "is_submittable": 1,
    "autoname": "naming_series:",
    "title_field": "sales_order",
    "search_fields": "sales_order,customer",
    "sort_field": "modified",
    "sort_order": "DESC",
    "fields": [
        {
            "fieldname": "sb_main",
            "label": "",
            "fieldtype": "Section Break",
        },
        {
            "fieldname": "naming_series",
            "label": "Série",
            "fieldtype": "Select",
            "options": "DISP-.YYYY.-.#####",
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
            "fieldname": "customer",
            "label": "Cliente",
            "fieldtype": "Link",
            "options": "Customer",
            "in_list_view": 1,
        },
        {
            "fieldname": "delivery_note",
            "label": "Nota de Entrega",
            "fieldtype": "Link",
            "options": "Delivery Note",
        },
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
        {
            "fieldname": "total_qty",
            "label": "Total de Ampolas",
            "fieldtype": "Float",
        },
        {
            "fieldname": "total_patients",
            "label": "Total de Pacientes",
            "fieldtype": "Int",
        },
        {
            "fieldname": "label_template",
            "label": "Template Etiqueta",
            "fieldtype": "Select",
            "options": LABEL_TEMPLATES,
            "default": "25x60mm",
        },
        {
            "fieldname": "printed_count",
            "label": "Etiquetas Impressas",
            "fieldtype": "Data",
            "allow_on_submit": 1,
        },
        {
            "fieldname": "all_printed",
            "label": "Todas Impressas",
            "fieldtype": "Check",
            "default": 0,
            "in_list_view": 1,
            "allow_on_submit": 1,
        },
        {
            "fieldname": "patients",
            "label": "Pacientes da Entrega",
            "fieldtype": "Table",
            "options": "Dispensacao Paciente",
            "reqd": 1,
        },
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
# Custom Field — Sales Order.dispensation (espelho 1:1)
# ---------------------------------------------------------------------------

DISPENSATION_SO_FIELDS = [
    {
        "dt": "Sales Order",
        "fieldname": "dispensation",
        "label": "Dispensação",
        "fieldtype": "Link",
        "options": "Dispensacao",
        "insert_after": "fp_patients",
        "read_only": 1,
        "allow_on_submit": 1,
        "description": "Documento de entrega/dispensação criado pra este pedido.",
    },
]
