# hackIAthon · Copiloto TVN — Plan maestro del equipo

Oct 6, 2026 · @vorluno

## Qué construimos

Un copiloto editorial para TVN que lee noticias públicas y datos oficiales, ordena los temas por prioridad explicada, muestra la evidencia de cada afirmación y redacta borradores para revisión humana. Entrega: jueves 8 de octubre, 23:59. Modalidad única: editorial TVN (la bancaria queda fuera, ver ADR-001).

El flujo que el jurado debe ver de punta a punta:

1. Cargar el snapshot y emitir un reporte de calidad.
2. Organizar: clasificar por tema y agrupar noticias del mismo evento.
3. Contextualizar con indicadores del Banco Mundial y sismos del USGS, sin forzar relaciones.
4. Priorizar con el puntaje P = 30R + 25I + 20U + 15N + 10E y mostrar sus componentes.
5. Explicar en una ficha: qué se reporta, quién, qué está respaldado y qué falta.
6. Producir brief (≤250 palabras), guion de 45–60 s y copy digital (≤80 palabras), con cita por afirmación.
7. Revisar: una persona marca nuevo, en revisión, requiere evidencia, aprobado como borrador o descartado.

### Condiciones de admisión (si falta una, no nos evalúan)

- [ ] Espacio Notion con las 8 páginas obligatorias y acceso del jurado verificado.
- [ ] Plan en Notion con al menos 8 tareas y 3 decisiones justificadas, registradas durante el evento.
- [ ] Catálogo completo de fuentes usadas.
- [ ] Al menos 5 fichas trazables, una de ellas con evidencia insuficiente.
- [ ] Matriz T01–T10 con resultados y métricas de la ejecución final.
- [ ] Repo GitHub con acceso del jurado: README, instalación, comando de ejecución, dependencias fijadas, .env.example y pruebas.
- [ ] Demo que funciona sin internet.
- [ ] Pitch de 10 minutos presentado desde Notion.
- [ ] Cero secretos en código, Notion o capturas; cero citas falsas.

### Rúbrica (100 puntos)

| Dimensión | Peso | Dueño principal |
| --- | --- | --- |
| Utilidad para TVN | 20 | C |
| Prototipo y flujo completo | 20 | José |
| Uso efectivo de IA | 15 | B |
| Evidencias y explicabilidad | 15 | José |
| Notion: ejecución y pitch | 15 | C |
| Calidad técnica y evaluación | 10 | B |
| Seguridad, privacidad y ética | 5 | C |

Pregunta abierta para el grupo de WhatsApp: ¿la organización entrega el snapshot congelado o lo armamos nosotros? El plan asume lo segundo; si lo entregan, B gana medio día.

## Equipo y roles

Tres roles con frontera clara: B produce los datos y la IA de clasificación, José los consume y construye el producto, C documenta, prueba y presenta. Cambien "B" y "C" por los nombres reales.

| Rol | Persona | Es dueño de | Entrega clave |
| --- | --- | --- | --- |
| Líder técnico e integración | José | Repo, arquitectura, puntaje, generación con LLM, interfaz Streamlit, demo offline | App funcionando de punta a punta |
| Datos e IA | B | Ingesta de las 4 fuentes, validación, manifest, embeddings, clasificación, agrupación, baseline, métricas F1 | `data/processed/` + `clusters.parquet` + reporte de baseline |
| Producto, Notion y QA | C | Espacio Notion, catálogo de datos, etiquetado humano, benchmark, T01–T10, riesgos y ética, pitch | Notion completo + matriz de pruebas + pitch ensayado |

Reglas de trabajo:

- Cada decisión técnica se anota en Notion el mismo día, con fecha y quién decidió. Sin eso no cumplimos la condición de admisión.
- Nadie trabaja en `main`: rama por tarea, PR corto, José hace merge.
- Sincronización de 10 minutos a las 9:00, 14:00 y 20:00 cada día: qué terminé, qué sigue, qué me bloquea.
- Si algo bloquea más de 45 minutos, se avisa en el grupo del equipo y se recorta alcance antes que perder la tarde.

## Roadmap

Tres hitos ordenan el trabajo; el del miércoles a las 20:00 es el que no se puede mover, porque el jueves es solo para probar, corregir y presentar.

&#91;embedded content: Roadmap · 3 personas × 3 días, 3 hitos\]

