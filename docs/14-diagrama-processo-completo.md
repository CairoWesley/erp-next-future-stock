# 14 — Diagrama do Processo Completo

> Visão **simples** do fluxo do início ao fim. Sem jargão técnico.
> Cada etapa mostra: **o que faz**, **onde no sistema**, e **quais dados ficam visíveis**.
>
> Depois do diagrama, seção de integração API por etapa.

---

## Diagrama Geral — Início ao Fim

```
                    ┌─────────────────────────────────────┐
                    │   ANTES (CADASTROS UMA VEZ SÓ)      │
                    └─────────────┬───────────────────────┘
                                  │
        ┌─────────────────────────┼────────────────────────┐
        │                         │                        │
        ▼                         ▼                        ▼
   ┌──────────┐           ┌──────────────┐         ┌──────────────┐
   │ CLIENTE  │           │   MÉDICO     │         │  PACIENTE    │
   │  (PJ/PF) │           │ (PRESCRITOR) │         │              │
   │          │           │              │         │              │
   │ Tela:    │           │ Tela:        │         │ Tela:        │
   │ Customer │           │ Prescriber   │         │ Patient      │
   └──────────┘           └──────────────┘         └──────────────┘
                                                          │
                                                          │
                          ┌───────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────┐
        │   PROCESSO PRINCIPAL                 │
        └─────────────┬───────────────────────┘
                      │
                      ▼
            ┌─────────────────────┐
            │  1. CRIAR LOTE      │  ◄── Planejamento avisa: "vou produzir X em Y"
            │   PLANEJADO (FPB)   │      Sistema reserva capacidade
            │                     │
            │ Tela:               │      Quem usa: PLANEJAMENTO
            │ Lote de Produção    │
            │ Futura              │
            └──────────┬──────────┘
                       │
                       │  Saldo livre = 2000 ampolas
                       ▼
            ┌─────────────────────┐
            │  2. EMITIR PEDIDO   │  ◄── Vendedor cria SO com pacientes
            │   (SALES ORDER)     │
            │                     │
            │ Tela:               │      Quem usa: COMERCIAL
            │ Sales Order         │
            │                     │
            │ Linha de paciente:  │
            │  - Nome+CPF+Email   │      ◄── DADOS VISÍVEIS direto na linha
            │  - Cidade+UF        │
            │  - Médico+CRM       │
            │  - Item+Qty         │
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  3. RESERVAR        │  ◄── Botão "Reservar Auto" no SO
            │   (PR)              │      Sistema decrementa saldo do FPB
            │                     │
            │ Tela:               │      Quem usa: COMERCIAL
            │ Production          │
            │ Reservation         │
            └──────────┬──────────┘
                       │
                       │  Esperar produção...
                       ▼
            ┌─────────────────────┐
            │  4. PRODUZIR        │  ◄── Fábrica termina lote físico
            │   (BATCH + UPDATE)  │
            │                     │
            │ Telas:              │      Quem usa: PRODUÇÃO
            │ Batch (criar lote)  │
            │ FPB (atualizar      │
            │  produced_qty)      │
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  5. ENTRADA NO      │  ◄── Stock Entry tipo Manufacture
            │  ESTOQUE FÍSICO     │      Sistema sabe que tem 2000 ampolas
            │                     │      reais no depósito
            │ Tela:               │
            │ Stock Entry         │      Quem usa: PRODUÇÃO
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  6. LIBERAR         │  ◄── Botão "Liberar Reservas" no FPB
            │   RESERVAS          │      Sistema distribui FIFO
            │   (FIFO)            │
            │                     │      Quem usa: SUPERVISOR PRODUÇÃO
            │ Tela:               │
            │ FPB → Actions       │
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  7. ALOCAR LOTE     │  ◄── Botão "Alocar Batch por Paciente"
            │   POR PACIENTE      │      Cada paciente sabe qual lote vai receber
            │                     │
            │ Tela:               │      Quem usa: COMERCIAL/EXPEDIÇÃO
            │ SO → botão custom   │
            │                     │
            │ Linha de paciente   │      ◄── DADOS VISÍVEIS:
            │  agora mostra:      │       - Lote atribuído
            │                     │       - Validade do lote
            │                     │       - Status: Alocado
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  8. ENTREGAR        │  ◄── Delivery Note baixa estoque
            │   (DN)              │      Imprime pra ir junto com a mercadoria
            │                     │
            │ Tela:               │      Quem usa: EXPEDIÇÃO
            │ Delivery Note       │
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  9. FATURAR         │  ◄── Sales Invoice gera contábil
            │   (SI)              │      (futuro: emite NF via ASAAS)
            │                     │
            │ Tela:               │      Quem usa: FINANCEIRO
            │ Sales Invoice       │
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  10. RECEBER        │  ◄── Payment Entry confirma pagamento
            │    PAGAMENTO        │      SI vira "Paid"
            │                     │
            │ Tela:               │      Quem usa: FINANCEIRO
            │ Payment Entry       │
            └──────────┬──────────┘
                       │
                       ▼
            ┌─────────────────────┐
            │  11. DISPENSAR      │  ◄── Farmacêutico entrega ao paciente
            │    + ETIQUETA       │      Imprime etiqueta Zebra
            │    ZEBRA            │      (PENDENTE construção)
            │                     │
            │ Tela:               │      Quem usa: FARMÁCIA
            │ Dispensation        │
            └─────────────────────┘
```

