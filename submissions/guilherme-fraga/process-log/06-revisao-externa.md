# Revisão externa — tentativa de derrubar o score e o backtest

> **Revisor: Claude Fable 5.1 (`claude-fable-5-1`)**, em sessão separada, sem contato com a sessão que construiu. Só leitura e scripts de verificação num venv de rascunho; nada foi editado no projeto.
>
> Lido: README do challenge, [04](04-logica-do-score.md), [05](05-backtest.md), [03 seções C e D](03-teste-hipoteses.md), [erros-e-correcoes](erros-e-correcoes.md), `scoring.py`, `loader.py`, `backtest.py`, os três arquivos de teste, `app.py` (só grep).
> Rodado: `pytest` (27 passed, venv limpo com pandas 3.0.5); o motor real via `calibrate`/`score_open_deals` para (a) refazer a curva do F2 contando os deals abertos como vivos, (b) refazer os três cortes do backtest incluindo os deals que nunca fecharam, (c) 33 cortes semanais de abril a novembro com um baseline extra, "mais novo primeiro". Os três cortes do 05 reproduzem exatamente (46,7 / 37,6 / 40,3), então o motor é determinístico e os números abaixo são comparáveis.

## Resumo

O guard de leakage está certo e a suavização do F1 faz o que promete. O problema está no **braço direito do U** (91–138 = 100): ele é um artefato de três causas empilhadas, e é ele que domina a fila de segunda-feira (58 dos 60 deals do topo de Agir em 31/12). O backtest não pega isso porque só avalia deals que **depois fecharam**, e compara contra um baseline (valor) que para uma métrica de tempo é o mesmo que sortear. Contra "mais novo primeiro" a fila empata ou perde. Nada disso é bug de linha; é método. Os detalhes de código são poucos e pequenos.

---

## BLOQUEIA

### B1. O F2 = 100 em 91–138 não vem dos dados. Vem de três artefatos, e 65% da fila de Agir está apoiada nele

**Onde:** `solution/src/lead_scorer/scoring.py:44-46` (faixa fina `(121, None)`), `:120` (`wall = max`), `:127-131` (vivos = só fechados), `:141-144` (regra do pico); `04-logica-do-score.md`, tabela "Degraus do F2" e frase "A curva é calculada dos dados na hora de rodar".

**(a) Tautologia da última faixa.** `wall` é o máximo de `days` entre os fechados. Logo, na faixa `121–wall`, "vivos no início" é por definição igual a "decididos na faixa" (193 = 193 no seu próprio quadro). `por_dia` vira `1 / comprimento = 1/18 = 5,56%`, dividido pelos 2,79% de referência dá 199, cortado em 100. Qualquer CSV em que `wall − 121 < 36` produz 100 nesse degrau, independente do que os deals fizeram. A regra "a zona recebe a atenção do seu trecho mais decisivo" (`:143`) garante que essa faixa tautológica manda na zona inteira 91–138. A afirmação do 04 de que "se o CSV mudar, os degraus mudam" é falsa para esse braço. E `tests/test_invariants.py:41` (`z["91–parede"] == 100`) testa a tautologia como se fosse propriedade dos dados.

**(b) Censura à direita ignorada.** "Decididos ÷ vivos" conta como vivos só os deals que **fecharam**. Os 1.589 deals abertos em Engaging (188 em 91–138, 1.291 além de 138) estavam vivos em cada idade e nunca entram no denominador. Contando-os (estimador tipo Kaplan-Meier, censura administrativa em 31/12):

| Faixa | por dia, só fechados (04) | por dia, com abertos vivos |
|---|---|---|
| 0–7 | 2,63% | 2,13% |
| 8–14 | 3,76% | 2,89% |
| 15–30 | 0,57% | 0,41% |
| 31–60 | 0,53% | 0,37% |
| 61–90 | 1,81% | 1,20% |
| 91–120 | 2,86% | 1,37% |
| 121–138 | 5,56% | 0,68% |

