"""
setup_11_so_dispensation_buttons.py — Client Script no Sales Order com botões
da fase final do fluxo (Alocação + Dispensação + Zebra).

Adiciona 3 botões no group "Produção Futura" do Sales Order submetido:
  1. "Alocar Batch por Paciente"  → future_production_allocate_patient_batches
  2. "Criar Dispensação"          → future_production_create_dispensation_from_so
  3. "Abrir Dispensação"          → navega pra Dispensation já criada (se existir)

Uso:
    python setup_11_so_dispensation_buttons.py
    python setup_11_so_dispensation_buttons.py --uninstall
"""

from __future__ import annotations

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


SO_DISP_SCRIPT = r"""
frappe.ui.form.on('Sales Order', {
    refresh(frm) {
        if (frm.is_new()) return;
        if (frm.doc.docstatus !== 1) return;

        // 1) Alocar Batch por Paciente
        frm.add_custom_button(__('Alocar Batch por Paciente'), () => {
            frappe.confirm(
                __('Distribuir batches dos PRs liberados entre as linhas fp_patients?'),
                () => {
                    frappe.call({
                        method: 'future_production_allocate_patient_batches',
                        args: { sales_order: frm.doc.name },
                        freeze: true,
                        freeze_message: __('Alocando batches...'),
                        callback: (r) => {
                            if (r && r.message) {
                                const n = r.message.allocated_rows || 0;
                                frappe.show_alert({
                                    message: __('{0} linhas de pacientes alocadas.', [n]),
                                    indicator: n > 0 ? 'green' : 'orange'
                                });
                                frm.reload_doc();
                            }
                        }
                    });
                }
            );
        }, __('Produção Futura'));

        // 2) Criar Dispensação (se ainda não tem)
        if (!frm.doc.dispensation) {
            frm.add_custom_button(__('Criar Dispensação'), () => {
                frappe.confirm(
                    __('Criar Dispensação para este pedido? Requer pacientes alocados (batch_no preenchido).'),
                    () => {
                        frappe.call({
                            method: 'future_production_create_dispensation_from_so',
                            args: { sales_order: frm.doc.name },
                            freeze: true,
                            freeze_message: __('Criando Dispensação...'),
                            callback: (r) => {
                                if (r && r.message) {
                                    const disp = r.message.dispensation;
                                    const created = r.message.created;
                                    frappe.show_alert({
                                        message: created
                                            ? __('Dispensação {0} criada com {1} pacientes.',
                                                 [disp, r.message.rows_count])
                                            : __('Dispensação {0} já existia.', [disp]),
                                        indicator: 'green'
                                    });
                                    frm.reload_doc();
                                    setTimeout(() => {
                                        frappe.set_route('Form', 'Dispensation', disp);
                                    }, 800);
                                }
                            },
                            error: (err) => {
                                frappe.msgprint({
                                    title: __('Falha ao criar Dispensação'),
                                    message: (err && err.message) || __('Erro desconhecido'),
                                    indicator: 'red'
                                });
                            }
                        });
                    }
                );
            }, __('Produção Futura'));
        } else {
            // 3) Abrir Dispensação existente
            frm.add_custom_button(__('Abrir Dispensação'), () => {
                frappe.set_route('Form', 'Dispensation', frm.doc.dispensation);
            }, __('Produção Futura'));
        }
    }
});
""".strip()


def install() -> int:
    client = client_from_env()
    log_section("Client Script: Sales Order — botões Dispensação + Alocação")
    try:
        client.upsert_client_script(
            name="Sales Order - Dispensation Buttons",
            dt="Sales Order",
            script=SO_DISP_SCRIPT,
            enabled=1,
        )
        log_ok("Client Script instalado.")
        return 0
    except Exception as exc:
        log_error(f"Falha: {exc}")
        return 1


def uninstall() -> int:
    client = client_from_env()
    log_section("Removendo Client Script Sales Order - Dispensation Buttons")
    try:
        client.delete_client_script("Sales Order - Dispensation Buttons")
    except Exception as exc:
        log_error(f"{exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
