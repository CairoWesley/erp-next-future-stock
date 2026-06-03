# Arquitetura — Sync Order validacao_receita → ERPNext (Opção B)

> Decidido: HubSpot UI Extension (React Card no Deal page) + webhook n8n.
> Quando pedido fica 100% validado + pago, botão aparece no Deal HubSpot.
> Click → n8n busca dados completos do backend Postgres + envia pra ERPNext.

## Fluxo end-to-end

```
1. operador           → cadastra paciente no frontend validacao
2. validador          → aprova receita
3. backend Node       → recompute order.status='completo' (auto)
4. payment gateway    → webhook backend → INSERT deal_payments status='pago'
5. backend Node       → enriquece HubSpot Deal property `pronto_para_erpnext=true`
                        (via hubspot.service quando 3 critérios ok)
6. HubSpot UI Card    → re-render, mostra botão "Enviar pra ERPNext"
7. user (admin/vend)  → revisa pedido, clica botão
8. UI Card            → POST https://n8n.injemedpharma.com.br/webhook/sync-order
                        body: { order_id, hubspot_deal_id }
9. n8n                → GET https://api.validacao.injemedpharma.com.br/api/orders/:id
                        (lê backend Node + Postgres)
                      → mapeia payload pra schema ERPNext
                      → POST https://erp.injemedpharma.com.br/api/method/future_production_issue_order
                      → POST https://erp.injemedpharma.com.br/api/method/future_production_payment_webhook
                      → POST https://erp.injemedpharma.com.br/api/method/future_production_prescriptions_webhook
                      → POST https://erp.injemedpharma.com.br/api/method/future_production_validate_and_reserve
10. ERPNext           → Customer + Address + Contact + Patient + Prescriber + SO + PR criados
                      → response com IDs criados
11. n8n               → POST callback https://api.validacao.injemedpharma.com.br/api/orders/:id/erpnext-sync-ok
                        body: { erpnext_so_id, erpnext_customer_id, ... }
12. backend Node      → marca order com `erpnext_sales_order = ...` (precisa migration nova)
13. HubSpot UI Card   → próximo re-render mostra "✅ Enviado pra ERPNext (SO 00071)"
```

## Componentes — quem faz o que

| Componente | Repo / Local | Stack | Responsabilidade | Status atual |
|---|---|---|---|---|
| **Frontend validacao** | `Unikka-Pharma/frontend-injemed-sistema-pacientes` | React+TS | Operador cadastra Patient; Validador aprova | ✅ pronto (assumindo funcional) |
| **Backend validacao** | `Unikka-Pharma/backend-sistema-receitas` | Node+Express+Postgres | recomputeOrderState, /api/orders/:id, /api/orders/deal/:dealId | ✅ pronto |
| **Webhook payment** | backend `routes/...` | Node | Recebe paid_at do gateway, insere deal_payments | ✅ presumido pronto |
| **Trigger HubSpot prop** | backend `services/hubspot.service.ts` | Node + HubSpot API | Quando 3 critérios ok, seta property `pronto_para_erpnext=true` na Deal | ⏳ TODO (extensão pequena) |
| **HubSpot UI Card** | repo HubSpot project novo | React + @hubspot/ui-extensions | Renderiza no Deal page. Lê GET /api/orders/deal/:dealId. Mostra status. Botão condicional. POST webhook n8n | ⏳ TODO |
| **n8n workflow** | n8n.injemedpharma.com.br | n8n | Webhook → HTTP backend → Transform → POST ERPNext (4 endpoints) → callback backend | ⏳ TODO |
| **ERPNext issue_order** | `setup/setup_14_issue_order.py` | Frappe Server Script | Cria Customer+Address+Contact+Patient+Prescriber+SO atomicamente | ⏳ ajustar mapping pra schema novo |
| **ERPNext webhooks** | `setup/setup_13_so_validation.py` | Frappe | payment_webhook, prescriptions_webhook, validate_and_reserve | ✅ pronto |

## Critérios "100% pronto pro ERPNext"

```sql
SELECT * FROM orders o
WHERE
  -- 1) Order completo (todos products com patients suficientes)
  o.status = 'completo'

  -- 2) Todas as validations dos pacientes aprovadas
  AND NOT EXISTS (
    SELECT 1
    FROM products p
    JOIN patients pat ON pat.product_id = p.id
    LEFT JOIN validations v ON v.patient_id = pat.id
    WHERE p.order_id = o.id
      AND (v.status IS NULL OR v.status != 'aprovado')
  )

  -- 3) Tem pelo menos 1 payment com paid_at NOT NULL
  AND EXISTS (
    SELECT 1
    FROM deal_payments dp
    WHERE dp.order_id = o.id
      AND dp.paid_at IS NOT NULL
      AND dp.status IN ('pago', 'confirmado', 'received', 'paid')
  )

  -- 4) Ainda não foi enviado pra ERPNext
  AND o.pedido_fc_emitido_at IS NULL   -- ou novo campo erpnext_sent_at IS NULL
```

> Pra evitar duplo envio, adicionar campo `orders.erpnext_sales_order TEXT` + `orders.erpnext_sent_at TIMESTAMP` via migration nova.

## Payload mapping detalhado

### postgres `validacao_receita.orders` (+ relacionados) → ERPNext `future_production_issue_order`

