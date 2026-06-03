# Fluxo n8n node-by-node — Sincronização Pedido → ERPNext

> Workflow **ativo** em produção. Webhook único recebe o pedido (UI Card
> React → HubSpot shape) e executa 4 etapas ERPNext nomeadas, visíveis
> uma a uma no n8n. Cada etapa = 1 endpoint dedicado.

## Onde

- **n8n**: https://n8n.injemedpharma.com.br → workflow `fRn3EyKJLWIxEX3l`
  "Sincronização Pedido → ERPNext (Processo Completo)" (ativo)
- **Webhook produção**: `POST https://n8n.injemedpharma.com.br/webhook/erp/sincronizar-pedido`
- **Export no repo**: `n8n_workflows/sincronizar_pedido_4steps.json`

## Diagrama

```
[Webhook]  POST /webhook/erp/sincronizar-pedido
   │       body: { hubspot_deal_id, companies[], contacts[],
   │               products[]{patients[]}, item_fpb[] }
   ▼
[Buscar Pagamento]  Postgres checkout_simples
   │   SELECT transaction PAID WHERE external_ref = hubspot_deal_id
   ▼
[Normalizar]  Code — monta sub-payloads:
   │   customer{}, items[], prescribers[], patients[],
   │   fp_patients[], item_fpb[], payment{}, prescriptions{}
   ▼
[1. Cadastra Cliente]   POST future_production_step_customer
   │   → Customer + Address + Contact   →  retorna {customer}
   ▼
[2. Cadastra Pedido]    POST future_production_step_order
   │   → Sales Order (items) DRAFT + flags  →  retorna {sales_order}
   ▼
[3. Cadastra Pacientes + Médico]  POST future_production_step_patients
   │   → Prescriber (upsert CPF/CRM) + Patient (upsert CPF)
   │   → append fp_patients rows + BIN-PACK lote (receita inteira)
   │   → SUBMETE o Sales Order
   ▼
[4. Reserva]            POST future_production_step_reserve
   │   → 1 Production Reservation por lote (item_fpb, qty operador)
   ▼
[Respond]  { ok, sales_order, cliente, pacientes, reservas }
```

## Por que essa ordem (e não cliente→pedido→reserva→pacientes)

Constraints do ERPNext descobertos em produção:

1. **`Production Reservation` exige Sales Order submetido**
   (`PR - Validate (Before Save)`: "Sales Order precisa estar submetido").
   → Reserva só roda DEPOIS do SO submeter.

2. **Tabela `fp_patients` não aceita append após submit**
   ("Not allowed to change Pacientes Vinculados after submission").
   → Pacientes têm que entrar no SO ANTES de submeter.

Resultado: SO criado DRAFT (etapa 2), pacientes adicionados + SO submetido
(etapa 3), reserva por último (etapa 4). A reserva "andou" pro fim — como
você falou: *"pode mudar a ordem só para reservar logo"*. O lote ainda é
escolhido na UI (item_fpb); a reserva apenas materializa as Production
Reservations depois que o pedido está firme.

## Endpoints (setup_19_step_endpoints.py)

### 1. `future_production_step_customer`

```json
POST /api/method/future_production_step_customer
{ "customer": { "customer_name", "customer_type", "tax_id",
                "customer_group", "territory", "email_id", "mobile_no",
                "address": {...}, "contact": {...} } }
→ { "ok": true, "customer": "00104", "created": true,
    "address": "...", "contact": "..." }
```
Upsert Customer por nome. Cria Address + Contact linkados se enviados.

### 2. `future_production_step_order`

```json
POST /api/method/future_production_step_order
{ "customer": "00104", "company": "Injemedpharma",
  "hubspot": {"deal_id":"..."}, "items": [{item_code, qty, rate}],
  "payment": {amount, status, transaction_id, paid_at},
  "prescriptions": {count, reference} }
→ { "ok": true, "sales_order": "00105", "grand_total": 1000.0,
    "so_items": {"TIR00060": ["..."]} }
```
Cria SO com items. Seta flags hubspot_complete + payment_validated +
prescriptions_validated inline. **NÃO submete** (fica DRAFT). Idempotente
por `hubspot_deal_id`.

### 3. `future_production_step_patients`

