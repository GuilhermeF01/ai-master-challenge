# Teste das hipóteses H1–H7

> Gerado por [`solution/analysis/test_hipoteses.py`](../solution/analysis/test_hipoteses.py) (stdlib, sem dependências).
> Win rate = Won / (Won + Lost). Deals abertos (Prospecting/Engaging) ficam fora de toda conta.
> Status de cada hipótese é decidido em [01-hipoteses.md](01-hipoteses.md), não aqui.

## Decisões tomadas antes do teste (a partir da auditoria)

1. Corrigir no load: `GTXPro → GTX Pro` e `technolgy → technology`.
2. Data de referência = **2017-12-31** (última data do dataset). A data de hoje não entra em nada.
3. `close_value` e `close_date` não são features de deal aberto. Valor de deal aberto = `sales_price` do produto.
4. O score precisa funcionar sem conta (68% dos abertos não têm); quando tiver conta, enriquece.

## Correções no load

| Correção | Efeito |
|---|---|
| `GTXPro → GTX Pro` | 1.480 linhas do pipeline recuperadas no join; 0 produtos órfãos depois |
| `technolgy → technology` | 12 contas corrigidas; 1.165 linhas do pipeline dessas contas |

**Baseline:** 6.711 deals fechados (Won 4.238 / Lost 2.473), win rate global **63,2%**. 2.089 abertos excluídos.

---

## H1 — Engaging fecha mais que Prospecting

| Verificação | Resultado |
|---|---|
| Deals fechados com `engage_date` | 6.711 / 6.711 |
| Deals fechados sem `engage_date` (fechou direto de Prospecting) | 0 |
| Deals em Prospecting com `engage_date` | 0 / 500 |
| Win rate de quem passou por Engaging | 63,2% |
| Win rate de quem ficou em Prospecting e fechou | não existe (0 linhas) |

Não dá pra comparar win rate: **todo** deal fechado passou por Engaging, e nenhum Prospecting fechou sem engajar. O dataset não tem o contrafactual.

---

## H2 — Vendedor importa

| Vendedor | Manager / Região | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|---|
| Hayden Neloms | Celia Rouche / West | 152 | 107 | 45 | 70,4% |
| Maureen Marcano | Summer Sewald / West | 213 | 149 | 64 | 70,0% |
| Wilburn Farren | Cara Losch / East | 79 | 55 | 24 | 69,6% |
| Cecily Lampkin | Dustin Brinkmann / Central | 160 | 107 | 53 | 66,9% |
| Versie Hillebrand | Dustin Brinkmann / Central | 264 | 176 | 88 | 66,7% |
| Moses Frase | Dustin Brinkmann / Central | 195 | 129 | 66 | 66,2% |
| Boris Faz | Rocco Neubert / East | 153 | 101 | 52 | 66,0% |
| James Ascencio | Summer Sewald / West | 206 | 135 | 71 | 65,5% |
| Corliss Cosme | Cara Losch / East | 229 | 150 | 79 | 65,5% |
| Rosalina Dieter | Celia Rouche / West | 110 | 72 | 38 | 65,5% |
| Reed Clapper | Rocco Neubert / East | 237 | 155 | 82 | 65,4% |
| Jonathan Berthelot | Melvin Marxen / Central | 264 | 171 | 93 | 64,8% |
| Rosie Papadopoulos | Cara Losch / East | 121 | 78 | 43 | 64,5% |
| Kami Bicknell | Summer Sewald / West | 272 | 174 | 98 | 64,0% |
| Vicki Laflamme | Celia Rouche / West | 347 | 221 | 126 | 63,7% |
| Elease Gluck | Celia Rouche / West | 126 | 80 | 46 | 63,5% |
| Violet Mclelland | Cara Losch / East | 193 | 122 | 71 | 63,2% |
| Darcel Schlecht | Melvin Marxen / Central | 553 | 349 | 204 | 63,1% |
| Marty Freudenburg | Melvin Marxen / Central | 194 | 122 | 72 | 62,9% |
| Cassey Cress | Rocco Neubert / East | 261 | 163 | 98 | 62,5% |
| Kary Hendrixson | Summer Sewald / West | 335 | 209 | 126 | 62,4% |
| Anna Snelling | Dustin Brinkmann / Central | 336 | 208 | 128 | 61,9% |
| Zane Levy | Summer Sewald / West | 261 | 161 | 100 | 61,7% |
| Garret Kinder | Cara Losch / East | 123 | 75 | 48 | 61,0% |
| Daniell Hammack | Rocco Neubert / East | 187 | 114 | 73 | 61,0% |
| Niesha Huffines | Melvin Marxen / Central | 175 | 105 | 70 | 60,0% |
| Gladys Colclough | Melvin Marxen / Central | 232 | 135 | 97 | 58,2% |
| Donn Cantrell | Rocco Neubert / East | 275 | 158 | 117 | 57,5% |
| Markita Hansen | Celia Rouche / West | 227 | 130 | 97 | 57,3% |
| Lajuana Vencill | Dustin Brinkmann / Central | 231 | 127 | 104 | 55,0% |

