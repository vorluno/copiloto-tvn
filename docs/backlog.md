# Backlog vigente · Copiloto TVN

Actualizado: martes 6 oct 2026. Fuente para la base "Tareas" de Notion (Cristian la carga en C-02).
Parte del backlog del plan maestro (37 tareas) con los cambios de abajo. Estados: ✅ hecha · 🟡 en curso · ⬜ por hacer · ↪ reasignada.

## Equipo

| Rol | Persona | Rama de ejemplo |
| --- | --- | --- |
| Líder técnico e integración | José | `feat/J-07-guard` |
| **B** · Datos e IA | **Levi** | `feat/B-03-worldbank` |
| **C** · Producto, frontend, Notion y QA | **Cristian** | `feat/C-12-bandeja` |

## Cambios respecto al plan maestro (6 oct)

1. **Cristian toma el frontend.** La interfaz (`app/`) pasa a ser suya: C-12 a C-16. José se queda con el backend (puntaje, búsqueda, generación, guard, caché, export de fichas). La app lee archivos del contrato y escribe `outputs/revisiones.jsonl` (ver CLAUDE.md §3), así que no pisan los mismos archivos.
2. **Levi toma la etapa 3 del reto, "Contextualizar"** (B-14), que no tenía dueño, y el **Catálogo de datos en Notion** (B-15, antes C-04): conoce las fuentes mejor que nadie.
3. **Entregables con el nombre del reto:** `noticias.csv` + `fuentes.json` (B-13). El reto (secc. 6–7) pide esos nombres; nuestro parquet sigue siendo el formato de trabajo.
4. **Notion lo da la organización** (licencia Business) y todavía no llega. Mientras tanto el registro va en `docs/notion/tareas.csv` y `decisiones.csv`, fechado en git, y se importa al llegar (ADR-011). C-01 ya no es crear el espacio: es armar las 8 páginas dentro del espacio provisto y verificar el acceso del jurado.
5. **LLM decidido:** OpenRouter + `google/gemini-2.5-flash`, temperatura 0 (ADR-005).
6. **Contrato:** `descripcion` (con nulos permitidos; solo RSS de TVN); `fecha_deteccion` nula en el RSS de TVN; nuevos `contexto.parquet` y `revisiones.jsonl`.
7. Tareas nuevas de otro tipo para Levi y Cristian: documentación, pitch, medición de valor y respaldo de la demo.

## José · líder técnico e integración

| ID | Tarea | Día | Depende de | Estado |
| --- | --- | --- | --- | --- |
| J-01 | Repo, estructura, README, Makefile, .env.example | Mar | — | ✅ (falta proteger `main`) |
| J-02 | Stub de 10 noticias sintéticas | Mar | J-01 | ✅ |
| J-03 | Esqueleto Streamlit con 4 pestañas | Mar | J-02 | ✅ → la sigue Cristian (C-12) |
| J-04 | Proveedor LLM y ADR-005 | Mar | — | 🟡 código listo; falta precio por token en Notion |
| J-05 | `score.py`: P y 5 componentes desde `scoring_v1.yaml` | Mié | B-08 (empieza con stub) | ✅ sobre el stub; falta correr con datos de Levi y `contexto.parquet` |
| J-06 | Búsqueda semántica: 10 fragmentos con ID y campo, o "sin evidencia" | Mié | B-07 | ✅ TF-IDF + cobertura; cambiar a embeddings cuando llegue B-07 |
| J-07 | Prompt, esquema Pydantic y `guard.py` | Mié | J-04 | ✅ #3 |
| J-08 | Brief, guion y copy con citas | Mié | J-07 | ✅ `build_package`; falta probar con Gemini y datos reales |
| J-09 | Exportar `fichas.jsonl` y leer `revisiones.jsonl` (solo backend; la interfaz es C-15) | Mié | J-08 | ✅ `make fichas`; falta correrlo con Gemini y noticias reales |
| J-10 | Abstención y contradicciones (T05, T06) | Jue | J-08 | ✅ T05 y T06 activas |
| J-11 | Defensa anti-inyección (T07) | Jue | J-07 | ✅ T07 activa |
| J-12 | Caché offline y modo sin internet (T10) | Jue | J-08 | 🟡 caché y modo offline listos; falta llenar la caché con el recorrido del pitch (jueves 12:00) |
| J-13 | Latencia mediana y p95, tokens y costo | Jue | J-08 | ⬜ |
| J-14 | Tag v1.0, README final, acceso del jurado | Jue | Todo | ⬜ |
| J-15 | `fichas_stub.jsonl` para que el frontend avance sin backend | Mar | J-02 | ✅ |
| J-16 | `docs/alcance-y-datos.md`: modalidad, recorrido y para qué sirve cada fuente (base de "Diseño de solución") | Mar | — | ✅ |

