"""
Custom Fields de visibilidade — mostram dados completos do Patient e Prescriber
direto na linha de fp_patients do Sales Order. Operador não precisa clicar
em link pra ver: nome, CPF, gênero, contato, cidade, conselho do médico.
"""

from __future__ import annotations


FORM_VISIBILITY_FIELDS = [
    # ----- Dados do Patient (fetch_from) -----
    {
        "dt": "Sales Order Patient",
        "fieldname": "patient_gender",
        "label": "Gênero",
        "fieldtype": "Data",
        "fetch_from": "patient.gender",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "mobile",
        "in_list_view": 0,
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "patient_birth_date",
        "label": "Nascimento",
        "fieldtype": "Date",
        "fetch_from": "patient.birth_date",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "patient_gender",
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "patient_email",
        "label": "E-mail",
        "fieldtype": "Data",
        "options": "Email",
        "fetch_from": "patient.email",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "patient_birth_date",
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "patient_city",
        "label": "Cidade",
        "fieldtype": "Data",
        "fetch_from": "patient.city",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "patient_email",
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "patient_state",
        "label": "UF",
        "fieldtype": "Data",
        "fetch_from": "patient.state",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "patient_city",
    },

    # ----- Dados do Prescriber (fetch_from) -----
    {
        "dt": "Sales Order Patient",
        "fieldname": "prescriber_full_name",
        "label": "Médico",
        "fieldtype": "Data",
        "fetch_from": "prescriber.full_name",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "prescriber_council",
        "in_list_view": 1,
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "prescriber_number",
        "label": "Nº Conselho",
        "fieldtype": "Data",
        "fetch_from": "prescriber.council_number",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "prescriber_full_name",
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "prescriber_state",
        "label": "UF Conselho",
        "fieldtype": "Data",
        "fetch_from": "prescriber.council_state",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "prescriber_number",
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "prescriber_status",
        "label": "Status Conselho",
        "fieldtype": "Data",
        "fetch_from": "prescriber.council_status",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "prescriber_state",
    },

    # ----- Dados do Batch (fetch_from) -----
    {
        "dt": "Sales Order Patient",
        "fieldname": "batch_expiry_date",
        "label": "Validade do Lote",
        "fieldtype": "Date",
        "fetch_from": "batch_no.expiry_date",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "batch_no",
        "in_list_view": 1,
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "batch_manufacturing_date",
        "label": "Fabricação do Lote",
        "fieldtype": "Date",
        "fetch_from": "batch_no.manufacturing_date",
        "fetch_if_empty": 0,
        "read_only": 1,
        "insert_after": "batch_expiry_date",
    },
]
