# Submissão — Guilherme Fraga — Challenge 003

## Sobre mim

- **Nome:** Guilherme Fraga
- **LinkedIn:** https://www.linkedin.com/in/guilherme-fraga-62006912a/
- **Challenge escolhido:** 003 — Lead Scorer (Vendas / RevOps)

---

## Executive Summary

Construí uma fila de atenção para o vendedor abrir na segunda de manhã: um app Streamlit que pontua os 2.089 deals abertos do CRM com três fatores explicados em português (idade em Engaging, encaixe vendedor × produto, valor do produto) e os separa em três categorias de ação — Agir, Engajar e Decidir. O achado principal não é o score: **1.291 dos 1.589 deals em Engaging (81%) estão além dos 138 dias, idade depois da qual nenhum deal do histórico fechou**, e 1.425 dos 2.089 abertos (68%) não têm conta preenchida — a lista de decisão do manager é maior que a fila de trabalho do vendedor. No backtest com 37 cortes semanais e população completa, o top 20% da fila se decide em 14 dias em 24,7% dos casos (mediana), 1,6× o acaso (15,6%) e ordenar por valor (15,9%) — mas empata com "mais novo primeiro" (24,4%), então **a fila não é vendida como previsão**: o sinal de tempo que ela tem é o que a data de engajamento já dá. O que a ferramenta entrega é o que "mais novo primeiro" não faz: tirar 1.291 deals da frente do vendedor, explicar cada deal, desempatar por valor e encaixe, e dar ao manager a visão do time.

---

## Solução

### Setup — 3 comandos, sem API key

```bash
cd submissions/guilherme-fraga/solution
pip install -r requirements.txt        # pandas, streamlit, pytest
streamlit run app.py                   # abre em http://localhost:8501
```

Extras: `python src/score_pipeline.py` gera `output/pipeline_scored.csv` (os 2.089 abertos pontuados); `pytest -q` roda os 36 testes; `python analysis/backtest.py` reproduz o backtest (~2 min). Nada usa rede nem a data de hoje: a referência é 2017-12-31, a última data do CRM.

### Abordagem

1. **Hipóteses antes dos dados.** Escrevi sete hipóteses e cinco suspeitas sobre os dados em [`process-log/01-hipoteses.md`](process-log/01-hipoteses.md) antes de abrir qualquer CSV, para o teste não virar confirmação.
2. **Auditoria.** [`02-auditoria-dados.md`](process-log/02-auditoria-dados.md): `GTXPro` ≠ `GTX Pro` (1.480 linhas que o join perderia), `technolgy` (12 contas), 68% dos abertos sem conta, `close_value` vazio em todo deal aberto, última data 2017-12-31, nenhum `close_date` antes de 2017-03-01.
3. **Teste das hipóteses** ([`03-teste-hipoteses.md`](process-log/03-teste-hipoteses.md)): win rate Won/(Won+Lost) por grupo, spread entre melhor e pior, tamanho de cada grupo. Quatro derrubadas (conta, setor, região/manager, conta que já comprou — esta última era artefato do `close_date`), uma não testável (todo deal fechado passou por Engaging), uma confirmada mas fraca (vendedor, 15,4 pp), e uma derrubada do jeito escrito mas confirmada no espírito (idade: nenhum deal fechou depois de 138 dias em Engaging; a mediana dos abertos era 165). Um check de ML com split temporal (AUC máximo 0,572; encaixe vendedor × produto 0,515 fora do período) mostrou que um modelo não faria melhor que uma heurística.
4. **Lógica escrita e aprovada antes de codar** ([`04-logica-do-score.md`](process-log/04-logica-do-score.md), [print da aprovação](process-log/screenshots/01-aprovacao-manual-logica-do-score.png)).
5. **Motor + testes de leakage** (`close_value`/`close_date` nunca entram como feature de deal aberto — três testes provam), **app**, **backtest**, **revisão externa** por outro modelo em sessão limpa ([`06-revisao-externa.md`](process-log/06-revisao-externa.md)), e quatro blocos de correção. 21 commits, um por etapa.

### Lógica do score (resumo — completa no [04](process-log/04-logica-do-score.md))

O score de 0 a 100 é **fila de atenção, não probabilidade de fechar** — o app diz isso na primeira linha.

```
score = (55 × F2 + 20 × F1 + 25 × F3) / 100     # Engaging até 138 dias
score = (20 × F1 + 25 × F3) / 45                 # Prospecting (sem data, sem F2)
Decidir (Engaging > 138 dias): sem score — decisão, não esforço
```

