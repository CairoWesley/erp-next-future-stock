# Etapa 3 — Cadastrar Médico (Prescriber + Council)

> **PULADA neste exemplo concreto** (deal HubSpot 60204250373 não tem
> médico/CRM em property estruturada — receita anexada apenas como arquivo).

## Quando aplicar

Em pedidos com prescrição rastreável: anvisa exige link `prescrição → médico
prescritor`. Pra automatizar, HubSpot deve ter properties:

```
medico_nome     Data
medico_crm      Data  
medico_uf       Data
medico_cpf      Data  (opcional — preferível; CRM+UF como fallback)
```

> Setup HubSpot dessas properties **não foi feito** no portal Injmedpharma
> atual. TODO: adicionar via HubSpot Settings → Properties → Contacts /
> Deals → Create property.

## DocType Prescriber + child Prescriber Council

### Estrutura

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
                    ├─ council_status  Select [Ativo, Cassado, ...]
                    ├─ specialty       Data
                    └─ is_primary      Check
```

Um Prescriber pode ter múltiplos conselhos (CRM-SP + CRM-RJ + CRBM). SO
linka o conselho específico usado no pedido.

## Payload exemplo

```python
POST /api/resource/Prescriber
{
    "doctype": "Prescriber",
    "cpf": "12345678901",
    "full_name": "Dra. Maria Santos",
    "specialty": "Endocrinologia",
    "email": "maria.santos@clinica.com.br",
    "mobile": "+5511988887777",
    "councils": [
        {
            "council_type": "CRM",
            "council_number": "123456",
            "council_state": "SP",
            "council_status": "Ativo",
            "specialty": "Endocrinologia",
            "is_primary": 1
        }
    ]
}
→ name: "00NNN" (auto-increment)
```

## Validações

`setup_07_prescribers` aplica:
- CPF único entre Prescribers
- Pelo menos 1 council obrigatório (ValidationError)
- council_number único por (council_type, council_state)
- Se múltiplos councils, exatamente 1 com `is_primary=1`

## URLs

```
Lista:  https://erp.injemedpharma.com.br/app/prescriber
Form:   https://erp.injemedpharma.com.br/app/prescriber/00NNN
```

## Status no fluxo Gustavo Dalmora

⏳ **Pendente** — médico não consta no deal HubSpot. Opções pra produção:

1. **Adicionar properties** ao HubSpot Deal (`medico_nome`, `medico_crm`,
   `medico_uf`) + UI form pro operador preencher antes de enviar pra ERPNext.
2. **OCR da receita anexada** + popular automático via n8n.
3. **Operador preenche manual** no ERPNext form Sales Order Patient
   (linha `fp_patients`).

Pra esse exemplo o Sales Order foi criado com `fp_patients` sem `prescriber`
(NULL). Funciona pra fluxo de reserva mas perde rastreabilidade médico.

## Próximo

[Etapa 4 — Cadastrar Paciente](04-cadastrar-paciente.md)
