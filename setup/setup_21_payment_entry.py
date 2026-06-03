"""
setup_21_payment_entry.py — endpoint pra LANÇAR o financeiro (recebimento).

Último passo da automação: depois de cadastro + reserva + pacientes, lança o
RECEBIMENTO no ERPNext. Daí pra frente (produção→dispensação) é manual.

Modelo (confirmado com negócio):
  - SÓ Payment Entry (sem Sales Invoice).
  - valor do pagamento fica HOJE (posting_date = data do pagamento)
  - recebimento FUTURO (clearance_date = data de liquidação)
      PIX/Boleto: 1 PE, clearance = D + pix/boleto_settlement_days
      Cartão Nx:  N PEs (1 por parcela), parcela i clearance = D + dias*i
  - banco + modo + conta a receber vêm da Config Financeira (setup_20).

clearance_date é o campo NATIVO do ERPNext de Bank Reconciliation: o
lançamento entra hoje, mas só "compensa" no banco na data futura.

Endpoint:
  future_production_register_payment
    body: { sales_order,
            payment: { method, installments, amount, paid_at, transaction_id } }
    → cria N Payment Entry (Receive), retorna nomes + cronograma.

Idempotente: se já existe PE com o mesmo reference_no (transaction_id +
parcela), pula.

Uso:
    python setup/setup_21_payment_entry.py
    python setup/setup_21_payment_entry.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


SCRIPT_REGISTER_PAYMENT = r'''
# /api/method/future_production_register_payment
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)

so_name = data.get("sales_order")
if not so_name:
    frappe.throw("sales_order obrigatorio.")
pay = data.get("payment") or {}
method = (pay.get("method") or "PIX").upper()
inst = int(pay.get("installments") or 1)
if inst < 1:
    inst = 1
amount = float(pay.get("amount") or 0)
txid = pay.get("transaction_id") or ""

if amount <= 0:
    frappe.response["message"] = {"ok": False, "message": "amount <= 0, nada a lancar."}
else:
    # Normaliza paid_at
    paid_raw = str(pay.get("paid_at") or frappe.utils.now())
    paid_clean = paid_raw.replace("T", " ").replace("Z", "").strip()
    if "." in paid_clean:
        paid_clean = paid_clean.split(".")[0]
    if "+" in paid_clean:
        paid_clean = paid_clean.split("+")[0].strip()
    paid_date = frappe.utils.getdate(paid_clean)

    so = frappe.get_doc("Sales Order", so_name)
    customer = so.customer
    company = so.company

    cfg = frappe.get_doc("Injemed Financial Settings", "Injemed Financial Settings")
    receivable = cfg.receivable_account
    if method in ("CREDIT_CARD", "CARTAO", "CARTÃO"):
        days = int(cfg.card_days_per_installment or 30)
        bank = cfg.bank_account_card
        mode = cfg.mode_card
    elif method == "BOLETO":
        days = int(cfg.boleto_settlement_days or 1)
        bank = cfg.bank_account_boleto
        mode = cfg.mode_boleto
        inst = 1
    else:
        days = int(cfg.pix_settlement_days or 1)
        bank = cfg.bank_account_pix
        mode = cfg.mode_pix
        inst = 1

    if not bank or not receivable:
        frappe.throw("Config Financeira sem banco/conta a receber. Configure Injemed Financial Settings.")

    # parcelas
    per = round(amount / inst, 2)
    created = []
    skipped = []
    acc = 0.0
    for i in range(1, inst + 1):
        val = round(amount - acc, 2) if i == inst else per
        acc = acc + val
        ref_no = txid + ("-p" + str(i) if inst > 1 else "")
        clearance = frappe.utils.add_days(paid_date, days * i)

        # idempotency por reference_no
        existing = frappe.db.get_value("Payment Entry",
            {"reference_no": ref_no, "docstatus": ["!=", 2]}, "name")
        if existing:
            skipped.append({"parcela": i, "payment_entry": existing})
            continue

        pe = frappe.new_doc("Payment Entry")
        pe.payment_type = "Receive"
        pe.company = company
        pe.posting_date = paid_date          # valor do pagamento = HOJE
        pe.party_type = "Customer"
        pe.party = customer
        pe.paid_from = receivable            # Clientes (a receber)
        pe.paid_to = bank                    # banco da config
        pe.paid_amount = val
        pe.received_amount = val
        pe.source_exchange_rate = 1
        pe.target_exchange_rate = 1
        if mode:
            pe.mode_of_payment = mode
        pe.reference_no = ref_no
        pe.reference_date = paid_date
        pe.clearance_date = clearance        # recebimento = FUTURO (liquidacao)
        pe.remarks = ("Pedido " + so_name + " | " + method +
                      (" parcela " + str(i) + "/" + str(inst) if inst > 1 else "") +
                      " | autorizado " + str(paid_date) +
                      " | recebimento previsto " + str(clearance))
        pe.insert(ignore_permissions=True)
        pe.submit()
        created.append({
            "parcela": i, "payment_entry": pe.name, "valor": val,
            "posting_date": str(paid_date), "clearance_date": str(clearance),
        })

    frappe.response["message"] = {
        "ok": True,
        "sales_order": so_name,
        "method": method,
        "installments": inst,
        "bank_account": bank,
        "mode_of_payment": mode,
        "created": created,
        "skipped": skipped,
    }
'''.strip()


def install() -> int:
    c = client_from_env()
    log_section("Endpoint future_production_register_payment")
    try:
        c.upsert_server_script({
            "name": "future_production_register_payment",
            "script_type": "API",
            "api_method": "future_production_register_payment",
            "allow_guest": 0, "enabled": 1,
            "script": SCRIPT_REGISTER_PAYMENT,
        })
        log_ok("Endpoint future_production_register_payment pronto.")
        return 0
    except Exception as exc:  # noqa: BLE001
        log_error(f"{exc}")
        return 1


def uninstall() -> int:
    c = client_from_env()
    try:
        c.delete_server_script("future_production_register_payment")
    except Exception as exc:  # noqa: BLE001
        log_error(f"{exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
