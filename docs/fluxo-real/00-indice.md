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

A partir de `setup_15_naming_series`, toda numeração é **auto-increment puro
zero-padded de 5 dígitos**, sem prefixo nem ano. Cada DocType tem contador
independente. Ver [`00b-numeracao.md`](00b-numeracao.md) pra detalhes.

| Tipo | Padrão antes | Padrão novo |
|---|---|---|
| Customer | CUST-2026-00001 | `00001` |
| Patient | PAC-2026-00001 | `00001` |
| Prescriber | PRES-2026-00031 | `00001` |
| Sales Order | SAL-ORD-2026-00089 | `00001` |
| Future Production Batch | FPB-2026-00115 (mantém) | próximo: `00001` |
| Production Reservation | PR-2026-00001 | `00001` |
| Dispensacao | DISP-2026-00001 | `00001` |
| Delivery Note | MAT-DN-2026-00001 | `00001` |
| Sales Invoice | ACC-SINV-2026-00001 | `00001` |
| Payment Entry | ACC-PAY-2026-00001 | `00001` |
| Stock Entry | MAT-STE-2026-00001 | `00001` |

## Índice

| # | Etapa | Status | Arquivo |
|---|---|---|---|
| 0a | Convenções gerais (este arquivo) | ✅ | [00-indice.md](00-indice.md) |
| 0b | Numeração auto-increment | ✅ | [00b-numeracao.md](00b-numeracao.md) |
| 0d | Sync produtos HubSpot ↔ ERPNext | ✅ | [00d-sync-produtos-hubspot.md](00d-sync-produtos-hubspot.md) |
| 1 | Criar primeiro FPB (lote planejado) | ✅ | [01-criar-fpb.md](01-criar-fpb.md) |
| 2 | Cadastrar Cliente real (Customer + Address + Contact) | ⏳ | (próximo) |
| 3 | Cadastrar Médico (Prescriber + Council) | ⏳ | — |
| 4 | Cadastrar Paciente (Patient) | ⏳ | — |
| 5 | Criar Sales Order com fp_patients | ⏳ | — |
| 6 | Validar e reservar | ⏳ | — |
| 7 | Registrar produção (Batch físico + update FPB) | ⏳ | — |
| 8 | Stock Entry Manufacture | ⏳ | — |
| 9 | Liberar reservas | ⏳ | — |
| 10 | Alocar batch por paciente | ⏳ | — |
| 11 | Delivery Note | ⏳ | — |
| 12 | Sales Invoice | ⏳ | — |
| 13 | Payment Entry | ⏳ | — |
| 14 | Criar Dispensação + imprimir etiqueta Zebra | ⏳ | — |
| 15 | Marcar como dispensado | ⏳ | — |

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