**(c) Truncagem à esquerda que o 03 registrou e o 04 esqueceu.** "Nenhum `close_date` antes de 2017-03-01" (03, H5). Um deal engajado em novembro de 2016 só pode ter duração ≥ 100 dias, por construção do dataset. Cruzando mês de engajamento × faixa de duração: as coortes de out/2016 a fev/2017 põem **512 dos 1.358 deals (38%) da zona 91–138** e 331 dos 1.621 de 61–90; out e nov/2016 têm 109 deals, **todos** em 91–138. O 03 fez a tabela "só engajados a partir de 2017-03-01" exatamente por isso; o 04 calibrou nos 6.711.

**Juntando (b) e (c)** (vivos = fechados + abertos, só coortes engajadas ≥ 01/03, degrau = pico ÷ referência, como o código faz): 0–14 = 100 · 15–60 = 18 · 61–90 = 48 · **91–138 = 46**. O braço direito é uma corcova de metade da altura, não uma parede de 100.

**Efeito no produto.** Em 31/12: 195 dos 298 deals de Agir têm F2 = 100, 188 deles por "última janela". O top 20% (60 deals) é 58 última janela + 2 janela crítica. A fila que o vendedor abre na segunda é "deals de 91–138 dias, ordenados por preço e encaixe". No backtest, em T = 01/07 e T = 01/10, **todos** os deals que estavam em 91–138 (203 e 194) nunca fecharam até 31/12; em 33 cortes semanais, um deal em 91–138 tem desfecho em 14 dias em 14% das vezes (0% em 10 dos 33 cortes), contra 35–38% na zona 0–14. A frase do card (`scoring.py:239-240`, "nenhum passou de 138") diz ao vendedor uma coisa falsa: 1.291 passaram.

**O que eu faria.** (1) Estimar a curva com todos os deals no conjunto de risco (fechados + abertos em Engaging), só coortes engajadas a partir de 01/03. (2) Degrau da zona = taxa média da zona, não pico de faixa fina; se quiser manter pico, nunca deixar a última faixa (a que termina na parede) definir nada. (3) Teste com dados sintéticos: durações uniformes têm que dar curva plana; hoje dão 100 na última faixa. (4) Reescrever a frase de 91–138 com o que os dados sustentam: "nenhum deal do histórico fechou depois de 138 dias; 1.291 abertos já passaram disso".

> **Resposta — aceito, corrigido (commit "fix(B1)").** Os três artefatos estavam lá. O que mudou em `calibrate`:
> 1. **Conjunto de risco com censura:** `calibrate(closed, products, open_deals=...)` — os abertos em Engaging entram como censurados na data de referência; hazard = desfechos ÷ dias de exposição (estimador atuarial, não "vivos no início ÷ comprimento").
> 2. **Coorte:** só deals engajados a partir do primeiro `close_date` do histórico (2017-03-01, derivado dos dados, não decorado). 5.739 fechados + 1.376 censurados.
> 3. **Degrau da zona = média de exposição da zona ÷ média de 0–14.** O pico de faixa fina saiu; a última faixa não define mais nada (D3 resolvido junto: mesma escala nos dois lados).
> 4. Frase de 91–138 e de Decidir reescritas com números calculados: "nenhum do histórico fechou depois de 138, e 1.291 abertos já passaram disso sem fechar" (D2).
>
> **Resultado:** 0–14 = 100 · 15–60 = 15 (piso 35) · 61–90 = 48 · **91–138 = 38** (era 100). Bate com os 46 do revisor pelo pico; pela média fica 38. Sem censura, mesma coorte, o braço volta a 100 — a tautologia era a censura.
>
> **Sobre o teste sintético:** o pedido foi "durações uniformes → curva plana". Isso não é verdade para um hazard: se todo mundo fecha até o dia M, quem chega vivo a M−1 fecha com certeza, e o hazard sobe por definição — uniforme só dá curva plana em *densidade*, que não é o que o F2 mede. O caso plano de um hazard é **hazard constante = durações geométricas**. Escrevi dois testes: `test_hazard_constante_da_curva_plana` (geométricas com censura → todas as zonas ≥ 85, por_dia entre 1,6% e 2,4%) e `test_censura_derruba_a_ultima_faixa` (sem os abertos, a última zona satura em 100; com eles, < 60). O `z["91–parede"] == 100` que testava a tautologia foi removido.
>
> **Efeito na fila de 31/12:** top 20% de Agir passou de "58 última janela + 2 janela crítica" para 7 janela crítica / 3 vale / 20 de 61–90 / 30 de 91–138. Os 188 de 91–138 saíram do topo e ficaram misturados por encaixe e valor. O 04 foi reescrito nessa seção.

