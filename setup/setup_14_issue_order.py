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

    # ----- 2) Prescribers (upsert por CPF + merge councils) -----
    pres_by_cpf = {}
    created_prescribers = []
    for p_in in prescribers_in:
        cpf = "".join(ch for ch in (p_in.get("cpf") or "") if ch.isdigit())
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

        so.append("fp_patients", {
            "patient": patient_name,
            "item_code": fp.get("item_code"),
            "qty": float(fp.get("qty") or 0),
            "prescriber": prescriber_name,
            "prescriber_council_row": council_row_id or "",
        })

    so.insert(ignore_permissions=True)
    so.submit()
    existing_so = so.name

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
