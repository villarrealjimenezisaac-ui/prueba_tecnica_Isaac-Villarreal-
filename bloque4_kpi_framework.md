# Bloque 4 — Diseño de KPIs desde Cero

**Entregable:** `bloque4_kpi_framework.md`  
**Programa:** Mejora de productividad de tiendas  
**Dataset base actual:** `transactions`, `transaction_items`, `stores`, `products`, `vendors`, `store_promotions`  
**Enfoque:** framework inicial implementable con datos actuales, señalando mejoras futuras cuando se requiera información adicional.

---

## 1. Objetivo del framework

El equipo directivo quiere mejorar la productividad de tiendas. Para eso, el framework debe medir no solo si la tienda vende más, sino **cómo** vende más:

- Si usa mejor su espacio físico.
- Si genera tráfico y tickets saludables.
- Si evita quiebres que destruyen venta potencial.
- Si los proveedores y categorías generan margen suficiente.
- Si las promociones realmente impulsan canasta y no solo descuentan venta que ya habría ocurrido.

La idea es evitar KPIs bonitos pero inútiles. Porque un dashboard lleno de numeritos sin decisión asociada es básicamente decoración corporativa con WiFi.

---

## 2. North Star Metric del programa

### North Star Metric: **GMV Productivo Ajustado por m²**

#### Definición exacta

GMV generado por metro cuadrado de tienda, ajustado por calidad comercial mediante margen bruto, disponibilidad operacional y experiencia básica del cliente.

Este KPI busca responder:

> “¿Qué tienda genera más valor comercial sostenible por cada metro cuadrado disponible?”

#### Fórmula conceptual

```text
GMV Productivo Ajustado por m² =
GMV por m²
× Índice de Margen
× Índice de Disponibilidad
× Índice de Experiencia
```

Donde:

```text
GMV por m² = GMV total / size_sqm

Índice de Margen = Margen bruto % de la tienda / Margen bruto % objetivo

Índice de Disponibilidad = 1 - Tasa de GMV perdido estimado por quiebres

Índice de Experiencia = combinación normalizada de ticket saludable, frecuencia y retención de clientes identificados
```

#### Implementación inicial con dataset actual

Con los datos actuales puede calcularse una versión inicial:

```text
GMV Productivo Ajustado por m² =
(GMV / size_sqm)
× (Margen bruto / GMV)
× (1 - GMV perdido estimado por quiebres / GMV potencial)
```

La parte de experiencia puede aproximarse con:

- Ticket promedio.
- Transacciones por m².
- Retención de clientes con loyalty card.

#### ¿Por qué esta North Star Metric?

Se elige porque alinea productividad, rentabilidad y ejecución operativa:

1. **Productividad:** mide venta por espacio, no solo venta absoluta.
2. **Rentabilidad:** evita premiar tiendas que venden mucho pero con bajo margen.
3. **Operación:** penaliza quiebres de stock que destruyen venta potencial.
4. **Cliente:** incorpora señales de frecuencia, ticket y retención.
5. **Comparabilidad:** permite comparar tiendas de tamaños distintos dentro del mismo formato.

No se recomienda usar solo GMV como North Star porque favorece tiendas grandes y puede esconder problemas de margen, espacio improductivo o mala disponibilidad. GMV solo es como medir salud por estatura: algo dice, pero no suficiente.

---

## 3. Principios de diseño de KPIs

1. **Cada KPI debe tener dueño operativo.** Si nadie puede accionar el KPI, es ruido.
2. **Cada KPI debe tener fórmula única.** Nada de “GMV versión finanzas”, “GMV versión retail”, “GMV versión mi Excel”.
3. **Separar resultados de causas.** GMV es resultado; quiebres, disponibilidad, tráfico y ticket son palancas.
4. **Medir por formato.** HIPERMERCADO, SUPERMERCADO, DESCUENTO y EXPRESS no deben compararse sin contexto.
5. **Usar percentiles al inicio.** Cuando no hay benchmark externo, el benchmark interno es más honesto.
6. **Tener controles de calidad.** Un KPI sin validación de datos es una trampa con colores bonitos.

---

## 4. Framework de KPIs

> Nota: Los targets sugeridos son benchmarks iniciales. Deben recalibrarse después de 8 a 12 semanas de operación formal.

