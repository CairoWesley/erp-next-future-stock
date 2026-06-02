# 08 — Troubleshooting

Problemas reais enfrentados durante a implantação inicial e suas soluções.

---

## 1. `python` aparece como instalado mas dá "Python não foi encontrado"

### Sintoma
```
> python --version
Python não foi encontrado; executar sem argumentos para instalar do Microsoft Store...
```

### Causa
No Windows, `python.exe` em `C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\` é um **stub de 0 bytes** que abre a Microsoft Store. Não é Python real.

### Solução
Instale Python de verdade. Via `winget`:
```powershell
winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements --silent --scope user
```

Após instalar, abra um terminal **novo** e confirme:
```powershell
where.exe python
# Deve listar: C:\Users\<user>\AppData\Local\Programs\Python\Python312\python.exe
```

---

## 2. `ServerScriptNotEnabled` — "Server Scripts are disabled"

### Sintoma
Ao criar um doc ou chamar um endpoint custom:
```
frappe.utils.safe_exec.ServerScriptNotEnabled: Server Scripts are disabled.
Please enable server scripts from bench configuration.
```

### Causa
A flag `server_script_enabled` não está no `common_site_config.json` do site. Os Server Scripts são criados como registros, mas o Frappe se recusa a **executar** sem essa flag.

### Solução
No host onde está o ERPNext:

```bash
# Direto no bench
bench --site <seu_site> set-config -g server_script_enabled 1
bench restart
```

Em Docker:
```bash
docker ps                                # achar container do backend
docker exec -it <container> bench --site <site> set-config -g server_script_enabled 1
docker compose restart                   # ou docker restart ...
```

### Como verificar do cliente
```bash
python -c "from lib.erpnext_api import client_from_env; c = client_from_env(); print(c.server_script_enabled())"
# Deve imprimir: True
```

> O método `server_script_enabled()` cria um Server Script API mínimo,
> tenta executá-lo, e remove. Se falhar com `ServerScriptNotEnabled`, retorna `False`.

---

## 3. `TimestampMismatchError` ao submeter doc

### Sintoma
```
frappe.exceptions.TimestampMismatchError:
O documento foi modificado depois de aberto (..., ...). Por favor faça atualização.
```

### Causa
Você está chamando `frappe.client.submit` passando só `{doctype, name}` ou um body **antigo**. O documento foi atualizado por um hook (After Save, por exemplo) e o `modified` mudou.

### Solução
Sempre faça `GET` imediatamente antes de submeter, e passe o body completo:

```python
def submit_doc(client, doctype, name):
    _, body = client._request("GET", f"/api/resource/{doctype}/{name}")
    doc = body["data"]
    client._request("POST", "/api/method/frappe.client.submit",
                    json_body={"doc": doc})
```

Hoje o helper `submit_doc` em `test_scenario.py` e `test_scenario_patients.py` faz exatamente isso.

---

## 4. `UpdateAfterSubmitError` ao atualizar campos do FPB/PR

### Sintoma
```
frappe.exceptions.UpdateAfterSubmitError:
Not allowed to change <strong>Quantidade Reservada</strong> after submission
from <strong>0.0</strong> to <strong>300.0</strong>
```

### Causa
Hook tentando `doc.save()` em documento com `docstatus=1`, sem `allow_on_submit=1` no campo.

### Solução
Duas correções aplicadas:

**a)** Campos calculados ganharam `allow_on_submit: 1` no payload do DocType:
- FPB: `reserved_qty`, `available_qty`, `produced_qty`, `released_qty`, `pending_release_qty`, `batch_no`, `work_order`, `status`
- PR: `released_qty`, `pending_qty`, `status`, `release_batch_no`, `delivery_note`

**b)** Hooks usam `frappe.db.set_value(...)` (bypass de validação) em vez de `doc.save()`:
```python
# ❌ Antes (dava erro)
fpb = frappe.get_doc("Future Production Batch", fpb_name)
fpb.reserved_qty = X
fpb.save(ignore_permissions=True)

# ✓ Agora
frappe.db.set_value("Future Production Batch", fpb_name, {
    "reserved_qty": X,
    ...
}, update_modified=False)
```

---

## 5. `NameError: name '_inplacevar_' is not defined`

### Sintoma
Em algum endpoint custom:
```
frappe.exceptions.ValidationError: NameError: name '_inplacevar_' is not defined
```

### Causa
RestrictedPython (sandbox dos Server Scripts) **não suporta operadores in-place** (`+=`, `-=`, `*=`).

### Solução
Trocar por operação expandida:
```python
# ❌ Antes
released_count += 1
remaining -= take

