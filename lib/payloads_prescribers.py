"""
Definições do módulo Médico Prescritor (v2 — child table de conselhos).

Modelo:
  - 1 Prescriber = 1 pessoa (CPF único)
  - Child table `councils[]` = N registros profissionais (CRM, CRO, CRF, etc.)
  - 1 médico pode ter múltiplos conselhos (1 CPF + N CRMs)
  - SO/Patient apontam: prescriber (pessoa) + prescriber_council_row (qual CRM)
"""

from __future__ import annotations

import os


MODULE = os.environ.get("ERPNEXT_MODULE", "Manufacturing")


def _full_perm(role: str) -> dict:
    return {"role": role, "read": 1, "write": 1, "create": 1, "delete": 1,
            "report": 1, "export": 1, "print": 1, "email": 1, "share": 1}


def _operator_perm(role: str) -> dict:
    return {"role": role, "read": 1, "write": 1, "create": 1,
            "report": 1, "export": 1, "print": 1, "email": 1}


def _reader_perm(role: str) -> dict:
    return {"role": role, "read": 1, "report": 1, "export": 1, "print": 1}


COUNCIL_TYPES = "\n".join([
    "CRM",       # Médico
    "CRO",       # Dentista
    "CRF",       # Farmacêutico
    "CRBM",      # Biomédico
    "CRN",       # Nutricionista
    "CRBio",     # Biólogo
    "CRP",       # Psicólogo
    "Outro",
])

COUNCIL_STATUS = "\nAtivo\nSuspenso\nCassado"
GENDER_OPTIONS = "\nMasculino\nFeminino\nOutro"
UF_OPTIONS = "\n".join([
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
])


# ---------------------------------------------------------------------------
# Prescriber Council — child table (1 linha = 1 registro profissional)
# ---------------------------------------------------------------------------

PRESCRIBER_COUNCIL = {
    "doctype": "DocType",
    "name": "Prescriber Council",
    "module": MODULE,
    "custom": 1,
    "istable": 1,
    "editable_grid": 1,
    "fields": [
        {
            "fieldname": "council_type",
            "label": "Tipo",
            "fieldtype": "Select",
            "options": COUNCIL_TYPES,
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "council_other",
            "label": "Sigla (se Outro)",
            "fieldtype": "Data",
            "depends_on": "eval:doc.council_type=='Outro'",
        },
        {
            "fieldname": "council_number",
            "label": "Número",
            "fieldtype": "Data",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "council_state",
            "label": "UF",
            "fieldtype": "Select",
            "options": UF_OPTIONS,
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "council_status",
            "label": "Status",
            "fieldtype": "Select",
            "options": COUNCIL_STATUS,
            "default": "Ativo",
            "in_list_view": 1,
        },
        {
            "fieldname": "specialty",
            "label": "Especialidade",
            "fieldtype": "Data",
        },
        {
            "fieldname": "is_primary",
            "label": "Principal",
            "fieldtype": "Check",
            "default": 0,
            "in_list_view": 1,
        },
        {
            "fieldname": "row_notes",
            "label": "Obs",
            "fieldtype": "Small Text",
        },
    ],
}


# ---------------------------------------------------------------------------
# Prescriber — DocType principal (pessoa)
# ---------------------------------------------------------------------------

