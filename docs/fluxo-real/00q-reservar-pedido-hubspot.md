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
1. GET deal {id}  → associations line_items + companies (endpoints dedicados)
2. cada line item → hs_sku (UPPERCASE) + quantity
3. SKU → Item ERPNext (item_code = SKU uppercase). Sem Item → unmatched_skus
4. customer: param > empresa associada ao deal > "Cliente HubSpot <id>"
5. cria Sales Order (idempotente por hubspot_deal_id) — TODAS as linhas
   (produto + FRETE) entram no pedido
6. reserva cada item STOCK: auto_reserve FIFO com SPLIT entre lotes
   (FRETE/non-stock entra no SO mas NÃO reserva)
```

### Split entre lotes (pedido > 1 lote)

`auto_reserve` distribui a quantidade entre lotes **FIFO** (mais antigo primeiro):

```
Pedido 100, lote A=50, lote B=50  →  reserva 50 no A + 50 no B (2 reservas)
Lote acaba  →  pula pro próximo FIFO
Total insuficiente (ex. 80 pra 100) → reserva 80 + erro INSUFFICIENT_TOTAL (short:20)
```

`fpb_map {item:lote}` força um lote específico (reserva o que couber nele).

### FRETE / itens non-stock

SKU non-stock (ex. `SV02000002` FRETE) **entra no pedido como linha** (compõe o
total) mas **não reserva** (pulado pelo `is_stock_item`). Requer o Item existir
no ERPNext — `unmatched_skus` lista SKU do HubSpot **sem Item** (esses sim ficam
de fora do pedido).

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
| `reserve_errors[].INSUFFICIENT_TOTAL` | estoque futuro < pedido em todos os lotes (reservou o disponível) |
| `reserve_errors[].BATCH_REQUIRED` | item sem lote (auto_reserve=0 e sem fpb_map) |

## Coexistência com o fluxo COM paciente (não afeta)

Os endpoints **sem paciente** (`create_batch`, `create_order`,
`reserve_from_hubspot`, `swap/cancel_reservation`) são Server Scripts **novos e
separados**. **Não editam nem chamam** o fluxo com paciente
(`step_patients`, `allocate_patient_batches`, `create_dispensation_from_so`,
receita, bin-pack). Os dois caminhos coexistem na mesma instância:

```
COM paciente:  step_customer → step_order → step_patients (bin-pack/receita)
               → step_reserve → ... → dispensação/ZPL
SEM paciente:  create_order / reserve_from_hubspot  → SO + reserva (FIFO)
```

- Ambos reservam contra os **mesmos FPB / Production Reservation** (sem conflito).
- Escolha **por pedido**: um SO feito por `create_order` não tem `fp_patients`
  (esperado). Pra dispensação com paciente, usa o fluxo paciente nesse pedido.
- Idempotência por `hubspot_deal_id`: um deal num caminho não duplica no outro.
- Única mudança **compartilhada** no histórico: `step_reserve` virou
  **lote-obrigatório** (FIFO removido) — decisão de negócio, não efeito do
  sem-paciente. Vale pros dois fluxos.

> Conclusão: usar a integração enxuta (sem paciente) **não impede** usar o
> fluxo completo (com paciente) depois, na mesma instância.

## Validado em prod (unikkapharma)

- **Deal real** `61048721486` → SO `00015` + customer `00006` + reserva
  `00016` no FPB-2026-00001 (OT10000029). FRETE `SV02000002` entrou como linha
  (R$66), **não reservou** (non-stock). Total R$1966. `unmatched_skus: []`.
- **Split FIFO** (pedido 1901 em OT10000052, lotes 1851+1300): 2 reservas —
  1851 no FPB-2026-00003 + 50 no FPB-2026-00004. ✓

Notas de implementação:
- Line items + companies vêm dos **endpoints dedicados de associação**
  (`/crm/v3/objects/deals/{id}/associations/line_items` e `.../companies`) —
  o `?associations=` inline não popula confiável.
- Token lido com `get_password()` (campo Password decripta).
- **Item FRETE** `SV02000002` criado non-stock no UP → entra no pedido sem reservar.
- Reserva STOCK faz **split FIFO** entre lotes (`INSUFFICIENT_TOTAL` se faltar).

## Requisitos técnicos (validados)

- Server Scripts habilitados (✅ via `common_site_config`, ver [00p](00p-catalogo-produtos-lotes.md)).
- Outbound HTTP do server script (`frappe.make_get_request`) — testado OK.
- Items com SKU uppercase + lotes futuros (FPB) abertos — ver [00p](00p-catalogo-produtos-lotes.md).
