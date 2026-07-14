-- bloque3_queries.sql
-- Motor: BigQuery Standard SQL
-- Reemplaza `your_project.your_dataset` por el proyecto/dataset real.
-- Dataset base: transactions, transaction_items, stores, products, vendors, store_promotions.

/* ============================================================================
PARTE A / P1: Estacionalidad por formato
GMV semanal por formato, sensibilidad estacional por coeficiente de variación,
y 3 picos / 3 caídas WoW más significativas del período.
============================================================================ */
WITH weekly_format AS (
  SELECT
    DATE_TRUNC(DATE(t.transaction_date), WEEK(SUNDAY)) AS week_start,
    s.format,
    SUM(t.total_amount) AS weekly_gmv
  FROM `your_project.your_dataset.transactions` t
  JOIN `your_project.your_dataset.stores` s USING (store_id)
  WHERE t.status = 'COMPLETED'
  GROUP BY week_start, s.format
), sensitivity AS (
  SELECT
    format,
    AVG(weekly_gmv) AS avg_weekly_gmv,
    STDDEV_SAMP(weekly_gmv) AS sd_weekly_gmv,
    SAFE_DIVIDE(STDDEV_SAMP(weekly_gmv), AVG(weekly_gmv)) AS seasonality_cv
  FROM weekly_format
  GROUP BY format
), total_weekly AS (
  SELECT week_start, SUM(weekly_gmv) AS total_weekly_gmv
  FROM weekly_format
  GROUP BY week_start
), wow AS (
  SELECT
    week_start,
    total_weekly_gmv,
    total_weekly_gmv - LAG(total_weekly_gmv) OVER (ORDER BY week_start) AS wow_change,
    SAFE_DIVIDE(
      total_weekly_gmv - LAG(total_weekly_gmv) OVER (ORDER BY week_start),
      LAG(total_weekly_gmv) OVER (ORDER BY week_start)
    ) AS wow_change_pct
  FROM total_weekly
)
SELECT 'SENSITIVITY' AS section, format AS dimension, NULL AS week_start,
       avg_weekly_gmv AS metric_1, seasonality_cv AS metric_2
FROM sensitivity
UNION ALL
SELECT 'TOP_3_PEAKS', NULL, week_start, total_weekly_gmv, wow_change_pct
FROM wow
WHERE wow_change IS NOT NULL
QUALIFY ROW_NUMBER() OVER (ORDER BY wow_change DESC) <= 3
UNION ALL
SELECT 'TOP_3_DROPS', NULL, week_start, total_weekly_gmv, wow_change_pct
FROM wow
WHERE wow_change IS NOT NULL
QUALIFY ROW_NUMBER() OVER (ORDER BY wow_change ASC) <= 3
ORDER BY section, metric_2 DESC;


/* ============================================================================
PARTE A / P2: Pareto de categorías por formato
Categorías que concentran el 80% del GMV por formato.
============================================================================ */
WITH category_format AS (
  SELECT
    s.format,
    p.category,
    SUM(ti.quantity * ti.unit_price) AS gmv
  FROM `your_project.your_dataset.transaction_items` ti
  JOIN `your_project.your_dataset.transactions` t USING (transaction_id)
  JOIN `your_project.your_dataset.stores` s USING (store_id)
  JOIN `your_project.your_dataset.products` p USING (item_id)
  WHERE t.status = 'COMPLETED'
  GROUP BY s.format, p.category
), ranked AS (
  SELECT
    *,
    SUM(gmv) OVER (PARTITION BY format ORDER BY gmv DESC) AS cumulative_gmv,
    SUM(gmv) OVER (PARTITION BY format) AS total_format_gmv
  FROM category_format
), with_prior AS (
  SELECT
    *,
    SAFE_DIVIDE(cumulative_gmv, total_format_gmv) AS cumulative_pct,
    LAG(SAFE_DIVIDE(cumulative_gmv, total_format_gmv), 1, 0)
      OVER (PARTITION BY format ORDER BY gmv DESC) AS prior_cumulative_pct
  FROM ranked
)
SELECT
  format,
  category,
  gmv,
  cumulative_gmv,
  total_format_gmv,
  cumulative_pct