| # | Dimensión | KPI | Definición exacta | Fórmula | Frecuencia | Fuente de datos | Target sugerido | ¿Cómo detectas si el dato está mal? |
|---:|---|---|---|---|---|---|---|---|
| 1 | Productividad de tienda | **GMV por m²** | Venta bruta generada por cada metro cuadrado de tienda en un período. | `SUM(total_amount) / size_sqm` usando solo transacciones `COMPLETED`. | Diario con cierre semanal y mensual. | `transactions`, `stores`. | Estar por encima del percentil 50 dentro del mismo formato; objetivo aspiracional P75. | `size_sqm <= 0`, tienda sin metraje, GMV negativo, saltos WoW > 3 desviaciones estándar, transacciones antes de `opening_date`. |
| 2 | Productividad de tienda | **Transacciones por m²** | Número de tickets generados por metro cuadrado. Mide productividad de tráfico y conversión operacional. | `COUNT(DISTINCT transaction_id) / size_sqm`. | Diario / semanal. | `transactions`, `stores`. | P50 dentro del formato; alerta si cae bajo P25 por 2 semanas consecutivas. | Duplicados de `transaction_id`, tienda sin ventas en horario esperado, `size_sqm` nulo, caída abrupta sin explicación promocional/operativa. |
| 3 | Productividad de tienda | **Ticket promedio** | GMV promedio por transacción completada. | `SUM(total_amount) / COUNT(DISTINCT transaction_id)`. | Diario / semanal / mensual. | `transactions`. | Mantener o crecer vs promedio móvil de 8 semanas; no caer más de 5% sin justificación. | `total_amount <= 0`, tickets extremos > P99.9, diferencias entre `total_amount` y suma de líneas `quantity * unit_price`. |
| 4 | Productividad de tienda | **Índice de Productividad de Tienda** **(KPI compuesto)** | Score compuesto que resume productividad espacial, tráfico y ticket, normalizado contra tiendas del mismo formato. | `0.50 * percentile_rank(GMV/m²) + 0.30 * percentile_rank(transacciones/m²) + 0.20 * percentile_rank(ticket_promedio)` por formato. | Semanal y mensual. | KPIs 1, 2 y 3 derivados de `transactions`, `stores`. | Score >= 0.60; alto desempeño >= 0.75; bajo desempeño < 0.25. | Si algún componente falta, si hay outliers extremos sin winsorización, si la tienda tiene menos de X días operativos, si el formato tiene muestra insuficiente. |
| 5 | Experiencia del cliente | **Retención M1 de clientes loyalty** | Porcentaje de clientes identificados cuya primera compra fue en un mes dado y que vuelven al mes siguiente. | `clientes_retenidos_mes_1 / clientes_cohorte_mes_0`, solo `loyalty_card = TRUE` y `customer_id IS NOT NULL`. | Mensual. | `transactions`. | Mejorar +3 pp vs promedio de cohortes anteriores; alerta si cae bajo P25 histórico. | `customer_id` nulo con `loyalty_card = TRUE`, cambios en captura de loyalty, cohortes incompletas, meses recientes sin ventana suficiente para madurar. |
| 6 | Experiencia del cliente | **Frecuencia de compra loyalty** | Número promedio de transacciones por cliente identificado activo en el período. | `COUNT(DISTINCT transaction_id) / COUNT(DISTINCT customer_id)` para clientes con loyalty. | Mensual. | `transactions`. | Crecimiento mensual >= 2% o mantenerse sobre promedio móvil 3 meses. | Duplicidad de tickets, clientes anónimos mezclados, cambios bruscos en proporción de `loyalty_card = TRUE`, IDs inválidos. |
| 7 | Experiencia del cliente / Operación | **Riesgo de quiebre de stock** **(Leading indicator)** | Señal temprana de posible quiebre: ítems con venta histórica que acumulan 2 días sin venta antes de convertirse en gap crítico de 3+ días. | `COUNT(store_id, item_id con 2 días consecutivos sin venta y venta promedio previa > 0)`; priorizar por `GMV promedio diario previo`. | Diario. | `transactions`, `transaction_items`, `products`. Ideal futuro: inventario on-hand. | Reducir casos de alto riesgo 20% en 8 semanas; cero riesgo alto en SKUs top 20% GMV. | Falsos positivos por tienda cerrada, productos descontinuados, promociones terminadas, calendario operativo no considerado, baja demanda normal confundida con quiebre. |
| 8 | Desempeño de proveedor | **GMROI por vendor-categoría** | Retorno de margen bruto sobre costo para cada proveedor y categoría. Mide si el inventario vendido genera margen suficiente. | `(SUM(quantity * unit_price) - SUM(quantity * cost)) / SUM(quantity * cost)`. | Semanal / mensual. | `transaction_items`, `transactions`, `products`, `vendors`. | GMROI >= 1.0 mínimo; objetivo >= P50 por categoría; alerta crítica < 1.0. | Costos nulos o cero, vendor inexistente, precio unitario cero sin promo, margen imposible, cambios de costo no versionados. |
| 9 | Desempeño de proveedor | **Velocidad de venta por SKU activo** | Unidades vendidas por día para SKUs activos de un proveedor/categoría. | `SUM(quantity) / días_con_venta_o_días_periodo` por vendor, categoría y SKU activo. | Semanal. | `transaction_items`, `transactions`, `products`, `vendors`. | Estar sobre P50 de categoría; alerta si SKU top cae > 30% vs promedio 4 semanas. | SKUs sin maestro, ventas duplicadas, períodos incompletos, producto nuevo sin historia, quiebres confundidos con baja demanda. |
| 10 | Promociones / Experiencia comercial | **Basket Uplift Promocional** | Diferencia porcentual de unidades y GMV promedio entre transacciones con ítems promocionados y sin promoción, por categoría. | `uplift_ticket = (ticket_promo - ticket_no_promo) / ticket_no_promo`; `uplift_unidades = (unidades_promo - unidades_no_promo) / unidades_no_promo`. | Por campaña y semanal durante promoción. | `transaction_items`, `transactions`, `products`, `store_promotions`. | Uplift de unidades > 0 y uplift de ticket >= 0; si ticket cae, validar margen incremental. | `was_on_promo` inconsistente, campañas sin fechas, tiendas en CONTROL/TREATMENT duplicadas, falta precio regular para medir descuento real. |

