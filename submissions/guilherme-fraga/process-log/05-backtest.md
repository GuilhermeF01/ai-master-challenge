# Backtest da fila — v2, depois da revisão externa

> Script: [`solution/analysis/backtest.py`](../solution/analysis/backtest.py) (só pandas; usa o motor real do app, ~2 min).
> **v1** (três cortes à mão, só deals que depois fecharam, baseline "valor") dizia "a fila faz o dobro". A [revisão externa](06-revisao-externa.md) derrubou os três pilares (B2, B3, I1). Esta v2 refaz com população completa, cortes semanais e o baseline que importa. A v1 está no histórico do git; os números dela aparecem aqui só para comparação.

## Método (v2)

Para cada corte semanal T — 37 cortes, de 2017-04-03 a 2017-12-11 (a janela de 14 dias precisa caber antes de 31/12):

1. Calibra o score **só com o que fechou antes de T**. Os deals abertos em T entram na curva do F2 como censurados (não se olha o futuro deles).
2. População = **todos** os deals em Engaging em T: engajados até T e que fecharam depois de T **ou nunca fecharam até 31/12**. Na v1 só entrava quem depois fechou — e isso escondia exatamente os deals que a fila mandou agir e nunca se decidiram (mediana de 45% da população por corte).
3. Aplica o score com `reference_date = T` — mesmo `score_open_deals` do app, mesma ordem.
4. Métrica: dos **top 20%** de Agir, quantos tiveram **desfecho (ganho ou perda) até T + 14 dias**. Quem nunca fechou conta zero.
5. Baselines: **mais novo primeiro** (`engage_date` desc — o que o vendedor faz no CRM sem ferramenta nenhuma), **F2 sozinho**, **ordenar por valor** (empates entre os 7 preços resolvidos de forma esperada), e a **média do grupo** (acaso).
6. Resumo por **mediana e amplitude** nos 37 cortes, e contagem de cortes em que a fila vence cada baseline.

## Resultado principal

| Ordem | Top 20% com desfecho em 14 dias — mediana (min–máx) | Fila vence em |
|---|---|---|
| **Fila (motor atual: 55 / 20 / 25, curva com censura, vale 35)** | **24,7% (12–50)** | — |
| Mais novo primeiro (`engage_date` desc) | 24,4% (12–48) | 19 / 37 |
| F2 sozinho | 22,9% (12–58) | 11 / 37 |
| Ordenar por valor | 15,9% (5–25) | 29 / 37 |
| Média do grupo (acaso) | 15,6% (5–29) | 31 / 37 |

População de Agir por corte: mediana 1.603 deals (999–2.016); deles, nunca fecharam até 31/12: mediana 793 (45%). Composição do top 20% da fila: mediana de 83% em 0–14 dias e 9% em 91–138.

**Leitura:** a fila acha onde a decisão está acontecendo em ~1,6× o acaso e ~1,6× ordenar por valor, e isso segura em 29–31 dos 37 cortes. Mas **não faz melhor que "mais novo primeiro"** — empata (19 / 37, mediana 24,7% vs 24,4%). O que a fila sabe sobre *tempo* é o que a data de engajamento já diz; F1 e F3 não são sinais de tempo e não conseguem mover esta métrica (ver grade abaixo).

<details>
<summary>Por corte (37 linhas)</summary>

