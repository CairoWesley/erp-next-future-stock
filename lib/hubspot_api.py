"""
Cliente HTTP para HubSpot CRM API v3.

Usa Private App access token (env HUBSPOT_ACCESS_TOKEN). Sem OAuth flow —
o token é gerado uma vez no painel do HubSpot e usado direto.

Padrão de logs igual ao lib/erpnext_api: [CRIANDO] / [OK] / [SKIP] / [ERRO].

Setup HubSpot:
    1. HubSpot → Settings (engrenagem topo direito)
    2. Integrations → Private Apps → Create a private app
    3. Nome: ERPNext Sync
    4. Scopes (Data tab):
       - crm.objects.products.read
       - crm.objects.products.write
    5. Create app → copia "Access token" (pat-na1-...)
    6. .env:  HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxx
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv

from lib.erpnext_api import log_creating, log_error, log_ok, log_skip  # noqa: F401


HUBSPOT_BASE = "https://api.hubapi.com"


class HubspotApiError(Exception):
    def __init__(self, status_code: int, message: str, payload: Any = None) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.payload = payload


class HubspotClient:
    def __init__(
        self,
        access_token: str,
        timeout: int = 30,
        verify_ssl: bool = True,
    ) -> None:
        if not access_token:
            raise ValueError("HUBSPOT_ACCESS_TOKEN não definido")

        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # -- baixo nível -------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: Any = None,
    ) -> tuple[int, Any]:
        url = f"{HUBSPOT_BASE}{path}"
        response = self._session.request(
            method,
            url,
            params=params,
            data=json.dumps(json_body) if json_body is not None else None,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )

        if response.status_code == 404:
            return 404, None

        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text

        if response.status_code >= 400:
            raise HubspotApiError(
                response.status_code,
                self._extract_error(body) or f"HTTP {response.status_code}",
                payload=body,
            )

        return response.status_code, body

    @staticmethod
    def _extract_error(body: Any) -> str | None:
        if isinstance(body, dict):
            for key in ("message", "errorType", "category", "subCategory"):
                value = body.get(key)
                if value:
                    return str(value)
        return None

    # -- Auth check --------------------------------------------------------

    def ping(self) -> dict:
        """Retorna info do account autenticado."""
        _, body = self._request("GET", "/account-info/v3/details")
        return body if isinstance(body, dict) else {}

    # -- Products (CRM Objects) --------------------------------------------

    def list_products(
        self,
        properties: list[str] | None = None,
        limit: int = 100,
        after: str | None = None,
    ) -> dict:
        """Lista products com paginação. Retorna {results, paging}."""
        params: dict = {"limit": limit}
        if properties:
            params["properties"] = ",".join(properties)
        if after:
            params["after"] = after
        _, body = self._request("GET", "/crm/v3/objects/products", params=params)
        return body or {}

    def list_all_products(
        self,
        properties: list[str] | None = None,
    ) -> list[dict]:
        """Itera todas as páginas e retorna lista completa."""
        out: list[dict] = []
        after: str | None = None
        while True:
            page = self.list_products(properties=properties, limit=100, after=after)
            out.extend(page.get("results", []))
            paging = page.get("paging") or {}
            next_info = paging.get("next") or {}
            after = next_info.get("after")
            if not after:
                break
        return out

    def update_product(self, product_id: int, properties: dict) -> dict:
        """PATCH /crm/v3/objects/products/{id}."""
        _, body = self._request(
            "PATCH",
            f"/crm/v3/objects/products/{product_id}",
            json_body={"properties": properties},
        )
        return body or {}

    def batch_update_products(self, updates: list[dict]) -> dict:
        """POST /crm/v3/objects/products/batch/update.

        updates = [{ "id": "...", "properties": { "hs_sku": "..." } }, ...]
        Limite HubSpot: 100 inputs por batch.
        """
        if not updates:
            return {}
        _, body = self._request(
            "POST",
            "/crm/v3/objects/products/batch/update",
            json_body={"inputs": updates},
        )
        return body or {}

    def batch_archive_products(self, product_ids: list[int]) -> dict:
        """POST /crm/v3/objects/products/batch/archive.

        Move records pra estado archived (não deleta hard).
        Limite HubSpot: 100 inputs por batch.
        """
        if not product_ids:
            return {}
        _, body = self._request(
            "POST",
            "/crm/v3/objects/products/batch/archive",
            json_body={"inputs": [{"id": str(pid)} for pid in product_ids]},
        )
        return body or {}


def client_from_env() -> HubspotClient:
    load_dotenv()
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
    if not token:
        print(
            "[ERRO] HUBSPOT_ACCESS_TOKEN não definido em .env.",
            file=sys.stderr,
        )
        print(
            "[INFO] Criar Private App em HubSpot Settings → Integrations → Private Apps.",
            file=sys.stderr,
        )
        print(
            "[INFO] Scopes mínimos: crm.objects.products.read, crm.objects.products.write",
            file=sys.stderr,
        )
        sys.exit(1)
    c = HubspotClient(access_token=token)
    log_ok("Conectado ao HubSpot via Private App token")
    return c
