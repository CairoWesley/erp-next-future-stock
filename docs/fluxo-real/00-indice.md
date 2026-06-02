# Fluxo Real — Documentação Etapa por Etapa

> Esta pasta documenta o fluxo **real** executado em produção em
> `https://erp.injemedpharma.com.br`. Cada arquivo cobre uma etapa:
> o que foi feito, como foi feito (UI + API), padrões adotados, resultado
> obtido e URLs pra inspecionar.

## Convenções

### Production Code do FPB

```
TIRZE<dosagem>-YYYYMMDD
       ╰──┬─╯ ╰───┬───╯
         │       └── Data de manipulação (YYYYMMDD)
         └── Dosagem em mg (60, 90, ...)

Exemplos:
  TIRZE60-20260602   Tirzepatida 60mg manipulada em 02/06/2026
  TIRZE90-20260615   Tirzepatida 90mg manipulada em 15/06/2026
```

### Batch ID (lote físico)

Mesmo padrão do `production_code` para rastreabilidade visual direta:

```
FPB.production_code == Batch.batch_id   (ex: TIRZE60-20260602)
```

### Códigos automáticos do ERPNext

| Tipo | Series | Exemplo |
|---|---|---|
| Future Production Batch | `FPB-.YYYY.-.#####` | FPB-2026-00115 |
| Production Reservation | `PR-.YYYY.-.#####` | PR-2026-00001 |
| Patient | `PAC-.YYYY.-.#####` | PAC-2026-00152 |
| Prescriber | `PRES-.YYYY.-.#####` | PRES-2026-00031 |
| Sales Order | nativo ERPNext | SAL-ORD-2026-00089 |
| Dispensacao | `DISP-.YYYY.-.#####` | DISP-2026-00001 |

## Índice

| # | Etapa | Status | Arquivo |
|---|---|---|---|
| 1 | Criar primeiro FPB (lote planejado) | ✅ | [01-criar-fpb.md](01-criar-fpb.md) |
| 2 | Criar Sales Order (pedido) | ⏳ | (próximo) |
| 3 | Validar e reservar | ⏳ | — |
| 4 | Registrar produção (Batch físico + update FPB) | ⏳ | — |
| 5 | Stock Entry Manufacture | ⏳ | — |
| 6 | Liberar reservas | ⏳ | — |
| 7 | Alocar batch por paciente | ⏳ | — |
| 8 | Delivery Note | ⏳ | — |
| 9 | Sales Invoice | ⏳ | — |
| 10 | Payment Entry | ⏳ | — |
| 11 | Criar Dispensação + imprimir etiqueta Zebra | ⏳ | — |
| 12 | Marcar como dispensado | ⏳ | — |

## Como usar esta pasta

Cada documento de etapa contém:

1. **O que faz** — explicação simples
2. **Quem faz** — papel responsável
3. **Pré-requisitos** — etapas anteriores
4. **Padrão adotado** — convenções específicas da Injemed
5. **Via UI (clique a clique)** — pra operador
6. **Via API (payload + curl)** — pra integração
7. **Resultado obtido** — IDs, valores reais
8. **URL pra inspecionar** — link direto ERPNext
9. **Próximo passo** — link pra próxima etapa
