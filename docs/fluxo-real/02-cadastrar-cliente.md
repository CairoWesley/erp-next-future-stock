# Etapa 2 — Cadastrar Cliente (Customer + Address + Contact)

> Cria entidade pagante no ERPNext a partir de HubSpot Company. Pra PF
> (Pessoa Física), HubSpot usa Company como "shell" do paciente —
> guardar CPF, endereço, contato. ERPNext recebe como `customer_type=Individual`.

## O que faz

Pra cada Deal HubSpot, 1 Customer ERPNext (idempotente por CPF/CNPJ).

```
HubSpot Company (PF shell)
  ├─ cpfcnpj            → Customer.tax_id
  ├─ name               → Customer.customer_name
  ├─ phone              → Customer.mobile_no + Address.phone
  └─ address fields     → Address record (linked to Customer)

HubSpot Contact (paciente)
  ├─ first/last name    → Contact record (linked to Customer)
  ├─ email              → Contact.email_ids[0]
  └─ phone              → Contact.phone_nos[0]
```

## Pré-requisitos

- `setup_15` aplicado (naming = `.#####` + Selling Settings)
- Customer Group "Pessoa Física" existente
- Territory "Brazil" existente

## Padrão Injmedpharma

- **PF**: `customer_type=Individual`, `customer_group=Pessoa Física`, `tax_id=CPF`
- **PJ**: `customer_type=Company`, `customer_group=Comercial`, `tax_id=CNPJ`
- Address linkado por `links: [{link_doctype: "Customer", link_name: customer_id}]`
- Address `is_primary_address=1` + `is_shipping_address=1` (mesmo endereço usa ambos por default)
- Contact linkado mesmo jeito + `is_primary_contact=1`

## Exemplo executado em prod (2026-06-02)

Deal HubSpot **60204250373** — Gustavo Dalmora.

### Payload Customer

```python
POST /api/resource/Customer
{
    "doctype": "Customer",
    "customer_name": "GUSTAVO DALMORA",
    "customer_type": "Individual",
    "customer_group": "Pessoa Física",
    "territory": "Brazil",
    "tax_id": "04294209941",
    "mobile_no": "+11913169667",
    "email_id": "gustavodalmora@gmail.com"
}
→ name: "00067"
```

### Payload Address

```python
POST /api/resource/Address
{
    "doctype": "Address",
    "address_title": "GUSTAVO DALMORA",
    "address_type": "Billing",
    "address_line1": "Rua Marechal Deodoro 902",
    "address_line2": "Sala 04",
    "city": "Concórdia",
    "state": "SC",
    "pincode": "89700003",
    "country": "Brazil",
    "email_id": "gustavodalmora@gmail.com",
    "phone": "+11913169667",
    "is_primary_address": 1,
    "is_shipping_address": 1,
    "links": [{"link_doctype": "Customer", "link_name": "00067"}]
}
→ name: "GUSTAVO DALMORA-Faturamento"
```

> **Address naming**: ERPNext usa autoname hardcoded `format:{address_title}-{address_type}`. Property Setter setup_15 não sobrescreve (limitação ERPNext core).

### Payload Contact

```python
POST /api/resource/Contact
{
    "doctype": "Contact",
    "first_name": "Gustavo",
    "last_name": "Dalmora",
    "email_ids": [{"email_id": "gustavodalmora@gmail.com", "is_primary": 1}],
    "phone_nos": [{
        "phone": "+11913169667",
        "is_primary_mobile_no": 1,
        "is_primary_phone": 1
    }],
    "is_primary_contact": 1,
    "links": [{"link_doctype": "Customer", "link_name": "00067"}]
}
→ name: "Gustavo Dalmora-00067-1"
```

> **Contact naming**: ERPNext usa autoname `{first_name} {last_name}-{customer_id}-{n}`. Mesma limitação.

## URLs ERPNext

```
Customer:  https://erp.injemedpharma.com.br/app/customer/00067
Address:   https://erp.injemedpharma.com.br/app/address/GUSTAVO DALMORA-Faturamento
Contact:   https://erp.injemedpharma.com.br/app/contact/Gustavo Dalmora-00067-1
```

## Erros comuns

| Erro | Causa | Fix |
|---|---|---|
| `LinkValidationError: Customer Group` | Group "All Customer Groups" não existe (instalação PT-BR usa "Todos os Grupos de Clientes") | Usar nome correto: `Pessoa Física`, `Comercial` |
| `LinkValidationError: Territory` | Idem com Território | `Brazil` ou `Todos os Territórios` |
| Customer criado com name = "GUSTAVO DALMORA" e não `00067` | Selling Settings.cust_master_name não foi configurado | Rodar `python setup/setup_15_naming_series.py` |

## Próximo

[Etapa 3 — Cadastrar Médico (Prescriber)](03-cadastrar-medico.md) — **PULADA neste exemplo** (deal HubSpot não tem médico estruturado; receita anexada manual).

[Etapa 4 — Cadastrar Paciente (Patient)](04-cadastrar-paciente.md)
