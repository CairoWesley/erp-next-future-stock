# Regras de Negócio — Pagamento, Liquidação e Gating por Etapa

> Regras REAIS do processo Injemedpharma. Define o pagamento (autorização
> vs liquidação) e, pra cada etapa do fluxo, a precondição (gate) que
> precisa ser verdadeira pra avançar. Fonte de verdade pra implementação.

---

## 1. Pagamento

### Provider

Todos os pagamentos passam pelo gateway **credpay** (config em
`checkout_simples.settings`: `card_primary_provider=credpay`,
`pix_primary_provider=credpay`). Fallback eventual: asaas.

Dados em `checkout_simples`:
- `checkouts.external_ref` = `hubspot_deal_id` (liga pagamento ao pedido)
- `transactions.status` ∈ { PAID, FAILED, EXPIRED, REFUNDED, PENDING }
- `transactions.payment_method` ∈ { PIX, CREDIT_CARD, BOLETO }
- `transactions.installments` = nº de parcelas (cartão 1–10)
- `transactions.amount_cents` = valor em centavos
- `transactions.paid_at` = timestamp da autorização

### Dois conceitos distintos

| Conceito | O que é | Quando | Libera |
|---|---|---|---|
| **AUTORIZAÇÃO** | gateway aprovou o pagamento (`status=PAID`) | instantâneo (PIX e cartão) | TODA a operação: reserva, produção, entrega, dispensação |
| **LIQUIDAÇÃO** | dinheiro efetivamente cai na conta | PIX D+1; cartão D+30 por parcela | apenas o reconhecimento financeiro (Payment Entry no ERPNext) |

> **Regra-mãe**: o processo OPERACIONAL anda com o pagamento
> **AUTORIZADO** (`status=PAID`). Não espera o dinheiro cair. A
> **LIQUIDAÇÃO** só importa pro lançamento financeiro (Payment Entry).

### Cronograma de liquidação (regra de cálculo)

Não existe campo de liquidação no banco — é **calculado** a partir de
`payment_method`, `installments` e `paid_at`:

```
PIX:
  liquida_em = paid_at + 1 dia          (D+1)
  1 liquidação = valor total

CREDIT_CARD (N parcelas):
  parcela i (i = 1..N):
    liquida_em = paid_at + 30*i dias     (D+30, D+60, ... D+30N)
    valor      = total / N               (última parcela ajusta centavos)

BOLETO:
  liquida_em = paid_at + 1 dia           (D+1, no compensar)
  1 liquidação = valor total
```

Exemplos reais:

```
PIX R$ 1.398,50 pago 2026-06-03
  → liquida 2026-06-04 (D+1), 1 lançamento R$ 1.398,50

CARTÃO R$ 1.963,98 pago 2026-06-02 (1 parcela)
  → liquida 2026-07-02 (D+30), 1 lançamento R$ 1.963,98

CARTÃO R$ 5.258,94 pago 2026-06-02 (3 parcelas)
  → parcela 1: 2026-07-02 (D+30)  R$ 1.752,98
  → parcela 2: 2026-08-01 (D+60)  R$ 1.752,98
  → parcela 3: 2026-08-31 (D+90)  R$ 1.752,98
```

### Reflexo no ERPNext

- **Operação** (reserva → dispensação): gate = `status=PAID` (autorizado).
- **Payment Entry**: 1 por liquidação REAL.
  - PIX/Boleto: 1 Payment Entry, posting_date = D+1.
  - Cartão N parcelas: N Payment Entries, parcela i com posting_date = D+30·i.
- Conciliação: cada Payment Entry casa com o crédito real do extrato credpay.

---

## 2. Gating por etapa do processo

Cada etapa só executa se a precondição (gate) for verdadeira. Gates de
**operação** dependem de AUTORIZAÇÃO; só o Payment Entry depende de
LIQUIDAÇÃO.

