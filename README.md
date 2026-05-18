# erp-next-future-stock

Módulo para **ERPNext** que adiciona controle de **Reserva de Produção Futura**
e **Lote × Pacientes**. Implantado 100% via API REST, sem precisar entrar
no container Docker e sem criar app customizado.

## O problema

A empresa fabrica ampolas em lotes coletivos (ex: 2.000 ampolas) que serão
divididas entre vários pedidos/clientes. Sem este módulo, é comum:

- Vender acima da capacidade planejada
- Reservar a mesma quantidade para mais de um cliente
- Não saber quais pedidos esperam determinada produção
- Não conseguir liberar parcialmente quando a produção real é menor
- Misturar estoque real com promessa de produção futura
- Perder rastreabilidade pedido → lote físico → paciente

## A solução

```
Future Production Batch  (planejado, ainda não fabricado)
       │
       │ N reservas
       ▼
Production Reservation  (Sales Order ↔ FPB)
       │
       ▼
Sales Order (com tabela fp_patients)
       │
       ▼
Patient (cadastro + CPF, endereço, contato)
```

## Recursos

- ✅ 2 DocTypes (Future Production Batch, Production Reservation) com workflow automático
- ✅ Lote × Pacientes — Patient + child table em Sales Order
- ✅ 6 endpoints REST customizados (reservar, auto-reservar, recalcular, criar WO, liberar, replanejar)
- ✅ 7 Server Scripts de validação e regras de negócio
- ✅ 4 Reports + Workspace "Produção Futura"
- ✅ Setup 100% idempotente via API (sem mexer no container Docker)
- ✅ Testes ponta a ponta com 4 cenários de produção (igual, sub-leve, sub-grave, sobre)

## Quickstart

```bash
git clone https://github.com/CairoWesley/erp-next-future-stock.git
cd erp-next-future-stock/erpnext-future-production-setup

python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # Linux/Mac

pip install -r requirements.txt
cp .env.example .env             # editar com URL + API key/secret
python setup_all.py
```

Pré-requisito crítico no servidor: `bench --site <site> set-config -g server_script_enabled 1 && bench restart`.
Veja [`docs/03-installation.md`](docs/03-installation.md) para a lista completa.

## Documentação

| Arquivo | O que tem |
|---|---|
| [`docs/01-overview.md`](docs/01-overview.md) | Problema, solução, escopo, papéis |
| [`docs/02-architecture.md`](docs/02-architecture.md) | DocTypes, Server Scripts, endpoints, decisões técnicas |
| [`docs/03-installation.md`](docs/03-installation.md) | Pré-requisitos, .env, setup_all, idempotência |
| [`docs/04-usage-flows.md`](docs/04-usage-flows.md) | Fluxos A (pedido + reserva) e B (efetivar lote) UI + API |
| [`docs/05-api-reference.md`](docs/05-api-reference.md) | Todos os endpoints com payload, response, curl |
| [`docs/06-data-model.md`](docs/06-data-model.md) | Schema completo dos 4 DocTypes |
| [`docs/07-business-rules.md`](docs/07-business-rules.md) | RB-001..RB-010 + onde cada uma é validada |
| [`docs/08-troubleshooting.md`](docs/08-troubleshooting.md) | Erros conhecidos e soluções (12 cases) |
| [`docs/09-testing.md`](docs/09-testing.md) | test_scenario.py com 4 cenários parametrizados |
| [`docs/10-changelog.md`](docs/10-changelog.md) | Histórico de versões |

## Estrutura

```
.
├── docs/                          ← documentação completa (10 arquivos)
├── lib/
│   ├── erpnext_api.py             cliente HTTP idempotente
│   ├── payloads.py                schemas dos DocTypes principais
│   └── payloads_patients.py       schemas do módulo de pacientes
├── setup_all.py                   orquestrador (6 passos)
├── setup_01_structure.py          DocTypes principais + Custom Fields
├── setup_02_client_scripts.py     UI / botões
├── setup_03_server_scripts.py     validações + endpoints API
├── setup_04_reports.py            relatórios
├── setup_05_workspace.py          menu lateral
├── setup_06_patients.py           módulo Lote × Pacientes
├── test_scenario.py               cenário Fluxo A + B (parametrizável)
├── test_scenario_patients.py      cenário com pacientes
├── tools/                         scripts de diagnóstico/manutenção
└── .env.example
```

## Stack

- Python 3.9+
- `requests`, `python-dotenv` (apenas essas duas dependências)
- ERPNext 14+ com `server_script_enabled` ativado

## Licença

Privado — uso interno da empresa.

## Versão atual

`0.1.0` — implementação inicial completa, validada contra `https://erp.injemedpharma.com.br`.
Ver [`docs/10-changelog.md`](docs/10-changelog.md).
