# Lógica do score — aprovada antes de codar

> Regras decididas a partir de [03-teste-hipoteses.md](03-teste-hipoteses.md) e do veredito em [01-hipoteses.md](01-hipoteses.md).
> Primeira versão aprovada manualmente ([screenshot](screenshots/01-aprovacao-manual-logica-do-score.png)) com três correções, registradas em [erros-e-correcoes.md](erros-e-correcoes.md): F2 refeito como atenção em U, K2 de 30 para 50, e ordem dentro de Decidir.
> **Revisão após o backtest ([05](05-backtest.md)):** pesos 40/35/25 → **55/20/25** e vale do F2 20 → **35**. As duas mudanças estão marcadas abaixo.

## O que o score é (e não é)

- Score de **0 a 100**. É **fila de atenção**, não probabilidade de fechar. Isso fica escrito no app, ao lado do número.
- Data de referência: **2017-12-31** (última data do dataset). A data de hoje não entra em nada.
- Deal aberto = `Prospecting` ou `Engaging`. Fechado (`Won`/`Lost`) só serve de histórico para calibrar as curvas.
- `close_value` e `close_date` **nunca entram como feature de deal aberto** (ver "Teste obrigatório" abaixo). `close_date` dos fechados é usado apenas para calcular a duração histórica em Engaging, que alimenta a curva do fator 2. `close_value` não é usado em lugar nenhum.
- Funciona **sem conta** (68% dos abertos não têm). Nenhum fator depende de `accounts.csv` — H3, H4 e H7 foram derrubadas. Quando há conta, o app só mostra os dados dela como contexto (setor, receita, matriz), sem entrar no número.

## Os três fatores

Cada fator devolve dois valores: um número **0–100** e uma **frase em português** explicando o sinal (positiva ou negativa).

### Fator 1 — Encaixe vendedor × produto (suavizado)

Win rate histórico do vendedor **naquele produto**, puxado para a média do vendedor quando a célula é pequena, e a média do vendedor puxada para a média geral quando o vendedor tem poucos deals.

```
media_geral       = Won / (Won + Lost) de todos os fechados            # 63,2%
vendedor_suav     = (won_vendedor + K1 * media_geral) / (n_vendedor + K1)
celula_suav       = (won_celula   + K2 * vendedor_suav) / (n_celula + K2)
F1                = clip( 50 + (celula_suav − media_geral) * 100 / 30 , 0, 100 )
```

- **K1 = 50, K2 = 50.** Com K2 = 50 a célula pesa 17% com 10 deals, 38% com 30, 67% com 100. Célula pequena desloca o score, não manda nele.
- Escala: ±15 pp em torno da média geral cobre 0–100 (48,2% → 0, 63,2% → 50, 78,2% → 100) — é o spread do vendedor sozinho (15,4 pp). Com K2 = 50, as células suavizadas dos dados reais ficam entre 50,5% e 73,6%, ou seja, F1 entre 8 e 85: nenhuma célula chega aos extremos.
- Exemplos com os dados reais (K1 = 50, K2 = 50):

| Vendedor / produto | Célula crua | Vendedor | Célula suavizada | F1 |
|---|---|---|---|---|
| Moses Frase / GTX Basic | 47/59 = 80% | 66,2% | 73,2% | 83 |
| Hayden Neloms / GTX Plus Pro | 9/10 = 90% | 70,4% | 72,2% | 80 |
| Wilburn Farren / GTX Plus Basic | 3/3 = 100% | 69,6% | 69,0% | 69 |
| Darcel Schlecht / GTX Pro | 160/265 = 60% | 63,1% | 60,8% | 42 |
| Anna Snelling / MG Advanced | 21/45 = 47% | 61,9% | 54,8% | 22 |
| Niesha Huffines / GTX Pro | 2/14 = 14% | 60,0% | 50,5% | 8 |

- Vendedor sem histórico no produto (célula n = 0): `celula_suav = vendedor_suav`. Vendedor sem histórico nenhum (os 5 sem deal): `= media_geral`, F1 = 50.
- Frases:
  - positiva: *"Você fecha GTX Basic em 47 de 59 deals (80%) — bem acima da média geral (63%)."*
  - negativa: *"Seu histórico em MG Advanced é 21 de 45 (47%) — abaixo da sua média (62%) e da geral (63%)."*
  - base pequena: *"Seu histórico em GTX Plus Pro é 9 de 10 (90%). Base pequena: o score usa 72% (puxado para a sua média de 70%)."*
  - sem histórico: *"Você ainda não fechou nenhum GTK 500. O score usa a sua média geral (66%)."*

