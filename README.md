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

Equipo: José (líder técnico e integración), B (datos e IA), C (producto, Notion y QA).
Contexto completo en [`docs/`](docs/) y reglas de trabajo en [`CLAUDE.md`](CLAUDE.md).

> **Estado (J-01):** esqueleto. La app corre sobre 10 noticias **sintéticas**
> (`data/stub/`); ingesta, IA, puntaje y generación llegan en las tareas B-xx y J-05+.

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
| `LLM_API_KEY` | Clave del proveedor de LLM (pendiente J-04). **Nunca** se sube al repo. |
| `LLM_MODEL` | Modelo y versión exactos (se registran en ADR-005). |
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
- `tests/test_stub_contract.py`: verifica que el stub cumple el contrato de
  `noticias.parquet` y trae los casos de T02, T03 y T07.

Los resultados de cada corrida se registran en la matriz T01–T10 de Notion (C).

## Otros comandos

| Comando | Hace | Dueño |
| --- | --- | --- |
| `make setup` | Crea `.venv` e instala `requirements.txt` | José |
| `make stub` | Regenera `data/stub/noticias_stub.parquet` | José |
| `make data` | Ingesta de las 4 fuentes y validación | B |
| `make nlp` | Embeddings, temas, procedencia, clusters y baseline | B |
| `make demo` | Abre la app; `OFFLINE=1` usa solo caché | José |
| `make test` | Corre T01–T10 y pruebas de contrato | Todos |
| `make eval` | Corre el benchmark y escribe `outputs/reports/` | José y B |

## Estructura del repo

```
copiloto-tvn/
├── CLAUDE.md                 # José · reglas para toda sesión: contratos, reglas del reto, convenciones
├── README.md                 # José (revisa C)
├── Makefile                  # José
├── requirements.txt          # José · versiones fijadas
├── .env.example              # José · LLM_API_KEY=, LLM_MODEL=, OFFLINE=0
├── docs/                     # Todos · reto, plan maestro y documento de cada rol
├── rules/
│   └── scoring_v1.yaml       # José · reglas del puntaje P
├── data/
│   ├── raw/                  # B · descargas originales (no se suben)
│   ├── processed/            # B · archivos de los contratos
│   ├── stub/                 # José · datos sintéticos (sintetico=true)
│   ├── etiquetas_humanas.csv # C · 60 noticias etiquetadas
│   ├── manifest.json         # B · consultas, cortes, licencias, SHA-256
│   └── diccionario.md        # B · campos, tipos, unidades, origen
├── benchmark/
│   └── benchmark_dev.jsonl   # C · 40 consultas de desarrollo
├── src/
│   ├── ingest/               # B · tvn_rss.py, gdelt.py, worldbank.py, usgs.py
│   ├── validate.py           # B · reporte de calidad (T01)
│   ├── nlp/                  # B · embed.py, classify.py, cluster.py, baseline.py, provenance.py
│   ├── search.py             # José · búsqueda semántica
│   ├── score.py              # José · puntaje P
│   ├── generate/             # José · prompts/, schema.py, generate.py, guard.py
│   ├── fichas.py             # José · arma y exporta fichas.jsonl
│   └── eval/                 # B y José · metrics.py, run_benchmark.py
├── app/
│   └── streamlit_app.py      # José · interfaz
├── outputs/
│   ├── fichas.jsonl          # José → C
│   ├── cache/                # José · salidas del LLM por hash (modo offline; no se sube)
│   └── reports/              # B y José · calidad, F1, benchmark, latencia
└── tests/                    # test_t01.py … test_t10.py · dueño indicado en cada archivo
```

## Cómo trabajamos

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
