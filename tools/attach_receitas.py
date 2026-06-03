"""
attach_receitas.py — anexa as receitas PDF (validadas) do validacao_receita
nas linhas de paciente do Sales Order no ERPNext.

Regra: só anexa receita de paciente com validations.status='aprovado'.
A receita tem que estar validada E dentro do sistema (ERPNext) pra o
pedido ser considerado completo.

Fluxo (por deal):
  1. Acha o Sales Order no ERPNext (por hubspot_deal_id).
  2. Lista os pacientes do deal no validacao_receita (Postgres) com
     receita_path + status de validação.
  3. Pra cada paciente APROVADO com receita:
       a. baixa o PDF do backend (validacao-api .../uploads/<path>)
       b. acha a row fp_patients no SO (match por CPF)
       c. faz upload do PDF no ERPNext (upload_file) na row
       d. seta receita + receita_original_name + receita_status na row

Idempotente: se a row já tem receita preenchida, pula.

Uso:
    python tools/attach_receitas.py --deal 60801476407
    python tools/attach_receitas.py --deal 60801476407 --force   # re-anexa
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import sys

import psycopg2
import requests

from lib.erpnext_api import client_from_env, log_error, log_ok, log_section, log_skip


BACKEND_URL = os.environ.get(
    "VALIDACAO_BACKEND_URL", "https://validacao-api.injemedpharma.com.br"
)
PG_DSN = dict(
    host=os.environ.get("VALIDACAO_PG_HOST", "2.24.98.117"),
    port=int(os.environ.get("VALIDACAO_PG_PORT", "5432")),
    user=os.environ.get("VALIDACAO_PG_USER", "postgres"),
    password=os.environ.get("VALIDACAO_PG_PASSWORD", ""),
    dbname=os.environ.get("VALIDACAO_PG_DB", "postgres"),
)


def digits(s: str) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def fetch_receitas(deal_id: str) -> list[dict]:
    """Pacientes do deal com receita + status de validação."""
    conn = psycopg2.connect(**PG_DSN)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pt.cpf, pt.nome, pt.receita_path, pt.receita_original_name,
               pt.assinatura_digital_status, v.status
        FROM validacao_receita.patients pt
        JOIN validacao_receita.products pr ON pr.id = pt.product_id
        JOIN validacao_receita.orders o ON o.id = pr.order_id
        LEFT JOIN validacao_receita.validations v ON v.patient_id = pt.id
        WHERE o.hubspot_deal_id = %s
        """,
        (str(deal_id),),
    )
    rows = []
    for r in cur.fetchall():
        rows.append({
            "cpf": digits(r[0]),
            "nome": r[1],
            "receita_path": r[2],
            "receita_original_name": r[3] or (r[2] or "receita.pdf"),
            "assinatura_status": r[4] or "nao_verificado",
            "validation_status": r[5] or "pendente",
        })
    conn.close()
    return rows


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--deal", required=True, help="HubSpot deal id")
    p.add_argument("--force", action="store_true", help="Re-anexa mesmo se já tem receita")
    args = p.parse_args(argv)

    log_section(f"Anexar receitas — deal {args.deal}")
    c = client_from_env()

    # 1. Sales Order do deal
    _, so_res = c._request("GET", "/api/resource/Sales Order", params={
        "filters": f'[["hubspot_deal_id","=","{args.deal}"]]',
        "fields": '["name"]',
    })
    so_list = (so_res or {}).get("data") or []
    if not so_list:
        log_error(f"Nenhum Sales Order pro deal {args.deal}.")
        return 1
    so_name = so_list[0]["name"]
    log_ok(f"Sales Order: {so_name}")

    # 2. rows fp_patients (cpf -> row)
    _, so_doc = c._request("GET", f"/api/resource/Sales Order/{so_name}")
    rows_by_cpf = {}
    for r in so_doc["data"].get("fp_patients", []):
        cpf = c._request("GET", f"/api/resource/Patient/{r['patient']}")[1]["data"].get("cpf")
        rows_by_cpf[digits(cpf)] = r

    # 3. receitas do validacao_receita
    receitas = fetch_receitas(args.deal)
    log_ok(f"Pacientes no validacao_receita: {len(receitas)}")

    attached = skipped = errors = 0
    for rec in receitas:
        cpf = rec["cpf"]
        if rec["validation_status"] != "aprovado":
            log_skip(f"{rec['nome']} ({cpf}): validação={rec['validation_status']} — não anexa")
            skipped += 1
            continue
        if not rec["receita_path"]:
            log_skip(f"{rec['nome']} ({cpf}): sem receita_path")
            skipped += 1
            continue
        row = rows_by_cpf.get(cpf)
        if not row:
            log_error(f"{rec['nome']} ({cpf}): sem row fp_patients no SO")
            errors += 1
            continue
        if (row.get("receita") or "") and not args.force:
            log_skip(f"{rec['nome']} ({cpf}): row já tem receita")
            skipped += 1
            continue

        # a. baixa PDF
        try:
            pdf = requests.get(f"{BACKEND_URL}/uploads/{rec['receita_path']}", timeout=30)
            if pdf.status_code != 200:
                log_error(f"{cpf}: download {pdf.status_code}")
                errors += 1
                continue
        except Exception as exc:  # noqa: BLE001
            log_error(f"{cpf}: download falhou {exc}")
            errors += 1
            continue

        # b. upload_file multipart
        try:
            sess = c._session
            saved_ct = sess.headers.get("Content-Type")
            sess.headers.pop("Content-Type", None)
            up = sess.post(
                f"{c.url}/api/method/upload_file",
                files={"file": (rec["receita_original_name"], pdf.content, "application/pdf")},
                data={"is_private": "1", "doctype": "Sales Order Patient",
                      "docname": row["name"], "fieldname": "receita"},
                timeout=60,
            )
            if saved_ct:
                sess.headers["Content-Type"] = saved_ct
            else:
                sess.headers["Content-Type"] = "application/json"
            file_url = up.json()["message"]["file_url"]
        except Exception as exc:  # noqa: BLE001
            log_error(f"{cpf}: upload falhou {exc}")
            errors += 1
            continue

        # c. seta campos
        for fld, val in (("receita", file_url),
                         ("receita_original_name", rec["receita_original_name"]),
                         ("receita_status", rec["assinatura_status"])):
            c._request("POST", "/api/method/frappe.client.set_value", json_body={
                "doctype": "Sales Order Patient", "name": row["name"],
                "fieldname": fld, "value": val,
            })
        log_ok(f"{rec['nome']} ({cpf}): receita anexada ({len(pdf.content)} bytes) → {file_url}")
        attached += 1

    log_section("Resumo")
    log_ok(f"Anexadas: {attached} | Puladas: {skipped} | Erros: {errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