| # | Etapa | Gate (precondição) | Origem da regra |
|---|---|---|---|
| 1 | **Cadastra Cliente** | CNPJ (PJ) ou CPF (PF) presente. PJ → `customer_type=Company`; senão `Individual`. | Negócio |
| 2 | **Cadastra Pedido (SO draft)** | Cliente cadastrado + cada item com SKU que existe no ERPNext (`Item.item_code`). | Técnico (LinkValidation) |
| 3 | **Cadastra Pacientes + Médico** | SO em draft + **cada paciente com receita APROVADA** (`validacao_receita.validations.status='aprovado'`) + médico com CRM+UF. Pacientes pendentes/rejeitados NÃO entram. | Negócio + Anvisa |
| 4 | **Submete Sales Order** | Pacientes adicionados ao SO + **pagamento AUTORIZADO** (`checkout transaction status=PAID`, valor = `grand_total` ±R$0,01) + receitas validadas. | Negócio (financeiro lançado) |
| 5 | **Reserva (Production Reservation)** | **SO submetido** (técnico: PR exige SO docstatus=1) + lote (FPB) escolhido com `status ∈ {Aberta para Reserva, Reservada Parcialmente}` e saldo suficiente. Bin-pack: receita inteira em 1 lote. | Técnico (PR-Validate) + Negócio |
| 6 | **Registrar Produção (Batch físico)** | Reservas existem pro lote + pagamento autorizado. Batch físico criado com `batch_id = production_code` (TIRZE60-YYYYMMDD). | Negócio |
| 7 | **Stock Entry (Manufacture)** | Batch criado. Dá entrada das ampolas produzidas no estoque. | Técnico (ERPNext) |
| 8 | **Liberar Reservas** | Batch produzido + estoque disponível ≥ reservado. Production Reservation → vincula Batch real. | Negócio |
| 9 | **Alocar Batch por Paciente** | Reserva liberada. Cada `fp_patient.batch_no` recebe o Batch físico do lote já atribuído (mesma `fp_future_production_batch`). | Técnico |
| 10 | **Delivery Note** | Batch alocado por paciente + **pagamento AUTORIZADO** (autorização basta — não espera liquidação). Estoque do Batch ≥ qty. | Negócio (confirmado) |
| 11 | **Sales Invoice (NF)** | Delivery Note submetida. Emite NF-e dos itens entregues. | Fiscal |
| 12 | **Payment Entry** | **LIQUIDAÇÃO** real (dinheiro caiu). PIX: 1 PE em D+1. Cartão Nx: N PEs, parcela i em D+30·i. Casa com extrato credpay. | Financeiro (confirmado) |
| 13 | **Dispensação + Etiqueta Zebra** | NF emitida + Delivery feita + receita anexada na linha do paciente. Imprime etiqueta ZPL por ampola/paciente. | Anvisa + Negócio |
| 14 | **Marcar Dispensado** | Etiqueta impressa + entrega confirmada ao paciente. Fecha o ciclo. | Negócio |

### Resumo dos gates financeiros

```
AUTORIZADO (status=PAID)  →  libera etapas 4,5,6,7,8,9,10,11,13,14
                              (todo o fluxo operacional)

LIQUIDADO (dinheiro caiu) →  libera APENAS etapa 12 (Payment Entry)
                              PIX D+1 · Cartão D+30 por parcela
```

---

## 3. Regras técnicas duras (ERPNext) — não-negociáveis

Descobertas em produção, viram constraint do fluxo:

1. **Production Reservation exige SO submetido**
   (`PR - Validate (Before Save)`: "Sales Order precisa estar submetido").
   → Reserva (etapa 5) só roda após submit (etapa 4).

2. **`fp_patients` não aceita append após submit**
   ("Not allowed to change Pacientes Vinculados after submission").
   → Pacientes (etapa 3) entram no SO ANTES do submit (etapa 4).

3. **Ordem real forçada**: Cliente → Pedido(draft) → Pacientes(+submit) → Reserva.
   (A reserva "andou" pro fim por causa de 1 e 2.)

4. **1 receita = 1 lote inteiro**. Bin-pack first-fit-decreasing nunca
   divide um paciente entre 2 lotes. Se a alocação qty-por-lote não fecha
   → erro pedindo reajuste.

5. **Item non-stock (FRETE, sku=SV02000002)** nunca reserva. Ignorado no
   bin-pack e nas Production Reservations.

6. **Naming**: tudo auto-increment `00001`. Company = `Injemedpharma`
   (com 'e' — FPB valida o Link estrito).

---

## 4. Validação de receita (Anvisa)

Pacientes só entram no SO se a receita estiver **aprovada** no sistema
`validacao_receita`:

```
validacao_receita.validations.status = 'aprovado'
  (não 'pendente', não 'rejeitado')
```

Plus rastreio Anvisa por princípio ativo (`principios_ativos`):
- Tirzepatida: limite 180mg / 90 dias por CPF
- Semaglutida: limite 16mg / 90 dias por CPF
- `historico_dispensacao` controla o acumulado por CPF + princípio.

A receita PDF fica anexada na linha do paciente no SO
(`Sales Order Patient.receita`, ver [00j](00j-receita-anexa-paciente.md)).

---

## 5. Onde cada regra é aplicada

| Regra | Aplicada em |
|---|---|
| Autorização gate operação | n8n node "Buscar Pagamento" + `step_order` (payment_validated) |
| Liquidação D+1/D+30 | `step_payment_entry` (TODO etapa 12) — calcula cronograma |
| Receita aprovada | sistema validacao_receita (antes de ir pro ERPNext) |
| PR exige SO submetido | ERPNext `PR - Validate` + ordem do fluxo n8n |
| Bin-pack receita inteira | `step_patients` (first-fit-decreasing) |
| Limite princípio ativo | validacao_receita `historico_dispensacao` |

---

## 6. Pendências (a confirmar com o negócio)

- [ ] Chargeback de cartão após produção: política de estorno/recall?
- [ ] PIX expirado/falho após reserva: libera o lote reservado de volta?
- [ ] Boleto (raro, 1 caso): mesma regra D+1? Confirmar prazo de compensação.
- [ ] Taxa credpay (MDR): descontar do netValue no Payment Entry? Qual %?
- [ ] Reembolso (REFUNDED): reverter Delivery/Invoice? Nota de devolução?
