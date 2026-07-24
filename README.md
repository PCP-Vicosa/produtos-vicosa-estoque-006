# Viçosa BI — Painel de Indicadores

Portal com os painéis de BI da Viçosa, publicado gratuitamente pelo GitHub
Pages. Hoje tem um painel funcionando (Estoque 006) e um espaço reservado
para o próximo (Aderência).

## Estrutura do portal

```
docs/
├── index.html            <- página inicial (portal), com os botões dos painéis
├── estoque-006/
│   ├── index.html         <- dashboard de Estoque 006 (gerado pelo script)
│   └── vendor/plotly.min.js
└── aderencia/
    └── index.html         <- placeholder "em construção" até os dados chegarem
```

Cada painel novo ganha sua própria subpasta dentro de `docs/`, e um novo
card é adicionado na página inicial (`docs/index.html`) apontando para ela.

## Painel: Estoque 006

Dashboard para acompanhamento diário do estoque do Depósito 006, gerado a
partir da planilha `BD_006.xlsx`. Complementa o BI em Power BI, servindo
como versão web para apresentação de resultados.

### O que ele mostra

- 3 páginas: **Visão Geral** (saldo total, variação, saldo por setor),
  **Família/SKU** (evolução por setor + gráfico cascata por SKU) e
  **Lotes e Validade** (tabelas de lotes com alerta de vencimento).
- Filtros por **Setor** e **Produto** com múltipla seleção (checkboxes).
- "Dias até vencer" calculado com base na data real de hoje (a data do
  dispositivo de quem está vendo a página), não na data da última leitura.

### Estrutura

```
dashboard-estoque-006/
├── data/
│   ├── BD_006.xlsx                  <- base de dados (histórico empilhado dia a dia)
│   ├── Dim_Peso_Produto.csv         <- peso (kg) por unidade de cada produto
│   ├── Dim_Nome_Curto_Produto.csv   <- nome comercial curto de cada produto
│   └── Tema.json                    <- tema de cores exportado do Power BI
├── scripts/
│   ├── build_dashboard.py   <- lê os dados e gera docs/estoque-006/index.html
│   └── template.html        <- layout/estilo/gráficos (Plotly), com marcador __DASHBOARD_DATA__
├── docs/
├── requirements.txt
└── README.md
```

### Como atualizar o dashboard (rotina do dia a dia)

1. Empilhe a leitura do dia na base `data/BD_006.xlsx` (nova(s) linha(s)
   com a coluna `Data Estoque` = data de hoje, mesmas colunas do restante
   da planilha). É este arquivo, já com o histórico completo, que o script lê.
2. Rode o script:

   ```bash
   pip install -r requirements.txt
   python scripts/build_dashboard.py
   ```

3. Isso regenera `docs/estoque-006/index.html` com os dados novos.
4. Suba a alteração para o GitHub:

   ```bash
   git add data/BD_006.xlsx docs/estoque-006/index.html
   git commit -m "Atualiza dados do estoque"
   git push
   ```

5. Se o GitHub Pages já estiver ativado (ver abaixo), o site publicado
   atualiza automaticamente em 1–2 minutos após o push.

## Como publicar no GitHub Pages (fazer uma vez só)

1. Crie um repositório no GitHub e suba este projeto (`git init`,
   `git remote add origin ...`, `git push`).
2. No GitHub, vá em **Settings > Pages**.
3. Em **Source**, selecione a branch `main` e a pasta `/docs`.
4. Salve. Em alguns minutos o portal aparece em
   `https://SEU-USUARIO.github.io/NOME-DO-REPOSITORIO/`.

## Abrindo localmente (sem GitHub)

Dá pra abrir `docs/index.html` direto no navegador, mas como é um arquivo
local (protocolo `file://`), os links entre pastas (`./estoque-006/`) não
abrem `index.html` automaticamente — funciona certinho só quando publicado
no GitHub Pages (ou rodando um servidor local, ex: `python -m http.server`
dentro da pasta `docs/`).

## Observação sobre a planilha

O script espera as seguintes colunas em `BD_006.xlsx` (aba `Plan1`, exatamente
com esses nomes de cabeçalho):

- `Data Estoque` — data da leitura/snapshot
- `Família` — código da família do produto
- `Produto` — código do produto
- `Descrição Produto` — nome do produto (usa-se a primeira parte antes do "-")
- `Saldo Lote` — saldo em estoque do lote
- `Lote Fab.` — número do lote
- `Data Fab. Lote` — data de fabricação do lote
- `Data Validade` — data de validade do lote

Se a planilha crescer com novas leituras diárias (novas linhas com uma nova
`Data Estoque`), basta atualizar o arquivo e rodar o script novamente — o
gráfico de evolução e os cartões se atualizam sozinhos.
