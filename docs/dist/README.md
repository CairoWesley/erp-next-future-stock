# Manual Operacional — Arquivos Gerados

Distribuíveis do manual em 3 formatos, gerados a partir do markdown fonte
`../11-manual-operacional.md`.

## Arquivos

| Arquivo | Tamanho | Uso |
|---|---|---|
| `manual-operacional.html` | ~86 KB | Web Page no ERPNext / abrir em browser |
| `manual-operacional.docx` | ~31 KB | Editar no Word / Google Docs |
| `manual-operacional.pdf`  | ~1.2 MB | Imprimir, distribuir, anexar em e-mail |
| `style.css`               | 5.6 KB | CSS embutido no HTML (referência) |

## Como regerar após editar o markdown

Dependências:
- `pandoc` 2.x+
- Google Chrome (para o PDF)

```bash
cd /Users/wesleycairo/Downloads/erpnext/docs/dist

# HTML (self-contained, com CSS embutido)
pandoc ../11-manual-operacional.md \
  -o manual-operacional.html \
  --standalone \
  --self-contained \
  --metadata title="Manual Operacional — Produção Futura" \
  --css=style.css \
  --toc \
  --toc-depth=2 \
  --highlight-style=tango

# DOCX (com TOC)
pandoc ../11-manual-operacional.md \
  -o manual-operacional.docx \
  --metadata title="Manual Operacional — Produção Futura" \
  --toc \
  --toc-depth=2

# PDF (via Chrome headless do HTML — preserva CSS)
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless --disable-gpu \
  --print-to-pdf="$(pwd)/manual-operacional.pdf" \
  --print-to-pdf-no-header \
  "file://$(pwd)/manual-operacional.html"
```

## Distribuição

### Como subir HTML no ERPNext

1. Login com System Manager
2. *Website → Web Page → + New*
3. Preencher:
   - **Title**: Manual Operacional — Produção Futura
   - **Route**: `manual-operacional`
   - **Published**: ☑
   - **Main Section**: cole o conteúdo do `<body>` do HTML (entre `<body>` e `</body>`)
4. **Save**
5. Acesse: `https://erp.suaempresa.com.br/manual-operacional`

> Alternativa mais simples: anexe o `manual-operacional.html` em
> *Build → File* → cole link no Workspace "Produção Futura" como bloco custom.

Mais opções no **Anexo II** do manual.

### Como distribuir o PDF

- Anexe em e-mail aos novos operadores
- Imprima e deixe na sala da expedição/produção/farmácia
- Suba em pasta compartilhada (Google Drive, SharePoint)

### Como editar o DOCX colaborativamente

- Abra no Word ou Google Docs (File → Open)
- Marque comentários e mudanças em "Track Changes"
- Quando consolidar: regere o markdown fonte ou mantenha o DOCX como mestre
  (perde sincronia com `.md`)

## Workflow recomendado

```
1. Operação muda
        │
        ▼
2. Edite docs/11-manual-operacional.md
        │
        ▼
3. Rode os 3 comandos pandoc/Chrome acima
        │
        ▼
4. Re-suba o HTML no ERPNext (passo "Como subir HTML")
        │
        ▼
5. Avise os times no canal interno
```
