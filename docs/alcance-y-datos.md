# Alcance, modalidad y uso de los datos

Qué estamos construyendo, para quién, y para qué sirve (y para qué **no** sirve) cada fuente
y cada pieza del sistema. Es la referencia del equipo y la base de la página
"Diseño de solución" de Notion. Fuente: [`reto.pdf`](reto.pdf) (secciones citadas entre
paréntesis), el [plan maestro](plan-maestro.md) y las decisiones en
[`notion/decisiones.csv`](notion/decisiones.csv).

Actualizado: martes 6 oct 2026 · Dueño: José (J-16).

---

## 1. Modalidad: TVN · principal

El reto (secc. 2) ofrece tres modalidades. Hacemos **una** completa (ADR-001):

| Modalidad del reto | Usuario | ¿La hacemos? | Cómo queda cubierta |
| --- | --- | --- | --- |
| **TVN · principal** | Editor/a y periodista | **Sí, es el núcleo** | Agenda priorizada (bandeja), ficha de investigación, preguntas pendientes y borradores por formato |
| **TVN · digital** | Productor/a digital | **En parte** | El título propuesto y el copy social (≤80 palabras) ya vienen en la salida editorial. No hacemos una sección propia de resumen web ni varias propuestas de titulares; si sobra tiempo el jueves, es una mejora barata |
| **Banca** | Analista económico o sectorial | **No** | Próximo paso en el pitch. Por eso la fuente D (SBP) no se descarga |

**La pregunta que responde el producto:** *"¿Qué temas de Panamá merecen revisión hoy, qué
evidencia hay de cada uno, qué falta verificar y qué borrador responsable puedo empezar?"*

**Lo que entrega** (salida TVN, secc. 3): brief de ≤250 palabras, título propuesto, enfoque de
interés público, 3 preguntas de investigación, fuentes y verificaciones pendientes; guion de
45–60 s; copy digital de ≤80 palabras. Todo es **borrador para revisión humana**: el sistema
no publica nada.

**Fuera de alcance** (secc. 2): medir rating o audiencia; decidir si una noticia es falsa;
datos personales; contenido detrás de paywall; producción audiovisual; publicación automática.

## 2. El recorrido de punta a punta

Las 7 etapas que pide el reto (secc. 3), quién las construye y qué archivo producen:

| # | Etapa | Qué hace | Dueño | Archivo / módulo | Pruebas |
| --- | --- | --- | --- | --- | --- |
| 1 | Cargar | Lee los datos, valida IDs, URLs, fechas y nulos; emite un reporte de calidad sin detener la carga | Levi | `src/ingest/`, `src/validate.py` → `outputs/reports/calidad.md` | T01 |
| 2 | Organizar | Clasifica en los 6 temas del reto (más `otro` para lo que no encaja) y agrupa noticias del mismo evento; cuenta procedencias, no registros | Levi | `src/nlp/` → `noticias.parquet`, `clusters.parquet` | T02, T03 |
| 3 | Contextualizar | Relaciona cada evento con un indicador del Banco Mundial o un sismo del USGS **solo si la relación se sostiene** | Levi | `contexto.parquet` (B-14) | T04 |
| 4 | Priorizar | Puntaje P = 30R + 25I + 20U + 15N + 10E con sus componentes; estado de evidencia aparte | José | `src/score.py` ✅ | T08 |
| 5 | Explicar | Ficha: qué se reporta, quién, qué está respaldado, qué falta y acción recomendada | José + Cristian | `src/fichas.py` → `fichas.jsonl`; `app/` | T09 |
| 6 | Producir | Brief, guion y copy con una cita por afirmación; hechos separados de inferencias | José | `src/generate/` (guard ✅) | T04–T07, T09 |
| 7 | Revisar | Una persona marca nuevo, en revisión, requiere evidencia, aprobado como borrador o descartado | Cristian | `app/` → `revisiones.jsonl`; Notion | — |

Todo funciona sin internet (T10): los datos se leen del snapshot local y las salidas del LLM
salen de `outputs/cache/`.

## 3. Las fuentes: para qué sirve cada una

Regla general (secc. 7): UTF-8, IDs estables, fechas en UTC, nulos conservados (nunca 0) y
cada afirmación citada con ID + campo o pasaje.

### A · Noticias: RSS de TVN + GDELT

