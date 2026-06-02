"""
Definições do módulo Lote × Pacientes.

  - DocType Patient (Paciente): cadastro mestre
  - DocType Sales Order Patient (Child Table): pacientes vinculados a um item do SO
  - Custom Fields no Sales Order: seção + tabela
"""

from __future__ import annotations

import os


MODULE = os.environ.get("ERPNEXT_MODULE", "Manufacturing")


def _full_perm(role: str) -> dict:
    return {
        "role": role,
        "read": 1, "write": 1, "create": 1, "delete": 1,
        "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
    }


def _operator_perm(role: str) -> dict:
    return {
        "role": role,
        "read": 1, "write": 1, "create": 1,
        "report": 1, "export": 1, "print": 1, "email": 1,
    }


def _reader_perm(role: str) -> dict:
    return {"role": role, "read": 1, "report": 1, "export": 1, "print": 1}


# ---------------------------------------------------------------------------
# Patient — DocType mestre
# ---------------------------------------------------------------------------

GENDER_OPTIONS = "\nMasculino\nFeminino\nOutro"


PATIENT = {
    "doctype": "DocType",
    "name": "Patient",
    "module": MODULE,
    "custom": 1,
    "is_submittable": 0,
    "track_changes": 1,
    "allow_rename": 1,
    "autoname": "naming_series:",
    "title_field": "patient_name",
    "search_fields": "patient_name,cpf,mobile",
    "sort_field": "modified",
    "sort_order": "DESC",
    "document_type": "Master",
    "fields": [
        {
            "fieldname": "naming_series",
            "label": "Série",
            "fieldtype": "Select",
            "options": "PAC-.YYYY.-.#####",
            "default": "PAC-.YYYY.-.#####",
            "reqd": 1,
        },
        {
            "fieldname": "patient_name",
            "label": "Nome do Paciente",
            "fieldtype": "Data",
            "reqd": 1,
            "in_list_view": 1,
            "in_global_search": 1,
            "bold": 1,
        },
        {"fieldname": "column_break_id", "fieldtype": "Column Break"},
        {
            "fieldname": "cpf",
            "label": "CPF",
            "fieldtype": "Data",
            "unique": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "in_global_search": 1,
            "description": "Use apenas dígitos (será validado).",
        },
        {
            "fieldname": "rg",
            "label": "RG",
            "fieldtype": "Data",
        },

        # ----- Dados pessoais -----
        {"fieldname": "section_personal", "label": "Dados Pessoais", "fieldtype": "Section Break"},
        {
            "fieldname": "birth_date",
            "label": "Data de Nascimento",
            "fieldtype": "Date",
        },
        {
            "fieldname": "gender",
            "label": "Gênero",
            "fieldtype": "Select",
            "options": GENDER_OPTIONS,
        },
        {"fieldname": "column_break_personal", "fieldtype": "Column Break"},
        {
            "fieldname": "prescribing_doctor",
            "label": "Médico Prescritor",
            "fieldtype": "Link",
            "options": "Customer",
            "in_standard_filter": 1,
            "description": "Cliente do tipo médico/clínica vinculado a este paciente.",
        },

        # ----- Contato -----
        {"fieldname": "section_contact", "label": "Contato", "fieldtype": "Section Break"},
        {
            "fieldname": "mobile",
            "label": "Celular",
            "fieldtype": "Data",
            "in_list_view": 1,
        },
        {
            "fieldname": "phone",
            "label": "Telefone Fixo",
            "fieldtype": "Data",
        },
        {"fieldname": "column_break_contact", "fieldtype": "Column Break"},
        {
            "fieldname": "email",
            "label": "Email",
            "fieldtype": "Data",
            "options": "Email",
        },

        # ----- Endereço -----
        {"fieldname": "section_address", "label": "Endereço de Entrega", "fieldtype": "Section Break"},
        {
            "fieldname": "postal_code",
            "label": "CEP",
            "fieldtype": "Data",
        },
        {
            "fieldname": "address_line_1",
            "label": "Logradouro",
            "fieldtype": "Data",
        },
        {
            "fieldname": "address_number",
            "label": "Número",
            "fieldtype": "Data",
        },
        {
            "fieldname": "address_complement",
            "label": "Complemento",
            "fieldtype": "Data",
        },
        {"fieldname": "column_break_address", "fieldtype": "Column Break"},
        {
            "fieldname": "neighborhood",
            "label": "Bairro",
            "fieldtype": "Data",
        },
        {
            "fieldname": "city",
            "label": "Cidade",
            "fieldtype": "Data",
            "in_list_view": 1,
        },
        {
            "fieldname": "state",
            "label": "UF",
            "fieldtype": "Data",
        },
        {
            "fieldname": "country",
            "label": "País",
            "fieldtype": "Link",
            "options": "Country",
            "default": "Brazil",
        },

        # ----- Observações -----
        {
            "fieldname": "section_notes",
            "label": "Observações",
            "fieldtype": "Section Break",
            "collapsible": 1,
        },
        {
            "fieldname": "notes",
            "label": "Observações Clínicas/Operacionais",
            "fieldtype": "Small Text",
        },
    ],
    "permissions": [
        _full_perm("System Manager"),
        _operator_perm("Sales User"),
        _operator_perm("Sales Manager"),
        _reader_perm("Stock User"),
        _reader_perm("Manufacturing User"),
    ],
}