# ✓ Agora
released_count = released_count + 1
remaining = remaining - take
```

Aplicado em `setup_03_server_scripts.py` (5 ocorrências corrigidas).

---

## 6. `SyntaxError: "_var" is an invalid variable name because it starts with "_"`

### Sintoma
```
SyntaxError: Line 10: "_digits" is an invalid variable name because it starts with "_"
```

### Causa
RestrictedPython proíbe **qualquer identificador começando com `_`** (variável, função, atributo).

### Solução
Renomear: `_digits` → `only_digits`, `_compute_status` → `compute_status`, etc.

---

## 7. `SyntaxError: format is an unsafe attribute`

### Sintoma
Em scripts mais novos:
```
SyntaxError: format is an unsafe attribute
```

### Causa
RestrictedPython, dependendo da versão, marca `str.format()` como atributo unsafe. **Comportamento inconsistente**: alguns scripts antigos funcionam, novos não.

### Solução defensiva
Em scripts novos, usar concatenação:
```python
# ❌ Pode dar problema
frappe.throw("Saldo: {0}, solicitado: {1}".format(a, b))

# ✓ Seguro
frappe.throw("Saldo: " + str(a) + ", solicitado: " + str(b))
```

Aplicado em `setup_06_patients.py` (todos os `frappe.throw`).

---

## 8. `LinkValidationError: Customer Group / Territory`

### Sintoma
Criando Customer via API:
```
Não foi possível encontrar Grupo de Clientes: All Customer Groups, Território: All Territories
```

### Causa
Ambiente PT-BR — os nomes dos masters foram traduzidos.

### Solução
Inspecione com:
```bash
python tools/inspect_master.py
```

Use os nomes que aparecerem (no caso testado: `Comercial`, `Brazil`).

```python
{
  "customer_group": "Comercial",
  "territory": "Brazil",
}
```

---

## 9. `Evento DocType não pode ser "On Submit"`

### Sintoma
```
frappe.exceptions.ValidationError: Evento DocType não pode ser "On Submit".
Deve pertencer a "Antes da inserção", "Before Validate", ...
```

### Causa
O Frappe usa internamente os nomes **em inglês**: `Before Insert`, `Before Validate`, `Before Save`, `After Insert`, `After Save`, **`Before Submit`**, **`After Submit`**, `Before Cancel`, **`After Cancel`**, etc.

A documentação às vezes fala "On Submit"/"On Cancel" — está errado. O correto é **`After Submit`** e **`After Cancel`**.

### Solução
```python
{
    "doctype_event": "After Submit",  # ✓
    # NÃO "On Submit"
}
```

---

## 10. DocType "já existe" mas vazio

### Sintoma
Setup roda, `[OK] DocType X já existe`, mas operações com X falham com `Field not permitted in query: ...`.

### Causa
O DocType existia **antes** do setup (talvez criado pela UI ou outro deploy) com schema incompleto. O método `create_doctype` é idempotente — se já existe, pula. Mas não atualiza o schema.

### Solução
```bash
python tools/fix_fpb_schema.py
```

O script:
1. Verifica se há documentos no DocType
2. Se zero: deleta o DocType e recria com schema completo
3. Se houver: aborta e instrui a remover dados manualmente

Para um reset total (cancela e apaga FPBs e PRs):
```bash
python tools/recreate_doctypes.py
python setup/setup_03_server_scripts.py    # reaplica scripts
```

---

## 11. `UnicodeEncodeError: 'charmap' codec can't encode '✓'` no Windows

### Sintoma
Scripts de teste imprimindo caracteres `✓` / `✗` / `→` quebram com:
```
UnicodeEncodeError: 'charmap' codec can't encode character '✓' in position N
```

### Causa
PowerShell padrão em Windows usa code page `cp1252` (Windows-1252), que não suporta caracteres Unicode acima de U+00FF.

### Solução
Em scripts de teste, usar ASCII:
```python
# ❌ Antes
ok = "✓" if condicao else "✗"

# ✓ Agora
ok = "OK" if condicao else "FAIL"
```

Ou, alternativamente (não aplicado aqui): definir `PYTHONIOENCODING=utf-8` no ambiente.

---

## 12. Sales Order Item nativo já tem `reserved_qty`

### Sintoma
Conflito ao tentar criar Custom Field `reserved_qty` em `Sales Order Item`:
```
Custom Field reserved_qty already exists for Sales Order Item.
```

### Causa
ERPNext já tem `Sales Order Item.reserved_qty` usado pelo módulo **Stock Reservation Entry**. Não é o nosso.

### Solução
Custom Fields do módulo usam **prefixo `fp_`** (future production):

| Documentação original | Implementado |
|---|---|
| `reserved_qty` | `fp_reserved_qty` |
| `released_qty` | `fp_released_qty` |
| `pending_release_qty` | `fp_pending_release_qty` |
| `future_production_batch` | `fp_future_production_batch` |
| `reservation_status` | `fp_reservation_status` |

Os labels continuam em português (sem prefixo).

---

## 13. Como inspecionar o ambiente

Para qualquer suspeita de inconsistência:

```bash
python tools/diagnose.py
```

Imprime:
- Companies cadastradas
- Warehouses ativos
- Items com estoque
- Customers e Sales Orders submetidos
- Future Production Batches e Production Reservations
- Server Scripts do módulo (com status enabled)

Para verificar o schema atual de um DocType específico:
```bash
python tools/inspect_fpb.py    # Future Production Batch
```

Para checar se o módulo Healthcare está instalado:
```bash
python tools/inspect_healthcare.py
```
