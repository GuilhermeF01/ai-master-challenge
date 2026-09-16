# Auditoria dos dados — antes do scoring

> Verificação das "Suspeitas sobre os dados" listadas em [01-hipoteses.md](01-hipoteses.md).
> Feita com `csv` da stdlib do Python (sem dependências). Só números, sem interpretação.

Volumes: `accounts` 85 · `products` 7 · `sales_teams` 35 · `sales_pipeline` 8.800.

---

## S1 — Inconsistências em `accounts.sector`

| Valor | Contas |
|---|---|
| retail | 17 |
| technolgy | 12 |
| medical | 12 |
| marketing | 8 |
| finance | 8 |
| software | 7 |
| entertainment | 6 |
| telecommunications | 6 |
| services | 5 |
| employment | 4 |

Outros campos de `accounts`:

| Verificação | Resultado |
|---|---|
| `office_location` = "Philipines" | 1 conta |
| `office_location` = "United States" | 71 / 85 |
| Nomes de conta duplicados | 0 |
| Nomes de conta com espaço sobrando | 0 |

---

## S2 — Nome de produto: `sales_pipeline` × `products`

| Produto no pipeline | Linhas | Existe em products.csv? |
|---|---|---|
| GTX Basic | 1.866 | sim |
| MG Special | 1.651 | sim |
| GTXPro | 1.480 | **não** (products tem "GTX Pro") |
| MG Advanced | 1.412 | sim |
| GTX Plus Basic | 1.383 | sim |
| GTX Plus Pro | 968 | sim |
| GTK 500 | 40 | sim |

Join direto perde 1.480 linhas (16,8%).

---

## S3 — Deals abertos sem `account`

| Stage | Total | Com account | Account vazio |
|---|---|---|---|
| Prospecting | 500 | 163 | 337 |
| Engaging | 1.589 | 501 | 1.088 |
| Won | 4.238 | 4.238 | 0 |
| Lost | 2.473 | 2.473 | 0 |

Abertos: 2.089; sem account: 1.425 (68,2%). Accounts do pipeline fora de `accounts.csv`: 0.

---

## S4 — `close_value` por stage

| Stage | Vazio | Zero | Preenchido |
|---|---|---|---|
| Prospecting | 500 | 0 | 0 |
| Engaging | 1.589 | 0 | 0 |
| Won | 0 | 0 | 4.238 |
| Lost | 0 | 2.473 | 0 |

---

## S5 — Datas

| Stage | `engage_date` preenchido | min | max | `close_date` preenchido | min | max |
|---|---|---|---|---|---|---|
| Prospecting | 0 / 500 | — | — | 0 / 500 | — | — |
| Engaging | 1.589 / 1.589 | 2016-11-03 | 2017-12-22 | 0 / 1.589 | — | — |
| Won | 4.238 / 4.238 | 2016-10-20 | 2017-12-27 | 4.238 / 4.238 | 2017-03-01 | 2017-12-31 |
| Lost | 2.473 / 2.473 | 2016-11-04 | 2017-12-22 | 2.473 / 2.473 | 2017-03-01 | 2017-12-31 |

| Verificação | Resultado |
|---|---|
| Última data nos dados | 2017-12-31 |
| Primeira data nos dados | 2016-10-20 |
| Casos com `close_date < engage_date` | 0 |

---

## Extras que apareceram de passagem

| Verificação | Resultado |
|---|---|
| `opportunity_id` duplicado | 0 |
| Agentes do pipeline fora de `sales_teams` | 0 |
| Agentes em `sales_teams` com 0 deals | 5 (Carl Lin, Carol Thompson, Elizabeth Anderson, Mei-Mei Johns, Natalya Ivanova) |
| Contas com `subsidiary_of` preenchido | 15 / 85 |
| Empresas-mãe distintas | 7 (Acme Corporation 4, Sonron 3, Bubba Gump 2, Inity 2, Golddex 2, Massive Dynamic 1, Warephase 1) |
| Empresas-mãe que também são contas | 7 / 7 |
