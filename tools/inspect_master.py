"""Lista valores para Customer Group, Territory, Price List, etc."""
import json
from lib.erpnext_api import client_from_env

c = client_from_env()

def show(dt, fields):
    _, body = c._request("GET", f"/api/resource/{dt}",
                         params={"fields": json.dumps(fields),
                                 "limit_page_length": 50, "order_by": "name asc"})
    rows = (body or {}).get("data") or []
    print(f"\n{dt} ({len(rows)} rows):")
    for r in rows:
        print(f"  {r}")

show("Customer Group", ["name", "is_group", "parent_customer_group"])
show("Territory",      ["name", "is_group", "parent_territory"])
show("Price List",     ["name", "currency", "enabled", "selling", "buying"])
show("Stock UOM",      ["name"])  # if exists
