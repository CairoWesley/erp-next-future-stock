# 15 — Dispensação + Etiqueta Zebra (v2)

> Modelo: **1 Sales Order = 1 Dispensação** (a entrega completa).
> Dispensação tem **child table** com 1 linha por paciente.
> Cada linha gera 1 etiqueta Zebra individual.

---

## O que é

`Dispensation` = registro da **entrega de um pedido inteiro**. Contém todas as
informações da entrega + child table `Dispensation Patient` com 1 linha por
paciente que recebe ampolas.

Cada linha da child table = 1 etiqueta Zebra individual com os dados daquele
paciente (CPF, item, lote, validade, qty).

Fluxo:

```
1 Sales Order (com fp_patients[] alocados)
                │
                ▼
1 Dispensation criada
                │
   ┌────────────┼────────────┬────────────┐
   ▼            ▼            ▼            ▼
Patient A   Patient B   Patient C   Patient D
3 ampolas   2 ampolas   4 ampolas   1 ampola
LOT-001     LOT-001     LOT-001     LOT-001
   │            │            │            │
   ▼            ▼            ▼            ▼
Etiqueta    Etiqueta    Etiqueta    Etiqueta
Zebra A     Zebra B     Zebra C     Zebra D
```

---

## DocTypes

### `Dispensation` (parent, submetível)

| Seção | Campo | Tipo | Origem |
|---|---|---|---|
| Identificação | naming_series | Select | `DISP-.YYYY.-.#####` |
| | status | Select | Rascunho / Pendente / Parcialmente Dispensado / Dispensado / Cancelado |
| Origem | sales_order | Link → Sales Order | 1 SO = 1 Dispensation |
| | delivery_note | Link → Delivery Note | opcional |
| | customer | Link → Customer | fetch |
| | customer_name | Data | fetch |
| Dispensação | dispensed_at | Datetime | default `now` |
| | pharmacist | Link → User | default `__user` |
| | total_qty | Float | calculado |
| | total_patients | Int | calculado |
| Pacientes | **patients** | **Table** | **child Dispensation Patient** |
| Etiqueta | label_template | Select | 50x30mm / 100x50mm |
| | all_printed | Check | atualiza automaticamente |
| | printed_count | Data | "X/Y" |
| Observações | notes | Small Text | livre |

### `Dispensation Patient` (child table)

Cada linha = 1 paciente:

| Campo | Tipo | Origem |
|---|---|---|
| patient | Link → Patient | manual |
| patient_name, cpf, mobile | Data | fetch_from patient |
| prescriber | Link → Prescriber | manual |
| prescriber_name, council, number, state | Data | fetch_from prescriber |
| item_code, item_name | Link + Data | manual + fetch |
| qty | Float | manual |
| batch_no, batch_expiry, batch_manufacturing | Link + 2 Data | manual + fetch |
| sales_order_patient_row | Data | row origem (hidden) |
| **printed** | Check | impressão individual |
| **printed_at** | Datetime | quando imprimiu |
| **signature** | Attach Image | assinatura do paciente |
| row_notes | Small Text | livre |

---

## Custom Field

`Sales Order.dispensation` (Link → Dispensation, read-only) = espelho do SO
pra dispensação criada.

---

## Endpoints API (5)

### 1. Criar Dispensation do SO

```http
POST /api/method/future_production_create_dispensation_from_so
{ "sales_order": "SAL-ORD-2026-00060" }
```

**Resposta**:
```json
{
  "message": {
    "sales_order": "SAL-ORD-2026-00060",
    "dispensation": "DISP-2026-00079",
    "created": true,
    "rows_count": 5,
    "total_qty": 770
  }
}
```

Idempotente: se SO já tem dispensation, retorna a existente (`created: false`).

### 2. Gerar ZPL de 1 linha

```http
POST /api/method/future_production_generate_zpl_label
{ "dispensation": "DISP-2026-00079", "row_name": "<row_name opcional>" }
```

Se `row_name` omitido, gera ZPL da primeira linha.

### 3. Gerar ZPL de TODAS as linhas

```http
POST /api/method/future_production_generate_all_zpl_labels
{ "dispensation": "DISP-2026-00079" }
```

**Resposta**:
```json
{
  "message": {
    "dispensation": "DISP-2026-00079",
    "label_template": "50x30mm",
    "labels_count": 5,
    "zpl": "^XA...^XZ\n^XA...^XZ\n^XA...^XZ\n^XA...^XZ\n^XA...^XZ",
    "labels": [
      {"row_name": "...", "patient_name": "Maria", "cpf": "111.444.777-35", "qty": 3},
      ...
    ]
  }
}
```

Zebra imprime N etiquetas seguidas no envio.

### 4. Marcar 1 linha como impressa

```http
POST /api/method/future_production_mark_label_printed
{ "dispensation": "DISP-2026-00079", "row_name": "<row_name>" }
```

Atualiza `printed=1` + `printed_at=now` na linha. Recalcula `printed_count`
e `all_printed` no parent.

### 5. Marcar Dispensation como Dispensado

