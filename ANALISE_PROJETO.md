# Viçosa BI — Análise técnica, crítica e roteiro de evolução

**Data da análise:** 27/07/2026
**Escopo:** todo o projeto (bases de dados, scripts de build, site publicado e rotina de trabalho)
**Base de referência:** BD_006.xlsx (1.403 linhas, 9 dias), BD_022.xlsx (47 linhas, snapshot de 25/07) e Producao_Semanal_PowerBI.xlsx (1.296 linhas, 29 semanas)

---

## 1. Resumo executivo

O projeto entrega hoje três painéis funcionais e publicados, com visual coerente, filtros que funcionam e números que já foram validados contra o Power BI original. Isso não é pouco: em pouco mais de uma semana o site saiu do zero e substituiu na prática a leitura de três relatórios distintos. O mérito principal é a arquitetura escolhida — site estático gerado por Python — que é barata, rápida, não depende de licença e não quebra quando o servidor de BI cai.

Dito isso, a análise encontrou **um problema de dado que compromete a confiança em um dos painéis hoje**, **uma limitação estrutural que impede o projeto de crescer** e **um conjunto grande de informação disponível que está sendo jogada fora**. Em ordem de gravidade:

1. **O painel Estoque 022 está mostrando material que já foi liberado.** O BD_022.xlsx em uso é do dia 25/07, enquanto o BD_006 é do dia 27/07. Dos 47 lotes exibidos como "aguardando liberação da qualidade", **33 já aparecem no depósito 006 do dia 27 com o saldo idêntico** — ou seja, 38.746,06 kg dos 55.235,55 kg mostrados no painel (70,1% do total) já foram liberados e estão sendo contados duas vezes entre os dois painéis. Não é um erro de cálculo do código: é o arquivo-fonte desatualizado sem que a página avise isso.

2. **Não existe chave que ligue o estoque à produção.** Dos 49 produtos da base de aderência e dos 44 do estoque, **apenas 3 nomes coincidem exatamente**. Enquanto isso não for resolvido, nenhum indicador que cruze "o que foi produzido" com "o que está em estoque" pode ser construído — e é exatamente aí que estão os indicadores de maior valor gerencial (cobertura, giro, aderência real de entrega).

3. **Só 8 das 37 colunas do BD_006 são usadas.** Parte disso é inevitável (25 colunas vêm constantes do SAP e são inúteis), mas o histórico dia a dia que já está empilhado permite calcular muito mais do que o painel mostra hoje: consumo diário por SKU, cobertura em dias, curva ABC, aging, risco de perda por validade em valor. Esses números já existem na base — só não estão sendo extraídos.

O restante deste documento detalha cada ponto, critica o que foi feito (inclusive o meu próprio trabalho de implementação) e propõe um roteiro priorizado.

---

## 2. O que existe hoje

O repositório `produtos-vicosa-estoque-006` gera um site estático em `/docs`, publicado por GitHub Pages, com uma página índice e três painéis.

**Aderência** lê a planilha semanal de produção e reproduz o KPI de aderência com três indicadores (Demandado × Produzido, Demandado × Programado, Programado × Produzido), quantidade produzida em unidades e em quilos, evolução mensal, comparativo semanal, aderência bruta por produto contra a meta de 95–105% e a lista de comentários da semana.

**Estoque 006** lê o histórico empilhado de saldos do depósito de expedição e mostra saldo em quilos ao longo do tempo, saldo por setor, análise por família e SKU (com gráfico cascata), além de três tabelas: todos os lotes, lotes com menos de 50% da validade e lotes vencidos.

**Estoque 022** replica a estrutura de tabelas do 006 para o depósito da qualidade, sem filtro de data, exibindo a data do arquivo como texto.

Os três compartilham a mesma barra lateral recolhível, o mesmo tema de cores herdado do Power BI, os mesmos componentes de filtro multi-seleção e o mesmo sistema de tabela ordenável. Isso foi bem feito: a consistência visual entre os painéis é alta e o custo de adicionar um quarto painel hoje é baixo.

---

## 3. Diagnóstico das bases de dados

### 3.1 BD_006.xlsx — extração de saldos do depósito 6