FROM with_prior
WHERE prior_cumulative_pct < 0.80
ORDER BY format, gmv DESC;


/* ============================================================================
PARTE A / P3: Cohortes de lealtad
Retención M1/M2/M3/M6 y ticket promedio de clientes retenidos.
============================================================================ */
WITH loyalty_tx AS (
  SELECT
    customer_id,
    transaction_id,
    DATE_TRUNC(DATE(transaction_date), MONTH) AS tx_month,
    total_amount
  FROM `your_project.your_dataset.transactions`
  WHERE status = 'COMPLETED'
    AND loyalty_card = TRUE
    AND customer_id IS NOT NULL
), cohorts AS (
  SELECT customer_id, MIN(tx_month) AS cohort_month
  FROM loyalty_tx
  GROUP BY customer_id
), activity AS (
  SELECT
    c.cohort_month,
    DATE_DIFF(lt.tx_month, c.cohort_month, MONTH) AS months_since_first_tx,
    lt.customer_id,
    COUNT(DISTINCT lt.transaction_id) AS tx_count,
    SUM(lt.total_amount) AS gmv
  FROM loyalty_tx lt
  JOIN cohorts c USING (customer_id)
  WHERE DATE_DIFF(lt.tx_month, c.cohort_month, MONTH) IN (0, 1, 2, 3, 6)
  GROUP BY c.cohort_month, months_since_first_tx, lt.customer_id
), cohort_size AS (
  SELECT cohort_month, COUNT(DISTINCT customer_id) AS cohort_customers
  FROM cohorts
  GROUP BY cohort_month
), metrics AS (
  SELECT
    cohort_month,
    months_since_first_tx,
    COUNT(DISTINCT customer_id) AS retained_customers,
    SAFE_DIVIDE(SUM(gmv), SUM(tx_count)) AS avg_ticket_retained
  FROM activity
  GROUP BY cohort_month, months_since_first_tx
)
SELECT
  cs.cohort_month,
  cs.cohort_customers,
  SAFE_DIVIDE(MAX(IF(months_since_first_tx = 1, retained_customers, NULL)), cs.cohort_customers) AS m1_retention,
  SAFE_DIVIDE(MAX(IF(months_since_first_tx = 2, retained_customers, NULL)), cs.cohort_customers) AS m2_retention,
  SAFE_DIVIDE(MAX(IF(months_since_first_tx = 3, retained_customers, NULL)), cs.cohort_customers) AS m3_retention,
  SAFE_DIVIDE(MAX(IF(months_since_first_tx = 6, retained_customers, NULL)), cs.cohort_customers) AS m6_retention,
  MAX(IF(months_since_first_tx = 0, avg_ticket_retained, NULL)) AS m0_avg_ticket,
  MAX(IF(months_since_first_tx = 1, avg_ticket_retained, NULL)) AS m1_avg_ticket,
  MAX(IF(months_since_first_tx = 2, avg_ticket_retained, NULL)) AS m2_avg_ticket,
  MAX(IF(months_since_first_tx = 3, avg_ticket_retained, NULL)) AS m3_avg_ticket,
  MAX(IF(months_since_first_tx = 6, avg_ticket_retained, NULL)) AS m6_avg_ticket
FROM cohort_size cs
LEFT JOIN metrics m USING (cohort_month)
GROUP BY cs.cohort_month, cs.cohort_customers
ORDER BY cohort_month;


