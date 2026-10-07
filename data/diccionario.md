# Diccionario de datos

Dueño: **B** (B-10). Base: "Contratos entre roles" en `CLAUDE.md` §3. Hashes, consultas exactas,
filas y licencias de cada archivo: `data/manifest.json` (`python -m src.manifest`; comprobar con
`python -m src.manifest --verify`).

Reglas para todos los archivos:

- UTF-8. Fechas en **UTC**, ISO 8601. La app muestra hora de Panamá (UTC−5) solo al mostrar.
- Un valor faltante es **nulo**, nunca 0 ni texto vacío.
- `fecha_publicacion` (la del medio) y `fecha_deteccion` (`seendate` de GDELT) **nunca** se mezclan ni se rellenan una con la otra.
- Período de noticias: **02/10/2025 00:00 UTC a 30/09/2026 23:59:59 UTC**. Una noticia sin fecha queda fuera (no se puede probar que esté dentro). Banco Mundial (2010–2024) y USGS (2024) no usan este período.

Cómo se arma: `make data` (descarga; necesita internet) → `make news` (valida, `noticias.parquet` y `outputs/reports/calidad.md`) → `make nlp` (tema, procedencia, clusters, baseline) → `python -m src.manifest`.

## `data/processed/noticias.parquet`

Una fila por noticia única (URL normalizada). Fuentes: TVN RSS, TVN web (sitemaps) y GDELT DOC 2.0.

| Campo | Tipo | Unidad / valores | Origen | Reglas |
| --- | --- | --- | --- | --- |
| `id_noticia` | texto | `N-` + 10 hex | calculado | 10 primeros caracteres del SHA-1 de la URL normalizada (minúsculas, sin fragmento, sin `utm_*`/`fbclid`/`gclid`, sin `/` final). Estable entre corridas y fuentes. |
| `titulo` | texto | — | RSS `title` · JSON-LD `headline` · GDELT `title` | Sin HTML ni entidades. Puede ser nulo si la fuente no lo trae (2 casos en GDELT). |
| `descripcion` | texto, nulo | — | RSS `description` · JSON-LD `description` | Solo TVN. En GDELT siempre nulo. |
| `url` | texto | URL | fuente | Enlace original. |
| `medio` | texto | — | TVN: "TVN" · GDELT: dominio | GDELT no da el nombre del medio. |
| `dominio` | texto | — | URL | Sin `www.`. |
| `idioma` | texto | ISO 639-1 (`es`, `en`...) | TVN: `es` · GDELT `language` | Nombre de GDELT pasado a código; si no está en la tabla, el nombre en minúsculas. |
| `fecha_publicacion` | fecha UTC, nulo | ISO 8601 | RSS `pubDate` · JSON-LD `datePublished` | La del medio. GDELT no la da: nula. |
| `fecha_deteccion` | fecha UTC, nulo | ISO 8601 | GDELT `seendate` | Cuándo GDELT vio la nota, no cuándo se publicó. En TVN siempre nula. |
| `fecha_extraccion` | fecha UTC | ISO 8601 | nuestra descarga | Hora de la descarga. |
| `origen` | texto | `tvn_rss`, `tvn_web`, `gdelt` | calculado | `tvn_web`: artículos desde los sitemaps públicos de tvn-2.com, solo metadatos JSON-LD, respetando robots.txt. |
| `alcance_texto` | texto | `titular/metadatos`, `descripcion_rss`, `descripcion_web` | calculado | De dónde salió el texto. Con `titular/metadatos` el borrador debe decir "basado únicamente en titular/metadatos". |
| `procedencia_id` | texto | `P-<dominio>` o `P-AG-<agencia>` | B-06 | Ver "Procedencia". |
| `tema` | texto | `economía`, `logística/Canal`, `turismo`, `servicios públicos`, `eventos naturales`, `regulación`, `otro` | B-07 | Tema con mayor similitud; bajo el umbral, `otro`. |
| `tema_confianza` | decimal | similitud coseno, −1 a 1 (en este corpus de −0,01 a 0,91) | B-07 | Similitud con la frase de tema más cercana. No es una probabilidad. Se guarda también cuando el tema es `otro` (la del tema más cercano). |
| `cluster_id` | texto | `K-` + 10 hex | B-08 | Ver "Eventos". |
| `sintetico` | booleano | — | calculado | Siempre `false` en el corpus real (regla 12). |
| `recirculada` *(extra, B-11)* | booleano | — | calculado | `true` si `fecha_deteccion − fecha_publicacion ≥ 7 días`: nota anterior que vuelve a circular. Conserva su `fecha_publicacion` original; se agrupa y se puntúa por esa fecha (T03). Hoy ninguna fuente trae las dos fechas en la misma noticia, así que en el corpus real es `false` en todas. |

Una URL que aparece en TVN y en GDELT se queda con la fila de TVN (trae descripción); el conteo está en `calidad.md`.

### Procedencia (B-06, ADR-007)

`procedencia_id` es la fuente original. Un cluster cuenta procedencias únicas, no registros: tres medios que replican a EFE son 3 registros y 1 procedencia.