O arquivo tem 37 colunas, mas **25 delas vêm com um único valor repetido em todas as linhas** e não carregam nenhuma informação: `Origem`, `Derivação`, `Depósito`, `Qtd. Bloqueada`, `Qtd.Res.Analise`, `Qtd. Embalada`, as seis colunas `Dimensão`, `Lote Original`, `Grupo Estoque`, `Grupo Produção`, `Grupo Comercial`, `Descrição Depósito`, `Status Lote`, `Endereçam.`, `Lote de Fabricante`, `Fabricante`, `Lote Fabricante`, `Data Valid. Fabr.`, `Cód. Prod. Fabr.` e `Marca`. Vários deles são campos que o SAP simplesmente não preenche nessa transação. Isso é importante saber para não se planejar indicadores em cima de campos que nunca virão preenchidos — `Status Lote` e `Endereçam.`, em particular, seriam ótimos, mas vêm vazios.

Sobram 12 colunas com variação real, das quais **8 são efetivamente usadas** pelos painéis. As quatro com informação desperdiçada são:

| Coluna | Situação | Valor potencial |
|---|---|---|
| `Qtd. Reservada` | 62 valores distintos, 31 lotes com reserva no dia 27 (1.164,21 un) | Permite separar saldo **livre** de saldo **comprometido** — hoje o painel trata tudo como disponível |
| `UM` | 3 valores (UN, KG, L) | Permite validar a conversão para quilos e detectar SKU com unidade trocada |
| `Cód. Fis.` | 44 valores (EAN) | Chave estável para integrar com qualquer outro sistema, muito melhor que o nome do produto |
| `Descr. Fis.` | 44 valores | Descrição alternativa, útil para conferência |

A cobertura da dimensão de peso está perfeita: os 44 produtos do BD_006 têm gramatura e nome curto cadastrados. Isso merece registro porque é o tipo de coisa que quebra em silêncio quando entra um SKU novo — hoje o script apenas imprime um aviso e trata como 0 kg, o que faria o produto sumir do gráfico sem ninguém perceber.

O histórico tem 9 dias (14, 15, 20, 21, 22, 23, 24, 25 e 27 de julho), com buracos nos dias 16, 17, 18, 19 e 26. Os buracos importam: qualquer cálculo de consumo diário precisa dividir pela distância real entre snapshots, não assumir um dia. O script atual não faz essa correção porque ainda não calcula consumo.

### 3.2 BD_022.xlsx — depósito da qualidade

Mesma estrutura, 47 linhas, 26 colunas constantes. Aqui `Qtd. Reservada` também vem zerada — o que faz sentido, material retido não é reservado.

O problema não é a estrutura, é o **regime de atualização**. O arquivo é sobrescrito, sem histórico. Isso tem duas consequências. A primeira já se materializou: o arquivo em uso é de 25/07 e o painel não tem como saber que está velho — ele mostra a data do arquivo, mas quem olha o site lado a lado vê "Estoque 022 · 25/07" e "Estoque 006 · 27/07" sem entender que os 38,7 toneladas do primeiro já migraram para o segundo. A segunda é mais estratégica: **sem histórico, o indicador mais valioso desse depósito é impossível de calcular — o tempo médio de liberação da qualidade.** Guardar um snapshot por dia (mesmo que só a data e as colunas úteis) custa quilobytes e destrava esse KPI.

### 3.3 Producao_Semanal_PowerBI.xlsx — base de aderência

1.296 linhas cobrindo 29 semanas de 2026 (janeiro a julho), 49 produtos, 7 setores. É a base mais rica do projeto em profundidade temporal — sete meses contra nove dias do estoque.

O ponto crítico já conhecido: **todas as 11 colunas calculadas vêm vazias** (`Ano`, `Mês`, `Mês Nº`, os três pares de KG, os dois Ajustados e as três colunas de Aderência). O Excel salva a fórmula sem o valor em cache. O script hoje recalcula tudo em Python, o que resolve — mas é uma dependência frágil: se alguém mudar uma fórmula na planilha, o Python continuará usando a fórmula antiga sem avisar. A recomendação estrutural é **inverter a lógica**: a planilha deveria ser apenas entrada de dados crus (produto, setor, gramatura, programado UN, produzido UN, demanda UN, semana) e todo o cálculo deveria viver no Python, com as colunas calculadas simplesmente removidas do arquivo. Isso elimina a classe inteira de erro.

