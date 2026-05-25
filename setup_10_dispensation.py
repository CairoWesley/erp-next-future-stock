"""
setup_10_dispensation.py — Dispensação + Etiquetas Zebra (v2).

Modelo: 1 Sales Order → 1 Dispensation (a entrega completa).
Dispensation tem child table `Dispensation Patient` (1 linha por paciente).
Cada linha = 1 etiqueta Zebra individual.

Cria:
  1. DocType Dispensation Patient (child)
  2. DocType Dispensation (submetível, com child + fetch fields)
  3. Custom Field Sales Order.dispensation (espelho 1:1)
  4. Server Scripts:
       future_production_create_dispensation_from_so(sales_order)
       future_production_generate_zpl_label(dispensation, row=opcional)
       future_production_generate_all_zpl_labels(dispensation)
       future_production_mark_label_printed(dispensation, row_name)
       future_production_mark_dispensation_completed(dispensation)
  5. Client Script no Dispensation com 2 botões:
       "Imprimir Todas as Etiquetas Zebra"
       "Imprimir Etiqueta da Linha" (por linha)

Uso:
    python setup_10_dispensation.py
    python setup_10_dispensation.py --uninstall
"""

from __future__ import annotations

import sys

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section
from lib.payloads_dispensation import (
    DISPENSATION,
    DISPENSATION_PATIENT,
    DISPENSATION_SO_FIELDS,
)


# ---------------------------------------------------------------------------
# Server Script: criar Dispensation a partir de um SO
# ---------------------------------------------------------------------------

SCRIPT_API_CREATE_DISP = r'''
# /api/method/future_production_create_dispensation_from_so
# Cria UMA Dispensation (com N rows de pacientes) para um SO.
# Idempotente: se SO ja tem dispensation, retorna a existente.

data = frappe.form_dict
so_name = data.get("sales_order")
if not so_name:
    frappe.throw("sales_order e obrigatorio.")

so = frappe.get_doc("Sales Order", so_name)
if so.docstatus != 1:
    frappe.throw("Sales Order precisa estar submetido.")

# Verifica se ja tem dispensation
existing = frappe.db.get_value("Dispensation", {"sales_order": so_name}, "name")
if existing:
    frappe.response["message"] = {
        "sales_order": so_name,
        "dispensation": existing,
        "created": False,
        "message": "Dispensation ja existia.",
    }
else:
    # Constroi rows do child table a partir de fp_patients alocados
    rows = []
    total_qty = 0.0
    for p in (so.get("fp_patients") or []):
        if not p.batch_no:
            continue  # sem batch nao pode dispensar
        rows.append({
            "patient": p.patient,
            "prescriber": p.prescriber,
            "item_code": p.item_code,
            "qty": p.qty,
            "batch_no": p.batch_no,
            "sales_order_patient_row": p.name,
            "printed": 0,
        })
        total_qty = total_qty + float(p.qty or 0)

    if not rows:
        frappe.throw(
            "SO " + so_name + " nao tem nenhuma linha fp_patients com batch_no preenchido. "
            "Rode future_production_allocate_patient_batches antes."
        )

    new_disp = frappe.new_doc("Dispensation")
    new_disp.sales_order = so_name
    new_disp.status = "Pendente"
    new_disp.total_qty = total_qty
    new_disp.total_patients = len(rows)
    new_disp.printed_count = "0/" + str(len(rows))
    for r in rows:
        new_disp.append("patients", r)
    new_disp.insert(ignore_permissions=True)

    frappe.db.set_value("Sales Order", so_name, {
        "dispensation": new_disp.name,
    }, update_modified=False)

    frappe.response["message"] = {
        "sales_order": so_name,
        "dispensation": new_disp.name,
        "created": True,
        "rows_count": len(rows),
        "total_qty": total_qty,
    }
'''.strip()


# ---------------------------------------------------------------------------
# Server Script: gerar ZPL de UMA linha (ou retorna todas se row vazio)
# ---------------------------------------------------------------------------

