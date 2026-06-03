# Trocar e Cancelar Reserva (chave produto + pedido)

> O pedido pode ficar **gerado no sistema sem reserva**. Duas operações de
> reserva, acionáveis por **chave = (produto + pedido HubSpot)**:
>
> 1. **Trocar** o lote de uma reserva — `future_production_swap_reservation`
> 2. **Cancelar** a reserva (pedido continua) — `future_production_cancel_reservation`
>
> Ambas resolvem o pedido por `sales_order` direto **ou** por `deal_id` (HubSpot).
> O hook `PR - On Cancel` devolve o saldo do FPB e atualiza o Sales Order Item
> automaticamente — aqui só disparamos o cancel e (no swap) re-reservamos.

---

## 1. Trocar reserva — `future_production_swap_reservation`

Cancela a reserva atual do(s) item(ns), **libera o lote antigo** e reserva no
**lote novo** (mesma validação do `step_reserve`). Re-distribui os pacientes
entre os lotes novos (bin-pack, **1 receita = 1 lote inteiro**).

```
POST /api/method/future_production_swap_reservation
```

### Body

```json
{
  "deal_id": "60801476407",
  "item_fpb": [
    { "item_code": "TIR00060", "lotes": [ { "fpb_name": "00141", "qty": 1 } ] }
  ]
}
```

| Campo | Obrigatório | Descrição |
|---|---|---|
| `sales_order` **ou** `deal_id` | sim | identifica o pedido (chave pedido) |
| `item_fpb` `[{item_code, lotes:[{fpb_name, qty}]}]` | um dos 3 | preferido — qty por lote + bin-pack |
| `fpb_map` `{item_code → fpb_name}` | um dos 3 | 1 lote por item |
| `fpb_name` `string` | um dos 3 | 1 lote pra todos os itens stock |

**Chave produto:** o conjunto de `item_code` informado define **quais itens
trocam**. Itens fora da chave **não são tocados** (reserva preservada). Sem
nenhum lote informado → `BATCH_REQUIRED` (lote obrigatório, sem FIFO).

### O que acontece (ordem)

```
1. cancela PRs ativas dos itens-alvo  → libera lote ANTIGO (hook recalcula FPB)
2. limpa fp_patients.fp_future_production_batch dos itens-alvo
3. cria PRs nos lotes NOVOS            (valida submit/item/status/saldo)
4. re-bin-pack pacientes nos lotes novos (receita inteira em 1 lote)
```

Tudo na mesma transação: o saldo liberado no passo 1 já é visto pelo passo 3.

### Gate: não troca em cima da hora

A troca é **bloqueada por item** se o lote atual:
- já foi **produzido** (`produced_qty > 0`), ou
- **produz em menos de N dias** (`planned_production_date − hoje < N`).

`N` = `Injemed Financial Settings.swap_min_days_before_production` (**padrão 5**,
editável na UI `/app/injemed-financial-settings`). Itens bloqueados voltam em
`blocked[]` com code `SWAP_TOO_LATE`; os demais itens trocam normalmente
(não-destrutivo — a reserva bloqueada fica intacta).

```json
"blocked": [
  { "code": "SWAP_TOO_LATE", "item_code": "TIR00060",
    "error": "Nao da pra trocar o produto TIR00060: lote 00137 produz em 0 dia(s) (minimo 5 dias antes da producao)." }
]
```

### Response

```json
{
  "ok": true,
  "sales_order": "00138",
  "cancelled":    [ { "reservation": "00139", "item_code": "TIR00060",
                      "future_production_batch": "00137", "reserved_qty": 1.0 } ],
  "reservations": [ { "reservation": "00142", "item_code": "TIR00060",
                      "future_production_batch": "00141", "reserved_qty": 1.0 } ],
  "reserve_errors": [],
  "patient_assignments": [ { "patient": "00136", "item_code": "TIR00060",
                             "qty": 1.0, "fpb": "00141" } ],
  "pack_errors": []
}
```

