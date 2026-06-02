# TODO / Runbook — Reset total e Rebuild

> Atualizado por Claude. Objetivo atual: **zerar 100% os dados de teste**
> (mantendo a empresa **Injmedpharma**) e depois reconstruir com dados reais
> para testar a integração.

---

## Pendências

- [ ] **1. Limpar 100% dos dados de teste** (manter a Company). Ver runbook abaixo.
- [ ] **2. Endereço + CNPJ reais da empresa.** A Company `Injmedpharma` não tem
      endereço (Address) nem CNPJ (`tax_id`) cadastrados. Hoje a etiqueta usa um
      placeholder no endereço. Cadastrar os dados reais e religar a etiqueta para
      **importar** dinamicamente (remover o placeholder em `build_zpl`).
- [ ] **3. Confirmar regra de cópias da etiqueta.** Hoje imprime **`qty*2+1`
      cópias da MESMA etiqueta** (1 caixa + 1 ampola por unidade + 1 adicional
      para o pedido). Se "caixa", "ampola" e "adicional" precisarem de
      **layouts/tamanhos diferentes**, implementar tipos distintos.

---

## Runbook: zerar a base e reconstruir

> ⚠️ **DESTRUTIVO e IRREVERSÍVEL. Faça backup ANTES.**

### 1) Backup
```bash
bench --site erp.injemedpharma.com.br backup
# ou pela UI do ERPNext: menu > Download Backups > gerar
```

### 2) Atualizar o código
```bash
git pull origin main
```

### 3) Dependências (Python 3.10+)
```bash
pip install -r requirements.txt
```

### 4) Configurar o `.env` (copie de `.env.example`)
```ini
ERPNEXT_URL=https://erp.injemedpharma.com.br
ERPNEXT_API_KEY=<sua_api_key>
ERPNEXT_API_SECRET=<sua_api_secret>
ERPNEXT_COMPANY=Injmedpharma
ERPNEXT_VERIFY_SSL=true
```
> A API key/secret gera em: **ERPNext > User (System Manager) > API Access > Generate Keys**.

### 5) Apagar 100% dos dados (mantém a Company)
```bash
python tools/deep_cleanup.py --all --yes
```
Apaga TODOS os registros de: Production Reservation, Dispensação, Sales Order,
Future Production Batch, Batch, Patient, Prescriber e Customer.
**A Company (Injmedpharma) NÃO é tocada.** A estrutura (DocTypes, Server/Client
Scripts, Custom Fields) também permanece.

> Sem `--all` (só dados de teste com prefixo TEST-/DEMO-):
> `python tools/deep_cleanup.py --yes`

### 6) Conferir
- Sem pacientes/médicos/clientes/pedidos/dispensações.
- DocTypes, scripts e a Company seguem intactos.

### 7) Reconstruir + testar integração
- Cadastrar a empresa (endereço + CNPJ — pendência #2).
- Cadastrar dados reais (pacientes, médicos, itens) e rodar o fluxo
  (pedido → alocação → dispensação → etiqueta) para testar a integração.

---

## Já entregue (na branch `main`)

- **Impressão Zebra** via BrowserPrint local (`http://localhost:9100`, sem
  precisar da lib JS; trata IPv6/CORS).
- **Etiqueta Receituário** única para todos os tamanhos, **orientada pelo lado
  maior** (estreitas giram 90°). Campos: REG, paciente, produto, **pH**, lote +
  `1 UN`, FAB/VAL, **médico + CRM na mesma linha**, uso injetável, conservação
  2-8 °C, endereço.
- **Cópias = `qty*2+1`** por linha (`^PQ`).
- **Auto-import** de paciente/médico (dos cadastros) no pedido e na dispensação.
- Default do template = `25x60mm`; opções: 25x60, 30x60, 50x30, 100x50,
  Receituario 100x50.
- `tools/deep_cleanup.py` com modo **`--all`** + limpeza de Dispensações.
