# 07 — Regras de Negócio

As regras estão numeradas conforme a documentação original
(`documentacao_erpnext_reserva_producao_futura_api_v2.md`, seção 13).

Cada regra é implementada em **pelo menos um** Server Script — quem garante o
cumprimento é o servidor, não a UI, para que valha tanto via UI quanto via API.

---

## RB-001 — Produção futura não é estoque

> A produção futura não deve ser usada como estoque disponível. Ela é
> promessa operacional.

**Implementação**:
- `Future Production Batch` é um DocType **independente** de Stock Ledger / Bin
- Não é Item nem cria movimentação de estoque
- Stock Entry / Pick List / Delivery Note continuam usando o Item + Batch nativos do ERPNext
- Apenas o **Batch físico** (campo `batch_no`) liga FPB ao estoque real, e só depois da produção

---

## RB-002 — Pedido precisa estar apto para reserva

> Critérios mínimos:
> ```
> Sales Order existe
> Sales Order contém o item
> Quantidade > 0
> Pedido está aprovado/pago
> ```

**Implementação**:
- Server Script `PR - Validate (Before Save)`:
  - `frappe.db.get_value("Sales Order", doc.sales_order, ...)` falha se SO não existe
  - Bloqueia se `docstatus != 1` (apenas SO **submetido** vale)
- Endpoint `future_production_reserve_sales_order_item` faz check explícito de `docstatus`

> A documentação fala em "pago" — hoje validamos apenas `docstatus=1`
> (submetido). Para amarrar a status financeiro real (Payment Entry concluído),
> precisa estender o Server Script com query em `Payment Entry Reference`.

---

## RB-003 — Item da reserva deve ser igual ao item da produção

```
Production Reservation.item_code = Future Production Batch.item_code
```

**Implementação**:
- Server Script `PR - Validate (Before Save)`: compara `doc.item_code` com `fpb.item_code`. Se diferente, `frappe.throw`.
- Endpoint `future_production_reserve_sales_order_item`: faz a mesma comparação antes de criar a PR.

---

## RB-004 — Não reservar acima do saldo

```
reserved_qty + nova_reserva <= planned_qty
```

**Implementação**:
- Server Script `PR - Validate (Before Save)`:
  ```python
  new_total = current_reserved + float(doc.reserved_qty)
  ceiling = planned + (overbooking_limit if allow_overbooking else 0)
  if new_total > ceiling:
      frappe.throw("Saldo insuficiente. Disponível: X, solicitado: Y.")
  ```
- Em update da PR (edição da `reserved_qty` já submetida), considera-se o valor antigo: `current_reserved = current_reserved - old_qty`

---

## RB-005 — Overbooking exige permissão explícita

```
Se allow_overbooking = 1:
  reserved_qty + nova_reserva <= planned_qty + overbooking_limit_qty
```

**Implementação**: mesma do RB-004 — o `ceiling` inclui `overbooking_limit_qty` apenas quando `allow_overbooking=1`.

**Configuração**: no FPB, marcar checkbox *Permitir Reserva Acima do Planejado* e preencher *Limite de Overbooking*.

---

## RB-006 — Não liberar acima do produzido

```
released_qty_total <= produced_qty
```

**Implementação**:
- Endpoint `future_production_release_batch`:
  ```python
  to_release = float(fpb.produced_qty) - float(fpb.released_qty or 0)
  if to_release <= 0:
      return {"released_count": 0, "message": "Nada a liberar"}
  ```
- Por PR (linha): `released_qty <= reserved_qty` — checado no `Before Save` da PR.

---

## RB-007 — Não entregar acima do liberado

```
delivery_qty <= released_qty
```

**Implementação**: **AINDA NÃO IMPLEMENTADA**.

Hoje o ERPNext nativo não conhece nossos campos `fp_released_qty`. O Delivery
Note nativo só bloqueia "delivery > qty do SO".

**Como completar** (proposta):
- Server Script `Delivery Note - Validate (Before Save)` que para cada linha:
  - Busque a PR pelo `against_sales_order` + `sales_order_item`
  - Verifique se `delivery_qty <= released_qty - delivered_qty acumulado`

Adicionar essa validação é trivial, mas tem que decidir o que fazer quando a
DN nasce de Pick List (que já restringe pelo batch_no certo). Hoje a regra é
**confiança no operador** com o lote certo via Pick List.

---

## RB-008 — Produção cancelada exige tratamento de reservas

> Não cancelar produção com reservas ativas sem replanejar, cancelar reservas
> ou registrar motivo.

**Implementação parcial**:
- O Frappe nativo bloqueia cancelar um doc que tem outros docs submitted referenciando ele (via Link Validation), mas isso não cobre o caso aqui porque a referência é via campo Link normal.
- **Hoje**: ao cancelar um FPB com PRs ativas, o cancelamento prossegue mas as PRs ficam "órfãs".

