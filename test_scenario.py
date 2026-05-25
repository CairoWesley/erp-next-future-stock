"""
test_scenario.py — executa o cenário de aceite da seção 23 da documentação.

Cenário:
  - Item: TIR00060 (Tirzepatida 60mg/2,4ml) — único item com estoque no ambiente
  - Warehouse: Produtos Acabados - I
  - Company: Injmedpharma
  - Cria 1 Future Production Batch com 2.000 unidades
  - Cria 4 Customers + 4 Sales Orders: 300, 500, 700, 500
  - Reserva todos via API future_production_reserve_sales_order_item
  - Esperado: reserved=2000, available=0, status="Totalmente Reservada"
  - Marca produced_qty=1850 + batch_no
  - Chama future_production_release_batch
  - Esperado: SO-0001=300, SO-0002=500, SO-0003=700, SO-0004=350 liberados
              SO-0004 fica com 150 pendente

Cleanup: cancela e apaga todos os documentos TEST-PF-* antes de rodar.
"""

from __future__ import annotations

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
CUSTOMERS = [
    ("TEST-PF-Alfa",  "Cliente Teste Alfa  - Reserva Produção Futura"),
    ("TEST-PF-Beta",  "Cliente Teste Beta  - Reserva Produção Futura"),
    ("TEST-PF-Gama",  "Cliente Teste Gama  - Reserva Produção Futura"),
    ("TEST-PF-Delta", "Cliente Teste Delta - Reserva Produção Futura"),
]
QUANTITIES = [300, 500, 700, 500]   # totais 2000
PLANNED_QTY = 2000
DEFAULT_PRODUCED_QTY = 1850         # 150 ficarão pendentes em SO-0004 (cenário seção 23)
TODAY = dt.date.today().isoformat()
DELIVERY_DATE = (dt.date.today() + dt.timedelta(days=30)).isoformat()
PRODUCTION_DATE = (dt.date.today() + dt.timedelta(days=14)).isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def call(client, method: str, path: str, **kwargs):
    return client._request(method, path, **kwargs)


def submit_doc(client, doctype: str, name: str) -> None:
    """Submete um documento buscando antes para evitar TimestampMismatchError."""
    encoded = name.replace(" ", "%20").replace("/", "%2F")
    _, body = call(client, "GET", f"/api/resource/{doctype}/{encoded}")
    doc = body.get("data", {})
    call(client, "POST", "/api/method/frappe.client.submit", json_body={"doc": doc})


def cancel_doc(client, doctype: str, name: str) -> None:
    """Cancela um documento submetido."""
    call(client, "POST", "/api/method/frappe.client.cancel",
         json_body={"doctype": doctype, "name": name})


def get_or_create_customer(client, name: str, customer_name: str) -> str:
    s, body = call(client, "GET", f"/api/resource/Customer/{name.replace(' ', '%20')}")
    if s == 200:
        log_ok(f"Customer {name} já existe")
        return name
    log_ok(f"Criando Customer {name}")
    _, body = call(client, "POST", "/api/resource/Customer", json_body={
        "doctype": "Customer",
        "customer_name": name,
        "customer_type": "Individual",
        "customer_group": "Comercial",
        "territory": "Brazil",
    })
    return body["data"]["name"]


