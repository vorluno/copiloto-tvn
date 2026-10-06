"""Builds data/stub/fichas_stub.jsonl: 4 SYNTHETIC case cards for the UI (C-12..C-14). Owner: José.

Follows the outputs/fichas.jsonl contract plus the LLM output schema from docs/jose.md,
so the frontend can be built before score.py (J-05) and generate.py (J-08) exist.
Scores are hand-written example values, NOT computed (`valores_de_ejemplo=true`).
Every cited passage is a literal substring of the cited stub field, as guard.py will require.

Cases:
- F-STUB-01: high priority with only partial evidence (T08).
- F-STUB-02: recirculated 2025 item, insufficient evidence (T03).
- F-STUB-03: unanswerable query -> abstention, null score (T06).
- F-STUB-04: source with injected instruction -> alert, nothing obeyed (T07).

Usage: python data/stub/make_fichas_stub.py  (run make_stub.py first)
"""

import json
from pathlib import Path

import pandas as pd

STUB_DIR = Path(__file__).parent
NEWS_PATH = STUB_DIR / "noticias_stub.parquet"
OUTPUT_PATH = STUB_DIR / "fichas_stub.jsonl"
ONLY_HEADLINE = "Basado únicamente en titular/metadatos."


def cite(news: pd.DataFrame, cluster_id: str, outlet_prefix: str, field: str, passage: str) -> dict:
    """Citation to a stub item; fails loudly if the passage is not in the field."""
    row = news[(news["cluster_id"] == cluster_id) & news["medio"].str.startswith(outlet_prefix)].iloc[0]
    assert passage in row[field], f"passage not found in {row['id_noticia']}.{field}"
    return {"id_fuente": row["id_noticia"], "campo": field, "pasaje": passage}


def ids_in(news: pd.DataFrame, cluster_id: str) -> list[str]:
    return news.loc[news["cluster_id"] == cluster_id, "id_noticia"].tolist()


WEIGHTS = {"R": 30, "I": 25, "U": 20, "N": 15, "E": 10}


def score(r: float, i: float, u: float, n: float, e: float) -> tuple[dict, dict]:
    """Example components in, P = 30R + 25I + 20U + 15N + 10E out (same formula as J-05)."""
    components = {"R": r, "I": i, "U": u, "N": n, "E": e}
    p = round(sum(WEIGHTS[k] * v for k, v in components.items()), 1)
    rango = "alto" if p >= 70 else "medio" if p >= 40 else "bajo"
    return (
        {"P": p, "rango": rango, "version_reglas": "scoring_v1", "valores_de_ejemplo": True},
        components,
    )


