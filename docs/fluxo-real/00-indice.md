# Fluxo Real — Índice Central

> Documenta o fluxo **real** end-to-end executado em produção
> `https://erp.injemedpharma.com.br`. Tudo aqui é dado/execução **real**,
> não exemplo teórico.

---

## 📂 Mapa rápido (todos os fluxos)

| Camada | Arquivo | O que cobre |
|---|---|---|
| **Convenções** | [00b-numeracao.md](00b-numeracao.md) | Auto-increment puro `00001..` em todos DocTypes operacionais |
| **Convenções** | (este) [00-indice.md](00-indice.md) | Padrão `TIRZE<dose>-YYYYMMDD`, lista geral |
| **Sync Produtos** | [00d-sync-produtos-hubspot.md](00d-sync-produtos-hubspot.md) | HubSpot Products → ERPNext Items + write-back `hs_sku` |
| **Sync SKU line_items** | [00g-workflow-auto-hs-sku.md](00g-workflow-auto-hs-sku.md) | HubSpot Workflow + n8n preenche `line_item.hs_sku` automaticamente |
| **Fonte de dados** | [00e-fonte-dados-validacao-receita.md](00e-fonte-dados-validacao-receita.md) | Schema Postgres validacao_receita + responsabilidades |
| **Arquitetura sync** | [00f-arquitetura-sync-validacao-receita.md](00f-arquitetura-sync-validacao-receita.md) | Opção B: HubSpot Card React + webhook n8n |
| **Integração** | [00h-integracao-automatica.md](00h-integracao-automatica.md) | setup_14 endpoint único + n8n workflow `sync_order_to_erpnext` |
| **Contrato Card** | [00i-contrato-card-react.md](00i-contrato-card-react.md) | Body/response do webhook, fpb_map vs patient_fpb, esqueleto TSX |
| **Receita anexa** | [00j-receita-anexa-paciente.md](00j-receita-anexa-paciente.md) | PDF receita anexado por linha do paciente em fp_patients |
| **Etapas 1-7** | (abaixo) | Execução end-to-end real (Paulo César deal 60801476407) |

---

## 🔗 Links operacionais

| Sistema | URL |
|---|---|
| ERPNext prod | https://erp.injemedpharma.com.br |
| n8n prod | https://n8n.injemedpharma.com.br |
| HubSpot Deals | https://app.hubspot.com/contacts/51388090 |
| Postgres (validacao_receita) | `postgres://postgres@2.24.98.117:5432/postgres` (schema `validacao_receita`) |
| Postgres (checkout_simples) | mesmo host, schema `checkout_simples` |
| Postgres (asaas) | mesmo host, schema `asaas` |

| Repositório | URL |
|---|---|
| ERPNext setup (este repo) | https://github.com/CairoWesley/erp-next-future-stock |
| Backend validacao_receita | https://github.com/Unikka-Pharma/backend-sistema-receitas |
| Frontend validacao | https://github.com/Unikka-Pharma/frontend-injemed-sistema-pacientes |
| n8n workflow sync deal | https://n8n.injemedpharma.com.br/workflow/0nuMbQ25ZzuUvmPE |

---

## 🎯 Webhook ÚNICO (Card React → ERPNext)

```
POST https://n8n.injemedpharma.com.br/webhook/erp/sync-order
Content-Type: application/json

# Forma preferencial: QUANTIDADE POR LOTE.
# Operador aloca X ampolas lote 1, Y ampolas lote 2.
# Sistema distribui pacientes entre lotes (bin-pack).
# REGRA: cada receita (paciente) cabe inteira em UM lote.
{
  "deal_id": "60801476407",
  "item_fpb": [
    {
      "item_code": "TIR00060",
      "lotes": [
        { "fpb_name": "FPB-2026-00115", "qty": 7 },
        { "fpb_name": "FPB-2026-00120", "qty": 3 }
      ]
    }
  ]
}
```

Detalhes completos em [00i-contrato-card-react.md](00i-contrato-card-react.md).

---

## 📋 Convenções gerais

### Production Code do FPB

```
TIRZE<dosagem>-YYYYMMDD
```

Exemplos:
- `TIRZE60-20260602` → Tirzepatida 60mg manipulada em 02/06/2026
- `TIRZE90-20260615` → Tirzepatida 90mg manipulada em 15/06/2026