def cleanup(client) -> None:
    log_section("Cleanup — removendo documentos TEST-PF-*")

    # Cancela e deleta Production Reservations
    _, body = call(client, "GET", "/api/resource/Production Reservation",
                   params={"fields": '["name","docstatus"]', "limit_page_length": 200})
    for pr in (body or {}).get("data") or []:
        try:
            if pr.get("docstatus") == 1:
                cancel_doc(client, "Production Reservation", pr["name"])
            call(client, "DELETE", f"/api/resource/Production Reservation/{pr['name']}")
            log_ok(f"  PR removida: {pr['name']}")
        except Exception as exc:
            log_error(f"  Falha PR {pr['name']}: {exc}")

    # Cancela e deleta Future Production Batches TEST-PF-*
    _, body = call(client, "GET", "/api/resource/Future Production Batch",
                   params={
                       "fields": '["name","docstatus","production_code"]',
                       "filters": '[["production_code","like","TEST-PF-%"]]',
                       "limit_page_length": 200,
                   })
    for fpb in (body or {}).get("data") or []:
        try:
            if fpb.get("docstatus") == 1:
                cancel_doc(client, "Future Production Batch", fpb["name"])
            call(client, "DELETE", f"/api/resource/Future Production Batch/{fpb['name']}")
            log_ok(f"  FPB removida: {fpb['name']}")
        except Exception as exc:
            log_error(f"  Falha FPB {fpb['name']}: {exc}")

    # Cancela e deleta Sales Orders dos customers de teste
    test_customers = [c[0] for c in CUSTOMERS]
    _, body = call(client, "GET", "/api/resource/Sales Order",
                   params={
                       "fields": '["name","docstatus","customer"]',
                       "filters": json.dumps([["customer", "in", test_customers]]),
                       "limit_page_length": 200,
                   })
    for so in (body or {}).get("data") or []:
        try:
            if so.get("docstatus") == 1:
                cancel_doc(client, "Sales Order", so["name"])
            call(client, "DELETE", f"/api/resource/Sales Order/{so['name']}")
            log_ok(f"  SO removido: {so['name']} ({so['customer']})")
        except Exception as exc:
            log_error(f"  Falha SO {so['name']}: {exc}")


# ---------------------------------------------------------------------------
# Cenário
# ---------------------------------------------------------------------------

