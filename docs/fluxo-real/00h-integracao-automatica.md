# Integração Automática Sync — setup_14 + n8n workflow

> Componentes pra automatizar o que foi feito manual no pedido Paulo César.
> Pronto pra disparar via webhook n8n.

## O que cada componente faz

| Componente | Onde | Faz |
|---|---|---|
| `future_production_issue_order` (Server Script) | ERPNext (setup_14) | Recebe payload único, upserta Customer + Address + Contact + Prescriber + Patient + SO + payment + prescriptions + auto-reserve FIFO contra FPB |
| `n8n_workflows/sync_order_to_erpnext.json` | n8n | Webhook → query Postgres validacao_receita + checkout_simples → transform → POST issue_order → marca order enviada |
| HubSpot Card React (TODO separado) | HubSpot Deal page | Botão "Enviar pra ERPNext" → POST webhook n8n |

## Endpoint `future_production_issue_order` — payload schema novo

```json
{
  "hubspot": { "deal_id": "60801476407", "contact_id": "225845250711" },
  "company": "Injmedpharma",
  "customer": {
    "customer_name": "Paulo César Moura Junior",
    "customer_type": "Individual",
    "customer_group": "Volpi",
    "tax_id": "00092473199",
    "address": {
      "title": "Paulo César Moura Junior",
      "type": "Billing",
      "address_line1": "Setor Habitacional IAPI Chácara 15A",
      "address_line2": "Casa 4",
      "city": "Brasília",
      "state": "DF",
      "pincode": "71081175",
      "country": "Brazil",
      "email_id": "pcmourajr@gmail.com",
      "phone": "+5561981468252"
    },
    "contact": {
      "first_name": "Paulo",
      "last_name": "César Moura Junior",
      "email": "pcmourajr@gmail.com",
      "phone": "+5561981468252"
    }
  },
  "prescribers": [
    {
      "cpf": "00092473199",
      "full_name": "Paulo César Moura Junior",
      "councils": [{ "council_type": "CRM", "council_number": "16245", "council_state": "DF", "is_primary": 1 }]
    }
  ],
  "patients": [
    { "cpf": "00593976169", "patient_name": "Eveline Jajah Franco Moura" }
  ],
  "items": [
    { "item_code": "TIR00060", "qty": 1, "rate": 1800, "warehouse": "Produtos Acabados - I" },
    { "item_code": "00069",    "qty": 1, "rate": 163.98, "warehouse": "Produtos Acabados - I" }
  ],
  "fp_patients": [
    {
      "patient_cpf": "00593976169",
      "prescriber_cpf": "",
      "prescriber_council": { "council_type": "CRM", "council_number": "16245", "council_state": "DF" },
      "item_code": "TIR00060",
      "qty": 1
    }
  ],
  "payment": {
    "amount": 1963.98,
    "status": "PAID",
    "transaction_id": "cmpwzng0u00pjyxqfq4ya11zn",
    "paid_at": "2026-06-02 18:46:15"
  },
  "prescriptions": {
    "count": 1,
    "reference": "validacao_receita order_id=1"
  }
}
```

## Funcionalidades adicionadas ao setup_14

| Bloco | Comportamento |
|---|---|
| Customer Address | Cria Address linkado ao Customer se `customer.address` enviado. Idempotente por (title, type). |
| Customer Contact | Cria Contact linkado ao Customer se `customer.contact` enviado. Idempotente: skip se já existe Contact linkado. |
| Prescriber CPF lookup | Mantém — upsert por CPF + merge councils. |
| Prescriber Council fallback | Quando CPF vazio, busca Prescriber existente por (council_type, state, number). Se não achar, gera CPF placeholder único `9<digits>`. |
| fp_patients lookup council | Sem `prescriber_cpf`, resolve por `prescriber_council` (consulta `tabPrescriber Council`). |
| Payment inline | Bloco `payment` → seta `payment_validated=1` + reference + amount. Valida `status ∈ {PAID,RECEIVED,CONFIRMED}` e amount ±R$ 0,01 vs `SO.grand_total`. |
| Prescriptions inline | Bloco `prescriptions` → seta `prescriptions_validated=1` + qty + reference. |
| Auto-reserve FIFO | Se 3 flags True após payment+prescriptions, cria Production Reservation por linha de Item stock, FIFO FPBs `available_qty > 0`. Sum `reserved_qty` por linha pra não duplicar (idempotente em re-call). |

## Response

```json
{
  "sales_order": "00077",
  "created": { "customer": null, "prescribers": [], "patients": [] },
  "validation_status": "Validado (Pronto para Reservar)",
  "hubspot_complete": true,
  "ready_to_reserve": true,
  "reservations": [
    { "reservation": "00079", "sales_order_item": "...", "future_production_batch": "FPB-2026-00115", "reserved_qty": 1.0 }
  ],
  "reserve_errors": []
}
```

`created` fica vazio quando SO já existia (idempotency hit). Reservations só
populadas se 3 flags ok e linha precisar reservar mais.

## n8n workflow — fluxo

