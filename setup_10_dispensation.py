"""
setup_10_dispensation.py — instala módulo Dispensação + Etiqueta Zebra.

Cria:
  1. DocType Dispensation (submetível, com fetch de Patient/Prescriber/Batch)
  2. Custom Field Sales Order Patient.dispensation (espelho)
  3. Server Scripts (endpoints):
       future_production_create_dispensations_from_so(sales_order)
       future_production_generate_zpl_label(dispensation)
       future_production_mark_dispensation_printed(dispensation)
  4. Client Script no Dispensation com botão "Imprimir Etiqueta Zebra"
     usando Zebra BrowserPrint JS

Uso:
    python setup_10_dispensation.py
    python setup_10_dispensation.py --uninstall
"""

from __future__ import annotations

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section
from lib.payloads_dispensation import DISPENSATION, DISPENSATION_SOP_FIELDS


# ---------------------------------------------------------------------------
# Server Script: criar dispensações a partir de um Sales Order
# ---------------------------------------------------------------------------

SCRIPT_API_CREATE_DISP = r'''
# /api/method/future_production_create_dispensations_from_so
# Cria 1 Dispensation (Rascunho) para cada linha fp_patients alocada
# (batch_no preenchido). Idempotente: pula linhas que ja tem dispensation.

data = frappe.form_dict
so_name = data.get("sales_order")
if not so_name:
    frappe.throw("sales_order e obrigatorio.")

so = frappe.get_doc("Sales Order", so_name)
if so.docstatus != 1:
    frappe.throw("Sales Order precisa estar submetido.")

created = []
skipped = 0

for row in (so.get("fp_patients") or []):
    if not row.batch_no:
        continue  # sem batch ainda, pula
    if row.get("dispensation"):
        skipped = skipped + 1
        continue  # ja tem dispensation

    new_disp = frappe.new_doc("Dispensation")
    new_disp.sales_order = so.name
    new_disp.sales_order_patient_row = row.name
    new_disp.patient = row.patient
    new_disp.prescriber = row.prescriber
    new_disp.item_code = row.item_code
    new_disp.qty = row.qty
    new_disp.batch_no = row.batch_no
    new_disp.status = "Pendente"
    new_disp.insert(ignore_permissions=True)

    # Espelha no SO Patient row
    frappe.db.set_value("Sales Order Patient", row.name, {
        "dispensation": new_disp.name,
    }, update_modified=False)

    created.append({
        "name": new_disp.name,
        "patient": row.patient,
        "patient_name": row.patient_name,
        "qty": float(row.qty or 0),
        "batch_no": row.batch_no,
    })

frappe.response["message"] = {
    "sales_order": so_name,
    "created_count": len(created),
    "skipped_count": skipped,
    "dispensations": created,
}
'''.strip()


# ---------------------------------------------------------------------------
# Server Script: gerar ZPL
# ---------------------------------------------------------------------------

