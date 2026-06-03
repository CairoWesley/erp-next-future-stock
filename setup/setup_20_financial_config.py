"""
setup_20_financial_config.py — Configuração Financeira (Single DocType) +
endpoints de liquidação.

Cria UM lugar pra configurar:
  - parâmetros de tempo de liquidação (PIX D+1, cartão D+30/parcela, boleto)
  - conta bancária (banco certo) que recebe cada método
  - conta de clientes (a receber)
  - Mode of Payment do ERPNext por método

DocType Single "Injemed Financial Settings" — form único no ERPNext
(Manufacturing workspace ou busca). Operador financeiro ajusta os números
e os bancos sem mexer em código.

Endpoints:
  future_production_get_financial_config   — lê a config
  future_production_payment_schedule       — calcula liquidação usando a config
                                             (substitui o cálculo hardcoded do n8n)

Uso:
    python setup/setup_20_financial_config.py
    python setup/setup_20_financial_config.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


DOCTYPE = "Injemed Financial Settings"
MODULE = os.environ.get("ERPNEXT_MODULE", "Manufacturing")
COMPANY = os.environ.get("ERPNEXT_COMPANY", "Injemedpharma")


def _perm(role):
    return {"role": role, "read": 1, "write": 1, "create": 1, "submit": 0,
            "cancel": 0, "delete": 0, "print": 1, "email": 1, "share": 1, "report": 1}


DOCTYPE_PAYLOAD = {
    "doctype": "DocType",
    "name": DOCTYPE,
    "module": MODULE,
    "custom": 1,
    "issingle": 1,
    "track_changes": 1,
    "sort_field": "modified",
    "sort_order": "DESC",
    "fields": [
        {"fieldname": "company", "label": "Empresa", "fieldtype": "Link",
         "options": "Company", "default": COMPANY, "reqd": 1},

        {"fieldname": "sec_tempo", "label": "Parâmetros de Tempo (Liquidação)",
         "fieldtype": "Section Break"},
        {"fieldname": "pix_settlement_days", "label": "Dias Liquidação PIX (D+)",
         "fieldtype": "Int", "default": "1",
         "description": "PIX: pago hoje cai em D+N. Padrão D+1."},
        {"fieldname": "boleto_settlement_days", "label": "Dias Liquidação Boleto (D+)",
         "fieldtype": "Int", "default": "1"},
        {"fieldname": "cb_tempo", "fieldtype": "Column Break"},
        {"fieldname": "card_days_per_installment", "label": "Dias por Parcela Cartão (D+)",
         "fieldtype": "Int", "default": "30",
         "description": "Cartão: parcela i liquida em D+(N*i). Padrão 30 → D+30, D+60..."},

        {"fieldname": "sec_contas", "label": "Contas de Recebimento (Banco Certo)",
         "fieldtype": "Section Break"},
        {"fieldname": "bank_account_pix", "label": "Banco — PIX", "fieldtype": "Link",
         "options": "Account"},
        {"fieldname": "bank_account_card", "label": "Banco — Cartão", "fieldtype": "Link",
         "options": "Account"},
        {"fieldname": "cb_contas", "fieldtype": "Column Break"},
        {"fieldname": "bank_account_boleto", "label": "Banco — Boleto", "fieldtype": "Link",
         "options": "Account"},
        {"fieldname": "receivable_account", "label": "Conta Clientes (a Receber)",
         "fieldtype": "Link", "options": "Account"},

        {"fieldname": "sec_modos", "label": "Modos de Pagamento (ERPNext)",
         "fieldtype": "Section Break"},
        {"fieldname": "mode_pix", "label": "Modo Pagamento — PIX", "fieldtype": "Link",
         "options": "Mode of Payment"},
        {"fieldname": "mode_card", "label": "Modo Pagamento — Cartão", "fieldtype": "Link",
         "options": "Mode of Payment"},
        {"fieldname": "cb_modos", "fieldtype": "Column Break"},
        {"fieldname": "mode_boleto", "label": "Modo Pagamento — Boleto", "fieldtype": "Link",
         "options": "Mode of Payment"},
    ],
    "permissions": [_perm("System Manager"), _perm("Accounts Manager"),
                    _perm("Accounts User")],
}


# Defaults aplicados ao singleton após criar o DocType.
DEFAULTS = {
    "company": COMPANY,
    "pix_settlement_days": 1,
    "boleto_settlement_days": 1,
    "card_days_per_installment": 30,
    "bank_account_pix": "Conta Bancária - I",
    "bank_account_card": "Conta Bancária - I",
    "bank_account_boleto": "Conta Bancária - I",
    "receivable_account": "Clientes - I",
    "mode_pix": "Pix",
    "mode_card": "Cartão de Crédito",
    "mode_boleto": "Boleto",
}


SCRIPT_GET_CONFIG = r'''
# /api/method/future_production_get_financial_config
cfg = frappe.get_doc("Injemed Financial Settings", "Injemed Financial Settings")
frappe.response["message"] = {
    "company": cfg.company,
    "pix_settlement_days": int(cfg.pix_settlement_days or 1),
    "card_days_per_installment": int(cfg.card_days_per_installment or 30),
    "boleto_settlement_days": int(cfg.boleto_settlement_days or 1),
    "bank_account_pix": cfg.bank_account_pix,
    "bank_account_card": cfg.bank_account_card,
    "bank_account_boleto": cfg.bank_account_boleto,
    "receivable_account": cfg.receivable_account,
    "mode_pix": cfg.mode_pix,
    "mode_card": cfg.mode_card,
    "mode_boleto": cfg.mode_boleto,
}
'''.strip()


SCRIPT_PAYMENT_SCHEDULE = r'''
# /api/method/future_production_payment_schedule
# body: { method: "PIX"|"CREDIT_CARD"|"BOLETO", installments: N,
#         amount: 1963.98, paid_at: "2026-06-02 18:46:15" }
# Usa a config (dias + banco + modo) pra montar o cronograma de liquidacao.
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)

method = (data.get("method") or "PIX").upper()
inst = int(data.get("installments") or 1)
if inst < 1:
    inst = 1
amount = float(data.get("amount") or 0)

paid_raw = str(data.get("paid_at") or frappe.utils.now())
paid_clean = paid_raw.replace("T", " ").replace("Z", "").strip()
if "." in paid_clean:
    paid_clean = paid_clean.split(".")[0]
if "+" in paid_clean:
    paid_clean = paid_clean.split("+")[0].strip()
paid_date = frappe.utils.getdate(paid_clean)

cfg = frappe.get_doc("Injemed Financial Settings", "Injemed Financial Settings")

schedule = []
if method in ("CREDIT_CARD", "CARTAO", "CARTÃO"):
    days = int(cfg.card_days_per_installment or 30)
    bank = cfg.bank_account_card
    mode = cfg.mode_card
    per = round(amount / inst, 2)
    acc = 0.0
    for i in range(1, inst + 1):
        val = round(amount - acc, 2) if i == inst else per
        acc = acc + val
        schedule.append({
            "parcela": i,
            "valor": val,
            "liquida_em": str(frappe.utils.add_days(paid_date, days * i)),
        })
elif method == "BOLETO":
    days = int(cfg.boleto_settlement_days or 1)
    bank = cfg.bank_account_boleto
    mode = cfg.mode_boleto
    schedule.append({"parcela": 1, "valor": amount,
                     "liquida_em": str(frappe.utils.add_days(paid_date, days))})
else:  # PIX
    days = int(cfg.pix_settlement_days or 1)
    bank = cfg.bank_account_pix
    mode = cfg.mode_pix
    schedule.append({"parcela": 1, "valor": amount,
                     "liquida_em": str(frappe.utils.add_days(paid_date, days))})

frappe.response["message"] = {
    "method": method,
    "installments": inst,
    "amount": amount,
    "bank_account": bank,
    "mode_of_payment": mode,
    "receivable_account": cfg.receivable_account,
    "company": cfg.company,
    "schedule": schedule,
}
'''.strip()


def install() -> int:
    c = client_from_env()
    log_section(f"DocType Single: {DOCTYPE}")
    try:
        c.create_doctype(DOCTYPE_PAYLOAD)
    except Exception as exc:  # noqa: BLE001
        log_error(f"DocType: {exc}")
        return 1

    # Aplica defaults no singleton (só campos cuja conta/modo existir)
    log_section("Defaults da config")
    safe = dict(DEFAULTS)
    # valida links — remove os que não existem pra não quebrar
    for fld, dt in (("bank_account_pix", "Account"), ("bank_account_card", "Account"),
                    ("bank_account_boleto", "Account"), ("receivable_account", "Account"),
                    ("mode_pix", "Mode of Payment"), ("mode_card", "Mode of Payment"),
                    ("mode_boleto", "Mode of Payment")):
        val = safe.get(fld)
        if val:
            _, ex = c._request("GET", f"/api/resource/{dt.replace(' ', '%20')}/{val.replace(' ', '%20')}")
            if ex is None:
                log_error(f"{fld}: '{val}' não existe — deixando vazio")
                safe.pop(fld, None)
    try:
        c._request("PUT", f"/api/resource/{DOCTYPE.replace(' ', '%20')}/{DOCTYPE.replace(' ', '%20')}",
                   json_body=safe)
        log_ok("Defaults aplicados.")
    except Exception as exc:  # noqa: BLE001
        log_error(f"Defaults: {exc}")

    log_section("Endpoints financeiros")
    for name, script in (("future_production_get_financial_config", SCRIPT_GET_CONFIG),
                         ("future_production_payment_schedule", SCRIPT_PAYMENT_SCHEDULE)):
        try:
            c.upsert_server_script({"name": name, "script_type": "API", "api_method": name,
                                    "allow_guest": 0, "enabled": 1, "script": script})
            log_ok(f"Endpoint {name} pronto.")
        except Exception as exc:  # noqa: BLE001
            log_error(f"{name}: {exc}")
    return 0


def uninstall() -> int:
    c = client_from_env()
    for name in ("future_production_get_financial_config", "future_production_payment_schedule"):
        try:
            c.delete_server_script(name)
        except Exception as exc:  # noqa: BLE001
            log_error(f"{name}: {exc}")
    try:
        c.delete_doctype(DOCTYPE)
    except Exception as exc:  # noqa: BLE001
        log_error(f"DocType: {exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