A coluna `Comentários` tem apenas 36 preenchimentos em 1.296 linhas (2,8%). É pouco, mas é o único dado qualitativo do projeto e explica os desvios — vale a pena estimular o preenchimento, porque um painel que mostra 78% de aderência sem dizer o motivo gera mais reunião do que ação.

### 3.4 O elo que falta entre as bases

Este é o achado estrutural mais importante.

| Base | Identificador do produto | Exemplo |
|---|---|---|
| BD_006 / BD_022 | Código SAP de 10 dígitos + nome curto da dimensão | `0400300026` → "Coco 900g" |
| Producao_Semanal | Texto livre digitado | "Iogurte Coco 900g" |

Comparando os nomes curtos do estoque com os nomes da aderência, **apenas 3 dos 49 batem exatamente**. Os padrões de escrita são incompatíveis: a aderência escreve "Doce de Leite 400g", "LEITE PASTEURIZADO VIÇOSA INTEGRAL" e "Iogurte Vida Leve Morango 180g", enquanto o estoque tem "Tradicional 400g", "Integral 1L" e "Vida Leve Morango 180g". Há também diferenças de caixa ("Requeijão Light 200g" contra "Requeijão Light 200G") que sozinhas já quebrariam o cruzamento.

Além disso os setores divergem: o estoque deriva 6 setores do código de família (Iogurte, Doce, Manteiga, Queijo, Leite, Requeijão) e a aderência tem 7 escritos em caixa alta, incluindo RICOTA, que não existe no mapeamento do estoque.

**Sem uma tabela de-para produto → código SAP, os dois domínios do projeto permanecem ilhas.** Construir esse de-para é um trabalho de uma tarde (49 linhas, feito uma vez) e é o pré-requisito de metade dos indicadores propostos na seção 6.

---

## 4. Achados críticos

### 4.1 Dupla contagem entre os painéis 006 e 022 — impacto alto, correção imediata

Comparando o snapshot de 27/07 do BD_006 com o BD_022 atual:

- 33 dos 47 lotes do 022 estão presentes no 006 do dia 27
- em 30 desses 33, o saldo é **exatamente igual** nos dois arquivos
- os 33 lotes foram fabricados entre 20 e 25/07 — exatamente a janela que estava retida na qualidade no dia 25
- em nenhum dos 8 dias anteriores do histórico (14 a 25/07) houve qualquer sobreposição de lote entre os dois depósitos

A conclusão é direta: o BD_022 não foi atualizado desde 25/07, aquele material já foi liberado e transferido, e o painel continua mostrando 55.235,55 kg como retido quando o número real é da ordem de 16.489,49 kg (os 14 lotes exclusivos). Quem somar os dois painéis está contando 22,6% do estoque do 006 duas vezes.

**Correções recomendadas, em ordem:** (a) atualizar o BD_022 junto com o BD_006, sempre, na mesma rotina; (b) fazer o build **falhar ou alertar em destaque** quando a data do BD_022 for anterior à do último snapshot do BD_006; (c) exibir no painel 022 um aviso visual quando o arquivo tiver mais de um dia de atraso; (d) como rede de segurança, o build do 022 pode remover automaticamente os lotes que já aparecem no 006 do dia mais recente, registrando quantos foram removidos.

### 4.2 O histórico do estoque é o ativo mais valioso e é o menos protegido

Os 9 dias empilhados no BD_006 não existem em nenhum outro lugar — o SAP entrega um saldo instantâneo, não um histórico. Esse arquivo é hoje o único acervo dessa informação, mora em uma pasta da área de trabalho, é editado manualmente, e já teve dois episódios de dias faltando (24, 25 e 27). Se o arquivo se perder ou corromper, a série é irrecuperável.

Isso não pede um banco de dados imediatamente, mas pede pelo menos: versionamento do arquivo de dados no Git (hoje ele está lá, o que ajuda), um backup automático datado a cada build, e — o mais importante — **substituir a consolidação manual por um script**. A consolidação de dias é hoje o único passo do processo que depende de alguém abrir o Excel e colar linhas, e é exatamente onde os erros aconteceram.

### 4.3 Fragilidades menores, mas reais

O `.gitignore` não ignora os arquivos de bloqueio do Excel (`~$*.xlsx`). Um deles já apareceu no diagnóstico do dia 27 e confundiu a investigação.

O `requirements.txt` tem apenas `pandas` e `openpyxl` sem versão fixada. Uma atualização de qualquer um dos dois pode mudar o comportamento de leitura sem aviso.

