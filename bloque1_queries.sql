-- bloque1_queries.sql
-- Motor: BigQuery Standard SQL
--
-- Instrucciones:
-- 1) Reemplaza `your_project.your_dataset` por el proyecto/dataset real en BigQuery.
-- 2) Cada query es independiente y usa MAX(transaction_date) como fecha ancla.
-- 3) Se consideran solo transacciones COMPLETED para KPIs comerciales.

/* ============================================================================
QUERY 1: Ventas comparables (Comp Sales)
Métrica estándar de retail

Calcula crecimiento YoY para tiendas comparables:
- Año actual YTD: desde inicio del año de la fecha máxima hasta la fecha máxima.
- Año anterior comparable: mismas fechas desplazadas 1 año.
- Excluye tiendas abiertas hace menos de 13 meses al inicio del período actual.
- Exige ventas en ambos períodos.

Salida:
- País y formato.
- GMV año actual vs año anterior a nivel país/formato.
- Growth % país/formato.
- Ranking de tiendas por crecimiento dentro de su formato.
============================================================================ */
WITH params AS (
  SELECT
    MAX(DATE(transaction_date)) AS anchor_date,
    DATE_TRUNC(MAX(DATE(transaction_date)), YEAR) AS current_start,
    MAX(DATE(transaction_date)) AS current_end,
    DATE_SUB(DATE_TRUNC(MAX(DATE(transaction_date)), YEAR), INTERVAL 1 YEAR) AS prior_start,
    DATE_SUB(MAX(DATE(transaction_date)), INTERVAL 1 YEAR) AS prior_end
  FROM `your_project.your_dataset.transactions`
), comparable_store_sales AS (
  SELECT
    s.country,
    s.format,
    s.store_id,
    s.store_name,
    SUM(CASE
      WHEN DATE(t.transaction_date) BETWEEN p.current_start AND p.current_end
      THEN t.total_amount ELSE 0
    END) AS gmv_current_year,
    SUM(CASE
      WHEN DATE(t.transaction_date) BETWEEN p.prior_start AND p.prior_end
      THEN t.total_amount ELSE 0
    END) AS gmv_prior_year
  FROM `your_project.your_dataset.transactions` AS t
  JOIN `your_project.your_dataset.stores` AS s
    ON s.store_id = t.store_id
  CROSS JOIN params AS p
  WHERE t.status = 'COMPLETED'
    AND DATE(s.opening_date) <= DATE_SUB(p.current_start, INTERVAL 13 MONTH)
    AND DATE(t.transaction_date) BETWEEN p.prior_start AND p.current_end
  GROUP BY s.country, s.format, s.store_id, s.store_name
  HAVING gmv_current_year > 0
     AND gmv_prior_year > 0
), ranked AS (
  SELECT
    *,
    SAFE_DIVIDE(gmv_current_year - gmv_prior_year, gmv_prior_year) AS store_comp_sales_growth_pct,
    RANK() OVER (
      PARTITION BY country, format
      ORDER BY SAFE_DIVIDE(gmv_current_year - gmv_prior_year, gmv_prior_year) DESC
    ) AS store_growth_rank_in_format
  FROM comparable_store_sales
)
SELECT
  country,
  format,
  SUM(gmv_current_year) OVER (PARTITION BY country, format) AS format_gmv_current_year,
  SUM(gmv_prior_year) OVER (PARTITION BY country, format) AS format_gmv_prior_year,
  SAFE_DIVIDE(
    SUM(gmv_current_year) OVER (PARTITION BY country, format)
      - SUM(gmv_prior_year) OVER (PARTITION BY country, format),
    SUM(gmv_prior_year) OVER (PARTITION BY country, format)
  ) AS format_comp_sales_growth_pct,
  store_id,
  store_name,
  gmv_current_year AS store_gmv_current_year,
  gmv_prior_year AS store_gmv_prior_year,
  store_comp_sales_growth_pct,
  store_growth_rank_in_format
FROM ranked
ORDER BY country, format, store_growth_rank_in_format;


