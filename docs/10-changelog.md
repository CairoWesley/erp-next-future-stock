# 10 — Changelog

Histórico de versões. Segue [Semantic Versioning](https://semver.org/).

---

## [0.2.0] — 2026-05-18

### Modelo Customer / Prescriber / Patient + Batch por paciente + Faturamento

#### Adicionado

**Módulo Prescriber** (`setup_07_prescribers.py`):
- `DocType Prescriber` com 25 campos (CPF, conselho profissional, UF, contato, endereço)
- Suporte a 8 tipos de conselho: CRM, CRO, CRF, CRBM, CRN, CRBio, CRP, Outro
- `Patient.default_prescriber` (Custom Field Link/Prescriber)
- `Sales Order Patient.prescriber` (Custom Field Link/Prescriber) + `.prescriber_council` (fetch read-only)
- Server Scripts: validação CPF único, unicidade `(council_type, number, state)`,
  bloqueio de uso quando `council_status=Cassado`
- `test_scenario_prescribers.py` cobrindo todas validações negativas

**Módulo Batch por Paciente** (`setup_08_patient_batch.py`):
- Custom Fields em `Sales Order Patient`:
  - `batch_no` (Link/Batch) — lote físico alocado
  - `allocated_qty` (Float) — quanto da qty já tem batch
  - `batch_status` (Select) — Pendente / Parcialmente Alocado / Alocado / Entregue / Cancelado
- Endpoint `future_production_allocate_patient_batches(sales_order)`:
  - FIFO sobre PRs liberadas
  - Distribui `release_batch_no` para cada linha de paciente
  - Idempotente

**Smoke Tests**:
- `mini_flow.py` — validação 1 FPB / 1 SO / 2 pacientes com check automático por fase
- `smoke_test_large.py` — 10 FPBs × 2000 ampolas, 22 SOs, 3 full + 7 parciais
- `smoke_test_huge.py` — 100 FPBs × 2000, 30 SOs, 10 produzidos full, com fases:
  - setup, fpbs, orders, produce, release, stock_in, allocate, invoice, report, cleanup
- `lib/visibility.py` — helpers de inspeção (tabelas FPB/PR/SO) + URLs UI por contexto
- `tools/deep_cleanup.py` — remoção em ordem de dependência

**Faturamento end-to-end**:
- Phase `stock_in`: Stock Entry Manufacture pra cada FPB produzido (entrada física no Bin)
- Phase `invoice`: Delivery Note direta + Sales Invoice via `make_sales_invoice`
- Validado em escala: 10 SEs + 19 DNs + 19 SIs no smoke huge

**Documentação**:
- `docs/11-manual-operacional.md` — manual visual de uso humano (~2950 linhas)
- `docs/12-smoke-test-grande.md` — guia do smoke large
- `docs/13-status-e-roadmap.md` — estado atual + pendências (este release)
- 3 formatos gerados em `docs/dist/`: HTML (197 KB) + DOCX (65 KB) + PDF (2.5 MB)
- Anexo I com integração API (chain n8n vs endpoint único)
- Anexo II com upload do manual dentro do ERPNext (Web Page DocType)

#### Corrigido

- **bug fp_released_qty dobrava**: `future_production_release_batch` aplicava
  delta sobre SQL sum que já tinha o set_value commitado. Cálculo agora confia
  no sum direto. Bug não pego antes porque testes assertavam só PR-level
  (correto), não SOI mirror. Descoberto via `mini_flow.py`.

---

## [0.3.0] — 2026-05-18

### Form Visibility + Dispensação v2 + Zebra ZPL

#### Adicionado

**Form Visibility** (`setup_09_form_visibility.py`):
- 11 Custom Fields `fetch_from` no `Sales Order Patient` mostram dados
  completos linkados sem precisar clicar:
  * Patient: gender, birth_date, email, city, state
  * Prescriber: full_name, council_number, council_state, council_status
  * Batch: expiry_date, manufacturing_date
- Total 17 dados visíveis por linha de paciente no SO

**Módulo Dispensação + Zebra (v2)** (`setup_10_dispensation.py`):
- Modelo: **1 Sales Order = 1 Dispensation** (entrega completa)
- DocType `Dispensation` (submetível) com:
  * sales_order (Link), customer (fetch), pharmacist, dispensed_at
  * total_qty, total_patients (calculados)
  * label_template (50x30mm / 100x50mm), all_printed, printed_count
- DocType `Dispensation Patient` (child table) com fetch fields completos:
  * patient + name + cpf + mobile
  * prescriber + name + council_type + number + state
  * item + name + qty
  * batch_no + expiry + manufacturing
  * printed (Check) + printed_at + signature (Attach Image)
- Custom Field `Sales Order.dispensation` (Link) — espelho 1:1
- 5 Server Scripts (endpoints API):
  * `create_dispensation_from_so` — 1 chamada cria Dispensation com N rows
  * `generate_zpl_label` — ZPL de 1 linha
  * `generate_all_zpl_labels` — ZPL multi (todas N linhas concatenadas)
  * `mark_label_printed` — marca 1 linha + atualiza counter
  * `mark_dispensation_completed` — status Dispensado + espelha em SOP
- Client Script com 3 botões:
  * "Imprimir Todas as Etiquetas Zebra" (header)
  * "Marcar como Dispensado" (header)
  * "Imprimir Esta Linha" (grid child)
- BrowserPrint integration com fallback dialog (cola ZPL manualmente)

**Documentação**:
- `docs/14-diagrama-processo-completo.md` — fluxo visual 11 etapas com
  tela + dados visíveis + URL + payload API por etapa
- `docs/15-dispensacao-zebra.md` — guia completo Dispensação v2

#### Validado em smoke test huge

- 19 Dispensations criadas (1 por SO alocado)
- 79 etiquetas potenciais totais
- ZPL multi: 1719 bytes (5 etiquetas), 1031 bytes (3 etiquetas)
- 11 SOs sem alocação rejeitados com erro claro (esperado)

#### Notas técnicas

- Frappe restricted Python rejeita `list of dict` em campos Table.
  Solução: `new_doc.append("patients", row)` por item.
- DocType com `unique: 1` em campo Link falha re-instalação quando
  tabela tem dados antigos órfãos. Solução: removido unique constraint,
  validação movida para endpoint.

---

## [0.1.0] — 2026-05-18

### Versão inicial — implementação completa

Instalada e validada em `https://erp.injemedpharma.com.br`.

#### Adicionado

**Módulo Reserva de Produção Futura**:
- `DocType Future Production Batch` com 30 campos, 11 status (workflow automático), permissions para 5 roles
- `DocType Production Reservation` com 17 campos, 5 status, permissions para 5 roles
- Custom Fields em `Sales Order Item`: `fp_section`, `fp_future_production_batch`, `fp_reserved_qty`, `fp_released_qty`, `fp_pending_release_qty`, `fp_reservation_status` (prefixo `fp_` para evitar colisão com nativos)
- 5 Server Scripts de evento (FPB Before Save, FPB After Save, PR Before Save, PR After Submit, PR After Cancel)
- 6 endpoints customizados em `/api/method/future_production_*`:
  - `reserve_sales_order_item`
  - `auto_reserve_sales_order`
  - `recalculate_batch`
  - `create_work_order`
  - `release_batch`
  - `replan_pending_qty`
- 3 Client Scripts (botões UI nas telas FPB, Sales Order, Production Reservation)
- 4 Reports (Mapa de Produção, Reservas por Produção, Pedidos Pendentes, Risco de Produção)
- Workspace "Produção Futura" com shortcuts e links

**Módulo Lote × Pacientes**:
- `DocType Patient` com 22 campos (identificação, contato, endereço, médico prescritor)
- `DocType Sales Order Patient` (child table) com 8 campos (fetch_from automatizado)
- Custom Fields em `Sales Order`: `fp_patients_section`, `fp_patients`
- 2 Server Scripts (validação de CPF, validação soma qty pacientes = qty item)

**Setup automatizado**:
- Cliente HTTP em `lib/erpnext_api.py` com idempotência (verificar-antes-de-criar) e logs estruturados
- Scripts numerados `setup_01..06.py` + orquestrador `setup_all.py`
- Suporte a `--uninstall` e `--skip N,M,...`

**Testes**:
- `test_scenario.py` parametrizável (`--produced-qty`) cobrindo 4 cenários (produção exata, subprodução leve, subprodução grave, sobreprodução)
- `test_scenario_patients.py` cobrindo cadastro de paciente, vínculo no SO, validações negativas

**Ferramentas auxiliares** em `tools/`:
- `diagnose.py` — snapshot do ambiente
- `inspect_fpb.py`, `inspect_master.py`, `inspect_healthcare.py` — introspecção
- `fix_fpb_schema.py` — recriação segura quando DocType veio vazio
- `recreate_doctypes.py` — reset destrutivo de FPB/PR

**Documentação**:
- `README.md` raiz com overview e quickstart
- 10 arquivos em `docs/`:
  1. Overview
  2. Architecture
  3. Installation
  4. Usage Flows
  5. API Reference
  6. Data Model
  7. Business Rules
  8. Troubleshooting
  9. Testing
  10. Changelog (este arquivo)

#### Correções e quirks descobertos durante a implantação

- `DocType` que já existia com schema mínimo (2 campos) — adicionado `tools/fix_fpb_schema.py`
- `frappe.client.submit` exige doc completo com `modified` atual — helpers `submit_doc`/`cancel_doc`
- Hooks bloqueavam por `UpdateAfterSubmitError` — trocado `doc.save()` por `frappe.db.set_value` + adicionado `allow_on_submit: 1` aos 13 campos calculados relevantes
- RestrictedPython:
  - Não suporta `+=`/`-=` — trocados por atribuição expandida em 5 lugares
  - Não permite identificadores com `_` no início (`_digits` → `only_digits`)
  - `str.format()` marcado como unsafe em alguns contextos — trocado por concatenação em scripts mais novos
- Frappe usa eventos em inglês internamente (`After Submit`, `After Cancel`) mesmo com UI traduzida
- Ambiente PT-BR exige `customer_group="Comercial"` e `territory="Brazil"`
- Caracteres unicode `✓`/`✗`/`→` quebram `cp1252` no Windows — trocado por ASCII (`OK`/`FAIL`)

#### Resultados de teste

Cenário da seção 23 da documentação original (`produced=1850`):

| Campo | Esperado | Obtido |
|---|---:|---:|
| FPB.planned_qty | 2000 | 2000 ✓ |
| FPB.reserved_qty | 2000 | 2000 ✓ |
| FPB.released_qty | 1850 | 1850 ✓ |
| FPB.pending_release_qty | 0 | 0 ✓ |
| SO-Delta.released_qty | 350 | 350 ✓ |
| SO-Delta.pending_qty | 150 | 150 ✓ |

Cenários adicionais validados: `produced=2000` (Liberada Totalmente), `produced=1500` (Delta zerada), `produced=2100` (100 unid sem reserva).

---

## Backlog (não implementado, candidato para 0.2.0+)

- **RB-007**: Server Script no Delivery Note bloqueando `delivery_qty > released_qty`
- **RB-008**: Server Script no FPB Before Cancel bloqueando cancelamento com PRs ativas
- **RBP-001 estendida**: validação do dígito verificador do CPF (algoritmo oficial)
- Rastreabilidade direta lote físico → paciente (campo `release_batch_no` em Sales Order Patient)
- Importação em massa de pacientes via CSV/XLSX
- Geração de etiqueta PDF por paciente
- Reports adicionais (CSV/Excel de pacientes por lote para auditoria)
- Suporte multi-empresa
- Testes unitários `pytest` para `lib/erpnext_api.py`
