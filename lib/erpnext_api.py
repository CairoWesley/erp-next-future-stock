"""
Cliente HTTP para a API REST do ERPNext.

Encapsula autenticação por token, idempotência (verificar-antes-de-criar) e
logging padronizado conforme RNF-008 da documentação.

Padrão de logs:
    [CRIANDO] DocType Future Production Batch
    [OK]      Custom Field Sales Order Item.fp_future_production_batch já existe
    [SKIP]    Server Script desabilitado no site_config
    [ERRO]    Falha ao criar Client Script: <detalhe>
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class _Color:
    RESET = "\033[0m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    GREY = "\033[90m"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        return os.environ.get("ANSICON") is not None or "WT_SESSION" in os.environ
    return True


_COLOR = _supports_color()


def _paint(text: str, color: str) -> str:
    return f"{color}{text}{_Color.RESET}" if _COLOR else text


def log_creating(what: str) -> None:
    print(f"{_paint('[CRIANDO]', _Color.CYAN)} {what}")


def log_ok(what: str) -> None:
    print(f"{_paint('[OK]     ', _Color.GREEN)} {what}")


def log_skip(what: str) -> None:
    print(f"{_paint('[SKIP]   ', _Color.YELLOW)} {what}")


def log_error(what: str) -> None:
    print(f"{_paint('[ERRO]   ', _Color.RED)} {what}", file=sys.stderr)


def log_section(title: str) -> None:
    line = "=" * 72
    print()
    print(_paint(line, _Color.GREY))
    print(_paint(f"  {title}", _Color.GREY))
    print(_paint(line, _Color.GREY))


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------

class ErpnextApiError(RuntimeError):
    """Erro retornado pela API do ERPNext (já com mensagem amigável)."""

    def __init__(self, status_code: int, message: str, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ErpnextClient:
    def __init__(
        self,
        url: str,
        api_key: str,
        api_secret: str,
        timeout: int = 30,
        verify_ssl: bool = True,
    ) -> None:
        if not url:
            raise ValueError("ERPNEXT_URL não definido")
        if not api_key or not api_secret:
            raise ValueError("ERPNEXT_API_KEY / ERPNEXT_API_SECRET não definidos")

        self.url = url.rstrip("/")
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"token {api_key}:{api_secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Frappe-Site-Name": "",
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
        full_url = f"{self.url}{path}"
        response = self._session.request(
            method,
            full_url,
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
            raise ErpnextApiError(
                response.status_code,
                self._extract_error(body) or f"HTTP {response.status_code}",
                payload=body,
            )

        return response.status_code, body

    @staticmethod
    def _extract_error(body: Any) -> str | None:
        if isinstance(body, dict):
            for key in ("exception", "_server_messages", "message", "exc"):
                value = body.get(key)
                if value:
                    if isinstance(value, str) and value.startswith("["):
                        try:
                            arr = json.loads(value)
                            return " | ".join(
                                json.loads(item).get("message", item) if isinstance(item, str)
                                else str(item)
                                for item in arr
                            )
                        except (ValueError, AttributeError):
                            return value
                    return value if isinstance(value, str) else json.dumps(value)
        if isinstance(body, str):
            return body[:500]
        return None

    # -- conexão -----------------------------------------------------------

    def ping(self) -> str:
        """Verifica autenticação. Retorna o usuário logado."""
        _, body = self._request("GET", "/api/method/frappe.auth.get_logged_user")
        return body.get("message", "") if isinstance(body, dict) else ""

    # -- DocTypes ----------------------------------------------------------

    def doctype_exists(self, name: str) -> bool:
        status, _ = self._request("GET", f"/api/resource/DocType/{quote(name, safe='')}")
        return status == 200

    def create_doctype(self, payload: dict) -> dict | None:
        name = payload.get("name")
        if not name:
            raise ValueError("payload de DocType precisa de 'name'")

        if self.doctype_exists(name):
            log_ok(f"DocType {name} já existe")
            return None

        log_creating(f"DocType {name}")
        _, body = self._request(
            "POST",
            "/api/resource/DocType",
            json_body=payload,
        )
        log_ok(f"DocType {name} criado")
        return body.get("data") if isinstance(body, dict) else None

    def delete_doctype(self, name: str) -> bool:
        if not self.doctype_exists(name):
            log_skip(f"DocType {name} não existe")
            return False
        log_creating(f"Removendo DocType {name}")
        self._request("DELETE", f"/api/resource/DocType/{quote(name, safe='')}")
        log_ok(f"DocType {name} removido")
        return True

    # -- Custom Fields -----------------------------------------------------

    def custom_field_exists(self, dt: str, fieldname: str) -> str | None:
        """Retorna o name do Custom Field ou None."""
        filters = json.dumps([["dt", "=", dt], ["fieldname", "=", fieldname]])
        _, body = self._request(
            "GET",
            "/api/resource/Custom Field",
            params={"filters": filters, "limit_page_length": 1, "fields": '["name"]'},
        )
        data = (body or {}).get("data") or []
        return data[0]["name"] if data else None

    def create_custom_field(self, payload: dict) -> dict | None:
        dt = payload["dt"]
        fieldname = payload["fieldname"]
        label = f"Custom Field {dt}.{fieldname}"

        existing = self.custom_field_exists(dt, fieldname)
        if existing:
            log_ok(f"{label} já existe ({existing})")
            return None

        log_creating(label)
        _, body = self._request(
            "POST",
            "/api/resource/Custom Field",
            json_body={"doctype": "Custom Field", **payload},
        )
        log_ok(f"{label} criado")
        return body.get("data") if isinstance(body, dict) else None

    def delete_custom_field(self, dt: str, fieldname: str) -> bool:
        name = self.custom_field_exists(dt, fieldname)
        if not name:
            log_skip(f"Custom Field {dt}.{fieldname} não existe")
            return False
        log_creating(f"Removendo Custom Field {dt}.{fieldname}")
        self._request("DELETE", f"/api/resource/Custom Field/{quote(name, safe='')}")
        log_ok(f"Custom Field {dt}.{fieldname} removido")
        return True

    # -- Property Setter ---------------------------------------------------

    def property_setter_exists(self, doc_type: str, field_name: str, property_name: str) -> str | None:
        filters = json.dumps([
            ["doc_type", "=", doc_type],
            ["field_name", "=", field_name],
            ["property", "=", property_name],
        ])
        _, body = self._request(
            "GET",
            "/api/resource/Property Setter",
            params={"filters": filters, "limit_page_length": 1, "fields": '["name"]'},
        )
        data = (body or {}).get("data") or []
        return data[0]["name"] if data else None

    # -- Client Scripts ----------------------------------------------------

    def client_script_exists(self, dt: str | None, name_hint: str | None = None) -> str | None:
        filters: list[list] = []
        if dt:
            filters.append(["dt", "=", dt])
        if name_hint:
            filters.append(["name", "=", name_hint])
        if not filters:
            return None
        _, body = self._request(
            "GET",
            "/api/resource/Client Script",
            params={
                "filters": json.dumps(filters),
                "limit_page_length": 1,
                "fields": '["name"]',
            },
        )
        data = (body or {}).get("data") or []
        return data[0]["name"] if data else None

    def upsert_client_script(self, name: str, dt: str, script: str, enabled: int = 1) -> dict | None:
        existing = self.client_script_exists(dt, name)
        payload = {
            "doctype": "Client Script",
            "name": name,
            "dt": dt,
            "view": "Form",
            "enabled": enabled,
            "script": script,
        }
        if existing:
            log_creating(f"Atualizando Client Script {name}")
            _, body = self._request(
                "PUT",
                f"/api/resource/Client Script/{quote(existing, safe='')}",
                json_body=payload,
            )
            log_ok(f"Client Script {name} atualizado")
            return body.get("data") if isinstance(body, dict) else None

        log_creating(f"Client Script {name}")
        _, body = self._request("POST", "/api/resource/Client Script", json_body=payload)
        log_ok(f"Client Script {name} criado")
        return body.get("data") if isinstance(body, dict) else None

    def delete_client_script(self, name: str) -> bool:
        existing = self.client_script_exists(None, name)
        if not existing:
            log_skip(f"Client Script {name} não existe")
            return False
        log_creating(f"Removendo Client Script {name}")
        self._request("DELETE", f"/api/resource/Client Script/{quote(existing, safe='')}")
        log_ok(f"Client Script {name} removido")
        return True

    # -- Server Scripts ----------------------------------------------------

    def server_script_enabled(self) -> bool:
        """Verifica se Server Scripts podem ser EXECUTADOS no site.

        Cria um script API temporário, chama-o e remove. Se a flag
        `server_script_enabled` não estiver no common_site_config.json,
        a chamada lança ServerScriptNotEnabled.
        """
        probe_name = "_fp_probe_script_enabled"
        try:
            self._request(
                "POST",
                "/api/resource/Server Script",
                json_body={
                    "doctype": "Server Script",
                    "name": probe_name,
                    "script_type": "API",
                    "api_method": probe_name,
                    "allow_guest": 0,
                    "enabled": 1,
                    "script": 'frappe.response["message"] = {"ok": True}',
                },
            )
        except ErpnextApiError as exc:
            msg = str(exc).lower()
            if "already exists" not in msg and "duplicate" not in msg:
                raise

        try:
            self.call_method(probe_name)
            return True
        except ErpnextApiError as exc:
            msg = str(exc).lower()
            if "server script" in msg and ("disabled" in msg or "enable" in msg):
                return False
            raise
        finally:
            try:
                self._request("DELETE", f"/api/resource/Server Script/{probe_name}")
            except Exception:
                pass

    def server_script_exists(self, name: str) -> bool:
        status, _ = self._request("GET", f"/api/resource/Server Script/{quote(name, safe='')}")
        return status == 200

    def upsert_server_script(self, payload: dict) -> dict | None:
        name = payload["name"]
        if self.server_script_exists(name):
            log_creating(f"Atualizando Server Script {name}")
            _, body = self._request(
                "PUT",
                f"/api/resource/Server Script/{quote(name, safe='')}",
                json_body=payload,
            )
            log_ok(f"Server Script {name} atualizado")
            return body.get("data") if isinstance(body, dict) else None

        log_creating(f"Server Script {name}")
        _, body = self._request(
            "POST",
            "/api/resource/Server Script",
            json_body={"doctype": "Server Script", **payload},
        )
        log_ok(f"Server Script {name} criado")
        return body.get("data") if isinstance(body, dict) else None

    def delete_server_script(self, name: str) -> bool:
        if not self.server_script_exists(name):
            log_skip(f"Server Script {name} não existe")
            return False
        log_creating(f"Removendo Server Script {name}")
        self._request("DELETE", f"/api/resource/Server Script/{quote(name, safe='')}")
        log_ok(f"Server Script {name} removido")
        return True

    # -- Reports -----------------------------------------------------------

    def report_exists(self, name: str) -> bool:
        status, _ = self._request("GET", f"/api/resource/Report/{quote(name, safe='')}")
        return status == 200

    def upsert_report(self, payload: dict) -> dict | None:
        name = payload["name"]
        if self.report_exists(name):
            log_creating(f"Atualizando Report {name}")
            _, body = self._request(
                "PUT",
                f"/api/resource/Report/{quote(name, safe='')}",
                json_body=payload,
            )
            log_ok(f"Report {name} atualizado")
            return body.get("data") if isinstance(body, dict) else None

        log_creating(f"Report {name}")
        _, body = self._request(
            "POST",
            "/api/resource/Report",
            json_body={"doctype": "Report", **payload},
        )
        log_ok(f"Report {name} criado")
        return body.get("data") if isinstance(body, dict) else None

    def delete_report(self, name: str) -> bool:
        if not self.report_exists(name):
            log_skip(f"Report {name} não existe")
            return False
        log_creating(f"Removendo Report {name}")
        self._request("DELETE", f"/api/resource/Report/{quote(name, safe='')}")
        log_ok(f"Report {name} removido")
        return True

    # -- Workspace ---------------------------------------------------------

    def workspace_exists(self, name: str) -> bool:
        status, _ = self._request("GET", f"/api/resource/Workspace/{quote(name, safe='')}")
        return status == 200

    def upsert_workspace(self, payload: dict) -> dict | None:
        name = payload["name"]
        if self.workspace_exists(name):
            log_creating(f"Atualizando Workspace {name}")
            _, body = self._request(
                "PUT",
                f"/api/resource/Workspace/{quote(name, safe='')}",
                json_body=payload,
            )
            log_ok(f"Workspace {name} atualizado")
            return body.get("data") if isinstance(body, dict) else None

        log_creating(f"Workspace {name}")
        _, body = self._request(
            "POST",
            "/api/resource/Workspace",
            json_body={"doctype": "Workspace", **payload},
        )
        log_ok(f"Workspace {name} criado")
        return body.get("data") if isinstance(body, dict) else None

    def delete_workspace(self, name: str) -> bool:
        if not self.workspace_exists(name):
            log_skip(f"Workspace {name} não existe")
            return False
        log_creating(f"Removendo Workspace {name}")
        self._request("DELETE", f"/api/resource/Workspace/{quote(name, safe='')}")
        log_ok(f"Workspace {name} removido")
        return True

    # -- utilidades --------------------------------------------------------

    def call_method(self, method: str, body: dict | None = None) -> Any:
        _, response = self._request(
            "POST",
            f"/api/method/{method}",
            json_body=body,
        )
        return response


# ---------------------------------------------------------------------------
# Bootstrap a partir do .env
# ---------------------------------------------------------------------------

def client_from_env() -> ErpnextClient:
    load_dotenv()

    url = os.environ.get("ERPNEXT_URL", "").strip()
    api_key = os.environ.get("ERPNEXT_API_KEY", "").strip()
    api_secret = os.environ.get("ERPNEXT_API_SECRET", "").strip()
    timeout = int(os.environ.get("ERPNEXT_HTTP_TIMEOUT", "30"))
    verify_ssl = os.environ.get("ERPNEXT_VERIFY_SSL", "true").lower() != "false"

    client = ErpnextClient(
        url=url,
        api_key=api_key,
        api_secret=api_secret,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )

    try:
        user = client.ping()
    except Exception as exc:
        log_error(f"Falha ao autenticar no ERPNext: {exc}")
        raise SystemExit(1) from exc

    log_ok(f"Conectado em {url} como {user}")
    return client
