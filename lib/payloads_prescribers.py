"""
Definições do módulo Médico Prescritor (Prescriber).

  - DocType Prescriber: cadastro mestre de profissionais habilitados
    a prescrever (CPF + conselho profissional + UF).
  - Custom Fields:
      Patient.default_prescriber          (Link/Prescriber)
      Sales Order Patient.prescriber      (Link/Prescriber, por linha)

Permite que Customer (comprador) e Prescriber (médico) sejam entidades
independentes — mesmo quando é a mesma pessoa física que compra e
prescreve, são 2 cadastros separados.
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
# Selects
# ---------------------------------------------------------------------------

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
# Prescriber — DocType mestre
# ---------------------------------------------------------------------------

PRESCRIBER = {
    "doctype": "DocType",
    "name": "Prescriber",
    "module": MODULE,
    "custom": 1,
    "is_submittable": 0,
    "track_changes": 1,
    "allow_rename": 1,
    "autoname": "naming_series:",
    "title_field": "full_name",
    "search_fields": "full_name,cpf,council_number",
    "sort_field": "modified",
    "sort_order": "DESC",
    "document_type": "Master",
    "fields": [
        # ----- Identificação -----
        {
            "fieldname": "naming_series",
            "label": "Série",
            "fieldtype": "Select",
            "options": "PRES-.YYYY.-.#####",
            "default": "PRES-.YYYY.-.#####",
            "reqd": 1,
        },
        {
            "fieldname": "full_name",
            "label": "Nome Completo",
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
            "reqd": 1,
            "unique": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "description": "11 dígitos. Pode digitar com ou sem máscara.",
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

        # ----- Conselho Profissional -----
        {
            "fieldname": "section_council",
            "label": "Conselho Profissional",
            "fieldtype": "Section Break",
        },
        {
            "fieldname": "council_type",
            "label": "Tipo de Conselho",
            "fieldtype": "Select",
            "options": COUNCIL_TYPES,
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "default": "CRM",
        },
        {
            "fieldname": "council_other",
            "label": "Outro Conselho (Sigla)",
            "fieldtype": "Data",
            "depends_on": "eval:doc.council_type=='Outro'",
            "mandatory_depends_on": "eval:doc.council_type=='Outro'",
            "description": "Use quando Tipo = Outro. Ex: CFFa, CFM, CRESS.",
        },
        {"fieldname": "column_break_council", "fieldtype": "Column Break"},
        {
            "fieldname": "council_number",
            "label": "Número do Conselho",
            "fieldtype": "Data",
            "reqd": 1,
            "in_list_view": 1,
            "description": "Só números, sem prefixo. Ex: 12345.",
        },
        {
            "fieldname": "council_state",
            "label": "UF do Conselho",
            "fieldtype": "Select",
            "options": UF_OPTIONS,
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
        },
        {
            "fieldname": "council_status",
            "label": "Status do Conselho",
            "fieldtype": "Select",
            "options": COUNCIL_STATUS,
            "default": "Ativo",
            "in_standard_filter": 1,
        },
        {
            "fieldname": "specialty",
            "label": "Especialidade",
            "fieldtype": "Data",
            "description": "Opcional. Ex: Endocrinologia, Cardiologia.",
        },

        # ----- Contato -----
        {
            "fieldname": "section_contact",
            "label": "Contato",
            "fieldtype": "Section Break",
        },
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
            "label": "E-mail Profissional",
            "fieldtype": "Data",
            "options": "Email",
        },

        # ----- Vínculo com Customer (opcional) -----
        {
            "fieldname": "section_clinic",
            "label": "Clínica / Empresa Vinculada",
            "fieldtype": "Section Break",
            "collapsible": 1,
        },
        {
            "fieldname": "clinic_name",
            "label": "Nome da Clínica/Consultório",
            "fieldtype": "Data",
        },
        {
            "fieldname": "customer_link",
            "label": "Customer Vinculado",
            "fieldtype": "Link",
            "options": "Customer",
            "description": (
                "Opcional. Se o médico trabalha numa empresa que já está "
                "cadastrada como Customer, vincule aqui para facilitar "
                "relatórios cruzados."
            ),
        },

        # ----- Endereço -----
        {
            "fieldname": "section_address",
            "label": "Endereço Profissional",
            "fieldtype": "Section Break",
            "collapsible": 1,
        },
        {"fieldname": "postal_code", "label": "CEP", "fieldtype": "Data"},
        {"fieldname": "address_line_1", "label": "Logradouro", "fieldtype": "Data"},
        {"fieldname": "address_number", "label": "Número", "fieldtype": "Data"},
        {"fieldname": "address_complement", "label": "Complemento", "fieldtype": "Data"},
        {"fieldname": "neighborhood", "label": "Bairro", "fieldtype": "Data"},
        {"fieldname": "column_break_addr", "fieldtype": "Column Break"},
        {"fieldname": "city", "label": "Cidade", "fieldtype": "Data"},
        {
            "fieldname": "state",
            "label": "UF",
            "fieldtype": "Select",
            "options": UF_OPTIONS,
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
            "label": "Observações",
            "fieldtype": "Small Text",
        },
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
# Custom Fields: Patient.default_prescriber + Sales Order Patient.prescriber
# ---------------------------------------------------------------------------

PRESCRIBER_CUSTOM_FIELDS = [
    # Patient ganha "default_prescriber" (Link/Prescriber).
    # Mantém prescribing_doctor (Link/Customer) legado pra compat com docs antigos.
    {
        "dt": "Patient",
        "fieldname": "default_prescriber",
        "label": "Médico Prescritor Padrão",
        "fieldtype": "Link",
        "options": "Prescriber",
        "insert_after": "prescribing_doctor",
        "in_standard_filter": 1,
        "description": (
            "Prescriber padrão deste paciente. Substitui prescribing_doctor "
            "(que agora é legado). Pode ser sobrescrito por linha no Sales Order."
        ),
    },
    # Sales Order Patient (child table) ganha "prescriber" — por linha.
    {
        "dt": "Sales Order Patient",
        "fieldname": "prescriber",
        "label": "Prescriber",
        "fieldtype": "Link",
        "options": "Prescriber",
        "insert_after": "item_code",
        "in_list_view": 1,
        "description": (
            "Médico que prescreveu para este paciente neste pedido. "
            "Se omitido, sistema usa Patient.default_prescriber."
        ),
    },
    # Sales Order Patient ganha "prescriber_label" — readonly fetch pra exibir
    # CRM-UF junto.
    {
        "dt": "Sales Order Patient",
        "fieldname": "prescriber_council",
        "label": "Conselho",
        "fieldtype": "Data",
        "fetch_from": "prescriber.council_type",
        "fetch_if_empty": 1,
        "read_only": 1,
        "insert_after": "prescriber",
        "in_list_view": 0,
    },
]
