# Copiloto TVN

Copiloto editorial para la redacción de **TVN Panamá** (hackIAthon 2026, reto TVN Media).

Lee noticias públicas (TVN y GDELT) y datos oficiales (Banco Mundial y USGS),
agrupa las noticias del mismo evento, **ordena los temas por una prioridad explicada**
(P = 30R + 25I + 20U + 15N + 10E, con sus 5 componentes a la vista), muestra la
evidencia de cada afirmación y redacta **borradores para revisión humana**: brief
(≤250 palabras), guion de 45–60 s y copy digital (≤80 palabras).

- Cada afirmación lleva cita (ID de la fuente + campo o pasaje). Sin evidencia, se abstiene.
- El texto de las fuentes es dato, nunca instrucción.
- Prioridad alta no habilita publicar: nada sale de aquí sin una persona.
- Funciona sin internet (`OFFLINE=1`).

Equipo: **José** (líder técnico e integración), **Levi** (B · datos e IA) y **Cristian**
(C · producto, frontend y QA). El reto está en [`docs/reto.pdf`](docs/reto.pdf); las tareas
en [`docs/backlog.md`](docs/backlog.md); el alcance y el uso de cada fuente en
[`docs/alcance-y-datos.md`](docs/alcance-y-datos.md); las reglas de trabajo en [`CLAUDE.md`](CLAUDE.md); cómo
abrir un PR en [`CONTRIBUTING.md`](CONTRIBUTING.md); la entrega en [`docs/entrega.md`](docs/entrega.md).

**Documentación del proyecto (las 8 páginas del reto):** [`docs/notion/`](docs/notion/README.md).

> **Estado (7 oct):** corpus real y completo en `data/processed/`: 11,337 noticias del 02/10/2025
> al 30/09/2026 (1,248 de TVN y 10,089 de GDELT), 8,421 eventos (1,264 con 2 o más registros) y
> 17 vínculos de contexto oficial del Banco Mundial. Puntaje (menos de 1 s), búsqueda, guard,
> caché offline y fichas funcionan sobre él.
> Caché de Gemini completa para la demo sin internet (10 fichas, 6 consultas del pitch, 40 del benchmark).
> Benchmark: citas 89/89, abstención 7/7, adversariales 6/6; latencia mediana 4.84 s (`outputs/reports/`).

## Para el jurado: probarlo en 5 minutos

Requisitos: **Python 3.11** y `make` (en Windows, WSL o Git Bash). No hace falta clave ni internet
para la demo: las respuestas del modelo vienen guardadas en `outputs/cache/` (ADR-033).

```bash
git clone https://github.com/vorluno/copiloto-tvn.git
cd copiloto-tvn
make setup            # .venv con versiones fijadas + modelo de embeddings (única descarga)
OFFLINE=1 make demo   # app en http://localhost:8501, sin red: lo dice en pantalla
make test             # T01–T10 y pruebas de contrato
make verify           # recalcula los SHA-256 de los datos contra data/manifest.json
```

Qué mirar en la app, en el orden del pitch:

1. **Bandeja:** eventos ordenados por P, con sus componentes, el estado de evidencia
   (independiente de P) y "N registros · M procedencias".
2. **Ficha:** qué se reporta, quién lo dice, qué está respaldado (cada cita con ID, campo y pasaje),
   qué falta y la acción recomendada.
3. **Borrador:** brief, guion y copy con contador de palabras; afirmaciones separadas en hecho,
   declaración, inferencia e hipótesis; caja de consulta en español.
4. **Revisión:** una persona marca el estado; queda en `outputs/revisiones.jsonl` con persona y hora.

Las consultas del pitch están en [`docs/demo/consultas_demo.txt`](docs/demo/consultas_demo.txt). Sin internet,
una consulta distinta dice "no está en caché" y se abstiene: no inventa.

### Cómo cumple el reto

