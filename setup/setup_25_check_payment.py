"""
setup_25_check_payment.py — verifica no checkout (API) se o deal foi PAGO 100%,
comparando com o valor total dos itens de linha (HubSpot).

Endpoint:
  future_production_check_payment
    body/query: { id | deal_id }
    → total_due  = soma dos line items do deal no HubSpot (valor total dos itens de linha)
      total_paid = soma das transações APROVADAS (PAID/AUTHORIZED) no checkout
      paid_100   = total_paid (+ tolerância) >= total_due
    → { deal_id, total_due, total_paid, paid_pct, paid_100, line_items, transactions }

Fluxo (server-to-server, sem cookie jar):
  1. HubSpot: line items do deal → soma amount → total_due.
  2. Checkout: POST /api/auth/login {user,password} → token (HMAC).
  3. POST /api/transactions/recheck-by-deal/{deal} com Cookie cs_session=<token>
     → reconsulta no provedor + lista os checkouts do deal.
  4. GET /api/checkouts/{id}/transactions por checkout → soma amountCents
     das transações com status aprovado.

Config (Injemed Financial Settings):
  checkout_api_url, checkout_user, checkout_password (Password),
  payment_approved_statuses (default "PAID,AUTHORIZED"), payment_tolerance_cents.

Uso:
    python setup/setup_25_check_payment.py
    python setup/setup_25_check_payment.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


SCRIPT = r'''
# /api/method/future_production_check_payment
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)

deal_id = str(data.get("deal_id") or data.get("id") or "").strip()
if not deal_id:
    frappe.throw("[MISSING_DEAL] Informe id (deal HubSpot). Ex: ?id=123456")

cfg = frappe.get_doc("Injemed Financial Settings", "Injemed Financial Settings")

def getpw(fn):
    try:
        return cfg.get_password(fn)
    except Exception:
        return None

hub_token = getpw("hubspot_access_token")
if not hub_token:
    frappe.throw("[NO_HUBSPOT_TOKEN] Configure o token HubSpot na config.")
co_url = (cfg.get("checkout_api_url") or "https://checkout.service.unikkapharma.com.br")
co_url = co_url.rstrip("/")
co_user = cfg.get("checkout_user")
co_pass = getpw("checkout_password")
if not co_user or not co_pass:
    frappe.throw("[NO_CHECKOUT_CREDS] Configure checkout_user e checkout_password na config.")

approved = []
for s in (cfg.get("payment_approved_statuses") or "PAID,AUTHORIZED").split(","):
    s2 = s.strip().upper()
    if s2:
        approved.append(s2)
tol = int(cfg.get("payment_tolerance_cents") or 0)

hub = "https://api.hubapi.com"
hh = {"Authorization": "Bearer " + str(hub_token)}

# 1) total devido = soma dos line items (amount) do deal
li_assoc = frappe.make_get_request(
    hub + "/crm/v3/objects/deals/" + deal_id + "/associations/line_items", headers=hh)
li_ids = []
for x in (li_assoc.get("results") or []):
    lid = x.get("id") or x.get("toObjectId")
    if lid:
        li_ids.append(str(lid))

due = 0.0
li_dbg = []
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
    li_dbg.append({"sku": p.get("hs_sku"), "name": p.get("name"), "amount": amt})
due_cents = int(round(due * 100))

# 2) login no checkout
login = frappe.make_post_request(co_url + "/api/auth/login",
    json={"user": co_user, "password": co_pass})
token = (login or {}).get("token")
if not token:
    frappe.throw("[CHECKOUT_LOGIN_FAIL] Login no checkout falhou (user/senha?).")
cookie = {"Cookie": "cs_session=" + str(token)}

# 3) recheck-by-deal → reconsulta no provedor + lista checkouts do deal
rec = frappe.make_post_request(
    co_url + "/api/transactions/recheck-by-deal/" + deal_id, headers=cookie, json={})
rdata = (rec or {}).get("data") or {}
checkouts = rdata.get("checkouts") or []

# 4) por checkout → transações → soma aprovadas
pix_disc = float(cfg.get("pix_discount_pct") or 0) / 100.0
pix_factor = 1.0
if pix_disc > 0.0 and pix_disc < 1.0:
    pix_factor = 1.0 / (1.0 - pix_disc)
paid_cents = 0
eff_cents = 0
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
        mth = (t.get("paymentMethod") or "").upper()
        tx_sum.append({"id": t.get("id"), "status": st, "amountCents": amt,
                       "method": mth, "paidAt": t.get("paidAt")})
        if st in approved:
            paid_cents = paid_cents + amt
            if mth == "PIX":
                eff_cents = eff_cents + int(round(amt * pix_factor))
            else:
                eff_cents = eff_cents + amt

paid_100 = due_cents > 0 and (eff_cents + tol) >= due_cents
pct = round(eff_cents * 100.0 / due_cents, 2) if due_cents > 0 else None

frappe.response["message"] = {
    "deal_id": deal_id,
    "total_due_cents": due_cents, "total_due": round(due_cents / 100.0, 2),
    "total_paid_cents": paid_cents, "total_paid": round(paid_cents / 100.0, 2),
    "total_paid_effective": round(eff_cents / 100.0, 2), "pix_discount_pct": round(pix_disc * 100.0, 2),
    "paid_pct": pct, "paid_100": paid_100,
    "approved_statuses": approved, "checkouts_found": len(checkouts),
    "line_items": li_dbg, "transactions": tx_sum,
}
'''.strip()


CONFIG_FIELDS = [
    {"fieldname": "checkout_sec", "label": "Checkout (verificação de pagamento)",
     "fieldtype": "Section Break", "insert_after": "hubspot_access_token"},
    {"fieldname": "checkout_api_url", "label": "Checkout API URL", "fieldtype": "Data",
     "insert_after": "checkout_sec",
     "description": "Base da API de checkout (ex: https://checkout.service.unikkapharma.com.br)."},
    {"fieldname": "checkout_user", "label": "Checkout - Usuário", "fieldtype": "Data",
     "insert_after": "checkout_api_url"},
    {"fieldname": "checkout_password", "label": "Checkout - Senha", "fieldtype": "Password",
     "insert_after": "checkout_user"},
    {"fieldname": "payment_approved_statuses", "label": "Status aprovados (CSV)",
     "fieldtype": "Data", "insert_after": "checkout_password",
     "description": "Status que contam como pago. Padrão: PAID,AUTHORIZED."},
    {"fieldname": "payment_tolerance_cents", "label": "Tolerância (centavos)",
     "fieldtype": "Int", "insert_after": "payment_approved_statuses",
     "description": "Folga em centavos pra considerar 100% pago (arredondamento)."},
]


def install() -> int:
    c = client_from_env()
    if not c.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1
    log_section("Endpoint future_production_check_payment + config checkout")

    for cf in CONFIG_FIELDS:
        try:
            c.create_custom_field({"dt": "Injemed Financial Settings", **cf})
        except Exception as exc:  # noqa: BLE001
            log_error(f"Custom Field {cf['fieldname']}: {exc}")

    # defaults
    try:
        c._request("PUT",
            "/api/resource/Injemed%20Financial%20Settings/Injemed%20Financial%20Settings",
            json_body={"checkout_api_url": "https://checkout.service.unikkapharma.com.br",
                       "payment_approved_statuses": "PAID,AUTHORIZED"})
    except Exception as exc:  # noqa: BLE001
        log_error(f"defaults: {exc}")

    try:
        c.upsert_server_script({
            "name": "future_production_check_payment", "script_type": "API",
            "api_method": "future_production_check_payment",
            "allow_guest": 0, "enabled": 1, "script": SCRIPT,
        })
        log_ok("Endpoint future_production_check_payment pronto.")
        return 0
    except Exception as exc:  # noqa: BLE001
        log_error(f"{exc}")
        return 1


def uninstall() -> int:
    c = client_from_env()
    try:
        c.delete_server_script("future_production_check_payment")
    except Exception as exc:  # noqa: BLE001
        log_error(f"{exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
