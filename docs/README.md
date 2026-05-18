# Documentação — `erp-next-future-stock`

Módulo de **Reserva de Produção Futura** + **Lote × Pacientes** para o ERPNext,
implantado 100% via API REST.

## Índice

| Arquivo | Quando ler |
|---|---|
| [`00-original-spec.md`](00-original-spec.md)    | Especificação inicial completa do projeto (referência histórica). |
| [`01-overview.md`](01-overview.md)              | Antes de tudo. Problema, solução, escopo. |
| [`02-architecture.md`](02-architecture.md)      | Para entender as peças: DocTypes, scripts, endpoints. |
| [`03-installation.md`](03-installation.md)      | Para instalar em um novo ambiente ERPNext. |
| [`04-usage-flows.md`](04-usage-flows.md)        | Para operar: criar pedido com reserva e efetivar lote. |
| [`05-api-reference.md`](05-api-reference.md)    | Para integrar (CRM externo, scripts). Endpoints + payloads. |
| [`06-data-model.md`](06-data-model.md)          | Schema completo dos DocTypes (FPB, PR, Patient, Sales Order Patient). |
| [`07-business-rules.md`](07-business-rules.md)  | Regras RB-001..RB-010 e onde cada uma é validada. |
| [`08-troubleshooting.md`](08-troubleshooting.md)| Erros conhecidos e soluções (server_script_enabled, etc.). |
| [`09-testing.md`](09-testing.md)                | Como rodar `test_scenario.py` e variações. |
| [`10-changelog.md`](10-changelog.md)            | Histórico de versões. |
| [`11-manual-operacional.md`](11-manual-operacional.md) | Manual visual de uso humano dentro do ERPNext (clique a clique). |
| [`12-smoke-test-grande.md`](12-smoke-test-grande.md) | Smoke test de volume realista (10 FPBs × 2k ampolas, 22 SOs, 30 patients). |
| [`13-status-e-roadmap.md`](13-status-e-roadmap.md) | Estado atual completo + tudo que aguarda aprovação/credenciais + sprints sugeridos. |

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

Veja [`03-installation.md`](03-installation.md) para pré-requisitos completos
(incl. habilitar `server_script_enabled` no bench).
