# 04 — Fluxos de Uso

Dois fluxos operacionais cobrem 95% do dia a dia:

- **Fluxo A** — Criar pedido com reserva (do CRM até a PR submetida)
- **Fluxo B** — Efetivar lote após a produção (do batch físico até a entrega)

Cada um descrito **pela UI** (clique a clique) e **pela API** (sequência de chamadas).

---

## Fluxo A — Criar pedido com reserva

### Diagrama

```
[Vendedor / CRM]
     │
     ▼
GET FPB com saldo ───► (sem saldo? → criar FPB primeiro)
     │
     ▼
POST Patient (se novo)
     │
     ▼
POST Sales Order (com fp_patients[])
     │
     ▼
POST submit do Sales Order
     │
     ▼
POST future_production_reserve_sales_order_item
     │
     ▼
[Reserva criada, saldo do FPB decrementado]
```

### Pela UI — passo a passo

#### Etapa 0 (se necessário) — Criar Future Production Batch

1. Menu lateral → **Produção Futura → Lote de Produção Futura → Novo**
2. Preencher:
   - **Código da Produção**: identificador único (ex: `AMP-2026-05-20-001`)
   - **Empresa**: sua company
   - **Produto a Produzir**: o Item
   - **Quantidade Planejada**: ex: `2000`
   - **Data Prevista de Produção**: data
   - **Depósito de Produto Acabado**: ex: `Produtos Acabados - I`
   - **Status**: `Aberta para Reserva`
3. **Save** → rascunho. **Submit** → fica `docstatus=1` e passa a aceitar reservas.

#### Etapa 1 — Cadastrar pacientes (se novos)

1. **Produção Futura → Paciente → Novo**
2. Preencher: nome, CPF (11 dígitos), médico prescritor, contato, endereço
3. **Save**

#### Etapa 2 — Criar Sales Order vindo do CRM

1. CRM nativo do Frappe: *Lead → Opportunity → Quotation → Sales Order* (botão **Create → Sales Order** dentro da Quotation aceita)
2. No Sales Order:
   - Conferir cliente (médico), items, qty, delivery_date
   - **Adicionar pacientes**: role até a seção *Pacientes* e clique *Add Row*. Para cada paciente: escolha o Patient (Link), o item_code (deve estar na lista de items do SO) e a qty
   - **Soma das qty dos pacientes por item = qty do item no SO**. Se não bater, o Before Save bloqueia com mensagem clara.
3. **Save**
4. **Submit** → `docstatus=1`. Agora pode reservar.

#### Etapa 3 — Reservar

Duas formas:

**3a. Reservar em UM lote específico** (operador escolhe):
1. Botão **Produção Futura → Reservar em Produção Futura**
2. Diálogo abre. Escolher:
   - Linha do pedido (qual item)
   - Lote de Produção Futura (já filtrado pelo item do SO)
   - Quantidade
   - Prioridade (padrão 100, menor libera primeiro)
3. **Reservar**

**3b. Reservar automaticamente** (sistema distribui):
1. Botão **Produção Futura → Reservar Automaticamente**
2. Confirme
3. Sistema busca FPBs do item, ordena pela `planned_production_date asc` e vai consumindo saldo até completar o SO

#### Etapa 4 — Validar

- Botão **Produção Futura → Ver Reservas do Pedido**
- No Sales Order Item, conferir: `fp_reserved_qty`, `fp_reservation_status = "Reservado"`, `fp_future_production_batch` preenchido
- No FPB, conferir: `reserved_qty` aumentou, `available_qty` caiu, `status` mudou (`Reservada Parcialmente` ou `Totalmente Reservada`)

### Pela API — sequência de chamadas

#### 1. Listar FPB com saldo para o item

```http
GET /api/resource/Future Production Batch
  ?fields=["name","production_code","planned_qty","available_qty","planned_production_date"]
  &filters=[["item_code","=","TIR00060"],["docstatus","=",1],
            ["status","in",["Aberta para Reserva","Reservada Parcialmente"]],
            ["available_qty",">",0]]
  &order_by=planned_production_date asc
```

#### 2. (Opcional) Criar Patient

```http
POST /api/resource/Patient
{
  "patient_name": "Maria Aparecida Silva",
  "cpf": "11144477735",
  "mobile": "11999990001",
  "city": "São Paulo",
  "state": "SP",
  "country": "Brazil",
  "prescribing_doctor": "TEST-PF-Alfa"
}
```

