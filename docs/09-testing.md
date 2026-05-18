# 09 — Testes

Dois scripts cobrem cenários ponta a ponta. Ambos rodam contra o ERPNext real
configurado no `.env`. Idempotentes: limpam dados de teste antes (somente os
de teste, por prefixo `TEST-PF-*`, `TEST-PT-*`).

## `test_scenario.py` — Fluxo A + B com FIFO

Reproduz o cenário de aceite da seção 23 da documentação original.

### Uso
```bash
python test_scenario.py                       # padrão: produced=1850
python test_scenario.py --produced-qty 2000   # produção igual ao planejado
python test_scenario.py --produced-qty 1500   # subprodução grave
python test_scenario.py --produced-qty 2100   # sobreprodução
python test_scenario.py --no-cleanup          # não apaga dados anteriores
```

### O que faz

1. **Pré-check**: confirma `server_script_enabled = True`
2. **Cleanup**: cancela e apaga PRs/FPBs/SOs do teste anterior
3. **Customers**: cria/reutiliza 4 customers (`TEST-PF-Alfa..Delta`)
4. **FPB**: cria 1 Future Production Batch de 2.000 unid + submete
5. **Sales Orders**: cria 4 SOs com qty 300/500/700/500 + submete cada
6. **Reservas**: chama `future_production_reserve_sales_order_item` para cada SO
7. **Batch + produção**: cria Batch físico, atualiza FPB com `produced_qty` e `batch_no`
8. **Liberação**: chama `future_production_release_batch`
9. **Análise**: compara estado obtido com expected (FPB e cada PR)

### Saída esperada (produced=1850)

```
========================================================================
  Análise — esperado vs obtido
========================================================================

  Future Production Batch: FPB-2026-00002
  Status: Liberada Parcialmente
  Campo                        Esperado       Obtido   OK
  ------------------------------------------------------------
  planned_qty                      2000       2000.0   OK
  reserved_qty                     2000       2000.0   OK
  available_qty                       0          0.0   OK
  produced_qty                   1850.0       1850.0   OK
  released_qty                   1850.0       1850.0   OK
  pending_release_qty               0.0          0.0   OK

  Production Reservations
  Pedido                 Cli           Reserv  Liber  Pend Status                OK
  -----------------------------------------------------------------------------------
  SAL-ORD-2026-00014     TEST-PF-Al       300    300     0 Liberado              OK
  SAL-ORD-2026-00015     TEST-PF-Be       500    500     0 Liberado              OK
  SAL-ORD-2026-00016     TEST-PF-Ga       700    700     0 Liberado              OK
  SAL-ORD-2026-00017     TEST-PF-De       500    350   150 Parcialmente Liberado OK

[OK] CENÁRIO APROVADO — todos os critérios da seção 23 foram atendidos.
```

### Resultados dos 4 cenários

#### A — `produced=2000` (igual ao planejado)
`FPB.status = "Liberada Totalmente"`. Todos os 4 pedidos: Liberado, 0 pendente.

#### B — `produced=1850` (subprodução leve, padrão da seção 23)
`FPB.status = "Liberada Parcialmente"`. SO-Delta com 150 pendentes.

#### C — `produced=1500` (subprodução grave)
`FPB.status = "Liberada Parcialmente"`. Alfa/Beta/Gama 100% liberados (1500 = 300+500+700), Delta = 0 liberado, 500 pendente, status "Reservado".

#### D — `produced=2100` (sobreprodução)
`FPB.status = "Liberada Parcialmente"`. Todos os 4 pedidos liberados. `pending_release_qty=100` (sobra sem reserva — vira saldo livre).

## `test_scenario_patients.py` — Módulo Lote × Pacientes

Valida o vínculo paciente → SO → FPB.

### Uso
```bash
python test_scenario_patients.py
```

### O que faz

