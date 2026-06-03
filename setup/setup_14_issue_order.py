"""
setup_14_issue_order.py — Endpoint único pra HubSpot/n8n criar pedido completo.

POST /api/method/future_production_issue_order
Body:
{
  "hubspot": {
    "deal_id": "...",
    "contact_id": "..."
  },
  "customer": {
    "name": "DEMO-Cliente Empresa Ltda",      # opcional. Se omitido, customer_name = name
    "customer_name": "DEMO-Cliente",
    "customer_type": "Company",                  # Company | Individual
    "tax_id": "12345678000190"                   # CNPJ ou CPF
  },
  "prescribers": [
    {
      "cpf": "12345678909",
      "full_name": "Dr José Silva",
      "councils": [
        {"council_type": "CRM", "council_number": "12345", "council_state": "SP", "is_primary": 1}
      ]
    }
  ],
  "patients": [
    {
      "cpf": "11144477735",
      "patient_name": "Maria Aparecida",
      "gender": "Feminino",
      "mobile": "11999990001",
      "default_prescriber_cpf": "12345678909"    # ref ao CPF do prescriber
    }
  ],
  "items": [
    {"item_code": "TIR00060", "qty": 10, "rate": 100, "warehouse": "Produtos Acabados - I"}
  ],
  "fp_patients": [
    {
      "patient_cpf": "11144477735",
      "prescriber_cpf": "12345678909",
      "prescriber_council": {"council_type": "CRM", "council_number": "12345", "council_state": "SP"},
      "item_code": "TIR00060",
      "qty": 10
    }
  ],
  "company": "Injmedpharma",                     # opcional, default Injmedpharma
  "delivery_date": "2026-07-15"                  # opcional, default +30d
}

Resposta:
{
  "message": {
    "sales_order": "SAL-ORD-2026-00001",
    "created": {
      "customer": "DEMO-Cliente",
      "prescribers": ["PRES-2026-00001"],
      "patients": ["PAC-2026-00001"]
    },
    "validation_status": "Aguardando Pagamento + Receitas",
    "hubspot_complete": true
  }
}

Idempotência:
- Customer por customer_name (lookup, atualiza se existe)
- Prescriber por CPF (lookup, adiciona councils faltantes)
- Patient por CPF (lookup, atualiza dados)
- Se SO já existe pro hubspot_deal_id, retorna existente sem recriar.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


SCRIPT_ISSUE_ORDER = r'''
# /api/method/future_production_issue_order
# Endpoint único: HubSpot/n8n envia payload completo, ERPNext upserta tudo.

data = frappe.form_dict
if not data:
    frappe.throw("Payload vazio.")

# Aceita body JSON inteiro (n8n passa string em data)
if isinstance(data, dict) and "customer" not in data and "data" in data:
    data = data.get("data") or {}

if isinstance(data, str):
    data = frappe.parse_json(data)

hub = data.get("hubspot") or {}
deal_id = hub.get("deal_id") or ""
contact_id = hub.get("contact_id") or ""

customer_in = data.get("customer") or {}
prescribers_in = data.get("prescribers") or []
patients_in = data.get("patients") or []
items_in = data.get("items") or []
fpps_in = data.get("fp_patients") or []
company = data.get("company") or "Injmedpharma"
delivery_date = data.get("delivery_date")
# --- Resolucao de lote (FPB) pra reserva. 4 formas, em ordem de precedencia: ---
#
# 1) item_fpb (PREFERIDO): alocacao QUANTIDADE POR LOTE.
#    [ { "item_code": "TIR00060",
#        "lotes": [ {"fpb_name": "FPB-A", "qty": 6}, {"fpb_name": "FPB-B", "qty": 4} ] } ]
#    Sistema distribui pacientes entre os lotes (bin-pack, receita inteira).
#    Cada paciente (receita) cabe inteiro em UM lote — nunca dividido.
#
# 2) fpb_map: { item_code: fpb_name } — 1 lote pra todo o item.
# 3) fpb_name: single, aplicado a TODOS items stock (retrocompat).
# 4) Nada: FIFO automatic.
explicit_fpb = (data.get("fpb_name") or data.get("future_production_batch") or "").strip()
fpb_map_in = data.get("fpb_map") or {}
if not isinstance(fpb_map_in, dict):
    fpb_map_in = {}

item_fpb_in = data.get("item_fpb") or []
if not isinstance(item_fpb_in, list):
    item_fpb_in = []
# Indexa: item_code -> [ {fpb_name, qty}, ... ]
item_alloc = {}
for entry in item_fpb_in:
    ic = (entry.get("item_code") or "").strip()
    if not ic:
        continue
    lotes = entry.get("lotes") or entry.get("allocations") or []
    cleaned = []
    for lt in lotes:
        fn = (lt.get("fpb_name") or lt.get("future_production_batch") or "").strip()
        q = float(lt.get("qty") or lt.get("quantity") or 0)
        if fn and q > 0:
            cleaned.append({"fpb_name": fn, "qty": q})
    if cleaned:
        item_alloc[ic] = cleaned

if not customer_in:
    frappe.throw("customer ausente.")
if not items_in:
    frappe.throw("items vazio.")
if not fpps_in:
    frappe.throw("fp_patients vazio.")

# Idempotência: se deal_id ja gerou SO, retorna ele.
if deal_id:
    existing_so = frappe.db.get_value(
        "Sales Order", {"hubspot_deal_id": deal_id, "docstatus": ["!=", 2]}, "name"
    )
    if existing_so:
        frappe.response["message"] = {
            "sales_order": existing_so,
            "created": {},
            "idempotent": True,
            "message": "SO ja existia pra hubspot_deal_id " + deal_id,
        }
    else:
        existing_so = None
else:
    existing_so = None

if not existing_so:
    # ----- 1) Customer (upsert por customer_name) -----
    cust_name_in = customer_in.get("customer_name") or customer_in.get("name")
    if not cust_name_in:
        frappe.throw("customer.customer_name ou customer.name obrigatorio.")
    cust_name = frappe.db.get_value("Customer", {"customer_name": cust_name_in}, "name")
    if cust_name:
        # Atualiza tax_id se vier
        if customer_in.get("tax_id"):
            frappe.db.set_value("Customer", cust_name, "tax_id",
                                str(customer_in["tax_id"]).replace(".", "").replace("/", "").replace("-", ""))
    else:
        new_c = frappe.new_doc("Customer")
        new_c.customer_name = cust_name_in
        new_c.customer_type = customer_in.get("customer_type") or "Company"
        new_c.customer_group = customer_in.get("customer_group") or "Comercial"
        new_c.territory = customer_in.get("territory") or "Brazil"
        if customer_in.get("tax_id"):
            new_c.tax_id = str(customer_in["tax_id"]).replace(".", "").replace("/", "").replace("-", "")
        new_c.insert(ignore_permissions=True)
        cust_name = new_c.name

    # ----- 1.5) Address linked to Customer (opcional) -----
    addr_in = customer_in.get("address") or {}
    if addr_in:
        addr_title = addr_in.get("title") or cust_name_in
        addr_type = addr_in.get("type") or "Billing"
        addr_key = addr_title + "-" + addr_type
        if not frappe.db.exists("Address", addr_key):
            new_addr = frappe.new_doc("Address")
            new_addr.address_title = addr_title
            new_addr.address_type = addr_type
            new_addr.address_line1 = addr_in.get("address_line1") or ""
            new_addr.address_line2 = addr_in.get("address_line2") or ""
            new_addr.city = addr_in.get("city") or ""
            new_addr.state = addr_in.get("state") or ""
            new_addr.pincode = addr_in.get("pincode") or ""
            new_addr.country = addr_in.get("country") or "Brazil"
            new_addr.email_id = addr_in.get("email_id") or ""
            new_addr.phone = addr_in.get("phone") or ""
            new_addr.is_primary_address = 1
            new_addr.is_shipping_address = 1
            new_addr.append("links", {"link_doctype": "Customer", "link_name": cust_name})
            new_addr.insert(ignore_permissions=True)

    # ----- 1.6) Contact linked to Customer (opcional) -----
    contact_in = customer_in.get("contact") or {}
    if contact_in:
        existing_ct = frappe.db.sql(
            "select c.name from `tabContact` c "
            "join `tabDynamic Link` dl on dl.parent = c.name "
            "where dl.link_doctype='Customer' and dl.link_name=%s limit 1",
            (cust_name,), as_dict=False,
        )
        if not existing_ct:
            new_ct = frappe.new_doc("Contact")
            new_ct.first_name = contact_in.get("first_name") or "Sem Nome"
            new_ct.last_name = contact_in.get("last_name") or ""
            if contact_in.get("email"):
                new_ct.append("email_ids", {"email_id": contact_in["email"], "is_primary": 1})
            if contact_in.get("phone"):
                new_ct.append("phone_nos", {
                    "phone": contact_in["phone"],
                    "is_primary_mobile_no": 1,
                    "is_primary_phone": 1,
                })
            new_ct.is_primary_contact = 1
            new_ct.append("links", {"link_doctype": "Customer", "link_name": cust_name})
            new_ct.insert(ignore_permissions=True)

    # ----- 2) Prescribers (upsert por CPF + merge councils) -----
    # Suporta lookup por CRM+UF quando CPF ausente (sistema validacao_receita
    # nao guarda CPF do medico, so CRM+UF). Cria CPF placeholder AUTO-<crm><uf>.
    pres_by_cpf = {}
    pres_by_council = {}  # (type, state, number) -> prescriber_name
    created_prescribers = []
    for p_in in prescribers_in:
        cpf = "".join(ch for ch in (p_in.get("cpf") or "") if ch.isdigit())
        # Lookup por council se sem CPF
        if not cpf and p_in.get("councils"):
            c0 = p_in["councils"][0]
            ct_type = c0.get("council_type") or ""
            ct_state = c0.get("council_state") or ""
            ct_num = str(c0.get("council_number") or "")
            existing_council = frappe.db.sql(
                "select parent from `tabPrescriber Council` "
                "where council_type=%s and council_state=%s and council_number=%s limit 1",
                (ct_type, ct_state, ct_num), as_dict=False,
            )
            if existing_council:
                cpf = frappe.db.get_value("Prescriber", existing_council[0][0], "cpf") or ""
            if not cpf:
                # gera CPF placeholder unico (11 digitos)
                base = ct_type + ct_num + ct_state
                base_digits = "".join(ch for ch in base if ch.isdigit()) or "0"
                cpf = ("9" + base_digits)[:11].ljust(11, "0")
        if not cpf:
            continue
        existing_pres = frappe.db.get_value("Prescriber", {"cpf": cpf}, "name")
        if existing_pres:
            pres_doc = frappe.get_doc("Prescriber", existing_pres)
            # Adiciona councils que ainda nao tem
            existing_keys = set()
            for ec in (pres_doc.councils or []):
                existing_keys.add(
                    (ec.council_type or "") + "|" +
                    (ec.council_state or "") + "|" + (ec.council_number or "")
                )
            need_save = False
            for inc in (p_in.get("councils") or []):
                key = (inc.get("council_type") or "") + "|" + (inc.get("council_state") or "") + "|" + str(inc.get("council_number") or "")
                if key not in existing_keys:
                    pres_doc.append("councils", {
                        "council_type": inc.get("council_type"),
                        "council_number": str(inc.get("council_number") or ""),
                        "council_state": inc.get("council_state"),
                        "council_status": inc.get("council_status") or "Ativo",
                        "specialty": inc.get("specialty") or "",
                        "is_primary": int(inc.get("is_primary") or 0),
                    })
                    need_save = True
            if need_save:
                pres_doc.save(ignore_permissions=True)
            pres_by_cpf[cpf] = pres_doc.name
        else:
            new_p = frappe.new_doc("Prescriber")
            new_p.full_name = p_in.get("full_name") or "Sem Nome"
            new_p.cpf = cpf
            for inc in (p_in.get("councils") or []):
                new_p.append("councils", {
                    "council_type": inc.get("council_type"),
                    "council_number": str(inc.get("council_number") or ""),
                    "council_state": inc.get("council_state"),
                    "council_status": inc.get("council_status") or "Ativo",
                    "specialty": inc.get("specialty") or "",
                    "is_primary": int(inc.get("is_primary") or 0),
                })
            if not (new_p.councils or []):
                frappe.throw("Prescriber CPF " + cpf + " sem councils.")
            new_p.insert(ignore_permissions=True)
            pres_by_cpf[cpf] = new_p.name
            created_prescribers.append(new_p.name)
        # Indexa por council pra lookup em fp_patients quando vier so CRM+UF
        for cc in (p_in.get("councils") or []):
            ck = (cc.get("council_type") or "", cc.get("council_state") or "",
                  str(cc.get("council_number") or ""))
            pres_by_council[ck] = pres_by_cpf[cpf]

    # ----- 3) Patients (upsert por CPF) -----
    pat_by_cpf = {}
    created_patients = []
    for pt_in in patients_in:
        cpf = "".join(ch for ch in (pt_in.get("cpf") or "") if ch.isdigit())
        if not cpf:
            continue
        existing_pat = frappe.db.get_value("Patient", {"cpf": cpf}, "name")
        default_pres = None
        if pt_in.get("default_prescriber_cpf"):
            dpcpf = "".join(ch for ch in pt_in["default_prescriber_cpf"] if ch.isdigit())
            default_pres = pres_by_cpf.get(dpcpf)
        if existing_pat:
            updates = {}
            if pt_in.get("patient_name"):
                updates["patient_name"] = pt_in["patient_name"]
            if pt_in.get("mobile"):
                updates["mobile"] = pt_in["mobile"]
            if pt_in.get("gender"):
                updates["gender"] = pt_in["gender"]
            if default_pres:
                updates["default_prescriber"] = default_pres
            if updates:
                frappe.db.set_value("Patient", existing_pat, updates)
            pat_by_cpf[cpf] = existing_pat
        else:
            new_pt = frappe.new_doc("Patient")
            new_pt.patient_name = pt_in.get("patient_name") or "Sem Nome"
            new_pt.cpf = cpf
            new_pt.gender = pt_in.get("gender") or "Outro"
            new_pt.mobile = pt_in.get("mobile") or ""
            new_pt.email = pt_in.get("email") or ""
            new_pt.country = pt_in.get("country") or "Brazil"
            if default_pres:
                new_pt.default_prescriber = default_pres
            new_pt.insert(ignore_permissions=True)
            pat_by_cpf[cpf] = new_pt.name
            created_patients.append(new_pt.name)

    # ----- 4) Sales Order -----
    so = frappe.new_doc("Sales Order")
    so.customer = cust_name
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

    for fp in fpps_in:
        pat_cpf = "".join(ch for ch in (fp.get("patient_cpf") or "") if ch.isdigit())
        pres_cpf = "".join(ch for ch in (fp.get("prescriber_cpf") or "") if ch.isdigit())
        patient_name = pat_by_cpf.get(pat_cpf)
        prescriber_name = pres_by_cpf.get(pres_cpf)
        # Fallback lookup por council quando prescriber_cpf vazio
        if not prescriber_name and fp.get("prescriber_council"):
            pc = fp["prescriber_council"]
            ck = (pc.get("council_type") or "", pc.get("council_state") or "",
                  str(pc.get("council_number") or ""))
            prescriber_name = pres_by_council.get(ck)
            if not prescriber_name:
                # Lookup global no DB
                row = frappe.db.sql(
                    "select parent from `tabPrescriber Council` "
                    "where council_type=%s and council_state=%s and council_number=%s limit 1",
                    ck, as_dict=False,
                )
                if row:
                    prescriber_name = row[0][0]

        # Acha council_row_id (se prescriber + council especificado)
        council_row_id = None
        pcs = fp.get("prescriber_council")
        if prescriber_name and pcs:
            council_row_id = frappe.db.sql(
                """
                select name from `tabPrescriber Council`
                where parent = %s and council_type = %s and council_state = %s
                  and council_number = %s
                limit 1
                """,
                (prescriber_name, pcs.get("council_type"), pcs.get("council_state"),
                 str(pcs.get("council_number") or "")),
                as_dict=False,
            )
            council_row_id = council_row_id[0][0] if council_row_id else None

        # FPB da linha fica VAZIO na criacao — o auto-reserve (bin-pack)
        # decide qual lote cada paciente recebe respeitando "receita inteira".
        # Excecao: se single-lote (fpb_map/explicit), seta como dica.
        item_c = fp.get("item_code") or ""
        line_fpb = (fp.get("fp_future_production_batch") or "").strip()
        if not line_fpb and item_c not in item_alloc:
            line_fpb = fpb_map_in.get(item_c, "") or explicit_fpb

        so.append("fp_patients", {
            "patient": patient_name,
            "item_code": fp.get("item_code"),
            "qty": float(fp.get("qty") or 0),
            "prescriber": prescriber_name,
            "prescriber_council_row": council_row_id or "",
            "fp_future_production_batch": line_fpb or None,
        })

    so.insert(ignore_permissions=True)
    so.submit()
    existing_so = so.name

# ----- 5) Payment inline (sem precisar webhook separado) -----
payment_in = data.get("payment") or {}
if payment_in:
    pstatus = (payment_in.get("status") or "").upper()
    pamount = float(payment_in.get("amount") or 0)
    so_grand = float(frappe.db.get_value("Sales Order", existing_so, "grand_total") or 0)
    if pstatus in ("PAID", "RECEIVED", "CONFIRMED") and abs(pamount - so_grand) <= 0.01:
        frappe.db.set_value("Sales Order", existing_so, {
            "payment_validated": 1,
            "payment_validated_at": payment_in.get("paid_at") or frappe.utils.now(),
            "payment_reference": payment_in.get("transaction_id") or "",
            "payment_amount": pamount,
        }, update_modified=False)

# ----- 6) Prescriptions inline -----
prescriptions_in = data.get("prescriptions") or {}
if prescriptions_in:
    frappe.db.set_value("Sales Order", existing_so, {
        "prescriptions_validated": 1,
        "prescriptions_validated_at": frappe.utils.now(),
        "prescriptions_qty_validated": int(prescriptions_in.get("count") or 0),
        "prescriptions_reference": prescriptions_in.get("reference") or "",
    }, update_modified=False)

# Recalcula validation_status: hubspot=True, payment/prescriptions ainda False.
refr = frappe.db.get_value(
    "Sales Order", existing_so,
    ["payment_validated", "prescriptions_validated", "hubspot_complete"],
    as_dict=True,
)
p_ok = int(refr.payment_validated or 0) == 1
r_ok = int(refr.prescriptions_validated or 0) == 1
h_ok = int(refr.hubspot_complete or 0) == 1
if p_ok and r_ok and h_ok:
    new_status = "Validado (Pronto para Reservar)"
elif p_ok and not r_ok:
    new_status = "Aguardando Receitas"
elif not p_ok and r_ok:
    new_status = "Aguardando Pagamento"
else:
    new_status = "Aguardando Multiplas Validacoes"
frappe.db.set_value("Sales Order", existing_so, {"validation_status": new_status},
                    update_modified=False)

# created_* vars só existem no fluxo de criação. Em modo idempotente, ficam vazias.
try:
    out_prescribers = created_prescribers
except NameError:
    out_prescribers = []
try:
    out_patients = created_patients
except NameError:
    out_patients = []
try:
    out_customer = cust_name
except NameError:
    out_customer = None

# ----- 7) Auto-reserve por ITEM com alocacao QTD-POR-LOTE + bin-pack pacientes -----
# Modelo: operador aloca X ampolas lote 1, Y ampolas lote 2, ... pra cada item.
# Sistema distribui os PACIENTES entre esses lotes. Regra dura: cada paciente
# (receita) cabe INTEIRO em UM unico lote — nunca dividido entre 2 lotes.
out_reservations = []
out_reserve_errors = []


def fpb_info(fpb_name):
    row = frappe.db.sql(
        "select name, (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) as available_qty, "
        "item_code, status, docstatus "
        "from `tabFuture Production Batch` where name=%s",
        (fpb_name,), as_dict=True,
    )
    return row[0] if row else None


if p_ok and r_ok and h_ok:
    so_doc = frappe.get_doc("Sales Order", existing_so)
    if so_doc.docstatus == 1:
        # Index SO items por item_code
        so_items_by_code = {}
        for it in so_doc.items:
            so_items_by_code.setdefault(it.item_code, []).append(it)

        # Agrupa fp_patients (pacientes) por item_code
        patients_by_item = {}
        for fpr in so_doc.fp_patients:
            patients_by_item.setdefault(fpr.item_code, []).append(fpr)

        for item_code, prows in patients_by_item.items():
            is_stock = frappe.db.get_value("Item", item_code, "is_stock_item")
            if not int(is_stock or 0):
                continue
            so_item_candidates = so_items_by_code.get(item_code, [])
            if not so_item_candidates:
                out_reserve_errors.append({
                    "item_code": item_code,
                    "message": "SO sem linha de item " + str(item_code),
                })
                continue
            so_item_name = so_item_candidates[0].name

            total_qty = sum(float(r.qty or 0) for r in prows)
            if total_qty <= 0:
                continue

            # Idempotency: ja reservado o total pra esse item? pula.
            already = frappe.db.sql(
                "select coalesce(sum(reserved_qty),0) from `tabProduction Reservation` "
                "where sales_order=%s and sales_order_item=%s and docstatus=1",
                (existing_so, so_item_name), as_dict=False,
            )
            already_qty = float((already[0][0] if already else 0) or 0)
            if already_qty >= total_qty:
                continue

            # ----- Monta alocacao de lotes pra esse item -----
            # Precedencia: item_alloc > fpb_map (single) > explicit_fpb > FIFO
            allocations = []  # [ {fpb_name, cap} ]  cap = capacidade efetiva
            if item_code in item_alloc:
                for lt in item_alloc[item_code]:
                    allocations.append({"fpb_name": lt["fpb_name"], "cap": lt["qty"]})
            else:
                single = (fpb_map_in.get(item_code) or "").strip() or explicit_fpb
                if single:
                    allocations.append({"fpb_name": single, "cap": total_qty})
                else:
                    # FIFO: enfileira FPBs abertos ate cobrir total_qty
                    fifo = frappe.db.sql(
                        "select name, (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) as avail "
                        "from `tabFuture Production Batch` "
                        "where item_code=%s and docstatus=1 "
                        "and status in ('Aberta para Reserva','Reservada Parcialmente') "
                        "and (coalesce(planned_qty,0)-coalesce(reserved_qty,0)) > 0 "
                        "order by planned_production_date asc, creation asc",
                        (item_code,), as_dict=True,
                    )
                    acc = 0
                    for f in fifo:
                        if acc >= total_qty:
                            break
                        allocations.append({"fpb_name": f.name, "cap": float(f.avail or 0)})
                        acc += float(f.avail or 0)

            if not allocations:
                out_reserve_errors.append({
                    "item_code": item_code,
                    "message": "Nenhum lote disponivel pra item " + str(item_code),
                })
                continue

            # ----- Valida cada FPB + limita capacidade ao saldo real -----
            valid_alloc = []
            alloc_invalid = False
            for a in allocations:
                info = fpb_info(a["fpb_name"])
                if not info:
                    out_reserve_errors.append({
                        "item_code": item_code,
                        "message": "FPB " + a["fpb_name"] + " nao existe.",
                    })
                    alloc_invalid = True
                    break
                if int(info.docstatus or 0) != 1:
                    out_reserve_errors.append({
                        "item_code": item_code,
                        "message": "FPB " + a["fpb_name"] + " nao submetida.",
                    })
                    alloc_invalid = True
                    break
                if info.item_code != item_code:
                    out_reserve_errors.append({
                        "item_code": item_code,
                        "message": "FPB " + a["fpb_name"] + " e do item " + str(info.item_code) +
                                   ", esperado " + str(item_code),
                    })
                    alloc_invalid = True
                    break
                if (info.status or "") not in ("Aberta para Reserva", "Reservada Parcialmente"):
                    out_reserve_errors.append({
                        "item_code": item_code,
                        "message": "FPB " + a["fpb_name"] + " status=" + str(info.status) +
                                   " nao aceita reservas.",
                    })
                    alloc_invalid = True
                    break
                # Capacidade efetiva = min(qty alocada, saldo real)
                eff = min(float(a["cap"]), float(info.available_qty or 0))
                valid_alloc.append({"fpb_name": a["fpb_name"], "cap": eff, "remaining": eff})
            if alloc_invalid:
                continue

            cap_total = sum(a["cap"] for a in valid_alloc)
            if cap_total < total_qty:
                out_reserve_errors.append({
                    "item_code": item_code,
                    "needed": total_qty,
                    "capacity": cap_total,
                    "message": "Capacidade dos lotes (" + str(cap_total) +
                               ") menor que total do item (" + str(total_qty) + ").",
                })
                continue

            # ----- Bin-pack: first-fit-decreasing. Receita (paciente) inteira. -----
            sorted_pats = sorted(prows, key=lambda r: float(r.qty or 0), reverse=True)
            assignments = []  # (fpr, fpb_name)
            packing_failed = False
            for fpr in sorted_pats:
                pq = float(fpr.qty or 0)
                if pq <= 0:
                    continue
                placed = False
                for a in valid_alloc:
                    if a["remaining"] >= pq:
                        a["remaining"] = a["remaining"] - pq
                        assignments.append((fpr, a["fpb_name"]))
                        placed = True
                        break
                if not placed:
                    out_reserve_errors.append({
                        "item_code": item_code,
                        "patient": fpr.patient,
                        "qty": pq,
                        "message": "Paciente " + str(fpr.patient) + " (qty " + str(pq) +
                                   ") nao cabe em nenhum lote restante. Ajuste as quantidades por lote.",
                    })
                    packing_failed = True
                    break
            if packing_failed:
                continue

            # ----- Cria 1 PR por lote (soma das qty dos pacientes daquele lote) -----
            qty_by_fpb = {}
            for fpr, fpb_name in assignments:
                qty_by_fpb[fpb_name] = qty_by_fpb.get(fpb_name, 0) + float(fpr.qty or 0)

            for fpb_name, qty in qty_by_fpb.items():
                pr = frappe.new_doc("Production Reservation")
                pr.sales_order = existing_so
                pr.sales_order_item = so_item_name
                pr.future_production_batch = fpb_name
                pr.item_code = item_code
                pr.reserved_qty = qty
                pr.insert(ignore_permissions=True)
                pr.submit()
                out_reservations.append({
                    "reservation": pr.name,
                    "sales_order_item": so_item_name,
                    "future_production_batch": fpb_name,
                    "item_code": item_code,
                    "reserved_qty": qty,
                })

            # ----- Marca cada paciente com seu lote (fp_future_production_batch) -----
            for fpr, fpb_name in assignments:
                frappe.db.set_value("Sales Order Patient", fpr.name,
                                    "fp_future_production_batch", fpb_name,
                                    update_modified=False)
        # final do loop por item — auto-reserve concluido

frappe.response["message"] = {
    "sales_order": existing_so,
    "created": {
        "customer": out_customer,
        "prescribers": out_prescribers,
        "patients": out_patients,
    },
    "validation_status": new_status,
    "hubspot_complete": True,
    "ready_to_reserve": (p_ok and r_ok and h_ok),
    "reservations": out_reservations,
    "reserve_errors": out_reserve_errors,
}
'''.strip()


def install() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1

    log_section("Server Script: future_production_issue_order")
    try:
        client.upsert_server_script({
            "name": "future_production_issue_order",
            "script_type": "API",
            "api_method": "future_production_issue_order",
            "allow_guest": 0,
            "enabled": 1,
            "script": SCRIPT_ISSUE_ORDER,
        })
        log_ok("Endpoint future_production_issue_order pronto.")
        return 0
    except Exception as exc:
        log_error(f"Falha: {exc}")
        return 1


def uninstall() -> int:
    client = client_from_env()
    try:
        client.delete_server_script("future_production_issue_order")
    except Exception as exc:
        log_error(f"{exc}")
    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
