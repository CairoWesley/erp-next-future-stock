# Contrato Card React HubSpot → n8n → ERPNext
> ⚠ **Lote é OBRIGATÓRIO** no step_reserve — não há seleção automática (FIFO removido).
> Sem `item_fpb`/`fpb_map`/`fpb_name` pro item de estoque → erro `BATCH_REQUIRED`,
> pedido criado mas NÃO reservado. O operador SEMPRE escolhe o lote no Card.


> Card React no HubSpot Deal page chama UM webhook único com 2 parâmetros.
> n8n busca todos os dados (Postgres + HubSpot + checkout_simples) e
> sincroniza pra ERPNext. Operador escolhe qual FPB usar pra reservar.

## Webhook URL

```
POST https://n8n.injemedpharma.com.br/webhook/erp/sync-order
Content-Type: application/json
```

## Request body

### Forma PREFERIDA — quantidade por lote (`item_fpb`)

Operador aloca **X ampolas pra cada lote** por item. Sistema distribui os
pacientes entre os lotes (bin-packing). **Regra dura: cada paciente
(receita) cabe inteiro em UM lote — nunca dividido entre 2 lotes.**

```json
{
  "deal_id": "60801476407",
  "item_fpb": [
    {
      "item_code": "TIR00060",
      "lotes": [
        { "fpb_name": "FPB-2026-00115", "qty": 7 },
        { "fpb_name": "FPB-2026-00120", "qty": 3 }
      ]
    },
    {
      "item_code": "00049",
      "lotes": [
        { "fpb_name": "FPB-2026-00130", "qty": 5 }
      ]
    }
  ]
}
```

**Como funciona o bin-packing:**

```
Item TIR00060 — total 10 ampolas (3 pacientes: 5, 3, 2)
Operador aloca: Lote A = 7, Lote B = 3

Distribuição (first-fit-decreasing, receita inteira):
  Paciente 5amp → Lote A   (A: 7→2)
  Paciente 3amp → Lote B   (B: 3→0)
  Paciente 2amp → Lote A   (A: 2→0)

Resultado:
  Production Reservation Lote A = 7 ampolas
  Production Reservation Lote B = 3 ampolas
  Cada paciente fica 100% em UM lote.
```

**Se a alocação não fechar:**

```
Operador aloca: Lote A = 6, Lote B = 4
  Paciente 5amp → Lote A (A: 6→1)
  Paciente 3amp → Lote B (B: 4→1)
  Paciente 2amp → NÃO CABE (A=1, B=1) → ERRO

reserve_errors: [{
  "item_code": "TIR00060",
  "patient": "00085",
  "qty": 2.0,
  "message": "Paciente 00085 (qty 2.0) nao cabe em nenhum lote restante.
              Ajuste as quantidades por lote."
}]
```

SO é criado mesmo assim; só a reserva desse item falha. Operador reajusta
as quantidades e re-chama (idempotente).

### Forma PER-ITEM (`fpb_map`) — 1 lote pra todo o item

```json
{
  "deal_id": "60801476407",
  "fpb_map": {
    "TIR00060": "FPB-2026-00115",
    "00049":    "FPB-2026-00120"
  }
}
```

Todos os pacientes do item vão pro mesmo lote (1 PR por item).

### Forma legada (1 FPB pra tudo)

```json
{ "deal_id": "60801476407", "fpb_name": "FPB-2026-00115" }
```

### Sem FPB (FIFO automático)

```json
{ "deal_id": "60801476407" }
```

ERPNext enfileira FPBs por `planned_production_date asc` até cobrir o total.

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `deal_id` | string | **sim** | HubSpot Deal ID |
| `item_fpb` | array | não | **Preferido.** `[{item_code, lotes:[{fpb_name, qty}]}]` — qtd por lote + bin-pack |
| `fpb_map` | dict | não | `{item_code → fpb_name}` — 1 lote por item |
| `fpb_name` | string | não | Single FPB pra todos items stock (legacy) |
| `order_id` | int | não | Alternativa ao deal_id (Postgres id) |

