"""
Definições declarativas de DocTypes, Custom Fields, Client Scripts, Server Scripts,
Reports e Workspace para o módulo Reserva de Produção Futura.

Baseado na documentação em
`../documentacao_erpnext_reserva_producao_futura_api_v2.md`
(seções 7, 8, 9, 15, 18, 19, 20).
"""

from __future__ import annotations

import os


MODULE = os.environ.get("ERPNEXT_MODULE", "Manufacturing")


# ---------------------------------------------------------------------------
# Helpers de permissões
# ---------------------------------------------------------------------------

def _full_perm(role: str) -> dict:
    return {
        "role": role,
        "read": 1,
        "write": 1,
        "create": 1,
        "delete": 1,
        "submit": 1,
        "cancel": 1,
        "amend": 1,
        "report": 1,
        "export": 1,
        "print": 1,
        "email": 1,
        "share": 1,
    }


def _operator_perm(role: str) -> dict:
    return {
        "role": role,
        "read": 1,
        "write": 1,
        "create": 1,
        "submit": 1,
        "report": 1,
        "export": 1,
        "print": 1,
        "email": 1,
    }


def _reader_perm(role: str) -> dict:
    return {
        "role": role,
        "read": 1,
        "report": 1,
        "export": 1,
        "print": 1,
    }


# ---------------------------------------------------------------------------
# Future Production Batch
# ---------------------------------------------------------------------------

STATUS_FPB = "\n".join([
    "Rascunho",
    "Aberta para Reserva",
    "Reservada Parcialmente",
    "Totalmente Reservada",
    "Fechada para Reserva",
    "Em Produção",
    "Produzida Parcialmente",
    "Produzida Totalmente",
    "Liberada Parcialmente",
    "Liberada Totalmente",
    "Cancelada",
])


