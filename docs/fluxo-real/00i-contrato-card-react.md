# Contrato Card React HubSpot → n8n → ERPNext

> Card React no HubSpot Deal page chama UM webhook único com 2 parâmetros.
> n8n busca todos os dados (Postgres + HubSpot + checkout_simples) e
> sincroniza pra ERPNext. Operador escolhe qual FPB usar pra reservar.

## Webhook URL

```
POST https://n8n.injemedpharma.com.br/webhook/erp/sync-order
Content-Type: application/json
```

## Request body

### Forma preferida (N items, N FPBs)

```json
{
  "deal_id":  "60801476407",
  "fpb_map": {
    "TIR00060": "FPB-2026-00115",
    "00049":    "FPB-2026-00120",
    "00057":    "FPB-2026-00125"
  }
}
```

`fpb_map`: dict `{ item_code: fpb_name }`. **Um lote por item.**

- Item presente no map sem FPB válido → erro no `reserve_errors[]` (não bloqueia SO).
- Item ausente do map → cai pra `fpb_name` top-level (se houver) ou FIFO.
- Item non-stock (FRETE) → ignorado automático (não tenta reservar).

### Forma alias (legível pelo Card React)

```json
{
  "deal_id": "60801476407",
  "items": [
    { "item_code": "TIR00060", "fpb_name": "FPB-2026-00115" },
    { "item_code": "00049",    "fpb_name": "FPB-2026-00120" },
    { "item_code": "00057",    "fpb_name": "FPB-2026-00125" }
  ]
}
```

n8n converte `items[]` → `fpb_map` automaticamente.

### Forma legada (1 FPB pra tudo)

```json
{
  "deal_id":  "60801476407",
  "fpb_name": "FPB-2026-00115"
}
```

Mantido pra retrocompat. Usa esse FPB pra **todos** items stock do pedido.

### Sem FPB (FIFO)

```json
{ "deal_id": "60801476407" }
```

ERPNext escolhe FPB por `planned_production_date asc`.

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `deal_id` | string | **sim** | HubSpot Deal ID |
| `fpb_map` | dict | não | Map `item_code → fpb_name` (preferencial pra N items) |
| `items` | array | não | Alias `[{item_code, fpb_name}]` (n8n converte pra fpb_map) |
| `fpb_name` | string | não | Single FPB pra todos items stock (legacy) |
| `order_id` | int | não | Alternativa ao deal_id (Postgres id) |

Aliases aceitos: `future_production_batch` no lugar de `fpb_name`.

## Response

```json
{
  "ok": true,
  "erpnext": {
    "sales_order": "00077",
    "created": {
      "customer": "00074",
      "prescribers": ["00075"],
      "patients": ["00076"]
    },
    "validation_status": "Validado (Pronto para Reservar)",
    "hubspot_complete": true,
    "ready_to_reserve": true,
    "reservations": [
      {
        "reservation": "00078",
        "sales_order_item": "abc123",
        "future_production_batch": "FPB-2026-00115",
        "reserved_qty": 1.0
      }
    ],
    "reserve_errors": []
  },
  "marked": [
    { "id": 1, "pedido_fc_emitido_at": "2026-06-03T15:12:35.211Z" }
  ]
}
```

| Campo response | Significado |
|---|---|
| `ok` | Sempre true se chegou aqui (HTTP 200). |
| `erpnext.sales_order` | Nome do SO criado/encontrado no ERPNext. |
| `erpnext.created.*` | Vazio se idempotency hit (já existia). Populado na primeira execução. |
| `erpnext.validation_status` | "Validado (Pronto para Reservar)" se 3 flags true; senão "Aguardando ...". |
| `erpnext.ready_to_reserve` | Bool. |
| `erpnext.reservations` | Lista de Production Reservations criadas nesta chamada (vazio se já estava reservado ou se faltam flags). |
| `erpnext.reserve_errors` | Lista de itens que não conseguiram reservar (FPB ausente, FPB do item errado, FPB não submetida, saldo insuficiente). |
| `marked` | Registro do `pedido_fc_emitido_at` (idempotente — só marca primeira vez). |

## Erros de FPB

Se `fpb_name` enviado mas tem problema, NÃO bloqueia o SO. SO é criado +
flags setadas; apenas a reserva falha e aparece em `reserve_errors`:

| Mensagem | Causa | Fix |
|---|---|---|
| `FPB X nao existe.` | Nome digitado errado / lote apagado | Verifica nome exato em ERPNext |
| `FPB X nao submetida.` | Lote em Rascunho (docstatus=0) | Submeter FPB primeiro |
| `FPB X e do item Y, esperado Z.` | Lote é de outro produto | Trocar fpb_name |
| `FPB X status=Bloqueado (esperado 'Aberta para Reserva').` | Lote fechado/encerrado | Trocar fpb_name |

## Exemplo curl (teste manual)

```bash
# Específico (operador escolheu FPB)
curl -X POST https://n8n.injemedpharma.com.br/webhook/erp/sync-order \
  -H "Content-Type: application/json" \
  -d '{
    "deal_id":  "60801476407",
    "fpb_name": "FPB-2026-00115"
  }'

# FIFO (sem escolher)
curl -X POST https://n8n.injemedpharma.com.br/webhook/erp/sync-order \
  -H "Content-Type: application/json" \
  -d '{ "deal_id": "60801476407" }'
```

