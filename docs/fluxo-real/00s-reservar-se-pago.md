# Reservar SE pago 100% (webhook ou manual) — fluxo combinado

> O fluxo que você pediu, num endpoint só:
>
> ```
> deal → itens de linha (HubSpot) → consulta pago (checkout) → 100%?
>   PAGO     → cria pedido + reserva (FIFO split, FRETE entra sem reservar)
>   NÃO PAGO → ignora (não cria nada)
>   SEM itens de linha → RECUSA
> ```

## Endpoint (serve as DUAS entradas)

```
POST/GET https://erp.service.unikkapharma.com.br/api/method/future_production_reserve_if_paid
Header: Authorization: token <KEY>:<SECRET>
```

- **Rota manual** (sem webhook): `?id=<DEAL_ID>`
- **Webhook**: POST com o payload do checkout — extrai o deal de
  `id` / `deal_id` / `externalRef` / `ref` (inclusive aninhado em `data.*`).

Mesmo endpoint pros dois. O `externalRef` do checkout = deal id HubSpot.

## Passos (no endpoint)

```
1. HubSpot: associations line_items do deal
     SEM line items → throw [NO_LINE_ITEMS]  (RECUSA)
2. soma amount dos line items → total_due
3. Checkout: login → recheck-by-deal → soma transações PAID/AUTHORIZED → total_paid
4. paid_100 = total_paid (+tol) >= total_due
5a. paid_100=false → { reserved:false, ignored:true }   (IGNORA)
5b. paid_100=true  → cria SO + reserva (FIFO split; FRETE/non-stock entra sem reservar)
```

## Response

**Pago → reservou:**
```json
{ "ok":true, "deal_id":"...", "reserved":true, "paid_100":true,
  "payment": { "total_due":1966.0, "total_paid":1966.0, "paid_pct":100.0, "transactions":[...] },
  "sales_order":"00020", "customer":"00006",
  "reservations":[ {"reservation":"...","future_production_batch":"FPB-2026-00001","reserved_qty":1.0} ],
  "reserve_errors":[], "unmatched_skus":[] }
```

**Não pago → ignorou:**
```json
{ "ok":true, "deal_id":"...", "reserved":false, "ignored":true, "reason":"nao pago 100%",
  "payment": { "total_due":1966.0, "total_paid":900.0, "paid_pct":45.78, "paid_100":false } }
```

**Sem itens de linha → recusa:** throw `[NO_LINE_ITEMS] Deal X sem itens de linha — pedido recusado.`

## Params

| Param | Default | Descrição |
|---|---|---|
| `id`/`deal_id`/`externalRef`/`ref` | **obrig.** | deal id HubSpot |
| `auto_reserve` | `1` | FIFO split entre lotes |
| `fpb_map` | — | `{item:lote}` lote explícito |
| `customer`/`company`/`warehouse` | (deal/config/UP) | overrides |

## Wiring do webhook — URL + secret

O endpoint é **público com secret** (`allow_guest=1`, gateado por
`webhook_secret`). Aponta o webhook do checkout (ou n8n) pra:

```
POST https://erp.service.unikkapharma.com.br/api/method/future_production_reserve_if_paid
```

Passa o secret num destes (⚠ **query `?secret=` NÃO funciona** com body JSON —
o Frappe não funde query no form_dict):

| Forma | Como |
|---|---|
| **Header** (recomendado) | `X-Webhook-Secret: <webhook_secret>` |
| **Body** | adiciona `"secret": "<webhook_secret>"` no JSON |

`webhook_secret` está em `Injemed Financial Settings` (gerado no setup; pode
trocar). Body = payload do checkout (precisa ter `externalRef`/`deal_id`/`ref`)
ou `{"id":"<deal>"}`.

Chamada **autenticada** (com `Authorization: token KEY:SECRET`) ignora o secret
(rota manual / server-to-server).

Idempotente por `hubspot_deal_id` — re-disparo não duplica; item já reservado é pulado.


### Desconto PIX

Pagamento via **PIX** pode ter desconto (config `pix_discount_pct`, default 5%).
O valor pago PIX é "grossed-up" (`pago / (1 - %/100)`) antes de comparar com o
total dos itens de linha. Ex: itens R$2580, PIX pago R$2451 (5% off) →
efetivo R$2580 = **100% pago** → reserva. Validado: deal 61049766698 → SO 00021.

### Payload do checkout (formato real, validado)

O checkout manda o deal id no campo **`external_ref`** (snake_case), dentro de
`transaction`:

```json
{ "event": "transaction.paid",
  "transaction": { "transaction_id":"...", "checkout_id":"...", "status":"PAID",
                   "amount_cents":245100, "external_ref":"61049766698" } }
```

O endpoint acha o `external_ref`/`externalRef` em **qualquer nível** (BFS).
Validado e2e: webhook real deal `61049766698` (PIX R$2451, itens R$2580).
Com desconto PIX 5% → efetivo R$2580 = **100%** → reservou (SO 00021). 417→200.

## Validado end-to-end (unikkapharma)

Deal real `61048721486`: `total_due` R$1966 (OT10000029 1900 + FRETE 66) =
`total_paid` R$1966 (1 transação `PAID` cartão; 1 `FAILED` ignorada) →
`paid_100:true` → reservado (SO 00015, FPB-2026-00001). Idempotente (sem
duplicar). Secret testado por header e por body.

## Erros / códigos

| code | quando |
|---|---|
| `[MISSING_DEAL]` | sem deal id em nenhum campo |
| `[NO_LINE_ITEMS]` | deal sem itens de linha → **recusa** |
| `[NO_HUBSPOT_TOKEN]` / `[NO_CHECKOUT_CREDS]` / `[CHECKOUT_LOGIN_FAIL]` | config/login |
| `reserved:false, ignored:true` | não pago 100% (não é erro) |
| `reserve_errors[]` | INSUFFICIENT_TOTAL / BATCH_* na reserva |

## Componentes (endpoints separados, se quiser usar isolado)

- `future_production_check_payment` — só verifica (ver [00r](00r-verificar-pagamento-checkout.md)).
- `future_production_reserve_from_hubspot` — só reserva, sem gate de pagamento (ver [00q](00q-reservar-pedido-hubspot.md)).
- `future_production_reserve_if_paid` — **este**, combina os dois.