Não existe nenhuma validação automática entre ler o Excel e gerar o HTML. Se a extração vier com metade das linhas, o site publica metade das linhas em silêncio. Um bloco de verificações simples — número de dias esperado, saldo total dentro de uma faixa plausível em relação ao dia anterior, nenhum SKU sem gramatura, nenhuma data de validade anterior à de fabricação — pegaria a maioria dos problemas antes da publicação.

Não existe um comando único de build. Hoje são três scripts rodados separadamente, o que abre espaço para publicar um painel atualizado e outro não. Um `build_all.py` resolve.

---

## 5. Crítica da rotina de trabalho

A rotina atual funciona, mas depende demais de intervenção manual em pontos onde o erro é silencioso.

O que está **bem resolvido**: a decisão de manter os arquivos-fonte dentro do repositório (dá rastreabilidade — dá para saber exatamente qual base gerou qual versão do site); a padronização da pasta `BI 006` como origem única; e o hábito de publicar por commit descritivo, o que já criou um histórico legível de 32 commits.

O que **preocupa**:

A consolidação dos dias no BD_006 é manual e já falhou duas vezes na semana analisada. É o passo mais crítico do processo e o menos protegido. A recomendação é passar para um modelo em que você deposita os arquivos diários numa pasta (`data/diarios/BD_006_2026-07-27.xlsx`) e o script empilha sozinho, ignorando duplicatas por chave (data + lote + produto). Isso torna o processo idempotente: rodar duas vezes não duplica nada, e um dia esquecido pode ser adicionado depois sem retrabalho.

O BD_022 depende de você lembrar de exportar de novo. Como vimos em 4.1, esse "lembrar" já custou a confiabilidade do painel. Enquanto o passo continuar manual, o build precisa checar a data e reclamar.

A verificação pós-publicação é visual — você abre o site e confere. Isso não escala com o número de painéis e não pega erros sutis (um SKU que sumiu, um total que mudou 30%). Um resumo impresso ao final de cada build ("9 dias, 170 lotes, 171.109,33 kg, variação de -2,1% em relação ao dia anterior, 0 avisos") permite conferir em três segundos e detecta o que o olho não pega.

Por fim, uma crítica ao **meu próprio trabalho de implementação** nesta série de sessões: eu resolvi cada problema quando ele apareceu (o zip malformado do SAP, os estilos do LibreOffice, as fórmulas sem cache, o fuso horário) e cada correção foi certeira, mas foram todas correções reativas. Em nenhum momento eu propus a camada de validação que teria detectado esses problemas antes de você — a maioria deles chegou até você como "o site está errado" em vez de "o build recusou publicar porque a base veio incompleta". Também gerei três templates HTML com muito código duplicado entre eles (formatadores, componente de multi-seleção, sistema de ordenação de tabela, barra lateral): funciona, mas cada ajuste de formato de número precisou ser feito três vezes, e nas próximas mudanças isso vai custar caro. Essas duas dívidas — validação e código compartilhado — são as que eu priorizaria antes de qualquer indicador novo.

---

## 6. Indicadores que podem ser construídos

Organizei por esforço, do que já é possível com os dados de hoje ao que exige nova coleta.

### 6.1 Já possíveis hoje, sem mudar nada na coleta

**Consumo diário e cobertura de estoque (dias de venda).** Rastreando lote a lote entre snapshots consecutivos, dá para medir quanto saiu de cada SKU por dia. Testei: é calculável para 43 dos 44 SKUs (um único SKU não teve nenhuma saída observada no período).

O método precisa ficar registrado no código, porque o resultado muda bastante conforme a escolha — cheguei a valores entre 8 e 18 dias de mediana testando variantes diferentes. A definição que recomendo fixar, por ser a mais defensável com os buracos que a série tem, é: consumo total do SKU = soma de todas as *reduções* de saldo por lote entre snapshots consecutivos ao longo de todo o período; consumo diário = esse total dividido pelos dias corridos entre o primeiro e o último snapshot (13 dias, de 14 a 27/07); cobertura = saldo atual ÷ consumo diário. Por esse critério, a **mediana de cobertura é de 13,2 dias**, com **6 SKUs abaixo de 2 dias** (risco de ruptura), 10 abaixo de 5 dias e **8 acima de 30 dias** (excesso).

