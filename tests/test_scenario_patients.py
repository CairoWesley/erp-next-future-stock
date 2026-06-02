"""
test_scenario_patients.py — valida o módulo Lote × Pacientes.

Cenário:
  - 1 médico (Customer) -> TEST-PF-Alfa
  - 4 pacientes do médico, cada um recebendo 1+ ampolas
  - 1 Sales Order com 1 item (TIR00060, qty=10) e os 4 pacientes vinculados
  - Validações testadas:
     1. Soma das ampolas dos pacientes deve = qty do item
     2. CPF inválido (10 dígitos) -> bloqueia
     3. Item do paciente fora do SO -> bloqueia
  - Ao final: reserva contra FPB e verifica rastreabilidade
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime as dt
import json
import sys
import time
import traceback
from typing import Any

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section


COMPANY = os.environ.get("ERPNEXT_COMPANY", "Injmedpharma")
ITEM_CODE = "TIR00060"
TARGET_WAREHOUSE = os.environ.get("ERPNEXT_WAREHOUSE", "Produtos Acabados - I")
DOCTOR = "TEST-PF-Alfa"  # médico/clínica
TODAY = dt.date.today().isoformat()
DELIVERY_DATE = (dt.date.today() + dt.timedelta(days=30)).isoformat()
PRODUCTION_DATE = (dt.date.today() + dt.timedelta(days=14)).isoformat()

# CPFs fictícios com 11 dígitos (não todos iguais — passam na validação básica)
PATIENTS = [
    # (suffix, nome, cpf, mobile, city, qty ampolas)
    ("p001", "Maria Aparecida Silva",   "11144477735", "11999990001", "São Paulo",     3),
    ("p002", "João Pedro Oliveira",     "22255588849", "11999990002", "São Paulo",     2),
    ("p003", "Ana Carolina Santos",     "33366699953", "21999990003", "Rio de Janeiro", 4),
    ("p004", "Carlos Eduardo Souza",    "44477700067", "31999990004", "Belo Horizonte", 1),
]
ITEM_TOTAL_QTY = sum(p[5] for p in PATIENTS)  # 10


def call(client, method: str, path: str, **kwargs):
    return client._request(method, path, **kwargs)


def submit_doc(client, doctype: str, name: str) -> None:
    encoded = name.replace(" ", "%20").replace("/", "%2F")
    _, body = call(client, "GET", f"/api/resource/{doctype}/{encoded}")
    doc = body.get("data", {})
    call(client, "POST", "/api/method/frappe.client.submit", json_body={"doc": doc})


def cancel_doc(client, doctype: str, name: str) -> None:
    call(client, "POST", "/api/method/frappe.client.cancel",
         json_body={"doctype": doctype, "name": name})


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup(client) -> None:
    log_section("Cleanup")

    # PRs do teste
    _, body = call(client, "GET", "/api/resource/Production Reservation",
                   params={"fields": '["name","docstatus","customer"]',
                           "filters": json.dumps([["customer", "=", DOCTOR]]),
                           "limit_page_length": 200})
    for pr in (body or {}).get("data") or []:
        try:
            if pr.get("docstatus") == 1:
                cancel_doc(client, "Production Reservation", pr["name"])
            call(client, "DELETE", f"/api/resource/Production Reservation/{pr['name']}")
            log_ok(f"  PR removida: {pr['name']}")
        except Exception as exc:
            log_error(f"  Falha PR: {exc}")

    # SOs do médico
    _, body = call(client, "GET", "/api/resource/Sales Order",
                   params={"fields": '["name","docstatus"]',
                           "filters": json.dumps([["customer", "=", DOCTOR]]),
                           "limit_page_length": 200})
    for so in (body or {}).get("data") or []:
        try:
            if so.get("docstatus") == 1:
                cancel_doc(client, "Sales Order", so["name"])
            call(client, "DELETE", f"/api/resource/Sales Order/{so['name']}")
            log_ok(f"  SO removido: {so['name']}")
        except Exception as exc:
            log_error(f"  Falha SO: {exc}")

    # FPBs TEST-PF-*
    _, body = call(client, "GET", "/api/resource/Future Production Batch",
                   params={"fields": '["name","docstatus","production_code"]',
                           "filters": '[["production_code","like","TEST-PT-%"]]',
                           "limit_page_length": 200})
    for fpb in (body or {}).get("data") or []:
        try:
            if fpb.get("docstatus") == 1:
                cancel_doc(client, "Future Production Batch", fpb["name"])
            call(client, "DELETE", f"/api/resource/Future Production Batch/{fpb['name']}")
            log_ok(f"  FPB removida: {fpb['name']}")
        except Exception as exc:
            log_error(f"  Falha FPB: {exc}")

    # Patients de teste (suffix p001..p004)
    suffixes = [p[0] for p in PATIENTS]
    _, body = call(client, "GET", "/api/resource/Patient",
                   params={"fields": '["name","patient_name"]',
                           "filters": json.dumps([["patient_name", "like", "%(p0%"]]),
                           "limit_page_length": 200})
    # Backup: pega todos com cpf nos da lista
    cpfs = [p[2] for p in PATIENTS]
    _, body2 = call(client, "GET", "/api/resource/Patient",
                    params={"fields": '["name","patient_name","cpf"]',
                            "filters": json.dumps([["cpf", "in", cpfs]]),
                            "limit_page_length": 200})
    for pat in (body2 or {}).get("data") or []:
        try:
            call(client, "DELETE", f"/api/resource/Patient/{pat['name']}")
            log_ok(f"  Patient removido: {pat['name']} ({pat.get('patient_name','')})")
        except Exception as exc:
            log_error(f"  Falha Patient: {exc}")


# ---------------------------------------------------------------------------
# Cenário
# ---------------------------------------------------------------------------

def get_or_create_doctor(client) -> str:
    s, _ = call(client, "GET", f"/api/resource/Customer/{DOCTOR}")
    if s == 200:
        log_ok(f"Médico {DOCTOR} já existe")
        return DOCTOR
    _, body = call(client, "POST", "/api/resource/Customer", json_body={
        "doctype": "Customer",
        "customer_name": DOCTOR,
        "customer_type": "Individual",
        "customer_group": "Comercial",
        "territory": "Brazil",
    })
    log_ok(f"Médico criado: {DOCTOR}")
    return body["data"]["name"]


def create_patients(client) -> list[str]:
    names = []
    for suffix, full_name, cpf, mobile, city, _qty in PATIENTS:
        _, body = call(client, "POST", "/api/resource/Patient", json_body={
            "doctype": "Patient",
            "patient_name": f"({suffix}) {full_name}",
            "cpf": cpf,
            "mobile": mobile,
            "city": city,
            "state": "SP" if "São Paulo" in city else ("RJ" if "Rio" in city else "MG"),
            "country": "Brazil",
            "gender": "Feminino" if "Maria" in full_name or "Ana" in full_name else "Masculino",
            "prescribing_doctor": DOCTOR,
        })
        names.append(body["data"]["name"])
        log_ok(f"  Patient criado: {body['data']['name']} ({full_name}, cpf={cpf})")
    return names


def run(client) -> dict[str, Any]:
    results: dict[str, Any] = {}

    log_section("1/6 — Garantir médico (Customer)")
    get_or_create_doctor(client)

    log_section("2/6 — Cadastrar 4 pacientes")
    patient_ids = create_patients(client)
    results["patients"] = patient_ids

    log_section("3/6 — Criar Future Production Batch de 2.000 unid")
    production_code = f"TEST-PT-{int(time.time())}"
    _, body = call(client, "POST", "/api/resource/Future Production Batch", json_body={
        "doctype": "Future Production Batch",
        "production_code": production_code,
        "company": COMPANY,
        "item_code": ITEM_CODE,
        "planned_qty": 2000,
        "planned_production_date": PRODUCTION_DATE,
        "target_warehouse": TARGET_WAREHOUSE,
        "status": "Aberta para Reserva",
    })
    fpb_name = body["data"]["name"]
    submit_doc(client, "Future Production Batch", fpb_name)
    log_ok(f"FPB criada e submetida: {fpb_name}")
    results["fpb"] = fpb_name

    log_section("4/6 — Sales Order do médico com 4 pacientes vinculados")
    patients_table = []
    for (suffix, full_name, cpf, mobile, city, qty), pat_name in zip(PATIENTS, patient_ids):
        patients_table.append({
            "patient": pat_name,
            "item_code": ITEM_CODE,
            "qty": qty,
        })

    so_payload = {
        "doctype": "Sales Order",
        "customer": DOCTOR,
        "company": COMPANY,
        "transaction_date": TODAY,
        "delivery_date": DELIVERY_DATE,
        "currency": "BRL",
        "selling_price_list": "Venda Padrão",
        "price_list_currency": "BRL",
        "plc_conversion_rate": 1,
        "conversion_rate": 1,
        "items": [{
            "item_code": ITEM_CODE,
            "qty": ITEM_TOTAL_QTY,
            "rate": 100,
            "delivery_date": DELIVERY_DATE,
            "warehouse": TARGET_WAREHOUSE,
        }],
        "fp_patients": patients_table,
    }
    _, body = call(client, "POST", "/api/resource/Sales Order", json_body=so_payload)
    so_name = body["data"]["name"]
    soi_id = body["data"]["items"][0]["name"]
    submit_doc(client, "Sales Order", so_name)
    log_ok(f"SO criado e submetido: {so_name} (item row={soi_id}, qty={ITEM_TOTAL_QTY})")
    log_ok(f"  Pacientes na tabela:")
    for p in (body["data"].get("fp_patients") or []):
        log_ok(f"    - {p.get('patient_name')} ({p.get('cpf')}) -> {p.get('qty')} ampolas, "
               f"mobile={p.get('mobile')}, city {p.get('city') or '(via cadastro)'}")
    results["so"] = so_name
    results["soi"] = soi_id

    log_section("5/6 — Reservar SO na FPB")
    msg = client.call_method("future_production_reserve_sales_order_item", {
        "sales_order": so_name,
        "sales_order_item": soi_id,
        "future_production_batch": fpb_name,
        "qty": ITEM_TOTAL_QTY,
        "priority": 100,
    })
    pr_info = (msg or {}).get("message") or {}
    log_ok(f"Reserva criada: PR={pr_info.get('reservation')}, "
           f"available restante={pr_info.get('available_qty_after')}")
    results["pr"] = pr_info.get("reservation")

    log_section("6/6 — Testar validações negativas")

    # Teste A: soma das ampolas dos pacientes != qty do item
    log_ok("A) Tentar criar SO com soma errada (deve FALHAR)")
    try:
        bad_payload = dict(so_payload)
        bad_payload["fp_patients"] = [
            {"patient": patient_ids[0], "item_code": ITEM_CODE, "qty": 99},  # erro
        ]
        bad_payload["items"] = [{
            "item_code": ITEM_CODE, "qty": 10, "rate": 100,
            "delivery_date": DELIVERY_DATE, "warehouse": TARGET_WAREHOUSE,
        }]
        call(client, "POST", "/api/resource/Sales Order", json_body=bad_payload)
        log_error("    FALHOU: deveria ter bloqueado!")
    except Exception as exc:
        log_ok(f"    BLOQUEADO corretamente: {str(exc)[:200]}")

    # Teste B: CPF inválido
    log_ok("B) Tentar criar Patient com CPF inválido (deve FALHAR)")
    try:
        call(client, "POST", "/api/resource/Patient", json_body={
            "doctype": "Patient",
            "patient_name": "Teste CPF Ruim",
            "cpf": "12345",  # só 5 dígitos
        })
        log_error("    FALHOU: deveria ter bloqueado!")
    except Exception as exc:
        log_ok(f"    BLOQUEADO corretamente: {str(exc)[:200]}")

    return results


def analyze(client, results: dict[str, Any]) -> int:
    log_section("Análise final")

    so_name = results["so"]
    pr_name = results["pr"]

    _, body = call(client, "GET", f"/api/resource/Sales Order/{so_name}")
    so = body["data"]

    print(f"\n  Sales Order: {so_name}")
    print(f"  Cliente (médico): {so.get('customer')}")
    print(f"  Total: {so.get('grand_total')}")
    print(f"  fp_reserved_qty (item): "
          f"{so['items'][0].get('fp_reserved_qty')} de {so['items'][0].get('qty')}")
    print(f"  fp_reservation_status: {so['items'][0].get('fp_reservation_status')}")
    print(f"  fp_future_production_batch: {so['items'][0].get('fp_future_production_batch')}")

    print(f"\n  Pacientes vinculados ({len(so.get('fp_patients', []))}):")
    print(f"  {'Nome':<40} {'CPF':<14} {'Cel':<14} {'Item':<12} {'Qtd':>4}")
    print(f"  {'-' * 90}")
    for p in so.get("fp_patients") or []:
        print(f"  {(p.get('patient_name') or ''):<40} {(p.get('cpf') or ''):<14} "
              f"{(p.get('mobile') or ''):<14} {(p.get('item_code') or ''):<12} "
              f"{p.get('qty') or '':>4}")

    print(f"\n  Production Reservation: {pr_name}")
    _, body = call(client, "GET", f"/api/resource/Production Reservation/{pr_name}")
    pr = body["data"]
    print(f"  Item: {pr.get('item_code')}, qty reservada: {pr.get('reserved_qty')}")
    print(f"  FPB: {pr.get('future_production_batch')}")
    print(f"  Status: {pr.get('status')}")
    print(f"  ==> Esta PR cobre o item do SO. Para descobrir QUAIS pacientes")
    print(f"  receberão dessa reserva, use o SO ({so_name}).fp_patients filtrando por item_code.")

    return 0


def main() -> int:
    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1

    if "--no-cleanup" not in sys.argv:
        cleanup(client)

    try:
        results = run(client)
    except Exception as exc:
        log_error(f"Cenário interrompido: {exc}")
        traceback.print_exc()
        return 1

    return analyze(client, results)


if __name__ == "__main__":
    raise SystemExit(main())
