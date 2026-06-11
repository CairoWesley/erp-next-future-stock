# Catálogo — produtos + lotes futuros (Injemed) — 2026-06-11

> Itens criados com **SKU uppercase** (= código HubSpot) e os **lotes futuros
> (FPB)** do print de produção. As validades ficam aqui porque o FPB **não tem
> campo de validade** — vão no **Batch físico** quando produzir manualmente.

## Produtos (ERPNext Items)

| item_code (SKU) | Nome | Preço (Venda Padrão) | has_batch_no |
|---|---|---|---|
| `OT10000029` | Tirzepatida 60mg/2,4ml | R$ 1.965,41 | sim |
| `OT10000052` | Tirzepatida 90mg/3,6ml | R$ 2.328,21 | sim |

> Já existiam equivalentes com outro código: `TIR00060` (=60mg/2,4ml) e
> `00049` (=90mg/3,6mL). Os novos `OT*` são os canônicos (alinhados ao SKU
> HubSpot). Decidir depois se deprecam os antigos.

## Lotes futuros (FPB — Aberta para Reserva, consumíveis por pedido)

| FPB | item_code | Lote (production_code) | Qtd planejada | Validade (p/ Batch físico) |
|---|---|---|---|---|
| `00164` | OT10000029 | `14746` | 2674 | 20/02/2027 |
| `00165` | OT10000029 | `14749` | 2555 | 10/03/2027 |
| `00166` | OT10000052 | `14747` | 1851 | 07/03/2027 |
| `00167` | OT10000052 | `14748` | 1300 | 09/03/2027 |
| `00168` | OT10000052 | `14750` | 2564 | 10/03/2027 |
| `00169` | OT10000052 | `TZ90260001` | 2743 | 17/03/2027 |
| | | **Total** | **13687** | (bate com o print) |

`planned_production_date` = 2026-06-11 (criados hoje como estoque futuro).
Status `Aberta para Reserva` → pedido consome via `create_order` / botão
"Reservar em Produção Futura" (ver [00o](00o-api-externa-pedido.md)).

> **Você sobe o Batch físico manualmente** com a validade acima. O FPB é só o
> estoque futuro reservável; o Batch (lote físico) carrega a validade real.

## ⚠ Pendências / flags desta carga

1. **Creds novas falharam auth** (`332ac451...` / `481311615...`) em
   erp.injemedpharma — segui com as creds do `.env` (funcionando). Se forem de
   **outra instância**, manda a URL.
2. **HubSpot não tocado**: o MCP conectado é o portal **49715898** (conta de
   teste, só "teset"/"TESTE"), **não** o Injemed (`51388090`). Sem
   `HUBSPOT_ACCESS_TOKEN` no `.env`. Pra criar/uppercase o SKU no HubSpot
   Injemed: subir o token OU conectar a conta certa no MCP.
3. **`Stock Settings.item_naming_by` mudou** `Naming Series` → `Item Code`
   (necessário pra forçar `OT...` como código). Novos itens agora usam o
   `item_code` informado (não a série `00001`). Reverter se quebrar outro fluxo.
4. Itens duplicados (TIR00060 / 00049) — ver acima.
