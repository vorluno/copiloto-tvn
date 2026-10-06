# hackIAthon · B — Datos e IA

Oct 6, 2026 · @vorluno

## Tu rol

Eres dueño de los datos y de la IA que los organiza: si tus archivos llegan a tiempo y cumplen el contrato, el resto del equipo avanza. Tu dimensión de la rúbrica es "Uso efectivo de IA" (15 puntos) y "Calidad técnica y evaluación" (10).

| Cuándo | Entregas a | Qué |
| --- | --- | --- |
| Martes 20:00 | José | `noticias.parquet` (parcial vale), `indicadores.csv`, `eventos.geojson`, reporte de calidad |
| Miércoles 12:00 | José y C | `clusters.parquet`, `manifest.json`, `diccionario.md` |
| Miércoles 18:00 | C | Ficha técnica de cada fuente para el catálogo de Notion |
| Jueves 14:00 | C | Macro-F1 de IA y baseline, con numerador, denominador y fallos |
| Jueves 20:00 | Repo | Datos finales y `make data` / `make nlp` reproducibles |

Cómo trabajas con el equipo:

- Los esquemas exactos están en "Contratos entre roles" del plan maestro. Si necesitas cambiar un campo, avisa a José antes.
- Rama por tarea (`feat/B-07-embeddings`) y el ID en cada commit.
- Cada decisión que tomes (modelo de embeddings, umbral de clustering, cómo detectas agencias) se la dictas a C para "Plan y decisiones" en Notion el mismo día.

Dos preguntas abiertas que José lleva al grupo del evento: si la organización entrega el snapshot ya congelado (en ese caso saltas B-01 a B-04) y qué ventana de fechas vale, porque el reto pide noticias de los últimos 30 días pero también dice excluir todo lo que esté fuera de \[2024-01-01, 2025-10-01). Hasta tener respuesta, extrae los últimos 30 días y documenta la ventana usada.

## Extracción de fuentes

Cuatro scripts en `src/ingest/`, uno por fuente; cada uno guarda la respuesta cruda en `data/raw/` con la fecha de extracción en el nombre y nunca se vuelve a pedir durante la demo. Los endpoints de abajo son de memoria: confírmalos contra la documentación enlazada en la sección 12 del PDF del reto antes de correr.

| Fuente | Archivo | Qué pedir | Cuidado con |
| --- | --- | --- | --- |
| TVN RSS | `tvn_rss.py` | Feed de la referencia \[2\] del reto: título, enlace, fecha, descripción. Meta ≥20 noticias de TVN | El RSS no guarda todo el histórico. La descripción del RSS no da licencia sobre el artículo: guardar solo metadatos |
| GDELT DOC 2.0 | `gdelt.py` | `mode=ArtList`, `format=json`, `maxrecords=250`, consultas: Panama + logística, turismo, economía, eventos naturales; una por ventana de días | Máximo 250 por consulta: partir por fechas. Deduplicar por URL. `seendate` es fecha de detección, no de publicación |
| Banco Mundial API v2 | `worldbank.py` | Países PAN;CRI;COL;DOM;MEX;GTM, años 2010:2024, una consulta por indicador (6), `format=json`, `per_page=1000` | Completar la cuadrícula con `valor` nulo donde falte: 6 × 6 × 15 = 540 combinaciones (el reto dice 1.350, cifra que no cuadra; documentar el cálculo y preguntar). Nunca 0. Licencia CC BY 4.0 en cada fila |
| USGS FDSN | `usgs.py` | `format=geojson`, 2024-01-01 a 2024-12-31, lat 5 a 12, lon −86 a −76, magnitud mínima 3 | La caja regional no es el territorio de Panamá. Solo sirve para hechos sísmicos, nunca para inundaciones ni pérdidas |

Campos de `noticias.parquet` que más se equivocan:

- `alcance_texto`: "titular/metadatos" para GDELT; "descripcion\_rss" si hay descripción de TVN. José lo usa para la frase obligatoria "basado únicamente en titular/metadatos".
- `fecha_publicacion`: la del medio; si no existe, nula. No la rellenes con `seendate`.
- `id_noticia`: estable entre corridas, por ejemplo `N-` + primeros 10 caracteres del SHA-1 de la URL normalizada.

Para `manifest.json` guarda por archivo: consulta exacta, fecha de corte UTC, cantidad de filas, filas excluidas y por qué, licencia y SHA-256.

## Procesamiento con IA

