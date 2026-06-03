# Receita PDF anexada na linha do paciente (Sales Order Patient)

> Cada paciente do pedido = uma linha em fp_patients = uma receita PDF
> anexada. Receita vem do backend validacao_receita (`patients.receita_path`),
> sobe pro ERPNext como File doc privado, fica linkada à row específica.

## Custom Fields criados (setup_18)

Em `Sales Order Patient` (DocType child do Sales Order):

| Field | Tipo | allow_on_submit | Descrição |
|---|---|---|---|
| `receita` | Attach | ✅ | URL do File ERPNext (`/private/files/...`) |
| `receita_original_name` | Data | ✅ | Nome original do arquivo (de `patients.receita_original_name`) |
| `receita_status` | Select | ✅ | Status assinatura digital (de `patients.assinatura_digital_status`) |

Options de `receita_status`:
- `nao_verificado`
- `verificando`
- `valida`
- `invalida`
- `sem_assinatura`
- `erro`

`allow_on_submit=1` porque na maioria dos casos a receita é anexada
DEPOIS do SO já estar submetido (sync n8n acontece após payment + reserve).

## Endpoint nativo Frappe (sem Server Script custom)

### 1. Upload do arquivo

```
POST https://erp.injemedpharma.com.br/api/method/upload_file
Authorization: token <KEY>:<SECRET>
Content-Type: multipart/form-data

file:        <pdf bytes>
is_private:  1
doctype:     Sales Order Patient
docname:     pqvpomge3i           # row name de fp_patients
fieldname:   receita
```

Resposta:
```json
{
  "message": {
    "name": "76cb14d428",
    "file_name": "receita.pdf",
    "file_url": "/private/files/receita.pdf",
    "is_private": 1,
    "attached_to_doctype": "Sales Order Patient",
    "attached_to_name": "pqvpomge3i"
  }
}
```

⚠ `upload_file` cria File doc e linka via `attached_to_*`, mas **NÃO**
popula o campo `receita` na row automaticamente. Precisa step 2.

### 2. Setar campo receita na row

```
POST https://erp.injemedpharma.com.br/api/method/frappe.client.set_value
Authorization: token <KEY>:<SECRET>
Content-Type: application/json

{
  "doctype":   "Sales Order Patient",
  "name":      "pqvpomge3i",
  "fieldname": "receita",
  "value":     "/private/files/receita.pdf"
}
```

Repete pra `receita_original_name` + `receita_status`.

## Achar row_name de fp_patients

Sales Order Patient é child — GET direto bloqueia (PermissionError).
Pegar via parent:

```
GET /api/resource/Sales Order/{so_name}
```

Response inclui `fp_patients[]` com `name` (row id) + `patient` + `item_code`.

Filter local: row onde `patient == <patient_name>` e (opcional) `item_code == <item>`.

## Fluxo n8n estendido

Após POST issue_order, fluxo continua:

```
[POST issue_order ERPNext]
    ↓ retorna sales_order, created.patients[], etc
[GET SO completo]
    GET /api/resource/Sales Order/{sales_order}
    pra pegar fp_patients[].name
    ↓
[Loop por paciente do Postgres]
  Pra cada validacao_receita.patients (row):
    [GET PDF receita do backend]
      GET https://api.validacao.injemedpharma.com.br/api/patients/{pat.id}/receita
      Authorization: Bearer <JWT admin>
      → bytes PDF
    ↓
    [Match row]
      Acha SO fp_patient row onde:
        patient == ERPNext Patient name (lookup por CPF)
        item_code == products.sku (mesmo SKU do produto)
    ↓
    [POST upload_file ERPNext]
      multipart {file, is_private=1, doctype=Sales Order Patient,
                 docname=<row.name>, fieldname=receita}
      → file_url
    ↓
    [POST frappe.client.set_value × 3]
      receita = file_url
      receita_original_name = pat.receita_original_name
      receita_status = pat.assinatura_digital_status
    ↓
[Loop fim]
[Respond]
```

## Pra adicionar ao n8n workflow

3 nodes novos após POST issue_order:

### Node "GET SO full"

```
HTTP GET https://erp.injemedpharma.com.br/api/resource/Sales Order/{{ $('POST issue_order ERPNext').first().json.message.sales_order }}
Authorization: token {{$env.ERPNEXT_API_KEY}}:{{$env.ERPNEXT_API_SECRET}}
```

### Node "Match patients × rows"

```js
// Match patients Postgres com fp_patients rows ERPNext
const so = $input.first().json.data;
const rows = so.fp_patients || [];
const products = $('Query Postgres').first().json.products || [];
const out = [];
for (const prod of products) {
  for (const pat of (prod.patients || [])) {
    const patName = pat.patient;  // veio do Transform já mapeado? PRECISA lookup CPF→Patient
    // Aproximação: lookup pelo CPF original
    const row = rows.find(r => r.item_code === prod.sku);
    if (row) {
      out.push({ json: {
        row_name: row.name,
        patient_postgres_id: pat.id,
        receita_path: pat.receita_path,
        receita_original_name: pat.receita_original_name,
        assinatura_status: pat.assinatura_digital_status,
      }});
    }
  }
}
return out;
```

⚠ Limitação atual: lookup row por item_code apenas. Se 2 pacientes no
mesmo item, ambiguidade. Pra MVP funciona pra 1-paciente-por-item.
Aprimorar lookup por (item_code + patient_cpf via cruzamento com Patient ERPNext).

### Node "GET PDF + Upload + Set"

3 sub-passos por paciente. Pode ser 1 Code node que faz tudo via fetch
OU 3 HTTP nodes em sequência.

## Testado em prod (Paulo / Eveline)

```
SO 00077 fp_patients[0]
  row_name = pqvpomge3i
  patient = 00076 (Eveline)
  item_code = TIR00060
  qty = 1.0

Após upload + set_value:
  receita = /private/files/receita_eveline_teste.pdf
  receita_original_name = receita_paulo_eveline.pdf
  receita_status = valida
```

Verifica via UI ERPNext:
```
https://erp.injemedpharma.com.br/app/sales-order/00077
  → seção "Pacientes Vinculados" → linha pqvpomge3i
  → coluna "Receita (PDF)" mostra link clicável
```

## Limitações

1. **n8n precisa baixar PDF do backend validacao**. Backend tem
   `/api/patients/:id/receita` que serve com `Content-Disposition: inline`.
   n8n HTTP node deve tratar como binary download.

2. **2 calls ERPNext por paciente** (upload_file + set_value). Pra 100
   pacientes = 200 calls. Aceitável; mas pra otimizar futuro: criar
   endpoint custom que faz tudo em 1 (requer base64 OR multipart,
   ambos com gotchas em Server Scripts).

3. **set_value falha se field não tem allow_on_submit=1**. Setup_18
   garante isso na criação. Se editar fields manualmente via UI,
   re-aplicar setup_18 OU marcar a flag.

4. **Receita Patient ERPNext vs Sales Order Patient row**. Patient
   DocType tem suas próprias attaches (medical records). NESSE caso
   a receita fica na ROW do SO (uma por pedido, não por Patient
   global). Pra rastreabilidade completa (Patient pode ter N receitas
   ao longo do tempo), considerar adicionar attach também em Patient.

## Próximo

- Atualizar n8n workflow oficial `sync_order_to_erpnext.json` com os 3 nodes novos
- Configurar n8n com credenciais backend validacao (JWT admin)
- Testar fluxo end-to-end com pedido novo