---

## Etapa por etapa — onde no sistema e dados visíveis

### Antes do processo — Cadastros mestres

#### Cliente (quem paga)

**Tela**: *Selling → Customer*
**URL**: `https://erp.suaempresa.com.br/app/customer`

**Dados visíveis ao abrir um cliente**:
- Customer Name + Type (Individual ou Company)
- CNPJ (se PJ) ou CPF (se PF) em **Tax ID**
- Endereço de cobrança
- Contatos (telefone + e-mail)
- Customer Group + Territory (sempre "Comercial" + "Brazil")
- Histórico de pedidos (lista lateral)

#### Médico Prescritor

**Tela**: *Produção Futura → Prescriber*
**URL**: `https://erp.suaempresa.com.br/app/prescriber`

**Dados visíveis ao abrir um Prescriber**:
- Nome completo + CPF
- **Conselho**: tipo (CRM/CRO/CRF/CRBM/...) + número + UF + status
- Especialidade
- Contato (celular, e-mail)
- Vínculo com Customer (se trabalha em clínica)
- Endereço profissional
- Lista lateral: pacientes vinculados a este médico

#### Paciente

**Tela**: *Produção Futura → Patient*
**URL**: `https://erp.suaempresa.com.br/app/patient`

**Dados visíveis ao abrir um Paciente**:
- Nome + CPF + RG
- Data de nascimento + Gênero
- **Médico padrão** (Link clicável → abre Prescriber completo)
- Celular, telefone, e-mail
- Endereço completo
- Lista lateral: pedidos onde este paciente aparece

---

### 1. Criar Lote Planejado (FPB)

**Quem usa**: Planejamento
**Tela**: *Produção Futura → Lote de Produção Futura → + New*
**URL**: `https://erp.suaempresa.com.br/app/future-production-batch`

**O que preencher**:
- Código da Produção (ex: AMP-2026-05-20-001)
- Item a produzir
- Quantidade planejada (ex: 2000)
- Data prevista de produção
- Depósito destino

**Ações**: Save → Submit

**Dados visíveis após criar**:
| Campo | Valor inicial |
|---|---|
| Planejado | 2000 |
| Reservado | 0 |
| **Disponível** | **2000** ← saldo livre pra reservas |
| Produzido | 0 |
| Liberado | 0 |
| Pendente | 0 |
| Status | Aberta para Reserva |

---

### 2. Emitir Pedido (Sales Order)

**Quem usa**: Comercial
**Tela**: *Selling → Sales Order → + New*
**URL**: `https://erp.suaempresa.com.br/app/sales-order`

**O que preencher**:
1. Customer
2. Date + Delivery Date
3. Items table: item_code + qty + rate + warehouse
4. **Pacientes table** (seção "Pacientes")