### B2. O backtest só avalia deals que depois fecharam. A censura afeta os três cortes, não só o de 01/10

**Onde:** `solution/analysis/backtest.py:44` (`eval_set = closed[...]`); `05-backtest.md`, "Ressalvas do método", primeiro item.

Em cada T, o app teria mostrado também os deals que estavam em Engaging e **nunca fecharam** até 31/12. Eles ficam fora da avaliação. Quantos: 723 em 01/07, 1.301 em 15/08, 1.479 em 01/10, contra 983 / 983 / 955 avaliados. Não são deals "além da parede" que cairiam em Decidir: em T tinham 0–138 dias de idade (61 / 183 / 45 em janela crítica; 203 / 199 / 194 em última janela). Estavam na fila de Agir, no topo, e o backtest fingiu que não existiam. É sobrevivência, e o resultado desses deals na métrica da fila é conhecido: zero.

Refazendo os três cortes com eles (desfecho = 0 se não fechou até 31/12):

| | T=01/07 | T=15/08 | T=01/10 | Média |
|---|---|---|---|---|
| Top 20% da fila (05, só quem fechou) | 46,7% | 37,6% | 40,3% | **41,5%** |
| Top 20% da fila, com os que nunca fecharam | 27,0% | 15,9% | 22,4% | **21,8%** |
| Média do grupo, idem | 9,7% | 16,3% | 6,6% | **10,9%** |
| Ordenar por valor, idem | 10,3% | 17,6% | 6,8% | **11,6%** |

Sobre o grupo a fila ainda faz ~1,6× (não "o dobro"); mas veja B3 para o baseline que importa.

**O que eu faria.** População de avaliação = todos os deals em Engaging em T (fechados depois **ou** ainda abertos em 31/12), desfecho binário "fechou até T+14". Restringir T ≤ 17/12 para a janela de 14 dias ser observável. E cortes semanais, não três (ver I1).

> **Resposta — aceito, corrigido (commit "fix(B2,B3,I1)").** População = todos os deals em Engaging em T (fecharam depois **ou** nunca fecharam até 31/12), desfecho = fechou até T+14, quem nunca fechou conta zero; T ≤ 17/12. Nos três cortes da v1: 46,7 → 27,0%, 37,6 → 13,4%, 40,3 → 28,7%. Bate com os seus 27,0 / 15,9 / 22,4 (a diferença é a curva do B1, que agora está no motor). O "o dobro" da v1 era sobrevivência e saiu do 05.

### B3. O baseline "ordenar por valor" não é baseline para uma métrica de tempo. Contra "mais novo primeiro" a fila empata ou perde

**Onde:** `backtest.py:53-66` e `:88`; `05-backtest.md`, tabela (a) e "Decisão", item 1.

Valor do produto não tem relação com *quando* o deal se decide: 21,7% vs 20,3% do grupo é sortear. A fila é 55% idade; o baseline honesto é ordenar por `engage_date` decrescente (o vendedor consegue fazer isso no CRM sem ferramenta nenhuma). Na **própria população do 05**:

| | T=01/07 | T=15/08 | T=01/10 | Média |
|---|---|---|---|---|
| Top 20% da fila (05) | 46,7% | 37,6% | 40,3% | 41,5% |
| Top 20% "mais novo primeiro" | 60,9% | 25,4% | 56,0% | **47,4%** |

