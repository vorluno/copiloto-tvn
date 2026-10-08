# 4 · Diseño de solución

Todo corre en local con Python 3.11 (ADR-002). El LLM solo redacta; ordenar, contar fuentes y validar
citas lo hace código determinista. Cada paso tiene su prueba (T01–T10, página 6).

## Arquitectura

```
Fuentes públicas                Datos (data/processed/, B)              Agente (src/, José)                 App (app/, C)
TVN RSS + sitemaps ──┐
GDELT DOC 2.0 ───────┼─► ingesta + validación ─► noticias.parquet ─┐
Banco Mundial API ───┤   (src/ingest, validate)   indicadores.csv  ├─► puntaje P (score.py) ─────────┐
USGS FDSN ───────────┘                            eventos.geojson  │   búsqueda (search.py)           ├─► Bandeja · Ficha
                         temas, procedencia, ─► clusters.parquet ──┤   borradores con LLM (generate/) │   Borrador · Consulta
                         eventos (src/nlp)       contexto.parquet ─┘   guard de citas (guard.py) ─────┘   Revisión · Datos
                                                                       caché por hash (outputs/cache/)       │
                                                                                                             ▼
                                                                                          outputs/revisiones.jsonl
```

## Modelo de datos

Los archivos de contrato, con dueño y consumidor, están en `CLAUDE.md` §3; cada columna, en
[`data/diccionario.md`](../../data/diccionario.md). Reglas que valen en todos: UTF-8, fechas ISO 8601
en UTC (la app muestra hora de Panamá), nulos como nulos y nunca como 0, y `fecha_publicacion`
(la del medio) separada de `fecha_deteccion` (la de GDELT). `data/manifest.json` guarda el SHA-256
de cada archivo (`make verify`).

## Reglas del puntaje (`rules/scoring_v1.yaml`, `src/score.py`)

**P = 30R + 25I + 20U + 15N + 10E**, cada componente entre 0 y 1. Rangos: bajo [0, 40), medio
[40, 70), alto [70, 100]. Desempate: más urgente y luego ID.

| Componente | Cómo se calcula |
| --- | --- |
| R · relevancia | 1.0 si es de Panamá y de uno de los 6 temas; 0.5 tema sin Panamá; 0.1 "otro" |
| I · impacto | 0.6 × alcance del tema + 0.4 × indicador oficial vinculado |
| U · urgencia | horas desde la fecha original más reciente: ≤ 24 h 1.0 · ≤ 72 h 0.7 · ≤ 7 d 0.4 · más 0.1 (se mide contra la fecha del corpus, ADR-027) |
| N · novedad | 1 − similitud máxima con los eventos de los 7 días previos |
| E · evidencia | 0.6 × min(1, procedencias / 3) + 0.4 × fuente oficial |

`estado_evidencia` (insuficiente, parcial, suficiente para el borrador) es **independiente de P**:
prioridad alta no habilita publicar. El LLM no participa en el puntaje.

## Modelos y versiones

| Pieza | Qué usa | Detalle |
| --- | --- | --- |
| Tema | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | similitud con descripciones de los 6 temas; bajo 0.45 → "otro" (umbral calibrado con media muestra de etiquetas humanas, B-12) |
| Evento | los mismos embeddings | coseno ≤ 0.30, 2 raíces de contenido en común y 72 h, enlace completo |
| Procedencia | reglas | agencia citada > casi copia (TF-IDF ≥ 0.9, 48 h, otro dominio) > medio (ADR-007) |
| Baseline | palabras clave por tema; TF-IDF ≥ 0.9 para eventos | contra él se mide la IA (página 6) |
| Búsqueda | TF-IDF por raíces con filtro de cobertura | reproducible, para que la caché no cambie (ADR-044) |
| Redacción | `google/gemini-2.5-flash` vía OpenRouter, temperatura 0 | salida JSON validada con Pydantic (`SalidaLLM`) |
| Interfaz | Streamlit 1.65 | pandas 3.0, scikit-learn 1.9, sentence-transformers 6.1 (`requirements.txt` fijado) |

## Prompts y guard

- Prompt vigente: [`src/generate/prompts/brief_v3.txt`](../../src/generate/prompts/brief_v3.txt) (v1 y v2 se conservan). Las reglas van solo en el mensaje de sistema; la evidencia, escapada, dentro de etiquetas `<fuente>` en el de usuario.
- **Guard** (`src/generate/guard.py`), que corre también sobre lo que viene de la caché:
  - descarta cada afirmación cuya cita (ID + campo + pasaje) no exista en la evidencia enviada;
  - descarta cifras sin respaldo y datos del Banco Mundial sin país, año y unidad, o dichos como "hoy";
  - fuerza "basado únicamente en titular/metadatos" cuando la fuente no tiene más;
  - bloquea claves o el prompt de sistema en la salida, y agrega la alerta si una fuente **o la consulta** trae instrucciones (T07, ADR-046);
  - sin evidencia, abstención con lo que falta (T06).
- **Caché:** cada respuesta se guarda por SHA-256 de prompt, modelo y mensajes; con `OFFLINE=1` nada sale a la red (T10).

## Límites

- Contradicciones: el modelo puso lado a lado 3 de 7 en el benchmark.
- Clusters: algunos eventos quedan partidos (los 33 tránsitos del Canal están en el #2 y el #22) y en otros se mezclan hechos; la regla de 2 palabras en común reduce lo segundo.
- 73.5 % del corpus queda en "otro": el ranking trabaja sobre el resto.
- GDELT pesa 9 de cada 10 notas y tiene pocos medios panameños.
- Detalle y controles en la página 7 (`riesgos-y-etica.md`, `riesgos-datos.md`).
