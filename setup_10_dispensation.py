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
existing = frappe.db.get_value("Dispensacao", {"sales_order": so_name}, "name")
if existing:
    frappe.response["message"] = {
        "sales_order": so_name,
        "dispensation": existing,
        "created": False,
        "message": "Dispensation ja existia.",
    }
else:
    # Constroi rows. Sem fetch_from no schema (Frappe v15 bug), populamos
    # patient_name/cpf/prescriber_name/item_name/batch_expiry manualmente.
    rows = []
    total_qty = 0.0
    for p in (so.get("fp_patients") or []):
        if not p.batch_no:
            continue

        # Patient data
        patient_doc = frappe.db.get_value(
            "Patient", p.patient,
            ["patient_name", "cpf", "mobile"], as_dict=True
        ) or {}
        # Prescriber data
        pres_doc = {}
        if p.prescriber:
            pres_doc = frappe.db.get_value(
                "Prescriber", p.prescriber,
                ["full_name", "council_type", "council_number", "council_state"],
                as_dict=True
            ) or {}
        # Item data
        item_doc = frappe.db.get_value(
            "Item", p.item_code, "item_name"
        )
        # Batch data
        batch_doc = frappe.db.get_value(
            "Batch", p.batch_no,
            ["expiry_date", "manufacturing_date"], as_dict=True
        ) or {}

        rows.append({
            "patient": p.patient,
            "patient_name": patient_doc.get("patient_name"),
            "cpf": patient_doc.get("cpf"),
            "mobile": patient_doc.get("mobile"),
            "prescriber": p.prescriber,
            "prescriber_name": pres_doc.get("full_name"),
            "prescriber_council": pres_doc.get("council_type"),
            "prescriber_number": pres_doc.get("council_number"),
            "prescriber_state": pres_doc.get("council_state"),
            "item_code": p.item_code,
            "item_name": item_doc,
            "qty": p.qty,
            "batch_no": p.batch_no,
            "batch_expiry": batch_doc.get("expiry_date"),
            "batch_manufacturing": batch_doc.get("manufacturing_date"),
            "sales_order_patient_row": p.name,
            "printed": 0,
        })
        total_qty = total_qty + float(p.qty or 0)

    if not rows:
        frappe.throw(
            "SO " + so_name + " nao tem nenhuma linha fp_patients com batch_no preenchido. "
            "Rode future_production_allocate_patient_batches antes."
        )

    new_disp = frappe.new_doc("Dispensacao")
    new_disp.sales_order = so_name
    new_disp.customer = so.customer
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

disp = frappe.get_doc("Dispensacao", disp_name)
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