Precedência: `item_fpb` > `fpb_map` > `fpb_name` > FIFO.

Item non-stock (FRETE) → ignorado automático.

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

## Erros de reserva

Erro de FPB NÃO bloqueia o SO. SO é criado + flags setadas; só a reserva
falha e aparece em `reserve_errors`:

| Mensagem | Causa | Fix |
|---|---|---|
| `Paciente X (qty N) nao cabe em nenhum lote restante.` | Alocação qty-por-lote não fecha bin-pack | Reajustar `qty` por lote no `item_fpb` |
| `Capacidade dos lotes (X) menor que total do item (Y).` | Soma das qty alocadas < total do item | Aumentar qty ou adicionar lote |
| `FPB X nao existe.` | Nome errado / lote apagado | Verificar nome exato |
| `FPB X nao submetida.` | Lote em Rascunho (docstatus=0) | Submeter FPB |
| `FPB X e do item Y, esperado Z.` | Lote é de outro produto | Trocar fpb_name |
| `FPB X status=... nao aceita reservas.` | Lote fechado/encerrado | Trocar fpb_name |
| `Nenhum lote disponivel pra item X` | FIFO sem FPB aberto | Criar FPB |

## Exemplo curl (teste manual)

```bash
# Quantidade por lote (preferido)
curl -X POST https://n8n.injemedpharma.com.br/webhook/erp/sync-order \
  -H "Content-Type: application/json" \
  -d '{
    "deal_id": "60801476407",
    "item_fpb": [
      { "item_code": "TIR00060", "lotes": [
        { "fpb_name": "FPB-2026-00115", "qty": 7 },
        { "fpb_name": "FPB-2026-00120", "qty": 3 }
      ]}
    ]
  }'

# 1 lote por item
curl -X POST https://n8n.injemedpharma.com.br/webhook/erp/sync-order \
  -H "Content-Type: application/json" \
  -d '{ "deal_id": "60801476407", "fpb_map": { "TIR00060": "FPB-2026-00115" } }'

# FIFO automático
curl -X POST https://n8n.injemedpharma.com.br/webhook/erp/sync-order \
  -H "Content-Type: application/json" \
  -d '{ "deal_id": "60801476407" }'
```

## React Card — esqueleto (qty por lote, N lotes por item)

UI por item: lista de alocações `(FPB, qty)`. Operador adiciona lotes e
distribui as ampolas. Card valida que `soma(qty) == total do item` antes
de habilitar o envio.