Em 33 cortes semanais: só quem fechou, fila 41,2% vs mais-novo 38,3% (fila ganha em 20 de 33); com os que nunca fecharam, fila **21,8%** vs mais-novo **25,2%** (fila ganha em 14 de 33). O ganho da fila sobre "ordenar por data de engajamento" é ≤ 3 pp e troca de sinal conforme o corte. O que a fila acrescenta sobre esse baseline é precisamente o braço direito do U, e ele (B1) é o que puxa a fila para baixo nos cortes de outubro e novembro, quando 71–84% do topo está em 91–138.

Ainda no método: a métrica "desfecho em 14 dias" é a mesma taxa que calibra o F2. O backtest verifica se a curva de hazard generaliza fora do período (verifica, no braço esquerdo). F1 e F3 **não conseguem** mover essa métrica por desenho (encaixe e preço não são sinais de tempo). Logo a grade 35 / 20 / 0 medida com `dec14` era não-informativa por construção; "o backtest é indiferente ao peso do F1" não é evidência sobre o F1, é consequência da métrica. O corte 35 → 20 se apoia só no AUC 0,515 do 03-D, e o 05 deveria dizer isso em vez de "as duas rodadas dizem a mesma coisa".

**O que eu faria.** Reportar fila vs "mais novo primeiro" vs F2 sozinho, na população do B2, em cortes semanais. Para F1 e F3 usar uma métrica que eles possam afetar (ex.: valor ganho em 90 dias pelo top 20%).

> **Resposta — aceito, corrigido.** Baselines agora: mais novo primeiro (`engage_date` desc), F2 sozinho, valor, grupo. Em 37 cortes semanais com população completa: fila 24,7% (12–50), mais novo 24,4% (12–48), fila vence em 19 / 37 — empate. Contra valor e acaso, ~1,6× em 29–31 / 37. O 05 v2 escreve isso na leitura principal: o sinal de tempo da fila é o que a data de engajamento já dá.
>
> Sobre F1 e F3: aceito integralmente. O 05 agora diz que a métrica de 14 dias não consegue medi-los (grade 55/20/25 → 100/0/0 varia dentro do ruído; 0/50/50 cai ao acaso), que "as duas rodadas dizem a mesma coisa" era falso, e que o peso 20 do F1 fica **só** pelo AUC 0,515 do 03-D. A métrica que os validaria (valor ganho em 90 dias pelo top 20%) fica registrada como trabalho não feito — não a rodei.

---

## IMPORTANTE

### I1. Os fechamentos têm estrutura de calendário; três cortes escolhidos à mão não dão para decidir nada, e o "corte de 15/08 que foge do padrão" tem explicação

**Onde:** `backtest.py:31` (`CORTES`); `05-backtest.md`, "Ruído" e item 4 de "O que a primeira rodada disse".

Fechamentos entre 02/07 e 15/07: 299 deals, **100% com ≤ 14 dias de idade**; entre 02/10 e 15/10: 269, também 100%. Entre 16/08 e 29/08: 69 / 64 / 136 / 76 nas quatro zonas. As coortes engajadas em abril, julho e outubro são majoritariamente curtas (505, 530, 497 deals em 0–14 contra ~100 nas outras faixas); a dataset é sintética e engaja/fecha em blocos. Os dois cortes onde a fila brilha (01/07 e 01/10) caem em semanas em que **só deal novo fecha**, o que qualquer regra "novo primeiro" acerta; o de 15/08 é onde o braço direito trabalhou (e "mais velho primeiro" faz 53,8% ali). "Não sei o motivo" no 05 é isso. Também: os cortes se sobrepõem (538 deals em comum entre 01/07 e 15/08; 197 entre 15/08 e 01/10), então o "≈ 2 pp na média dos três" assume independência que não existe.

**O que eu faria.** Cortes semanais, reportar mediana e amplitude; registrar em Limitações que o padrão de calendário é da dataset, não do negócio.

