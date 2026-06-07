# Processo Manual no ERPNext — Produção até Dispensação

> A partir do pedido pronto (cadastro + reserva + pacientes + receita +
> financeiro lançado, tudo via API), o time opera **manual no ERPNext**.
> Este é o clique-a-clique. Tudo acontece a partir do **Sales Order**.

## Pré-requisitos (já feitos pela automação)

```
✅ Sales Order submetido (docstatus=1)
✅ Pacientes vinculados (fp_patients) com lote escolhido
✅ Production Reservation criada
✅ Receita anexada (validada)
✅ Payment Entry lançado (recebimento)
✅ Pagamento AUTORIZADO (status=PAID) ← gate pra produzir
```

Abre o pedido:
```
https://erp.injemedpharma.com.br/app/sales-order/<NUMERO>
```

No topo direito do Sales Order aparecem os botões (Client Script
"Sales Order - Dispensation Buttons"):

```
┌─────────────────────────────────────────────┐
│ Sales Order 00129          [Submit ✓]        │
│  ▸ Validar e Reservar                        │
│  ▸ Forçar Reserva (ignorar validações)       │
│  ▸ Alocar Batch por Paciente                 │
│  ▸ Criar Dispensação      ← gera dispensação │
│  ▸ Abrir Dispensação                         │
└─────────────────────────────────────────────┘
```

---

## ETAPA 9 — Produzir o lote (Batch físico)

Antes de alocar, o lote planejado (FPB) precisa virar lote físico
produzido. No ERPNext:

```
1. Menu lateral → Produção Futura → Lote de Produção Futura
   OU direto: /app/future-production-batch/<FPB>
2. Abre o FPB (ex: FPB-2026-00115)
3. Preenche:
     Lote Real Produzido (batch_no)  → cria/seleciona o Batch
                                        batch_id = TIRZE60-20260602
     Quantidade Produzida (produced_qty) → ex: 2000
4. Salva
   → status muda pra "Produzida Totalmente"
```

> O Batch (`batch_id = production_code`) é o lote físico rastreável.
> Padrão: `TIRZE<dose>-YYYYMMDD`.

**Entrada de estoque**: as ampolas produzidas precisam entrar no estoque
"Produtos Acabados - I" com esse Batch (Stock Entry → Material Receipt,
ou Manufacture se usar Work Order/BOM). Sem estoque, a entrega (Delivery)
não baixa.

---

## ETAPA 10 — Liberar Reservas

Distribui o produzido entre as reservas (FIFO por prioridade → data de
pagamento → data de reserva).

```
No FPB → botão "Liberar Reservas"
  OU endpoint future_production_release_batch
→ released_qty sobe · reservas viram "liberadas"
```

Requer: `produced_qty > 0` + `batch_no` preenchido.

---

## ETAPA 11 — Alocar Batch por Paciente

Grava o lote físico em cada linha de paciente do pedido.

```
No Sales Order → botão "Alocar Batch por Paciente"
  (chama future_production_allocate_patient_batches)
→ cada fp_patient.batch_no = TIRZE60-20260602
  (respeita o lote que o bin-pack já tinha atribuído ao paciente)
```

---

## ETAPA 12 — Delivery Note (Entrega) — opcional/fiscal

```
No Sales Order → botão "Create" (nativo ERPNext) → Delivery Note
→ confere itens + batch → Submit
→ baixa estoque do Batch
```

Gate: pagamento AUTORIZADO basta (não espera liquidar).

---

## ETAPA 13 — Sales Invoice (NF-e) — ⛔ PULA no modelo atual

> **Modelo confirmado: só Payment Entry, sem Sales Invoice.** O recebimento já
> foi lançado pela API (valor hoje, liquidação futura). Não emite Sales Invoice
> aqui. (Se um dia precisar de NF-e fiscal, é nesta etapa — fora do fluxo atual.)

```
No Delivery Note (ou Sales Order) → "Create" → Sales Invoice
→ confere → Submit → emite NF-e
```

---

## ETAPA 14 — Gerar a DISPENSAÇÃO  ⭐

```
No Sales Order → botão "Criar Dispensação"
  (chama future_production_create_dispensation_from_so)
→ cria o documento Dispensacao (DISP-2026-#####)
   com a child table de pacientes (1 linha por paciente)

Depois → botão "Abrir Dispensação" (abre o doc criado)
```

O documento Dispensacao tem:
```
status:          Rascunho → Pendente → Dispensado
sales_order:     <SO>
customer:        <cliente>
delivery_note:   <DN se houver>
pharmacist:      <farmacêutico>
label_template:  25x60mm | 30x60mm | 50x30mm | 100x50mm | Receituario 100x50mm
patients[]:      pacientes da entrega (Dispensacao Paciente)
```

---

## ETAPA 15 — Imprimir Etiquetas Zebra

Na Dispensacao (Client Script "Dispensacao - Print Zebra Labels"):

```
1. Escolhe o "label_template" (ex: Receituario 100x50mm)
2. Botão "Imprimir Etiquetas Zebra"
     → future_production_generate_all_zpl_labels (todas)
     → OU future_production_generate_zpl_label (uma)
     → envia ZPL pra impressora Zebra via BrowserPrint
3. Botão marca impresso → future_production_mark_label_printed
     → printed_count sobe · all_printed quando todas
```

> Requer a impressora Zebra com BrowserPrint instalado no navegador do
> farmacêutico. O ZPL é gerado por paciente/ampola conforme o template.

---

## ETAPA 16 — Marcar Dispensado

```
Na Dispensacao → botão "Marcar Dispensado"
  (chama future_production_mark_dispensation_completed)
→ status = "Dispensado" · dispensed_at = agora
→ fecha o ciclo
```

---

## 🔁 Resumo — ordem dos cliques

```
[FPB]  preenche Batch real + Qtd Produzida → Produzida
        └ Liberar Reservas
[SO]   Alocar Batch por Paciente
        └ (PULA Delivery Note + Sales Invoice — só Payment Entry)
        └ Criar Dispensação → Abrir Dispensação
[DISP] escolhe template → Imprimir Etiquetas Zebra
        └ Marcar Dispensado
```

> Batch físico: validade **6 meses** (item TIR00060 shelf life 180d — a
> validade auto-preenche da data de fabricação). Ex. SO 00138:
> Batch `TIRZE60-20260603`, fab 03/06/2026, val 03/12/2026.

## Endpoints por trás de cada botão

| Botão (onde) | Endpoint |
|---|---|
| Validar e Reservar (SO) | `future_production_validate_and_reserve` |
| Alocar Batch por Paciente (SO) | `future_production_allocate_patient_batches` |
| **Criar Dispensação (SO)** | `future_production_create_dispensation_from_so` |
| Liberar Reservas (FPB) | `future_production_release_batch` |
| Imprimir Etiquetas Zebra (DISP) | `future_production_generate_all_zpl_labels` / `generate_zpl_label` |
| (marca impresso) | `future_production_mark_label_printed` |
| Marcar Dispensado (DISP) | `future_production_mark_dispensation_completed` |

## Gates (precondições) — ver [00l](00l-regras-negocio.md)

- Produção (9-11): pagamento AUTORIZADO (status=PAID).
- Entrega/NF (12-13): autorização basta.
- Dispensação (14-16): NF + entrega + receita anexada validada.
- Financeiro (Payment Entry): já lançado pela API (valor hoje, recebimento
  futuro na liquidação) — conciliar no banco na `clearance_date`.