**Linha de paciente — dados visíveis automaticamente**:

```
┌─────────────────────────────────────────────────────────────────────┐
│  PACIENTES  (cada linha)                                             │
├─────────────────────────────────────────────────────────────────────┤
│  Patient:          PAC-2026-00014 ▼   [clique → abre cadastro]      │
│  Patient Name:     Maria Aparecida    (← auto preenche)             │
│  CPF:              111.444.777-35     (← auto preenche)             │
│  Celular:          11999990001        (← auto preenche)             │
│  Gênero:           Feminino           (← auto preenche)             │
│  Nascimento:       1980-05-20         (← auto preenche)             │
│  E-mail:           maria@exemplo.com  (← auto preenche)             │
│  Cidade:           São Paulo          (← auto preenche)             │
│  UF:               SP                 (← auto preenche)             │
│                                                                     │
│  Item:             TIR00060                                          │
│  Qty:              3                                                 │
│                                                                     │
│  Prescriber:       PRES-2026-00007 ▼  [clique → abre Prescriber]    │
│  Médico:           Dr. José da Silva  (← auto preenche)             │
│  Conselho:         CRM                (← auto preenche)             │
│  Nº Conselho:      12345              (← auto preenche)             │
│  UF Conselho:      SP                 (← auto preenche)             │
│  Status Conselho:  Ativo              (← auto preenche)             │
│                                                                     │
│  ── Após etapa 7 (alocação) também aparecem: ──                     │
│  Lote Atribuído:   LOT-AMP-2026-05-20-001                            │
│  Validade do Lote: 2027-05-20                                        │
│  Fabricação:       2026-05-20                                        │
│  Qtd Alocada:      3                                                 │
│  Status Alocação:  Alocado                                           │
└─────────────────────────────────────────────────────────────────────┘
```

> **Regra**: soma das qty dos pacientes por item = qty do item no SO.

**Ações**: Save → Submit

---

### 3. Reservar (Production Reservation)

**Quem usa**: Comercial (mesmo que criou o SO)
**Tela**: dentro do **Sales Order já submetido**, botão **Produção Futura → Reservar Automaticamente**

**O que acontece**:
- Sistema procura FPBs do item com saldo
- Ordena por data (FIFO: mais antigo primeiro)
- Decrementa available_qty do FPB
- Cria documento Production Reservation
- Atualiza no SO Item os campos:
  - `fp_reserved_qty`
  - `fp_future_production_batch`
  - `fp_reservation_status = Reservado`

**Onde inspecionar depois**:
- *Produção Futura → Reserva de Produção* → vê PR criada
- No SO Item, role até "Produção Futura" → vê tudo preenchido

---

### 4. Produzir (Batch + atualizar FPB)

**Quem usa**: Operador de produção
**Telas**: 2 telas

**4.1 Criar Batch físico**

*Stock → Batch → + New*
- Batch ID (ex: LOT-AMP-2026-05-20-001)
- Item, Batch Qty real, datas de fabricação e validade

**4.2 Atualizar FPB**

Abrir o FPB submetido, editar 2 campos:
- Quantidade Produzida (ex: 2000)
- Lote Real Produzido (link pro Batch criado)

**Save** → status do FPB muda automaticamente.

---

### 5. Entrada no Estoque Físico (Stock Entry)

**Quem usa**: Produção
**Tela**: *Stock → Stock Entry → + New*

**O que preencher**:
- Stock Entry Type: **Manufacture**
- Items: TIR00060, qty=2000, warehouse=destino, batch_no, marcar **is_finished_item**

**Save → Submit**

Agora o ERPNext sabe que há 2000 ampolas físicas no depósito.

---

### 6. Liberar Reservas (FIFO)

**Quem usa**: Supervisor de produção
**Tela**: dentro do **FPB submetido**, botão **Actions → Liberar Reservas**

**O que acontece**:
- Sistema pega `produced_qty` do FPB
- Distribui entre as PRs do FPB seguindo FIFO (priority asc, payment_date asc, etc)
- Cada PR ganha `released_qty` + `release_batch_no`
- SO Item atualiza espelho

