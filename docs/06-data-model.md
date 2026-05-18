# 06 — Data Model

Schema completo dos 4 DocTypes customizados + campos custom em Sales Order e Sales Order Item.

---

## Future Production Batch

**Tipo**: Document, Submittable, Module `Manufacturing`, `custom=1`, `track_changes=1`
**Autoname**: `naming_series:` → `FPB-.YYYY.-.#####`
**Title field**: `production_code`
**Search fields**: `production_code,item_code,status`

### Campos

| Campo | Tipo | Obrigatório | Read Only | Allow on Submit | Propósito |
|---|---|---|---|---|---|
| `naming_series` | Select `FPB-.YYYY.-.#####` | sim | — | — | Numeração |
| `production_code` | Data | sim | — | — | Identificador operacional único |
| `company` | Link / Company | sim | — | — | |
| `status` | Select | sim | — | sim | Workflow (ver abaixo) |
| `item_code` | Link / Item | sim | — | — | Produto a fabricar |
| `item_name` | Data | — | sim (fetch) | — | `fetch_from: item_code.item_name` |
| `uom` | Link / UOM | — | sim (fetch) | — | `fetch_from: item_code.stock_uom` |
| `bom` | Link / BOM | — | — | — | |
| `planned_qty` | Float | sim | — | — | `non_negative=1` |
| `reserved_qty` | Float | — | sim | sim | Calculado pelos hooks |
| `available_qty` | Float | — | sim | sim | `planned - reserved` |
| `produced_qty` | Float | — | — | sim | Quanto saiu da produção |
| `released_qty` | Float | — | sim | sim | Soma das `released_qty` das PRs |
| `pending_release_qty` | Float | — | sim | sim | `produced - released` |
| `planned_production_date` | Date | sim | — | — | |
| `expected_release_date` | Date | — | — | — | |
| `reservation_cutoff_datetime` | Datetime | — | — | — | Limite para aceitar novas reservas |
| `production_plan` | Link / Production Plan | — | — | — | |
| `work_order` | Link / Work Order | — | — | sim | Setado por `create_work_order` |
| `batch_no` | Link / Batch | — | — | sim | Lote físico real produzido |
| `target_warehouse` | Link / Warehouse | sim | — | — | Depósito de FG |
| `wip_warehouse` | Link / Warehouse | — | — | — | Depósito WIP |
| `allow_overbooking` | Check | — | — | — | Permite reservar acima do planejado |
| `overbooking_limit_qty` | Float | — | — | — | Limite extra (depends_on `allow_overbooking`) |
| `notes` | Small Text | — | — | — | |

### Status (workflow)

```
Rascunho                 (docstatus=0)
  └─► Aberta para Reserva           (docstatus=1, reserved=0)
        └─► Reservada Parcialmente   (0 < reserved < planned)
              └─► Totalmente Reservada (reserved >= planned)
                    └─► Em Produção  (work_order vinculada)
                          └─► Produzida Parcialmente (0 < produced < planned)
                                └─► Produzida Totalmente (produced >= planned)
                                      └─► Liberada Parcialmente (released > 0)
                                            └─► Liberada Totalmente (released >= produced)
  Cancelada (docstatus=2)
  Fechada para Reserva   (manual, bloqueia novas reservas)
```

A transição é automática (calculada no After Save).

### Permissões

| Role | r | w | c | d | submit | cancel | amend |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| System Manager | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Manufacturing Manager | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Manufacturing User | ✓ | ✓ | ✓ | | ✓ | | |
| Sales User | ✓ | | | | | | |
| Stock User | ✓ | | | | | | |

---

## Production Reservation

**Tipo**: Document, Submittable, Module `Manufacturing`, `custom=1`, `track_changes=1`
**Autoname**: `naming_series:` → `PR-.YYYY.-.#####`
**Title field**: `customer`

### Campos

| Campo | Tipo | Obrigatório | Read Only | Allow on Submit | Propósito |
|---|---|---|---|---|---|
| `naming_series` | Select `PR-.YYYY.-.#####` | sim | — | — | |
| `status` | Select | sim | — | sim | Reservado / Parcialmente Liberado / Liberado / Cancelado / Replanejado |
| `sales_order` | Link / Sales Order | sim | — | — | |
| `sales_order_item` | Data | sim | — | — | `name` da linha do SO Item |
| `customer` | Link / Customer | sim | — | — | `fetch_from: sales_order.customer` |
| `priority` | Int (default 100) | — | — | — | Menor = libera primeiro |
| `item_code` | Link / Item | sim | — | — | |
| `future_production_batch` | Link / Future Production Batch | sim | — | — | |
| `reserved_qty` | Float | sim | — | — | `non_negative=1` |
| `released_qty` | Float | — | sim | sim | Atualizado por `release_batch` |
| `pending_qty` | Float | — | sim | sim | `reserved - released` |
| `payment_date` | Datetime | — | — | — | Critério FIFO |
| `reservation_date` | Datetime | — | — | — | default `now` |
| `release_batch_no` | Link / Batch | — | — | sim | Lote físico que foi liberado |
| `delivery_note` | Link / Delivery Note | — | — | sim | Entrega oficial |
| `notes` | Small Text | — | — | — | |

### Status

```
Reservado (default)
  └─► Parcialmente Liberado (0 < released < reserved)
        └─► Liberado (released >= reserved)
  Cancelado (docstatus=2)
  Replanejado (reserved foi reduzido por replan e released=0)
```