> **Resposta — aceito, corrigido.** 37 cortes semanais (03/04 a 11/12), resumo por mediana e amplitude, tabela por corte no 05. A explicação do 15/08 e dos blocos de fechamento (02–15/07 e 02–15/10 com 100% de deals ≤ 14 dias) está na seção "Estrutura de calendário" do 05 e vai para as Limitações do README como padrão do dataset, não do negócio. A média dos três cortes com "≈ 2 pp de ruído" saiu.

### I2. Peso 20 do F1 e o rótulo "Confiança" contam uma história que a evidência não sustenta

**Onde:** `scoring.py:312-317` (confiança por n da célula); `04`, seção "Confiança"; `03-D` (AUC 0,515).

Fora do período o encaixe vendedor × produto quase não ordena (AUC 0,515; vendedor + produto sem idade, 0,528). Mesmo assim o card mostra "Você fecha GTX Basic em 47 de 59 (80%) — bem acima da média" com rótulo **Alta** para 154 dos 298 deals de Agir. O rótulo mede tamanho de amostra de um fator que pesa 20% e não generaliza; o fator que decide a ordem (F2, 55%) não tem confiança nenhuma e é o que carrega o artefato do B1. Para o vendedor "Confiança Alta" lê-se "esse score é confiável", que é o contrário do que os dados dizem.

**O que eu faria.** Ou tirar o F1 do número (a grade com 75 / 0 / 25 deu o mesmo resultado; a frase de histórico continua no card como contexto, que é o que o 04 já diz que ele é), ou validar o F1 com uma métrica que ele possa mover. Renomear "Confiança" para "base do histórico" ou calcular a confiança a partir do que manda no score.

> **Resposta — aceito na parte do rótulo, corrigido (commit "fix(I2,I3)"); a parte do peso fica como está, e digo por quê.** "Confiança" virou **base do histórico** (`base_historico`: ampla / média / pequena), no motor, no CSV, no app (com *help* dizendo que é amostra do F1, não confiança no score) e no 04. Sobre tirar o F1 do número: o 05 v2 registra que o backtest não mede F1 e que o peso 20 fica só pelo AUC 0,515 — é a mesma evidência que você cita. A decisão de manter 20 em vez de 0 é de produto (a frase de histórico com um número que pesa algo é mais honesta com o vendedor do que uma frase que pesa zero) e está marcada como não validada. Se a decisão final do 05 for tirar, é um número na config.

### I3. A fila de Agir é, na prática, ordem por zona; F1 e F3 só desempatam. A de Engajar é ordem por preço

**Onde:** `scoring.py:301` e `:304`; `04`, "Pesos" e "Categorias de ação".

Degraus 100 / 65 / 35 × 0,55 = saltos de 19,3 e 16,5 pontos; F1 real vai de 8 a 85, ou seja ≤ 15,4 pontos. Em 31/12, só **2,3%** dos pares entre zonas diferentes (527 de 22.735) têm a ordem de zona invertida por F1 + F3; o primeiro deal de 61–90 aparece na posição 158 e o primeiro do vale na 230 de 298. Isso explica por que a grade do 05 é plana: os pesos quase não importam. Não é bug, mas o 04 deveria dizer "a ordem é zona, depois preço, depois encaixe" em vez de apresentar três fatores ponderados. Em Engajar (500 deals, F3 = 55% do peso), 92% dos pares estão na mesma ordem que `sales_price`; o F1 ordena 53% (moeda). O README do challenge diz "não é só ordenar por valor"; a lista de Engajar é.

**O que eu faria.** Escrever isso nas Limitações; em Engajar, admitir que sem data não há sinal e a lista é de valor.