SCRIPT_API_GENERATE_ZPL = r'''
# /api/method/future_production_generate_zpl_label
# Retorna ZPL pronto para enviar ao Zebra BrowserPrint.

data = frappe.form_dict
disp_name = data.get("dispensation")
if not disp_name:
    frappe.throw("dispensation e obrigatorio.")

disp = frappe.get_doc("Dispensation", disp_name)

# Helper: trunca texto para ZPL (impede campos enormes quebrarem layout)
def trunc(s, n):
    if not s:
        return ""
    s = str(s)
    if len(s) <= n:
        return s
    return s[:n-1] + "."

# Dados
patient_name = trunc(disp.patient_name or "", 30)
cpf_raw = (disp.cpf or "")
# Formata CPF visual
cpf_digits = "".join(c for c in cpf_raw if c.isdigit())
if len(cpf_digits) == 11:
    cpf_fmt = cpf_digits[:3] + "." + cpf_digits[3:6] + "." + cpf_digits[6:9] + "-" + cpf_digits[9:]
else:
    cpf_fmt = cpf_raw

item_name = trunc(disp.item_name or disp.item_code or "", 28)
batch = trunc(disp.batch_no or "", 24)

# Datas no formato BR
def fmt_date(d):
    if not d:
        return ""
    s = str(d)
    if len(s) >= 10 and s[4] == "-":
        return s[8:10] + "/" + s[5:7] + "/" + s[:4]
    return s

val = fmt_date(disp.batch_expiry)
fab = fmt_date(disp.batch_manufacturing)
qty = int(float(disp.qty or 0)) if float(disp.qty or 0) == int(float(disp.qty or 0)) else float(disp.qty or 0)

# Barcode data: SO|paciente|batch
barcode = (disp.sales_order or "") + "|" + (disp.patient or "") + "|" + (disp.batch_no or "")

# Template (ZPL string puro)
if (disp.label_template or "50x30mm") == "100x50mm":
    # 100mm x 50mm @ 203dpi = 800 x 400 dots
    zpl = (
        "^XA" +
        "^CI28" +  # UTF-8
        "^PW800^LL400" +
        "^FO30,20^A0N,36,36^FD" + patient_name + "^FS" +
        "^FO30,65^A0N,28,28^FDCPF: " + cpf_fmt + "^FS" +
        "^FO30,105^A0N,32,32^FD" + item_name + "^FS" +
        "^FO30,150^A0N,26,26^FDLote: " + batch + "^FS" +
        "^FO30,185^A0N,26,26^FDValidade: " + val + "^FS" +
        "^FO30,220^A0N,26,26^FDFabricacao: " + fab + "^FS" +
        "^FO30,255^A0N,28,28^FDQtd: " + str(qty) + " ampolas^FS" +
        "^FO30,300^BCN,60,Y,N,N^FD" + barcode + "^FS" +
        "^FO500,20^A0N,18,18^FD" + (disp.sales_order or "") + "^FS" +
        "^FO500,42^A0N,18,18^FD" + (disp.name or "") + "^FS" +
        "^XZ"
    )
else:
    # 50mm x 30mm @ 203dpi = 400 x 240 dots
    zpl = (
        "^XA" +
        "^CI28" +
        "^PW400^LL240" +
        "^FO15,10^A0N,24,24^FD" + patient_name + "^FS" +
        "^FO15,40^A0N,18,18^FDCPF: " + cpf_fmt + "^FS" +
        "^FO15,65^A0N,20,20^FD" + item_name + "^FS" +
        "^FO15,90^A0N,18,18^FDLote: " + batch + "^FS" +
        "^FO15,113^A0N,18,18^FDVal: " + val + " Qty: " + str(qty) + "^FS" +
        "^FO15,140^BCN,55,Y,N,N^FD" + barcode + "^FS" +
        "^XZ"
    )

# Salva preview no doc (allow_on_submit)
frappe.db.set_value("Dispensation", disp.name, {
    "zpl_preview": zpl,
}, update_modified=False)

frappe.response["message"] = {
    "dispensation": disp.name,
    "label_template": disp.label_template,
    "zpl": zpl,
    "patient_name": patient_name,
    "cpf": cpf_fmt,
    "batch_no": disp.batch_no,
    "qty": qty,
    "expiry": val,
}
'''.strip()


# ---------------------------------------------------------------------------
# Server Script: marcar como impresso
# ---------------------------------------------------------------------------

SCRIPT_API_MARK_PRINTED = r'''
# /api/method/future_production_mark_dispensation_printed
# Marca printed=1 + printed_at=now. Opcional: muda status pra Dispensado.

data = frappe.form_dict
disp_name = data.get("dispensation")
mark_dispensed = int(data.get("mark_dispensed") or 0)
if not disp_name:
    frappe.throw("dispensation e obrigatorio.")

updates = {
    "printed": 1,
    "printed_at": frappe.utils.now(),
}
if mark_dispensed:
    updates["status"] = "Dispensado"
    # Atualiza espelho do batch_status no SO Patient
    disp = frappe.db.get_value("Dispensation", disp_name,
                                ["sales_order_patient_row"], as_dict=True)
    if disp and disp.sales_order_patient_row:
        frappe.db.set_value("Sales Order Patient", disp.sales_order_patient_row, {
            "batch_status": "Entregue",
        }, update_modified=False)

frappe.db.set_value("Dispensation", disp_name, updates, update_modified=False)

frappe.response["message"] = {
    "dispensation": disp_name,
    "printed": 1,
    "status_changed_to": updates.get("status"),
}
'''.strip()


# ---------------------------------------------------------------------------
# Client Script — botão "Imprimir Etiqueta Zebra" no Dispensation
# ---------------------------------------------------------------------------

