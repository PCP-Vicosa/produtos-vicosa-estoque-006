# Plano de ação — Viçosa BI

Derivado do documento `ANALISE_PROJETO.md`. Horizonte definido pelo usuário: **hoje**.
Por isso o plano está organizado em duas partes: o que já foi **executado hoje** (Fase 1
completa) e o que fica **pronto para executar**, cada item com critério de aceite
objetivo, para que a execução não dependa de interpretação.

Data: 27/07/2026

---

## Parte I — Executado hoje (Fase 1: corrigir e proteger)

### 1.1 Correção da contagem em duplicidade no Estoque 022 — CONCLUÍDO

Era o achado crítico da análise (§4.1): o painel exibia 38.746,06 kg de material que
já havia sido liberado e já constava no Depósito 006, porque o `BD_022.xlsx` era de
25/07 enquanto o `BD_006.xlsx` já estava em 27/07. Isso representava 70,1% do total
mostrado no painel e uma dupla contagem de 22,6% do estoque do 006.

O que foi feito: a função `conferir_contra_006` foi adicionada ao
`scripts/build_estoque_022.py`. Ela lê o último snapshot do BD_006, remove do painel
todo lote que já apareça lá e calcula a defasagem de datas entre as duas bases. O
resultado da conferência viaja no payload e é renderizado como uma faixa de alerta no
topo da página, em amarelo para um dia de defasagem e vermelho acima disso.

*Critério de aceite (atendido):* o build imprime `33 lote(s) do BD_022 já constam no
Depósito 006 de 27/07/2026 (38.746,06 kg)` e a página passa a mostrar 14 lotes em vez
de 47, com o alerta visível.

### 1.2 Camada de validação das bases — CONCLUÍDO

A crítica central da §5 era que toda correção do projeto foi reativa: o erro chegava ao
usuário como "o site está errado" em vez de o build se recusar a publicar. O novo
`scripts/validacoes.py` inverte isso. Ele classifica cada achado em **ERRO** (impede a
publicação) ou **AVISO** (publica, mas imprime em destaque).

Verificações implementadas — BD_006: arquivo existe e não está vazio, colunas
obrigatórias presentes, nenhuma Data Estoque nula, Saldo Lote numérico, nenhuma
validade anterior à fabricação, nenhuma duplicidade de data+lote+produto, todo SKU com
gramatura cadastrada (ERRO, porque sem ela o produto viraria 0 kg em silêncio) e com
nome curto (AVISO), variação de saldo diária acima de 40% e snapshot com mais de um dia
de atraso. BD_022: leitura pelo carregador robusto, defasagem contra o 006, contagem de
lotes sobrepostos. Aderência: colunas cruas presentes, valores faltantes, gramatura zero
ou negativa (ERRO), Data Início Semana ausente e última semana com mais de 14 dias.

*Critério de aceite (atendido):* `python scripts/validacoes.py` roda sobre as bases
reais e devolve 0 erros e 3 avisos, todos verdadeiros.

### 1.3 Build único com resumo — CONCLUÍDO

O `scripts/build_all.py` passa a ser o ponto único de geração: valida, aborta se houver
ERRO, gera os três painéis em sequência e imprime um resumo do que foi publicado.
Existe a saída de emergência `--ignorar-erros` para o caso de precisar publicar com uma
base sabidamente imperfeita.

*Critério de aceite (atendido):* um único comando gera tudo e encerra com

```
Estoque 006  : 9 dia(s) de historico | ultimo snapshot 27/07/2026
               170 lotes | 44 SKUs | 171.109,33 kg | variacao vs. dia anterior: +23.7%
```

### 1.4 Higiene do repositório — CONCLUÍDO

O `.gitignore` passou a ignorar os arquivos de bloqueio `~$*.xlsx` que o Excel cria com
a planilha aberta e que vinham sujando os commits. O `requirements.txt` deixou de ser
uma lista solta e passou a ter limites de versão (`pandas>=2.2,<4.0`,
`openpyxl>=3.1,<4.0`), largos o bastante para funcionar na máquina do usuário e
estreitos o bastante para que uma atualização não mude o comportamento de leitura do
Excel sem aviso.

### 1.5 Unificação do Plotly e remoção de peso morto — CONCLUÍDO

As duas cópias byte a byte idênticas do Plotly (4,85 MB cada) viraram um único
`docs/vendor/plotly.min.js`, e as quatro páginas e templates passaram a apontar para
`../vendor/plotly.min.js`. O `docs/assets/logo-vicosa.jpg` de 916 KB, que nenhuma página
referenciava, foi removido.

*Critério de aceite (atendido):* a pasta `docs/` caiu de aproximadamente 11,5 MB para
5,8 MB e nenhuma página perdeu gráfico — os três painéis foram regerados e carregam.

---

## Parte II — Pronto para executar

### Fase 2 — Destravar o crescimento