```json
POST /api/method/future_production_step_patients
{ "sales_order": "00105",
  "prescribers": [{cpf, full_name, councils[]}],
  "patients": [{cpf, patient_name, mobile, gender}],
  "fp_patients": [{patient_cpf, prescriber_cpf, prescriber_council, item_code, qty}],
  "item_fpb": [{item_code, lotes:[{fpb_name, qty}]}] }
→ { "ok": true, "assignments": [{patient, item_code, qty, fpb, prescriber}],
    "pack_errors": [], "so_submitted": true }
```
Upsert Prescriber (CPF, fallback CRM+UF). Upsert Patient (CPF). Append
fp_patients rows + **bin-pack** cada paciente num lote (receita inteira,
first-fit-decreasing). **Submete** o SO no fim.

### 4. `future_production_step_reserve`

```json
POST /api/method/future_production_step_reserve
{ "sales_order": "00105",
  "item_fpb": [{item_code, lotes:[{fpb_name, qty}]}] }
→ { "ok": true, "reservations": [{reservation, future_production_batch,
      item_code, reserved_qty}], "reserve_errors": [] }
```
Cria 1 Production Reservation por lote (qty do operador). Fallback
fpb_map / fpb_name / FIFO. Valida FPB + saldo. Idempotente.

## Payload de entrada (UI → Webhook)

```json
{
  "hubspot_deal_id": "60801476407",
  "companies": [{
    "name": "PAULO CESAR MOURA JUNIOR", "cnpj": "", "cpf_responsavel": "00092473199",
    "nome_responsavel_tecnico": "...", "numero_conselho": "16245",
    "conselho": "1 - CRM", "estado_conselho": "DF",
    "endereco": "...", "municipio": "Brasília", "uf": "DF", "cep": "71081175"
  }],
  "contacts": [{ "firstname": "Paulo", "lastname": "...", "email": "...", "phone": "..." }],
  "products": [{
    "sku": "TIR00060", "quantity": 10, "price": 100, "name": "Tirzepatida 60",
    "patients": [
      { "cpf": "...", "nome": "...", "quantidade": 5,
        "medico_crm": "16245", "medico_uf": "DF", "medico_nome": "..." }
    ]
  }],
  "item_fpb": [{
    "item_code": "TIR00060",
    "lotes": [ {"fpb_name": "FPB-A", "qty": 7}, {"fpb_name": "FPB-B", "qty": 3} ]
  }]
}
```

`item_fpb` = alocação quantidade-por-lote escolhida na UI. Sistema distribui
os pacientes (bin-pack) respeitando "receita inteira em 1 lote".

## Resposta

```json
{
  "ok": true,
  "sales_order": "00115",
  "cliente":   { "customer": "...", "address": "...", "contact": "..." },
  "pacientes": { "assignments": [...], "so_submitted": true, "pack_errors": [] },
  "reservas":  { "reservations": [...], "reserve_errors": [] }
}
```

## Credenciais n8n usadas

| Credencial | ID | Uso |
|---|---|---|
| `Postgres dedicado` | `ZQSVfJQfNFuAdvFd` | node "Buscar Pagamento" (checkout_simples) |
| `ERPNext Injemed (claude)` | `JNoxJ2A0Ng6Eytu6` | httpHeaderAuth nos nodes ERP (Authorization: token KEY:SECRET) |

> A credencial ERPNext usa a API key/secret de um usuário System Manager.
> Se a key for rotacionada (Generate Keys gera novo secret), atualize a
> credencial no n8n OU recrie e repointe os nodes httpRequest. A key
> anterior `(temp)` foi revogada em 2026-06-03.

## Teste executado em prod (2026-06-03)

```
Webhook payload: 1 item (10 ampolas), 3 pacientes [5,3,2], item_fpb A=7 B=3
  1. Cadastra Cliente            → Customer
  2. Cadastra Pedido             → SO 00115 (draft)
  3. Cadastra Pacientes + Médico → 3 pac bin-pack (5→A, 3→B, 2→A), SO submetido
  4. Reserva                     → PR lote A=7, PR lote B=3
  Respond ok=true
Dados de teste removidos após validação.
```

## Reimportar

`n8n_workflows/sincronizar_pedido_4steps.json` — Import from File no n8n.
Após import, reconectar credenciais Postgres + httpHeaderAuth nos nodes
(IDs de credencial são específicos do ambiente).

## Idempotência

Re-disparar o webhook com mesmo `hubspot_deal_id` é seguro:
- step_order retorna o SO existente (lookup por hubspot_deal_id)
- step_patients pula pacientes já na SO (lookup por cpf+item)
- step_reserve pula lotes já reservados (sum reserved_qty)
