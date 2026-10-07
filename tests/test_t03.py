"""T03 · Old news recirculated. Owner: B (B-11).

Prepared input: A 2025 headline detected today.
Expected result: Shows the original publication date; it is not treated as a new event.
Source: test matrix in docs/c-producto-notion-qa.md (section 9 of the challenge).

Runs the real pipeline (embedding model from the local cache) on synthetic rows
(sintetico=true, never in the corpus): a story published in October 2025 and detected
again on 20 Sep 2026, next to the same story published that day by two outlets.
"""

import pandas as pd

from src.export import news_csv
from src.fichas import ACTION_RECIRCULATED, recommended_action
from src.ingest.common import NEWS_COLUMNS
from src.nlp import cluster, embed
from src.nlp.recirculation import mark_recirculated
from src.nlp.run import enrich
from src.score import score_clusters

ORIGINAL = pd.Timestamp("2025-10-15T14:00:00Z")
TODAY = pd.Timestamp("2026-09-20T12:00:00Z")
TITLE = "Autoridad del Canal de Panamá anuncia nuevas restricciones de calado por la sequía"


def item(i: int, dominio: str, published, detected) -> dict:
    return {
        "id_noticia": f"N-{i:010x}", "titulo": TITLE, "descripcion": None, "url": f"https://{dominio}/n{i}",
        "medio": dominio, "dominio": dominio, "idioma": "es", "fecha_publicacion": published,
        "fecha_deteccion": detected, "fecha_extraccion": TODAY, "origen": "gdelt",
        "alcance_texto": "titular/metadatos", "procedencia_id": None, "tema": None, "tema_confianza": None,
        "cluster_id": None, "sintetico": True,
    }


def corpus() -> pd.DataFrame:
    df = pd.DataFrame([
        item(0, "viejo.com", ORIGINAL, TODAY),        # 2025 story detected today
        item(1, "a.com", TODAY - pd.Timedelta(hours=2), None),
        item(2, "b.com", TODAY - pd.Timedelta(hours=1), None),
    ], columns=NEWS_COLUMNS)
    for col in ("fecha_publicacion", "fecha_deteccion", "fecha_extraccion"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def run() -> pd.DataFrame:
    news = corpus()
    return enrich(news, embed.embed_news(news, cache=False)).set_index("id_noticia")


def test_t03_marked_recirculated_and_keeps_its_original_date():
    out = run()
    old = out.loc["N-0000000000"]
    assert bool(old["recirculada"]) is True
    assert old["fecha_publicacion"] == ORIGINAL  # original date shown, never replaced
    assert old["fecha_deteccion"] == TODAY
    assert not out.loc[["N-0000000001", "N-0000000002"], "recirculada"].any()
    assert news_csv(out.reset_index()).set_index("id_noticia").loc["N-0000000000", "fecha_publicacion"] == "2025-10-15T14:00:00Z"


def test_t03_not_treated_as_a_new_event():
    out = run()
    # Same headline, but it does not join today's event: it is compared by its 2025 date.
    assert out.loc["N-0000000000", "cluster_id"] != out.loc["N-0000000001", "cluster_id"]
    assert out.loc["N-0000000001", "cluster_id"] == out.loc["N-0000000002", "cluster_id"]

    scored = score_clusters(out.reset_index(), now=TODAY).set_index("cluster_id")
    old, new = scored.loc[out.loc["N-0000000000", "cluster_id"]], scored.loc[out.loc["N-0000000001", "cluster_id"]]
    assert bool(old["recirculada"]) is True and bool(new["recirculada"]) is False
    assert old["base_urgencia"] == "publicacion"
    assert old["U"] < new["U"]  # urgency measured from 2025, not from today's detection
    assert recommended_action(old["estado_evidencia"], [], False, None, True) == ACTION_RECIRCULATED

    clusters = cluster.build_clusters(out.reset_index()).set_index("cluster_id")
    assert bool(clusters.loc[out.loc["N-0000000000", "cluster_id"], "recirculada"]) is True


def test_normal_detection_lag_is_not_recirculation():
    df = corpus()
    df.loc[0, "fecha_deteccion"] = ORIGINAL + pd.Timedelta(days=1)
    assert mark_recirculated(df).tolist() == [False, False, False]