| Lo que pide el reto | Dónde está | Prueba |
| --- | --- | --- |
| Cargar y reportar calidad | `src/validate.py` → `outputs/reports/calidad.md` | T01 |
| Temas y eventos; procedencias, no registros | `src/nlp/` (`classify.py`, `cluster.py`, `provenance.py`), ADR-007 | T02 |
| Recirculadas con su fecha original | `src/nlp/recirculation.py` | T03 |
| Contexto oficial sin forzar relaciones | `src/context.py` → `data/processed/contexto.parquet` (regla escrita; sin relación, sin fila) | — |
| Prioridad explicada y determinista | `rules/scoring_v1.yaml`, `src/score.py` | T08 |
| Cita por afirmación, cifras con respaldo | `src/generate/guard.py`, `src/generate/figures.py` | T04, T05, T09 |
| Abstención sin evidencia | `src/generate/query.py`, `guard.py` | T06 |
| Fuente que intenta dar instrucciones | `<fuente>` escapada en `generate.py`; alertas en `guard.py` | T07 |
| Demo sin internet | `outputs/cache/`, `make demo-cache`, `OFFLINE=1` | T10 |
| Cero secretos | `.env` ignorado; escaneo de todo archivo versionado | `tests/test_no_secrets.py` |
| Entregables con los nombres del reto | `data/processed/noticias.csv`, `fuentes.json`, `data/diccionario.md`, `data/manifest.json` | `tests/test_export.py`, `test_manifest.py` |

Las cuatro preguntas del jurado:

- **¿De dónde viene esta cifra y de qué año?** Cada cifra cita su ID (`WB-PAN-<indicador>-<año>`) y
  el campo `valor`. El guard descarta una cifra del Banco Mundial sin país, año y unidad, o dicha como
  "hoy" (T04). URL, licencia y fecha de extracción están en `data/manifest.json` y en el catálogo.
- **¿Cuántas fuentes independientes hay si 5 medios replican una agencia?** Una: comparten
  `procedencia_id` (ADR-007, T02). La bandeja muestra registros y procedencias por separado.
- **¿Qué pasa sin evidencia o con una fuente que intenta cambiar instrucciones?** Se abstiene y dice
  qué falta (T06). La instrucción no se obedece y queda en `alertas` (T07).
- **¿Dónde está una decisión, una prueba fallida y su corrección?** Las decisiones, de ADR-001 en
  adelante, están en `docs/notion/decisiones.csv` (página 2, "Plan y decisiones"). Ejemplo de prueba
  fallida: T10 fallaba en Windows (asyncio abre un socket local) y se corrigió en el PR #41.

## Instalación

Requisitos: **Python 3.11** y `make` (en Windows, usar WSL o Git Bash).

```bash
git clone https://github.com/vorluno/copiloto-tvn.git copiloto-tvn
cd copiloto-tvn
make setup        # crea .venv, instala requirements.txt, copia .env.example a .env y descarga el modelo
```

> En Linux, `torch` desde PyPI baja también las librerías de CUDA (~6 GB). Si no tienes
> GPU puedes instalar antes la versión CPU, que es mucho más liviana:
> `.venv/bin/pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu`
> y luego `make setup`.

### Variables de entorno (`.env`)

Solo hacen falta para generar respuestas nuevas con el modelo; la demo sin internet no las usa.