def run(client, produced_qty: float) -> dict[str, Any]:
    results: dict[str, Any] = {"produced_qty": produced_qty}

    # ----- 1. Customers --------------------------------------------------
    log_section("1/6 — Customers de teste")
    customer_names = []
    for name, full in CUSTOMERS:
        customer_names.append(get_or_create_customer(client, name, full))
    results["customers"] = customer_names

    # ----- 2. Future Production Batch -----------------------------------
    log_section("2/6 — Criando Future Production Batch (2.000 unid.)")
    production_code = f"TEST-PF-{int(time.time())}"
    fpb_payload = {
        "doctype": "Future Production Batch",
        "production_code": production_code,
        "company": COMPANY,
        "item_code": ITEM_CODE,
        "planned_qty": PLANNED_QTY,
        "planned_production_date": PRODUCTION_DATE,
        "target_warehouse": TARGET_WAREHOUSE,
        "status": "Aberta para Reserva",
    }
    _, body = call(client, "POST", "/api/resource/Future Production Batch",
                   json_body=fpb_payload)
    fpb_name = body["data"]["name"]
    log_ok(f"FPB criada: {fpb_name} (code={production_code})")

    # Submit
    submit_doc(client, "Future Production Batch", fpb_name)
    log_ok(f"FPB {fpb_name} submetida")
    results["fpb"] = fpb_name

    # ----- 3. Sales Orders -----------------------------------------------
    log_section("3/6 — Sales Orders (300, 500, 700, 500)")
    sales_orders = []
    for cust, qty in zip(customer_names, QUANTITIES):
        so_payload = {
            "doctype": "Sales Order",
            "customer": cust,
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
                "qty": qty,
                "rate": 100,
                "delivery_date": DELIVERY_DATE,
                "warehouse": TARGET_WAREHOUSE,
            }],
        }
        try:
            _, body = call(client, "POST", "/api/resource/Sales Order", json_body=so_payload)
            so_name = body["data"]["name"]
            soi_name = body["data"]["items"][0]["name"]
            submit_doc(client, "Sales Order", so_name)
            log_ok(f"  SO {so_name} ({cust} qty={qty}) submetido — item row={soi_name}")
            sales_orders.append({
                "name": so_name, "customer": cust, "qty": qty, "soi": soi_name
            })
        except Exception as exc:
            log_error(f"  Falha SO para {cust}: {exc}")
            raise
    results["sales_orders"] = sales_orders

    # ----- 4. Reservas via API ------------------------------------------
    log_section("4/6 — Reservando via future_production_reserve_sales_order_item")
    reservations = []
    for so in sales_orders:
        payload = {
            "sales_order": so["name"],
            "sales_order_item": so["soi"],
            "future_production_batch": fpb_name,
            "qty": so["qty"],
            "priority": 100,
        }
        try:
            body = client.call_method("future_production_reserve_sales_order_item", payload)
            msg = (body or {}).get("message") or {}
            log_ok(f"  Reservada: {msg.get('reservation')} ({so['customer']} qty={so['qty']}) "
                   f"available_after={msg.get('available_qty_after')}")
            reservations.append(msg)
        except Exception as exc:
            log_error(f"  Falha reserva para {so['name']}: {exc}")
            raise
    results["reservations"] = reservations

    # ----- 5. Marcar produção real e batch ------------------------------
    log_section(f"5/6 — Marcando produção real ({produced_qty:g} unid) + batch")
    batch_name = f"TEST-PF-LOT-{int(time.time())}"

    _, body = call(client, "POST", "/api/resource/Batch", json_body={
        "doctype": "Batch",
        "batch_id": batch_name,
        "item": ITEM_CODE,
        "batch_qty": produced_qty,
    })
    actual_batch_name = body["data"]["name"]
    log_ok(f"Batch criado: {actual_batch_name}")

    _, body = call(client, "PUT", f"/api/resource/Future Production Batch/{fpb_name}",
                   json_body={"produced_qty": produced_qty, "batch_no": actual_batch_name})
    log_ok(f"FPB atualizada: produced_qty={produced_qty:g}, batch={actual_batch_name}")
    results["batch"] = actual_batch_name

    # ----- 6. Liberar reservas via API ----------------------------------
    log_section("6/6 — Liberando reservas via future_production_release_batch")
    body = client.call_method("future_production_release_batch",
                              {"future_production_batch": fpb_name})
    msg = (body or {}).get("message") or {}
    log_ok(f"Release: count={msg.get('released_count')}, "
           f"remaining={msg.get('remaining_to_release')}, "
           f"released_qty={msg.get('released_qty')}, "
           f"pending={msg.get('pending_release_qty')}")
    results["release_result"] = msg

    return results


# ---------------------------------------------------------------------------
# Análise
# ---------------------------------------------------------------------------

def _expected_distribution(produced: float) -> list[tuple[str, int, float, float, str]]:
    """Aplica a regra FIFO sobre QUANTITIES para gerar o esperado por reserva."""
    remaining = produced
    rows: list[tuple[str, int, float, float, str]] = []
    for i, qty in enumerate(QUANTITIES, start=1):
        take = max(0.0, min(qty, remaining))
        pending = qty - take
        if take >= qty and take > 0:
            status = "Liberado"
        elif take > 0:
            status = "Parcialmente Liberado"
        else:
            status = "Reservado"
        rows.append((f"SO-{i:04d}", qty, take, pending, status))
        remaining = max(0.0, remaining - take)
    return rows


