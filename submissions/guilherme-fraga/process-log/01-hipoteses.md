# Hipóteses — registradas antes de qualquer análise

> Escritas antes de abrir os CSVs para análise. O campo `Status` foi preenchido depois, com o resultado do teste (números em [03-teste-hipoteses.md](03-teste-hipoteses.md)).

## H1. Deal que já está engajado (Engaging) fecha mais fácil que Prospecting.

- **Status:** não testável — não existe deal fechado sem passar por Engaging (6.711/6.711 fechados têm `engage_date`; 0 Prospecting fechou sem engajar), então não há contrafactual.

## H2. Os vendedores têm performance bem diferente entre si — quem vende importa.

- **Status:** confirmada, mas fraca — spread de 15,4 pp (70,4% vs 55,0%), mas a maioria fica entre 60% e 67% (mediana 63,6%, desvio 3,6 pp). Entra no score com peso médio, suavizando quem tem poucos deals.

## H3. Conta grande, com mais receita, fecha mais.

- **Status:** derrubada — 1,9 pp entre quartis de revenue e 1,5 pp entre quartis de employees, sem ordem monotônica.

## H4. O setor da conta pode influenciar.

- **Status:** derrubada — 3,7 pp entre o melhor (marketing) e o pior (finance) setor; menos de 5 pp não entra.

## H5. Deal parado há muito tempo, mesmo em Engaging, provavelmente está fora — não vale mais o esforço.

- **Status:** derrubada do jeito que foi escrita — dentro da janela, idade é sinal **bom**, não ruim (0–7 dias: 53,5% → 121+ dias: 75,6%; mediana Lost 14 dias vs Won 57): quem perde, perde cedo. Mas o achado dos 138 dias confirma o espírito: nenhum deal fechou depois de 138 dias em Engaging e a mediana dos abertos é 165. Deal velho não é "menos chance", é "sem precedente" — passou de 138 não vale esforço, vale decisão. Vira categoria própria no produto.

## H6. Região/manager influencia na venda.

- **Status:** derrubada — 1,4 pp entre regiões e 2,3 pp entre managers.

## H7. Conta que já comprou antes compra mais fácil de novo.

- **Status:** derrubada — 10,7 pp na direção oposta (sem Won anterior 72,1% vs com Won anterior 61,4%); 5,3 pp pós-cut com n=126. Artefato registrado: `close_date` só começa em 2017-03-01, então os 972 deals engajados antes disso não podiam ter Won anterior por construção — o grupo "sem Won anterior" é quase todo esse artefato.

---

## Suspeitas sobre os dados

Coisas a verificar **antes** de qualquer score, a partir de uma olhada rápida no `head` dos CSVs (resultados em [02-auditoria-dados.md](02-auditoria-dados.md)):

- Vi `technolgy` escrito errado em `accounts.sector`; quero saber quantas inconsistências desse tipo existem.
- Se o nome do produto bate entre `sales_pipeline` e `products` (o join pode perder linha).
- Quantos deals abertos estão sem `account`.
- `close_value` em deal aberto: está vazio, zero ou preenchido?
- O dataset é de 2016-2017. Qualquer conta de "dias parado" não pode usar a data de hoje. Quero saber qual é a última data que existe nos dados.