| T | Agir em T | Nunca fecharam | Fila | Mais novo | F2 só | Valor | Grupo | Top 20% em 0–14 | em 91–138 |
|---|---|---|---|---|---|---|---|---|---|
| 2017-04-03 | 1365 | 365 | 37% | 44% | 37% | 10% | 9% | 100% | 0% |
| 2017-04-10 | 1453 | 387 | 36% | 42% | 39% | 7% | 8% | 100% | 0% |
| 2017-04-17 | 1521 | 407 | 40% | 40% | 40% | 8% | 9% | 99% | 0% |
| 2017-04-24 | 1587 | 434 | 37% | 36% | 37% | 15% | 16% | 87% | 0% |
| 2017-05-01 | 1597 | 455 | 22% | 19% | 23% | 20% | 20% | 75% | 0% |
| 2017-05-08 | 1555 | 466 | 24% | 22% | 25% | 25% | 21% | 82% | 0% |
| 2017-05-15 | 1556 | 487 | 24% | 24% | 23% | 25% | 23% | 100% | 0% |
| 2017-05-22 | 1507 | 510 | 19% | 20% | 19% | 22% | 22% | 100% | 0% |
| 2017-05-29 | 1468 | 525 | 16% | 16% | 15% | 19% | 20% | 98% | 0% |
| 2017-06-05 | 1467 | 525 | 16% | 17% | 15% | 17% | 18% | 82% | 18% |
| 2017-06-12 | 1468 | 541 | 20% | 15% | 20% | 16% | 17% | 56% | 44% |
| 2017-06-19 | 1485 | 560 | 25% | 21% | 23% | 16% | 16% | 59% | 41% |
| 2017-06-26 | 1506 | 568 | 24% | 31% | 22% | 12% | 11% | 61% | 38% |
| 2017-07-03 | 1559 | 572 | 25% | 42% | 23% | 9% | 8% | 67% | 33% |
| 2017-07-10 | 1603 | 572 | 32% | 38% | 38% | 8% | 8% | 83% | 17% |
| 2017-07-17 | 1635 | 562 | 31% | 31% | 31% | 7% | 6% | 84% | 9% |
| 2017-07-24 | 1850 | 683 | 32% | 34% | 31% | 15% | 15% | 100% | 0% |
| 2017-07-31 | 1982 | 843 | 12% | 13% | 13% | 17% | 17% | 100% | 0% |
| 2017-08-07 | 1954 | 909 | 12% | 14% | 12% | 16% | 16% | 100% | 0% |
| 2017-08-14 | 1930 | 953 | 12% | 12% | 12% | 17% | 16% | 99% | 1% |
| 2017-08-21 | 1879 | 953 | 18% | 16% | 18% | 16% | 16% | 88% | 6% |
| 2017-08-28 | 1843 | 961 | 17% | 16% | 20% | 14% | 14% | 83% | 8% |
| 2017-09-04 | 1855 | 960 | 19% | 18% | 20% | 17% | 15% | 92% | 5% |
| 2017-09-11 | 1869 | 964 | 17% | 17% | 18% | 15% | 15% | 93% | 5% |
| 2017-09-18 | 1849 | 958 | 14% | 13% | 14% | 13% | 12% | 90% | 6% |
| 2017-09-25 | 1865 | 950 | 19% | 21% | 20% | 10% | 8% | 84% | 11% |
| 2017-10-02 | 1913 | 940 | 31% | 35% | 35% | 7% | 7% | 84% | 12% |
| 2017-10-09 | 1929 | 922 | 26% | 26% | 26% | 5% | 5% | 73% | 20% |
| 2017-10-16 | 1963 | 903 | 26% | 26% | 26% | 5% | 5% | 65% | 21% |
| 2017-10-23 | 2016 | 899 | 35% | 34% | 34% | 15% | 12% | 62% | 30% |
| 2017-10-30 | 1949 | 880 | 23% | 22% | 20% | 17% | 15% | 37% | 46% |
| 2017-11-06 | 1827 | 864 | 26% | 20% | 21% | 19% | 17% | 34% | 36% |
| 2017-11-13 | 1705 | 848 | 28% | 25% | 21% | 21% | 19% | 34% | 29% |
| 2017-11-20 | 1572 | 829 | 33% | 32% | 42% | 21% | 21% | 34% | 23% |
| 2017-11-27 | 1419 | 809 | 36% | 35% | 41% | 22% | 20% | 32% | 19% |
| 2017-12-04 | 1277 | 793 | 40% | 37% | 47% | 20% | 21% | 31% | 19% |
| 2017-12-11 | 999 | 612 | 50% | 48% | 58% | 23% | 29% | 36% | 16% |

</details>

## Os três cortes da v1, refeitos com a população completa

| T | Fila (v1, só quem fechou) | Fila agora | Mais novo | Valor | Grupo |
|---|---|---|---|---|---|
| 2017-07-01 | 46,7% | 27,0% | 47,9% | 10,3% | 9,7% |
| 2017-08-15 | 37,6% | 13,4% | 13,4% | 17,6% | 16,3% |
| 2017-10-01 | 40,3% | 28,7% | 33,2% | 6,8% | 6,6% |

O "41,5% vs 21,7%, o dobro" da v1 era sobrevivência: os deals que a fila mandou agir e que nunca se decidiram estavam fora da conta. Com eles, 07-01 cai de 46,7% para 27,0% — e "mais novo primeiro" faz 47,9% no mesmo corte.

## Configuração antiga vs atual, mesmos 37 cortes

| Configuração | Fila: mediana (min–máx) | Vitórias sobre mais novo primeiro |
|---|---|---|
| antiga 40 / 35 / 25, vale da curva | 23,5% (12–44) | 16 / 37 |
| atual 55 / 20 / 25, vale com piso 35 | 24,7% (12–50) | 19 / 37 |

As duas rodam na curva com censura do B1; a curva antiga sem censura (braço direito em 100) não existe mais no motor. Diferença de 1,2 pp na mediana, 3 cortes a mais — dentro do ruído.

## O que a métrica de 14 dias não mede

A métrica é de **tempo**: "vai se decidir nos próximos 14 dias?". F1 (encaixe vendedor × produto) e F3 (preço do produto) não são sinais de tempo e, por desenho, não conseguem movê-la. A grade abaixo existe só para deixar isso visível:

