import csv
import json
import math
from collections import defaultdict, Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, stdev

BASE = Path(__file__).resolve().parent
OUT = BASE / "bloque3_visualizaciones"
RESULTS = BASE / "bloque3_results.json"
OUT.mkdir(exist_ok=True)

TEST_START = date(2024, 9, 1)
TEST_END = date(2024, 10, 12)
PRE_START = TEST_START - timedelta(days=42)
PRE_END = TEST_START - timedelta(days=1)
CONFLICT_CONTROL_STORES = {"TIENDA_008", "TIENDA_037"}


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def month_start(d):
    return date(d.year, d.month, 1)


def week_start(d):
    return d - timedelta(days=(d.weekday() + 1) % 7)  # Sunday retail week


def fmt_money(x):
    return f"${x:,.0f}"


def fmt_pct(x):
    if x is None:
        return "N/A"
    return f"{x * 100:.1f}%"


def read_csv(name):
    with (BASE / name).open(newline="", encoding="utf-8-sig") as fh:
        yield from csv.DictReader(fh)


def load_dimensions():
    stores, products, vendors = {}, {}, {}
    for r in read_csv("stores.csv"):
        stores[r["store_id"]] = {
            "store_name": r["store_name"], "country": r["country"],
            "city": r["city"], "format": r["format"],
            "size_sqm": int(r["size_sqm"]), "opening_date": parse_date(r["opening_date"]),
            "region": r["region"],
        }
    for r in read_csv("products.csv"):
        products[r["item_id"]] = {
            "item_name": r["item_name"], "brand": r["brand"],
            "vendor_id": r["vendor_id"], "category": r["category"],
            "department": r["department"], "cost": float(r["cost"]),
        }
    for r in read_csv("vendors.csv"):
        vendors[r["vendor_id"]] = {
            "vendor_name": r["vendor_name"], "country": r["country"],
            "tier": r["tier"], "is_shared_catalog": r["is_shared_catalog"].lower() == "true",
        }
    return stores, products, vendors


def load_promotions():
    rows_by_store = defaultdict(list)
    for r in read_csv("store_promotions.csv"):
        rows_by_store[r["store_id"]].append(r)
    assignments = {}
    conflicts = []
    for store_id, rows in rows_by_store.items():
        variants = {r["variant"] for r in rows}
        if store_id in CONFLICT_CONTROL_STORES:
            assignments[store_id] = "CONTROL"
            conflicts.append(store_id)
        elif "TREATMENT" in variants:
            assignments[store_id] = "TREATMENT"
        elif "CONTROL" in variants:
            assignments[store_id] = "CONTROL"
    return assignments, sorted(conflicts)


def t_cdf(t, df):
    # Student's t CDF via regularized incomplete beta; stdlib-only, no scipy puppy magic.
    if df <= 0:
        return 0.5
    x = df / (df + t * t)
    a, b = df / 2.0, 0.5
    ib = betai(a, b, x)
    if t >= 0:
        return 1 - 0.5 * ib
    return 0.5 * ib


def betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ln_bt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    ln_bt += a * math.log(x) + b * math.log(1 - x)
    bt = math.exp(ln_bt)
    if x < (a + 1) / (a + b + 2):
        return bt * betacf(a, b, x) / a
    return 1 - bt * betacf(b, a, 1 - x) / b


def betacf(a, b, x):
    max_iter, eps, fpmin = 200, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d, h = 1.0, 1.0 - qab * x / qap, 1.0
    if abs(d) < fpmin:
        d = fpmin
    d = 1 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < eps:
            break
    return h


def welch_ttest(a, b):
    n1, n2 = len(a), len(b)
    m1, m2 = mean(a), mean(b)
    v1, v2 = stdev(a) ** 2, stdev(b) ** 2
    se = math.sqrt(v1 / n1 + v2 / n2)
    diff = m1 - m2
    df_num = (v1 / n1 + v2 / n2) ** 2
    df_den = (v1 * v1) / (n1 * n1 * (n1 - 1)) + (v2 * v2) / (n2 * n2 * (n2 - 1))
    df = df_num / df_den if df_den else min(n1, n2) - 1
    t = diff / se if se else 0
    p = 2 * (1 - t_cdf(abs(t), df))
    crit = 1.96 if df > 60 else 2.0
    return {"diff": diff, "t": t, "df": df, "p_value": p, "ci_low": diff - crit * se, "ci_high": diff + crit * se}


