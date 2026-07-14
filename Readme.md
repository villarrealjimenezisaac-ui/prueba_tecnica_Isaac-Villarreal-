Uso de la IA para resolución de prueba técnica



**Bloque 0**

Preguntas a la IA trabajando los archivos CSV

* ¿Qué porcentaje de transacciones no tiene customer\_id ? ¿Es consistente con loyalty\_card = FALSE ?

  * Se revisaron los datos que sean consistentes
* ¿El total\_amount en transactions coincide con la suma de unit\_price × quantity en transaction\_items ?

  * Se revisaron datos que sean consistentes
* Determinar si existen ¿Existen transaction\_id duplicados? Respuesta en k61

  * Se revisaron datos que sean consistentes
* ¿Hay total\_amount negativos o cero? ¿Hay unit\_price = 0 con was\_on\_promo = FALSE? respuesta en k65

  * Se revisaron datos que sean consistentes
* ¿Hay store\_id en pestaña transactions que no existan en pestaña stores ? ¿ vendor\_id en pestaña products que no existan en pestaña vendors ?

  * se revisaron dato que sean consistentes
* ¿Hay tiendas con gaps de días consecutivos sin transacciones? ¿Son esperables o sospechosos?

  * Se tuvo que alinear a la IA con aclaración (Recordemos que la base de datos tiene una base de fecha de 01012024, entonces la fecha de apartura es solo para validar que no existan transacciones antes de la fecha de apertura el resto de transacciones solo contemplan el periodo de la base de datos que es del 01012024 al 30062025 ?)
  * Se realizó el mismo ejercicio con Puppy y se detectó si existen tiendas con GAP en fechas, se volvió a reenfocar a Copilot "HAciendo una revión veo que la  TIENDA\_012 no tiene los 547 días, puedes revisar la logica de analisis"
* A/B Test ¿Hay tiendas asignadas simultáneamente a CONTROL y TREATMENT en pestaña store\_promotions ? resultados en 02 de pesataña Store\_promotions

  * Se hizo un comparativo del análisis de puppy contra lo documentado y se confirmó similitud en el análisis y se confirmó una especie de auditoría de la auditoría realizada con Copilot







**Bloque 1**

Para el bloque 1 como no sé crear SQL utilicé Puppy para crearlo con el siguiente prompt



Debo crear un ENTREGABLE: bloque1\_queries.sql



Con varios Querys



Query 1 Ventas comparables (Comp Sales)

Métrica estándar de retail

Calcula el crecimiento YoY solo para tiendas que estuvieron operando en ambos períodos (excluye tiendas abiertas

hace menos de 13 meses). Por país y formato muestra:

GMV año actual vs. año anterior

Comp Sales Growth %

Ranking de tiendas por crecimiento dentro de su formato

Query 2 Productividad por metro cuadrado

KPI operativo

Para cada tienda calcula GMV total del último trimestre, GMV/m², número de transacciones/m², ticket promedio y

ranking dentro de su formato.

Identifica las tiendas por debajo del percentil 25 de GMV/m² dentro de su formato — márcalas como

BAJO\_RENDIMIENTO .

Query 3 Análisis de cohortes de clientes con tarjeta de lealtad

Retención

Para clientes identificados ( loyalty\_card = TRUE ), define la cohorte por mes de primera transacción. Calcula:

Tamaño de cada cohorte (clientes únicos)

Tasa de retención mensual: % que volvió en los meses 1, 2, 3 y 6

Ticket promedio de la cohorte en cada período

Si el ticket crece o decrece con el tiempo para los clientes retenidos

Resultado esperado: tabla pivoteada con cohortes en filas y meses en columnas.

Query 4 GMROI por proveedor y categoría

Gross Margin Return on Investment

Para cada combinación de vendor y categoría calcula GMV, costo total, margen bruto, GMROI = Margen Bruto / Costo

Total, SKUs activos y velocidad de venta (unidades/día).

Marca los vendors con GMROI < 1 — están generando menos margen que lo que cuestan.

Query 5 Detección de posibles quiebres de stock

