# 13 — Status e Roadmap

> Snapshot do estado do projeto + tudo que está parado aguardando aprovação ou
> credenciais. Atualizado em 2026-05-18.

---

## Sumário

- [1. Estado Atual](#1-estado-atual)
- [2. Etapas Pendentes (precisam decisão/credenciais)](#2-etapas-pendentes)
- [3. Decisões Técnicas Pendentes](#3-decisões-técnicas-pendentes)
- [4. Sprints Sugeridos](#4-sprints-sugeridos)
- [5. Como Continuar (comandos exatos)](#5-como-continuar)
- [6. Validação de cada feature (UI + API)](#6-validação)

---

## 1. Estado Atual

### Implementação ✅ (já em produção em `erp.suaempresa.com.br`)

| # | Módulo | Status | Arquivo de Setup |
|---|---|---|---|
| 1 | Future Production Batch + Production Reservation (DocTypes) | ✅ Instalado | `setup_01_structure.py` |
| 2 | Client Scripts (botões UI) | ✅ Instalado | `setup_02_client_scripts.py` |
| 3 | Server Scripts (validações + 6 endpoints API) | ✅ Instalado | `setup_03_server_scripts.py` |
| 4 | Reports (4 relatórios) | ✅ Instalado | `setup_04_reports.py` |
| 5 | Workspace "Produção Futura" | ✅ Instalado | `setup_05_workspace.py` |
| 6 | Patients (mestres + child table) | ✅ Instalado | `setup_06_patients.py` |
| 7 | Prescribers (CRM/CRO/CRF/CRBM/...) | ✅ Instalado | `setup_07_prescribers.py` |
| 8 | Batch por Paciente (alocação) | ✅ Instalado | `setup_08_patient_batch.py` |
| 9 | Form Visibility (11 fetch fields) | ✅ Instalado | `setup_09_form_visibility.py` |
| 10 | Dispensação + Zebra (v2: 1 SO = 1 entrega + child) | ✅ Instalado | `setup_10_dispensation.py` |

### Endpoints REST disponíveis ✅ (12 endpoints)

```
POST /api/method/future_production_reserve_sales_order_item
POST /api/method/future_production_auto_reserve_sales_order
POST /api/method/future_production_recalculate_batch
POST /api/method/future_production_create_work_order
POST /api/method/future_production_release_batch
POST /api/method/future_production_replan_pending_qty
POST /api/method/future_production_allocate_patient_batches
POST /api/method/future_production_create_dispensation_from_so
POST /api/method/future_production_generate_zpl_label
POST /api/method/future_production_generate_all_zpl_labels
POST /api/method/future_production_mark_label_printed
POST /api/method/future_production_mark_dispensation_completed
```

### Testes ✅ (todos passando)

| Teste | Cenário | Tempo |
|---|---|---|
| `test_scenario.py` | 4 SOs + 1 FPB 2000 + 4 cenários de produção | ~30s |
| `test_scenario_patients.py` | Validações de CPF, soma qty, item match | ~20s |
| `test_scenario_prescribers.py` | CPF dup, conselho dup, Cassado bloqueia | ~25s |
| `mini_flow.py` | End-to-end 1 SO com asserts automáticos | ~15s |
| `smoke_test_large.py` | 10 FPBs × 2k, 22 SOs | ~3 min |
| `smoke_test_huge.py` | 100 FPBs × 2k, 30 SOs, faturamento end-to-end | ~5 min |

### Fluxo end-to-end validado ✅

```
[Comercial]
  Cadastro Customer ─► Cadastro Prescriber ─► Cadastro Patient
                                 │
                                 ▼
                  Criar FPB (planejar produção)
                                 │
                                 ▼
                  Criar Sales Order + fp_patients[]
                                 │
                                 ▼
                  Reservar (manual ou auto FIFO)

[Produção]
                                 │
                                 ▼
                  Criar Batch físico real
                                 │
                                 ▼
                  Atualizar FPB.produced_qty + batch_no
                                 │
                                 ▼
                  Stock Entry Manufacture (entrada no Bin)

[Supervisor]
                                 │
                                 ▼
                  Liberar Reservas (FIFO)
                                 │
                                 ▼
                  Alocar Batch por Paciente

[Expedição]
                                 │
                                 ▼
                  Delivery Note (baixa estoque)

[Financeiro]
                                 │
                                 ▼
                  Sales Invoice (gera contábil)
                                 │
                                 ▼
              [PENDENTE] Payment Entry (recebimento)

[Farmácia]
                                 │
                                 ▼
              [PENDENTE] Dispensação + Etiqueta Zebra
```

### Documentação ✅

| Arquivo | Conteúdo | Linhas |
|---|---|---|
| `docs/01-overview.md` | Problema + solução | — |
| `docs/02-architecture.md` | DocTypes + scripts | — |
| `docs/03-installation.md` | Pré-requisitos + setup | — |
| `docs/04-usage-flows.md` | Fluxos A + B | — |
| `docs/05-api-reference.md` | Todos endpoints | — |
| `docs/06-data-model.md` | Schema completo | — |
| `docs/07-business-rules.md` | RB-001..010 | — |
| `docs/08-troubleshooting.md` | 12 cases conhecidos | — |
| `docs/09-testing.md` | Como rodar testes | — |
| `docs/10-changelog.md` | Histórico de versões | — |
| `docs/11-manual-operacional.md` | Manual visual operador | ~2950 |
| `docs/12-smoke-test-grande.md` | Guia smoke large | — |
| `docs/13-status-e-roadmap.md` | Este arquivo | — |

Distribuíveis em `docs/dist/`: HTML (197 KB) + DOCX (65 KB) + PDF (2.5 MB)

---

## 2. Etapas Pendentes

### A. Aguardando credenciais

| # | Item | Bloqueio | Onde colocar |
|---|---|---|---|
| **A1** | Integração ASAAS (emissão NF + cobrança) | API key prod | `.env` → `ASAAS_API_KEY` |
| **A2** | Metabase dashboards | URL + login + DB MariaDB | `.env` → `METABASE_*` + `ERPNEXT_DB_*` |

### B. Aguardando decisão de negócio

| # | Item | Decisão necessária |
|---|---|---|
| **B1** | Modelo Zebra impressora | GC420 / ZD220 / ZT411 / genérico? |
| **B2** | Validação CPF dígito verificador | Implementar agora ou só auditoria? |
| **B3** | Migração `prescribing_doctor → default_prescriber` | Quando rodar? Forçar ou opcional? |
| **B4** | ASAAS sandbox ou prod | Recomendado: sandbox primeiro |
| **B5** | Dados fiscais Sua Empresa Ltda | Stub OK por enquanto. Quando completar? |

### C. Construção de código (sem deps externas)

| # | Item | Esforço | Prioridade | Status |
|---|---|---|---|---|
| **C1** | Payment Entry phase no smoke huge | Pequeno | Alta | ⏳ pendente |
| **C2** | DocType `Dispensation` + Server Script ZPL | Médio | Alta | ✅ feito (v2 com child) |
| **C3** | Client Script botão "Imprimir Etiqueta Zebra" + BrowserPrint JS | Médio | Alta | ✅ feito |
| **C4** | Endpoint único `future_production_issue_order` (1 call cria SO + reserva) | Médio | Média | ⏳ pendente |
| **C5** | Server Script RB-007 (delivery_qty ≤ released_qty) | Pequeno | Média | ⏳ pendente |
| **C6** | Server Script RB-008 (bloqueia cancel FPB com PR ativa) | Pequeno | Média | ⏳ pendente |
| **C7** | Migração script `prescribing_doctor` → `default_prescriber` | Pequeno | Baixa | ⏳ pendente |
| **C8** | Workspace add link "Médico Prescritor" no menu | Pequeno | Baixa | ⏳ pendente |
| **C9** | Smoke test replan + cancel | Pequeno | Baixa | ⏳ pendente |
| **C10** | Tabela `fp_dispensations` (registro de dispensação por paciente + data + assinatura) | Médio | Alta | ✅ feito (child table) |
| **C11** | Botão "Criar Dispensação" no Sales Order (Client Script) | Pequeno | Média | ⏳ pendente |
| **C12** | Form Visibility (fetch fields completos no fp_patients) | Pequeno | Alta | ✅ feito |

### D. Construção de código (precisam credentials)

| # | Item | Depende de |
|---|---|---|
| **D1** | Server Script cliente ASAAS (HTTP wrapper) | A1 |
| **D2** | DocType `Asaas Invoice` (espelho da NF emitida) | A1 |
| **D3** | Endpoint `future_production_asaas_emit_invoice(sales_invoice)` | A1 |
| **D4** | Webhook handler ASAAS (atualiza payment status no SI) | A1 |
| **D5** | Queries SQL pra dashboard Metabase | A2 |
| **D6** | JSON export de 4 dashboards Metabase (Produção, Vendas, Estoque, Pendências) | A2 |

### E. Documentação adicional

| # | Item |
|---|---|
| **E1** | `docs/14-asaas-integration.md` (após A1 resolvido) |
| **E2** | `docs/15-metabase-dashboards.md` (após A2 resolvido) |
| **E3** | `docs/16-dispensacao-zebra.md` (após C2-C3) |
| **E4** | Atualizar `docs/11-manual-operacional.md` seção J com tela real |

---

## 3. Decisões Técnicas Pendentes

### 3.1. ASAAS sandbox vs prod

**Recomendação**: começar sandbox. Sandbox emite NF fictícia mas com mesma API. Valida fluxo sem custo/risco. Após OK, troca URL no `.env`.

```env
# Sandbox
ASAAS_URL=https://sandbox.asaas.com/api/v3
ASAAS_API_KEY=<sandbox-key>

# Prod (depois de validar)
ASAAS_URL=https://api.asaas.com/v3
ASAAS_API_KEY=<prod-key>
```

### 3.2. Dispensação — DocType novo ou child em Delivery Note?

| Abordagem | Prós | Contras |
|---|---|---|
| **DocType `Dispensation`** | Atomic, audit completo, status própria, signature, fotos | + 1 DocType pra manter |
| **Child table `fp_dispensations` em DN** | Reaproveita DN, menos doctypes | Menos auditável, status mixed |

**Recomendado**: DocType separado. Cada dispensação = 1 documento submitable com paciente, lote, qty, data, assinatura, farmacêutico responsável.

### 3.3. Metabase — conexão direta ao banco vs API ERPNext

| Opção | Performance | Setup |
|---|---|---|
| **Conexão direta MariaDB** | Rápida | Precisa usuário readonly no DB |
| **API REST ERPNext** | Lenta (N+1) | Só auth token |

**Recomendado**: conexão direta. Criar usuário MySQL readonly:
```sql
CREATE USER 'metabase_ro'@'%' IDENTIFIED BY '<senha>';
GRANT SELECT ON `_<site>_db`.* TO 'metabase_ro'@'%';
FLUSH PRIVILEGES;
```

### 3.4. Validação CPF (algoritmo dígito verificador)

Hoje valida só 11 dígitos + não-triviais. ANVISA pode exigir DV oficial. Implementação: 8 linhas Python no Server Script. Esforço baixo.

### 3.5. Cancelar SO com SI emitida

Hoje: ERPNext nativo bloqueia. Decisão: workflow de reverso explícito ou usar Credit Note?

---

## 4. Sprints Sugeridos

### Sprint 1 — Sem dependências externas (1-2 dias)

Pode rodar agora sem esperar credentials.

- [x] **C2**: DocType `Dispensation` + endpoint ZPL genérico ✅
- [x] **C3**: Client Script "Imprimir Etiqueta Zebra" (com Zebra BrowserPrint) ✅
- [x] **C10**: Child table de pacientes na Dispensação ✅
- [x] **C12**: Form Visibility (fetch fields) ✅
- [ ] **C1**: Payment Entry phase no smoke
- [ ] **C4**: Endpoint único `issue_order`
- [ ] **C5**: RB-007 (delivery_qty ≤ released_qty)
- [ ] **C8**: Workspace Prescriber
- [ ] **C11**: Botão "Criar Dispensação" no Sales Order

### Sprint 2 — ASAAS (precisa A1)

- [ ] **D1-D4**: Integração ASAAS completa
- [ ] **E1**: Doc ASAAS
- [ ] Validar com 1 NF de teste antes de rodar em lote

### Sprint 3 — Metabase (precisa A2)

- [ ] **D5-D6**: Queries + 4 dashboards
- [ ] **E2**: Doc Metabase
- [ ] Importar JSONs no ambiente real

### Sprint 4 — Hardening

- [ ] **B2**: DV CPF
- [ ] **C6**: RB-008
- [ ] **C7**: Migração prescribing_doctor
- [ ] **C9**: Testes replan/cancel
- [ ] **E4**: Atualizar manual operacional

---

## 5. Como Continuar

### Pra rodar tudo agora (smoke huge end-to-end)

```bash
source .venv/bin/activate

# Limpa qualquer estado anterior
python smoke_test_huge.py --phase cleanup
python tools/deep_cleanup.py --yes

# Roda tudo
python smoke_test_huge.py --phase all
```

### Pra validar 1 fluxo pequeno (debug)

```bash
python mini_flow.py            # interativo (pausa entre fases)
python mini_flow.py --no-pause # rápido (sem pausa)
python mini_flow.py --cleanup  # limpa
```

### Pra adicionar credentials

Edite `.env` (já tem placeholders em `.env.example`):

```bash
ASAAS_URL=https://api.asaas.com/v3
ASAAS_API_KEY=<sua-key-real>

METABASE_URL=https://<seu>.metabase.com
METABASE_USERNAME=<email>
METABASE_PASSWORD=<senha>

ERPNEXT_DB_HOST=<ip>
ERPNEXT_DB_PORT=3306
ERPNEXT_DB_NAME=<db>
ERPNEXT_DB_USER=<user>
ERPNEXT_DB_PASSWORD=<pass>
```

### Pra reinstalar do zero (após reset DB)

```bash
python setup_all.py            # roda 8 passos idempotentes
```

### Pra desinstalar (mantém docs do ERPNext)

```bash
python setup_all.py --uninstall
```

---

## 6. Validação

### Cada feature em UI + API + Python

#### Future Production Batch

```bash
# UI
https://erp.suaempresa.com.br/app/future-production-batch

# API
curl -X GET "https://erp.suaempresa.com.br/api/resource/Future Production Batch" \
  -H "Authorization: token API_KEY:API_SECRET" \
  --data-urlencode 'fields=["name","planned_qty","available_qty","produced_qty","released_qty","status"]' \
  -G

# Python
python -c "
from lib.erpnext_api import client_from_env
from lib.visibility import list_fpbs, print_fpb_table
c = client_from_env()
print_fpb_table(list_fpbs(c))
"
```

#### Production Reservation

```
UI:     https://erp.suaempresa.com.br/app/production-reservation
API:    GET /api/resource/Production Reservation
        ?filters=[["docstatus","=",1],["pending_qty",">",0]]
```

#### Prescriber

```
UI:     https://erp.suaempresa.com.br/app/prescriber
        Filtre por council_type=CRM, council_state=SP, council_status=Ativo
```

#### Sales Order com fp_patients

```
UI:     https://erp.suaempresa.com.br/app/sales-order/<name>
        Role até "Pacientes" → vê batch_no/allocated_qty/batch_status por linha
```

#### Stock Balance (verificar entrada física)

```
UI:     https://erp.suaempresa.com.br/app/stock-balance
        Filtre item_code=TIR00060 → vê qty por batch + warehouse
```

#### Sales Invoice

```
UI:     https://erp.suaempresa.com.br/app/sales-invoice
        Status: Unpaid (até Payment Entry)
```

### Reports customizados

| Report | URL |
|---|---|
| Mapa de Produção | `/app/query-report/Mapa%20de%20Produção` |
| Saldo por Lote | `/app/query-report/Saldo%20por%20Lote` |
| Reservas por Pedido | `/app/query-report/Reservas%20por%20Pedido` |
| Pendências de Liberação | `/app/query-report/Pedidos%20Pendentes%20de%20Liberação` |

---

## Anexo — Resumo de commits

```
b5ad483 refactor: Dispensation v2 — 1 per SO with child table of patients
9499566 feat: add Dispensation DocType + Zebra ZPL labels (setup_10)
4339ac4 feat: add form visibility fetch fields + complete process diagram doc
24e4c0b docs: comprehensive status + roadmap + pending approvals (v0.2.0)
10728e9 feat: add invoice + stock-in phases to huge smoke test
0b918bf feat: add huge-scale smoke test (100 FPBs, 30 SOs) + deep cleanup
8bb29e4 fix: correct fp_released_qty double-counting in release_batch
a20854c feat: add batch-per-patient allocation (setup_08)
68da624 feat: add large-volume smoke test with visibility helpers
3524f3b feat: add Prescriber DocType module (setup_07)
b5e5d36 docs: add operational manual with 4 entity model
9df0ec0 Initial commit: erp-next-future-stock 0.1.0
```

---

## Anexo — Próximas perguntas a responder

Pra desbloquear próximas etapas, preciso de:

### Pra ASAAS (Sprint 2)

1. **API key ASAAS** (prod ou sandbox)
2. **CNPJ Sua Empresa Ltda** (pra ASAAS validar emissor)
3. **Inscrição Estadual** + **regime tributário**
4. **NCM** do TIR00060
5. **CFOP** padrão de venda (interna ou interestadual)

### Pra Metabase (Sprint 3)

1. **URL Metabase**
2. **Login + senha admin Metabase**
3. **IP/host do MariaDB do ERPNext** (acessível pelo Metabase)
4. **Usuário readonly MariaDB** (criar se não existir)
5. **Nome do database** (geralmente `_<site_id>_db`)

### Pra Zebra (Sprint 1 C2-C3)

1. **Modelo da impressora** (GC420, ZD220, ZT411, etc)
2. **Conectividade** (USB local, USB compartilhada via Print Server, rede IP)
3. **Dimensão da etiqueta** (50×30mm, 60×40mm, outro)
4. **Campos obrigatórios** na etiqueta (paciente, CPF, lote, validade, item, barcode/QR)
