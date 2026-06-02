"""
Custom Fields de validação pré-reserva no Sales Order.

3 flags + dados de auditoria. Reserva só rola quando 3 flags = True.
Webhooks externos (checkout, receita) atualizam flags.
"""

from __future__ import annotations


VALIDATION_STATUS_OPTIONS = "\n".join([
    "Aguardando Pagamento",
    "Aguardando Receitas",
    "Aguardando Cadastro HubSpot",
    "Aguardando Múltiplas Validações",
    "Validado (Pronto para Reservar)",
    "Reservado",
])


VALIDATION_SO_FIELDS = [
    # ----- Section break -----
    {
        "dt": "Sales Order",
        "fieldname": "section_validation",
        "label": "Validações Pré-Reserva",
        "fieldtype": "Section Break",
        "insert_after": "fp_patients",
        "collapsible": 1,
    },

    # ----- Status consolidado -----
    {
        "dt": "Sales Order",
        "fieldname": "validation_status",
        "label": "Status Validação",
        "fieldtype": "Select",
        "options": VALIDATION_STATUS_OPTIONS,
        "default": "Aguardando Múltiplas Validações",
        "insert_after": "section_validation",
        "in_list_view": 1,
        "in_standard_filter": 1,
        "read_only": 1,
        "allow_on_submit": 1,
    },
    {
        "dt": "Sales Order",
        "fieldname": "validation_blockers",
        "label": "Bloqueios",
        "fieldtype": "Small Text",
        "insert_after": "validation_status",
        "read_only": 1,
        "allow_on_submit": 1,
        "description": "Lista do que falta validar pra liberar reserva.",
    },

    # ----- 1) Pagamento -----
    {
        "dt": "Sales Order",
        "fieldname": "cb_payment",
        "fieldtype": "Column Break",
        "insert_after": "validation_blockers",
    },
    {
        "dt": "Sales Order",
        "fieldname": "payment_validated",
        "label": "Pagamento Confirmado",
        "fieldtype": "Check",
        "default": 0,
        "insert_after": "cb_payment",
        "in_list_view": 1,
        "in_standard_filter": 1,
        "allow_on_submit": 1,
        "description": "Atualizado pelo webhook do checkout.",
    },
    {
        "dt": "Sales Order",
        "fieldname": "payment_validated_at",
        "label": "Pago em",
        "fieldtype": "Datetime",
        "insert_after": "payment_validated",
        "read_only": 1,
        "allow_on_submit": 1,
    },
    {
        "dt": "Sales Order",
        "fieldname": "payment_reference",
        "label": "ID Transação Checkout",
        "fieldtype": "Data",
        "insert_after": "payment_validated_at",
        "allow_on_submit": 1,
    },
    {
        "dt": "Sales Order",
        "fieldname": "payment_amount",
        "label": "Valor Pago",
        "fieldtype": "Currency",
        "insert_after": "payment_reference",
        "allow_on_submit": 1,
    },

    # ----- 2) Receitas -----
    {
        "dt": "Sales Order",
        "fieldname": "cb_prescriptions",
        "fieldtype": "Column Break",
        "insert_after": "payment_amount",
    },
    {
        "dt": "Sales Order",
        "fieldname": "prescriptions_validated",
        "label": "Receitas Validadas",
        "fieldtype": "Check",
        "default": 0,
        "insert_after": "cb_prescriptions",
        "in_list_view": 1,
        "in_standard_filter": 1,
        "allow_on_submit": 1,
        "description": "Atualizado pelo webhook do sistema próprio de receitas.",
    },
    {
        "dt": "Sales Order",
        "fieldname": "prescriptions_validated_at",
        "label": "Receitas Validadas em",
        "fieldtype": "Datetime",
        "insert_after": "prescriptions_validated",
        "read_only": 1,
        "allow_on_submit": 1,
    },
    {
        "dt": "Sales Order",
        "fieldname": "prescriptions_reference",
        "label": "Referência Receitas",
        "fieldtype": "Data",
        "insert_after": "prescriptions_validated_at",
        "allow_on_submit": 1,
    },
    {
        "dt": "Sales Order",
        "fieldname": "prescriptions_qty_validated",
        "label": "Qtd Receitas Validadas",
        "fieldtype": "Int",
        "insert_after": "prescriptions_reference",
        "allow_on_submit": 1,
        "description": "Soma das qty validadas pelo sistema de receitas.",
    },

    # ----- 3) HubSpot -----
    {
        "dt": "Sales Order",
        "fieldname": "cb_hubspot",
        "fieldtype": "Column Break",
        "insert_after": "prescriptions_qty_validated",
    },
    {
        "dt": "Sales Order",
        "fieldname": "hubspot_complete",
        "label": "Cadastro HubSpot Completo",
        "fieldtype": "Check",
        "default": 0,
        "insert_after": "cb_hubspot",
        "in_list_view": 1,
        "in_standard_filter": 1,
        "allow_on_submit": 1,
        "description": "Marcado pelo endpoint issue_order quando HubSpot envia payload válido.",
    },
    {
        "dt": "Sales Order",
        "fieldname": "hubspot_validated_at",
        "label": "HubSpot Validado em",
        "fieldtype": "Datetime",
        "insert_after": "hubspot_complete",
        "read_only": 1,
        "allow_on_submit": 1,
    },
    {
        "dt": "Sales Order",
        "fieldname": "hubspot_deal_id",
        "label": "HubSpot Deal ID",
        "fieldtype": "Data",
        "insert_after": "hubspot_validated_at",
        "allow_on_submit": 1,
    },
    {
        "dt": "Sales Order",
        "fieldname": "hubspot_contact_id",
        "label": "HubSpot Contact ID",
        "fieldtype": "Data",
        "insert_after": "hubspot_deal_id",
        "allow_on_submit": 1,
    },
]
