# Etapa 8 — Financeiro Lançado + Handoff pra Manual

> Fim da automação. Tudo via API/n8n até aqui: cadastro + reserva +
> pacientes + receita + **financeiro lançado (recebimento)**. A partir
> da produção, o time opera **manual no ERPNext**.

## Fronteira automação ↔ manual

```
═══════════ AUTOMÁTICO (n8n / API) ═══════════
  1. Cadastra Cliente
  2. Cadastra Pedido (SO)
  3. Cadastra Pacientes + Médico
     └ receita anexada (validada)
  4. Reserva (lote por bin-pack)
  5. Lançar Recebimento (Payment Entry)   ← último passo automático
─────────────────────────────────────────────
═══════════ MANUAL (ERPNext UI) ══════════════
  Produção (Work Order/Batch) → Stock Entry →
  Liberar Reserva → Alocar Batch/Paciente →
  Delivery Note → Sales Invoice (NF) →
  Dispensação + Zebra → Marcar Dispensado
═══════════════════════════════════════════════
```

## Lançar Recebimento — `future_production_register_payment`

Modelo confirmado com negócio: **só Payment Entry** (sem Sales Invoice),
**valor do pagamento hoje** + **recebimento futuro**.

```json
POST /api/method/future_production_register_payment
{
  "sales_order": "00129",
  "payment": { "method": "CREDIT_CARD", "installments": 1,
               "amount": 1963.98, "paid_at": "2026-06-02 18:46:15",
               "transaction_id": "cmpwzng0u00pjyxqfq4ya11zn" }
}
→ {
  "ok": true, "method": "CREDIT_CARD", "installments": 1,
  "bank_account": "Conta Bancária - I", "mode_of_payment": "Cartão de Crédito",
  "created": [
    { "parcela": 1, "payment_entry": "00128", "valor": 1963.98,
      "posting_date": "2026-06-02", "clearance_date": "2026-07-02" }
  ],
  "skipped": []
}
```

### Como mapeia "valor hoje, recebimento futuro"

| Campo Payment Entry | Valor | Significado |
|---|---|---|
| `posting_date` | data do pagamento (hoje) | **valor lançado hoje** |
| `clearance_date` | data de liquidação (futuro) | **recebimento futuro** (compensa no banco) |
| `paid_from` | `Clientes - I` (config) | conta a receber baixada |
| `paid_to` | banco da config | onde o dinheiro entra |
| `mode_of_payment` | modo da config | Pix / Cartão / Boleto |

`clearance_date` é o campo NATIVO de Bank Reconciliation do ERPNext: o
lançamento entra hoje mas só "compensa" no banco na data futura — exatamente
"valor hoje, recebimento futuro".

### Parcelas (cartão)

Cartão N parcelas → **N Payment Entries**, parcela i com:
- `posting_date` = data do pagamento (todas hoje)
- `clearance_date` = D+(dias·i) → parcela 1 D+30, parcela 2 D+60...
- `valor` = total/N (última ajusta centavos)
- `reference_no` = `<transaction_id>-pN` (idempotência por parcela)

PIX/Boleto → 1 Payment Entry, clearance = D+1.

Os dias (30/1) + banco + modo vêm da **Config Financeira**
(`Injemed Financial Settings`, ver [00m](00m-configuracao-financeira.md)).

### Idempotência

`reference_no` = transaction_id (+ parcela). Re-chamar pula PEs já criados.
Não duplica recebimento.

## No fluxo n8n

Node **"5. Lançar Recebimento"** (após "4. Reserva", `continueOnFail`):
chama `register_payment` com `{sales_order, payment}`. O Respond devolve
`recebimento` (PEs criados + cronograma).

Validado em prod: PE 00128, valor 02/06 (hoje), clearance 02/07 (D+30),
banco "Conta Bancária - I". Re-chamada pula (idempotente).

## Próximas etapas (MANUAL no ERPNext)

A partir daqui o operador trabalha no ERPNext. Endpoints existem pra
apoiar mas o disparo é manual:

| # | Etapa | Endpoint de apoio | Quem |
|---|---|---|---|
| 9 | Produção (Work Order) | `future_production_create_work_order` (precisa BOM) | PCP |
| 10 | Stock Entry (Batch real) | nativo ERPNext | produção |
| 11 | Liberar Reserva | `future_production_release_batch` | produção |
| 12 | Alocar Batch/Paciente | `future_production_allocate_patient_batches` | produção |
| 13 | Delivery Note | nativo ERPNext | expedição |
| 14 | Sales Invoice (NF) | nativo ERPNext | fiscal |
| 15 | Dispensação + Zebra | `create_dispensation_from_so` + `generate_zpl_label` + `mark_label_printed` | farmacêutico |
| 16 | Marcar Dispensado | `mark_dispensation_completed` | sistema |

> Gate operacional (9-16): pagamento **AUTORIZADO** (status=PAID) basta —
> não espera a liquidação. Ver [00l](00l-regras-negocio.md).

## Conciliação bancária

Quando o dinheiro cair de fato (extrato credpay), o financeiro marca o
Payment Entry como compensado na `clearance_date` (Bank Reconciliation
Tool do ERPNext). PIX bate em D+1, cada parcela do cartão em D+30·i.

## Aplicar

```bash
python setup/setup_21_payment_entry.py
```
