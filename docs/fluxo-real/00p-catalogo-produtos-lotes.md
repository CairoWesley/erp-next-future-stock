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

**Suíte COMPLETA instalada** (toda a setup_01..23), porém os Server Scripts
estão **dormentes** — instalados como doc, mas só EXECUTAM após habilitar a flag.

```
9 DocTypes (FPB, Production Reservation, Patient, Prescriber, Dispensacao,
            Dispensacao Paciente, Sales Order Patient, Prescriber Council,
            Injemed Financial Settings)
37 Server Scripts = 28 endpoints (future_production_*) + 9 hooks
   (FPB Validate/Update Status, PR Validate/On Submit/On Cancel,
    Patient/Prescriber/SO validations)
6 Client Scripts (botões UI: FPB, PR, Dispensação, Reserva Ops, etc.)
+ Custom Fields (SO Item, Sales Order Patient, Financial Settings),
  Property Setters (form layout), naming, reports, workspace.
```

### 🟡 Último passo: habilitar Server Scripts (1 comando, no servidor)

Os scripts existem mas **não rodam** até ligar a flag (igual fez no injemed):

```bash
bench --site <site-unikka> set-config server_script_enabled 1
bench --site <site-unikka> clear-cache
```

Depois disso, **tudo fica live sem re-aplicar nada** (reservar/cancelar/trocar,
create_order, financeiro, status automático do FPB, dispensação, ZPL).

> **Follow-up:** endpoints default usam company "Injemedpharma" /
> "Produtos Acabados - I". No unikkapharma, passar `company`="Unikka Pharma" +
> `warehouse`="Produtos Acabados - UP" explícito nas chamadas, OU parametrizar
> os defaults dos scripts (ler de Injemed Financial Settings).

## `.env`

Apontado pro unikkapharma (creds Unikka). Injemed comentado — trocar de volta
pra retomar o fluxo manual do SO 00138 lá.
