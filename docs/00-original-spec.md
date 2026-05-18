# Documentação Completa — Módulo ERPNext de Reserva de Produção Futura para Ampolas

## 1. Visão geral do projeto

Este documento descreve o planejamento completo para criação de um módulo no ERPNext para controlar **reservas de produção futura**.

O cenário principal é:

- A empresa possui pedidos de venda pagos.
- Esses pedidos precisam reservar quantidade de uma produção futura.
- Uma produção futura pode ser de, por exemplo, **2.000 ampolas**.
- Essas 2.000 ampolas não pertencem a um único cliente.
- Cada cliente/pedido reserva uma parte dessa produção.
- Quando a produção real é concluída, as quantidades são liberadas para os pedidos conforme regra operacional.
- Caso a produção seja menor que o planejado, alguns pedidos podem ser liberados parcialmente e o saldo restante pode ser replanejado para uma próxima produção.
- O ERPNext está rodando em Docker, então o melhor cenário de setup é usar API REST externa, sem depender de configuração manual dentro do container.

Resumo operacional:

```text
Pedido pago
    ↓
Reserva em produção futura
    ↓
Produção coletiva de 2.000 ampolas
    ↓
Entrada do lote real no estoque
    ↓
Liberação das quantidades por pedido/cliente
    ↓
Separação e entrega
```

Regra central:

```text
A produção futura é coletiva.
O cliente não é dono do lote inteiro.
Cada cliente possui uma reserva de quantidade dentro daquela produção.
```

---

## 2. Problema que o módulo resolve

Sem esse módulo, a operação fica vulnerável a erros como:

1. Vender mais ampolas do que a produção futura comporta.
2. Reservar a mesma quantidade para mais de um cliente.
3. Não saber quais pedidos estão vinculados a determinada produção.
4. Não saber quanto de uma produção já está reservado.
5. Não saber quanto ainda está disponível para reserva.
6. Não conseguir liberar parcialmente pedidos quando a produção real for menor que a planejada.
7. Não conseguir rastrear qual lote real atendeu cada cliente.
8. Não conseguir replanejar saldo pendente para produções futuras.
9. Misturar estoque real com promessa de produção futura.
10. Depender de controles paralelos fora do ERPNext.

O objetivo é transformar isso em um fluxo controlado, rastreável e auditável dentro do ERPNext.

---

## 3. Conceitos principais

### 3.1. Pedido do cliente

Representado pelo **Sales Order**.

Exemplo:

```text
Pedido: SO-0001
Cliente: Clínica Alfa
Produto: Ampola X
Quantidade: 300
Status financeiro: Pago
```

O Sales Order representa a demanda comercial.

---

### 3.2. Produção futura

Representada pelo DocType customizado:

```text
Future Production Batch
```

Ou em português:

```text
Lote de Produção Futura
```

Exemplo:

```text
Produção futura: FPB-2026-00001
Código operacional: AMP-2026-05-20-001
Produto: Ampola X
Quantidade planejada: 2.000
Quantidade reservada: 1.300
Quantidade disponível: 700
Status: Reservada Parcialmente
```

Esse documento **não representa estoque físico**. Ele representa uma produção planejada que ainda vai acontecer.

---

### 3.3. Reserva de produção

Representada pelo DocType customizado:

```text
Production Reservation
```

Ou em português:

```text
Reserva de Produção
```

Exemplo:

```text
Reserva: PR-2026-00001
Pedido: SO-0001
Cliente: Clínica Alfa
Produção futura: FPB-2026-00001
Quantidade reservada: 300
Quantidade liberada: 0
Status: Reservado
```

Esse documento conecta:

```text
Pedido de venda
    ↔
Produção futura
```

---

## 4. Diferença entre produção futura e lote real

### Future Production Batch

Existe antes da fabricação.

Responde:

- O que será produzido?
- Quando será produzido?
- Quanto será produzido?
- Quanto já foi reservado?
- Quanto ainda está disponível?
- Quais pedidos estão esperando essa produção?

Exemplo:

```text
Future Production Batch: FPB-2026-00001
Planejado: 2.000
Reservado: 1.800
Disponível: 200
Produzido: 0
```

### Batch do ERPNext

É o lote físico real, criado depois da fabricação.

Exemplo:

```text
Batch: LOT-AMP-2026-05-20-001
Quantidade real produzida: 1.850
```

Responde:

- Qual lote físico foi produzido?
- Qual lote foi entregue a cada cliente?
- Qual lote deve ser rastreado em auditoria, devolução ou recall?

Relação:

```text
Future Production Batch
    ↓ após fabricação
Batch real do ERPNext
```

---

## 5. Escopo do projeto

### Dentro do escopo

1. Criação de produção futura.
2. Controle de quantidade planejada.
3. Controle de quantidade reservada.
4. Controle de quantidade disponível.
5. Controle de quantidade produzida.
6. Controle de quantidade liberada.
7. Reserva de produção futura por pedido.
8. Reserva de uma produção para vários clientes.
9. Reserva parcial entre múltiplas produções.
10. Bloqueio de reserva acima da quantidade disponível.
11. Liberação total ou parcial após produção.
12. Liberação por prioridade/FIFO.
13. Replanejamento de saldo pendente.
14. Vinculação com Sales Order.
15. Vinculação com Work Order.
16. Vinculação com Batch real.
17. Vinculação com Delivery Note.
18. Campos de visualização no Sales Order Item.
19. Relatórios operacionais.
20. Setup automatizado via API REST.
21. Compatibilidade com ambiente Docker.
22. Documentação de endpoints e payloads.

