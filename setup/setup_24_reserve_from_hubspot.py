"""
setup_24_reserve_from_hubspot.py — endpoint que puxa o pedido do HubSpot
(line items + SKU) e gera a reserva (consome estoque futuro). Patient-free.

URL (sistema externo / browser com auth):
  GET/POST /api/method/future_production_reserve_from_hubspot?id=<DEAL_ID>

Fluxo:
  1. Lê o token HubSpot da config (Injemed Financial Settings.hubspot_access_token).
  2. GET deal {id} no HubSpot → associations line_items + companies.
  3. Cada line item → hs_sku (UPPERCASE) + quantity. Mapeia SKU → Item ERPNext.
  4. Resolve customer (param > empresa associada ao deal > "Cliente HubSpot <id>").
  5. Cria Sales Order (idempotente por hubspot_deal_id) + reserva cada item
     (auto_reserve FIFO por padrão; ou fpb_map {item:lote}).
  6. Retorna { sales_order, reservations, reserve_errors, unmatched_skus }.

Params:
  id | deal_id   (obrigatório)
  auto_reserve   (default 1 — FIFO; 0 = só cria SO, sem reservar sem fpb_map)
  fpb_map        ({item_code: fpb_name} — lote explícito por item)
  customer       (override do cliente)
  company        (default da config / "Unikka Pharma")
  warehouse      (default "Produtos Acabados - UP")

Requer: Server Scripts habilitados + token HubSpot na config + outbound HTTP.

Uso:
    python setup/setup_24_reserve_from_hubspot.py
    python setup/setup_24_reserve_from_hubspot.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


SCRIPT = r'''
# /api/method/future_production_reserve_from_hubspot
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)

deal_id = str(data.get("deal_id") or data.get("id") or "").strip()
if not deal_id:
    frappe.throw("[MISSING_DEAL] Informe id (deal HubSpot). Ex: ?id=123456")

cfg = frappe.get_doc("Injemed Financial Settings", "Injemed Financial Settings")
# Password field: get() devolve o valor encriptado — get_password() decripta.
try:
    token = cfg.get_password("hubspot_access_token")
except Exception:
    token = cfg.get("hubspot_access_token")
if not token:
    frappe.throw("[NO_HUBSPOT_TOKEN] Configure o token HubSpot em "
                 "Injemed Financial Settings (campo hubspot_access_token).")

company = data.get("company") or cfg.get("company") or "Unikka Pharma"
warehouse = data.get("warehouse") or "Produtos Acabados - UP"
auto = int(data.get("auto_reserve") if data.get("auto_reserve") is not None else 1)
fpb_map = data.get("fpb_map") or {}

hub = "https://api.hubapi.com"
headers = {"Authorization": "Bearer " + str(token)}

# 1) line items do deal — endpoint DEDICADO de associações (v3)
try:
    li_assoc = frappe.make_get_request(
        hub + "/crm/v3/objects/deals/" + deal_id + "/associations/line_items",
        headers=headers)
except Exception as exc:
    frappe.throw("[HUBSPOT_DEAL_FAIL] Falha ao buscar deal " + deal_id +
                 " no HubSpot: " + str(exc)[:200])

li_results = li_assoc.get("results") or []
li_ids = []
for x in li_results:
    lid = x.get("id") or x.get("toObjectId")
    if lid:
        li_ids.append(str(lid))

# 2) cada line item → sku + qty
items_in = []
unmatched = []
li_debug = []
for liid in li_ids:
    li_url = (hub + "/crm/v3/objects/line_items/" + liid +
              "?properties=hs_sku,quantity,name,price,hs_product_id")
    li = frappe.make_get_request(li_url, headers=headers)
    props = li.get("properties") or {}
    li_debug.append({"id": liid, "hs_sku": props.get("hs_sku"),
        "quantity": props.get("quantity"), "name": props.get("name"),
        "hs_product_id": props.get("hs_product_id")})
    sku = (props.get("hs_sku") or "").strip().upper()
    qty = float(props.get("quantity") or 0)
    rate = float(props.get("price") or 0)
    if not sku or qty <= 0:
        continue
    if not frappe.db.exists("Item", sku):
        unmatched.append({"sku": sku, "name": props.get("name"), "qty": qty})
        continue
    items_in.append({"item_code": sku, "qty": qty, "rate": rate})

if not items_in:
    frappe.response["message"] = {"ok": False, "deal_id": deal_id,
        "error": "Nenhum line item mapeavel.",
        "line_items_count": len(li_ids),
        "line_items": li_debug,
        "unmatched_skus": unmatched}
else:
    # 3) customer
    cust = data.get("customer")
    if not cust:
        comp_assoc = frappe.make_get_request(
            hub + "/crm/v3/objects/deals/" + deal_id + "/associations/companies",
            headers=headers)
        comp_results = comp_assoc.get("results") or []
        if comp_results:
            comp0 = comp_results[0]
            comp_id = str(comp0.get("id") or comp0.get("toObjectId"))
            comp = frappe.make_get_request(
                hub + "/crm/v3/objects/companies/" + comp_id + "?properties=name",
                headers=headers)
            cust_name = ((comp.get("properties") or {}).get("name") or "").strip()
            if cust_name:
                ex = frappe.db.get_value("Customer", {"customer_name": cust_name}, "name")
                if ex:
                    cust = ex
                else:
                    nc = frappe.new_doc("Customer")
                    nc.customer_name = cust_name
                    nc.customer_type = "Company"
                    nc.insert(ignore_permissions=True)
                    cust = nc.name
    if not cust:
        cust_name = "Cliente HubSpot " + deal_id
        ex = frappe.db.get_value("Customer", {"customer_name": cust_name}, "name")
        if ex:
            cust = ex
        else:
            nc = frappe.new_doc("Customer")
            nc.customer_name = cust_name
            nc.customer_type = "Individual"
            nc.insert(ignore_permissions=True)
            cust = nc.name

    # 4) Sales Order (idempotente por deal)
    ddate = frappe.utils.add_days(frappe.utils.today(), 30)
    existing = frappe.db.get_value("Sales Order",
        {"hubspot_deal_id": deal_id, "docstatus": ["!=", 2]}, "name")
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
        so.hubspot_deal_id = deal_id
        for it in items_in:
            so.append("items", {"item_code": it["item_code"], "qty": it["qty"],
                "rate": it["rate"], "warehouse": warehouse, "delivery_date": ddate})
        so.insert(ignore_permissions=True)
        so.submit()
        so_name = so.name

    # 5) reserva (FIFO ou fpb_map)
    def pick_fifo(ic, need):
        rows = frappe.db.sql(
            "select name from `tabFuture Production Batch` where item_code=%s and docstatus=1 "
            "and status in ('Aberta para Reserva','Reservada Parcialmente') "
            "and (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) >= %s "
            "order by planned_production_date asc, creation asc limit 1",
            (ic, need), as_dict=False)
        return rows[0][0] if rows else None

    so_doc = frappe.get_doc("Sales Order", so_name)
    reservations = []
    errors = []
    for row in so_doc.items:
        ic = row.item_code
        already = frappe.db.sql(
            "select coalesce(sum(reserved_qty),0) from `tabProduction Reservation` "
            "where sales_order=%s and sales_order_item=%s and docstatus=1",
            (so_name, row.name), as_dict=False)
        need = float(row.qty or 0) - float((already[0][0] if already else 0) or 0)
        if need <= 0:
            continue
        fpb_name = (fpb_map.get(ic) or "").strip()
        if not fpb_name and auto:
            fpb_name = pick_fifo(ic, need)
        if not fpb_name:
            errors.append({"code": "BATCH_REQUIRED", "item_code": ic,
                "error": "Sem lote para " + str(ic) + " (auto_reserve=0 e sem fpb_map)."})
            continue
        info = frappe.db.sql(
            "select (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) as avail, "
            "item_code, status, docstatus from `tabFuture Production Batch` where name=%s",
            (fpb_name,), as_dict=True)
        if not info:
            errors.append({"code": "BATCH_NOT_FOUND", "item_code": ic, "fpb": fpb_name})
            continue
        info = info[0]
        if int(info.docstatus or 0) != 1 or (info.status or "") not in ("Aberta para Reserva", "Reservada Parcialmente"):
            errors.append({"code": "BATCH_CLOSED", "item_code": ic, "fpb": fpb_name,
                "status": info.status})
            continue
        if info.item_code != ic:
            errors.append({"code": "BATCH_WRONG_ITEM", "item_code": ic, "fpb": fpb_name})
            continue
        if float(info.avail or 0) < need:
            errors.append({"code": "INSUFFICIENT_QTY", "item_code": ic, "fpb": fpb_name,
                "available": float(info.avail or 0), "need": need})
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

    frappe.response["message"] = {"ok": True, "deal_id": deal_id, "sales_order": so_name,
        "customer": cust, "reservations": reservations, "reserve_errors": errors,
        "unmatched_skus": unmatched}
'''.strip()


def install() -> int:
    c = client_from_env()
    if not c.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1
    log_section("Endpoint future_production_reserve_from_hubspot")

    # Custom Field: token HubSpot na config
    try:
        c.create_custom_field({
            "dt": "Injemed Financial Settings",
            "fieldname": "hubspot_access_token",
            "label": "HubSpot Access Token (Private App)",
            "fieldtype": "Password",
            "insert_after": "company",
            "description": "Token do Private App HubSpot (portal dos deals/produtos). "
                           "Usado pelo endpoint reserve_from_hubspot.",
        })
        log_ok("Custom Field hubspot_access_token pronto.")
    except Exception as exc:  # noqa: BLE001
        log_error(f"Custom Field token: {exc}")

    try:
        c.upsert_server_script({
            "name": "future_production_reserve_from_hubspot",
            "script_type": "API",
            "api_method": "future_production_reserve_from_hubspot",
            "allow_guest": 0, "enabled": 1, "script": SCRIPT,
        })
        log_ok("Endpoint future_production_reserve_from_hubspot pronto.")
        return 0
    except Exception as exc:  # noqa: BLE001
        log_error(f"{exc}")
        return 1


def uninstall() -> int:
    c = client_from_env()
    try:
        c.delete_server_script("future_production_reserve_from_hubspot")
    except Exception as exc:  # noqa: BLE001
        log_error(f"{exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
