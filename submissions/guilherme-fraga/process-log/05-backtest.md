# Backtest da fila — o vale do F2 e o peso do F1, com número

> Script: [`solution/analysis/backtest.py`](../solution/analysis/backtest.py) (só pandas; usa o motor real do app).
> Duas dúvidas deixadas em aberto no [04](04-logica-do-score.md): o vale do F2 em 20 e o peso 35 do F1 depois do AUC 0,515 fora do período ([03, seção D](03-teste-hipoteses.md#d--check-de-ml-um-modelo-faria-melhor-que-a-heurística)).
> **Nenhum peso foi alterado.** Este documento é a tabela; a decisão é registrada depois.

## Método

Para cada data de corte T ("finge que é hoje"):

1. Calibra o score **só com o que fechou antes de T** (`calibrate` no subconjunto).
2. Pega os deals que **estavam em Engaging em T** (`engage_date ≤ T < close_date`) **e que depois fecharam** — o desfecho é conhecido.
3. Aplica o score com `reference_date = T` — mesmo `score_open_deals` do app, mesma ordem, mesmo desempate.
4. Dos **top 20%** que a fila mandou agir, quantos ganharam — contra **ordenar por valor** (preço do produto; empates entre os 7 preços resolvidos de forma esperada) e contra a **média do grupo**.

Grade: vale do F2 (zona 15–60) em {20, 35, 50} × peso do F1 em {35, 20, 0}, o que sai do F1 vai para o F2, F3 fixo em 25. Três cortes em vez de dois, para não decidir em cima de um só.

| T (finge que é hoje) | Fechados antes de T (calibração) | Engaging em T que fecharam depois | Top 20% (k) | Win rate do grupo | Top 20% por valor |
|---|---|---|---|---|---|
| 2017-07-01 | 2.679 | 983 | 197 | 62,8% | 63,8% |
| 2017-08-15 | 3.684 | 983 | 197 | 67,1% | 70,2% |
| 2017-10-01 | 4.726 | 955 | 191 | 59,5% | 60,1% |

A parede é 138 em todos os cortes (o deal de 138 dias fechou antes de maio), então nenhum deal de avaliação cai em Decidir — o teste mede só a fila de Agir.

Ruído: com k ≈ 195 por corte, o erro-padrão de uma win rate é ≈ 3,5 pp por corte e ≈ 2 pp na média dos três. **Diferenças de 1 pp são ruído. Diferenças de 5 pp não são.**

## Grade — win rate dos top 20% mandados a agir

| Vale (15–60) | Pesos F2 / F1 / F3 | T=2017-07-01 | T=2017-08-15 | T=2017-10-01 | Média | vs grupo | vs valor |
|---|---|---|---|---|---|---|---|
| 20 | 40 / 35 / 25 **← atual** | 58,9% | 59,9% | 53,4% | **57,4%** | −5,7 pp | −7,3 pp |
| 20 | 55 / 20 / 25 | 58,9% | 59,9% | 55,0% | **57,9%** | −5,2 pp | −6,8 pp |
| 20 | 75 / 0 / 25 | 59,9% | 59,4% | 56,0% | **58,4%** | −4,7 pp | −6,3 pp |
| 35 | 40 / 35 / 25 | 58,9% | 59,9% | 53,4% | **57,4%** | −5,7 pp | −7,3 pp |
| 35 | 55 / 20 / 25 | 58,9% | 59,9% | 55,0% | **57,9%** | −5,2 pp | −6,8 pp |
| 35 | 75 / 0 / 25 | 59,9% | 59,4% | 56,0% | **58,4%** | −4,7 pp | −6,3 pp |
| 50 | 40 / 35 / 25 | 58,9% | 59,9% | 53,4% | **57,4%** | −5,7 pp | −7,3 pp |
| 50 | 55 / 20 / 25 | 58,9% | 59,9% | 55,0% | **57,9%** | −5,2 pp | −6,8 pp |
| 50 | 75 / 0 / 25 | 59,9% | 59,4% | 56,0% | **58,4%** | −4,7 pp | −6,3 pp |

**O vale não aparece nesta tabela** — as três linhas de cada peso são idênticas. O top 20% é preenchido inteiro pelas pontas do U (0–14 e 91–138, ambas F2 = 100); o vale só reordena o meio da fila. Por isso a segunda grade:

## Grade — win rate dos top 50% (alcança o vale)

| Vale (15–60) | Pesos F2 / F1 / F3 | T=2017-07-01 | T=2017-08-15 | T=2017-10-01 | Média | vs grupo | vs valor | % do top 50% que está no vale |
|---|---|---|---|---|---|---|---|---|
| 20 | 40 / 35 / 25 **← atual** | 62,8% | 64,4% | 56,9% | **61,4%** | −1,7 pp | −1,3 pp | 13% |
| 20 | 55 / 20 / 25 | 62,4% | 63,6% | 56,7% | **60,9%** | −2,2 pp | −1,8 pp | 11% |
| 20 | 75 / 0 / 25 | 62,0% | 64,0% | 55,2% | **60,4%** | −2,7 pp | −2,3 pp | 11% |
| 35 | 40 / 35 / 25 | 63,2% | 64,8% | 57,1% | **61,7%** | −1,4 pp | −1,0 pp | 16% |
| 35 | 55 / 20 / 25 | 62,2% | 63,8% | 56,5% | **60,8%** | −2,3 pp | −1,9 pp | 13% |
| 35 | 75 / 0 / 25 | 62,0% | 64,0% | 55,2% | **60,4%** | −2,7 pp | −2,3 pp | 11% |
| 50 | 40 / 35 / 25 | 63,0% | 65,9% | 57,3% | **62,1%** | −1,1 pp | −0,6 pp | 24% |
| 50 | 55 / 20 / 25 | 62,2% | 65,9% | 56,7% | **61,6%** | −1,5 pp | −1,1 pp | 19% |
| 50 | 75 / 0 / 25 | 62,4% | 64,8% | 55,0% | **60,8%** | −2,4 pp | −1,9 pp | 18% |

Referência top 50% por valor: 62,0% · 68,0% · 58,1%.

## O que está no topo (config atual)

| T | % do top 20% em janela crítica (≤ 14 d) | % em última janela (91–138 d) | Idade mediana do topo | Win rate topo | Win rate grupo |
|---|---|---|---|---|---|
| 2017-07-01 | 100% | 0% | 5 dias | 58,9% | 62,8% |
| 2017-08-15 | 73% | 27% | 8 dias | 59,9% | 67,1% |
| 2017-10-01 | 98% | 1% | 6 dias | 53,4% | 59,5% |

## Win rate por zona de idade em T (o que o F2 está ordenando)

| T | 0–14 | 15–60 | 61–90 | 91–138 |
|---|---|---|---|---|
| 2017-07-01 | 61% (n=333) | 64% (n=576) | 61% (n=74) | — |
| 2017-08-15 | 61% (n=210) | 70% (n=394) | 70% (n=293) | 59% (n=86) |
| 2017-10-01 | 56% (n=323) | 63% (n=558) | 50% (n=72) | 0% (n=2) |

## Quantos dias o vendedor tem — dias de T até a perda, só deals que perderam (mediana · p75)

| T | Estavam em 0–14 em T | Estavam em 15–60 em T | Estavam em 61–90 em T |
|---|---|---|---|
| 2017-07-01 | **7** · 54 (n=130) | 49 · 58 (n=207) | 39 · 45 (n=29) |
| 2017-08-15 | 84 · 97 (n=82) | 33 · 80 (n=119) | 12 · 24 (n=87) |
| 2017-10-01 | **10** · 57 (n=143) | 49 · 59 (n=206) | 39 · 47 (n=36) |

## O que os números dizem (sem mudar nada)

1. **Vale do F2.** Invisível no top 20%. No top 50%, vale 50 rende +0,7 pp sobre vale 20 (62,1% vs 61,4%) e coloca o dobro de deals do vale no topo (24% vs 13%). A diferença está dentro do ruído (≈ 2 pp). O número não manda subir nem manda ficar — diz que o vale é uma escolha de produto, não de acurácia.

2. **Peso do F1.** No top 20%, tirar o F1 melhora 1,0 pp (57,4% → 58,4%). No top 50%, tirar o F1 piora 1,0 pp (61,4% → 60,4%). Sinais contrários, ambos dentro do ruído. Bate com o 0,515 do check de ML: fora do período, o encaixe vendedor × produto quase não ordena. Nada aqui sustenta 35 especificamente; nada aqui derruba.

3. **O achado que pesa mais: com a métrica escolhida, o topo da fila atual ganha menos que o grupo (−5,7 pp) e menos que ordenar por valor (−7,3 pp).** É consequência direta do desenho, não bug: o top 20% é 73–100% janela crítica (idade mediana 5–8 dias), e a zona 0–14 tem a menor win rate em todos os cortes (56–61% contra 63–70% no vale). O U manda atenção para onde se perde; "quantos ganharam" mede onde se ganha. **Este backtest não consegue validar a tese da atenção** — precisaria do contrafactual (o que teria acontecido com esforço), que o dataset não tem.

4. **O que ele confirma da tese:** a premissa "quem perde, perde cedo" segura fora da amostra. Em dois dos três cortes, metade das perdas dos deals em janela crítica acontece **em 7–10 dias a partir de T**. Se o esforço evita perda, ele precisa ser nessa semana. (O corte de 15/08 foge do padrão — mediana 84 dias — e não sei o motivo; fica registrado.)

5. **Ordenar por valor** bate a fila em win rate porque os produtos caros não fecham menos (4,8 pp entre produtos, H4) e o empate esperado devolve quase a média do grupo. Não é que valor prediz; é que não atrapalha.

## Ressalvas do método

- **Censura à direita no corte de 10/01:** deals abertos em T que não fecharam até 31/12 ficam fora. Sobram os que fecharam rápido — e nas zonas mais velhas isso distorce (61–90: 50% com n=72; 91–138: n=2).
- **Idade em T é idade parcial**, não a duração final — é o que o app vê de verdade, ao contrário do check de ML.
- **Empates no score** são resolvidos como no app (janela crítica primeiro, depois `opportunity_id`); o último critério é arbitrário, e o efeito no top 20% é pequeno.
- A métrica é binária (ganhou / perdeu). Não pesa o valor do que ganhou.

## Decisão

_(preenchida depois de ler a tabela)_