Si el hito del martes se atrasa, José sigue con los datos stub y nadie se bloquea. Si el del miércoles se atrasa, se recorta: primero el guion, después el copy; el brief con citas nunca se recorta.

## Contratos entre roles

Cada archivo tiene un dueño y un consumidor; nadie cambia un esquema sin avisar en la sincronización. Todo en UTF-8, fechas ISO 8601 en UTC, nulos como nulos (nunca 0).

| Archivo | Lo produce | Lo consume | Campos | Primera versión |
| --- | --- | --- | --- | --- |
| `data/processed/noticias.parquet` | B | José | id\_noticia, titulo, url, medio, dominio, idioma, fecha\_publicacion, fecha\_deteccion, fecha\_extraccion, origen (tvn\_rss / gdelt), alcance\_texto ("titular/metadatos" o "descripcion\_rss"), procedencia\_id, tema, tema\_confianza, cluster\_id | Martes 20:00 (parcial vale) |
| `data/processed/clusters.parquet` | B | José | cluster\_id, ids\_noticia, n\_registros, n\_procedencias\_independientes, tema, fecha\_primera, fecha\_ultima | Miércoles 12:00 |
| `data/processed/indicadores.csv` | B | José | pais\_iso3, indicador\_id, anio, valor (nullable), unidad, fuente\_url, fecha\_extraccion, licencia | Martes 20:00 |
| `data/processed/eventos.geojson` | B | José | id, magnitude, time, updated, longitude, latitude, depth, place, status, url | Martes 20:00 |
| `data/manifest.json` | B | C | versión, fecha\_corte\_UTC, consultas, cantidad por archivo, licencias, SHA-256, transformaciones | Miércoles 12:00 |
| `data/etiquetas_humanas.csv` | C | B | id\_noticia, tema\_humano, cluster\_humano, etiquetador | Miércoles 12:00 (60 noticias) |
| `benchmark/benchmark_dev.jsonl` | C | José y B | id, tipo (sustentada / contradiccion / sin\_respuesta / adversarial), consulta, respuesta\_esperada, ids\_evidencia\_esperados, sintetico | Miércoles 18:00 |
| `outputs/fichas.jsonl` | José | C | id\_caso, modalidad, ids\_fuente, afirmaciones, citas, puntaje, componentes, estado\_evidencia, borrador, estado\_revision | Miércoles 20:00 |
| `outputs/cache/` | José | Demo | Salidas del LLM guardadas por hash de entrada, para la demo sin internet | Jueves 12:00 |

Definiciones que todos usan igual:

- **procedencia\_id**: la fuente original de la noticia. Cinco medios que replican a EFE comparten la misma procedencia y cuentan como una sola.
- **fecha\_publicacion vs fecha\_deteccion**: la primera es la del medio; la segunda es el `seendate` de GDELT. Nunca se mezclan.
- **estado\_evidencia**: insuficiente, parcial o suficiente para el borrador. Es independiente del puntaje.
- **Cita válida**: ID de evidencia + campo o pasaje que respalda la afirmación. Una URL suelta no cuenta.

## ADRs

Ocho decisiones aceptadas hoy; cada una se copia tal cual a la base "Plan y decisiones" de Notion (cuentan para el mínimo de 3). Si una cambia, no se borra: se marca "Reemplazada por ADR-0XX" y se escribe la nueva.

### ADR-001 · Solo modalidad editorial TVN

- **Contexto:** el reto recomienda la editorial y no exige dos productos; tenemos 3 días y 3 personas.
- **Decisión:** construimos solo el paquete editorial. La bancaria queda como próximo paso en el pitch.
- **Consecuencia:** la fuente D (SBP) no se descarga. Un recorrido completo pesa más que dos a medias.

### ADR-002 · Python local, Streamlit y Parquet/DuckDB

- **Contexto:** la demo debe funcionar sin internet y el jurado debe poder reproducirla.
- **Decisión:** Python 3.11, datos en Parquet consultados con DuckDB, interfaz en Streamlit, todo local.
- **Consecuencia:** cero servicios pagos obligatorios; `make demo` levanta todo. No hay frontend a medida.

### ADR-003 · Embeddings multilingües para clasificar y agrupar

