# Criar Lote — FPB (Lote de Produção Futura) vs Batch (Lote Físico)

> Guia manual: criar o lote no ERPNext pra a venda poder reservar. Faça
> pela UI. Padrão de código: `TIRZE<dose>-YYYYMMDD`.

## 2 conceitos — não confundir

| | **FPB — Lote de Produção Futura** | **Batch — Lote Físico** |
|---|---|---|
| O que é | PROMESSA de fabricar N ampolas | lote REAL produzido |
| Quando | ANTES de produzir (planejamento) | DEPOIS de manipular |
| Estoque | NÃO é estoque (é capacidade reservável) | É estoque físico, rastreável |
| DocType | `Future Production Batch` | `Batch` (nativo ERPNext) |
| Código | `production_code` = TIRZE60-20260602 | `batch_id` = TIRZE60-20260602 (mesmo) |
| Pro quê | vendas reservam contra ele | dispensação sai dele |

> Mesmo código nos dois (`TIRZE60-20260602`) → rastreio visual: lote
> planejado → lote físico.

```
FPB (planejado)  ──reservas──►  vendas
   │ produz (manipula)
   ▼
Batch (físico)   ──estoque──►  dispensação ao paciente
```

**Agora** você cria só o **FPB** (pra venda reservar). O **Batch** vem
depois, quando produzir (etapa manual de produção).

---

## Criar o FPB (passo a passo — UI)

### 1. Abrir

```
Menu lateral → Produção Futura → Lote de Produção Futura
  OU direto: https://erp.injemedpharma.com.br/app/future-production-batch/new
```

Topo direito → **+ Add Future Production Batch** (ou já abre no /new).

### 2. Preencher (campos obrigatórios *)

```
┌────────────────────────────────────────────────────────────┐
│  NOVO LOTE DE PRODUÇÃO FUTURA                    [Save]     │
├────────────────────────────────────────────────────────────┤
│  Série *:               (deixa o default .#####)            │
│                                                            │
│  Código da Produção *:  TIRZE60-20260603                   │
│     ↑ padrão TIRZE<dose>-AAAAMMDD (dose 60, hoje)          │
│                                                            │
│  Empresa *:             Injemedpharma                      │
│                                                            │
│  Status *:              Aberta para Reserva                │
│     ↑ ESSE status é o que deixa a venda reservar           │
│                                                            │
│  Produto a Produzir *:  TIR00060                           │
│     (Tirzepatida 60mg/2,4ml — preenche nome sozinho)       │
│                                                            │
│  Quantidade Planejada *: 1                                 │
│     ↑ pra pedido de 1 ampola, pode ser 1 (ou mais)         │
│                                                            │
│  Data Prevista de Produção *: 03/06/2026                   │
│                                                            │
│  Depósito de Produto Acabado *: Produtos Acabados - I      │
│                                                            │
│  (opcionais)                                               │
│  Data Prevista de Liberação:  10/06/2026  (+7d quarentena) │
│  Depósito WIP:                Trabalho Em Andamento - I    │
└────────────────────────────────────────────────────────────┘
```

| Campo | Valor | Por quê |
|---|---|---|
| Código da Produção * | `TIRZE60-20260603` | padrão dose+data |
| Empresa * | `Injemedpharma` | (com 'e') |
| Status * | `Aberta para Reserva` | libera reserva |
| Produto a Produzir * | `TIR00060` | Tirzepatida 60mg |
| Quantidade Planejada * | `1` | cobre o pedido de 1 ampola |
| Data Prevista de Produção * | hoje | quando manipula |
| Depósito de Produto Acabado * | `Produtos Acabados - I` | onde o acabado entra |

### 3. Salvar (Rascunho)

`Save` (Ctrl+S) → fica como **Rascunho** (docstatus=0). Pode editar.

### 4. Submeter

Botão azul **Submit** (topo direito) → status **Aberta para Reserva**
(docstatus=1).

> Só DEPOIS de submeter o lote aceita reservas. Em Rascunho não reserva.

### 5. Conferir

```
Quantidade Planejada:  1
Quantidade Reservada:  0
Quantidade Disponível: 1   ← saldo livre pra reservar
Status:                Aberta para Reserva
```

---

## Pra o pedido de 1 ampola

```
1. Cria o FPB acima (planned_qty = 1, ou maior)  ← VOCÊ FAZ AGORA
2. Pedido no HubSpot + paciente validado no validacao_receita
3. Card React → webhook n8n → cliente+pedido+paciente+médico+receita
                            → RESERVA (1 ampola contra esse FPB)
                            → recebimento (Payment Entry)
4. ERPNext recebe pronto → produção/dispensação MANUAL
```

No Card React, na hora de escolher o lote, vai aparecer esse FPB
(`TIRZE60-20260603`, 1 disponível). O operador aloca 1 ampola nele.

---

## Quando produzir (DEPOIS) — criar o Batch físico

Etapa manual de produção (ver `09-processo-manual-erpnext.md`):
```
Abre o FPB → preenche:
  Lote Real Produzido (batch_no) → cria Batch com batch_id = TIRZE60-20260603
  Quantidade Produzida           → 1
Salva → status "Produzida Totalmente"
+ Stock Entry (Material Receipt) das ampolas no estoque com esse Batch
```

O `Batch` (lote físico) usa o MESMO código do FPB pra rastreio.