```tsx
import { useState, useEffect } from 'react';

const SyncCard = ({ context }) => {
  const dealId = context.crm.objectId;
  const [orderStatus, setOrderStatus] = useState(null);
  const [fpbsByItem, setFpbsByItem] = useState({});  // { sku: FPB[] }
  // alloc: { sku: [ {fpb_name, qty} ] }
  const [alloc, setAlloc] = useState({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  // 1. Status do order (backend validacao)
  useEffect(() => {
    fetch(`https://api.validacao.injemedpharma.com.br/api/orders/deal/${dealId}`)
      .then(r => r.json()).then(setOrderStatus);
  }, [dealId]);

  // 2. FPBs abertos por item (paralelo, exclui FRETE)
  useEffect(() => {
    if (!orderStatus?.products?.length) return;
    const skus = orderStatus.products
      .filter(p => p.sku !== 'SV02000002')
      .map(p => p.sku);
    Promise.all(skus.map(sku =>
      fetch(`https://erp.injemedpharma.com.br/api/resource/Future Production Batch?` +
        `filters=[["item_code","=","${sku}"],["status","in",["Aberta para Reserva","Reservada Parcialmente"]],["docstatus","=",1]]&` +
        `fields=["name","production_code","available_qty"]&order_by=planned_production_date asc`,
        { headers: { Authorization: `token <KEY>:<SECRET>` }}
      ).then(r => r.json()).then(d => [sku, d.data || []])
    )).then(rs => setFpbsByItem(Object.fromEntries(rs)));
  }, [orderStatus]);

  const totalBySku = sku => {
    const prod = (orderStatus?.products || []).find(p => p.sku === sku);
    return Number(prod?.quantity || 0);
  };
  const allocSum = sku =>
    (alloc[sku] || []).reduce((s, l) => s + Number(l.qty || 0), 0);

  const ready =
    orderStatus?.status === 'completo' &&
    (orderStatus.products || []).every(p =>
      (p.patients || []).every(pt => pt.validation_status === 'aprovado'));

  // cada item stock: soma das qty alocadas == total do item
  const allClosed = Object.keys(fpbsByItem).every(
    sku => allocSum(sku) === totalBySku(sku) && allocSum(sku) > 0);

  const addLote = sku =>
    setAlloc(p => ({ ...p, [sku]: [...(p[sku] || []), { fpb_name: '', qty: 0 }] }));
  const setLote = (sku, i, field, v) =>
    setAlloc(p => {
      const arr = [...(p[sku] || [])];
      arr[i] = { ...arr[i], [field]: v };
      return { ...p, [sku]: arr };
    });

  const handleSubmit = async () => {
    setBusy(true);
    const item_fpb = Object.entries(alloc).map(([item_code, lotes]) => ({
      item_code,
      lotes: lotes.filter(l => l.fpb_name && Number(l.qty) > 0)
                  .map(l => ({ fpb_name: l.fpb_name, qty: Number(l.qty) })),
    }));
    const resp = await fetch('https://n8n.injemedpharma.com.br/webhook/erp/sync-order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deal_id: dealId, item_fpb }),
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
        const sum = allocSum(sku), tot = totalBySku(sku);
        return (
          <Box key={sku}>
            <Text>{prod?.name} (SKU {sku}) — total {tot} ampolas
              {' '}({sum}/{tot} alocadas {sum === tot ? '✅' : '⚠'})</Text>
            {(alloc[sku] || []).map((lote, i) => (
              <Flex key={i} gap="small">
                <Select
                  options={fpbs.map(f => ({
                    label: `${f.production_code} (${f.available_qty} disp)`,
                    value: f.name,
                  }))}
                  value={lote.fpb_name}
                  onChange={v => setLote(sku, i, 'fpb_name', v)}
                />
                <NumberInput
                  value={lote.qty}
                  min={0}
                  onChange={v => setLote(sku, i, 'qty', v)}
                />
              </Flex>
            ))}
            <Button variant="secondary" onClick={() => addLote(sku)}>
              + Adicionar lote
            </Button>
          </Box>
        );
      })}

      <Button onClick={handleSubmit} disabled={!ready || !allClosed || busy}>
        {busy ? 'Enviando…' : 'Enviar pra ERPNext'}
      </Button>

      {result && (
        <Text>
          {result.ok
            ? `✅ SO ${result.erpnext.sales_order} | ${result.erpnext.reservations?.length || 0} reserva(s)`
            : `❌ ${JSON.stringify(result)}`}
        </Text>
      )}

      {result?.erpnext?.reserve_errors?.length > 0 && (
        <Box>
          <Heading>Erros de reserva</Heading>
          {result.erpnext.reserve_errors.map((e, i) =>
            <Text key={i}>{e.item_code}{e.patient ? ` / ${e.patient}` : ''}: {e.message}</Text>
          )}
        </Box>
      )}
    </Tile>
  );
};
```

> Card só habilita "Enviar" quando, pra cada item stock,
> `soma(qty alocada) == total do item`. O ERPNext ainda valida bin-pack
> (receita inteira) — se a divisão não fechar com as receitas reais,
> retorna `reserve_errors` e o operador reajusta.

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
