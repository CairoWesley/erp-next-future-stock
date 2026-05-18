"""
Definições do módulo Batch por Paciente.

Adiciona ao child table Sales Order Patient:
  - batch_no             : Link/Batch (lote físico atribuído a este paciente)
  - allocated_qty        : Float (quanto da qty já foi amarrado a um batch)
  - batch_status         : Select (Pendente / Parcialmente Alocado / Alocado / Entregue / Cancelado)

Endpoint `future_production_allocate_patient_batches(sales_order)` é o
preenche essas colunas automaticamente, seguindo FIFO sobre as PRs do
SO já liberadas.
"""

from __future__ import annotations

BATCH_STATUS_OPTIONS = "\n".join([
    "Pendente",
    "Parcialmente Alocado",
    "Alocado",
    "Entregue",
    "Cancelado",
])


PATIENT_BATCH_CUSTOM_FIELDS = [
    {
        "dt": "Sales Order Patient",
        "fieldname": "batch_no",
        "label": "Lote Atribuído",
        "fieldtype": "Link",
        "options": "Batch",
        "insert_after": "qty",
        "in_list_view": 1,
        "description": (
            "Lote físico atribuído a este paciente. Preenchido automaticamente "
            "via future_production_allocate_patient_batches após liberação."
        ),
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "allocated_qty",
        "label": "Qtd Alocada em Lote",
        "fieldtype": "Float",
        "default": 0,
        "non_negative": 1,
        "insert_after": "batch_no",
        "in_list_view": 0,
        "read_only": 1,
        "description": "Parte da qty solicitada que já tem batch_no atribuído.",
    },
    {
        "dt": "Sales Order Patient",
        "fieldname": "batch_status",
        "label": "Status de Alocação",
        "fieldtype": "Select",
        "options": BATCH_STATUS_OPTIONS,
        "default": "Pendente",
        "insert_after": "allocated_qty",
        "in_list_view": 1,
        "read_only": 1,
        "in_standard_filter": 1,
    },
]
