"""
setup_03_server_scripts.py — cria/atualiza os Server Scripts do módulo.

Tipos criados:
  DocType Event (seção 19)
    - validate_future_production_batch          (Before Save)
    - update_future_production_batch_status     (After Save)
    - validate_production_reservation           (Before Save)
    - on_submit_production_reservation          (On Submit)
    - on_cancel_production_reservation          (On Cancel)

  API (seção 17)
    - future_production_reserve_sales_order_item
    - future_production_auto_reserve_sales_order
    - future_production_recalculate_batch
    - future_production_create_work_order
    - future_production_release_batch
    - future_production_replan_pending_qty

Pré-requisito: `server_script_enabled: 1` em common_site_config.json.
No bench:  bench --site <site> set-config -g server_script_enabled 1

Uso:
    python setup_03_server_scripts.py
    python setup_03_server_scripts.py --uninstall

Nota técnica: cada SCRIPT_* abaixo usa aspas simples triplas (r''' ''') como
delimitador externo. Isso permite escrever blocos SQL em aspas duplas triplas
dentro do script Python sem precisar escapar nada.
"""

from __future__ import annotations

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


# ===========================================================================
# DocType Events
# ===========================================================================

SCRIPT_VALIDATE_FPB = r'''
# Future Production Batch -- Before Save
# RB-001, RB-004, RNF-005, fórmulas seção 7.

if not doc.planned_qty or doc.planned_qty <= 0:
    frappe.throw("A Quantidade Planejada precisa ser maior que zero.")

if not doc.item_code:
    frappe.throw("Produto a Produzir é obrigatório.")

if not doc.target_warehouse:
    frappe.throw("Depósito de Produto Acabado é obrigatório.")

reserved = float(doc.reserved_qty or 0)
planned = float(doc.planned_qty or 0)
overbooking_limit = float(doc.overbooking_limit_qty or 0) if doc.allow_overbooking else 0
ceiling = planned + overbooking_limit

if reserved > ceiling:
    frappe.throw(
        "Reservado ({0}) excede o limite permitido ({1}). "
        "Ative Overbooking ou ajuste o Planejado.".format(reserved, ceiling)
    )

doc.available_qty = planned - reserved

produced = float(doc.produced_qty or 0)
released = float(doc.released_qty or 0)
if released > produced:
    frappe.throw("Liberado ({0}) não pode ser maior que Produzido ({1}).".format(released, produced))
doc.pending_release_qty = produced - released
'''.strip()


SCRIPT_UPDATE_FPB_STATUS = r'''
# Future Production Batch -- After Save
# Ajusta status automático segundo seção 7.

reserved = float(doc.reserved_qty or 0)
planned = float(doc.planned_qty or 0)
produced = float(doc.produced_qty or 0)
released = float(doc.released_qty or 0)

if doc.docstatus == 2:
    new_status = "Cancelada"
elif doc.docstatus == 0:
    new_status = "Rascunho"
else:
    if produced > 0 and released >= produced and released > 0:
        new_status = "Liberada Totalmente" if produced >= planned else "Liberada Parcialmente"
    elif produced > 0 and released > 0:
        new_status = "Liberada Parcialmente"
    elif produced > 0 and produced >= planned:
        new_status = "Produzida Totalmente"
    elif produced > 0:
        new_status = "Produzida Parcialmente"
    elif doc.work_order:
        new_status = "Em Produção"
    elif reserved <= 0:
        new_status = "Aberta para Reserva"
    elif reserved >= planned:
        new_status = "Totalmente Reservada"
    else:
        new_status = "Reservada Parcialmente"

if new_status != doc.status:
    frappe.db.set_value("Future Production Batch", doc.name, "status", new_status,
                        update_modified=False)
'''.strip()