### Fator 2 — Necessidade de atenção pela idade em Engaging

> **Reescrito após a [revisão externa](06-revisao-externa.md), B1.** A versão aprovada era um U com 100 nas duas pontas. O braço direito (91–138 = 100) era artefato de três causas empilhadas: (a) a última faixa terminava na parede, então "vivos" era igual a "decididos" por definição; (b) os 1.589 deals abertos em Engaging — vivos em cada idade e nunca fechados — não entravam no denominador; (c) as coortes engajadas antes do primeiro fechamento do dataset (2017-03-01) só podiam ter duração longa. A versão abaixo corrige as três. A tabela original fica no histórico do git.

**Não mede chance de ganhar.** Mede onde a decisão está acontecendo: o **hazard** por idade — de cada dia vivido em Engaging naquela faixa, quantos terminam em desfecho (ganho ou perda).

```
conjunto de risco  = fechados (evento na duração) + abertos em Engaging (censurados na referência)
coorte             = engajados a partir do primeiro close_date do histórico (2017-03-01)
por_dia(faixa)     = desfechos na faixa ÷ dias de exposição na faixa
F2(zona)           = min(100, por_dia(zona) ÷ por_dia(0–14) × 100)      # média da zona, nunca o pico de uma faixa
```

Calibrado em 5.739 fechados da coorte + 1.376 abertos censurados em 2017-12-31:

| Faixa (dias) | Desfechos | Vivos no início | Exposição (dias) | Por dia |
|---|---|---|---|---|
| 0–7 | 1.410 | 7.115 | 52.629 | 2,68% |
| 8–14 | 1.364 | 5.705 | 34.598 | 3,94% |
| 15–30 | 326 | 4.334 | 65.475 | 0,50% |
| 31–60 | 503 | 3.997 | 113.893 | 0,44% |
| 61–90 | 1.290 | 3.455 | 84.431 | 1,53% |
| 91–120 | 757 | 2.112 | 48.492 | 1,56% |
| 121–138 | 89 | 1.252 | 20.837 | 0,43% |

**Degraus do F2** (média da zona ÷ média de 0–14):

| Zona | Por dia | Curva | F2 | O que a curva diz |
|---|---|---|---|---|
| **0–14 dias** | 3,18% | 100 | **100** | 56% das perdas da coorte acontecem aqui. É onde se perde — e onde o esforço evita a perda. |
| **15–60 dias** | 0,46% | 15 | **35** (piso) | Vale: 7× mais calmo que as duas primeiras semanas. Follow-up normal. Piso de produto em 35 (decisão no [05](05-backtest.md)): é a zona que mais ganha e não pode ficar no fundo. |
| **61–90 dias** | 1,53% | 48 | **48** | Segunda onda: metade da intensidade da primeira. |
| **91–138 dias** | 1,22% | 38 | **38** | Perto da parede. Sem censura este degrau dava 100; com os 1.291 abertos que já passaram de 138 no conjunto de risco, cai para 38. Não é "última janela quente" — é a antessala de Decidir. |

- A curva é calculada dos dados na hora de rodar: com o CSV, os degraus mudam (teste sintético com hazard constante dá curva plana; sem os abertos no conjunto de risco, a última zona satura em 100 — os dois estão em `tests/test_invariants.py`). Os cortes de faixa (14 / 60 / 90) são fixos; a parede (138) é o máximo dos fechados, todas as coortes.
- `f2_curva` guarda o valor da curva; `f2` é o que o score usa (só o piso do vale difere).
- Marcadores dentro de Agir: **janela crítica** (≤ 14 dias) e **última janela** (91–138) continuam como rótulos de zona.
- Frases (números calculados da coorte, não decorados — revisão D2):
  - 0–14: *"Há 9 dias em Engaging. 56% das perdas acontecem até o dia 14 — é agora que o seu esforço evita a perda."*
  - 15–60: *"Há 45 dias em Engaging. Zona de follow-up: só 14% dos desfechos acontecem entre os dias 15 e 60. Mantenha a cadência."*
  - 61–90: *"Há 75 dias em Engaging. Segunda onda de decisões: 22% dos desfechos acontecem entre 61 e 90 dias."*
  - 91–138: *"Há 95 dias em Engaging. Perto da parede: 85% dos que fecham já fecharam aos 90 dias, nenhum do histórico fechou depois de 138, e 1.291 abertos já passaram disso sem fechar. Decida antes que vire mais um."*
  - Decidir: *"Há 377 dias em Engaging. Nenhum deal do histórico fechou depois de 138 dias; 1.291 abertos já passaram disso sem fechar. Não é esforço, é decisão: requalificar ou descartar."*
  - Prospecting: *"Sem data de engajamento: não há sinal de tempo. Score usa só encaixe e valor."*