| Fator | O que é | Como vira 0–100 |
|---|---|---|
| **F2 · atenção pela idade** (peso 55) | Hazard por idade em Engaging: de cada dia vivido naquela faixa, quantos terminam em desfecho. Calibrado nos 5.739 fechados da coorte pós-2017-03-01 **mais 1.376 abertos como censurados** (sem eles, a última faixa satura em 100 por construção). | Degraus: **0–14 dias = 100** (3,18%/dia; 56% das perdas acontecem aqui) · 15–60 = 15 pela curva, **35 por piso de produto** · 61–90 = **48** · 91–138 = **38**. |
| **F1 · encaixe vendedor × produto** (peso 20) | Win rate do vendedor naquele produto, puxado para a média do vendedor (K2 = 50) e esta para a média geral (K1 = 50). Célula de 10 deals pesa 17%. | ±15 pp em torno da média geral (63,2%) cobrem 0–100; nos dados reais fica entre 8 e 85. |
| **F3 · valor em jogo** (peso 25) | Preço de tabela do produto (`close_value` de deal aberto é vazio). | Log: MG Special 0 → GTK 500 100; GTX Pro 72. |

Categorias mandam na ordem, o score desempata: **Agir** (Engaging ≤ 138 dias) → **Engajar** (Prospecting) → **Decidir** (Engaging > 138, ordenado por valor para o manager limpar os grandes primeiro). Na prática, dentro de Agir a janela crítica (≤ 14 dias) vem sempre primeiro e, fora dela, a ordem segue o preço em 91% dos pares; Engajar é uma lista de valor (92%) com o encaixe desempatando. Cada fator devolve uma frase com números calculados dos dados. "Base do histórico" (ampla / média / pequena) diz quantos deals fechados sustentam a frase do encaixe — não é confiança no score.

### Resultados / Findings

**Três deals reais, um de cada categoria** (de [`output/pipeline_scored.csv`](solution/output/pipeline_scored.csv)):

| | Agir — `NGTVHTFH` | Engajar — `NKFG3KKP` | Decidir — `125VIRMX` |
|---|---|---|---|
| Vendedor / produto | Boris Faz / GTX Pro | Versie Hillebrand / GTX Plus Pro | Elease Gluck / GTK 500 (conta Warephase) |
| Idade | 12 dias em Engaging — *janela crítica* | Prospecting, sem data | 377 dias em Engaging |
| **Score** | **86** (F2 100 · F1 66 · F3 72) | **70** (F1 65 · F3 74) | **—** |
| Frase da idade | "Há 12 dias em Engaging. 56% das perdas acontecem até o dia 14 — é agora que o seu esforço evita a perda." | "Sem data de engajamento: não há sinal de tempo. Score usa só encaixe e valor." | "Há 377 dias em Engaging. Nenhum deal do histórico fechou depois de 138 dias; 1291 abertos já passaram disso sem fechar. Não é esforço, é decisão: requalificar ou descartar." |
| Frase do encaixe | "Você fecha GTX Pro em 17 de 23 deals (74%) — bem acima da média geral (63%)." | "Você fecha GTX Plus Pro em 15 de 21 deals (71%) — acima da média geral (63%)." | "Seu histórico em GTK 500 é 7 de 12 (58%). Base pequena: o score usa 62% (puxado para a sua média de 63%)." |
| Frase do valor | "GTX Pro: USD 4.821 em jogo — 3º produto mais caro dos 7." | "GTX Plus Pro: USD 5.482 em jogo — 2º produto mais caro dos 7." | "GTK 500: USD 26.768 em jogo — o produto mais caro do catálogo." |

**O achado principal, para o manager** (na primeira tela do app, [print](process-log/screenshots/03-app-faixa-do-topo-e-achado-principal.png)):

| | |
|---|---|
| Agir (Engaging até 138 dias) | **298** |
| Engajar (Prospecting) | **500** |
| Decidir (Engaging há mais de 138 dias) | **1.291** — 81% do Engaging |
| Abertos sem conta no CRM | **1.425 de 2.089** — 68% |

A lista de decisão é maior que a fila de trabalho. Só 7 deals têm menos de 14 dias: o pipeline quase não tem deal novo. Isso é o retrato do snapshot de 31/12/2017, não um bug — e é o argumento mais forte da ferramenta para a Head de RevOps: antes de priorizar, limpar.

