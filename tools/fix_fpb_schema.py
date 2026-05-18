"""
fix_fpb_schema.py — corrige o schema do Future Production Batch.

O DocType existia antes do setup com schema mínimo (apenas 2 campos).
O setup_01_structure detectou "já existe" e pulou a criação.

Este script:
  1. Lista quantos documentos FPB existem (segurança)
  2. Se zero: deleta o DocType vazio e recria com o schema completo
  3. Se houver dados: aborta e instrui a remover manualmente
"""

from __future__ import annotations

import json

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section
from lib.payloads import FUTURE_PRODUCTION_BATCH


def main() -> int:
    c = client_from_env()

    log_section("Verificando documentos existentes")
    _, body = c._request(
        "GET",
        "/api/resource/Future Production Batch",
        params={"fields": '["name"]', "limit_page_length": 200},
    )
    docs = (body or {}).get("data") or []
    print(f"  Documentos encontrados: {len(docs)}")
    for d in docs[:10]:
        print(f"    - {d['name']}")

    if docs:
        log_error(
            f"Existem {len(docs)} documentos no DocType. Aborte e remova-os manualmente "
            "antes de recriar o schema:\n"
            "  /app/future-production-batch"
        )
        return 1

    log_section("Removendo DocType vazio")
    try:
        c.delete_doctype("Future Production Batch")
    except Exception as exc:
        log_error(f"Falha ao remover: {exc}")
        return 1

    log_section("Recriando DocType com schema completo")
    try:
        c.create_doctype(FUTURE_PRODUCTION_BATCH)
        log_ok("Schema corrigido.")
        return 0
    except Exception as exc:
        log_error(f"Falha ao recriar: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