## React Card — esqueleto sugerido (N items, N Selects)

```tsx
import { useState, useEffect } from 'react';
import { hubspot } from '@hubspot/ui-extensions';

const SyncCard = ({ context }) => {
  const dealId = context.crm.objectId;
  const [orderStatus, setOrderStatus] = useState(null);
  const [fpbsByItem, setFpbsByItem] = useState({});  // { item_code: FPB[] }
  const [selection, setSelection] = useState({});    // { item_code: fpb_name }
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  // 1. Status do order
  useEffect(() => {
    fetch(`https://api.validacao.injemedpharma.com.br/api/orders/deal/${dealId}`)
      .then(r => r.json()).then(setOrderStatus);
  }, [dealId]);

  // 2. FPBs por item (paralelo)
  useEffect(() => {
    if (!orderStatus?.products?.length) return;
    const stockSkus = orderStatus.products
      .filter(p => p.sku !== 'SV02000002')   // exclui FRETE
      .map(p => p.sku);
    Promise.all(stockSkus.map(sku =>
      fetch(`https://erp.injemedpharma.com.br/api/resource/Future Production Batch?` +
        `filters=[["item_code","=","${sku}"],["status","=","Aberta para Reserva"],["docstatus","=",1]]&` +
        `fields=["name","production_code","item_code","available_qty","planned_production_date"]&` +
        `order_by=planned_production_date asc`,
        { headers: { Authorization: `token <KEY>:<SECRET>` }}
      ).then(r => r.json()).then(d => [sku, d.data || []])
    )).then(results => {
      setFpbsByItem(Object.fromEntries(results));
    });
  }, [orderStatus]);

  const ready =
    orderStatus?.status === 'completo' &&
    (orderStatus.products || []).every(p =>
      (p.patients || []).every(pt => pt.validation_status === 'aprovado'));

  const allItemsSelected =
    Object.keys(fpbsByItem).every(sku => selection[sku]);

  const handleSubmit = async () => {
    setBusy(true);
    const resp = await fetch('https://n8n.injemedpharma.com.br/webhook/erp/sync-order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        deal_id: dealId,
        fpb_map: selection,    // { 'TIR00060': 'FPB-...', '00049': 'FPB-...' }
      }),
    });
    setResult(await resp.json());
    setBusy(false);
  };

  return (
    <Tile>
      <Heading>Sync ERPNext</Heading>
      <Text>Status validacao: {orderStatus?.status || 'carregando'}</Text>
      <Text>Pacientes aprovados: {ready ? '✅' : '⏳'}</Text>

      {Object.entries(fpbsByItem).map(([sku, fpbs]) => {
        const prod = orderStatus.products.find(p => p.sku === sku);
        return (
          <Box key={sku}>
            <Text>{prod?.name} (SKU {sku}) — qty {prod?.quantity}</Text>
            <Select
              label={`Lote pra ${sku}`}
              options={fpbs.map(f => ({
                label: `${f.production_code} (${f.available_qty} disponíveis)`,
                value: f.name,
              }))}
              value={selection[sku] || ''}
              onChange={v => setSelection(prev => ({ ...prev, [sku]: v }))}
            />
          </Box>
        );
      })}

      <Button onClick={handleSubmit} disabled={!ready || !allItemsSelected || busy}>
        {busy ? 'Enviando…' : 'Enviar pra ERPNext'}
      </Button>

      {result && (
        <Text>
          {result.ok
            ? `✅ SO ${result.erpnext.sales_order} | reservas: ${result.erpnext.reservations?.length || 0}`
            : `❌ ${JSON.stringify(result)}`}
        </Text>
      )}

      {result?.erpnext?.reserve_errors?.length > 0 && (
        <Box>
          <Heading>Erros de reserva</Heading>
          {result.erpnext.reserve_errors.map((e, i) =>
            <Text key={i}>{e.item_code}: {e.message}</Text>
          )}
        </Box>
      )}
    </Tile>
  );
};
```

## Quem busca o que (fluxo dados)

```
Card React (HubSpot Deal page)
  ├─ context.crm.objectId        → deal_id
  ├─ GET backend validacao       → order status + patients + validations
  └─ GET ERPNext FPB list        → FPBs abertas pra escolher
        ↓ operador escolhe FPB
        ↓ click "Enviar pra ERPNext"
        ↓
n8n webhook
  ├─ Postgres query              → order + company + contact + products + patients + payment (checkout_simples)
  ├─ Transform → ERPNext payload
  └─ POST issue_order ERPNext
        ↓ ERPNext cria/atualiza Customer + Address + Contact + Prescriber + Patient + SO
        ↓ payment_validated + prescriptions_validated → 3 flags ok
        ↓ auto-reserve usando FPB explicito (não FIFO)
        ↓ Production Reservation criada
n8n
  └─ UPDATE Postgres pedido_fc_emitido_at = NOW()
        ↓
Card React
  └─ mostra "✅ SO 00077 criado, lote FPB-2026-00115 reservado"
```

## Idempotência ponta-a-ponta

Re-click do botão (mesmo deal_id + mesmo fpb_name) é seguro:
- ERPNext detecta SO existente por hubspot_deal_id → retorna ele
- Production Reservation só cria se `needed > already_reserved`
- Postgres marca `pedido_fc_emitido_at` apenas uma vez (NULL na WHERE)
