<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="docs/readme/hero-m-dark.png">
  <source media="(max-width: 600px)" srcset="docs/readme/hero-m-light.png">
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme/hero-dark.png">
  <img alt="Copiloto TVN. Copiloto editorial para la redacción de TVN Panamá: ordena las noticias por una prioridad explicada, muestra la evidencia de cada afirmación y redacta borradores que siempre revisa una persona. Nunca publica. Debajo, el espectro de prioridad de los 8,421 eventos reales del corpus, de 91.0 a 7.0, con los 35 de prioridad alta en negro." src="docs/readme/hero-light.png" width="100%">
</picture>

<p align="center">
  <a href="https://copiloto-tvn.apps.vorluno.dev"><b>Demo en línea</b></a> &nbsp;·&nbsp;
  <a href="docs/demo/copiloto-tvn-demo-respaldo.mp4">Video de 1 min 45 s</a> &nbsp;·&nbsp;
  <a href="#cómo-funciona">Cómo funciona</a> &nbsp;·&nbsp;
  <a href="#en-cifras">Cifras</a> &nbsp;·&nbsp;
  <a href="#correrlo-en-tu-máquina">Correrlo en tu máquina</a> &nbsp;·&nbsp;
  <a href="docs/notion/README.md">Documentación</a>
</p>

<br>

**hackIAthon 2026 · reto TVN Media · modalidad editorial.** Copiloto TVN lee noticias públicas (TVN y GDELT) y
datos oficiales (Banco Mundial y USGS), agrupa las noticias del mismo hecho y las ordena por una **prioridad que se
explica sola**: cinco componentes a la vista, calculados con reglas fijas. Para cada evento arma una ficha con la
evidencia y redacta **borradores para revisión humana**: resumen, guion de TV y texto para redes.

- **Cada afirmación lleva su cita:** ID de la fuente, campo y pasaje. Sin evidencia, no responde.
- **El texto de las fuentes es dato, nunca instrucción.** Si una fuente intenta dar órdenes, aparece una alerta.
- **Una prioridad alta no autoriza a publicar:** nada sale de aquí sin una persona.
- **Funciona sin internet** (`OFFLINE=1`): las respuestas del modelo vienen guardadas en el repositorio.

## Pruébalo

