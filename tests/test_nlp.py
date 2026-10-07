"""NLP pieces without the embedding model (B-06, B-07, B-08, B-09). Owner: B.

Hand-made vectors and synthetic rows, so these tests are exact and need no download.
"""

import numpy as np
import pandas as pd

from src.ingest.common import NEWS_COLUMNS
from src.nlp import baseline, cluster, provenance
from src.nlp.classify import OTHER, TOPICS

T0 = pd.Timestamp("2026-09-01T12:00:00Z")


def news(rows: list[dict]) -> pd.DataFrame:
    base = {"descripcion": None, "medio": None, "idioma": "es", "fecha_publicacion": None, "fecha_deteccion": None,
            "origen": "gdelt", "alcance_texto": "titular/metadatos", "sintetico": True}
    df = pd.DataFrame([{**base, **r} for r in rows]).reindex(columns=NEWS_COLUMNS)
    for col in ("fecha_publicacion", "fecha_deteccion", "fecha_extraccion"):
        df[col] = pd.to_datetime(df[col], utc=True)
    df["medio"] = df["medio"].fillna(df["dominio"])
    return df


def row(i: int, titulo: str, dominio: str, hours: float | None = 0, **extra) -> dict:
    when = None if hours is None else T0 + pd.Timedelta(hours=hours)
    return {"id_noticia": f"N-{i:010x}", "titulo": titulo, "dominio": dominio, "fecha_deteccion": when, **extra}


# --- B-06 procedencia -------------------------------------------------------------

def test_default_provenance_is_the_outlet():
    df = news([row(1, "Uno", "a.com"), row(2, "Otro tema distinto", "a.com"), row(3, "Tercero", "b.com")])
    assert provenance.assign_provenance(df).tolist() == ["P-a-com", "P-a-com", "P-b-com"]


def test_agency_named_in_title_or_description_is_the_provenance():
    df = news([row(1, "Sube el dólar, informa EFE", "a.com"),
               row(2, "Otra nota", "b.com", descripcion="dijo a la AFP un portavoz"),
               row(3, "Mapa de la zona", "c.com")])  # "Mapa" must not read as AP
    assert provenance.assign_provenance(df).tolist() == ["P-AG-efe", "P-AG-afp", "P-c-com"]


def test_near_copies_on_other_domains_within_48h_share_the_earliest_outlet():
    title = "Gobierno anuncia nuevo plan de agua potable para la provincia de Colón"
    df = news([row(1, title, "b.com", hours=10), row(2, title, "a.com", hours=0), row(3, title, "c.com", hours=60)])
    out = provenance.assign_provenance(df).tolist()
    assert out[0] == out[1] == "P-a-com"
    assert out[2] == "P-c-com"  # 60 h after the first: outside the 48 h window


def test_near_copy_of_an_agency_item_takes_the_agency():
    title = "Gobierno anuncia nuevo plan de agua potable para la provincia de Colón"
    df = news([row(1, title, "a.com", descripcion="Según EFE"), row(2, title, "b.com", hours=3)])
    assert set(provenance.assign_provenance(df)) == {"P-AG-efe"}


# --- B-08 agrupación ----------------------------------------------------------------

def unit(*xs: float) -> np.ndarray:
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_close_vectors_within_72h_are_one_cluster_and_far_in_time_are_not():
    vectors = np.stack([unit(1, 0, 0), unit(1, 0.05, 0), unit(1, 0, 0.05), unit(0, 1, 0)])
    when = pd.Series([T0, T0 + pd.Timedelta(hours=30), T0 + pd.Timedelta(hours=100), T0])
    labels = cluster.cluster_labels(vectors, when)
    assert labels[0] == labels[1]
    assert labels[2] != labels[0]  # same text, 100 h later
    assert labels[3] != labels[0]  # same time, different text


def test_complete_linkage_never_spans_more_than_72h():
    vectors = np.stack([unit(1, 0, 0)] * 3)
    when = pd.Series([T0, T0 + pd.Timedelta(hours=60), T0 + pd.Timedelta(hours=120)])
    labels = cluster.cluster_labels(vectors, when)
    assert labels[0] != labels[2]


def test_undated_items_stay_alone():
    vectors = np.stack([unit(1, 0, 0)] * 2)
    labels = cluster.cluster_labels(vectors, pd.Series([T0, pd.NaT]))
    assert labels[0] != labels[1]


def test_cluster_ids_are_stable_and_singletons_keep_the_provisional_id():
    ids = pd.Series(["N-00000000bb", "N-00000000aa", "N-00000000cc"])
    first = cluster.cluster_ids(ids, np.array([0, 0, 1]))
    second = cluster.cluster_ids(ids[::-1].reset_index(drop=True), np.array([1, 0, 0]))
    assert first[0] == first[1] == second[1] == second[2]
    assert first[2] == "K-00000000cc"


def test_clusters_count_provenances_not_records():
    df = news([row(i, "t", d, procedencia_id=p, tema=t, cluster_id="K-1")
               for i, (d, p, t) in enumerate([("a.com", "P-AG-efe", "economía"), ("b.com", "P-AG-efe", "economía"),
                                              ("c.com", "P-c-com", "otro")])])
    out = cluster.build_clusters(df).iloc[0]
    assert (out["n_registros"], out["n_procedencias_independientes"], out["n_medios"]) == (3, 2, 3)
    assert out["tema"] == "economía"
    assert out["fecha_primera"] == out["fecha_ultima"] == T0
    assert set(cluster.CLUSTER_COLUMNS) <= set(cluster.build_clusters(df).columns)


# --- B-09 baseline --------------------------------------------------------------------

def test_keyword_topics_and_whole_word_short_keywords():
    assert baseline.keyword_topic("Récord de tránsitos por el Canal y sus esclusas")[0] == "logística/Canal"
    assert baseline.keyword_topic("Sismo de magnitud 5 sacude Chiriquí")[0] == "eventos naturales"
    assert baseline.keyword_topic("Muere una leyenda del folclor")[0] == OTHER  # "ley" is not "leyenda"
    assert baseline.keyword_topic("") == (OTHER, 0.0)


def test_baseline_has_the_ai_output_columns_and_groups_exact_duplicates():
    title = "Gobierno anuncia nuevo plan de agua potable para la provincia de Colón"
    df = news([row(1, title, "a.com"), row(2, title, "b.com", hours=5), row(3, "Sismo en Chiriquí", "c.com")])
    out = baseline.run_baseline(df)
    assert list(out.columns) == baseline.OUTPUT_COLUMNS
    assert out.loc[0, "cluster_id"] == out.loc[1, "cluster_id"] != out.loc[2, "cluster_id"]
    assert set(out["tema"]) <= set(TOPICS) | {OTHER}