/* ============================================================================
QUERY 2: Productividad por metro cuadrado
KPI operativo

Para cada tienda calcula en el último trimestre móvil:
- GMV total.
- GMV/m².
- Transacciones/m².
- Ticket promedio.
- Ranking dentro de su formato.
- Marca BAJO_RENDIMIENTO si está por debajo del percentil 25 de GMV/m² dentro
  de su formato.
============================================================================ */
WITH params AS (
  SELECT
    DATE_SUB(MAX(DATE(transaction_date)), INTERVAL 3 MONTH) + 1 AS quarter_start,
    MAX(DATE(transaction_date)) AS quarter_end
  FROM `your_project.your_dataset.transactions`
), store_metrics AS (
  SELECT
    s.country,
    s.format,
    s.store_id,
    s.store_name,
    s.size_sqm,
    COUNT(DISTINCT t.transaction_id) AS transactions_count,
    SUM(t.total_amount) AS gmv_total,
    SAFE_DIVIDE(SUM(t.total_amount), NULLIF(s.size_sqm, 0)) AS gmv_per_sqm,
    SAFE_DIVIDE(COUNT(DISTINCT t.transaction_id), NULLIF(s.size_sqm, 0)) AS transactions_per_sqm,
    SAFE_DIVIDE(SUM(t.total_amount), COUNT(DISTINCT t.transaction_id)) AS avg_ticket
  FROM `your_project.your_dataset.transactions` AS t
  JOIN `your_project.your_dataset.stores` AS s
    ON s.store_id = t.store_id
  CROSS JOIN params AS p
  WHERE t.status = 'COMPLETED'
    AND DATE(t.transaction_date) BETWEEN p.quarter_start AND p.quarter_end
  GROUP BY s.country, s.format, s.store_id, s.store_name, s.size_sqm
), scored AS (
  SELECT
    *,
    PERCENTILE_CONT(gmv_per_sqm, 0.25) OVER (PARTITION BY country, format) AS p25_gmv_per_sqm,
    RANK() OVER (PARTITION BY country, format ORDER BY gmv_per_sqm DESC) AS productivity_rank_in_format
  FROM store_metrics
)
SELECT
  country,
  format,
  store_id,
  store_name,
  size_sqm,
  gmv_total,
  gmv_per_sqm,
  transactions_count,
  transactions_per_sqm,
  avg_ticket,
  productivity_rank_in_format,
  p25_gmv_per_sqm,
  CASE
    WHEN gmv_per_sqm < p25_gmv_per_sqm THEN 'BAJO_RENDIMIENTO'
    ELSE 'NORMAL'
  END AS performance_flag
FROM scored
ORDER BY country, format, productivity_rank_in_format;


