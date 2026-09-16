import csv, collections, datetime as dt, statistics
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
REF_DATE = dt.date(2017, 12, 31)

def load(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

acc, prod, teams, pipe = load("accounts.csv"), load("products.csv"), load("sales_teams.csv"), load("sales_pipeline.csv")

# ---------- correções no load ----------
n_prod_fix = 0
for r in pipe:
    if r["product"] == "GTXPro":
        r["product"] = "GTX Pro"; n_prod_fix += 1
n_sec_fix = 0
for a in acc:
    if a["sector"] == "technolgy":
        a["sector"] = "technology"; n_sec_fix += 1
prodset = {p["product"] for p in prod}
tech_accounts = {a["account"] for a in acc if a["sector"] == "technology"}
print("## Correções no load")
print(f"- GTXPro -> GTX Pro: {n_prod_fix} linhas do pipeline; produtos do pipeline fora de products.csv após correção: {sum(1 for r in pipe if r['product'] not in prodset)}")
print(f"- technolgy -> technology: {n_sec_fix} contas; linhas do pipeline dessas contas: {sum(1 for r in pipe if r['account'] in tech_accounts)}")

acc_by = {a["account"]: a for a in acc}
team_by = {t["sales_agent"]: t for t in teams}
D = lambda s: dt.date.fromisoformat(s) if s.strip() else None
for r in pipe:
    r["engage"] = D(r["engage_date"]); r["close"] = D(r["close_date"])

closed = [r for r in pipe if r["deal_stage"] in ("Won", "Lost")]
open_ = [r for r in pipe if r["deal_stage"] in ("Prospecting", "Engaging")]

def wr(rows):
    won = sum(1 for r in rows if r["deal_stage"] == "Won")
    return won, len(rows) - won, (won / len(rows) if rows else float("nan"))

def table(title, groups, first_col="Grupo", extra=None, sort=True):
    """groups: dict name -> rows. extra: dict name -> str (coluna adicional)."""
    print(f"\n### {title}\n")
    hdr = f"| {first_col} |" + (" Info |" if extra else "") + " Deals fechados | Won | Lost | Win rate |"
    print(hdr); print("|---|" + ("---|" if extra else "") + "---|---|---|---|")
    stats = []
    for name, rows in groups.items():
        w, l, p = wr(rows); stats.append((name, len(rows), p))
    if sort: stats.sort(key=lambda x: -x[2])
    for name, n, p in stats:
        w, l, _ = wr(groups[name])
        print(f"| {name} |" + (f" {extra[name]} |" if extra else "") + f" {n} | {w} | {l} | {p*100:.1f}% |")
    best, worst = stats[0], stats[-1]
    print(f"\nMelhor: **{best[0]}** ({best[2]*100:.1f}%, n={best[1]}) · Pior: **{worst[0]}** ({worst[2]*100:.1f}%, n={worst[1]}) · Diferença: **{(best[2]-worst[2])*100:.1f} pp** · Menor grupo: n={min(s[1] for s in stats)}")
    return stats

W, L, P = wr(closed)
print(f"\nBaseline: deals fechados = {len(closed)} (Won {W}, Lost {L}), win rate global = {P*100:.1f}%. Abertos excluídos: {len(open_)}.")

# ---------- H1 ----------
print("\n## H1 — Engaging vs Prospecting")
print(f"- Deals fechados com engage_date preenchido: {sum(1 for r in closed if r['engage'])} / {len(closed)}")
print(f"- Deals fechados sem engage_date (fecharam direto de Prospecting): {sum(1 for r in closed if not r['engage'])}")
print(f"- Deals em Prospecting com engage_date: {sum(1 for r in pipe if r['deal_stage']=='Prospecting' and r['engage'])} / 500")
print(f"- Win rate dos deals que passaram por Engaging (= todos os fechados): {P*100:.1f}%")
print("- Win rate de deal que ficou em Prospecting sem engajar: não existe nenhum deal fechado nessa condição (0 linhas).")

# ---------- H2 ----------
print("\n## H2 — Vendedor")
g = collections.defaultdict(list)
for r in closed: g[r["sales_agent"]].append(r)
stats = table("Win rate por vendedor (30 com deals)", g, "Vendedor",
              extra={a: f"{team_by[a]['manager']} / {team_by[a]['regional_office']}" for a in g})
rates = [s[2] for s in stats]
print(f"Mediana entre vendedores: {statistics.median(rates)*100:.1f}% · desvio-padrão: {statistics.pstdev(rates)*100:.1f} pp")

# ---------- H3 ----------
print("\n## H3 — Tamanho da conta")
def quartiles(field):
    vals = sorted(float(a[field]) for a in acc)
    q = [vals[int(len(vals)*k)] for k in (0.25, 0.5, 0.75)]
    def bucket(v):
        return "Q1 (menor)" if v < q[0] else "Q2" if v < q[1] else "Q3" if v < q[2] else "Q4 (maior)"
    groups = collections.defaultdict(list); nacc = collections.Counter(); rng = {}
    for a in acc: nacc[bucket(float(a[field]))] += 1
    for r in closed: groups[bucket(float(acc_by[r["account"]][field]))].append(r)
    for b in groups:
        vs = [float(a[field]) for a in acc if bucket(float(a[field])) == b]
        rng[b] = f"{min(vs):g}–{max(vs):g} · {nacc[b]} contas"
    return dict(sorted(groups.items())), rng
for field, label in (("revenue", "revenue (USD mi)"), ("employees", "employees")):
    groups, rng = quartiles(field)
    table(f"Win rate por quartil de {label} da conta", groups, "Quartil", extra=rng, sort=False)

# ---------- H4 ----------
print("\n## H4 — Setor")
g = collections.defaultdict(list)
for r in closed: g[acc_by[r["account"]]["sector"]].append(r)
table("Win rate por setor da conta", g, "Setor")

# ---------- H5 ----------
print("\n## H5 — Dias em Engaging (deals fechados: close_date − engage_date)")
days = [(r["close"] - r["engage"]).days for r in closed]
qs = statistics.quantiles(days, n=4)
print(f"- Distribuição: min {min(days)} · p25 {qs[0]:.0f} · mediana {qs[1]:.0f} · p75 {qs[2]:.0f} · max {max(days)}")
bands = [(0, 7), (8, 14), (15, 30), (31, 60), (61, 90), (91, 120), (121, 10**6)]
lab = lambda lo, hi: f"{lo}–{hi}" if hi < 10**6 else f"{lo}+"
g = {lab(lo, hi): [r for r in closed if lo <= (r["close"] - r["engage"]).days <= hi] for lo, hi in bands}
table("Win rate por faixa de dias em Engaging", g, "Dias", sort=False)
cut = dt.date(2017, 3, 1)
early = [r for r in closed if r["engage"] < cut]; late = [r for r in closed if r["engage"] >= cut]
print(f"\nFato estrutural: nenhum close_date antes de {cut}. Deals fechados engajados antes de {cut}: {len(early)} (win rate {wr(early)[2]*100:.1f}%, dias min {min((r['close']-r['engage']).days for r in early)}); engajados de {cut} em diante: {len(late)} (win rate {wr(late)[2]*100:.1f}%).")
g2 = {lab(lo, hi): [r for r in late if lo <= (r["close"] - r["engage"]).days <= hi] for lo, hi in bands}
table(f"Mesma tabela, só deals engajados a partir de {cut}", g2, "Dias", sort=False)
open_eng = [(REF_DATE - r["engage"]).days for r in pipe if r["deal_stage"] == "Engaging"]
qo = statistics.quantiles(open_eng, n=4)
print(f"\nExtra — deals abertos em Engaging, dias até {REF_DATE}: n={len(open_eng)} · min {min(open_eng)} · p25 {qo[0]:.0f} · mediana {qo[1]:.0f} · p75 {qo[2]:.0f} · max {max(open_eng)}")

# ---------- H6 ----------
print("\n## H6 — Região / manager")
g = collections.defaultdict(list)
for r in closed: g[team_by[r["sales_agent"]]["regional_office"]].append(r)
table("Win rate por escritório regional", g, "Região")
g = collections.defaultdict(list)
for r in closed: g[team_by[r["sales_agent"]]["manager"]].append(r)
table("Win rate por manager", g, "Manager", extra={m: team_by[[a for a in team_by if team_by[a]['manager']==m][0]]['regional_office'] for m in g})

# ---------- H7 ----------
print("\n## H7 — Conta / matriz que já teve Won antes do engage_date do deal")
won_dates = collections.defaultdict(list)
for r in closed:
    if r["deal_stage"] == "Won": won_dates[r["account"]].append(r["close"])
def had_prior_won(account, before):
    return any(d < before for d in won_dates.get(account, []))
print(f"- Contas com ≥1 Won em qualquer momento do dataset: {len(won_dates)} / {len(acc)}")
g = {"Conta já tinha Won antes": [r for r in closed if had_prior_won(r["account"], r["engage"])],
     "Conta sem Won anterior": [r for r in closed if not had_prior_won(r["account"], r["engage"])]}
table("Conta já tinha Won antes do engage_date (todos os fechados)", g, "Grupo")
g = {"Conta já tinha Won antes": [r for r in late if had_prior_won(r["account"], r["engage"])],
     "Conta sem Won anterior": [r for r in late if not had_prior_won(r["account"], r["engage"])]}
table(f"Mesma coisa, só deals engajados a partir de {cut} (quando já era possível ter Won anterior)", g, "Grupo")
subs = [r for r in closed if acc_by[r["account"]]["subsidiary_of"].strip()]
print(f"\nDeals fechados de contas que são subsidiárias: {len(subs)} ({len({r['account'] for r in subs})} contas, 7 matrizes)")
g = {"Matriz já tinha Won antes": [r for r in subs if had_prior_won(acc_by[r["account"]]["subsidiary_of"], r["engage"])],
     "Matriz sem Won anterior": [r for r in subs if not had_prior_won(acc_by[r["account"]]["subsidiary_of"], r["engage"])]}
table("Matriz já tinha Won antes do engage_date (deals de subsidiárias)", g, "Grupo")
subs_late = [r for r in subs if r["engage"] >= cut]
g = {"Matriz já tinha Won antes": [r for r in subs_late if had_prior_won(acc_by[r["account"]]["subsidiary_of"], r["engage"])],
     "Matriz sem Won anterior": [r for r in subs_late if not had_prior_won(acc_by[r["account"]]["subsidiary_of"], r["engage"])]}
table(f"Mesma coisa, só subsidiárias engajadas a partir de {cut}", g, "Grupo")

# ---------- Extras pedidos depois do veredito ----------
print("\n## Extra A — Produto")
g = collections.defaultdict(list)
for r in closed: g[r["product"]].append(r)
price = {p["product"]: p["sales_price"] for p in prod}
table("Win rate por produto", g, "Produto", extra={p: f"USD {price[p]}" for p in g})

print("\n## Extra B — Produto x vendedor")
cell = collections.defaultdict(list)
for r in closed: cell[(r["sales_agent"], r["product"])].append(r)
products = [p["product"] for p in prod]
agents = sorted({r["sales_agent"] for r in closed})
print("\n### Matriz vendedor x produto — win rate (n)\n")
print("| Vendedor | " + " | ".join(products) + " |")
print("|---|" + "---|" * len(products))
for a in agents:
    row = []
    for p in products:
        rows = cell.get((a, p), [])
        row.append(f"{wr(rows)[2]*100:.0f}% ({len(rows)})" if rows else "— (0)")
    print(f"| {a} | " + " | ".join(row) + " |")
print("\n### Spread entre vendedores dentro de cada produto\n")
print("| Produto | Vendedores com n≥30 | Melhor | Pior | Spread | Menor n (entre os ≥30) |")
print("|---|---|---|---|---|---|")
for p in products:
    cells = [(a, len(cell[(a, p)]), wr(cell[(a, p)])[2]) for a in agents if len(cell.get((a, p), [])) >= 30]
    if not cells:
        print(f"| {p} | 0 | — | — | — | — |"); continue
    cells.sort(key=lambda x: -x[2]); b, w = cells[0], cells[-1]
    print(f"| {p} | {len(cells)} | {b[0]} {b[2]*100:.1f}% (n={b[1]}) | {w[0]} {w[2]*100:.1f}% (n={w[1]}) | {(b[2]-w[2])*100:.1f} pp | {min(c[1] for c in cells)} |")
for min_n in (30, 50):
    cells = [(k, len(v), wr(v)[2]) for k, v in cell.items() if len(v) >= min_n]
    cells.sort(key=lambda x: -x[2]); b, w = cells[0], cells[-1]
    print(f"\nTodas as células com n≥{min_n}: {len(cells)} de {len(cell)} · melhor {b[0][0]} / {b[0][1]} {b[2]*100:.1f}% (n={b[1]}) · pior {w[0][0]} / {w[0][1]} {w[2]*100:.1f}% (n={w[1]}) · spread **{(b[2]-w[2])*100:.1f} pp** (vendedor sozinho: 15,4 pp; produto sozinho: ver tabela acima)")

print("\n## Extra C — H5: curva acumulada de fechamento por dias em Engaging")
won_days = [(r["close"] - r["engage"]).days for r in closed if r["deal_stage"] == "Won"]
lost_days = [(r["close"] - r["engage"]).days for r in closed if r["deal_stage"] == "Lost"]
print("\n| Dias | % dos fechados já fechados | % dos Won já fechados | % dos Lost já fechados |")
print("|---|---|---|---|")
for d in (7, 14, 30, 60, 90, 120, 138):
    f = lambda xs: sum(1 for x in xs if x <= d) / len(xs) * 100
    print(f"| ≤ {d} | {f(days):.1f}% | {f(won_days):.1f}% | {f(lost_days):.1f}% |")
print(f"\nMediana de dias: Won {statistics.median(won_days):.0f} · Lost {statistics.median(lost_days):.0f} · todos {statistics.median(days):.0f}")