#### 3. Criar Sales Order

```http
POST /api/resource/Sales Order
{
  "customer": "TEST-PF-Alfa",
  "company": "Injmedpharma",
  "transaction_date": "2026-05-17",
  "delivery_date": "2026-06-17",
  "currency": "BRL",
  "selling_price_list": "Venda Padrão",
  "items": [
    { "item_code": "TIR00060", "qty": 10, "rate": 100,
      "delivery_date": "2026-06-17", "warehouse": "Produtos Acabados - I" }
  ],
  "fp_patients": [
    { "patient": "PAC-2026-00014", "item_code": "TIR00060", "qty": 3 },
    { "patient": "PAC-2026-00015", "item_code": "TIR00060", "qty": 2 },
    { "patient": "PAC-2026-00016", "item_code": "TIR00060", "qty": 4 },
    { "patient": "PAC-2026-00017", "item_code": "TIR00060", "qty": 1 }
  ]
}
```

**Atenção**: a soma das `qty` por item nos `fp_patients` deve igualar a `qty` do item no SO.

Retorna `data.name = "SAL-ORD-2026-00031"` e `data.items[0].name = "<row_id>"`.

#### 4. Submeter o SO

```http
POST /api/method/frappe.client.submit
{"doc": <body INTEIRO retornado em 3, incluindo modified>}
```

Mandar o doc completo evita `TimestampMismatchError`.

#### 5. Reservar

```http
POST /api/method/future_production_reserve_sales_order_item
{
  "sales_order": "SAL-ORD-2026-00031",
  "sales_order_item": "<row_id da etapa 3>",
  "future_production_batch": "FPB-2026-00003",
  "qty": 10,
  "priority": 100
}
```

Resposta:
```json
{"message": {
  "reservation": "PR-2026-00027",
  "future_production_batch": "FPB-2026-00003",
  "reserved_qty": 10,
  "available_qty_after": 1990
}}
```

#### 6. Confirmar

```http
GET /api/resource/Sales Order/SAL-ORD-2026-00031
```

Verifique nos items: `fp_reserved_qty=10`, `fp_reservation_status="Reservado"`, `fp_future_production_batch="FPB-2026-00003"`.

---

## Fluxo B — Efetivar lote após produção

### Diagrama

```
[Produção termina]
     │
     ▼
POST Batch (registra lote físico)
     │
     ▼
PUT FPB {produced_qty, batch_no}
     │
     ▼
POST future_production_release_batch (FIFO)
     │
     ▼
POST Stock Entry Manufacture (entrada física opcional)
     │
     ▼
POST Pick List (por SO)
     │
     ▼
POST Delivery Note
```

### Pela UI

#### Etapa 1 — Criar Batch real

1. **Stock → Batch → Novo**
2. Preencher:
   - **Batch ID**: ex: `LOT-AMP-2026-05-20-001`
   - **Item**: TIR00060
   - **Batch Qty**: 1850
   - **Manufacturing Date**: data da produção
   - **Expiry Date**: validade

#### Etapa 2 — Atualizar FPB com produção real

1. Abra o FPB submetido
2. Edite:
   - **Quantidade Produzida**: `1850`
   - **Lote Real Produzido**: `LOT-AMP-2026-05-20-001`
3. **Save**

> Edição de campos pós-submit funciona porque `produced_qty` e `batch_no` têm
> `allow_on_submit=1`.

O After Save ajusta o status para `Produzida Parcialmente` ou `Produzida Totalmente`.

#### Etapa 3 — Liberar reservas

1. No FPB → botão **Ações → Liberar Reservas**
2. Confirme

Sistema distribui o `produced_qty` entre as PRs do FPB seguindo a regra FIFO:
1. `priority` ASC (menor primeiro)
2. `payment_date` ASC (mais antigo primeiro)
3. `reservation_date` ASC
4. `creation` ASC

Cada PR fica com `released_qty` ≤ `reserved_qty`. Se o produzido acabar antes, sobram PRs com `pending_qty > 0`.

#### Etapa 4 — Pick List por SO

Para cada Sales Order com `fp_released_qty > 0`:
1. Abra o SO → **Create → Pick List**
2. Confirme as quantidades e o **batch_no** sugerido
3. **Save → Submit**

#### Etapa 5 — Delivery Note