/* ============================================================================
QUERY 3: Análisis de cohortes de clientes con tarjeta de lealtad
Retención

Para clientes identificados loyalty_card = TRUE:
- Define cohorte por mes de primera transacción.
- Calcula tamaño de cohorte.
- Retención mensual en meses 1, 2, 3 y 6.
- Ticket promedio de la cohorte en cada período.
- Indica si el ticket crece/decrece contra mes 0.

Salida pivoteada: cohortes en filas y meses en columnas.
============================================================================ */
WITH loyalty_transactions AS (
  SELECT
    customer_id,
    transaction_id,
    DATE(transaction_date) AS transaction_date,
    DATE_TRUNC(DATE(transaction_date), MONTH) AS transaction_month,
    total_amount
  FROM `your_project.your_dataset.transactions`
  WHERE status = 'COMPLETED'
    AND loyalty_card = TRUE
    AND customer_id IS NOT NULL
), customer_cohorts AS (
  SELECT
    customer_id,
    MIN(transaction_month) AS cohort_month
  FROM loyalty_transactions
  GROUP BY customer_id
), customer_month_activity AS (
  SELECT
    c.cohort_month,
    lt.customer_id,
    DATE_DIFF(lt.transaction_month, c.cohort_month, MONTH) AS months_since_first_tx,
    COUNT(DISTINCT lt.transaction_id) AS transactions_count,
    SUM(lt.total_amount) AS customer_month_gmv,
    SAFE_DIVIDE(SUM(lt.total_amount), COUNT(DISTINCT lt.transaction_id)) AS customer_month_avg_ticket
  FROM loyalty_transactions AS lt
  JOIN customer_cohorts AS c
    ON c.customer_id = lt.customer_id
  WHERE DATE_DIFF(lt.transaction_month, c.cohort_month, MONTH) IN (0, 1, 2, 3, 6)
  GROUP BY c.cohort_month, lt.customer_id, months_since_first_tx
), cohort_size AS (
  SELECT
    cohort_month,
    COUNT(DISTINCT customer_id) AS cohort_customers
  FROM customer_cohorts
  GROUP BY cohort_month
), cohort_period_metrics AS (
  SELECT
    cohort_month,
    months_since_first_tx,
    COUNT(DISTINCT customer_id) AS retained_customers,
    AVG(customer_month_avg_ticket) AS avg_ticket_retained_customers
  FROM customer_month_activity
  GROUP BY cohort_month, months_since_first_tx
), pivoted AS (
  SELECT
    cs.cohort_month,
    cs.cohort_customers,
    MAX(IF(cpm.months_since_first_tx = 0, cpm.retained_customers, NULL)) AS m0_active_customers,
    MAX(IF(cpm.months_since_first_tx = 1, cpm.retained_customers, NULL)) AS m1_retained_customers,
    MAX(IF(cpm.months_since_first_tx = 2, cpm.retained_customers, NULL)) AS m2_retained_customers,
    MAX(IF(cpm.months_since_first_tx = 3, cpm.retained_customers, NULL)) AS m3_retained_customers,
    MAX(IF(cpm.months_since_first_tx = 6, cpm.retained_customers, NULL)) AS m6_retained_customers,
    MAX(IF(cpm.months_since_first_tx = 0, cpm.avg_ticket_retained_customers, NULL)) AS m0_avg_ticket,
    MAX(IF(cpm.months_since_first_tx = 1, cpm.avg_ticket_retained_customers, NULL)) AS m1_avg_ticket,
    MAX(IF(cpm.months_since_first_tx = 2, cpm.avg_ticket_retained_customers, NULL)) AS m2_avg_ticket,
    MAX(IF(cpm.months_since_first_tx = 3, cpm.avg_ticket_retained_customers, NULL)) AS m3_avg_ticket,
    MAX(IF(cpm.months_since_first_tx = 6, cpm.avg_ticket_retained_customers, NULL)) AS m6_avg_ticket
  FROM cohort_size AS cs
  LEFT JOIN cohort_period_metrics AS cpm
    ON cpm.cohort_month = cs.cohort_month
  GROUP BY cs.cohort_month, cs.cohort_customers
)
SELECT
  cohort_month,
  cohort_customers,
  SAFE_DIVIDE(m1_retained_customers, cohort_customers) AS m1_retention_rate,
  SAFE_DIVIDE(m2_retained_customers, cohort_customers) AS m2_retention_rate,
  SAFE_DIVIDE(m3_retained_customers, cohort_customers) AS m3_retention_rate,
  SAFE_DIVIDE(m6_retained_customers, cohort_customers) AS m6_retention_rate,
  m0_avg_ticket,
  m1_avg_ticket,
  m2_avg_ticket,
  m3_avg_ticket,
  m6_avg_ticket,
  CASE
    WHEN m1_avg_ticket IS NULL THEN 'SIN_DATOS'
    WHEN m1_avg_ticket > m0_avg_ticket THEN 'CRECE'
    WHEN m1_avg_ticket < m0_avg_ticket THEN 'DECRECE'
    ELSE 'ESTABLE'
  END AS m1_ticket_trend_vs_m0,
  CASE
    WHEN m2_avg_ticket IS NULL THEN 'SIN_DATOS'
    WHEN m2_avg_ticket > m0_avg_ticket THEN 'CRECE'
    WHEN m2_avg_ticket < m0_avg_ticket THEN 'DECRECE'
    ELSE 'ESTABLE'
  END AS m2_ticket_trend_vs_m0,
  CASE
    WHEN m3_avg_ticket IS NULL THEN 'SIN_DATOS'
    WHEN m3_avg_ticket > m0_avg_ticket THEN 'CRECE'
    WHEN m3_avg_ticket < m0_avg_ticket THEN 'DECRECE'
    ELSE 'ESTABLE'
  END AS m3_ticket_trend_vs_m0,
  CASE
    WHEN m6_avg_ticket IS NULL THEN 'SIN_DATOS'
    WHEN m6_avg_ticket > m0_avg_ticket THEN 'CRECE'
    WHEN m6_avg_ticket < m0_avg_ticket THEN 'DECRECE'
    ELSE 'ESTABLE'
  END AS m6_ticket_trend_vs_m0