PRESCRIBER = {
    "doctype": "DocType",
    "name": "Prescriber",
    "module": MODULE,
    "custom": 1,
    "is_submittable": 0,
    "allow_rename": 1,
    "autoname": "naming_series:",
    "title_field": "full_name",
    "search_fields": "full_name,cpf",
    "sort_field": "modified",
    "sort_order": "DESC",
    "fields": [
        {
            "fieldname": "sb_id",
            "fieldtype": "Section Break",
            "label": "Identificação",
        },
        {
            "fieldname": "naming_series",
            "label": "Série",
            "fieldtype": "Select",
            "options": "PRES-.YYYY.-.#####",
            "reqd": 1,
        },
        {
            "fieldname": "full_name",
            "label": "Nome Completo",
            "fieldtype": "Data",
            "reqd": 1,
            "in_list_view": 1,
            "in_global_search": 1,
        },
        {
            "fieldname": "cpf",
            "label": "CPF",
            "fieldtype": "Data",
            "reqd": 1,
            "unique": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
        },
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

        # Child table com N conselhos
        {
            "fieldname": "sb_councils",
            "fieldtype": "Section Break",
            "label": "Conselhos Profissionais",
        },
        {
            "fieldname": "councils",
            "label": "Conselhos",
            "fieldtype": "Table",
            "options": "Prescriber Council",
            "reqd": 1,
            "description": "1+ conselhos profissionais. Marque 1 como Principal.",
        },

        # Contato
        {
            "fieldname": "sb_contact",
            "fieldtype": "Section Break",
            "label": "Contato",
            "collapsible": 1,
        },
        {"fieldname": "mobile", "label": "Celular", "fieldtype": "Data"},
        {"fieldname": "phone", "label": "Telefone Fixo", "fieldtype": "Data"},
        {"fieldname": "email", "label": "E-mail Profissional", "fieldtype": "Data", "options": "Email"},

        # Vínculo Customer
        {
            "fieldname": "sb_clinic",
            "fieldtype": "Section Break",
            "label": "Clínica/Empresa",
            "collapsible": 1,
        },
        {"fieldname": "clinic_name", "label": "Clínica", "fieldtype": "Data"},
        {"fieldname": "customer_link", "label": "Customer Vinculado", "fieldtype": "Link", "options": "Customer"},

        # Endereço
        {
            "fieldname": "sb_address",
            "fieldtype": "Section Break",
            "label": "Endereço",
            "collapsible": 1,
        },
        {"fieldname": "postal_code", "label": "CEP", "fieldtype": "Data"},
        {"fieldname": "address_line_1", "label": "Logradouro", "fieldtype": "Data"},
        {"fieldname": "address_number", "label": "Número", "fieldtype": "Data"},
        {"fieldname": "address_complement", "label": "Complemento", "fieldtype": "Data"},
        {"fieldname": "neighborhood", "label": "Bairro", "fieldtype": "Data"},
        {"fieldname": "city", "label": "Cidade", "fieldtype": "Data"},
        {"fieldname": "state", "label": "UF", "fieldtype": "Select", "options": UF_OPTIONS},
        {"fieldname": "country", "label": "País", "fieldtype": "Link", "options": "Country", "default": "Brazil"},

        {
            "fieldname": "sb_notes",
            "fieldtype": "Section Break",
            "label": "Observações",
            "collapsible": 1,
        },
        {"fieldname": "notes", "label": "Observações", "fieldtype": "Small Text"},
    ],
    "permissions": [
        _full_perm("System Manager"),
        _operator_perm("Sales User"),
        _operator_perm("Sales Manager"),
        _reader_perm("Manufacturing User"),
        _reader_perm("Stock User"),
    ],
}


# ---------------------------------------------------------------------------
# Custom Fields — Patient + Sales Order Patient
# ---------------------------------------------------------------------------

PRESCRIBER_CUSTOM_FIELDS = [
    # Patient: prescriber padrão + qual conselho usar
    {
        "dt": "Patient",
        "fieldname": "default_prescriber",
        "label": "Médico Prescritor Padrão",
        "fieldtype": "Link",
        "options": "Prescriber",
        "insert_after": "prescribing_doctor",
        "in_standard_filter": 1,
    },
    {
        "dt": "Patient",
        "fieldname": "default_council_label",
        "label": "Conselho Padrão",
        "fieldtype": "Data",
        "insert_after": "default_prescriber",
        "description": "Texto livre: CRM-SP 12345 (informativo). Conselho real é escolhido no SO.",
    },

    # Sales Order Patient: prescriber + qual conselho usado nesta linha
    {
        "dt": "Sales Order Patient",
        "fieldname": "prescriber",
        "label": "Médico Prescritor",
        "fieldtype": "Link",
        "options": "Prescriber",
        "insert_after": "item_code",
        "in_list_view": 1,
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "prescriber_council_row",
        "label": "Conselho Usado",
        "fieldtype": "Data",
        "insert_after": "prescriber",
        "description": "ID da linha do child Prescriber.councils que está sendo usado neste pedido.",
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "prescriber_council",
        "label": "Tipo Conselho",
        "fieldtype": "Data",
        "insert_after": "prescriber_council_row",
        "in_list_view": 1,
    },
]
