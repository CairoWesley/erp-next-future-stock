# Etapa 1 — Criar Future Production Batch (Lote Planejado)

> Primeira etapa do fluxo. Cria o "balde" futuro de produção onde
> reservas vão consumir saldo até que o lote físico seja fabricado.

## O que faz

`Future Production Batch (FPB)` = **promessa de fabricação**. Sistema reserva
capacidade pra vendas futuras antes do lote físico existir.

**Não é estoque real**. É declaração de intenção de produzir N ampolas do
item X na data Y, com saldo reservável de N.

## Quem faz

Planejador de Produção (PCP).

## Pré-requisitos

- Item cadastrado com `Has Batch No` marcado (TIR00060 já está)
- Warehouse "Produtos Acabados - I" existente
- Company "Injmedpharma" com permissão System Manager pro usuário API

## Padrão Injemed

### Production Code

```
TIRZE<dosagem>-YYYYMMDD
```

- `TIRZE60` = Tirzepatida 60mg
- `TIRZE90` = Tirzepatida 90mg
- `YYYYMMDD` = data de manipulação (ex: 20260602 = 2 de junho de 2026)

### Quantidade

- Capacidade da linha: 2.000 ampolas por lote (padrão)
- Pode variar (1.500, 2.500…) conforme planejamento

### Data prevista de produção

- Quando a fabricação efetivamente vai acontecer
- Pode ser hoje (manipulação no dia) ou data futura

### Data esperada de liberação

- Após período de quarentena/análise
- Padrão: 7 dias após manipulação

## Via UI (clique a clique)

### Passo 1 — Acessar

```
Menu lateral → Produção Futura → Lote de Produção Futura
```

URL direta: `https://erp.injemedpharma.com.br/app/future-production-batch`

### Passo 2 — Criar novo

Topo direito → **+ New**

### Passo 3 — Preencher

```
┌──────────────────────────────────────────────────────────────┐
│  NEW FUTURE PRODUCTION BATCH                       Save     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Código da Produção *:    TIRZE60-20260602                   │
│  ↑ Padrão: TIRZE<dosagem>-YYYYMMDD                          │
│                                                              │
│  Empresa *:               Injmedpharma                       │
│                                                              │
│  Status *:                Aberta para Reserva                │
│                                                              │
│  Produto a Produzir *:    TIR00060                           │
│  (Tirzepatida 60mg/2,4ml — preenche sozinho)                │
│                                                              │
│  Quantidade Planejada *:  2000                               │
│                                                              │
│  Data Prevista Produção *: 02/06/2026                        │
│  Data Esperada Liberação:  09/06/2026  (+7d quarentena)     │
│                                                              │
│  Depósito de PA *:        Produtos Acabados - I              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Passo 4 — Save

Save → fica como **Rascunho** (docstatus=0). Pode editar livremente.

### Passo 5 — Submit

Botão **Submit** (azul, topo direito) → **Aberta para Reserva** (docstatus=1).

Agora aceita reservas de Sales Orders.

## Via API (REST)

### Cria

```bash
curl -X POST "https://erp.injemedpharma.com.br/api/resource/Future Production Batch" \
  -H "Authorization: token <API_KEY>:<API_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{
    "production_code": "TIRZE60-20260602",
    "company": "Injmedpharma",
    "item_code": "TIR00060",
    "planned_qty": 2000,
    "planned_production_date": "2026-06-02",
    "expected_release_date": "2026-06-09",
    "target_warehouse": "Produtos Acabados - I",
    "status": "Aberta para Reserva"
  }'
```

Resposta:
```json
{
  "data": {
    "name": "FPB-2026-00115",
    "production_code": "TIRZE60-20260602",
    ...
  }
}
```

### Submete

```bash
# Pega doc completo
curl -X GET "https://erp.injemedpharma.com.br/api/resource/Future Production Batch/FPB-2026-00115" \
  -H "Authorization: token ..." > /tmp/fpb.json

# Submit (envia o doc inteiro com modified atualizado)
curl -X POST "https://erp.injemedpharma.com.br/api/method/frappe.client.submit" \
  -H "Authorization: token ..." \
  -H "Content-Type: application/json" \
  -d "{\"doc\": $(cat /tmp/fpb.json | jq .data)}"
```

### Via Python (lib do projeto)

```python
from lib.erpnext_api import client_from_env

c = client_from_env()
r = c._request('POST', '/api/resource/Future Production Batch', json_body={
    'doctype': 'Future Production Batch',
    'production_code': 'TIRZE60-20260602',
    'company': 'Injmedpharma',
    'item_code': 'TIR00060',
    'planned_qty': 2000,
    'planned_production_date': '2026-06-02',
    'expected_release_date': '2026-06-09',
    'target_warehouse': 'Produtos Acabados - I',
    'status': 'Aberta para Reserva',
})
fpb_name = r[1]['data']['name']

# Submit
_, b = c._request('GET', f'/api/resource/Future Production Batch/{fpb_name}')
c._request('POST', '/api/method/frappe.client.submit', json_body={'doc': b['data']})
```

## Resultado obtido (em prod)

```
Data execução:  2026-06-02
Production code: TIRZE60-20260602

ERPNext criou:
  name:        FPB-2026-00115
  status:      Aberta para Reserva
  docstatus:   1
  planned_qty: 2000
  reserved_qty: 0
  available_qty: 2000    ← saldo livre pra reservas
  produced_qty:  0
  released_qty:  0
```

## URLs pra inspecionar

| O que ver | URL |
|---|---|
| FPB específico | https://erp.injemedpharma.com.br/app/future-production-batch/FPB-2026-00115 |
| Lista de FPBs | https://erp.injemedpharma.com.br/app/future-production-batch |
| Workspace Produção Futura | https://erp.injemedpharma.com.br/app/producao-futura |
| Report Saldo por Lote | https://erp.injemedpharma.com.br/app/query-report/Saldo%20por%20Lote |

## Estado atual do banco

```
1 FPB submetido:
  FPB-2026-00115  TIRZE60-20260602  TIR00060  Plan=2000  Disp=2000
```

## Validações automáticas

O ERPNext valida (Server Scripts `setup_03`):

- `production_code` único (unique=1)
- `item_code` precisa existir e ter `Has Batch No=1`
- `planned_qty > 0` (non_negative=1)
- `target_warehouse` precisa existir e estar ativo
- `company` precisa existir

## Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| `Mandatory: Quantidade Planejada` | Esqueceu qty | Preencher |
| `Item must have Has Batch No` | Item sem batch | Editar Item, marcar checkbox |
| `production_code já existe` | Duplicado | Trocar data ou suffix |
| `LinkValidationError: Warehouse` | Warehouse não existe | Verificar nome exato |

## Próximo passo

[Etapa 2 — Criar Sales Order](02-criar-sales-order.md) (pedido com pacientes vinculados)