1. Por defecto, el propio medio: `P-<dominio>` (dos notas del mismo medio no son independientes entre sí).
2. Si el título, la descripción o el medio nombra una agencia (EFE, AFP, AP, Reuters, Europa Press, Xinhua, Prensa Latina, ANSA, DPA, Bloomberg): `P-AG-<agencia>`. "AP" solo cuenta como "(AP)", "AP:", "la AP" o "Associated Press".
3. Títulos casi idénticos (TF-IDF coseno ≥ 0,9) en dominios distintos dentro de 48 h comparten procedencia: la agencia si alguno la nombra; si no, el medio de la nota más temprana.

**Límite:** con solo titulares y descripciones cortas la detección es aproximada. Un medio que reescribe una nota de agencia sin nombrarla conserva su propia procedencia; dos notas de un mismo medio sobre el mismo hecho cuentan como una.

### Tema (B-07)

Modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (CPU, revisión en `embeddings_modelo.json`). Texto: título + descripción si existe. Cada tema tiene 2–3 frases en español (`src/nlp/classify.py`); el puntaje de un tema es la mejor similitud con sus frases. Umbral **0,50** (provisional: se calibra en B-12 con la mitad de las etiquetas humanas y se reporta con la otra mitad). Deportes, crimen, farándula e internacional sin relación con Panamá no tienen frases: caen en `otro`.

### Eventos (B-08)

Clustering aglomerativo con enlace completo sobre distancia coseno de los embeddings, umbral **0,30**, y solo entre noticias a 72 h o menos (fecha del medio o, si no hay, de detección; sin ninguna de las dos, la noticia queda sola). Con enlace completo, todas las noticias de un cluster están a ≤ 0,30 entre sí y a ≤ 72 h entre sí. Una noticia sola conserva `K-` + su hash; un grupo es `K-` + 10 hex del SHA-1 de sus `id_noticia` ordenados (estable entre corridas). **Límite:** notas de formato repetido (clima del día, cotización del dólar) a veces quedan juntas; B-12 lo mide contra `cluster_humano`.

## `data/processed/noticias.csv` y `data/processed/fuentes.json` (entregables del reto, B-13)

Nombres que exige el reto (secc. 6–7). Se generan al final de `make nlp` (`python -m src.export`).

- **`noticias.csv`**: las mismas filas y columnas que `noticias.parquet` (incluye los campos mínimos del reto: `id_noticia`, `titulo`, `url`, `medio`, `idioma`, `fecha_publicacion`, `fecha_deteccion`, `fecha_extraccion`, `tema`, `origen`, `alcance_texto`). UTF-8 sin BOM, separador coma, fin de línea LF. Fechas como texto ISO 8601 UTC (`2026-09-30T14:05:00Z`). Nulo = celda vacía, nunca 0.
- **`fuentes.json`**:
  - `periodo_UTC`, `n_noticias`.
  - `consultas`: las tres vías de entrada (`tvn_rss`, `tvn_web`, `gdelt`) con URL, consultas de GDELT, cantidad de noticias y `condiciones_uso`.
  - `medios`: una entrada por (`origen`, `dominio`) con `medio`, `n_noticias`, `fecha_primera_UTC`, `fecha_ultima_UTC` (fecha del medio o, si no hay, de detección) y `condiciones_uso`. Ordenados de más a menos noticias.
  - Condiciones: ni TVN ni GDELT dan derechos sobre los artículos enlazados; se entregan solo titular, URL y metadatos (y la descripción de TVN). Para leer la nota, ir a la URL del medio.

## `data/processed/clusters.parquet`

Una fila por `cluster_id` de `noticias.parquet`.

| Campo | Tipo | Unidad | Reglas |
| --- | --- | --- | --- |
| `cluster_id` | texto | `K-` + 10 hex | Igual que en noticias. |
| `ids_noticia` | lista de texto | — | Noticias del evento, ordenadas. |
| `n_registros` | entero | noticias | Cuántas noticias tiene. |
| `n_procedencias_independientes` | entero | procedencias | `procedencia_id` únicos. Es lo que cuenta para corroborar, no `n_registros`. |
| `tema` | texto | mismos valores que noticias | El más frecuente; empate en orden alfabético (misma regla que `src/score.py`). |
| `fecha_primera` / `fecha_ultima` | fecha UTC | ISO 8601 | Menor y mayor fecha de referencia (del medio o, si no hay, de detección). Resumen del evento: no reemplaza las fechas de cada noticia. |
| `n_medios` *(extra)* | entero | medios | `medio` únicos: ninguna fuente se pierde al agrupar (T02). |
| `medios` *(extra)* | lista de texto | — | Los medios del evento. |
| `recirculada` *(extra)* | booleano | — | `true` si alguna noticia del evento es recirculada (B-11). |

## `data/processed/baseline.parquet`

Mismas columnas que la IA para comparar en B-12: `id_noticia`, `tema`, `tema_confianza`, `procedencia_id`, `cluster_id`. Sin embeddings: tema por palabras clave (`src/nlp/baseline.py`; `tema_confianza` = proporción de palabras clave encontradas que son del tema elegido) y duplicados por TF-IDF ≥ 0,9 en 72 h. Uso interno; la app no lo lee.