Este é, na minha avaliação, **o indicador de maior valor imediato do projeto** — transforma o painel de "quanto tem" em "quanto tempo dura". A ressalva é que, com 9 snapshots e 5 dias faltando, ele ainda é uma estimativa grosseira; com um mês de série diária completa passa a ser confiável, e é mais um motivo para automatizar a consolidação.

**Curva ABC por SKU.** No dia 27, os 5 maiores SKUs sozinhos representam 74,1% do estoque em quilos e são necessários 7 SKUs para chegar aos 80% (o sexto leva o acumulado a 77,5% e o sétimo a 80,2%). Ou seja, 7 dos 44 SKUs são a classe A. Uma visão ABC diz onde vale a pena apertar o controle e onde não vale.

**Aging e risco de perda em valor.** A base já traz fabricação e validade de cada lote. Hoje o painel classifica por "menos de 50% de validade", que é um corte único. Uma faixa etária completa por **percentual de vida útil já consumida** (0–25%, 25–50%, 50–75%, 75–100%, vencido) mostra a distribuição — no dia 27 são 116 lotes na primeira faixa, 35, 13, 5 e 1 vencido. Vale padronizar a leitura em toda a interface, porque hoje as tabelas falam em validade *restante* e a inversão das duas convenções confunde (a mesma foto lida por validade restante daria 5/18/35/111/1). Somando o saldo por faixa em quilos, sai um indicador de material em risco: **hoje há 1.654,40 kg vencendo em até 7 dias e 5.457,93 kg em até 30 dias**. Se a dimensão de produto ganhar uma coluna de custo por quilo, isso vira um valor em reais, que é a linguagem que a diretoria entende.

**Vida útil por setor e desvio de padrão.** A vida útil total varia muito por setor (Leite: mediana de 8 dias; Iogurte: 44; Requeijão: 97; Manteiga: 128,5; Doce: 179). Dentro de Queijo a variação vai de 85 a 119 dias, o que sugere ou produtos com shelf life diferente agrupados no mesmo setor ou lotes com data cadastrada errada. Um alerta de "vida útil fora do padrão do SKU" pegaria erro de cadastro de validade na origem.

**Saldo livre versus comprometido.** Usando `Qtd. Reservada`, o card "Saldo Atual" pode ser desdobrado em disponível e reservado. São 1.164,21 unidades reservadas em 31 lotes no dia 27 — pouco em volume, mas é a diferença entre "tenho" e "posso vender".

**Entradas e saídas por dia.** O rastreio lote a lote também identifica quantos lotes novos entraram e quantos foram zerados por dia. Um gráfico de barras entrada/saída ao lado da linha de saldo explica *por que* o saldo mudou, coisa que a linha sozinha não faz.

**Aderência: tendência e ranking de ofensores.** A base de aderência tem 29 semanas. Dá para mostrar a série completa com média móvel, identificar os produtos que mais reprovaram a meta ao longo do ano (frequência fora da faixa de 95–105%, não só o valor da semana) e separar desvio para cima (produziu mais que o programado) de desvio para baixo, que têm causas e consequências opostas.

**Aderência: contribuição em quilos para o desvio.** Hoje o percentual trata todos os produtos igualmente. Um produto de 5 kg que ficou 20% abaixo pesa muito mais na fábrica do que um de 120 g na mesma situação. Um gráfico de "quilos faltantes por produto" ordena as prioridades corretamente.

### 6.2 Possíveis com pequenas mudanças na coleta

**Tempo médio de liberação da qualidade.** Basta guardar um snapshot diário do BD_022 (arquivar por data em vez de sobrescrever). Com o histórico, o lote que aparece no 022 no dia X e no 006 no dia Y dá o lead time de liberação por setor e por produto. Já dá para ver o esboço disso: os 33 lotes que estavam retidos em 25/07 foram liberados até 27/07. Esse é o KPI que justifica o painel 022 existir.

**Estoque total da fábrica e curva de retenção.** Com o histórico do 022, o painel pode mostrar a soma dos dois depósitos e o percentual retido ao longo do tempo — hoje o material na qualidade representa 32,3% do que está na expedição, um número que ninguém acompanha.

**Cobertura contra demanda real.** Com a tabela de-para produto (seção 3.4), a cobertura deixa de ser calculada sobre o consumo observado e passa a ser calculada sobre a demanda programada da base de aderência, que é a informação correta para planejar.

