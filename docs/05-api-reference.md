# 05 — Referência da API

Todas as chamadas exigem autenticação por token:

```
Authorization: token <API_KEY>:<API_SECRET>
Content-Type: application/json
Accept: application/json
```

URL base nos exemplos: `$ERPNEXT_URL` (ex: `https://erp.suaempresa.com.br`).

## Sumário

| Categoria | Endpoint |
|---|---|
| Autenticação | `GET /api/method/frappe.auth.get_logged_user` |
| **Future Production Batch** | CRUD via `/api/resource/Future Production Batch` |
| **Production Reservation** | CRUD via `/api/resource/Production Reservation` |
| **Patient** | CRUD via `/api/resource/Patient` |
| **Endpoints custom** | `POST /api/method/future_production_*` |
| Sales Order com pacientes | CRUD via `/api/resource/Sales Order` (campo `fp_patients`) |

---

## 1. Endpoints customizados (`/api/method/...`)

### 1.1. `future_production_reserve_sales_order_item`

Reserva 1 linha de Sales Order em 1 Future Production Batch específico.

**Método**: POST
**URL**: `/api/method/future_production_reserve_sales_order_item`

**Body**:
```json
{
  "sales_order": "SAL-ORD-2026-00031",
  "sales_order_item": "<row_id>",
  "future_production_batch": "FPB-2026-00003",
  "qty": 10,
  "priority": 100
}
```

**Resposta 200**:
```json
{
  "message": {
    "reservation": "PR-2026-00027",
    "future_production_batch": "FPB-2026-00003",
    "reserved_qty": 10,
    "available_qty_after": 1990
  }
}
```

**Validações que podem falhar**:
- `sales_order, sales_order_item, future_production_batch` obrigatórios
- `qty > 0`
- Sales Order precisa estar submetido (`docstatus=1`)
- A linha `sales_order_item` precisa existir no SO
- `item_code` da linha do SO **igual** ao `item_code` do FPB
- `qty <= available_qty` do FPB (mais `overbooking_limit_qty` se `allow_overbooking=1`)

**Curl**:
```bash
curl -X POST "$ERPNEXT_URL/api/method/future_production_reserve_sales_order_item" \
  -H "Authorization: token $ERPNEXT_API_KEY:$ERPNEXT_API_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"sales_order":"SAL-ORD-2026-00031","sales_order_item":"abc123","future_production_batch":"FPB-2026-00003","qty":10,"priority":100}'
```

### 1.2. `future_production_auto_reserve_sales_order`

Distribui automaticamente um Sales Order entre FPBs disponíveis (sem precisar escolher).

**Body**:
```json
{"sales_order": "SAL-ORD-2026-00031"}
```

**Resposta**:
```json
{
  "message": {
    "sales_order": "SAL-ORD-2026-00031",
    "reservations": [
      {"reservation": "PR-2026-00027", "sales_order_item": "<row>",
       "future_production_batch": "FPB-2026-00003", "qty": 10}
    ],
    "errors": []
  }
}
```

**Lógica**:
1. Para cada item do SO, calcula `pending = qty - fp_reserved_qty`
2. Busca FPBs com `item_code = item.item_code`, `docstatus=1`, status `Aberta para Reserva` / `Reservada Parcialmente` / `Em Produção` / `Produzida Parcialmente`
3. Ordena por `planned_production_date asc, creation asc`
4. Pega saldo de cada FPB até completar `pending`
5. Pode dividir 1 item entre múltiplos FPBs

### 1.3. `future_production_recalculate_batch`

Recalcula `reserved_qty`, `released_qty`, `available_qty`, `pending_release_qty`, `status` de um FPB com base nas PRs submetidas.

**Body**:
```json
{"future_production_batch": "FPB-2026-00003"}
```

**Resposta**:
```json
{
  "message": {
    "future_production_batch": "FPB-2026-00003",
    "planned_qty": 2000,
    "reserved_qty": 10,
    "available_qty": 1990,
    "produced_qty": 0,
    "released_qty": 0,
    "pending_release_qty": 0,
    "status": "Reservada Parcialmente"
  }
}
```

Use para reconciliar quando há suspeita de inconsistência (ex: após operações manuais via console SQL).

### 1.4. `future_production_create_work_order`

Cria Work Order para o FPB, usando BOM padrão ativa do item.

**Body**:
```json
{"future_production_batch": "FPB-2026-00003"}
```

**Resposta**:
```json
{
  "message": {
    "future_production_batch": "FPB-2026-00003",
    "work_order": "MFG-WO-2026-00001",
    "bom": "BOM-TIR00060-001"
  }
}
```

**Falha se**:
- FPB não submetido
- Já tem `work_order` vinculada
- Item sem BOM padrão ativa

Atualiza o FPB com `work_order=<wo>` e `status="Em Produção"`.

### 1.5. `future_production_release_batch`

Distribui `produced_qty` entre as Production Reservations do FPB seguindo regra FIFO.

**Body**:
```json
{"future_production_batch": "FPB-2026-00003"}
```

**Resposta**:
```json
{
  "message": {
    "future_production_batch": "FPB-2026-00003",
    "released_count": 4,
    "remaining_to_release": 0,
    "released_qty": 1850,
    "pending_release_qty": 0
  }
}
```

**Pré-condições**:
- `produced_qty > 0`
- `batch_no` preenchido (Link válido para Batch existente)