- **Contexto:** el reto exige al menos una capacidad NLP real; un IF/ELSE no cuenta.
- **Decisión:** un modelo de sentence-transformers multilingüe que corre en CPU (candidatos: `intfloat/multilingual-e5-small` o `paraphrase-multilingual-MiniLM-L12-v2`; B elige y registra versión). Clasificación por similitud con descripciones de los 6 temas; agrupación con clustering aglomerativo por coseno dentro de una ventana de 72 h.
- **Consecuencia:** el modelo se descarga una vez y queda en caché para la demo offline.

### ADR-004 · Baseline de palabras clave contra el que medimos

- **Contexto:** el reto exige comparar la IA con un baseline simple y decir cuándo no ayuda.
- **Decisión:** baseline = reglas de palabras clave por tema + TF-IDF para duplicados. Medimos macro-F1 de ambos sobre las 60 etiquetas humanas de C.
- **Consecuencia:** si el baseline gana en algún tema, lo reportamos tal cual en el pitch.

### ADR-005 · LLM solo para redactar, con salida JSON y citas

- **Contexto:** el riesgo principal es inventar hechos o seguir instrucciones escondidas en una noticia.
- **Decisión:** el LLM recibe solo evidencia recuperada, separada de las instrucciones con etiquetas `<fuente>`. Responde en JSON con: afirmaciones, cita por afirmación, tipo (hecho, declaración, inferencia, hipótesis) y vacíos. Si no hay evidencia, devuelve abstención. Proveedor por confirmar hoy a las 14:00; se registran modelo, versión, temperatura 0 y costo por consulta.
- **Consecuencia:** un validador en código rechaza cualquier afirmación sin cita existente antes de mostrarla.

### ADR-006 · Puntaje determinista y versionado

- **Contexto:** el puntaje debe ser reproducible y explicable.
- **Decisión:** P = 30R + 25I + 20U + 15N + 10E, cada componente de 0 a 1 con reglas escritas en `rules/scoring_v1.yaml`. Rangos: bajo \[0,40), medio \[40,70), alto \[70,100\]. Empate: mayor urgencia, luego ID. El LLM no calcula el puntaje.
- **Consecuencia:** la ficha muestra los 5 componentes y la versión de reglas.

### ADR-007 · Corroboración por procedencia, no por cantidad

- **Contexto:** varios medios replicando una agencia no son confirmación independiente (CU-03, T02).
- **Decisión:** cada noticia lleva `procedencia_id`; un cluster cuenta procedencias únicas, no registros. La duplicación no sube el puntaje de novedad ni de evidencia.
- **Consecuencia:** la ficha dice "5 registros, 1 procedencia independiente".

### ADR-008 · Revisión humana manual en Notion y demo con caché

- **Contexto:** automatizar Notion es opcional y la demo no puede depender de internet.
- **Decisión:** la revisión se marca en la app y C la copia a Notion. Las salidas del LLM se guardan por hash; sin internet, la app sirve desde `outputs/cache/` y lo indica en pantalla.
- **Consecuencia:** cubre T10 sin trabajo extra de integración.

## Backlog para Notion

37 tareas listas para pegar en la base "Plan y decisiones" (el mínimo exigido es 8). Agreguen en Notion las columnas Estado y Fecha de cierre; el criterio de "hecho" de cada tarea está en el documento personal de su dueño.