La IA del proyecto vive aquí: embeddings para clasificar y agrupar, medidos contra un baseline de palabras clave. Todo corre en CPU y queda en caché para la demo sin internet.

1. **Embeddings.** Elegir entre `intfloat/multilingual-e5-small` y `paraphrase-multilingual-MiniLM-L12-v2` con 20 titulares de prueba; registrar modelo y versión. Texto de entrada: título + descripción si existe. Guardar `data/processed/embeddings.npy` con su lista de IDs en el mismo orden.
2. **Clasificación por tema.** Escribir 2–3 frases en español que describan cada tema: economía, logística/Canal, turismo, servicios públicos, eventos naturales, regulación. Tema = el de mayor similitud coseno; si queda bajo el umbral, "otro". El umbral se calibra con la mitad de las etiquetas de C y se reporta con la otra mitad.
3. **Procedencia.** Una noticia replicada de una agencia comparte `procedencia_id` con el original. Dos señales: el nombre de la agencia en título o medio (EFE, AFP, AP, Reuters, Europa Press) y títulos casi idénticos en dominios distintos dentro de 48 h (similitud TF-IDF ≥ 0,9). Con solo titulares la detección es aproximada: decirlo en el diccionario.
4. **Agrupación de eventos.** Clustering aglomerativo por distancia coseno, solo entre noticias a menos de 72 h. Por cluster: registros, procedencias únicas, tema mayoritario, fechas primera y última. Tres titulares del mismo evento = 1 cluster, sin perder ninguna fuente (T02).
5. **Recirculadas (T03).** Si una noticia del cluster tiene `fecha_publicacion` muy anterior a su detección, marcar `recirculada=true` y conservar la fecha original para que el puntaje de urgencia no la trate como nueva.
6. **Baseline.** Diccionario de palabras clave por tema ("canal", "esclusa", "tránsito" para logística/Canal, etc.) y duplicados por TF-IDF solo, sin embeddings.
7. **Métricas.** Macro-F1 de tema para IA y baseline; precisión y recall por pares para la agrupación contra `cluster_humano`. Reportar tamaño de muestra, método de etiquetado y en qué temas el baseline empata o gana.

Lo que el pitch necesita de ti es una tabla de dos filas (IA vs baseline) y una frase honesta sobre cuándo la IA no ayuda.

## Tus tareas

12 tareas; las cinco del martes desbloquean a José, así que van primero aunque queden imperfectas.

### Martes 6

- [ ] **B-01 · TVN RSS.** ≥20 noticias de TVN en `data/raw/` y en `noticias.parquet`.
- [ ] **B-02 · GDELT.** ≥100 registros únicos (meta 200), deduplicados por URL, con la ventana efectiva anotada.
- [ ] **B-03 · Banco Mundial.** Cuadrícula completa país × indicador × año con nulos explícitos y unidad por indicador.
- [ ] **B-04 · USGS.** Todos los sismos que devuelva la consulta, sin fijar una cantidad.
- [ ] **B-05 · Validación (T01).** `validate.py` separa filas con fechas inválidas, URLs rotas o campos obligatorios vacíos en `outputs/reports/calidad.md`, conserva los nulos y no detiene la carga. Prueba con un archivo sintético roto en `tests/test_t01.py`.

### Miércoles 7

- [ ] **B-06 · Procedencia.** Cada noticia tiene `procedencia_id`; el diccionario explica la regla.
- [ ] **B-07 · Embeddings y temas.** Cada noticia tiene `tema` y `tema_confianza`; modelo y umbral anotados en Notion.
- [ ] **B-08 · Agrupación (T02).** `clusters.parquet` listo a las 12:00; prueba con 3 registros del mismo evento → 1 cluster, 3 fuentes, 1 o más procedencias según corresponda.
- [ ] **B-09 · Baseline.** `baseline.py` produce tema y duplicados sin embeddings, mismo formato de salida.
- [ ] **B-10 · Manifest y diccionario.** `manifest.json` con SHA-256 por archivo; `diccionario.md` con cada campo, tipo, unidad y origen. Pasar a C la ficha de cada fuente.

### Jueves 8

- [ ] **B-11 · Recirculadas (T03).** Una noticia vieja recirculada aparece con su fecha original; prueba en `tests/test_t03.py`.
- [ ] **B-12 · Métricas.** `outputs/reports/clasificacion.md` con macro-F1 de IA y baseline, n de la muestra y lista de errores. Entregar a C a las 14:00.

Al cerrar cada tarea: commit con su ID, aviso en el grupo del equipo y una línea a C para el registro de Notion.