**Onde inspecionar**:
- *FPB → Status = "Liberada Totalmente" ou "Parcialmente"*
- *Production Reservation → Status = "Liberado" ou "Parcialmente Liberado"*

---

### 7. Alocar Lote por Paciente

**Quem usa**: Comercial / Expedição
**Tela**: dentro do **Sales Order**, botão **Alocar Batch por Paciente**
(ou via API)

**O que acontece**:
- Sistema percorre PRs já liberadas do SO
- Distribui `release_batch_no` entre as linhas `fp_patients` (FIFO)
- Preenche em cada linha: `batch_no`, `allocated_qty`, `batch_status=Alocado`

**Dados visíveis depois**:

```
PACIENTES após alocação:
┌────────────────┬─────┬──────────────┬───────────┬─────────────┐
│ Patient        │ Qty │ Batch        │ Validade  │ Status      │
├────────────────┼─────┼──────────────┼───────────┼─────────────┤
│ Maria Aparec.  │  3  │ LOT-...-001  │ 2027-05-20│ Alocado     │
│ João Silva     │  2  │ LOT-...-001  │ 2027-05-20│ Alocado     │
│ Ana Beatriz    │  4  │ LOT-...-001  │ 2027-05-20│ Alocado     │
│ Carlos Souza   │  1  │ LOT-...-001  │ 2027-05-20│ Alocado     │
└────────────────┴─────┴──────────────┴───────────┴─────────────┘
```

---

### 8. Entregar (Delivery Note)

**Quem usa**: Expedição
**Tela**: *Stock → Delivery Note → + New*
(ou: dentro do SO, botão **Create → Delivery Note**)

**O que acontece**:
- Items vêm do SO automaticamente
- Você preenche batch_no por linha
- Submit → baixa estoque (-2000 do Bin)
- Cria Stock Ledger Entry
- SO Item: `delivered_qty` += qty entregue

---

### 9. Faturar (Sales Invoice)

**Quem usa**: Financeiro
**Tela**: dentro do **Delivery Note submetido**, botão **Create → Sales Invoice**

**O que acontece**:
- Items, qty, rate vêm da DN
- Você confere impostos
- Submit → gera lançamento contábil
- Status SO: "To Bill" → "Completed"

**Após integração ASAAS (sprint 2)**: emissão automática de NFe.

---

### 10. Receber Pagamento (Payment Entry)

**Quem usa**: Financeiro
**Tela**: dentro do **Sales Invoice**, botão **Create → Payment**

**O que preencher**:
- Posting Date (data do pagamento)
- Paid Amount
- Mode of Payment (Pix/Boleto/Transferência)
- Bank Account de destino

**Save → Submit** → SI fica "Paid".

**Após integração ASAAS (sprint 2)**: webhook ASAAS atualiza automaticamente quando cliente paga o boleto.

---

### 11. Dispensar + Etiqueta Zebra (PENDENTE)

**Quem usa**: Farmacêutico
**Tela**: a construir — `Dispensation` DocType

**Fluxo proposto**:
1. Farmacêutico abre o SO já entregue (DN submetida)
2. Role até **Pacientes** — cada linha tem `batch_no` preenchido (etapa 7)
3. Botão **Criar Dispensação** por paciente
4. Sistema cria documento Dispensation com:
   - Patient + CPF + dados
   - Item + Batch + qty + validade
   - Data/hora dispensação
   - Farmacêutico responsável
5. Botão **Imprimir Etiqueta Zebra**
6. Sistema gera ZPL e envia via Zebra BrowserPrint pra impressora local
7. Etiqueta sai com: nome paciente, CPF, item, lote, validade, barcode

---

# PARTE 2 — Integração API por Etapa

> Pra fazer o mesmo fluxo por **API** (sem tocar UI), use os endpoints abaixo.
> Auth header padrão em todas:
>
> ```
> Authorization: token <API_KEY>:<API_SECRET>
> Content-Type: application/json
> ```

---

## Etapa 0 — Cadastros mestres (CRUD REST)

### Customer