**Regra de distribuição** (ordem):
1. `priority` ASC (menor primeiro)
2. `payment_date` ASC
3. `reservation_date` ASC
4. `creation` ASC

Para cada PR processada:
- Define `released_qty += take`
- Define `pending_qty -= take`
- Grava `release_batch_no` da PR = `batch_no` do FPB
- Atualiza `status` ("Liberado" se zerou pending, senão "Parcialmente Liberado")
- Atualiza espelho no Sales Order Item (`fp_released_qty`, `fp_pending_release_qty`, `fp_reservation_status`)

### 1.6. `future_production_replan_pending_qty`

Move parte do saldo pendente de uma PR para outra FPB.

**Body**:
```json
{
  "source_reservation": "PR-2026-00027",
  "target_future_production_batch": "FPB-2026-00004",
  "qty": 150
}
```

**Resposta**:
```json
{
  "message": {
    "source_reservation": "PR-2026-00027",
    "new_reservation": "PR-2026-00028",
    "target_future_production_batch": "FPB-2026-00004",
    "qty": 150
  }
}
```

**Validações**:
- Reserva origem submetida
- `qty <= pending_qty` da origem
- `item_code` da PR origem = `item_code` do FPB destino
- Saldo disponível no FPB destino

**Efeitos**:
- Reduz `reserved_qty` da PR origem
- Atualiza status da PR origem ("Replanejado" se zerou e nada foi liberado, "Liberado" se zerou após liberar tudo, "Parcialmente Liberado" caso contrário)
- Cria nova PR no FPB destino com os mesmos dados (SO, paciente, item, priority, payment_date)
- Recalcula saldos das duas FPBs

---

## 2. CRUD genérico de DocType (REST padrão)

### Future Production Batch

#### Criar
```http
POST /api/resource/Future Production Batch
{
  "production_code": "AMP-2026-05-20-001",
  "company": "Sua Empresa Ltda",
  "item_code": "TIR00060",
  "planned_qty": 2000,
  "planned_production_date": "2026-05-20",
  "target_warehouse": "Produtos Acabados - I",
  "status": "Aberta para Reserva"
}
```

#### Listar (com filtros e campos)
```http
GET /api/resource/Future Production Batch
  ?fields=["name","production_code","item_code","planned_qty","available_qty","status"]
  &filters=[["docstatus","=",1],["available_qty",">",0]]
  &order_by=planned_production_date asc
  &limit_page_length=50
```

#### Ler 1 doc
```http
GET /api/resource/Future Production Batch/FPB-2026-00003
```

#### Atualizar (campos com `allow_on_submit=1`)
```http
PUT /api/resource/Future Production Batch/FPB-2026-00003
{
  "produced_qty": 1850,
  "batch_no": "LOT-AMP-2026-05-20-001"
}
```

#### Submeter
```http
POST /api/method/frappe.client.submit
{"doc": <body retornado em GET, com modified>}
```

#### Cancelar
```http
POST /api/method/frappe.client.cancel
{"doctype": "Future Production Batch", "name": "FPB-2026-00003"}
```

#### Deletar (precisa estar `docstatus=0` ou `2`)
```http
DELETE /api/resource/Future Production Batch/FPB-2026-00003
```

### Production Reservation, Patient

Mesma API REST padrão. Substituir o nome do DocType.

### Sales Order com `fp_patients`

Campo `fp_patients` aceita lista de objects:

```json
{
  "doctype": "Sales Order",
  "customer": "TEST-PF-Alfa",
  ...
  "items": [
    {"item_code": "TIR00060", "qty": 10, ...}
  ],
  "fp_patients": [
    {"patient": "PAC-2026-00014", "item_code": "TIR00060", "qty": 3},
    {"patient": "PAC-2026-00015", "item_code": "TIR00060", "qty": 2},
    {"patient": "PAC-2026-00016", "item_code": "TIR00060", "qty": 4},
    {"patient": "PAC-2026-00017", "item_code": "TIR00060", "qty": 1}
  ]
}
```

> A soma das `qty` por item nos pacientes deve igualar `qty` do item no SO. Validação em Before Save.

---

## 3. Erros comuns

### `ServerScriptNotEnabled`
Habilite `server_script_enabled` no bench. Ver [`08-troubleshooting.md`](08-troubleshooting.md).

### `TimestampMismatchError`
Submetendo doc sem passar o `modified` atualizado. Faça `GET` antes de `submit`:
```python
_, body = client._request("GET", f"/api/resource/{dt}/{name}")
client._request("POST", "/api/method/frappe.client.submit", json_body={"doc": body["data"]})
```

### `UpdateAfterSubmitError`
Tentou alterar campo sem `allow_on_submit=1` em doc com `docstatus=1`. Use `frappe.db.set_value` ou marque o campo como `allow_on_submit` no schema.

### `LinkValidationError: Customer Group / Territory`
Ambiente PT-BR usa nomes traduzidos. Use `customer_group="Comercial"` e `territory="Brazil"` (não `"All Customer Groups"`/`"All Territories"`).

### `ValidationError: Item ... qty do pedido (X) diferente da soma das ampolas dos pacientes (Y)`
A soma das `qty` em `fp_patients` para esse `item_code` precisa bater com `items[i].qty`. Corrija e refaça o save.

### `ValidationError: CPF precisa ter 11 digitos`
CPF do Patient com formato errado. Normalize para 11 dígitos (com ou sem máscara — o servidor strip de tudo que não é dígito).