/* ============================================================================
PARTE A / P4: Quiebres de stock e impacto
Gaps de 3+ días sin venta para store/item con venta histórica; GMV perdido
estimado con promedio diario de GMV de los 28 días anteriores.
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
  FROM `your_project.your_dataset.transaction_items` ti
  JOIN `your_project.your_dataset.transactions` t USING (transaction_id)
  WHERE t.status = 'COMPLETED'
  GROUP BY t.store_id, ti.item_id, sale_date
), dates_with_sentinel AS (
  SELECT store_id, item_id, sale_date FROM daily_sales
  UNION ALL
  SELECT DISTINCT store_id, item_id, DATE_ADD(anchor_date, INTERVAL 1 DAY)
  FROM daily_sales CROSS JOIN params
), gaps AS (
  SELECT
    store_id,
    item_id,
    DATE_ADD(LAG(sale_date) OVER (PARTITION BY store_id, item_id ORDER BY sale_date), INTERVAL 1 DAY) AS gap_start,
    DATE_SUB(sale_date, INTERVAL 1 DAY) AS gap_end,
    DATE_DIFF(sale_date, LAG(sale_date) OVER (PARTITION BY store_id, item_id ORDER BY sale_date), DAY) - 1 AS gap_days
  FROM dates_with_sentinel
), candidate_gaps AS (
  SELECT * FROM gaps WHERE gap_days >= 3 AND gap_start IS NOT NULL
), pregap_calendar AS (
  SELECT cg.*, d AS calendar_date
  FROM candidate_gaps cg,
  UNNEST(GENERATE_DATE_ARRAY(DATE_SUB(gap_start, INTERVAL 28 DAY), DATE_SUB(gap_start, INTERVAL 1 DAY))) d
), scored AS (
  SELECT
    pc.store_id,
    pc.item_id,
    pc.gap_start,
    pc.gap_end,
    pc.gap_days,
    SAFE_DIVIDE(SUM(COALESCE(ds.units_sold, 0)), COUNT(*)) AS avg_daily_units_before,
    SAFE_DIVIDE(SUM(COALESCE(ds.gmv, 0)), COUNT(*)) AS avg_daily_gmv_before
  FROM pregap_calendar pc
  LEFT JOIN daily_sales ds
    ON ds.store_id = pc.store_id
   AND ds.item_id = pc.item_id
   AND ds.sale_date = pc.calendar_date
  GROUP BY pc.store_id, pc.item_id, pc.gap_start, pc.gap_end, pc.gap_days
)
SELECT
  sc.store_id,
  sc.item_id,
  p.category,
  p.vendor_id,
  COALESCE(v.vendor_name, 'VENDOR_NO_ENCONTRADO') AS vendor_name,
  sc.gap_start,
  sc.gap_end,
  sc.gap_days,
  sc.avg_daily_gmv_before,
  sc.avg_daily_gmv_before * sc.gap_days AS estimated_lost_gmv
FROM scored sc
JOIN `your_project.your_dataset.products` p USING (item_id)
LEFT JOIN `your_project.your_dataset.vendors` v USING (vendor_id)
WHERE sc.avg_daily_units_before > 0
ORDER BY estimated_lost_gmv DESC;


/* ============================================================================
PARTE A / P5: Hallazgo libre
Proxy de descuento por categoría: precio promedio unitario en promo vs no promo.
============================================================================ */
SELECT
  p.category,
  SAFE_DIVIDE(SUM(IF(ti.was_on_promo, ti.quantity * ti.unit_price, 0)), SUM(IF(ti.was_on_promo, ti.quantity, 0))) AS promo_avg_unit_price,
  SAFE_DIVIDE(SUM(IF(NOT ti.was_on_promo, ti.quantity * ti.unit_price, 0)), SUM(IF(NOT ti.was_on_promo, ti.quantity, 0))) AS non_promo_avg_unit_price,
  SAFE_DIVIDE(
    SAFE_DIVIDE(SUM(IF(ti.was_on_promo, ti.quantity * ti.unit_price, 0)), SUM(IF(ti.was_on_promo, ti.quantity, 0)))
      - SAFE_DIVIDE(SUM(IF(NOT ti.was_on_promo, ti.quantity * ti.unit_price, 0)), SUM(IF(NOT ti.was_on_promo, ti.quantity, 0))),
    SAFE_DIVIDE(SUM(IF(NOT ti.was_on_promo, ti.quantity * ti.unit_price, 0)), SUM(IF(NOT ti.was_on_promo, ti.quantity, 0)))
  ) AS discount_proxy_pct,
  SUM(IF(ti.was_on_promo, ti.quantity * ti.unit_price, 0)) AS promo_gmv