| Variable | Para qué |
| --- | --- |
| `LLM_API_KEY` | Clave de OpenRouter (https://openrouter.ai/keys). **Nunca** se sube al repo. |
| `LLM_MODEL` | Modelo exacto (ADR-005): `google/gemini-2.5-flash`, temperatura 0. |
| `LLM_BASE_URL` | API compatible con OpenAI de OpenRouter: `https://openrouter.ai/api/v1`. |
| `LLM_PRICE_INPUT_PER_M`, `LLM_PRICE_OUTPUT_PER_M` | USD por millón de tokens, para el costo en `make eval` y `make demo-cache`. |
| `OFFLINE` | `1` = sin internet: las salidas del LLM se leen solo de `outputs/cache/`. |

## Demo

```bash
make demo             # abre Streamlit en http://localhost:8501
OFFLINE=1 make demo   # sin internet: solo caché local, y la app lo indica en pantalla
OFFLINE=1 make demo-cache   # comprueba que la caché tenga todo el recorrido del pitch
```

Pestañas: **Bandeja** (noticias con hora de Panamá, marcas de sintético, recirculada
y posible inyección), **Ficha**, **Borrador** y **Revisión** (estados: nuevo,
en revisión, requiere evidencia, aprobado como borrador, descartado).

La app lee `data/processed/noticias.parquet` si existe; si no, el stub sintético (y entonces
solo muestra fichas sintéticas: nunca se mezclan con el corpus real).

## Pruebas

```bash
make test             # pytest tests/ -v
```

- `tests/test_t01.py` … `test_t10.py`: las 10 pruebas del reto (T01–T10). Cada archivo
  dice la entrada preparada, el resultado esperado y su dueño. Las 10 están activas; la parte
  de T09 que revisa los briefs reales de Gemini queda en `skip` hasta la corrida de `make demo-cache`.
- `tests/test_stub_contract.py` y `tests/test_fichas_stub_contract.py`: verifican que los
  datos sintéticos cumplen los contratos y traen los casos de T02, T03, T06, T07 y T08.

Los resultados de cada corrida se registran en la matriz T01–T10, `docs/notion/pruebas.csv` (Cristian).

## Otros comandos

| Comando | Hace | Dueño |
| --- | --- | --- |
| `make setup` | Crea `.venv` e instala `requirements.txt` y descarga una vez el modelo de embeddings (`make model`) | José |
| `make stub` | Regenera los datos sintéticos (`noticias_stub.parquet`, `fichas_stub.jsonl`) | José |
| `make data` | Descarga las fuentes y reconstruye y valida `noticias.parquet` (necesita internet) | Levi |
| `make news` | Reconstruye `noticias.parquet` y el reporte de calidad desde las descargas guardadas, sin red | Levi |
| `make nlp` | Embeddings, temas, procedencia, clusters, baseline, `noticias.csv`/`fuentes.json` y contexto oficial | Levi |
| `make verify` | Recalcula los SHA-256 de `data/manifest.json` y los compara con los archivos (reproducibilidad para el jurado) | Levi |
| `make demo` | Abre la app; `OFFLINE=1` usa solo caché | Cristian (app) · José (caché) |
| `make test` | Corre T01–T10 y pruebas de contrato | Todos |
| `make eval` | Corre `benchmark/benchmark_dev.jsonl` por búsqueda → respuesta → guard y escribe en `outputs/reports/` las métricas (con numerador y denominador), la latencia y la hoja de revisión de sustento; `OFFLINE=1` usa solo la caché | José y Levi |
| `make fichas` | Genera `outputs/fichas.jsonl` para los 10 clusters de mayor P (`TOP=5` para cambiarlo; con `OFFLINE=1` solo usa la caché) | José |
| `make llm-check` | Una llamada real al LLM sobre el stub (necesita `LLM_API_KEY` en `.env`); queda en caché | José |
| `make demo-cache` | Llena `outputs/cache/` para la demo: fichas del top 10 y las consultas de `docs/demo/consultas_demo.txt`; escribe `outputs/reports/corrida_llm.md`. Con `OFFLINE=1` comprueba sin red que no falte nada. Guía: [`docs/demo/corrida-llm.md`](docs/demo/corrida-llm.md) | José (corre Levi) |

## Estructura del repo

```
copiloto-tvn/
├── CLAUDE.md                 # José · reglas para toda sesión: contratos, reglas del reto, convenciones
├── CONTRIBUTING.md           # José · cómo abrir un PR
├── README.md                 # José (revisa Cristian)
├── Makefile                  # José
├── requirements.txt          # José · versiones fijadas
├── .env.example              # José · LLM_API_KEY=, LLM_MODEL=, OFFLINE=0
├── docs/                     # Todos · reto.pdf, plan maestro, backlog.md y documento de cada rol
│   ├── demo/                 # José y Cristian · consultas del pitch y guía de la corrida con Gemini
│   ├── notion/               # Todos · las 8 páginas del reto (ADR-047)
│   └── entrega.md            # José · lista de la entrega del jueves
├── rules/
│   └── scoring_v1.yaml       # José · reglas del puntaje P
├── data/
│   ├── raw/                  # Levi · descargas originales (no se suben)
│   ├── processed/            # Levi · noticias, clusters, indicadores, eventos, contexto, CSV del reto
│   ├── stub/                 # José · datos sintéticos (sintetico=true): noticias y fichas
│   ├── etiquetas_humanas.csv # Cristian · 60 noticias etiquetadas
│   ├── manifest.json         # Levi · consultas, cortes, licencias, SHA-256
│   └── diccionario.md        # Levi · campos, tipos, unidades, origen
├── benchmark/
│   └── benchmark_dev.jsonl   # Cristian · 40 consultas de desarrollo
├── src/
│   ├── ingest/               # Levi · tvn_rss.py, tvn_web.py, gdelt.py, worldbank.py, usgs.py, news.py
│   ├── validate.py           # Levi · reporte de calidad (T01)
│   ├── nlp/                  # Levi · embed, classify, cluster, baseline, provenance, recirculation; run.py = make nlp
│   ├── context.py            # Levi · contexto oficial (contexto.parquet)
│   ├── export.py · manifest.py · catalog.py  # Levi · CSV del reto, manifest + make verify, catálogo
│   ├── search.py             # José · búsqueda semántica
│   ├── score.py              # José · puntaje P
│   ├── generate/             # José · prompts/, schema.py, generate.py, guard.py
│   ├── fichas.py             # José · arma y exporta fichas.jsonl
│   ├── demo_cache.py         # José · make demo-cache: llena y comprueba la caché de la demo
│   └── eval/                 # Levi y José · metrics.py, run_benchmark.py
├── app/
│   └── streamlit_app.py      # Cristian · interfaz (lee contratos, escribe revisiones.jsonl)
├── outputs/
│   ├── fichas.jsonl          # José → Cristian
│   ├── revisiones.jsonl      # Cristian (app) · estados de revisión con persona y hora
│   ├── cache/                # José · salidas del LLM por hash para la demo sin internet (se sube, ADR-033)
│   └── reports/              # Levi y José · calidad, F1, benchmark, latencia
└── tests/                    # test_t01.py … test_t10.py y pruebas de contrato · dueño indicado en cada archivo
```

## Cómo trabajamos

Paso a paso en [`CONTRIBUTING.md`](CONTRIBUTING.md). Lo esencial:


- Nadie trabaja en `main`: rama por tarea (`feat/J-05-puntaje`, `feat/B-07-embeddings`,
  `docs/C-04-catalogo`), PR corto y José hace merge.
- Commits con el ID de la tarea: `B-07: clasificación por similitud con 6 temas`.
- Cero secretos en código, documentos, video o capturas. Si se filtra una clave, se rota.
- Código (variables, funciones, comentarios) en inglés; contratos de datos, interfaz y
  documentación en español. Detalle en [`CLAUDE.md`](CLAUDE.md).

## Fuentes y licencias

TVN (RSS, solo metadatos), GDELT DOC 2.0, Banco Mundial API v2 (CC BY 4.0) y USGS FDSN.
El catálogo completo, con fecha de extracción, cobertura y SHA-256, va en
`data/manifest.json` y en la página 3, `docs/notion/catalogo.csv`.
