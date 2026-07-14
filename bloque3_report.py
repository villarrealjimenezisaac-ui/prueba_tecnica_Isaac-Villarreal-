import json
import shutil
import subprocess
from pathlib import Path
from statistics import mean

BASE = Path(__file__).resolve().parent
OUT = BASE / "bloque3_visualizaciones"
RESULTS = json.loads((BASE / "bloque3_results.json").read_text(encoding="utf-8"))
HTML = BASE / "bloque3_analisis.html"
PDF = BASE / "bloque3_analisis.pdf"


def money(x):
    return f"${x:,.0f}"


def pct(x):
    return "N/A" if x is None else f"{x*100:.1f}%"


def pct_raw(x):
    return "N/A" if x is None else f"{x:.1f}%"


def svg(name):
    return (OUT / name).read_text(encoding="utf-8")


def table(headers, rows):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def avg_ticket_by_month(m):
    vals = [r[f"m{m}_avg_ticket"] for r in RESULTS["cohorts"]["rows"] if r[f"m{m}_avg_ticket"]]
    return mean(vals) if vals else None


def build_html():
    season = RESULTS["seasonality"]
    ab = RESULTS["ab_test"]
    cohorts = RESULTS["cohorts"]
    stock = RESULTS["stockouts"]
    free = RESULTS["free_finding"]
    ticket_path = [(m, avg_ticket_by_month(m)) for m in [0, 1, 2, 3, 6]]

    sensitivity_rows = [
        [x["format"], money(x["avg_weekly_gmv"]), f"{x['cv']:.3f}"]
        for x in season["sensitivity"]
    ]
    peak_rows = [[x["week"], money(x["gmv"]), money(x["change"]), pct(x["change_pct"])] for x in season["peaks"]]
    drop_rows = [[x["week"], money(x["gmv"]), money(x["change"]), pct(x["change_pct"])] for x in season["drops"]]

    pareto_rows = []
    for fmt, data in RESULTS["pareto"].items():
        cats = ", ".join(f"{x['category']} ({pct(x['cumulative_pct'])} acum.)" for x in data["leaders_80"])
        pareto_rows.append([fmt, cats, money(data["total_gmv"])])

    cat_rows = [[r["category"], f"{r['count']:,}", money(r["lost"])] for r in stock["top_categories"][:5]]
    vendor_rows = [[r["vendor_id"], r["vendor_name"], f"{r['count']:,}", money(r["lost"])] for r in stock["top_vendors"][:5]]

    ab_pre_rows = []
    for group, row in ab["pre_summary"].items():
        formats = ", ".join(f"{k}:{v}" for k, v in row["formats"].items())
        ab_pre_rows.append([group, row["stores"], money(row["avg_weekly_base_gmv"]), f"{row['avg_size_sqm']:,.0f}", formats])
    stat = ab["gmv_ttest"]

    free_rows = [[r["category"], money(r["promo_avg_unit_price"]), money(r["non_promo_avg_unit_price"]), pct(r["discount_proxy_pct"])] for r in free["rows"][:6]]

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Bloque 3 — Análisis Exploratorio + Experimentación</title>
<style>
@page {{ size: Letter; margin: 0.55in; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Arial, Helvetica, sans-serif; color:#2e3038; line-height:1.38; margin:0; }}
h1 {{ color:#0053e2; font-size:27px; border-bottom:5px solid #ffc220; padding-bottom:9px; margin:0 0 14px; }}
h2 {{ color:#003b95; font-size:19px; margin:22px 0 8px; }}
h3 {{ color:#1f1f2e; font-size:15px; margin:16px 0 6px; }}
p, li, td, th {{ font-size:10.5px; }}
p {{ margin:6px 0; }}
.badge {{ display:inline-block; padding:4px 8px; border-radius:999px; background:#eaf3ff; color:#003b95; font-size:10.5px; font-weight:700; margin-right:5px; }}
.kpis {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:9px; margin:12px 0; }}
.kpi {{ border:1px solid #d5d8dd; border-radius:12px; padding:10px; background:#f8f9fb; }}
.kpi b {{ color:#0053e2; font-size:17px; display:block; }}
.kpi span {{ font-size:10px; color:#555; }}
table {{ width:100%; border-collapse:collapse; margin:8px 0 14px; page-break-inside:avoid; }}
th {{ background:#0053e2; color:white; text-align:left; }}
th, td {{ border:1px solid #d5d8dd; padding:5px 7px; vertical-align:top; }}
tr:nth-child(even) td {{ background:#f8f9fb; }}
.chart {{ border:1px solid #d5d8dd; border-radius:14px; padding:8px; margin:10px 0 14px; page-break-inside:avoid; }}
.chart svg {{ width:100%; height:auto; }}
.callout {{ border-left:5px solid #ffc220; background:#fff8e1; padding:9px 11px; border-radius:8px; margin:8px 0 12px; }}
.warning {{ border-left-color:#ea1100; background:#fff1f0; }}
.success {{ border-left-color:#2a8703; background:#f0faed; }}
.page-break {{ page-break-before:always; }}
</style>
</head>
<body>
<h1>Bloque 3 — Análisis Exploratorio + Experimentación</h1>
<p><span class="badge">Período analizado: {RESULTS['period']['start']} a {RESULTS['period']['end']}</span><span class="badge">Fuente: CSV locales Bloque 1</span><span class="badge">A/B: conflictos asumidos CONTROL</span></p>

<div class="kpis">
  <div class="kpi"><b>{season['sensitivity'][0]['format']}</b><span>Formato más sensible a estacionalidad, CV {season['sensitivity'][0]['cv']:.3f}</span></div>
  <div class="kpi"><b>{money(stock['total_lost_gmv'])}</b><span>GMV perdido estimado por posibles quiebres</span></div>
  <div class="kpi"><b>{pct(stat['lift_relative'])}</b><span>Lift relativo TREATMENT vs CONTROL en GMV semanal</span></div>
  <div class="kpi"><b>{stat['p_value']:.3f}</b><span>p-value Welch t-test del A/B</span></div>
</div>

<h2>Resumen ejecutivo</h2>
<ul>
<li>El formato <b>{season['sensitivity'][0]['format']}</b> es el más sensible a estacionalidad: vende menos en promedio, pero fluctúa más proporcionalmente.</li>
<li>El Pareto por formato es muy parecido: <b>Electrónica, Hogar y Ropa</b> superan aproximadamente el 80% del GMV en todos los formatos. El perfil de categoría es más homogéneo de lo esperado.</li>
<li>Las cohortes recientes muestran mejor retención M3 que las antiguas: {pct(cohorts['recent_m3_avg'])} vs {pct(cohorts['old_m3_avg'])}. Ojo: las cohortes recientes tienen menor ventana de maduración.</li>
<li>Los posibles quiebres son sistemáticos en categorías de alto valor, especialmente Electrónica y Hogar. El estimado debe tratarse como direccional, no como contabilidad oficial.</li>
<li>El A/B test no respalda rollout total: TREATMENT tuvo GMV semanal menor que CONTROL, p-value {stat['p_value']:.3f}, IC95% [{money(stat['ci_low'])}, {money(stat['ci_high'])}]. Además, los grupos no están perfectamente balanceados en base, tamaño ni formato.</li>
</ul>

<h2>Parte A — Análisis exploratorio</h2>
<h3>Pregunta 1 — Estacionalidad por formato</h3>
<div class="chart">{svg('01_gmv_semanal_por_formato.svg')}</div>
{table(['Formato', 'GMV semanal promedio', 'Coeficiente de variación'], sensitivity_rows)}
<p><b>Interpretación:</b> EXPRESS es el formato más sensible porque su CV es el más alto. Esto sugiere que pequeñas variaciones de demanda, tráfico o surtido impactan más fuerte en tiendas pequeñas.</p>
<h3>Top 3 picos WoW</h3>
{table(['Semana', 'GMV', 'Cambio absoluto', 'Cambio %'], peak_rows)}
<ul>
<li><b>2024-12-01:</b> hipótesis de impulso por temporada navideña / Black Friday extendido.</li>
<li><b>2024-06-30:</b> posible efecto de cierre de mes, pago o campaña comercial de mitad de año.</li>
<li><b>2025-03-16:</b> posible promoción estacional o normalización posterior a semanas débiles.</li>
</ul>
<h3>Top 3 caídas WoW</h3>
{table(['Semana', 'GMV', 'Cambio absoluto', 'Cambio %'], drop_rows)}
<ul>
<li><b>2025-06-29:</b> muy probablemente semana incompleta al final del dataset; no debe interpretarse como caída real sin calendario completo.</li>
<li><b>2024-12-29:</b> normalización post Navidad.</li>
<li><b>2025-01-05:</b> efecto enero: menor tráfico y ajuste de gasto después de temporada alta.</li>
</ul>

<h3>Pregunta 2 — Pareto de categorías por formato</h3>
{table(['Formato', 'Categorías que llegan a ~80% GMV', 'GMV total formato'], pareto_rows)}
<div class="chart">{svg('02_pareto_hipermercado.svg')}</div>
<div class="chart">{svg('02_pareto_descuento.svg')}</div>
<p><b>Conclusión:</b> HIPERMERCADO y DESCUENTO comparten las mismas categorías líderes: Electrónica, Hogar y Ropa. Esto indica que la diferencia entre formatos no está en qué categorías lideran, sino en escala, ticket, tamaño de tienda y posiblemente profundidad de surtido.</p>

<h3>Pregunta 3 — Cohortes de lealtad</h3>
<div class="chart">{svg('03_retencion_cohortes.svg')}</div>
<div class="kpis">
  <div class="kpi"><b>{pct(cohorts['old_m3_avg'])}</b><span>Retención M3 promedio en cohortes antiguas</span></div>
  <div class="kpi"><b>{pct(cohorts['recent_m3_avg'])}</b><span>Retención M3 promedio en cohortes recientes</span></div>
  <div class="kpi"><b>{cohorts['largest_drop']['cohort_month']}</b><span>Cohorte con mayor caída detectada</span></div>
  <div class="kpi"><b>M{cohorts['largest_drop']['month']}</b><span>Mes relativo de mayor caída</span></div>
</div>
<p>Ticket promedio agregado de clientes retenidos: {', '.join(f'M{m}: {money(v)}' for m, v in ticket_path if v)}.</p>
<p><b>Interpretación:</b> las cohortes recientes retienen mejor en M3, pero se debe monitorear maduración. El ticket retenido no muestra una tendencia explosiva; se mantiene relativamente estable, lo que sugiere que la mejora viene más por retención/frecuencia que por expansión fuerte de ticket.</p>
<p><b>Hipótesis de mayor caída:</b> la pérdida más fuerte aparece en la cohorte {cohorts['largest_drop']['cohort_month']} hacia M{cohorts['largest_drop']['month']}; puede explicarse por compradores atraídos por campañas puntuales que no desarrollaron hábito recurrente.</p>

<h3>Pregunta 4 — Quiebres de stock y su impacto</h3>
<div class="chart">{svg('04_quiebres_categoria_gmv_perdido.svg')}</div>
<div class="kpis">
  <div class="kpi"><b>{stock['total_gaps']:,}</b><span>Gaps potenciales detectados</span></div>
  <div class="kpi"><b>{money(stock['total_lost_gmv'])}</b><span>GMV perdido estimado</span></div>
  <div class="kpi"><b>{stock['top_categories'][0]['category']}</b><span>Categoría con mayor GMV perdido</span></div>
  <div class="kpi"><b>{stock['top_vendors'][0]['vendor_name']}</b><span>Proveedor con mayor GMV perdido estimado</span></div>
</div>
{table(['Categoría', 'Gaps', 'GMV perdido estimado'], cat_rows)}
{table(['Vendor ID', 'Proveedor', 'Gaps', 'GMV perdido estimado'], vendor_rows)}
<p><b>Diagnóstico:</b> el patrón parece más de abastecimiento/disponibilidad que de demanda: los gaps se detectan solo donde había venta histórica y venta promedio antes del gap. Electrónica concentra menos gaps que Alimentos/Hogar, pero mucho más GMV perdido por valor unitario.</p>
<div class="callout warning"><b>Cuidado metodológico:</b> sin inventario real ni calendario operativo, esto es una detección de riesgo de quiebre, no prueba absoluta de stockout. Aun así, sirve para priorizar revisión con Supply Chain.</div>

<h3>Pregunta 5 — Hallazgo libre</h3>
<div class="chart">{svg('06_hallazgo_descuento_promo.svg')}</div>
{table(['Categoría', 'Precio unitario promo', 'Precio unitario no promo', 'Proxy descuento'], free_rows)}
<p><b>Hallazgo:</b> las promociones muestran un descuento implícito cercano a 20% en varias categorías. Si el volumen incremental no compensa la reducción de precio, el negocio puede estar subsidiando compras que iban a ocurrir de todos modos.</p>
<p><b>Impacto:</b> conviene evaluar promociones por margen y no solo por GMV. Un uplift de unidades con ticket plano o menor puede destruir margen.</p>

<h2 class="page-break">Parte B — Interpretación de A/B test</h2>
<h3>1. Validación del experimento</h3>
{table(['Grupo', 'Tiendas', 'GMV semanal base', 'Tamaño promedio m²', 'Mix formatos'], ab_pre_rows)}
<p>Tiendas asignadas a ambos grupos y asumidas como CONTROL: {', '.join(ab['conflict_stores_assumed_control'])}.</p>
<div class="callout warning"><b>Validación:</b> los grupos no son perfectamente comparables. CONTROL tiene mayor GMV base promedio ({money(ab['pre_summary']['CONTROL']['avg_weekly_base_gmv'])} vs {money(ab['pre_summary']['TREATMENT']['avg_weekly_base_gmv'])}) y tiendas más grandes ({ab['pre_summary']['CONTROL']['avg_size_sqm']:,.0f} m² vs {ab['pre_summary']['TREATMENT']['avg_size_sqm']:,.0f} m²).</div>

<h3>2. Resultado en GMV</h3>
<div class="chart">{svg('05_ab_gmv_promedio_semanal.svg')}</div>
<div class="kpis">
  <div class="kpi"><b>{money(ab['avg_weekly_gmv']['TREATMENT'])}</b><span>GMV semanal promedio TREATMENT</span></div>
  <div class="kpi"><b>{money(ab['avg_weekly_gmv']['CONTROL'])}</b><span>GMV semanal promedio CONTROL</span></div>
  <div class="kpi"><b>{money(stat['diff'])}</b><span>Diferencia absoluta T-C</span></div>
  <div class="kpi"><b>{pct(stat['lift_relative'])}</b><span>Lift relativo</span></div>
</div>
<p><b>Welch t-test:</b> t={stat['t']:.2f}, p-value={stat['p_value']:.3f}, IC95% de diferencia absoluta [{money(stat['ci_low'])}, {money(stat['ci_high'])}]. El intervalo incluye cero y el efecto observado es negativo.</p>

<h3>3. Ticket y frecuencia</h3>
{table(['Métrica', 'TREATMENT', 'CONTROL', 'Lectura'], [
    ['Transacciones semanales por tienda', f"{ab['avg_weekly_transactions']['TREATMENT']:.1f}", f"{ab['avg_weekly_transactions']['CONTROL']:.1f}", 'TREATMENT tiene menor frecuencia'],
    ['Ticket promedio', money(ab['avg_ticket']['TREATMENT']), money(ab['avg_ticket']['CONTROL']), 'TREATMENT también tiene ticket ligeramente menor'],
])}
<p>El efecto no viene de tickets más altos ni de más transacciones. En la muestra observada, TREATMENT queda por debajo en ambos componentes.</p>

<h3>4. Decisión de negocio</h3>
<div class="callout warning"><b>Recomendación:</b> no implementaría la nueva exhibición en todas las tiendas con esta evidencia. El p-value no es significativo, el efecto observado es negativo y los grupos tienen desbalance base.</div>
<p>Antes de rollout haría una segunda prueba con mejor balance por formato/tamaño/GMV base, excluiría conflictos de asignación desde diseño experimental y agregaría costo de implementación para calcular ROI incremental.</p>
<p><b>Si el p-value fuera 0.08:</b> tampoco haría rollout total automáticamente. Lo trataría como señal direccional: extendería el experimento, aumentaría muestra, usaría stratified randomization o diferencia-en-diferencias, y solo escalaría si el efecto económico cubre costos con margen de seguridad.</p>

<h2>Archivos generados</h2>
<ul>
<li><code>bloque3_analisis.pdf</code>: reporte ejecutivo final.</li>
<li><code>bloque3_queries.sql</code>: SQL reproducible en BigQuery.</li>
<li><code>bloque3_visualizaciones/*.svg</code>: visualizaciones exportadas.</li>
<li><code>bloque3_results.json</code>: evidencia estructurada reproducible.</li>
</ul>
</body></html>"""


def find_browser():
    candidates = [
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    for name in ["msedge", "chrome", "chromium"]:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def main():
    HTML.write_text(build_html(), encoding="utf-8")
    browser = find_browser()
    if not browser:
        raise RuntimeError("No encontré Edge/Chrome para exportar PDF")
    cmd = [browser, "--headless", "--disable-gpu", f"--print-to-pdf={PDF}", str(HTML)]
    subprocess.run(cmd, cwd=BASE, check=True, timeout=90, capture_output=True, text=True)
    print(f"Wrote {PDF}")


if __name__ == "__main__":
    main()
