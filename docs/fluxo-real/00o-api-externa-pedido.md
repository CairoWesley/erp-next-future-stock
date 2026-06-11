# API externa — gerar pedido que consome estoque futuro

> Sistema externo (qualquer plataforma) gera o pedido via REST e **consome o
> estoque futuro** (FPB) na mesma chamada. **Sem pacientes** — só
> cliente + itens + lote. Endpoints aplicados no ERPNext por `setup_23`.

## Autenticação

Header em toda chamada (API Key/Secret de um usuário ERPNext):

```
Authorization: token <API_KEY>:<API_SECRET>
Content-Type: application/json
```

Base URL: `https://erp.injemedpharma.com.br`

> Gera a chave em **/app/user/<email> → API Access → Generate Keys**.
> Guarda o secret (só aparece uma vez).

## A rota (sequência)

```
┌ (opcional) cria estoque futuro ─────────────────────────────┐
│ POST /api/method/future_production_create_batch            │
│   → FPB submetido (Aberta para Reserva), Disponível = N    │
└─────────────────────────────────────────────────────────────┘
            ↓
┌ gera pedido + CONSOME estoque futuro (1 chamada) ───────────┐
│ POST /api/method/future_production_create_order            │
│   → Sales Order submetido + Production Reservation por item │
│   → FPB.Disponível CAI (consumido)                          │
└─────────────────────────────────────────────────────────────┘
```

Se o FPB (estoque futuro) já existe, pula o passo 1 e só chama `create_order`.

---

## 1. `future_production_create_batch` — criar estoque futuro

```
POST /api/method/future_production_create_batch
```

| Campo | Obrigatório | Default | Descrição |
|---|---|---|---|
| `item_code` | **sim** | — | produto (ex. `TIR00060`) |
| `planned_qty` | **sim** | — | quantidade do lote (estoque futuro) |
| `production_code` | não | `LOTE-<item>` | código do lote (ex. `TIRZE60-20260625`) |
| `planned_production_date` | não | hoje | data prevista de produção |
| `target_warehouse` | não | `Produtos Acabados - I` | depósito do acabado |
| `company` | não | `Injemedpharma` | empresa |

**Response**
```json
{ "ok": true, "future_production_batch": "00156", "production_code": "TIRZE60-20260625",
  "item_code": "TIR00060", "planned_qty": 3.0, "available_qty": 3.0, "status": "Aberta para Reserva" }
```

```bash
curl -X POST https://erp.injemedpharma.com.br/api/method/future_production_create_batch \
  -H "Authorization: token <KEY>:<SECRET>" -H "Content-Type: application/json" \
  -d '{ "item_code":"TIR00060", "planned_qty":3, "production_code":"TIRZE60-20260625",
        "planned_production_date":"2026-06-25" }'
```

---

## 2. `future_production_create_order` — pedido + consome estoque futuro

```
POST /api/method/future_production_create_order
```

| Campo | Obrigatório | Default | Descrição |
|---|---|---|---|
| `customer` | **sim** | — | nome OU razão social (resolve por `customer_name`) |
| `items` | **sim** | — | `[{item_code, qty, rate, fpb_name?, warehouse?}]` |
| `items[].fpb_name` | * | — | lote a consumir (estoque futuro) por item |
| `auto_reserve` | não | `false` | sem `fpb_name` → escolhe FIFO (lote aberto mais antigo c/ saldo) |
| `company` | não | `Injemedpharma` | empresa |
| `delivery_date` | não | hoje+30 | entrega |
| `hubspot_deal_id` | não | — | idempotência (re-chama = mesmo SO) |

> **Lote obrigatório por item**: informe `fpb_name` OU `auto_reserve=true`.
> Sem nenhum → o SO é criado mas o item **não reserva** (`BATCH_REQUIRED`).
> Item non-stock (FRETE) é ignorado.

