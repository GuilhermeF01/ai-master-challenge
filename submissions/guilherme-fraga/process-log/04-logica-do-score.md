# Lógica do score — aprovada antes de codar

> Regras decididas a partir de [03-teste-hipoteses.md](03-teste-hipoteses.md) e do veredito em [01-hipoteses.md](01-hipoteses.md).
> Primeira versão aprovada manualmente ([screenshot](screenshots/01-aprovacao-manual-logica-do-score.png)) com três correções, registradas em [erros-e-correcoes.md](erros-e-correcoes.md): F2 refeito como atenção em U, K2 de 30 para 50, e ordem dentro de Decidir.

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

### Fator 2 — Necessidade de atenção pela idade em Engaging (curva em U)

**Não mede chance de ganhar.** Mede onde o esforço do vendedor muda o resultado. Calibrado pela curva dos 6.711 fechados: em cada faixa de idade, quanto do que ainda estava vivo foi decidido, por dia.

| Faixa (dias em Engaging) | Desfechos na faixa | % de todos os desfechos | % dos Lost | Vivos no início | Decididos ÷ vivos | Por dia |
|---|---|---|---|---|---|---|
| 0–7 | 1.413 | 21,1% | 26,6% | 6.711 | 21,1% | 2,63% |
| 8–14 | 1.393 | 20,8% | 23,9% | 5.298 | 26,3% | 3,76% |
| 15–30 | 357 | 5,3% | 3,9% | 3.905 | 9,1% | 0,57% |
| 31–60 | 569 | 8,5% | 7,8% | 3.548 | 16,0% | 0,53% |
| 61–90 | 1.621 | 24,2% | 22,0% | 2.979 | 54,4% | 1,81% |
| 91–120 | 1.165 | 17,4% | 14,0% | 1.358 | 85,8% | 2,86% |
| 121–138 | 193 | 2,9% | 1,9% | 193 | 100,0% | 5,56% |

A coluna "por dia" é o U: 2,6–3,8% nos primeiros 14 dias, cai para 0,5% entre 15 e 60, volta a 1,8% entre 61 e 90 e passa de 2,9% a partir do dia 91.

**Degraus do F2** — `por dia ÷ 2,79%` (a taxa da zona 0–14), limitado a 100:

| Zona | F2 | O que a curva diz |
|---|---|---|
| **0–14 dias** | **100** | 41,8% de todos os desfechos e **50,5% das perdas** acontecem aqui. É onde se perde — e onde o esforço evita a perda. |
| **15–60 dias** | **20** | Vale do U: 13,8% dos desfechos em 46 dias, 0,52% por dia — 5× mais calmo que as pontas. Follow-up normal. |
| **61–90 dias** | **65** | Segunda onda: 24,2% dos desfechos (22% das perdas) em 30 dias. |
| **91–138 dias** | **100** | Última janela antes da parede: **80% dos que fecham já fecharam aos 90**, 100% dos vivos são decididos aqui, nenhum deal passou de 138. |

- O vale (15–60) sai da fórmula em 19, arredondado para 20. É mais baixo que "médio = 50" porque os dados dizem que a faixa é calma mesmo; se quiser um piso mais alto, é um número só para mudar, mas as pontas perdem contraste.
  - **Ressalva registrada na aprovação:** 20 parece baixo — um deal de 45 dias com encaixe bom e valor alto fica atrás de quase todo deal novo. Fica em 20 por enquanto, sem mudar no chute; **revisar depois do backtest, com número na mão.**