SCRIPT_API_GENERATE_ZPL = r'''
# /api/method/future_production_generate_zpl_label
# Gera ZPL para 1 linha (row_name) ou pra primeira se nao informado.

data = frappe.form_dict
disp_name = data.get("dispensation")
row_name = data.get("row_name")
if not disp_name:
    frappe.throw("dispensation e obrigatorio.")

disp = frappe.get_doc("Dispensation", disp_name)
rows = disp.get("patients") or []
if not rows:
    frappe.throw("Dispensation sem pacientes.")

target = None
if row_name:
    for r in rows:
        if r.name == row_name:
            target = r
            break
    if not target:
        frappe.throw("Linha " + str(row_name) + " nao encontrada.")
else:
    target = rows[0]

def trunc(s, n):
    if not s:
        return ""
    s = str(s)
    if len(s) <= n:
        return s
    return s[:n-1] + "."

def fmt_date(d):
    if not d:
        return ""
    s = str(d)
    if len(s) >= 10 and s[4] == "-":
        return s[8:10] + "/" + s[5:7] + "/" + s[:4]
    return s

patient_name = trunc(target.patient_name or "", 30)
cpf_digits = "".join(c for c in (target.cpf or "") if c.isdigit())
if len(cpf_digits) == 11:
    cpf_fmt = cpf_digits[:3] + "." + cpf_digits[3:6] + "." + cpf_digits[6:9] + "-" + cpf_digits[9:]
else:
    cpf_fmt = target.cpf or ""

item_name = trunc(target.item_name or target.item_code or "", 28)
batch = trunc(target.batch_no or "", 24)
val = fmt_date(target.batch_expiry)
fab = fmt_date(target.batch_manufacturing)
qty_f = float(target.qty or 0)
qty = int(qty_f) if qty_f == int(qty_f) else qty_f
barcode = (disp.sales_order or "") + "|" + (target.patient or "") + "|" + (target.batch_no or "")

if (disp.label_template or "50x30mm") == "100x50mm":
    zpl = (
        "^XA" + "^CI28" + "^PW800^LL400" +
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
    zpl = (
        "^XA" + "^CI28" + "^PW400^LL240" +
        "^FO15,10^A0N,24,24^FD" + patient_name + "^FS" +
        "^FO15,40^A0N,18,18^FDCPF: " + cpf_fmt + "^FS" +
        "^FO15,65^A0N,20,20^FD" + item_name + "^FS" +
        "^FO15,90^A0N,18,18^FDLote: " + batch + "^FS" +
        "^FO15,113^A0N,18,18^FDVal: " + val + " Qty: " + str(qty) + "^FS" +
        "^FO15,140^BCN,55,Y,N,N^FD" + barcode + "^FS" +
        "^XZ"
    )

frappe.response["message"] = {
    "dispensation": disp.name,
    "row_name": target.name,
    "patient": target.patient,
    "patient_name": patient_name,
    "cpf": cpf_fmt,
    "batch_no": target.batch_no,
    "qty": qty,
    "expiry": val,
    "zpl": zpl,
}
'''.strip()


# ---------------------------------------------------------------------------
# Server Script: gerar ZPL de TODAS as linhas (concatenado)
# ---------------------------------------------------------------------------