FROM pivoted
ORDER BY cohort_month;


/* ============================================================================
QUERY 4: GMROI por proveedor y categoría
Gross Margin Return on Investment

Para cada vendor/categoría calcula:
- GMV.
- Costo total.
- Margen bruto.
- GMROI = margen bruto / costo total.
- SKUs activos.
- Velocidad de venta = unidades / día.
- Marca vendors con GMROI < 1.
============================================================================ */
WITH params AS (
  SELECT
    MIN(DATE(transaction_date)) AS start_date,
    MAX(DATE(transaction_date)) AS end_date,
    DATE_DIFF(MAX(DATE(transaction_date)), MIN(DATE(transaction_date)), DAY) + 1 AS analysis_days
  FROM `your_project.your_dataset.transactions`
  WHERE status = 'COMPLETED'
), item_sales AS (
  SELECT
    COALESCE(v.vendor_id, p.vendor_id) AS vendor_id,
    COALESCE(v.vendor_name, 'VENDOR_NO_ENCONTRADO') AS vendor_name,
    p.category,
    ti.item_id,
    SUM(ti.quantity) AS units_sold,
    SUM(ti.quantity * ti.unit_price) AS gmv,
    SUM(ti.quantity * p.cost) AS total_cost
  FROM `your_project.your_dataset.transaction_items` AS ti
  JOIN `your_project.your_dataset.transactions` AS t
    ON t.transaction_id = ti.transaction_id
  JOIN `your_project.your_dataset.products` AS p
    ON p.item_id = ti.item_id
  LEFT JOIN `your_project.your_dataset.vendors` AS v
    ON v.vendor_id = p.vendor_id
  WHERE t.status = 'COMPLETED'
  GROUP BY vendor_id, vendor_name, p.category, ti.item_id
)
SELECT
  vendor_id,
  vendor_name,
  category,
  SUM(gmv) AS gmv,
  SUM(total_cost) AS total_cost,
  SUM(gmv - total_cost) AS gross_margin,
  SAFE_DIVIDE(SUM(gmv - total_cost), SUM(total_cost)) AS gmroi,
  COUNT(DISTINCT item_id) AS active_skus,
  SAFE_DIVIDE(SUM(units_sold), ANY_VALUE(p.analysis_days)) AS sales_velocity_units_per_day,
  CASE
    WHEN SAFE_DIVIDE(SUM(gmv - total_cost), SUM(total_cost)) < 1 THEN 'GMROI_MENOR_1'
    ELSE 'OK'
  END AS gmroi_flag
FROM item_sales
CROSS JOIN params AS p
GROUP BY vendor_id, vendor_name, category
ORDER BY gmroi ASC, gross_margin ASC;