**Backtest** ([`05-backtest.md`](process-log/05-backtest.md)) — 37 cortes semanais; em cada um, calibra só com o que fechou antes, pontua todos os deals em Engaging naquele dia (inclusive os que nunca fecharam) e mede quantos do top 20% tiveram desfecho em 14 dias:

| Ordem | Mediana (min–máx) | Fila vence em |
|---|---|---|
| **Fila** | **24,7% (12–50)** | — |
| Mais novo primeiro (`engage_date` desc) | 24,4% (12–48) | 19 / 37 |
| Ordenar por valor | 15,9% (5–25) | 29 / 37 |
| Acaso | 15,6% (5–29) | 31 / 37 |

**O que é dado observado e o que é premissa:**

| Observado nos dados | Premissa (decisão de produto, não validada) |
|---|---|
| Nenhum deal fechou depois de 138 dias em Engaging; 1.291 abertos já passaram disso. | Que um deal além da parede merece decisão, não esforço. |
| 56% das perdas da coorte acontecem até o dia 14; o hazard de 0–14 é 3,18%/dia contra 0,46% em 15–60. | Que esforço nos primeiros 14 dias muda o desfecho (precisa de contrafactual). |
| Vendedor × produto ordena dentro do período (15,4–28,8 pp de spread) e quase não ordena fora dele (AUC 0,515). | Que vale manter o encaixe no número com peso 20, em vez de só na frase. |
| Preço do produto não prediz fechamento (4,8 pp entre produtos). | Que, a sinal igual, o deal maior vem antes (peso 25). |
| A curva dá 15 no vale (15–60 dias); é onde os fechados mais ganham (72,8% em 15–30 dias, 66,3% em 31–60, contra 53,5% em 0–7). | Piso de 35: a zona que mais ganha não fica no fundo da fila. |

### Recomendações

1. **Antes de priorizar, limpar:** os 1.291 deals além da parede precisam de decisão (requalificar ou descartar), pelo manager, ordenados por valor. A aba "Visão do manager" existe para isso.
2. **Preencher conta:** 68% dos abertos não têm `account`. Nenhum fator do score depende de conta (as hipóteses de conta caíram), mas o vendedor não sabe com quem está falando.
3. **Usar a fila como fila de atenção, não como previsão** — e medir o que a ferramenta muda de verdade só depois de instrumentar o esforço (contatos, reuniões), que o CRM não tem.
4. **Revisar os pesos com dados novos:** o backtest não distingue pesos entre 40 e 100 no F2; F1 e F3 não foram validados. São decisões de produto e estão marcadas como tal.

### Limitações

- **O backtest não valida a tese central.** Ele mostra que a curva de idade generaliza (1,6× o acaso), mas não que o esforço na janela crítica muda o desfecho — isso exige contrafactual. E a fila empata com "mais novo primeiro": o sinal de tempo é o da data de engajamento.
- **F1 e F3 não foram validados.** A métrica de 14 dias mede tempo e não consegue movê-los; o peso 20 do F1 fica só pelo AUC 0,515. Validar exigiria uma métrica de valor (por exemplo, valor ganho em 90 dias pelo top 20%) — não feita.
- **O dataset fecha em blocos.** Entre 02/07 e 15/07 fecharam 299 deals, 100% com ≤ 14 dias de idade; entre 02/10 e 15/10, 269, também 100%. Os cortes do backtest sobem e descem com esse calendário (amplitude 12–50%). É padrão do dataset (sintético), não do negócio.
- **Sem sinal de atividade.** O CRM não tem e-mails, reuniões, último contato. A idade é o único sinal de tempo.
- **Prospecting sem data.** 500 deals sem sinal de tempo: a lista é essencialmente por valor do produto, com o encaixe desempatando.
- **Snapshot estático e sem persistência.** Referência fixa em 2017-12-31; a coluna "decisão" na aba de Decidir vive só na sessão e não grava no CRM. Para escalar: conector com o CRM, recálculo agendado, histórico de scores, feedback do vendedor.
- **Os ~35 vendedores e 7 produtos** cabem em tabelas de contingência; com mais dimensões a suavização precisaria de outro desenho.

### Comparação com o baseline (IA sozinha, brief cru)

Rodei o enunciado do challenge sem nenhum contexto num `claude -p` em sessão limpa, sem os CSVs ([`baseline/prompt.md`](process-log/baseline/prompt.md), [`baseline/output.md`](process-log/baseline/output.md)), para medir o que a IA entrega sozinha. Não executei o código dele; a comparação é de desenho.

