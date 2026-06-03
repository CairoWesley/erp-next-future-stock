# Pedido REAL Executado — Paulo César (deal 60801476407)

> Primeiro pedido sincronizado pela rota completa: HubSpot Deal +
> sistema validacao_receita + checkout_simples (pagamento) → ERPNext.
> Executado em 2026-06-03.

## Fontes de dados (cada um cuida do seu)

| Fonte | O que provê | Tabelas/Endpoints |
|---|---|---|
| **HubSpot CRM** | Deal + Company (cliente PJ/PF) + Contact + line_items (produtos) | objects Deal/Company/Contact/Line item |
| **validacao_receita** (Postgres) | Patient + Médico (CRM/UF) + receita + validation | `validacao_receita.{orders, deal_companies, patients, validations}` |
| **checkout_simples** (Postgres) | Pagamento (valor, status, paid_at, payer info) | `checkout_simples.{checkouts, transactions, payers}` |

## Dados consolidados do pedido

```
[Deal HubSpot 60801476407]
  Nome:     PAULO CESAR MOURA JUNIOR - 02/06/2026
  Valor:    R$ 1.963,98
  Stage:    contractsent
  Owner:    Janaina Lima

[Company HubSpot 55411491512 = pagador]
  Nome:     PAULO CESAR MOURA JUNIOR (PF Volpi — médico revende)
  CPF:      00092473199
  CRM:      16245-DF Regular
  Endereço: IAPI Chácara 15A casa 4, Guará II, Brasília-DF, 71081175

[Contact HubSpot 225845250711]
  Email:    pcmourajr@gmail.com
  Phone:    +55618146825

[Line items HubSpot]
  55750240770  TIRZEPATIDA 60MG/2,4 ML  qty=1  R$ 1.800,00  hs_sku=TIR00060
  55750240771  FRETE                    qty=1  R$   163,98  hs_sku=SV02000002

[validacao_receita.orders 1]
  status=completo  hubspot_deal_id=60801476407
  pedido_fc_emitido_at=2026-06-03 (marca de sync ERPNext)

[validacao_receita.patients 1]
  CPF:                  00593976169
  Nome:                 EVELINE JAJAH FRANCO MOURA
  Médico:               PAULO CESAR MOURA JUNIOR (CRM 16245-DF)
  Validation:           aprovado
  Assinatura digital:   válida
  Posologia:            ...
  Receita:              <PDF>

[checkout_simples — pagamento]
  checkout cmpwx8ep800p5yxqf019dbtn5
    description:      "60801476407 - R$ 1.963,98 - Janaina Lima"
    external_ref:     60801476407   ← link com HubSpot deal id
    amount_cents:     196398
  transaction cmpwzng0u00pjyxqfq4ya11zn
    status=PAID  payment_method=CREDIT_CARD  paid_at=2026-06-02 18:46:15
    provider:     credpay
    card:         VISA ****6659
  payer
    name:         Paulo César Moura Junior
    cpf:          00092473199
    email:        pcmourajr@gmail.com
    phone:        61981468252
    endereço:     Setor Habitacional IAPI Chácara 15A, Casa 4, Guará II, 71081175
```

## ERPNext — IDs criados

```
Customer 00074    Paulo César Moura Junior (Individual, group=Volpi)
                  tax_id=00092473199
Address           Paulo César Moura Junior-Faturamento
Contact           Paulo César Moura Junior-00074-1
Prescriber 00075  Paulo César (CRM-DF 16245 Ativo)
                  council_row=fqo7u27uut
Patient 00076     Eveline Jajah Franco Moura (CPF 00593976169)
                  default_prescriber=00075
                  default_council_label=CRM-DF 16245
Sales Order 00077 docstatus=1  status=To Deliver and Bill
                  grand_total=R$ 1.963,98
                  validation_status=Validado (Pronto para Reservar)
                  hubspot_deal_id=60801476407
                  hubspot_contact_id=225845250711
                  items:
                    TIR00060  qty=1  rate=1800
                    00069     qty=1  rate=163,98   (FRETE)
                  fp_patients:
                    patient=00076  prescriber=00075
                    prescriber_council_row=fqo7u27uut
                    item_code=TIR00060  qty=1
                    fp_future_production_batch=FPB-2026-00115
Production Reservation 00078
                  1 ampola Tirzepatida 60mg reservada contra FPB-2026-00115
Payment webhook   PAID, transaction_id=cmpwzng0u00pjyxqfq4ya11zn (real)
                  amount=1963,98  paid_at=2026-06-02 18:46:15
```

## Estado FPB-2026-00115 após reserva

```
Antes:                       Depois:
  planned_qty:    2000          planned_qty:    2000
  reserved_qty:   0             reserved_qty:   1
  available_qty:  2000          available_qty:  1999
```

## Quem faz o que (fluxo executado)

| Ator | Ação | Sistema |
|---|---|---|
| **operador** | criou paciente Eveline vinculado ao deal | frontend validacao-receita |
| **validador** | aprovou receita | frontend validacao-receita |
| **sistema validacao** | `order.status='completo'` via recomputeOrderState | backend Node auto |
| **gateway credpay** | confirmou pagamento (Paulo paga com cartão) | checkout_simples auto |
| **eu (claude)** | queryei Postgres + HubSpot + executei sync ERPNext | script Python |
| **ERPNext** | criou Customer + Address + Contact + Prescriber + Patient + SO + PR | Server Scripts |

Em produção final esse último passo é:
**user clica botão no HubSpot Card → webhook n8n → n8n executa script equivalente.**

## URLs ERPNext

```
Customer:     https://erp.injemedpharma.com.br/app/customer/00074
Patient:      https://erp.injemedpharma.com.br/app/patient/00076
Prescriber:   https://erp.injemedpharma.com.br/app/prescriber/00075
Sales Order:  https://erp.injemedpharma.com.br/app/sales-order/00077
Production Reservation: https://erp.injemedpharma.com.br/app/production-reservation/00078
FPB:          https://erp.injemedpharma.com.br/app/future-production-batch/FPB-2026-00115
```

## Próximas etapas do fluxo

8. Registrar produção (criar Batch físico TIRZE60-20260602 com 2000 ampolas)
9. Stock Entry Manufacture
10. Liberar reservas (PR → Batch real)
11. Alocar Batch por paciente (Eveline recebe ampola do Batch criado)
12. Delivery Note
13. Sales Invoice
14. Payment Entry (vincular ao transaction_id checkout_simples)
15. Dispensação + etiqueta Zebra
16. Marcar dispensado