SCRIPT_VALIDATE_PR = r'''
# Production Reservation -- Before Save
# RB-002, RB-003, RB-004, RB-005, regras seção 8.

if not doc.reserved_qty or float(doc.reserved_qty) <= 0:
    frappe.throw("Quantidade Reservada precisa ser maior que zero.")

if not doc.future_production_batch:
    frappe.throw("Lote de Produção Futura é obrigatório.")

fpb = frappe.get_doc("Future Production Batch", doc.future_production_batch)

# RB-003: item igual
if fpb.item_code != doc.item_code:
    frappe.throw(
        "Item da reserva ({0}) é diferente do item da produção ({1}).".format(
            doc.item_code, fpb.item_code
        )
    )

# RB-002: pedido aprovado (apenas Sales Order submitted vale)
so_data = frappe.db.get_value("Sales Order", doc.sales_order, ["docstatus", "status"])
if not so_data:
    frappe.throw("Sales Order {0} não encontrado.".format(doc.sales_order))
if so_data[0] != 1:
    frappe.throw("Sales Order {0} precisa estar submetido.".format(doc.sales_order))

# RB-004 / RB-005: saldo
current_reserved = float(fpb.reserved_qty or 0)

if not doc.is_new():
    old_qty = float(frappe.db.get_value("Production Reservation", doc.name, "reserved_qty") or 0)
    current_reserved = current_reserved - old_qty

new_total = current_reserved + float(doc.reserved_qty)
planned = float(fpb.planned_qty or 0)
ceiling = planned + (float(fpb.overbooking_limit_qty or 0) if fpb.allow_overbooking else 0)

if new_total > ceiling:
    available = ceiling - current_reserved
    frappe.throw(
        "Saldo insuficiente. Disponível: {0}, solicitado: {1}.".format(
            available, doc.reserved_qty
        )
    )

released = float(doc.released_qty or 0)
if released > float(doc.reserved_qty):
    frappe.throw("Liberado não pode ser maior que Reservado.")
doc.pending_qty = float(doc.reserved_qty) - released

if doc.docstatus == 2:
    doc.status = "Cancelado"
elif released <= 0:
    doc.status = "Reservado"
elif released >= float(doc.reserved_qty):
    doc.status = "Liberado"
else:
    doc.status = "Parcialmente Liberado"
'''.strip()


SCRIPT_ON_SUBMIT_PR = r'''
# Production Reservation -- On Submit
# Recalcula a produção (via set_value, bypass de UpdateAfterSubmit)
# e atualiza campos espelho no Sales Order Item.

fpb_name = doc.future_production_batch

totals = frappe.db.sql(
    """
    select coalesce(sum(reserved_qty), 0), coalesce(sum(released_qty), 0)
    from `tabProduction Reservation`
    where future_production_batch = %s and docstatus = 1
    """,
    (fpb_name,),
)[0]

fpb_data = frappe.db.get_value(
    "Future Production Batch", fpb_name,
    ["planned_qty", "produced_qty", "docstatus", "work_order", "status"],
    as_dict=True,
)
planned = float(fpb_data.planned_qty or 0)
produced = float(fpb_data.produced_qty or 0)
reserved = float(totals[0] or 0)
released = float(totals[1] or 0)

if produced > 0 and released >= produced and released > 0:
    new_status = "Liberada Totalmente" if produced >= planned else "Liberada Parcialmente"
elif produced > 0 and released > 0:
    new_status = "Liberada Parcialmente"
elif produced > 0 and produced >= planned:
    new_status = "Produzida Totalmente"
elif produced > 0:
    new_status = "Produzida Parcialmente"
elif fpb_data.work_order:
    new_status = "Em Produção"
elif reserved <= 0:
    new_status = "Aberta para Reserva"
elif reserved >= planned:
    new_status = "Totalmente Reservada"
else:
    new_status = "Reservada Parcialmente"

frappe.db.set_value("Future Production Batch", fpb_name, {
    "reserved_qty": reserved,
    "released_qty": released,
    "available_qty": planned - reserved,
    "pending_release_qty": produced - released,
    "status": new_status,
}, update_modified=False)

if doc.sales_order_item:
    item_total = frappe.db.sql(
        """
        select coalesce(sum(reserved_qty), 0), coalesce(sum(released_qty), 0)
        from `tabProduction Reservation`
        where sales_order_item = %s and docstatus = 1
        """,
        (doc.sales_order_item,),
    )[0]

    reserved_total = float(item_total[0] or 0)
    released_total = float(item_total[1] or 0)
    pending_total = reserved_total - released_total

    soi_qty = float(frappe.db.get_value("Sales Order Item", doc.sales_order_item, "qty") or 0)
    if released_total <= 0:
        status_label = "Parcialmente Reservado" if reserved_total < soi_qty else "Reservado"
    elif released_total >= reserved_total:
        status_label = "Liberado"
    else:
        status_label = "Parcialmente Liberado"

    frappe.db.set_value("Sales Order Item", doc.sales_order_item, {
        "fp_future_production_batch": fpb_name,
        "fp_reserved_qty": reserved_total,
        "fp_released_qty": released_total,
        "fp_pending_release_qty": pending_total,
        "fp_reservation_status": status_label,
    }, update_modified=False)
'''.strip()


