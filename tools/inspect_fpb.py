"""Inspeciona o schema atual do DocType Future Production Batch."""
import json
from lib.erpnext_api import client_from_env

c = client_from_env()
_, body = c._request("GET", "/api/resource/DocType/Future Production Batch")
doc = body.get("data", {})

print(f"\nDocType: {doc.get('name')}")
print(f"Module: {doc.get('module')}")
print(f"Custom: {doc.get('custom')}")
print(f"Is Submittable: {doc.get('is_submittable')}")
print(f"Autoname: {doc.get('autoname')}")
print(f"\nCampos ({len(doc.get('fields', []))}):")
print(f"  {'fieldname':<32} {'fieldtype':<14} {'options':<30} reqd")
print(f"  {'-' * 90}")
for f in doc.get("fields", []):
    print(f"  {(f.get('fieldname') or ''):<32} {(f.get('fieldtype') or ''):<14} "
          f"{(f.get('options') or '')[:28]:<30} {f.get('reqd') or ''}")