def safe_div(a, b):
    return a / b if b else None


def line_svg(path, title, series_by_name, width=980, height=420):
    margin = 55
    xs = sorted({x for series in series_by_name.values() for x, _ in series})
    vals = [y for series in series_by_name.values() for _, y in series]
    ymin, ymax = 0, max(vals) * 1.08 if vals else 1
    colors = ["#0053e2", "#2a8703", "#995213", "#7f3fbf", "#ea1100"]
    def xp(x):
        idx = xs.index(x)
        return margin + idx * (width - 2 * margin) / max(1, len(xs) - 1)
    def yp(y):
        return height - margin - (y - ymin) * (height - 2 * margin) / (ymax - ymin)
    parts = [svg_header(width, height, title)]
    for i in range(5):
        y = margin + i * (height - 2 * margin) / 4
        parts.append(f'<line x1="{margin}" y1="{y}" x2="{width-margin}" y2="{y}" stroke="#e5e7eb"/>')
    for idx, (name, series) in enumerate(series_by_name.items()):
        points = " ".join(f"{xp(x):.1f},{yp(y):.1f}" for x, y in sorted(series))
        color = colors[idx % len(colors)]
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="3" points="{points}"/>')
        parts.append(f'<text x="{width-margin-150}" y="{35+idx*18}" fill="{color}" font-size="13">{name}</text>')
    parts.append(f'<text x="{margin}" y="{height-12}" font-size="11" fill="#555">Semanas: {xs[0]} a {xs[-1]}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def bar_svg(path, title, rows, width=980, height=420, money=True):
    margin, label_w = 55, 210
    rows = rows[:12]
    vals = [r[1] for r in rows]
    vmax = max(vals) * 1.1 if vals else 1
    bar_h = (height - 2 * margin) / max(1, len(rows))
    parts = [svg_header(width, height, title)]
    for i, (label, val) in enumerate(rows):
        y = margin + i * bar_h + 4
        w = (width - margin - label_w - 80) * val / vmax
        parts.append(f'<text x="{margin}" y="{y+bar_h/2}" font-size="12" fill="#333">{html_escape(label[:28])}</text>')
        parts.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bar_h-8:.1f}" rx="5" fill="#0053e2"/>')
        shown = fmt_money(val) if money else f"{val:,.1f}"
        parts.append(f'<text x="{label_w+w+8:.1f}" y="{y+bar_h/2}" font-size="12" fill="#333">{shown}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def svg_header(width, height, title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
<rect width="100%" height="100%" fill="white"/>
<text x="24" y="32" font-family="Arial" font-size="20" font-weight="700" fill="#0053e2">{html_escape(title)}</text>'''


def html_escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def analyze():
    stores, products, vendors = load_dimensions()
    promo_assignments, conflicts = load_promotions()
    tx = {}
    weekly_format_gmv = defaultdict(float)
    store_week = defaultdict(lambda: {"gmv": 0.0, "tx": 0})
    loyalty_by_customer_month = defaultdict(lambda: {"gmv": 0.0, "tx": 0})
    store_day_gmv = defaultdict(float)
    dates = []
    for r in read_csv("transactions.csv"):
        if r["status"] != "COMPLETED":
            continue
        d = parse_date(r["transaction_date"])
        total = float(r["total_amount"])
        sid = r["store_id"]
        st = stores[sid]
        tx[r["transaction_id"]] = {
            "date": d, "store_id": sid, "format": st["format"], "country": st["country"],
            "region": st["region"], "total": total, "customer_id": r["customer_id"],
            "loyalty": r["loyalty_card"].lower() == "true",
        }
        dates.append(d)
        weekly_format_gmv[(st["format"], week_start(d))] += total
        store_week[(sid, week_start(d))]["gmv"] += total
        store_week[(sid, week_start(d))]["tx"] += 1
        store_day_gmv[(sid, d)] += total
        if r["loyalty_card"].lower() == "true" and r["customer_id"]:
            cm = month_start(d)
            key = (r["customer_id"], cm)
            loyalty_by_customer_month[key]["gmv"] += total
            loyalty_by_customer_month[key]["tx"] += 1
    anchor = max(dates)

    format_weeks = defaultdict(list)
    for (fmt, wk), gmv in weekly_format_gmv.items():
        format_weeks[fmt].append((wk.isoformat(), gmv))
    sensitivity = []
    for fmt, vals in format_weeks.items():
        ys = [v for _, v in vals]
        sensitivity.append({"format": fmt, "cv": safe_div(stdev(ys), mean(ys)) if len(ys) > 1 else 0, "avg_weekly_gmv": mean(ys)})
    total_weekly = defaultdict(float)
    for (_, wk), gmv in weekly_format_gmv.items():
        total_weekly[wk] += gmv
    wow = []
    prior = None
    for wk in sorted(total_weekly):
        if prior:
            change = total_weekly[wk] - total_weekly[prior]
            wow.append({"week": wk.isoformat(), "gmv": total_weekly[wk], "change": change, "change_pct": safe_div(change, total_weekly[prior])})
        prior = wk
    peaks = sorted(wow, key=lambda x: x["change"], reverse=True)[:3]
    drops = sorted(wow, key=lambda x: x["change"])[:3]

    category_format_gmv = defaultdict(float)
    vendor_category = defaultdict(lambda: {"gmv": 0.0, "cost": 0.0, "units": 0.0, "sku": set()})
    daily_sales = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    promo_cat = defaultdict(lambda: {"promo_gmv": 0.0, "promo_units": 0.0, "non_gmv": 0.0, "non_units": 0.0})
    for r in read_csv("transaction_items.csv"):
        t = tx.get(r["transaction_id"])
        if not t:
            continue
        item = products[r["item_id"]]
        qty = int(r["quantity"])
        unit_price = float(r["unit_price"])
        gmv = qty * unit_price
        category_format_gmv[(t["format"], item["category"])] += gmv
        vkey = (item["vendor_id"], item["category"])
        vendor_category[vkey]["gmv"] += gmv
        vendor_category[vkey]["cost"] += qty * item["cost"]
        vendor_category[vkey]["units"] += qty
        vendor_category[vkey]["sku"].add(r["item_id"])
        daily_sales[(t["store_id"], r["item_id"] )][t["date"]][0] += qty
        daily_sales[(t["store_id"], r["item_id"] )][t["date"]][1] += gmv
        bucket = promo_cat[item["category"]]
        if r["was_on_promo"].lower() == "true":
            bucket["promo_gmv"] += gmv; bucket["promo_units"] += qty
        else:
            bucket["non_gmv"] += gmv; bucket["non_units"] += qty

    pareto = {}
    for fmt in sorted({k[0] for k in category_format_gmv}):
        rows = sorted([(cat, gmv) for (f, cat), gmv in category_format_gmv.items() if f == fmt], key=lambda x: x[1], reverse=True)
        total, acc, leaders = sum(v for _, v in rows), 0.0, []
        for cat, gmv in rows:
            acc += gmv
            leaders.append({"category": cat, "gmv": gmv, "cumulative_pct": safe_div(acc, total)})
            if acc / total >= 0.8:
                break
        pareto[fmt] = {"total_gmv": total, "leaders_80": leaders, "all": rows}

    cohort = build_cohorts(loyalty_by_customer_month)
    stockouts = build_stockouts(daily_sales, stores, products, vendors, anchor)
    ab = build_ab(store_week, stores, promo_assignments, conflicts)
    free = free_finding(promo_cat)

    make_visuals(format_weeks, pareto, cohort, stockouts, ab, free)
    results = {
        "period": {"start": min(dates).isoformat(), "end": max(dates).isoformat()},
        "seasonality": {"sensitivity": sorted(sensitivity, key=lambda x: x["cv"], reverse=True), "peaks": peaks, "drops": drops},
        "pareto": pareto, "cohorts": cohort, "stockouts": stockouts,
        "ab_test": ab, "free_finding": free,
        "visualizations": sorted(str(p.relative_to(BASE)) for p in OUT.glob("*.svg")),
    }
    RESULTS.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return results


def build_cohorts(customer_month):
    first_month = {}
    for customer, month in customer_month:
        first_month[customer] = min(month, first_month.get(customer, month))
    cells = defaultdict(lambda: {"customers": set(), "gmv": 0.0, "tx": 0})
    cohort_sizes = Counter(first_month.values())
    for (customer, month), metrics in customer_month.items():
        cohort = first_month[customer]
        ms = (month.year - cohort.year) * 12 + month.month - cohort.month
        if ms in {0, 1, 2, 3, 6}:
            cell = cells[(cohort, ms)]
            cell["customers"].add(customer); cell["gmv"] += metrics["gmv"]; cell["tx"] += metrics["tx"]
    rows = []
    for cohort, size in sorted(cohort_sizes.items()):
        row = {"cohort_month": cohort.isoformat(), "cohort_customers": size}
        for ms in [0, 1, 2, 3, 6]:
            c = cells.get((cohort, ms), {"customers": set(), "gmv": 0, "tx": 0})
            row[f"m{ms}_retention"] = safe_div(len(c["customers"]), size)
            row[f"m{ms}_avg_ticket"] = safe_div(c["gmv"], c["tx"])
        rows.append(row)
    mature = [r for r in rows if r["m3_retention"] is not None]
    old = mature[: max(1, len(mature)//3)]
    recent = mature[-max(1, len(mature)//3):]
    def avg_ret(rows, m):
        vals = [r[f"m{m}_retention"] for r in rows if r[f"m{m}_retention"] is not None]
        return mean(vals) if vals else None
    drops = []
    for r in rows:
        prev = r["m0_retention"] or 1
        for m in [1, 2, 3, 6]:
            cur = r[f"m{m}_retention"]
            if cur is not None:
                drops.append({"cohort_month": r["cohort_month"], "month": m, "drop_pp": prev - cur})
                prev = cur
    return {
        "rows": rows,
        "old_m3_avg": avg_ret(old, 3), "recent_m3_avg": avg_ret(recent, 3),
        "largest_drop": max(drops, key=lambda x: x["drop_pp"]) if drops else None,
    }


def build_stockouts(daily_sales, stores, products, vendors, anchor):
    gaps, by_cat, by_vendor = [], defaultdict(lambda: {"count": 0, "lost": 0.0}), defaultdict(lambda: {"count": 0, "lost": 0.0})
    for (store_id, item_id), daymap in daily_sales.items():
        sold_dates = sorted(daymap)
        all_dates = sold_dates + [anchor + timedelta(days=1)]
        prev = None
        for d in all_dates:
            if prev is not None:
                gap_days = (d - prev).days - 1
                if gap_days >= 3:
                    start, end = prev + timedelta(days=1), d - timedelta(days=1)
                    units = gmv = 0.0
                    for i in range(1, 29):
                        u, v = daymap.get(start - timedelta(days=i), [0.0, 0.0])
                        units += u; gmv += v
                    avg_units, avg_gmv = units / 28, gmv / 28
                    if avg_units > 0:
                        lost = avg_gmv * gap_days
                        prod = products[item_id]
                        vendor = vendors.get(prod["vendor_id"], {"vendor_name": "NO_ENCONTRADO"})
                        row = {"store_id": store_id, "item_id": item_id, "category": prod["category"],
                               "vendor_id": prod["vendor_id"], "vendor_name": vendor["vendor_name"],
                               "gap_start": start.isoformat(), "gap_end": end.isoformat(),
                               "duration_days": gap_days, "avg_daily_gmv_before": avg_gmv,
                               "estimated_lost_gmv": lost}
                        gaps.append(row)
                        by_cat[prod["category"]]["count"] += 1; by_cat[prod["category"]]["lost"] += lost
                        by_vendor[prod["vendor_id"]]["count"] += 1; by_vendor[prod["vendor_id"]]["lost"] += lost
            prev = d
    top_gaps = sorted(gaps, key=lambda x: x["estimated_lost_gmv"], reverse=True)[:50]
    top_cat = sorted(([{"category": k, **v} for k, v in by_cat.items()]), key=lambda x: x["lost"], reverse=True)[:10]
    top_vendor = sorted(([{"vendor_id": k, "vendor_name": vendors.get(k, {}).get("vendor_name", "NO_ENCONTRADO"), **v} for k, v in by_vendor.items()]), key=lambda x: x["lost"], reverse=True)[:10]
    return {"total_gaps": len(gaps), "total_lost_gmv": sum(g["estimated_lost_gmv"] for g in gaps), "top_gaps": top_gaps, "top_categories": top_cat, "top_vendors": top_vendor}


def build_ab(store_week, stores, assignments, conflicts):
    pre, test = defaultdict(lambda: {"gmv": 0.0, "tx": 0}), defaultdict(lambda: {"gmv": 0.0, "tx": 0})
    for (sid, wk), m in store_week.items():
        if sid not in assignments:
            continue
        wkd = parse_date(wk) if isinstance(wk, str) else wk
        if PRE_START <= wkd <= PRE_END:
            pre[sid]["gmv"] += m["gmv"]; pre[sid]["tx"] += m["tx"]
        if TEST_START <= wkd <= TEST_END:
            test[sid]["gmv"] += m["gmv"]; test[sid]["tx"] += m["tx"]
    group_stores = defaultdict(list)
    for sid, group in assignments.items():
        group_stores[group].append(sid)
    pre_summary, test_weekly_gmv, tx_weekly, ticket = {}, [], [], []
    for group, sids in group_stores.items():
        base = [pre[s]["gmv"] / 6 for s in sids if s in pre]
        sizes = [stores[s]["size_sqm"] for s in sids]
        formats = Counter(stores[s]["format"] for s in sids)
        pre_summary[group] = {"stores": len(sids), "avg_weekly_base_gmv": mean(base) if base else 0, "avg_size_sqm": mean(sizes), "formats": dict(formats)}
        for s in sids:
            test_weekly_gmv.append((group, test[s]["gmv"] / 6 if s in test else 0))
            tx_weekly.append((group, test[s]["tx"] / 6 if s in test else 0))
            ticket.append((group, safe_div(test[s]["gmv"], test[s]["tx"]) or 0))
    treatment = [v for g, v in test_weekly_gmv if g == "TREATMENT"]
    control = [v for g, v in test_weekly_gmv if g == "CONTROL"]
    stats = welch_ttest(treatment, control)
    stats["lift_relative"] = safe_div(stats["diff"], mean(control))
    return {
        "conflict_stores_assumed_control": conflicts, "pre_summary": pre_summary,
        "gmv_ttest": stats,
        "avg_weekly_gmv": {"TREATMENT": mean(treatment), "CONTROL": mean(control)},
        "avg_weekly_transactions": {g: mean([v for gg, v in tx_weekly if gg == g]) for g in ["TREATMENT", "CONTROL"]},
        "avg_ticket": {g: mean([v for gg, v in ticket if gg == g]) for g in ["TREATMENT", "CONTROL"]},
    }


def free_finding(promo_cat):
    rows = []
    for cat, m in promo_cat.items():
        promo_unit_price = safe_div(m["promo_gmv"], m["promo_units"])
        non_unit_price = safe_div(m["non_gmv"], m["non_units"])
        if promo_unit_price and non_unit_price:
            rows.append({"category": cat, "promo_avg_unit_price": promo_unit_price,
                         "non_promo_avg_unit_price": non_unit_price,
                         "discount_proxy_pct": safe_div(promo_unit_price - non_unit_price, non_unit_price),
                         "promo_gmv": m["promo_gmv"]})
    rows.sort(key=lambda x: x["discount_proxy_pct"])
    return {"title": "Promociones muestran descuento implícito desigual por categoría", "rows": rows[:10]}


def make_visuals(format_weeks, pareto, cohort, stockouts, ab, free):
    line_svg(OUT / "01_gmv_semanal_por_formato.svg", "GMV semanal por formato", format_weeks)
    for fmt, data in pareto.items():
        bar_svg(OUT / f"02_pareto_{fmt.lower()}.svg", f"Pareto de categorías - {fmt}", data["all"])
    retention = {"M1": [], "M2": [], "M3": [], "M6": []}
    for r in cohort["rows"]:
        for m in [1, 2, 3, 6]:
            if r[f"m{m}_retention"] is not None:
                retention[f"M{m}"].append((r["cohort_month"], r[f"m{m}_retention"] * 100))
    line_svg(OUT / "03_retencion_cohortes.svg", "Retención por cohorte de lealtad (%)", retention)
    bar_svg(OUT / "04_quiebres_categoria_gmv_perdido.svg", "GMV perdido estimado por categoría", [(r["category"], r["lost"]) for r in stockouts["top_categories"]])
    ab_rows = [("Treatment", ab["avg_weekly_gmv"]["TREATMENT"]), ("Control", ab["avg_weekly_gmv"]["CONTROL"])]
    bar_svg(OUT / "05_ab_gmv_promedio_semanal.svg", "A/B test: GMV promedio semanal por tienda", ab_rows)
    bar_svg(OUT / "06_hallazgo_descuento_promo.svg", "Hallazgo libre: descuento proxy en promo (%)", [(r["category"], r["discount_proxy_pct"] * 100) for r in free["rows"]], money=False)


if __name__ == "__main__":
    res = analyze()
    print(f"Wrote {RESULTS}")
    print(f"Wrote {len(res['visualizations'])} SVG visualizations to {OUT}")
