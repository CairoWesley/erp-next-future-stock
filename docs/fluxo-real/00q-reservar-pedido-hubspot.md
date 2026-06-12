# Reservar pedido a partir do HubSpot (1 chamada por deal id)

> Endpoint no domínio do ERP: recebe o **deal id HubSpot**, puxa os **line items
> + SKU** do HubSpot, cria o Sales Order e **reserva** (consome estoque futuro).
> Patient-free. Instalado por `setup_24`.

## URL

```
GET  https://erp.service.unikkapharma.com.br/api/method/future_production_reserve_from_hubspot?id=123456
POST .../api/method/future_production_reserve_from_hubspot   (body {id|deal_id})
Header: Authorization: token <API_KEY>:<API_SECRET>
```

> `123456` = **deal id HubSpot**. GET com `?id=` funciona (cria o pedido).
> Quer a URL bonita `/reservar-pedido?id=`? Dá pra criar um rewrite no
> Traefik/nginx → o método acima. Por ora usa o `/api/method/...`.

## Pré-requisito: token HubSpot na config

O endpoint lê o token do Private App HubSpot de
**Injemed Financial Settings → "HubSpot Access Token"** (campo `hubspot_access_token`,
tipo Password). Sem ele → erro `[NO_HUBSPOT_TOKEN]`.

Configura em `/app/injemed-financial-settings` (ou via API). Scopes mínimos do
Private App: `crm.objects.deals.read`, `crm.objects.line_items.read`,
`crm.objects.companies.read`.

## O que faz (passo a passo)

```
1. GET deal {id}  → associations line_items + companies
2. cada line item → hs_sku (UPPERCASE) + quantity
3. SKU → Item ERPNext (item_code = SKU uppercase). Sem match → unmatched_skus
4. customer: param > empresa associada ao deal > "Cliente HubSpot <id>"
5. cria Sales Order (idempotente por hubspot_deal_id)
6. reserva cada item: auto_reserve FIFO (default) OU fpb_map {item:lote}
```

## Params

| Param | Default | Descrição |
|---|---|---|
| `id` / `deal_id` | **obrig.** | deal id HubSpot |
| `auto_reserve` | `1` | FIFO (pega lote aberto mais antigo). `0` = só cria SO sem reservar (sem fpb_map) |
| `fpb_map` | — | `{item_code: fpb_name}` lote explícito por item |
| `customer` | (do deal) | override do cliente |
| `company` | config / `Unikka Pharma` | empresa |
| `warehouse` | `Produtos Acabados - UP` | depósito da linha |

## Response

```json
{
  "ok": true,
  "deal_id": "123456",
  "sales_order": "00007",
  "customer": "Empresa X",
  "reservations": [
    { "reservation": "00008", "future_production_batch": "FPB-2026-00001",
      "item_code": "OT10000029", "reserved_qty": 10.0 }
  ],
  "reserve_errors": [],
  "unmatched_skus": []
}
```

| Campo | Significado |
|---|---|
| `reservations` | reservas criadas (consumiram o estoque futuro) |
| `reserve_errors` | item sem lote / saldo (`BATCH_REQUIRED`, `INSUFFICIENT_QTY`, ...) |
| `unmatched_skus` | SKU do HubSpot **sem Item** correspondente no ERPNext |

## Mapeamento SKU

O `hs_sku` do line item é **UPPERCASE** e casado com `item_code` do ERPNext
(ex.: `ot10000029` → `OT10000029`). SKU sem Item → entra em `unmatched_skus`
(não quebra o pedido; os outros itens seguem).

## curl

```bash
# garante o token na config (1x):
curl -X PUT https://erp.service.unikkapharma.com.br/api/resource/Injemed%20Financial%20Settings/Injemed%20Financial%20Settings \
  -H "Authorization: token <KEY>:<SECRET>" -H "Content-Type: application/json" \
  -d '{ "hubspot_access_token": "pat-na1-XXXX" }'

# reserva a partir do deal:
curl "https://erp.service.unikkapharma.com.br/api/method/future_production_reserve_from_hubspot?id=123456" \
  -H "Authorization: token <KEY>:<SECRET>"
```

## Erros

| code | quando |
|---|---|
| `[MISSING_DEAL]` | sem `id`/`deal_id` |
| `[NO_HUBSPOT_TOKEN]` | token não configurado |
| `[HUBSPOT_DEAL_FAIL]` | deal não encontrado / token inválido / sem scope |
| `ok:false` + `unmatched_skus` | nenhum line item mapeável (SKU sem Item) |
| `reserve_errors[]` | item mapeado mas sem lote/saldo (FIFO vazio, etc.) |

## Requisitos técnicos (validados)

- Server Scripts habilitados (✅ via `common_site_config`, ver [00p](00p-catalogo-produtos-lotes.md)).
- Outbound HTTP do server script (`frappe.make_get_request`) — testado OK.
- Items com SKU uppercase + lotes futuros (FPB) abertos — ver [00p](00p-catalogo-produtos-lotes.md).