`reserve_errors` usa o mesmo catálogo do `step_reserve` (`BATCH_NOT_FOUND`,
`BATCH_NOT_SUBMITTED`, `BATCH_WRONG_ITEM`, `BATCH_CLOSED`, `INSUFFICIENT_QTY`,
`BATCH_REQUIRED`, `ITEM_NOT_IN_ORDER`). `pack_errors` → `PATIENT_NOT_FIT`.

> Se o lote novo falhar a validação, a reserva antiga **já foi cancelada** e o
> item fica **sem reserva** (com o erro no `reserve_errors`). O operador corrige
> o lote e re-chama (o swap é idempotente: sem PR ativa, só re-reserva).

---

## 2. Cancelar reserva — `future_production_cancel_reservation`

Cancela a(s) reserva(s) e **libera o lote**. Por padrão **o pedido continua no
sistema** (submetido), só fica **sem reserva**. Limpa o lote por paciente.

```
POST /api/method/future_production_cancel_reservation
```

### Body

```json
{ "deal_id": "60801476407" }
```

| Campo | Default | Descrição |
|---|---|---|
| `sales_order` **ou** `deal_id` | — | identifica o pedido |
| `item_code` | (todos) | cancela só a reserva desse produto (chave produto) |
| `cancel_order` | `false` | `true` → cancela **também o Sales Order** ("com pedido e tudo") |
| `cancel_payments` | `false` | `true` → estorna os Payment Entry lançados antes de cancelar o pedido |

### Modos

```
cancel_order=false (default)       → cancela reserva; PEDIDO FICA (sem reserva)
cancel_order=true                  → cancela reserva + Sales Order
   + recebimento lançado?
       sem cancel_payments         → THROW [ORDER_HAS_PAYMENTS] (atômico, NADA cancela)
       com cancel_payments=true    → estorna PE(s) + cancela o pedido
```

**Pré-flight atômico:** se o pedido tem Payment Entry submetido e você pediu
`cancel_order` sem `cancel_payments`, o endpoint **lança erro antes de cancelar
qualquer coisa** — a reserva e o pedido ficam intactos. Listamos os PEs no erro
pro operador decidir (estornar é decisão financeira).

`item_code` **não** combina com `cancel_order` (cancelar o pedido afeta todos os
itens) → `ITEM_FILTER_WITH_ORDER`.

### Response

```json
{
  "ok": true,
  "sales_order": "00138",
  "cancelled": [ { "reservation": "00142", "item_code": "TIR00060",
                   "future_production_batch": "00141", "reserved_qty": 1.0 } ],
  "patients_cleared": 1,
  "order_cancelled": false,
  "payments_cancelled": []
}
```

---

## Erros (catálogo)

| code | quando |
|---|---|
| `[MISSING_SO]` (throw) | sem `sales_order` nem `deal_id` válido |
| `[ORDER_HAS_PAYMENTS]` (throw) | `cancel_order` com PE lançado e sem `cancel_payments` |
| `[ITEM_FILTER_WITH_ORDER]` (throw) | `item_code` junto com `cancel_order` |
| `SWAP_TOO_LATE` (blocked[]) | swap: lote atual já produzido ou faltam <N dias pra produção |
| `ITEM_NOT_IN_ORDER` | swap: item informado não está no pedido |
| `BATCH_REQUIRED` / `BATCH_*` / `INSUFFICIENT_QTY` | swap: validação do lote novo (igual `step_reserve`) |
| `PATIENT_NOT_FIT` | swap: bin-pack não fecha nos lotes novos |

---

## curl (teste)