A partir do Pick List submetido:
1. Botão **Create → Delivery Note**
2. **Save → Submit**

Entrega oficial.

### Pela API

#### 1. Criar Batch

```http
POST /api/resource/Batch
{
  "batch_id": "LOT-AMP-2026-05-20-001",
  "item": "TIR00060",
  "batch_qty": 1850,
  "manufacturing_date": "2026-05-20",
  "expiry_date": "2027-05-20"
}
```

#### 2. Atualizar FPB

```http
PUT /api/resource/Future Production Batch/FPB-2026-00003
{
  "produced_qty": 1850,
  "batch_no": "LOT-AMP-2026-05-20-001"
}
```

#### 3. Liberar reservas

```http
POST /api/method/future_production_release_batch
{"future_production_batch": "FPB-2026-00003"}
```

Resposta:
```json
{"message": {
  "future_production_batch": "FPB-2026-00003",
  "released_count": 4,
  "remaining_to_release": 0,
  "released_qty": 1850,
  "pending_release_qty": 0
}}
```

#### 4. (Opcional) Stock Entry de Manufacture

Para registrar a entrada física do FG no depósito (se não usou Work Order):

```http
POST /api/resource/Stock Entry
{
  "stock_entry_type": "Manufacture",
  "company": "Injmedpharma",
  "posting_date": "2026-05-20",
  "items": [{
    "t_warehouse": "Produtos Acabados - I",
    "item_code": "TIR00060",
    "qty": 1850,
    "basic_rate": 50,
    "batch_no": "LOT-AMP-2026-05-20-001"
  }]
}

POST /api/method/frappe.client.submit
{"doc": <body anterior>}
```

#### 5. Pick List + Delivery Note

```http
POST /api/resource/Pick List
{
  "company": "Injmedpharma",
  "purpose": "Delivery",
  "locations": [{
    "sales_order": "SAL-ORD-2026-00031",
    "item_code": "TIR00060",
    "qty": 10,
    "warehouse": "Produtos Acabados - I",
    "batch_no": "LOT-AMP-2026-05-20-001"
  }]
}

POST /api/method/frappe.client.submit
{"doc": <body anterior>}

# Depois:
POST /api/method/erpnext.stock.doctype.pick_list.pick_list.create_delivery_note
{"source_name": "<nome do Pick List>"}
```

---

## Casos especiais

### Replanejar saldo pendente

Quando uma PR fica com `pending_qty > 0` (porque a produção saiu menor), o saldo pode ser movido para um próximo FPB:

**Pela UI**: no Production Reservation → **Ações → Replanejar Pendência** → escolher FPB destino + qty

**Pela API**:
```http
POST /api/method/future_production_replan_pending_qty
{
  "source_reservation": "PR-2026-00027",
  "target_future_production_batch": "FPB-2026-00004",
  "qty": 150
}
```

Cria nova PR no destino, decrementa a original, atualiza saldos das duas FPBs.

### Cancelar uma reserva

Cancele via UI (botão *Cancel*) ou:

```http
POST /api/method/frappe.client.cancel
{"doctype": "Production Reservation", "name": "PR-2026-00027"}
```

O `On Cancel` devolve o saldo ao FPB automaticamente.

### Recalcular FPB (manutenção)

Se houver inconsistência (raro, mas pode acontecer após operações manuais via SQL):

```http
POST /api/method/future_production_recalculate_batch
{"future_production_batch": "FPB-2026-00003"}
```

Re-soma todas as PRs submetidas e atualiza `reserved_qty`, `released_qty`, `available_qty`, `pending_release_qty`, `status`.

### Criar Work Order a partir do FPB

```http
POST /api/method/future_production_create_work_order
{"future_production_batch": "FPB-2026-00003"}
```

Busca BOM ativa do item, cria Work Order vinculada, atualiza `status` do FPB para "Em Produção".

### Rastreabilidade lote físico → paciente

Hoje a relação é indireta:
1. Dado um Batch `LOT-X`, encontrar PRs onde `release_batch_no = LOT-X`
2. Para cada PR, abrir o `sales_order` referenciado
3. No SO, ler `fp_patients` filtrando por `item_code` da PR

Não há tabela direta `Batch → Patient`. Se a auditoria exigir, ver [`07-business-rules.md`](07-business-rules.md) (RB-006) para a proposta de adicionar `release_batch_no` na linha de paciente.