## `data/processed/embeddings.npy`, `embeddings_ids.json`, `embeddings_modelo.json`

Matriz `float32` de N × 384, un vector normalizado (norma 1) por noticia, en el orden de `embeddings_ids.json`. `embeddings_modelo.json` guarda modelo, revisión, dimensión y texto de entrada. Si cambia el modelo, se recalculan todos.

## `data/processed/contexto.parquet` (contexto oficial, B-14)

Etapa 3 del reto: un evento se relaciona con un dato oficial **solo si la relación se sostiene**; si no, no hay fila. Regla en `src/context.py`.

| Campo | Tipo | Valores | Reglas |
| --- | --- | --- | --- |
| `cluster_id` | texto | `K-` + 10 hex | El evento. |
| `id_evidencia` | texto | `WB-PAN-<indicador>-<año>` o id del USGS | Se cita igual en el borrador. Nunca apunta a un valor nulo. |
| `tipo` | texto | `indicador`, `sismo` | `src/score.py` lo usa para I y E. |
| `regla` | texto | — | Qué condiciones se cumplieron (tema, palabras encontradas). |
| `nota` | texto | — | Límites al citar: año del dato, "no mide la fecha de la noticia", caja del USGS. |

**Indicadores (solo Panamá):** el tema mayoritario del evento lo permite (economía: PIB, inflación, desempleo, exportaciones; logística/Canal: exportaciones; servicios públicos: uso de internet), el texto menciona Panamá o una institución panameña, **y** nombra lo que mide el indicador (p. ej. "desempleo", "inflación", "exportaciones"). El tema solo no basta. Se cita el último año con dato.

**Sismos:** solo para eventos naturales que mencionan un sismo y con un evento del USGS a 72 h o menos. El catálogo es de 2024 y las noticias de 2025-10 a 2026-09: hoy no hay filas de sismo, a propósito (un sismo de 2024 no respalda un titular de 2026).

**Límite:** con solo titulares, un evento sobre empleo que no use esas palabras no recibe indicador; es preferible a forzar uno.

## `data/processed/indicadores.csv` (Banco Mundial, B-03)

Cuadrícula completa: 6 países × 6 indicadores × 15 años = 540 filas.

| Campo | Tipo | Unidad | Reglas |
| --- | --- | --- | --- |
| `pais_iso3` | texto | ISO 3166-1 alfa-3 | PAN, CRI, COL, DOM, MEX, GTM. |
| `indicador_id` | texto | código del Banco Mundial | NY.GDP.MKTP.KD.ZG, FP.CPI.TOTL.ZG, SL.UEM.TOTL.ZS, SP.POP.TOTL, IT.NET.USER.ZS, NE.EXP.GNFS.ZS. |
| `anio` | entero | año | 2010 a 2024. |
| `valor` | decimal, nulo | según `unidad` | Nulo si el Banco Mundial no lo tiene; nunca 0. |
| `unidad` | texto | — | Crecimiento del PIB y del IPC: `% anual`; desempleo: `% de la fuerza laboral`; población: `personas`; internet: `% de la población`; exportaciones: `% del PIB`. |
| `fuente_url` | texto | URL | Consulta exacta a la API v2. |
| `fecha_extraccion` | fecha UTC | ISO 8601 | Hora de la descarga. |
| `licencia` | texto | — | `CC BY 4.0`. |

Al citar: siempre país, año y unidad; nunca "hoy" (regla 9). El reto menciona 1.350 combinaciones; con 6 × 6 × 15 son 540 (cálculo en `docs/alcance-y-datos.md`; pregunta abierta a la organización).

## `data/processed/eventos.geojson` (USGS, B-04)

FeatureCollection; `metadata` trae `fuente_url`, `fecha_extraccion`, `licencia` y `n_eventos`. Todos los sismos que devuelve la consulta (2024, M ≥ 3, lat 5–12, lon −86 a −76).

| Campo | Tipo | Unidad | Reglas |
| --- | --- | --- | --- |
| `id` | texto | id del USGS | Único. |
| `magnitude` | decimal | magnitud (escala que reporta el USGS) | — |
| `time` / `updated` | fecha UTC | ISO 8601 | Hora del sismo / última revisión del USGS. |
| `longitude`, `latitude` | decimal | grados | WGS 84. |
| `depth` | decimal | km | — |
| `place` | texto | — | Descripción del USGS (en inglés). |
| `status` | texto | `reviewed` / `automatic` | — |
| `url` | texto | URL | Página del evento en el USGS. |

**Límite:** la caja regional no es el territorio de Panamá. Solo sirve para hechos sísmicos, nunca para inundaciones ni pérdidas.

## Archivos de otros dueños que usan estos datos

- `data/etiquetas_humanas.csv` (C, C-05): `id_noticia`, `tema_humano`, `cluster_humano`, `etiquetador`, `nota`, más columnas de lectura. Muestra de 60 con semilla fija (`src/nlp/label_sample.py`).