- 61–90 fica como degrau próprio (65) e não dentro do "médio" porque a curva mostra uma segunda onda ali — um quarto de todos os desfechos.
- As duas pontas ficam em 100: a categoria e os marcadores dizem qual é qual (*janela crítica* ≤ 14 / *última janela* 91–138). Dentro da mesma pontuação de F2, F1 e F3 desempatam.
- A curva é calculada dos dados na hora de rodar, não é hard-coded — se o CSV mudar, os degraus mudam. Os cortes de faixa (14 / 60 / 90 / 138) são fixos.
- Frases:
  - 0–14: *"Há 9 dias em Engaging. Metade das perdas acontece até o dia 14 — é agora que o seu esforço evita a perda."*
  - 15–60: *"Há 45 dias em Engaging. Zona de follow-up: só 14% dos desfechos acontecem entre os dias 15 e 60. Mantenha a cadência."*
  - 61–90: *"Há 75 dias em Engaging. Segunda onda de decisões: um em cada quatro deals se define entre 61 e 90 dias."*
  - 91–138: *"Há 110 dias em Engaging. Última janela: 80% dos que fecham já fecharam aos 90 dias e nenhum passou de 138. Empurre para a decisão."*
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
score = (40 * F2 + 35 * F1 + 25 * F3) / 100                     # Engaging
score = (35 * F1 + 25 * F3) / 60                                # Prospecting (sem F2, renormalizado)
```

| Fator | Peso | Justificativa a partir dos spreads |
|---|---|---|
| F2 — Atenção pela idade | **40** | Maior spread do teste (22,1 pp por faixa; 17,4 pp pós-cut), grupos grandes (menor n = 89), e a curva acumulada mostra onde as decisões acontecem (mediana Lost 14 dias vs Won 57). É o sinal que o vendedor **não vê** no CRM: ele vê o stage, não a curva. |
| F1 — Encaixe | **35** | Vendedor sozinho dá 15,4 pp; com produto sobe para 28,8 pp (n ≥ 50), mas parte disso é n pequeno e a suavização come parte do spread (F1 real fica entre 8 e 85). Fica logo abaixo da idade. Também é um sinal que o vendedor em parte já conhece — o app confirma mais do que revela. |
| F3 — Valor | **25** | Não prediz fechamento (4,8 pp entre produtos), então não pode pesar como os outros dois. Entra porque fila de atenção é sobre dinheiro: a sinal igual, o deal maior vem antes. Com 25, a diferença máxima por valor é 25 pontos — GTX Pro (72) ganha 18 pontos sobre MG Special (0) em igualdade, mas um GTK 500 com encaixe e idade ruins (≈ 25 + 3 + 8 ≈ 36) não passa um deal mediano no vale com bom encaixe (≈ 8 + 29 + 18 ≈ 55). |

## Categorias de ação

A **categoria manda na ordem**; o score desempata **dentro** dela.

| # | Categoria | Regra | Ordem interna | O que o app pede |
|---|---|---|---|---|
| 1 | **Agir** | Engaging, idade ≤ 138 dias | score desc | Trabalhar o deal. Fila normal. |
| 2 | **Engajar** | Prospecting | score desc (só F1 e F3) | Iniciar o engajamento. Aviso "sem sinal de tempo". |
| 3 | **Decidir** | Engaging, idade > 138 dias | **`sales_price` desc**, desempate por idade desc | Não é esforço, é decisão: **requalificar ou descartar**. Sem score de fila. Ordenado por valor para o manager limpar os grandes primeiro. |

- Engaging antes de Prospecting porque está mais perto do dinheiro; Decidir por último porque não é trabalho de venda.
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

Além desses: teste de que a soma dos pesos dá 100 (e 60 renormalizado para Prospecting), de que F1/F2/F3 ficam em [0, 100], de que o F2 é U (0–14 e 91–138 > 61–90 > 15–60), e de que a correção `GTXPro → GTX Pro` deixa 0 produtos órfãos.

## Saída por deal

```
opportunity_id, vendedor, manager, região, produto, conta (ou "—"),
categoria, score (0–100 ou "—" em Decidir), confiança,
F1, F2, F3, frase_F1, frase_F2, frase_F3, marcadores (ex.: "janela crítica", "última janela")
```

Filtros do app: vendedor, manager, região (o bônus do README). Sem API key, sem rede.

## Decisões fechadas

1. Pesos 40 / 35 / 25.
2. K1 = 50, **K2 = 50**.
3. F1 em ±15 pp; **F2 em degraus de atenção (U)**; F3 em log.
4. Ordem das categorias Agir → Engajar → Decidir; **Decidir ordenado por valor**.
5. Marcadores "janela crítica" e "última janela" como rótulos dentro de Agir.
