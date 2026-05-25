# 11 — Manual Operacional

> Guia visual e detalhado de **uso humano dentro do ERPNext**.
> Premissa: **nada é automático**. Cada etapa tem um operador clicando em telas.
> Quando algo for opcionalmente automatizável (n8n, robô, API), isso é dito explicitamente no Anexo I.

> **Para quem é este manual**: você nunca usou o ERPNext, ou usou pouco. Não
> precisa saber programar. Cada passo é descrito como se fosse a primeira vez.

---

## Sumário

- [0. Antes de Começar (LEIA PRIMEIRO)](#0-antes-de-começar)
  - [0.1. O que é o ERPNext](#01-o-que-é-o-erpnext)
  - [0.2. Glossário rápido](#02-glossário-rápido)
  - [0.3. Como entrar no sistema (login)](#03-como-entrar-no-sistema)
  - [0.4. Conhecendo a tela inicial](#04-conhecendo-a-tela-inicial)
  - [0.5. Convenções deste manual](#05-convenções-deste-manual)
  - [0.6. Botões e atalhos que aparecem o tempo todo](#06-botões-e-atalhos)
- [1. Visão Geral do Processo](#1-visão-geral-do-processo)
- [2. Papéis e Responsabilidades](#2-papéis-e-responsabilidades)
- [3. Mapa de Telas (onde fica cada coisa)](#3-mapa-de-telas)
- [4. Cadastros Mestres (uma vez por entidade)](#4-cadastros-mestres)
- [5. Etapa A — Planejar Lote de Produção (FPB)](#5-etapa-a--planejar-lote-de-produção-fpb)
- [6. Etapa B — Emitir Pedido de Venda (com Pacientes)](#6-etapa-b--emitir-pedido-de-venda)
- [7. Etapa C — Reservar Lote](#7-etapa-c--reservar-lote)
- [8. Etapa D — Programar Produção (Work Order)](#8-etapa-d--programar-produção)
- [9. Etapa E — Registrar Produção Real (Batch + FPB)](#9-etapa-e--registrar-produção-real)
- [10. Etapa F — Liberar Reservas](#10-etapa-f--liberar-reservas)
- [11. Etapa G — Picking (Pick List)](#11-etapa-g--picking)
- [12. Etapa H — Entrega (Delivery Note)](#12-etapa-h--entrega)
- [13. Etapa I — Faturamento (Sales Invoice)](#13-etapa-i--faturamento)
- [14. Etapa J — Dispensação + Etiqueta Zebra](#14-etapa-j--dispensação)
- [15. Exceções (Replanejar, Cancelar, Sobra/Falta)](#15-exceções)
- [16. Checklist Diário do Operador](#16-checklist-diário)

---

## 0. Antes de Começar

### 0.1. O que é o ERPNext

O **ERPNext** é o sistema onde sua empresa registra tudo: clientes, pedidos,
produção, entregas, faturas. Pense nele como um **caderno gigante e
inteligente** — tudo que acontece no negócio fica anotado lá, organizado, e
o sistema **avisa** se algo não bate (ex: você tenta vender ampolas que
não existem em estoque).

Ele funciona pelo navegador (Chrome, Firefox, Edge, Safari). Não precisa
instalar nada na sua máquina — basta acessar um endereço web.

> **Endereço de acesso**: `https://erp.injemedpharma.com.br` (ou o que sua
> empresa configurou). Anote esse endereço — vai usar todos os dias.

### 0.2. Glossário rápido

Termos que aparecem o tempo todo neste manual. Decore os 6 primeiros — sem
eles, nada faz sentido.

| Termo | Significado em português claro |
|---|---|
| **FPB** (Future Production Batch) | "**Lote de Produção Futura**". É a promessa: "vamos fabricar 2.000 ampolas no dia 20/05". Existe **antes** da produção real acontecer. Permite vender hoje algo que sai daqui a 30 dias. |
| **PR** (Production Reservation) | "**Reserva de Produção**". Liga um pedido específico a um FPB. É como reservar um lugar no cinema: enquanto não chega a data, ninguém mais pode ocupar aquela cadeira. |
| **SO** (Sales Order) | "**Pedido de Venda**". O documento que registra: cliente X comprou Y ampolas por Z reais. |
| **Customer** | "**Cliente comprador**" — quem paga a nota fiscal. Pode ser PJ (CNPJ) ou PF (CPF). |
| **Prescriber** | "**Médico Prescritor**" — profissional de saúde com conselho (CRM, CRO, CRF, etc) que assina a prescrição. **Sempre pessoa física**. Cadastro diferente do Customer. |
| **Conselho Profissional** | Registro do prescritor: CRM (médico), CRO (dentista), CRF (farmacêutico), CRBM (biomédico), CRN (nutricionista), etc. |
| **Batch** | "**Lote físico real**". Quando a produção termina e as ampolas existem de verdade, esse é o número/código que identifica aquele grupo de ampolas (data de fabricação, data de validade). |
| **Item** | Qualquer **produto** cadastrado no sistema (uma ampola, uma caixa, uma matéria-prima). Identificado por um código único (ex: TIR00060). |
| **DocType** | Tipo de documento no ERPNext. Cliente é um DocType. Pedido é outro. Lote é outro. Não se assuste com o nome técnico — sempre que aparecer, leia como "tipo de cadastro". |
| **Submit / Submeter** | É como "**assinar e enviar**". Antes de Submit, o documento é só um rascunho que pode ser apagado. Depois de Submit, ele vira oficial — não pode mais ser editado livremente, só cancelado. **Equivale a "fechar o pedido" no caixa**. |
| **Save / Salvar** | Salva o rascunho. Não é o mesmo que Submit. Você pode Save 100 vezes e ainda editar tudo. Mas só depois do Submit é que o sistema "aceita" o documento como real. |
| **Cancel** | Desfaz um Submit. O documento fica registrado mas com status "Cancelado" — vira só histórico. |
| **Workspace** | "**Área de trabalho**". É o painel de atalhos no menu lateral esquerdo. Tem um Workspace chamado "Produção Futura" com tudo do nosso processo. |
| **Field / Campo** | Cada caixinha de preenchimento numa tela (Nome, CPF, Quantidade…). |
| **Link Field** | Campo que conecta com outro cadastro. Ex: no Pedido, o campo "Cliente" é um Link Field — você não digita o nome, você escolhe um cliente já cadastrado. |
| **Child Table / Tabela Filho** | Tabela dentro de um documento. Ex: dentro do Pedido tem a tabela de Itens (cada linha é um produto) e a tabela de Pacientes (cada linha é uma pessoa). |
| **Warehouse / Depósito** | Local físico onde as ampolas ficam guardadas (ex: "Produtos Acabados - I"). |
| **BOM** (Bill of Materials) | "**Lista de Materiais**". Receita do que precisa pra fabricar 1 ampola (matérias-primas, embalagem, etc). |
| **Work Order** | "**Ordem de Produção**". Documento que autoriza começar a fabricar. |
| **Pick List** | "**Lista de Separação**". Diz pro pessoal da expedição quais ampolas separar (de qual lote, qual depósito). |
| **Delivery Note** | "**Nota de Entrega**". Confirma que as ampolas saíram do depósito. |
| **Sales Invoice** | "**Fatura/Nota Fiscal**". Documento de cobrança. Gera o lançamento contábil. |
| **Payment Entry** | "**Recebimento**". Registra que o cliente pagou. |

### 0.3. Como entrar no sistema

1. Abra o navegador (Chrome, Edge, etc.)
2. Digite o endereço: `https://erp.injemedpharma.com.br` (ou o seu)
3. Aparece a tela de login:

```
   ┌─────────────────────────────────────┐
   │           Login ERPNext              │
   ├─────────────────────────────────────┤
   │                                      │
   │  E-mail:    [_________________]      │
   │                                      │
   │  Senha:     [_________________]      │
   │                                      │
   │            [ Entrar ]                │
   │                                      │
   │  Esqueci minha senha                 │
   └─────────────────────────────────────┘
```

4. Coloque seu **e-mail corporativo** + **senha**
5. Clique **Entrar**

> **Primeira vez?** Peça o login pro administrador (TI/RH). Ele cria o usuário e te manda link pra criar senha.

> **Esqueci a senha**: clique no link "Esqueci minha senha" — sistema envia
> e-mail com instruções pra resetar.

### 0.4. Conhecendo a tela inicial

Depois de logar, você vê algo assim:

```
┌────────────────────────────────────────────────────────────────────────┐
│ ☰  ERPNext        🔍 Buscar...                            🔔  👤 Você  │ ← Barra superior
├──────────┬─────────────────────────────────────────────────────────────┤
│          │                                                             │
│  Menu    │              ÁREA PRINCIPAL                                  │
│  lateral │              (muda conforme você navega)                     │
│          │                                                             │
│  • Home  │                                                             │
│  • Sell  │                                                             │
│  • Stock │                                                             │
│  • ...   │                                                             │
│          │                                                             │
└──────────┴─────────────────────────────────────────────────────────────┘
```

**O que cada parte faz**:

| Elemento | Função |
|---|---|
| 🔍 Buscar (topo) | **Procura qualquer coisa no sistema**. Digite "TIR00060" e ele te leva pro item. Digite "Maria" e mostra clientes e pacientes com esse nome. |
| 🔔 Notificações | Avisos do sistema (ex: alguém mencionou você num comentário). |
| 👤 Seu avatar | Menu de conta — sair, mudar senha, configurações pessoais. |
| ☰ Menu lateral | Lista de áreas: Vendas, Estoque, Produção, etc. Clique pra expandir. |

> **Dica**: use a **busca do topo** o tempo todo. É a forma mais rápida de
> abrir qualquer documento, item, cliente ou paciente.

### 0.5. Convenções deste manual

Quando você ler:

| Notação | Significado |
|---|---|
| *Selling → Sales Order → + New* | Clique no menu "Selling", depois em "Sales Order", depois no botão "+ New" |
| **Save** | Clique no botão "Save" (normalmente no canto superior direito) |
| **Submit** | Clique no botão "Submit" (aparece depois de Save) |
| `TIR00060` | Texto literal pra digitar exatamente assim |
| `<algo>` | Você substitui pelo valor real (ex: `<seu nome>` vira "Maria") |
| ☑ | Checkbox que precisa estar marcado |
| ☐ | Checkbox que pode ficar desmarcado |
| ✓ | Validação que deu certo |
| ⚠ | Atenção — leia com cuidado |

### 0.6. Botões e atalhos que aparecem o tempo todo

Toda tela de cadastro/documento no ERPNext tem alguns botões padrão:

```
┌──────────────────────────────────────────────────────────────────┐
│ < Voltar           Documento ABC-123                             │
│                                                                  │
│                       [ Salvar ]  [ Submit ]  [ Menu ▼ ]         │ ← Topo direito
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Campo 1: [________________]                                    │
│   Campo 2: [________________]                                    │
│                                                                  │
│   ...                                                            │
└──────────────────────────────────────────────────────────────────┘
```

| Botão | O que faz | Atalho de teclado |
|---|---|---|
| **Salvar / Save** | Salva rascunho. Ainda editável. | `Ctrl + S` |
| **Submit** | Oficializa o documento. Aparece depois de Save. | `Ctrl + Shift + S` |
| **Cancel** | Anula um documento já submetido. Aparece no menu ▼ depois do Submit. | — |
| **Amend** | Cria nova versão a partir de um documento cancelado. | — |
| **Print** | Imprime/gera PDF do documento. | — |
| **Menu ▼** | Outras ações (Print, Duplicate, Delete, etc). | — |
| **+ New** | Cria novo documento daquele tipo. | — |
| **+ Add Row** (dentro de tabelas) | Adiciona uma linha numa tabela filho. | — |

**Ações sempre disponíveis em listas**:

- **Filtros** (topo da lista): clique em "Filter" pra restringir o que aparece
- **Colunas** (botão ⚙️): escolhe quais colunas mostrar
- **Exportar**: baixa Excel/CSV do que está filtrado

---

## 1. Visão Geral do Processo

### Por que esse processo existe?

A empresa fabrica ampolas em **lotes grandes** (ex: 2.000 ampolas de uma vez)
que serão divididas entre **vários pedidos de vários clientes** ao longo do
mês. Sem um sistema que faça isso direito, acontece:

- **Vender o que não tem** — operador promete entrega mas não sabia que o lote já estava todo reservado
- **Reservar a mesma coisa pra mais de um cliente** — caos quando chegar a hora de entregar
- **Não saber quem vai receber o quê** — paciente certo, lote errado, validade vencendo
- **Confundir estoque real com promessa de produção** — vendedor olha "1000 ampolas disponíveis" achando que é estoque, mas é só plano

O processo abaixo resolve isso. Cada etapa tem responsável claro. O sistema
**bloqueia** ações erradas (ex: você tenta reservar 3.000 num lote de 2.000 — ele recusa).

### O fluxo completo (em uma imagem)

```
   COMERCIAL          PRODUÇÃO            EXPEDIÇÃO          FARMÁCIA
   ─────────          ─────────           ─────────          ─────────

   Cadastros          (antes: criar
   (Cliente,           FPB planejado)
   Paciente)
      │                                                      
      ▼                                                      
   [B] Sales Order  ──►  [A] FPB existe                      
   (com pacientes)         (saldo > 0)                       
      │                       │                              
      ▼                       │                              
   [C] Reserva  ──────────────┘                              
   (PR criada,                                               
    saldo do FPB cai)                                        
      │                                                      
      └──────────►  [D] Work Order                           
                       │                                     
                       ▼                                     
                    [E] Produção real                        
                       (Batch + produced_qty)                
                       │                                     
                       ▼                                     
                    [F] Liberar (FIFO)                       
                       │                                     
                       └────────►  [G] Pick List             
                                      │                      
                                      ▼                      
                                   [H] Delivery Note ───►   [J] Dispensação
                                      │                       (etiqueta Zebra)
                                      ▼                      
                                   [I] Sales Invoice         
                                      (Fatura/NF)            
                                      │
                                      ▼
                                   Payment Entry
                                   (Recebimento)
```

### Como ler esse fluxo

- Cada **letra entre colchetes** ([A], [B], etc) é uma **etapa numerada** neste manual
- A **coluna** mostra qual setor cuida da etapa
- **Setas para baixo** = ordem do tempo
- **Setas horizontais** = a coisa "atravessa" pro próximo setor
- Tudo começa com **cadastros** (etapa 4) que são feitos uma única vez por entidade

### Tempo aproximado por etapa

| Etapa | Quem | Duração típica |
|---|---|---|
| 4. Cadastrar cliente/paciente | Comercial | 2-5 min por cadastro |
| A. Planejar FPB | Planejamento | 5 min |
| B. Emitir Pedido | Comercial | 5-10 min |
| C. Reservar | Comercial | 1 min |
| D. Work Order | Planejamento | 2 min |
| E. Produção real | Produção | varia — depende do batch físico |
| F. Liberar | Supervisor | 1 min |
| G. Pick List | Expedição | 5-15 min (depende da separação física) |
| H. Delivery Note | Expedição | 2 min |
| I. Faturamento | Financeiro | 5 min |
| J. Dispensação | Farmácia | 3-5 min por paciente |

---

## 2. Papéis e Responsabilidades

Quem faz o quê, e quais seções deste manual leem com prioridade.

| Papel | Responsabilidade principal | Telas-chave | Leia com prioridade |
|---|---|---|---|
| **Vendedor / Comercial** | Cadastrar cliente, médico prescritor e paciente, emitir pedido, reservar lote | Customer, Prescriber, Patient, Sales Order | Seções 4, 6, 7 |
| **Planejador de Produção** | Criar lote planejado (FPB), criar Work Order, acompanhar saldo | Future Production Batch, Work Order, BOM | Seções 5, 8 |
| **Operador de Produção** | Registrar o lote físico real e quanto saiu da produção | Batch, Future Production Batch, Stock Entry | Seção 9 |
| **Supervisor de Produção** | Acionar a liberação FIFO das reservas | Future Production Batch, Production Reservation | Seção 10, 15 |
| **Expedição / Logística** | Separar e entregar | Pick List, Delivery Note | Seções 11, 12 |
| **Financeiro** | Emitir nota fiscal, registrar recebimento | Sales Invoice, Payment Entry | Seção 13 |
| **Farmacêutico** | Dispensar ampola, imprimir etiqueta paciente | Delivery Note (ou Dispensation) | Seção 14 |
| **Gestor / Auditoria** | Acompanhar relatórios, identificar pendências | Reports, Workspace "Produção Futura" | Seção 16 |

### Quem precisa de qual permissão de acesso

> Se uma tela não aparece pra você, **provavelmente é permissão**. Avise o
> TI/administrador. Os papéis acima precisam:

- **Vendedor**: Sales User + Customer + Patient (criar/editar)
- **Planejador**: Manufacturing User + Future Production Batch (criar/submeter)
- **Operador**: Stock User + Batch (criar) + Future Production Batch (editar)
- **Supervisor**: Manufacturing Manager
- **Expedição**: Stock User + Pick List + Delivery Note
- **Financeiro**: Accounts User + Sales Invoice + Payment Entry
- **Farmacêutico**: papel "Dispensador" (a definir quando módulo for criado)
- **Gestor**: System Manager OU role customizada read-only

---

## 3. Mapa de Telas

### Onde fica cada coisa no menu lateral

Depois de logar, o **menu lateral esquerdo** tem várias áreas. Cada área
agrupa as telas (DocTypes) que pertencem a aquele setor.

```
Menu lateral do ERPNext (clique pra expandir cada área)
│
├─ 🏠 Home                              (tela inicial, atalhos)
│
├─ 💰 Selling                            (área comercial)
│   ├─ Customer                          ← cadastro de cliente
│   ├─ Sales Order                       ← pedido de venda
│   ├─ Quotation                          ← orçamento (opcional)
│   └─ Sales Person                       ← vendedores
│
├─ 📦 Stock                              (área de estoque)
│   ├─ Item                              ← catálogo de produtos
│   ├─ Batch                             ← lote físico real
│   ├─ Stock Entry                       ← movimentação de estoque
│   ├─ Pick List                         ← lista de separação
│   ├─ Delivery Note                     ← nota de entrega
│   └─ Warehouse                         ← depósitos
│
├─ 🏭 Manufacturing                       (área de produção)
│   ├─ Work Order                        ← ordem de produção
│   ├─ BOM                               ← lista de materiais
│   └─ Production Plan                   ← plano de produção
│
├─ 💵 Accounts                            (área financeira)
│   ├─ Sales Invoice                     ← nota fiscal/fatura
│   ├─ Payment Entry                     ← recebimento
│   └─ Journal Entry                     ← lançamento contábil
│
└─ ⭐ Produção Futura                     ← Workspace customizado (importante!)
    ├─ Lote de Produção Futura           ← FPB (nosso DocType custom)
    ├─ Reserva de Produção               ← PR (nosso DocType custom)
    ├─ Paciente                          ← Patient (nosso DocType custom)
    ├─ Médico Prescritor                 ← Prescriber (a construir)
    └─ Relatórios
        ├─ Mapa de Produção              ← visão geral de todos os lotes
        ├─ Saldo por Lote                ← quanto disponível por FPB
        ├─ Reservas por Pedido           ← detalhe de cada SO
        └─ Pendências de Liberação       ← sobras pra replanejar
```

### Como abrir uma tela específica

**3 caminhos** que sempre funcionam:

**Caminho 1 — Menu lateral**:
1. Clique na área (ex: "Selling")
2. Clique no item (ex: "Sales Order")
3. Abre a **lista** de todos os pedidos

**Caminho 2 — Busca rápida (mais rápido)**:
1. No topo, na barra de busca, digite o nome do DocType ou do registro
2. Ex: digite "Sales Order" → mostra atalho pra lista
3. Ex: digite "SAL-ORD-2026-00031" → abre o pedido específico

**Caminho 3 — URL direta** (se você sabe a URL):
- `https://seu-erpnext.com.br/app/sales-order` → lista de pedidos
- `https://seu-erpnext.com.br/app/sales-order/new` → novo pedido
- `https://seu-erpnext.com.br/app/sales-order/SAL-ORD-2026-00031` → pedido específico

### Diferença entre Lista e Documento

```
LISTA (várias linhas)              DOCUMENTO (1 cadastro completo)
─────────────────                  ──────────────────────────────
+ New  Filter  Export              < Voltar     Save  Submit
                                                                
☐ Nome     Status     Data         Nome:    [____________]
☐ ABC-001  Aberto    01/05         Status:  [____________]
☐ ABC-002  Fechado   02/05         Data:    [____________]
☐ ABC-003  Aberto    03/05         ...
```

- **Lista**: visão geral, várias linhas. Clique em qualquer linha pra abrir o documento.
- **Documento**: detalhe completo de 1 cadastro. Aqui você edita os campos.

---

## 4. Cadastros Mestres

> "Cadastros mestres" são informações que você cadastra **uma vez** e
> **reusa** depois. Cliente é mestre. Médico Prescritor é mestre. Paciente é
> mestre. Item (produto) é mestre. Você não cadastra do zero toda vez que faz
> pedido — você escolhe o já existente.

> **Antes de cadastrar**, sempre **busque primeiro**: a pessoa já pode estar
> no sistema. Cadastros duplicados criam confusão (dois "Dr. José" diferentes,
> qual usar?).

### 4.0. Panorama: 4 entidades distintas

Antes de mergulhar em cada cadastro, entenda que o sistema trabalha com
**4 entidades separadas** que se conectam num pedido:

```
   ┌─────────────────────────────────┐
   │ 1. CUSTOMER (quem PAGA)         │
   │                                 │
   │ Pode ser:                        │
   │  • Empresa (PJ, CNPJ)            │
   │    Ex: Clínica X, Hospital Y     │
   │  • Pessoa física (PF, CPF)       │
   │    Ex: médico que compra direto  │
   └──────────────┬──────────────────┘
                  │ paga
                  ▼
   ┌─────────────────────────────────────────────────┐
   │ 2. PRESCRIBER (quem PRESCREVE)                  │
   │                                                  │
   │ Sempre pessoa física com conselho profissional:  │
   │  • CPF                                            │
   │  • Tipo Conselho: CRM, CRO, CRF, CRBM/CRN, etc.  │
   │  • Número do conselho                             │
   │  • UF do conselho                                 │
   │                                                  │
   │ ⚠ É um cadastro INDEPENDENTE do Customer.        │
   │ Mesmo se o médico compra direto, ele tem:        │
   │   - 1 cadastro como Customer (Individual)         │
   │   - 1 cadastro como Prescriber (com CRM)          │
   └──────────────┬──────────────────────────────────┘
                  │ prescreve para
                  ▼
   ┌─────────────────────────────────┐
   │ 3. PATIENT (quem RECEBE)        │
   │                                 │
   │  • CPF                           │
   │  • Nome                          │
   │  • Contato, endereço             │
   │  • Médico padrão (Prescriber)    │
   └──────────────┬──────────────────┘
                  │ consome
                  ▼
   ┌─────────────────────────────────┐
   │ 4. ITEM (o quê)                 │
   │                                 │
   │  • TIR00060 — Tirzepatida...     │
   │  • Com batch + validade          │
   └─────────────────────────────────┘
```

#### Como essas 4 entidades aparecem no Pedido de Venda (SO)

```
   Sales Order
   ├─ customer:    Customer (cabeçalho — quem paga a NF)
   ├─ items[]:     Item + qty + preço
   └─ fp_patients[]:  cada linha tem...
       ├─ patient:     Patient
       ├─ prescriber:  Prescriber (pode ser DIFERENTE por linha!)
       ├─ item_code:   Item
       └─ qty:         quantidade
```

#### Cenários reais que esse modelo cobre

| Cenário | Customer | Prescriber | Patient |
|---|---|---|---|
| Clínica compra, 1 médico prescreve todos os pacientes | Clínica XYZ Ltda (CNPJ) | Dr. José (CRM-SP) | Maria, João, Ana |
| Médico compra direto pra si mesmo prescrever | Dr. José (Individual, CPF) | Dr. José (CRM-SP) — outro cadastro | Maria |
| Hospital com vários médicos no mesmo pedido | Hospital ABC (CNPJ) | Dr. José pra Maria, Dra. Ana pra João | Maria, João |
| Farmácia comprando pra estoque pra múltiplos médicos | Farmácia Bem-Estar (CNPJ) | varia por paciente | varia |

> **Decisão**: Customer e Prescriber **sempre** são cadastros separados,
> mesmo quando é a mesma pessoa física. Isso garante:
> - Compras anônimas (PJ) sem médico atrelado funcionam
> - Histórico de prescrição do médico não polui dados de compra
> - Auditoria CRM/conselho separa do financeiro

#### Ordem recomendada de cadastro

1. **Customer** (PJ ou PF) — quem paga
2. **Prescriber** — médico/dentista/farmacêutico que prescreve
3. **Patient** — paciente final (linka o Prescriber padrão)
4. **Item** (TI cadastra uma vez, comercial reusa)

> **Status do módulo Prescriber**: ⚠ DocType ainda não existe no sistema.
> Hoje o sistema usa `prescribing_doctor` no Patient apontando pra Customer
> (modelo antigo, simplificado). A construção do DocType `Prescriber` está
> na fila de implementação. Enquanto não existe, **continue cadastrando o
> médico como Customer Individual** (modelo simplificado). Quando o
> Prescriber for criado, vai ter migração automática.

### 4.1. Cadastro de Cliente (Customer)

#### O que é?

Cliente = quem **compra** as ampolas e **paga a nota fiscal**. Pode ser:

- **Pessoa Jurídica (PJ — empresa)**: clínica, hospital, farmácia, distribuidor — identificada pelo **CNPJ**
- **Pessoa Física (PF)**: um médico que compra direto pra prescrever — identificada pelo **CPF**

> ⚠ **Importante**: Customer é só o **comprador/pagador**. Mesmo quando é
> uma pessoa física que também prescreve (médico que compra pra si mesmo),
> esse cadastro de Customer **não substitui** o cadastro de Prescriber
> (seção 4.2). São registros diferentes pra finalidades diferentes.

#### Quando cadastrar?

- Antes de fazer o primeiro pedido pra essa pessoa/empresa
- Quando receber um lead novo do comercial

#### Quem faz?

Comercial (vendedor que está atendendo)

#### Passo a passo

**1.** No menu lateral, clique em **Selling** → **Customer**

Você vê a lista de todos os clientes cadastrados:

```
┌─────────────────────────────────────────────────────────────┐
│ Customer                                  + New   Filter     │
├─────────────────────────────────────────────────────────────┤
│ ☐ Nome                       Tipo       Grupo                │
│ ☐ Dr. Antonio Pereira        Individual Comercial            │
│ ☐ Clínica São Paulo Ltda     Company    Comercial            │
│ ☐ ...                                                        │
└─────────────────────────────────────────────────────────────┘
```

**2.** **PRIMEIRO**: use a busca no topo. Digite parte do nome (ex: "Antonio"). Se aparecer, **NÃO cadastre de novo** — clique no existente.

**3.** Se realmente não existe, clique **+ New** (canto superior direito)

**4.** Aparece a tela de novo cliente. Preencha conforme o tipo:

#### Se for Pessoa Jurídica (empresa — CNPJ)

```
┌──────────────────────────────────────────────────────────────┐
│  NEW CUSTOMER (Pessoa Jurídica)                Save           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Customer Name *: [Clínica São Paulo Ltda____________]        │
│  ← Razão social. Como sai na nota fiscal.                    │
│                                                              │
│  Customer Type:   ○ Individual  ◉ Company                    │
│  ← Empresa = Company.                                        │
│                                                              │
│  Customer Group *: [Comercial                       ▼]       │
│  Territory *:      [Brazil                           ▼]      │
│                                                              │
│  Tax Category:     [Regime Geral / Simples / ...     ▼]      │
│  ← Importante pra cálculo de imposto na NF.                  │
│                                                              │
│  Default Currency: [BRL                             ▼]       │
│                                                              │
│  ── More Info ── (role pra baixo)                            │
│                                                              │
│  Tax ID (CNPJ) *:  [12.345.678/0001-90]                       │
│  ← CNPJ da empresa. Pode digitar com ou sem máscara.         │
│                                                              │
│  Inscrição Estadual:[________________]                        │
│  Inscrição Municipal:[________________]                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### Se for Pessoa Física (médico que compra direto — CPF)

```
┌──────────────────────────────────────────────────────────────┐
│  NEW CUSTOMER (Pessoa Física)                  Save           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Customer Name *: [Dr. José da Silva__________]               │
│  ← Nome completo.                                            │
│                                                              │
│  Customer Type:   ◉ Individual  ○ Company                    │
│                                                              │
│  Customer Group *: [Comercial                       ▼]       │
│  Territory *:      [Brazil                           ▼]      │
│                                                              │
│  Default Currency: [BRL                             ▼]       │
│                                                              │
│  ── More Info ──                                             │
│                                                              │
│  Tax ID (CPF) *:   [111.444.777-35]                           │
│  ← CPF da pessoa. Pode digitar com ou sem máscara.           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

> **Regras gerais**:
> - Customer Group: SEMPRE **Comercial**. ⚠ NÃO USE "All Customer Groups".
> - Territory: SEMPRE **Brazil**. ⚠ NÃO USE "All Territories".
> - Currency: SEMPRE **BRL**.

**5.** Role para baixo. Há outras seções:

- **Contact Info** (telefone, e-mail) — preencha pelo menos 1 contato
- **Address** (endereço de cobrança) — preencha CEP, rua, número, cidade, UF

> **Atenção**: e-mail e telefone são opcionais MAS muito úteis pra enviar
> nota fiscal e comunicação. Sempre que possível, preencha.

**6.** No topo direito, clique **Save**

**7.** ✓ **Sucesso**: o cliente foi criado. Aparece um número/código tipo
`CUST-2026-00045` ou simplesmente o próprio nome.

#### Erros comuns e o que fazer

| Erro | Causa | Solução |
|---|---|---|
| `LinkValidationError: Customer Group All Customer Groups` | Você escolheu o grupo errado | Volte ao campo "Customer Group" e escolha **Comercial** |
| `LinkValidationError: Territory` | Mesma coisa pra Território | Escolha **Brazil** |
| `Mandatory field: Customer Name` | Esqueceu o nome | Preencha |
| Cliente duplicado | Você cadastrou alguém que já existia | Use o existente, apague o novo (Menu ▼ → Delete) |

### 4.2. Cadastro de Médico Prescritor (Prescriber)

> ⚠ **Status atual**: O DocType `Prescriber` está **planejado mas ainda não
> foi construído** no sistema. Esta seção descreve como vai funcionar quando
> implementado. Enquanto não existe, **continue usando Customer Individual**
> com nome do médico (modelo simplificado atual). Quando o `Prescriber` for
> criado, haverá script de migração automática.

#### O que é?

Prescriber = **profissional habilitado a prescrever** medicamentos. Pessoa
física obrigatoriamente, com **registro em conselho profissional** válido.

**Não confunda com Customer**:
- Customer paga a NF (pode ser empresa ou PF)
- Prescriber assina a prescrição (sempre PF com conselho)

#### Quem pode ser Prescriber?

Profissionais com habilitação legal pra prescrever medicamentos
controlados/biológicos no Brasil:

| Conselho | Profissão | Sigla típica |
|---|---|---|
| **CRM** | Médico | CRM-SP 12345 |
| **CRO** | Dentista (Cirurgião-Dentista) | CRO-SP 12345 |
| **CRF** | Farmacêutico (em casos previstos em lei) | CRF-SP 12345 |
| **CRBM / CRN / Outros** | Biomédico, Nutricionista, outros — quando a lei permitir | varia |

#### Quando cadastrar?

- Antes de cadastrar o primeiro paciente desse médico
- Quando receber a primeira prescrição

#### Quem faz?

Comercial (que recebe a prescrição)

#### Passo a passo

**1.** Menu → **Produção Futura** → **Médico Prescritor (Prescriber)**

**2.** **PRIMEIRO**: busque por CPF ou nome. Se existir, reuse.

**3.** **+ New**

**4.** Preencha:

```
┌──────────────────────────────────────────────────────────────┐
│  NEW PRESCRIBER                                Save           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ── Identificação ──                                          │
│                                                              │
│  Nome *:               [Dr. José da Silva____________]        │
│  ← Nome completo como aparece no conselho.                   │
│                                                              │
│  CPF *:                [123.456.789-09]                       │
│  ← 11 dígitos válidos. Único no sistema.                     │
│                                                              │
│  Data de Nascimento:   [DD/MM/AAAA]   (opcional)              │
│  Gênero:               ○ Masculino ○ Feminino ○ Outro         │
│                                                              │
│  ── Conselho Profissional ──                                  │
│                                                              │
│  Tipo de Conselho *:   ◉ CRM (Médico)                        │
│                        ○ CRO (Dentista)                      │
│                        ○ CRF (Farmacêutico)                  │
│                        ○ CRBM (Biomédico)                    │
│                        ○ CRN (Nutricionista)                 │
│                        ○ Outro                                │
│                                                              │
│  Número do Conselho *: [12345]                                │
│  ← Só números, sem prefixo CRM.                              │
│                                                              │
│  UF do Conselho *:     [SP ▼]                                 │
│  ← Estado onde o conselho foi emitido (SP, RJ, MG, ...).     │
│                                                              │
│  Outro Conselho (se "Outro"):                                │
│  [_______________]                                            │
│  ← Aparece só se Tipo = "Outro". Ex: "CFFa" (Fonoaudiologia).│
│                                                              │
│  Status do Conselho:   ● Ativo  ○ Suspenso  ○ Cassado        │
│                                                              │
│  Especialidade:        [Endocrinologia____]   (opcional)      │
│                                                              │
│  ── Contato ──                                                │
│                                                              │
│  Celular:              [(11) 99999-0000]                      │
│  E-mail Profissional:  [jose@clinica.com]                     │
│                                                              │
│  ── Endereço Profissional ──                                  │
│                                                              │
│  Consultório / Clínica:[Clínica São Paulo Ltda]               │
│  Customer Vinculado:   [Clínica São Paulo Ltda     ▼]        │
│  ← Opcional. Se o médico trabalha numa empresa que já é      │
│    cliente, escolha aqui. Facilita relatórios.               │
│                                                              │
│  CEP:                  [01310-100]                            │
│  Rua/Número/Bairro/Cidade/UF                                 │
│                                                              │
│  ── Observações ──                                            │
│  [_____________________________________________]              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**5.** Clique **Save**

**6.** ✓ **Sucesso**: gera código `PRES-2026-#####` (ex: `PRES-2026-00007`).

#### Validações automáticas

- **CPF**: 11 dígitos válidos, único no sistema
- **Número do conselho**: combinação `(tipo + número + UF)` deve ser única
  (não pode ter 2 PRES-2026 com CRM-SP-12345)
- **Status "Cassado"**: bloqueia uso em novas prescrições (sistema avisa)

#### Médico que também compra direto

Caso especial: Dr. José prescreve **e** compra direto pra si. Você precisa de
**2 cadastros distintos**:

```
   ┌────────────────────────────────────┐
   │ Customer Dr. José (Individual, CPF)│
   │   - Tax ID: 123.456.789-09          │
   │   - Pra emitir NF                   │
   └────────────────────────────────────┘
   
   ┌────────────────────────────────────┐
   │ Prescriber Dr. José (CPF + CRM)    │
   │   - CPF: 123.456.789-09             │
   │   - CRM-SP 12345                    │
   │   - Pra constar em prescrições     │
   └────────────────────────────────────┘
```

**Por que 2 cadastros?**
- Customer pode ser PJ (empresa não tem CRM)
- Prescriber é dado regulatório (ANVISA, conselho)
- Histórico de compras ≠ histórico de prescrições

**Não é trabalho duplicado** — você cadastra 1 vez cada e reusa pra sempre.

#### Atualizar dados do médico

Mudou clínica? Mudou número de telefone? **Edite o Prescriber existente** (não
crie novo). Sistema mantém histórico (`track_changes=1`).

> ⚠ **Não edite** Tipo/Número/UF do conselho a menos que tenha sido erro de
> digitação. Mudança real de inscrição (transferência de UF, por exemplo)
> normalmente vira novo registro pra preservar auditoria. Avise gestor.

#### Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| `CPF já cadastrado como Prescriber: PRES-2026-00007` | Tentou duplicar | Use o existente |
| `Conselho CRM-SP-12345 já existe (PRES-2026-00007)` | Outro Prescriber tem mesmo conselho | Use o existente (ou corrija o número) |
| `CPF inválido` | < 11 dígitos | Confira CPF |
| Status "Cassado" e estou criando pedido | Conselho foi cassado | Não pode prescrever. Use outro médico ou avise jurídico. |

### 4.3. Cadastro de Paciente (Patient)

#### O que é?

Paciente = a **pessoa que vai receber** a ampola. Pode ser diferente do
cliente: o cliente é o médico que compra, mas o paciente é quem usa o
medicamento.

Cada ampola, no final, fica vinculada a 1 paciente específico (rastreabilidade
exigida pra medicamento controlado).

#### Quando cadastrar?

- Quando o médico passa a prescrição pro vendedor
- Antes de criar o Sales Order (Pedido)

#### Quem faz?

Comercial (vendedor que recebe a prescrição)

#### Passo a passo

**1.** No menu lateral, abra **Produção Futura** (Workspace customizado)

**2.** Clique em **Paciente**

**3.** **PRIMEIRO**: na busca, procure pelo **CPF** ou **nome**. Se já existe, use.

**4.** Se não existe, **+ New**

**5.** Preencha:

```
┌──────────────────────────────────────────────────────────────┐
│  NEW PATIENT                                      Save        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Nome do Paciente *:    [Maria Aparecida Silva________]      │
│  ← Nome completo, como sai na etiqueta.                      │
│                                                              │
│  CPF:                   [111.444.777-35_______________]      │
│  ← Pode digitar com ou sem pontos. Sistema limpa.            │
│  ⚠ Precisa ter 11 dígitos válidos. Não pode ser "11111…".    │
│                                                              │
│  RG:                    [_______________]                     │
│  ← Opcional.                                                 │
│                                                              │
│  Data de Nascimento:    [DD/MM/AAAA]                          │
│                                                              │
│  Gênero:                ◉ Feminino ○ Masculino ○ Outro       │
│                                                              │
│  Médico Prescritor *:   [PRES-2026-00007 — Dr. José  ▼]      │
│  ← Link Field. Procura na lista de Prescribers (seção 4.2).  │
│  ⚠ Médico padrão deste paciente. Pode ser sobrescrito em     │
│    cada Sales Order (linha por linha em fp_patients).         │
│                                                              │
│  ── Contato ──                                                │
│  Celular:               [(11) 99999-0001]                     │
│  Telefone:              [(11) 3000-0000]                      │
│  E-mail:                [maria@exemplo.com]                   │
│                                                              │
│  ── Endereço ──                                               │
│  CEP:                   [01310-100]                           │
│  Rua/Logradouro:        [Av. Paulista]                        │
│  Número:                [1500]                                │
│  Complemento:           [Apto 10]                             │
│  Bairro:                [Bela Vista]                          │
│  Cidade:                [São Paulo]                           │
│  UF:                    [SP]                                  │
│  País:                  [Brazil]    (padrão)                  │
│                                                              │
│  Observações:           [_______________________________]     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**6.** Clique **Save**

**7.** ✓ **Sucesso**: gera código no padrão `PAC-2026-#####` (ex: `PAC-2026-00014`).

> **Anote esse código**. Você vai precisar dele ao montar o Sales Order
> (etapa 6). Ou usa a busca, mas tendo o código é mais rápido.

#### Paciente recorrente (mesma pessoa volta depois)

**Pergunta comum**: "O médico mandou o mesmo paciente hoje. E daqui a 3 meses
ele vai voltar. São dois cadastros ou um só?"

**Resposta**: **UM SÓ cadastro**. Paciente é cadastro mestre permanente. Cria
**uma vez na vida** e reusa em **todas** as compras futuras dessa pessoa.

#### Como funciona na prática

```
   ┌─────────────────────────────────────────────────────────┐
   │                                                         │
   │   Visita 1 — Hoje (2026-05-17)                          │
   │                                                         │
   │   Médico manda paciente Maria pela primeira vez         │
   │      │                                                  │
   │      ▼                                                  │
   │   Vendedor:                                             │
   │     - Busca CPF de Maria → não acha                     │
   │     - Cadastra Patient                                  │
   │     - Sistema gera: PAC-2026-00014                      │
   │     - Cria Sales Order SAL-ORD-2026-00031               │
   │       (fp_patients aponta PAC-2026-00014)               │
   │                                                         │
   └─────────────────────────────────────────────────────────┘
                              │
                              │  3 meses depois...
                              ▼
   ┌─────────────────────────────────────────────────────────┐
   │                                                         │
   │   Visita 2 — Daqui a 3 meses (2026-08-17)               │
   │                                                         │
   │   Médico manda Maria de novo (mesmo paciente)           │
   │      │                                                  │
   │      ▼                                                  │
   │   Vendedor:                                             │
   │     - Busca CPF de Maria → ACHA PAC-2026-00014          │
   │     - REUSA o cadastro existente                        │
   │     - NÃO cria novo Patient                             │
   │     - Cria NOVO Sales Order SAL-ORD-2026-00089          │
   │       (fp_patients aponta MESMO PAC-2026-00014)         │
   │                                                         │
   └─────────────────────────────────────────────────────────┘
```

#### Regra: CPF é único

O sistema **força** essa unicidade pelo CPF. Se você tentar cadastrar de novo
um CPF que já existe, dá erro:

```
   ⚠ ERRO: DuplicateEntryError
   CPF "11144477735" já existe (Patient: PAC-2026-00014).
```

#### O que MUDA entre uma visita e outra

- **Sales Order**: NOVO a cada compra (transacional)
- **Reservas (PR)**: NOVAS a cada compra
- **Quantidade na linha `fp_patients`**: pode mudar (3 ampolas agora, 5 daqui 3 meses)
- **Lote físico (Batch)**: provavelmente diferente (validade nova)

#### O que NÃO muda

- **Patient (cadastro mestre)**: o mesmo `PAC-2026-00014`
- **CPF, RG, data de nascimento**: o mesmo
- **Médico prescritor**: pode ser o mesmo OU outro (se mudou de médico)

#### Quando atualizar dados do Patient

Endereço, telefone, e-mail mudam? **Edite o Patient existente** (não crie novo):

1. Abra o `PAC-2026-00014`
2. Atualize os campos
3. **Save**

Sistema mantém histórico de alterações (`track_changes=1`) — auditoria fica
preservada.

#### Vantagens de manter 1 só cadastro

- **Histórico unificado**: relatório "todos os pedidos da Maria desde 2026" funciona
- **Rastreabilidade**: liga lotes históricos (que ela já tomou) com novos
- **Sem duplicação**: ninguém fica confuso entre 3 "Maria" diferentes
- **LGPD**: dados pessoais em 1 lugar, mais fácil de atualizar/anonimizar

#### Mesma lógica vale pra Customer (médico)

Médico prescritor também é cadastro mestre **único**. Cadastre uma vez. Use
em todos os SOs e Patients que ele prescrever.

#### Erros comuns e o que fazer

| Erro | Causa | Solução |
|---|---|---|
| `CPF precisa ter 11 dígitos` | CPF incompleto ou com letra | Confira o CPF. Pode digitar com ou sem máscara, mas precisa ter 11 dígitos. |
| `CPF inválido (todos iguais)` | Você digitou 11111111111 ou similar | Use CPF real. |
| `CPF duplicado` | Esse CPF já está cadastrado | Use o cadastro existente (busca pelo CPF). |
| Médico Prescritor não aparece | O médico não está cadastrado como Prescriber | Cadastre o médico primeiro como Prescriber (seção 4.2) |

### 4.4. Cadastro de Item (Produto / Ampola)

#### O que é?

Item = o **produto** que a empresa vende/fabrica. Ex: "Tirzepatida 60mg/2,4ml".
Tem um código único (ex: `TIR00060`) que aparece em todos os lugares.

#### Quando cadastrar?

- Quando entra um produto novo no catálogo da empresa
- **Não é diário** — TI/produção faz raramente

#### Quem faz?

TI ou Gestor de Produto (não é o operador comercial)

#### Passo a passo (referência rápida)

**1.** Menu lateral → **Stock** → **Item** → **+ New**

**2.** Preencha:

```
┌──────────────────────────────────────────────────────────────┐
│  Item Code *:         [TIR00060]                              │
│  ← Código único. Use letras+números curtos. Não muda depois.  │
│                                                              │
│  Item Name *:         [Tirzepatida 60mg/2,4ml]                │
│  ← Nome legível.                                              │
│                                                              │
│  Item Group *:        [Products                       ▼]     │
│                                                              │
│  Stock UOM *:         [Unit] ou [Nos]                         │
│  ← Unidade de medida em estoque (unidade, kg, litro…).        │
│                                                              │
│  ☑ Maintain Stock                                            │
│  ← Marque sempre — sem isso, sistema não controla estoque.    │
│                                                              │
│  ☑ Has Batch No                                              │
│  ← ⚠ ESSENCIAL pra nosso processo. Sem isso, FPB não funciona.│
│                                                              │
│  ☑ Has Expiry Date                                           │
│  ← Marque pra medicamento com validade.                       │
│                                                              │
│  Shelf Life (days):   [730]                                   │
│  ← Validade em dias a partir da fabricação (ex: 730 = 2 anos).│
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**3.** **Save**

✓ Item disponível pra uso em pedidos e produção.

#### Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| Item já existe | Código duplicado | Use código diferente ou edite o existente |
| FPB não aceita o item | Esqueceu de marcar "Has Batch No" | Edite o Item e marque |

---

## 5. Etapa A — Planejar Lote de Produção (FPB)

### O que é um FPB?

FPB (Future Production Batch) = "**Lote de Produção Futura**". É a **promessa**
da empresa de fabricar um lote num determinado dia. **Não é estoque real**.

**Analogia**: você reserva uma mesa no restaurante pra sábado às 20h. A mesa
não está ocupada ainda — só está **prometida**. Outros não podem reservar
ela pra mesma hora. Quando chegar sábado, você ocupa de verdade.

O FPB funciona igual. O sistema "guarda" uma quantidade de futuras ampolas
que ainda não foram fabricadas, e permite vender contra essa promessa.

### Por que criar antes do pedido?

- **Vender com prazo**: cliente quer 500 ampolas pro mês que vem? Você
  precisa ter um lote planejado pra reservar contra ele.
- **Não dá pra vender o ar**: se nenhum FPB existe, não dá pra prometer
  entrega futura.
- **Controla capacidade**: o lote tem tamanho fixo (ex: 2.000 ampolas). Você
  não consegue vender mais que isso.

### Quem faz?

Planejador de Produção (cargo: PCP — Planejamento e Controle de Produção)

### Quando criar?

- Sempre antes do mês começar (planejamento mensal)
- Sempre que o saldo dos FPBs atuais estiver acabando
- Quando o comercial avisar "vou ter uma demanda grande no mês X"

### Passo a passo

**1.** Menu → **Produção Futura** → **Lote de Produção Futura**

**2.** Clique **+ New**

**3.** Aparece a tela em branco. Preencha cada campo (explico um por um):

```
┌──────────────────────────────────────────────────────────────┐
│  NEW FUTURE PRODUCTION BATCH                                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Código da Produção *:                                       │
│  [AMP-2026-05-20-001___________]                              │
│  ↑ Identificador legível pra equipe. Use convenção:          │
│    [SIGLA]-[ANO]-[MES]-[DIA]-[SEQUENCIAL]                    │
│    Ex: AMP-2026-05-20-001 = primeira fornada do dia 20/05/26 │
│                                                              │
│  Empresa *:                                                  │
│  [Injmedpharma                                       ▼]      │
│                                                              │
│  Status *:                                                   │
│  [Aberta para Reserva                                ▼]      │
│  ↑ SEMPRE comece com "Aberta para Reserva".                  │
│    Outros status só mudam depois automaticamente.            │
│                                                              │
│  ── Produto ──                                                │
│                                                              │
│  Produto a Produzir *:                                       │
│  [TIR00060 — Tirzepatida 60mg/2,4ml                   ▼]     │
│  ↑ Use a busca. Digite TIR e o sistema sugere.               │
│                                                              │
│  Nome do Produto:    (preenche sozinho ao escolher o item)    │
│  Unidade:            (preenche sozinho)                       │
│                                                              │
│  BOM (opcional):                                             │
│  [BOM-TIR00060-001                                   ▼]      │
│  ↑ Lista de Materiais. Opcional aqui.                        │
│                                                              │
│  ── Quantidades e Datas ──                                    │
│                                                              │
│  Quantidade Planejada *:                                     │
│  [2000]                                                       │
│  ↑ Quantas ampolas você vai fabricar. Bate com capacidade da │
│    linha (não invente).                                       │
│                                                              │
│  Data Prevista de Produção *:                                │
│  [2026-05-20]                                                 │
│  ↑ Quando a fabricação vai acontecer.                        │
│                                                              │
│  Data Esperada de Liberação:                                 │
│  [2026-05-25]                                                 │
│  ↑ Quando as ampolas estarão prontas pra sair (após          │
│    quarentena/análise). Opcional.                            │
│                                                              │
│  ── Depósitos ──                                              │
│                                                              │
│  Depósito de Produto Acabado *:                              │
│  [Produtos Acabados - I                              ▼]      │
│  ↑ Onde as ampolas prontas vão ficar.                        │
│                                                              │
│  Depósito WIP (Work in Progress):                            │
│  [WIP - I                                            ▼]      │
│  ↑ Opcional. Onde fica o produto em fabricação.              │
│                                                              │
│  ── Avançado (opcional) ──                                    │
│                                                              │
│  ☐ Permitir Reserva Acima do Planejado                       │
│  ↑ MARQUE só se quiser permitir overbooking (vender mais que │
│    a capacidade). Padrão: NÃO MARCAR.                        │
│                                                              │
│  Limite extra: [0]                                            │
│  ↑ Se permitir overbooking, quanto a mais (ex: 200 = pode    │
│    reservar até 2200 num lote planejado de 2000).            │
│                                                              │
│  Limite pra novas reservas:                                  │
│  [2026-05-15 18:00:00]                                        │
│  ↑ Depois dessa data/hora, sistema bloqueia novas reservas.  │
│    Opcional.                                                  │
│                                                              │
│  Observações: [_____________________________________________]│
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**4.** Clique **Save** — o documento fica salvo como **Rascunho** (status visual amarelo)

**5.** Confira tudo. Se algo estiver errado, edite e Save de novo.

**6.** Clique **Submit** (botão azul no canto superior direito)

> Sistema pergunta: "Are you sure you want to submit this document?"
> Confirme.

**7.** ✓ **Sucesso**: o documento muda pra **Submitted** (status verde).
Agora ele pode receber reservas.

### Como o FPB muda de status sozinho

Depois de submetido, o FPB muda de status automaticamente conforme os eventos
acontecem. Você **não** precisa mudar manualmente.

```
   Rascunho
       │  Save = rascunho amarelo
       ▼
   ┌─────────────────────┐
   │  Save + Submit       │ ──► docstatus=1 (verde)
   └──────────┬───────────┘
              ▼
   ┌─────────────────────────┐
   │ Aberta para Reserva     │  ← agora aceita reservas
   │ reserved = 0            │
   └──────────┬──────────────┘
              │ vendedor cria reserva
              ▼
   ┌─────────────────────────┐
   │ Reservada Parcialmente  │  ← parte das ampolas já tem dono
   │ 0 < reserved < planned  │
   └──────────┬──────────────┘
              ▼
   ┌─────────────────────────┐
   │ Totalmente Reservada    │  ← todas vendidas (no papel)
   │ reserved >= planned     │
   └──────────┬──────────────┘
              │ Work Order criada
              ▼
   ┌─────────────────────────┐
   │ Em Produção             │  ← fabricação começou
   └──────────┬──────────────┘
              ▼
   ┌─────────────────────────┐
   │ Produzida Parcialmente  │  ← parte saiu da produção
   └──────────┬──────────────┘
              ▼
   ┌─────────────────────────┐
   │ Produzida Totalmente    │
   └──────────┬──────────────┘
              │ supervisor libera
              ▼
   ┌─────────────────────────┐
   │ Liberada Parcial/Total  │  ← pronto pra entregar
   └─────────────────────────┘
```

### Checklist antes de submeter

- [ ] Código da Produção único e legível?
- [ ] Item correto?
- [ ] Quantidade bate com a capacidade real da linha?
- [ ] Data realista (não passada, não muito distante)?
- [ ] Depósito correto?
- [ ] Empresa correta (se multi-empresa)?

### Como conferir que ficou pronto

Abra de novo o FPB. No topo aparece:

```
┌────────────────────────────────────────────────────────────┐
│ Future Production Batch FPB-2026-00003                      │
│ ● Submitted        Status: Aberta para Reserva              │
├────────────────────────────────────────────────────────────┤
│                                                            │
│   Planejado:     2000                                       │
│   Reservado:        0                                       │
│   Disponível:    2000   ← saldo livre pra reservas          │
│   Produzido:        0                                       │
│   Liberado:         0                                       │
│   Pend. Liber.:     0                                       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

✓ "Submitted" + status "Aberta para Reserva" + Disponível=2000 → tudo certo.

### Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| Não consigo submeter | Falta um campo obrigatório | Procure o campo em vermelho (geralmente Quantidade Planejada ou Data) |
| Quero apagar um FPB | Tem reservas vinculadas | Cancele todas as PRs antes (etapa 15.2). Só depois apaga o FPB. |
| Erro "Item must have Has Batch No" | Item foi mal cadastrado | Volte na seção 4.3 e marque a checkbox |

---

## 6. Etapa B — Emitir Pedido de Venda

### O que é um Sales Order (SO)?

Sales Order = "**Pedido de Venda**". É o documento oficial que diz:
"o cliente X comprou Y ampolas por Z reais, com entrega prevista para a data D".

A partir dele, todos os próximos passos acontecem (reserva, faturamento,
entrega).

### Pré-requisitos

Antes de criar o SO, **garanta que existem**:

- [ ] **Cliente cadastrado** (seção 4.1)
- [ ] **Pacientes cadastrados** (seção 4.2) — um por pessoa que vai receber
- [ ] **Item cadastrado** (seção 4.3)
- [ ] **FPB submetido com saldo** (seção 5) — pra poder reservar depois

> Se algum desses não existe, **volte e cadastre primeiro**. Não tente criar
> o SO sem pré-requisitos — vai dar erro no meio.

### Quem faz?

Comercial (vendedor)

### Passo a passo

#### Passo 6.1 — Conferir saldo nos lotes (FPB)

Antes de prometer ao cliente, abra a **lista de FPBs** e veja o que tem
disponível.

**1.** Menu → **Produção Futura** → **Lote de Produção Futura**

**2.** No topo da lista, clique **Filter** e configure:

```
┌─────────────────────────────────────────────────┐
│ Filter:                                          │
│ Item Code:        [TIR00060          ]           │
│ Status:           [Aberta para Reserva, ]        │
│                   [Reservada Parcialmente]       │
│ Available Qty:    [> 0                  ]        │
└─────────────────────────────────────────────────┘
```

**3.** Clique **Apply**

**4.** Apaarece a lista filtrada:

```
┌──────────────────────────────────────────────────────────────────┐
│ Lotes disponíveis (saldo livre)                                    │
├───────────────┬──────────┬────────┬────────┬────────┬─────────────┤
│ FPB           │ Item     │ Plan   │ Reserv │ Disp   │ Data prev.  │
├───────────────┼──────────┼────────┼────────┼────────┼─────────────┤
│ FPB-2026-001  │ TIR00060 │ 2000   │ 1500   │ 500    │ 2026-05-20  │
│ FPB-2026-002  │ TIR00060 │ 2000   │ 0      │ 2000   │ 2026-06-15  │
└───────────────┴──────────┴────────┴────────┴────────┴─────────────┘
```

**5.** Confirme com o cliente uma data viável (baseado em "Data prev.").

> Se nenhum FPB aparecer com saldo, **não prometa entrega**. Avise o
> Planejador de Produção pra criar um FPB novo (seção 5).

#### Passo 6.2 — Criar o SO

**1.** Menu → **Selling** → **Sales Order** → **+ New**

**2.** Preencha o **cabeçalho**:

```
┌──────────────────────────────────────────────────────────────┐
│  NEW SALES ORDER                              Save           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Customer *:           [Dr. José da Silva           ▼]       │
│  ↑ Digite parte do nome; ele sugere. Se não aparece, volte e │
│    cadastre antes (seção 4.1).                                │
│                                                              │
│  Date *:               [2026-05-17]   (hoje, default)         │
│                                                              │
│  Delivery Date *:      [2026-06-17]                           │
│  ↑ Data prometida ao cliente. Não pode ser antes da data de  │
│    produção do FPB (não faz sentido).                         │
│                                                              │
│  Order Type:           [Sales] (default)                      │
│                                                              │
│  ── Currency & Price ──                                      │
│                                                              │
│  Currency:             [BRL] (default)                        │
│  Price List:           [Venda Padrão                   ▼]    │
│  ↑ Se sua empresa tem várias tabelas de preço, escolha.       │
│                                                              │
│  Company:              [Injmedpharma] (default)               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### Passo 6.3 — Adicionar items (produtos)

Role para baixo até a seção **Items**.

**1.** Clique **+ Add Row** (botão verde dentro da tabela)

**2.** Aparece uma linha em branco. Preencha:

```
┌────────────────────────────────────────────────────────────────┐
│  ITEMS                                                          │
│  ┌──────────┬─────┬──────┬─────────────────────────────────┐  │
│  │ Item *   │ Qty │ Rate │ Warehouse        │ Delivery Date │  │
│  ├──────────┼─────┼──────┼──────────────────┼───────────────┤  │
│  │ TIR00060 │  10 │ 100  │ Produtos Acabados│ 2026-06-17    │  │
│  │          │     │      │ - I              │               │  │
│  └──────────┴─────┴──────┴──────────────────┴───────────────┘  │
│  [+ Add Row]                                                    │
│                                                                │
│  Total: R$ 1.000,00  (Qty × Rate)                              │
└────────────────────────────────────────────────────────────────┘
```

- **Item**: código do produto (use a busca, digite "TIR")
- **Qty**: quantidade total da venda (todas as ampolas, somando pacientes)
- **Rate**: preço unitário em R$ (se já tem na Price List, preenche sozinho)
- **Warehouse**: depósito de onde vai sair (combina com o FPB)
- **Delivery Date**: pode ser igual à data do cabeçalho

> **Importante**: a `Qty` aqui é o TOTAL. Ex: se vai pra 4 pacientes (3+2+4+1=10),
> coloque `Qty=10` aqui na linha do item. A divisão entre pacientes é a
> próxima etapa.

#### Passo 6.4 — Adicionar pacientes (CRÍTICO)

Role mais para baixo. Procure a seção **"Pacientes"** (pode estar collapsible — clique pra expandir).

**1.** Clique **+ Add Row** dentro da tabela de Pacientes

**2.** Para cada paciente, preencha 1 linha:

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  PACIENTES                                                                            │
│  ┌─────────────────┬───────────────────┬──────────────────┬──────────┬─────┐         │
│  │ Patient *       │ Patient Name(auto)│ Prescriber *     │ Item *   │ Qty │         │
│  ├─────────────────┼───────────────────┼──────────────────┼──────────┼─────┤         │
│  │ PAC-2026-00014▼ │ Maria Aparecida   │ PRES-2026-00007▼ │ TIR00060 │  3  │         │
│  │                 │                   │ Dr. José (CRM-SP)│          │     │         │
│  │ PAC-2026-00015▼ │ João Silva        │ PRES-2026-00007▼ │ TIR00060 │  2  │         │
│  │                 │                   │ Dr. José (CRM-SP)│          │     │         │
│  │ PAC-2026-00016▼ │ Ana Beatriz       │ PRES-2026-00011▼ │ TIR00060 │  4  │         │
│  │                 │                   │ Dra. Ana (CRM-RJ)│          │     │         │
│  │ PAC-2026-00017▼ │ Carlos Souza      │ PRES-2026-00007▼ │ TIR00060 │  1  │         │
│  │                 │                   │ Dr. José (CRM-SP)│          │     │         │
│  └─────────────────┴───────────────────┴──────────────────┴──────────┴─────┘         │
│  [+ Add Row]                                                                          │
│                                                                                       │
│  Total pacientes (item TIR00060): 3+2+4+1 = 10  ✓ bate com qty do item                │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

**Como funciona o Link Field "Patient"**:
- Clique na célula → aparece dropdown
- Digite o nome ou CPF → ele filtra
- Clique no certo → nome e CPF preenchem sozinhos
- **Prescriber preenche sozinho** com o médico padrão cadastrado no Patient
  (seção 4.3 — campo "Médico Prescritor")

**Como funciona a coluna Prescriber**:
- Cada linha de paciente pode ter um **médico diferente**
- Sistema sugere automaticamente o médico padrão do Patient
- Você pode **sobrescrever** clicando e escolhendo outro Prescriber
- Útil quando: hospital/clínica compra pra vários pacientes de médicos
  distintos no mesmo pedido

**Colunas adicionais (após produção/liberação)**:

| Coluna | O que mostra | Quando preenche |
|---|---|---|
| `Lote Atribuído` | Batch físico que vai pra este paciente | Após liberação + chamar `future_production_allocate_patient_batches` |
| `Qtd Alocada em Lote` | Quanto da qty já está vinculado ao batch | Mesmo momento |
| `Status de Alocação` | Pendente / Parcialmente Alocado / Alocado / Entregue / Cancelado | Mesmo momento |

> Fluxo automático: após acionar **Liberar Reservas** (etapa F), execute
> também **Alocar Batch por Paciente** (botão ou API) para que cada linha
> de paciente saiba **qual batch físico** vai receber. A farmácia usa essa
> info pra separar e imprimir etiquetas Zebra (etapa J).

> ⚠ Se um paciente recebeu prescrição de **2 médicos diferentes** pro mesmo
> item (caso raro), crie **2 linhas** desse paciente no SO, uma com cada
> Prescriber e dividindo a qty.

> **⚠ REGRA OBRIGATÓRIA**:
> A **soma das quantidades dos pacientes** PARA CADA ITEM precisa ser **igual**
> à quantidade do item no cabeçalho.
>
> Ex: linha de item `TIR00060 qty=10` → soma das `qty` dos pacientes do item
> `TIR00060` precisa dar **10** (não 9, não 11).
>
> Se não bater, o Save bloqueia com mensagem:
> `"Item TIR00060: qty do pedido (10) diferente da soma das ampolas dos
> pacientes (9)"`

#### Passo 6.5 — Save → Submit

**1.** Clique **Save** (canto superior direito)

> Se algo estiver errado, aparece erro vermelho. Conserte e Save de novo.

**2.** Após Save, aparece o botão **Submit** (azul)

**3.** Clique **Submit**

**4.** Sistema pergunta confirmação. Confirme.

**5.** ✓ **Sucesso**: o SO muda pra **Submitted** (verde). Aparece um código
tipo `SAL-ORD-2026-00031`.

> **Anote esse código**. Vai usar na próxima etapa (Reserva).

### Como conferir que ficou pronto

Abra o SO novamente. Topo deve estar:

```
┌────────────────────────────────────────────────────────────┐
│ Sales Order SAL-ORD-2026-00031                              │
│ ● Submitted    Status: To Deliver and Bill                  │
│ Customer: Dr. José da Silva                                 │
│ Total: R$ 1.000,00                                          │
└────────────────────────────────────────────────────────────┘
```

✓ Status "To Deliver and Bill" + linha de itens preenchida + tabela de pacientes preenchida.

### Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| `Item X: qty diferente da soma dos pacientes` | Soma dos pacientes ≠ qty do item | Recalcule, ajuste qty dos pacientes |
| `Mandatory: Customer` | Esqueceu o cliente | Selecione no campo Customer |
| `Mandatory: Delivery Date` | Esqueceu a data | Preencha |
| `Item code not found` | Item não cadastrado | Volte e cadastre (seção 4.3) |
| Não consigo escolher um paciente | Lista vazia | Cadastre o paciente primeiro (seção 4.2) |
| `Patient item_code não está nos items do SO` | Você botou item diferente no paciente | Use o mesmo item_code do item da linha |

---

## 7. Etapa C — Reservar Lote

### O que é uma Reserva?

Reserva = **amarra** uma linha do Pedido de Venda a um Lote de Produção
Futura. Cria um documento **Production Reservation (PR)** e **diminui o
saldo disponível** do FPB.

**Analogia**: comprou ingresso pro show. O ingresso é a PR. A capacidade do
estádio (FPB) tinha 2.000 lugares — agora tem 1.990 (você levou 10).

### Por que reservar?

- **Garante a entrega**: sem reserva, outro vendedor pode "tomar" o saldo
- **Liga produção a venda**: produção sabe pra quem cada ampola vai
- **Rastreabilidade**: depois consegue ver "essa ampola era do paciente X"

### Quem faz?

Comercial (mesmo vendedor que criou o SO) OU Planejamento

### Quando?

Logo depois de submeter o SO. **Não deixe pra depois** — outro pedido pode
"engolir" o saldo enquanto isso.

### Dois modos de reservar

#### Modo 1 — Reserva manual (operador escolhe o FPB)

**Use quando**:
- Cliente exigiu um lote específico (ex: validade que combina com cronograma do paciente)
- Produção quer empurrar primeiro um lote prioritário
- Você sabe exatamente qual FPB usar

**Passo a passo**:

**1.** Abra o **Sales Order** submetido (seção 6)

**2.** No topo direito, clique no botão **Produção Futura** (botão customizado)

**3.** Aparece sub-menu. Clique **Reservar em Produção Futura**

**4.** Abre um diálogo:

```
┌─────────────────────────────────────────────────────┐
│ Reservar em Produção Futura                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Linha do Pedido:                                   │
│  [TIR00060 (qty=10)                          ▼]    │
│  ↑ Se o SO tem mais de 1 item, escolhe qual.       │
│                                                     │
│  Lote de Produção Futura:                          │
│  [FPB-2026-001 (disp=500)                    ▼]    │
│  ↑ Só mostra FPBs do mesmo item com saldo > 0.     │
│                                                     │
│  Quantidade:                                        │
│  [10]                                                │
│  ↑ Padrão = qty da linha. Pode reservar parcial.   │
│                                                     │
│  Prioridade:                                        │
│  [100]                                               │
│  ↑ Menor número = libera primeiro. Padrão 100.     │
│    Use 50 pra "VIP", 200 pra "pode esperar".       │
│                                                     │
│           [ Cancelar ]    [ Reservar ]              │
└─────────────────────────────────────────────────────┘
```

**5.** Confira e clique **Reservar**

**6.** ✓ Sistema confirma com mensagem tipo:
"Reserva PR-2026-00027 criada. Saldo do FPB-2026-001: 490 disponíveis."

#### Modo 2 — Reserva automática (sistema escolhe)

**Use quando**:
- Você não se importa em qual lote ficar
- Quer ser rápido
- Confia na regra FIFO (lote mais antigo primeiro)

**Passo a passo**:

**1.** Abra o **Sales Order** submetido

**2.** Botão **Produção Futura** → **Reservar Automaticamente**

**3.** Confirme

**4.** Sistema busca FPBs do item, ordena por **data de produção (mais antigo
primeiro)**, e vai distribuindo até completar o pedido. Pode dividir 1 item
entre 2 ou mais FPBs se for preciso.

**5.** ✓ Mensagem de sucesso lista quantas reservas foram criadas e em quais FPBs.

### Como conferir que deu certo

**Confira em 2 lugares**:

**1.** Volte ao **Sales Order**. Role até a linha de item e expanda a seção
**Produção Futura** (campos espelho):

```
┌────────────────────────────────────────────────────────────────┐
│ Item: TIR00060   qty: 10                                        │
│                                                                │
│  ── Produção Futura ─────────────────────────────────────       │
│  FPB:               FPB-2026-001                                │
│  Reservado:         10                                          │
│  Liberado:          0                                           │
│  Pendente Liber.:   0                                           │
│  Status Reserva:    Reservado  ✓                                │
└────────────────────────────────────────────────────────────────┘
```

✓ "Status Reserva: Reservado" + FPB preenchido + Reservado=10 → tudo certo.

**2.** Abra o **FPB**. O saldo deve ter caído:

```
   Planejado:    2000
   Reservado:    1510   ← era 1500, agora +10 (esta reserva)
   Disponível:    490   ← era 500
   Status:       Reservada Parcialmente
```

### Como ver todas as reservas que existem

Menu → **Produção Futura** → **Reserva de Produção**

Lista todas as PRs do sistema. Filtre por cliente, FPB, status, etc.

### Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| `Saldo insuficiente no FPB` | Tentou reservar mais que o disponível | Reduza a qty ou escolha outro FPB |
| `Sales Order precisa estar submetido` | SO ainda é rascunho | Volte e Submit primeiro |
| `Item do FPB diferente do item do SO` | Você escolheu FPB do produto errado | Escolha FPB do mesmo item |
| `Não aparece FPB no dropdown` | Nenhum FPB com saldo desse item | Volte na seção 5 e crie um |

---

## 8. Etapa D — Programar Produção

### O que é uma Work Order?

Work Order = "**Ordem de Produção**". É o documento que **autoriza a produção
a começar**. Diz: "fabricar 2.000 ampolas do item TIR00060 pra suprir o
FPB-2026-001".

### Quem faz?

Planejador de Produção

### Quando?

Quando o FPB está totalmente reservado (ou no momento decidido pela equipe —
pode ser antes, dependendo da estratégia).

### Tem que criar Work Order obrigatoriamente?

**Não**. Você pode pular essa etapa se sua empresa não usa Work Order
formal. Vai direto pra Etapa E (registrar produção). Mas perde:
- Controle automático de matéria-prima (BOM)
- Cálculo de custo de produção
- Rastreio de tempo

> **Recomendado**: usar Work Order se sua empresa já tem BOMs cadastrados.

### Passo a passo (com Work Order)

**1.** Abra o **FPB** submetido (ex: FPB-2026-001)

**2.** No topo direito, clique **Ações** → **Criar Work Order**

**3.** Confirme

**4.** Sistema:
- Busca a **BOM padrão ativa** do item
- Cria a Work Order vinculada
- Atualiza o FPB para status "Em Produção"
- Mostra mensagem com o código da WO criada (ex: `MFG-WO-2026-00001`)

**5.** ✓ Abra a Work Order pra conferir e (se necessário) ajustar:
- Quantidade total
- Data de início/fim planejadas
- Operações (etapas de produção)
- Material Request (requisição de matéria-prima)

### O que acontece após criar a WO

A WO segue um fluxo próprio do ERPNext:
- **Not Started** → **In Process** → **Completed**

A produção real (etapa 9) só vai começar quando a equipe física iniciar de fato.

### Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| `Item sem BOM ativa` | Não tem BOM cadastrado pro item | Cadastre BOM em *Manufacturing → BOM → + New* |
| `FPB não submetido` | FPB ainda é rascunho | Submit primeiro |
| `WO já existe pra esse FPB` | Já criou antes | Use a existente (não duplique) |

---

## 9. Etapa E — Registrar Produção Real

### O que acontece nessa etapa?

A produção física **terminou**. As ampolas existem de verdade agora. Você
precisa:

1. **Criar o Batch (lote físico)** no sistema — registra a identidade do lote
2. **Atualizar o FPB** com a quantidade real produzida + número do batch
3. **Dar entrada do estoque** (Stock Entry) — pra o sistema saber que existem N ampolas no depósito

### Quem faz?

Operador de Produção (ou Apontador da fábrica)

### Quando?

Imediatamente após o batch sair da linha de produção e passar pelo controle
de qualidade.

### Passo a passo

#### Passo 9.1 — Criar Batch físico

**1.** Menu → **Stock** → **Batch** → **+ New**

**2.** Preencha:

```
┌──────────────────────────────────────────────────────────────┐
│  NEW BATCH                                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Batch ID *:           [LOT-AMP-2026-05-20-001]               │
│  ↑ Código físico do lote. Use convenção:                     │
│    LOT-[SIGLA]-[ANO-MES-DIA]-[SEQ]                            │
│                                                              │
│  Item *:               [TIR00060                       ▼]    │
│                                                              │
│  Batch Qty *:          [1850]                                 │
│  ↑ Quantidade REAL produzida (pode ser menor que planejado). │
│                                                              │
│  Manufacturing Date:   [2026-05-20]                           │
│  ↑ Data de fabricação real.                                  │
│                                                              │
│  Expiry Date:          [2027-05-20]                           │
│  ↑ Data de validade (já sai do sistema se você cadastrou     │
│    Shelf Life no Item).                                      │
│                                                              │
│  Description:          [Lote 1 da fornada 2026-05-20]         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**3.** **Save**

✓ Batch criado. Anote o código (ex: `LOT-AMP-2026-05-20-001`).

#### Passo 9.2 — Atualizar o FPB com produção real

**1.** Abra o **FPB** correspondente (busque por nome ou pelo Workspace)

**2.** Mesmo já submetido, **2 campos podem ser editados** (estão habilitados pra isso):

```
┌──────────────────────────────────────────────────────────────┐
│  Quantidade Produzida:  [1850]    ← coloque o real           │
│  Lote Real Produzido:   [LOT-AMP-2026-05-20-001  ▼]          │
│                         ↑ Link Field, escolhe o Batch criado │
└──────────────────────────────────────────────────────────────┘
```

**3.** Clique **Save**

**4.** ✓ Sistema:
- Atualiza o status do FPB pra "Produzida Parcialmente" (porque 1850 < 2000) ou "Produzida Totalmente"
- Recalcula `pending_release_qty`

#### Passo 9.3 — Dar entrada do estoque (Stock Entry)

> **Por que esse passo?**: o FPB sozinho **não move estoque**. Sem Stock Entry,
> o ERPNext não sabe que existem 1850 ampolas no depósito — não vai conseguir
> emitir Pick List ou Delivery Note depois.

**1.** Menu → **Stock** → **Stock Entry** → **+ New**

**2.** Preencha:

```
┌──────────────────────────────────────────────────────────────┐
│  NEW STOCK ENTRY                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Stock Entry Type *:   [Manufacture                  ▼]      │
│  ↑ Importante: "Manufacture", não "Material Receipt".         │
│                                                              │
│  Posting Date *:       [2026-05-20]                           │
│                                                              │
│  Company:              [Injmedpharma]                         │
│                                                              │
│  Work Order:           [MFG-WO-2026-00001          ▼]        │
│  ↑ Se tem Work Order (etapa 8), linka aqui — o sistema       │
│    importa automaticamente as matérias-primas da BOM.        │
│                                                              │
│  BOM No:               (preenche sozinho se vincular WO)     │
│  For Quantity:         [1850]                                 │
│                                                              │
│  ── Items ──                                                  │
│                                                              │
│  ┌──────────┬───────────────────────┬──────┬──────────┐      │
│  │ Item     │ Target Warehouse      │ Qty  │ Batch No │      │
│  ├──────────┼───────────────────────┼──────┼──────────┤      │
│  │ TIR00060 │ Produtos Acabados - I │ 1850 │ LOT-...  │      │
│  └──────────┴───────────────────────┴──────┴──────────┘      │
│                                                              │
│  (se vinculou WO, aparece também a saída das matérias-primas │
│   automaticamente — confira)                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**3.** **Save** → **Submit**

**4.** ✓ Sistema:
- Cria `Stock Ledger Entry`
- Atualiza `Bin.actual_qty` do (TIR00060, Produtos Acabados - I, LOT-...) = 1850
- Agora as ampolas existem oficialmente no estoque do sistema

### Como conferir

**No FPB**:
```
   Planejado:    2000
   Produzido:    1850   ← atualizou
   Lote:         LOT-AMP-2026-05-20-001
   Status:       Produzida Parcialmente
   Liberado:     0
   Pend. Liber.: 1850   ← tudo aguardando liberação
```

**No menu Stock → Stock Balance** (relatório):

```
   Item: TIR00060
   Warehouse: Produtos Acabados - I
   Batch: LOT-AMP-2026-05-20-001
   Actual Qty: 1850
```

### Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| `produced_qty maior que planned_qty` | Você produziu mais que planejou (overbooking) | Marque "Permitir Reserva Acima do Planejado" no FPB primeiro |
| `Batch ID já existe` | Código duplicado | Use código diferente |
| Stock Entry não aceita batch | Item sem "Has Batch No" | Volte na seção 4.3 e marque |
| Não consigo editar produced_qty no FPB | Algum bug ou campo não habilitado pra allow_on_submit | Avise TI/admin |

---

## 10. Etapa F — Liberar Reservas

### O que é "liberar"?

"Liberar" = pegar a quantidade **produzida** e distribuir entre as **reservas
existentes**, seguindo a regra **FIFO** (quem chegou primeiro leva primeiro).

Cada reserva (PR) recebe sua parcela. O campo `released_qty` da PR é
atualizado. O campo `release_batch_no` aponta pra o lote físico.

A partir daqui, a expedição sabe **quais ampolas vão pra cada pedido**.

### Por que precisa liberar?

Sem liberar, as reservas continuam "no ar" — abstratas. Liberar é o passo que
**transforma promessa em compromisso real** de entrega.

### Quem faz?

Supervisor de Produção (ou alguém com permissão Manufacturing Manager)

### Quando?

Logo após registrar a produção real (etapa 9). Não deixe pra depois — a
expedição precisa disso pra começar a separar.

### Passo a passo

**1.** Abra o **FPB** com `produced_qty > 0` (ex: FPB-2026-001 com produzido=1850)

**2.** Confira:
- [ ] `produced_qty` > 0 (etapa 9 feita)
- [ ] `batch_no` preenchido (etapa 9 feita)

**3.** No topo direito, clique **Ações** → **Liberar Reservas**

**4.** Sistema pergunta confirmação. Confirme.

**5.** Sistema executa o algoritmo FIFO (explicado abaixo).

**6.** ✓ Mensagem de sucesso tipo:
"4 reservas processadas. Total liberado: 1850. Pendente: 0."

### Como funciona o FIFO

```
   Ordenar PRs ativas do FPB por (nessa ordem):
       1. priority ASC          (menor número = primeiro)
       2. payment_date ASC      (quem pagou antes leva antes)
       3. reservation_date ASC  (quem reservou antes)
       4. creation ASC          (criação no sistema mais antiga)
   
   take = produced_qty disponível pra distribuir
   
   Pra cada PR na ordem:
       parte = min(pending_qty da PR, take)
       PR.released_qty += parte
       PR.release_batch_no = batch_no do FPB
       take -= parte
       Se take == 0: parar
   
   PRs não atendidas ficam com pending_qty > 0 → "Parcialmente Liberado"
```

### Exemplo numérico

```
   FPB.produced_qty = 1850
   FPB.batch_no     = LOT-AMP-2026-05-20-001
   
   Reservas (em ordem FIFO):
   ┌────────────┬──────────┬─────────┬─────────────────────────────────┐
   │ PR         │ SO       │ Reserv  │ Após liberar 1850               │
   ├────────────┼──────────┼─────────┼─────────────────────────────────┤
   │ PR-...027  │ SO-001   │  300    │  Liberado 300, Pendente 0       │
   │ PR-...028  │ SO-002   │  500    │  Liberado 500, Pendente 0       │
   │ PR-...029  │ SO-003   │  700    │  Liberado 700, Pendente 0       │
   │ PR-...030  │ SO-004   │  500    │  Liberado 350, Pendente 150  ⚠  │
   └────────────┴──────────┴─────────┴─────────────────────────────────┘
   Total liberado: 1850
   Sobrou pendente: 150 (na PR-030, do SO-004)
```

A PR-030 fica com **status "Parcialmente Liberado"** e `pending_qty=150`.

### O que conferir

| Tela | O que olhar |
|---|---|
| **FPB** | `released_qty = 1850`, `pending_release_qty = 0` |
| **Cada PR** | `released_qty`, `release_batch_no` preenchido, status correto |
| **Cada SO Item** | `fp_released_qty`, `fp_pending_release_qty` atualizado |

### Se sobrou pendente (alguém ficou sem)

Vai pra **etapa 15.1 — Replanejar pendência**. Você pode mover o saldo
pendente pra um próximo FPB que ainda vai produzir.

### Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| `Nada a liberar` | `produced_qty = 0` ou tudo já foi liberado | Confira etapa 9 |
| `Batch não preenchido` | Esqueceu de informar o `batch_no` no FPB | Edite o FPB e preencha o batch (etapa 9.2) |

---

## 11. Etapa G — Picking (Pick List)

### O que é Pick List?

Pick List = "**Lista de Separação**". Documento que diz ao operador de
expedição: "vai no depósito X, prateleira Y, pega N ampolas do lote Z".

É o que se imprime e leva pro armazém pra separar fisicamente.

### Quem faz?

Expedição / Logística

### Quando?

Depois que as reservas do SO foram liberadas (etapa 10).

### Pré-requisitos

- [ ] Etapa 10 executada (existe `fp_released_qty > 0` em algum item do SO)
- [ ] Batch físico existe no depósito (etapa 9)

### Passo a passo

**1.** Abra o **Sales Order** que vai entregar

**2.** No topo direito, clique **Create** → **Pick List**

**3.** Aparece a tela do Pick List com os dados pré-preenchidos:

```
┌────────────────────────────────────────────────────────────────────┐
│  NEW PICK LIST                                                      │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Purpose:    [Delivery                                  ▼]         │
│  ↑ "Delivery" pra preparar pra entrega.                            │
│                                                                    │
│  Company:    [Injmedpharma]                                         │
│                                                                    │
│  ── Locations ──                                                    │
│                                                                    │
│  ┌──────────────┬──────────┬─────┬─────────────────┬────────────┐ │
│  │ Sales Order  │ Item     │ Qty │ Warehouse       │ Batch No   │ │
│  ├──────────────┼──────────┼─────┼─────────────────┼────────────┤ │
│  │ SO-2026-031  │ TIR00060 │  10 │ Produtos Acab-I │ LOT-...    │ │
│  └──────────────┴──────────┴─────┴─────────────────┴────────────┘ │
│                                                                    │
│  ↑ Sistema sugere automaticamente o batch que foi liberado pra     │
│    esse SO. NÃO MUDE manualmente, salvo se souber o que faz.       │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**4.** Confira:
- Item correto
- Qty correta
- Warehouse certo
- Batch no certo (o que foi liberado)

**5.** **Save** → **Submit**

**6.** **Imprima** (botão **Print** no menu ▼) e dê pro operador de armazém.

### Conferência física (no chão de fábrica)

Operador de armazém faz:

- [ ] Lê o batch_no impresso na Pick List
- [ ] Vai até a prateleira correspondente
- [ ] Confere o lote físico bate
- [ ] Conta as ampolas (qty)
- [ ] Confere embalagem (não rasgada, sem dano)
- [ ] Confere validade visível
- [ ] Separa em caixa identificada com o número do SO
- [ ] Avisa que pode emitir Delivery Note (próxima etapa)

### Erros comuns

| Erro | Causa | Solução |
|---|---|---|
| `Insufficient stock` | Batch não tem qty suficiente | Confira no Stock Balance |
| `Batch não encontrado` | Etapa 9 não foi feita | Volte e crie o Batch + Stock Entry |
| Sistema sugere outro batch | Você mudou manualmente | Deixe o que ele sugere (é o que foi liberado) |

---

## 12. Etapa H — Entrega (Delivery Note)

### O que é Delivery Note (DN)?

Delivery Note = "**Nota de Entrega / Romaneio**". Documento que oficializa
**a saída das ampolas do depósito** rumo ao cliente. **Baixa o estoque** do sistema.

### Quem faz?

Expedição

### Quando?

Depois do Pick List submetido e da separação física confirmada.

### Passo a passo

**1.** Abra o **Pick List** submetido

**2.** Botão **Create** → **Delivery Note**

**3.** Sistema cria a DN herdando tudo automaticamente:

```
┌────────────────────────────────────────────────────────────────┐
│  NEW DELIVERY NOTE                                              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Customer:        Dr. José da Silva                             │
│  Posting Date:    2026-05-22                                    │
│  Company:         Injmedpharma                                  │
│                                                                │
│  ── Items ──                                                    │
│  TIR00060 × 10  batch=LOT-... warehouse=Produtos Acabados - I   │
│  (todos os campos vêm do Pick List)                             │
│                                                                │
│  ── Shipping ──                                                 │
│  Shipping Address: (endereço do cliente)                        │
│  Tracking No:      [se for entrega por transportadora]          │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**4.** Revise. Se tudo bate, **Save** → **Submit**

**5.** ✓ Sistema:
- Baixa `actual_qty` do estoque: -10 do batch LOT-...
- Cria `Stock Ledger Entry`
- Atualiza o SO Item: `delivered_qty += 10`

**6.** **Imprima** a DN. Acompanha a mercadoria até o cliente.

### Como conferir

**No SO**:
```
   Item: TIR00060   qty: 10
   Delivered Qty:  10  ← atualizou
   Status SO:      To Bill   ← muda de "To Deliver and Bill" pra só "To Bill"
```

**No Stock Balance**:
```
   TIR00060 / Produtos Acabados-I / LOT-...
   Actual Qty:  1840  ← era 1850, agora -10
```

---

## 13. Etapa I — Faturamento

### O que é Sales Invoice?

Sales Invoice = "**Fatura / Nota Fiscal**". Documento de cobrança que **gera
lançamento contábil** (débito Cliente, crédito Receita).

### Quem faz?

Financeiro

### Quando?

Após a entrega (Delivery Note submetida). Pode ser no mesmo dia ou no fim do
mês — depende da política da empresa.

### Passo a passo

**1.** Abra a **Delivery Note** submetida

**2.** Botão **Create** → **Sales Invoice**

**3.** Sistema cria a Sales Invoice herdando tudo:

```
┌────────────────────────────────────────────────────────────────┐
│  NEW SALES INVOICE                                              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Customer:        Dr. José da Silva                             │
│  Posting Date:    2026-05-22                                    │
│  Due Date:        2026-06-22  (30 dias)                         │
│                                                                │
│  ── Items ──                                                    │
│  TIR00060 × 10 × R$ 100,00 = R$ 1.000,00                        │
│                                                                │
│  ── Taxes ──                                                    │
│  (impostos calculados automaticamente baseado em Tax Category)  │
│  ICMS: R$ XXX                                                   │
│  PIS:  R$ XXX                                                   │
│                                                                │
│  Total Geral:    R$ 1.XXX,XX                                    │
│                                                                │
│  ── Payment Terms ──                                            │
│  Vencimento:     2026-06-22                                     │
│  Modo:           Boleto / Pix / Cartão                          │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**4.** Confira:
- [ ] Impostos calculados
- [ ] Vencimento certo
- [ ] Total correto

**5.** **Save** → **Submit**

✓ Sistema gera lançamento contábil + (se integrado com SEFAZ) emite a NFe.

### Receber pagamento (Payment Entry)

Quando o cliente pagar:

**1.** Abra a **Sales Invoice**

**2.** Botão **Create** → **Payment**

**3.** Preencha:

```
   Posting Date:     [data do pagamento]
   Payment Type:     Receive
   Party Type:       Customer
   Party:            Dr. José da Silva (preenchido)
   Paid Amount:      [valor recebido]
   Mode of Payment:  [Pix / Boleto / Transferência / Dinheiro]
   Bank Account:     [conta de destino]
```

**4.** **Save** → **Submit**

✓ Sales Invoice fica **Paid** (status verde "Paid").

---

## 14. Etapa J — Dispensação + Etiqueta Zebra

> **Significado**: ato físico de entregar as ampolas **aos pacientes finais**.
> **1 Sales Order = 1 Dispensação** (a entrega completa do pedido).
> Cada paciente da dispensação ganha **1 etiqueta Zebra individual**.

### Modelo

```
1 Sales Order (com pacientes alocados em batches)
                  │
                  ▼
1 Dispensation criada (DISP-2026-NNNNN)
                  │
   ┌──────────────┼──────────────┬──────────────┐
   ▼              ▼              ▼              ▼
Paciente A    Paciente B    Paciente C    Paciente D
3 ampolas     2 ampolas     4 ampolas     1 ampola
   │              │              │              │
   ▼              ▼              ▼              ▼
Etiqueta      Etiqueta      Etiqueta      Etiqueta
Zebra A       Zebra B       Zebra C       Zebra D
```

### Pré-requisito

SO precisa ter `fp_patients[].batch_no` preenchido. Isso acontece após
**Etapa F (Liberar)** + **Alocação** (botão "Alocar Batch por Paciente"
ou endpoint `future_production_allocate_patient_batches`).

### Quem usa
Farmacêutico responsável.

### Telas

| Tela | URL | O que faz |
|---|---|---|
| Lista de Dispensações | `/app/dispensation` | Vê todas, filtra por status |
| 1 Dispensação | `/app/dispensation/DISP-2026-NNNNN` | Header + child de pacientes |

### Passo a passo

#### 14.1. Criar Dispensação a partir do SO

Via API (botão UI futuro — C11):

```http
POST /api/method/future_production_create_dispensation_from_so
{ "sales_order": "SAL-ORD-2026-00060" }
```

Sistema cria 1 `Dispensation` com 1 linha por paciente alocado:

```
┌─────────────────────────────────────────────────────────────┐
│ Dispensation DISP-2026-00079                                  │
│ Status: Pendente                                              │
│                                                               │
│ Origem                                                        │
│  Sales Order:      SAL-ORD-2026-00060                         │
│  Cliente:          Clínica X (CNPJ)                           │
│                                                               │
│ Dispensação                                                   │
│  Data/Hora:        2026-05-18 14:30                           │
│  Farmacêutico:     wesley.cairo@injemedpharma.com.br          │
│  Total de Ampolas: 770                                        │
│  Total Pacientes:  5                                          │
│                                                               │
│ Etiquetas                                                     │
│  Template:         50x30mm   (ou 100x50mm)                    │
│  Impressas:        0/5                                        │
│                                                               │
│ Pacientes da Entrega                                          │
│ ┌──────────────────┬─────┬────────────┬──────────┬────────┐  │
│ │ Paciente         │ Qty │ Lote       │ Validade │ Print  │  │
│ ├──────────────────┼─────┼────────────┼──────────┼────────┤  │
│ │ Maria Aparecida  │ 154 │ LOT-AMP-.. │20/05/2027│  ☐     │  │
│ │ João Silva       │ 154 │ LOT-AMP-.. │20/05/2027│  ☐     │  │
│ │ Ana Beatriz      │ 154 │ LOT-AMP-.. │20/05/2027│  ☐     │  │
│ │ Carlos Souza     │ 154 │ LOT-AMP-.. │20/05/2027│  ☐     │  │
│ │ Paula Costa      │ 154 │ LOT-AMP-.. │20/05/2027│  ☐     │  │
│ └──────────────────┴─────┴────────────┴──────────┴────────┘  │
└─────────────────────────────────────────────────────────────┘
```

Cada linha mostra automaticamente (fetch_from):
- Nome + CPF + Celular (do Patient)
- Médico + Nº Conselho (do Prescriber)
- Item + qty
- Lote + Validade + Fabricação (do Batch)

#### 14.2. Conferir paciente fisicamente

Pra cada paciente que vem retirar:
- Confira CPF com documento
- Confere se qty bate
- Separa as ampolas do batch correto

#### 14.3. Imprimir Etiquetas Zebra

**3 botões disponíveis** no header e grid:

| Botão | Onde | Função |
|---|---|---|
| **Imprimir Todas as Etiquetas Zebra** | Header → menu Zebra | Imprime N etiquetas seguidas (1 por paciente) |
| **Imprimir Esta Linha** | Grid (após selecionar linha) | Imprime 1 etiqueta da linha |
| **Marcar como Dispensado** | Header → menu Zebra | Status final + atualiza espelhos |

**Como funciona**:

1. Clique **"Imprimir Todas as Etiquetas Zebra"**
2. Sistema chama `future_production_generate_all_zpl_labels`
3. Gera ZPL concatenado (todas N etiquetas)
4. Envia ao **Zebra BrowserPrint** (extensão local que conecta na impressora USB/rede)
5. Zebra imprime N etiquetas seguidas
6. Sistema marca `printed=1` em cada linha + `printed_count="5/5"` + `all_printed=1`

**Sem BrowserPrint instalado**: abre dialog com o ZPL — você copia e cola em
[labelary.com](https://labelary.com) (preview) ou Zebra Setup Utilities.

#### 14.4. Coletar assinatura + concluir

Cada linha tem campo `signature` (Attach Image) — anexe foto da assinatura
do paciente recebendo.

Quando todos receberam:
- Clique **"Marcar como Dispensado"**
- Confirma
- Sistema:
  - Status → "Dispensado"
  - Para cada paciente, atualiza `Sales Order Patient.batch_status = "Entregue"`

### Templates de etiqueta

**50x30mm (default)** — etiqueta pequena pra ampola individual:

```
┌──────────────────────────────────────────────────┐
│ Maria Aparecida Silva                             │
│ CPF: 111.444.777-35                               │
│ Tirzepatida 60mg/2,4ml                            │
│ Lote: LOT-AMP-2026-05-20-001                      │
│ Val: 20/05/2027  Qty: 3                           │
│ ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮  (barcode SAL-ORD|PAC|LOT)      │
└──────────────────────────────────────────────────┘
```

**100x50mm** — etiqueta maior pra embalagem secundária:

```
┌────────────────────────────────────────────────────────┐
│ Maria Aparecida Silva                                   │
│ CPF: 111.444.777-35                                     │
│                                                         │
│ Tirzepatida 60mg/2,4ml                                  │
│                                                         │
│ Lote: LOT-AMP-2026-05-20-001                            │
│ Validade: 20/05/2027                                    │
│ Fabricacao: 20/05/2026                                  │
│ Qtd: 3 ampolas                                          │
│                                                         │
│ ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮  (barcode)                │
│                                                         │
│                              SAL-ORD-2026-00060         │
│                              DISP-2026-00079            │
└────────────────────────────────────────────────────────┘
```

### Detalhes técnicos completos

Ver [`docs/15-dispensacao-zebra.md`](15-dispensacao-zebra.md).

### Pré-requisitos no PC da farmácia

1. Instalar **Zebra BrowserPrint** (Windows/Mac):
   https://www.zebra.com/us/en/products/software/barcode-printers/link-os/browser-print.html
2. Conectar Zebra via USB ou rede
3. Browser detecta automaticamente

---

## 15. Exceções

> Situações fora do fluxo normal. Aqui você encontra o "e se acontecer X".

### 15.1. Produziu MENOS que o reservado

**Como acontece**: planejou produzir 2000, mas só saíram 1850. Sobrou pelo
menos uma reserva pendente.

**Sintoma**: depois da etapa F (liberar), alguma PR fica com `pending_qty > 0`.

**Decisão**: 3 opções.

#### Opção A — Replanejar a pendência pra outro FPB

> Use quando: existe (ou vai existir) outro FPB do mesmo item.

**Passo a passo**:

1. Menu → **Produção Futura** → **Reserva de Produção**
2. Filtre por `pending_qty > 0` (ou abra a PR pendente direto)
3. Abra a PR pendente
4. Botão **Ações** → **Replanejar Pendência**
5. Diálogo:

```
┌─────────────────────────────────────────────────┐
│ Replanejar 150 ampolas pendentes da PR-030       │
├─────────────────────────────────────────────────┤
│ Destino:                                         │
│ [FPB-2026-002 (disp=2000)              ▼]       │
│                                                  │
│ Qty:    [150]                                    │
│                                                  │
│         [ Cancelar ]    [ Replanejar ]          │
└─────────────────────────────────────────────────┘
```

6. **Replanejar**

✓ Sistema:
- Reduz `reserved_qty` da PR origem (de 500 vira 350, com 350 já liberado, 0 pendente)
- Cria nova PR (PR-031) no FPB destino com mesmos dados + 150 reservadas
- Recalcula saldos dos 2 FPBs

#### Opção B — Avisar o cliente, negociar entrega parcial

Operação manual: telefone, e-mail. Se o cliente aceita receber o parcial,
você emite Pick List + DN só com o que tem. O restante fica pendente até
nova produção.

#### Opção C — Cancelar a PR pendente

> Use quando: cliente não pode esperar ou quer cancelar.

1. Abra a PR pendente
2. Botão **Cancel** (canto superior direito ou menu ▼)
3. Confirme

✓ Sistema:
- PR vira `docstatus=2` (cancelada)
- Saldo volta zero
- Espelho no SO Item zera

### 15.2. Cancelar uma reserva

**Quando**: cliente desistiu, pedido errado, troca de lote.

1. Abra a **PR** (ou a partir do SO → seção Produção Futura → link)
2. Botão **Cancel**
3. Confirme

✓ Saldo volta automaticamente ao FPB. Espelho no SO Item atualizado.

### 15.3. Cancelar um Sales Order

> Não dá pra cancelar SO se tem PRs ativas vinculadas. Cancele as PRs primeiro.

**Ordem correta**:
1. Cancelar **cada PR** vinculada ao SO (etapa 15.2)
2. Se já tem Delivery Note submetida: cancelar DN também
3. Se já tem Sales Invoice: cancelar SI
4. **Aí** cancelar o SO

### 15.4. Cancelar um FPB

> Mesma lógica: cancele tudo que depende dele primeiro.

**Ordem**:
1. Cancelar cada PR do FPB
2. Cancelar Work Order vinculada
3. **Aí** cancelar o FPB

### 15.5. Reconciliação manual (saldos parecem errados)

> Raro. Pode acontecer se alguém mexeu no banco direto via SQL/console.

**Como saber**: os números do FPB não batem com a soma das PRs.

**Solução**:

1. Abra o **FPB**
2. Botão **Ações** → **Recalcular Saldos**
3. Confirme

✓ Sistema:
- Re-soma todas as PRs submetidas vinculadas ao FPB
- Atualiza `reserved_qty`, `released_qty`, `available_qty`, `pending_release_qty`, `status`

### 15.6. Cliente quer trocar de lote (já reservado)

**Cenário**: cliente reservou lote A, mas pediu pra trocar pra lote B
(validade melhor).

**Passo a passo**:
1. Cancele a PR atual (etapa 15.2) — saldo volta pro FPB A
2. Crie nova reserva pro lote B (etapa 7)
3. Avise comercial pra ajustar comunicação com cliente

### 15.7. Erro "Não consigo acessar a tela"

Provável **falta de permissão**. Avise TI/admin do sistema com:
- Qual tela você tentou abrir
- Print da tela de erro (se houver)
- Seu usuário/e-mail

---

## 16. Checklist Diário

> Tarefas que cada papel deve fazer todo dia útil.

### Comercial (manhã)

- [ ] Abrir lista de FPBs (filtro `available_qty > 0`)
- [ ] Conferir saldo disponível por item — comunicar produção se baixo
- [ ] Atender pedidos pendentes (criar SO + reservar)
- [ ] Conferir se reservas do dia anterior estão `Reservado` no SO
- [ ] Revisar leads/prospects do CRM

### Planejamento (manhã)

- [ ] Listar FPBs com `Totalmente Reservada` há mais de 3 dias sem Work Order → criar WO
- [ ] Listar FPBs sem reservas e `planned_production_date - 7 dias <= hoje` → revisar com comercial
- [ ] Conferir capacidade da semana (somar `planned_qty` dos FPBs)

### Produção (durante e fim do turno)

- [ ] Atualizar `produced_qty` no FPB ao final de cada batch
- [ ] Criar Batch físico + Stock Entry Manufacture
- [ ] Conferir entrada de matéria-prima/saída de FG bate
- [ ] Ao final do dia, mandar resumo da produção pra Supervisor

### Supervisor (final do turno de produção)

- [ ] Validar produção registrada bate com chão de fábrica
- [ ] Acionar **Liberar Reservas** em cada FPB com produção finalizada
- [ ] Conferir se sobrou pendência — alinhar com comercial pra replanejar

### Expedição (manhã/tarde)

- [ ] Listar SOs com `fp_released_qty > 0` (relatório) → criar Pick List
- [ ] Conferência física antes de cada Delivery Note
- [ ] Submeter DN após confirmação física
- [ ] Anotar tracking/transportadora

### Financeiro (diário)

- [ ] DNs submetidas sem Sales Invoice → criar SI
- [ ] SIs vencendo nos próximos 5 dias → preparar cobrança
- [ ] Payments recebidos → registrar Payment Entry
- [ ] Relatório de inadimplência semanal

### Farmácia (no recebimento de pedido na loja)

- [ ] DN bate com SO?
- [ ] Conferir CPF do paciente que vai retirar
- [ ] Imprimir etiqueta paciente (Zebra) para cada ampola
- [ ] Coletar assinatura na dispensação
- [ ] Arquivar prescrição/receita

### Gestor (semanal)

- [ ] Relatório de pendências (etapa 15.1)
- [ ] Saldo geral de FPBs (capacidade próximas semanas)
- [ ] Inadimplência (financeiro)
- [ ] Aging de reservas (PRs muito antigas sem liberação)

---

## Apêndice — Resumo das transições de status

### Future Production Batch

```
   Rascunho ──Save──► Aberta para Reserva ──reserva──► Reservada Parcialmente
                                                              │
                                                              ▼
                                          Totalmente Reservada
                                                              │
                                                  cria WO     ▼
                                                          Em Produção
                                                              │
                                                produced_qty  ▼
                                          Produzida Parcial / Total
                                                              │
                                                    libera    ▼
                                          Liberada Parcial / Total
```

### Production Reservation

```
   Reservado ──libera parcial──► Parcialmente Liberado
       │                              │
       │                              ▼ libera total
       └──libera total─────────► Liberado
       │
       │
       └──cancelar────────────► Cancelado  (docstatus=2, saldo volta ao FPB)
       │
       └──replanejar zerou───► Replanejado
```

### Sales Order Item (campos espelho)

| `fp_reservation_status` | Significado em português claro |
|---|---|
| `Sem Reserva` | Linha do item sem PR vinculada (ainda não reservou) |
| `Reservado` | Tem PR ativa, nada liberado ainda — aguardando produção |
| `Parcialmente Reservado` | Reservou parte da qty do item (resto ainda livre) |
| `Liberado` | Tudo liberado, pronto pra pickar/entregar |
| `Parcialmente Liberado` | Parte do reservado já saiu da produção (resto pendente) |
| `Pendente` | Liberação ficou incompleta — precisa replanejar |

---

> **Última atualização**: 2026-05-18.
> Quando construir o módulo Dispensação + Etiquetas Zebra, atualizar
> seção 14 com tela real e procedimento clique-a-clique.

---

# Anexo I — Passo a Passo via Integração (API / n8n)

> Para quem **NÃO** vai usar a UI do ERPNext e prefere disparar o fluxo por
> automação (n8n, Make, scripts, CRM externo, app móvel).

Toda chamada precisa do header:

```
Authorization: token <API_KEY>:<API_SECRET>
Content-Type: application/json
Accept: application/json
```

Como gerar a chave: *User → seu usuário → API Access → Generate Keys*.

---

## Opção A — Chain de endpoints existentes

> Funciona **hoje**, sem nada novo no servidor. Você (n8n) faz 6-8 chamadas em
> sequência.

### A.1. Listar lotes com saldo

```http
GET {{URL}}/api/resource/Future Production Batch
  ?fields=["name","production_code","item_code","planned_qty","available_qty","planned_production_date","status"]
  &filters=[["docstatus","=",1],
            ["item_code","=","TIR00060"],
            ["status","in",["Aberta para Reserva","Reservada Parcialmente"]],
            ["available_qty",">",0]]
  &order_by=planned_production_date asc
  &limit_page_length=50
```

Resposta:
```json
{ "data": [
  { "name": "FPB-2026-00003", "available_qty": 500, ... }
]}
```

Pegue `data[0].name` para usar na reserva.

### A.2. Criar/verificar Customer

```http
GET {{URL}}/api/resource/Customer/DEMO-PF-Customer
```

- **404** → criar:

```http
POST {{URL}}/api/resource/Customer
{
  "customer_name": "Cliente Demo",
  "customer_type": "Individual",
  "customer_group": "Comercial",
  "territory": "Brazil"
}
```

- **200** → já existe, prossiga.

### A.3. Criar/verificar Patient (loop por paciente)

```http
GET {{URL}}/api/resource/Patient
  ?filters=[["cpf","=","11144477735"]]
  &fields=["name"]&limit_page_length=1
```

- Lista vazia → criar:

```http
POST {{URL}}/api/resource/Patient
{
  "patient_name": "Maria Aparecida Silva",
  "cpf": "11144477735",
  "mobile": "11999990001",
  "gender": "Feminino",
  "city": "São Paulo",
  "state": "SP",
  "country": "Brazil",
  "default_prescriber": "PRES-2026-00007"
}
```

> Antes era `prescribing_doctor` apontando pra Customer. Modelo novo:
> `default_prescriber` apontando pra `Prescriber` (DocType a construir —
> seção 4.2 do manual). Migração mantém compatibilidade enquanto a transição
> acontece.

Guarde `data.name` (ex: `PAC-2026-00014`).

### A.4. Criar Sales Order (rascunho)

```http
POST {{URL}}/api/resource/Sales Order
{
  "customer": "DEMO-PF-Customer",
  "company": "Injmedpharma",
  "transaction_date": "2026-05-17",
  "delivery_date": "2026-06-17",
  "currency": "BRL",
  "selling_price_list": "Venda Padrão",
  "price_list_currency": "BRL",
  "plc_conversion_rate": 1,
  "conversion_rate": 1,
  "items": [
    { "item_code": "TIR00060", "qty": 10, "rate": 100,
      "delivery_date": "2026-06-17",
      "warehouse": "Produtos Acabados - I" }
  ],
  "fp_patients": [
    { "patient": "PAC-2026-00014", "prescriber": "PRES-2026-00007", "item_code": "TIR00060", "qty": 3 },
    { "patient": "PAC-2026-00015", "prescriber": "PRES-2026-00007", "item_code": "TIR00060", "qty": 2 },
    { "patient": "PAC-2026-00016", "prescriber": "PRES-2026-00011", "item_code": "TIR00060", "qty": 4 },
    { "patient": "PAC-2026-00017", "prescriber": "PRES-2026-00007", "item_code": "TIR00060", "qty": 1 }
  ]
}
```

Guarde:
- `data.name` (ex: `SAL-ORD-2026-00031`)
- `data.items[0].name` (row_id da linha — necessário pra reserva manual)

> **Regras**:
> - Soma `fp_patients.qty` por `item_code` precisa bater com `items[].qty` do mesmo item.
> - Campo `prescriber` opcional na API — se omitido, sistema pega o
>   `default_prescriber` do Patient. Pra sobrescrever, passe explicitamente.
> - Campo `prescriber` aceita o ID do Prescriber (ex: `PRES-2026-00007`).

### A.5. Submeter Sales Order

```http
POST {{URL}}/api/method/frappe.client.submit
{ "doc": <doc INTEIRO retornado em A.4> }
```

> Mandar o doc completo evita `TimestampMismatchError`. Em n8n, use o output
> de A.4 direto.

### A.6. Reservar lote

**Modo 1 — manual** (você escolheu o FPB):

```http
POST {{URL}}/api/method/future_production_reserve_sales_order_item
{
  "sales_order": "SAL-ORD-2026-00031",
  "sales_order_item": "<row_id de A.4>",
  "future_production_batch": "FPB-2026-00003",
  "qty": 10,
  "priority": 100
}
```

**Modo 2 — automático** (sistema escolhe via FIFO):

```http
POST {{URL}}/api/method/future_production_auto_reserve_sales_order
{ "sales_order": "SAL-ORD-2026-00031" }
```

### A.7. Confirmar estado final

```http
GET {{URL}}/api/resource/Sales Order/SAL-ORD-2026-00031
```

Conferir nos items: `fp_reserved_qty`, `fp_reservation_status="Reservado"`, `fp_future_production_batch="FPB-...".

### Fluxo n8n recomendado

```
[HTTP GET FPB list] ─► [HTTP GET/POST Customer] ─► [Loop pacientes: GET/POST Patient]
                                                           │
                                                           ▼
                                                  [HTTP POST Sales Order]
                                                           │
                                                           ▼
                                                  [HTTP POST submit]
                                                           │
                                                           ▼
                                                  [HTTP POST reserve (manual ou auto)]
                                                           │
                                                           ▼
                                                  [HTTP GET confirmação]
```

### Demais etapas (Produção → Faturamento)

| Etapa | Endpoint |
|---|---|
| Criar Work Order | `POST /api/method/future_production_create_work_order` |
| Criar Batch físico | `POST /api/resource/Batch` |
| Atualizar produced_qty | `PUT /api/resource/Future Production Batch/<name>` |
| Stock Entry Manufacture | `POST /api/resource/Stock Entry` + submit |
| Liberar FIFO | `POST /api/method/future_production_release_batch` |
| Pick List | `POST /api/resource/Pick List` + submit |
| Delivery Note | `POST /api/method/erpnext.stock.doctype.pick_list.pick_list.create_delivery_note` |
| Sales Invoice | `POST /api/method/erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice` |
| Payment Entry | `POST /api/resource/Payment Entry` + submit |
| Replanejar pendência | `POST /api/method/future_production_replan_pending_qty` |
| Recalcular saldos | `POST /api/method/future_production_recalculate_batch` |
| Cancelar reserva | `POST /api/method/frappe.client.cancel` (doctype=Production Reservation) |

Detalhes de payload de cada um: ver [`05-api-reference.md`](05-api-reference.md).

---

## Opção B — Endpoint único custom (a construir)

> **Vantagens**: 1 chamada em vez de 7-8. Atômico (se algo falha, nada
> persiste). n8n fica trivial: 1 nó HTTP.
> **Custo**: precisa criar o Server Script (script Python rodando dentro do
> ERPNext). Roda 1 vez no setup, depois fica disponível como rota.

### B.1. Endpoint `future_production_list_available_batches`

```http
POST {{URL}}/api/method/future_production_list_available_batches
{ "item_code": "TIR00060" }
```

Resposta:
```json
{ "message": {
  "item_code": "TIR00060",
  "batches": [
    {
      "name": "FPB-2026-00003",
      "production_code": "AMP-2026-05-20-001",
      "planned_qty": 2000,
      "available_qty": 500,
      "planned_production_date": "2026-05-20",
      "status": "Reservada Parcialmente"
    }
  ]
}}
```

### B.2. Endpoint `future_production_issue_order` (TUDO em 1)

```http
POST {{URL}}/api/method/future_production_issue_order
{
  "customer": {
    "name": "DEMO-PF-Customer",
    "customer_name": "Cliente Demo",
    "customer_type": "Individual",
    "customer_group": "Comercial",
    "territory": "Brazil"
  },
  "item_code": "TIR00060",
  "qty": 10,
  "rate": 100,
  "warehouse": "Produtos Acabados - I",
  "company": "Injmedpharma",
  "delivery_date": "2026-06-17",
  "prescriber_default": {
    "name": "PRES-2026-00007",
    "cpf": "12345678909",
    "council_type": "CRM",
    "council_number": "12345",
    "council_state": "SP",
    "full_name": "Dr. José da Silva"
  },
  "patients": [
    { "patient_name": "Maria Aparecida", "cpf": "11144477735", "qty": 3,
      "mobile": "11999990001", "gender": "Feminino",
      "city": "São Paulo", "state": "SP",
      "prescriber": "PRES-2026-00007" },
    { "patient_name": "João Silva", "cpf": "52998224725", "qty": 2,
      "gender": "Masculino", "city": "São Paulo", "state": "SP",
      "prescriber": "PRES-2026-00007" },
    { "patient_name": "Ana Beatriz", "cpf": "39053344705", "qty": 4,
      "gender": "Feminino", "city": "Campinas", "state": "SP",
      "prescriber": "PRES-2026-00011" },
    { "patient_name": "Carlos Souza", "cpf": "12345678909", "qty": 1,
      "gender": "Masculino", "city": "São Paulo", "state": "SP",
      "prescriber": "PRES-2026-00007" }
  ],
  "reservation_mode": "auto",
  "future_production_batch": null,
  "priority": 100
}
```

> **Comportamento esperado do endpoint Issue Order**:
> - Se `prescriber` em cada paciente for um **ID existente** (`PRES-...`), usa direto
> - Se for um **objeto** com CPF + conselho, faz upsert (cria se não existe, reusa se CPF já cadastrado)
> - Se omitido na linha do paciente, usa `default_prescriber` do Patient cadastrado
> - Se Patient não existe ainda (será criado neste call), `prescriber` é obrigatório

Resposta:
```json
{ "message": {
  "sales_order": "SAL-ORD-2026-00031",
  "customer": "DEMO-PF-Customer",
  "patients": [
    {"patient": "PAC-2026-00014", "name": "Maria Aparecida", "qty": 3},
    {"patient": "PAC-2026-00015", "name": "João Silva", "qty": 2},
    {"patient": "PAC-2026-00016", "name": "Ana Beatriz", "qty": 4},
    {"patient": "PAC-2026-00017", "name": "Carlos Souza", "qty": 1}
  ],
  "reservations": [
    {"reservation": "PR-2026-00027",
     "future_production_batch": "FPB-2026-00003",
     "qty": 10}
  ],
  "available_qty_after": 1990
}}
```

### Comparação rápida

| Critério | Opção A (chain) | Opção B (endpoint único) |
|---|---|---|
| Calls do n8n | 6-8 + loop pacientes | **1** |
| Funciona hoje? | ✅ Sim | ❌ Precisa setup_07 |
| Erro parcial | Difícil rollback manual | Atômico (transação) |
| Idempotência | Você implementa | Server faz (upsert) |
| Mudança de regra | Editar fluxo n8n | Editar Server Script |

### Quando usar cada uma

- **A** se: quer começar **já**, não pode mexer no servidor agora, time conhece n8n bem
- **B** se: quer fluxo limpo a longo prazo, vai escalar pra dezenas de chamadas/dia, quer auditoria centralizada

---

# Anexo II — Disponibilizar este Manual dentro do ERPNext

> Como subir este documento (HTML) **dentro** do ERPNext para os usuários
> acessarem direto no menu.

## Caminho 1 — Web Page (recomendado)

ERPNext tem o DocType nativo `Web Page` que serve HTML em `/<slug>`.

1. Menu → *Website → Web Page → + New*
2. Preencher:
   ```
   Title:      Manual Operacional — Produção Futura
   Route:      manual-operacional        (vira /manual-operacional)
   Published:  ☑
   Main Section: < cole o HTML gerado aqui >
   ```
3. **Save**

Acesso: `https://erp.suaempresa.com.br/manual-operacional`.

> **Atenção CSS**: o `Web Page` aplica o tema do site por cima. Se o HTML
> estiver com CSS inline (como o gerado), respeita as cores. Se conflitar,
> use seção *Header* + *Footer* só com o `<body>` interno.

## Caminho 2 — File anexado a Workspace

1. Menu → *Build → File → + New → Upload* → suba `manual-operacional.html`
2. Copie a URL retornada (ex: `/files/manual-operacional.html`)
3. Vá no Workspace **Produção Futura**
4. *Edit → Add Custom Block → Header com link*:
   ```html
   <a href="/files/manual-operacional.html" target="_blank">
     📖 Abrir Manual Operacional
   </a>
   ```
5. **Save** workspace

## Caminho 3 — Help Article (knowledge base)

Se o site ERPNext tem app *Help Desk* / *Knowledge Base* instalado:

1. *Knowledge Base → New Article*
2. Cole o markdown direto (renderiza pra HTML)
3. Categoria: "Produção Futura"

## Caminho 4 — API custom para servir o HTML

Server Script (script type API):

```python
# api_method: get_manual_operacional
with open(frappe.get_site_path("public", "files", "manual-operacional.html")) as f:
    frappe.response["type"] = "page"
    frappe.response["data"] = f.read()
```

Acesso: `GET /api/method/get_manual_operacional`.

---

# Anexo III — Onde encontrar os arquivos gerados

| Formato | Arquivo | Uso |
|---|---|---|
| Markdown (fonte) | `docs/11-manual-operacional.md` | Editar e regerar |
| HTML | `docs/dist/manual-operacional.html` | Upload no ERPNext / browser |
| DOCX | `docs/dist/manual-operacional.docx` | Editar no Word/Google Docs |
| PDF | `docs/dist/manual-operacional.pdf` | Imprimir / distribuir |

Pra regerar após mudar o Markdown, ver `docs/dist/README.md`.
