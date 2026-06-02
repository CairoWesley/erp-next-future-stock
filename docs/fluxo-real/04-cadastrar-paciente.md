# Etapa 4 — Cadastrar Paciente (Patient)

> Cria registro do paciente no DocType Patient (ERPNext Healthcare).
> Linka ao Customer (que é entidade pagante). Pra PF, geralmente
> Paciente.cpf == Customer.tax_id (mesma pessoa paga + consome).

## DocType Patient

```
Patient
  ├─ patient_name      Data
  ├─ first_name        Data
  ├─ last_name         Data
  ├─ cpf               Data  unique (custom field setup_06)
  ├─ mobile            Data
  ├─ email             Data
  ├─ sex               Select [Male, Female, Other]
  ├─ dob               Date  (date of birth)
  ├─ blood_group       Select
  ├─ default_prescriber  Link  (custom field setup_07 — médico habitual)
  └─ default_council_label  Data  (custom — "CRM-SP 123456")
```

## Exemplo executado em prod (2026-06-02)

Patient pra deal Gustavo Dalmora.

```python
POST /api/resource/Patient
{
    "doctype": "Patient",
    "patient_name": "Gustavo Dalmora",
    "first_name": "Gustavo",
    "last_name": "Dalmora",
    "cpf": "04294209941",
    "mobile": "+11913169667",
    "email": "gustavodalmora@gmail.com",
    "sex": "Male"
}
→ name: "00068"
```

## URLs

```
Form:    https://erp.injemedpharma.com.br/app/patient/00068
Lista:   https://erp.injemedpharma.com.br/app/patient
```

## Validações

`setup_06_patients` aplica:
- CPF unique entre Patients
- patient_name obrigatório
- (Soft validation) CPF de 11 dígitos

## Pra esse exemplo

```
Patient 00068 = Gustavo Dalmora
  CPF:       04294209941 (mesmo do Customer 00067)
  Vínculo:   manual via fp_patients[] no Sales Order
  Prescriber: NULL (médico não identificado neste pedido)
```

## Próximo

[Etapa 5 — Criar Sales Order com fp_patients](05-criar-sales-order.md)
