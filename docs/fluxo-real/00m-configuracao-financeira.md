# Configuração Financeira — Parâmetros de Tempo + Banco Certo

> UM lugar no ERPNext pra configurar os tempos de liquidação (PIX D+1,
> cartão D+30/parcela) e a conta bancária que recebe cada método. O
> operador financeiro ajusta sem mexer em código. Os endpoints de cálculo
> leem essa config.

## DocType Single: `Injemed Financial Settings`

Form único no ERPNext (busca "Injemed Financial Settings" ou via
Manufacturing). Campos:

### Parâmetros de Tempo (Liquidação)

| Campo | Default | Significado |
|---|---|---|
| `pix_settlement_days` | 1 | PIX liquida em D+N (pago hoje cai D+1) |
| `card_days_per_installment` | 30 | Cartão: parcela i liquida em D+(N·i) → D+30, D+60... |
| `boleto_settlement_days` | 1 | Boleto liquida em D+N |

### Contas de Recebimento (Banco Certo)

| Campo | Default | Significado |
|---|---|---|
| `bank_account_pix` | Conta Bancária - I | Banco que recebe PIX |
| `bank_account_card` | Conta Bancária - I | Banco que recebe cartão |
| `bank_account_boleto` | Conta Bancária - I | Banco que recebe boleto |
| `receivable_account` | Clientes - I | Conta de clientes (a receber) |

### Modos de Pagamento (ERPNext)

| Campo | Default | Mode of Payment |
|---|---|---|
| `mode_pix` | Pix | usado no Payment Entry de PIX |
| `mode_card` | Cartão de Crédito | usado no Payment Entry de cartão |
| `mode_boleto` | Boleto | usado no Payment Entry de boleto |

URL do form:
`https://erp.injemedpharma.com.br/app/injemed-financial-settings`

## Endpoints

### `future_production_get_financial_config`

Lê a config. Sem body.

```json
→ {
  "company": "Injemedpharma",
  "pix_settlement_days": 1,
  "card_days_per_installment": 30,
  "boleto_settlement_days": 1,
  "bank_account_pix": "Conta Bancária - I",
  "bank_account_card": "Conta Bancária - I",
  "bank_account_boleto": "Conta Bancária - I",
  "receivable_account": "Clientes - I",
  "mode_pix": "Pix", "mode_card": "Cartão de Crédito", "mode_boleto": "Boleto"
}
```

### `future_production_payment_schedule`

Calcula o cronograma de liquidação usando a config. Fonte ÚNICA do
cálculo (n8n não calcula mais hardcoded).

```json
POST { "method": "CREDIT_CARD", "installments": 3,
       "amount": 5258.94, "paid_at": "2026-06-02 18:46:15" }
→ {
  "method": "CREDIT_CARD", "installments": 3, "amount": 5258.94,
  "bank_account": "Conta Bancária - I",
  "mode_of_payment": "Cartão de Crédito",
  "receivable_account": "Clientes - I",
  "company": "Injemedpharma",
  "schedule": [
    { "parcela": 1, "valor": 1752.98, "liquida_em": "2026-07-02" },
    { "parcela": 2, "valor": 1752.98, "liquida_em": "2026-08-01" },
    { "parcela": 3, "valor": 1752.98, "liquida_em": "2026-08-31" }
  ]
}
```

Validado em prod (quando a API key estava ativa):
- Cartão 3x R$5258.94 → D+30/D+60/D+90 ✓
- PIX R$1398.50 → D+1 ✓

## Uso no fluxo n8n

Node **"Liquidação (config)"** (após "4. Reserva", `continueOnFail`):
chama `future_production_payment_schedule` com o pagamento normalizado.
O Respond devolve `liquidacao` (cronograma + banco + modo) pro Card React.

Como é `continueOnFail`, se o cálculo falhar o pedido ainda é
sincronizado — liquidação é informativa, não trava operação (ver
[00l](00l-regras-negocio.md): operação anda no AUTORIZADO).

## Onde isso vira Payment Entry (etapa 12 — TODO)

Pra cada item do `schedule`, criar 1 Payment Entry no ERPNext quando a
data `liquida_em` chegar (ou via conciliação do extrato credpay):
- `paid_to` = `bank_account` da config
- `mode_of_payment` = `mode_of_payment` da config
- `paid_amount` = `valor` da parcela
- `posting_date` = `liquida_em`
- referência = Sales Invoice / Sales Order do pedido

## Aplicar

```bash
python setup/setup_20_financial_config.py
```

Cria o DocType Single + aplica defaults (valida que as contas/modos
existem antes de setar) + registra os 2 endpoints.

## Ajustar valores

Financeiro abre o form `Injemed Financial Settings` no ERPNext e muda
qualquer número/banco/modo. Sem deploy. Os endpoints leem na hora.