### Fora do escopo inicial

1. Planejamento avançado de capacidade produtiva.
2. Algoritmo de otimização de produção.
3. Controle de qualidade detalhado.
4. Gestão regulatória farmacêutica completa.
5. Integração fiscal completa.
6. Integração com gateways de pagamento.
7. Criação automática de Delivery Note sem revisão humana.
8. Controle multiempresa avançado.
9. Mobile app.
10. Dashboard BI externo.

---

## 6. Documentos nativos do ERPNext usados

### 6.1. Item

Representa o produto vendido e produzido.

Exemplo:

```text
AMP-001 - Ampola X 1ml
```

Configurações necessárias:

```text
Is Stock Item: Sim
Maintain Stock: Sim
Has Batch No: Sim
Allow Sales: Sim
Allow Purchase: Não, se for produto acabado produzido internamente
```

Finalidade:

- Aparece no Sales Order.
- Aparece na BOM.
- Aparece na Work Order.
- Aparece no Future Production Batch.
- Aparece na Production Reservation.
- Aparece no Batch/estoque.
- Aparece no Delivery Note.

---

### 6.2. BOM

A BOM é a ficha técnica de produção.

Exemplo:

```text
Para fabricar 1 ampola:
- 1 frasco
- 1 tampa
- 1 rótulo
- X ml de insumo ativo
- Y ml de veículo/base
```

Finalidade:

- Permitir que a Work Order calcule materiais necessários.
- Padronizar a produção.
- Servir como referência da fórmula/ficha técnica.

---

### 6.3. Sales Order

O Sales Order é o pedido do cliente.

Exemplo:

```text
SO-0001
Cliente: Clínica Alfa
Item: AMP-001
Quantidade: 300
```

Finalidade:

- Origem da demanda.
- Pedido que será reservado contra uma produção futura.
- Documento que depois será entregue via Delivery Note.

---

### 6.4. Production Plan

Pode ser usado para planejamento agrupado.

MVP simples:

```text
Future Production Batch → Work Order
```

Fluxo mais estruturado:

```text
Future Production Batch → Production Plan → Work Order
```

---

### 6.5. Work Order

É a ordem de produção real.

Exemplo:

```text
WO-0001
Produto: AMP-001
Quantidade: 2.000
BOM: BOM-AMP-001
```

Finalidade:

- Executar a produção.
- Consumir matérias-primas.
- Gerar entrada de produto acabado.
- Conectar o planejamento futuro com a produção real.

---

### 6.6. Batch

É o lote físico real produzido.

Exemplo:

```text
LOT-AMP-2026-05-20-001
```

Finalidade:

- Controlar rastreabilidade.
- Informar qual lote atendeu qual pedido.
- Ser usado em Pick List e Delivery Note.

---

### 6.7. Stock Entry

Registra movimentações de estoque.

No fluxo de fabricação, registra:

- Saída de matéria-prima.
- Entrada do produto acabado.

---

### 6.8. Pick List

Documento de separação.

Finalidade:

- Separar o lote correto para o pedido correto.
- Evitar que separe produto não liberado.

---

### 6.9. Delivery Note

Documento de entrega/remessa.

Regra do projeto:

```text
Delivery Note só pode sair até a quantidade liberada para o pedido.
```

---

## 7. DocType customizado: Future Production Batch

### O que é

Documento que representa uma produção futura coletiva.

Exemplo:

```text
Future Production Batch: FPB-2026-00001
Código operacional: AMP-2026-05-20-001
Produto: Ampola X
Quantidade planejada: 2.000
```

### Finalidade

Serve para:

1. Registrar produções futuras.
2. Controlar quantidade planejada.
3. Controlar quantidade reservada.
4. Controlar saldo disponível.
5. Controlar produção real.
6. Controlar liberação para pedidos.
7. Vincular Work Order.
8. Vincular Batch real.
9. Servir como base para relatórios.
10. Evitar venda/reserva acima da produção.

### Campos

| Campo | Label | Tipo | Obrigatório | Read Only | Descrição |
|---|---|---|---|---|---|
| naming_series | Série | Select | Sim | Não | Série automática do documento |
| production_code | Código da Produção | Data | Sim | Não | Código operacional da produção futura |
| company | Empresa | Link / Company | Sim | Não | Empresa responsável |
| status | Status | Select | Sim | Não | Status operacional |
| item_code | Produto a Produzir | Link / Item | Sim | Não | Produto fabricado |
| item_name | Nome do Produto | Data | Não | Sim | Nome buscado do Item |
| uom | Unidade de Medida | Link / UOM | Não | Sim | Unidade de estoque |
| planned_qty | Quantidade Planejada | Float | Sim | Não | Quantidade prevista |
| reserved_qty | Quantidade Reservada | Float | Não | Sim | Soma das reservas |
| available_qty | Quantidade Disponível | Float | Não | Sim | Saldo disponível |
| produced_qty | Quantidade Produzida | Float | Não | Controlado | Quantidade real produzida |
| released_qty | Quantidade Liberada | Float | Não | Sim | Soma liberada |
| pending_release_qty | Pendente de Liberação | Float | Não | Sim | Produzido menos liberado |
| planned_production_date | Data Prevista de Produção | Date | Sim | Não | Data planejada |
| expected_release_date | Data Prevista de Liberação | Date | Não | Não | Data de liberação |
| reservation_cutoff_datetime | Limite para Reserva | Datetime | Não | Não | Limite de novas reservas |
| production_plan | Plano de Produção | Link / Production Plan | Não | Não | Production Plan vinculado |
| work_order | Ordem de Produção | Link / Work Order | Não | Não | Work Order vinculada |
| bom | BOM | Link / BOM | Não | Não | Ficha técnica usada |
| batch_no | Lote Real Produzido | Link / Batch | Não | Não | Lote real |
| target_warehouse | Depósito de Produto Acabado | Link / Warehouse | Sim | Não | Warehouse de entrada |
| wip_warehouse | Depósito WIP | Link / Warehouse | Não | Não | Warehouse em processo |
| allow_overbooking | Permitir Reserva Acima do Planejado | Check | Não | Não | Permite exceção |
| overbooking_limit_qty | Limite de Overbooking | Float | Não | Não | Limite adicional |
| notes | Observações | Small Text | Não | Não | Observações |

