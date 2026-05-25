# 16 — Multi-Empresa + Ambiente de Teste

> Suporte a múltiplas Companies no mesmo ERPNext + scripts/tests parametrizados
> via env vars. Dados isolados por Company.

---

## Conceito

ERPNext nativo suporta **multi-tenant via Company**. Todo documento
transacional (Sales Order, Future Production Batch, Stock Entry, Invoice…)
tem o campo `company` — dados ficam **isolados** entre Companies.

DocTypes **mestres globais** (Item, Patient, Prescriber, Customer) são
compartilhados entre Companies por padrão.

```
ERPNext Single Site
  ├── Company A: "Sua Empresa Ltda"   (abrev: I)
  │   ├── Sales Orders próprios
  │   ├── FPBs próprios
  │   ├── Warehouse "Produtos Acabados - I"
  │   └── Accounting chart próprio
  │
  └── Company B: "TEST-CO Ltda"       (abrev: TC)
      ├── Sales Orders próprios (zero overlap com A)
      ├── FPBs próprios
      ├── Warehouse "Produtos Acabados - TC"
      └── Accounting chart próprio
```

---

## Criar Company de teste

```bash
# Cria TEST-CO Ltda com tudo necessário
python setup_12_test_company.py

# OU com nome custom
python setup_12_test_company.py --name "Sandbox Empresa" --abbr "SB"

# Remover
python setup_12_test_company.py --uninstall
```

**O que cria**:
- Company "TEST-CO Ltda" (abrev TC)
- Chart of Accounts padrão
- Warehouses: Stores, Produtos Acabados, Work In Progress, Matérias Primas (todos com `- TC` sufixo)
- Customer Group "Comercial"
- Territory "Brazil"
- Price List "Venda Padrão"
- Modes of Payment: Pix, Boleto, Transferência Bancária, Dinheiro

---

## Trocar entre Companies

### Via `.env`

```env
# Produção
ERPNEXT_COMPANY=Sua Empresa Ltda
ERPNEXT_WAREHOUSE=Produtos Acabados - I

# Teste (ambiente isolado)
ERPNEXT_COMPANY=TEST-CO Ltda
ERPNEXT_WAREHOUSE=Produtos Acabados - TC
```

Rodar smoke test no ambiente teste:

```bash
ERPNEXT_COMPANY="TEST-CO Ltda" \
ERPNEXT_WAREHOUSE="Produtos Acabados - TC" \
  python smoke_test_huge.py --phase all
```

### Via shell export

```bash
export ERPNEXT_COMPANY="TEST-CO Ltda"
export ERPNEXT_WAREHOUSE="Produtos Acabados - TC"
python smoke_test_huge.py --phase all
```

### Via UI ERPNext

Topo direito → seu avatar → **My Settings** → **Default Company**

---

## Scripts parametrizados

Todos os scripts agora leem env vars:

| Script | Variáveis |
|---|---|
| `mini_flow.py` | `ERPNEXT_COMPANY`, `ERPNEXT_WAREHOUSE` |
| `smoke_test_large.py` | `ERPNEXT_COMPANY`, `ERPNEXT_WAREHOUSE` |
| `smoke_test_huge.py` | `ERPNEXT_COMPANY`, `ERPNEXT_WAREHOUSE` |
| `test_scenario*.py` | `ERPNEXT_COMPANY`, `ERPNEXT_WAREHOUSE` |
| `setup_*.py` | `ERPNEXT_MODULE` (default `Manufacturing`) |

Default sempre = `Injmedpharma` + `Produtos Acabados - I` (produção).

---

## Workflow recomendado

### 1. Desenvolvimento

```bash
# Use TEST-CO pra desenvolver sem tocar produção
export ERPNEXT_COMPANY="TEST-CO Ltda"
export ERPNEXT_WAREHOUSE="Produtos Acabados - TC"

python smoke_test_huge.py --phase all
# Inspeciona em UI: filtros por company=TEST-CO Ltda
```

### 2. Promoção pra produção

```bash
# Volta pra produção
unset ERPNEXT_COMPANY ERPNEXT_WAREHOUSE
# OU define explicitamente
export ERPNEXT_COMPANY="Sua Empresa Ltda"
export ERPNEXT_WAREHOUSE="Produtos Acabados - I"

# Roda novamente — mesmo código, dados separados
python smoke_test_huge.py --phase all
```

### 3. Cleanup isolado

```bash
# Limpa só TEST-CO
ERPNEXT_COMPANY="TEST-CO Ltda" python smoke_test_huge.py --phase cleanup
ERPNEXT_COMPANY="TEST-CO Ltda" python tools/deep_cleanup.py --yes
```

---

## Permissions: isolar usuários por Company

Pra que usuário de teste **só veja** TEST-CO:

1. *User → seu usuário → User Permissions → + Add*
2. Allow: **Company** = `TEST-CO Ltda`
3. Apply: ☑ Apply to All Doctypes
4. **Save**

Agora esse usuário só enxerga docs onde `company = TEST-CO Ltda`. Lista de FPBs,
SOs, etc filtra automaticamente.

---

## DocTypes globais vs por-Company

| DocType | Escopo |
|---|---|
| Item (TIR00060) | Global — compartilhado |
| Customer | Global |
| Patient | Global (não tem campo `company`) |
| Prescriber | Global |
| **Future Production Batch** | **Por Company** |
| **Production Reservation** | **Por Company** (via SO.company) |
| Sales Order | Por Company |
| Sales Invoice | Por Company |
| Delivery Note | Por Company |
| Stock Entry | Por Company |
| Batch (lote físico) | Por warehouse → indireto por Company |
| **Dispensation** | **Por Company** (via SO.company) |

---

## Alternativa avançada: Multi-Site Frappe

Pra **isolamento total** (DB separado, URL separada):

```bash
# No servidor (precisa shell)
bench new-site teste.suaempresa.com.br --mariadb-root-password <senha>
bench --site teste.suaempresa.com.br install-app erpnext
bench setup add-domain --site teste.suaempresa.com.br teste.suaempresa.com.br
```

Cada site tem:
- DB próprio (zero contato com produção)
- URL própria
- API keys próprias

Trade-off: mais infra, manutenção dobrada.

**Recomendação**: começar com Company adicional no mesmo site. Migrar pra
multi-site só se isolamento crítico (LGPD, certificação).

---

## URLs úteis pós-setup

```
Lista de Companies:
  https://erp.injemedpharma.com.br/app/company

Detalhe TEST-CO:
  https://erp.injemedpharma.com.br/app/company/TEST-CO%20Ltda

Warehouses:
  https://erp.injemedpharma.com.br/app/warehouse
  → filtro company=TEST-CO Ltda

User Permissions (pra restringir):
  https://erp.injemedpharma.com.br/app/user-permission
```

---

## Comandos diretos

```bash
# Criar
python setup_12_test_company.py

# Rodar smoke huge em teste
ERPNEXT_COMPANY="TEST-CO Ltda" ERPNEXT_WAREHOUSE="Produtos Acabados - TC" \
  python smoke_test_huge.py --phase all

# Verificar dados criados em TEST-CO
ERPNEXT_COMPANY="TEST-CO Ltda" python -c "
from lib.erpnext_api import client_from_env
from lib.visibility import list_fpbs, print_fpb_table
c = client_from_env()
print_fpb_table(list_fpbs(c, code_prefix='DEMO-HUGE'))
"

# Limpar dados de teste
ERPNEXT_COMPANY="TEST-CO Ltda" python tools/deep_cleanup.py --yes

# Remover Company inteira (precisa apagar docs primeiro)
python setup_12_test_company.py --uninstall
```
