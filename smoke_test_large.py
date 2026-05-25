"""
smoke_test_large.py — Smoke test em fases com volume realista.

Cenário:
  - 10 FPBs × 2.000 ampolas = 20.000 capacidade planejada
  - 6 Prescribers (3 CRM, 1 CRO, 1 CRF, 1 CRBM)
  - 30 Patients distribuídos
  - ~22 Sales Orders distribuídos entre 5 Customers
  - Total reservado: ~15.000 ampolas (~75% da capacidade)
  - Produção:
      * 3 FPBs produzidos TOTAL (2.000/2.000 cada = 6.000)
      * 7 FPBs produzidos PARCIAL (entre 1.000 e 1.800 — varia)
  - Liberação: FIFO automática

Fases (execução incremental):
    python smoke_test_large.py --phase setup       # 1. Customer/Prescriber/Patient
    python smoke_test_large.py --phase fpbs        # 2. 10 FPBs (aberta para reserva)
    python smoke_test_large.py --phase orders      # 3. SOs + reservas (auto FIFO)
    python smoke_test_large.py --phase produce     # 4. Produção real
    python smoke_test_large.py --phase release     # 5. Liberar FIFO
    python smoke_test_large.py --phase allocate    # 6. Alocar batch por paciente
    python smoke_test_large.py --phase report      # 7. Relatório final
    python smoke_test_large.py --phase cleanup     # Remover tudo (TEST-LRG-*)
    python smoke_test_large.py --phase all         # roda 1..7 em sequência

Estado entre fases salvo em .smoke_state.json.

Cada fase termina imprimindo "VISIBILIDADE":
  - URLs UI pra abrir no browser
  - Chamadas API pra validar via curl/Postman
  - Valores esperados
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path
from urllib.parse import quote

from lib.erpnext_api import (
    ErpnextApiError,
    client_from_env,
    log_error,
    log_ok,
    log_section,
)
from lib.visibility import (
    list_fpbs,
    list_prs_by_fpbs,
    list_pending_prs,
    list_sos_by_prefix,
    print_fpb_table,
    print_pr_table,
    print_so_table,
    print_visibility_hints,
)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

COMPANY = os.environ.get("ERPNEXT_COMPANY", "Injmedpharma")
ITEM_CODE = "TIR00060"
TARGET_WAREHOUSE = os.environ.get("ERPNEXT_WAREHOUSE", "Produtos Acabados - I")
RATE = 100.0

TAG = "TEST-LRG"                       # prefix em todos os documentos
CODE_PREFIX = f"{TAG}-FPB"
STATE_FILE = Path(".smoke_state.json")

NUM_FPBS = 10
QTY_PER_FPB = 2000
NUM_CUSTOMERS = 5
NUM_PRESCRIBERS = 6
NUM_PATIENTS = 30
NUM_SOS = 22

# 3 FPBs full + 7 partial
FULL_FPB_COUNT = 3
PARTIAL_PRODUCED_RANGE = (1000, 1800)

RANDOM_SEED = 42


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def call(client, method: str, path: str, **kwargs):
    return client._request(method, path, **kwargs)


def submit_doc(client, doctype: str, name: str) -> None:
    encoded = quote(name, safe="")
    _, body = call(client, "GET", f"/api/resource/{doctype}/{encoded}")
    doc = body.get("data", {})
    call(client, "POST", "/api/method/frappe.client.submit", json_body={"doc": doc})


def cancel_doc(client, doctype: str, name: str) -> None:
    try:
        call(client, "POST", "/api/method/frappe.client.cancel",
             json_body={"doctype": doctype, "name": name})
    except ErpnextApiError as exc:
        if "Not Submitted" not in str(exc) and "Cancelled" not in str(exc):
            raise


def get_doc(client, doctype: str, name: str) -> dict:
    encoded = quote(name, safe="")
    _, body = call(client, "GET", f"/api/resource/{doctype}/{encoded}")
    return (body or {}).get("data") or {}


# ---------------------------------------------------------------------------
# Phase 1 — Setup base (Customer / Prescriber / Patient)
# ---------------------------------------------------------------------------

CUSTOMER_NAMES = [
    f"{TAG}-Cliente-{ch}"
    for ch in ["Alfa", "Beta", "Gama", "Delta", "Epsilon"]
]

PRESCRIBER_SEED = [
    # (nome, cpf, council_type, council_number, council_state, specialty)
    (f"{TAG}-Dr-Ricardo",  "11122233396", "CRM", "10001", "SP", "Endocrinologia"),
    (f"{TAG}-Dra-Helena",  "22233344407", "CRM", "20002", "RJ", "Cardiologia"),
    (f"{TAG}-Dr-Marcelo",  "33344455518", "CRM", "30003", "MG", "Geriatria"),
    (f"{TAG}-Dra-Patricia","44455566629", "CRO", "40004", "SP", "Endodontia"),
    (f"{TAG}-Dr-Eduardo",  "55566677730", "CRF", "50005", "PR", "Farmácia Clínica"),
    (f"{TAG}-Dra-Beatriz", "66677788841", "CRBM","60006", "SP", "Biomedicina Estética"),
]

PATIENT_FIRST_NAMES = [
    "Maria", "Joao", "Ana", "Pedro", "Carla", "Luiz", "Beatriz", "Roberto",
    "Patricia", "Fernando", "Juliana", "Marcos", "Camila", "Rafael", "Larissa",
    "Bruno", "Aline", "Felipe", "Sandra", "Gabriel", "Renata", "Andre",
    "Vanessa", "Eduardo", "Mariana", "Diego", "Tatiana", "Leonardo", "Priscila",
    "Henrique",
]

PATIENT_LAST_NAMES = ["Silva", "Santos", "Oliveira", "Souza", "Pereira"]


def _gen_cpf(idx: int) -> str:
    """Gera CPF unique-ish (apenas 11 dígitos não triviais)."""
    base = f"{(idx * 9377 + 100000000) % 99999999999:011d}"
    if base == base[0] * 11:
        base = base[:-1] + "9"
    return base


def phase_setup(client, state: dict) -> dict:
    log_section("Phase 1/6 — Setup base (Customers + Prescribers + Patients)")

    # --- Customers
    customers = []
    for name in CUSTOMER_NAMES:
        encoded = quote(name, safe="")
        status, _ = call(client, "GET", f"/api/resource/Customer/{encoded}")
        if status == 200:
            log_ok(f"  Customer já existe: {name}")
        else:
            call(client, "POST", "/api/resource/Customer", json_body={
                "doctype": "Customer",
                "customer_name": name,
                "customer_type": "Company",
                "customer_group": "Comercial",
                "territory": "Brazil",
            })
            log_ok(f"  Customer criado: {name}")
        customers.append(name)

    # --- Prescribers
    prescribers = []
    for nome, cpf, ctype, cnum, cstate, specialty in PRESCRIBER_SEED:
        # busca por CPF
        _, body = call(client, "GET", "/api/resource/Prescriber",
                       params={"filters": json.dumps([["cpf", "=", cpf]]),
                               "fields": '["name"]', "limit_page_length": 1})
        existing = (body or {}).get("data") or []
        if existing:
            pname = existing[0]["name"]
            log_ok(f"  Prescriber já existe: {pname} ({nome})")
        else:
            _, body = call(client, "POST", "/api/resource/Prescriber", json_body={
                "doctype": "Prescriber",
                "full_name": nome,
                "cpf": cpf,
                "council_type": ctype,
                "council_number": cnum,
                "council_state": cstate,
                "council_status": "Ativo",
                "specialty": specialty,
            })
            pname = body["data"]["name"]
            log_ok(f"  Prescriber criado: {pname} ({ctype}-{cstate} {cnum})")
        prescribers.append(pname)

    # --- Patients (30, distribuídos entre prescribers)
    patients = []
    random.seed(RANDOM_SEED)
    for i in range(NUM_PATIENTS):
        first = PATIENT_FIRST_NAMES[i % len(PATIENT_FIRST_NAMES)]
        last = PATIENT_LAST_NAMES[i % len(PATIENT_LAST_NAMES)]
        pname = f"{TAG}-{first} {last} {i:02d}"
        cpf = _gen_cpf(i + 100)
        # Lookup por CPF
        _, body = call(client, "GET", "/api/resource/Patient",
                       params={"filters": json.dumps([["cpf", "=", cpf]]),
                               "fields": '["name"]', "limit_page_length": 1})
        existing = (body or {}).get("data") or []
        if existing:
            pac_name = existing[0]["name"]
        else:
            assigned_prescriber = prescribers[i % len(prescribers)]
            _, body = call(client, "POST", "/api/resource/Patient", json_body={
                "doctype": "Patient",
                "patient_name": pname,
                "cpf": cpf,
                "gender": "Feminino" if i % 2 == 0 else "Masculino",
                "country": "Brazil",
                "default_prescriber": assigned_prescriber,
                "mobile": f"11{i:09d}",
            })
            pac_name = body["data"]["name"]
        patients.append({
            "name": pac_name,
            "patient_name": pname,
            "cpf": cpf,
            "default_prescriber": prescribers[i % len(prescribers)],
        })
    log_ok(f"  {len(patients)} Patients prontos.")

    state["customers"] = customers
    state["prescribers"] = prescribers
    state["patients"] = patients
    save_state(state)

    print_visibility_hints(
        os.environ.get("ERPNEXT_URL", ""),
        item_code=ITEM_CODE,
        code_prefix=TAG,
    )
    return state


# ---------------------------------------------------------------------------
# Phase 2 — Criar 10 FPBs
# ---------------------------------------------------------------------------

def phase_fpbs(client, state: dict) -> dict:
    log_section(f"Phase 2/6 — Criar {NUM_FPBS} FPBs × {QTY_PER_FPB} ampolas")

    fpb_names = []
    base_date = dt.date.today() + dt.timedelta(days=14)
    for i in range(NUM_FPBS):
        prod_date = (base_date + dt.timedelta(days=i * 3)).isoformat()
        code = f"{CODE_PREFIX}-{i:02d}-{int(time.time()) % 100000}"
        # Tenta evitar duplicação
        _, body = call(client, "GET", "/api/resource/Future Production Batch",
                       params={"filters": json.dumps([["production_code", "=", code]]),
                               "fields": '["name"]', "limit_page_length": 1})
        if (body or {}).get("data"):
            log_ok(f"  FPB já existe: {code}")
            fpb_names.append((body["data"][0])["name"])
            continue

        _, body = call(client, "POST", "/api/resource/Future Production Batch", json_body={
            "doctype": "Future Production Batch",
            "production_code": code,
            "company": COMPANY,
            "item_code": ITEM_CODE,
            "planned_qty": QTY_PER_FPB,
            "planned_production_date": prod_date,
            "target_warehouse": TARGET_WAREHOUSE,
            "status": "Aberta para Reserva",
        })
        fpb_name = body["data"]["name"]
        submit_doc(client, "Future Production Batch", fpb_name)
        fpb_names.append(fpb_name)
        log_ok(f"  FPB {i+1}/{NUM_FPBS} criado e submetido: {fpb_name} (data prod {prod_date})")

    state["fpbs"] = fpb_names
    save_state(state)

    # Mostra tabela final
    fpbs = list_fpbs(client, item_code=ITEM_CODE, code_prefix=TAG)
    print_fpb_table(fpbs, title=f"Phase 2 — {len(fpbs)} FPBs após criação")

    print_visibility_hints(
        os.environ.get("ERPNEXT_URL", ""),
        item_code=ITEM_CODE,
        code_prefix=TAG,
        fpb_names=fpb_names,
    )
    return state


# ---------------------------------------------------------------------------
# Phase 3 — Criar SOs e reservar (auto)
# ---------------------------------------------------------------------------

def phase_orders(client, state: dict) -> dict:
    log_section(f"Phase 3/6 — Criar {NUM_SOS} SOs e reservar (auto FIFO)")

    customers = state.get("customers") or []
    patients = state.get("patients") or []
    if not customers or not patients:
        log_error("Phase 1 não executada. Rode --phase setup antes.")
        return state

    random.seed(RANDOM_SEED + 7)
    so_qtys = []
    # Distribui ~15000 ampolas em 22 SOs (média ~680/SO, variação 200..1200)
    remaining = 15000
    for i in range(NUM_SOS - 1):
        max_take = min(1200, remaining - (NUM_SOS - 1 - i) * 200)
        q = random.randint(200, max(200, max_take))
        so_qtys.append(q)
        remaining -= q
    so_qtys.append(max(200, remaining))

    so_names = []
    for i, qty in enumerate(so_qtys):
        cust = customers[i % len(customers)]
        # Escolhe 3-5 patients aleatoriamente
        n_patients = random.randint(3, 5)
        chosen = random.sample(patients, k=min(n_patients, len(patients)))

        # Distribui qty entre os pacientes
        shares = _distribute_qty(qty, n_patients)
        fp_patients_rows = []
        for pac, share in zip(chosen, shares):
            if share <= 0:
                continue
            fp_patients_rows.append({
                "patient": pac["name"],
                "item_code": ITEM_CODE,
                "qty": share,
                "prescriber": pac["default_prescriber"],
            })

        # Ajusta soma final
        diff = qty - sum(r["qty"] for r in fp_patients_rows)
        if diff != 0 and fp_patients_rows:
            fp_patients_rows[0]["qty"] += diff

        so_payload = {
            "doctype": "Sales Order",
            "customer": cust,
            "company": COMPANY,
            "transaction_date": dt.date.today().isoformat(),
            "delivery_date": (dt.date.today() + dt.timedelta(days=45)).isoformat(),
            "currency": "BRL",
            "selling_price_list": "Venda Padrão",
            "price_list_currency": "BRL",
            "plc_conversion_rate": 1,
            "conversion_rate": 1,
            "items": [{
                "item_code": ITEM_CODE,
                "qty": qty,
                "rate": RATE,
                "delivery_date": (dt.date.today() + dt.timedelta(days=45)).isoformat(),
                "warehouse": TARGET_WAREHOUSE,
            }],
            "fp_patients": fp_patients_rows,
        }
        try:
            _, body = call(client, "POST", "/api/resource/Sales Order", json_body=so_payload)
            so_name = body["data"]["name"]
            submit_doc(client, "Sales Order", so_name)
            log_ok(f"  SO {i+1}/{NUM_SOS} {so_name} cust={cust} qty={qty} "
                   f"({len(fp_patients_rows)} pacientes)")
        except ErpnextApiError as exc:
            log_error(f"  SO {i+1} falhou: {exc}")
            continue

        # Reserva auto
        try:
            resp = client.call_method("future_production_auto_reserve_sales_order",
                                       {"sales_order": so_name})
            msg = (resp or {}).get("message") or {}
            reservs = msg.get("reservations") or []
            log_ok(f"    -> {len(reservs)} reserva(s) auto criadas")
            so_names.append(so_name)
        except ErpnextApiError as exc:
            log_error(f"    -> reserva falhou: {exc}")

    state["sos"] = so_names
    save_state(state)

    # Visibility
    fpbs = list_fpbs(client, item_code=ITEM_CODE, code_prefix=TAG)
    print_fpb_table(fpbs, title="Phase 3 — FPBs após reservas (reserved/available)")

    print_visibility_hints(
        os.environ.get("ERPNEXT_URL", ""),
        item_code=ITEM_CODE,
        code_prefix=TAG,
        fpb_names=state.get("fpbs") or [],
        so_names=so_names,
    )
    return state


def _distribute_qty(total: int, n_parts: int) -> list[int]:
    if n_parts <= 0:
        return []
    base = total // n_parts
    rest = total - base * n_parts
    return [base + (1 if i < rest else 0) for i in range(n_parts)]


# ---------------------------------------------------------------------------
# Phase 4 — Produzir 3 full + 7 partial
# ---------------------------------------------------------------------------

def phase_produce(client, state: dict) -> dict:
    log_section(f"Phase 4/6 — Produção: {FULL_FPB_COUNT} FPBs full + "
                f"{NUM_FPBS - FULL_FPB_COUNT} parciais")

    fpb_names = state.get("fpbs") or []
    if not fpb_names:
        log_error("Sem FPBs em estado. Rode --phase fpbs.")
        return state

    random.seed(RANDOM_SEED + 11)

    production_plan = []
    for i, name in enumerate(fpb_names):
        if i < FULL_FPB_COUNT:
            produced = QTY_PER_FPB
        else:
            produced = random.randint(*PARTIAL_PRODUCED_RANGE)
        production_plan.append((name, produced))

    batches_created = []
    for i, (fpb_name, produced) in enumerate(production_plan):
        # Criar Batch físico
        batch_id = f"{TAG}-LOT-{i:02d}-{int(time.time()) % 100000}"
        _, body = call(client, "POST", "/api/resource/Batch", json_body={
            "doctype": "Batch",
            "batch_id": batch_id,
            "item": ITEM_CODE,
            "batch_qty": produced,
        })
        actual_batch = body["data"]["name"]
        log_ok(f"  Batch criado: {actual_batch} (qty={produced})")

        # Atualizar FPB
        try:
            call(client, "PUT", f"/api/resource/Future Production Batch/{fpb_name}",
                 json_body={"produced_qty": produced, "batch_no": actual_batch})
            log_ok(f"  FPB {fpb_name} atualizado: produced={produced}")
        except ErpnextApiError as exc:
            log_error(f"  Falha atualizar {fpb_name}: {exc}")
            continue

        batches_created.append({"fpb": fpb_name, "batch": actual_batch,
                                "produced": produced, "full": i < FULL_FPB_COUNT})

    state["batches"] = batches_created
    save_state(state)

    fpbs = list_fpbs(client, item_code=ITEM_CODE, code_prefix=TAG)
    print_fpb_table(fpbs, title="Phase 4 — FPBs após produção (produced/pending_release)")

    print_visibility_hints(
        os.environ.get("ERPNEXT_URL", ""),
        item_code=ITEM_CODE,
        code_prefix=TAG,
        fpb_names=fpb_names,
    )
    return state


# ---------------------------------------------------------------------------
# Phase 5 — Liberar reservas (FIFO)
# ---------------------------------------------------------------------------

def phase_release(client, state: dict) -> dict:
    log_section("Phase 5/6 — Liberar reservas (FIFO em cada FPB)")

    batches = state.get("batches") or []
    if not batches:
        log_error("Sem produção registrada. Rode --phase produce.")
        return state

    for b in batches:
        try:
            resp = client.call_method("future_production_release_batch",
                                       {"future_production_batch": b["fpb"]})
            msg = (resp or {}).get("message") or {}
            log_ok(f"  Release {b['fpb']}: count={msg.get('released_count')}, "
                   f"released={msg.get('released_qty')}, "
                   f"pending={msg.get('pending_release_qty')}")
        except ErpnextApiError as exc:
            log_error(f"  Release {b['fpb']} falhou: {exc}")

    fpbs = list_fpbs(client, item_code=ITEM_CODE, code_prefix=TAG)
    print_fpb_table(fpbs, title="Phase 5 — FPBs após liberação")

    print_visibility_hints(
        os.environ.get("ERPNEXT_URL", ""),
        item_code=ITEM_CODE,
        code_prefix=TAG,
        fpb_names=state.get("fpbs") or [],
    )
    return state


# ---------------------------------------------------------------------------
# Phase 6 — Alocar batch por paciente
# ---------------------------------------------------------------------------

def phase_allocate(client, state: dict) -> dict:
    log_section("Phase 6/7 — Alocar batch por paciente (fp_patients.batch_no)")

    so_names = state.get("sos") or []
    if not so_names:
        log_error("Sem SOs em estado. Rode --phase orders.")
        return state

    total_allocated = 0
    sos_with_alloc = 0
    for so_name in so_names:
        try:
            resp = client.call_method(
                "future_production_allocate_patient_batches",
                {"sales_order": so_name},
            )
            msg = (resp or {}).get("message") or {}
            n = int(msg.get("allocated_rows") or 0)
            if n > 0:
                sos_with_alloc += 1
                total_allocated += n
                log_ok(f"  {so_name}: {n} linha(s) alocada(s)")
        except ErpnextApiError as exc:
            log_error(f"  {so_name}: {exc}")

    log_ok(f"  Total: {total_allocated} linha(s) em {sos_with_alloc} SO(s)")

    # Amostra: pega 3 SOs e mostra estado dos pacientes
    log_section("Amostra — primeiros 3 SOs com pacientes alocados")
    shown = 0
    for so_name in so_names:
        if shown >= 3:
            break
        so_doc = get_doc(client, "Sales Order", so_name)
        patients = so_doc.get("fp_patients") or []
        if not patients:
            continue
        log_ok(f"\n  SO: {so_name}  (qty total={so_doc.get('items', [{}])[0].get('qty')})")
        rows = []
        for p in patients:
            rows.append([
                (p.get("patient_name") or "")[:30],
                f"{float(p.get('qty') or 0):.0f}",
                f"{float(p.get('allocated_qty') or 0):.0f}",
                (p.get("batch_no") or "-")[:24],
                (p.get("batch_status") or "")[:22],
            ])
        for r in rows:
            print(f"    - {r[0]:<30} qty={r[1]:>5} alloc={r[2]:>5} "
                  f"batch={r[3]:<24} status={r[4]}")
        shown += 1

    return state


# ---------------------------------------------------------------------------
# Phase 7 — Relatório final
# ---------------------------------------------------------------------------

def phase_report(client, state: dict) -> dict:
    log_section("Phase 7/7 — Relatório final consolidado")

    fpb_names = state.get("fpbs") or []
    fpbs = list_fpbs(client, item_code=ITEM_CODE, code_prefix=TAG)
    print_fpb_table(fpbs, title=f"FPBs do teste ({TAG})")

    # SOs
    sos = list_sos_by_prefix(client, f"{TAG}-Cliente-")
    print_so_table(sos, title="Sales Orders do teste")

    # PRs
    prs = list_prs_by_fpbs(client, fpb_names)
    print_pr_table(prs, title="Production Reservations do teste")

    # Pendências (geral, não só do teste)
    pending = [p for p in prs if float(p.get("pending_qty") or 0) > 0]
    if pending:
        log_section(f"PENDÊNCIAS — {len(pending)} reservas com saldo a liberar")
        rows = []
        total_pending = 0.0
        for p in pending:
            rows.append([
                p.get("name", ""),
                (p.get("future_production_batch") or "")[:18],
                (p.get("sales_order") or "")[:22],
                (p.get("customer") or "")[:18],
                f"{float(p.get('reserved_qty') or 0):.0f}",
                f"{float(p.get('released_qty') or 0):.0f}",
                f"{float(p.get('pending_qty') or 0):.0f}",
            ])
            total_pending += float(p.get("pending_qty") or 0)
        for r in rows:
            print(f"  - {r[0]:<22} FPB={r[1]:<18} SO={r[2]:<22} "
                  f"R={r[4]:>5} L={r[5]:>5} P={r[6]:>5}")
        print(f"\n  TOTAL pendente: {total_pending:.0f} ampolas")
    else:
        log_ok("Nenhuma pendência. Todas reservas foram liberadas.")

    print_visibility_hints(
        os.environ.get("ERPNEXT_URL", ""),
        item_code=ITEM_CODE,
        code_prefix=TAG,
        fpb_names=fpb_names,
        so_names=state.get("sos") or [],
    )

    return state


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def phase_cleanup(client, state: dict) -> dict:
    log_section(f"Cleanup — removendo documentos {TAG}-*")

    # Cancela + apaga PRs vinculadas a SOs TEST-LRG
    _, body = call(client, "GET", "/api/resource/Sales Order",
                   params={"filters": json.dumps([["customer", "like", f"{TAG}-%"]]),
                           "fields": '["name","docstatus"]',
                           "limit_page_length": 500})
    for so in (body or {}).get("data") or []:
        _, prs = call(client, "GET", "/api/resource/Production Reservation",
                      params={"filters": json.dumps([["sales_order", "=", so["name"]]]),
                              "fields": '["name","docstatus"]'})
        for pr in (prs or {}).get("data") or []:
            try:
                if pr.get("docstatus") == 1:
                    cancel_doc(client, "Production Reservation", pr["name"])
                call(client, "DELETE", f"/api/resource/Production Reservation/{pr['name']}")
            except Exception:
                pass
        try:
            if so.get("docstatus") == 1:
                cancel_doc(client, "Sales Order", so["name"])
            call(client, "DELETE", f"/api/resource/Sales Order/{so['name']}")
        except Exception as exc:
            log_error(f"  Falha SO {so['name']}: {exc}")
    log_ok("  SOs e PRs removidos")

    # Cancela + apaga FPBs
    _, body = call(client, "GET", "/api/resource/Future Production Batch",
                   params={"filters": json.dumps([["production_code", "like", f"{TAG}-%"]]),
                           "fields": '["name","docstatus"]',
                           "limit_page_length": 500})
    for fpb in (body or {}).get("data") or []:
        try:
            if fpb.get("docstatus") == 1:
                cancel_doc(client, "Future Production Batch", fpb["name"])
            call(client, "DELETE", f"/api/resource/Future Production Batch/{fpb['name']}")
        except Exception as exc:
            log_error(f"  Falha FPB {fpb['name']}: {exc}")
    log_ok("  FPBs removidos")

    # Batches físicos
    _, body = call(client, "GET", "/api/resource/Batch",
                   params={"filters": json.dumps([["batch_id", "like", f"{TAG}-%"]]),
                           "fields": '["name"]',
                           "limit_page_length": 500})
    for b in (body or {}).get("data") or []:
        try:
            call(client, "DELETE", f"/api/resource/Batch/{b['name']}")
        except Exception:
            pass

    # Patients
    _, body = call(client, "GET", "/api/resource/Patient",
                   params={"filters": json.dumps([["patient_name", "like", f"{TAG}-%"]]),
                           "fields": '["name"]', "limit_page_length": 500})
    for p in (body or {}).get("data") or []:
        try:
            call(client, "DELETE", f"/api/resource/Patient/{p['name']}")
        except Exception:
            pass

    # Prescribers
    _, body = call(client, "GET", "/api/resource/Prescriber",
                   params={"filters": json.dumps([["full_name", "like", f"{TAG}-%"]]),
                           "fields": '["name"]', "limit_page_length": 500})
    for p in (body or {}).get("data") or []:
        try:
            call(client, "DELETE", f"/api/resource/Prescriber/{p['name']}")
        except Exception:
            pass

    # Customers
    for name in CUSTOMER_NAMES:
        try:
            call(client, "DELETE", f"/api/resource/Customer/{quote(name, safe='')}")
        except Exception:
            pass

    if STATE_FILE.exists():
        STATE_FILE.unlink()
    log_ok("Cleanup concluído.")
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PHASES = {
    "setup":    phase_setup,
    "fpbs":     phase_fpbs,
    "orders":   phase_orders,
    "produce":  phase_produce,
    "release":  phase_release,
    "allocate": phase_allocate,
    "report":   phase_report,
    "cleanup":  phase_cleanup,
}

ALL_SEQUENCE = ["setup", "fpbs", "orders", "produce", "release", "allocate", "report"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True,
                        choices=list(PHASES.keys()) + ["all"],
                        help="Fase a executar")
    args = parser.parse_args()

    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados — habilite no bench.")
        return 1

    state = load_state()

    phases = ALL_SEQUENCE if args.phase == "all" else [args.phase]
    for phase in phases:
        try:
            state = PHASES[phase](client, state)
        except Exception as exc:
            log_error(f"Phase '{phase}' falhou: {exc}")
            traceback.print_exc()
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