| | RSS de TVN | GDELT DOC 2.0 |
| --- | --- | --- |
| Qué trae | Titular, enlace, fecha del medio y descripción corta | Titulares de medios de todo el mundo sobre Panamá, con `seendate` (cuándo GDELT la detectó) |
| Para qué la usamos | La voz del patrocinador: relación directa con Panamá (R = 1) y la única fuente con descripción | Volumen y **corroboración**: ver cuántos medios cubren un hecho y si son independientes |
| `alcance_texto` | `descripcion_rss` | `titular/metadatos` |
| Fechas | `fecha_publicacion` = la del medio; `fecha_deteccion` vacía | `fecha_deteccion` = `seendate`; `fecha_publicacion` casi siempre vacía (GDELT no la da) |
| No sirve para | Republicar el artículo, los videos ni las imágenes (la descripción del RSS no da licencia) | Confirmar un hecho por repetición: cinco medios que replican a EFE son **una** procedencia (ADR-007) |

Meta del reto: 200 noticias únicas; mínimo 100, con al menos 20 de TVN; los últimos 30 días
(hasta 90 si faltan). Entregables con los nombres del reto: `noticias.csv` y `fuentes.json` (B-13).

**Consecuencia en el borrador:** como solo tenemos titulares y metadatos, todo borrador basado
en GDELT dice "Basado únicamente en titular/metadatos." y no agrega detalles (lo impone
`guard.py`).

### B · Banco Mundial: contexto económico comparable

**Qué es:** series **anuales** oficiales, 2010–2024, de 6 países y 6 indicadores (secc. 6).

| Indicador | Qué mide | Unidad |
| --- | --- | --- |
| `NY.GDP.MKTP.KD.ZG` | Crecimiento del PIB | % anual |
| `FP.CPI.TOTL.ZG` | Inflación (precios al consumidor) | % anual |
| `SL.UEM.TOTL.ZS` | Desempleo | % de la fuerza laboral |
| `SP.POP.TOTL` | Población | personas |
| `IT.NET.USER.ZS` | Uso de internet | % de la población |
| `NE.EXP.GNFS.ZS` | Exportaciones de bienes y servicios | % del PIB |

Países: **PAN** (Panamá) y cinco de comparación regional: CRI, COL, DOM, MEX, GTM.

**Cómo se guarda** (`indicadores.csv`, B-03): una fila por país × indicador × año, **aunque no
haya dato**. En ese caso `valor` queda vacío, nunca 0: un dato faltante es "no hay dato", no
"cero crecimiento". Con 6 × 6 × 15 años salen **540 combinaciones**; el reto dice 1.350, cifra
que no cuadra (pregunta abierta a la organización). Cada fila lleva `unidad`, `fuente_url`,
`fecha_extraccion` y `licencia` (CC BY 4.0).

**Para qué lo usamos (tres usos):**

1. **Respaldar cifras en el brief (CU-02, T04).** Cuando un tema económico tiene un dato
   oficial pertinente, el borrador puede citarlo, siempre con **país, año y unidad**:
   - ✅ "Según el Banco Mundial, el PIB de Panamá creció X % anual en 2023." · cita `WB-PAN-NY.GDP.MKTP.KD.ZG-2023 · valor`
   - ❌ "La economía panameña crece X % hoy." → el guard la descarta (dato anual sin año o presentado como actual).
   - Si `valor` está vacío, ese dato **no existe como evidencia** y no se puede citar.
2. **Sumar al puntaje.** Si `contexto.parquet` (B-14) relaciona un evento con un indicador:
   - **I (impacto)** sube: `0.6 × alcance del tema + 0.4 × hay indicador oficial pertinente`.
   - **E (evidencia)** sube: `0.6 × min(1, procedencias/3) + 0.4 × hay fuente oficial`.
   - El **estado de evidencia** puede pasar a "suficiente para el borrador" (necesita ≥2 procedencias **y** fuente oficial).
3. **Comparar con la región**, como contexto: "en 2023 Panamá estuvo por encima o por debajo de CRI, COL...". Siempre con el año.

**Qué indicador es pertinente para cada tema** (propuesta para la regla de B-14; Levi la
ajusta y la registra como decisión):

| Tema del evento | Indicadores pertinentes | Ejemplo de uso |
| --- | --- | --- |
| economía | PIB, inflación, desempleo, exportaciones/PIB | Noticia de precios → inflación anual más reciente con dato |
| logística/Canal | exportaciones/PIB | Noticia de comercio → peso de las exportaciones en 2023 |
| servicios públicos | uso de internet (solo si la noticia es de conectividad o telecomunicaciones) | — |
| turismo, regulación, eventos naturales | ninguno directo | Sin relación sustentada → **sin fila**; no se fuerza |
| cualquiera | población | Solo como denominador o contexto, nunca como evidencia del hecho |