**Aderência de entrega (produzido versus consumido).** Cruzando produção semanal com entrada de lote no estoque, dá para verificar se o que foi apontado como produzido realmente entrou no depósito, e em quanto tempo.

**Ruptura por SKU.** Um SKU que desaparece do snapshot (saldo zero) é uma ruptura. Com o de-para, dá para saber se houve demanda programada para ele naquela semana — o que separa "acabou porque vendeu" de "acabou porque não produziu".

### 6.3 Possíveis com dado novo

**Valor financeiro do estoque e da perda.** Exige uma coluna de custo por quilo na dimensão de produto. Converte todos os indicadores de risco em reais.

**Giro de estoque contábil.** Exige o custo e o consumo do período. É o indicador clássico que a diretoria costuma pedir.

**FEFO — aderência à ordem de saída por validade.** Comparando, entre dois snapshots, qual lote saiu contra qual lote deveria ter saído primeiro pela validade, dá para medir se a expedição respeita FEFO. Esse cálculo é possível com os dados atuais, mas o resultado só é confiável com snapshots diários sem buracos.

---

## 7. Otimizações por painel

### Estoque 006

O painel é o mais completo, mas hoje ele responde "quanto tem" e para por aí. As mudanças de maior retorno: substituir o card "Diferença diária" por **cobertura em dias** (mais acionável); adicionar barras de entrada/saída sob a linha de saldo; trocar o corte único de 50% de validade por uma **faixa etária com cores** e o total em quilos por faixa; separar saldo livre de reservado; e adicionar uma visão ABC. A tabela "Informações de produtos fabricados" tem hoje todos os lotes sem hierarquia — ganharia muito com agrupamento por SKU expansível, mostrando o total do SKU e os lotes só quando o usuário abre.

Uma observação de UX: o gráfico cascata por SKU foi um bom acerto, mas ele mostra o estoque de um instante. Para acompanhamento diário, o que falta é a **variação** — uma cascata do que entrou e saiu entre dois dias seria mais informativa que a foto do saldo.

### Aderência

O painel replica bem o Power BI, e é aí que está a limitação: ele replica em vez de melhorar. Com 29 semanas de histórico, faltam a série temporal completa com média móvel, o ranking de ofensores recorrentes, a separação entre desvio para cima e para baixo, e a contribuição em quilos por produto. O card "% Dentro da Meta" trata todos os produtos igualmente e deveria ter uma versão ponderada por volume. Os comentários, hoje relegados a uma aba, deveriam aparecer como marcador no gráfico da semana correspondente — é onde a informação explica o número.

### Estoque 022

Além da correção urgente da seção 4.1, o painel precisa de identidade própria. Ele foi construído como cópia do 006, mas a pergunta que ele responde é outra: não é "quanto tem", é "**há quanto tempo está parado e por quê**". Os cards deveriam ser tempo médio de retenção, lote mais antigo retido, quantidade retida por setor e percentual do estoque total em retenção. Uma coluna de "dias parado" na tabela, com destaque para o que passou do normal, resolveria a maior parte disso — e depende apenas de guardar histórico.

---

## 8. Otimizações técnicas e do site

### Peso e desempenho

O Plotly está duplicado: `docs/aderencia/vendor/plotly.min.js` e `docs/estoque-006/vendor/plotly.min.js` são **byte a byte idênticos, 4,85 MB cada**, somando 9,7 MB no repositório. Devem virar um único `docs/vendor/plotly.min.js` referenciado pelos dois. Além disso, o projeto usa apenas gráficos de linha, barra e cascata — a distribuição `plotly-basic` (cerca de metade do tamanho) atende, e um bundle customizado atenderia com menos ainda.

Existe um `docs/assets/logo-vicosa.jpg` de 916 KB que **não é referenciado por nenhuma página** (todas usam o `.png` de 23 KB). É peso morto no repositório e pode ser removido.

As páginas em si estão saudáveis: 514 KB e 499 KB brutas, que caem para 51 KB e 38 KB com a compressão que o GitHub Pages já aplica. Isso não é problema hoje, mas cresce linearmente com o histórico — quando o BD_006 tiver um ano de dias empilhados, o payload embutido no HTML vai incomodar. A solução, quando chegar a hora, é separar os dados em um `.json` carregado à parte (que o navegador cacheia entre visitas) em vez de embutir no HTML.