SCRIPT_ON_CANCEL_PR = r'''
# Production Reservation -- On Cancel
# Devolve saldo (via set_value), atualiza FPB e Sales Order Item.

fpb_name = doc.future_production_batch

totals = frappe.db.sql(
    """
    select coalesce(sum(reserved_qty), 0), coalesce(sum(released_qty), 0)
    from `tabProduction Reservation`
    where future_production_batch = %s and docstatus = 1
    """,
    (fpb_name,),
)[0]

fpb_data = frappe.db.get_value(
    "Future Production Batch", fpb_name,
    ["planned_qty", "produced_qty", "work_order"],
    as_dict=True,
)
planned = float(fpb_data.planned_qty or 0)
produced = float(fpb_data.produced_qty or 0)
reserved = float(totals[0] or 0)
released = float(totals[1] or 0)

if produced > 0 and released >= produced and released > 0:
    new_status = "Liberada Totalmente" if produced >= planned else "Liberada Parcialmente"
elif produced > 0 and released > 0:
    new_status = "Liberada Parcialmente"
elif produced > 0 and produced >= planned:
    new_status = "Produzida Totalmente"
elif produced > 0:
    new_status = "Produzida Parcialmente"
elif fpb_data.work_order:
    new_status = "Em Produção"
elif reserved <= 0:
    new_status = "Aberta para Reserva"
elif reserved >= planned:
    new_status = "Totalmente Reservada"
else:
    new_status = "Reservada Parcialmente"

frappe.db.set_value("Future Production Batch", fpb_name, {
    "reserved_qty": reserved,
    "released_qty": released,
    "available_qty": planned - reserved,
    "pending_release_qty": produced - released,
    "status": new_status,
}, update_modified=False)

frappe.db.set_value("Production Reservation", doc.name, "status", "Cancelado",
                    update_modified=False)

if doc.sales_order_item:
    item_total = frappe.db.sql(
        """
        select coalesce(sum(reserved_qty), 0), coalesce(sum(released_qty), 0)
        from `tabProduction Reservation`
        where sales_order_item = %s and docstatus = 1
        """,
        (doc.sales_order_item,),
    )[0]

    reserved_total = float(item_total[0] or 0)
    released_total = float(item_total[1] or 0)
    pending_total = reserved_total - released_total

    if reserved_total <= 0:
        status_label = "Sem Reserva"
        fpb_link = None
    else:
        soi_qty = float(frappe.db.get_value("Sales Order Item", doc.sales_order_item, "qty") or 0)
        if released_total <= 0:
            status_label = "Parcialmente Reservado" if reserved_total < soi_qty else "Reservado"
        elif released_total >= reserved_total:
            status_label = "Liberado"
        else:
            status_label = "Parcialmente Liberado"
        fpb_link = fpb_name

    frappe.db.set_value("Sales Order Item", doc.sales_order_item, {
        "fp_future_production_batch": fpb_link,
        "fp_reserved_qty": reserved_total,
        "fp_released_qty": released_total,
        "fp_pending_release_qty": pending_total,
        "fp_reservation_status": status_label,
    }, update_modified=False)
'''.strip()


# ===========================================================================
# API Methods (seção 17)
# ===========================================================================

