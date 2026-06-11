# STATUS — Estado do Projeto (fonte de verdade)

> Resumo vivo do que foi feito e do que falta. Atualizar conforme avança.
> Última atualização: 2026-06-03 (fluxo manual produção→dispensação iniciado, SO 00138).

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

### Pedido real gerado via n8n (deal 60801476407) — COMPLETO
```
FPB 00137 TIRZE60-20260603 (item TIR00060, 1 ampola)
SO 00138 R$1963.98 (TIR00060 1800 + FRETE 00069 163.98)
  Customer 00133 (Paulo César) · Patient 00136 (Eveline) · Prescriber 00135
  fp_patient: lote 00137 · receita REAL anexada (valida)
  Reserva PR 00143 → FPB 00137 (1/1 → Totalmente Reservada)
    (PR 00139→00142→00143: trocada/recriada nos testes swap/cancel; ativa=00143)
  Recebimento PE 00140 R$1963.98 · valor 02/06 · liquida 02/07 (D+30) · linkado ao SO
Pronto pra produção/dispensação MANUAL.
```

> **Ops de reserva** (doc 00n): `swap_reservation` troca o lote;
> `cancel_reservation` libera (pedido fica) ou cancela o pedido inteiro
> (`cancel_order`+`cancel_payments`). Validadas em prod no SO 00138.

### 🏭 Fluxo manual em andamento (SO 00138) — guia 09

Modo: **operador clica no ERPNext** (eu guio). Batch físico validade 6 meses
(shelf life 180d). Pula 12 Delivery Note + 13 Sales Invoice ("só Payment Entry").

```
[ ] 9  Produzir: cria Batch TIRZE60-20260603 (val 03/12/2026) +
       FPB 00137.batch_no + produced_qty=1 → "Produzida Totalmente"   ⬅ AQUI
[ ] 10 FPB 00137 → botão "Liberar Reservas" → PR 00143 Liberado
[ ] 11 SO 00138 → botão "Alocar Batch por Paciente" → paciente 00136 batch_no
[—] 12 Delivery Note  — PULA (sem baixa fiscal nesse fluxo)
[—] 13 Sales Invoice  — PULA (modelo só Payment Entry)
[ ] 14 SO 00138 → "Criar Dispensação" → "Abrir Dispensação"
[ ] 15 Dispensação → template → "Imprimir Etiquetas Zebra" (Zebra+BrowserPrint)
[ ] 16 Dispensação → "Marcar Dispensado" → fecha ciclo
```

Gates: produção exige pago AUTORIZADO ✓ · allocate exige PR released ·
dispensação pula paciente sem batch_no.

## Catálogo de erros padronizado (`{code, error, ...ctx}`)

reserve_errors / pack_errors retornam código + mensagem PT:
| code | mensagem | quando |
|---|---|---|
| `BATCH_REQUIRED` | Lote obrigatório: selecione o lote para o produto X | nenhum lote informado (sem FIFO automático) |
| `BATCH_NOT_FOUND` | Lote X não encontrado | fpb_name errado |
| `BATCH_NOT_SUBMITTED` | Lote X não está submetido | FPB em rascunho |
| `BATCH_WRONG_ITEM` | Lote X é de outro produto (Y) | lote de item diferente |
| `BATCH_CLOSED` | Lote X não aceita reservas (status: ...) | lote fechado |
| `INSUFFICIENT_QTY` | Não há quantidade disponível no lote X (disp N, solic M) | saldo < pedido |
| `PATIENT_NOT_FIT` | Paciente X (qtd N) não cabe em nenhum lote restante | bin-pack não fecha |
| `[MISSING_CUSTOMER]` (throw) | Cliente (customer_name) é obrigatório | input |
| `[CUSTOMER_NOT_FOUND]` (throw) | Cliente não encontrado | step_order |
| `[NO_ITEMS]` (throw) | Pedido sem itens | step_order |
| `[MISSING_SO]` (throw) | sales_order/deal_id é obrigatório | step_reserve/patients/cancel/swap |
| `ITEM_NOT_IN_ORDER` | item do swap não está no pedido | swap_reservation |
| `SWAP_TOO_LATE` (blocked) | lote já produzido ou <N dias pra produção | swap_reservation |
| `[ORDER_HAS_PAYMENTS]` (throw) | cancel_order com PE lançado sem cancel_payments | cancel_reservation |
| `[ITEM_FILTER_WITH_ORDER]` (throw) | item_code junto com cancel_order | cancel_reservation |

> "Pacientes não validados" é gate UPSTREAM (validacao_receita.validations.
> status='aprovado') — só pacientes aprovados são enviados/anexados.

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
| Webhook trocar reserva | `POST /webhook/erp/trocar-reserva` (wf `78jiYigeTvfA7Yqd`) |
| Webhook cancelar reserva | `POST /webhook/erp/cancelar-reserva` (wf `AatKl05FLZQHeg0j`) |
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
- `setup_22_reservation_ops` — **trocar** (swap) e **cancelar** reserva (chave produto+pedido)

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
- [~] Validar fluxo manual ponta-a-ponta (produzir batch → dispensação → ZPL)
      EM ANDAMENTO no SO 00138 (guia manual, etapas 9-16 — ver bloco acima)
- [ ] Stock Entry automático na produção (hoje manual)
- [ ] BOM pro TIR00060 se quiser Work Order (hoje sem BOM)
- [ ] Cron/job pra conciliar Payment Entry na clearance_date (extrato credpay)
- [ ] HubSpot Card React: confirmar que aponta pro webhook + envia item_fpb
  (UI já existe, validar payload qty-por-lote)
- [ ] Archive 63 produtos duplicados no HubSpot (task pendente)
- [ ] Properties HubSpot pra médico estruturado (hoje vem de patients.medico_*)
- [ ] Limpar SOs de teste cancelados (00077, 00125, 00126, 00144+PE 00145) — debris
      (00144/00145 = teste cancel_order; cancelados docstatus=2, GL trava delete)

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
API EXTERNA patient-free (doc 00o, setup_23):
  create_batch (cria estoque futuro/FPB)
  create_order (SO+submit+reserva numa chamada; fpb_name OU auto_reserve FIFO)
  reserve_sales_order_item · auto_reserve_sales_order (granular/UI)
RESERVA OPS (chave produto+pedido):
  swap_reservation (troca lote: cancela antigo + reserva novo + re-bin-pack)
    gate: SWAP_TOO_LATE se produzido ou <N dias (config swap_min_days, padrão 5)
  cancel_reservation (libera lote; cancel_order/cancel_payments p/ pedido inteiro)
  n8n webhooks: /webhook/erp/trocar-reserva · /webhook/erp/cancelar-reserva
  UI ERPNext: botões "Cancelar Reserva" + "Trocar Lote" (Client Script no SO)
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
swap_min_days_before_production = 5 (mín. dias antes da produção pra trocar lote)
```
Editável no form ERPNext: `/app/injemed-financial-settings`