Melhor − pior: **15,4 pp** (70,4% vs 55,0%). Menor grupo n=79. Mediana 63,6%, desvio-padrão 3,6 pp. 5 vendedores do `sales_teams` não têm nenhum deal.

---

## H3 — Conta grande fecha mais

Quartis calculados sobre as 85 contas.

| Revenue (USD mi) | Contas | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|---|
| Q1: 4,5–441 | 21 | 1.288 | 830 | 458 | 64,4% |
| Q2: 497–1.197 | 21 | 1.437 | 880 | 557 | 61,2% |
| Q3: 1.224–2.715 | 21 | 1.767 | 1.141 | 626 | 64,6% |
| Q4: 2.741–11.698 | 22 | 2.219 | 1.387 | 832 | 62,5% |

Melhor − pior: **1,9 pp** (Q1 vs Q4).

| Employees | Contas | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|---|
| Q1: 9–1.165 | 21 | 1.335 | 855 | 480 | 64,0% |
| Q2: 1.179–2.641 | 21 | 1.554 | 951 | 603 | 61,2% |
| Q3: 2.769–5.374 | 21 | 1.627 | 1.059 | 568 | 65,1% |
| Q4: 5.595–34.288 | 22 | 2.195 | 1.373 | 822 | 62,6% |

Melhor − pior: **1,5 pp** (Q1 vs Q4).

---

## H4 — Setor influencia

| Setor | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|
| marketing | 623 | 404 | 219 | 64,8% |
| entertainment | 402 | 260 | 142 | 64,7% |
| software | 704 | 450 | 254 | 63,9% |
| technology | 1.058 | 671 | 387 | 63,4% |
| services | 352 | 223 | 129 | 63,4% |
| retail | 1.267 | 799 | 468 | 63,1% |
| employment | 286 | 179 | 107 | 62,6% |
| telecommunications | 456 | 285 | 171 | 62,5% |
| medical | 950 | 592 | 358 | 62,3% |
| finance | 613 | 375 | 238 | 61,2% |

Melhor − pior: **3,7 pp**. Menor grupo n=286.

---

## H5 — Deal parado há muito tempo está fora

Dias em Engaging dos fechados = `close_date − engage_date`. Distribuição: min 1 · p25 8 · mediana 45 · p75 85 · **max 138**.

| Dias | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|
| 0–7 | 1.413 | 756 | 657 | 53,5% |
| 8–14 | 1.393 | 801 | 592 | 57,5% |
| 15–30 | 357 | 260 | 97 | 72,8% |
| 31–60 | 569 | 377 | 192 | 66,3% |
| 61–90 | 1.621 | 1.078 | 543 | 66,5% |
| 91–120 | 1.165 | 820 | 345 | 70,4% |
| 121+ | 193 | 146 | 47 | 75,6% |

Melhor − pior: **22,1 pp** — na direção **oposta** à hipótese (121+ é o melhor grupo, 0–7 o pior). Menor grupo n=193.

Fato estrutural: nenhum `close_date` antes de 2017-03-01. 972 fechados foram engajados antes disso (win rate 72,8%); 5.739 depois (61,5%). Mesma tabela só com os engajados a partir de 2017-03-01:

| Dias | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|
| 0–7 | 1.410 | 754 | 656 | 53,5% |
| 8–14 | 1.364 | 775 | 589 | 56,8% |
| 15–30 | 326 | 237 | 89 | 72,7% |
| 31–60 | 503 | 324 | 179 | 64,4% |
| 61–90 | 1.290 | 841 | 449 | 65,2% |
| 91–120 | 757 | 537 | 220 | 70,9% |
| 121+ | 89 | 62 | 27 | 69,7% |

Melhor − pior: **17,4 pp** (15–30 vs 0–7), mesma direção.

Extra que pesa pra essa hipótese: deals **abertos** em Engaging, dias até 2017-12-31: n=1.589 · min 9 · p25 148 · **mediana 165** · p75 263 · max 423. Nenhum deal fechado passou de 138 dias.