Análisis operativo

Un ítem tiene un posible quiebre si pasó 3 o más días consecutivos sin registrar ninguna venta en una tienda donde

históricamente sí lo vendía.

Devuelve: tienda, ítem, categoría, fechas del gap, duración en días, ventas promedio diarias antes del gap y GMV

estimado perdido.

Ordena por GMV perdido estimado descendente.

Query 6 Impacto de promociones en ticket y volumen

Basket analysis

Usando was\_on\_promo en transaction\_items , compara por categoría el ticket promedio y las unidades promedio

entre transacciones con y sin ítems en promo.

¿Las promociones generan compras adicionales (basket uplift) o solo descuento en lo que ya se iba a comprar?



Todo esto usando como base de datos los archivos adjuntos



Posteriormente le dije que ejecutara el SQL para tener un dashboard y poder analizar la información



**Bloque 2**

Para el bloque 2 nuevamente utilicé CodePuppy con el siguiente prompt



Debo crear dos entregables ENTREGABLE: bloque2\_modelo.pdf + bloque2\_decisiones.md

Con las siguientes indicaciones A Modelo Dimensional

Diseña un Star Schema en BigQuery que soporte: Comp Sales por tienda/formato/país/período, GMROI por

vendor/categoría/región, retención de clientes por cohorte, productividad de tienda y análisis de promociones.

Incluye:

Diagrama del modelo (draw.io, dbdiagram.io, Lucidchart o a mano)

Tablas de hechos y dimensiones con sus campos clave

Justificación de al menos 3 decisiones de diseño — ej. cómo modelar que el 60% de transacciones no tiene

customer\_id

B Diseño del Pipeline ETL/ELT

Sin escribir código, responde en texto o diagrama de flujo:

¿Cómo manejarías que las tiendas reportan ventas con hasta 2 horas de retraso?

¿Cómo detectarías automáticamente que una tienda dejó de enviar datos?

¿Cómo harías cargas incrementales sin duplicar transacciones?

¿Con qué frecuencia correría el pipeline si el dashboard necesita refresh diario?

C Gobernanza

¿Cómo protegerías customer\_id para cumplir con políticas de privacidad?

¿Quién debería ser el data owner de la tabla de transacciones?

Si dos reportes muestran GMV diferente para la misma tienda y el mismo día — ¿cuál sería tu proceso para

resolverlo?



HAcer 3 preguntas antes de iniciar



**Bloque 3**

Análisis Exploratorio + Experimentación

ENTREGABLE:

bloque3\_analisis.pdf + visualizaciones exportadas SQL

PARTE A — ANÁLISIS EXPLORATORIO

Pregunta 1 — Estacionalidad por formato

¿Cómo evoluciona el GMV semanal por formato de tienda? ¿Qué formato es más sensible a la estacionalidad? Identifica

los 3 picos y las 3 caídas más significativas del período y propón una hipótesis para cada uno.

Pregunta 2 — Pareto de categorías por formato

¿Qué categorías concentran el 80% del GMV? ¿Las categorías líderes en HIPERMERCADO son las mismas que en

DESCUENTO ? ¿Qué dice esto sobre el perfil del comprador de cada formato?

Pregunta 3 — Cohortes de lealtad

Con base en la Query 3 del Bloque 1: ¿las cohortes más recientes retienen mejor o peor que las antiguas? ¿El ticket

promedio de los clientes retenidos crece con el tiempo? ¿En qué mes se da la mayor caída y qué hipótesis tienes?

Pregunta 4 — Quiebres de stock y su impacto

Con los gaps detectados en la Query 5: ¿hay categorías o proveedores donde los quiebres son sistemáticos? ¿Cuánto

GMV total estimado se perdió? ¿Es un problema de demanda o de abastecimiento?

Pregunta 5 — Hallazgo libre

Identifica por tu cuenta un hallazgo relevante que no estaba en las preguntas anteriores. Muéstralo con evidencia y

explica el impacto para el negocio.

PARTE B — INTERPRETACIÓN DE A/B TEST