```
[Webhook /webhook/erp/sync-order]
  body: { deal_id: "60801476407" }   OR   { order_id: 1 }
  ↓
[Parse input]
  → { deal_id, order_id }
  ↓
[Query Postgres (validacao_receita + checkout_simples)]
  SQL único composto:
    - WITH o AS (orders ...)
    - prods AS (products + agg patients + validations)
    - SELECT order_data, company, contact, products, payment, payer
  Junta tudo numa única linha JSON.
  ↓
[Transform → ERPNext payload]
  JS Code:
    - taxId: cpf_responsavel || cnpj || payer.cpf_cnpj
    - customer.address: payer fields ou company fields (priorize payer)
    - customer.contact: contact firstname/lastname/email/phone
    - prescribers: company resp_técnico + médicos únicos extraídos de patients
    - patients: únicos por CPF
    - items: 1 por product (sku, qty, price)
    - fp_patients: 1 por paciente (patient_cpf + prescriber_council CRM-UF + item + qty)
    - payment: amount/100, transaction_id, paid_at
    - prescriptions: count + reference
  ↓
[POST issue_order ERPNext]
  ↓
[Mark order sent]
  UPDATE validacao_receita.orders SET pedido_fc_emitido_at = NOW()
  WHERE hubspot_deal_id = $1 AND pedido_fc_emitido_at IS NULL
  ↓
[Respond { ok, erpnext, marked }]
```

## Setup n8n

### 1. Importar workflow

```
n8n.injemedpharma.com.br → New workflow → Import from File
Seleciona n8n_workflows/sync_order_to_erpnext.json
```

### 2. Credenciais Postgres

```
n8n → Credentials → New → Postgres
  Name:     validacao_receita PG
  Host:     2.24.98.117
  Port:     5432
  Database: postgres
  User:     postgres
  Password: <senha — não commitar>
  SSL:      disabled (ou conforme infra)
```

Após criar credencial, edita nodes "Query Postgres" e "Mark order sent" e
seleciona essa credencial (substitui `REPLACE_ME`).

### 3. Env vars

```
n8n → Settings → Variables
  ERPNEXT_API_KEY    = <key>
  ERPNEXT_API_SECRET = <secret>
```

### 4. Ativar

Toggle topo direito → ativa. Copia "Production URL" do Webhook node.

## Como disparar

### Via curl (teste manual)

```bash
curl -X POST https://n8n.injemedpharma.com.br/webhook/erp/sync-order \
  -H "Content-Type: application/json" \
  -d '{"deal_id":"60801476407"}'
```

### Via HubSpot Card (TODO)

React UI Extension renderiza no Deal page. Botão "Enviar pra ERPNext" →
fetch POST pra URL acima.

## Idempotência ponta-a-ponta

| Onde | Como |
|---|---|
| ERPNext SO | Lookup por `hubspot_deal_id` antes de criar |
| ERPNext Customer | Lookup por `customer_name` |
| ERPNext Prescriber | Lookup por CPF; merge councils |
| ERPNext Patient | Lookup por CPF; atualiza campos |
| ERPNext Address | Lookup por `(title, type)` |
| ERPNext Contact | Lookup por Dynamic Link a Customer |
| ERPNext Production Reservation | Sum reserved_qty por sales_order_item — só aloca diferença |
| Postgres mark | `pedido_fc_emitido_at IS NULL` na condição WHERE |

Re-chamar workflow com mesmo `deal_id` é seguro: response volta com
`created` vazio, marca Postgres só uma vez.

## Limitações conhecidas

1. **Workflow não busca line_items HubSpot direto.** Usa apenas `products` do
   validacao_receita. Se backend não importou FRETE (sku=SV02000002 hardcoded
   no backend), FRETE não vai pro ERPNext via essa rota. Solução: pode
   adicionar node HubSpot pra puxar line_items + merge antes do Transform.

2. **Pacientes com mesmo CPF do médico** (PF Volpi auto-uso) — Patient.cpf e
   Prescriber.cpf são iguais. ERPNext permite (DocTypes diferentes). OK.

3. **Address autoname** = `format:{address_title}-{address_type}` hardcoded
   ERPNext core. Mesmo título → mesmo Address. Cuidado se 2 customers
   diferentes tiverem mesmo "title" + type (improvável).

4. **CPF placeholder pra Prescriber sem CPF**: `9<crm><uf><pad>`. Funciona
   pra unique check mas não passa validação DV CPF. Aceitável pra dados de
   médicos parciais; corrigir depois via integração CFM.

5. **Payment vem de `checkout_simples`** (esse projeto). Asaas + outros
   gateways: aceitam quando adicionar query alternativa OR backend Node
   normaliza tudo em `checkout_simples.transactions`.

## Próximos passos

| # | Quem | O quê |
|---|---|---|
| 1 | **você** | importa n8n workflow, configura credenciais Postgres + ERPNext env |
| 2 | **você** | testa via curl `POST /webhook/erp/sync-order { deal_id }` |
| 3 | claude (após) | scaffold HubSpot Card React extension (task #19) |
| 4 | claude (após) | adiciona node n8n pra buscar HubSpot line_items + merge FRETE |
| 5 | claude (após) | integração CFM lookup CPF de Prescriber (task pendente) |