SCRIPT_API_RECALCULATE = r'''
# /api/method/future_production_recalculate_batch
data = frappe.form_dict
fpb_name = data.get("future_production_batch")
if not fpb_name:
    frappe.throw("future_production_batch é obrigatório.")

totals = frappe.db.sql(
    """
    select coalesce(sum(reserved_qty), 0), coalesce(sum(released_qty), 0)
    from `tabProduction Reservation`
    where future_production_batch = %s and docstatus = 1
    """,
    (fpb_name,),
)[0]

fpb_data = frappe.db.get_value(
    "Future Production Batch", fpb_name,
    ["planned_qty", "produced_qty", "work_order"],
    as_dict=True,
)
planned = float(fpb_data.planned_qty or 0)
produced = float(fpb_data.produced_qty or 0)
reserved = float(totals[0] or 0)
released = float(totals[1] or 0)
available = planned - reserved
pending_release = produced - released

if produced > 0 and released >= produced and released > 0:
    new_status = "Liberada Totalmente" if produced >= planned else "Liberada Parcialmente"
elif produced > 0 and released > 0:
    new_status = "Liberada Parcialmente"
elif produced > 0 and produced >= planned:
    new_status = "Produzida Totalmente"
elif produced > 0:
    new_status = "Produzida Parcialmente"
elif fpb_data.work_order:
    new_status = "Em Produção"
elif reserved <= 0:
    new_status = "Aberta para Reserva"
elif reserved >= planned:
    new_status = "Totalmente Reservada"
else:
    new_status = "Reservada Parcialmente"

frappe.db.set_value("Future Production Batch", fpb_name, {
    "reserved_qty": reserved,
    "released_qty": released,
    "available_qty": available,
    "pending_release_qty": pending_release,
    "status": new_status,
}, update_modified=False)

frappe.response["message"] = {
    "future_production_batch": fpb_name,
    "planned_qty": planned,
    "reserved_qty": reserved,
    "available_qty": available,
    "produced_qty": produced,
    "released_qty": released,
    "pending_release_qty": pending_release,
    "status": new_status,
}
'''.strip()


SCRIPT_API_RESERVE = r'''
# /api/method/future_production_reserve_sales_order_item
data = frappe.form_dict
so_name = data.get("sales_order")
soi_id = data.get("sales_order_item")
fpb_name = data.get("future_production_batch")
qty = float(data.get("qty") or 0)
priority = int(data.get("priority") or 100)

if not (so_name and soi_id and fpb_name):
    frappe.throw("sales_order, sales_order_item e future_production_batch são obrigatórios.")
if qty <= 0:
    frappe.throw("qty deve ser maior que zero.")

so = frappe.get_doc("Sales Order", so_name)
if so.docstatus != 1:
    frappe.throw("Sales Order precisa estar submetido.")

soi = None
for row in so.items:
    if row.name == soi_id:
        soi = row
        break
if not soi:
    frappe.throw("Linha {0} não encontrada no Sales Order {1}.".format(soi_id, so_name))

fpb = frappe.get_doc("Future Production Batch", fpb_name)
if fpb.item_code != soi.item_code:
    frappe.throw("Item da linha ({0}) é diferente do item da produção ({1}).".format(
        soi.item_code, fpb.item_code
    ))

available = float(fpb.planned_qty or 0) - float(fpb.reserved_qty or 0)
if fpb.allow_overbooking:
    available = available + float(fpb.overbooking_limit_qty or 0)
if qty > available:
    frappe.throw("Saldo insuficiente. Disponível: {0}, solicitado: {1}.".format(available, qty))

pr = frappe.get_doc({
    "doctype": "Production Reservation",
    "sales_order": so.name,
    "sales_order_item": soi.name,
    "customer": so.customer,
    "item_code": soi.item_code,
    "future_production_batch": fpb.name,
    "reserved_qty": qty,
    "priority": priority,
    "reservation_date": frappe.utils.now_datetime(),
})
pr.insert(ignore_permissions=True)
pr.submit()

available_after = frappe.db.get_value(
    "Future Production Batch", fpb.name, "available_qty"
)
frappe.response["message"] = {
    "reservation": pr.name,
    "future_production_batch": fpb.name,
    "reserved_qty": qty,
    "available_qty_after": float(available_after or 0),
}
'''.strip()