/* ============================================================================
QUERY 5: Detección de posibles quiebres de stock
Análisis operativo

Un ítem tiene posible quiebre si pasó 3+ días consecutivos sin venta en una
store donde históricamente sí se vendía.

Metodología:
- Detecta gaps entre fechas consecutivas de venta por store/item.
- También detecta gaps al cierre del dataset usando anchor_date + 1 como
  siguiente venta virtual.
- Estima ventas promedio diarias antes del gap con ventana calendario de 28 días.
- GMV perdido estimado = GMV promedio diario previo x duración del gap.
============================================================================ */
WITH params AS (
  SELECT MAX(DATE(transaction_date)) AS anchor_date
  FROM `your_project.your_dataset.transactions`
  WHERE status = 'COMPLETED'
), daily_sales AS (
  SELECT
    t.store_id,
    ti.item_id,
    DATE(t.transaction_date) AS sale_date,
    SUM(ti.quantity) AS units_sold,
    SUM(ti.quantity * ti.unit_price) AS gmv
  FROM `your_project.your_dataset.transaction_items` AS ti
  JOIN `your_project.your_dataset.transactions` AS t
    ON t.transaction_id = ti.transaction_id
  WHERE t.status = 'COMPLETED'
  GROUP BY t.store_id, ti.item_id, sale_date
), sale_dates_with_sentinel AS (
  SELECT store_id, item_id, sale_date
  FROM daily_sales

  UNION ALL

  SELECT DISTINCT
    ds.store_id,
    ds.item_id,
    DATE_ADD(p.anchor_date, INTERVAL 1 DAY) AS sale_date
  FROM daily_sales AS ds
  CROSS JOIN params AS p
), gaps AS (
  SELECT
    store_id,
    item_id,
    DATE_ADD(LAG(sale_date) OVER (PARTITION BY store_id, item_id ORDER BY sale_date), INTERVAL 1 DAY) AS gap_start_date,
    DATE_SUB(sale_date, INTERVAL 1 DAY) AS gap_end_date,
    DATE_DIFF(
      sale_date,
      LAG(sale_date) OVER (PARTITION BY store_id, item_id ORDER BY sale_date),
      DAY
    ) - 1 AS gap_duration_days
  FROM sale_dates_with_sentinel
), candidate_gaps AS (
  SELECT *
  FROM gaps
  WHERE gap_duration_days >= 3
    AND gap_start_date IS NOT NULL
), pre_gap_calendar AS (
  SELECT
    cg.store_id,
    cg.item_id,
    cg.gap_start_date,
    cg.gap_end_date,
    cg.gap_duration_days,
    calendar_date
  FROM candidate_gaps AS cg,
  UNNEST(GENERATE_DATE_ARRAY(
    DATE_SUB(cg.gap_start_date, INTERVAL 28 DAY),
    DATE_SUB(cg.gap_start_date, INTERVAL 1 DAY)
  )) AS calendar_date
), pre_gap_sales AS (
  SELECT
    pgc.store_id,
    pgc.item_id,
    pgc.gap_start_date,
    pgc.gap_end_date,
    pgc.gap_duration_days,
    SAFE_DIVIDE(SUM(COALESCE(ds.units_sold, 0)), COUNT(*)) AS avg_daily_units_before_gap,
    SAFE_DIVIDE(SUM(COALESCE(ds.gmv, 0)), COUNT(*)) AS avg_daily_gmv_before_gap
  FROM pre_gap_calendar AS pgc
  LEFT JOIN daily_sales AS ds
    ON ds.store_id = pgc.store_id
   AND ds.item_id = pgc.item_id
   AND ds.sale_date = pgc.calendar_date
  GROUP BY pgc.store_id, pgc.item_id, pgc.gap_start_date, pgc.gap_end_date, pgc.gap_duration_days
)
SELECT
  pgs.store_id,
  s.store_name,
  pgs.item_id,
  pr.item_name,
  pr.category,
  pgs.gap_start_date,
  pgs.gap_end_date,
  pgs.gap_duration_days,
  pgs.avg_daily_units_before_gap AS ventas_promedio_diarias_antes_gap,
  pgs.avg_daily_gmv_before_gap,
  pgs.avg_daily_gmv_before_gap * pgs.gap_duration_days AS estimated_lost_gmv
