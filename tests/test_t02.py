"""T02 · Three records of the same event. Owner: B (B-08).

Prepared input: 3 headlines about the same event.
Expected result: 1 cluster, 3 sources, importance not tripled (independent provenances are counted, not records).
Source: test matrix in docs/c-producto-notion-qa.md (section 9 of the challenge).

Runs the real pipeline (embedding model from the local cache, B-06/B-07/B-08) on a
small synthetic set (sintetico=true, never in the corpus): three outlets with the same
event, an unrelated item the same day and the same event 5 days later.
"""

import pandas as pd

from src.ingest.common import NEWS_COLUMNS
from src.nlp import cluster, embed
from src.nlp.run import enrich
from src.score import score_clusters

T0 = pd.Timestamp("2026-09-20T13:00:00Z")
NOW = pd.Timestamp("2026-09-21T00:00:00Z")


def item(i: int, titulo: str, dominio: str, hours: float = 0, descripcion: str | None = None) -> dict:
    return {
        "id_noticia": f"N-{i:010x}", "titulo": titulo, "descripcion": descripcion,
        "url": f"https://{dominio}/n{i}", "medio": dominio, "dominio": dominio, "idioma": "es",
        "fecha_publicacion": None, "fecha_deteccion": T0 + pd.Timedelta(hours=hours),
        "fecha_extraccion": NOW, "origen": "gdelt", "alcance_texto": "titular/metadatos",
        "procedencia_id": None, "tema": None, "tema_confianza": None, "cluster_id": None, "sintetico": True,
    }


def frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=NEWS_COLUMNS)
    for col in ("fecha_publicacion", "fecha_deteccion", "fecha_extraccion"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


SAME_EVENT = [
    "Canal de Panamá aumenta a 36 los tránsitos diarios de buques",
    "El Canal de Panamá sube a 36 los tránsitos diarios por la mejora del lago Gatún",
    "Canal de Panamá permitirá 36 tránsitos diarios de buques desde octubre",
]


def run(news: pd.DataFrame) -> pd.DataFrame:
    return enrich(news, embed.embed_news(news, cache=False))


def test_t02_three_outlets_one_cluster_three_sources():
    rows = [item(i, t, d, hours=i * 5) for i, (t, d) in enumerate(zip(SAME_EVENT, ["a.com", "b.com", "c.com"]))]
    rows.append(item(9, "Selección de Panamá anuncia convocatoria para el amistoso de noviembre", "a.com", hours=2))
    out = run(frame(rows)).set_index("id_noticia")

    event_ids = [f"N-{i:010x}" for i in range(3)]
    assert out.loc[event_ids, "cluster_id"].nunique() == 1
    assert out.loc["N-0000000009", "cluster_id"] != out.loc[event_ids[0], "cluster_id"]

    clusters = cluster.build_clusters(out.reset_index()).set_index("cluster_id")
    row = clusters.loc[out.loc[event_ids[0], "cluster_id"]]
    assert row["n_registros"] == 3
    assert row["n_medios"] == 3  # no source is lost
    assert sorted(row["ids_noticia"]) == event_ids
    assert row["tema"] == "logística/Canal"


def test_t02_replicas_of_one_agency_count_as_one_provenance():
    rows = [item(i, t + " (EFE)", d, hours=i) for i, (t, d) in enumerate(zip(SAME_EVENT, ["a.com", "b.com", "c.com"]))]
    out = run(frame(rows))
    assert out["cluster_id"].nunique() == 1
    assert out["procedencia_id"].nunique() == 1

    scored = score_clusters(out, now=NOW).iloc[0]
    assert scored["n_registros"] == 3
    assert scored["n_procedencias_independientes"] == 1  # importance not tripled


def test_t02_same_story_more_than_72h_later_is_a_new_cluster():
    rows = [item(0, SAME_EVENT[0], "a.com"), item(1, SAME_EVENT[1], "b.com", hours=24 * 5)]
    out = run(frame(rows))
    assert out["cluster_id"].nunique() == 2