> **Resposta — aceito, escrito no 04 — com um número diferente do seu, porque a correção B1 mudou a fila.** Com o braço direito em 100 a ordem era zona → preço → encaixe (2,3% dos pares entre zonas invertidos, como você mediu). Com a curva corrigida (48 / 38 / 35 fora da janela crítica), 33% dos pares entre zonas são invertidos por F1 + F3, e fora da janela crítica **a ordem segue o preço em 91% dos pares**. O 04 agora diz: Agir = janela crítica → preço → encaixe → zona; Engajar = lista de valor (92% dos pares em ordem de preço), com o encaixe desempatando — e a legenda do app diz o mesmo.

### I4. Não existe README com Setup / Lógica / Limitações

**Onde:** `submissions/guilherme-fraga/` e `solution/` (não há README.md em nenhum dos dois; `git ls-files` confirma). O challenge lista os três como obrigatórios e o 05 diz "isso vai para o README como a evidência de que a ferramenta funciona". Se o README for escrito com o "41,5% vs 21,7%, o dobro", vai carregar B2 e B3.

> **Resposta — aceito; fica para o fechamento.** O README (Setup / Lógica / Limitações) é a última etapa, depois da decisão do 05 v2 — exatamente para não carregar o "41,5% vs 21,7%". O que ele vai poder afirmar é o que o 05 v2 sustenta: ~1,6× sobre valor e acaso, empate com "mais novo primeiro", e o que a métrica não mede.

---

## DETALHE

### D1. Engaging sem `engage_date` derruba o scorer
`scoring.py:291` dá `age = None`; `:299-301` entra em Agir e faz `cfg.w_f2 * None` → `TypeError`; `:307` faria `None <= 14`. Idade negativa (engage_date > referência) faz `zone_for` devolver `None` e `:228` quebra. O CSV atual não tem nenhum dos dois casos (0 Engaging sem data), então é latente. Eu roteava para Engajar com frase própria, ou levantava `ValueError` com mensagem, e testava com uma linha sintética.

> **Resposta — aceito, corrigido (commit "fix(D1,D4–D7)").** Engaging sem `engage_date` vai para **Engajar** com frase própria ("Engaging sem data de engajamento no CRM… preencha a data para entrar na fila de Agir"); `engage_date` depois da referência levanta `ValueError("Idade negativa…")`. Os dois testados com linha sintética em `test_invariants.py`.

### D2. Frases hard-coded contradizem "a curva não é hard-coded"
`scoring.py:230` "Metade das perdas acontece até o dia 14" (50,5% no total; 56,4% pós-março), `:239` "80% dos que fecham já fecharam aos 90" (79,8%; 85,3% pós-março), `:240` "nenhum passou de {wall}" (falso, ver B1). Calcular de `calib` ou reescrever.

> **Resposta — aceito, corrigido no bloco B1.** As três frases saíram do código como texto fixo e viraram números de `calib.notes`, calculados na coorte: "56% das perdas acontecem até o dia 14", "85% dos que fecham já fecharam aos 90 dias", e "nenhum do histórico fechou depois de 138; 1.291 abertos já passaram disso sem fechar". Exemplos no 04 atualizados.

### D3. Normalização inconsistente no F2
`scoring.py:137-138` usa a **média** da zona 0–14 como referência; `:143` usa o **pico** da faixa fina como numerador. A zona 0–14 sai ≥ 100 por construção (3,76 / 2,79 = 135). Média dos dois lados, ou pico dos dois.

> **Resposta — aceito, corrigido no bloco B1.** Média dos dois lados: `F2(zona) = por_dia(zona) ÷ por_dia(0–14)`, ambos como desfechos ÷ exposição da zona inteira. A zona 0–14 sai 100 por definição (é a escala), não "≥ 100 cortado".

### D4. Testes fixam números do dataset, não propriedades
`test_invariants.py:41-46` afirma `91–parede == 100` (tautologia, B1a) e `f2_curva["15–60"] == 20`. Nenhum teste com pipeline sintético que provaria que a curva responde aos dados (durações uniformes → plana). `backtest.py` não tem teste nenhum; faltaria pelo menos "calibração nunca vê `close_date ≥ T`" e "avaliação inclui deals ainda abertos em 31/12" (B2).