CLIENT_SCRIPT_DISPENSATION = r'''
// Client Script — Dispensation Form
// Botão: Imprimir Etiqueta Zebra (chama endpoint + envia via BrowserPrint)

frappe.ui.form.on('Dispensation', {
  refresh(frm) {
    if (frm.doc.docstatus === 0 || frm.doc.docstatus === 1) {
      frm.add_custom_button('Imprimir Etiqueta Zebra', () => print_zebra_label(frm));
    }
  }
});

function print_zebra_label(frm) {
  frappe.call({
    method: 'future_production_generate_zpl_label',
    args: { dispensation: frm.doc.name },
    freeze: true,
    freeze_message: 'Gerando etiqueta...',
    callback: (r) => {
      const msg = r && r.message;
      if (!msg || !msg.zpl) {
        frappe.msgprint({ title: 'Erro', message: 'ZPL nao foi gerado', indicator: 'red' });
        return;
      }
      send_to_zebra(frm, msg.zpl);
    }
  });
}

function send_to_zebra(frm, zpl) {
  // Tenta usar Zebra BrowserPrint (precisa estar instalado no PC do operador)
  if (typeof BrowserPrint === 'undefined') {
    // Sem BrowserPrint: oferece copiar ZPL pra colar em outro app
    show_zpl_dialog(zpl, frm);
    return;
  }
  BrowserPrint.getDefaultDevice('printer', (device) => {
    if (!device) {
      frappe.msgprint({
        title: 'Impressora nao encontrada',
        message: 'Conecte a Zebra e abra o app BrowserPrint local.',
        indicator: 'orange',
      });
      show_zpl_dialog(zpl, frm);
      return;
    }
    device.send(zpl, () => {
      mark_printed(frm, true);
    }, (err) => {
      frappe.msgprint({ title: 'Falha na impressao', message: err, indicator: 'red' });
    });
  }, (err) => {
    frappe.msgprint({
      title: 'BrowserPrint nao respondeu',
      message: String(err),
      indicator: 'orange',
    });
    show_zpl_dialog(zpl, frm);
  });
}

function show_zpl_dialog(zpl, frm) {
  // Fallback: mostra ZPL pra operador copiar e colar em outra ferramenta
  const d = new frappe.ui.Dialog({
    title: 'ZPL Gerado',
    size: 'large',
    fields: [
      { fieldtype: 'HTML', options: '<p>Zebra BrowserPrint nao detectado. Copie o ZPL abaixo e cole no labelary.com ou no app Zebra Setup Utilities.</p>' },
      { fieldname: 'zpl', fieldtype: 'Code', label: 'ZPL', options: 'Text', default: zpl, read_only: 1 },
    ],
    primary_action_label: 'Marcar como Impressa (manual)',
    primary_action: () => { mark_printed(frm, false); d.hide(); }
  });
  d.show();
}

function mark_printed(frm, mark_dispensed) {
  frappe.call({
    method: 'future_production_mark_dispensation_printed',
    args: { dispensation: frm.doc.name, mark_dispensed: mark_dispensed ? 1 : 0 },
    callback: () => {
      frappe.show_alert({ message: 'Etiqueta marcada como impressa.', indicator: 'green' });
      frm.reload_doc();
    }
  });
}
'''.strip()


# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------

def install() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1

    errors = 0

    log_section("1/4 — DocType Dispensation")
    try:
        client.create_doctype(DISPENSATION)
    except Exception as exc:
        log_error(f"Dispensation: {exc}")
        return 1

    log_section("2/4 — Custom Field Sales Order Patient.dispensation")
    for field in DISPENSATION_SOP_FIELDS:
        try:
            client.create_custom_field(field)
        except Exception as exc:
            log_error(f"{field['dt']}.{field['fieldname']}: {exc}")
            errors += 1

    log_section("3/4 — Server Scripts (endpoints API)")
    scripts = [
        ("future_production_create_dispensations_from_so", SCRIPT_API_CREATE_DISP),
        ("future_production_generate_zpl_label", SCRIPT_API_GENERATE_ZPL),
        ("future_production_mark_dispensation_printed", SCRIPT_API_MARK_PRINTED),
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
            log_error(f"Server Script {name}: {exc}")
            errors += 1

    log_section("4/4 — Client Script Dispensation (botão Zebra)")
    try:
        client.upsert_client_script(
            name="Dispensation - Print Zebra Label",
            dt="Dispensation",
            script=CLIENT_SCRIPT_DISPENSATION,
        )
    except Exception as exc:
        log_error(f"Client Script Dispensation: {exc}")
        errors += 1

    if errors == 0:
        log_ok("Módulo Dispensação instalado.")
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()

    log_section("Removendo Client Script")
    try:
        client.delete_client_script("Dispensation - Print Zebra Label")
    except Exception as exc:
        log_error(f"Client Script: {exc}")

    log_section("Removendo Server Scripts")
    for name in (
        "future_production_create_dispensations_from_so",
        "future_production_generate_zpl_label",
        "future_production_mark_dispensation_printed",
    ):
        try:
            client.delete_server_script(name)
        except Exception as exc:
            log_error(f"{name}: {exc}")

    log_section("Removendo Custom Fields")
    for field in reversed(DISPENSATION_SOP_FIELDS):
        try:
            client.delete_custom_field(field["dt"], field["fieldname"])
        except Exception as exc:
            log_error(f"{field['dt']}.{field['fieldname']}: {exc}")

    log_section("Removendo DocType Dispensation")
    try:
        client.delete_doctype("Dispensation")
    except Exception as exc:
        log_error(f"Dispensation: {exc}")

    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