---

## H6 — Região / manager

| Região | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|
| West | 2.249 | 1.438 | 811 | 63,9% |
| East | 1.858 | 1.171 | 687 | 63,0% |
| Central | 2.604 | 1.629 | 975 | 62,6% |

Melhor − pior: **1,4 pp**.

| Manager | Região | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|---|
| Cara Losch | East | 745 | 480 | 265 | 64,4% |
| Summer Sewald | West | 1.287 | 828 | 459 | 64,3% |
| Celia Rouche | West | 962 | 610 | 352 | 63,4% |
| Dustin Brinkmann | Central | 1.186 | 747 | 439 | 63,0% |
| Melvin Marxen | Central | 1.418 | 882 | 536 | 62,2% |
| Rocco Neubert | East | 1.113 | 691 | 422 | 62,1% |

Melhor − pior: **2,3 pp**.

---

## H7 — Conta que já comprou compra de novo

"Já teve Won" = existe Won da conta com `close_date < engage_date` do deal. 85/85 contas têm pelo menos um Won em algum momento — por isso a comparação precisa ser temporal.

| Conta | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|
| Sem Won anterior | 1.098 | 792 | 306 | 72,1% |
| Já tinha Won antes | 5.613 | 3.446 | 2.167 | 61,4% |

Diferença: **10,7 pp** — na direção **oposta** à hipótese. Mas 972 dos 1.098 "sem Won anterior" são os engajados antes de 2017-03-01, quando nenhum Won existia ainda. Só engajados a partir de 2017-03-01:

| Conta | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|
| Sem Won anterior | 126 | 84 | 42 | 66,7% |
| Já tinha Won antes | 5.613 | 3.446 | 2.167 | 61,4% |

Diferença: **5,3 pp**, mesma direção, grupo pequeno (n=126).

Matriz — 1.160 fechados de 15 contas subsidiárias (7 matrizes):

| Matriz | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|
| Sem Won anterior | 208 | 150 | 58 | 72,1% |
| Já tinha Won antes | 952 | 588 | 364 | 61,8% |

Diferença: **10,4 pp**, direção oposta. Só engajados a partir de 2017-03-01: sem Won anterior n=**21** (81,0%) vs já tinha n=952 (61,8%) — grupo pequeno demais.

---

## Resumo dos spreads

| Hipótese | Spread melhor − pior | Menor grupo | Observação |
|---|---|---|---|
| H1 | — | — | não testável: sem contrafactual no dataset |
| H2 vendedor | 15,4 pp | 79 | |
| H3 tamanho (revenue) | 1,9 pp | 1.288 | |
| H3 tamanho (employees) | 1,5 pp | 1.335 | |
| H4 setor | 3,7 pp | 286 | |
| H5 dias em Engaging | 22,1 pp (17,4 pp pós-cut) | 193 (89) | direção oposta à hipótese |
| H6 região | 1,4 pp | 1.858 | |
| H6 manager | 2,3 pp | 745 | |
| H7 conta já teve Won | 10,7 pp (5,3 pp pós-cut) | 1.098 (126) | direção oposta à hipótese |
| H7 matriz já teve Won | 10,4 pp (19,2 pp pós-cut) | 208 (21) | direção oposta; pós-cut grupo pequeno demais |

---

## Extras pedidos depois do veredito

### A — Win rate por produto

| Produto | Preço (USD) | Fechados | Won | Lost | Win rate |
|---|---|---|---|---|---|
| MG Special | 55 | 1.223 | 793 | 430 | 64,8% |
| GTX Plus Pro | 5.482 | 745 | 479 | 266 | 64,3% |
| GTX Basic | 550 | 1.436 | 915 | 521 | 63,7% |
| GTX Pro | 4.821 | 1.147 | 729 | 418 | 63,6% |
| GTX Plus Basic | 1.096 | 1.051 | 653 | 398 | 62,1% |
| MG Advanced | 3.393 | 1.084 | 654 | 430 | 60,3% |
| GTK 500 | 26.768 | 25 | 15 | 10 | 60,0% |

Melhor − pior: **4,8 pp** (MG Special vs GTK 500, n=25). Sem o GTK 500: 4,5 pp (MG Special vs MG Advanced).

### B — Produto × vendedor

Matriz vendedor × produto — win rate (n):