| | Baseline (brief cru) | Esta submissão |
|---|---|---|
| **O que fez** | Score = percentil de Chance × Ticket × Timing. Chance por taxas de produto, conta e vendedor com shrinkage (k = 20) em log-odds; timing por quantis do ciclo dos deals ganhos; app Streamlit, CLI, testes e backtest de AUC/Brier — tudo escrito de memória, sem rodar. | Hipóteses antes dos dados, auditoria, teste de cada hipótese, lógica aprovada antes de codar, motor com testes de leakage, backtest com população completa, revisão externa e correções registradas. |
| **Onde fez melhor** | **Ticket pela mediana do `close_value` dos deals ganhos do produto** — dinheiro real, não preço de tabela. Aqui usei o preço de tabela (F3), porque a regra de leakage tirou `close_value` de tudo; a mediana dos ganhos é calibração, não feature de deal aberto, e seria uma melhoria válida. Também escolheu "conta" como fator, que testei e caiu (1,9 pp de spread; "conta que já comprou" era artefato do `close_date`). | — |
| **O que fizemos a mais** | Timing comparava deals abertos com o ciclo dos ganhos "não é um modelo de sobrevivência", nas palavras dele — e é exatamente o erro que a revisão externa achou aqui (B1) e que corrigimos com censura e coorte. Score relativo (percentil) não separa "esforço" de "decisão". | A parede de 138 dias como categoria própria (1.291 deals), a curva de hazard com censura, três testes que provam que `close_value`/`close_date` não entram, um backtest que inclui quem nunca fechou e compara com o baseline trivial, e a decisão de não vender a fila como previsão. |

---

## Process Log — Como usei IA

> **Este bloco é obrigatório.** Sem ele, a submissão é desclassificada.

### Ferramentas usadas

| Ferramenta | Para que usou |
|------------|--------------|
| Claude Code (Opus 5) | Toda a construção: auditoria, teste de hipóteses, motor, app, backtest, documentação — sob aprovação manual de cada edição e um commit por etapa. |
| Claude Fable 5.1 (`claude-fable-5-1`), sessão limpa | Revisor externo: tentou derrubar o score e o backtest sem contato com a sessão que construiu ([`06-revisao-externa.md`](process-log/06-revisao-externa.md), [print](process-log/screenshots/05-revisao-externa-fable-crivo.png)). Achou três bloqueadores, todos aceitos. |
| `claude -p` (brief cru, sem CSVs) | Baseline do que a IA entrega sozinha ([`baseline/`](process-log/baseline/)). |
| Python: pandas, Streamlit, pytest; scikit-learn só na análise | Motor, app, 36 testes, check de ML. |

### Workflow

1. Registrei sete hipóteses e cinco suspeitas sobre os dados **antes** de a IA abrir qualquer CSV ([01](process-log/01-hipoteses.md)).
2. A IA auditou as suspeitas — só números, sem interpretar ([02](process-log/02-auditoria-dados.md)). Decidi as correções de dados, a data de referência (2017-12-31, nunca a de hoje) e que `close_value`/`close_date` não entram como feature de deal aberto.
3. A IA testou as sete hipóteses com win rate, spread e tamanho de grupo; eu dei o veredito de cada uma ([03](process-log/03-teste-hipoteses.md)). Pedi produto × vendedor e a curva acumulada, que não estavam na lista original.
4. Pedi um check de ML (regressão logística, split temporal) antes de gastar tempo com heurística: AUC 0,572, encaixe 0,515 fora do período ([03-D](process-log/03-teste-hipoteses.md), [print](process-log/screenshots/02-check-ml-f1-nao-generaliza.png)).
5. A IA propôs a lógica do score; corrigi três pontos (o F2 media probabilidade, não atenção; K2; ordem de Decidir) e aprovei manualmente ([04](process-log/04-logica-do-score.md), [print](process-log/screenshots/01-aprovacao-manual-logica-do-score.png)).
6. Motor com três testes de leakage e invariantes; conferi o topo da fila e as categorias na mão. App em Streamlit; pedi o filtro de produto, o buraco de conta agregado, o desempate por janela crítica e os degraus em texto ([prints 03 e 04](process-log/screenshots/)).
7. Backtest v1 com três cortes; a IA mediu win rate — corrigi: a métrica de uma fila é "desfecho em 14 dias". Decidi vale 35 e pesos 55/20/25 por produto, já que os números não distinguiam.
8. Revisão externa em sessão limpa ([06](process-log/06-revisao-externa.md)): três bloqueadores (braço direito da curva era artefato de censura; backtest só avaliava sobreviventes; baseline errado), quatro importantes, sete detalhes. Aceitei todos; a IA corrigiu em quatro blocos, um commit cada, e respondeu ponto a ponto no próprio documento.
9. Backtest v2 com população completa e cortes semanais ([05](process-log/05-backtest.md)): a fila empata com "mais novo primeiro". Decidi não vendê-la como previsão e escrevi o que ela entrega.