SCRIPT_API_AUTO_RESERVE = r'''
# /api/method/future_production_auto_reserve_sales_order
data = frappe.form_dict
so_name = data.get("sales_order")
if not so_name:
    frappe.throw("sales_order é obrigatório.")

so = frappe.get_doc("Sales Order", so_name)
if so.docstatus != 1:
    frappe.throw("Sales Order precisa estar submetido.")

created = []
errors = []

for row in so.items:
    pending = float(row.qty or 0) - float(row.fp_reserved_qty or 0)
    if pending <= 0:
        continue

    fpbs = frappe.get_all(
        "Future Production Batch",
        filters={
            "item_code": row.item_code,
            "docstatus": 1,
            "status": ["in", [
                "Aberta para Reserva",
                "Reservada Parcialmente",
                "Em Produção",
                "Produzida Parcialmente",
            ]],
        },
        fields=["name", "planned_qty", "reserved_qty", "allow_overbooking",
                "overbooking_limit_qty", "planned_production_date"],
        order_by="planned_production_date asc, creation asc",
    )

    for fpb_row in fpbs:
        if pending <= 0:
            break
        available = float(fpb_row.planned_qty or 0) - float(fpb_row.reserved_qty or 0)
        if fpb_row.allow_overbooking:
            available = available + float(fpb_row.overbooking_limit_qty or 0)
        if available <= 0:
            continue

        take = min(pending, available)
        try:
            pr = frappe.get_doc({
                "doctype": "Production Reservation",
                "sales_order": so.name,
                "sales_order_item": row.name,
                "customer": so.customer,
                "item_code": row.item_code,
                "future_production_batch": fpb_row.name,
                "reserved_qty": take,
                "priority": 100,
                "reservation_date": frappe.utils.now_datetime(),
            })
            pr.insert(ignore_permissions=True)
            pr.submit()
            created.append({
                "reservation": pr.name,
                "sales_order_item": row.name,
                "future_production_batch": fpb_row.name,
                "qty": take,
            })
            pending = pending - take
        except Exception as exc:
            errors.append({"sales_order_item": row.name, "error": str(exc)})
            break

frappe.response["message"] = {
    "sales_order": so.name,
    "reservations": created,
    "errors": errors,
}
'''.strip()


SCRIPT_API_CREATE_WO = r'''
# /api/method/future_production_create_work_order
data = frappe.form_dict
fpb_name = data.get("future_production_batch")
if not fpb_name:
    frappe.throw("future_production_batch é obrigatório.")

fpb = frappe.get_doc("Future Production Batch", fpb_name)
if fpb.docstatus != 1:
    frappe.throw("Lote precisa estar submetido.")
if fpb.work_order:
    frappe.throw("Já existe Work Order vinculada: {0}.".format(fpb.work_order))

bom = fpb.bom
if not bom:
    bom = frappe.db.get_value("BOM",
                              {"item": fpb.item_code, "is_active": 1, "is_default": 1},
                              "name")
if not bom:
    frappe.throw("Nenhuma BOM padrão ativa encontrada para o item {0}.".format(fpb.item_code))

wo = frappe.get_doc({
    "doctype": "Work Order",
    "production_item": fpb.item_code,
    "qty": fpb.planned_qty,
    "bom_no": bom,
    "company": fpb.company,
    "fg_warehouse": fpb.target_warehouse,
    "wip_warehouse": fpb.wip_warehouse,
    "planned_start_date": fpb.planned_production_date,
})
wo.insert(ignore_permissions=True)

updates = {"work_order": wo.name, "status": "Em Produção"}
if not fpb.bom:
    updates["bom"] = bom
frappe.db.set_value("Future Production Batch", fpb.name, updates, update_modified=False)

frappe.response["message"] = {
    "future_production_batch": fpb.name,
    "work_order": wo.name,
    "bom": bom,
}
'''.strip()