### Código

Os três templates duplicam os formatadores de número, o componente de multi-seleção, o sistema de ordenação de tabela e toda a barra lateral. Extrair isso para um `docs/vendor/vicosa-ui.js` compartilhado eliminaria cerca de um terço do código e acabaria com a necessidade de aplicar a mesma correção três vezes — como aconteceu na mudança de formato dos quilos.

Do lado Python, os três scripts repetem o carregamento de dimensões, os formatadores de data, o mapeamento de setor e a injeção no template. Um módulo `comum.py` resolve. E vale criar o `build_all.py` com o bloco de validações descrito em 4.3.

### Visual e experiência

O visual atual é limpo e legível, o que já é mais do que a maioria dos painéis internos consegue. As melhorias que mais mudariam a percepção, em ordem de impacto por esforço:

Um **cabeçalho de estado** em cada painel dizendo com clareza a qual data o dado se refere e há quanto tempo foi atualizado, com cor de alerta quando estiver velho. Isso é o que teria evitado o problema do 022 passar despercebido.

**Tema claro e escuro** com detecção da preferência do sistema. É barato de fazer porque as cores já estão em variáveis CSS.

**Micro-gráficos nas tabelas** (uma barra proporcional na célula de saldo, uma linha de tendência de 7 dias por SKU) dão muito mais leitura por centímetro de tela do que números puros.

**Exportação para Excel/CSV** direto da tabela filtrada. É o pedido que sempre aparece depois que o painel começa a ser usado de verdade, e é uma função de vinte linhas.

**Semáforo de validade com faixas coloridas** substituindo as três tabelas separadas por uma tabela única com filtro de faixa — menos rolagem, mesma informação.

Uma **página inicial que resuma** em vez de só listar os três painéis: quatro ou cinco números-chave (estoque total, cobertura média, material vencendo em 7 dias, aderência da última semana, quilos retidos na qualidade) com link para o painel correspondente. Hoje o índice é um menu; poderia ser o painel mais consultado do site.

---

## 9. Roteiro sugerido

**Primeiro — corrigir e proteger (esta semana).** Atualizar o BD_022 e validar o resultado; adicionar a checagem de data entre as bases no build; criar o `build_all.py` com o bloco de validações e o resumo impresso; ignorar `~$*.xlsx` no Git; fixar as versões no `requirements.txt`; unificar o Plotly e remover o JPG não usado.

**Segundo — destravar o crescimento (próximas duas semanas).** Criar a tabela de-para produto ligando os 49 nomes da aderência aos códigos SAP; começar a arquivar o BD_022 por data; automatizar a consolidação dos dias do BD_006 a partir de uma pasta de arquivos diários; extrair o código JS e Python compartilhado.

**Terceiro — entregar valor novo (mês seguinte).** Cobertura em dias e consumo diário no painel 006; faixa etária de validade com total em quilos; separação de saldo livre e reservado; tempo de liberação da qualidade no painel 022; série histórica completa e ranking de ofensores na Aderência; página inicial com resumo executivo.

**Quarto — quando houver dado de custo.** Valor do estoque, valor em risco de perda, giro contábil e aderência FEFO.

---

## 10. Avaliação final

O projeto está em um ponto melhor do que a maioria das iniciativas parecidas chega: existe, é usado, os números conferem com a fonte original e o custo de manutenção é próximo de zero. A arquitetura escolhida foi acertada e vai suportar tudo o que está proposto aqui sem precisar ser trocada.

O que separa o estado atual de um BI de verdade não é gráfico nem visual — é que hoje o site **reproduz** os dados e ainda não os **interpreta**. Ele diz que há 171.109,33 kg no depósito, mas não diz que isso dá cerca de 13 dias de cobertura na mediana, que 6 SKUs vão faltar em menos de dois dias, que 5.457,93 kg vencem em um mês, nem que 22,6% do que aparece como retido na qualidade já foi liberado há dois dias. Todos esses números foram calculados para esta análise a partir dos arquivos que já estão no repositório, sem nenhum dado novo.

A prioridade, na minha leitura, é essa: antes de novos painéis, extrair do que já existe. E antes de extrair, colocar as validações que impedem uma base desatualizada de virar um número errado publicado — porque o custo de um painel que erra em silêncio é maior que o benefício de um painel a mais.