### Status

```text
Rascunho
Aberta para Reserva
Reservada Parcialmente
Totalmente Reservada
Fechada para Reserva
Em Produção
Produzida Parcialmente
Produzida Totalmente
Liberada Parcialmente
Liberada Totalmente
Cancelada
```

### Fórmulas

```text
available_qty = planned_qty - reserved_qty
pending_release_qty = produced_qty - released_qty
```

Regras:

```text
available_qty nunca deve ser negativo
released_qty nunca deve ser maior que produced_qty
reserved_qty nunca deve ser maior que planned_qty, exceto overbooking controlado
```

---

## 8. DocType customizado: Production Reservation

### O que é

Documento que representa a reserva de um pedido dentro de uma produção futura.

Exemplo:

```text
Production Reservation: PR-2026-00001
Pedido: SO-0001
Cliente: Clínica Alfa
Produção futura: FPB-2026-00001
Quantidade reservada: 300
```

### Finalidade

Serve para:

1. Registrar que um pedido reservou parte de uma produção futura.
2. Controlar quantidade reservada por pedido.
3. Controlar quantidade liberada por pedido.
4. Controlar pendência por pedido.
5. Definir prioridade de liberação.
6. Permitir liberação parcial.
7. Permitir replanejamento.
8. Conectar o pedido ao lote real produzido.

### Campos

| Campo | Label | Tipo | Obrigatório | Read Only | Descrição |
|---|---|---|---|---|---|
| naming_series | Série | Select | Sim | Não | Série automática |
| sales_order | Pedido de Venda | Link / Sales Order | Sim | Não | Pedido vinculado |
| sales_order_item | Linha do Pedido | Data | Sim | Não | ID da linha |
| customer | Cliente | Link / Customer | Sim | Não | Cliente |
| item_code | Produto | Link / Item | Sim | Não | Produto reservado |
| future_production_batch | Lote de Produção Futura | Link / Future Production Batch | Sim | Não | Produção vinculada |
| reserved_qty | Quantidade Reservada | Float | Sim | Não | Quantidade prometida |
| released_qty | Quantidade Liberada | Float | Não | Sim | Quantidade liberada |
| pending_qty | Quantidade Pendente | Float | Não | Sim | Quantidade pendente |
| payment_date | Data do Pagamento | Datetime | Não | Não | Usada para FIFO |
| reservation_date | Data da Reserva | Datetime | Não | Não | Data da reserva |
| priority | Prioridade | Int | Não | Não | Prioridade manual |
| status | Status | Select | Sim | Não | Status da reserva |
| release_batch_no | Lote Real Liberado | Link / Batch | Não | Não | Lote físico |
| delivery_note | Nota de Entrega | Link / Delivery Note | Não | Não | Entrega |
| notes | Observações | Small Text | Não | Não | Observações |

### Status

```text
Reservado
Parcialmente Liberado
Liberado
Cancelado
Replanejado
```

### Fórmula

```text
pending_qty = reserved_qty - released_qty
```

---

## 9. Campos customizados no Sales Order Item

A fonte oficial será sempre Production Reservation.

Campos espelho:

| Campo | Label | Tipo | Descrição |
|---|---|---|---|
| future_production_section | Produção Futura | Section Break | Agrupador |
| future_production_batch | Lote de Produção Futura | Link / Future Production Batch | Produção vinculada |
| reserved_qty | Qtd. Reservada em Produção | Float | Total reservado |
| released_qty | Qtd. Liberada | Float | Total liberado |
| pending_release_qty | Qtd. Pendente de Liberação | Float | Pendente |
| reservation_status | Status da Reserva | Select | Resumo |

Status:

```text
Sem Reserva
Reservado
Parcialmente Reservado
Liberado
Parcialmente Liberado
Pendente
```

---

## 10. Fluxo operacional completo

### 10.1. Criação da produção futura

Usuário cria:

```text
Future Production Batch
Produto: AMP-001
Quantidade planejada: 2.000
Data prevista de produção: 20/05/2026
Status: Aberta para Reserva
```

Sistema deve calcular:

```text
reserved_qty = 0
available_qty = 2.000
produced_qty = 0
released_qty = 0
pending_release_qty = 0
```

### 10.2. Pedido pago

Pedido:

```text
SO-0001
Cliente: Clínica Alfa
Item: AMP-001
Quantidade: 300
Status financeiro: Pago
```

Usuário escolhe reservar na produção:

```text
FPB-2026-00001
```

Sistema cria:

```text
Production Reservation
Pedido: SO-0001
Quantidade reservada: 300
Status: Reservado
```

Produção muda para:

```text
planned_qty = 2.000
reserved_qty = 300
available_qty = 1.700
status = Reservada Parcialmente
```