## Levi · B · datos e IA

| ID | Tarea | Día · hora | Depende de | Estado |
| --- | --- | --- | --- | --- |
| B-01 | Ingesta TVN RSS (≥20 noticias, con `descripcion`) | Mar 20:00 | J-01 | ✅ #15 (55 noticias) |
| B-02 | Ingesta GDELT DOC 2.0 por fechas, dedupe por URL | Mar 20:00 | J-01 | ⬜ |
| B-03 | Banco Mundial: cuadrícula completa con nulos (6 países × 6 indicadores × 15 años) | Mar 20:00 | J-01 | ✅ #9 |
| B-04 | USGS 2024, caja regional, M≥3 | Mar 20:00 | J-01 | ✅ #10 |
| B-05 | Validación y reporte de calidad (T01) | Mar 20:00 | B-01..B-04 | ✅ #12 (T01 activa) |
| B-06 | `procedencia_id`: agencias replicadas | Mié | B-05 | ⬜ |
| B-07 | Embeddings y clasificación por tema | Mié | B-05 | ⬜ |
| B-08 | Agrupación y conteo de procedencias (T02) | Mié 12:00 | B-06, B-07 | ⬜ |
| B-09 | Baseline: palabras clave + TF-IDF | Mié | B-05 | ⬜ |
| B-10 | `manifest.json` con SHA-256 y `diccionario.md` | Mié 12:00 | B-05 | ⬜ |
| B-11 | Recirculadas: conservar fecha original (T03) | Jue | B-08 | ⬜ |
| B-12 | Macro-F1 IA vs baseline sobre etiquetas humanas | Jue 14:00 | B-09, C-05 | ⬜ |
| **B-13** | **`noticias.csv` + `fuentes.json`** con los nombres del reto, desde el parquet | Mié 18:00 | B-05 | ⬜ |
| **B-14** | **Contexto oficial** (`contexto.parquet`): relacionar clusters con indicadores del Banco Mundial y sismos del USGS con una regla escrita; sin relación sustentada, sin fila. Alimenta el I y la E del puntaje y T04 | Mié 18:00 | B-03, B-04, B-08 | ⬜ |
| **B-15** | **Catálogo de datos en Notion** (antes C-04): una fila por fuente con los 8 campos del reto | Mié 18:00 | B-10 | ⬜ |
| **B-16** | **Riesgos de los datos** para la página "Riesgos y ética": derechos por fuente, sesgos (solo titulares, cobertura de GDELT), límites de la caja del USGS | Mié 20:00 | B-15 | ⬜ |
| **B-17** | **`make verify`**: recalcula los SHA-256 y los compara con `manifest.json` (reproducibilidad para el jurado) | Jue 12:00 | B-10 | ⬜ |
| **B-18** | **Pitch, bloque 4** (2 min: IA, baseline y métricas): sección en la página 8 de Notion con la tabla IA vs baseline y una frase honesta sobre cuándo no ayuda; 2 ensayos | Jue 20:00 | B-12 | ⬜ |

## Cristian · C · producto, frontend, Notion y QA