### Fator 3 — Valor em jogo

`sales_price` do produto, em escala **logarítmica** de 0 a 100.

| Produto | Preço (USD) | F3 |
|---|---|---|
| MG Special | 55 | 0 |
| GTX Basic | 550 | 37 |
| GTX Plus Basic | 1.096 | 48 |
| MG Advanced | 3.393 | 67 |
| GTX Pro | 4.821 | 72 |
| GTX Plus Pro | 5.482 | 74 |
| GTK 500 | 26.768 | 100 |

- Log e não linear porque em escala linear o GTK 500 (26.768) vira 100 e todo o resto fica abaixo de 21 — o fator deixaria de distinguir GTX Pro de MG Special, que é a distinção que aparece 8.700 vezes no pipeline. Log dá um degrau por ordem de grandeza.
- Frases: *"GTX Pro: USD 4.821 em jogo — 4º produto mais caro dos 7."* / *"MG Special: USD 55 — o produto mais barato do catálogo."*

## Pesos

```
score = (55 * F2 + 20 * F1 + 25 * F3) / 100                     # Engaging
score = (20 * F1 + 25 * F3) / 45                                # Prospecting (sem F2, renormalizado)
```

Eram 40 / 35 / 25 na aprovação. Revisados no [05](05-backtest.md): o AUC 0,515 do encaixe fora do período e as duas rodadas do backtest dizem a mesma coisa — **encaixe é contexto, não motor**. A frase do F1 continua no cartão; o número pesa menos.

| Fator | Peso | Justificativa a partir dos spreads |
|---|---|---|
| F2 — Atenção pela idade | **55** (era 40) | Maior spread do teste (22,1 pp por faixa; 17,4 pp pós-cut), grupos grandes (menor n = 89), e a curva acumulada mostra onde as decisões acontecem (mediana Lost 14 dias vs Won 57). É o sinal que o vendedor **não vê** no CRM: ele vê o stage, não a curva. O backtest ([05](05-backtest.md)) mede se a curva generaliza fora do período. |
| F1 — Encaixe | **20** (era 35) | Vendedor sozinho dá 15,4 pp; com produto sobe para 28,8 pp (n ≥ 50), mas parte disso é n pequeno e a suavização come parte do spread (F1 real fica entre 8 e 85). Fora do período, quase não ordena (AUC 0,515; backtest indiferente a 35 / 20 / 0). É um sinal que o vendedor em parte já conhece — o app confirma mais do que revela. Fica como contexto. |
| F3 — Valor | **25** | Não prediz fechamento (4,8 pp entre produtos), então não pode pesar como os outros dois. Entra porque fila de atenção é sobre dinheiro: a sinal igual, o deal maior vem antes. Com 25, a diferença máxima por valor é 25 pontos — GTX Pro (72) ganha 18 pontos sobre MG Special (0) em igualdade, mas um GTK 500 no vale com encaixe ruim (≈ 19 + 2 + 25 ≈ 46) não passa um deal em janela crítica com encaixe mediano (≈ 55 + 10 + 9 ≈ 74). |

## Categorias de ação

A **categoria manda na ordem**; o score desempata **dentro** dela.

| # | Categoria | Regra | Ordem interna | O que o app pede |
|---|---|---|---|---|
| 1 | **Agir** | Engaging, idade ≤ 138 dias | score desc | Trabalhar o deal. Fila normal. |
| 2 | **Engajar** | Prospecting | score desc (só F1 e F3) | Iniciar o engajamento. Aviso "sem sinal de tempo". |
| 3 | **Decidir** | Engaging, idade > 138 dias | **`sales_price` desc**, desempate por idade desc | Não é esforço, é decisão: **requalificar ou descartar**. Sem score de fila. Ordenado por valor para o manager limpar os grandes primeiro. |