1. **Cleanup**: PRs/SOs/FPBs/Patients anteriores do teste
2. **Customer (médico)**: reutiliza `TEST-PF-Alfa`
3. **Pacientes**: cria 4 Patients com CPFs válidos
4. **FPB**: 2.000 unid de `TIR00060`
5. **Sales Order com `fp_patients`**: 1 item (10 ampolas), 4 pacientes (3+2+4+1=10)
6. **Reserva**: 10 unid no FPB via API
7. **Validações negativas**:
   - **A.** Tentar criar SO com soma errada (99 ≠ 10) → deve falhar
   - **B.** Tentar criar Patient com CPF inválido (5 dígitos) → deve falhar

### Saída esperada (resumo)

```
[OK] Patient criado: PAC-2026-00010 (Maria Aparecida Silva, cpf=11144477735)
... (4 patients)

[OK] FPB criada e submetida: FPB-2026-00003

[OK] SO criado e submetido: SAL-ORD-2026-00030 (item row=..., qty=10)
[OK]   Pacientes na tabela:
[OK]     - Maria Aparecida Silva (11144477735) -> 3.0 ampolas
[OK]     - João Pedro Oliveira (22255588849) -> 2.0 ampolas
[OK]     - Ana Carolina Santos (33366699953) -> 4.0 ampolas
[OK]     - Carlos Eduardo Souza (44477700067) -> 1.0 ampolas

[OK] Reserva criada: PR=PR-2026-00026, available restante=1990.0

[OK] A) Tentar criar SO com soma errada (deve FALHAR)
[OK]    BLOQUEADO corretamente: ValidationError: Item TIR00060: qty do
       pedido (10.0) diferente da soma das ampolas dos pacientes (99.0).

[OK] B) Tentar criar Patient com CPF inválido (deve FALHAR)
[OK]    BLOQUEADO corretamente: ValidationError: CPF precisa ter 11
       digitos. Recebido: 12345
```

## Helpers do diretório `tools/`

Scripts de inspeção e manutenção. Não são testes automatizados, mas são úteis durante depuração.

| Script | Função |
|---|---|
| `diagnose.py` | Snapshot do ambiente (Companies, Warehouses, Items, SOs, FPBs, PRs, Server Scripts) |
| `inspect_fpb.py` | Dump dos campos do DocType Future Production Batch |
| `inspect_master.py` | Lista Customer Groups, Territories, Price Lists (descobrir nomes PT-BR) |
| `inspect_healthcare.py` | Checa se o módulo Healthcare nativo do ERPNext está instalado |
| `fix_fpb_schema.py` | Apaga e recria FPB se o DocType existir com schema incompleto |
| `recreate_doctypes.py` | Cancela e apaga TODOS os FPBs/PRs e recria os DocTypes do zero |

> `recreate_doctypes.py` é destrutivo — use só em homologação ou quando trocar de versão de schema.

## Limpeza completa

Para zerar tudo do módulo (mantém Customers, Items, Warehouses):

```bash
python tools/recreate_doctypes.py     # apaga FPBs, PRs e os 2 DocTypes
python setup_all.py                   # recria do zero
```

## Workflow recomendado em CI/CD

```bash
# 1. Validar conexão
python -c "from lib.erpnext_api import client_from_env; client_from_env().server_script_enabled() or exit(1)"

# 2. Deploy idempotente
python setup_all.py

# 3. Smoke test (sem cleanup, evita interferir com prod)
python test_scenario.py --produced-qty 2000 --no-cleanup
```

## Não há testes unitários (ainda)

O projeto não tem `pytest`/`unittest` para a `lib/erpnext_api.py` porque o sistema-alvo é o ERPNext remoto e o valor de teste vem dos cenários ponta a ponta. Se o módulo crescer, considerar adicionar:

- `test_payloads.py` — verificar que cada payload de DocType passa por `json.dumps` (catch typos)
- `test_erpnext_client_mock.py` — mockar `requests.Session` e validar URL/headers/body