SCRIPT_API_RELEASE = r'''
# /api/method/future_production_release_batch
# Distribui o produzido entre as reservas seguindo a regra seção 10.5:
# priority asc, payment_date asc, reservation_date asc, creation asc.

data = frappe.form_dict
fpb_name = data.get("future_production_batch")
if not fpb_name:
    frappe.throw("future_production_batch é obrigatório.")

fpb = frappe.get_doc("Future Production Batch", fpb_name)
if fpb.docstatus != 1:
    frappe.throw("Lote precisa estar submetido.")
if not fpb.produced_qty or float(fpb.produced_qty) <= 0:
    frappe.throw("Quantidade Produzida precisa ser maior que zero.")
if not fpb.batch_no:
    frappe.throw("Lote Real Produzido (batch_no) precisa estar preenchido antes da liberação.")

to_release = float(fpb.produced_qty) - float(fpb.released_qty or 0)

if to_release <= 0:
    frappe.response["message"] = {
        "future_production_batch": fpb.name,
        "released_count": 0,
        "remaining_to_release": 0,
        "message": "Nada a liberar.",
    }
else:
    reservations = frappe.db.sql(
        """
        select name, reserved_qty, released_qty, sales_order_item
        from `tabProduction Reservation`
        where future_production_batch = %s
          and docstatus = 1
          and (coalesce(reserved_qty, 0) - coalesce(released_qty, 0)) > 0
        order by coalesce(priority, 100) asc,
                 payment_date asc,
                 reservation_date asc,
                 creation asc
        """,
        (fpb_name,),
        as_dict=True,
    )

    released_count = 0
    remaining = to_release

    for r in reservations:
        if remaining <= 0:
            break
        pending = float(r.reserved_qty or 0) - float(r.released_qty or 0)
        if pending <= 0:
            continue
        take = min(pending, remaining)
        new_released = float(r.released_qty or 0) + take
        new_pending = float(r.reserved_qty or 0) - new_released

        if new_released >= float(r.reserved_qty or 0):
            new_status = "Liberado"
        else:
            new_status = "Parcialmente Liberado"

        frappe.db.set_value("Production Reservation", r.name, {
            "released_qty": new_released,
            "pending_qty": new_pending,
            "release_batch_no": fpb.batch_no,
            "status": new_status,
        }, update_modified=False)

        if r.sales_order_item:
            item_total = frappe.db.sql(
                """
                select coalesce(sum(reserved_qty), 0), coalesce(sum(released_qty), 0)
                from `tabProduction Reservation`
                where sales_order_item = %s and docstatus = 1
                """,
                (r.sales_order_item,),
            )[0]
            rt = float(item_total[0] or 0)
            # SQL sum ja inclui o set_value anterior (frappe.db.set_value commitou
            # released_qty da PR atual). Usar direto, sem ajuste de delta.
            rl = float(item_total[1] or 0)
            soi_qty = float(frappe.db.get_value("Sales Order Item", r.sales_order_item, "qty") or 0)
            if rl >= rt:
                status_label = "Liberado"
            elif rl > 0:
                status_label = "Parcialmente Liberado"
            elif rt < soi_qty:
                status_label = "Parcialmente Reservado"
            else:
                status_label = "Reservado"

            frappe.db.set_value("Sales Order Item", r.sales_order_item, {
                "fp_reserved_qty": rt,
                "fp_released_qty": rl,
                "fp_pending_release_qty": rt - rl,
                "fp_reservation_status": status_label,
            }, update_modified=False)

        released_count = released_count + 1
        remaining = remaining - take

    fpb_totals = frappe.db.sql(
        """
        select coalesce(sum(released_qty), 0)
        from `tabProduction Reservation`
        where future_production_batch = %s and docstatus = 1
        """,
        (fpb_name,),
    )[0][0]
    new_released_total = float(fpb_totals or 0)
    new_pending = float(fpb.produced_qty or 0) - new_released_total

    reserved = float(fpb.reserved_qty or 0)
    planned = float(fpb.planned_qty or 0)
    produced = float(fpb.produced_qty or 0)
    if produced > 0 and new_released_total >= produced and new_released_total > 0:
        new_status = "Liberada Totalmente" if produced >= planned else "Liberada Parcialmente"
    elif produced > 0 and new_released_total > 0:
        new_status = "Liberada Parcialmente"
    elif produced > 0 and produced >= planned:
        new_status = "Produzida Totalmente"
    elif produced > 0:
        new_status = "Produzida Parcialmente"
    elif fpb.work_order:
        new_status = "Em Produção"
    elif reserved <= 0:
        new_status = "Aberta para Reserva"
    elif reserved >= planned:
        new_status = "Totalmente Reservada"
    else:
        new_status = "Reservada Parcialmente"

    frappe.db.set_value("Future Production Batch", fpb_name, {
        "released_qty": new_released_total,
        "pending_release_qty": new_pending,
        "status": new_status,
    }, update_modified=False)

    frappe.response["message"] = {
        "future_production_batch": fpb_name,
        "released_count": released_count,
        "remaining_to_release": remaining,
        "released_qty": new_released_total,
        "pending_release_qty": new_pending,
    }
'''.strip()


