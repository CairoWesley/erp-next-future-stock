# Etapa 3 — Cadastrar Médico (Prescriber + Council)

> Cria Prescriber no ERPNext a partir de Company HubSpot. Pra Injmedpharma,
> Company "Volpi" (médico revende) carrega CRM/UF/número + nome do
> responsável técnico no próprio record da Company.

## Descoberta importante

HubSpot Company Injmedpharma tem properties customizadas pra dados médicos:

| Property HubSpot | Significado |
|---|---|
| `consec` (Conselho) | Tipo (CRM/CRO/...) com prefix numérico ("1 - CRM") |
| `numero_do_conselho` | Número do registro |
| `estado_do_conselho` | UF (SP, RJ, ...) |
| `status_do_crm_medico` | Status (Regular, Cassado, ...) |
| `nome_do_responsavel_tecnico` | Nome completo do médico RT |
| `cpf_do_responsavel_tecnico` | CPF do médico (pode = cpfcnpj da empresa pra PF) |
| `tipo_de_cliente` | Categoria interna ("Volpi" = médico que revende) |
| `tipo_de_documento` | CPF ou CNPJ |

> Isso difere do que tinha sido planejado em payloads_prescribers.py
> (`medico_nome`, `medico_crm`, `medico_uf`). O portal real da Injmedpharma
> usa property names diferentes. Sync precisa adaptar.

## DocType Prescriber + child Prescriber Council

```
Prescriber (parent, 1 CPF único)
  ├─ cpf          Data unique
  ├─ full_name    Data
  ├─ specialty    Data
  ├─ email        Data
  ├─ mobile       Data
  └─ councils[]   Table → Prescriber Council
                    ├─ council_type    Select [CRM, CRO, CRBM, ...]
                    ├─ council_number  Data
                    ├─ council_state   Select [SP, RJ, ...]
                    ├─ council_status  Select [Ativo, Cassado, Suspenso]
                    ├─ specialty       Data
                    └─ is_primary      Check
```

Um Prescriber pode ter múltiplos conselhos (CRM-SP + CRM-RJ + CRBM). SO
linka conselho específico usado no pedido.

## Exemplo executado em prod (2026-06-02)

Médico GUSTAVO DALMORA, Company HubSpot id 54895733889.

### Properties HubSpot do médico

```
cpfcnpj:                       04294209941
nome_do_responsavel_tecnico:   GUSTAVO DALMORA
cpf_do_responsavel_tecnico:    04294209941   (mesmo da empresa — médico PF)
consec:                        1 - CRM
numero_do_conselho:            223389
estado_do_conselho:            SP
status_do_crm_medico:          Regular
tipo_de_cliente:               Volpi
```

### Payload Prescriber

```python
POST /api/resource/Prescriber
{
    "doctype": "Prescriber",
    "cpf": "04294209941",
    "full_name": "GUSTAVO DALMORA",
    "email": "gustavodalmora@gmail.com",
    "mobile": "+11913169667",
    "councils": [
        {
            "council_type": "CRM",
            "council_number": "223389",
            "council_state": "SP",
            "council_status": "Ativo",
            "is_primary": 1
        }
    ]
}
→ name: "00073"
   councils[0].name: "aht0q4v142" (random child row name)
```

### Updates downstream

```python
# Patient 00068: aponta médico padrão
PUT /api/resource/Patient/00068
{
    "default_prescriber": "00073",
    "default_council_label": "CRM-SP 223389"
}

# Customer 00067: grupo "Volpi" (categoria HubSpot)
PUT /api/resource/Customer/00067
{
    "customer_group": "Volpi"
}
```

### Customer Group "Volpi" criado

```python
POST /api/resource/Customer Group
{
    "doctype": "Customer Group",
    "customer_group_name": "Volpi",
    "parent_customer_group": "Todos os Grupos de Clientes"
}
→ name: "Volpi"
```

## Convenção Volpi

`Tipo de Cliente: Volpi` no HubSpot = **médico que compra pra revender ao paciente próprio**.

Modelo de negócio:
- Médico (Volpi) compra Tirzepatida da Injmedpharma
- Médico revende/aplica no paciente próprio
- Paciente final pode ser:
  - O próprio médico (uso pessoal — caso comum em médicos endocrinologistas)
  - Paciente do médico (revenda)
- ERPNext: `Customer = médico (paga)`, `Patient = quem consome (pode ser médico)`

## Validações

`setup_07_prescribers` aplica:
- CPF único entre Prescribers (não cria 2 prescribers com mesmo CPF)
- Pelo menos 1 council obrigatório (ValidationError "Cadastre pelo menos 1 conselho profissional")
- council_number único por (council_type, council_state)
- Se múltiplos councils, exatamente 1 com `is_primary=1`

## SO 00071 — limitação

Sales Order 00071 foi criado ANTES do Prescriber existir. fp_patients
ficou sem `prescriber` / `prescriber_council` (NULL). SO já submetida
(docstatus=1) e child fields não têm `allow_on_submit=1`, então update
direto bloqueia.

Opções pra corrigir histórico:
1. Cancel SO + Edit + Resubmit (perde Production Reservation 00072)
2. Aceitar lacuna histórica + garantir SO futuros saem com prescriber

Decisão: **aceitar lacuna histórica**. Patient 00068 agora tem
`default_prescriber=00073` → próximos SO com esse Patient auto-fetch.

## URLs

```
Prescriber:   https://erp.injemedpharma.com.br/app/prescriber/00073
Patient:      https://erp.injemedpharma.com.br/app/patient/00068
Customer:     https://erp.injemedpharma.com.br/app/customer/00067
Group Volpi:  https://erp.injemedpharma.com.br/app/customer-group/Volpi
```

## TODO

- [ ] **Sync HubSpot Prescribers**: estender `tools/sync_products_hubspot.py`
  pra também ler Companies com `tipo_de_cliente=Volpi` → criar Prescribers
  no ERPNext. Properties: nome_do_responsavel_tecnico, cpf_do_responsavel_tecnico,
  consec, numero_do_conselho, estado_do_conselho.
- [ ] **Issue Order endpoint**: setup_14 hubspot_issue_order_v2.json precisa
  receber medico_cpf via property (mesma estratégia), não calcular CPF stub.
- [ ] **n8n workflow**: webhook HubSpot Deal Stage Change → busca Company →
  busca medico data → POST future_production_issue_order com prescribers[].

## Próximo

[Etapa 4 — Cadastrar Paciente](04-cadastrar-paciente.md)
