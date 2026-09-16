# Erros e correções

> Toda vez que a IA propôs algo e eu corrigi. Cada entrada tem o que foi proposto, a correção e a causa raiz — o motivo pelo qual a proposta saiu errada, não só o que mudou.

## 1. Fator 2 media probabilidade de ganhar, não necessidade de atenção

- **Etapa:** [04-logica-do-score.md](04-logica-do-score.md), primeira versão (aprovação manual em [screenshots/01](screenshots/01-aprovacao-manual-logica-do-score.png)).
- **Proposta da IA:** F2 = win rate condicional pela idade do deal (dos fechados que ainda estavam abertos nessa idade, quantos ganharam). Deal de 9 dias tirava ~17, deal de 120 dias tirava 100. Como a própria IA notou a tensão com os deals novos, colou um marcador "janela crítica" por cima em vez de repensar o fator.
- **Correção:** o score é **fila de atenção**, não probabilidade. Metade das perdas acontece até o dia 14 — é ali que o esforço muda o resultado. Deal de 120 dias que sobreviveu fecha com ou sem empurrão. F2 vira **necessidade de atenção em U**: alto nos primeiros 14 dias (onde se perde), médio de 15 a 90 (follow-up normal), alto de novo de 90 a 138 (última janela antes da parede — 80% dos que fecham já fecharam aos 90). Degraus calibrados pela curva dos fechados.
- **Causa raiz:** a IA respondeu "onde é mais provável ganhar" quando a pergunta era "onde o meu tempo faz diferença". Otimizou a métrica estatisticamente mais limpa (win rate condicional é a resposta correta para *probabilidade*) e perdeu o objetivo declarado no topo do próprio documento ("fila de atenção, não probabilidade"). O marcador foi sintoma: a IA viu a contradição e a tratou como detalhe de interface, não como erro de modelagem.

## 2. K2 = 30 deixava célula de 14 deals zerar o fator

- **Etapa:** mesma versão do `04`.
- **Proposta da IA:** K2 = 30 (célula pesa 50% com 30 deals). O próprio exemplo mostrado — Niesha Huffines / GTX Pro, 2 de 14 — caía a F1 = 0. A IA ofereceu K2 = 50 como "alternativa conservadora" em vez de recomendá-lo.
- **Correção:** K2 = 50. Com isso a mesma célula vai a F1 = 8 (50,5% suavizado); célula pesa 17% com 10 deals, 38% com 30, 67% com 100.
- **Causa raiz:** a IA calibrou K2 para bater com o corte n ≥ 30 usado na análise (uma conveniência da tabela anterior), e não contra o critério que eu tinha dado em palavras — "não quero célula de 10 deals mandando no score". Testou o exemplo, viu que violava o critério, e mesmo assim manteve a proposta e empurrou a decisão de volta.

## 3. Categoria "Decidir" sem ordem definida

- **Etapa:** mesma versão do `04`.
- **Proposta da IA:** "Decidir" sem score de fila e sem critério de ordenação.
- **Correção:** ordenar por **valor** (`sales_price`) decrescente, desempate por idade decrescente, para o manager limpar os grandes primeiro.
- **Causa raiz:** a IA tratou "sai da fila normal" como "não precisa de ordem". Uma lista de 1.291 deals sem ordem não é uma lista de decisão — é uma pilha. Faltou perguntar quem consome essa lista (o manager) e o que ele faz com ela.

## 4. `git add -f` em diretório arrastou `__pycache__` para o commit

- **Etapa:** commit do motor (`aff9516`), parte 1 do build.
- **O que aconteceu:** a IA rodou `git add -f solution/src solution/tests` (diretórios). O `-f` existe porque o `.gitignore` raiz ignora `submissions/`, mas ele também passa por cima do `.gitignore` da própria pasta — e levou 5 arquivos `.pyc` junto. Corrigido em commit separado (`64affb6`, `git rm --cached`), sem amend.
- **Correção de processo:** `git add -f` só em **arquivos** novos, nomeados um a um. Nunca em diretório.
- **Causa raiz:** a IA tratou o `-f` como "necessário por causa do ignore raiz" e esqueceu que ele é global: força tudo, inclusive o que o ignore local deveria segurar. Erro de processo, não de código — conta igual.

## 5. Backtest mediu "quantos ganharam" numa fila que promete "onde a decisão está acontecendo"

