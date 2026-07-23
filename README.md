# Dashboard de Estoque — Depósito 006

Dashboard estático (HTML) para acompanhamento diário do estoque do Depósito 006,
gerado a partir da planilha `BD_006.xlsx`. Complementa o BI em Power BI já em
construção, servindo como versão web para apresentação de resultados, publicável
gratuitamente pelo GitHub Pages.

## O que ele mostra

- Filtro por **Família** (que já refina a lista de **Produto**, efeito cascata) e por **Período**.
- Cartões com saldo atual, saldo do dia anterior e variação.
- Gráfico de evolução do saldo dia a dia para o produto selecionado.
- Tabela de lotes em estoque na última leitura, com lote, data de fabricação,
  data de validade e um selo de status (dias até vencer: verde ≥ 21 dias,
  amarelo entre 8 e 20, vermelho ≤ 7 dias ou vencido).

## Estrutura do projeto

```
dashboard-estoque-006/
├── data/
│   └── BD_006.xlsx          <- base de dados (substitua por uma versão mais nova quando atualizar)
├── scripts/
│   ├── build_dashboard.py   <- lê o xlsx e gera o HTML
│   └── template.html        <- layout/estilo/gráfico (Plotly), com um marcador __DASHBOARD_DATA__
├── docs/
│   ├── index.html           <- dashboard gerado (é o que o GitHub Pages publica)
│   └── vendor/plotly.min.js <- biblioteca de gráficos, embutida localmente (não depende de internet)
├── requirements.txt
└── README.md
```

## Como atualizar o dashboard (rotina do dia a dia)

1. Substitua o arquivo `data/BD_006.xlsx` pela versão mais recente da base
   (a mesma planilha que você já usa/atualiza para o Power BI).
2. Rode o script:

   ```bash
   pip install -r requirements.txt
   python scripts/build_dashboard.py
   ```

3. Isso regenera `docs/index.html` com os dados novos.
4. Suba a alteração para o GitHub:

   ```bash
   git add data/BD_006.xlsx docs/index.html
   git commit -m "Atualiza dados do estoque"
   git push
   ```

5. Se o GitHub Pages já estiver ativado (ver abaixo), o site publicado
   atualiza automaticamente em 1–2 minutos após o push.

## Como publicar no GitHub Pages (fazer uma vez só)

1. Crie um repositório no GitHub (ex: `dashboard-estoque-006`) e suba este
   projeto (`git init`, `git remote add origin ...`, `git push`).
2. No GitHub, vá em **Settings > Pages**.
3. Em **Source**, selecione a branch `main` e a pasta `/docs`.
4. Salve. Em alguns minutos o link do dashboard aparece na própria página
   (formato `https://SEU-USUARIO.github.io/dashboard-estoque-006/`).

## Abrindo localmente (sem GitHub)

Também é possível abrir o arquivo `docs/index.html` direto no navegador
(duplo clique) sem precisar de internet ou servidor — os gráficos funcionam
porque a biblioteca Plotly está embutida em `docs/vendor/`.

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
