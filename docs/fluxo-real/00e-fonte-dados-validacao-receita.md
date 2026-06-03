# Fonte de Dados — Sistema validacao_receita

> Mudança importante: **Pacientes e Prescribers NÃO vêm do HubSpot direto**.
> Vêm de um sistema dedicado de validação de receitas (backend Node +
> Postgres) onde operadores cadastram cada paciente vinculado a cada
> produto + receita anexada + médico, e validadores aprovam.
>
> Quando pedido fica 100% validado + pago → vai pro ERPNext via botão
> manual no frontend ou webhook n8n.

## Repositórios

- **Backend** (Node + Express + Postgres): https://github.com/Unikka-Pharma/backend-sistema-receitas
- **Frontend**: https://github.com/Unikka-Pharma/frontend-injemed-sistema-pacientes
- **n8n flow sync**: https://n8n.injemedpharma.com.br/workflow/0nuMbQ25ZzuUvmPE

## Schema Postgres

Database: `validacao_receita` · Schema: `postgres_main`

### Tabela: orders (pedido principal)

```sql
orders
  id                    SERIAL PK
  hubspot_deal_id       VARCHAR(50) UNIQUE   ← link com HubSpot CRM
  responsavel           VARCHAR(255)
  status                em_andamento | completo
  obs, tipo_frete, transportadora
  contact_name, company_name, owner_name, owner_email
  assigned_to           FK users(id)
  hubspot_owner_id      VARCHAR(50)
  locked                BOOLEAN
  pedido_fc_emitido_at  TIMESTAMP   ← marca emissão pra FCerta
  created_at, updated_at
```

### Tabela: deal_companies (empresa pagante — Customer ERPNext)

```sql
deal_companies (1:N order)
  id
  order_id              FK orders
  name                  VARCHAR(255)
  cnpj OR cpf_responsavel   ← determina PJ vs PF
  nome_responsavel_tecnico  ← Prescriber linkado ao Customer
  numero_conselho, conselho, estado_conselho   ← CRM-SP 223389
  endereco, bairro, cep, municipio, uf, complemento
  inscricao_estadual
  hs_object_id          ← link Company HubSpot
```

### Tabela: deal_contacts (contato — Contact ERPNext)

```sql
deal_contacts (1:N order)
  email, firstname, lastname, phone, hs_object_id
```

### Tabela: deal_payments (Payment Entry ERPNext)

```sql
deal_payments (1:N order)
  external_id, valor, parcelas, status, forma_pagamento
  provider_name, comprovante_url, payment_url
  paid_at, payer_name, payer_cpf_cnpj
```

### Tabela: products (Sales Order Item ERPNext)

```sql
products (1:N order)
  sku                       ← chave de match com ERPNext Item
  name, price, quantity
  max_per_patient, min_patients   ← regras de divisão por paciente
  principio_ativo_id        ← FK principios_ativos
  dosagem_mg
```

### Tabela: patients (Patient + fp_patients linha ERPNext)

```sql
patients (N por product)
  cpf, nome, telefone, data_nascimento, idade
  cep, endereco, numero, complemento, bairro, municipio, uf
  quantidade                ← qtd desse paciente do produto
  posologia                 TEXT
  data_prescricao           DATE
  receita_path              VARCHAR(500)
  receita_original_name     VARCHAR(500)
  sku                       VARCHAR(50)
  
  -- dados DENORMALIZADOS do médico (NÃO vem de users!)
  medico_nome               VARCHAR(255)
  medico_crm                VARCHAR(20)
  medico_uf                 VARCHAR(2)
  
  -- assinatura digital
  assinatura_digital_status nao_verificado | verificando | valida | invalida | sem_assinatura | erro
  assinatura_digital_detalhes JSONB
  assinatura_verificada_em  TIMESTAMP
  
  requisicao_fcerta         BIGINT  ← link FCerta
```

### Tabela: validations (status aprovação por paciente)

```sql
validations (1:1 patient)
  patient_id              UNIQUE FK
  status                  pendente | aprovado | rejeitado
  validated_by            FK users
  notes                   TEXT
  validated_at            TIMESTAMP
```

### Tabela: users (operadores DO SISTEMA, não médicos)

```sql
users
  username, password_hash, name, role, active
  role: operador | validador | admin | vendedor
  hubspot_owner_id        ← vendedor mapeia owner HubSpot
```

> **Importante**: `users` são funcionários do sistema validacao_receita
> (operador cadastra pacientes, validador aprova receitas, admin gerencia,
> vendedor vê seus deals). Médicos NÃO ficam aqui — médicos vêm
> denormalizados em `patients.medico_*` ou `deal_companies.responsavel_tecnico*`.

### Tabela: principios_ativos + produto_principio_ativo

```sql
principios_ativos
  nome (Tirzepatida, Semaglutida)
  limite_mg (180, 16)
  periodo_dias (90)

produto_principio_ativo
  product_id + principio_ativo_id + dosagem_mg
```

### Tabela: historico_dispensacao (controle de limite por CPF)

```sql
historico_dispensacao
  cpf + principio_ativo_id + patient_id + order_id
  dosagem_total_mg = dosagem_mg × quantidade
  data_dispensacao
```

Index: `idx_historico_cpf_principio` (cpf, principio_ativo_id, data_dispensacao).

Usado pra checar limite de 180mg Tirzepatida / 90 dias por CPF.

## Lógica "Pedido completo"

Função `recomputeOrderState(orderId)` em `src/services/order-state.service.ts`:

