# 15 — Dispensação + Etiqueta Zebra

> Módulo final do fluxo. Cada ato físico de entregar ampolas ao paciente vira
> um documento `Dispensation` rastreável + uma etiqueta Zebra impressa.

---

## O que é

`Dispensation` = registro de UM ato de entrega de ampola(s) a UM paciente
identificado. Contém: paciente, prescritor, lote, qty, data/hora, farmacêutico
responsável, assinatura, status da impressão.

Equivalente regulatório: prescrição → dispensação. Fecha a cadeia de
custódia: **planejamento → produção → lote físico → reserva → paciente
→ dispensação assinada**.

---

## DocType `Dispensation` — campos

| Seção | Campo | Tipo | Origem |
|---|---|---|---|
| Identificação | naming_series | Select | `DISP-.YYYY.-.#####` |
| | status | Select | Rascunho / Pendente / Dispensado / Cancelado |
| Origem | sales_order | Link → Sales Order | manual |
| | sales_order_patient_row | Data | row name do fp_patients |
| | customer | Link → Customer | fetch_from sales_order |
| Paciente | patient | Link → Patient | manual |
| | patient_name, cpf, mobile, email | Data | fetch_from patient |
| Prescritor | prescriber | Link → Prescriber | manual |
| | prescriber_name, council, number, state | Data | fetch_from prescriber |
| Produto | item_code, item_name, qty | mix | manual + fetch |
| | batch_no, batch_expiry, batch_manufacturing | mix | manual + fetch |
| Dispensação | dispensed_at | Datetime | default `now` |
| | pharmacist | Link → User | default `__user` |
| | signature | Attach Image | upload |
| Etiqueta | label_template | Select | 50x30mm / 100x50mm |
| | printed | Check | atualiza após print |
| | printed_at | Datetime | idem |
| | zpl_preview | Code | ZPL último gerado |
| | notes | Small Text | livre |

`Sales Order Patient.dispensation` (Link/Dispensation) = espelho da
linha → dispensação criada.

---

## Endpoints API (3 novos)

### 1. Criar dispensações em lote a partir de um SO

```http
POST /api/method/future_production_create_dispensations_from_so
{ "sales_order": "SAL-ORD-2026-00060" }
```

**Resposta**:
```json
{
  "message": {
    "sales_order": "SAL-ORD-2026-00060",
    "created_count": 5,
    "skipped_count": 0,
    "dispensations": [
      {"name": "DISP-2026-00001", "patient": "PAC-...", "patient_name": "Maria", "qty": 154, "batch_no": "LOT-..."},
      ...
    ]
  }
}
```

Idempotente: pula linhas que já têm `dispensation` preenchido.

### 2. Gerar ZPL

```http
POST /api/method/future_production_generate_zpl_label
{ "dispensation": "DISP-2026-00001" }
```

**Resposta**:
```json
{
  "message": {
    "dispensation": "DISP-2026-00001",
    "label_template": "50x30mm",
    "zpl": "^XA^CI28^PW400^LL240^FO15,10^A0N,24,24^FDMaria...^XZ",
    "patient_name": "Maria Aparecida",
    "cpf": "111.444.777-35",
    "batch_no": "LOT-AMP-2026-05-20-001",
    "qty": 3,
    "expiry": "20/05/2027"
  }
}
```

Salva ZPL gerado em `Dispensation.zpl_preview` (read-only, allow_on_submit).

### 3. Marcar como impressa

```http
POST /api/method/future_production_mark_dispensation_printed
{
  "dispensation": "DISP-2026-00001",
  "mark_dispensed": 1
}
```

- `printed=1`, `printed_at=now`
- Se `mark_dispensed=1`: status → "Dispensado" + atualiza `Sales Order Patient.batch_status` = "Entregue"

---

## Templates ZPL

### 50x30mm (default) — 400×240 dots @ 203dpi

```
^XA
^CI28                       (UTF-8)
^PW400^LL240
^FO15,10^A0N,24,24^FDMaria Aparecida Silva^FS
^FO15,40^A0N,18,18^FDCPF: 111.444.777-35^FS
^FO15,65^A0N,20,20^FDTirzepatida 60mg/2,4ml^FS
^FO15,90^A0N,18,18^FDLote: LOT-AMP-2026-05-20-001^FS
^FO15,113^A0N,18,18^FDVal: 20/05/2027 Qty: 3^FS
^FO15,140^BCN,55,Y,N,N^FDSAL-ORD-...|PAC-...|LOT-...^FS
^XZ
```

### 100x50mm — 800×400 dots @ 203dpi