| Pesos F2 / F1 / F3 | Fila: mediana (min–máx) | Vitórias sobre mais novo |
|---|---|---|
| 55 / 20 / 25 (atual) | 24,7% (12–50) | 19 / 37 |
| 40 / 35 / 25 | 23,2% (12–45) | 17 / 37 |
| 75 / 0 / 25 | 24,8% (12–56) | 16 / 37 |
| 100 / 0 / 0 | 23,2% (12–58) | 14 / 37 |
| 0 / 50 / 50 | 15,3% (4–28) | 8 / 37 |

Tirar o F2 (0 / 50 / 50) leva a fila ao nível do acaso; mexer entre 40 e 100 no F2 não muda nada fora do ruído. **Logo: o peso 20 do F1 não é sustentado por este backtest — ele fica só pelo AUC 0,515 do [03-D](03-teste-hipoteses.md) (encaixe calibrado num período quase não ordena o seguinte).** "As duas rodadas dizem a mesma coisa", escrito na v1, era falso: a segunda rodada não conseguia dizer nada sobre o F1. Validar F1 e F3 exigiria uma métrica que eles possam mover (por exemplo, valor ganho em 90 dias pelo top 20%); fica como trabalho não feito.

## Estrutura de calendário (I1)

Os fechamentos vêm em blocos: entre 02/07 e 15/07 fecharam 299 deals, 100% com ≤ 14 dias de idade; entre 02/10 e 15/10, 269, também 100%. As coortes engajadas em abril, julho e outubro são majoritariamente curtas (~500 deals em 0–14 contra ~100 nas outras faixas). Isso explica os picos da tabela por corte (abril, julho, outubro, dezembro) e o vale de agosto–setembro: são semanas em que **só deal novo fecha**, e qualquer regra "novo primeiro" acerta. O corte de 15/08 "que fugia do padrão" na v1 era isso. O padrão é do dataset (sintético), não do negócio — e os cortes se sobrepõem (o mesmo deal aparece em vários), então a amplitude é mais informativa que qualquer média.

## O que sobra de evidência

1. **O F2 (curva de hazard com censura) generaliza fora do período:** o top 20% da fila se decide em 14 dias ~1,6× mais que o acaso, em 31 dos 37 cortes. A premissa "quem perde, perde cedo" segura.
2. **Mas "mais novo primeiro" faz o mesmo.** O sinal de tempo que a fila tem é o que a data de engajamento já dá. A fila não acrescenta poder de previsão de *quando* sobre isso.
3. **O que a ferramenta acrescenta e a métrica não mede:** a parede (1.291 deals em Decidir, que "mais novo primeiro" deixa no fundo da lista para sempre), as frases (por que este deal), o desempate por valor e encaixe dentro da mesma zona, e a visão do manager. Nada disso está validado por número.
4. **Ordenar por valor** é indistinguível do acaso para esta métrica (15,9% vs 15,6%).

## Ressalvas do método

- Censura à direita perto do fim: cortes de dezembro têm população menor (999 em 11/12) e a janela de 14 dias encosta em 31/12.
- Idade em T é idade parcial — é o que o app vê, ao contrário do check de ML.
- Empates no score seguem o app (janela crítica primeiro, depois `opportunity_id`).
- A métrica é binária e não pesa valor; F1 e F3 ficam sem validação.

## Decisão

1. **A fila não é previsão, e não vai ser vendida como previsão.** Empata com "mais novo primeiro" (24,7% vs 24,4%, vence em 19 de 37 cortes) e faz ~1,6× o acaso. A verdade é essa: o sinal de tempo que a fila tem é o que a data de engajamento já dá. O README diz isso com esses números — e não usa "o dobro" em lugar nenhum.
2. **O que a ferramenta entrega é o que "mais novo primeiro" não faz:**
   - tira os **1.291 deals além da parede** da frente do vendedor e os põe numa lista de decisão, ordenada por valor, para o manager;
   - **explica cada deal** com três frases calculadas dos dados (idade, encaixe, valor);
   - **desempata por valor e encaixe** dentro da mesma zona de idade;
   - dá ao manager a **visão do time** com o buraco de conta (1.425 de 2.089 abertos sem conta) na cara.
3. **Pesos e degraus ficam como estão** (55 / 20 / 25; curva com censura 100 / 15 → piso 35 / 48 / 38): o backtest não distingue pesos entre 40 e 100 no F2, e F1/F3 seguem sem validação (o 20 do F1 fica só pelo AUC 0,515). São decisões de produto, marcadas como tal no [04](04-logica-do-score.md).
4. **Fica registrado como não validado:** que o esforço na janela crítica muda o desfecho (precisa de contrafactual); que F1 e F3 melhoram alguma coisa (precisa de métrica de valor); e que o padrão de fechamento em blocos existe fora deste dataset.