| Vendedor | GTX Basic | GTX Pro | MG Special | MG Advanced | GTX Plus Pro | GTX Plus Basic | GTK 500 |
|---|---|---|---|---|---|---|---|
| Anna Snelling | 63% (51) | — (0) | 71% (144) | 47% (45) | 58% (48) | 52% (48) | — (0) |
| Boris Faz | 65% (26) | 74% (23) | 64% (14) | 63% (19) | 62% (29) | 67% (42) | — (0) |
| Cassey Cress | 60% (58) | 72% (53) | 67% (15) | 60% (60) | 56% (32) | 60% (43) | — (0) |
| Cecily Lampkin | 67% (24) | — (0) | 64% (39) | 66% (50) | 63% (27) | 80% (20) | — (0) |
| Corliss Cosme | 67% (54) | 67% (55) | 69% (16) | 43% (21) | 79% (38) | 61% (44) | 0% (1) |
| Daniell Hammack | 61% (18) | 70% (57) | 60% (10) | 36% (22) | 67% (27) | 58% (53) | — (0) |
| Darcel Schlecht | 68% (53) | 60% (265) | 65% (43) | 59% (61) | 70% (47) | 67% (83) | 0% (1) |
| Donn Cantrell | 61% (74) | 55% (73) | 33% (9) | 67% (48) | 57% (30) | 51% (41) | — (0) |
| Elease Gluck | 81% (16) | 80% (10) | 65% (51) | 54% (24) | 17% (6) | 71% (7) | 58% (12) |
| Garret Kinder | 52% (31) | 65% (20) | 67% (15) | 73% (22) | 52% (23) | 67% (12) | — (0) |
| Gladys Colclough | 54% (26) | 52% (50) | 61% (49) | 62% (53) | 56% (25) | 62% (29) | — (0) |
| Hayden Neloms | — (0) | — (0) | 74% (23) | 77% (77) | 90% (10) | 52% (42) | — (0) |
| James Ascencio | 63% (54) | 61% (33) | 69% (16) | 75% (16) | 69% (64) | 61% (23) | — (0) |
| Jonathan Berthelot | 65% (110) | 65% (48) | 81% (26) | 50% (18) | 62% (8) | 63% (54) | — (0) |
| Kami Bicknell | 66% (108) | 55% (42) | 75% (28) | 69% (26) | 83% (18) | 52% (50) | — (0) |
| Kary Hendrixson | 64% (129) | 65% (77) | 66% (29) | 44% (18) | 65% (31) | 59% (51) | — (0) |
| Lajuana Vencill | 57% (98) | — (0) | 50% (36) | 51% (55) | 59% (17) | 60% (25) | — (0) |
| Markita Hansen | 62% (47) | 60% (30) | 52% (54) | 60% (40) | 50% (14) | 57% (37) | 60% (5) |
| Marty Freudenburg | 65% (26) | 62% (16) | 74% (23) | 49% (41) | 72% (32) | 62% (56) | — (0) |
| Maureen Marcano | 56% (41) | 77% (30) | 65% (23) | 59% (17) | 81% (32) | 74% (70) | — (0) |
| Moses Frase | 80% (59) | — (0) | 57% (46) | 62% (42) | 54% (24) | 71% (24) | — (0) |
| Niesha Huffines | 60% (53) | 14% (14) | 55% (22) | 71% (17) | 80% (15) | 65% (54) | — (0) |
| Reed Clapper | 65% (37) | 67% (63) | 79% (19) | 64% (44) | 56% (32) | 67% (42) | — (0) |
| Rosalina Dieter | 67% (15) | 86% (7) | 58% (52) | 70% (23) | 50% (2) | 80% (5) | 83% (6) |
| Rosie Papadopoulos | 78% (9) | 81% (31) | 61% (33) | 54% (24) | 56% (18) | 50% (6) | — (0) |
| Versie Hillebrand | 65% (20) | — (0) | 69% (169) | 59% (46) | 71% (21) | 50% (8) | — (0) |
| Vicki Laflamme | 67% (83) | 68% (59) | 64% (80) | 57% (79) | 59% (27) | 68% (19) | — (0) |
| Violet Mclelland | 60% (25) | 56% (9) | 66% (108) | 66% (29) | 40% (5) | 59% (17) | — (0) |
| Wilburn Farren | 75% (12) | 69% (13) | 64% (11) | 72% (29) | 55% (11) | 100% (3) | — (0) |
| Zane Levy | 61% (79) | 67% (69) | 50% (20) | 56% (18) | 66% (32) | 60% (43) | — (0) |

Spread entre vendedores dentro de cada produto (só células com n ≥ 30):