**Response**
```json
{ "ok": true, "sales_order": "00157", "grand_total": 1800.0,
  "reservations": [ { "reservation":"00158", "future_production_batch":"00156",
                      "item_code":"TIR00060", "reserved_qty":1.0 } ],
  "reserve_errors": [] }
```

```bash
# lote explícito (consome o FPB informado)
curl -X POST https://erp.injemedpharma.com.br/api/method/future_production_create_order \
  -H "Authorization: token <KEY>:<SECRET>" -H "Content-Type: application/json" \
  -d '{ "customer":"00133",
        "items":[ { "item_code":"TIR00060", "qty":1, "rate":1800, "fpb_name":"00156" } ] }'

# auto (FIFO escolhe o lote aberto)
curl -X POST .../future_production_create_order \
  -d '{ "customer":"00133", "auto_reserve":true,
        "items":[ { "item_code":"TIR00060", "qty":2, "rate":1800 } ] }'
```

---

## Catálogo de erros

Throw (HTTP 417) — input inválido, nada criado:

| code | quando |
|---|---|
| `[MISSING_ITEM]` / `[ITEM_NOT_FOUND]` / `[INVALID_QTY]` | create_batch |
| `[MISSING_CUSTOMER]` / `[CUSTOMER_NOT_FOUND]` / `[NO_ITEMS]` | create_order |

`reserve_errors[]` (HTTP 200, SO criado, item não reservou):

| code | quando |
|---|---|
| `BATCH_REQUIRED` | sem `fpb_name` e sem `auto_reserve` (ou FIFO sem lote aberto) |
| `BATCH_NOT_FOUND` / `BATCH_NOT_SUBMITTED` | lote errado / rascunho |
| `BATCH_WRONG_ITEM` | lote é de outro produto |
| `BATCH_CLOSED` | lote não aceita reservas |
| `INSUFFICIENT_QTY` | saldo do estoque futuro < pedido |

---

## Endpoints granulares (alternativa — UI / passo-a-passo)

Se preferir orquestrar manualmente (ou espelhar os botões da UI):

| Ação | Endpoint | Body |
|---|---|---|
| Reservar 1 linha em 1 lote | `future_production_reserve_sales_order_item` | `{sales_order, sales_order_item, future_production_batch, qty}` |
| Reservar tudo FIFO | `future_production_auto_reserve_sales_order` | `{sales_order}` |
| Ver reservas | (listar `Production Reservation` por `sales_order`) | — |
| Trocar lote | `future_production_swap_reservation` | ver [00n](00n-trocar-cancelar-reserva.md) |
| Cancelar reserva | `future_production_cancel_reservation` | ver [00n](00n-trocar-cancelar-reserva.md) |

`create_order` faz SO+submit+reserva numa só chamada — recomendado pro sistema externo.

---

## Validado em prod

`create_batch` (planned 3) → `create_order` explícito (avail 3→2) →
`create_order` auto (avail 2→0, Totalmente Reservada) → `create_order` sem lote
(`BATCH_REQUIRED`, SO sem reserva). Sem pacientes em nenhum.

---

## Replicar noutra instância ERPNext

As customizações são os scripts `setup/setup_*.py` (DocTypes, Server Scripts,
Custom Fields, naming, workspace). Pra aplicar noutro ERPNext:

```
1. Aponta o .env pro novo ERPNext (ERPNEXT_URL + API_KEY/SECRET).
2. Habilita Server Scripts no novo (bench set-config server_script_enabled 1).
3. Roda os setups na ordem:
     python setup/setup_01..13   (DocTypes FPB/PR/Patient/Dispensacao + scripts)
     python setup/setup_15_naming_series.py
     python setup/setup_20_financial_config.py
     python setup/setup_23_external_api.py   (esta API externa)
4. Cria os Items + 1 FPB de teste → chama create_order.
```

Pré-requisitos no ERPNext alvo: Company, Warehouse "Produtos Acabados - I",
Price List "Venda Padrão", Customer Group. (Os setups assumem `Injemedpharma`.)