### 10.3. Vários clientes na mesma produção

Exemplo:

```text
SO-0001 → 300
SO-0002 → 500
SO-0003 → 700
SO-0004 → 500
```

Total:

```text
2.000
```

Produção:

```text
planned_qty = 2.000
reserved_qty = 2.000
available_qty = 0
status = Totalmente Reservada
```

### 10.4. Produção real

Quando a produção ocorre:

```text
Work Order: WO-0001
Produto: AMP-001
Planejado: 2.000
Produzido real: 1.850
Batch real: LOT-AMP-2026-05-20-001
```

Atualiza:

```text
Future Production Batch.produced_qty = 1.850
Future Production Batch.batch_no = LOT-AMP-2026-05-20-001
```

### 10.5. Liberação das reservas

Regra recomendada:

```text
1. Menor priority primeiro
2. Data de pagamento mais antiga
3. Data de reserva mais antiga
4. Pedido mais antigo
```

Produzido:

```text
1.850
```

Reservas:

```text
SO-0001 = 300
SO-0002 = 500
SO-0003 = 700
SO-0004 = 500
```

Liberação:

```text
SO-0001 = 300
SO-0002 = 500
SO-0003 = 700
SO-0004 = 350
```

Resultado:

```text
SO-0001: Liberado
SO-0002: Liberado
SO-0003: Liberado
SO-0004: Parcialmente Liberado, pendente 150
```

### 10.6. Replanejamento de pendência

Saldo pendente:

```text
SO-0004 = 150
```

Opções:

1. Manter pendente aguardando próxima produção.
2. Criar nova reserva para próxima produção.
3. Cancelar saldo pendente.
4. Substituir produto, se permitido comercialmente.

Recomendação:

```text
Criar nova Production Reservation para a próxima Future Production Batch.
```

### 10.7. Entrega

Quando o pedido tiver quantidade liberada:

```text
Pick List
    ↓
Delivery Note
```

Regra:

```text
A Delivery Note não pode exceder a quantidade liberada.
```

---

## 11. Requisitos funcionais

### RF-001 — Criar produção futura

O sistema deve permitir criar uma produção futura com produto, empresa, quantidade planejada, datas, warehouse e status.

### RF-002 — Controlar saldo da produção futura

O sistema deve controlar planejado, reservado, disponível, produzido, liberado e pendente.

### RF-003 — Reservar pedido em produção futura

O sistema deve permitir que um pedido pago reserve quantidade de uma produção futura.

### RF-004 — Permitir vários clientes na mesma produção

Uma produção futura deve aceitar reservas de vários Sales Orders e vários clientes.

### RF-005 — Impedir reserva acima do saldo

Bloquear quando:

```text
quantidade solicitada > available_qty
```

Exceto se overbooking estiver permitido.

### RF-006 — Permitir reserva parcial entre produções

Exemplo:

```text
Pedido: 600 unidades
Produção A: 200 disponíveis
Produção B: 400 disponíveis
```

### RF-007 — Vincular produção futura à Work Order

A produção futura deve poder ser vinculada a uma Work Order.

### RF-008 — Vincular produção futura ao Batch real

Após produção, permitir vincular o Batch real produzido.

### RF-009 — Liberar reservas após produção

Liberar reservas com base em:

```text
produced_qty - released_qty
```

### RF-010 — Permitir liberação parcial

Se produzido real for menor que reservado, liberar parcialmente.

### RF-011 — Controlar prioridade de liberação

Ordenar liberação por prioridade manual, data de pagamento, data de reserva e criação do pedido.

### RF-012 — Replanejar saldo pendente

Permitir mover quantidade pendente para outra produção futura.

### RF-013 — Exibir resumo no pedido

Sales Order Item deve exibir produção futura, reservado, liberado, pendente e status.

### RF-014 — Relatório de produções futuras

Relatório com produção, produto, datas, planejado, reservado, disponível, produzido, liberado e status.

### RF-015 — Relatório de reservas por produção

Relatório com produção, pedido, cliente, produto, reservado, liberado, pendente e status.

### RF-016 — Relatório de pedidos pendentes

Relatório de pedidos com reserva pendente, produção atrasada, liberação parcial ou saldo não replanejado.

### RF-017 — Setup via API

Script externo deve criar automaticamente DocTypes, Custom Fields, Client Scripts, Server Scripts, Workspace e relatórios quando possível.

---

## 12. Requisitos não funcionais

### RNF-001 — Idempotência

O script de setup deve poder rodar mais de uma vez sem duplicar DocTypes ou campos.

### RNF-002 — Compatibilidade com Docker

O setup deve rodar de fora do container, usando API REST.

### RNF-003 — Segurança

A API deve usar autenticação por token de usuário com permissão administrativa.

### RNF-004 — Auditoria

DocTypes principais devem ter:

```text
track_changes = 1
```

### RNF-005 — Performance

Consultas de saldo devem usar filtros por:

- future_production_batch
- item_code
- status
- docstatus

### RNF-006 — Rastreabilidade

Toda reserva deve manter vínculo com Sales Order, Sales Order Item, cliente, produção futura, Batch real e Delivery Note.

### RNF-007 — Manutenibilidade

Scripts separados:

```text
setup_01_structure.py
setup_02_client_scripts.py
setup_03_server_scripts.py
setup_04_reports.py
setup_05_workspace.py
```

### RNF-008 — Observabilidade

Logs claros:

```text
[CRIANDO] DocType Future Production Batch
[OK] Custom Field já existe
[ERRO] Falha ao criar Client Script
```

---

## 13. Regras de negócio