---

## Patient

**Tipo**: Document (Master), **não-submittable**, Module `Manufacturing`, `custom=1`, `track_changes=1`
**Autoname**: `naming_series:` → `PAC-.YYYY.-.#####`
**Title field**: `patient_name`
**Search fields**: `patient_name,cpf,mobile`

### Campos

| Campo | Tipo | Obrigatório | Único | Validado |
|---|---|---|---|---|
| `naming_series` | Select `PAC-.YYYY.-.#####` | sim | — | — |
| `patient_name` | Data | sim | — | — |
| `cpf` | Data | — | sim | 11 dígitos não triviais (normalizado para só dígitos) |
| `rg` | Data | — | — | — |
| `birth_date` | Date | — | — | — |
| `gender` | Select (Masculino/Feminino/Outro) | — | — | — |
| `prescribing_doctor` | Link / Customer | — | — | — |
| `mobile` | Data | — | — | — |
| `phone` | Data | — | — | — |
| `email` | Data (Email) | — | — | formato email |
| `postal_code` | Data | — | — | — |
| `address_line_1` | Data | — | — | — |
| `address_number` | Data | — | — | — |
| `address_complement` | Data | — | — | — |
| `neighborhood` | Data | — | — | — |
| `city` | Data | — | — | — |
| `state` | Data | — | — | — |
| `country` | Link / Country (default Brazil) | — | — | — |
| `notes` | Small Text | — | — | — |

### Validações (Server Script `Patient - Validate CPF`)

- Se `cpf` preenchido:
  - Strip tudo que não é dígito
  - Precisa ter 11 caracteres restantes
  - Não pode ser todos iguais (ex: `11111111111`)
- O CPF é armazenado **só com dígitos** (sem máscara). Use `123.456.789-09` no input que ele vira `12345678909`.

---

## Sales Order Patient (Child Table)

**Tipo**: Document, `istable=1`, Module `Manufacturing`, `custom=1`
**Editable grid**: sim
**Não tem `name` próprio** — usa `name` random como toda child table

### Campos

| Campo | Tipo | Obrigatório | Read Only | Fetch |
|---|---|---|---|---|
| `patient` | Link / Patient | sim | — | — |
| `patient_name` | Data | — | sim | `patient.patient_name` |
| `cpf` | Data | — | sim | `patient.cpf` |
| `mobile` | Data | — | sim | `patient.mobile` |
| `item_code` | Link / Item | sim | — | — |
| `qty` | Float | sim | — | — |
| `delivery_address_override` | Small Text | — | — | — |
| `notes` | Small Text | — | — | — |

Aparece em **`Sales Order.fp_patients`** (custom field do tipo Table).

---

## Custom Fields em `Sales Order Item`

Espelho da reserva — todos `read_only=1`, populados pelos hooks da PR.

| Campo | Tipo | Default |
|---|---|---|
| `fp_section` | Section Break "Produção Futura" (insert_after `delivery_date`, `collapsible=1`) | — |
| `fp_future_production_batch` | Link / Future Production Batch | — |
| `fp_reserved_qty` | Float | 0 |
| `fp_column_break` | Column Break | — |
| `fp_released_qty` | Float | 0 |
| `fp_pending_release_qty` | Float | 0 |
| `fp_reservation_status` | Select | "Sem Reserva" |

### Opções de `fp_reservation_status`
```
Sem Reserva
Reservado
Parcialmente Reservado
Liberado
Parcialmente Liberado
Pendente
```

---

## Custom Fields em `Sales Order`

| Campo | Tipo | Insert After |
|---|---|---|
| `fp_patients_section` | Section Break "Pacientes" | `items` |
| `fp_patients` | Table → Sales Order Patient | `fp_patients_section` |

---

## Relacionamentos

```
┌──────────────────────┐
│ Future Production    │  1
│      Batch           │
│                      │
└────────┬─────────────┘
         │ 1
         │
         │ N
         ▼
┌──────────────────────┐
│ Production           │  N
│   Reservation        │
│ - sales_order        │──── 1 ────┐
│ - sales_order_item   │           │
│ - item_code          │           │
└──────────────────────┘           ▼
                           ┌──────────────────────┐
                           │   Sales Order        │
                           │   + items[]          │
                           │   + fp_patients[]    │  ◄── child table
                           └──────────┬───────────┘
                                      │ N
                                      ▼
                           ┌──────────────────────┐
                           │ Sales Order Patient  │  N
                           │ - patient (Link)     │── 1 ──►  Patient
                           │ - item_code          │
                           │ - qty                │
                           └──────────────────────┘
```

## Fórmulas

```
Future Production Batch
  available_qty       = planned_qty - reserved_qty
  pending_release_qty = produced_qty - released_qty

Production Reservation
  pending_qty = reserved_qty - released_qty

Validações de saldo
  reserved_qty[FPB]   <= planned_qty + overbooking_limit_qty  (RB-004, RB-005)
  released_qty[FPB]   <= produced_qty                          (RB-006)
  released_qty[PR]    <= reserved_qty[PR]                      (RB-006)
```

## Naming

| DocType | Series | Exemplo |
|---|---|---|
| Future Production Batch | `FPB-.YYYY.-.#####` | `FPB-2026-00003` |
| Production Reservation  | `PR-.YYYY.-.#####`  | `PR-2026-00027` |
| Patient | `PAC-.YYYY.-.#####` | `PAC-2026-00014` |