FUTURE_PRODUCTION_BATCH = {
    "doctype": "DocType",
    "name": "Future Production Batch",
    "module": MODULE,
    "custom": 1,
    "is_submittable": 1,
    "track_changes": 1,
    "allow_rename": 0,
    "autoname": "naming_series:",
    "title_field": "production_code",
    "search_fields": "production_code,item_code,status",
    "sort_field": "modified",
    "sort_order": "DESC",
    "document_type": "Document",
    "fields": [
        # ----- Identificação -----
        {
            "fieldname": "naming_series",
            "label": "Série",
            "fieldtype": "Select",
            "options": "FPB-.YYYY.-.#####",
            "default": "FPB-.YYYY.-.#####",
            "reqd": 1,
        },
        {
            "fieldname": "production_code",
            "label": "Código da Produção",
            "fieldtype": "Data",
            "reqd": 1,
            "unique": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "bold": 1,
        },
        {"fieldname": "column_break_id", "fieldtype": "Column Break"},
        {
            "fieldname": "company",
            "label": "Empresa",
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1,
            "in_standard_filter": 1,
        },
        {
            "fieldname": "status",
            "label": "Status",
            "fieldtype": "Select",
            "options": STATUS_FPB,
            "reqd": 1,
            "default": "Rascunho",
            "in_list_view": 1,
            "in_standard_filter": 1,
            "bold": 1,
            "allow_on_submit": 1,
        },
        # ----- Produto -----
        {"fieldname": "section_break_product", "label": "Produto", "fieldtype": "Section Break"},
        {
            "fieldname": "item_code",
            "label": "Produto a Produzir",
            "fieldtype": "Link",
            "options": "Item",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
        },
        {
            "fieldname": "item_name",
            "label": "Nome do Produto",
            "fieldtype": "Data",
            "read_only": 1,
            "fetch_from": "item_code.item_name",
            "fetch_if_empty": 1,
        },
        {"fieldname": "column_break_product", "fieldtype": "Column Break"},
        {
            "fieldname": "uom",
            "label": "Unidade de Medida",
            "fieldtype": "Link",
            "options": "UOM",
            "read_only": 1,
            "fetch_from": "item_code.stock_uom",
            "fetch_if_empty": 1,
        },
        {
            "fieldname": "bom",
            "label": "BOM",
            "fieldtype": "Link",
            "options": "BOM",
        },
        # ----- Quantidades -----
        {"fieldname": "section_break_qty", "label": "Quantidades", "fieldtype": "Section Break"},
        {
            "fieldname": "planned_qty",
            "label": "Quantidade Planejada",
            "fieldtype": "Float",
            "reqd": 1,
            "in_list_view": 1,
            "non_negative": 1,
        },
        {
            "fieldname": "reserved_qty",
            "label": "Quantidade Reservada",
            "fieldtype": "Float",
            "read_only": 1,
            "default": 0,
            "non_negative": 1,
            "allow_on_submit": 1,
        },
        {
            "fieldname": "available_qty",
            "label": "Quantidade Disponível",
            "fieldtype": "Float",
            "read_only": 1,
            "default": 0,
            "allow_on_submit": 1,
        },
        {"fieldname": "column_break_qty", "fieldtype": "Column Break"},
        {
            "fieldname": "produced_qty",
            "label": "Quantidade Produzida",
            "fieldtype": "Float",
            "default": 0,
            "non_negative": 1,
            "allow_on_submit": 1,
        },
        {
            "fieldname": "released_qty",
            "label": "Quantidade Liberada",
            "fieldtype": "Float",
            "read_only": 1,
            "default": 0,
            "non_negative": 1,
            "allow_on_submit": 1,
        },
        {
            "fieldname": "pending_release_qty",
            "label": "Pendente de Liberação",
            "fieldtype": "Float",
            "read_only": 1,
            "default": 0,
            "allow_on_submit": 1,
        },
        # ----- Datas -----
        {"fieldname": "section_break_dates", "label": "Datas", "fieldtype": "Section Break"},
        {
            "fieldname": "planned_production_date",
            "label": "Data Prevista de Produção",
            "fieldtype": "Date",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "expected_release_date",
            "label": "Data Prevista de Liberação",
            "fieldtype": "Date",
        },
        {"fieldname": "column_break_dates", "fieldtype": "Column Break"},
        {
            "fieldname": "reservation_cutoff_datetime",
            "label": "Limite para Reserva",
            "fieldtype": "Datetime",
        },
        # ----- Vínculos -----
        {"fieldname": "section_break_links", "label": "Vínculos", "fieldtype": "Section Break"},
        {
            "fieldname": "production_plan",
            "label": "Plano de Produção",
            "fieldtype": "Link",
            "options": "Production Plan",
        },
        {
            "fieldname": "work_order",
            "label": "Ordem de Produção",
            "fieldtype": "Link",
            "options": "Work Order",
            "allow_on_submit": 1,
        },
        {"fieldname": "column_break_links", "fieldtype": "Column Break"},
        {
            "fieldname": "batch_no",
            "label": "Lote Real Produzido",
            "fieldtype": "Link",
            "options": "Batch",
            "allow_on_submit": 1,
        },
        # ----- Depósitos -----
        {"fieldname": "section_break_warehouses", "label": "Depósitos", "fieldtype": "Section Break"},
        {
            "fieldname": "target_warehouse",
            "label": "Depósito de Produto Acabado",
            "fieldtype": "Link",
            "options": "Warehouse",
            "reqd": 1,
        },
        {"fieldname": "column_break_warehouses", "fieldtype": "Column Break"},
        {
            "fieldname": "wip_warehouse",
            "label": "Depósito WIP",
            "fieldtype": "Link",
            "options": "Warehouse",
        },
        # ----- Overbooking -----
        {
            "fieldname": "section_break_overbooking",
            "label": "Overbooking",
            "fieldtype": "Section Break",
            "collapsible": 1,
        },
        {
            "fieldname": "allow_overbooking",
            "label": "Permitir Reserva Acima do Planejado",
            "fieldtype": "Check",
            "default": 0,
        },
        {"fieldname": "column_break_overbooking", "fieldtype": "Column Break"},
        {
            "fieldname": "overbooking_limit_qty",
            "label": "Limite de Overbooking",
            "fieldtype": "Float",
            "default": 0,
            "depends_on": "eval:doc.allow_overbooking==1",
        },
        # ----- Observações -----
        {
            "fieldname": "section_break_notes",
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
        _full_perm("Manufacturing Manager"),
        _operator_perm("Manufacturing User"),
        _reader_perm("Sales User"),
        _reader_perm("Stock User"),
    ],
}


# ---------------------------------------------------------------------------
# Production Reservation
# ---------------------------------------------------------------------------

STATUS_PR = "\n".join([
    "Reservado",
    "Parcialmente Liberado",
    "Liberado",
    "Cancelado",
    "Replanejado",
])


PRODUCTION_RESERVATION = {
    "doctype": "DocType",
    "name": "Production Reservation",
    "module": MODULE,
    "custom": 1,
    "is_submittable": 1,
    "track_changes": 1,
    "allow_rename": 0,
    "autoname": "naming_series:",
    "title_field": "customer",
    "search_fields": "sales_order,customer,future_production_batch",
    "sort_field": "modified",
    "sort_order": "DESC",
    "document_type": "Document",
    "fields": [
        {
            "fieldname": "naming_series",
            "label": "Série",
            "fieldtype": "Select",
            "options": "PR-.YYYY.-.#####",
            "default": "PR-.YYYY.-.#####",
            "reqd": 1,
        },
        {
            "fieldname": "status",
            "label": "Status",
            "fieldtype": "Select",
            "options": STATUS_PR,
            "reqd": 1,
            "default": "Reservado",
            "in_list_view": 1,
            "in_standard_filter": 1,
            "bold": 1,
            "allow_on_submit": 1,
        },
        # ----- Pedido -----
        {"fieldname": "section_break_so", "label": "Pedido", "fieldtype": "Section Break"},
        {
            "fieldname": "sales_order",
            "label": "Pedido de Venda",
            "fieldtype": "Link",
            "options": "Sales Order",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
        },
        {
            "fieldname": "sales_order_item",
            "label": "Linha do Pedido",
            "fieldtype": "Data",
            "reqd": 1,
            "description": "ID (name) da linha do Sales Order Item",
        },
        {"fieldname": "column_break_so", "fieldtype": "Column Break"},
        {
            "fieldname": "customer",
            "label": "Cliente",
            "fieldtype": "Link",
            "options": "Customer",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "fetch_from": "sales_order.customer",
            "fetch_if_empty": 1,
        },
        {
            "fieldname": "priority",
            "label": "Prioridade",
            "fieldtype": "Int",
            "default": 100,
            "description": "Menor valor = libera primeiro",
        },
        # ----- Item / Produção -----
        {"fieldname": "section_break_item", "label": "Item / Produção", "fieldtype": "Section Break"},
        {
            "fieldname": "item_code",
            "label": "Produto",
            "fieldtype": "Link",
            "options": "Item",
            "reqd": 1,
            "in_list_view": 1,
        },
        {"fieldname": "column_break_item", "fieldtype": "Column Break"},
        {
            "fieldname": "future_production_batch",
            "label": "Lote de Produção Futura",
            "fieldtype": "Link",
            "options": "Future Production Batch",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
        },
        # ----- Quantidades -----
        {"fieldname": "section_break_qty", "label": "Quantidades", "fieldtype": "Section Break"},
        {
            "fieldname": "reserved_qty",
            "label": "Quantidade Reservada",
            "fieldtype": "Float",
            "reqd": 1,
            "in_list_view": 1,
            "non_negative": 1,
        },
        {
            "fieldname": "released_qty",
            "label": "Quantidade Liberada",
            "fieldtype": "Float",
            "read_only": 1,
            "default": 0,
            "non_negative": 1,
            "allow_on_submit": 1,
        },
        {"fieldname": "column_break_qty", "fieldtype": "Column Break"},
        {
            "fieldname": "pending_qty",
            "label": "Quantidade Pendente",
            "fieldtype": "Float",
            "read_only": 1,
            "default": 0,
            "allow_on_submit": 1,
        },
        # ----- Datas -----
        {"fieldname": "section_break_dates", "label": "Datas", "fieldtype": "Section Break"},
        {
            "fieldname": "payment_date",
            "label": "Data do Pagamento",
            "fieldtype": "Datetime",
            "description": "Usada para FIFO de liberação",
        },
        {"fieldname": "column_break_dates", "fieldtype": "Column Break"},
        {
            "fieldname": "reservation_date",
            "label": "Data da Reserva",
            "fieldtype": "Datetime",
            "default": "now",
        },
        # ----- Pós-produção -----
        {"fieldname": "section_break_post", "label": "Pós-Produção", "fieldtype": "Section Break"},
        {
            "fieldname": "release_batch_no",
            "label": "Lote Real Liberado",
            "fieldtype": "Link",
            "options": "Batch",
            "allow_on_submit": 1,
        },
        {"fieldname": "column_break_post", "fieldtype": "Column Break"},
        {
            "fieldname": "delivery_note",
            "label": "Nota de Entrega",
            "fieldtype": "Link",
            "options": "Delivery Note",
            "allow_on_submit": 1,
        },
        # ----- Observações -----
        {
            "fieldname": "section_break_notes",
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
        _full_perm("Manufacturing Manager"),
        _operator_perm("Manufacturing User"),
        _operator_perm("Sales User"),
        _reader_perm("Stock User"),
    ],
}


# ---------------------------------------------------------------------------
# Custom Fields no Sales Order Item (seção 9)
#
# Os nomes têm prefixo `fp_` para evitar colisão com campos nativos
# (Sales Order Item já possui `reserved_qty` usado pelo Stock Reservation Entry).
# ---------------------------------------------------------------------------

STATUS_RESERVA_SOI = "\n".join([
    "",
    "Sem Reserva",
    "Reservado",
    "Parcialmente Reservado",
    "Liberado",
    "Parcialmente Liberado",
    "Pendente",
])


SALES_ORDER_ITEM_FIELDS = [
    {
        "dt": "Sales Order Item",
        "fieldname": "fp_section",
        "label": "Produção Futura",
        "fieldtype": "Section Break",
        "insert_after": "delivery_date",
        "collapsible": 1,
    },
    {
        "dt": "Sales Order Item",
        "fieldname": "fp_future_production_batch",
        "label": "Lote de Produção Futura",
        "fieldtype": "Link",
        "options": "Future Production Batch",
        "insert_after": "fp_section",
        "read_only": 1,
    },
    {
        "dt": "Sales Order Item",
        "fieldname": "fp_reserved_qty",
        "label": "Qtd. Reservada em Produção",
        "fieldtype": "Float",
        "insert_after": "fp_future_production_batch",
        "read_only": 1,
        "default": 0,
    },
    {
        "dt": "Sales Order Item",
        "fieldname": "fp_column_break",
        "fieldtype": "Column Break",
        "insert_after": "fp_reserved_qty",
    },
    {
        "dt": "Sales Order Item",
        "fieldname": "fp_released_qty",
        "label": "Qtd. Liberada",
        "fieldtype": "Float",
        "insert_after": "fp_column_break",
        "read_only": 1,
        "default": 0,
    },
    {
        "dt": "Sales Order Item",
        "fieldname": "fp_pending_release_qty",
        "label": "Qtd. Pendente de Liberação",
        "fieldtype": "Float",
        "insert_after": "fp_released_qty",
        "read_only": 1,
        "default": 0,
    },
    {
        "dt": "Sales Order Item",
        "fieldname": "fp_reservation_status",
        "label": "Status da Reserva",
        "fieldtype": "Select",
        "options": STATUS_RESERVA_SOI,
        "insert_after": "fp_pending_release_qty",
        "read_only": 1,
        "default": "Sem Reserva",
    },
]