### RB-001 — Produção futura não é estoque

A produção futura não deve ser usada como estoque disponível. Ela é promessa operacional.

### RB-002 — Pedido precisa estar apto para reserva

Critérios mínimos:

```text
Sales Order existe
Sales Order contém o item
Quantidade > 0
Pedido está aprovado/pago
```

### RB-003 — Item da reserva deve ser igual ao item da produção

```text
Production Reservation.item_code = Future Production Batch.item_code
```

### RB-004 — Não reservar acima do saldo

```text
reserved_qty + nova_reserva <= planned_qty
```

### RB-005 — Overbooking exige permissão explícita

Se `allow_overbooking = 1`:

```text
reserved_qty + nova_reserva <= planned_qty + overbooking_limit_qty
```

### RB-006 — Não liberar acima do produzido

```text
released_qty_total <= produced_qty
```

### RB-007 — Não entregar acima do liberado

```text
delivery_qty <= released_qty
```

### RB-008 — Produção cancelada exige tratamento de reservas

Não cancelar produção com reservas ativas sem replanejar, cancelar reservas ou registrar motivo.

### RB-009 — Produção parcial libera por prioridade/FIFO

Se produzido < reservado, liberar na ordem definida.

### RB-010 — Reserva cancelada devolve saldo

Se a reserva não foi liberada, o saldo deve voltar para a produção.

---

## 14. Arquitetura de implantação em Docker/API

### Cenário

ERPNext está rodando em Docker.

Setup roda externamente:

```text
Notebook do desenvolvedor
ou container auxiliar
ou pipeline CI/CD
        ↓ API REST
ERPNext Docker
```

### Vantagens da API

1. Não precisa entrar no container.
2. Não precisa criar custom app inicialmente.
3. Pode ser executado em homologação e produção.
4. Pode ser versionado.
5. Pode ser repetido.
6. Evita configuração manual campo por campo.

### Variáveis de ambiente

Arquivo `.env`:

```env
ERPNEXT_URL=https://erp.suaempresa.com.br
ERPNEXT_API_KEY=sua_api_key
ERPNEXT_API_SECRET=sua_api_secret
```

Ambiente local:

```env
ERPNEXT_URL=http://localhost:8080
ERPNEXT_API_KEY=sua_api_key
ERPNEXT_API_SECRET=sua_api_secret
```

### Autenticação

Header:

```http
Authorization: token API_KEY:API_SECRET
Content-Type: application/json
Accept: application/json
```

Exemplo:

```bash
curl -X GET "$ERPNEXT_URL/api/resource/User" \
  -H "Authorization: token $ERPNEXT_API_KEY:$ERPNEXT_API_SECRET" \
  -H "Accept: application/json"
```

---

## 15. Documentação da API REST usada no setup

### 15.1. Testar conexão

Endpoint:

```http
GET /api/method/frappe.auth.get_logged_user
```

Curl:

```bash
curl -X GET "$ERPNEXT_URL/api/method/frappe.auth.get_logged_user" \
  -H "Authorization: token $ERPNEXT_API_KEY:$ERPNEXT_API_SECRET" \
  -H "Accept: application/json"
```

Resposta esperada:

```json
{
  "message": "usuario@empresa.com"
}
```

---

### 15.2. Verificar se DocType existe

Endpoint:

```http
GET /api/resource/DocType/{name}
```

Exemplo:

```bash
curl -X GET "$ERPNEXT_URL/api/resource/DocType/Future%20Production%20Batch" \
  -H "Authorization: token $ERPNEXT_API_KEY:$ERPNEXT_API_SECRET" \
  -H "Accept: application/json"
```

---

### 15.3. Criar DocType Future Production Batch

Endpoint:

```http
POST /api/resource/DocType
```

Payload resumido:

```json
{
  "doctype": "DocType",
  "name": "Future Production Batch",
  "module": "Manufacturing",
  "custom": 1,
  "is_submittable": 1,
  "track_changes": 1,
  "allow_rename": 0,
  "autoname": "naming_series:",
  "fields": [
    {
      "fieldname": "naming_series",
      "label": "Série",
      "fieldtype": "Select",
      "options": "FPB-.YYYY.-.#####",
      "default": "FPB-.YYYY.-.#####",
      "reqd": 1
    },
    {
      "fieldname": "production_code",
      "label": "Código da Produção",
      "fieldtype": "Data",
      "reqd": 1,
      "unique": 1
    },
    {
      "fieldname": "item_code",
      "label": "Produto a Produzir",
      "fieldtype": "Link",
      "options": "Item",
      "reqd": 1
    },
    {
      "fieldname": "planned_qty",
      "label": "Quantidade Planejada",
      "fieldtype": "Float",
      "reqd": 1
    }
  ],
  "permissions": [
    {
      "role": "System Manager",
      "read": 1,
      "write": 1,
      "create": 1,
      "delete": 1,
      "submit": 1,
      "cancel": 1,
      "amend": 1
    }
  ]
}
```

---

### 15.4. Criar DocType Production Reservation

Endpoint:

```http
POST /api/resource/DocType
```

Payload resumido:

```json
{
  "doctype": "DocType",
  "name": "Production Reservation",
  "module": "Manufacturing",
  "custom": 1,
  "is_submittable": 1,
  "track_changes": 1,
  "allow_rename": 0,
  "autoname": "naming_series:",
  "fields": [
    {
      "fieldname": "sales_order",
      "label": "Pedido de Venda",
      "fieldtype": "Link",
      "options": "Sales Order",
      "reqd": 1
    },
    {
      "fieldname": "customer",
      "label": "Cliente",
      "fieldtype": "Link",
      "options": "Customer",
      "reqd": 1
    },
    {
      "fieldname": "future_production_batch",
      "label": "Lote de Produção Futura",
      "fieldtype": "Link",
      "options": "Future Production Batch",
      "reqd": 1
    },
    {
      "fieldname": "reserved_qty",
      "label": "Quantidade Reservada",
      "fieldtype": "Float",
      "reqd": 1
    }
  ]
}
```

---

### 15.5. Criar Custom Field no Sales Order Item

Endpoint:

```http
POST /api/resource/Custom Field
```

Exemplo seção:

```json
{
  "doctype": "Custom Field",
  "dt": "Sales Order Item",
  "fieldname": "future_production_section",
  "label": "Produção Futura",
  "fieldtype": "Section Break",
  "insert_after": "delivery_date",
  "collapsible": 1
}
```

Exemplo link com produção futura:

```json
{
  "doctype": "Custom Field",
  "dt": "Sales Order Item",
  "fieldname": "future_production_batch",
  "label": "Lote de Produção Futura",
  "fieldtype": "Link",
  "options": "Future Production Batch",
  "insert_after": "future_production_section",
  "read_only": 1
}
```

Exemplo quantidade reservada:

```json
{
  "doctype": "Custom Field",
  "dt": "Sales Order Item",
  "fieldname": "reserved_qty",
  "label": "Qtd. Reservada em Produção",
  "fieldtype": "Float",
  "insert_after": "future_production_batch",
  "read_only": 1
}
```

---

### 15.6. Criar Client Script

Endpoint:

```http
POST /api/resource/Client Script
```

Payload exemplo:

```json
{
  "doctype": "Client Script",
  "dt": "Future Production Batch",
  "enabled": 1,
  "script": "frappe.ui.form.on('Future Production Batch', { refresh(frm) { if (!frm.is_new()) { frm.add_custom_button('Recalcular Saldos', () => { frappe.msgprint('Recalcular saldos será chamado aqui.'); }); } } });"
}
```

---

### 15.7. Criar Server Script

Endpoint:

```http
POST /api/resource/Server Script
```

Observação:

Em self-hosted, pode ser necessário habilitar:

```json
{
  "server_script_enabled": true
}
```

Payload exemplo:

```json
{
  "doctype": "Server Script",
  "name": "Validate Future Production Batch",
  "script_type": "DocType Event",
  "reference_doctype": "Future Production Batch",
  "event_frequency": "All",
  "doctype_event": "Before Save",
  "enabled": 1,
  "script": "if doc.planned_qty <= 0:\n    frappe.throw('A quantidade planejada precisa ser maior que zero.')"
}
```

---

### 15.8. Criar registro de Future Production Batch via API

Endpoint:

```http
POST /api/resource/Future Production Batch
```

Payload:

```json
{
  "production_code": "AMP-2026-05-20-001",
  "company": "Minha Empresa",
  "status": "Aberta para Reserva",
  "item_code": "AMP-001",
  "planned_qty": 2000,
  "reserved_qty": 0,
  "available_qty": 2000,
  "produced_qty": 0,
  "released_qty": 0,
  "pending_release_qty": 0,
  "planned_production_date": "2026-05-20",
  "expected_release_date": "2026-05-21",
  "target_warehouse": "PA - Produto Acabado - ME"
}
```

---

### 15.9. Criar Production Reservation via API

Endpoint:

```http
POST /api/resource/Production Reservation
```

Payload:

```json
{
  "sales_order": "SO-0001",
  "sales_order_item": "abc123linha",
  "customer": "Clínica Alfa",
  "item_code": "AMP-001",
  "future_production_batch": "FPB-2026-00001",
  "reserved_qty": 300,
  "released_qty": 0,
  "pending_qty": 300,
  "reservation_date": "2026-05-17 10:30:00",
  "priority": 100,
  "status": "Reservado"
}
```

---

### 15.10. Submeter documento via API

Endpoint:

```http
POST /api/method/frappe.client.submit
```

Payload:

```json
{
  "doc": {
    "doctype": "Production Reservation",
    "name": "PR-2026-00001"
  }
}
```

---

### 15.11. Atualizar documento via API

Endpoint:

```http
PUT /api/resource/{DocType}/{name}
```

Exemplo:

```http
PUT /api/resource/Future Production Batch/FPB-2026-00001
```

Payload:

```json
{
  "produced_qty": 1850,
  "batch_no": "LOT-AMP-2026-05-20-001",
  "status": "Produzida Parcialmente"
}
```

---

### 15.12. Buscar produções futuras disponíveis

Endpoint:

```http
GET /api/resource/Future Production Batch
```

Filtros sugeridos:

```json
[
  ["item_code", "=", "AMP-001"],
  ["status", "in", ["Aberta para Reserva", "Reservada Parcialmente"]],
  ["available_qty", ">", 0]
]
```

Campos:

```json
[
  "name",
  "production_code",
  "item_code",
  "planned_qty",
  "reserved_qty",
  "available_qty",
  "planned_production_date",
  "status"
]
```

Curl:

```bash
curl -G "$ERPNEXT_URL/api/resource/Future Production Batch" \
  -H "Authorization: token $ERPNEXT_API_KEY:$ERPNEXT_API_SECRET" \
  --data-urlencode 'fields=["name","production_code","item_code","planned_qty","reserved_qty","available_qty","planned_production_date","status"]' \
  --data-urlencode 'filters=[["item_code","=","AMP-001"],["available_qty",">",0]]'
```