- **Etapa:** [05-backtest.md](05-backtest.md), primeira rodada.
- **Proposta da IA:** medir a fila por win rate do top 20% — e concluir que "o topo da fila ganha menos que o grupo (−5,7 pp) e que ordenar por valor (−7,3 pp)", apresentando isso como o achado principal.
- **Correção:** não errado, mas errada para a fila. "Quantos ganharam" mede onde se ganha; a fila é para achar onde a decisão está acontecendo agora. Métrica certa: dos top 20%, quantos tiveram **desfecho (ganho ou perda) nos 14 dias seguintes a T**. Com ela, a fila faz o dobro de ordenar por valor (41,5% vs 21,7%).
- **Causa raiz:** a IA reproduziu o erro nº 1 um nível acima. No nº 1 ela desenhou o F2 como probabilidade; corrigido, desenhou o U — e depois avaliou o U com a métrica de probabilidade que o próprio 04 dizia não ser o objetivo. Aceitou a especificação do teste ("quantos ganharam") literalmente, viu que o resultado contradizia o desenho, e explicou a contradição em vez de questionar a métrica. O sinal de alerta estava lá: "este backtest não consegue validar a tese da atenção" — a resposta certa era propor a métrica que consegue, não registrar a limitação.

## 6. O braço direito do U era artefato — e a fila de segunda-feira estava apoiada nele

- **Etapa:** [06-revisao-externa.md](06-revisao-externa.md), B1 (revisor externo, outro modelo em sessão limpa). Aceito e corrigido no commit `fix(B1)`.
- **O que estava errado:** a curva do F2 contava como "vivos" só os deals que fecharam. Os 1.589 abertos em Engaging — vivos em cada idade, nunca fechados — ficavam fora do denominador; na última faixa (121–138) "vivos" era igual a "decididos" por definição, e o degrau saturava em 100 para qualquer CSV. Somado à truncagem à esquerda (coortes pré-2017-03 só podiam ter duração longa) e à regra do pico, 91–138 = 100 e 195 dos 298 deals de Agir tinham F2 = 100. O top 20% da fila era "58 última janela + 2 janela crítica".
- **Correção:** conjunto de risco com censura (abertos entram como censurados na referência), só coortes engajadas a partir do primeiro fechamento, degrau pela média de exposição da zona. 91–138 caiu de 100 para 38. Frases com números calculados.
- **Causa raiz:** erro de método, não de código. Uma quantidade de tempo-até-evento foi estimada só com quem teve o evento — o erro clássico de sobrevivência, que a própria auditoria (03-H5, "fato estrutural: nenhum close_date antes de 2017-03-01") já tinha sinalizado e o 04 ignorou. E a tautologia da última faixa passou porque **confirmava a hipótese**: "última janela antes da parede, alto de novo" era o que se queria ver, então 193 = 193 virou "100% dos vivos são decididos aqui" em vez de "isto não pode estar certo". O teste `z["91–parede"] == 100` fixava o artefato como propriedade.

## 7. O backtest v1 media sobreviventes contra um baseline que não compete

- **Etapa:** [06-revisao-externa.md](06-revisao-externa.md), B2 + B3 + I1. Aceito e corrigido no commit `fix(B2,B3,I1)`.
- **O que estava errado:** (a) a população de avaliação era "deals em Engaging em T **que depois fecharam**" — os que a fila mandou agir e nunca se decidiram (45% da população por corte) ficavam fora, e o resultado deles na métrica é zero por definição; (b) o baseline era "ordenar por valor", que para uma métrica de tempo é o acaso — o baseline que a fila precisa vencer é "mais novo primeiro", que o vendedor faz no CRM sem ferramenta; (c) três cortes à mão, dois deles em semanas em que só deal novo fecha. Resultado: "41,5% vs 21,7%, o dobro". Com população completa, cortes semanais e o baseline certo: 24,7% vs 24,4%, empate.
- **Correção:** população completa (quem nunca fechou conta zero), 37 cortes semanais com mediana e amplitude, baselines mais-novo-primeiro / F2 sozinho / valor / grupo. O 05 v2 diz o que sobra: ~1,6× sobre valor e acaso, empate com mais-novo-primeiro, F1 e F3 não medidos.
- **Causa raiz:** o conjunto de avaliação foi definido pelo **desfecho** ("que depois fecharam") em vez de pelo **estado em T** ("que estavam em Engaging") — sobrevivência, de novo, o mesmo erro do nº 6 aplicado à avaliação. E o baseline foi o que o pedido nomeou ("comparado com ordenar por valor"), sem perguntar qual é o baseline trivial que uma fila de tempo tem que bater. Os dois erros apontam na mesma direção: aceitar a especificação literal quando a especificação tinha um buraco de método.
