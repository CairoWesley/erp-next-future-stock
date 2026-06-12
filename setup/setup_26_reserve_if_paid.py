"""
setup_26_reserve_if_paid.py — fluxo COMBINADO gateado por pagamento.

Recebe um deal (manual OU webhook do checkout) e:
  1. Puxa os itens de linha do deal no HubSpot. SEM itens de linha → RECUSA.
  2. Consulta o checkout: soma as transações PAGAS (PAID/AUTHORIZED) do deal.
  3. Compara com o total dos itens de linha (HubSpot).
  4. Pago 100% → cria o pedido + reserva (FIFO split, FRETE non-stock entra mas
     não reserva). Não pago → IGNORA (não cria nada).

Serve as DUAS entradas (mesmo endpoint):
  - Rota manual:  GET/POST .../future_production_reserve_if_paid?id=<DEAL_ID>
  - Webhook:      POST {...} — extrai deal id de id/deal_id/externalRef/ref
                  (inclusive aninhado em data.*).

Params extras: auto_reserve(1), fpb_map{item:lote}, customer, company, warehouse.

Requer: token HubSpot + credenciais do checkout em Injemed Financial Settings
(ver setup_24 e setup_25).

Uso:
    python setup/setup_26_reserve_if_paid.py
    python setup/setup_26_reserve_if_paid.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


SCRIPT = r'''
# /api/method/future_production_reserve_if_paid
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)

# deal id flexível (manual ?id= OU payload de webhook)
deal_id = str(data.get("deal_id") or data.get("id") or data.get("externalRef")
              or data.get("ref") or "").strip()
if not deal_id:
    nested = data.get("data") or {}
    if isinstance(nested, dict):
        deal_id = str(nested.get("externalRef") or nested.get("dealId")
                      or nested.get("deal_id") or nested.get("ref") or "").strip()
if not deal_id:
    frappe.throw("[MISSING_DEAL] Informe id/deal_id/externalRef (deal HubSpot).")

cfg = frappe.get_doc("Injemed Financial Settings", "Injemed Financial Settings")

# Webhook público (allow_guest): chamada não-autenticada exige o secret.
# Chamada autenticada (token/sessão) ignora.
if frappe.session.user == "Guest":
    wsec = cfg.get("webhook_secret")
    given = str(data.get("secret") or "")
    if not given:
        try:
            given = str((frappe.request.args or {}).get("secret") or "")
        except Exception:
            given = ""
    if not given:
        try:
            given = str((frappe.request.headers or {}).get("X-Webhook-Secret") or "")
        except Exception:
            given = ""
    if not wsec or given != str(wsec):
        frappe.throw("[BAD_SECRET] Webhook secret invalido ou ausente.")

def getpw(fn):
    try:
        return cfg.get_password(fn)
    except Exception:
        return None

hub_token = getpw("hubspot_access_token")
if not hub_token:
    frappe.throw("[NO_HUBSPOT_TOKEN] Configure o token HubSpot na config.")
co_url = (cfg.get("checkout_api_url") or "https://checkout.service.unikkapharma.com.br").rstrip("/")
co_user = cfg.get("checkout_user")
co_pass = getpw("checkout_password")
if not co_user or not co_pass:
    frappe.throw("[NO_CHECKOUT_CREDS] Configure checkout_user e checkout_password.")
approved = []
for s in (cfg.get("payment_approved_statuses") or "PAID,AUTHORIZED").split(","):
    s2 = s.strip().upper()
    if s2:
        approved.append(s2)
tol = int(cfg.get("payment_tolerance_cents") or 0)
company = data.get("company") or cfg.get("company") or "Unikka Pharma"
warehouse = data.get("warehouse") or "Produtos Acabados - UP"
auto = int(data.get("auto_reserve") if data.get("auto_reserve") is not None else 1)
fpb_map = data.get("fpb_map") or {}

hub = "https://api.hubapi.com"
hh = {"Authorization": "Bearer " + str(hub_token)}

# 1) itens de linha do deal — SEM itens → RECUSA
li_assoc = frappe.make_get_request(
    hub + "/crm/v3/objects/deals/" + deal_id + "/associations/line_items", headers=hh)
li_ids = []
for x in (li_assoc.get("results") or []):
    lid = x.get("id") or x.get("toObjectId")
    if lid:
        li_ids.append(str(lid))
if not li_ids:
    frappe.throw("[NO_LINE_ITEMS] Deal " + deal_id + " sem itens de linha — pedido recusado.")

items_in = []
unmatched = []
due = 0.0
for liid in li_ids:
    li = frappe.make_get_request(
        hub + "/crm/v3/objects/line_items/" + liid +
        "?properties=hs_sku,quantity,price,amount,name", headers=hh)
    p = li.get("properties") or {}
    amt_raw = p.get("amount")
    if amt_raw is None or amt_raw == "":
        amt = float(p.get("price") or 0) * float(p.get("quantity") or 0)
    else:
        amt = float(amt_raw)
    due = due + amt
    sku = (p.get("hs_sku") or "").strip().upper()
    qty = float(p.get("quantity") or 0)
    rate = float(p.get("price") or 0)
    if not sku or qty <= 0:
        continue
    if not frappe.db.exists("Item", sku):
        unmatched.append({"sku": sku, "name": p.get("name"), "qty": qty})
        continue
    items_in.append({"item_code": sku, "qty": qty, "rate": rate})
due_cents = int(round(due * 100))

# 2) checkout: login → recheck-by-deal → soma transações aprovadas
login = frappe.make_post_request(co_url + "/api/auth/login",
    json={"user": co_user, "password": co_pass})
token = (login or {}).get("token")
if not token:
    frappe.throw("[CHECKOUT_LOGIN_FAIL] Login no checkout falhou (user/senha?).")
cookie = {"Cookie": "cs_session=" + str(token)}
rec = frappe.make_post_request(
    co_url + "/api/transactions/recheck-by-deal/" + deal_id, headers=cookie, json={})
checkouts = ((rec or {}).get("data") or {}).get("checkouts") or []
paid_cents = 0
tx_sum = []
for ck in checkouts:
    ckid = ck.get("id")
    if not ckid:
        continue
    txs = frappe.make_get_request(
        co_url + "/api/checkouts/" + str(ckid) + "/transactions", headers=cookie)
    txlist = txs.get("data") if isinstance(txs, dict) else txs
    for t in (txlist or []):
        st = (t.get("status") or "").upper()
        amt = int(t.get("amountCents") or 0)
        tx_sum.append({"id": t.get("id"), "status": st, "amountCents": amt,
                       "method": t.get("paymentMethod")})
        if st in approved:
            paid_cents = paid_cents + amt

paid_100 = due_cents > 0 and (paid_cents + tol) >= due_cents
pct = round(paid_cents * 100.0 / due_cents, 2) if due_cents > 0 else None
payment = {"total_due": round(due_cents / 100.0, 2), "total_paid": round(paid_cents / 100.0, 2),
           "total_due_cents": due_cents, "total_paid_cents": paid_cents,
           "paid_pct": pct, "paid_100": paid_100, "transactions": tx_sum}

# 3) gate
if not paid_100:
    # NÃO pago 100% → ignora (não cria/reserva nada)
    frappe.response["message"] = {"ok": True, "deal_id": deal_id, "reserved": False,
        "ignored": True, "reason": "nao pago 100%", "payment": payment,
        "unmatched_skus": unmatched}
elif not items_in:
    frappe.response["message"] = {"ok": False, "deal_id": deal_id, "reserved": False,
        "error": "Pago, mas nenhum line item mapeavel (SKU sem Item).",
        "payment": payment, "unmatched_skus": unmatched}
else:
    # 4) PAGO 100% → cria pedido + reserva
    cust = data.get("customer")
    if not cust:
        comp_assoc = frappe.make_get_request(
            hub + "/crm/v3/objects/deals/" + deal_id + "/associations/companies", headers=hh)
        comp_results = comp_assoc.get("results") or []
        if comp_results:
            comp0 = comp_results[0]
            comp_id = str(comp0.get("id") or comp0.get("toObjectId"))
            comp = frappe.make_get_request(
                hub + "/crm/v3/objects/companies/" + comp_id + "?properties=name", headers=hh)
            cn = ((comp.get("properties") or {}).get("name") or "").strip()
            if cn:
                ex = frappe.db.get_value("Customer", {"customer_name": cn}, "name")
                if ex:
                    cust = ex
                else:
                    nc = frappe.new_doc("Customer")
                    nc.customer_name = cn
                    nc.customer_type = "Company"
                    nc.insert(ignore_permissions=True)
                    cust = nc.name
    if not cust:
        cn = "Cliente HubSpot " + deal_id
        ex = frappe.db.get_value("Customer", {"customer_name": cn}, "name")
        if ex:
            cust = ex
        else:
            nc = frappe.new_doc("Customer")
            nc.customer_name = cn
            nc.customer_type = "Individual"
            nc.insert(ignore_permissions=True)
            cust = nc.name

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

    so_doc = frappe.get_doc("Sales Order", so_name)

    def fifo_lotes(item_code):
        return frappe.db.sql(
            "select name, (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) as avail "
            "from `tabFuture Production Batch` where item_code=%s and docstatus=1 "
            "and status in ('Aberta para Reserva','Reservada Parcialmente') "
            "and (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) > 0 "
            "order by planned_production_date asc, creation asc", (item_code,), as_dict=True)

    def make_pr(soi_name, item_code, lote_name, qty_pr):
        pr = frappe.new_doc("Production Reservation")
        pr.sales_order = so_name
        pr.sales_order_item = soi_name
        pr.future_production_batch = lote_name
        pr.item_code = item_code
        pr.customer = so_doc.customer
        pr.reserved_qty = qty_pr
        pr.insert(ignore_permissions=True)
        pr.submit()
        return pr.name

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
        need = float(row.qty or 0) - float((already[0][0] if already else 0) or 0)
        if need <= 0:
            continue
        explicit = (fpb_map.get(ic) or "").strip()
        if explicit:
            info = frappe.db.sql(
                "select (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) as avail, "
                "item_code, status, docstatus from `tabFuture Production Batch` where name=%s",
                (explicit,), as_dict=True)
            if info and int(info[0].docstatus or 0) == 1 and info[0].item_code == ic and (info[0].status or "") in ("Aberta para Reserva", "Reservada Parcialmente"):
                take = min(need, float(info[0].avail or 0))
                if take > 0:
                    prn = make_pr(row.name, ic, explicit, take)
                    reservations.append({"reservation": prn, "future_production_batch": explicit,
                        "item_code": ic, "reserved_qty": take})
                    if take < need:
                        errors.append({"code": "INSUFFICIENT_QTY", "item_code": ic, "fpb": explicit,
                            "need": need, "reserved": take})
                else:
                    errors.append({"code": "INSUFFICIENT_QTY", "item_code": ic, "fpb": explicit, "need": need})
            else:
                errors.append({"code": "BATCH_INVALID", "item_code": ic, "fpb": explicit})
        elif auto:
            remaining = need
            for lt in fifo_lotes(ic):
                if remaining <= 0:
                    break
                take = min(remaining, float(lt.avail or 0))
                if take <= 0:
                    continue
                prn = make_pr(row.name, ic, lt.name, take)
                reservations.append({"reservation": prn, "future_production_batch": lt.name,
                    "item_code": ic, "reserved_qty": take})
                remaining = remaining - take
            if remaining > 0:
                errors.append({"code": "INSUFFICIENT_TOTAL", "item_code": ic,
                    "need": need, "short": remaining})
        else:
            errors.append({"code": "BATCH_REQUIRED", "item_code": ic})

    frappe.response["message"] = {"ok": True, "deal_id": deal_id, "reserved": True,
        "paid_100": True, "payment": payment, "sales_order": so_name, "customer": cust,
        "reservations": reservations, "reserve_errors": errors, "unmatched_skus": unmatched}
'''.strip()


def install() -> int:
    import secrets
    c = client_from_env()
    if not c.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1
    log_section("Endpoint future_production_reserve_if_paid (webhook + manual)")

    # Campo webhook_secret na config + gera valor se vazio (idempotente)
    try:
        c.create_custom_field({
            "dt": "Injemed Financial Settings", "fieldname": "webhook_secret",
            "label": "Webhook Secret (reserve_if_paid)", "fieldtype": "Data",
            "insert_after": "payment_tolerance_cents",
            "description": "Secret pro webhook público. Mande como ?secret=... ou header X-Webhook-Secret.",
        })
        _, cur = c._request("GET",
            "/api/resource/Injemed%20Financial%20Settings/Injemed%20Financial%20Settings")
        val = ((cur or {}).get("data") or {}).get("webhook_secret")
        if not val:
            new_secret = secrets.token_hex(24)
            c._request("PUT",
                "/api/resource/Injemed%20Financial%20Settings/Injemed%20Financial%20Settings",
                json_body={"webhook_secret": new_secret})
            log_ok(f"webhook_secret gerado: {new_secret}")
        else:
            log_ok(f"webhook_secret já existe: {val}")
    except Exception as exc:  # noqa: BLE001
        log_error(f"webhook_secret: {exc}")

    try:
        c.upsert_server_script({
            "name": "future_production_reserve_if_paid", "script_type": "API",
            "api_method": "future_production_reserve_if_paid",
            "allow_guest": 1, "enabled": 1, "script": SCRIPT,
        })
        log_ok("Endpoint future_production_reserve_if_paid pronto (allow_guest=1, secret-gated).")
        return 0
    except Exception as exc:  # noqa: BLE001
        log_error(f"{exc}")
        return 1


def uninstall() -> int:
    c = client_from_env()
    try:
        c.delete_server_script("future_production_reserve_if_paid")
    except Exception as exc:  # noqa: BLE001
        log_error(f"{exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
