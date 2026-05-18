"""
setup_02_client_scripts.py — cria/atualiza os Client Scripts do módulo.

Os scripts vivem em registros do DocType `Client Script` (não em arquivos .js do app).
Em cada execução o script existente (mesmo `name`) é atualizado — mudanças aqui se
propagam ao próximo deploy sem precisar criar versões.

Telas afetadas:
  - Future Production Batch: botões Recalcular, Criar Work Order, Liberar Reservas, etc.
  - Sales Order:            Reservar em Produção Futura, Reservar Automaticamente
  - Production Reservation: Replanejar, navegar para Pedido/Produção

Uso:
    python setup_02_client_scripts.py
    python setup_02_client_scripts.py --uninstall
"""

from __future__ import annotations

import sys

from lib.erpnext_api import client_from_env, log_error, log_section


# ---------------------------------------------------------------------------
# Future Production Batch
# ---------------------------------------------------------------------------

FPB_SCRIPT = r"""
frappe.ui.form.on('Future Production Batch', {
    refresh(frm) {
        if (frm.is_new()) return;

        frm.add_custom_button(__('Recalcular Saldos'), () => {
            frappe.call({
                method: 'future_production_recalculate_batch',
                args: { future_production_batch: frm.doc.name },
                freeze: true,
                freeze_message: __('Recalculando saldos...'),
                callback: (r) => {
                    if (r.message) {
                        frappe.show_alert({
                            message: __('Saldos recalculados.'),
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    }
                }
            });
        }, __('Ações'));

        if (frm.doc.docstatus === 1 && !frm.doc.work_order) {
            frm.add_custom_button(__('Criar Work Order'), () => {
                frappe.confirm(
                    __('Criar Work Order para esta produção futura?'),
                    () => {
                        frappe.call({
                            method: 'future_production_create_work_order',
                            args: { future_production_batch: frm.doc.name },
                            freeze: true,
                            callback: (r) => {
                                if (r.message && r.message.work_order) {
                                    frappe.show_alert({
                                        message: __('Work Order {0} criada.', [r.message.work_order]),
                                        indicator: 'green'
                                    });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, __('Ações'));
        }

        if (frm.doc.docstatus === 1 && frm.doc.produced_qty > 0) {
            frm.add_custom_button(__('Liberar Reservas'), () => {
                frappe.confirm(
                    __('Liberar reservas com base em {0} unidades produzidas?',
                       [frm.doc.produced_qty]),
                    () => {
                        frappe.call({
                            method: 'future_production_release_batch',
                            args: { future_production_batch: frm.doc.name },
                            freeze: true,
                            freeze_message: __('Liberando reservas...'),
                            callback: (r) => {
                                if (r.message) {
                                    frappe.show_alert({
                                        message: __('Liberação concluída: {0} reservas processadas.',
                                                    [r.message.released_count || 0]),
                                        indicator: 'green'
                                    });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, __('Ações'));
        }

        frm.add_custom_button(__('Ver Reservas'), () => {
            frappe.set_route('List', 'Production Reservation', {
                future_production_batch: frm.doc.name
            });
        }, __('Ver'));
    },

    item_code(frm) {
        if (frm.doc.item_code && !frm.doc.bom) {
            frappe.db.get_value('BOM',
                { item: frm.doc.item_code, is_active: 1, is_default: 1 },
                'name'
            ).then(r => {
                if (r.message && r.message.name) {
                    frm.set_value('bom', r.message.name);
                }
            });
        }
    },

    planned_qty(frm) {
        const reserved = frm.doc.reserved_qty || 0;
        frm.set_value('available_qty', (frm.doc.planned_qty || 0) - reserved);
    },

    produced_qty(frm) {
        const released = frm.doc.released_qty || 0;
        frm.set_value('pending_release_qty', (frm.doc.produced_qty || 0) - released);
    }
});
""".strip()


# ---------------------------------------------------------------------------
# Sales Order
# ---------------------------------------------------------------------------