def build_zpl(tpl, patient_name, cpf_fmt, item_name, batch, val, fab, qty, barcode, so, disp_name):
    # Registro de tamanhos: nome -> (largura_mm, altura_mm, orientacao).
    # Para um novo tamanho: adicione aqui e na opcao do campo label_template
    # (LABEL_TEMPLATES em lib/payloads_dispensation.py). 203 dpi ~= 8 dots/mm.
    sizes = {
        "25x60mm": (25, 60, "portrait"),
        "50x30mm": (50, 30, "landscape"),
        "100x50mm": (100, 50, "landscape"),
    }
    size = sizes.get(tpl, (25, 60, "portrait"))
    w_mm = size[0]
    h_mm = size[1]
    orient = size[2]
    pw = w_mm * 8
    ll = h_mm * 8
    # qtd da linha -> numero de copias (^PQ). 1 etiqueta por unidade/ampola.
    pq = int(qty)
    if pq < 1:
        pq = 1

    if orient == "portrait":
        # Texto girado 90 graus (A0R): cabe nome longo ao longo da altura (ll).
        # A altura da fonte cresce em +x; linhas empilhadas pela largura (pw),
        # com posicoes proporcionais para escalar a outros tamanhos retrato.
        m = 16
        nm_x = int(pw * 0.82)
        cp_x = int(pw * 0.70)
        it_x = int(pw * 0.58)
        lo_x = int(pw * 0.46)
        va_x = int(pw * 0.34)
        bc_x = int(pw * 0.08)
        nm_h = int(pw * 0.13)
        cp_h = int(pw * 0.09)
        it_h = int(pw * 0.10)
        lo_h = int(pw * 0.085)
        va_h = int(pw * 0.085)
        bc_h = int(pw * 0.19)
        return (
            "^XA^CI28^PW" + str(pw) + "^LL" + str(ll) +
            "^FO" + str(nm_x) + "," + str(m) + "^A0R," + str(nm_h) + "," + str(nm_h) + "^FD" + patient_name + "^FS" +
            "^FO" + str(cp_x) + "," + str(m) + "^A0R," + str(cp_h) + "," + str(cp_h) + "^FDCPF: " + cpf_fmt + "^FS" +
            "^FO" + str(it_x) + "," + str(m) + "^A0R," + str(it_h) + "," + str(it_h) + "^FD" + item_name + "^FS" +
            "^FO" + str(lo_x) + "," + str(m) + "^A0R," + str(lo_h) + "," + str(lo_h) + "^FDLote: " + batch + "^FS" +
            "^FO" + str(va_x) + "," + str(m) + "^A0R," + str(va_h) + "," + str(va_h) + "^FDVal: " + val + "   Qtd: " + str(qty) + "^FS" +
            "^FO" + str(bc_x) + "," + str(m) + "^BCR," + str(bc_h) + ",N,N,N^FD" + barcode + "^FS" +
            "^PQ" + str(pq) + "^XZ"
        )

    if w_mm == 100 and h_mm == 50:
        return (
            "^XA" + "^CI28" + "^PW800^LL400" +
            "^FO30,20^A0N,36,36^FD" + patient_name + "^FS" +
            "^FO30,65^A0N,28,28^FDCPF: " + cpf_fmt + "^FS" +
            "^FO30,105^A0N,32,32^FD" + item_name + "^FS" +
            "^FO30,150^A0N,26,26^FDLote: " + batch + "^FS" +
            "^FO30,185^A0N,26,26^FDValidade: " + val + "^FS" +
            "^FO30,220^A0N,26,26^FDFabricacao: " + fab + "^FS" +
            "^FO30,255^A0N,28,28^FDQtd: " + str(qty) + " ampolas^FS" +
            "^FO30,300^BCN,60,Y,N,N^FD" + barcode + "^FS" +
            "^FO500,20^A0N,18,18^FD" + so + "^FS" +
            "^FO500,42^A0N,18,18^FD" + disp_name + "^FS" +
            "^PQ" + str(pq) + "^XZ"
        )

    # landscape padrao 50x30mm
    return (
        "^XA" + "^CI28" + "^PW400^LL240" +
        "^FO15,10^A0N,24,24^FD" + patient_name + "^FS" +
        "^FO15,40^A0N,18,18^FDCPF: " + cpf_fmt + "^FS" +
        "^FO15,65^A0N,20,20^FD" + item_name + "^FS" +
        "^FO15,90^A0N,18,18^FDLote: " + batch + "^FS" +
        "^FO15,113^A0N,18,18^FDVal: " + val + " Qty: " + str(qty) + "^FS" +
        "^FO15,140^BCN,55,Y,N,N^FD" + barcode + "^FS" +
        "^PQ" + str(pq) + "^XZ"
    )


