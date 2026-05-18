# 12 — Smoke Test Grande (Volume Realista)

Teste de carga em fases para validar o sistema com **20.000 ampolas
planejadas** em 10 FPBs, simulando um mês real de operação.

## Cenário simulado

| Métrica | Valor |
|---|---|
| FPBs | 10 × 2.000 = 20.000 ampolas |
| Customers | 5 (PJ) |
| Prescribers | 6 (3 CRM + 1 CRO + 1 CRF + 1 CRBM) |
| Patients | 30 |
| Sales Orders | 22 (~15.000 reservadas) |
| Produção | 3 FPBs full (2000) + 7 FPBs parciais (1000-1800) |
| Liberação | FIFO automático |

## Estrutura

```
smoke_test_large.py         # orquestrador em fases
lib/visibility.py           # helpers de inspeção (FPB/PR/SO tables)
.smoke_state.json           # estado entre fases (gerado, não commitado)
```

## Como rodar

```bash
source .venv/bin/activate

# Fase a fase (recomendado pra validar cada etapa)
python smoke_test_large.py --phase setup     # 1. Customers, Prescribers, Patients
python smoke_test_large.py --phase fpbs      # 2. Criar 10 FPBs
python smoke_test_large.py --phase orders    # 3. SOs + reservas auto FIFO
python smoke_test_large.py --phase produce   # 4. Produção real (3 full + 7 parcial)
python smoke_test_large.py --phase release   # 5. Liberar FIFO
python smoke_test_large.py --phase report    # 6. Relatório consolidado

# Tudo de uma vez
python smoke_test_large.py --phase all

# Limpar tudo (remove TEST-LRG-*)
python smoke_test_large.py --phase cleanup
```

## Resultado esperado por fase

### Phase 1 — Setup
- 5 Customers `TEST-LRG-Cliente-{Alfa,Beta,Gama,Delta,Epsilon}` criados
- 6 Prescribers criados (códigos `PRES-2026-NNNNN`)
- 30 Patients criados (códigos `PAC-2026-NNNNN`)

### Phase 2 — FPBs
Após executar, **todos** os 10 FPBs:
- Status: **Aberta para Reserva**
- Submetidos (docstatus=1)
- Datas de produção espaçadas (a cada 3 dias)

| Inspeção | Como |
|---|---|
| API | `GET /api/resource/Future Production Batch?filters=[["production_code","like","TEST-LRG-%"]]` |
| UI Lista | `https://erp.injemedpharma.com.br/app/future-production-batch` |
| UI Workspace | `https://erp.injemedpharma.com.br/app/producao-futura` |

**Estado esperado**: planned=20000, reserved=0, available=20000

### Phase 3 — Orders
22 SOs criados (status "To Deliver and Bill"). FIFO consome do mais antigo primeiro.

**Estado esperado** (depende do seed):
- FPBs 1-6: 100% reservados (Totalmente Reservada)
- FPB 7: parcial (~50%)
- FPBs 8-10: 0% reservados (futuros)
- Total reservado: ~13.010 ampolas

| Inspeção | Como |
|---|---|
| API SOs | `GET /api/resource/Sales Order?filters=[["customer","like","TEST-LRG-%"]]` |
| API PRs | `GET /api/resource/Production Reservation?filters=[["future_production_batch","in",[FPB names]]]` |
| UI SO | `https://erp.injemedpharma.com.br/app/sales-order/SAL-ORD-2026-XXXXX` |

### Phase 4 — Produce
- 3 primeiros FPBs (1-3): `produced_qty = 2000` (full)
- 7 restantes: produced entre 1000-1800 (aleatório seed=42+11)
- Cada FPB ganha um `batch_no` (Batch físico real criado)

**Status esperado**:
- FPBs 1-6: "Totalmente Reservada" (produzidos mas ainda não liberados)
- FPB 7: "Reservada Parcialmente"
- FPBs 8-10: "Aberta para Reserva"

> ⚠ Note: status não muda para "Produzida Parcial/Total" até a fase **release**.

### Phase 5 — Release
FIFO distribui produção entre PRs por prioridade + reservation_date.

**Estado final esperado**:

| FPB | Plan | Reserv | Prod | Liber | Pend | Status |
|---|---|---|---|---|---|---|
| 1 | 2000 | 2000 | 2000 | 2000 | 0 | Liberada Totalmente |
| 2 | 2000 | 2000 | 2000 | 2000 | 0 | Liberada Totalmente |
| 3 | 2000 | 2000 | 2000 | 2000 | 0 | Liberada Totalmente |
| 4 | 2000 | 2000 | 1631 | 1631 | 0 | Liberada Parcialmente |
| 5 | 2000 | 2000 | 1221 | 1221 | 0 | Liberada Parcialmente |
| 6 | 2000 | 2000 | 1467 | 1467 | 0 | Liberada Parcialmente |
| 7 | 2000 | 1010 | 1514 | 1010 | 504 | Liberada Parcialmente |
| 8 | 2000 | 0 | 1728 | 0 | 1728 | Produzida Parcialmente |
| 9 | 2000 | 0 | 1494 | 0 | 1494 | Produzida Parcialmente |
| 10 | 2000 | 0 | 1735 | 0 | 1735 | Produzida Parcialmente |

**Totais**: reserved=13010, produced=16790, released=11329, pending=5461.

### Phase 6 — Report
Imprime tabela final consolidada + pendências.

**Análise das pendências (1681 ampolas em PRs)**:
- 5 PRs com `pending_qty > 0`
- Algumas reservas dividiram entre 2 FPBs (auto-reserve)
- Quando o FPB destino produziu menos que o reservado → sobra na PR

> Diferença: FPB pending (5461) = produced - released, inclui produção
> SEM reserva (ex: FPBs 8-10 que ninguém reservou). PR pending (1681) =
> reserved - released, só conta reservas com saldo a entregar.

## Visibilidade em qualquer momento

### Via API (snapshot completo)

```bash
# Todos FPBs do teste
curl -X GET \
  "https://erp.injemedpharma.com.br/api/resource/Future Production Batch" \
  --data-urlencode 'fields=["name","production_code","planned_qty","reserved_qty","available_qty","produced_qty","released_qty","pending_release_qty","status"]' \
  --data-urlencode 'filters=[["production_code","like","TEST-LRG-%"]]' \
  --data-urlencode 'order_by=planned_production_date asc' \
  -H "Authorization: token API_KEY:API_SECRET" \
  -G

# Todas reservas pendentes (não só do teste)
curl -X GET \
  "https://erp.injemedpharma.com.br/api/resource/Production Reservation" \
  --data-urlencode 'filters=[["docstatus","=",1],["pending_qty",">",0]]' \
  --data-urlencode 'fields=["name","sales_order","future_production_batch","pending_qty","customer"]' \
  -H "Authorization: token API_KEY:API_SECRET" \
  -G
```

### Via UI (interface humana)

| O que ver | URL |
|---|---|
| Lista de FPBs | `/app/future-production-batch` |
| Workspace Produção Futura | `/app/producao-futura` |
| Lista de Reservas | `/app/production-reservation` |
| Lista de Sales Orders | `/app/sales-order` |
| Report Saldo por Lote | `/app/query-report/Saldo%20por%20Lote` |
| Report Pendências | `/app/query-report/Pedidos%20Pendentes%20de%20Liberação` |
| Stock Balance (item) | `/app/stock-balance` (filtro item=TIR00060) |

### Via Python (script ad-hoc)

```python
from lib.erpnext_api import client_from_env
from lib.visibility import list_fpbs, print_fpb_table

client = client_from_env()
fpbs = list_fpbs(client, item_code="TIR00060", code_prefix="TEST-LRG")
print_fpb_table(fpbs)
```

## Cleanup

```bash
python smoke_test_large.py --phase cleanup
```

Remove em ordem:
1. PRs (cancela + apaga)
2. SOs (cancela + apaga)
3. FPBs (cancela + apaga)
4. Batches físicos
5. Patients
6. Prescribers
7. Customers
8. `.smoke_state.json`

## Análise crítica do que o teste valida

| Cenário coberto | Onde aparece |
|---|---|
| FIFO ordena FPBs por data | Phase 3: FPBs 1-6 cheios antes do 7 |
| Auto-reserve divide entre FPBs | Phase 3: vários SOs com 2 reservas |
| Produção parcial registra batch | Phase 4: batch criado com qty real |
| Release FIFO por prioridade | Phase 5: PRs com priority=100 distribuídas em ordem |
| Pending qty calculado | Phase 5: PR-052 com pending=369 (correto) |
| Status FPB evolui automaticamente | Phase 5: vários status diferentes |
| Prescriber por linha funciona | Phase 3: fp_patients com prescriber por linha |

## Cenários NÃO cobertos (próximos testes)

- Cassação de Prescriber durante o teste
- Replanejamento de pendência via `future_production_replan_pending_qty`
- Cancelamento de SO com reservas ativas
- Stock Entry Manufacture (entrada física no Bin)
- Pick List + Delivery Note + Sales Invoice (fluxo de saída completo)