### Onde a IA errou e como corrigi

Sete correções registradas com causa raiz em [`erros-e-correcoes.md`](process-log/erros-e-correcoes.md). As que mudaram o produto:

- **#1** — o F2 media "onde é mais provável ganhar" quando o objetivo era "onde o meu tempo faz diferença"; a IA viu a contradição e a tratou como detalhe de interface (um marcador) em vez de erro de modelagem.
- **#2** — propôs K2 = 30 sabendo que uma célula de 14 deals zerava o fator, contra o critério que eu tinha dado.
- **#5** — mediu o backtest por "quantos ganharam" numa fila que promete "onde a decisão está acontecendo": repetiu o erro #1 um nível acima.
- **#6** — o braço direito do U era artefato: a curva contava como vivos só quem fechou. A tautologia passou porque confirmava a hipótese. Achado pelo revisor externo, não por mim nem pela IA que construiu.
- **#7** — o backtest v1 avaliava só sobreviventes contra um baseline que não compete ("valor"); o resultado da v1 virou empate com "mais novo primeiro".

Mais dois de processo: `git add -f` em diretório arrastou `__pycache__` (#4), e Decidir sem ordem definida (#3).

### O que eu adicionei que a IA sozinha não faria

- **Hipóteses antes dos dados** e a regra de que nenhum número aparece antes delas.
- **"Fila de atenção, não probabilidade"** — a definição que separa este score de um modelo de win rate, e que a IA violou duas vezes (#1 e #5) até a definição virar a métrica do backtest.
- **Decisões de produto explícitas e marcadas como não validadas:** vale 35, pesos 55/20/25, parede como categoria própria, Decidir ordenado por valor para o manager.
- **A revisão externa** por outro modelo em sessão limpa, e a decisão de aceitar os três bloqueadores mesmo derrubando o resultado mais bonito da submissão.
- **A framing final:** não vender a fila como previsão; o valor está em Decidir, nas frases, no desempate e na visão do manager. O baseline sem contexto não faria nenhuma dessas quatro coisas.

---

## Evidências

- [x] Screenshots — [`process-log/screenshots/`](process-log/screenshots/): [01 aprovação manual da lógica](process-log/screenshots/01-aprovacao-manual-logica-do-score.png) · [02 check de ML](process-log/screenshots/02-check-ml-f1-nao-generaliza.png) · [03 app, faixa do topo](process-log/screenshots/03-app-faixa-do-topo-e-achado-principal.png) · [04 app, fila do vendedor](process-log/screenshots/04-app-fila-do-vendedor-cartoes.png) · [05 revisão externa](process-log/screenshots/05-revisao-externa-fable-crivo.png)
- [ ] Screen recording — não
- [ ] Chat exports — não; a narrativa está nos documentos abaixo
- [x] Git history — 21 commits em `submissions/guilherme-fraga/`, um por etapa, com `Co-Authored-By: Claude`
- [x] Narrativa escrita — [`01-hipoteses.md`](process-log/01-hipoteses.md) · [`02-auditoria-dados.md`](process-log/02-auditoria-dados.md) · [`03-teste-hipoteses.md`](process-log/03-teste-hipoteses.md) · [`04-logica-do-score.md`](process-log/04-logica-do-score.md) · [`05-backtest.md`](process-log/05-backtest.md) · [`06-revisao-externa.md`](process-log/06-revisao-externa.md) · [`erros-e-correcoes.md`](process-log/erros-e-correcoes.md) · [`baseline/`](process-log/baseline/)
- [x] Código — [`solution/`](solution/) (README de setup e estrutura em [`solution/README.md`](solution/README.md)); análises reproduzíveis em [`solution/analysis/`](solution/analysis/)

---

_Submissão enviada em: 2026-09-16_