| Qué | Enlace |
| --- | --- |
| **Demo en línea** | <https://copiloto-tvn.apps.vorluno.dev> · usuario `jurado` · contraseña `unjq-r8ca-vt7q` |
| **Video de la demo sin internet** | [`docs/demo/copiloto-tvn-demo-respaldo.mp4`](docs/demo/copiloto-tvn-demo-respaldo.mp4) · 1 min 45 s, interfaz v1.1 |
| **Versión final** | tag [`v1.1`](https://github.com/vorluno/copiloto-tvn/releases/tag/v1.1) · misma lógica y datos que `v1.0`; cambia la interfaz (ADR-049) |
| **Notion del equipo** | [Documentación técnica](https://app.notion.com/p/3f36d0f0b114817ba1a2cf059af5b356) · [Documentación funcional](https://app.notion.com/p/3f36d0f0b11481feb68dc27af313d3f9) · [Presentación del Pitch Day](https://app.notion.com/p/3f36d0f0b114812d93a9d2b3f2163f56) (espacio del hackIAthon) |

Las credenciales son públicas a propósito: solo evitan que buscadores y bots indexen la demo. La demo corre `v1.1`
en línea: las preguntas sugeridas salen de la caché en segundos y las nuevas las redacta Gemini 2.5 Flash; si el
servicio de IA no responde, la app lo dice y no inventa. Las revisiones que se marquen ahí se borran al volver a
desplegar.

<br>

## Cómo funciona

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="docs/readme/flujo-m-dark.png">
  <source media="(max-width: 600px)" srcset="docs/readme/flujo-m-light.png">
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme/flujo-dark.png">
  <img alt="Del titular al borrador, en 7 etapas: 01 Cargar (valida y reporta calidad), 02 Organizar (temas, eventos, procedencias), 03 Contextualizar (dato oficial si se sostiene), 04 Priorizar (P con reglas fijas), 05 Explicar (ficha con su evidencia), 06 Producir (resumen, guion y redes) y 07 Revisar (decide una persona)." src="docs/readme/flujo-light.png" width="100%">
</picture>

<br><br>

**El LLM solo redacta.** Ordenar, contar fuentes independientes y validar citas lo hace código determinista, y cada
paso tiene su prueba (T01–T10). Cinco medios que replican a la misma agencia cuentan como **una** procedencia
(ADR-007). Un guard revisa toda salida del modelo, también la que viene de la caché: descarta citas que no existen,
cifras sin respaldo y datos del Banco Mundial sin país, año y unidad.

<br>

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="docs/readme/formula-m-dark.png">
  <source media="(max-width: 600px)" srcset="docs/readme/formula-m-light.png">
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme/formula-dark.png">
  <img alt="Prioridad con reglas fijas, en rules/scoring_v1.yaml: P = 30R + 25I + 20U + 15N + 10E. R, relación con Panamá y los 6 temas, por 30. I, impacto del tema y dato oficial, por 25. U, urgencia contra la fecha del corpus, por 20. N, novedad frente a los 7 días previos, por 15. E, evidencia: procedencias y fuente oficial, por 10. La IA no calcula la prioridad: solo redacta. Una prioridad alta no autoriza a publicar." src="docs/readme/formula-light.png" width="100%">
</picture>

<br><br>

Cada componente va de 0 a 1, así que P va de 0 a 100: bajo por debajo de 40, medio hasta 70 y alto desde 70. La
urgencia se mide contra la fecha más reciente del corpus y no contra el reloj, para que el orden sea reproducible
(ADR-027). El **estado de evidencia** se calcula aparte: el caso del Canal tiene P 78.3 y 7 procedencias, pero
ningún dato oficial vinculado, así que queda «parcial».

<br>

## La app

<img alt="La Mesa de la demo en línea: a la izquierda la barra lateral (Mesa, Preguntar, Revisión, Fuentes y datos) con el estado En línea; al centro la bandeja ordenada por prioridad; a la derecha la ficha del Canal de Panamá con prioridad 78.3 de 100, evidencia parcial, 7 notas de 7 fuentes independientes y la acción recomendada." src="docs/readme/app-mesa.png" width="100%">

**Mesa:** la bandeja ordenada por prioridad y la ficha del evento elegido, lado a lado. La ficha dice qué se
reporta, quién lo dice, qué está respaldado (cada cita con ID, campo y pasaje), qué falta y la acción recomendada, y
ahí mismo se piden los tres formatos de borrador: resumen, guion de TV y texto para redes.

<table>
  <tr>
    <td width="33%" valign="top"><img alt="Preguntar: respuesta a una pregunta sugerida, con los pasos visibles y cada dato con su fuente." src="docs/readme/app-preguntar.png"><br><b>Preguntar.</b> Cada respuesta muestra sus pasos y sus fuentes.</td>
    <td width="33%" valign="top"><img alt="Ficha sin evidencia suficiente: el sistema no redacta un borrador y explica qué falta." src="docs/readme/app-abstencion.png"><br><b>Sin evidencia, no inventa.</b> Explica qué falta en vez de redactar.</td>
    <td width="33%" valign="top"><img alt="Revisión: una persona marca el estado de cada caso con su nombre; queda registrado con fecha y hora." src="docs/readme/app-revision.png"><br><b>Revisión.</b> Decide una persona, con nombre y hora.</td>
  </tr>
</table>

<br>

## En cifras

<picture>
  <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="docs/readme/cifras-m-dark.png">
  <source media="(max-width: 600px)" srcset="docs/readme/cifras-m-light.png">
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme/cifras-dark.png">
  <img alt="En cifras, ejecución final: 11,337 noticias del 02/10/2025 al 30/09/2026; 8,421 eventos; 89 de 89 afirmaciones con cita válida; 88 de 89 con sustento revisado a mano (99 %, meta 90 %); 7 de 7 abstenciones correctas; 6 de 6 ataques sin filtración; latencia mediana de 4.84 s (meta 15 s); 407 pruebas en verde y 4 omitidas en la versión v1.1." src="docs/readme/cifras-light.png" width="100%">
</picture>

<br><br>

Benchmark de desarrollo de 40 consultas (20 sustentadas, 7 de contradicción, 7 sin respuesta y 6 adversariales)
con `google/gemini-2.5-flash` a temperatura 0. Costo total de 0.084 USD, unos **0.002 USD por consulta**. Los
límites también se reportan: el modelo puso lado a lado 3 de 7 contradicciones y respondió 15 de 20 consultas
respondibles. Detalle, con numerador y denominador, en [`outputs/reports/`](outputs/reports/).

<br>

## Cómo cumple el reto

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

<details>
<summary><b>Las cuatro preguntas del jurado</b></summary>
<br>

- **¿De dónde viene esta cifra y de qué año?** Cada cifra cita su ID (`WB-PAN-<indicador>-<año>`) y el campo
  `valor`. El guard descarta una cifra del Banco Mundial sin país, año y unidad, o dicha como «hoy» (T04). URL,
  licencia y fecha de extracción están en `data/manifest.json` y en el catálogo.
- **¿Cuántas fuentes independientes hay si 5 medios replican una agencia?** Una: comparten `procedencia_id`
  (ADR-007, T02). La bandeja muestra notas y fuentes independientes por separado.
- **¿Qué pasa sin evidencia o con una fuente que intenta cambiar instrucciones?** Se abstiene y dice qué falta
  (T06). La instrucción no se obedece y queda como alerta (T07).
- **¿Dónde está una decisión, una prueba fallida y su corrección?** Las decisiones, de ADR-001 a ADR-049, están en
  [`docs/notion/decisiones.csv`](docs/notion/decisiones.csv). Ejemplo de prueba fallida: T10 fallaba en Windows
  (asyncio abre un socket local) y se corrigió en el PR #41.

</details>

<br>

## Correrlo en tu máquina

Requisitos: **Python 3.11** y `make` (en Windows, WSL o Git Bash). Para la demo no hace falta clave ni internet: las
respuestas del modelo vienen guardadas en `outputs/cache/` (ADR-033).

```bash
git clone https://github.com/vorluno/copiloto-tvn.git
cd copiloto-tvn
make setup                  # .venv con versiones fijadas, .env desde .env.example y modelo de embeddings
OFFLINE=1 make demo         # app en http://localhost:8501, sin red: lo dice en pantalla
OFFLINE=1 make demo-cache   # comprueba que la caché tenga todo el recorrido del pitch
make test                   # T01–T10 y pruebas de contrato
make verify                 # recalcula los SHA-256 de los datos contra data/manifest.json
```

Las preguntas del pitch están en [`docs/demo/consultas_demo.txt`](docs/demo/consultas_demo.txt). Sin internet, una
pregunta distinta no está guardada: la app lo dice y no inventa.

> En Linux, `torch` desde PyPI descarga también las librerías de CUDA (~6 GB). Sin GPU, conviene instalar antes la
> versión CPU: `.venv/bin/pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu` y luego
> `make setup`.

<details>
<summary><b>Variables de entorno</b> (solo para generar respuestas nuevas)</summary>
<br>

| Variable | Para qué |
| --- | --- |
| `LLM_API_KEY` | Clave de OpenRouter (<https://openrouter.ai/keys>). **Nunca** se sube al repositorio. |
| `LLM_MODEL` | Modelo exacto (ADR-005): `google/gemini-2.5-flash`, temperatura 0. |
| `LLM_BASE_URL` | API compatible con OpenAI de OpenRouter: `https://openrouter.ai/api/v1`. |
| `LLM_PRICE_INPUT_PER_M`, `LLM_PRICE_OUTPUT_PER_M` | USD por millón de tokens, para el costo en `make eval` y `make demo-cache`. |
| `OFFLINE` | `1` = sin internet: las salidas del LLM se leen solo de `outputs/cache/`. |

</details>

<details>
<summary><b>Todos los comandos</b></summary>
<br>

| Comando | Hace | Dueño |
| --- | --- | --- |
| `make setup` | Crea `.venv`, instala `requirements.txt` y descarga una vez el modelo de embeddings (`make model`) | José |
| `make stub` | Regenera los datos sintéticos (`noticias_stub.parquet`, `fichas_stub.jsonl`) | José |
| `make data` | Descarga las fuentes y reconstruye y valida `noticias.parquet` (necesita internet) | Levi |
| `make news` | Reconstruye `noticias.parquet` y el reporte de calidad desde las descargas guardadas, sin red | Levi |
| `make nlp` | Embeddings, temas, procedencia, clusters, baseline, `noticias.csv`/`fuentes.json` y contexto oficial | Levi |
| `make verify` | Recalcula los SHA-256 de `data/manifest.json` y los compara con los archivos | Levi |
| `make demo` | Abre la app; `OFFLINE=1` usa solo caché | Cristian (app) · José (caché) |
| `make test` | Corre T01–T10 y las pruebas de contrato | Todos |
| `make eval` | Corre `benchmark/benchmark_dev.jsonl` por búsqueda → respuesta → guard y escribe en `outputs/reports/` las métricas, la latencia y la hoja de revisión de sustento; `OFFLINE=1` usa solo la caché | José y Levi |
| `make fichas` | Genera `outputs/fichas.jsonl` para los 10 eventos de mayor P (`TOP=5` para cambiarlo) | José |
| `make llm-check` | Una llamada real al LLM sobre el stub (necesita `LLM_API_KEY` en `.env`); queda en caché | José |
| `make demo-cache` | Llena `outputs/cache/` con las fichas del top 10 y las consultas de `docs/demo/consultas_demo.txt`; con `OFFLINE=1` comprueba sin red que no falte nada. Guía: [`docs/demo/corrida-llm.md`](docs/demo/corrida-llm.md) | José (corre Levi) |

</details>

<details>
<summary><b>Pruebas</b></summary>
<br>

```bash
make test             # pytest tests/ -v
```

- `tests/test_t01.py` … `test_t10.py`: las 10 pruebas del reto. Cada archivo dice la entrada preparada, el
  resultado esperado y su dueño.
- `tests/test_stub_contract.py` y `tests/test_fichas_stub_contract.py`: los datos sintéticos cumplen los contratos
  y traen los casos de T02, T03, T06, T07 y T08.
- `tests/test_textos.py`: la interfaz habla con palabras de redacción y nunca muestra valores internos.
- `tests/test_no_secrets.py`: falla si aparece una clave en cualquier archivo versionado.

Corrida de la versión final: **407 pruebas en verde y 4 omitidas**, con el modelo de embeddings. La matriz T01–T10,
con lo observado y cada corrección, está en [`docs/notion/pruebas.csv`](docs/notion/pruebas.csv).

</details>

<details>
<summary><b>Estructura del repositorio</b></summary>
<br>

```
copiloto-tvn/
├── CLAUDE.md                 # José · reglas para toda sesión: contratos, reglas del reto, convenciones
├── CONTRIBUTING.md           # José · cómo abrir un PR
├── Makefile                  # José
├── requirements.txt          # José · versiones fijadas
├── .env.example              # José · LLM_API_KEY=, LLM_MODEL=, OFFLINE=0
├── docs/                     # Todos · reto.pdf, backlog.md y documento de cada rol
│   ├── demo/                 # José y Cristian · consultas del pitch, video y guía de la corrida con Gemini
│   ├── notion/               # Todos · las 8 páginas del reto, imágenes y piezas interactivas de Notion
│   ├── readme/               # Imágenes de este README, en claro y en oscuro
│   └── entrega.md            # José · lista de la entrega
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
│   ├── nlp/                  # Levi · embed, classify, cluster, baseline, provenance, recirculation
│   ├── context.py            # Levi · contexto oficial (contexto.parquet)
│   ├── export.py · manifest.py · catalog.py  # Levi · CSV del reto, manifest + make verify, catálogo
│   ├── search.py             # José · búsqueda
│   ├── score.py              # José · puntaje P
│   ├── generate/             # José · prompts/, schema.py, generate.py, guard.py
│   ├── fichas.py             # José · arma y exporta fichas.jsonl
│   ├── demo_cache.py         # José · make demo-cache
│   └── eval/                 # Levi y José · metrics.py, run_benchmark.py
├── app/
│   ├── streamlit_app.py      # Cristian · interfaz (lee contratos, escribe revisiones.jsonl)
│   ├── textos.py             # Palabras de redacción para todo lo que se ve en pantalla
│   └── static/fonts/         # Archivo e IBM Plex Mono (OFL), servidas por la propia app
├── outputs/
│   ├── fichas.jsonl          # José → Cristian
│   ├── revisiones.jsonl      # Cristian (app) · estados de revisión con persona y hora
│   ├── cache/                # José · salidas del LLM por hash para la demo sin internet (ADR-033)
│   └── reports/              # Levi y José · calidad, F1, benchmark, latencia
└── tests/                    # test_t01.py … test_t10.py y pruebas de contrato
```

</details>

<br>

## Equipo

| Persona | Rol |
| --- | --- |
| José Luis González Montenegro | Líder técnico e integración |
| Jampier González («Levi» en el repositorio) | Datos e IA |
| Cristian Valdés | Producto, frontend y QA |

Nadie trabajó en `main`: una rama por tarea (`feat/J-05-puntaje`, `feat/B-07-embeddings`, `docs/C-04-catalogo`),
PR corto y commits con el ID de la tarea. Cero secretos en código, documentos, video o capturas. Código en inglés;
contratos de datos, interfaz y documentación en español. Detalle en [`CONTRIBUTING.md`](CONTRIBUTING.md) y
[`CLAUDE.md`](CLAUDE.md). El reto está en [`docs/reto.pdf`](docs/reto.pdf); el alcance y el uso de cada fuente en
[`docs/alcance-y-datos.md`](docs/alcance-y-datos.md).

## Fuentes y licencias

TVN (RSS y sitemaps, solo metadatos públicos: no se guarda ni redistribuye el cuerpo), GDELT DOC 2.0 (solo titular,
URL y metadatos), Banco Mundial API v2 (CC BY 4.0, con atribución) y USGS FDSN (dominio público). El catálogo
completo, con fecha de extracción, cobertura y SHA-256, está en `data/manifest.json` y en
[`docs/notion/catalogo.csv`](docs/notion/catalogo.csv). Las fuentes tipográficas de la app (Archivo e IBM Plex Mono)
se distribuyen bajo la licencia SIL Open Font License.

<br>

<p align="center"><sub>Borradores para revisión humana. Nada se publica desde aquí.</sub></p>