```http
POST /api/resource/Customer
{
  "customer_name": "Clínica São Paulo Ltda",
  "customer_type": "Company",
  "customer_group": "Comercial",
  "territory": "Brazil",
  "tax_id": "12345678000190"
}
```

### Prescriber

```http
POST /api/resource/Prescriber
{
  "full_name": "Dr. José da Silva",
  "cpf": "11144477735",
  "council_type": "CRM",
  "council_number": "12345",
  "council_state": "SP",
  "council_status": "Ativo",
  "specialty": "Endocrinologia"
}
```

### Patient

```http
POST /api/resource/Patient
{
  "patient_name": "Maria Aparecida Silva",
  "cpf": "11144477735",
  "gender": "Feminino",
  "country": "Brazil",
  "default_prescriber": "PRES-2026-00007",
  "mobile": "11999990001",
  "email": "maria@exemplo.com",
  "city": "São Paulo",
  "state": "SP"
}
```

> **Lookup antes**: faça `GET /api/resource/Patient?filters=[["cpf","=","..."]]`
> pra reusar Patient existente.

---

## Etapa 1 — Criar FPB

```http
POST /api/resource/Future Production Batch
{
  "production_code": "AMP-2026-05-20-001",
  "company": "Sua Empresa Ltda",
  "item_code": "TIR00060",
  "planned_qty": 2000,
  "planned_production_date": "2026-05-20",
  "target_warehouse": "Produtos Acabados - I",
  "status": "Aberta para Reserva"
}

# Submeter
POST /api/method/frappe.client.submit
{ "doc": <body retornado acima COM modified> }
```

---

## Etapa 2 — Criar SO com fp_patients

```http
POST /api/resource/Sales Order
{
  "customer": "Clínica São Paulo Ltda",
  "company": "Sua Empresa Ltda",
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
    { "patient": "PAC-2026-00014", "item_code": "TIR00060",
      "qty": 3, "prescriber": "PRES-2026-00007" },
    { "patient": "PAC-2026-00015", "item_code": "TIR00060",
      "qty": 2, "prescriber": "PRES-2026-00007" },
    { "patient": "PAC-2026-00016", "item_code": "TIR00060",
      "qty": 4, "prescriber": "PRES-2026-00011" },
    { "patient": "PAC-2026-00017", "item_code": "TIR00060",
      "qty": 1, "prescriber": "PRES-2026-00007" }
  ]
}

# Guarda data.name (SO) e data.items[0].name (row_id pra reserva manual)
# Submeter:
POST /api/method/frappe.client.submit
{ "doc": <body retornado> }
```

---

## Etapa 3 — Reservar (Auto)

```http
POST /api/method/future_production_auto_reserve_sales_order
{ "sales_order": "SAL-ORD-2026-00031" }
```

**Resposta**:
```json
{
  "message": {
    "reservations": [
      {"reservation": "PR-...", "future_production_batch": "FPB-...", "qty": 10}
    ]
  }
}
```

---

## Etapa 4 — Produzir

```http
# 4.1 — Criar Batch físico
POST /api/resource/Batch
{
  "batch_id": "LOT-AMP-2026-05-20-001",
  "item": "TIR00060",
  "batch_qty": 2000,
  "manufacturing_date": "2026-05-20",
  "expiry_date": "2027-05-20"
}

# 4.2 — Atualizar FPB
PUT /api/resource/Future Production Batch/FPB-2026-00003
{
  "produced_qty": 2000,
  "batch_no": "LOT-AMP-2026-05-20-001"
}
```

---

## Etapa 5 — Stock Entry Manufacture

```http
POST /api/resource/Stock Entry
{
  "stock_entry_type": "Manufacture",
  "company": "Sua Empresa Ltda",
  "posting_date": "2026-05-20",
  "items": [{
    "item_code": "TIR00060",
    "t_warehouse": "Produtos Acabados - I",
    "qty": 2000,
    "basic_rate": 50,
    "batch_no": "LOT-AMP-2026-05-20-001",
    "use_serial_batch_fields": 1,
    "is_finished_item": 1
  }]
}

# Submeter:
POST /api/method/frappe.client.submit
{ "doc": <body> }
```

---

## Etapa 6 — Liberar Reservas FIFO

