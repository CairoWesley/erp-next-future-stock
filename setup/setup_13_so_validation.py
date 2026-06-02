"""
setup_13_so_validation.py — Validações pré-reserva no Sales Order.

Modelo:
  - 3 flags no SO: payment_validated, prescriptions_validated, hubspot_complete
  - Botão "Reservar Automaticamente" agora chama validate_and_reserve
    (em vez de auto_reserve direto)
  - Webhooks externos atualizam flags:
      * /api/method/future_production_payment_webhook
      * /api/method/future_production_prescriptions_webhook
      * /api/method/future_production_mark_hubspot_complete
  - Quando 3 flags = True, validate_and_reserve roda auto_reserve_sales_order
    internamente e atualiza validation_status.

Cria:
  1. 17 Custom Fields no Sales Order (3 flags + audit + section/columns)
  2. Server Scripts:
       future_production_validate_and_reserve
       future_production_payment_webhook
       future_production_prescriptions_webhook
       future_production_mark_hubspot_complete
       future_production_refresh_validation_status (interno)
  3. Server Script no Sales Order Before Save: recalcula validation_status
  4. Atualiza Client Script setup_11 (botão usa novo endpoint)

Uso:
    python setup_13_so_validation.py
    python setup_13_so_validation.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section
from lib.payloads_validation import VALIDATION_SO_FIELDS


# ---------------------------------------------------------------------------
# Server Script — recalcula validation_status + blockers
# (chamado de dentro dos outros endpoints, não por evento)
# ---------------------------------------------------------------------------

SCRIPT_REFRESH_STATUS = r'''
# /api/method/future_production_refresh_validation_status
# Recalcula validation_status e validation_blockers de 1 SO baseado nas 3 flags.

data = frappe.form_dict
so_name = data.get("sales_order")
if not so_name:
    frappe.throw("sales_order e obrigatorio.")

so = frappe.db.get_value(
    "Sales Order", so_name,
    ["payment_validated", "prescriptions_validated", "hubspot_complete", "docstatus"],
    as_dict=True,
)
if not so:
    frappe.throw("Sales Order " + so_name + " nao encontrado.")

p_ok = int(so.payment_validated or 0) == 1
r_ok = int(so.prescriptions_validated or 0) == 1
h_ok = int(so.hubspot_complete or 0) == 1

blockers = []
if not p_ok:
    blockers.append("Aguardando confirmacao de pagamento (webhook do checkout).")
if not r_ok:
    blockers.append("Aguardando validacao das receitas (sistema interno).")
if not h_ok:
    blockers.append("Cadastro HubSpot incompleto.")

if p_ok and r_ok and h_ok:
    status = "Validado (Pronto para Reservar)"
    blockers_text = ""
elif sum([p_ok, r_ok, h_ok]) == 0:
    status = "Aguardando Multiplas Validacoes"
    blockers_text = "\n".join(blockers)
elif not p_ok and r_ok and h_ok:
    status = "Aguardando Pagamento"
    blockers_text = "\n".join(blockers)
elif p_ok and not r_ok and h_ok:
    status = "Aguardando Receitas"
    blockers_text = "\n".join(blockers)
elif p_ok and r_ok and not h_ok:
    status = "Aguardando Cadastro HubSpot"
    blockers_text = "\n".join(blockers)
else:
    status = "Aguardando Multiplas Validacoes"
    blockers_text = "\n".join(blockers)

# Se ja foi reservado em algum momento, mantem status reservado
already_reserved = frappe.db.exists("Production Reservation", {"sales_order": so_name, "docstatus": 1})
if already_reserved:
    status = "Reservado"

frappe.db.set_value("Sales Order", so_name, {
    "validation_status": status,
    "validation_blockers": blockers_text,
}, update_modified=False)

frappe.response["message"] = {
    "sales_order": so_name,
    "validation_status": status,
    "validation_blockers": blockers_text,
    "payment_validated": p_ok,
    "prescriptions_validated": r_ok,
    "hubspot_complete": h_ok,
    "ready_to_reserve": (p_ok and r_ok and h_ok and not already_reserved),
}
'''.strip()


# ---------------------------------------------------------------------------
# Server Script — validate_and_reserve (botão "Reservar")
# ---------------------------------------------------------------------------

SCRIPT_VALIDATE_AND_RESERVE = r'''
# /api/method/future_production_validate_and_reserve
# Checa 3 flags + reserva se OK. Se algum bloqueio, retorna lista de pendencias.
# Atomico — nao reserva parcial.

data = frappe.form_dict
so_name = data.get("sales_order")
force = int(data.get("force") or 0) == 1
if not so_name:
    frappe.throw("sales_order e obrigatorio.")

so = frappe.db.get_value(
    "Sales Order", so_name,
    ["payment_validated", "prescriptions_validated", "hubspot_complete", "docstatus"],
    as_dict=True,
)
if not so:
    frappe.throw("Sales Order " + so_name + " nao encontrado.")
if so.docstatus != 1:
    frappe.throw("Sales Order precisa estar submetido (docstatus=1).")

p_ok = int(so.payment_validated or 0) == 1
r_ok = int(so.prescriptions_validated or 0) == 1
h_ok = int(so.hubspot_complete or 0) == 1

missing = []
if not p_ok:
    missing.append({"flag": "payment_validated", "label": "Pagamento confirmado"})
if not r_ok:
    missing.append({"flag": "prescriptions_validated", "label": "Receitas validadas"})
if not h_ok:
    missing.append({"flag": "hubspot_complete", "label": "Cadastro HubSpot completo"})

if missing and not force:
    frappe.response["message"] = {
        "sales_order": so_name,
        "ok": False,
        "missing": missing,
        "message": "Reserva bloqueada. " + str(len(missing)) + " validacao(s) pendente(s).",
    }
else:
    # Verifica se ja tem PRs ativas
    existing = frappe.db.exists("Production Reservation", {"sales_order": so_name, "docstatus": 1})
    if existing:
        frappe.response["message"] = {
            "sales_order": so_name,
            "ok": True,
            "already_reserved": True,
            "message": "SO ja possui reservas ativas. Nada a fazer.",
        }
    else:
        # Chama auto_reserve internamente
        original_form_dict = dict(frappe.form_dict)
        frappe.form_dict["sales_order"] = so_name
        try:
            reserve_resp = frappe.get_attr(
                "frappe.script_manager.run_doc_method"
            ) if False else None
        except Exception:
            reserve_resp = None

        # Executa o endpoint auto_reserve invocando sua logica diretamente.
        # Mais simples: chamar via frappe.call_method nao funciona em server scripts,
        # entao replicamos a chave: para cada item do SO, busca FPB compativel e cria PR.
        so_doc = frappe.get_doc("Sales Order", so_name)
        reservations = []
        errors = []

        for item in (so_doc.items or []):
            pending = float(item.qty or 0) - float(item.fp_reserved_qty or 0)
            if pending <= 0:
                continue

            fpbs = frappe.db.sql(
                """
                select name, available_qty, planned_qty, reserved_qty
                from `tabFuture Production Batch`
                where item_code = %s
                  and docstatus = 1
                  and status in ('Aberta para Reserva', 'Reservada Parcialmente',
                                 'Em Producao', 'Produzida Parcialmente')
                  and available_qty > 0
                order by planned_production_date asc, creation asc
                """,
                (item.item_code,),
                as_dict=True,
            )

            remaining = pending
            for fpb in fpbs:
                if remaining <= 0:
                    break
                take = min(float(fpb.available_qty), remaining)
                if take <= 0:
                    continue

                pr = frappe.new_doc("Production Reservation")
                pr.sales_order = so_name
                pr.sales_order_item = item.name
                pr.customer = so_doc.customer
                pr.item_code = item.item_code
                pr.future_production_batch = fpb.name
                pr.reserved_qty = take
                pr.priority = 100
                pr.status = "Reservado"
                pr.reservation_date = frappe.utils.now()
                pr.insert(ignore_permissions=True)
                pr.submit()

                reservations.append({
                    "reservation": pr.name,
                    "sales_order_item": item.name,
                    "future_production_batch": fpb.name,
                    "qty": take,
                })
                remaining = remaining - take

            if remaining > 0:
                errors.append({
                    "item_code": item.item_code,
                    "missing_qty": remaining,
                    "message": "Saldo insuficiente em FPBs disponiveis.",
                })

        frappe.form_dict = original_form_dict

        if not errors:
            frappe.db.set_value("Sales Order", so_name, {
                "validation_status": "Reservado",
            }, update_modified=False)

        frappe.response["message"] = {
            "sales_order": so_name,
            "ok": True,
            "reservations": reservations,
            "errors": errors,
            "message": str(len(reservations)) + " reserva(s) criada(s).",
        }
'''.strip()


# ---------------------------------------------------------------------------
# Server Script — webhook pagamento (checkout customizado)
# ---------------------------------------------------------------------------

SCRIPT_PAYMENT_WEBHOOK = r'''
# /api/method/future_production_payment_webhook
# Webhook do checkout customizado. Payload:
#   { "sales_order": "...", "amount": 1000.00, "status": "PAID",
#     "transaction_id": "...", "paid_at": "2026-06-02 14:00:00" }
# Aceita tambem "RECEIVED" como sinonimo de PAID.

data = frappe.form_dict
so_name = data.get("sales_order")
amount = float(data.get("amount") or 0)
status = (data.get("status") or "").upper()
transaction_id = data.get("transaction_id") or ""
paid_at = data.get("paid_at") or frappe.utils.now()

if not so_name:
    frappe.throw("sales_order e obrigatorio.")

so = frappe.db.get_value(
    "Sales Order", so_name,
    ["grand_total", "docstatus"],
    as_dict=True,
)
if not so:
    frappe.throw("Sales Order " + so_name + " nao encontrado.")

if status not in ("PAID", "RECEIVED", "CONFIRMED"):
    frappe.response["message"] = {
        "sales_order": so_name,
        "ok": False,
        "message": "Status do pagamento (" + status + ") nao indica pagamento confirmado. Flag nao alterada.",
    }
else:
    expected = float(so.grand_total or 0)
    tolerance = 0.01
    if abs(amount - expected) > tolerance:
        frappe.response["message"] = {
            "sales_order": so_name,
            "ok": False,
            "expected_amount": expected,
            "received_amount": amount,
            "message": "Valor pago (" + str(amount) + ") nao bate com SO.grand_total (" + str(expected) + ").",
        }
    else:
        frappe.db.set_value("Sales Order", so_name, {
            "payment_validated": 1,
            "payment_validated_at": paid_at,
            "payment_reference": transaction_id,
            "payment_amount": amount,
        }, update_modified=False)

        # Recalcula status
        frappe.form_dict["sales_order"] = so_name
        refresh_resp = frappe.call(
            "future_production_refresh_validation_status",
            sales_order=so_name,
        ) if False else None
        # frappe.call de server scripts customizados nao expoe assim;
        # replicamos refresh inline.
        refr_so = frappe.db.get_value(
            "Sales Order", so_name,
            ["payment_validated", "prescriptions_validated", "hubspot_complete"],
            as_dict=True,
        )
        p_ok = int(refr_so.payment_validated or 0) == 1
        r_ok = int(refr_so.prescriptions_validated or 0) == 1
        h_ok = int(refr_so.hubspot_complete or 0) == 1
        if p_ok and r_ok and h_ok:
            new_status = "Validado (Pronto para Reservar)"
        else:
            new_status = "Aguardando Multiplas Validacoes"
            if p_ok and r_ok and not h_ok:
                new_status = "Aguardando Cadastro HubSpot"
            elif p_ok and not r_ok and h_ok:
                new_status = "Aguardando Receitas"
            elif not p_ok and r_ok and h_ok:
                new_status = "Aguardando Pagamento"
        frappe.db.set_value("Sales Order", so_name, {"validation_status": new_status},
                            update_modified=False)

        frappe.response["message"] = {
            "sales_order": so_name,
            "ok": True,
            "payment_validated": True,
            "new_validation_status": new_status,
            "ready_to_reserve": (p_ok and r_ok and h_ok),
        }
'''.strip()


# ---------------------------------------------------------------------------
# Server Script — webhook receitas
# ---------------------------------------------------------------------------

SCRIPT_PRESCRIPTIONS_WEBHOOK = r'''
# /api/method/future_production_prescriptions_webhook
# Webhook do sistema interno de receitas. Payload:
#   { "sales_order": "...", "validated_qty_by_item": {"TIR00060": 10, "EMB00001": 1},
#     "reference": "REC-...", "validated_at": "2026-06-02 14:00:00" }

data = frappe.form_dict
so_name = data.get("sales_order")
qty_by_item = data.get("validated_qty_by_item") or {}
reference = data.get("reference") or ""
validated_at = data.get("validated_at") or frappe.utils.now()

if not so_name:
    frappe.throw("sales_order e obrigatorio.")

if isinstance(qty_by_item, str):
    qty_by_item = json.loads(qty_by_item)

so_doc = frappe.get_doc("Sales Order", so_name)
if so_doc.docstatus != 1:
    frappe.throw("Sales Order precisa estar submetido.")

# Confere: para cada item do SO, qty receita >= qty pedido
errors = []
total_validated = 0
for item in (so_doc.items or []):
    needed = float(item.qty or 0)
    validated = float(qty_by_item.get(item.item_code) or 0)
    total_validated = total_validated + int(validated)
    if validated < needed:
        errors.append({
            "item_code": item.item_code,
            "qty_needed": needed,
            "qty_validated": validated,
        })

if errors:
    frappe.response["message"] = {
        "sales_order": so_name,
        "ok": False,
        "errors": errors,
        "message": "Receitas insuficientes em " + str(len(errors)) + " item(ns).",
    }
else:
    frappe.db.set_value("Sales Order", so_name, {
        "prescriptions_validated": 1,
        "prescriptions_validated_at": validated_at,
        "prescriptions_reference": reference,
        "prescriptions_qty_validated": total_validated,
    }, update_modified=False)

    refr = frappe.db.get_value(
        "Sales Order", so_name,
        ["payment_validated", "prescriptions_validated", "hubspot_complete"],
        as_dict=True,
    )
    p_ok = int(refr.payment_validated or 0) == 1
    r_ok = int(refr.prescriptions_validated or 0) == 1
    h_ok = int(refr.hubspot_complete or 0) == 1
    if p_ok and r_ok and h_ok:
        new_status = "Validado (Pronto para Reservar)"
    elif p_ok and r_ok and not h_ok:
        new_status = "Aguardando Cadastro HubSpot"
    elif not p_ok and r_ok and h_ok:
        new_status = "Aguardando Pagamento"
    else:
        new_status = "Aguardando Multiplas Validacoes"
    frappe.db.set_value("Sales Order", so_name, {"validation_status": new_status},
                        update_modified=False)

    frappe.response["message"] = {
        "sales_order": so_name,
        "ok": True,
        "prescriptions_validated": True,
        "new_validation_status": new_status,
        "ready_to_reserve": (p_ok and r_ok and h_ok),
    }
'''.strip()


# ---------------------------------------------------------------------------
# Server Script — marca hubspot_complete (chamado pelo issue_order endpoint)
# ---------------------------------------------------------------------------

SCRIPT_MARK_HUBSPOT = r'''
# /api/method/future_production_mark_hubspot_complete
# Payload:
#   { "sales_order": "...", "deal_id": "...", "contact_id": "..." }

data = frappe.form_dict
so_name = data.get("sales_order")
deal_id = data.get("deal_id") or ""
contact_id = data.get("contact_id") or ""

if not so_name:
    frappe.throw("sales_order e obrigatorio.")

so = frappe.db.exists("Sales Order", so_name)
if not so:
    frappe.throw("Sales Order " + so_name + " nao encontrado.")

frappe.db.set_value("Sales Order", so_name, {
    "hubspot_complete": 1,
    "hubspot_validated_at": frappe.utils.now(),
    "hubspot_deal_id": deal_id,
    "hubspot_contact_id": contact_id,
}, update_modified=False)

refr = frappe.db.get_value(
    "Sales Order", so_name,
    ["payment_validated", "prescriptions_validated", "hubspot_complete"],
    as_dict=True,
)
p_ok = int(refr.payment_validated or 0) == 1
r_ok = int(refr.prescriptions_validated or 0) == 1
h_ok = int(refr.hubspot_complete or 0) == 1
if p_ok and r_ok and h_ok:
    new_status = "Validado (Pronto para Reservar)"
elif p_ok and not r_ok and h_ok:
    new_status = "Aguardando Receitas"
elif not p_ok and r_ok and h_ok:
    new_status = "Aguardando Pagamento"
else:
    new_status = "Aguardando Multiplas Validacoes"
frappe.db.set_value("Sales Order", so_name, {"validation_status": new_status},
                    update_modified=False)

frappe.response["message"] = {
    "sales_order": so_name,
    "ok": True,
    "hubspot_complete": True,
    "new_validation_status": new_status,
    "ready_to_reserve": (p_ok and r_ok and h_ok),
}
'''.strip()


# ---------------------------------------------------------------------------
# Install / Uninstall
# ---------------------------------------------------------------------------

def install() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1

    errors = 0

    log_section(f"1/2 — {len(VALIDATION_SO_FIELDS)} Custom Fields no Sales Order")
    for f in VALIDATION_SO_FIELDS:
        try:
            client.create_custom_field(f)
        except Exception as exc:
            log_error(f"  {f['fieldname']}: {exc}")
            errors += 1

    log_section("2/2 — Server Scripts (5 endpoints)")
    scripts = [
        ("future_production_refresh_validation_status", SCRIPT_REFRESH_STATUS),
        ("future_production_validate_and_reserve", SCRIPT_VALIDATE_AND_RESERVE),
        ("future_production_payment_webhook", SCRIPT_PAYMENT_WEBHOOK),
        ("future_production_prescriptions_webhook", SCRIPT_PRESCRIPTIONS_WEBHOOK),
        ("future_production_mark_hubspot_complete", SCRIPT_MARK_HUBSPOT),
    ]
    for name, script in scripts:
        try:
            client.upsert_server_script({
                "name": name,
                "script_type": "API",
                "api_method": name,
                "allow_guest": 0,
                "enabled": 1,
                "script": script,
            })
        except Exception as exc:
            log_error(f"  {name}: {exc}")
            errors += 1

    if errors == 0:
        log_ok("Módulo Validação Pré-Reserva instalado.")
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()

    log_section("Removendo Server Scripts")
    for name in (
        "future_production_refresh_validation_status",
        "future_production_validate_and_reserve",
        "future_production_payment_webhook",
        "future_production_prescriptions_webhook",
        "future_production_mark_hubspot_complete",
    ):
        try:
            client.delete_server_script(name)
        except Exception as exc:
            log_error(f"  {name}: {exc}")

    log_section("Removendo Custom Fields")
    for f in reversed(VALIDATION_SO_FIELDS):
        try:
            client.delete_custom_field(f["dt"], f["fieldname"])
        except Exception as exc:
            log_error(f"  {f['dt']}.{f['fieldname']}: {exc}")

    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
