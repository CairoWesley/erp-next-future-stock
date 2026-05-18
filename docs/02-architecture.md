# 02 — Arquitetura

## Visão de alto nível

```
┌──────────────────────────────────────────────────────────────────┐
│                    erp-next-future-stock                         │
│                                                                  │
│  ┌─ Scripts de setup (rodam fora do ERPNext, via HTTP) ─────┐   │
│  │  setup_01_structure.py    → DocTypes + Custom Fields     │   │
│  │  setup_02_client_scripts  → 3 Client Scripts (UI)        │   │
│  │  setup_03_server_scripts  → 11 Server Scripts            │   │
│  │  setup_04_reports.py      → 4 Reports                    │   │
│  │  setup_05_workspace.py    → Workspace + menu             │   │
│  │  setup_06_patients.py     → Patient + Sales Order Patient│   │
│  │  setup_all.py             → orquestra os 6 anteriores    │   │
│  └──────────────────────────────────────────────────────────┘   │
│           │                                                      │
│           │  HTTPS + token API_KEY:API_SECRET                    │
│           ▼                                                      │
│  ┌─ ERPNext em Docker ────────────────────────────────────────┐  │
│  │                                                            │  │
│  │  /api/resource/<DocType>          ← CRUD genérico          │  │
│  │  /api/resource/Server Script      ← cria/atualiza scripts  │  │
│  │  /api/resource/Client Script      ← cria/atualiza JS       │  │
│  │  /api/method/<api_name>           ← endpoints customizados │  │
│  │                                                            │  │
│  │  ┌─ DocTypes custom ──────────────────────────────────┐    │  │
│  │  │  Future Production Batch (submittable)             │    │  │
│  │  │  Production Reservation (submittable)              │    │  │
│  │  │  Patient (master)                                  │    │  │
│  │  │  Sales Order Patient (child table)                 │    │  │
│  │  └────────────────────────────────────────────────────┘    │  │
│  │                                                            │  │
│  │  ┌─ Custom Fields ───────────────────────────────────┐     │  │
│  │  │  Sales Order Item: fp_section, fp_reserved_qty,    │     │  │
│  │  │    fp_released_qty, fp_pending_release_qty,        │     │  │
│  │  │    fp_future_production_batch, fp_reservation_status│    │  │
│  │  │  Sales Order: fp_patients_section, fp_patients     │     │  │
│  │  └────────────────────────────────────────────────────┘    │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## DocTypes

### Future Production Batch (`Manufacturing` module)
Representa uma produção planejada para o futuro. Tem ciclo de vida draft → submitted → cancelled. Submittable (`is_submittable=1`), aceita reservas só com `docstatus=1`.

Campos calculados que recebem `allow_on_submit=1` (edição permitida pós-submit via `frappe.db.set_value`):
- `reserved_qty`, `available_qty`, `produced_qty`, `released_qty`, `pending_release_qty`
- `batch_no`, `work_order`, `status`

Schema completo: ver [`06-data-model.md`](06-data-model.md).

### Production Reservation (`Manufacturing` module)
Liga 1 linha de Sales Order a 1 FPB. Também submittable. Cada PR consome saldo do FPB pai ao ser submetida e devolve ao ser cancelada.

### Patient (`Manufacturing` module)
Cadastro mestre dos pacientes. Não-submittable. CPF é único e validado (11 dígitos, não trivial).

### Sales Order Patient (`Manufacturing` module, child table)
`istable=1`. Aparece como tabela dentro do Sales Order (custom field `fp_patients`). Cada linha tem: patient, item_code, qty, mais campos fetch_from do Patient (nome, CPF, mobile).

## Custom Fields

### Em `Sales Order Item` (espelho da reserva)
| Campo | Tipo | Propósito |
|---|---|---|
| `fp_section` | Section Break | Agrupador "Produção Futura" |
| `fp_future_production_batch` | Link / Future Production Batch | FPB onde está reservado |
| `fp_reserved_qty` | Float (read-only) | Quanto foi reservado |
| `fp_released_qty` | Float (read-only) | Quanto foi liberado |
| `fp_pending_release_qty` | Float (read-only) | Quanto falta liberar |
| `fp_reservation_status` | Select (read-only) | Sem Reserva / Reservado / Parcialmente Reservado / Liberado / Parcialmente Liberado / Pendente |

> Prefixo `fp_` para **não colidir** com `Sales Order Item.reserved_qty` nativo (usado pelo Stock Reservation Entry do ERPNext).

### Em `Sales Order` (módulo Pacientes)
| Campo | Tipo | Propósito |
|---|---|---|
| `fp_patients_section` | Section Break | Agrupador "Pacientes" |
| `fp_patients` | Table → Sales Order Patient | Pacientes vinculados |

## Server Scripts

### DocType Events (5)
| Nome | DocType | Evento | Função |
|---|---|---|---|
| FPB - Validate (Before Save) | Future Production Batch | Before Save | Valida planned > 0, reservado ≤ planejado+overbooking, recalcula available_qty e pending_release_qty |
| FPB - Update Status (After Save) | Future Production Batch | After Save | Ajusta `status` automaticamente conforme reservado/produzido/liberado |
| PR - Validate (Before Save) | Production Reservation | Before Save | Valida item igual ao FPB, SO submetido, saldo suficiente |
| PR - On Submit | Production Reservation | After Submit | Recalcula totais do FPB + atualiza espelho no SO Item |
| PR - On Cancel | Production Reservation | After Cancel | Devolve saldo ao FPB + atualiza espelho |
| SO - Validate Patients | Sales Order | Before Save | Valida soma qty pacientes = qty item, CPF, item nas linhas do SO |
| Patient - Validate CPF | Patient | Before Save | Valida CPF (11 dígitos, não trivial), normaliza armazenando só dígitos |

### Endpoints customizados (6)
Disponíveis em `/api/method/<nome>`. Todos exigem autenticação por token.

| Endpoint | Função |
|---|---|
| `future_production_reserve_sales_order_item` | Reserva 1 linha de SO em 1 FPB específico |
| `future_production_auto_reserve_sales_order` | Distribui automaticamente um SO inteiro entre FPBs disponíveis |
| `future_production_recalculate_batch` | Recalcula totais de um FPB (manutenção) |
| `future_production_create_work_order` | Cria Work Order a partir do FPB |
| `future_production_release_batch` | Distribui o produzido entre as reservas (FIFO/prioridade) |
| `future_production_replan_pending_qty` | Move qty pendente de uma PR para outra FPB |

Detalhes em [`05-api-reference.md`](05-api-reference.md).

## Client Scripts (3)

Adicionam botões nas telas:

| DocType | Botões |
|---|---|
| Future Production Batch | Recalcular Saldos, Criar Work Order, Liberar Reservas, Ver Reservas |
| Sales Order | Reservar em Produção Futura, Reservar Automaticamente, Ver Reservas do Pedido |
| Production Reservation | Replanejar Pendência, Ver Pedido, Ver Produção |

## Reports (4)

Tipo Report Builder (não Query Report) para evitar restrições de SQL puro:

| Nome | Base DocType | Filtros padrão |
|---|---|---|
| Mapa de Produção Futura | Future Production Batch | — |
| Reservas por Produção | Production Reservation | `docstatus=1` |
| Pedidos Pendentes de Liberação | Production Reservation | `docstatus=1, pending_qty>0, status in [Reservado, Parcialmente Liberado]` |
| Risco de Produção | Future Production Batch | `docstatus=1, status not in [Produzida Totalmente, Liberada Totalmente, Cancelada], planned_production_date < hoje` |

## Workspace

`Produção Futura` (módulo Manufacturing) com:
- 5 shortcuts: Lotes, Reservas, Pacientes, Mapa de Produção, Pendências
- Card "Documentos": Future Production Batch, Production Reservation, Patient, Sales Order, Work Order
- Card "Relatórios": os 4 reports

## Decisões técnicas relevantes

### 1. DocTypes `custom: 1`
Criados como custom doctypes (sem arquivos `.json`/`.py` no filesystem do app). Permite implantar via API REST sem entrar no container. Limitação: não há controllers Python — toda lógica fica em Server Scripts.

### 2. `frappe.db.set_value` em vez de `doc.save()` nos hooks
Documento submetido (`docstatus=1`) não aceita `doc.save()` em campos calculados — dá `UpdateAfterSubmitError`. A solução é gravar direto no banco via `set_value(..., update_modified=False)`.

### 3. `allow_on_submit: 1` nos campos calculados
13 campos relevantes (em FPB e PR) marcados com `allow_on_submit=1` para permitir atualização programática após submit.

### 4. RestrictedPython quirks
O sandbox de Server Script proíbe:
- Operadores in-place (`+=`, `-=`) → trocados por `x = x + y`
- Variáveis com `_` no início (`_digits`) → renomeadas para `only_digits`
- Algumas chamadas a `str.format()` → trocadas por concatenação `"..." + str(x)` em scripts onde dá problema

Detalhes e armadilhas em [`08-troubleshooting.md`](08-troubleshooting.md).

### 5. Eventos `After Submit`/`After Cancel` em vez de `On Submit`/`On Cancel`
O Frappe internamente usa `After Submit`/`After Cancel`; a UI em PT-BR traduz para "Após o envio" mas o valor armazenado é em inglês.

### 6. Schema do Sales Order Patient
Child table com `fetch_from` para puxar nome/CPF/mobile do Patient. Os fetches só rodam no client; ao gravar via API REST, é preciso passar os valores ou o servidor preenche no Before Save.

### 7. Prefixo `fp_` nos custom fields
Evita colisão com campos nativos do ERPNext (especialmente `Sales Order Item.reserved_qty` do Stock Reservation Entry).

## Mapa de arquivos

```
erpnext-future-production-setup/
├── README.md                      overview + quickstart
├── docs/                          ← documentação completa (este diretório)
├── .env.example                   template de variáveis
├── .gitignore
├── requirements.txt               requests, python-dotenv
│
├── setup_all.py                   orquestrador (6 passos)
├── setup_01_structure.py          FPB + PR + Custom Fields no SO Item
├── setup_02_client_scripts.py     3 Client Scripts
├── setup_03_server_scripts.py     11 Server Scripts
├── setup_04_reports.py            4 Reports
├── setup_05_workspace.py          Workspace
├── setup_06_patients.py           Patient + Sales Order Patient + 2 validações
│
├── test_scenario.py               cenário Fluxo A + B (parametrizável)
├── test_scenario_patients.py      cenário com pacientes
│
├── lib/
│   ├── __init__.py
│   ├── erpnext_api.py             cliente HTTP com idempotência
│   ├── payloads.py                FPB, PR, custom fields do SO Item
│   └── payloads_patients.py       Patient, Sales Order Patient, custom fields do SO
│
└── tools/                         scripts de diagnóstico/manutenção
    ├── diagnose.py                snapshot do ambiente
    ├── fix_fpb_schema.py          recria FPB se schema veio vazio
    ├── inspect_fpb.py             dump dos campos do FPB
    ├── inspect_master.py          lista Customer Group, Territory, Price List
    ├── inspect_healthcare.py      checa se ERPNext Healthcare está instalado
    └── recreate_doctypes.py       limpa dados de teste e recria DocTypes
```
