"""
setup_22_reservation_ops.py — operacoes de RESERVA: cancelar e trocar.

Pedido pode ficar gerado no sistema SEM reserva. Dois endpoints:

  1. future_production_cancel_reservation
       Cancela a(s) reserva(s) — libera o lote. O PEDIDO CONTINUA no sistema
       (submetido), so fica SEM reserva. Limpa o lote por paciente (fp_patients).
       body: { sales_order | deal_id, item_code? }
         - item_code ausente → cancela TODAS as reservas do pedido.
         - item_code presente → cancela so as reservas daquele produto (chave
           produto + pedido).

  2. future_production_swap_reservation
       Troca o lote da reserva (chave PRODUTO + PEDIDO HubSpot). Cancela a
       reserva atual do(s) item(ns), libera o lote antigo, e reserva no lote
       novo (item_fpb/fpb_map/fpb_name) + re-distribui os pacientes (bin-pack).
       body: { sales_order | deal_id,
               item_fpb:[{item_code, lotes:[{fpb_name, qty}]}] | fpb_map | fpb_name }

Ambos resolvem o pedido por sales_order direto OU por deal_id (HubSpot).
O hook "PR - On Cancel" devolve o saldo do FPB e atualiza o Sales Order Item
automaticamente no cancelamento — aqui so disparamos o cancel + limpamos o
lote por paciente.

Uso:
    python setup/setup_22_reservation_ops.py
    python setup/setup_22_reservation_ops.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


# Resolve SO por sales_order direto ou deal_id (HubSpot) — bloco reusado.
RESOLVE_SO = r'''
so_name = data.get("sales_order")
if not so_name:
    deal = data.get("deal_id") or ""
    if not deal and data.get("hubspot"):
        deal = (data.get("hubspot") or {}).get("deal_id") or ""
    if deal:
        so_name = frappe.db.get_value("Sales Order",
            {"hubspot_deal_id": str(deal), "docstatus": ["!=", 2]}, "name")
if not so_name:
    frappe.throw("[MISSING_SO] Informe sales_order ou deal_id valido.")
'''


# ===========================================================================
# 1) CANCELAR reserva — libera lote, pedido continua sem reserva
# ===========================================================================
SCRIPT_CANCEL = (r'''
# /api/method/future_production_cancel_reservation
# body: { sales_order | deal_id, item_code?, cancel_order?, cancel_payments? }
#   cancel_order=false (default) → cancela so a reserva; PEDIDO CONTINUA no sistema.
#   cancel_order=true            → cancela reserva + o Sales Order ("com pedido e tudo").
#       Pre-flight: se houver recebimento (Payment Entry) lancado, THROW atomico
#       (nada e cancelado) — a menos que cancel_payments=true, que estorna os PEs.
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)
''' + RESOLVE_SO + r'''
item_filter = (data.get("item_code") or "").strip()
cancel_order = int(data.get("cancel_order") or 0)
cancel_payments = int(data.get("cancel_payments") or 0)

# Recebimentos (Payment Entry submetidos) ligados ao pedido
linked_pes = frappe.db.sql(
    "select distinct per.parent from `tabPayment Entry Reference` per "
    "join `tabPayment Entry` pe on pe.name = per.parent "
    "where per.reference_doctype = 'Sales Order' and per.reference_name = %s "
    "and pe.docstatus = 1",
    (so_name,), as_dict=False)
pe_names = [row[0] for row in linked_pes]

# PRE-FLIGHT atomico: cancelar o pedido com recebimento lancado exige decisao explicita.
# item_filter nao faz sentido com cancel_order (cancela o pedido inteiro).
if cancel_order and item_filter:
    frappe.throw("[ITEM_FILTER_WITH_ORDER] Nao combine item_code com cancel_order: "
                 "cancelar o pedido afeta todos os itens. Remova item_code.")
if cancel_order and pe_names and not cancel_payments:
    frappe.throw("[ORDER_HAS_PAYMENTS] Pedido " + so_name + " tem recebimento(s) "
                 "lancado(s): " + ", ".join(pe_names) + ". Estorne antes, ou passe "
                 "cancel_payments=true pra cancelar os recebimentos junto.")

filters = {"sales_order": so_name, "docstatus": 1}
if item_filter:
    filters["item_code"] = item_filter
prs = frappe.get_all("Production Reservation", filters=filters,
    fields=["name", "item_code", "future_production_batch", "reserved_qty"])

cancelled = []
items_done = {}
for pr in prs:
    doc = frappe.get_doc("Production Reservation", pr.name)
    doc.cancel()  # hook "PR - On Cancel" devolve saldo do FPB + atualiza SOI
    cancelled.append({"reservation": pr.name, "item_code": pr.item_code,
        "future_production_batch": pr.future_production_batch,
        "reserved_qty": float(pr.reserved_qty or 0)})
    items_done[pr.item_code] = True

# Limpa o lote por paciente (fp_patients) dos itens cancelados
cleared = 0
so_doc = frappe.get_doc("Sales Order", so_name)
for r in so_doc.fp_patients:
    if (item_filter == "" or r.item_code == item_filter) and (r.fp_future_production_batch or ""):
        frappe.db.set_value("Sales Order Patient", r.name,
            "fp_future_production_batch", None, update_modified=False)
        cleared = cleared + 1

# Cancela o pedido (e recebimentos) se pedido — senao o SO continua submetido.
payments_cancelled = []
order_cancelled = False
if cancel_order:
    if cancel_payments:
        for pn in pe_names:
            frappe.get_doc("Payment Entry", pn).cancel()
            payments_cancelled.append(pn)
    so_full = frappe.get_doc("Sales Order", so_name)
    if so_full.docstatus == 1:
        so_full.cancel()
        order_cancelled = True

frappe.response["message"] = {"ok": True, "sales_order": so_name,
    "cancelled": cancelled, "patients_cleared": cleared,
    "order_cancelled": order_cancelled,
    "payments_cancelled": payments_cancelled,
    "message": ("Nenhuma reserva ativa." if not cancelled and not order_cancelled
                else None)}
''').strip()


# ===========================================================================
# 2) TROCAR reserva — cancela lote antigo + reserva lote novo (chave produto+pedido)
# ===========================================================================
SCRIPT_SWAP = (r'''
# /api/method/future_production_swap_reservation
# body: { sales_order | deal_id,
#         item_fpb:[{item_code, lotes:[{fpb_name, qty}]}] | fpb_map | fpb_name }
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)
''' + RESOLVE_SO + r'''
item_fpb = data.get("item_fpb") or []
fpb_map = data.get("fpb_map") or {}
single = (data.get("fpb_name") or "").strip()

# alloc por item: [{fpb_name, qty}]
alloc = {}
for e in item_fpb:
    ic = (e.get("item_code") or "").strip()
    cleaned = []
    for lt in (e.get("lotes") or e.get("allocations") or []):
        fn = (lt.get("fpb_name") or "").strip()
        q = float(lt.get("qty") or 0)
        if fn and q > 0:
            cleaned.append({"fpb_name": fn, "qty": q})
    if cleaned:
        alloc[ic] = cleaned

so_doc = frappe.get_doc("Sales Order", so_name)
totals = {}
so_item_name = {}
for it in so_doc.items:
    totals[it.item_code] = totals.get(it.item_code, 0) + float(it.qty or 0)
    if it.item_code not in so_item_name:
        so_item_name[it.item_code] = it.name

# Itens-alvo do swap (chave produto): item_fpb > fpb_map > (single → todos stock)
target_items = []
if alloc:
    target_items = list(alloc.keys())
elif fpb_map:
    target_items = list(fpb_map.keys())
elif single:
    for ic in totals.keys():
        is_stock = frappe.db.get_value("Item", ic, "is_stock_item")
        if int(is_stock or 0):
            target_items.append(ic)
if not target_items:
    frappe.throw("[BATCH_REQUIRED] Informe o(s) lote(s) novo(s) (item_fpb/fpb_map/fpb_name) pra trocar.")

# 1) CANCELA reservas atuais dos itens-alvo (libera lote antigo)
cancelled = []
for ic in target_items:
    prs = frappe.get_all("Production Reservation",
        filters={"sales_order": so_name, "item_code": ic, "docstatus": 1},
        fields=["name", "future_production_batch", "reserved_qty"])
    for pr in prs:
        doc = frappe.get_doc("Production Reservation", pr.name)
        doc.cancel()  # hook devolve saldo do FPB antigo
        cancelled.append({"reservation": pr.name, "item_code": ic,
            "future_production_batch": pr.future_production_batch,
            "reserved_qty": float(pr.reserved_qty or 0)})

# 2) limpa lote por paciente dos itens-alvo (vai re-bin-packar abaixo)
for r in so_doc.fp_patients:
    if r.item_code in target_items and (r.fp_future_production_batch or ""):
        frappe.db.set_value("Sales Order Patient", r.name,
            "fp_future_production_batch", None, update_modified=False)

# 3) RE-RESERVA nos lotes novos (mesma validacao do step_reserve)
def fpb_info(name):
    rr = frappe.db.sql(
        "select name, (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) as avail, "
        "item_code, status, docstatus from `tabFuture Production Batch` where name=%s",
        (name,), as_dict=True)
    return rr[0] if rr else None

reservations = []
errors = []
for item_code in target_items:
    total = totals.get(item_code, 0)
    soi = so_item_name.get(item_code)
    if not soi:
        errors.append({"code": "ITEM_NOT_IN_ORDER", "item_code": item_code,
            "error": "Item " + str(item_code) + " nao esta no pedido " + so_name + "."})
        continue
    lotes = []
    if item_code in alloc:
        lotes = alloc[item_code]
    else:
        s = (fpb_map.get(item_code) or "").strip() or single
        if s:
            lotes = [{"fpb_name": s, "qty": total}]
    if not lotes:
        errors.append({"code": "BATCH_REQUIRED", "item_code": item_code,
            "error": "Lote obrigatorio: selecione o lote para o produto " +
            str(item_code) + " (nao ha selecao automatica)."})
        continue
    for lt in lotes:
        info = fpb_info(lt["fpb_name"])
        if not info:
            errors.append({"code": "BATCH_NOT_FOUND", "item_code": item_code, "fpb": lt["fpb_name"],
                "error": "Lote " + lt["fpb_name"] + " nao encontrado"})
            continue
        if int(info.docstatus or 0) != 1:
            errors.append({"code": "BATCH_NOT_SUBMITTED", "item_code": item_code, "fpb": lt["fpb_name"],
                "error": "Lote " + lt["fpb_name"] + " nao esta submetido"})
            continue
        if info.item_code != item_code:
            errors.append({"code": "BATCH_WRONG_ITEM", "item_code": item_code, "fpb": lt["fpb_name"],
                "error": "Lote " + lt["fpb_name"] + " e de outro produto (" + str(info.item_code) + ")"})
            continue
        if (info.status or "") not in ("Aberta para Reserva", "Reservada Parcialmente"):
            errors.append({"code": "BATCH_CLOSED", "item_code": item_code, "fpb": lt["fpb_name"],
                "error": "Lote " + lt["fpb_name"] + " nao aceita reservas (status: " + str(info.status) + ")"})
            continue
        qreq = float(lt["qty"])
        if float(info.avail or 0) < qreq:
            errors.append({"code": "INSUFFICIENT_QTY", "item_code": item_code, "fpb": lt["fpb_name"],
                "qty": qreq, "available": float(info.avail or 0),
                "error": "Nao ha quantidade disponivel no lote " + lt["fpb_name"] +
                " (disponivel " + str(float(info.avail or 0)) + ", solicitado " + str(qreq) + ")"})
            continue
        pr = frappe.new_doc("Production Reservation")
        pr.sales_order = so_name
        pr.sales_order_item = soi
        pr.future_production_batch = lt["fpb_name"]
        pr.item_code = item_code
        pr.reserved_qty = qreq
        pr.insert(ignore_permissions=True)
        pr.submit()
        reservations.append({"reservation": pr.name, "future_production_batch": lt["fpb_name"],
            "item_code": item_code, "reserved_qty": qreq})

# 4) RE-BIN-PACK pacientes nos lotes novos (1 receita = 1 lote inteiro)
remaining = {}
order_lotes = {}
for ic in target_items:
    order_lotes.setdefault(ic, [])
    lts = alloc.get(ic) or []
    if not lts:
        s = (fpb_map.get(ic) or "").strip() or single
        if s:
            lts = [{"fpb_name": s, "qty": totals.get(ic, 0)}]
    for lt in lts:
        fn = lt["fpb_name"]
        q = float(lt["qty"])
        remaining[(ic, fn)] = remaining.get((ic, fn), 0) + q
        if fn not in order_lotes[ic]:
            order_lotes[ic].append(fn)

so_fresh = frappe.get_doc("Sales Order", so_name)
pat_rows = []
for r in so_fresh.fp_patients:
    if r.item_code in target_items:
        pat_rows.append({"name": r.name, "item_code": r.item_code,
            "qty": float(r.qty or 0), "patient": r.patient})
pat_rows = sorted(pat_rows, key=lambda x: x["qty"], reverse=True)

patient_assignments = []
pack_errors = []
for r in pat_rows:
    ic = r["item_code"]
    qty = r["qty"]
    chosen = None
    for fn in order_lotes.get(ic, []):
        if remaining.get((ic, fn), 0) >= qty:
            remaining[(ic, fn)] = remaining[(ic, fn)] - qty
            chosen = fn
            break
    if order_lotes.get(ic) and not chosen:
        pack_errors.append({"code": "PATIENT_NOT_FIT", "item_code": ic,
            "patient": r["patient"], "qty": qty,
            "error": "Paciente " + str(r["patient"]) + " (qtd " + str(qty) +
            ") nao cabe em nenhum lote restante. Ajuste as quantidades por lote."})
        continue
    frappe.db.set_value("Sales Order Patient", r["name"],
        "fp_future_production_batch", chosen, update_modified=False)
    patient_assignments.append({"patient": r["patient"], "item_code": ic,
        "qty": qty, "fpb": chosen})

frappe.response["message"] = {"ok": True, "sales_order": so_name,
    "cancelled": cancelled, "reservations": reservations,
    "reserve_errors": errors, "patient_assignments": patient_assignments,
    "pack_errors": pack_errors}
''').strip()


ENDPOINTS = [
    ("future_production_cancel_reservation", SCRIPT_CANCEL),
    ("future_production_swap_reservation", SCRIPT_SWAP),
]


def install() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1
    log_section("Reservation ops (cancel / swap)")
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
