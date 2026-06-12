# Verificar pagamento — pago 100%? (checkout API × itens de linha HubSpot)

> Endpoint que compara o **valor total dos itens de linha** (HubSpot) com o que
> foi **pago no checkout** (API `checkout.service.unikkapharma.com.br`) e diz se
> o deal está **100% pago**.

## URL

```
GET/POST https://erp.service.unikkapharma.com.br/api/method/future_production_check_payment?id=<DEAL_ID>
Header: Authorization: token <KEY>:<SECRET>
```

## O que faz

```
1. HubSpot: line items do deal → soma amount = total_due (valor total dos itens de linha)
2. Checkout: POST /api/auth/login {user,password} → token (HMAC, server-to-server)
3. POST /api/transactions/recheck-by-deal/{deal}  (Cookie cs_session=<token>)
      → reconsulta status no provedor + lista os checkouts do deal (externalRef)
4. GET /api/checkouts/{id}/transactions por checkout
      → soma amountCents das transações APROVADAS (PAID/AUTHORIZED)
5. paid_100 = total_paid (+ tolerância) >= total_due
```

> `externalRef` do checkout = **deal id HubSpot** (é como os checkouts são agrupados).
> O `recheck-by-deal` força reconsulta no provedor (PIX/cartão/boleto) antes de somar.

## Config (Injemed Financial Settings)

| Campo | Descrição |
|---|---|
| `checkout_api_url` | base (default `https://checkout.service.unikkapharma.com.br`) |
| `checkout_user` / `checkout_password` | login do painel checkout (Password) |
| `payment_approved_statuses` | status que contam como pago. Default `PAID,AUTHORIZED` |
| `payment_tolerance_cents` | folga em centavos (arredondamento). Default 0 |

Status possíveis: `PENDING, AWAITING_3DS, AUTHORIZED, PAID, FAILED, EXPIRED, REFUNDED, OVERDUE, CANCELED`.

## Response

```json
{
  "deal_id": "61048721486",
  "total_due": 1966.00,  "total_due_cents": 196600,
  "total_paid": 1966.00, "total_paid_cents": 196600,
  "paid_pct": 100.0,
  "paid_100": true,
  "approved_statuses": ["PAID","AUTHORIZED"],
  "checkouts_found": 1,
  "line_items": [ {"sku":"OT10000029","name":"...","amount":1900.0}, {"sku":"SV02000002","name":"FRETE","amount":66.0} ],
  "transactions": [ {"id":"...","status":"PAID","amountCents":196600,"method":"PIX","paidAt":"..."} ]
}
```

| Campo | Significado |
|---|---|
| `total_due` | soma dos itens de linha do HubSpot (R$) |
| `total_paid` | soma das transações aprovadas no checkout (R$) |
| `paid_pct` | % pago |
| `paid_100` | **true = pode reservar/produzir** |

## curl

```bash
# 1x: credenciais do checkout na config
curl -X PUT https://erp.service.unikkapharma.com.br/api/resource/Injemed%20Financial%20Settings/Injemed%20Financial%20Settings \
  -H "Authorization: token <KEY>:<SECRET>" -H "Content-Type: application/json" \
  -d '{ "checkout_user":"<user>", "checkout_password":"<senha>" }'

# verifica:
curl "https://erp.service.unikkapharma.com.br/api/method/future_production_check_payment?id=61048721486" \
  -H "Authorization: token <KEY>:<SECRET>"
```

## Erros

| code | quando |
|---|---|
| `[MISSING_DEAL]` | sem id |
| `[NO_HUBSPOT_TOKEN]` / `[NO_CHECKOUT_CREDS]` | config faltando |
| `[CHECKOUT_LOGIN_FAIL]` | user/senha do checkout errados |

## Gate no pedido (opcional — próximo passo)

Dá pra plugar como **gate** no `reserve_from_hubspot` (`require_payment=1`):
só reserva se `paid_100`. Hoje é endpoint **separado** — o sistema externo
chama `check_payment` primeiro e, se `paid_100`, chama `reserve_from_hubspot`.

## Técnico (validado)

- `make_post_request(url, json=...)` + `make_get_request(url, headers=...)` no
  server script — outbound OK.
- Login retorna `token` reutilizável como `Cookie: cs_session=<token>`
  (server-to-server, sem cookie jar).
- HubSpot line items: endpoint dedicado de associação + `amount` por linha.