- Engaging antes de Prospecting porque está mais perto do dinheiro; Decidir por último porque não é trabalho de venda.
- **Empate no score dentro de Agir: janela crítica (≤ 14 dias) primeiro** — ali a perda é questão de dias. (Ajuste feito ao ver o app: Boris Faz tinha dois GTX Pro com 81, o de 117 dias na frente do de 12.)
- Marcadores dentro de Agir (rótulo, não categoria): **janela crítica** (≤ 14 dias) e **última janela** (91–138 dias). O F2 já carrega a urgência no número; o marcador só nomeia qual das duas pontas do U o deal está.
- Regra fixa de dados: **não existe deal fechado sem passar por Engaging** (H1). Prospecting nunca vai direto para Decidir.

### Como o pipeline aberto se distribui nessas regras (2017-12-31)

| Categoria / zona | Deals |
|---|---|
| Agir · 0–14 dias | 7 |
| Agir · 15–60 dias | 50 |
| Agir · 61–90 dias | 53 |
| Agir · 91–138 dias | 188 |
| **Agir (total)** | **298** |
| **Engajar** (Prospecting) | **500** |
| **Decidir** (> 138 dias) | **1.291** |

Ou seja: na data de referência, 81% dos deals em Engaging estão além da parede. A fila de trabalho tem 798 deals; a lista de decisão tem 1.291. É o retrato do snapshot, não um bug — e é o argumento mais forte do app para a Head de RevOps.

## Confiança (separada do score)

Baseada em **quantos deals fechados o vendedor tem naquele produto** (n da célula), porque é o único fator com base amostral por deal — a curva de idade usa os 6.711 fechados e o valor é tabela.

| Confiança | n da célula |
|---|---|
| Alta | ≥ 50 |
| Média | 20–49 |
| Baixa | < 20 (inclui 0) |

Prospecting acrescenta a frase "sem sinal de tempo" mas não rebaixa a confiança — são coisas diferentes e o app mostra as duas.

## Teste obrigatório: `close_value` e `close_date` não entram

Testes automatizados (`pytest`), rodam com `pip install` + um comando:

1. **Permutação** — embaralhar `close_value` e `close_date` **dos deals abertos** no CSV e re-rodar: o score, a categoria, a confiança e as frases de **cada deal aberto** têm que ser idênticos.
2. **Remoção** — apagar as duas colunas dos deals abertos antes de chamar o scorer: saída idêntica. O scorer recebe os abertos **sem essas colunas** por construção (o loader as descarta), e o teste verifica que elas não chegam lá.
3. **Isolamento do histórico** — embaralhar `close_value` dos deals **fechados**: saída idêntica (prova que o valor real de fechamento não vaza nem pela calibração). `close_date` dos fechados não entra nesse teste porque é ele que define a duração da curva — isso é histórico, não feature.

Além desses: teste de que a soma dos pesos dá 100 (e 45 renormalizado para Prospecting), de que F1/F2/F3 ficam em [0, 100], de que o F2 é U (0–14 e 91–138 > 61–90 > 15–60), e de que a correção `GTXPro → GTX Pro` deixa 0 produtos órfãos.

## Saída por deal

```
opportunity_id, vendedor, manager, região, produto, conta (ou "—"),
categoria, score (0–100 ou "—" em Decidir), confiança,
F1, F2, F3, frase_F1, frase_F2, frase_F3, marcadores (ex.: "janela crítica", "última janela")
```

Filtros do app: vendedor, manager, região (o bônus do README). Sem API key, sem rede.

## Decisões fechadas

1. Pesos ~~40 / 35 / 25~~ → **55 / 20 / 25** (revisto no 05).
2. K1 = 50, **K2 = 50**.
3. F1 em ±15 pp; **F2 em degraus de hazard por idade com censura, com piso de 35 no vale** (revisto no 05 e na revisão externa B1); F3 em log.
4. Ordem das categorias Agir → Engajar → Decidir; **Decidir ordenado por valor**.
5. Marcadores "janela crítica" e "última janela" como rótulos dentro de Agir.