SCRIPT_API_REPLAN = r'''
# /api/method/future_production_replan_pending_qty
data = frappe.form_dict
source_name = data.get("source_reservation")
target_fpb = data.get("target_future_production_batch")
qty = float(data.get("qty") or 0)

if not (source_name and target_fpb):
    frappe.throw("source_reservation e target_future_production_batch são obrigatórios.")
if qty <= 0:
    frappe.throw("qty deve ser maior que zero.")

source = frappe.get_doc("Production Reservation", source_name)
if source.docstatus != 1:
    frappe.throw("Reserva origem precisa estar submetida.")

pending = float(source.reserved_qty or 0) - float(source.released_qty or 0)
if qty > pending:
    frappe.throw("Qty solicitada ({0}) maior que pendente ({1}).".format(qty, pending))

target = frappe.get_doc("Future Production Batch", target_fpb)
if target.item_code != source.item_code:
    frappe.throw("Item do destino diferente do item da reserva original.")

available = float(target.planned_qty or 0) - float(target.reserved_qty or 0)
if target.allow_overbooking:
    available = available + float(target.overbooking_limit_qty or 0)
if qty > available:
    frappe.throw("Saldo insuficiente no destino. Disponível: {0}.".format(available))

new_source_reserved = float(source.reserved_qty or 0) - qty
released_total = float(source.released_qty or 0)
new_source_pending = new_source_reserved - released_total
if new_source_pending <= 0 and released_total == 0:
    new_source_status = "Replanejado"
elif new_source_pending <= 0:
    new_source_status = "Liberado"
else:
    new_source_status = "Parcialmente Liberado"

frappe.db.set_value("Production Reservation", source.name, {
    "reserved_qty": new_source_reserved,
    "pending_qty": new_source_pending,
    "status": new_source_status,
    "notes": (source.notes or "") + "\n[Replanejado] {0} unid -> {1}".format(qty, target_fpb),
}, update_modified=False)

new_pr = frappe.get_doc({
    "doctype": "Production Reservation",
    "sales_order": source.sales_order,
    "sales_order_item": source.sales_order_item,
    "customer": source.customer,
    "item_code": source.item_code,
    "future_production_batch": target.name,
    "reserved_qty": qty,
    "priority": source.priority,
    "payment_date": source.payment_date,
    "reservation_date": frappe.utils.now_datetime(),
    "notes": "Replanejada a partir de {0}".format(source.name),
})
new_pr.insert(ignore_permissions=True)
new_pr.submit()

for batch_name in (source.future_production_batch, target.name):
    t = frappe.db.sql(
        """
        select coalesce(sum(reserved_qty), 0), coalesce(sum(released_qty), 0)
        from `tabProduction Reservation`
        where future_production_batch = %s and docstatus = 1
        """,
        (batch_name,),
    )[0]
    fpb_data = frappe.db.get_value(
        "Future Production Batch", batch_name,
        ["planned_qty", "produced_qty", "work_order"],
        as_dict=True,
    )
    planned = float(fpb_data.planned_qty or 0)
    produced = float(fpb_data.produced_qty or 0)
    reserved = float(t[0] or 0)
    released = float(t[1] or 0)

    if produced > 0 and released >= produced and released > 0:
        new_status = "Liberada Totalmente" if produced >= planned else "Liberada Parcialmente"
    elif produced > 0 and released > 0:
        new_status = "Liberada Parcialmente"
    elif produced > 0 and produced >= planned:
        new_status = "Produzida Totalmente"
    elif produced > 0:
        new_status = "Produzida Parcialmente"
    elif fpb_data.work_order:
        new_status = "Em Produção"
    elif reserved <= 0:
        new_status = "Aberta para Reserva"
    elif reserved >= planned:
        new_status = "Totalmente Reservada"
    else:
        new_status = "Reservada Parcialmente"

    frappe.db.set_value("Future Production Batch", batch_name, {
        "reserved_qty": reserved,
        "released_qty": released,
        "available_qty": planned - reserved,
        "pending_release_qty": produced - released,
        "status": new_status,
    }, update_modified=False)

frappe.response["message"] = {
    "source_reservation": source.name,
    "new_reservation": new_pr.name,
    "target_future_production_batch": target.name,
    "qty": qty,
}
'''.strip()


