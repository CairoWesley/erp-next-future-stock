"""
setup_19_step_endpoints.py — 4 endpoints GRANULARES pro fluxo n8n node-by-node.

Cada etapa do n8n chama UM endpoint. Ordem:

  1. future_production_step_customer  — Cliente + Address + Contact
  2. future_production_step_order     — Sales Order (items) + flags + submit
  3. future_production_step_reserve   — Reserva por lote (item_fpb → 1 PR/lote)
  4. future_production_step_patients  — Pacientes + Médico + fp_patients + bin-pack lote

Todos idempotentes. Reusam padrões do setup_14 mas separados pra visibilidade
no n8n (cada node = 1 etapa nomeada).

Uso:
    python setup/setup_19_step_endpoints.py
    python setup/setup_19_step_endpoints.py --uninstall
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


# ===========================================================================
# 1) CLIENTE — Customer + Address + Contact
# ===========================================================================
SCRIPT_STEP_CUSTOMER = r'''
# /api/method/future_production_step_customer
# body: { customer: {customer_name, customer_type, tax_id, customer_group,
#                     territory, email_id, mobile_no, address{}, contact{}} }
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)
cin = data.get("customer") or {}
name_in = cin.get("customer_name") or cin.get("name")
if not name_in:
    frappe.throw("customer.customer_name obrigatorio.")

def digits(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())

cust = frappe.db.get_value("Customer", {"customer_name": name_in}, "name")
created = False
if cust:
    if cin.get("tax_id"):
        frappe.db.set_value("Customer", cust, "tax_id", digits(cin.get("tax_id")))
    if cin.get("customer_group"):
        frappe.db.set_value("Customer", cust, "customer_group", cin.get("customer_group"))
else:
    doc = frappe.new_doc("Customer")
    doc.customer_name = name_in
    doc.customer_type = cin.get("customer_type") or "Individual"
    doc.customer_group = cin.get("customer_group") or "Comercial"
    doc.territory = cin.get("territory") or "Brazil"
    if cin.get("tax_id"):
        doc.tax_id = digits(cin.get("tax_id"))
    if cin.get("mobile_no"):
        doc.mobile_no = cin.get("mobile_no")
    if cin.get("email_id"):
        doc.email_id = cin.get("email_id")
    doc.insert(ignore_permissions=True)
    cust = doc.name
    created = True

# Address
addr_in = cin.get("address") or {}
addr_name = None
if addr_in and (addr_in.get("address_line1") or addr_in.get("pincode")):
    title = addr_in.get("title") or name_in
    atype = addr_in.get("type") or "Billing"
    key = title + "-" + atype
    if frappe.db.exists("Address", key):
        addr_name = key
    else:
        a = frappe.new_doc("Address")
        a.address_title = title
        a.address_type = atype
        a.address_line1 = addr_in.get("address_line1") or "-"
        a.address_line2 = addr_in.get("address_line2") or ""
        a.city = addr_in.get("city") or ""
        a.state = addr_in.get("state") or ""
        a.pincode = digits(addr_in.get("pincode"))
        a.country = addr_in.get("country") or "Brazil"
        a.email_id = addr_in.get("email_id") or ""
        a.phone = addr_in.get("phone") or ""
        a.is_primary_address = 1
        a.is_shipping_address = 1
        a.append("links", {"link_doctype": "Customer", "link_name": cust})
        a.insert(ignore_permissions=True)
        addr_name = a.name

# Contact
ct_in = cin.get("contact") or {}
ct_name = None
if ct_in and ct_in.get("first_name"):
    existing = frappe.db.sql(
        "select c.name from `tabContact` c join `tabDynamic Link` dl "
        "on dl.parent=c.name where dl.link_doctype='Customer' and dl.link_name=%s limit 1",
        (cust,), as_dict=False)
    if existing:
        ct_name = existing[0][0]
    else:
        ct = frappe.new_doc("Contact")
        ct.first_name = ct_in.get("first_name")
        ct.last_name = ct_in.get("last_name") or ""
        if ct_in.get("email"):
            ct.append("email_ids", {"email_id": ct_in.get("email"), "is_primary": 1})
        if ct_in.get("phone"):
            ct.append("phone_nos", {"phone": ct_in.get("phone"),
                                    "is_primary_mobile_no": 1, "is_primary_phone": 1})
        ct.is_primary_contact = 1
        ct.append("links", {"link_doctype": "Customer", "link_name": cust})
        ct.insert(ignore_permissions=True)
        ct_name = ct.name

frappe.response["message"] = {
    "ok": True, "customer": cust, "created": created,
    "address": addr_name, "contact": ct_name,
}
'''.strip()


# ===========================================================================
# 2) PEDIDO — Sales Order (items) + flags + submit
# ===========================================================================
SCRIPT_STEP_ORDER = r'''
# /api/method/future_production_step_order
# body: { customer, company, items[], hubspot:{deal_id,contact_id},
#         payment:{amount,status,transaction_id,paid_at}, prescriptions:{count,reference},
#         delivery_date }
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)

cust_in = data.get("customer")
if isinstance(cust_in, dict):
    cust = frappe.db.get_value("Customer", {"customer_name": cust_in.get("customer_name")}, "name")
else:
    cust = cust_in
if not cust:
    frappe.throw("customer nao encontrado.")

company = data.get("company") or "Injemedpharma"
items_in = data.get("items") or []
if not items_in:
    frappe.throw("items vazio.")
hub = data.get("hubspot") or {}
deal_id = hub.get("deal_id") or ""
contact_id = hub.get("contact_id") or ""
delivery_date = data.get("delivery_date")

# Idempotency: SO ja existe pro deal?
existing_so = None
if deal_id:
    existing_so = frappe.db.get_value(
        "Sales Order", {"hubspot_deal_id": deal_id, "docstatus": ["!=", 2]}, "name")

if not existing_so:
    so = frappe.new_doc("Sales Order")
    so.customer = cust
    so.company = company
    so.transaction_date = frappe.utils.today()
    so.delivery_date = delivery_date or frappe.utils.add_days(frappe.utils.today(), 30)
    so.currency = "BRL"
    so.selling_price_list = "Venda Padrão"
    so.price_list_currency = "BRL"
    so.plc_conversion_rate = 1
    so.conversion_rate = 1
    so.hubspot_deal_id = deal_id
    so.hubspot_contact_id = contact_id
    so.hubspot_complete = 1
    so.hubspot_validated_at = frappe.utils.now()
    for it in items_in:
        so.append("items", {
            "item_code": it.get("item_code"),
            "qty": float(it.get("qty") or 0),
            "rate": float(it.get("rate") or 0),
            "warehouse": it.get("warehouse") or "Produtos Acabados - I",
            "delivery_date": delivery_date or frappe.utils.add_days(frappe.utils.today(), 30),
        })
    so.insert(ignore_permissions=True)
    # NAO submete aqui — fica DRAFT ate os pacientes serem adicionados
    # (fp_patients nao aceita append apos submit). step_patients submete no fim.
    existing_so = so.name

# Payment inline
pay = data.get("payment") or {}
if pay:
    st = (pay.get("status") or "").upper()
    amt = float(pay.get("amount") or 0)
    grand = float(frappe.db.get_value("Sales Order", existing_so, "grand_total") or 0)
    if st in ("PAID", "RECEIVED", "CONFIRMED") and abs(amt - grand) <= 0.01:
        frappe.db.set_value("Sales Order", existing_so, {
            "payment_validated": 1,
            "payment_validated_at": pay.get("paid_at") or frappe.utils.now(),
            "payment_reference": pay.get("transaction_id") or "",
            "payment_amount": amt,
        }, update_modified=False)

# Prescriptions inline
pres = data.get("prescriptions") or {}
if pres:
    frappe.db.set_value("Sales Order", existing_so, {
        "prescriptions_validated": 1,
        "prescriptions_validated_at": frappe.utils.now(),
        "prescriptions_qty_validated": int(pres.get("count") or 0),
        "prescriptions_reference": pres.get("reference") or "",
    }, update_modified=False)

# Map item_code -> [so_item_name]
so_items = {}
rows = frappe.db.get_all("Sales Order Item", filters={"parent": existing_so},
                         fields=["name", "item_code"])
for r in rows:
    so_items.setdefault(r.item_code, []).append(r.name)

frappe.response["message"] = {
    "ok": True,
    "sales_order": existing_so,
    "grand_total": frappe.db.get_value("Sales Order", existing_so, "grand_total"),
    "so_items": so_items,
}
'''.strip()


# ===========================================================================
# 3) RESERVA — item_fpb → 1 PR por lote (qty do operador)
# ===========================================================================
SCRIPT_STEP_RESERVE = r'''
# /api/method/future_production_step_reserve
# body: { sales_order, item_fpb:[{item_code, lotes:[{fpb_name, qty}]}],
#         fpb_map:{item_code:fpb_name}, fpb_name }
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)
so_name = data.get("sales_order")
if not so_name:
    frappe.throw("sales_order obrigatorio.")

item_fpb = data.get("item_fpb") or []
fpb_map = data.get("fpb_map") or {}
single = (data.get("fpb_name") or "").strip()

# Index alloc por item: [{fpb_name, qty}]
alloc = {}
for e in item_fpb:
    ic = (e.get("item_code") or "").strip()
    lotes = e.get("lotes") or e.get("allocations") or []
    cleaned = []
    for lt in lotes:
        fn = (lt.get("fpb_name") or "").strip()
        q = float(lt.get("qty") or 0)
        if fn and q > 0:
            cleaned.append({"fpb_name": fn, "qty": q})
    if cleaned:
        alloc[ic] = cleaned

def fpb_info(name):
    r = frappe.db.sql(
        "select name, (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) as avail, "
        "item_code, status, docstatus from `tabFuture Production Batch` where name=%s",
        (name,), as_dict=True)
    return r[0] if r else None

so_doc = frappe.get_doc("Sales Order", so_name)
reservations = []
errors = []
# Total por item (soma das linhas)
totals = {}
so_item_name = {}
for it in so_doc.items:
    totals[it.item_code] = totals.get(it.item_code, 0) + float(it.qty or 0)
    if it.item_code not in so_item_name:
        so_item_name[it.item_code] = it.name

for item_code, total in totals.items():
    is_stock = frappe.db.get_value("Item", item_code, "is_stock_item")
    if not int(is_stock or 0):
        continue
    soi = so_item_name[item_code]
    # Ja reservado?
    already = frappe.db.sql(
        "select coalesce(sum(reserved_qty),0) from `tabProduction Reservation` "
        "where sales_order=%s and sales_order_item=%s and docstatus=1",
        (so_name, soi), as_dict=False)
    already_qty = float((already[0][0] if already else 0) or 0)
    if already_qty >= total:
        continue
    # Monta lotes
    lotes = []
    if item_code in alloc:
        lotes = alloc[item_code]
    else:
        s = (fpb_map.get(item_code) or "").strip() or single
        if s:
            lotes = [{"fpb_name": s, "qty": total}]
        else:
            fifo = frappe.db.sql(
                "select name, (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) as avail "
                "from `tabFuture Production Batch` where item_code=%s and docstatus=1 "
                "and status in ('Aberta para Reserva','Reservada Parcialmente') "
                "and (coalesce(planned_qty,0)-coalesce(reserved_qty,0))>0 "
                "order by planned_production_date asc, creation asc", (item_code,), as_dict=True)
            acc = 0
            for f in fifo:
                if acc >= total:
                    break
                take = min(float(f.avail or 0), total - acc)
                lotes.append({"fpb_name": f.name, "qty": take})
                acc += take
    if not lotes:
        errors.append({"item_code": item_code, "message": "Nenhum lote pra item " + str(item_code)})
        continue
    # Cria 1 PR por lote (valida cada)
    for lt in lotes:
        info = fpb_info(lt["fpb_name"])
        if not info:
            errors.append({"item_code": item_code, "message": "FPB " + lt["fpb_name"] + " nao existe."})
            continue
        if int(info.docstatus or 0) != 1:
            errors.append({"item_code": item_code, "message": "FPB " + lt["fpb_name"] + " nao submetida."})
            continue
        if info.item_code != item_code:
            errors.append({"item_code": item_code, "message": "FPB " + lt["fpb_name"] + " e de outro item."})
            continue
        if (info.status or "") not in ("Aberta para Reserva", "Reservada Parcialmente"):
            errors.append({"item_code": item_code, "message": "FPB " + lt["fpb_name"] + " status=" + str(info.status)})
            continue
        qreq = float(lt["qty"])
        if float(info.avail or 0) < qreq:
            errors.append({"item_code": item_code, "qty": qreq, "available": float(info.avail or 0),
                           "message": "FPB " + lt["fpb_name"] + " saldo insuficiente."})
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

frappe.response["message"] = {"ok": True, "sales_order": so_name,
                              "reservations": reservations, "reserve_errors": errors}
'''.strip()


# ===========================================================================
# 4) PACIENTES — Patient + Médico + fp_patients + bin-pack lote
# ===========================================================================
SCRIPT_STEP_PATIENTS = r'''
# /api/method/future_production_step_patients
# body: { sales_order, prescribers[], patients[], fp_patients[],
#         item_fpb:[{item_code, lotes:[{fpb_name, qty}]}] }
data = frappe.form_dict
if isinstance(data, str):
    data = frappe.parse_json(data)
so_name = data.get("sales_order")
if not so_name:
    frappe.throw("sales_order obrigatorio.")

prescribers_in = data.get("prescribers") or []
patients_in = data.get("patients") or []
fpps_in = data.get("fp_patients") or []
item_fpb = data.get("item_fpb") or []

def digits(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())

# ---- Médicos (upsert por CPF, fallback CRM+UF placeholder) ----
pres_by_cpf = {}
pres_by_council = {}
created_pres = []
for p in prescribers_in:
    cpf = digits(p.get("cpf"))
    councils = p.get("councils") or []
    if not cpf and councils:
        c0 = councils[0]
        ct_type = c0.get("council_type") or "CRM"
        ct_st = c0.get("council_state") or ""
        ct_num = str(c0.get("council_number") or "")
        ex = frappe.db.sql("select parent from `tabPrescriber Council` "
            "where council_type=%s and council_state=%s and council_number=%s limit 1",
            (ct_type, ct_st, ct_num), as_dict=False)
        if ex:
            cpf = frappe.db.get_value("Prescriber", ex[0][0], "cpf") or ""
        if not cpf:
            base = digits(ct_num) or "0"
            cpf = ("9" + base)[:11].ljust(11, "0")
    if not cpf:
        continue
    exist = frappe.db.get_value("Prescriber", {"cpf": cpf}, "name")
    if exist:
        pname = exist
        pdoc = frappe.get_doc("Prescriber", exist)
        keys = set()
        for ec in (pdoc.councils or []):
            keys.add((ec.council_type or "") + "|" + (ec.council_state or "") + "|" + (ec.council_number or ""))
        chg = False
        for inc in councils:
            kk = (inc.get("council_type") or "") + "|" + (inc.get("council_state") or "") + "|" + str(inc.get("council_number") or "")
            if kk not in keys:
                pdoc.append("councils", {"council_type": inc.get("council_type"),
                    "council_number": str(inc.get("council_number") or ""),
                    "council_state": inc.get("council_state"),
                    "council_status": inc.get("council_status") or "Ativo",
                    "is_primary": int(inc.get("is_primary") or 0)})
                chg = True
        if chg:
            pdoc.save(ignore_permissions=True)
    else:
        np = frappe.new_doc("Prescriber")
        np.full_name = p.get("full_name") or "Sem Nome"
        np.cpf = cpf
        for inc in councils:
            np.append("councils", {"council_type": inc.get("council_type"),
                "council_number": str(inc.get("council_number") or ""),
                "council_state": inc.get("council_state"),
                "council_status": inc.get("council_status") or "Ativo",
                "is_primary": int(inc.get("is_primary") or 0)})
        if not (np.councils or []):
            continue
        np.insert(ignore_permissions=True)
        pname = np.name
        created_pres.append(pname)
    pres_by_cpf[cpf] = pname
    for cc in councils:
        ck = (cc.get("council_type") or "", cc.get("council_state") or "", str(cc.get("council_number") or ""))
        pres_by_council[ck] = pname

# ---- Pacientes (upsert por CPF) ----
pat_by_cpf = {}
created_pat = []
for pt in patients_in:
    cpf = digits(pt.get("cpf"))
    if not cpf:
        continue
    ex = frappe.db.get_value("Patient", {"cpf": cpf}, "name")
    if ex:
        if pt.get("patient_name"):
            frappe.db.set_value("Patient", ex, "patient_name", pt.get("patient_name"))
        pat_by_cpf[cpf] = ex
    else:
        np = frappe.new_doc("Patient")
        np.patient_name = pt.get("patient_name") or "Sem Nome"
        np.cpf = cpf
        np.sex = pt.get("gender") or pt.get("sex") or "Outro"
        if pt.get("mobile"):
            np.mobile = pt.get("mobile")
        np.insert(ignore_permissions=True)
        pat_by_cpf[cpf] = np.name
        created_pat.append(np.name)

# ---- Bin-pack: capacidade por lote vinda do item_fpb ----
# remaining[(item_code, fpb_name)] = qty
remaining = {}
order_lotes = {}  # item_code -> [fpb_name,...] (ordem)
for e in item_fpb:
    ic = (e.get("item_code") or "").strip()
    order_lotes.setdefault(ic, [])
    for lt in (e.get("lotes") or []):
        fn = (lt.get("fpb_name") or "").strip()
        q = float(lt.get("qty") or 0)
        if fn and q > 0:
            remaining[(ic, fn)] = remaining.get((ic, fn), 0) + q
            if fn not in order_lotes[ic]:
                order_lotes[ic].append(fn)

# Desconta o que ja foi atribuido em fp_patients existentes (idempotency)
so_doc = frappe.get_doc("Sales Order", so_name)
existing_pat_rows = {}  # (cpf, item_code) -> row
for r in so_doc.fp_patients:
    rc = frappe.db.get_value("Patient", r.patient, "cpf") or ""
    existing_pat_rows[(rc, r.item_code)] = r
    fn = (r.fp_future_production_batch or "").strip()
    if fn and (r.item_code, fn) in remaining:
        remaining[(r.item_code, fn)] = remaining[(r.item_code, fn)] - float(r.qty or 0)

# Ordena fp_patients novos por qty desc (first-fit-decreasing)
new_rows = []
for fp in fpps_in:
    cpf = digits(fp.get("patient_cpf"))
    ic = fp.get("item_code") or ""
    if (cpf, ic) in existing_pat_rows:
        continue  # ja na SO
    new_rows.append(fp)
new_rows = sorted(new_rows, key=lambda x: float(x.get("qty") or 0), reverse=True)

assignments = []
pack_errors = []
appended = []
for fp in new_rows:
    cpf = digits(fp.get("patient_cpf"))
    ic = fp.get("item_code") or ""
    qty = float(fp.get("qty") or 0)
    patient_name = pat_by_cpf.get(cpf)
    # Prescriber resolve
    pres_cpf = digits(fp.get("prescriber_cpf"))
    prescriber = pres_by_cpf.get(pres_cpf)
    pc = fp.get("prescriber_council") or {}
    if not prescriber and pc:
        ck = (pc.get("council_type") or "", pc.get("council_state") or "", str(pc.get("council_number") or ""))
        prescriber = pres_by_council.get(ck)
        if not prescriber:
            row = frappe.db.sql("select parent from `tabPrescriber Council` "
                "where council_type=%s and council_state=%s and council_number=%s limit 1",
                ck, as_dict=False)
            if row:
                prescriber = row[0][0]
    # council row id
    council_row = None
    if prescriber and pc:
        rr = frappe.db.sql("select name from `tabPrescriber Council` where parent=%s "
            "and council_type=%s and council_state=%s and council_number=%s limit 1",
            (prescriber, pc.get("council_type"), pc.get("council_state"), str(pc.get("council_number") or "")),
            as_dict=False)
        council_row = rr[0][0] if rr else None
    # bin-pack lote
    chosen = None
    for fn in order_lotes.get(ic, []):
        if remaining.get((ic, fn), 0) >= qty:
            remaining[(ic, fn)] = remaining[(ic, fn)] - qty
            chosen = fn
            break
    if order_lotes.get(ic) and not chosen:
        pack_errors.append({"item_code": ic, "patient": patient_name, "qty": qty,
            "message": "Paciente " + str(patient_name) + " (qty " + str(qty) + ") nao cabe em nenhum lote restante."})
        continue
    # Append row na SO
    so_doc.append("fp_patients", {
        "patient": patient_name,
        "item_code": ic,
        "qty": qty,
        "prescriber": prescriber,
        "prescriber_council_row": council_row or "",
        "fp_future_production_batch": chosen or None,
    })
    appended.append(cpf)
    assignments.append({"patient": patient_name, "item_code": ic, "qty": qty,
                        "fpb": chosen, "prescriber": prescriber})

if appended:
    so_doc.save(ignore_permissions=True)

# Submete o SO agora que os pacientes estao adicionados (se ainda draft)
submitted = False
so_fresh = frappe.get_doc("Sales Order", so_name)
if so_fresh.docstatus == 0:
    so_fresh.submit()
    submitted = True

frappe.response["message"] = {
    "ok": True, "sales_order": so_name,
    "patients_created": created_pat, "prescribers_created": created_pres,
    "assignments": assignments, "pack_errors": pack_errors,
    "so_submitted": submitted,
}
'''.strip()


ENDPOINTS = [
    ("future_production_step_customer", SCRIPT_STEP_CUSTOMER),
    ("future_production_step_order", SCRIPT_STEP_ORDER),
    ("future_production_step_reserve", SCRIPT_STEP_RESERVE),
    ("future_production_step_patients", SCRIPT_STEP_PATIENTS),
]


def install() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1
    log_section("4 endpoints granulares (step_customer/order/reserve/patients)")
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
