# Catálogo — produtos + lotes futuros (Unikka Pharma) — 2026-06-11

> Criados na instância **`erp.service.unikkapharma.com.br`** (Company
> **Unikka Pharma** / UP). SKU uppercase = código do item. Lotes do print de
> produção como **estoque futuro (FPB)**. Validades ficam aqui — o FPB **não
> tem campo de validade**; vão no **Batch físico** quando produzir manual.
>
> ⚠ Os mesmos itens/lotes foram criados por engano antes no `injemedpharma`
> e **removidos de lá** (instância errada).

## Instância

| | |
|---|---|
| URL | https://erp.service.unikkapharma.com.br |
| Company | Unikka Pharma (abbr UP) |
| Warehouse acabado | Produtos Acabados - UP |
| Price List | Venda Padrão |

## Produtos (ERPNext Items)

| item_code (SKU) | Nome | Preço (Venda Padrão) | has_batch_no |
|---|---|---|---|
| `OT10000029` | Tirzepatida 60mg/2,4ml | R$ 1.965,41 | sim |
| `OT10000052` | Tirzepatida 90mg/3,6ml | R$ 2.328,21 | sim |

## Lotes futuros (FPB — Aberta para Reserva, consumíveis por pedido)

| FPB | item_code | Lote (production_code) | Qtd planejada | Validade (p/ Batch físico) |
|---|---|---|---|---|
| `FPB-2026-00001` | OT10000029 | `14746` | 2674 | 20/02/2027 |
| `FPB-2026-00002` | OT10000029 | `14749` | 2555 | 10/03/2027 |
| `FPB-2026-00003` | OT10000052 | `14747` | 1851 | 07/03/2027 |
| `FPB-2026-00004` | OT10000052 | `14748` | 1300 | 09/03/2027 |
| `FPB-2026-00005` | OT10000052 | `14750` | 2564 | 10/03/2027 |
| `FPB-2026-00006` | OT10000052 | `TZ90260001` | 2743 | 17/03/2027 |
| | | **Total** | **13687** | (bate com o print) |

`planned_production_date` = 2026-06-11. Status `Aberta para Reserva`.

> **Você sobe o Batch físico manualmente** com a validade acima.

## Estado das customizações no unikkapharma

| Setup | O que | Estado |
|---|---|---|
| `setup_01` | DocTypes FPB + Production Reservation + Custom Fields SO Item | ✅ aplicado |
| `setup_02..18` | client scripts, reports, workspace, patient, prescriber, dispensação, naming, receita | ⏳ pendente |
| `setup_03/13/14/19-23` | **server scripts** (validações, hooks FPB, endpoints, financeiro) | 🔴 BLOQUEADO |

### 🔴 Bloqueio: Server Scripts desabilitados

A instância está com **Server Scripts OFF**. Sem isso não dá pra instalar os
hooks/endpoints (status automático do FPB, reservar/cancelar/trocar, create_order,
financeiro). Habilitar no **servidor** (não dá via API):

```bash
bench --site <site-unikka> set-config server_script_enabled 1
bench --site <site-unikka> clear-cache
```

Depois disso, a suíte completa entra idempotente:
```bash
python setup/setup_all.py          # 01..18
python setup/setup_19_step_endpoints.py
python setup/setup_20_financial_config.py
python setup/setup_21_payment_entry.py
python setup/setup_22_reservation_ops.py
python setup/setup_23_external_api.py
```

> Os FPB já criados continuam válidos; os hooks só passam a recalcular saldo
> automático ao reservar. Endpoints (`create_order`, etc.) default usam company
> "Injemedpharma" / "Produtos Acabados - I" — passar `company`/`warehouse`
> explícito p/ Unikka Pharma OU parametrizar os defaults (follow-up).

## `.env`

Apontado pro unikkapharma (creds Unikka). Injemed comentado — trocar de volta
pra retomar o fluxo manual do SO 00138 lá.