?? Escenario: El equipo de merchandising probó una nueva estrategia de exhibición en punto de venta. Se

seleccionaron tiendas aleatoriamente: unas recibieron la nueva exhibición ( TREATMENT ), otras mantuvieron la

exhibición estándar ( CONTROL ). El test corrió 6 semanas (septiembre–octubre 2024).

1 Validación del experimento. ¿Los grupos son comparables en GMV base, formato y tamaño antes del test? ¿Hay

alguna tienda asignada a ambos grupos?

2 Resultado en GMV. ¿El GMV promedio semanal por tienda en TREATMENT es significativamente mayor? Usa un

t-test. Reporta: diferencia absoluta, lift relativo, p-value e intervalo de confianza al 95%.

3 Resultado en ticket y frecuencia. ¿El efecto viene de tickets más altos, de más transacciones por tienda, o de

ambos?

4 Decisión de negocio. ¿Implementarías la nueva exhibición en todas las tiendas? Argumenta considerando el pvalue, el tamaño del efecto y el costo de implementación. ¿Qué harías si el p-value es 0.08?



HACERME 3 PREGUNTAS ANTES DE INICIAR



**Bloque 4**

Ayudame a crear el Bloque 4

Diseño de KPIs desde Cero

ENTREGABLE: bloque4\_kpi\_framework.md

El equipo directivo quiere lanzar un programa de mejora de productividad de tiendas. No existe ningún framework de

KPIs aún. Tu trabajo es construirlo desde cero.

Para cada KPI define:

KPI DEFINICIÓN EXACTA FÓRMULA FRECUENCIA FUENTE DE DATOS TARGET SUGERIDO ¿CÓMO DETECTAS SI EL DATO ESTÁ MAL?

Completa esta tabla con mínimo 6

Restricciones:

Mínimo 6 KPIs

Cubre al menos 3 dimensiones: productividad de tienda, experiencia del cliente y desempeño de proveedor

Al menos un leading indicator (predictivo, no solo de resultado final)

Al menos un KPI compuesto (calculado a partir de otros KPIs)

Define el North Star Metric del programa y justifica por qué lo elegiste



hacerme 3 pregunta antes de empezar



**Bloque 5**

Le pedía codepuppy lo siguiente: 



Necesito que a partir de este SQL se cree un documento que pueda ser utilizado como base de datos para en PBI para crear un dashboard con l

os siguientes detalles Header: GMV neto, número de transacciones, ticket promedio, GMV/m² — con variación vs. semana anterior

Filtros: país, formato de tienda, región, rango de fechas

Ranking visual de tiendas por desempeño dentro de su formato

Comp Sales: tendencia semanal año actual vs. año anterior por formato

Alerta automática: tiendas con GMV/m² por debajo del percentil 25 marcadas en rojo

Retención: visualización de la tabla de cohortes del Bloque 1 — Query 3

Stock: lista de ítems con mayor duración de quiebre activo por tienda





Además aparte necesito crear un pdf con los siguientes detalles

&#x20;EXECUTIVE PRESENTATION in English — basic to intermediate level

?? Nota sobre el nivel de inglés: No necesitas gramática perfecta ni vocabulario avanzado. Enfócate en ser claro y

organizado. Oraciones cortas y bullet points son completamente válidos. No se requiere presentar en vivo — la

presentación se entrega como archivo PDF.

Máximo 5 slides dirigidas al VP de Operaciones:

1

Executive Summary

3 key findings, written simply and clearly

2

Store Performance

Comp Sales results, best and worst

formats or markets

3

Opportunities

Underperforming stores, low GMROI

vendors, loyalty insights

4

Risks

Stock-out impact, retention drop, data

audit findings

5

Recommendations

What to do, who should do it, and by

when

Lo que evaluamos:

Inglés claro y simple — evita oraciones largas y complejas

Cada recomendación debe incluir al menos un número (%, $, número de tiendas, días)

Los hallazgos deben tener sentido sin ver los datos

Flujo lógico de hallazgos a recomendaciones