def analyze(client, results: dict[str, Any]) -> int:
    log_section("Análise — esperado vs obtido")

    produced = float(results.get("produced_qty", 0))
    distributed = min(produced, sum(QUANTITIES))
    fpb_name = results["fpb"]
    _, body = call(client, "GET", f"/api/resource/Future Production Batch/{fpb_name}")
    fpb = body["data"]

    expected_fpb = {
        "planned_qty": 2000,
        "reserved_qty": 2000,
        "available_qty": 0,
        "produced_qty": produced,
        "released_qty": distributed,
        "pending_release_qty": produced - distributed,
    }

    print(f"\n  Future Production Batch: {fpb_name}")
    print(f"  Status: {fpb.get('status')}")
    print(f"  {'Campo':<24} {'Esperado':>12} {'Obtido':>12}   OK")
    print(f"  {'-' * 60}")
    fpb_ok = True
    for k, expected in expected_fpb.items():
        got = float(fpb.get(k) or 0)
        ok = "OK" if abs(got - expected) < 0.01 else "FAIL"
        if ok == "FAIL":
            fpb_ok = False
        print(f"  {k:<24} {expected:>12} {got:>12}   {ok}")

    expected_so = _expected_distribution(produced)
    print(f"\n  Production Reservations")
    print(f"  {'Pedido':<22} {'Cli':<12} {'Reserv':>7} {'Liber':>7} {'Pend':>5} "
          f"{'Status':<22} OK")
    print(f"  {'-' * 90}")

    prs_ok = True
    _, body = call(client, "GET", "/api/resource/Production Reservation",
                   params={
                       "fields": '["name","sales_order","customer","reserved_qty","released_qty","pending_qty","status"]',
                       "filters": json.dumps([["future_production_batch", "=", fpb_name]]),
                       "order_by": "creation asc",
                       "limit_page_length": 50,
                   })
    prs = (body or {}).get("data") or []
    for i, pr in enumerate(prs):
        expected_idx = i if i < len(expected_so) else None
        if expected_idx is not None:
            _label, _exp_res, exp_rel, exp_pend, exp_status = expected_so[expected_idx]
            rel_ok = abs(float(pr["released_qty"]) - exp_rel) < 0.01
            pend_ok = abs(float(pr["pending_qty"]) - exp_pend) < 0.01
            status_ok = pr["status"] == exp_status
            ok = "OK" if (rel_ok and pend_ok and status_ok) else "FAIL"
            if ok == "FAIL":
                prs_ok = False
        else:
            ok = "?"
        print(f"  {pr['sales_order']:<22} {(pr['customer'] or '')[:10]:<12} "
              f"{pr['reserved_qty']:>7.0f} {pr['released_qty']:>7.0f} {pr['pending_qty']:>5.0f} "
              f"{pr['status']:<22} {ok}")

    print()
    if fpb_ok and prs_ok:
        log_ok("CENÁRIO APROVADO — todos os critérios da seção 23 foram atendidos.")
        return 0
    log_error("CENÁRIO FALHOU — divergências detectadas acima.")
    return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # arg simples: --produced-qty N (default 1850)
    produced_qty = float(DEFAULT_PRODUCED_QTY)
    for i, arg in enumerate(sys.argv):
        if arg == "--produced-qty" and i + 1 < len(sys.argv):
            produced_qty = float(sys.argv[i + 1])
            break
        if arg.startswith("--produced-qty="):
            produced_qty = float(arg.split("=", 1)[1])
            break

    client = client_from_env()

    log_section("Pré-check: server_script_enabled")
    if not client.server_script_enabled():
        log_error(
            "Server Scripts estão DESABILITADOS neste site.\n"
            "Habilite no servidor (bench ou container Docker):\n"
            "    bench --site erp.injemedpharma.com.br set-config -g server_script_enabled 1\n"
            "    bench restart\n"
            "Sem isso o módulo não roda — nem validações, nem endpoints."
        )
        return 1
    log_ok("server_script_enabled = True")
    log_ok(f"Cenário: planned={PLANNED_QTY}, produced={produced_qty:g}, "
           f"pedidos={QUANTITIES}")

    if "--no-cleanup" not in sys.argv:
        cleanup(client)

    try:
        results = run(client, produced_qty=produced_qty)
    except Exception as exc:
        log_error(f"Cenário interrompido: {exc}")
        traceback.print_exc()
        return 1

    return analyze(client, results)


if __name__ == "__main__":
    raise SystemExit(main())