```http
POST /api/method/future_production_mark_dispensation_completed
{ "dispensation": "DISP-2026-00079" }
```

- Status → "Dispensado"
- Para cada paciente, atualiza `Sales Order Patient.batch_status = "Entregue"`

---

## UI — Botões no Dispensation Form

| Botão | Onde | O que faz |
|---|---|---|
| **Imprimir Todas as Etiquetas Zebra** | Header (menu Zebra) | Gera ZPL multi + envia via BrowserPrint + marca todas printed |
| **Marcar como Dispensado** | Header (menu Zebra) | Confirmação + atualiza espelhos |
| **Imprimir Esta Linha** | Grid child (botão custom) | Imprime 1 etiqueta da linha selecionada |

---

## Templates ZPL

### 50x30mm (default) — 400×240 dots @ 203dpi

```
^XA
^CI28
^PW400^LL240
^FO15,10^A0N,24,24^FDMaria Aparecida Silva^FS
^FO15,40^A0N,18,18^FDCPF: 111.444.777-35^FS
^FO15,65^A0N,20,20^FDTirzepatida 60mg/2,4ml^FS
^FO15,90^A0N,18,18^FDLote: LOT-AMP-2026-05-20-001^FS
^FO15,113^A0N,18,18^FDVal: 20/05/2027 Qty: 3^FS
^FO15,140^BCN,55,Y,N,N^FDSAL-ORD-...|PAC-...|LOT-...^FS
^XZ
```

### 100x50mm — 800×400 dots @ 203dpi (mais informações)

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

---

## Smoke test (validado)

```
$ python smoke/smoke_test_huge.py --phase dispense

Dispensations criadas: 19  (1 por SO alocado)
Total de etiquetas potenciais: 79  (soma das linhas)
Amostra: DISP-2026-00079 (SO SAL-ORD-2026-00060) → 5 etiquetas, 1719 bytes ZPL
```

---

## Fluxo de uso na UI

```
1. SO já alocado (fp_patients[] com batch_no)
                  │
                  ▼
2. (Botão futuro) "Criar Dispensação" no SO
   OU chama API future_production_create_dispensation_from_so
                  │
                  ▼
3. Sistema cria 1 Dispensation com N linhas (1 por paciente)
                  │
                  ▼
4. Farmacêutico abre a Dispensation
                  │
                  ▼
5. Vê todas as linhas com nome, CPF, item, lote, validade
                  │
                  ▼
6. Clica "Imprimir Todas as Etiquetas Zebra"
                  │
                  ▼
7. Sistema gera ZPL multi (todas etiquetas) + envia via BrowserPrint
                  │
                  ▼
8. Zebra imprime N etiquetas seguidas
                  │
                  ▼
9. Farmacêutico cola cada etiqueta na ampola correspondente
                  │
                  ▼
10. Coleta assinatura de cada paciente (upload por linha)
                  │
                  ▼
11. Clica "Marcar como Dispensado"
                  │
                  ▼
12. Status → Dispensado + espelha em Sales Order Patient
```

---

## Pré-requisito: Zebra BrowserPrint

Instalar no PC do farmacêutico:
https://www.zebra.com/us/en/products/software/barcode-printers/link-os/browser-print.html

- Windows ou Mac
- Conecta Zebra USB ou rede
- Roda no system tray
- Browser detecta automaticamente

**Sem BrowserPrint**: Client Script abre dialog com ZPL pra copiar e colar em
labelary.com (preview) ou Zebra Setup Utilities.

---

## URLs UI

| O que | URL |
|---|---|
| Lista de Dispensações | `https://erp.suaempresa.com.br/app/dispensation` |
| Filtro por status Pendente | `?status=Pendente` |
| Filtro por cliente | `?customer=<nome>` |
| 1 Dispensação | `/app/dispensation/DISP-2026-00079` |
| SO com link pra Dispensation | role até campo `dispensation` no SO |

---

## Validação manual

**1)** Abre Dispensation:
```
https://erp.suaempresa.com.br/app/dispensation/DISP-2026-00079
```

**2)** Confira no header:
- Sales Order vinculado
- Customer + customer_name
- Total de Ampolas (soma das linhas)
- Total de Pacientes (count linhas)
- Status = Pendente
- printed_count = 0/5

**3)** Role até "Pacientes da Entrega" — vê tabela com 5 linhas, cada uma com:
- Patient + Nome + CPF + Celular
- Prescriber + Nome do Médico + Conselho + Nº + UF
- Item + Nome do Item + Qtd
- Lote + Validade + Fabricação
- printed (checkbox, vazio)

**4)** Clica **"Imprimir Todas as Etiquetas Zebra"** no header:
- Se BrowserPrint OK → imprime 5 etiquetas
- Senão → dialog com ZPL pra copiar

**5)** Após imprimir → `printed=1` em cada linha + `all_printed=1` + `printed_count=5/5`

**6)** Clica **"Marcar como Dispensado"**:
- Status → Dispensado
- `Sales Order Patient.batch_status` de cada linha vira "Entregue"