FROM pre_gap_sales AS pgs
JOIN `your_project.your_dataset.products` AS pr
  ON pr.item_id = pgs.item_id
JOIN `your_project.your_dataset.stores` AS s
  ON s.store_id = pgs.store_id
WHERE pgs.avg_daily_units_before_gap > 0
ORDER BY estimated_lost_gmv DESC;


/* ============================================================================
QUERY 6: Impacto de promociones en ticket y volumen
Basket analysis

Usando was_on_promo en transaction_items:
- Compara por categoría transacciones con vs sin ítems en promo.
- Calcula ticket promedio y unidades promedio.
- Clasifica si hay basket uplift o si parece solo descuento/no uplift.

Nota:
- Sin precio regular/base no se puede medir descuento puro de forma exacta.
- Este query infiere uplift comparando GMV y unidades promedio por categoría.
============================================================================ */
WITH transaction_category_metrics AS (
  SELECT
    t.transaction_id,
    p.category,
    LOGICAL_OR(ti.was_on_promo) AS has_promo_item_in_category,
    SUM(ti.quantity) AS category_units,
    SUM(ti.quantity * ti.unit_price) AS category_gmv
  FROM `your_project.your_dataset.transactions` AS t
  JOIN `your_project.your_dataset.transaction_items` AS ti
    ON ti.transaction_id = t.transaction_id
  JOIN `your_project.your_dataset.products` AS p
    ON p.item_id = ti.item_id
  WHERE t.status = 'COMPLETED'
  GROUP BY t.transaction_id, p.category
), category_promo_comparison AS (
  SELECT
    category,
    has_promo_item_in_category,
    COUNT(DISTINCT transaction_id) AS transactions_count,
    AVG(category_gmv) AS avg_ticket_category,
    AVG(category_units) AS avg_units_category
  FROM transaction_category_metrics
  GROUP BY category, has_promo_item_in_category
), pivoted AS (
  SELECT
    category,
    MAX(IF(has_promo_item_in_category, transactions_count, NULL)) AS promo_transactions,
    MAX(IF(NOT has_promo_item_in_category, transactions_count, NULL)) AS non_promo_transactions,
    MAX(IF(has_promo_item_in_category, avg_ticket_category, NULL)) AS promo_avg_ticket,
    MAX(IF(NOT has_promo_item_in_category, avg_ticket_category, NULL)) AS non_promo_avg_ticket,
    MAX(IF(has_promo_item_in_category, avg_units_category, NULL)) AS promo_avg_units,
    MAX(IF(NOT has_promo_item_in_category, avg_units_category, NULL)) AS non_promo_avg_units
  FROM category_promo_comparison
  GROUP BY category
)
SELECT
  category,
  promo_transactions,
  non_promo_transactions,
  promo_avg_ticket,
  non_promo_avg_ticket,
  SAFE_DIVIDE(promo_avg_ticket - non_promo_avg_ticket, non_promo_avg_ticket) AS ticket_uplift_pct,
  promo_avg_units,
  non_promo_avg_units,
  SAFE_DIVIDE(promo_avg_units - non_promo_avg_units, non_promo_avg_units) AS units_uplift_pct,
  CASE
    WHEN promo_avg_units > non_promo_avg_units
     AND promo_avg_ticket > non_promo_avg_ticket
      THEN 'BASKET_UPLIFT_COMPRA_ADICIONAL'
    WHEN promo_avg_units > non_promo_avg_units
     AND promo_avg_ticket <= non_promo_avg_ticket
      THEN 'UPLIFT_UNIDADES_PERO_TICKET_NO_CRECE'
    WHEN promo_avg_units <= non_promo_avg_units
     AND promo_avg_ticket <= non_promo_avg_ticket
      THEN 'SIN_UPLIFT_POSIBLE_DESCUENTO'
    ELSE 'MIXTO_REVISAR_MARGEN'
  END AS promo_impact_interpretation
FROM pivoted
ORDER BY ticket_uplift_pct DESC, units_uplift_pct DESC;