| Produto | Vendedores com n≥30 | Melhor | Pior | Spread |
|---|---|---|---|---|
| GTX Basic | 18 | Moses Frase 79,7% (n=59) | Garret Kinder 51,6% (n=31) | 28,0 pp |
| GTX Pro | 16 | Rosie Papadopoulos 80,6% (n=31) | Gladys Colclough 52,0% (n=50) | 28,6 pp |
| MG Special | 13 | Anna Snelling 70,8% (n=144) | Lajuana Vencill 50,0% (n=36) | 20,8 pp |
| MG Advanced | 14 | Hayden Neloms 76,6% (n=77) | Anna Snelling 46,7% (n=45) | 30,0 pp |
| GTX Plus Pro | 11 | Maureen Marcano 81,2% (n=32) | Reed Clapper 56,2% (n=32) | 25,0 pp |
| GTX Plus Basic | 17 | Maureen Marcano 74,3% (n=70) | Donn Cantrell 51,2% (n=41) | 23,1 pp |
| GTK 500 | 0 | — | — | — |

Spread global das células:

| Filtro | Células | Melhor | Pior | Spread |
|---|---|---|---|---|
| n ≥ 30 | 89 de 178 | Maureen Marcano / GTX Plus Pro 81,2% (n=32) | Anna Snelling / MG Advanced 46,7% (n=45) | **34,6 pp** |
| n ≥ 50 | 47 de 178 | Moses Frase / GTX Basic 79,7% (n=59) | Lajuana Vencill / MG Advanced 50,9% (n=55) | **28,8 pp** |

Referência: vendedor sozinho 15,4 pp (menor n=79); produto sozinho 4,8 pp. Células são bem menores que os grupos de vendedor — o spread maior vem em parte do n menor.

### C — H5: curva acumulada de fechamento por dias em Engaging

| Dias | % dos fechados já fechados | % dos Won já fechados | % dos Lost já fechados |
|---|---|---|---|
| ≤ 7 | 21,1% | 17,8% | 26,6% |
| ≤ 14 | 41,8% | 36,7% | 50,5% |
| ≤ 30 | 47,1% | 42,9% | 54,4% |
| ≤ 60 | 55,6% | 51,8% | 62,2% |
| ≤ 90 | 79,8% | 77,2% | 84,1% |
| ≤ 120 | 97,1% | 96,6% | 98,1% |
| ≤ 138 | 100,0% | 100,0% | 100,0% |

Mediana de dias em Engaging: Won 57 · Lost 14 · todos 45.

### D — Check de ML: um modelo faria melhor que a heurística?

Regressão logística nos 6.711 fechados com **split temporal**: treina nos que fecharam antes de 2017-09-29 (4.680 deals, win rate 64,2%), testa nos que fecharam depois (2.031 deals, win rate 60,8%). Script: [`solution/analysis/ml_check.py`](../solution/analysis/ml_check.py) (só análise; requer scikit-learn, que não é dependência do app). Heurísticas calibradas só no treino.

| Modelo | Features | AUC treino | AUC teste |
|---|---|---|---|
| LR vendedor + produto + idade (linear) | 38 | 0,591 | 0,565 |
| LR vendedor + produto + idade (faixas) | 44 | 0,602 | **0,572** |
| LR vendedor + produto (sem idade) | 37 | 0,548 | 0,528 |
| LR idade (faixas) só | 7 | 0,589 | 0,569 |
| LR vendedor×produto + idade (faixas) | 185 | 0,640 | 0,564 |
| Heurística F1 só (célula suavizada, K1=K2=50) | 1 | 0,595 | 0,515 |
| Heurística score completo (F2 em U) — não é probabilidade | 3 | 0,496 | 0,477 |

- Melhor modelo: 0,572 de AUC no teste. Idade sozinha dá 0,569 — praticamente tudo que o modelo sabe vem da idade.
- Vendedor + produto sem idade: 0,528. A interação vendedor×produto sobe no treino (0,640) e cai no teste (0,564): overfit.
- F1 da heurística: 0,595 no treino → **0,515 no teste**. O encaixe vendedor×produto calibrado num período quase não ordena o período seguinte.
- Score completo abaixo de 0,5 é esperado: o F2 em U dá 100 à faixa de 0–14 dias, que tem a menor win rate. O score ordena por atenção, não por chance de ganhar — o número confirma que ele não é probabilidade.
- Ressalva: "idade" aqui é a duração total do deal fechado, conhecida só no fechamento. Para um deal aberto só se conhece a idade até hoje. O AUC com idade é um teto otimista, não o que um modelo entregaria em produção.
