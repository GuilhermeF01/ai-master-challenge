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