### Batch ID (lote físico)

Mesmo padrão do `production_code` pra rastreabilidade visual:

```
FPB.production_code == Batch.batch_id   (ex: TIRZE60-20260602)
```

### Numeração ERPNext

A partir de `setup_15_naming_series`, toda numeração é
**auto-increment puro zero-padded 5 dígitos** sem prefixo nem ano.
Cada DocType com contador independente. Ver
[00b-numeracao.md](00b-numeracao.md).

| Tipo | Antes | Depois |
|---|---|---|
| Customer | CUST-2026-00001 | `00001` |
| Patient | PAC-2026-00001 | `00001` |
| Prescriber | PRES-2026-00001 | `00001` |
| Sales Order | SAL-ORD-2026-00001 | `00001` |
| FPB | FPB-2026-00115 (mantém) | próximo: `00001` |
| Production Reservation | PR-2026-00001 | `00001` |
| Dispensacao | DISP-2026-00001 | `00001` |
| Delivery Note / Sales Invoice / Payment Entry / Stock Entry | (antigos) | `00001` |

---

## 🚀 Etapas do fluxo real

### Pré-etapas (cobertura única do sistema)

| # | Etapa | Status | Doc |
|---|---|---|---|
| 0a | Convenções gerais | ✅ | (este arquivo) |
| 0b | Numeração auto-increment | ✅ | [00b-numeracao.md](00b-numeracao.md) |
| 0d | Sync produtos HubSpot ↔ ERPNext | ✅ | [00d-sync-produtos-hubspot.md](00d-sync-produtos-hubspot.md) |
| 0e | Fonte de dados validacao_receita | ✅ análise | [00e-fonte-dados-validacao-receita.md](00e-fonte-dados-validacao-receita.md) |
| 0f | Arquitetura sync (HubSpot Card + n8n) | ✅ design | [00f-arquitetura-sync-validacao-receita.md](00f-arquitetura-sync-validacao-receita.md) |
| 0g | Workflow auto `line_item.hs_sku` | ✅ design | [00g-workflow-auto-hs-sku.md](00g-workflow-auto-hs-sku.md) |
| 0h | Integração setup_14 + n8n sync_order | ✅ implementado | [00h-integracao-automatica.md](00h-integracao-automatica.md) |
| 0i | Contrato Card React (deal_id + patient_fpb) | ✅ implementado | [00i-contrato-card-react.md](00i-contrato-card-react.md) |
| 0j | Receita PDF anexada na linha do paciente | ✅ implementado | [00j-receita-anexa-paciente.md](00j-receita-anexa-paciente.md) |
| 0k | **Fluxo n8n node-by-node (ATIVO em prod)** | ✅ rodando | [00k-fluxo-n8n-node-by-node.md](00k-fluxo-n8n-node-by-node.md) |
| 0l | **Regras de negócio (pagamento/liquidação/gating)** | ✅ | [00l-regras-negocio.md](00l-regras-negocio.md) |
| 0m | Configuração Financeira (tempos + banco certo) | ✅ | [00m-configuracao-financeira.md](00m-configuracao-financeira.md) |

### Por pedido (cada deal HubSpot dispara)

| # | Etapa | Status | Doc |
|---|---|---|---|
| 1 | Criar primeiro FPB (lote planejado) | ✅ | [01-criar-fpb.md](01-criar-fpb.md) |
| 2 | Cadastrar Cliente (Customer + Address + Contact) | ✅ via sync | [02-cadastrar-cliente.md](02-cadastrar-cliente.md) |
| 3 | Cadastrar Médico (Prescriber + Council) | ✅ via sync | [03-cadastrar-medico.md](03-cadastrar-medico.md) |
| 4 | Cadastrar Paciente (Patient) | ✅ via sync | [04-cadastrar-paciente.md](04-cadastrar-paciente.md) |
| 5 | Criar Sales Order com fp_patients | ✅ via sync | [05-criar-sales-order.md](05-criar-sales-order.md) |
| 6 | Validar e reservar (3 flags + FPB escolhido) | ✅ via sync | [06-validar-reservar.md](06-validar-reservar.md) |
| ✅ exemplo | Pedido REAL Paulo César (deal 60801476407) | ✅ executado em prod | [07-pedido-real-paulo-cesar.md](07-pedido-real-paulo-cesar.md) |
| 8 | Registrar produção (Batch físico + update FPB) | ⏳ próxima | — |
| 9 | Stock Entry Manufacture | ⏳ | — |
| 10 | Liberar reservas (PR → Batch real) | ⏳ | — |
| 11 | Alocar batch por paciente | ⏳ | — |
| 12 | Delivery Note | ⏳ | — |
| 13 | Sales Invoice | ⏳ | — |
| 14 | Payment Entry (link checkout_simples) | ⏳ | — |
| 15 | Criar Dispensação + imprimir etiqueta Zebra | ⏳ | — |
| 16 | Marcar como dispensado | ⏳ | — |

