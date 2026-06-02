# 03 — Instalação

## Pré-requisitos

### Local (máquina onde rodam os scripts)
- Python 3.9+
- `pip` para instalar `requests` e `python-dotenv`
- Acesso de rede ao ERPNext (HTTP/HTTPS)

### No servidor ERPNext
1. **ERPNext 14+** acessível via HTTPS
2. **Usuário com perfil System Manager** já criado
3. **API Key e API Secret** desse usuário
   - Em ERPNext: *User → seu usuário → API Access → Generate Keys*
   - Copie o Secret **na hora** — ele só aparece uma vez
4. **`server_script_enabled: 1`** no `common_site_config.json`
   - Sem isso o módulo não funciona. Habilite no bench:
   ```bash
   bench --site <seu_site> set-config -g server_script_enabled 1
   bench restart
   ```
   - Para ambientes Docker (frappe_docker):
   ```bash
   docker ps                                # localizar container do backend
   docker exec -it <container> bench --site <seu_site> set-config -g server_script_enabled 1
   docker compose restart                   # ou docker restart <containers>
   ```

## Passo 1 — Clonar e preparar ambiente

```bash
git clone https://github.com/CairoWesley/erp-next-future-stock.git
cd erp-next-future-stock/erpnext-future-production-setup

python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

## Passo 2 — Configurar `.env`

```bash
cp .env.example .env
```

Edite o `.env`:

```env
ERPNEXT_URL=https://erp.suaempresa.com.br
ERPNEXT_API_KEY=cole_sua_api_key
ERPNEXT_API_SECRET=cole_sua_api_secret

ERPNEXT_COMPANY=Sua Empresa
ERPNEXT_MODULE=Manufacturing
ERPNEXT_HTTP_TIMEOUT=30
ERPNEXT_VERIFY_SSL=true
```

> **Atenção SSL**: deixe `ERPNEXT_VERIFY_SSL=true` em produção. Só desative em
> ambientes locais com certificado auto-assinado.

## Passo 3 — Validar conexão

```bash
python -c "from lib.erpnext_api import client_from_env; c = client_from_env(); print('server_script_enabled =', c.server_script_enabled())"
```

Saída esperada:
```
[OK]      Conectado em https://erp.suaempresa.com.br como wesley@suaempresa.com.br
server_script_enabled = True
```

Se aparecer `server_script_enabled = False`, volte e habilite no bench (passo
4 dos pré-requisitos). Sem isso o setup **falha** no passo 3.

## Passo 4 — Instalação completa

```bash
python setup/setup_all.py
```

Saída esperada (resumo): os 6 passos rodam em sequência, cada um com seu
bloco `[CRIANDO] / [OK]`. Ao final:

```
========================================================================
  Resumo
========================================================================
[OK]      Instalando concluído com sucesso.
```

## Instalação por etapa (recomendada na primeira vez)

Para isolar falhas, rode passo a passo:

```bash
python setup/setup_01_structure.py        # DocTypes + Custom Fields
python setup/setup_02_client_scripts.py   # Botões UI
python setup/setup_03_server_scripts.py   # Validações + endpoints API
python setup/setup_04_reports.py          # Relatórios
python setup/setup_05_workspace.py        # Menu lateral
python setup/setup_06_patients.py         # Módulo Lote × Pacientes
```

## Idempotência

Todos os scripts são **idempotentes**: rodar 2x, 10x, 100x não duplica nada.

- DocType que já existe → `[OK] já existe`
- Custom Field que já existe → idem
- Client/Server Script já existe → faz `update` (envia diff novo)
- Report já existe → faz `update`
- Workspace já existe → faz `update`

Isso permite usar em CI/CD: a cada deploy, o estado convergente é aplicado.

## Verificação visual

Depois de instalar, abra o ERPNext:

1. **Workspace**: menu lateral → *Produção Futura* deve aparecer
2. **DocTypes**: `/app/future-production-batch/new` e `/app/production-reservation/new` devem abrir formulários completos
3. **Sales Order**: abra um SO e veja a seção *Pacientes* (com tabela `fp_patients`) e os custom fields em cada linha de item
4. **Relatórios**: *Produção Futura → Mapa de Produção* deve carregar mesmo sem dados

## Atualizando código existente

Se mudou algum payload, script ou workspace localmente e quer publicar:

```bash
python setup/setup_all.py
```

Tudo que mudou vai como `update`. Para **mudanças no schema de DocType existente** (adicionar/remover campos), o `create_doctype` pula porque já existe — é preciso recriar:

```bash
python tools/recreate_doctypes.py
python setup/setup_all.py
```

> Atenção: `recreate_doctypes.py` cancela e apaga TODOS os documentos
> existentes de `Future Production Batch` e `Production Reservation`. Use só
> em homologação ou se tiver certeza.

## Desinstalação

```bash
python setup/setup_all.py --uninstall
```

Remove em ordem inversa: Pacientes → Workspace → Reports → Server Scripts → Client Scripts → Custom Fields → DocTypes.

**Não apaga dados.** Se houver documentos criados, a remoção do DocType falha — apague os documentos primeiro (UI ou `tools/recreate_doctypes.py`).

## Pular passos

```bash
python setup/setup_all.py --skip 4,5      # pular Reports e Workspace
```

## Troubleshooting de instalação

Erros conhecidos com solução em [`08-troubleshooting.md`](08-troubleshooting.md):

- *"Python não foi encontrado"* (Windows stub da Microsoft Store)
- *"Server Scripts are disabled"*
- *"ValidationError after submit"*
- *"NameError: _inplacevar_ is not defined"*
- *"DocType já existe (mas vazio)"*
