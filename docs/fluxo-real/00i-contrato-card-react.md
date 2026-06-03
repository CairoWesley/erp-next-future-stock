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

```json
{
  "deal_id":  "60801476407",
  "fpb_name": "FPB-2026-00115"
}
```

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `deal_id` | string | **sim** | HubSpot Deal ID (também salvo em `validacao_receita.orders.hubspot_deal_id`) |
| `fpb_name` | string | não | Nome do Future Production Batch alvo. Se omitido, n8n usa FIFO (próximo FPB disponível por `planned_production_date`). |

Alternativa: `order_id` (int Postgres) ao invés de `deal_id`.

Alias aceitos: `future_production_batch` no lugar de `fpb_name`.

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

## React Card — esqueleto sugerido

```tsx
import { useState, useEffect } from 'react';
import { hubspot } from '@hubspot/ui-extensions';

const SyncCard = ({ context }) => {
  const dealId = context.crm.objectId;
  const [orderStatus, setOrderStatus] = useState(null);
  const [fpbs, setFpbs] = useState([]);
  const [selectedFpb, setSelectedFpb] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  // 1. Buscar status do order no backend validacao_receita
  useEffect(() => {
    fetch(`https://api.validacao.injemedpharma.com.br/api/orders/deal/${dealId}`)
      .then(r => r.json()).then(setOrderStatus);
  }, [dealId]);

  // 2. Buscar FPBs abertas no ERPNext (filtra por item dos products do order)
  useEffect(() => {
    if (!orderStatus?.products?.length) return;
    const skus = orderStatus.products.map(p => p.sku);
    fetch(`https://erp.injemedpharma.com.br/api/resource/Future Production Batch?` +
      `filters=[["item_code","in",${JSON.stringify(skus)}],["status","=","Aberta para Reserva"],["docstatus","=",1]]&` +
      `fields=["name","production_code","item_code","available_qty","planned_production_date"]`,
      { headers: { Authorization: `token <KEY>:<SECRET>` }}
    ).then(r => r.json()).then(d => setFpbs(d.data));
  }, [orderStatus]);

  const ready =
    orderStatus?.status === 'completo' &&
    (orderStatus.products || []).every(p =>
      (p.patients || []).every(pt => pt.validation_status === 'aprovado'));
    // payment check no checkout_simples seria server-side via backend extra OU n8n

  const handleSubmit = async () => {
    setBusy(true);
    const resp = await fetch('https://n8n.injemedpharma.com.br/webhook/erp/sync-order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deal_id: dealId, fpb_name: selectedFpb || null }),
    });
    setResult(await resp.json());
    setBusy(false);
  };

  return (
    <Tile>
      <Heading>Sync ERPNext</Heading>
      <Text>Status validacao: {orderStatus?.status || 'carregando'}</Text>
      <Text>Pacientes aprovados: {ready ? '✅' : '⏳'}</Text>
      
      <Select
        label="Lote (FPB) a reservar"
        options={fpbs.map(f => ({
          label: `${f.production_code} (${f.available_qty} disponíveis)`,
          value: f.name
        }))}
        value={selectedFpb}
        onChange={setSelectedFpb}
      />
      
      <Button onClick={handleSubmit} disabled={!ready || busy}>
        {busy ? 'Enviando…' : 'Enviar pra ERPNext'}
      </Button>
      
      {result && (
        <Text>
          {result.ok
            ? `✅ SO ${result.erpnext.sales_order} criado.`
            : `❌ ${JSON.stringify(result)}`}
        </Text>
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
