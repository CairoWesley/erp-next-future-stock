# 01 — Visão Geral

## Problema

A empresa vende ampolas (item farmacêutico) cuja produção é **coletiva** e
**futura**: um único lote pode ter 2.000 ampolas que serão divididas entre
vários clientes/pedidos. Antes deste módulo, isso era controlado em planilhas
paralelas, gerando:

1. Venda acima da capacidade planejada.
2. Reserva da mesma quantidade para mais de um cliente.
3. Falta de rastreabilidade pedido → lote físico → paciente.
4. Sem regra clara de liberação quando a produção real fica abaixo do planejado.
5. Estoque "promessa" misturado com estoque físico.

## Solução

Três camadas dentro do próprio ERPNext, criadas como DocTypes customizados:

```
┌─────────────────────────────────────┐
│  Future Production Batch (FPB)       │  Lote de Produção Futura
│  - planejado: 2.000                  │  (capacidade prometida,
│  - reservado: 1.300                  │   ainda não fabricada)
│  - disponível: 700                   │
│  - produzido: 0                      │
└──────────────┬──────────────────────┘
               │ N reservas
               │
┌──────────────▼──────────────────────┐
│  Production Reservation (PR)         │  Reserva de um pedido
│  - sales_order: SO-0001              │  dentro de um FPB
│  - cliente: Clínica Alfa             │
│  - reservado: 300                    │
│  - liberado: 0   pendente: 300       │
└──────────────┬──────────────────────┘
               │ pertence a
               │
┌──────────────▼──────────────────────┐
│  Sales Order (nativo + custom)       │  Pedido do médico
│  + tabela fp_patients[]              │  + lista de pacientes
└─────────────────────────────────────┘
               │ 1..N pacientes
               │
┌──────────────▼──────────────────────┐
│  Patient                             │  Paciente final
│  - nome, CPF, endereço, telefone     │
│  - médico prescritor                 │
└─────────────────────────────────────┘
```

## Escopo

### Dentro do escopo
- Criar lote de produção futura
- Controlar planejado / reservado / disponível / produzido / liberado / pendente
- Reservar pedido inteiro ou parcial contra um ou mais FPBs
- Bloquear reserva acima do saldo (com exceção opt-in `allow_overbooking`)
- Liberar reservas por FIFO/prioridade quando a produção real é menor
- Vincular pacientes (com CPF, endereço, contato) a cada linha do pedido
- Validar que a soma das ampolas dos pacientes bate com a qty do item
- 4 relatórios operacionais
- Setup 100% via API REST (sem entrar no container Docker)

### Fora do escopo (nesta versão)
- Planejamento avançado de capacidade
- Algoritmos de otimização
- Controle de qualidade detalhado
- Gestão regulatória farmacêutica completa
- Integração fiscal / gateways de pagamento
- Criação automática de Delivery Note sem revisão humana
- Mobile / BI externo
- Geração de etiquetas individuais por paciente (PDF)
- Importação em massa de pacientes via CSV/XLSX

## Quem usa

| Papel | O que faz |
|---|---|
| **Vendedor (CRM)** | Cria Sales Order e adiciona pacientes |
| **Comercial** | Reserva o SO em FPB (manual ou automático) |
| **Planejamento** | Cria/cancela FPB; abre/fecha para reserva |
| **Produção** | Marca `produced_qty` e `batch_no` no FPB |
| **Operações** | Dispara liberação, gera Pick List + Delivery Note |
| **Auditoria** | Lê relatórios e usa rastreabilidade lote → SO → paciente |

## Status

Versão 0.1.0 — instalada e validada contra `https://erp.injemedpharma.com.br`
com o cenário de aceite da seção 23 da documentação original
(2.000 planejados, 4 reservas de 300/500/700/500, produção real de 1.850 →
distribuição FIFO com 150 pendentes para o último pedido).

Ver [`09-testing.md`](09-testing.md) para resultados completos dos 4 cenários
testados (`produced=2000`, `1850`, `1500`, `2100`).