| ID | Tarea | Dueño | Día | Depende de |
| --- | --- | --- | --- | --- |
| J-01 | Crear repo, estructura de carpetas, README base, .env.example, Makefile | José | Mar | — |
| J-02 | Datos stub sintéticos (10 noticias) para avanzar sin esperar ingesta | José | Mar | J-01 |
| J-03 | Esqueleto Streamlit: bandeja, ficha, borrador, revisión | José | Mar | J-02 |
| J-04 | Elegir proveedor LLM y registrar ADR-005 completo | José | Mar | — |
| J-05 | `scoring_v1.yaml` + cálculo de R, I, U, N, E y puntaje P | José | Mié | B-08 |
| J-06 | Búsqueda semántica en español sobre los embeddings | José | Mié | B-07 |
| J-07 | Prompt, esquema JSON y validador de citas | José | Mié | J-04 |
| J-08 | Generar brief, guion 45–60 s y copy ≤80 palabras | José | Mié | J-07 |
| J-09 | Exportar `fichas.jsonl` y estados de revisión | José | Mié | J-08 |
| J-10 | Abstención y contradicciones (T05, T06) | José | Jue | J-08 |
| J-11 | Defensa anti-inyección (T07) | José | Jue | J-07 |
| J-12 | Caché offline y modo sin internet (T10) | José | Jue | J-08 |
| J-13 | Medir latencia mediana y p95, tokens y costo | José | Jue | J-08 |
| J-14 | Tag v1.0, README final, acceso del jurado al repo | José | Jue | Todo |
| B-01 | Ingesta TVN RSS | B | Mar | J-01 |
| B-02 | Ingesta GDELT DOC 2.0 por fechas, dedupe por URL | B | Mar | J-01 |
| B-03 | Ingesta Banco Mundial: cuadrícula completa (540 combinaciones) con nulos | B | Mar | J-01 |
| B-04 | Ingesta USGS 2024, caja regional, M≥3 | B | Mar | J-01 |
| B-05 | Validación y reporte de calidad (T01) | B | Mar | B-01 a B-04 |
| B-06 | `procedencia_id`: detectar agencias replicadas | B | Mié | B-05 |
| B-07 | Embeddings y clasificación por tema | B | Mié | B-05 |
| B-08 | Agrupación de eventos y conteo de procedencias (T02) | B | Mié | B-06, B-07 |
| B-09 | Baseline: palabras clave + TF-IDF | B | Mié | B-05 |
| B-10 | `manifest.json` con SHA-256 y `diccionario.md` | B | Mié | B-05 |
| B-11 | Noticias recirculadas: conservar fecha original (T03) | B | Jue | B-08 |
| B-12 | Macro-F1 de IA vs baseline sobre etiquetas humanas | B | Jue | B-09, C-05 |
| C-01 | Espacio Notion con 8 páginas, acceso de equipo y jurado | C | Mar | — |
| C-02 | Cargar ADRs y este backlog en "Plan y decisiones" | C | Mar | C-01 |
| C-03 | Post diario en LinkedIn (3 marcas + hashtags) | C | Mar, Mié, Jue | — |
| C-04 | Catálogo de datos con B | C | Mié | B-10 |
| C-05 | Etiquetar 60 noticias: tema y evento | C | Mié | B-05 |
| C-06 | Benchmark de desarrollo: 40 consultas | C | Mié | B-05 |
| C-07 | Página Riesgos y ética | C | Mié | — |
| C-08 | Ejecutar T01–T10 y registrar resultados | C | Jue | J-12 |
| C-09 | Precision@5 contra selección independiente | C | Jue | J-05 |
| C-10 | 5+ fichas en Notion, una con evidencia insuficiente | C | Jue | J-09 |
| C-11 | Pitch en Notion y 2 ensayos cronometrados | C | Jue | Todo |

## Checklist de entrega · jueves 23:59

Congelamos código a las 20:00; de 20:00 a 23:00 solo se documenta y ensaya; a las 23:00 se entrega, con una hora de margen.

**Repo (José)**

- [ ] README con: qué hace, instalación, `make demo`, variables de entorno, cómo correr pruebas.
- [ ] `requirements.txt` con versiones fijadas y `.env.example` sin secretos.
- [ ] `git log` y capturas revisados: ningún token.
- [ ] Tag `v1.0` y acceso del jurado verificado desde una cuenta externa.

**Datos (B)**

- [ ] `raw/`, `processed/`, `manifest.json`, `diccionario.md` y `benchmark_dev.jsonl` en el repo.
- [ ] Si una fuente no permite redistribuir, solo metadatos y la receta para descargarla.

**Notion (C)**

- [ ] Las 8 páginas completas y el enlace abre para el jurado.
- [ ] Al menos 8 tareas y 3 decisiones con fecha; una prueba fallida con su corrección.
- [ ] 5+ fichas, una con evidencia insuficiente.
- [ ] Matriz T01–T10 con numerador, denominador y fallos.
- [ ] Pitch navegable con enlaces al repo y a la demo.

**Demo (todos)**

- [ ] Ensayada con wifi apagado.
- [ ] Recorrido del pitch: una consulta útil, una ficha con citas, un borrador, un caso de abstención.
- [ ] Respuestas listas para las 4 preguntas del jurado: de dónde viene esta cifra y de qué año; cuántas fuentes independientes hay si 5 medios replican una agencia; qué pasa sin evidencia o con una fuente que intenta cambiar instrucciones; dónde está en Notion una decisión, una prueba fallida y su corrección.