```http
POST /api/method/future_production_release_batch
{ "future_production_batch": "FPB-2026-00003" }
```

**Resposta**:
```json
{
  "message": {
    "released_count": 4,
    "released_qty": 1850,
    "pending_release_qty": 0
  }
}
```

---

## Etapa 7 — Alocar Batch por Paciente

```http
POST /api/method/future_production_allocate_patient_batches
{ "sales_order": "SAL-ORD-2026-00031" }
```

**Resposta**:
```json
{
  "message": {
    "sales_order": "SAL-ORD-2026-00031",
    "allocated_rows": 4
  }
}
```

---

## Etapa 8 — Delivery Note

```http
POST /api/resource/Delivery Note
{
  "customer": "Clínica São Paulo Ltda",
  "company": "Sua Empresa Ltda",
  "posting_date": "2026-05-22",
  "items": [{
    "item_code": "TIR00060",
    "qty": 10,
    "rate": 100,
    "warehouse": "Produtos Acabados - I",
    "batch_no": "LOT-AMP-2026-05-20-001",
    "against_sales_order": "SAL-ORD-2026-00031",
    "so_detail": "<row_id>"
  }]
}

# Submeter:
POST /api/method/frappe.client.submit
{ "doc": <body> }
```

---

## Etapa 9 — Sales Invoice (a partir do DN)

```http
POST /api/method/erpnext.stock.doctype.delivery_note.delivery_note.make_sales_invoice
{ "source_name": "MAT-DN-2026-00001" }

# Pega o doc retornado em message, insere:
POST /api/method/frappe.client.insert
{ "doc": <message do call acima> }

# Submeter:
POST /api/method/frappe.client.submit
{ "doc": <body do insert> }
```

---

## Etapa 10 — Payment Entry

```http
POST /api/resource/Payment Entry
{
  "payment_type": "Receive",
  "party_type": "Customer",
  "party": "Clínica São Paulo Ltda",
  "paid_amount": 1000,
  "received_amount": 1000,
  "mode_of_payment": "Bank Draft",
  "posting_date": "2026-06-22",
  "references": [{
    "reference_doctype": "Sales Invoice",
    "reference_name": "ACC-SINV-2026-00001",
    "allocated_amount": 1000
  }]
}

# Submeter
POST /api/method/frappe.client.submit
{ "doc": <body> }
```

---

## Etapa 11 — Dispensação (PENDENTE)

A construir. Endpoint planejado:

```http
POST /api/method/future_production_create_dispensation
{
  "sales_order": "SAL-ORD-2026-00031",
  "patient_row": "<row_id de fp_patients>",
  "pharmacist": "farmaceutico@suaempresa.com.br"
}

# Retorna nome da Dispensation criada

POST /api/method/future_production_print_zebra_label
{ "dispensation": "DISP-2026-00001" }

# Retorna { zpl: "^XA...^XZ" } pra enviar via BrowserPrint
```

---

# Resumo — Tela do ERPNext para cada etapa

| Etapa | Tela ERPNext | URL |
|---|---|---|
| Cliente | Customer | `/app/customer` |
| Médico | Prescriber | `/app/prescriber` |
| Paciente | Patient | `/app/patient` |
| 1. FPB | Future Production Batch | `/app/future-production-batch` |
| 2. Pedido | Sales Order | `/app/sales-order` |
| 3. Reserva | Production Reservation | `/app/production-reservation` |
| 4.1 Batch | Batch | `/app/batch` |
| 4.2 FPB update | Future Production Batch | mesmo |
| 5. Stock Entry | Stock Entry | `/app/stock-entry` |
| 6. Liberar | FPB → Actions | mesmo |
| 7. Alocar | SO → botão | mesmo |
| 8. DN | Delivery Note | `/app/delivery-note` |
| 9. SI | Sales Invoice | `/app/sales-invoice` |
| 10. Payment | Payment Entry | `/app/payment-entry` |
| 11. Dispensação | (a construir) | — |

**Workspace central**: `/app/producao-futura`
**Reports**: `/app/query-report/Mapa%20de%20Produção`