# ===========================================================================
# Lista declarativa
# ===========================================================================

DOCEVENT_SCRIPTS = [
    {
        "name": "FPB - Validate (Before Save)",
        "script_type": "DocType Event",
        "reference_doctype": "Future Production Batch",
        "doctype_event": "Before Save",
        "enabled": 1,
        "script": SCRIPT_VALIDATE_FPB,
    },
    {
        "name": "FPB - Update Status (After Save)",
        "script_type": "DocType Event",
        "reference_doctype": "Future Production Batch",
        "doctype_event": "After Save",
        "enabled": 1,
        "script": SCRIPT_UPDATE_FPB_STATUS,
    },
    {
        "name": "PR - Validate (Before Save)",
        "script_type": "DocType Event",
        "reference_doctype": "Production Reservation",
        "doctype_event": "Before Save",
        "enabled": 1,
        "script": SCRIPT_VALIDATE_PR,
    },
    {
        "name": "PR - On Submit",
        "script_type": "DocType Event",
        "reference_doctype": "Production Reservation",
        "doctype_event": "After Submit",
        "enabled": 1,
        "script": SCRIPT_ON_SUBMIT_PR,
    },
    {
        "name": "PR - On Cancel",
        "script_type": "DocType Event",
        "reference_doctype": "Production Reservation",
        "doctype_event": "After Cancel",
        "enabled": 1,
        "script": SCRIPT_ON_CANCEL_PR,
    },
]


API_SCRIPTS = [
    {
        "name": "future_production_recalculate_batch",
        "script_type": "API",
        "api_method": "future_production_recalculate_batch",
        "allow_guest": 0,
        "enabled": 1,
        "script": SCRIPT_API_RECALCULATE,
    },
    {
        "name": "future_production_reserve_sales_order_item",
        "script_type": "API",
        "api_method": "future_production_reserve_sales_order_item",
        "allow_guest": 0,
        "enabled": 1,
        "script": SCRIPT_API_RESERVE,
    },
    {
        "name": "future_production_auto_reserve_sales_order",
        "script_type": "API",
        "api_method": "future_production_auto_reserve_sales_order",
        "allow_guest": 0,
        "enabled": 1,
        "script": SCRIPT_API_AUTO_RESERVE,
    },
    {
        "name": "future_production_create_work_order",
        "script_type": "API",
        "api_method": "future_production_create_work_order",
        "allow_guest": 0,
        "enabled": 1,
        "script": SCRIPT_API_CREATE_WO,
    },
    {
        "name": "future_production_release_batch",
        "script_type": "API",
        "api_method": "future_production_release_batch",
        "allow_guest": 0,
        "enabled": 1,
        "script": SCRIPT_API_RELEASE,
    },
    {
        "name": "future_production_replan_pending_qty",
        "script_type": "API",
        "api_method": "future_production_replan_pending_qty",
        "allow_guest": 0,
        "enabled": 1,
        "script": SCRIPT_API_REPLAN,
    },
]


ALL_SCRIPTS = DOCEVENT_SCRIPTS + API_SCRIPTS


def _check_server_scripts_enabled(client) -> bool:
    if client.server_script_enabled():
        return True
    log_error(
        "Server Scripts não habilitados neste site.\n"
        "Habilite no host com:\n"
        "    bench --site <seu_site> set-config -g server_script_enabled 1\n"
        "    bench restart\n"
        "E rode este script novamente."
    )
    return False


def install() -> int:
    client = client_from_env()
    if not _check_server_scripts_enabled(client):
        return 1

    errors = 0
    for spec in ALL_SCRIPTS:
        log_section(f"Server Script: {spec['name']}  ({spec['script_type']})")
        try:
            client.upsert_server_script(spec)
        except Exception as exc:
            log_error(f"{spec['name']}: {exc}")
            errors += 1

    if errors == 0:
        log_ok(f"Server Scripts instalados: {len(ALL_SCRIPTS)}")
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()
    for spec in reversed(ALL_SCRIPTS):
        log_section(f"Removendo Server Script: {spec['name']}")
        try:
            client.delete_server_script(spec["name"])
        except Exception as exc:
            log_error(f"{spec['name']}: {exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