SCRIPT_API_GENERATE_ALL_ZPL = r'''
# /api/method/future_production_generate_all_zpl_labels
# Gera ZPL concatenado de todas as linhas. Zebra imprime N etiquetas seguidas.

data = frappe.form_dict
disp_name = data.get("dispensation")
if not disp_name:
    frappe.throw("dispensation e obrigatorio.")

disp = frappe.get_doc("Dispensation", disp_name)
rows = disp.get("patients") or []
if not rows:
    frappe.throw("Dispensation sem pacientes.")

def trunc(s, n):
    if not s:
        return ""
    s = str(s)
    if len(s) <= n:
        return s
    return s[:n-1] + "."

def fmt_date(d):
    if not d:
        return ""
    s = str(d)
    if len(s) >= 10 and s[4] == "-":
        return s[8:10] + "/" + s[5:7] + "/" + s[:4]
    return s

template = disp.label_template or "50x30mm"
all_zpl_parts = []
labels_info = []

for row in rows:
    patient_name = trunc(row.patient_name or "", 30)
    cpf_digits = "".join(c for c in (row.cpf or "") if c.isdigit())
    if len(cpf_digits) == 11:
        cpf_fmt = cpf_digits[:3] + "." + cpf_digits[3:6] + "." + cpf_digits[6:9] + "-" + cpf_digits[9:]
    else:
        cpf_fmt = row.cpf or ""

    item_name = trunc(row.item_name or row.item_code or "", 28)
    batch = trunc(row.batch_no or "", 24)
    val = fmt_date(row.batch_expiry)
    fab = fmt_date(row.batch_manufacturing)
    qty_f = float(row.qty or 0)
    qty = int(qty_f) if qty_f == int(qty_f) else qty_f
    barcode = (disp.sales_order or "") + "|" + (row.patient or "") + "|" + (row.batch_no or "")

    if template == "100x50mm":
        zpl = (
            "^XA" + "^CI28" + "^PW800^LL400" +
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
        zpl = (
            "^XA" + "^CI28" + "^PW400^LL240" +
            "^FO15,10^A0N,24,24^FD" + patient_name + "^FS" +
            "^FO15,40^A0N,18,18^FDCPF: " + cpf_fmt + "^FS" +
            "^FO15,65^A0N,20,20^FD" + item_name + "^FS" +
            "^FO15,90^A0N,18,18^FDLote: " + batch + "^FS" +
            "^FO15,113^A0N,18,18^FDVal: " + val + " Qty: " + str(qty) + "^FS" +
            "^FO15,140^BCN,55,Y,N,N^FD" + barcode + "^FS" +
            "^XZ"
        )

    all_zpl_parts.append(zpl)
    labels_info.append({
        "row_name": row.name,
        "patient_name": patient_name,
        "cpf": cpf_fmt,
        "batch_no": row.batch_no,
        "qty": qty,
    })

all_zpl = "\n".join(all_zpl_parts)

frappe.response["message"] = {
    "dispensation": disp.name,
    "label_template": template,
    "labels_count": len(labels_info),
    "zpl": all_zpl,
    "labels": labels_info,
}
'''.strip()


# ---------------------------------------------------------------------------
# Server Script: marcar UMA linha como impressa
# ---------------------------------------------------------------------------

SCRIPT_API_MARK_ROW_PRINTED = r'''
# /api/method/future_production_mark_label_printed
# Marca 1 linha printed=1. Atualiza contador no parent.

data = frappe.form_dict
disp_name = data.get("dispensation")
row_name = data.get("row_name")
if not disp_name or not row_name:
    frappe.throw("dispensation + row_name sao obrigatorios.")

frappe.db.set_value("Dispensation Patient", row_name, {
    "printed": 1,
    "printed_at": frappe.utils.now(),
}, update_modified=False)

# Conta quantas linhas impressas / total
total = frappe.db.count("Dispensation Patient", {"parent": disp_name})
printed = frappe.db.count("Dispensation Patient", {
    "parent": disp_name, "printed": 1,
})
all_printed = 1 if printed >= total and total > 0 else 0

frappe.db.set_value("Dispensation", disp_name, {
    "printed_count": str(printed) + "/" + str(total),
    "all_printed": all_printed,
}, update_modified=False)

frappe.response["message"] = {
    "dispensation": disp_name,
    "row_name": row_name,
    "printed": str(printed) + "/" + str(total),
    "all_printed": all_printed,
}
'''.strip()


# ---------------------------------------------------------------------------
# Server Script: marcar Dispensation como concluida
# ---------------------------------------------------------------------------

SCRIPT_API_MARK_COMPLETED = r'''
# /api/method/future_production_mark_dispensation_completed
# Muda status para Dispensado e atualiza espelhos em Sales Order Patient.

data = frappe.form_dict
disp_name = data.get("dispensation")
if not disp_name:
    frappe.throw("dispensation e obrigatorio.")

disp = frappe.get_doc("Dispensation", disp_name)

frappe.db.set_value("Dispensation", disp_name, {
    "status": "Dispensado",
}, update_modified=False)

# Atualiza espelho em cada Sales Order Patient
for row in (disp.get("patients") or []):
    if row.sales_order_patient_row:
        frappe.db.set_value("Sales Order Patient", row.sales_order_patient_row, {
            "batch_status": "Entregue",
        }, update_modified=False)

frappe.response["message"] = {
    "dispensation": disp_name,
    "status": "Dispensado",
    "patients_updated": len(disp.get("patients") or []),
}
'''.strip()