---

## 5. Cobertura de restricciones

| Restricción | Cumplimiento |
|---|---|
| Mínimo 6 KPIs | Se proponen 10 KPIs. |
| Al menos 3 dimensiones | Productividad de tienda, experiencia del cliente, desempeño de proveedor y promociones. |
| Al menos un leading indicator | `Riesgo de quiebre de stock`. |
| Al menos un KPI compuesto | `Índice de Productividad de Tienda`. |
| North Star Metric definida | `GMV Productivo Ajustado por m²`. |
| Detección de datos malos | Incluida para cada KPI. |

---

## 6. Detalle de targets sugeridos

Como todavía no existe un framework histórico formal, los targets no deberían inventarse como si vinieran grabados en piedra. La recomendación es iniciar con **benchmarks internos por formato**:

### Productividad de tienda

- Usar percentiles por formato: HIPERMERCADO contra HIPERMERCADO, DESCUENTO contra DESCUENTO, etc.
- Target inicial: superar P50.
- Bajo rendimiento: debajo de P25 durante 2 períodos consecutivos.
- Alto rendimiento: P75 o superior sostenido por 4 semanas.

### Experiencia del cliente

- Retención M1: mejorar +3 puntos porcentuales vs promedio de cohortes históricas.
- Frecuencia loyalty: crecer 2% mensual o sostenerse sobre promedio móvil de 3 meses.
- Ticket promedio: no caer más de 5% vs promedio móvil salvo estrategia promocional explícita.

### Desempeño de proveedor

- GMROI mínimo: 1.0.
- Vendors con GMROI < 1 deben entrar en revisión comercial.
- Velocidad de venta: comparar contra P50 de la categoría.
- SKUs top con caída > 30% deben revisarse por disponibilidad, precio o demanda.

### Promociones

- Una promoción saludable debe generar al menos uno de estos efectos:
  - Más unidades por transacción.
  - Mayor ticket promedio.
  - Mejor margen absoluto.
  - Mayor retención o recompra posterior.

Si solo reduce precio sin aumentar volumen, ticket, margen o retención, no es promoción: es regalar margen con moño.

---

## 7. Reglas de calidad transversales

Estas validaciones deberían ejecutarse antes de publicar KPIs:

| Control | Regla | Acción si falla |
|---|---|---|
| Completitud de transacciones | Cada tienda activa debe reportar ventas dentro del SLA esperado. | Marcar tienda como `DATA_DELAYED` y excluir de ranking diario hasta completar. |
| Duplicados | `transaction_id` y `transaction_item_id` no deben duplicarse. | Deduplicar en staging con última versión por timestamp de ingesta. |
| Integridad referencial | Todo `store_id`, `item_id`, `vendor_id` debe existir en maestros. | Enviar a cola de remediación; usar categoría/vendor `NO_ENCONTRADO` temporalmente. |
| Validez financiera | `total_amount > 0`, `quantity > 0`, `unit_price >= 0`, `cost >= 0`. | Excluir de KPIs financieros si viola reglas críticas. |
| Consistencia ticket-líneas | `transactions.total_amount` debe reconciliar con `SUM(quantity * unit_price)` dentro de tolerancia. | Usar suma de líneas como métrica analítica hasta reconciliar. |
| Frescura | Última transacción por tienda no debe exceder umbral operativo. | Alertar a DataOps/Operaciones. |
| Calendario operativo | No evaluar quiebres o tráfico cuando tienda está cerrada. | Requiere calendario operativo futuro. |

