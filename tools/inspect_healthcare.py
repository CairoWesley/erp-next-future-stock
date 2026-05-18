"""Checa se o módulo Healthcare (DocType Patient) está instalado."""
from lib.erpnext_api import client_from_env

c = client_from_env()
for name in ("Patient", "Healthcare Settings", "Patient Encounter"):
    s, _ = c._request("GET", f"/api/resource/DocType/{name.replace(' ', '%20')}")
    print(f"{name:25} {'OK' if s == 200 else 'NAO INSTALADO'}")
