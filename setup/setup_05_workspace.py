"""
setup_05_workspace.py — cria o Workspace "Produção Futura".

Conteúdo (seção 16):
    Produção Futura
        ├── Lotes de Produção Futura     (Future Production Batch)
        ├── Reservas de Produção          (Production Reservation)
        ├── Mapa de Produção              (Report: Mapa de Produção Futura)
        └── Pendências de Liberação       (Report: Pedidos Pendentes de Liberação)

Inclui shortcuts (cards do topo) e a árvore lateral.

Uso:
    python setup_05_workspace.py
    python setup_05_workspace.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import os
import sys

from lib.erpnext_api import client_from_env, log_error, log_section


MODULE = os.environ.get("ERPNEXT_MODULE", "Manufacturing")
WORKSPACE_NAME = "Produção Futura"


# Conteúdo visual do workspace (formato JSON do builder do Frappe 14+).
# Renderizado como cabeçalho + cards de atalhos + cards de links.
WORKSPACE_CONTENT = json.dumps(
    [
        {
            "id": "header_pf",
            "type": "header",
            "data": {"text": "<span class=\"h4\"><b>Produção Futura</b></span>", "col": 12},
        },
        {
            "id": "shortcut_lotes",
            "type": "shortcut",
            "data": {"shortcut_name": "Lotes de Produção Futura", "col": 3},
        },
        {
            "id": "shortcut_reservas",
            "type": "shortcut",
            "data": {"shortcut_name": "Reservas de Produção", "col": 3},
        },
        {
            "id": "shortcut_mapa",
            "type": "shortcut",
            "data": {"shortcut_name": "Mapa de Produção", "col": 3},
        },
        {
            "id": "shortcut_pendencias",
            "type": "shortcut",
            "data": {"shortcut_name": "Pendências de Liberação", "col": 3},
        },
        {
            "id": "shortcut_pacientes",
            "type": "shortcut",
            "data": {"shortcut_name": "Pacientes", "col": 3},
        },
        {
            "id": "spacer1",
            "type": "spacer",
            "data": {"col": 12},
        },
        {
            "id": "card_docs",
            "type": "card",
            "data": {"card_name": "Documentos", "col": 4},
        },
        {
            "id": "card_reports",
            "type": "card",
            "data": {"card_name": "Relatórios", "col": 4},
        },
    ],
    ensure_ascii=False,
)


WORKSPACE = {
    "doctype": "Workspace",
    "name": WORKSPACE_NAME,
    "title": WORKSPACE_NAME,
    "label": WORKSPACE_NAME,
    "module": MODULE,
    "category": "Modules",
    "public": 1,
    "is_hidden": 0,
    "type": "Workspace",
    "icon": "stock",
    "indicator_color": "blue",
    "for_user": "",
    "content": WORKSPACE_CONTENT,
    "links": [
        # ----- Documentos -----
        {
            "label": "Documentos",
            "type": "Card Break",
            "hidden": 0,
            "onboard": 0,
            "is_query_report": 0,
            "icon": "file",
        },
        {
            "label": "Lote de Produção Futura",
            "link_to": "Future Production Batch",
            "link_type": "DocType",
            "type": "Link",
            "hidden": 0,
            "onboard": 1,
            "is_query_report": 0,
            "dependencies": "",
        },
        {
            "label": "Reserva de Produção",
            "link_to": "Production Reservation",
            "link_type": "DocType",
            "type": "Link",
            "hidden": 0,
            "onboard": 1,
            "is_query_report": 0,
            "dependencies": "Future Production Batch",
        },
        {
            "label": "Paciente",
            "link_to": "Patient",
            "link_type": "DocType",
            "type": "Link",
            "hidden": 0,
            "onboard": 1,
            "is_query_report": 0,
        },
        {
            "label": "Sales Order",
            "link_to": "Sales Order",
            "link_type": "DocType",
            "type": "Link",
            "hidden": 0,
            "onboard": 0,
            "is_query_report": 0,
        },
        {
            "label": "Work Order",
            "link_to": "Work Order",
            "link_type": "DocType",
            "type": "Link",
            "hidden": 0,
            "onboard": 0,
            "is_query_report": 0,
        },
        # ----- Relatórios -----
        {
            "label": "Relatórios",
            "type": "Card Break",
            "hidden": 0,
            "onboard": 0,
            "is_query_report": 0,
            "icon": "chart",
        },
        {
            "label": "Mapa de Produção Futura",
            "link_to": "Mapa de Produção Futura",
            "link_type": "Report",
            "type": "Link",
            "hidden": 0,
            "onboard": 0,
            "is_query_report": 0,
        },
        {
            "label": "Reservas por Produção",
            "link_to": "Reservas por Produção",
            "link_type": "Report",
            "type": "Link",
            "hidden": 0,
            "onboard": 0,
            "is_query_report": 0,
        },
        {
            "label": "Pedidos Pendentes de Liberação",
            "link_to": "Pedidos Pendentes de Liberação",
            "link_type": "Report",
            "type": "Link",
            "hidden": 0,
            "onboard": 0,
            "is_query_report": 0,
        },
        {
            "label": "Risco de Produção",
            "link_to": "Risco de Produção",
            "link_type": "Report",
            "type": "Link",
            "hidden": 0,
            "onboard": 0,
            "is_query_report": 0,
        },
    ],
    "shortcuts": [
        {
            "label": "Lotes de Produção Futura",
            "link_to": "Future Production Batch",
            "type": "DocType",
            "color": "Blue",
            "format": "{} ativos",
            "stats_filter": json.dumps({"docstatus": 1}),
        },
        {
            "label": "Reservas de Produção",
            "link_to": "Production Reservation",
            "type": "DocType",
            "color": "Green",
            "format": "{} ativas",
            "stats_filter": json.dumps({"docstatus": 1}),
        },
        {
            "label": "Pacientes",
            "link_to": "Patient",
            "type": "DocType",
            "color": "Purple",
            "format": "{} cadastrados",
        },
        {
            "label": "Mapa de Produção",
            "link_to": "Mapa de Produção Futura",
            "type": "Report",
            "color": "Cyan",
        },
        {
            "label": "Pendências de Liberação",
            "link_to": "Pedidos Pendentes de Liberação",
            "type": "Report",
            "color": "Orange",
        },
    ],
}


def install() -> int:
    client = client_from_env()
    log_section(f"Workspace: {WORKSPACE_NAME}")
    try:
        client.upsert_workspace(WORKSPACE)
        return 0
    except Exception as exc:
        log_error(f"{WORKSPACE_NAME}: {exc}")
        return 1


def uninstall() -> int:
    client = client_from_env()
    log_section(f"Removendo Workspace: {WORKSPACE_NAME}")
    try:
        client.delete_workspace(WORKSPACE_NAME)
    except Exception as exc:
        log_error(f"{WORKSPACE_NAME}: {exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