**2.1 Tabela de-para produto.** É o bloqueio estrutural da §3.4: apenas 3 dos 49 nomes
de produto da base de aderência batem com os do estoque, o que impede qualquer indicador
que cruze os dois domínios. A ação é criar `data/Dim_DePara_Produto.csv` ligando cada
nome da aderência ao código SAP correspondente. É trabalho manual de cadastro, não de
programação, e precisa do conhecimento do PCP.
*Aceite:* os 49 nomes mapeados, e uma verificação no `validacoes.py` que acusa ERRO
quando um nome novo aparecer sem mapeamento.

**2.2 Arquivar o BD_022 por data.** Hoje o arquivo é sobrescrito, o que joga fora o
histórico. Passar a salvar como `data/estoque-022/historico/BD_022_AAAA-MM-DD.xlsx` a
cada extração. Sem custo hoje, e é o que habilita o indicador mais valioso do painel 022.
*Aceite:* a pasta de histórico acumulando um arquivo por dia útil.

**2.3 Automatizar a consolidação do BD_006.** Em vez de consolidar manualmente, um
script que lê uma pasta de extrações diárias e monta a base empilhada, detectando dias
faltantes (hoje faltam os dias 16, 17, 18, 19 e 26).
*Aceite:* rodar o script sobre a pasta reproduz a base atual e lista os dias ausentes.

**2.4 Extrair código compartilhado.** Um `docs/vendor/vicosa-ui.js` com os formatadores,
a multi-seleção, a ordenação de tabela e a barra lateral hoje triplicados nos templates;
e um `scripts/comum.py` com o carregamento de dimensões, os formatadores de data, o
mapeamento de setor e a injeção no template.
*Aceite:* os três painéis geram saída idêntica à atual com cerca de um terço menos de
código, e uma mudança de formatação passa a ser feita em um só lugar.

### Fase 3 — Entregar valor novo

**3.1 Cobertura em dias no painel 006.** Substituir o card "Diferença diária" por
cobertura, com a metodologia da §6.1 fixada no código (consumo = soma das reduções de
saldo por lote entre snapshots consecutivos ÷ dias corridos do período). Hoje a mediana
é de 13,2 dias, com 6 SKUs abaixo de 2 dias.
*Aceite:* o card aparece, e um comentário no código documenta a fórmula escolhida.

**3.2 Faixa etária de validade.** Trocar o corte único de 50% por cinco faixas de vida
útil consumida (0–25, 25–50, 50–75, 75–100, vencido) com cores e total em quilos por
faixa, padronizando a leitura em toda a interface para evitar a inversão apontada na
§6.1.
*Aceite:* a soma dos quilos das faixas bate com o saldo total do dia.

**3.3 Saldo livre versus reservado.** Desdobrar o card de saldo usando
`Qtd. Reservada`.

**3.4 Tempo de liberação da qualidade.** Depende de 2.2. Cruzando o dia em que o lote
aparece no 022 com o dia em que aparece no 006, sai o lead time por setor e produto —
o KPI que justifica o painel 022 existir.

**3.5 Aderência: série histórica e ofensores.** Usar as 29 semanas disponíveis para
série com média móvel, ranking de produtos recorrentemente fora da faixa de 95–105%,
separação entre desvio para cima e para baixo, e contribuição em quilos por produto.

**3.6 Página inicial com resumo.** Trocar o menu por cinco números-chave com link para
o painel correspondente: estoque total, cobertura mediana, material vencendo em 7 dias
(hoje 1.654,40 kg), aderência da última semana e quilos retidos na qualidade.

**3.7 Exportação para CSV** da tabela filtrada e **cabeçalho de estado** com a data do
dado e cor de alerta quando estiver velho.

### Fase 4 — Quando houver custo por quilo

Adicionar a coluna de custo à dimensão de produto habilita, sem trabalho adicional de
coleta, o valor financeiro do estoque, o valor em risco de perda, o giro contábil e a
aderência FEFO.

---

## Ordem recomendada e dependências

A Fase 1 está fechada. A Fase 2 não depende de nada além de decisão e cadastro, e o item
2.2 deveria começar hoje mesmo, porque cada dia sem arquivar é um dia de histórico
perdido para sempre. Os itens 3.1, 3.2, 3.3, 3.5, 3.6 e 3.7 são independentes entre si e
podem ser feitos em qualquer ordem; o 3.4 espera o 2.2 acumular pelo menos duas semanas.
A Fase 4 espera apenas o dado de custo.

## Ação imediata do usuário

Exportar o `BD_022.xlsx` novamente com a data de hoje — o alerta agora protege contra a
duplicidade, mas o painel só volta a mostrar a realidade da qualidade com a base atual.
E publicar o que foi feito hoje, no VS Code:

```
git add . && git commit -m "fase 1: validacoes, build unico, correcao 022 e limpeza" && git push
```
