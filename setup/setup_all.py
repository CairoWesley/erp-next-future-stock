"""
setup_all.py — orquestrador que executa todos os passos do setup em sequência.

Ordem de instalação:
    1. setup_01_structure         — DocTypes + Custom Fields
    2. setup_02_client_scripts    — botões UI
    3. setup_03_server_scripts    — validações + endpoints
    4. setup_04_reports           — relatórios
    5. setup_05_workspace         — menu

Ordem de desinstalação (--uninstall) é a inversa.

Uso:
    python setup_all.py                # instala tudo
    python setup_all.py --uninstall    # remove tudo
    python setup_all.py --skip 3,4     # pula os passos 3 e 4
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import sys
from importlib import import_module
from typing import Callable

from lib.erpnext_api import log_error, log_ok, log_section


STEPS: list[tuple[int, str, str]] = [
    (1, "setup_01_structure",       "DocTypes + Custom Fields"),
    (2, "setup_02_client_scripts",  "Client Scripts (botões UI)"),
    (3, "setup_03_server_scripts",  "Server Scripts (validações + endpoints)"),
    (4, "setup_04_reports",         "Reports"),
    (5, "setup_05_workspace",       "Workspace / Menu"),
    (6, "setup_06_patients",        "Módulo Lote × Pacientes"),
    (7, "setup_07_prescribers",     "Módulo Médico Prescritor"),
    (8, "setup_08_patient_batch",   "Batch por Paciente (alocação)"),
    (9, "setup_09_form_visibility", "Form Visibility (fetch fields)"),
    (10, "setup_10_dispensation",   "Dispensação + Etiqueta Zebra"),
    (11, "setup_11_so_dispensation_buttons", "Botões UI no Sales Order"),
    (13, "setup_13_so_validation",  "Validações Pré-Reserva (pagamento/receitas/HubSpot)"),
    (15, "setup_15_naming_series",  "Naming Series auto-increment (format:{#####})"),
    (16, "setup_16_form_layout",    "Form Layout (todos campos críticos visíveis)"),
    (18, "setup_18_receita_attach", "Receita Attach (Custom Fields Sales Order Patient)"),
]


def _resolve(module_name: str, uninstall: bool) -> Callable[[], int]:
    module = import_module(module_name)
    return module.uninstall if uninstall else module.install


def run(uninstall: bool = False, skip: set[int] | None = None) -> int:
    skip = skip or set()
    sequence = list(reversed(STEPS)) if uninstall else STEPS
    action = "Removendo" if uninstall else "Instalando"
    failed: list[str] = []
    total = len(STEPS)

    for num, module_name, label in sequence:
        if num in skip:
            log_section(f"[{num}/{total}] SKIP — {label}")
            continue
        log_section(f"[{num}/{total}] {action}: {label}")
        try:
            rc = _resolve(module_name, uninstall)()
            if rc != 0:
                failed.append(label)
        except Exception as exc:
            log_error(f"Falha em {module_name}: {exc}")
            failed.append(label)

    log_section("Resumo")
    if failed:
        log_error(f"Passos com erro: {', '.join(failed)}")
        return 1
    log_ok(f"{action} concluído com sucesso.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Orquestrador do setup do módulo Reserva de Produção Futura."
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove tudo em ordem inversa (não apaga dados — só metadados).",
    )
    parser.add_argument(
        "--skip",
        type=str,
        default="",
        help="Lista de passos a pular, separados por vírgula. Ex: --skip 3,4,6",
    )
    args = parser.parse_args(argv)

    skip: set[int] = set()
    if args.skip:
        try:
            skip = {int(s.strip()) for s in args.skip.split(",") if s.strip()}
        except ValueError:
            log_error("--skip aceita apenas números, ex: --skip 3,4")
            return 2

    return run(uninstall=args.uninstall, skip=skip)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
