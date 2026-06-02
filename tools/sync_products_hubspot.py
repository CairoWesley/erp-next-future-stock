"""
sync_products_hubspot.py — sync de produtos HubSpot → ERPNext + write-back SKU.

Fluxo:
    1. Lista todos products do HubSpot (paginação automática)
    2. Filtra lixo (nomes em SKIP_NAMES: "teste", "FRETE")
    3. Dedup por nome canônico (case-insensitive, com normalização especial pra Tirzepatida)
    4. Pra cada nome único:
        a. Match com Item ERPNext existente por item_name → reusa item_code
        b. Senão cria Item novo (autoname gera SKU 00001+, has_batch_no=1)
    5. Write-back SKU no HubSpot:
        a. Update primeiro hubspot_id de cada grupo com hs_sku = item_code
        b. Renomeia duplicatas com prefixo "[DUP] " + descrição apontando canonical
        c. (opcional) --archive-dups: archive em batch via API

Idempotente. Re-rodadas:
    - Item ERPNext já existe (mesmo item_name) → reusa
    - HubSpot product já tem hs_sku → skip (não sobrescreve)

Requer:
    - .env com ERPNEXT_URL, ERPNEXT_API_KEY, ERPNEXT_API_SECRET
    - .env com HUBSPOT_ACCESS_TOKEN (Private App, scopes products.read+write)

Uso:
    python tools/sync_products_hubspot.py
    python tools/sync_products_hubspot.py --dry-run
    python tools/sync_products_hubspot.py --archive-dups
    python tools/sync_products_hubspot.py --skip-writeback   # só cria Items
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import sys

from lib.erpnext_api import client_from_env as erpnext_client
from lib.erpnext_api import log_creating, log_error, log_ok, log_section, log_skip
from lib.hubspot_api import client_from_env as hubspot_client


SKIP_NAMES = {"teste", "FRETE"}

# (canonical_name → item_code) que NUNCA devem ser auto-criados.
# Já existem no ERPNext por convenção (TIR00060 = Tirzepatida 60mg).
PINNED_MAPPING = {
    "Tirzepatida 60mg/2,4mL": "TIR00060",
}


def normalize_name(name: str) -> tuple[str, str]:
    """Retorna (norm_key, canonical_name)."""
    name = name.strip()
    norm = name.lower()
    if "tirzepatida" in norm and "60" in norm:
        return "tirzepatida 60mg/2,4ml", "Tirzepatida 60mg/2,4mL"
    if "tirzepatida" in norm and "90" in norm:
        return "tirzepatida 90mg/3,6ml", "Tirzepatida 90mg/3,6mL"
    return norm, name


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="Só mostra plano, não executa")
    p.add_argument("--archive-dups", action="store_true",
                   help="Archive os products duplicados no HubSpot (batch API)")
    p.add_argument("--skip-writeback", action="store_true",
                   help="Pula write-back de SKU no HubSpot")
    p.add_argument("--item-group", default="Produtos", help="Item Group dos Items novos")
    p.add_argument("--stock-uom", default="Unidade", help="UoM padrão dos Items novos")
    args = p.parse_args(argv)

    log_section("Sync HubSpot Products → ERPNext Items")
    erp = erpnext_client()
    hub = hubspot_client()

    # ---- 1. Lista products HubSpot --------------------------------------
    log_section("1/4 — Lista products HubSpot")
    products = hub.list_all_products(properties=["name", "description", "hs_sku"])
    log_ok(f"Total products HubSpot: {len(products)}")

    # ---- 2. Dedup -------------------------------------------------------
    log_section("2/4 — Dedup por nome canônico")
    groups: dict[str, dict] = {}
    skipped_records = []
    for pr in products:
        props = pr.get("properties") or {}
        name = (props.get("name") or "").strip()
        if not name or name in SKIP_NAMES:
            skipped_records.append((pr["id"], name, "skip-list"))
            continue
        norm, canon = normalize_name(name)
        existing_sku = (props.get("hs_sku") or "").strip()
        g = groups.setdefault(norm, {
            "canonical": canon,
            "hs_ids": [],
            "description": props.get("description") or "",
            "existing_sku": existing_sku or None,
        })
        g["hs_ids"].append(int(pr["id"]))
        if not g["description"] and props.get("description"):
            g["description"] = props["description"]
        if not g["existing_sku"] and existing_sku:
            g["existing_sku"] = existing_sku

    total_hs = sum(len(g["hs_ids"]) for g in groups.values())
    log_ok(f"Records válidos: {total_hs}")
    log_ok(f"Skipped: {len(skipped_records)}")
    log_ok(f"Grupos únicos: {len(groups)}")

    # ---- 3. Cria/reusa Items ERPNext ------------------------------------
    log_section("3/4 — Criar / reusar Items ERPNext")
    _, r = erp._request("GET", "/api/resource/Item", params={
        "fields": '["name","item_code","item_name"]',
        "limit_page_length": 1000,
    })
    existing_by_name = {it["item_name"]: it["item_code"]
                        for it in (r or {}).get("data", []) if it.get("item_name")}
    log_ok(f"Items existentes no ERPNext: {len(existing_by_name)}")

    mapping: dict[str, str] = {}  # canonical → item_code
    created = reused = 0
    for norm in sorted(groups, key=lambda k: groups[k]["canonical"]):
        g = groups[norm]
        canon = g["canonical"]
        if canon in PINNED_MAPPING:
            mapping[canon] = PINNED_MAPPING[canon]
            reused += 1
            continue
        if canon in existing_by_name:
            mapping[canon] = existing_by_name[canon]
            reused += 1
            continue
        # variant: case insensitive match
        match = next((v for k, v in existing_by_name.items() if k.lower() == canon.lower()), None)
        if match:
            mapping[canon] = match
            reused += 1
            continue
        if args.dry_run:
            mapping[canon] = "<NEW>"
            created += 1
            continue
        payload = {
            "doctype": "Item",
            "item_name": canon,
            "item_group": args.item_group,
            "stock_uom": args.stock_uom,
            "has_batch_no": 1,
            "is_stock_item": 1,
            "include_item_in_manufacturing": 1,
            "description": (g["description"] or canon)[:500],
        }
        try:
            _, resp = erp._request("POST", "/api/resource/Item", json_body=payload)
            item_code = resp["data"]["name"]
            mapping[canon] = item_code
            created += 1
            log_creating(f"Item {item_code} = {canon}")
        except Exception as exc:  # noqa: BLE001
            log_error(f"Falha criar Item '{canon}': {exc}")

    log_ok(f"Items criados: {created}")
    log_ok(f"Items reusados: {reused}")

    # ---- 4. Write-back SKU no HubSpot -----------------------------------
    if args.skip_writeback:
        log_skip("Write-back HubSpot pulado (--skip-writeback)")
        return 0

    log_section("4/4 — Write-back SKU no HubSpot")
    inputs = []
    dup_ids = []
    for norm in sorted(groups, key=lambda k: groups[k]["canonical"]):
        g = groups[norm]
        canon = g["canonical"]
        item_code = mapping.get(canon)
        if not item_code or item_code == "<NEW>":
            continue
        primary_id = g["hs_ids"][0]
        # Idempotência: se já tem hs_sku igual, skip
        if g["existing_sku"] == item_code:
            log_skip(f"hs_id={primary_id} já tem hs_sku={item_code}")
        else:
            inputs.append({
                "id": str(primary_id),
                "properties": {"hs_sku": item_code},
            })
        dup_ids.extend(g["hs_ids"][1:])

    log_ok(f"Updates necessárias: {len(inputs)}")
    log_ok(f"Duplicatas identificadas: {len(dup_ids)}")

    if args.dry_run:
        log_skip("DRY-RUN — nada aplicado")
        return 0

    # Batches de 100 (limite HubSpot)
    if inputs:
        for i in range(0, len(inputs), 100):
            batch = inputs[i:i+100]
            try:
                resp = hub.batch_update_products(batch)
                ok_count = len([r for r in resp.get("results", []) if r.get("id")])
                log_ok(f"Batch {i//100 + 1}: {ok_count}/{len(batch)} ok")
            except Exception as exc:  # noqa: BLE001
                log_error(f"Batch {i//100 + 1}: {exc}")

    # Archive duplicatas
    if args.archive_dups and dup_ids:
        log_section("Archive duplicatas HubSpot")
        for i in range(0, len(dup_ids), 100):
            batch = dup_ids[i:i+100]
            try:
                hub.batch_archive_products(batch)
                log_ok(f"Archive batch {i//100 + 1}: {len(batch)} records")
            except Exception as exc:  # noqa: BLE001
                log_error(f"Archive batch {i//100 + 1}: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
