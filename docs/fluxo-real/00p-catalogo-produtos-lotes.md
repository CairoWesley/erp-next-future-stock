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

### ✅ Server Scripts LIVE (resolvido) — gotcha frappe_docker swarm

Tudo funcionando: `create_order` consumiu estoque futuro (SO 00002, reserva
00003, FPB-2026-00001 2674→2669), `auto_reserve` FIFO pegou o lote sozinho.

**O pulo do gato (custou várias tentativas):** num deploy **frappe_docker
(Docker Swarm)**, pôr `server_script_enabled: 1` só no **site_config.json**
NÃO bastou — o `bench console` lia `1`, mas o **gunicorn** continuava
`ServerScriptNotEnabled`. Resolveu colocando o flag no **`common_site_config.json`
(global)**:

```bash
# 1. flag no config GLOBAL (volume erpnext_sites, raiz _data)
nano /var/lib/docker/volumes/erpnext_sites/_data/common_site_config.json
#    adiciona dentro do { }:   "server_script_enabled": 1,

# 2. recria o backend no swarm (NÃO basta bench restart dentro do container)
docker service update --force erpnext_erpnext_backend
```

Aprendizados:
- Em Swarm, **`bench restart`/`supervisorctl` dentro do container não fazem nada** —
  quem reinicia o gunicorn é `docker service update --force <service>` no host.
- O site_config fica no **volume** `erpnext_sites` (`/var/lib/docker/volumes/
  erpnext_sites/_data/<site>/site_config.json`); editar no host = editar o que o
  container lê.
- Diagnóstico decisivo: `docker exec <backend> bench --site <site> console` →
  `frappe.conf.get("server_script_enabled")`; e POST direto em `localhost:8000`
  de dentro do backend (pula Traefik/nginx) pra isolar proxy × gunicorn.

> **Follow-up:** endpoints default usam company "Injemedpharma" /
> "Produtos Acabados - I". No unikkapharma, passar `company`="Unikka Pharma" +
> `warehouse`="Produtos Acabados - UP" explícito nas chamadas, OU parametrizar
> os defaults dos scripts (ler de Injemed Financial Settings).

## `.env`

Apontado pro unikkapharma (creds Unikka). Injemed comentado — trocar de volta
pra retomar o fluxo manual do SO 00138 lá.