> **Resposta — aceito, corrigido.** Os testes de número (`91–parede == 100`, `f2_curva["15–60"] == 20`) saíram no B1 e viraram propriedades: 0–14 é a escala, a última zona não satura, censura derruba a última faixa, hazard constante dá curva plana (sintético). Novo `tests/test_backtest.py`: calibração nunca vê `close_date ≥ T`; população inclui quem nunca fechou e quem fechou depois de T, sem colunas de leakage; quem nunca fechou conta zero; a janela de 14 dias cabe antes de 31/12; o empate esperado do baseline por valor dá o número certo num caso à mão. 35 testes.

### D5. Exemplo de frase errado no 04
"GTX Pro: 4º produto mais caro dos 7": é o 3º (GTK 500, GTX Plus Pro, GTX Pro). O código diz 3º; o doc não.

> **Resposta — aceito, corrigido.** "3º produto mais caro dos 7" no 04 (o código já dizia 3º).

### D6. Rótulo "vale 20" na config antiga
`backtest.py:36` e tabela (a) do 05: com `vale_minimo=0` a curva calibrada em cada T dá 23 / 17 / 20, não 20. Inofensivo (o top 20% não enxerga o vale), mas o rótulo é aproximado.

> **Resposta — aceito, corrigido na v2 do backtest (bloco B2).** A configuração antiga é rotulada "vale da curva" (`vale_minimo=0`), sem número fixo.

### D7. Dois `if __name__ == "__main__"` no backtest
`backtest.py:204-206` e `:226-227`, com `dias_ate_a_perda` definido entre eles. Funciona pela ordem de execução do módulo; um `main()` só. `win_rate_topo_por_valor = taxa_topo_por_valor` (`:69`) é alias sem função.

> **Resposta — aceito, corrigido na v2 do backtest.** Um `main()` só; o alias `win_rate_topo_por_valor` saiu.

---

## O que está certo (e eu tentei derrubar)

- **Leakage de `close_value` / `close_date`.** `split_pipeline` descarta as colunas (`loader.py:74-78`), `score_open_deals` recusa se chegarem (`scoring.py:276-278`), os três testes do 04 existem e o regex contra `today()/now()` fecha a porta da data de hoje (`test_leakage.py:56-59`). `close_value` não aparece em lugar nenhum do scoring. No backtest, `calib_set` usa `close_date < T` estrito (`backtest.py:43`) e a avaliação força `deal_stage = "Engaging"` e derruba as colunas (`:49`). Não achei vazamento.
- **Suavização K1 = K2 = 50.** Rosalina Dieter / GTK 500, 5 de 6 (83%), sai com F1 = 61,9 e "Baixa"; Niesha / GTX Pro, 2 de 14, sai em 8, não em 0. Célula pequena não manda. Isso o teste `test_celula_pequena_nao_manda` cobre de verdade.
- **F3 em log** é a escolha certa para esse catálogo, e o código de rank/frase está correto.
- **Parede de 138 como categoria Decidir.** Nenhuma coorte tem fechado com mais de 138 dias, inclusive as engajadas depois de 15/08 (máximo 134), então a parede é propriedade do dado e não da truncagem. Ordenar Decidir por valor para o manager é a decisão certa.
- **Troca da métrica** (win rate → desfecho em 14 dias) foi correção legítima para uma fila. O que falhou foi população (B2) e baseline (B3), não a métrica.
- **Piso 35 no vale** está documentado como decisão de produto, com `f2_curva` preservado. Honesto.
- **Setup roda**: `pip install` das três dependências e `pytest` passam em venv limpo; o app sobe no `AppTest`.

## Se eu tivesse que ordenar o conserto

1. B1 (curva com censura + coorte ≥ 01/03, sem pico na última faixa) — muda a fila de segunda-feira.
2. B2 + B3 + I1 juntos (população completa, baseline "mais novo primeiro", cortes semanais) — muda o que o README pode afirmar.
3. I2 (confiança) e I4 (README) — antes de entregar.
4. D1–D7 quando der.
