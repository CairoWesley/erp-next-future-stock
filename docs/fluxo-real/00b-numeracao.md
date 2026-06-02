# Convenção de Numeração — Auto-Increment Puro

> Decisão: nada de prefixo, nada de ano. Só sequência. Cada DocType tem
> seu próprio contador independente.

## Padrão

```
Formato: 00001, 00002, 00003, ...
Padding: 5 dígitos com zero à esquerda
Counter: independente por DocType
```

Exemplo:
```
Customer  00001, 00002, 00003
Patient   00001, 00002, 00003   ← contador separado
FPB       00001, 00002, 00003   ← contador separado
```

## DocTypes cobertos

| DocType | Antes | Depois | Estratégia |
|---|---|---|---|
| Customer | CUST-2026-00001 | `00001` | Selling Settings + naming_series field |
| Patient | (Healthcare default) | `00001` | naming_series field |
| Prescriber | PRES-2026-00001 | `00001` | Property Setter autoname |
| Sales Order | SAL-ORD-2026-00001 | `00001` | naming_series field |
| Future Production Batch | FPB-2026-00115 (mantém) | próximo: `00001` | Property Setter autoname |
| Production Reservation | PR-2026-00001 | `00001` | Property Setter autoname |
| Dispensacao | DISP-2026-00001 | `00001` | Property Setter autoname |
| Delivery Note | MAT-DN-2026-00001 | `00001` | naming_series field |
| Sales Invoice | ACC-SINV-2026-00001 | `00001` | naming_series field |
| Payment Entry | ACC-PAY-2026-00001 | `00001` | naming_series field |
| Stock Entry | MAT-STE-2026-00001 | `00001` | naming_series field |

DocTypes auxiliares (Address, Contact, Sales Person) mantêm naming
nativo do ERPNext — naming Python hardcoded no core, Property Setter
não sobrescreve. Não impacta operação (são suporte de Customer).

## Estratégia por categoria

Cada DocType cai numa de 3 categorias:

### 1. Custom (criados por nós)

```
DocTypes: FPB, PR, Prescriber, Dispensacao
Override: Property Setter autoname = "format:{#####}"
```

Sem hook de naming nativo. Property Setter sobrescreve direto. Funciona.

### 2. Nativos com field `naming_series`

```
DocTypes: Sales Order, Delivery Note, Sales Invoice,
         Payment Entry, Stock Entry, Patient
Override: 2 Property Setters no field naming_series:
          - options = ".#####"
          - default = ".#####"
```

ERPNext usa o valor selecionado no campo `naming_series` do form pra
gerar o nome. Forçando options=".#####" e default=".#####", o único
valor possível é o auto-increment puro.

### 3. Nativos com Settings master

```
DocTypes: Customer
Override:
  - Selling Settings.cust_master_name = "Naming Series"
    (antes era "Customer Name" — usava customer_name como ID)
  - + Property Setter naming_series field (mesma estratégia da categoria 2)
```

Customer tem chave configurável: usar customer_name ou naming series.
Forçamos naming series.

## IDs antigos

Registros já criados antes da mudança **mantêm o nome antigo**. Não há
renomeação retroativa (perigoso — quebra links). Exemplo:

```
FPB-2026-00115   (criado em 2026-06-02, antes da mudança)
00001            (próximo FPB, novo padrão)
00002, 00003 ... (sequência continua)
```

Mistura visual é aceita.

## Aplicação

Script:
```bash
python setup/setup_15_naming_series.py
```

Logs:
```
========================================================================
  Naming Series — auto-increment puro (format:{#####})
========================================================================
1/3 — DocTypes custom (autoname override)
[OK] FPB.autoname
[OK] PR.autoname
[OK] Prescriber.autoname
[OK] Dispensacao.autoname

2/3 — DocTypes nativos com field naming_series
[OK] Sales Order.naming_series.options
[OK] Sales Order.naming_series.default
...

3/3 — Settings singletons
[OK] Selling Settings.cust_master_name = "Naming Series"
```

## Validação executada em prod

```python
# Customer
{"customer_name": "TESTE", "customer_type": "Company", ...}
→ name: "00002"

# FPB
{"production_code": "TESTE-NAMING", ...}
→ name: "00002"

# Patient
{"patient_name": "TESTE", "cpf": "...", ...}
→ name: "00003"
```

Contadores funcionam, independentes por DocType.

## Reversão

```bash
python setup/setup_15_naming_series.py --uninstall
```

Remove Property Setters + reverte Selling Settings.cust_master_name pra
"Customer Name". Naming volta ao default ERPNext nos próximos registros.
Os já criados com numeração nova mantém o nome.
