# Etapa 6 — Validar e Reservar contra FPB

> 3 flags têm que estar marcadas (`payment_validated`, `prescriptions_validated`,
> `hubspot_complete`). Quando todas True, endpoint `validate_and_reserve`
> aloca quantidade de cada item contra FPB(s) abertos via FIFO + cria
> Production Reservation(s).

## Pré-requisitos

- Sales Order criado (Etapa 5)
- `hubspot_complete = 1` (setado na criação do SO via issue_order)
- `prescriptions_validated = 1` (webhook ou seed direto)
- `payment_validated = 1` (vem via webhook ASAAS / checkout)
- SO submetido (`docstatus = 1`)
- FPB com saldo disponível pra cada Item de estoque

## Endpoints (setup_13)

### 1. `future_production_payment_webhook`

Marca payment_validated quando gateway confirma.

```python
POST /api/method/future_production_payment_webhook
{
    "sales_order": "00071",
    "amount": 1361.64,
    "status": "PAID",          # PAID | RECEIVED | CONFIRMED
    "transaction_id": "asaas_pay_xxxxx",
    "paid_at": "2026-06-02 14:00:00"
}
```

Validações:
- `status` ∈ {PAID, RECEIVED, CONFIRMED} senão flag não muda
- `amount` precisa bater com `SO.grand_total` (tolerância R$ 0,01)
- Seta `payment_validated=1`, `payment_validated_at`, `payment_reference`, `payment_amount`
- Recalcula `validation_status` automaticamente

Response típica:
```json
{
    "sales_order": "00071",
    "ok": true,
    "payment_validated": true,
    "new_validation_status": "Validado (Pronto para Reservar)",
    "ready_to_reserve": true
}
```

### 2. `future_production_prescriptions_webhook`

Marca prescriptions_validated. Payload similar — usado pelo sistema de
gestão de receitas.

### 3. `future_production_validate_and_reserve`

Aloca contra FPB. Requer SO submetido.

```python
POST /api/method/future_production_validate_and_reserve
{
    "sales_order": "00071"
}
```

Lógica:
- Lê flags. Se < 3 = True → erro "Validações incompletas"
- Lê `SO.items[]`. Pra cada `is_stock_item=1`:
  - Procura FPB(s) com mesmo `item_code` + status `Aberta para Reserva` + saldo > 0
  - FIFO: ordena por `planned_production_date ASC`
  - Cria Production Reservation com `qty = min(needed, fpb.available_qty)`
  - Repete enquanto needed > 0
- Pra `is_stock_item=0` (FRETE): retorna erro `Saldo insuficiente em FPBs disponíveis`
  → **ignorável** (esperado pra non-stock)

Response típica:
```json
{
    "sales_order": "00071",
    "ok": true,
    "reservations": [
        {
            "reservation": "00072",
            "sales_order_item": "ce1c5h33gf",
            "future_production_batch": "00070",
            "qty": 1.0
        }
    ],
    "errors": [
        {
            "item_code": "00069",
            "missing_qty": 1.0,
            "message": "Saldo insuficiente em FPBs disponiveis."
        }
    ],
    "message": "1 reserva(s) criada(s)."
}
```

## Exemplo executado em prod

```python
# Antes: payment_validated=0
POST /api/method/future_production_payment_webhook
  → payment_validated=1
  → validation_status = "Validado (Pronto para Reservar)"

# Submit SO
POST /api/method/frappe.client.submit  {sales_order: "00071"}
  → docstatus=1

# Reserva
POST /api/method/future_production_validate_and_reserve
  → Production Reservation 00072 contra FPB 00070, qty=1
  → Warning Item 00069 (FRETE) — ignorável

# Estado final SO
docstatus:         1
status:            "To Deliver and Bill"
validation_status: "Validado (Pronto para Reservar)"
```

## Estado FPB 00070 após reserva

```
Antes:                       Depois:
  planned_qty:    500          planned_qty:    500
  reserved_qty:   0            reserved_qty:   1
  available_qty:  500          available_qty:  499
```

## URLs

```
SO submitted:          https://erp.injemedpharma.com.br/app/sales-order/00071
Production Reservation:https://erp.injemedpharma.com.br/app/production-reservation/00072
FPB com saldo update:  https://erp.injemedpharma.com.br/app/future-production-batch/00070
Report Saldo por Lote: https://erp.injemedpharma.com.br/app/query-report/Saldo%20por%20Lote
```

## Erros comuns

| Erro | Causa | Fix |
|---|---|---|
| `Status do pagamento () nao indica pagamento confirmado` | Payload sem `status` ou status diferente de PAID/RECEIVED/CONFIRMED | Mandar `"status": "PAID"` |
| `Valor pago (X) nao bate com SO.grand_total (Y)` | Mismatch de centavos | Conferir cálculo; tolerância R$ 0,01 |
| `Sales Order precisa estar submetido (docstatus=1)` | Tentou reservar antes do submit | Submit primeiro |
| `Validações incompletas` | Alguma flag = 0 | Setar as 3 flags (payment + prescriptions + hubspot_complete) |
| `Saldo insuficiente em FPBs disponiveis` (pra Item stock) | Sem FPB aberta com saldo pra esse Item | Criar FPB ou esperar produção |

## Próximo

[Etapa 7 — Registrar produção (Batch físico + Stock Entry)](07-registrar-producao.md)