```
order.status = 'completo' SE:
  TODOS products tem patients_filled >= patients_needed
  AND TODOS products tem quantity_filled >= quantity

  patients_needed = MAX(min_patients, CEIL(quantity / max_per_patient))
  quantity_filled = SUM(patient.quantidade) para todos pacientes do produto
```

**NÃO inclui** `validations.status='aprovado'` nem deal_payment.

## Lógica "100% validado + pago" (proposta — ainda não implementada)

Pra ir pro ERPNext, condição mais estrita:

```sql
order.status = 'completo'
AND TODOS patients.validation.status = 'aprovado'
AND EXISTS deal_payment WHERE status IN ('pago', 'confirmado', ...)
```

Implementar como:
1. **Função SQL/view** `orders_ready_for_erpnext` que aplica os 3 critérios
2. **Endpoint** `POST /api/orders/:id/send-to-erpnext` no backend Node
3. **Botão** no frontend chamando o endpoint
4. Backend → POST `future_production_issue_order` no ERPNext

## Mapping → ERPNext

```
postgres                            ERPNext
─────────────────────────────────────────────────────────────────
orders                              Sales Order (1:1 via hubspot_deal_id)
  status='completo'                   → trigger upsert
  obs                                 → SO.terms_and_conditions_details
  tipo_frete, transportadora          → SO custom fields ou Delivery Note

deal_companies                      Customer
  cnpj IF NOT NULL                    → tax_id (customer_type=Company)
  ELSE cpf_responsavel                → tax_id (customer_type=Individual)
  name                                → customer_name
  endereço completo                   → Address (linked is_primary_address=1)
  nome_responsavel_tecnico            → Customer.default_prescriber
    + conselho + numero + estado      → Prescriber + Council
    + cpf_responsavel                 → Prescriber.cpf (mesmo do Customer pra PF)

deal_contacts                       Contact (linked ao Customer)

deal_payments                       Payment Entry
  (criado APÓS Sales Invoice ser submetida)

products                            Sales Order Item
  sku                                 → item_code (match exato c/ Item criado por sync HubSpot)
  name, price, quantity               → standard fields

patients                            Patient + Sales Order Patient (fp_patients)
  cpf                                 → Patient.cpf (lookup/create unique)
  nome                                → Patient.patient_name
  data_nascimento, telefone, email    → Patient fields
  endereço completo                   → Address (linked to Patient)
  
  medico_nome, medico_crm, medico_uf  → Prescriber + Council (lookup/create)
                                        ⚠ Prescriber sem CPF (não vem do sistema)
                                        TODO: enriquecer via consulta CFM
  
  → fp_patients line:
    patient                           = Patient.name
    prescriber                        = Prescriber.name
    prescriber_council_row            = Prescriber Council.name (CRM-UF número)
    item_code                         = products.sku
    qty                               = patients.quantidade
    fp_future_production_batch        = FIFO via auto_reserve

principios_ativos                   Item.principio_ativo (custom field opcional)
                                    + Server Script valida limite_mg / periodo_dias
                                    contra historico_dispensacao
```

## Conexão Postgres

Variáveis `.env` (TODO setar):

```bash
VALIDACAO_PG_HOST=
VALIDACAO_PG_PORT=5432
VALIDACAO_PG_DB=validacao_receita
VALIDACAO_PG_SCHEMA=postgres_main
VALIDACAO_PG_USER=
VALIDACAO_PG_PASS=
```

OU usar API REST do backend (auth via JWT):

```bash
VALIDACAO_API_URL=https://api.validacao.injemedpharma.com.br
VALIDACAO_API_TOKEN=jwt_admin_token_aqui
```

API endpoints úteis:
```
POST   /api/auth/login                      → JWT
GET    /api/orders                          → lista (filtered por role)
GET    /api/orders/:id                      → detalhe completo
GET    /api/orders/deal/:dealId             → detalhe por HubSpot deal id (público)
GET    /api/patients                        
GET    /api/users                           → operadores/validadores (não médicos)
GET    /api/validations
```

## Próximos passos (Roadmap)

1. ⏳ Receber credenciais Postgres OU token JWT do backend
2. ⏳ Criar `lib/validacao_receita_api.py` — cliente HTTP do backend (preferível) OU `lib/validacao_receita_pg.py` (Postgres direto)
3. ⏳ Criar `tools/sync_order_to_erpnext.py` — recebe order_id, busca Order completo, cria/atualiza tudo no ERPNext atomicamente
4. ⏳ Estender `setup_14_issue_order.py` ou criar novo endpoint `future_production_issue_order_v2` que aceite payload do validacao_receita
5. ⏳ Adicionar custom field `Customer.default_prescriber` (já existe? confirmar)
6. ⏳ Frontend: botão "Enviar pra ERPNext" no detalhe do pedido (chama backend → backend chama ERPNext)
7. ⏳ Doc passos 02-06 atualizados com fluxo novo

## Limpeza executada

Customer/Patient/Prescriber/SO/PR criados manualmente no fluxo Gustavo
foram **apagados** (eram exemplo errado):

```
Deleted:
  Customer 00067, Patient 00068, Prescriber 00073
  Contact + Address Gustavo
  SO 00071, PR 00072

Mantido:
  Item 00049 (Tirzepatida 90mg)   ← veio do sync HubSpot, ok
  Item 00069 (FRETE)              ← útil pra qualquer pedido
  FPB 00070 (TIRZE90-20260602)    ← lote planejado, válido
  Customer Group "Volpi"          ← útil pra classificação futura
```