---

## 8. KPIs implementables hoy vs fuentes futuras recomendadas

### Implementables con dataset actual

Se pueden implementar hoy:

1. GMV por m².
2. Transacciones por m².
3. Ticket promedio.
4. Índice de Productividad de Tienda.
5. Retención M1 de clientes loyalty.
6. Frecuencia de compra loyalty.
7. Riesgo de quiebre de stock aproximado por gaps de venta.
8. GMROI por vendor-categoría.
9. Velocidad de venta por SKU activo.
10. Basket Uplift Promocional.

### Fuentes futuras recomendadas

Para madurar el framework, conviene agregar:

| Fuente futura | Para qué sirve |
|---|---|
| Inventario on-hand por tienda/SKU/día | Confirmar quiebres reales, no solo inferidos por falta de venta. |
| Calendario operativo de tienda | Evitar alertas falsas cuando una tienda está cerrada. |
| Tráfico de tienda / footfall | Separar problema de tráfico vs conversión. |
| NPS / encuestas cliente | Medir experiencia real, no solo comportamiento transaccional. |
| Devoluciones y cancelaciones | Calcular GMV neto y calidad de venta. |
| Costos logísticos por proveedor | Mejorar GMROI hacia rentabilidad total, no solo margen bruto. |
| Planogramas / espacio por categoría | Medir productividad por m² de categoría, no solo por tienda completa. |

---

## 9. Cadencia de gestión recomendada

| Frecuencia | Revisión | Participantes | Decisiones esperadas |
|---|---|---|---|
| Diario | Frescura de datos, riesgo de quiebre, ventas anómalas. | Operaciones tienda, DataOps. | Resolver tiendas sin datos, revisar SKUs críticos. |
| Semanal | Productividad por tienda, GMV/m², transacciones/m², ticket, promociones. | Operaciones, Comercial, Merchandising. | Acciones por tienda/formato, ajustes de exhibición o promo. |
| Mensual | GMROI, retención loyalty, ranking de proveedores, productividad sostenida. | Dirección, Finanzas, Supply Chain, Comercial. | Rebalanceo de surtido, negociación con vendors, metas por formato. |
| Trimestral | North Star Metric, evolución del programa, rediseño de targets. | Comité directivo. | Escalar iniciativas, cerrar brechas estructurales, inversión. |

---

## 10. Cómo usar el framework para decidir

### Si una tienda tiene bajo GMV por m²

Revisar en este orden:

1. ¿Tiene baja transacción por m²?  
   - Problema probable: tráfico/conversión.
2. ¿Tiene buen tráfico pero bajo ticket?  
   - Problema probable: mix, canasta o promoción mal diseñada.
3. ¿Tiene quiebres altos?  
   - Problema probable: abastecimiento.
4. ¿Tiene GMROI bajo?  
   - Problema probable: vende, pero con margen insuficiente.

### Si un proveedor tiene GMROI bajo

Revisar:

1. Costo unitario.
2. Precio de venta.
3. Profundidad promocional.
4. Categorías donde participa.
5. Velocidad de venta.
6. Posibles quiebres.

### Si una promoción sube unidades pero baja ticket/margen

No aprobar rollout automático. Revisar:

1. Margen incremental.
2. Canibalización.
3. Comparación CONTROL/TREATMENT.
4. Recompra posterior.
5. Costo de implementación.

---

## 11. Recomendación final

El programa debe gestionarse con una North Star Metric clara: **GMV Productivo Ajustado por m²**. Esta métrica evita premiar crecimiento superficial y obliga a balancear venta, espacio, margen, disponibilidad y comportamiento del cliente.

Para arrancar, se recomienda implementar primero estos 6 KPIs mínimos:

1. GMV por m².
2. Transacciones por m².
3. Ticket promedio.
4. Índice de Productividad de Tienda.
5. Riesgo de quiebre de stock.
6. GMROI por vendor-categoría.

Luego, en una segunda fase, robustecer experiencia de cliente con retención, frecuencia loyalty y fuentes externas como NPS/footfall.

El framework debe revisarse mensualmente durante los primeros tres meses. Los targets iniciales por percentil deben recalibrarse cuando haya suficiente historia bajo reglas consistentes. Porque sí: medir mal durante mucho tiempo no convierte el dato en verdad, solo en tradición con dashboard.