---

## 🔌 Endpoints ERPNext customizados

| Method | Endpoint | Setup | Função |
|---|---|---|---|
| POST | `/api/method/future_production_issue_order` | `setup/setup_14_issue_order.py` | Sync único: Customer + Address + Contact + Prescriber + Patient + SO + payment + prescriptions + auto-reserve |
| POST | `/api/method/future_production_payment_webhook` | `setup/setup_13_so_validation.py` | Webhook gateway pagamento (legado, substituído por inline em issue_order) |
| POST | `/api/method/future_production_prescriptions_webhook` | `setup/setup_13_so_validation.py` | Webhook validação receita (idem) |
| POST | `/api/method/future_production_validate_and_reserve` | `setup/setup_13_so_validation.py` | Reserva contra FPB FIFO (legado, agora inline em issue_order) |
| POST | `/api/method/upload_file` | nativo Frappe | Upload receita PDF + linka a fp_patients row |
| POST | `/api/method/frappe.client.set_value` | nativo Frappe | Setar campos da row (receita, status) |

---

## 📦 n8n workflows

| Arquivo | Trigger | Função |
|---|---|---|
| `n8n_workflows/sync_order_to_erpnext.json` | webhook `/erp/sync-order` | Lê Postgres + HubSpot + checkout → POST issue_order ERPNext |
| `n8n_workflows/set_line_item_sku.json` | HubSpot Workflow → webhook `/hubspot/line-item-created` | Preenche `line_item.hs_sku` automaticamente |
| `n8n_workflows/hubspot_issue_order_v2.json` | webhook | Versão legada (sem Postgres) — desuso |

---

## 🗄 Schema validacao_receita (Postgres)

Tabelas principais (schema completo em [00e](00e-fonte-dados-validacao-receita.md)):

| Tabela | Função |
|---|---|
| `orders` | pedido (link `hubspot_deal_id`) |
| `deal_companies` | empresa pagante (CNPJ/CPF + endereço + resp. técnico/CRM) |
| `deal_contacts` | contato do CRM |
| `deal_payments` | (não usado — payment vem de `checkout_simples`) |
| `products` | linhas de produto do pedido (`sku` bate com ERPNext Item) |
| `patients` | paciente único por linha (com médico denormalizado, receita PDF path) |
| `validations` | aprovação por paciente |
| `users` | operadores/validadores/admin/vendedor (NÃO médicos) |
| `principios_ativos` | Tirzepatida 180mg/90d, Semaglutida 16mg/90d |

---

## 💳 Schema checkout_simples (Postgres — mesmo host)

| Tabela | Função |
|---|---|
| `checkouts` | link `external_ref = hubspot_deal_id` |
| `transactions` | status PAID + paid_at + provider |
| `payers` | dados do pagador (CPF, endereço, cartão) |

---

## ✅ Regras de negócio críticas

1. **1 receita = 1 lote inteiro**. Paciente nunca dividido entre 2 lotes.
2. **Alocação por quantidade-por-lote**. Operador define X ampolas lote 1, Y lote 2. Sistema distribui pacientes (bin-pack first-fit-decreasing) respeitando regra 1. Se não fechar → erro pedindo reajuste.
3. **Customer = entidade pagante** (PF ou PJ Volpi). CPF/CNPJ do pagador.
4. **Médico (Prescriber)** vem denormalizado de `patients.medico_*`. Lookup por CRM+UF. CPF placeholder se ausente.
5. **Receita PDF** = 1 por paciente. Anexada na row `fp_patients[i].receita`.
6. **Payment** sempre vem de `checkout_simples` (validacao_receita não cuida).
7. **Idempotência**: webhook re-disparado retorna SO existente sem duplicar nada.