# ---------------------------------------------------------------------------
# Client Script
# ---------------------------------------------------------------------------

CLIENT_SCRIPT_DISPENSATION = r'''
// Client Script — Dispensation
// 2 botoes: "Imprimir Todas Etiquetas" e "Imprimir Esta Linha" no child grid

frappe.ui.form.on('Dispensation', {
  refresh(frm) {
    if (frm.doc.docstatus === 2) return;
    frm.add_custom_button('Imprimir Todas as Etiquetas Zebra',
      () => print_all_labels(frm),
      'Zebra'
    );
    frm.add_custom_button('Marcar como Dispensado (todos pacientes)',
      () => mark_completed(frm),
      'Zebra'
    );
  }
});

frappe.ui.form.on('Dispensation Patient', {
  patients_add(frm, cdt, cdn) { /* nada por enquanto */ },
});

// Botao por linha (gambiarra via menu de linha — usa "Imprimir Esta Linha")
frappe.ui.form.on('Dispensation', {
  setup(frm) {
    frm.fields_dict.patients.grid.add_custom_button('Imprimir Esta Linha',
      function() {
        const selected = frm.fields_dict.patients.grid.get_selected_children();
        if (!selected.length) {
          frappe.msgprint('Selecione 1 linha primeiro.');
          return;
        }
        print_one_label(frm, selected[0].name);
      }
    );
  }
});

function print_all_labels(frm) {
  frappe.call({
    method: 'future_production_generate_all_zpl_labels',
    args: { dispensation: frm.doc.name },
    freeze: true,
    freeze_message: 'Gerando ' + (frm.doc.patients || []).length + ' etiquetas...',
    callback: (r) => {
      const msg = r && r.message;
      if (!msg || !msg.zpl) {
        frappe.msgprint({ title: 'Erro', message: 'ZPL nao gerado.', indicator: 'red' });
        return;
      }
      send_to_zebra(frm, msg.zpl, msg.labels, /*mark_all*/true);
    }
  });
}

function print_one_label(frm, row_name) {
  frappe.call({
    method: 'future_production_generate_zpl_label',
    args: { dispensation: frm.doc.name, row_name: row_name },
    freeze: true,
    callback: (r) => {
      const msg = r && r.message;
      if (!msg || !msg.zpl) {
        frappe.msgprint({ title: 'Erro', message: 'ZPL nao gerado.', indicator: 'red' });
        return;
      }
      send_to_zebra(frm, msg.zpl, [{ row_name: msg.row_name }], /*mark_all*/false);
    }
  });
}

function send_to_zebra(frm, zpl, labels, mark_all) {
  if (typeof BrowserPrint === 'undefined') {
    show_zpl_dialog(frm, zpl, labels, mark_all);
    return;
  }
  BrowserPrint.getDefaultDevice('printer', (device) => {
    if (!device) {
      frappe.msgprint({
        title: 'Impressora nao encontrada',
        message: 'Conecte a Zebra e abra o BrowserPrint.',
        indicator: 'orange',
      });
      show_zpl_dialog(frm, zpl, labels, mark_all);
      return;
    }
    device.send(zpl, () => {
      mark_printed_rows(frm, labels);
    }, (err) => {
      frappe.msgprint({ title: 'Falha na impressao', message: String(err), indicator: 'red' });
    });
  }, (err) => {
    show_zpl_dialog(frm, zpl, labels, mark_all);
  });
}

function show_zpl_dialog(frm, zpl, labels, mark_all) {
  const d = new frappe.ui.Dialog({
    title: 'ZPL Gerado',
    size: 'large',
    fields: [
      { fieldtype: 'HTML', options: '<p>Zebra BrowserPrint nao detectado. Copie o ZPL e cole em labelary.com (preview) ou Zebra Setup Utilities.</p>' },
      { fieldname: 'zpl', fieldtype: 'Code', label: 'ZPL', options: 'Text', default: zpl, read_only: 1 },
    ],
    primary_action_label: 'Marcar como Impresso',
    primary_action: () => { mark_printed_rows(frm, labels); d.hide(); }
  });
  d.show();
}

function mark_printed_rows(frm, labels) {
  if (!labels || !labels.length) {
    frm.reload_doc();
    return;
  }
  let done = 0;
  labels.forEach((lbl) => {
    frappe.call({
      method: 'future_production_mark_label_printed',
      args: { dispensation: frm.doc.name, row_name: lbl.row_name },
      callback: () => {
        done = done + 1;
        if (done === labels.length) {
          frappe.show_alert({ message: done + ' etiqueta(s) marcadas como impressa(s).', indicator: 'green' });
          frm.reload_doc();
        }
      }
    });
  });
}

function mark_completed(frm) {
  frappe.confirm('Marcar Dispensação como concluída e atualizar espelhos no Sales Order?',
    () => {
      frappe.call({
        method: 'future_production_mark_dispensation_completed',
        args: { dispensation: frm.doc.name },
        callback: () => {
          frappe.show_alert({ message: 'Dispensação marcada como Dispensado.', indicator: 'green' });
          frm.reload_doc();
        }
      });
    }
  );
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

    log_section("1/5 — DocType Dispensation Patient (child)")
    try:
        client.create_doctype(DISPENSATION_PATIENT)
    except Exception as exc:
        log_error(f"Dispensation Patient: {exc}")
        return 1

    log_section("2/5 — DocType Dispensation (parent)")
    try:
        client.create_doctype(DISPENSATION)
    except Exception as exc:
        log_error(f"Dispensation: {exc}")
        return 1

    log_section("3/5 — Custom Field Sales Order.dispensation")
    for field in DISPENSATION_SO_FIELDS:
        try:
            client.create_custom_field(field)
        except Exception as exc:
            log_error(f"{field['dt']}.{field['fieldname']}: {exc}")
            errors += 1

    log_section("4/5 — Server Scripts (5 endpoints)")
    scripts = [
        ("future_production_create_dispensation_from_so", SCRIPT_API_CREATE_DISP),
        ("future_production_generate_zpl_label", SCRIPT_API_GENERATE_ZPL),
        ("future_production_generate_all_zpl_labels", SCRIPT_API_GENERATE_ALL_ZPL),
        ("future_production_mark_label_printed", SCRIPT_API_MARK_ROW_PRINTED),
        ("future_production_mark_dispensation_completed", SCRIPT_API_MARK_COMPLETED),
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

    log_section("5/5 — Client Script Dispensation (botões Zebra)")
    try:
        client.upsert_client_script(
            name="Dispensation - Print Zebra Labels",
            dt="Dispensation",
            script=CLIENT_SCRIPT_DISPENSATION,
        )
    except Exception as exc:
        log_error(f"Client Script Dispensation: {exc}")
        errors += 1

    if errors == 0:
        log_ok("Módulo Dispensação (v2) instalado.")
    return 0 if errors == 0 else 1


def uninstall() -> int:
    client = client_from_env()

    log_section("Removendo Client Script")
    try:
        client.delete_client_script("Dispensation - Print Zebra Labels")
    except Exception as exc:
        log_error(f"Client Script: {exc}")

    log_section("Removendo Server Scripts")
    for name in (
        "future_production_create_dispensation_from_so",
        "future_production_generate_zpl_label",
        "future_production_generate_all_zpl_labels",
        "future_production_mark_label_printed",
        "future_production_mark_dispensation_completed",
    ):
        try:
            client.delete_server_script(name)
        except Exception as exc:
            log_error(f"{name}: {exc}")

    log_section("Removendo Custom Field Sales Order.dispensation")
    for field in reversed(DISPENSATION_SO_FIELDS):
        try:
            client.delete_custom_field(field["dt"], field["fieldname"])
        except Exception as exc:
            log_error(f"{field['dt']}.{field['fieldname']}: {exc}")

    log_section("Removendo DocType Dispensation")
    try:
        client.delete_doctype("Dispensation")
    except Exception as exc:
        log_error(f"Dispensation: {exc}")

    log_section("Removendo DocType Dispensation Patient (child)")
    try:
        client.delete_doctype("Dispensation Patient")
    except Exception as exc:
        log_error(f"Dispensation Patient: {exc}")

    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
