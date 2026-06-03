# STATUS — Estado do Projeto (fonte de verdade)

> Resumo vivo do que foi feito e do que falta. Atualizar conforme avança.
> Última atualização: 2026-06-03 (após LIMPEZA GERAL).

## 🧹 Estado atual dos dados (pós-limpeza)

ERPNext **zerado de transacional**, só Items mantidos:
```
Sales Order 0 · Customer 0 · Patient 0 · Prescriber 0 · Payment Entry 0
Production Reservation 0 · Future Production Batch 0 · Address 0 · Contact 0
Item: 69 (catálogo HubSpot — MANTIDO)
```
Mantidos: DocTypes, Server Scripts, Custom Fields, Config Financeira,
Customer Group "Volpi", naming, n8n workflow. Postgres validacao_receita
INTACTO (16 orders). Counter de naming NÃO reseta (próximo registro segue
do número onde parou, não 00001).

> **Pra rodar venda real via n8n: precisa criar 1 FPB (lote) antes** — a
> reserva precisa de lote aberto. Ver guia em `10-criar-lote-fpb.md`.

## Visão geral

Sistema de produção/dispensação Injmedpharma no ERPNext, integrado a:
- **HubSpot** (CRM, deals, products) — via MCP + Private App
- **validacao_receita** (Postgres, backend Node) — pacientes + médico + receita validada
- **checkout_simples** (Postgres) — pagamentos (credpay)
- **n8n** — orquestra o sync (HubSpot/Postgres → ERPNext)

Fronteira: **tudo automático até o pedido pronto + financeiro lançado**;
da produção em diante é **manual no ERPNext**.

## URLs / acesso

| Sistema | URL |
|---|---|
| ERPNext | https://erp.injemedpharma.com.br |
| n8n | https://n8n.injemedpharma.com.br (workflow `fRn3EyKJLWIxEX3l`) |
| Webhook sync | `POST /webhook/erp/sincronizar-pedido` |
| Backend validacao | https://validacao-api.injemedpharma.com.br (uploads de receita em `/uploads/<path>`) |
| Postgres | `2.24.98.117:5432/postgres` (schemas: validacao_receita, checkout_simples, asaas, hubspot_injemed) |
| Repo | https://github.com/CairoWesley/erp-next-future-stock |

Credenciais (NÃO commitadas, em `.env` gitignored):
ERPNEXT_API_KEY/SECRET, HUBSPOT_ACCESS_TOKEN, N8N_API_KEY, VALIDACAO_PG_PASSWORD.
Company ERPNext = **Injemedpharma** (com 'e').

## ✅ FEITO

### Setup ERPNext (setup/*.py)
- `setup_01..13` — DocTypes (FPB, Production Reservation, Patient, Prescriber,
  Dispensacao), Custom Fields, Server Scripts, Reports, Workspace, validações
- `setup_14_issue_order` — endpoint único `future_production_issue_order`
- `setup_15_naming_series` — auto-increment puro `00001` em tudo
- `setup_16_form_layout` — todos campos visíveis
- `setup_18_receita_attach` — campos receita na linha do paciente (fp_patients)
- `setup_19_step_endpoints` — **4 endpoints granulares** (step_customer/order/reserve/patients)
- `setup_20_financial_config` — **Config Financeira** (DocType Single) + endpoints
- `setup_21_payment_entry` — **register_payment** (Payment Entry valor-hoje/recebimento-futuro)

### Pipeline automático (n8n workflow ATIVO)
```
Webhook → Buscar Pagamento (checkout_simples) → Normalizar
  → 1. Cadastra Cliente   (step_customer)
  → 2. Cadastra Pedido    (step_order — SO draft)
  → 3. Cadastra Pacientes + Médico (step_patients — bin-pack + submit)
  → 4. Reserva            (step_reserve — 1 PR por lote)
  → 5. Lançar Recebimento (register_payment — Payment Entry linkado ao SO)
  → Liquidação (config)
       ├→ Respond
       └→ [async] Receitas: Buscar→Preparar→Download PDF→Upload→Set campos
```
Credencial n8n ERPNext: `ERPNext Injemed (claude)`. PG: `Postgres dedicado`.