```bash
# Trocar lote do TIR00060 pro lote 00141
curl -X POST https://erp.injemedpharma.com.br/api/method/future_production_swap_reservation \
  -H "Authorization: token <KEY>:<SECRET>" -H "Content-Type: application/json" \
  -d '{ "deal_id": "60801476407",
        "item_fpb": [ { "item_code": "TIR00060", "lotes": [ { "fpb_name": "00141", "qty": 1 } ] } ] }'

# Cancelar só a reserva (pedido fica no sistema, sem reserva)
curl -X POST https://erp.injemedpharma.com.br/api/method/future_production_cancel_reservation \
  -H "Authorization: token <KEY>:<SECRET>" -H "Content-Type: application/json" \
  -d '{ "deal_id": "60801476407" }'

# Cancelar a reserva de UM produto só
curl -X POST .../future_production_cancel_reservation \
  -d '{ "sales_order": "00138", "item_code": "TIR00060" }'

# Cancelar o pedido inteiro + estornar recebimentos
curl -X POST .../future_production_cancel_reservation \
  -d '{ "sales_order": "00138", "cancel_order": true, "cancel_payments": true }'
```

---

## Webhooks n8n (Card React chama)

Duas rotas dedicadas (auth ERPNext via credencial `ERPNext Injemed`). Repassam
o body pro endpoint e devolvem o `message` (ou `{ok:false,error}` normalizado).

| Op | Webhook n8n | Workflow ID | Endpoint ERPNext |
|---|---|---|---|
| Trocar | `POST /webhook/erp/trocar-reserva` | `78jiYigeTvfA7Yqd` | `swap_reservation` |
| Cancelar | `POST /webhook/erp/cancelar-reserva` | `AatKl05FLZQHeg0j` | `cancel_reservation` |

```bash
# Trocar (Card manda deal_id + lote novo — "re-mando e atualiza")
curl -X POST https://n8n.injemedpharma.com.br/webhook/erp/trocar-reserva \
  -H "Content-Type: application/json" \
  -d '{ "deal_id":"60801476407", "fpb_map": { "TIR00060":"00141" } }'

# Cancelar (só reserva; pedido fica)
curl -X POST https://n8n.injemedpharma.com.br/webhook/erp/cancelar-reserva \
  -H "Content-Type: application/json" -d '{ "deal_id":"60801476407" }'
```

> **Por que webhook dedicado e não re-enviar no sync?** O sync principal
> (`/webhook/erp/sincronizar-pedido`) é **idempotente**: se o item já tem
> reserva, ele **pula** (não troca). Pra trocar o lote, use a rota
> `trocar-reserva` — é o "re-mando o pedido com o lote novo e atualiza".

## UI ERPNext (botões no Sales Order)

Client Script `Sales Order - Reserva Ops` (instalado por `setup_22`) adiciona,
no grupo **Reserva** do pedido submetido:

- **Cancelar Reserva** → confirma e chama `cancel_reservation` (pedido fica).
- **Trocar Lote** → diálogo: escolhe produto + novo FPB (filtrado por item +
  status aberto) → `swap_reservation` (`fpb_map`). Mostra `blocked`/erros/sucesso.

## Validado em prod (SO 00138)

| Op | Resultado |
|---|---|
| swap 00137 → 00141 | cancel PR 00139, cria PR 00142, lote antigo liberado (avail 1), paciente re-alocado |
| cancel (só reserva) | PR cancelada, lote liberado, `patients_cleared=1`, **SO docstatus=1** (fica) |
| cancel `cancel_order` (tem PE) | THROW `ORDER_HAS_PAYMENTS` — atômico, PR sobrevive |
| cancel `cancel_order`+`cancel_payments` (SO descartável) | SO + PE cancelados (docstatus 2) |
| gate swap 00138 (lote produz hoje, 0d<5) | `SWAP_TOO_LATE` — bloqueado, PR intacta |
| gate swap lote futuro (+12d) | permitido — troca OK |
| webhook `trocar-reserva` | retorna `blocked` (gate) — chain OK |
| webhook `cancelar-reserva` | retorna `{ok:false,error}` normalizado (throw) |