FROM `your_project.your_dataset.transaction_items` ti
JOIN `your_project.your_dataset.transactions` t USING (transaction_id)
JOIN `your_project.your_dataset.products` p USING (item_id)
WHERE t.status = 'COMPLETED'
GROUP BY p.category
ORDER BY discount_proxy_pct ASC;


/* ============================================================================
PARTE B: A/B test de exhibición
Supuesto requerido: tiendas conflictivas TIENDA_008 y TIENDA_037 se tratan como CONTROL.
BigQuery no trae t-test nativo universal; este query entrega la tabla agregada para
calcular Welch t-test en Python/R/Sheets. Incluye base pre-test y test.
============================================================================ */
WITH assignment_raw AS (
  SELECT store_id, ARRAY_AGG(DISTINCT variant) AS variants
  FROM `your_project.your_dataset.store_promotions`
  WHERE promo_name = 'Exhibicion_Q3_2024'
  GROUP BY store_id
), assignment AS (
  SELECT
    store_id,
    CASE
      WHEN store_id IN ('TIENDA_008', 'TIENDA_037') THEN 'CONTROL'
      WHEN 'TREATMENT' IN UNNEST(variants) THEN 'TREATMENT'
      ELSE 'CONTROL'
    END AS experiment_group,
    ARRAY_LENGTH(variants) > 1 AS had_conflict
  FROM assignment_raw
), weekly_store AS (
  SELECT
    a.experiment_group,
    a.had_conflict,
    t.store_id,
    s.format,
    s.size_sqm,
    DATE_TRUNC(DATE(t.transaction_date), WEEK(SUNDAY)) AS week_start,
    SUM(t.total_amount) AS weekly_gmv,
    COUNT(DISTINCT t.transaction_id) AS weekly_transactions,
    SAFE_DIVIDE(SUM(t.total_amount), COUNT(DISTINCT t.transaction_id)) AS avg_ticket
  FROM `your_project.your_dataset.transactions` t
  JOIN assignment a USING (store_id)
  JOIN `your_project.your_dataset.stores` s USING (store_id)
  WHERE t.status = 'COMPLETED'
    AND DATE(t.transaction_date) BETWEEN DATE '2024-07-21' AND DATE '2024-10-12'
  GROUP BY a.experiment_group, a.had_conflict, t.store_id, s.format, s.size_sqm, week_start
)
SELECT
  experiment_group,
  store_id,
  format,
  size_sqm,
  had_conflict,
  AVG(IF(week_start BETWEEN DATE '2024-07-21' AND DATE '2024-08-31', weekly_gmv, NULL)) AS pre_avg_weekly_gmv,
  AVG(IF(week_start BETWEEN DATE '2024-09-01' AND DATE '2024-10-12', weekly_gmv, NULL)) AS test_avg_weekly_gmv,
  AVG(IF(week_start BETWEEN DATE '2024-09-01' AND DATE '2024-10-12', weekly_transactions, NULL)) AS test_avg_weekly_transactions,
  AVG(IF(week_start BETWEEN DATE '2024-09-01' AND DATE '2024-10-12', avg_ticket, NULL)) AS test_avg_ticket
FROM weekly_store
GROUP BY experiment_group, store_id, format, size_sqm, had_conflict
ORDER BY experiment_group, store_id;
