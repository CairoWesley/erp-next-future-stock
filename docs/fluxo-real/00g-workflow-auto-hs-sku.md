# Workflow Automático — Set `line_item.hs_sku` no HubSpot

> Problema: line_items HubSpot são criados sem `hs_sku` (instâncias do
> product no deal não herdam sku do product no catálogo). Backend
> `validacao_receita` (`import.service.ts:147`) recusa import quando
> `line_item.hs_sku` está vazio.
>
> Solução: HubSpot Workflow detecta novo line_item → webhook n8n →
> lookup `product.hs_sku` (do catálogo) → PATCH `line_item.hs_sku`.
>
> Pra FRETE, sku hardcoded = `SV02000002` (backend já filtra por isso).

## Componentes

| Ator | O quê | Onde |
|---|---|---|
| **HubSpot Workflow** | Trigger quando line_item criado/atualizado E hs_sku vazio | UI Settings → Workflows |
| **HubSpot webhook action** | POST pro n8n com line_item payload | dentro do workflow |
| **n8n workflow** | Recebe webhook → classifica (skip / FRETE / lookup) → GET product → PATCH line_item | n8n.injemedpharma.com.br |
| **HubSpot API** | GET product.hs_sku + PATCH line_item.hs_sku | https://api.hubapi.com |

## Setup passo a passo

### 1. n8n — importar workflow

```
1. Acessa https://n8n.injemedpharma.com.br
2. New workflow → Import from File
3. Seleciona n8n_workflows/set_line_item_sku.json (deste repo)
4. Workflow abre com 8 nodes
5. Webhook node → copia o "Production URL" (algo tipo
   https://n8n.injemedpharma.com.br/webhook/hubspot/line-item-created)
6. Ativa workflow (toggle topo direito)
```

### 2. n8n — env var

n8n precisa do token HubSpot pra fazer GET product + PATCH line_item.

```
n8n → Settings → Variables (ou Environment Variables)
Add:
  HUBSPOT_ACCESS_TOKEN = pat-na1-xxxxxxxx
```

(mesmo Private App token usado em `tools/sync_products_hubspot.py`)

### 3. HubSpot — criar Workflow

```
HubSpot UI → Automations → Workflows → Create workflow
  Type: Line item-based
  Name: Auto set hs_sku
  Description: Quando line_item criado sem hs_sku, completa via webhook n8n

Enrollment trigger:
  Line item: Create date is known
  AND
  Line item: hs_sku is unknown (vazio)

Action 1 — "Send a webhook":
  Method: POST
  Webhook URL: <URL do webhook n8n copiado no passo 1>
  Include enrollment object properties:
    ☑ hs_object_id
    ☑ hs_sku
    ☑ hs_product_id
    ☑ name
    ☑ quantity
    ☑ price
  Use authentication: No (n8n não exige auth no webhook por default;
                       se quiser, adiciona basic auth ou header secret)

Save → Review → Turn on
```

### 4. Teste

```
1. HubSpot → cria um Deal teste
2. Adiciona line_item de um product existente (Tirzepatida 90mg)
3. Não preencher hs_sku manualmente
4. Espera ~30s (HubSpot Workflows não são instantâneos)
5. Volta no line_item → hs_sku deve aparecer = "00049" (SKU do
   product Tirzepatida 90mg no catálogo)
6. Repete com line_item "FRETE" → hs_sku deve virar "SV02000002"
```

## Logs / debug

```
n8n → Executions → ver últimas execuções do workflow
HubSpot → Workflow → Performance tab → ver enrollments + actions
```

## Limitações

1. **Atraso HubSpot Workflows**: ~30s a 5min até enrollar. Não é
   real-time. Pra fluxo de import urgente, ainda manual via PATCH.

2. **Line items criados ANTES do workflow estar ativo**: não dispara.
   Sweep manual via `tools/sweep_line_items_sku.py` (TODO criar) ou
   batch update no MCP HubSpot.

3. **product no catálogo SEM hs_sku**: workflow tenta lookup mas falha.
   Resolver pelo `tools/sync_products_hubspot.py --skip-writeback=false`.

4. **Custom Code action HubSpot** (Operations Hub Pro) eliminaria
   o webhook + n8n. Mas requer tier pago.

## Por que não webhook direto pro backend Node?

Backend Node hoje **não tem rota** `/webhooks/hubspot/line-item-created`.
Criar rota nova exige PR no `backend-sistema-receitas`. n8n é mais
leve pra essa task — código JS inline + zero deploy.

Se mais tarde decidir consolidar tudo no backend, basta:
- criar rota Node `POST /webhooks/hubspot/line-item-set-sku`
- replicar lógica do n8n Code node em TypeScript
- apontar HubSpot Workflow pra essa URL
- desativar n8n workflow

## Alternativa puramente HubSpot (Operations Hub Starter+)

```
HubSpot Workflow:
  Trigger: Line item created (hs_sku unknown)
  Action: Use the value of the property... → Copy from associated record
    Source: Product → hs_sku
    Target: Line item → hs_sku
```

⚠ Essa action **só está disponível nos planos Operations Hub Pro+**.
Tier atual Injmedpharma precisa confirmar.