def build(news: pd.DataFrame) -> list[dict]:
    canal_tvn = cite(news, "C-STUB-01", "TVN", "titulo", "límite de calado por bajo nivel del lago Gatún")
    canal_efe = cite(news, "C-STUB-01", "Diario A", "titulo", "EFE: el Canal de Panamá fija nuevo calado máximo")
    quake = cite(news, "C-STUB-02", "Portal B", "titulo", "Sismo de magnitud 5,1 se siente en Chiriquí")
    injected_id = ids_in(news, "C-STUB-03")[0]

    p1, c1 = score(1.0, 0.8, 0.7, 0.6, 0.4)
    p2, c2 = score(1.0, 0.54, 0.1, 0.2, 0.2)
    p4, c4 = score(0.1, 0.0, 1.0, 0.0, 0.2)

    cards = [
        {
            "id_caso": "F-STUB-01",
            "modalidad": "editorial",
            "cluster_id": "C-STUB-01",
            "ids_fuente": ids_in(news, "C-STUB-01"),
            "n_registros": 3,
            "n_procedencias_independientes": 2,
            "puntaje": p1,
            "componentes": c1,
            "estado_evidencia": "parcial",
            "abstencion": False,
            "motivo_abstencion": None,
            "titulo": "Límite de calado en el Canal por bajo nivel de Gatún",
            "enfoque_interes_publico": "Efecto del nivel del lago Gatún en el tránsito por el Canal.",
            "afirmaciones": [
                {"texto": "TVN reporta que el Canal de Panamá anunció un límite de calado por bajo nivel del lago Gatún.",
                 "tipo": "hecho", "citas": [canal_tvn]},
                {"texto": "Una nota de EFE replicada por dos medios indica que el Canal fijó un nuevo calado máximo.",
                 "tipo": "declaracion", "citas": [canal_efe]},
            ],
            "citas": [canal_tvn, canal_efe],
            "contradicciones": [],
            "preguntas_investigacion": [
                "¿Cuál es el nuevo calado máximo y desde cuándo rige?",
                "¿Qué datos oficiales del nivel de Gatún respaldan la medida?",
                "¿Qué tipo de buques se ven afectados?",
            ],
            "verificaciones_pendientes": [
                "Falta fuente oficial: 3 registros, 2 procedencias independientes, sin indicador ni comunicado.",
            ],
            "borrador": {
                "brief": f"{ONLY_HEADLINE} TVN y una nota de EFE replicada por dos medios reportan un nuevo "
                         "límite de calado en el Canal de Panamá asociado al bajo nivel del lago Gatún. "
                         "No hay aún una fuente oficial en la evidencia.",
                "guion": None,
                "copy": None,
            },
            "alertas": [],
            "estado_revision": "nuevo",
            "revisor": None,
            "fecha_revision": None,
            "sintetico": True,
        },
        {
            "id_caso": "F-STUB-02",
            "modalidad": "editorial",
            "cluster_id": "C-STUB-02",
            "ids_fuente": ids_in(news, "C-STUB-02"),
            "n_registros": 1,
            "n_procedencias_independientes": 1,
            "puntaje": p2,
            "componentes": c2,
            "estado_evidencia": "insuficiente",
            "abstencion": False,
            "motivo_abstencion": None,
            "titulo": "Sismo en Chiriquí: nota de 2025 recirculada",
            "enfoque_interes_publico": "Evitar presentar como nuevo un evento de 2025.",
            "afirmaciones": [
                {"texto": "Un medio publicó en marzo de 2025 que un sismo de magnitud 5,1 se sintió en Chiriquí.",
                 "tipo": "hecho", "citas": [quake]},
            ],
            "citas": [quake],
            "contradicciones": [],
            "preguntas_investigacion": [
                "¿Por qué la nota vuelve a circular ahora?",
                "¿Hay un evento sísmico reciente en el catálogo del USGS?",
                "¿Algún medio la está presentando como nueva?",
            ],
            "verificaciones_pendientes": [
                "Fecha original de publicación 2025-03-14; detectada el 2026-10-06. No es un evento nuevo.",
            ],
            "borrador": {"brief": None, "guion": None, "copy": None},
            "alertas": [],
            "estado_revision": "requiere evidencia",
            "revisor": None,
            "fecha_revision": None,
            "sintetico": True,
        },
        {
            "id_caso": "F-STUB-03",
            "modalidad": "editorial",
            "cluster_id": None,
            "consulta": "¿Cuál fue la inflación de Panamá en septiembre de 2026?",
            "ids_fuente": [],
            "n_registros": None,
            "n_procedencias_independientes": None,
            "puntaje": None,  # no score without a cluster: null, never 0
            "componentes": None,
            "estado_evidencia": "insuficiente",
            "abstencion": True,
            "motivo_abstencion": "El corpus no tiene datos mensuales de inflación de 2026; "
                                 "el Banco Mundial solo trae series anuales hasta 2024.",
            "titulo": None,
            "enfoque_interes_publico": None,
            "afirmaciones": [],
            "citas": [],
            "contradicciones": [],
            "preguntas_investigacion": [],
            "verificaciones_pendientes": ["Buscar la cifra en una fuente oficial mensual."],
            "borrador": {"brief": None, "guion": None, "copy": None},
            "alertas": [],
            "estado_revision": "nuevo",
            "revisor": None,
            "fecha_revision": None,
            "sintetico": True,
        },
        {
            "id_caso": "F-STUB-04",
            "modalidad": "editorial",
            "cluster_id": "C-STUB-03",
            "ids_fuente": [injected_id],
            "n_registros": 1,
            "n_procedencias_independientes": 1,
            "puntaje": p4,
            "componentes": c4,
            "estado_evidencia": "insuficiente",
            "abstencion": True,
            "motivo_abstencion": "La única fuente no contiene un hecho noticioso; contiene una instrucción.",
            "titulo": None,
            "enfoque_interes_publico": None,
            "afirmaciones": [],
            "citas": [],
            "contradicciones": [],
            "preguntas_investigacion": [],
            "verificaciones_pendientes": [],
            "borrador": {"brief": None, "guion": None, "copy": None},
            "alertas": [f"posible instrucción inyectada en {injected_id}"],
            "estado_revision": "descartado",
            "revisor": None,
            "fecha_revision": None,
            "sintetico": True,
        },
    ]
    return cards


if __name__ == "__main__":
    cards = build(pd.read_parquet(NEWS_PATH))
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for card in cards:
            f.write(json.dumps(card, ensure_ascii=False) + "\n")
    print(f"{len(cards)} synthetic case cards -> {OUTPUT_PATH}")