### Regras implementadas
- **1 receita = 1 lote inteiro** (bin-pack first-fit-decreasing, receita não divide)
- **Alocação qty-por-lote** (`item_fpb: [{item_code, lotes:[{fpb_name, qty}]}]`)
- **Receita validada** (validations.status='aprovado') antes de anexar
- **Pagamento**: AUTORIZADO (PAID) libera operação; LIQUIDAÇÃO (PIX D+1,
  cartão D+30/parcela) só pro Payment Entry
- **Payment Entry**: posting=hoje, clearance=liquidação futura, linkado ao SO,
  banco/modo da Config Financeira. Cartão Nx = N PEs.
- **FRETE** (sku SV02000002) = Item non-stock, nunca reserva
- Constraint ERPNext: PR exige SO submetido + fp_patients não aceita append
  após submit → ordem cliente→pedido(draft)→pacientes(+submit)→reserva

### Outros
- Sync 65 produtos HubSpot → Items ERPNext + write-back hs_sku
- n8n `set_line_item_sku` (auto hs_sku em line_items)
- `tools/attach_receitas.py` (reprocesso receita por deal)
- `tools/sync_products_hubspot.py`
- Docs `docs/fluxo-real/00..00m + 01-09` (índice em 00-indice.md)

### Validado em prod (deal Paulo 60801476407)
Customer + Address + Contact + Prescriber + Patient + SO + Reserva +
receita real (PDF 95KB) + Payment Entry linkado (clearance D+30). Webhook
end-to-end 200.

## ⏳ PENDENTE / MANUAL

### Manual no ERPNext (etapas 9-16) — doc 09
A partir do pedido pronto, time opera manual:
- Produção: FPB → Batch real + Qtd Produzida → Liberar Reservas
- SO: Alocar Batch por Paciente → Delivery Note → Sales Invoice →
  **Criar Dispensação** (botão no SO) → Abrir Dispensação
- Dispensacao: Imprimir Etiquetas Zebra → Marcar Dispensado
- Endpoints já existem (release_batch, allocate_patient_batches,
  create_dispensation_from_so, generate_zpl, mark_*)

### A construir / validar
- [ ] Validar fluxo manual ponta-a-ponta (produzir batch → dispensação → ZPL)
- [ ] Stock Entry automático na produção (hoje manual)
- [ ] BOM pro TIR00060 se quiser Work Order (hoje sem BOM)
- [ ] Cron/job pra conciliar Payment Entry na clearance_date (extrato credpay)
- [ ] HubSpot Card React: confirmar que aponta pro webhook + envia item_fpb
  (UI já existe, validar payload qty-por-lote)
- [ ] Archive 63 produtos duplicados no HubSpot (task pendente)
- [ ] Properties HubSpot pra médico estruturado (hoje vem de patients.medico_*)
- [ ] Limpar SOs de teste cancelados (00077, 00125, 00126) — debris

### Decisões abertas (00l seção 6)
- Chargeback cartão após produção
- PIX/cartão expirado/falho após reserva: libera lote?
- MDR credpay (desconto no Payment Entry?)
- Reembolso (REFUNDED): reverter Delivery/Invoice?

## Endpoints ERPNext (todos `future_production_*`)
```
AUTOMÁTICO (n8n):
  step_customer · step_order · step_reserve · step_patients
  register_payment · payment_schedule · get_financial_config
  issue_order (legado, single-call)
MANUAL (botões ERPNext):
  validate_and_reserve · allocate_patient_batches · release_batch
  create_work_order · recalculate_batch · replan_pending_qty
  create_dispensation_from_so · generate_zpl_label · generate_all_zpl_labels
  mark_label_printed · mark_dispensation_completed
WEBHOOKS (legado):
  payment_webhook · prescriptions_webhook · mark_hubspot_complete
```

## Config Financeira (Injemed Financial Settings — DocType Single)
```
PIX D+1 · Cartão D+30/parcela · Boleto D+1
Banco (PIX/cartão/boleto) = "Conta Bancária - I"
Conta a receber = "Clientes - I"
Modos = Pix / Cartão de Crédito / Boleto
```
Editável no form ERPNext: `/app/injemed-financial-settings`