```
^XA
^CI28
^PW800^LL400
^FO30,20^A0N,36,36^FD<paciente>^FS
^FO30,65^A0N,28,28^FDCPF: <cpf>^FS
^FO30,105^A0N,32,32^FD<item>^FS
^FO30,150^A0N,26,26^FDLote: <batch>^FS
^FO30,185^A0N,26,26^FDValidade: <val>^FS
^FO30,220^A0N,26,26^FDFabricacao: <fab>^FS
^FO30,255^A0N,28,28^FDQtd: <n> ampolas^FS
^FO30,300^BCN,60,Y,N,N^FD<barcode>^FS
^FO500,20^A0N,18,18^FD<SO>^FS
^FO500,42^A0N,18,18^FD<DISP>^FS
^XZ
```

Barcode (Code128): `<sales_order>|<patient>|<batch_no>`

---

## Fluxo de uso (UI)

```
1. SO já tem fp_patients alocados (batch_no preenchido — etapa 7)
                  │
                  ▼
2. Operador abre o SO
                  │
                  ▼
3. (UI futura) Botão "Criar Dispensações" no SO
   OU chama API future_production_create_dispensations_from_so
                  │
                  ▼
4. Sistema cria N Dispensations (1 por paciente)
                  │
                  ▼
5. Farmacêutico abre cada Dispensation
                  │
                  ▼
6. Confere paciente (CPF visível) + lote (validade)
                  │
                  ▼
7. Clica "Imprimir Etiqueta Zebra"
                  │
                  ▼
8. Client Script chama generate_zpl + envia via BrowserPrint
                  │
                  ▼
9. Etiqueta sai na impressora local
                  │
                  ▼
10. Sistema marca printed=1 + (opcional) status=Dispensado
                  │
                  ▼
11. Paciente assina (upload signature) + Submit
```

---

## Pré-requisito Cliente (PC do farmacêutico)

Instalar **Zebra BrowserPrint**:

1. Download: https://www.zebra.com/us/en/products/software/barcode-printers/link-os/browser-print.html
2. Instalar no PC do farmacêutico (Windows/Mac)
3. Conectar Zebra via USB ou rede
4. Abrir o BrowserPrint local (fica em system tray)
5. No browser, ERPNext detecta automaticamente quando carrega o Client Script

> Se BrowserPrint **não estiver instalado**: Client Script abre diálogo com o
> ZPL pra copiar e colar em [labelary.com](http://labelary.com) (preview) ou
> Zebra Setup Utilities.

---

## Como rodar agora (sem Zebra física)

```bash
# Criar dispensações pra 1 SO
curl -X POST \
  "https://erp.injemedpharma.com.br/api/method/future_production_create_dispensations_from_so" \
  -H "Authorization: token API_KEY:API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"sales_order": "SAL-ORD-2026-00060"}'

# Gerar ZPL de uma dispensação
curl -X POST \
  "https://erp.injemedpharma.com.br/api/method/future_production_generate_zpl_label" \
  -H "Authorization: token API_KEY:API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"dispensation": "DISP-2026-00001"}'
```

Cole o ZPL em **http://labelary.com/viewer.html** pra ver preview da etiqueta.

---

## Smoke test

```bash
python smoke_test_huge.py --phase dispense
```

Saída esperada:
```
74 Dispensations criadas em 18 SOs (8.7s)
Amostra ZPL: DISP-2026-00006 → 343 bytes
Amostra ZPL: DISP-2026-00009 → 343 bytes
Amostra ZPL: DISP-2026-00012 → 343 bytes
```

---

## URLs UI

| O que | URL |
|---|---|
| Lista de Dispensações | `https://erp.injemedpharma.com.br/app/dispensation` |
| Filtro por status Pendente | `?status=Pendente` |
| Filtro por farmacêutico | `?pharmacist=<email>` |
| 1 Dispensação | `/app/dispensation/DISP-2026-00001` |
| Lista filtrada por paciente | `/app/dispensation?patient=PAC-...` |

---

## Próximos passos sugeridos

| # | Item | Esforço |
|---|---|---|
| 1 | Adicionar botão "Criar Dispensações" no Sales Order (Client Script) | Pequeno |
| 2 | Workspace add link "Dispensação" | Trivial |
| 3 | Print Format ERPNext nativo pra A4 (alternativa Zebra) | Médio |
| 4 | Server Script no Submit do Dispensation: bloqueia se `signature` vazio | Pequeno |
| 5 | Report "Dispensações por Lote" (auditoria ANVISA) | Pequeno |
| 6 | Report "Dispensações por Paciente" (histórico) | Pequeno |
| 7 | Endpoint webhook quando farmácia externa entrega | Médio |

---

## Validação manual

**1)** Abra Dispensation no UI:
https://erp.injemedpharma.com.br/app/dispensation/DISP-2026-00001

**2)** Confira:
- patient_name, CPF, item, batch, validade preenchidos automaticamente
- Botão "Imprimir Etiqueta Zebra" visível no topo
- Status = "Pendente"

**3)** Clique "Imprimir Etiqueta Zebra":
- Se BrowserPrint instalado + Zebra conectada → imprime
- Senão → modal com ZPL pra copiar

**4)** Após imprimir → `printed=1` + `printed_at` preenchido
