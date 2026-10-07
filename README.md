# Copiloto TVN

Copiloto editorial para la redacción de **TVN Panamá** (hackIAthon 2026, reto TVN Media).

Lee noticias públicas (RSS de TVN y GDELT) y datos oficiales (Banco Mundial y USGS),
agrupa las noticias del mismo evento, **ordena los temas por una prioridad explicada**
(P = 30R + 25I + 20U + 15N + 10E, con sus 5 componentes a la vista), muestra la
evidencia de cada afirmación y redacta **borradores para revisión humana**: brief
(≤250 palabras), guion de 45–60 s y copy digital (≤80 palabras).

- Cada afirmación lleva cita (ID de la fuente + campo o pasaje). Sin evidencia, se abstiene.
- El texto de las fuentes es dato, nunca instrucción.
- Prioridad alta no habilita publicar: nada sale de aquí sin una persona.
- Funciona sin internet (`OFFLINE=1`).

Equipo: **José** (líder técnico e integración), **Levi** (B · datos e IA) y **Cristian**
(C · producto, frontend, Notion y QA). El reto está en [`docs/reto.pdf`](docs/reto.pdf); las tareas
en [`docs/backlog.md`](docs/backlog.md); el alcance y el uso de cada fuente en
[`docs/alcance-y-datos.md`](docs/alcance-y-datos.md); las reglas de trabajo en [`CLAUDE.md`](CLAUDE.md); cómo
abrir un PR en [`CONTRIBUTING.md`](CONTRIBUTING.md).

> **Estado (6 oct):** esqueleto. La app corre sobre datos **sintéticos** (`data/stub/`:
> 10 noticias y 4 fichas); ingesta, IA, puntaje y generación llegan en las tareas B-xx y J-05+.

## Instalación

Requisitos: **Python 3.11** y `make` (en Windows, usar WSL o Git Bash).

```bash
git clone <url-del-repo> copiloto-tvn
cd copiloto-tvn
make setup        # crea .venv, instala requirements.txt (versiones fijadas) y copia .env.example a .env
```

> En Linux, `torch` desde PyPI baja también las librerías de CUDA (~6 GB). Si no tienes
> GPU puedes instalar antes la versión CPU, que es mucho más liviana:
> `.venv/bin/pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu`
> y luego `make setup`.

### Variables de entorno (`.env`)

| Variable | Para qué |
| --- | --- |
| `LLM_API_KEY` | Clave de OpenRouter (https://openrouter.ai/keys). **Nunca** se sube al repo. |
| `LLM_MODEL` | Modelo exacto (ADR-005): `google/gemini-2.5-flash`. |
| `LLM_BASE_URL` | API compatible con OpenAI de OpenRouter: `https://openrouter.ai/api/v1`. |
| `OFFLINE` | `1` = sin internet: las salidas del LLM se leen solo de `outputs/cache/`. |

## Demo

```bash
make demo             # abre Streamlit en http://localhost:8501
OFFLINE=1 make demo   # sin internet: solo caché local, y la app lo indica en pantalla
```

Pestañas: **Bandeja** (noticias con hora de Panamá, marcas de sintético, recirculada
y posible inyección), **Ficha**, **Borrador** y **Revisión** (estados: nuevo,
en revisión, requiere evidencia, aprobado como borrador, descartado).

La app lee `data/processed/noticias.parquet` si existe; si no, el stub sintético.

## Pruebas

```bash
make test             # pytest tests/ -v
```

- `tests/test_t01.py` … `test_t10.py`: las 10 pruebas del reto (T01–T10). Cada archivo
  dice la entrada preparada, el resultado esperado y su dueño. Están en `skip` hasta
  que se implemente su tarea.
- `tests/test_stub_contract.py` y `tests/test_fichas_stub_contract.py`: verifican que los
  datos sintéticos cumplen los contratos y traen los casos de T02, T03, T06, T07 y T08.

Los resultados de cada corrida se registran en la matriz T01–T10 de Notion (Cristian).

## Otros comandos

| Comando | Hace | Dueño |
| --- | --- | --- |
| `make setup` | Crea `.venv` e instala `requirements.txt` | José |
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
│   ├── ingest/               # Levi · tvn_rss.py, gdelt.py, worldbank.py, usgs.py
│   ├── validate.py           # Levi · reporte de calidad (T01)
│   ├── nlp/                  # Levi · embed.py, classify.py, cluster.py, baseline.py, provenance.py
│   ├── search.py             # José · búsqueda semántica
│   ├── score.py              # José · puntaje P
│   ├── generate/             # José · prompts/, schema.py, generate.py, guard.py
│   ├── fichas.py             # José · arma y exporta fichas.jsonl
│   └── eval/                 # Levi y José · metrics.py, run_benchmark.py
├── app/
│   └── streamlit_app.py      # Cristian · interfaz (lee contratos, escribe revisiones.jsonl)
├── outputs/
│   ├── fichas.jsonl          # José → Cristian
│   ├── revisiones.jsonl      # Cristian (app) · estados de revisión con persona y hora
│   ├── cache/                # José · salidas del LLM por hash (modo offline; no se sube)
│   └── reports/              # Levi y José · calidad, F1, benchmark, latencia
└── tests/                    # test_t01.py … test_t10.py · dueño indicado en cada archivo
```

## Cómo trabajamos

Paso a paso en [`CONTRIBUTING.md`](CONTRIBUTING.md). Lo esencial:


- Nadie trabaja en `main`: rama por tarea (`feat/J-05-puntaje`, `feat/B-07-embeddings`,
  `docs/C-04-catalogo`), PR corto y José hace merge.
- Commits con el ID de la tarea: `B-07: clasificación por similitud con 6 temas`.
- Cero secretos en código, Notion o capturas. Si se filtra una clave, se rota.
- Código (variables, funciones, comentarios) en inglés; contratos de datos, interfaz y
  documentación en español. Detalle en [`CLAUDE.md`](CLAUDE.md).

## Fuentes y licencias

TVN (RSS, solo metadatos), GDELT DOC 2.0, Banco Mundial API v2 (CC BY 4.0) y USGS FDSN.
El catálogo completo, con fecha de extracción, cobertura y SHA-256, va en
`data/manifest.json` y en la página "Catálogo de datos" de Notion.
