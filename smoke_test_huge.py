"""
smoke_test_huge.py — Stress test final: 100 FPBs, 30 SOs, 10 produzidos.

Cenário:
  - 100 FPBs × 2.000 ampolas = 200.000 capacidade planejada
  - 10 Customers (PJ com CNPJ)
  - 20 Prescribers (mix CRM/CRO/CRF/CRBM)
  - 100 Patients
  - 30 SOs demandando ~33.000 ampolas (≈ 16-17 lotes)
  - Produção: 10 FPBs full (2.000 cada = 20.000 ampolas)
  - Após release:
      * 10 FPBs liberados completamente
      * 6-7 FPBs com reservas mas SEM produção (aguardando)
      * ~83 FPBs livres (sem demanda)

Ordem (igual ao mundo real):
  1. Cadastros mestres
  2. FPBs (criados primeiro — capacidade declarada)
  3. SOs + reservas auto (FIFO consome FPBs antigos)
  4. Produção de 10 FPBs
  5. Release FIFO
  6. Alocar batch por paciente
  7. Relatório consolidado + URLs

Uso:
    python smoke_test_huge.py --phase all
    python smoke_test_huge.py --phase setup
    ...
    python smoke_test_huge.py --phase cleanup
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
    list_sos_by_prefix,
    print_fpb_table,
    print_pr_table,
    print_so_table,
    print_visibility_hints,
)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

COMPANY = "Injmedpharma"
ITEM_CODE = "TIR00060"
TARGET_WAREHOUSE = "Produtos Acabados - I"
RATE = 100.0

TAG = "DEMO-HUGE"
CODE_PREFIX = f"{TAG}-FPB"
STATE_FILE = Path(".huge_state.json")

NUM_FPBS = 100
QTY_PER_FPB = 2000
NUM_CUSTOMERS = 10
NUM_PRESCRIBERS = 20
NUM_PATIENTS = 100
NUM_SOS = 30
TOTAL_SO_DEMAND = 33000

NUM_FPBS_PRODUCED = 10        # primeiros 10 (FIFO oldest)
PRODUCED_QTY_FULL = 2000      # 10 FPBs com produção full

RANDOM_SEED = 2026


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def call(client, method, path, **kwargs):
    return client._request(method, path, **kwargs)


def submit(client, doctype, name):
    encoded = quote(name, safe="")
    _, body = call(client, "GET", f"/api/resource/{doctype}/{encoded}")
    doc = body.get("data", {})
    call(client, "POST", "/api/method/frappe.client.submit", json_body={"doc": doc})


def cancel(client, doctype, name):
    try:
        call(client, "POST", "/api/method/frappe.client.cancel",
             json_body={"doctype": doctype, "name": name})
    except ErpnextApiError as exc:
        if "Cancelled" not in str(exc) and "Not Submitted" not in str(exc):
            raise


def get_doc(client, doctype, name):
    encoded = quote(name, safe="")
    _, body = call(client, "GET", f"/api/resource/{doctype}/{encoded}")
    return (body or {}).get("data") or {}


def gen_cnpj(idx: int) -> str:
    """CNPJ sintético (só 14 dígitos não triviais)."""
    base = f"{(idx * 13 + 100000000000) % 99999999999999:014d}"
    if base == base[0] * 14:
        base = base[:-1] + "9"
    return base


def gen_cpf(idx: int) -> str:
    base = f"{(idx * 9377 + 100000000) % 99999999999:011d}"
    if base == base[0] * 11:
        base = base[:-1] + "9"
    return base


def distribute_qty(total: int, n_parts: int) -> list[int]:
    if n_parts <= 0:
        return []
    base = total // n_parts
    rest = total - base * n_parts
    return [base + (1 if i < rest else 0) for i in range(n_parts)]


# ---------------------------------------------------------------------------
# Phase 1 — Setup mestre
# ---------------------------------------------------------------------------

CUSTOMER_TEMPLATE = [
    f"{TAG}-Cliente-{i:02d}" for i in range(1, NUM_CUSTOMERS + 1)
]

PRESCRIBER_SEED = []
for i in range(NUM_PRESCRIBERS):
    council_types = ["CRM"] * 12 + ["CRO"] * 4 + ["CRF"] * 2 + ["CRBM"] * 2
    council_states = ["SP", "RJ", "MG", "PR", "RS", "SC", "BA"]
    PRESCRIBER_SEED.append({
        "full_name": f"{TAG}-Prescritor-{i:02d}",
        "cpf": gen_cpf(700 + i),
        "council_type": council_types[i % len(council_types)],
        "council_number": f"{20000 + i * 7:05d}",
        "council_state": council_states[i % len(council_states)],
        "specialty": ["Endocrinologia", "Cardiologia", "Geriatria",
                      "Endodontia", "Farmácia Clínica", "Biomedicina"][i % 6],
    })


def phase_setup(client, state: dict) -> dict:
    log_section(f"Phase 1/7 — Setup base ({NUM_CUSTOMERS} Customers, "
                f"{NUM_PRESCRIBERS} Prescribers, {NUM_PATIENTS} Patients)")

    # Customers (PJ com CNPJ)
    customers = []
    for i, name in enumerate(CUSTOMER_TEMPLATE):
        status, _ = call(client, "GET", f"/api/resource/Customer/{quote(name, safe='')}")
        if status == 200:
            customers.append(name)
            continue
        call(client, "POST", "/api/resource/Customer", json_body={
            "doctype": "Customer",
            "customer_name": name,
            "customer_type": "Company",
            "customer_group": "Comercial",
            "territory": "Brazil",
            "tax_id": gen_cnpj(i + 500),
        })
        customers.append(name)
    log_ok(f"  {len(customers)} Customers prontos")

    # Prescribers
    prescribers = []
    for seed in PRESCRIBER_SEED:
        _, body = call(client, "GET", "/api/resource/Prescriber",
                       params={"filters": json.dumps([["cpf", "=", seed["cpf"]]]),
                               "fields": '["name"]', "limit_page_length": 1})
        existing = (body or {}).get("data") or []
        if existing:
            prescribers.append(existing[0]["name"])
            continue
        _, body = call(client, "POST", "/api/resource/Prescriber", json_body={
            "doctype": "Prescriber",
            "full_name": seed["full_name"],
            "cpf": seed["cpf"],
            "council_type": seed["council_type"],
            "council_number": seed["council_number"],
            "council_state": seed["council_state"],
            "council_status": "Ativo",
            "specialty": seed["specialty"],
        })
        prescribers.append(body["data"]["name"])
    log_ok(f"  {len(prescribers)} Prescribers prontos")

    # Patients
    random.seed(RANDOM_SEED)
    patients = []
    for i in range(NUM_PATIENTS):
        cpf = gen_cpf(1000 + i)
        pname = f"{TAG}-Paciente-{i:03d}"
        _, body = call(client, "GET", "/api/resource/Patient",
                       params={"filters": json.dumps([["cpf", "=", cpf]]),
                               "fields": '["name"]', "limit_page_length": 1})
        existing = (body or {}).get("data") or []
        if existing:
            pac_name = existing[0]["name"]
        else:
            _, body = call(client, "POST", "/api/resource/Patient", json_body={
                "doctype": "Patient",
                "patient_name": pname,
                "cpf": cpf,
                "gender": "Feminino" if i % 2 == 0 else "Masculino",
                "country": "Brazil",
                "default_prescriber": prescribers[i % len(prescribers)],
                "mobile": f"11{i:09d}",
            })
            pac_name = body["data"]["name"]
        patients.append({
            "name": pac_name,
            "patient_name": pname,
            "cpf": cpf,
            "default_prescriber": prescribers[i % len(prescribers)],
        })
    log_ok(f"  {len(patients)} Patients prontos")

    state["customers"] = customers
    state["prescribers"] = prescribers
    state["patients"] = patients
    save_state(state)
    return state


# ---------------------------------------------------------------------------
# Phase 2 — 100 FPBs
# ---------------------------------------------------------------------------

def phase_fpbs(client, state: dict) -> dict:
    log_section(f"Phase 2/7 — Criar {NUM_FPBS} FPBs × {QTY_PER_FPB}")

    fpb_names = []
    base_date = dt.date.today() + dt.timedelta(days=7)
    t0 = time.time()

    for i in range(NUM_FPBS):
        prod_date = (base_date + dt.timedelta(days=i)).isoformat()
        code = f"{CODE_PREFIX}-{i:03d}-{int(time.time()) % 10000}"
        try:
            _, body = call(client, "POST", "/api/resource/Future Production Batch",
                           json_body={
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
            submit(client, "Future Production Batch", fpb_name)
            fpb_names.append(fpb_name)
            if (i + 1) % 10 == 0:
                log_ok(f"  {i+1}/{NUM_FPBS} criados (último: {fpb_name})")
        except ErpnextApiError as exc:
            log_error(f"  FPB {i+1} falhou: {exc}")

    state["fpbs"] = fpb_names
    save_state(state)
    log_ok(f"  Total FPBs criados: {len(fpb_names)} em {time.time()-t0:.1f}s")
    log_ok(f"  Capacidade total declarada: {len(fpb_names) * QTY_PER_FPB:,} ampolas")
    return state


# ---------------------------------------------------------------------------
# Phase 3 — 30 SOs com reserva auto
# ---------------------------------------------------------------------------

def phase_orders(client, state: dict) -> dict:
    log_section(f"Phase 3/7 — Criar {NUM_SOS} SOs (~{TOTAL_SO_DEMAND} ampolas)")

    customers = state.get("customers") or []
    patients = state.get("patients") or []
    if not customers or not patients:
        log_error("Phase 1 não rodada.")
        return state

    # Distribui demanda em 30 SOs
    random.seed(RANDOM_SEED + 1)
    qtys = []
    remaining = TOTAL_SO_DEMAND
    for i in range(NUM_SOS - 1):
        avg = remaining // (NUM_SOS - i)
        q = random.randint(int(avg * 0.6), int(avg * 1.4))
        q = max(200, min(1800, q))
        qtys.append(q)
        remaining -= q
    qtys.append(max(200, remaining))

    so_names = []
    t0 = time.time()
    for i, qty in enumerate(qtys):
        cust = customers[i % len(customers)]
        # 3-5 pacientes por SO
        n_patients = random.randint(3, 5)
        chosen = random.sample(patients, k=min(n_patients, len(patients)))
        shares = distribute_qty(qty, n_patients)

        rows = []
        for pac, share in zip(chosen, shares):
            if share <= 0:
                continue
            rows.append({
                "patient": pac["name"],
                "item_code": ITEM_CODE,
                "qty": share,
                "prescriber": pac["default_prescriber"],
            })
        # Ajusta soma
        diff = qty - sum(r["qty"] for r in rows)
        if diff != 0 and rows:
            rows[0]["qty"] = rows[0]["qty"] + diff

        so_payload = {
            "doctype": "Sales Order",
            "customer": cust,
            "company": COMPANY,
            "transaction_date": dt.date.today().isoformat(),
            "delivery_date": (dt.date.today() + dt.timedelta(days=60)).isoformat(),
            "currency": "BRL",
            "selling_price_list": "Venda Padrão",
            "price_list_currency": "BRL",
            "plc_conversion_rate": 1,
            "conversion_rate": 1,
            "items": [{
                "item_code": ITEM_CODE,
                "qty": qty,
                "rate": RATE,
                "delivery_date": (dt.date.today() + dt.timedelta(days=60)).isoformat(),
                "warehouse": TARGET_WAREHOUSE,
            }],
            "fp_patients": rows,
        }
        try:
            _, body = call(client, "POST", "/api/resource/Sales Order", json_body=so_payload)
            so_name = body["data"]["name"]
            submit(client, "Sales Order", so_name)
            client.call_method("future_production_auto_reserve_sales_order",
                               {"sales_order": so_name})
            so_names.append(so_name)
            if (i + 1) % 5 == 0:
                log_ok(f"  {i+1}/{NUM_SOS} SOs criados + reservados (último: {so_name} qty={qty})")
        except ErpnextApiError as exc:
            log_error(f"  SO {i+1} falhou: {exc}")

    state["sos"] = so_names
    save_state(state)
    log_ok(f"  Total SOs: {len(so_names)} em {time.time()-t0:.1f}s")
    log_ok(f"  Demanda total reservada: ~{sum(qtys):,} ampolas")
    return state


# ---------------------------------------------------------------------------
# Phase 4 — Produzir 10 FPBs full
# ---------------------------------------------------------------------------

def phase_produce(client, state: dict) -> dict:
    log_section(f"Phase 4/7 — Produzir {NUM_FPBS_PRODUCED} FPBs full ({PRODUCED_QTY_FULL} cada)")

    fpb_names = state.get("fpbs") or []
    if not fpb_names:
        log_error("Phase 2 não rodada.")
        return state

    # Produz os PRIMEIROS NUM_FPBS_PRODUCED (mais antigos por planned_production_date)
    targets = fpb_names[:NUM_FPBS_PRODUCED]
    batches = []
    t0 = time.time()

    for i, fpb in enumerate(targets):
        batch_id = f"{TAG}-LOT-{i:03d}-{int(time.time()) % 10000}"
        try:
            _, body = call(client, "POST", "/api/resource/Batch", json_body={
                "doctype": "Batch",
                "batch_id": batch_id,
                "item": ITEM_CODE,
                "batch_qty": PRODUCED_QTY_FULL,
            })
            actual = body["data"]["name"]
            call(client, "PUT", f"/api/resource/Future Production Batch/{fpb}",
                 json_body={"produced_qty": PRODUCED_QTY_FULL, "batch_no": actual})
            batches.append({"fpb": fpb, "batch": actual, "produced": PRODUCED_QTY_FULL})
            log_ok(f"  {i+1}/{NUM_FPBS_PRODUCED}: {fpb} ← {actual} (qty={PRODUCED_QTY_FULL})")
        except ErpnextApiError as exc:
            log_error(f"  Produção {fpb} falhou: {exc}")

    state["batches"] = batches
    save_state(state)
    total = sum(b["produced"] for b in batches)
    log_ok(f"  Total produzido: {total:,} ampolas em {time.time()-t0:.1f}s")
    return state


# ---------------------------------------------------------------------------
# Phase 5 — Release FIFO
# ---------------------------------------------------------------------------

def phase_release(client, state: dict) -> dict:
    log_section(f"Phase 5/7 — Liberar reservas dos {NUM_FPBS_PRODUCED} FPBs produzidos")

    batches = state.get("batches") or []
    if not batches:
        log_error("Phase 4 não rodada.")
        return state

    total_released = 0
    for b in batches:
        try:
            resp = client.call_method("future_production_release_batch",
                                       {"future_production_batch": b["fpb"]})
            msg = (resp or {}).get("message") or {}
            log_ok(f"  {b['fpb']}: liberado {msg.get('released_qty'):.0f}, "
                   f"pending {msg.get('pending_release_qty'):.0f}")
            total_released += float(msg.get("released_qty") or 0)
        except ErpnextApiError as exc:
            log_error(f"  Release {b['fpb']} falhou: {exc}")

    log_ok(f"  Total liberado: {total_released:,.0f} ampolas")
    return state


# ---------------------------------------------------------------------------
# Phase 6 — Alocar batches por paciente
# ---------------------------------------------------------------------------

def phase_allocate(client, state: dict) -> dict:
    log_section("Phase 6/7 — Alocar batch por paciente (fp_patients.batch_no)")

    so_names = state.get("sos") or []
    total_alloc = 0
    sos_with = 0
    for so in so_names:
        try:
            resp = client.call_method("future_production_allocate_patient_batches",
                                       {"sales_order": so})
            n = int((resp or {}).get("message", {}).get("allocated_rows") or 0)
            if n > 0:
                total_alloc += n
                sos_with += 1
        except ErpnextApiError as exc:
            log_error(f"  Alloc {so}: {exc}")

    log_ok(f"  {total_alloc} linhas de pacientes alocadas em {sos_with} SOs")
    return state


# ---------------------------------------------------------------------------
# Phase 7 — Relatório consolidado
# ---------------------------------------------------------------------------

def phase_report(client, state: dict) -> dict:
    log_section("Phase 7/7 — Relatório consolidado")

    # Snapshot FPBs (todos do teste)
    fpbs = list_fpbs(client, item_code=ITEM_CODE, code_prefix=TAG)
    log_section(f"FPBs do teste ({TAG}) — {len(fpbs)} total")

    # Agrupa por status
    by_status = {}
    totals = {"planned": 0, "reserved": 0, "available": 0,
              "produced": 0, "released": 0, "pending": 0}
    for f in fpbs:
        st = f.get("status", "?")
        by_status[st] = by_status.get(st, 0) + 1
        for k, kf in (("planned", "planned_qty"), ("reserved", "reserved_qty"),
                       ("available", "available_qty"), ("produced", "produced_qty"),
                       ("released", "released_qty"), ("pending", "pending_release_qty")):
            try:
                totals[k] += float(f.get(kf) or 0)
            except (TypeError, ValueError):
                pass

    print("\n  Por status:")
    for st, n in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f"    {st:<26} {n:>4} FPBs")

    print(f"\n  Totais ({len(fpbs)} FPBs):")
    print(f"    planned   = {totals['planned']:>10,.0f} ampolas")
    print(f"    reserved  = {totals['reserved']:>10,.0f}")
    print(f"    available = {totals['available']:>10,.0f}")
    print(f"    produced  = {totals['produced']:>10,.0f}")
    print(f"    released  = {totals['released']:>10,.0f}")
    print(f"    pending   = {totals['pending']:>10,.0f}")

    # SOs
    sos = list_sos_by_prefix(client, f"{TAG}-Cliente-")
    total_value = sum(float(s.get("grand_total") or 0) for s in sos)
    log_section(f"Sales Orders ({len(sos)})")
    print(f"  Valor total: R$ {total_value:,.2f}")

    # Pendências
    pending_prs = [p for p in list_prs_by_fpbs(client, state.get("fpbs", []))
                   if float(p.get("pending_qty") or 0) > 0]
    log_section(f"PRs com pendência ({len(pending_prs)})")
    total_pending = sum(float(p.get("pending_qty") or 0) for p in pending_prs)
    print(f"  Total pendente: {total_pending:,.0f} ampolas")
    print(f"  (ampolas RESERVADAS por clientes aguardando FPBs futuros produzirem)")

    # URLs
    base = os.environ.get("ERPNEXT_URL", "").rstrip("/")
    log_section("LINKS PARA INSPEÇÃO NO BROWSER")
    print(f"\n  ╔═══ Workspace Produção Futura ═══╗")
    print(f"  {base}/app/producao-futura")
    print(f"\n  ╔═══ Listas ═══╗")
    print(f"  FPBs:        {base}/app/future-production-batch")
    print(f"  Reservas:    {base}/app/production-reservation")
    print(f"  SOs:         {base}/app/sales-order")
    print(f"  Patients:    {base}/app/patient")
    print(f"  Prescribers: {base}/app/prescriber")
    print(f"  Customers:   {base}/app/customer")
    print(f"  Batches:     {base}/app/batch")
    print(f"\n  ╔═══ Relatórios customizados ═══╗")
    print(f"  Mapa Produção:      {base}/app/query-report/Mapa%20de%20Produção")
    print(f"  Saldo por Lote:     {base}/app/query-report/Saldo%20por%20Lote")
    print(f"  Reservas Pedido:    {base}/app/query-report/Reservas%20por%20Pedido")
    print(f"  Pendências:         {base}/app/query-report/Pedidos%20Pendentes%20de%20Liberação")
    print(f"\n  ╔═══ Filtros úteis nas listas ═══╗")
    print(f"  FPBs do teste:")
    print(f"    {base}/app/future-production-batch?production_code=%{TAG}%")
    print(f"  SOs do teste:")
    print(f"    {base}/app/sales-order?customer=%{TAG}-Cliente-%")

    return state


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def phase_cleanup(client, state: dict) -> dict:
    log_section(f"Cleanup — removendo {TAG}-*")

    # Reuse deep_cleanup logic
    sys.path.insert(0, ".")
    from tools.deep_cleanup import cleanup as deep
    deep(client, [TAG])

    if STATE_FILE.exists():
        STATE_FILE.unlink()
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True,
                        choices=list(PHASES.keys()) + ["all"])
    args = parser.parse_args()

    client = client_from_env()
    if not client.server_script_enabled():
        log_error("Server Scripts desabilitados.")
        return 1

    state = load_state()
    phases = ALL_SEQUENCE if args.phase == "all" else [args.phase]

    for ph in phases:
        try:
            state = PHASES[ph](client, state)
        except Exception as exc:
            log_error(f"Fase '{ph}' falhou: {exc}")
            traceback.print_exc()
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
