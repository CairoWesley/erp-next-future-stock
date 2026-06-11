"""
setup_23_external_api.py — API EXTERNA patient-free pra gerar pedido que
consome estoque futuro (FPB). Sistema externo chama via REST.

Caminho (sem paciente):
  estoque futuro (FPB) → pedido (SO) → reserva (consome FPB).

Endpoints:
  future_production_create_batch
    body: { item_code, planned_qty, production_code?, planned_production_date?,
            target_warehouse?, company? }
    → cria + submete o FPB (estoque futuro). Retorna nome + saldo.

  future_production_create_order
    body: { customer, items:[{item_code, qty, rate, fpb_name?, warehouse?}],
            auto_reserve?, company?, delivery_date?, hubspot_deal_id? }
    → cria + submete o Sales Order E reserva cada linha contra o FPB
      (fpb_name explicito por item; ou auto_reserve=true → FIFO lote aberto).
      Reserva = CONSOME o estoque futuro (FPB.available cai). SEM pacientes.
    → retorna { sales_order, reservations[], reserve_errors[] }.
    Idempotente por hubspot_deal_id (se informado).

Reusa o hook "PR - On Submit" (atualiza FPB) — aqui so cria a Production
Reservation. Mesmo catalogo de erros do step_reserve.

Uso:
    python setup/setup_23_external_api.py
    python setup/setup_23_external_api.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


SCRIPT_CREATE_BATCH = r'''
# /api/method/future_production_create_batch
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)

item_code = data.get("item_code")
if not item_code:
    frappe.throw("[MISSING_ITEM] item_code e obrigatorio.")
if not frappe.db.exists("Item", item_code):
    frappe.throw("[ITEM_NOT_FOUND] Item nao encontrado: " + str(item_code))
planned = float(data.get("planned_qty") or 0)
if planned <= 0:
    frappe.throw("[INVALID_QTY] planned_qty deve ser maior que zero.")

company = data.get("company") or "Injemedpharma"
code = (data.get("production_code") or "").strip() or ("LOTE-" + str(item_code))
ppd = data.get("planned_production_date") or frappe.utils.today()
wh = data.get("target_warehouse") or "Produtos Acabados - I"

b = frappe.new_doc("Future Production Batch")
b.production_code = code
b.company = company
b.status = "Aberta para Reserva"
b.item_code = item_code
b.planned_qty = planned
b.planned_production_date = ppd
b.target_warehouse = wh
b.insert(ignore_permissions=True)
b.submit()

avail = frappe.db.get_value("Future Production Batch", b.name, "available_qty")
frappe.response["message"] = {
    "ok": True,
    "future_production_batch": b.name,
    "production_code": code,
    "item_code": item_code,
    "planned_qty": planned,
    "available_qty": float(avail if avail is not None else planned),
    "status": b.status,
}
'''.strip()


SCRIPT_CREATE_ORDER = r'''
# /api/method/future_production_create_order
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)

cust = data.get("customer")
if not cust:
    frappe.throw("[MISSING_CUSTOMER] customer e obrigatorio.")
if not frappe.db.exists("Customer", cust):
    found = frappe.db.get_value("Customer", {"customer_name": cust}, "name")
    if found:
        cust = found
    else:
        frappe.throw("[CUSTOMER_NOT_FOUND] Cliente nao encontrado: " + str(cust))

company = data.get("company") or "Injemedpharma"
items_in = data.get("items") or []
if not items_in:
    frappe.throw("[NO_ITEMS] items e obrigatorio.")
auto = int(data.get("auto_reserve") or 0)
ddate = data.get("delivery_date") or frappe.utils.add_days(frappe.utils.today(), 30)
deal = (data.get("hubspot_deal_id") or "").strip()

# Idempotency por deal
existing = None
if deal:
    existing = frappe.db.get_value("Sales Order",
        {"hubspot_deal_id": deal, "docstatus": ["!=", 2]}, "name")

if existing:
    so_name = existing
else:
    so = frappe.new_doc("Sales Order")
    so.customer = cust
    so.company = company
    so.transaction_date = frappe.utils.today()
    so.delivery_date = ddate
    so.currency = "BRL"
    so.selling_price_list = "Venda Padrão"
    so.price_list_currency = "BRL"
    so.plc_conversion_rate = 1
    so.conversion_rate = 1
    if deal:
        so.hubspot_deal_id = deal
    for it in items_in:
        so.append("items", {
            "item_code": it.get("item_code"),
            "qty": float(it.get("qty") or 0),
            "rate": float(it.get("rate") or 0),
            "warehouse": it.get("warehouse") or "Produtos Acabados - I",
            "delivery_date": ddate,
        })
    so.insert(ignore_permissions=True)
    so.submit()
    so_name = so.name

# item_code -> fpb_name (do input)
fpb_for = {}
for it in items_in:
    ic = (it.get("item_code") or "").strip()
    fn = (it.get("fpb_name") or it.get("future_production_batch") or "").strip()
    if ic and fn:
        fpb_for[ic] = fn

def pick_fifo(item_code, need):
    rows = frappe.db.sql(
        "select name from `tabFuture Production Batch` "
        "where item_code=%s and docstatus=1 "
        "and status in ('Aberta para Reserva','Reservada Parcialmente') "
        "and (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) >= %s "
        "order by planned_production_date asc, creation asc limit 1",
        (item_code, need), as_dict=False)
    return rows[0][0] if rows else None

so_doc = frappe.get_doc("Sales Order", so_name)
reservations = []
errors = []
for row in so_doc.items:
    ic = row.item_code
    is_stock = frappe.db.get_value("Item", ic, "is_stock_item")
    if not int(is_stock or 0):
        continue
    already = frappe.db.sql(
        "select coalesce(sum(reserved_qty),0) from `tabProduction Reservation` "
        "where sales_order=%s and sales_order_item=%s and docstatus=1",
        (so_name, row.name), as_dict=False)
    already_qty = float((already[0][0] if already else 0) or 0)
    need = float(row.qty or 0) - already_qty
    if need <= 0:
        continue

    fpb_name = fpb_for.get(ic)
    if not fpb_name and auto:
        fpb_name = pick_fifo(ic, need)
    if not fpb_name:
        errors.append({"code": "BATCH_REQUIRED", "item_code": ic,
            "error": "Lote obrigatorio para " + str(ic) +
            " (informe fpb_name no item, ou auto_reserve=true com lote aberto)."})
        continue

    info = frappe.db.sql(
        "select (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) as avail, "
        "item_code, status, docstatus from `tabFuture Production Batch` where name=%s",
        (fpb_name,), as_dict=True)
    if not info:
        errors.append({"code": "BATCH_NOT_FOUND", "item_code": ic, "fpb": fpb_name,
            "error": "Lote " + fpb_name + " nao encontrado"})
        continue
    info = info[0]
    if int(info.docstatus or 0) != 1:
        errors.append({"code": "BATCH_NOT_SUBMITTED", "item_code": ic, "fpb": fpb_name,
            "error": "Lote " + fpb_name + " nao esta submetido"})
        continue
    if info.item_code != ic:
        errors.append({"code": "BATCH_WRONG_ITEM", "item_code": ic, "fpb": fpb_name,
            "error": "Lote " + fpb_name + " e de outro produto (" + str(info.item_code) + ")"})
        continue
    if (info.status or "") not in ("Aberta para Reserva", "Reservada Parcialmente"):
        errors.append({"code": "BATCH_CLOSED", "item_code": ic, "fpb": fpb_name,
            "error": "Lote " + fpb_name + " nao aceita reservas (status: " + str(info.status) + ")"})
        continue
    if float(info.avail or 0) < need:
        errors.append({"code": "INSUFFICIENT_QTY", "item_code": ic, "fpb": fpb_name,
            "qty": need, "available": float(info.avail or 0),
            "error": "Saldo insuficiente no lote " + fpb_name +
            " (disponivel " + str(float(info.avail or 0)) + ", solicitado " + str(need) + ")"})
        continue

    pr = frappe.new_doc("Production Reservation")
    pr.sales_order = so_name
    pr.sales_order_item = row.name
    pr.future_production_batch = fpb_name
    pr.item_code = ic
    pr.customer = so_doc.customer
    pr.reserved_qty = need
    pr.insert(ignore_permissions=True)
    pr.submit()
    reservations.append({"reservation": pr.name, "future_production_batch": fpb_name,
        "item_code": ic, "reserved_qty": need})

frappe.response["message"] = {
    "ok": True,
    "sales_order": so_name,
    "grand_total": frappe.db.get_value("Sales Order", so_name, "grand_total"),
    "reservations": reservations,
    "reserve_errors": errors,
}
'''.strip()


ENDPOINTS = [
    ("future_production_create_batch", SCRIPT_CREATE_BATCH),
    ("future_production_create_order", SCRIPT_CREATE_ORDER),
]


def install() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1
    log_section("API externa patient-free (create_batch / create_order)")
    rc = 0
    for name, script in ENDPOINTS:
        try:
            client.upsert_server_script({
                "name": name, "script_type": "API", "api_method": name,
                "allow_guest": 0, "enabled": 1, "script": script,
            })
            log_ok(f"Endpoint {name} pronto.")
        except Exception as exc:  # noqa: BLE001
            log_error(f"{name}: {exc}")
            rc = 1
    return rc


def uninstall() -> int:
    client = client_from_env()
    for name, _ in ENDPOINTS:
        try:
            client.delete_server_script(name)
        except Exception as exc:  # noqa: BLE001
            log_error(f"{name}: {exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
