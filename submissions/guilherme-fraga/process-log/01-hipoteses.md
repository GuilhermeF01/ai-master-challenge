# Hipóteses — registradas antes de qualquer análise

> Escritas antes de abrir os CSVs para análise. O campo `Status` é preenchido depois, com o resultado do teste.

## H1. Deal que já está engajado (Engaging) fecha mais fácil que Prospecting.

- **Status:** a testar

## H2. Os vendedores têm performance bem diferente entre si — quem vende importa.

- **Status:** a testar

## H3. Conta grande, com mais receita, fecha mais.

- **Status:** a testar

## H4. O setor da conta pode influenciar.

- **Status:** a testar

## H5. Deal parado há muito tempo, mesmo em Engaging, provavelmente está fora — não vale mais o esforço.

- **Status:** a testar

## H6. Região/manager influencia na venda.

- **Status:** a testar

## H7. Conta que já comprou antes compra mais fácil de novo.

- **Status:** a testar

---

## Suspeitas sobre os dados

Coisas a verificar **antes** de qualquer score, a partir de uma olhada rápida no `head` dos CSVs:

- Vi `technolgy` escrito errado em `accounts.sector`; quero saber quantas inconsistências desse tipo existem.
- Se o nome do produto bate entre `sales_pipeline` e `products` (o join pode perder linha).
- Quantos deals abertos estão sem `account`.
- `close_value` em deal aberto: está vazio, zero ou preenchido?
- O dataset é de 2016-2017. Qualquer conta de "dias parado" não pode usar a data de hoje. Quero saber qual é a última data que existe nos dados.