# ---------------------------------------------------------------------------
# Sales Order Patient — Child Table
# ---------------------------------------------------------------------------

SALES_ORDER_PATIENT = {
    "doctype": "DocType",
    "name": "Sales Order Patient",
    "module": MODULE,
    "custom": 1,
    "istable": 1,
    "track_changes": 0,
    "editable_grid": 1,
    "fields": [
        {
            "fieldname": "patient",
            "label": "Paciente",
            "fieldtype": "Link",
            "options": "Patient",
            "reqd": 1,
            "in_list_view": 1,
            "columns": 2,
        },
        {
            "fieldname": "patient_name",
            "label": "Nome",
            "fieldtype": "Data",
            "fetch_from": "patient.patient_name",
            "fetch_if_empty": 0,
            "read_only": 1,
            "in_list_view": 1,
            "columns": 2,
        },
        {
            "fieldname": "cpf",
            "label": "CPF",
            "fieldtype": "Data",
            "fetch_from": "patient.cpf",
            "fetch_if_empty": 0,
            "read_only": 1,
            "in_list_view": 1,
            "columns": 1,
        },
        {
            "fieldname": "mobile",
            "label": "Celular",
            "fieldtype": "Data",
            "fetch_from": "patient.mobile",
            "fetch_if_empty": 0,
            "read_only": 1,
            "in_list_view": 1,
            "columns": 1,
        },
        {
            "fieldname": "item_code",
            "label": "Item",
            "fieldtype": "Link",
            "options": "Item",
            "reqd": 1,
            "in_list_view": 1,
            "columns": 2,
        },
        {
            "fieldname": "qty",
            "label": "Qtd.",
            "fieldtype": "Float",
            "reqd": 1,
            "default": 1,
            "in_list_view": 1,
            "columns": 1,
            "non_negative": 1,
        },
        {
            "fieldname": "ph",
            "label": "pH",
            "fieldtype": "Float",
            "precision": "2",
            "columns": 1,
        },
        {
            "fieldname": "delivery_address_override",
            "label": "Endereço de Entrega (se diferente do cadastro)",
            "fieldtype": "Small Text",
        },
        {
            "fieldname": "notes",
            "label": "Observação",
            "fieldtype": "Small Text",
        },
    ],
}


# ---------------------------------------------------------------------------
# Custom Fields no Sales Order — seção Pacientes + tabela
# ---------------------------------------------------------------------------

SALES_ORDER_PATIENT_FIELDS = [
    {
        "dt": "Sales Order",
        "fieldname": "fp_patients_section",
        "label": "Pacientes",
        "fieldtype": "Section Break",
        "insert_after": "items",
        "collapsible": 0,
    },
    {
        "dt": "Sales Order",
        "fieldname": "fp_patients",
        "label": "Pacientes Vinculados",
        "fieldtype": "Table",
        "options": "Sales Order Patient",
        "insert_after": "fp_patients_section",
        "description": (
            "Para cada item do pedido, listar os pacientes que receberão as ampolas. "
            "A soma das quantidades dos pacientes por item deve ser igual à quantidade "
            "do item no pedido."
        ),
    },
]