**Para qué NO sirve:** medir lo que pasa hoy ni este mes (el último año es 2024 y los datos se
revisan con el tiempo); explicar la causa de una noticia; responder "¿cuál fue la inflación de
septiembre de 2026?". Esa pregunta es justo un caso de **abstención** (T06).

### C · USGS: sismos oficiales

**Qué es:** catálogo de sismos de 2024, magnitud ≥3, en una caja regional (latitud 5 a 12,
longitud −86 a −76), con ID y URL por evento (`eventos.geojson`, B-04).

**Para qué lo usamos:** respaldar **hechos sísmicos** (magnitud, hora, lugar, profundidad)
cuando una noticia de "eventos naturales" habla de un sismo. Con el ID del USGS la cita es
trazable, y el vínculo cuenta como fuente oficial en el puntaje (B-14).

**Para qué NO sirve:**
- Como evidencia de inundaciones, daños o pérdidas económicas.
- Para decir "en Panamá": la caja **no es** el territorio de Panamá; se usa el `place` del evento tal cual.
- Para eventos fuera de 2024: si una noticia de 2025 o 2026 habla de un sismo, el catálogo no la cubre y se dice ("verificación pendiente"), sin inventar el vínculo.

### D · SBP (Superintendencia de Bancos de Panamá)

No la usamos: es solo para la modalidad bancaria (ADR-001).

## 4. Qué hace la IA y qué no

| Pieza | Tecnología | Hace | No hace |
| --- | --- | --- | --- |
| Clasificar y agrupar (B-07, B-08) | Embeddings multilingües en CPU | Tema por similitud con descripciones de los 6 temas; agrupa noticias del mismo evento en 72 h | Decidir si algo es verdad |
| Baseline (B-09) | Palabras clave + TF-IDF | Punto de comparación: macro-F1 de IA vs baseline, y decir dónde la IA no ayuda | — |
| Búsqueda (J-06) | Embeddings | Encuentra los 10 fragmentos más cercanos a una consulta, o "sin evidencia" | Buscar en internet |
| Puntaje (J-05) | Reglas en código (`scoring_v1.yaml`) | P y sus 5 componentes, reproducible | Usar el LLM |
| Redacción (J-08) | OpenRouter + Gemini 2.5 Flash, temperatura 0 | Brief, guion y copy en JSON, con una cita por afirmación | Calcular, decidir ni publicar |
| Guard (J-07) | Código | Rechaza citas falsas, filtraciones, instrucciones inyectadas y datos sin año; abstiene si no queda nada sustentado | — |

El texto de las fuentes es **dato, nunca instrucción**: va dentro de etiquetas `<fuente>`, y si
pide "ignora tus reglas", el sistema no obedece y levanta una alerta (T07).

## 5. Lo que el jurado verá en la demo

| Caso de uso (secc. 4) | Qué mostramos | Con qué |
| --- | --- | --- |
| **CU-01** "¿Qué 5 temas merecen revisión y por qué?" | Bandeja con el top 5, P desglosado y estado de evidencia | `score.py` + bandeja (C-12) |
| **CU-02** Tema económico + serie oficial + brief | Brief que cita un indicador con país, año y unidad | B-14 + J-08 + ficha (C-13) |
| **CU-03** Repetición ≠ corroboración | "5 registros, 1 procedencia independiente" | B-06/B-08 + ficha |
| **CU-04** Cifra inexistente o contradicción | Abstención explícita; dos versiones con "verificación pendiente" | Guard + J-10 |

Y las 4 preguntas del jurado (secc. 11): de dónde sale una cifra y de qué año → cita a la fila
del Banco Mundial; cuántas fuentes independientes hay → procedencias del cluster; qué pasa sin
evidencia o con una fuente que da órdenes → T06 y T07 en vivo; una decisión, una prueba
fallida y su corrección → Notion (por ahora `docs/notion/`).

## 6. Preguntas abiertas a la organización

1. ¿Entregan el **snapshot congelado** (secc. 6 y 11 lo piden "al menos 72 horas antes")? Si sí, Levi se salta las descargas (B-01 a B-04).
2. **Ventana de fechas:** el reto pide los 30 días previos a la extracción y también excluir todo lo que esté fuera de [2024-01-01, 2025-10-01). Hoy esas dos reglas no se pueden cumplir juntas.
3. **Banco Mundial:** ¿1.350 o 540 combinaciones?
4. ¿Cuándo llega el espacio **Notion Business** y con cuántos puestos?
