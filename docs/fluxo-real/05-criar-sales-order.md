# Etapa 5 — Criar Sales Order com fp_patients

> Pedido formal no ERPNext, com tabela `fp_patients` (custom Injemed)
> linkando cada linha de Item ao Patient + opcionalmente Prescriber +
> FPB de reserva.

## Pré-requisitos

- Customer cadastrado (Etapa 2)
- Patient cadastrado (Etapa 4)
- Item ERPNext existe com SKU (vindo do sync HubSpot — etapa 0d)
- FPB aberta para o Item (Etapa 1) — pra rastrear reserva contra produção planejada
- `setup_13_so_validation` aplicado (flags + endpoints)

## Custom Fields no Sales Order (setup_13)

```
hubspot_complete           Check
hubspot_deal_id            Data
hubspot_contact_id         Data
hubspot_validated_at       Datetime

payment_validated          Check
payment_validated_at       Datetime
payment_reference          Data
payment_amount             Currency

prescriptions_validated    Check
prescriptions_validated_at Datetime
prescriptions_reference    Data
prescriptions_qty_validated Int

validation_status          Select [Aguardando..., Validado, Reservado, etc]
validation_blockers        Small Text

fp_patients                Table → Sales Order Patient
                             ├─ patient                 Link Patient
                             ├─ prescriber              Link Prescriber (optional)
                             ├─ prescriber_council_row  Link Prescriber Council (optional)
                             ├─ prescriber_council      Data ("CRM-SP 123456" auto-fetch)
                             ├─ item_code               Link Item
                             ├─ qty                     Float
                             ├─ fp_future_production_batch  Link FPB
                             ├─ batch_no                Link Batch (post-produção)
                             └─ status                  Select
```

## Item FRETE (special)

Pedido HubSpot tem linha "FRETE". ERPNext precisa Item correspondente.
Decisão: Item non-stock.

```python
POST /api/resource/Item
{
    "doctype": "Item",
    "item_name": "FRETE",
    "item_group": "Serviços",
    "stock_uom": "Unidade",
    "is_stock_item": 0,      # ← não consome estoque
    "has_batch_no": 0,       # ← sem lote
    "description": "Frete de entrega (cobrança variável, não estoque)"
}
→ name: "00069"
```

Item FRETE entra como linha no SO mas **não** gera reserva FPB (esperado:
`validate_and_reserve` retorna warning "Saldo insuficiente em FPBs
disponíveis" pra essa linha — ignorável).

## Exemplo executado em prod (2026-06-02)

Sales Order pra Gustavo Dalmora, mapping do deal HubSpot 60204250373:

```python
POST /api/resource/Sales Order
{
    "doctype": "Sales Order",
    "customer": "00067",
    "company": "Injmedpharma",
    "transaction_date": "2026-06-02",
    "delivery_date": "2026-06-09",
    "order_type": "Sales",
    "items": [
        {
            "item_code": "00049",            # Tirzepatida 90mg
            "item_name": "Tirzepatida 90mg/3,6mL",
            "qty": 1,
            "rate": 1260,
            "warehouse": "Produtos Acabados - I"
        },
        {
            "item_code": "00069",            # FRETE
            "item_name": "FRETE",
            "qty": 1,
            "rate": 101.64,
            "warehouse": "Produtos Acabados - I"
        }
    ],
    # HubSpot tracking
    "hubspot_complete": 1,
    "hubspot_deal_id": "60204250373",
    "hubspot_contact_id": "221125256039",
    # Receitas
    "prescriptions_validated": 1,
    "prescriptions_qty_validated": 1,
    "prescriptions_reference": "HubSpot deal 60204250373",
    # Pagamento (vai via webhook depois)
    "payment_validated": 0,
    # Pacientes vinculados
    "fp_patients": [
        {
            "patient": "00068",
            "item_code": "00049",
            "qty": 1,
            "fp_future_production_batch": "00070"   # FPB TIRZE90-20260602
            # prescriber: NULL (médico não identificado nesse exemplo)
        }
    ]
}
→ name: "00071"
   grand_total: 1361.64        (= 1260 + 101.64, bate com deal HubSpot)
   validation_status: "Aguardando Múltiplas Validações"
                                (payment_validated=0)
```

## URLs

```
Form SO:  https://erp.injemedpharma.com.br/app/sales-order/00071
Lista:    https://erp.injemedpharma.com.br/app/sales-order
```

## Estado do banco após SO

```
Customer 00067   Gustavo Dalmora (PF)
Patient 00068    Gustavo Dalmora
Item 00049       Tirzepatida 90mg
Item 00069       FRETE (non-stock)
FPB 00070        TIRZE90-20260602  saldo: 500 disponíveis
SO 00071         Draft → Validado     R$ 1361.64
                 Pendente: payment_webhook
```

## Próximo

[Etapa 6 — Validar e Reservar](06-validar-reservar.md)
