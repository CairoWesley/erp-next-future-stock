# Sync Produtos HubSpot ↔ ERPNext

> Pré-etapa. Produtos vêm do HubSpot (CRM já em uso). Sistema busca lista
> de products, cria Items no ERPNext com SKU auto-gerado, e escreve esse
> SKU de volta no HubSpot (`hs_sku` property). Garante 1 SKU consistente
> nos dois sistemas.

## Quando rodar

- **Setup inicial** — ao implantar o ERPNext, importa catálogo do HubSpot
- **Periodicamente** — produtos novos no HubSpot? Rodar sync pega + cria Items
- **Após dedup HubSpot** — limpou duplicatas? Sync reflete o novo estado

## Pré-requisitos

### HubSpot — Private App

```
1. HubSpot UI → Settings (engrenagem topo direito)
2. Integrations → Private Apps → Create a private app
3. Nome: ERPNext Sync
4. Aba "Scopes" → Data → marca:
     ☑ crm.objects.products.read
     ☑ crm.objects.products.write
5. Create app → confirma popup
6. Aba "Auth" → copia "Access token" (pat-na1-xxxxxxxx)
```

### Configuração `.env`

```bash
# Já existente:
ERPNEXT_URL=https://erp.injemedpharma.com.br
ERPNEXT_API_KEY=...
ERPNEXT_API_SECRET=...

# Adicionar:
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx
```

## Convenções

### Item naming (ERPNext)

Configurado em `setup/setup_15_naming_series.py`:
- `Stock Settings.item_naming_by = "Naming Series"`
- `Item.naming_series.default = ".#####"`

→ Cada Item novo recebe SKU `00001`, `00002`, `00003`, ...

### Pinned mapping

Items que **não** devem ser auto-criados (já existem no ERPNext por
convenção histórica):

| Nome no HubSpot | item_code ERPNext |
|---|---|
| `Tirzepatida 60mg/2,4mL` | `TIR00060` |

Configurado em `tools/sync_products_hubspot.py:PINNED_MAPPING`.

### Skip list

Records HubSpot ignorados (lixo de teste):

| Nome | Razão |
|---|---|
| `teste` | record de teste |
| `FRETE` | serviço, não produto físico |

### Dedup por nome canônico

HubSpot pode ter products duplicados (mesmo nome, IDs diferentes). Strategy:

```
norm = name.lower().strip()
# Caso especial: "TIRZEPATIDA 60MG/2,4 ML" → "Tirzepatida 60mg/2,4mL"
if "tirzepatida" in norm and "60" in norm:
    norm = "tirzepatida 60mg/2,4ml"
    canon = "Tirzepatida 60mg/2,4mL"
```

Cada grupo de nome:
- 1 Item ERPNext único
- SKU escrito apenas no **primeiro hubspot_id** do grupo (canonical)
- Demais hubspot_ids são identificados como duplicatas

## Fluxo completo

```
┌─────────────┐     1. list_all_products       ┌───────────┐
│  Script     │ ──────────────────────────────▶│  HubSpot  │
│  Python     │ ◀──────────────────────────────│           │
│             │     ~130 products              └───────────┘
│             │
│             │     2. Dedup local
│             │     (norm by canonical name)
│             │     ~65 grupos
│             │
│             │     3. Pra cada grupo:         ┌───────────┐
│             │     POST /api/resource/Item   ─│  ERPNext  │
│             │     (autoname → SKU 00001+)    │           │
│             │ ◀───────────────────────────── └───────────┘
│             │     {name: "00003", ...}
│             │
│             │     4. batch_update_products   ┌───────────┐
│             │     {id, properties:           │  HubSpot  │
│             │       {hs_sku: "00003"}}      ─│           │
│             │ ◀─────────────────────────────  └───────────┘
└─────────────┘
```

## Uso

```bash
# Sync completo (idempotente)
python tools/sync_products_hubspot.py

# Só mostra plano, não executa
python tools/sync_products_hubspot.py --dry-run

# Sync + archive duplicatas
python tools/sync_products_hubspot.py --archive-dups

# Só cria Items ERPNext (pula write-back)
python tools/sync_products_hubspot.py --skip-writeback
```

## Resultado da execução em prod (2026-06-02)

```
HubSpot products original:         132
  Filtrados (teste/FRETE):           2
  Records válidos:                 130
  Records processados:             128
  Nomes únicos:                     65

ERPNext Items:
  Reusados:                          1  (TIR00060 pinned)
  Criados auto-increment:           64  (SKUs 00003..00066)
  Total:                            65

HubSpot write-back (hs_sku):
  Updated com SKU:                  65  (1 por nome único)
  Duplicatas SEM SKU:               63  (hs_sku é UNIQUE no HubSpot)
```

## Limitações conhecidas

### 1. `hs_sku` é UNIQUE no HubSpot

HubSpot bloqueia setar o mesmo `hs_sku` em mais de 1 product:

```
error: Cannot set hs_sku=00003 on 44875033349.
       44948151596 already has that value.
```

**Workaround**: setar SKU só no primeiro hubspot_id de cada grupo
(canonical). Duplicatas ficam sem SKU. Recomendado: archive depois.

### 2. Archive via MCP HubSpot

MCP `manage_crm_objects` **não** suporta archive direto:
```
error: Property "archived" does not exist
```

Solução: usar API REST direto (`POST /crm/v3/objects/products/batch/archive`)
via `lib/hubspot_api.py:batch_archive_products`. Requer Private App token
(MCP não autoriza essa rota).

### 3. Properties price / cost_of_goods_sold

Portal HubSpot atual da Injmedpharma **não retorna** essas properties no
GET (provavelmente não populadas). Sync atual não importa preço — só
nome + descrição + has_batch_no=1. Setup de Item Price (Standard Selling)
fica TODO separado.

## Idempotência

| Cenário | Comportamento |
|---|---|
| Item ERPNext já existe (mesmo `item_name`) | Reusa `item_code` existente |
| HubSpot product já tem `hs_sku` igual ao calculado | Skip (log: já tem hs_sku=...) |
| Re-rodar sync após criar product novo no HubSpot | Detecta + cria Item + write back |
| Duplicata HubSpot adicionada após sync | Identifica + tenta write back → erro hs_sku unique → entra na lista de dups |

## TODO

- [ ] Archive das 63 duplicatas HubSpot atuais (executar `--archive-dups` quando Private App estiver configurada)
- [ ] Importar `price` HubSpot → Item Price (Standard Selling) — quando portal popular essa property
- [ ] Webhook bidirecional: produto novo no HubSpot dispara sync automático
- [ ] n8n workflow exporta o script Python como step pra rodar em cron