**Como completar** (proposta):
- Server Script `FPB - Before Cancel` que bloqueia se existir PR com `docstatus=1` para esse FPB:
  ```python
  active = frappe.db.count("Production Reservation",
                           {"future_production_batch": doc.name, "docstatus": 1})
  if active > 0:
      frappe.throw(f"Existem {active} reservas ativas. Replaneje ou cancele antes.")
  ```

---

## RB-009 — Produção parcial libera por prioridade/FIFO

> Se produzido < reservado, liberar na ordem definida.

**Implementação**:
- Endpoint `future_production_release_batch`:
  ```sql
  select name, reserved_qty, released_qty
  from `tabProduction Reservation`
  where future_production_batch = %s
    and docstatus = 1
    and (reserved_qty - released_qty) > 0
  order by priority asc,
           payment_date asc,
           reservation_date asc,
           creation asc
  ```
- Distribui `produced_qty` na ordem retornada, parando quando zera.

**Verificado nos cenários A/B/C/D** ([`09-testing.md`](09-testing.md)).

---

## RB-010 — Reserva cancelada devolve saldo

> Se a reserva não foi liberada, o saldo deve voltar para a produção.

**Implementação**:
- Server Script `PR - On Cancel`:
  - Re-soma todas as PRs ativas do FPB
  - `set_value` no FPB com novos `reserved_qty`, `released_qty`, `available_qty`, `pending_release_qty`, `status`
  - Atualiza espelho no Sales Order Item

**Observação**: se a PR já tinha `released_qty > 0` (parte foi entregue), o cancelamento devolve apenas o saldo não liberado — o liberado fica registrado no histórico mas some da PR (`docstatus=2`). Para auditoria, há `track_changes=1` em ambos os DocTypes.

---

## Regras adicionais (módulo Pacientes)

### RBP-001 — CPF válido

CPF do Patient deve ter 11 dígitos não triviais.

**Implementação**: `Patient - Validate CPF (Before Save)`. Validação atual:
- Strip tudo que não é dígito
- Exige 11 caracteres restantes
- Recusa se todos iguais (`11111111111`, `22222222222`, etc.)

**Não implementado**: validação do dígito verificador (DV) pelo algoritmo oficial. Se a auditoria exigir, é fácil estender com a fórmula de DV.

### RBP-002 — Soma das ampolas dos pacientes = qty do item

Para cada item do Sales Order com pacientes vinculados:
```
sum(fp_patients[item == X].qty) == sales_order.items[X].qty
```

**Implementação**: `SO - Validate Patients (Before Save)`:
```python
by_item_patients = {}
for p in patients:
    by_item_patients[p.item_code] = by_item_patients.get(p.item_code, 0) + float(p.qty)

for row in (doc.items or []):
    sum_patients = by_item_patients.get(row.item_code, 0)
    if sum_patients > 0 and abs(sum_patients - float(row.qty)) > 0.001:
        frappe.throw("Item ...: qty diferente da soma das ampolas dos pacientes.")
```

> **Compatibilidade**: o SO pode ser criado sem pacientes (`fp_patients` vazio) — a validação só roda quando há pelo menos uma linha de paciente.

### RBP-003 — Item do paciente deve estar nos itens do SO

```
patient.item_code in [item.item_code for item in sales_order.items]
```

**Implementação**: parte do mesmo Server Script (`SO - Validate Patients`).

### RBP-004 — Quantidade do paciente > 0

Não aceita `qty=0` ou negativo. Bloqueia no Before Save.

---

## Resumo da matriz regra × implementação

| Regra | Tipo de check | Implementada em |
|---|---|---|
| RB-001 | Conceitual | (FPB é DocType separado, sem Stock Ledger) |
| RB-002 | Validação | `PR - Validate`, endpoint `reserve_sales_order_item` |
| RB-003 | Validação | `PR - Validate`, endpoint `reserve_sales_order_item` |
| RB-004 | Validação | `PR - Validate`, endpoint `reserve_sales_order_item` |
| RB-005 | Validação | `PR - Validate`, endpoint `reserve_sales_order_item` |
| RB-006 | Validação | `PR - Validate`, `release_batch` |
| RB-007 | **TODO** | (não implementado) |
| RB-008 | **TODO** parcial | (apenas track_changes para auditoria) |
| RB-009 | Lógica | `release_batch` |
| RB-010 | Lógica | `PR - On Cancel` |
| RBP-001 | Validação | `Patient - Validate CPF` |
| RBP-002 | Validação | `SO - Validate Patients` |
| RBP-003 | Validação | `SO - Validate Patients` |
| RBP-004 | Validação | `SO - Validate Patients` |