SO_SCRIPT = r"""
frappe.ui.form.on('Sales Order', {
    refresh(frm) {
        if (frm.doc.docstatus !== 1) return;

        frm.add_custom_button(__('Reservar em Produção Futura'), () => {
            const items = (frm.doc.items || []).filter(i =>
                (i.qty || 0) > (i.fp_reserved_qty || 0)
            );

            if (!items.length) {
                frappe.msgprint(__('Todos os itens deste pedido já estão totalmente reservados.'));
                return;
            }

            const item_options = items.map(i =>
                `${i.name}|${i.item_code} (${i.qty - (i.fp_reserved_qty || 0)} pendente)`
            );

            const d = new frappe.ui.Dialog({
                title: __('Reservar item em Produção Futura'),
                fields: [
                    {
                        fieldname: 'sales_order_item',
                        label: __('Linha do Pedido'),
                        fieldtype: 'Select',
                        reqd: 1,
                        options: item_options.map(o => o.split('|')[1]).join('\n'),
                        change() {
                            const idx = item_options.findIndex(
                                o => o.split('|')[1] === d.get_value('sales_order_item')
                            );
                            if (idx >= 0) {
                                d.set_value('_row_id', items[idx].name);
                                d.set_value('_item_code', items[idx].item_code);
                                d.fields_dict.future_production_batch.df.get_query = () => ({
                                    filters: {
                                        item_code: items[idx].item_code,
                                        docstatus: 1
                                    }
                                });
                                d.fields_dict.future_production_batch.refresh();
                            }
                        }
                    },
                    { fieldname: '_row_id',     fieldtype: 'Data', hidden: 1 },
                    { fieldname: '_item_code',  fieldtype: 'Data', hidden: 1 },
                    {
                        fieldname: 'future_production_batch',
                        label: __('Lote de Produção Futura'),
                        fieldtype: 'Link',
                        options: 'Future Production Batch',
                        reqd: 1
                    },
                    {
                        fieldname: 'qty',
                        label: __('Quantidade'),
                        fieldtype: 'Float',
                        reqd: 1
                    },
                    {
                        fieldname: 'priority',
                        label: __('Prioridade'),
                        fieldtype: 'Int',
                        default: 100
                    }
                ],
                primary_action_label: __('Reservar'),
                primary_action(values) {
                    frappe.call({
                        method: 'future_production_reserve_sales_order_item',
                        args: {
                            sales_order: frm.doc.name,
                            sales_order_item: values._row_id,
                            future_production_batch: values.future_production_batch,
                            qty: values.qty,
                            priority: values.priority || 100
                        },
                        freeze: true,
                        callback: (r) => {
                            if (r.message && r.message.reservation) {
                                frappe.show_alert({
                                    message: __('Reserva {0} criada. Disponível restante: {1}',
                                                [r.message.reservation, r.message.available_qty_after]),
                                    indicator: 'green'
                                });
                                d.hide();
                                frm.reload_doc();
                            }
                        }
                    });
                }
            });
            d.show();
        }, __('Produção Futura'));

        frm.add_custom_button(__('Reservar Automaticamente'), () => {
            frappe.confirm(
                __('Tentar reservar automaticamente todos os itens pendentes nas produções futuras com saldo?'),
                () => {
                    frappe.call({
                        method: 'future_production_auto_reserve_sales_order',
                        args: { sales_order: frm.doc.name },
                        freeze: true,
                        freeze_message: __('Reservando...'),
                        callback: (r) => {
                            if (r.message) {
                                const created = (r.message.reservations || []).length;
                                frappe.show_alert({
                                    message: __('{0} reservas criadas.', [created]),
                                    indicator: created ? 'green' : 'orange'
                                });
                                frm.reload_doc();
                            }
                        }
                    });
                }
            );
        }, __('Produção Futura'));

        frm.add_custom_button(__('Ver Reservas do Pedido'), () => {
            frappe.set_route('List', 'Production Reservation', {
                sales_order: frm.doc.name
            });
        }, __('Produção Futura'));
    }
});
""".strip()


# ---------------------------------------------------------------------------
# Production Reservation
# ---------------------------------------------------------------------------

PR_SCRIPT = r"""
frappe.ui.form.on('Production Reservation', {
    refresh(frm) {
        if (frm.is_new()) return;

        if (frm.doc.docstatus === 1 && (frm.doc.pending_qty || 0) > 0) {
            frm.add_custom_button(__('Replanejar Pendência'), () => {
                const d = new frappe.ui.Dialog({
                    title: __('Replanejar saldo pendente'),
                    fields: [
                        {
                            fieldname: 'target_future_production_batch',
                            label: __('Próxima Produção Futura'),
                            fieldtype: 'Link',
                            options: 'Future Production Batch',
                            reqd: 1,
                            get_query: () => ({
                                filters: {
                                    item_code: frm.doc.item_code,
                                    docstatus: 1,
                                    name: ['!=', frm.doc.future_production_batch]
                                }
                            })
                        },
                        {
                            fieldname: 'qty',
                            label: __('Quantidade'),
                            fieldtype: 'Float',
                            reqd: 1,
                            default: frm.doc.pending_qty,
                            description: __('Máx: {0}', [frm.doc.pending_qty])
                        }
                    ],
                    primary_action_label: __('Replanejar'),
                    primary_action(values) {
                        if (values.qty > frm.doc.pending_qty) {
                            frappe.msgprint(__('Quantidade maior que a pendente.'));
                            return;
                        }
                        frappe.call({
                            method: 'future_production_replan_pending_qty',
                            args: {
                                source_reservation: frm.doc.name,
                                target_future_production_batch: values.target_future_production_batch,
                                qty: values.qty
                            },
                            freeze: true,
                            callback: (r) => {
                                if (r.message && r.message.new_reservation) {
                                    frappe.show_alert({
                                        message: __('Nova reserva: {0}', [r.message.new_reservation]),
                                        indicator: 'green'
                                    });
                                    d.hide();
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                });
                d.show();
            }, __('Ações'));
        }

        if (frm.doc.sales_order) {
            frm.add_custom_button(__('Ver Pedido'), () => {
                frappe.set_route('Form', 'Sales Order', frm.doc.sales_order);
            }, __('Ver'));
        }

        if (frm.doc.future_production_batch) {
            frm.add_custom_button(__('Ver Produção'), () => {
                frappe.set_route('Form', 'Future Production Batch',
                    frm.doc.future_production_batch);
            }, __('Ver'));
        }
    },

    reserved_qty(frm) {
        const released = frm.doc.released_qty || 0;
        frm.set_value('pending_qty', (frm.doc.reserved_qty || 0) - released);
    }
});
""".strip()


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

SCRIPTS = [
    ("Future Production Batch - UI", "Future Production Batch", FPB_SCRIPT),
    ("Sales Order - Future Production UI", "Sales Order", SO_SCRIPT),
    ("Production Reservation - UI", "Production Reservation", PR_SCRIPT),
]


def install() -> int:
    client = client_from_env()
    errors = 0
    for name, dt, script in SCRIPTS:
        log_section(f"Client Script: {name}")
        try:
            client.upsert_client_script(name=name, dt=dt, script=script, enabled=1)
        except Exception as exc:
            log_error(f"{name}: {exc}")
            errors += 1
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()
    for name, _, _ in SCRIPTS:
        log_section(f"Removendo Client Script: {name}")
        try:
            client.delete_client_script(name)
        except Exception as exc:
            log_error(f"{name}: {exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