```json
{
  "hubspot": {
    "deal_id": "<orders.hubspot_deal_id>",
    "contact_id": "<deal_contacts[0].hs_object_id>",
    "company_id": "<deal_companies[0].hs_object_id>"
  },

  "company": "Injmedpharma",

  "customer": {
    "customer_name": "<deal_companies[0].name>",
    "customer_type": "<companies.cnpj ? 'Company' : 'Individual'>",
    "tax_id": "<companies.cnpj ?? companies.cpf_responsavel>",
    "customer_group": "Volpi",
    "territory": "Brazil",
    "default_prescriber_cpf": "<companies.cpf_responsavel>",
    "address": {
      "address_line1": "<companies.endereco>",
      "address_line2": "<companies.complemento>",
      "city": "<companies.municipio>",
      "state": "<companies.uf>",
      "pincode": "<companies.cep>",
      "country": "Brazil"
    },
    "contact": {
      "first_name": "<contacts.firstname>",
      "last_name": "<contacts.lastname>",
      "email": "<contacts.email>",
      "phone": "<contacts.phone>"
    }
  },

  "prescribers": [
    {
      "cpf": "<companies.cpf_responsavel>",
      "full_name": "<companies.nome_responsavel_tecnico>",
      "councils": [{
        "council_type": "<companies.conselho>",
        "council_number": "<companies.numero_conselho>",
        "council_state": "<companies.estado_conselho>",
        "council_status": "Ativo",
        "is_primary": 1
      }]
    },
    "...médicos únicos extraídos de patients[].medico_*..."
  ],

  "patients": [
    {
      "cpf": "<patients.cpf>",
      "patient_name": "<patients.nome>",
      "mobile": "<patients.telefone>",
      "birth_date": "<patients.data_nascimento>",
      "address": {
        "address_line1": "<patients.endereco> <patients.numero>",
        "address_line2": "<patients.complemento>",
        "city": "<patients.municipio>",
        "state": "<patients.uf>",
        "pincode": "<patients.cep>",
        "country": "Brazil"
      },
      "default_prescriber_cpf": "<patients.medico_cpf>" 
      // ⚠ Patient medico CPF NÃO existe no schema; usar lookup por
      //   (medico_crm + medico_uf) ao resolver Prescriber
    }
  ],

  "items": [
    {
      "item_code": "<products.sku>",
      "qty": "<products.quantity>",
      "rate": "<products.price>",
      "warehouse": "Produtos Acabados - I"
    }
  ],

  "fp_patients": [
    {
      "patient_cpf": "<patients.cpf>",
      "prescriber_cpf_or_lookup": "<patients.medico_crm + patients.medico_uf>",
      "prescriber_council": {
        "council_type": "CRM",
        "council_number": "<patients.medico_crm>",
        "council_state": "<patients.medico_uf>"
      },
      "item_code": "<patients.product.sku>",
      "qty": "<patients.quantidade>"
    }
  ],

  "payment": {
    "amount": "<deal_payments[0].valor>",
    "status": "PAID",
    "transaction_id": "<deal_payments[0].external_id>",
    "paid_at": "<deal_payments[0].paid_at>"
  },

  "prescriptions": {
    "count": "<patients.length>",
    "reference": "<order.id>"
  }
}
```

## Ajustes no ERPNext

### setup_14_issue_order.py — adicionar mapping novo

Schema atual aceita: `{customer, prescribers[], patients[], items[], fp_patients[]}`.

Adicionar:
1. `customer.address` (substruct) — criar Address linkado
2. `customer.contact` (substruct) — criar Contact linkado
3. `payment` (top-level) — chamar payment_webhook após criar SO
4. `prescriptions` (top-level) — chamar prescriptions_webhook
5. **Auto-disparar** `validate_and_reserve` no final se as 3 flags ficarem true

### setup_03_server_scripts.py — Prescriber lookup por CRM+UF

Pacientes vêm com `medico_crm + medico_uf` (sem CPF). Lookup:
```python
prescriber = frappe.db.get_value(
    'Prescriber Council',
    {'council_type': 'CRM', 'council_number': crm, 'council_state': uf},
    'parent'
)
```
Se não achar: cria Prescriber novo com `cpf=f'AUTO-{crm}-{uf}'` (placeholder pra unique) + council. CPF real depois via integração CFM.

### Custom field novo (migration)

```python
# Em payloads_visibility.py ou setup novo:
{
    'dt': 'Customer',
    'fieldname': 'default_prescriber',
    'label': 'Responsável Técnico (Médico)',
    'fieldtype': 'Link',
    'options': 'Prescriber',
    'insert_after': 'customer_group',
}
```

## Migration nova no backend Node

```sql
-- 011_erpnext_sync.sql
ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS erpnext_sales_order VARCHAR(50),
  ADD COLUMN IF NOT EXISTS erpnext_customer    VARCHAR(50),
  ADD COLUMN IF NOT EXISTS erpnext_sent_at     TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_orders_erpnext_pending
  ON orders(status, erpnext_sent_at)
  WHERE status='completo' AND erpnext_sent_at IS NULL;
```

Plus em deals HubSpot — property `pronto_para_erpnext: boolean` (criar via UI Settings → Properties).

## Próximos passos executáveis

1. **claude** (agora):
   - cria n8n workflow JSON em `n8n_workflows/sync_order_to_erpnext.json` (skeleton)
   - ajusta `setup_14_issue_order.py` pra novo mapping
   - cria `setup_17_customer_prescriber_field.py` pra add Customer.default_prescriber
2. **você** (depois):
   - cria HubSpot property `pronto_para_erpnext`
   - cria migration backend `011_erpnext_sync.sql`
   - scaffold HubSpot UI Card project
3. **você** (depois):
   - cadastra 1 pedido real no frontend
   - testa fluxo end-to-end
