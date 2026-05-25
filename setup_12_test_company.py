"""
setup_12_test_company.py — Cria Company adicional (ambiente de teste isolado).

Cria uma segunda Company no mesmo ERPNext, com toda a infra base necessária
pra rodar smoke tests sem misturar com dados de produção:
  - Company (root accounting tree + abbreviation)
  - Warehouses (Stores, WIP, Finished Goods)
  - Customer Group, Territory (se faltarem)
  - Price List
  - Mode of Payment

Não duplica DocTypes custom (FPB, Patient, Prescriber, Dispensation) — esses
são globais e funcionam pra qualquer Company via campo `company`.

Uso:
    python setup_12_test_company.py                          # cria TEST-CO Ltda
    python setup_12_test_company.py --name "Empresa Teste"   # nome custom
    python setup_12_test_company.py --abbr "TEST"            # abrev custom
    python setup_12_test_company.py --uninstall              # remove TEST-CO

Após criar:
    export ERPNEXT_COMPANY="TEST-CO Ltda"
    python smoke_test_huge.py --phase all
"""

from __future__ import annotations

import argparse
import sys

from lib.erpnext_api import ErpnextApiError, client_from_env, log_error, log_ok, log_section


DEFAULT_NAME = "TEST-CO Ltda"
DEFAULT_ABBR = "TC"
DEFAULT_COUNTRY = "Brazil"
DEFAULT_CURRENCY = "BRL"


def get_or_404(client, doctype: str, name: str):
    status, body = client._request("GET", f"/api/resource/{doctype}/{name.replace(' ', '%20')}")
    return (body or {}).get("data") if status == 200 else None