| ID | Tarea | Día · hora | Depende de | Estado |
| --- | --- | --- | --- | --- |
| C-01 | Armar las 8 páginas en el espacio Notion Business provisto; José y Levi como editores; acceso del jurado verificado | Al recibirlo | Organización | ⬜ bloqueada: la organización aún no entrega el espacio |
| C-02 | Llevar Tareas y Decisiones en `docs/notion/*.csv` desde hoy e importarlas a "Plan y decisiones" cuando llegue Notion | Mar 18:00 | — | 🟡 CSV iniciales listos |
| C-03 | Post diario en LinkedIn (3 marcas + hashtags) | Mar, Mié, Jue | — | ⬜ |
| C-04 | Catálogo de datos | — | — | ↪ B-15 (Levi) |
| C-05 | Etiquetar 60 noticias: tema y evento | Mié 12:00 | B-05 | ⬜ |
| C-06 | Benchmark de desarrollo: 40 consultas | Mié 18:00 | B-05 | ⬜ |
| C-07 | Página "Riesgos y ética" (con el aporte de Levi en B-16) | Mié 20:00 | B-16 | ⬜ |
| C-08 | Ejecutar T01–T10 y registrar resultados | Jue 18:00 | J-12 | ⬜ |
| C-09 | Precision@5 contra selección independiente | Jue | J-05 | ⬜ |
| C-10 | 5+ fichas en Notion, una con evidencia insuficiente | Jue | J-09 | ⬜ |
| C-11 | Pitch en Notion y 2 ensayos cronometrados | Jue 22:00 | Todo | ⬜ |
| **C-12** | **Bandeja priorizada (CU-01):** top 5 por P con rango, estado de evidencia, tema, "N registros · M procedencias", filtros; hora de Panamá. Lee `fichas_stub.jsonl` y luego `fichas.jsonl` | Mié 12:00 | J-15 | ✅ #7 |
| **C-13** | **Ficha (etapa 5):** qué se reporta, quién, qué está respaldado, qué falta y acción recomendada; 5 componentes en barras + versión de reglas; cada cita muestra ID, campo y pasaje | Mié 18:00 | C-12 | ✅ #16 |
| **C-14** | **Borrador y consulta:** brief, guion y copy con contador de palabras; afirmaciones con su tipo (hecho / declaración / inferencia / hipótesis) diferenciado; contradicciones lado a lado (T05); abstención visible (T06); alertas (T07); aviso "basado únicamente en titular/metadatos"; caja de consulta en español (CU-04) | Mié 20:00 | C-13 | ⬜ |
| **C-15** | **Revisión:** 5 estados + persona revisora + nota → `outputs/revisiones.jsonl`; botón "copiar para Notion" con la ficha en Markdown (ADR-008) | Mié 20:00 | C-13 | ⬜ |
| **C-16** | **Pantalla "Datos y calidad":** reporte de calidad, manifest y licencias; aviso de modo sin internet (T10) | Jue 12:00 | B-10 | ⬜ |
| **C-17** | **Valor operativo:** tiempo manual vs asistido en la misma tarea, ≥3 pruebas, para el bloque 5 del pitch. Si no se mide, se dice "hipótesis de valor" | Jue 14:00 | C-14 | ⬜ |
| **C-18** | **Respaldo de la demo:** grabación del recorrido con wifi apagado y capturas sin secretos en Notion (evidencia de T10) | Jue 19:00 | J-12 | ⬜ |

**Carga de Cristian:** es la más alta (17 tareas). Si se atrasa, se recortan en este orden: C-16, la caja de consulta de C-14 y luego C-17. Nunca se recortan la ficha con citas, la abstención ni el respaldo offline.

## Primer PR de cada uno (hoy)

- **Levi:** `feat/B-03-worldbank`. Es la API más estable y desbloquea T04 y B-14. Después siguen B-01, B-02, B-04 y B-05, cada una en su rama.
- **Cristian:** `feat/C-12-bandeja` sobre `data/stub/fichas_stub.jsonl`. En paralelo, mantener `docs/notion/*.csv` al día (C-02) y preparar el texto de las páginas 1 y 7 para pegarlo cuando llegue Notion.
- **José:** `feat/J-07-guard`, y luego `feat/J-05-puntaje` sobre el stub.