---

## 16. Script de setup via API — arquitetura recomendada

Estrutura:

```text
erpnext-future-production-setup/
├── .env
├── requirements.txt
├── setup_01_structure.py
├── setup_02_client_scripts.py
├── setup_03_server_scripts.py
├── setup_04_reports.py
├── setup_05_workspace.py
└── lib/
    ├── erpnext_api.py
    └── payloads.py
```

requirements.txt:

```txt
requests
python-dotenv
```

Responsabilidade:

### setup_01_structure.py

Cria Future Production Batch, Production Reservation e Custom Fields no Sales Order Item.

### setup_02_client_scripts.py

Cria botões na tela Future Production Batch e Sales Order.

### setup_03_server_scripts.py

Cria validações de saldo, item divergente e entrega acima do liberado.

### setup_04_reports.py

Cria relatórios operacionais.

### setup_05_workspace.py

Cria workspace/menu:

```text
Produção Futura
    ├── Lotes de Produção Futura
    ├── Reservas de Produção
    ├── Mapa de Produção
    ├── Pendências de Liberação
```

---

## 17. API interna futura do módulo

Além da API REST padrão, recomenda-se criar endpoints internos.

### 17.1. Reservar item de pedido

```http
POST /api/method/future_production.reserve_sales_order_item
```

Payload:

```json
{
  "sales_order": "SO-0001",
  "sales_order_item": "abc123linha",
  "future_production_batch": "FPB-2026-00001",
  "qty": 300,
  "priority": 100
}
```

Resposta:

```json
{
  "message": {
    "reservation": "PR-2026-00001",
    "future_production_batch": "FPB-2026-00001",
    "reserved_qty": 300,
    "available_qty_after": 1700
  }
}
```

Validações:

1. Pedido existe.
2. Linha do pedido existe.
3. Produção existe.
4. Item da linha é igual ao item da produção.
5. Produção está aberta para reserva.
6. Quantidade solicitada é maior que zero.
7. Existe saldo disponível.

---

### 17.2. Reservar pedido automaticamente

```http
POST /api/method/future_production.auto_reserve_sales_order
```

Payload:

```json
{
  "sales_order": "SO-0001"
}
```

Lógica:

1. Lê itens do pedido.
2. Busca produções futuras abertas por item.
3. Ordena pela data de produção mais próxima.
4. Reserva até completar a quantidade do pedido.
5. Se necessário, divide entre produções.
6. Retorna lista de reservas criadas.

---

### 17.3. Recalcular saldo da produção

```http
POST /api/method/future_production.recalculate_batch
```

Payload:

```json
{
  "future_production_batch": "FPB-2026-00001"
}
```

Resposta:

```json
{
  "message": {
    "future_production_batch": "FPB-2026-00001",
    "planned_qty": 2000,
    "reserved_qty": 1500,
    "available_qty": 500,
    "produced_qty": 0,
    "released_qty": 0,
    "pending_release_qty": 0,
    "status": "Reservada Parcialmente"
  }
}
```

---

### 17.4. Criar Work Order

```http
POST /api/method/future_production.create_work_order
```

Payload:

```json
{
  "future_production_batch": "FPB-2026-00001"
}
```

Lógica:

1. Busca Future Production Batch.
2. Valida item.
3. Busca BOM padrão.
4. Cria Work Order.
5. Vincula Work Order à produção futura.
6. Atualiza status para Em Produção.

---

### 17.5. Liberar reservas

```http
POST /api/method/future_production.release_batch
```

Payload:

```json
{
  "future_production_batch": "FPB-2026-00001"
}
```

Lógica:

1. Busca produção futura.
2. Valida produced_qty > 0.
3. Valida batch_no preenchido.
4. Calcula saldo disponível para liberação.
5. Busca reservas pendentes.
6. Ordena por prioridade/FIFO.
7. Atualiza released_qty e pending_qty.
8. Atualiza status das reservas.
9. Atualiza campos espelho do Sales Order Item.
10. Recalcula saldo da produção.

---

### 17.6. Replanejar saldo pendente

```http
POST /api/method/future_production.replan_pending_qty
```

Payload:

```json
{
  "source_reservation": "PR-2026-00004",
  "target_future_production_batch": "FPB-2026-00002",
  "qty": 150
}
```

Lógica:

1. Busca reserva original.
2. Valida pending_qty suficiente.
3. Valida produção destino.
4. Cria nova reserva.
5. Registra vínculo/replanejamento.
6. Recalcula saldos das duas produções.

---

## 18. Client Scripts esperados

### Future Production Batch

Botões:

```text
Recalcular Saldos
Criar Work Order
Liberar Reservas
Ver Reservas
Fechar para Reserva
```

### Sales Order

Botões:

```text
Reservar em Produção Futura
Reservar Automaticamente
Ver Reservas do Pedido
```

### Production Reservation

Botões:

```text
Replanejar Pendência
Cancelar Reserva
Ver Pedido
Ver Produção
```

---

## 19. Server Scripts esperados

### Validate Future Production Batch

Valida:

- planned_qty > 0.
- item_code informado.
- target_warehouse informado.
- planned_qty >= reserved_qty.
- available_qty não negativo.

### Validate Production Reservation

Valida:

- reserved_qty > 0.
- released_qty <= reserved_qty.
- item_code igual ao item da produção.
- produção aberta para reserva.
- quantidade reservada cabe no saldo.

### On Submit Production Reservation

Executa:

- Recalcular saldo da produção futura.
- Atualizar campos do Sales Order Item.

### On Cancel Production Reservation

Executa:

- Devolver saldo.
- Recalcular produção futura.
- Atualizar Sales Order Item.

### On Update Future Production Batch

Executa:

- Recalcular available_qty.
- Recalcular pending_release_qty.
- Ajustar status.

---

## 20. Relatórios

### 20.1. Mapa de Produção Futura

Colunas:

```text
Produção
Código operacional
Produto
Data prevista
Planejado
Reservado
Disponível
Produzido
Liberado
Status
```

### 20.2. Reservas por Produção

Colunas:

```text
Produção
Pedido
Cliente
Produto
Reservado
Liberado
Pendente
Prioridade
Status
```

### 20.3. Pedidos Pendentes de Liberação

Colunas:

```text
Pedido
Cliente
Produto
Reservado
Liberado
Pendente
Produção
Data prevista
Status da produção
```

### 20.4. Risco de Produção

Critérios:

```text
Produção com data vencida e status não produzido
Produção com reservado > produzido
Produção com pendência não replanejada
Produção totalmente reservada sem Work Order
```

---

## 21. Plano de implementação

### Fase 1 — Setup estrutural via API

Entregáveis:

- Script de criação dos DocTypes.
- Script de criação dos Custom Fields.
- Validação visual no ERPNext.

### Fase 2 — Validações básicas

Entregáveis:

- Server Scripts de validação.
- Regras de saldo.
- Bloqueios de erro operacional.

### Fase 3 — Botões e telas

Entregáveis:

- Client Scripts.
- Botões operacionais.
- Fluxo guiado para usuário.

### Fase 4 — Reserva manual e automática

Entregáveis:

- Endpoint de reserva manual.
- Endpoint de reserva automática.
- Atualização do Sales Order Item.

### Fase 5 — Produção e liberação

Entregáveis:

- Botão criar Work Order.
- Botão liberar reservas.
- Regra FIFO/prioridade.
- Controle de produção parcial.

### Fase 6 — Replanejamento

Entregáveis:

- Replanejar pendência para outra produção.
- Histórico de replanejamento.
- Relatório de pendências.

### Fase 7 — Relatórios e operação

Entregáveis:

- Workspace.
- Relatórios.
- Treinamento operacional.
- Checklist de produção.

---

## 22. Critérios de aceite

1. Usuário consegue criar uma produção futura de 2.000 ampolas.
2. Usuário consegue reservar vários pedidos na mesma produção.
3. Sistema impede reserva acima do saldo disponível.
4. Sistema mostra no pedido quanto foi reservado e liberado.
5. Usuário consegue vincular Work Order à produção futura.
6. Usuário consegue informar lote real produzido.
7. Sistema libera reservas por prioridade/FIFO.
8. Produção parcial gera pedidos parcialmente liberados.
9. Saldo pendente pode ser replanejado.
10. Relatórios mostram produção, reservas e pendências corretamente.
11. Script via API cria toda a estrutura sem operação manual.
12. Script pode ser executado novamente sem duplicar campos.

---

## 23. Teste principal do MVP

### Cenário

Produção futura:

```text
FPB-2026-00001
Produto: AMP-001
Planejado: 2.000
```

Pedidos:

```text
SO-0001: 300
SO-0002: 500
SO-0003: 700
SO-0004: 500
```

Resultado esperado após reserva:

```text
reserved_qty = 2.000
available_qty = 0
status = Totalmente Reservada
```

Produção real:

```text
produced_qty = 1.850
batch_no = LOT-AMP-2026-05-20-001
```

Resultado esperado após liberação:

```text
SO-0001: 300 liberado
SO-0002: 500 liberado
SO-0003: 700 liberado
SO-0004: 350 liberado
SO-0004: 150 pendente
```

---

## 24. Segurança e permissões

### Perfis

#### System Manager

Acesso total.

#### Manufacturing Manager

Pode criar, editar, submeter, cancelar e liberar produções.

#### Manufacturing User

Pode criar e acompanhar produções.

#### Sales User

Pode visualizar produções e criar reservas, se permitido.

#### Stock User

Pode visualizar reservas e operar liberação/entrega.

### Proteções

1. Campos calculados devem ser read-only.
2. Cancelamento deve exigir permissão.
3. Overbooking deve ser restrito.
4. Scripts API devem usar token de usuário técnico.
5. Logs devem registrar criação/alteração.
6. Produção com reserva ativa não deve ser cancelada sem tratamento.

---

## 25. Versionamento recomendado

Versionar os scripts em Git:

```text
erpnext-future-production-setup/
├── README.md
├── .env.example
├── requirements.txt
├── setup_01_structure.py
├── setup_02_client_scripts.py
├── setup_03_server_scripts.py
├── setup_04_reports.py
└── docs/
    └── planejamento_modulo_reserva_producao_futura.md
```

---

## 26. Resumo final

O módulo cria uma camada de controle entre venda e produção.

A venda gera demanda.

A produção futura representa capacidade planejada.

A reserva conecta o pedido à produção.

A produção real gera lote físico.

A liberação transforma reserva em quantidade disponível para entrega.

Fluxo final:

```text
Sales Order pago
    ↓
Production Reservation
    ↓
Future Production Batch
    ↓
Work Order
    ↓
Batch real
    ↓
Liberação por pedido
    ↓
Pick List / Delivery Note
```

Regra de ouro:

```text
Não tratar produção futura como estoque.
Produção futura é promessa operacional.
Estoque real só existe após Batch/Stock Entry.
```