def install(name: str, abbr: str) -> int:
    client = client_from_env()

    log_section(f"Criando Company de teste: {name} (abbr={abbr})")

    # 1) Company
    existing = get_or_404(client, "Company", name)
    if existing:
        log_ok(f"Company {name} já existe")
    else:
        try:
            client._request("POST", "/api/resource/Company", json_body={
                "doctype": "Company",
                "company_name": name,
                "abbr": abbr,
                "country": DEFAULT_COUNTRY,
                "default_currency": DEFAULT_CURRENCY,
                "chart_of_accounts": "Standard",
                "create_chart_of_accounts_based_on": "Standard Template",
                "domain": "Manufacturing",
            })
            log_ok(f"Company {name} criada")
        except ErpnextApiError as exc:
            log_error(f"Falha criar Company: {exc}")
            return 1

    # 2) Warehouses (criados automaticamente pela Company, mas reforçamos)
    log_section("Warehouses padrão")
    warehouse_seed = [
        ("Stores", "Stores", "Group", 0),
        ("Produtos Acabados", "Produtos Acabados", "Warehouse", 1),
        ("Work In Progress", "Work In Progress", "Warehouse", 1),
        ("Matérias Primas", "Matérias Primas", "Warehouse", 1),
    ]
    for label, wh_name_base, wh_type, is_leaf in warehouse_seed:
        full_name = f"{wh_name_base} - {abbr}"
        existing = get_or_404(client, "Warehouse", full_name)
        if existing:
            log_ok(f"  Warehouse {full_name} já existe")
            continue
        try:
            payload = {
                "doctype": "Warehouse",
                "warehouse_name": wh_name_base,
                "company": name,
                "is_group": 0 if is_leaf else 1,
            }
            client._request("POST", "/api/resource/Warehouse", json_body=payload)
            log_ok(f"  Warehouse {full_name} criado")
        except ErpnextApiError as exc:
            log_error(f"  Warehouse {full_name}: {exc}")

    # 3) Customer Group (idempotente)
    log_section("Customer Group + Territory")
    for grp in ["Comercial"]:
        if not get_or_404(client, "Customer Group", grp):
            try:
                client._request("POST", "/api/resource/Customer Group", json_body={
                    "doctype": "Customer Group",
                    "customer_group_name": grp,
                    "parent_customer_group": "All Customer Groups",
                    "is_group": 0,
                })
                log_ok(f"  Customer Group {grp} criado")
            except ErpnextApiError as exc:
                log_error(f"  {grp}: {exc}")
        else:
            log_ok(f"  Customer Group {grp} já existe")

    # 4) Territory
    for terr in ["Brazil"]:
        if not get_or_404(client, "Territory", terr):
            try:
                client._request("POST", "/api/resource/Territory", json_body={
                    "doctype": "Territory",
                    "territory_name": terr,
                    "parent_territory": "All Territories",
                    "is_group": 0,
                })
                log_ok(f"  Territory {terr} criado")
            except ErpnextApiError as exc:
                log_error(f"  {terr}: {exc}")
        else:
            log_ok(f"  Territory {terr} já existe")

    # 5) Price List
    log_section("Price List")
    pl_name = "Venda Padrão"
    if not get_or_404(client, "Price List", pl_name):
        try:
            client._request("POST", "/api/resource/Price List", json_body={
                "doctype": "Price List",
                "price_list_name": pl_name,
                "currency": DEFAULT_CURRENCY,
                "selling": 1,
                "enabled": 1,
            })
            log_ok(f"  Price List {pl_name} criada")
        except ErpnextApiError as exc:
            log_error(f"  {pl_name}: {exc}")
    else:
        log_ok(f"  Price List {pl_name} já existe")

    # 6) Mode of Payment (Pix + Boleto + Transferência)
    log_section("Modes of Payment")
    for mop in ["Pix", "Boleto", "Transferência Bancária", "Dinheiro"]:
        if not get_or_404(client, "Mode of Payment", mop):
            try:
                client._request("POST", "/api/resource/Mode of Payment", json_body={
                    "doctype": "Mode of Payment",
                    "mode_of_payment": mop,
                    "type": "General",
                    "enabled": 1,
                })
                log_ok(f"  MoP {mop} criado")
            except ErpnextApiError as exc:
                log_error(f"  {mop}: {exc}")
        else:
            log_ok(f"  MoP {mop} já existe")

    log_section("PRÓXIMOS PASSOS")
    print(f"""
    Pra rodar smoke tests nessa nova company:

      export ERPNEXT_COMPANY="{name}"
      python smoke_test_huge.py --phase all

    Pra alternar entre companies no .env:

      ERPNEXT_COMPANY={name}                  # ambiente teste
      ERPNEXT_COMPANY=Sua Empresa Ltda        # ambiente produção (default)

    UI — navegar entre companies:

      Topo direito → seu avatar → My Settings → Default Company

    Workspace ERPNext mostra dados por company automaticamente.
    """)

    return 0


def uninstall(name: str, abbr: str) -> int:
    client = client_from_env()
    log_section(f"Removendo Company {name}")

    # Apaga warehouses primeiro
    for label in ["Produtos Acabados", "Work In Progress", "Matérias Primas", "Stores"]:
        full = f"{label} - {abbr}"
        try:
            client._request("DELETE", f"/api/resource/Warehouse/{full.replace(' ', '%20')}")
            log_ok(f"  Warehouse {full} removido")
        except ErpnextApiError:
            pass

    # Apaga company
    try:
        client._request("DELETE", f"/api/resource/Company/{name.replace(' ', '%20')}")
        log_ok(f"Company {name} removida")
    except ErpnextApiError as exc:
        log_error(f"Falha remover Company: {exc}")
        log_error("Dica: ERPNext bloqueia delete se houver SOs/SIs/Stock Entries vinculados.")
        log_error("Apague esses docs primeiro.")
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--abbr", default=DEFAULT_ABBR)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()

    if args.uninstall:
        return uninstall(args.name, args.abbr)
    return install(args.name, args.abbr)


if __name__ == "__main__":
    sys.exit(main())