zpl = build_zpl(
    disp.label_template or "25x60mm",
    patient_name, cpf_fmt, item_name, batch, val, fab, qty, barcode,
    disp.sales_order or "", disp.name or "",
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

disp = frappe.get_doc("Dispensacao", disp_name)
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


def build_zpl(tpl, patient_name, cpf_fmt, item_name, batch, val, fab, qty, barcode, so, disp_name):
    # Registro de tamanhos: nome -> (largura_mm, altura_mm, orientacao).
    # Para um novo tamanho: adicione aqui e na opcao do campo label_template
    # (LABEL_TEMPLATES em lib/payloads_dispensation.py). 203 dpi ~= 8 dots/mm.
    sizes = {
        "25x60mm": (25, 60, "portrait"),
        "50x30mm": (50, 30, "landscape"),
        "100x50mm": (100, 50, "landscape"),
    }
    size = sizes.get(tpl, (25, 60, "portrait"))
    w_mm = size[0]
    h_mm = size[1]
    orient = size[2]
    pw = w_mm * 8
    ll = h_mm * 8
    # qtd da linha -> numero de copias (^PQ). 1 etiqueta por unidade/ampola.
    pq = int(qty)
    if pq < 1:
        pq = 1

    if orient == "portrait":
        # Texto girado 90 graus (A0R): cabe nome longo ao longo da altura (ll).
        # A altura da fonte cresce em +x; linhas empilhadas pela largura (pw),
        # com posicoes proporcionais para escalar a outros tamanhos retrato.
        m = 16
        nm_x = int(pw * 0.82)
        cp_x = int(pw * 0.70)
        it_x = int(pw * 0.58)
        lo_x = int(pw * 0.46)
        va_x = int(pw * 0.34)
        bc_x = int(pw * 0.08)
        nm_h = int(pw * 0.13)
        cp_h = int(pw * 0.09)
        it_h = int(pw * 0.10)
        lo_h = int(pw * 0.085)
        va_h = int(pw * 0.085)
        bc_h = int(pw * 0.19)
        return (
            "^XA^CI28^PW" + str(pw) + "^LL" + str(ll) +
            "^FO" + str(nm_x) + "," + str(m) + "^A0R," + str(nm_h) + "," + str(nm_h) + "^FD" + patient_name + "^FS" +
            "^FO" + str(cp_x) + "," + str(m) + "^A0R," + str(cp_h) + "," + str(cp_h) + "^FDCPF: " + cpf_fmt + "^FS" +
            "^FO" + str(it_x) + "," + str(m) + "^A0R," + str(it_h) + "," + str(it_h) + "^FD" + item_name + "^FS" +
            "^FO" + str(lo_x) + "," + str(m) + "^A0R," + str(lo_h) + "," + str(lo_h) + "^FDLote: " + batch + "^FS" +
            "^FO" + str(va_x) + "," + str(m) + "^A0R," + str(va_h) + "," + str(va_h) + "^FDVal: " + val + "   Qtd: " + str(qty) + "^FS" +
            "^FO" + str(bc_x) + "," + str(m) + "^BCR," + str(bc_h) + ",N,N,N^FD" + barcode + "^FS" +
            "^PQ" + str(pq) + "^XZ"
        )

    if w_mm == 100 and h_mm == 50:
        return (
            "^XA" + "^CI28" + "^PW800^LL400" +
            "^FO30,20^A0N,36,36^FD" + patient_name + "^FS" +
            "^FO30,65^A0N,28,28^FDCPF: " + cpf_fmt + "^FS" +
            "^FO30,105^A0N,32,32^FD" + item_name + "^FS" +
            "^FO30,150^A0N,26,26^FDLote: " + batch + "^FS" +
            "^FO30,185^A0N,26,26^FDValidade: " + val + "^FS" +
            "^FO30,220^A0N,26,26^FDFabricacao: " + fab + "^FS" +
            "^FO30,255^A0N,28,28^FDQtd: " + str(qty) + " ampolas^FS" +
            "^FO30,300^BCN,60,Y,N,N^FD" + barcode + "^FS" +
            "^FO500,20^A0N,18,18^FD" + so + "^FS" +
            "^FO500,42^A0N,18,18^FD" + disp_name + "^FS" +
            "^PQ" + str(pq) + "^XZ"
        )

    # landscape padrao 50x30mm
    return (
        "^XA" + "^CI28" + "^PW400^LL240" +
        "^FO15,10^A0N,24,24^FD" + patient_name + "^FS" +
        "^FO15,40^A0N,18,18^FDCPF: " + cpf_fmt + "^FS" +
        "^FO15,65^A0N,20,20^FD" + item_name + "^FS" +
        "^FO15,90^A0N,18,18^FDLote: " + batch + "^FS" +
        "^FO15,113^A0N,18,18^FDVal: " + val + " Qty: " + str(qty) + "^FS" +
        "^FO15,140^BCN,55,Y,N,N^FD" + barcode + "^FS" +
        "^PQ" + str(pq) + "^XZ"
    )


template = disp.label_template or "25x60mm"
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

    zpl = build_zpl(
        template,
        patient_name, cpf_fmt, item_name, batch, val, fab, qty, barcode,
        disp.sales_order or "", disp.name or "",
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

frappe.db.set_value("Dispensacao Paciente", row_name, {
    "printed": 1,
    "printed_at": frappe.utils.now(),
}, update_modified=False)

# Conta quantas linhas impressas / total
total = frappe.db.count("Dispensacao Paciente", {"parent": disp_name})
# NOTA: "printed" e nome reservado no RestrictedPython (mecanismo de print),
# por isso a variavel se chama printed_n. As chaves de string "printed" sao ok.
printed_n = frappe.db.count("Dispensacao Paciente", {
    "parent": disp_name, "printed": 1,
})
all_printed = 1 if printed_n >= total and total > 0 else 0

frappe.db.set_value("Dispensacao", disp_name, {
    "printed_count": str(printed_n) + "/" + str(total),
    "all_printed": all_printed,
}, update_modified=False)

frappe.response["message"] = {
    "dispensation": disp_name,
    "row_name": row_name,
    "printed": str(printed_n) + "/" + str(total),
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

disp = frappe.get_doc("Dispensacao", disp_name)

frappe.db.set_value("Dispensacao", disp_name, {
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

frappe.ui.form.on('Dispensacao', {
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

    // Botão "Imprimir Esta Linha" no grid child — registra no refresh
    // (em Frappe v15, frm.fields_dict.patients.grid pode não existir no setup)
    const patients_field = frm.fields_dict && frm.fields_dict.patients;
    if (patients_field && patients_field.grid && !patients_field.grid._zebra_btn_added) {
      patients_field.grid.add_custom_button('Imprimir Esta Linha', function() {
        const selected = patients_field.grid.get_selected_children();
        if (!selected.length) {
          frappe.msgprint('Selecione 1 linha primeiro.');
          return;
        }
        print_one_label(frm, selected[0].name);
      });
      patients_field.grid._zebra_btn_added = true;
    }
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

// ---------------------------------------------------------------------------
// Zebra Browser Print — comunicacao DIRETA com o servico HTTP local.
// Nao depende da biblioteca BrowserPrint*.min.js (que nunca era carregada na
// pagina, por isso o codigo antigo caia sempre no dialog de copiar/colar).
//
// Descobertas validadas no ambiente do farmaceutico:
//  - O servico escuta em http://localhost:9100 (bind IPv6 ::1; 127.0.0.1 NAO
//    responde). Por isso usar 'localhost'/'[::1]', nunca '127.0.0.1'.
//  - GET  /default?type=printer  -> device padrao (simple request, sem preflight)
//  - POST /write  com body=JSON {device,data} e SEM header Content-Type, pois
//    'application/json' dispara preflight CORS (OPTIONS) que o servico nao trata.
//    Sem o header, o body string vira text/plain => simple request => funciona.
//  - http://localhost a partir de pagina HTTPS NAO e bloqueado por mixed-content
//    (Chrome trata localhost/::1 como origem potencialmente segura).
// ---------------------------------------------------------------------------
const ZEBRA_BASES = [
  'http://localhost:9100',
  'http://[::1]:9100',
  'http://127.0.0.1:9100',
  'https://localhost:9101',
  'https://[::1]:9101',
  'https://127.0.0.1:9101'
];

async function zebra_find_base() {
  if (window.__zebra_base) return window.__zebra_base;
  for (const base of ZEBRA_BASES) {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 2500);
      const r = await fetch(base + '/available', { signal: ctrl.signal });
      clearTimeout(timer);
      if (r.ok) { window.__zebra_base = base; return base; }
    } catch (e) { /* tenta a proxima base */ }
  }
  return null;
}

function send_to_zebra(frm, zpl, labels, mark_all) {
  (async () => {
    const base = await zebra_find_base();
    if (!base) {
      frappe.msgprint({
        title: 'Browser Print nao detectado',
        message: 'Abra o Zebra Browser Print na bandeja do sistema e tente novamente.',
        indicator: 'orange'
      });
      show_zpl_dialog(frm, zpl, labels, mark_all);
      return;
    }
    let device;
    try {
      const dr = await fetch(base + '/default?type=printer');
      device = await dr.json();
    } catch (e) {
      show_zpl_dialog(frm, zpl, labels, mark_all);
      return;
    }
    if (!device || !device.uid) {
      frappe.msgprint({
        title: 'Impressora nao encontrada',
        message: 'Selecione a Zebra como Default Device no Browser Print.',
        indicator: 'orange'
      });
      show_zpl_dialog(frm, zpl, labels, mark_all);
      return;
    }
    try {
      // SEM header Content-Type => text/plain => simple request => sem preflight CORS.
      // Retry: o servico as vezes responde 500 quando a impressora ainda processa
      // o trabalho anterior; tentamos ate 3x antes de cair no fallback do dialog.
      let wr = null;
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          wr = await fetch(base + '/write', {
            method: 'POST',
            body: JSON.stringify({ device: device, data: zpl })
          });
          if (wr.ok) break;
        } catch (e) { wr = null; }
        await new Promise((res) => setTimeout(res, 400));
      }
      if (!wr || !wr.ok) throw new Error('HTTP ' + (wr ? wr.status : 'sem resposta'));
      frappe.show_alert({ message: 'Enviado para a Zebra (' + (device.name || device.uid) + ').', indicator: 'green' });
      mark_printed_rows(frm, labels);
    } catch (e) {
      frappe.msgprint({ title: 'Falha na impressao', message: String((e && e.message) || e), indicator: 'red' });
      show_zpl_dialog(frm, zpl, labels, mark_all);
    }
  })();
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
            name="Dispensacao - Print Zebra Labels",
            dt="Dispensacao",
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
        client.delete_client_script("Dispensacao - Print Zebra Labels")
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
        client.delete_doctype("Dispensacao")
    except Exception as exc:
        log_error(f"Dispensation: {exc}")

    log_section("Removendo DocType Dispensation Patient (child)")
    try:
        client.delete_doctype("Dispensacao Paciente")
    except Exception as exc:
        log_error(f"Dispensation Patient: {exc}")

    return 0


def main(argv: list[str]) -> int:
    if "--uninstall" in argv:
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
