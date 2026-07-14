1. bloque0\_auditoria.md

\-Completitud ¿Qué porcentaje de transacciones no tiene customer\_id ? ¿Es consistente con loyalty\_card = FALSE ?

Total de transacciones	174880

Sin customer\_id	104632

**% Sin customer\_id	59.83%**

Sin customer\_id	104632

loyalty\_card = FALSE	104632

Sin customer\_id Y loyalty\_card=FALSE	104632

**¿Son consistentes?	SÍ - 100% consistente**



\-Consistencia ¿El total\_amount en transactions coincide con la suma de unit\_price × quantity en transaction\_items ?

Suma total\_amount:	¢48,719,262.24

Suma qty\*price items:	¢48,751,364.86

**Diferencia:	-¢32,102.62**

**Diferencia %:	0.0659%**

**Dado que la diferencia es menor al 1% se informará del margen de error pero no se modificaran datos**



\-Unicidad ¿Existen transaction\_id duplicados?

Total transaction\_id:	174880

**¿Existen duplicados?:	NO - Todos son únicos**



\-Validez ¿Hay total\_amount negativos o cero? ¿Hay unit\_price = 0 con was\_on\_promo = FALSE?

**¿Hay total\_amount = 0?	SÍ - 3 registros**

TX\_00036043

TX\_00065737

TX\_00108161

¿Hay unit\_price=0 Y was\_on\_promo=FALSE?	SÍ - 231 registros

Se ubica que es el **ITEM\_089 es el que está con unit\_price = 0, para efectos del ejercicio se mantendrán los datos para no modificar la base de datos**



\-Integridad referencial ¿Hay store\_id en transactions que no existan en stores ? ¿ vendor\_id en products que no existan en vendors ?

**¿Hay store\_id huérfanos?	NO - Todos válidos**

&#x20; - store\_ids únicos en transactions:	40

&#x20; - store\_ids en tabla Stores:	40



**¿Hay vendor\_id huérfanos en Products?	SÍ - Hay huérfanos**

&#x20; - vendor\_ids únicos en Products:	31

&#x20; - vendor\_ids en tabla Vendors:	30

&#x09;

\--- Detalle de vendor\_id huérfanos ---

**vendor\_id(s) sin registro en Vendors:	VND\_031**

Productos afectados:	5



\-Frescura ¿Hay tiendas con gaps de días consecutivos sin transacciones? ¿Son esperables o sospechosos?

**Se detecta que la tienda TIENDA\_012 tiene una GAP de información de la fecha 09092024 al 17092024, se asumirá que se consultó con la operación y se confirma que hubo una remodelación en esas fechas entonces se mantiene el dato y se documenta el hallazgo**



\-Integridad temporal ¿Existe alguna tienda con transacciones anteriores a su opening\_date ?

ANOMALÍA DETECTADA:
? **TIENDA\_037:** Cobertura > 100% indica transacciones

&#x20; **ANTES de su fecha de apertura oficial (2024-06-01)**

&#x20; Posible error en opening\_date o datos de prueba

**Para efectos de ejercicio se asumirá que se revisó con la operación y se corrigió la fecha de apertura para el 18052025**



\-A/B Test ¿Hay tiendas asignadas simultáneamente a CONTROL y TREATMENT en store\_promotions ?

Se detectan 2 tiendas con las dos variantes simultaneamente, TIENDA\_008 y TIENDA\_037, para efectos del ejercicios se asumirá que se consultó a la operación y se determinó ambas tiendas son de control



&#x20;

