"""
test_scenario_prescribers.py — valida o módulo Prescriber.

Cenário:
  1. Criar 2 Prescribers válidos (CRM-SP, CRO-RJ)
  2. Tentar duplicar CPF (deve falhar)
  3. Tentar duplicar conselho (mesmo tipo+número+UF) (deve falhar)
  4. Tentar criar com "Outro" sem council_other (deve falhar)
  5. Editar Prescriber → status Cassado
  6. Atualizar Patient com default_prescriber
  7. Criar SO com pacientes apontando prescribers diferentes
  8. Tentar usar prescriber Cassado em SO (deve falhar)
  9. Cleanup

Pré-requisito: setup_all.py executado (DocType Prescriber existe).
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
import traceback
from urllib.parse import quote

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section, ErpnextApiError


COMPANY = os.environ.get("ERPNEXT_COMPANY", "Injmedpharma")
ITEM_CODE = "TIR00060"
TARGET_WAREHOUSE = os.environ.get("ERPNEXT_WAREHOUSE", "Produtos Acabados - I")


def call(client, method: str, path: str, **kwargs):
    return client._request(method, path, **kwargs)


def submit_doc(client, doctype: str, name: str) -> None:
    encoded = quote(name, safe="")
    _, body = call(client, "GET", f"/api/resource/{doctype}/{encoded}")
    doc = body.get("data", {})
    call(client, "POST", "/api/method/frappe.client.submit", json_body={"doc": doc})


def cancel_doc(client, doctype: str, name: str) -> None:
    call(client, "POST", "/api/method/frappe.client.cancel",
         json_body={"doctype": doctype, "name": name})


def cleanup(client) -> None:
    log_section("Cleanup — removendo Prescribers + SOs de teste")

    # Cancela/apaga SOs TEST-PRES-*
    _, body = call(client, "GET", "/api/resource/Sales Order",
                   params={
                       "fields": '["name","docstatus"]',
                       "filters": json.dumps([["customer", "=", "TEST-PRES-Customer"]]),
                       "limit_page_length": 200,
                   })
    for so in (body or {}).get("data") or []:
        # Cancela PRs primeiro
        try:
            _, prs = call(client, "GET", "/api/resource/Production Reservation",
                          params={"filters": json.dumps([["sales_order", "=", so["name"]]]),
                                  "fields": '["name","docstatus"]'})
            for pr in (prs or {}).get("data") or []:
                if pr.get("docstatus") == 1:
                    cancel_doc(client, "Production Reservation", pr["name"])
                call(client, "DELETE", f"/api/resource/Production Reservation/{pr['name']}")
        except Exception:
            pass
        try:
            if so.get("docstatus") == 1:
                cancel_doc(client, "Sales Order", so["name"])
            call(client, "DELETE", f"/api/resource/Sales Order/{so['name']}")
            log_ok(f"  SO removido: {so['name']}")
        except Exception as exc:
            log_error(f"  Falha SO {so['name']}: {exc}")

    # Apaga FPBs TEST-PRES-*
    _, body = call(client, "GET", "/api/resource/Future Production Batch",
                   params={
                       "fields": '["name","docstatus","production_code"]',
                       "filters": '[["production_code","like","TEST-PRES-%"]]',
                       "limit_page_length": 100,
                   })
    for fpb in (body or {}).get("data") or []:
        try:
            if fpb.get("docstatus") == 1:
                cancel_doc(client, "Future Production Batch", fpb["name"])
            call(client, "DELETE", f"/api/resource/Future Production Batch/{fpb['name']}")
            log_ok(f"  FPB removido: {fpb['name']}")
        except Exception as exc:
            log_error(f"  Falha FPB {fpb['name']}: {exc}")

    # Apaga Prescribers de teste (CPF tag TEST-)
    _, body = call(client, "GET", "/api/resource/Prescriber",
                   params={
                       "fields": '["name","full_name"]',
                       "filters": '[["full_name","like","TEST-PRES-%"]]',
                       "limit_page_length": 100,
                   })
    for p in (body or {}).get("data") or []:
        try:
            call(client, "DELETE", f"/api/resource/Prescriber/{p['name']}")
            log_ok(f"  Prescriber removido: {p['name']} ({p['full_name']})")
        except Exception as exc:
            log_error(f"  Falha Prescriber {p['name']}: {exc}")

    # Apaga Patients de teste
    _, body = call(client, "GET", "/api/resource/Patient",
                   params={
                       "fields": '["name","patient_name"]',
                       "filters": '[["patient_name","like","TEST-PRES-%"]]',
                       "limit_page_length": 100,
                   })
    for p in (body or {}).get("data") or []:
        try:
            call(client, "DELETE", f"/api/resource/Patient/{p['name']}")
            log_ok(f"  Patient removido: {p['name']}")
        except Exception as exc:
            log_error(f"  Falha Patient {p['name']}: {exc}")


def expect_fail(label: str, fn):
    try:
        fn()
        log_error(f"  FAIL — esperava erro mas passou: {label}")
        return False
    except ErpnextApiError as exc:
        log_ok(f"  BLOQUEADO corretamente ({label}): {str(exc)[:200]}")
        return True
    except Exception as exc:
        log_error(f"  FAIL — exceção inesperada em '{label}': {exc}")
        return False


def run(client) -> int:
    failed = 0

    # ---------- 1. Criar 2 Prescribers válidos ----------
    log_section("1/6 — Criar 2 Prescribers válidos")

    pres_a_payload = {
        "doctype": "Prescriber",
        "full_name": "TEST-PRES-Dr-Jose-CRM-SP",
        "cpf": "11144477735",
        "council_type": "CRM",
        "council_number": "12345",
        "council_state": "SP",
        "council_status": "Ativo",
        "gender": "Masculino",
        "specialty": "Endocrinologia",
        "mobile": "11999990000",
        "email": "jose.test@example.com",
    }
    _, body = call(client, "POST", "/api/resource/Prescriber", json_body=pres_a_payload)
    pres_a = body["data"]["name"]
    log_ok(f"  Prescriber A criado: {pres_a} (CRM-SP 12345)")

    pres_b_payload = {
        "doctype": "Prescriber",
        "full_name": "TEST-PRES-Dra-Ana-CRO-RJ",
        "cpf": "52998224725",
        "council_type": "CRO",
        "council_number": "67890",
        "council_state": "RJ",
        "council_status": "Ativo",
        "gender": "Feminino",
        "specialty": "Endodontia",
    }
    _, body = call(client, "POST", "/api/resource/Prescriber", json_body=pres_b_payload)
    pres_b = body["data"]["name"]
    log_ok(f"  Prescriber B criado: {pres_b} (CRO-RJ 67890)")

    # ---------- 2. Tentar duplicar CPF (deve FALHAR) ----------
    log_section("2/6 — Validações negativas")

    log_ok("  A) Duplicar CPF de Dr. Jose")
    ok = expect_fail("CPF duplicado", lambda: call(client, "POST", "/api/resource/Prescriber",
                                                    json_body={
                                                        "doctype": "Prescriber",
                                                        "full_name": "TEST-PRES-OutroComMesmoCPF",
                                                        "cpf": "11144477735",  # mesmo do A
                                                        "council_type": "CRM",
                                                        "council_number": "99999",
                                                        "council_state": "MG",
                                                    }))
    if not ok:
        failed += 1

    log_ok("  B) Duplicar conselho (CRM-SP 12345)")
    ok = expect_fail("Conselho duplicado", lambda: call(client, "POST", "/api/resource/Prescriber",
                                                         json_body={
                                                             "doctype": "Prescriber",
                                                             "full_name": "TEST-PRES-OutroComMesmoCRM",
                                                             "cpf": "39053344705",
                                                             "council_type": "CRM",
                                                             "council_number": "12345",  # mesmo do A
                                                             "council_state": "SP",
                                                         }))
    if not ok:
        failed += 1

    log_ok("  C) Tipo 'Outro' sem council_other")
    ok = expect_fail("Outro sem council_other", lambda: call(client, "POST", "/api/resource/Prescriber",
                                                              json_body={
                                                                  "doctype": "Prescriber",
                                                                  "full_name": "TEST-PRES-Outro-sem-sigla",
                                                                  "cpf": "12345678909",
                                                                  "council_type": "Outro",
                                                                  "council_number": "55555",
                                                                  "council_state": "SP",
                                                              }))
    if not ok:
        failed += 1

    log_ok("  D) CPF inválido (5 dígitos)")
    ok = expect_fail("CPF inválido", lambda: call(client, "POST", "/api/resource/Prescriber",
                                                   json_body={
                                                       "doctype": "Prescriber",
                                                       "full_name": "TEST-PRES-CPF-curto",
                                                       "cpf": "12345",
                                                       "council_type": "CRM",
                                                       "council_number": "77777",
                                                       "council_state": "SP",
                                                   }))
    if not ok:
        failed += 1

    # ---------- 3. Criar Customer + 4 Patients + FPB pra SO ----------
    log_section("3/6 — Preparar Customer, Patients e FPB")

    # Customer
    try:
        _, _ = call(client, "POST", "/api/resource/Customer", json_body={
            "doctype": "Customer",
            "customer_name": "TEST-PRES-Customer",
            "customer_type": "Individual",
            "customer_group": "Comercial",
            "territory": "Brazil",
        })
        log_ok("  Customer criado: TEST-PRES-Customer")
    except ErpnextApiError as exc:
        if "already exists" in str(exc).lower() or "exists" in str(exc).lower():
            log_ok("  Customer já existe: TEST-PRES-Customer")
        else:
            raise

    # Patients (4 pessoas) com default_prescriber
    patients = []
    # CPFs únicos pra este teste (não conflitam com outros test_scenarios)
    pacs_seed = [
        ("TEST-PRES-Maria",  "98765432100", pres_a),
        ("TEST-PRES-Joao",   "87654321098", pres_a),
        ("TEST-PRES-Ana",    "76543210987", pres_b),
        ("TEST-PRES-Carlos", "65432109876", pres_a),
    ]
    for nome, cpf, default_pres in pacs_seed:
        _, body = call(client, "POST", "/api/resource/Patient", json_body={
            "doctype": "Patient",
            "patient_name": nome,
            "cpf": cpf,
            "gender": "Feminino" if "Maria" in nome or "Ana" in nome else "Masculino",
            "country": "Brazil",
            "default_prescriber": default_pres,
        })
        pac_name = body["data"]["name"]
        patients.append({"name": pac_name, "default_prescriber": default_pres})
        log_ok(f"  Patient criado: {pac_name} (default={default_pres})")

    # FPB
    fpb_code = f"TEST-PRES-FPB-{int(time.time())}"
    _, body = call(client, "POST", "/api/resource/Future Production Batch", json_body={
        "doctype": "Future Production Batch",
        "production_code": fpb_code,
        "company": COMPANY,
        "item_code": ITEM_CODE,
        "planned_qty": 100,
        "planned_production_date": (dt.date.today() + dt.timedelta(days=14)).isoformat(),
        "target_warehouse": TARGET_WAREHOUSE,
        "status": "Aberta para Reserva",
    })
    fpb_name = body["data"]["name"]
    submit_doc(client, "Future Production Batch", fpb_name)
    log_ok(f"  FPB criado e submetido: {fpb_name}")

    # ---------- 4. Criar SO com prescriber por linha ----------
    log_section("4/6 — Criar SO com prescriber por linha")

    so_payload = {
        "doctype": "Sales Order",
        "customer": "TEST-PRES-Customer",
        "company": COMPANY,
        "transaction_date": dt.date.today().isoformat(),
        "delivery_date": (dt.date.today() + dt.timedelta(days=30)).isoformat(),
        "currency": "BRL",
        "selling_price_list": "Venda Padrão",
        "price_list_currency": "BRL",
        "plc_conversion_rate": 1,
        "conversion_rate": 1,
        "items": [{
            "item_code": ITEM_CODE,
            "qty": 10,
            "rate": 100,
            "delivery_date": (dt.date.today() + dt.timedelta(days=30)).isoformat(),
            "warehouse": TARGET_WAREHOUSE,
        }],
        "fp_patients": [
            {"patient": patients[0]["name"], "item_code": ITEM_CODE, "qty": 3, "prescriber": pres_a},
            {"patient": patients[1]["name"], "item_code": ITEM_CODE, "qty": 2, "prescriber": pres_a},
            {"patient": patients[2]["name"], "item_code": ITEM_CODE, "qty": 4, "prescriber": pres_b},  # médico diferente
            {"patient": patients[3]["name"], "item_code": ITEM_CODE, "qty": 1, "prescriber": pres_a},
        ],
    }
    _, body = call(client, "POST", "/api/resource/Sales Order", json_body=so_payload)
    so_name = body["data"]["name"]
    submit_doc(client, "Sales Order", so_name)
    log_ok(f"  SO criado e submetido: {so_name}")

    # Conferir prescribers na tabela
    _, body = call(client, "GET", f"/api/resource/Sales Order/{so_name}")
    so_doc = body["data"]
    log_ok(f"  Pacientes do SO com prescribers:")
    for row in so_doc.get("fp_patients", []):
        log_ok(f"    - {row.get('patient_name')} qty={row.get('qty')} prescriber={row.get('prescriber')}")

    # ---------- 5. Cassar Prescriber A → testar bloqueio em novo SO ----------
    log_section("5/6 — Cassar Prescriber A e testar bloqueio")

    _, body = call(client, "GET", f"/api/resource/Prescriber/{pres_a}")
    pres_doc = body["data"]
    pres_doc["council_status"] = "Cassado"
    call(client, "PUT", f"/api/resource/Prescriber/{pres_a}", json_body=pres_doc)
    log_ok(f"  Prescriber A ({pres_a}) marcado como 'Cassado'")

    log_ok("  Tentar criar novo SO usando Prescriber Cassado (deve FALHAR)")
    so_fail_payload = {
        "doctype": "Sales Order",
        "customer": "TEST-PRES-Customer",
        "company": COMPANY,
        "transaction_date": dt.date.today().isoformat(),
        "delivery_date": (dt.date.today() + dt.timedelta(days=30)).isoformat(),
        "currency": "BRL",
        "selling_price_list": "Venda Padrão",
        "price_list_currency": "BRL",
        "plc_conversion_rate": 1,
        "conversion_rate": 1,
        "items": [{
            "item_code": ITEM_CODE,
            "qty": 5,
            "rate": 100,
            "delivery_date": (dt.date.today() + dt.timedelta(days=30)).isoformat(),
            "warehouse": TARGET_WAREHOUSE,
        }],
        "fp_patients": [
            {"patient": patients[0]["name"], "item_code": ITEM_CODE, "qty": 5, "prescriber": pres_a},
        ],
    }
    ok = expect_fail("Prescriber Cassado", lambda: call(client, "POST", "/api/resource/Sales Order",
                                                        json_body=so_fail_payload))
    if not ok:
        failed += 1

    # Restaurar status pra Ativo (cleanup amigável)
    _, body = call(client, "GET", f"/api/resource/Prescriber/{pres_a}")
    pres_doc = body["data"]
    pres_doc["council_status"] = "Ativo"
    call(client, "PUT", f"/api/resource/Prescriber/{pres_a}", json_body=pres_doc)
    log_ok(f"  Prescriber A restaurado para 'Ativo'")

    # ---------- 6. Sumário ----------
    log_section("6/6 — Sumário")
    if failed == 0:
        log_ok("CENÁRIO PRESCRIBER APROVADO — todas validações funcionaram.")
        return 0
    log_error(f"CENÁRIO PRESCRIBER FALHOU — {failed} validação(ões) com problema.")
    return 1


def main() -> int:
    client = client_from_env()

    log_section("Pré-check: server_script_enabled")
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1
    log_ok("server_script_enabled = True")

    if "--no-cleanup" not in sys.argv:
        cleanup(client)

    try:
        rc = run(client)
    except Exception as exc:
        log_error(f"Cenário interrompido: {exc}")
        traceback.print_exc()
        return 1
    finally:
        if "--keep" not in sys.argv:
            cleanup(client)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
