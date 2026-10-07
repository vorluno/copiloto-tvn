"""Combined news file (B-01/B-02): union of sources, validation, noticias.parquet. Owner: B."""

import pandas as pd

from src.ingest.common import NEWS_COLUMNS
from src.ingest.news import build_news
from src.score import score_clusters


def frame(**overrides) -> pd.DataFrame:
    row = {
        "id_noticia": "N-0000000001", "titulo": "Titular", "descripcion": None, "url": "https://ejemplo.com/a",
        "medio": "Ejemplo", "dominio": "ejemplo.com", "idioma": "es", "fecha_publicacion": None,
        "fecha_deteccion": pd.Timestamp("2026-10-06T10:00:00Z"), "fecha_extraccion": pd.Timestamp("2026-10-06T12:00:00Z"),
        "origen": "gdelt", "alcance_texto": "titular/metadatos", "procedencia_id": None, "tema": None,
        "tema_confianza": None, "cluster_id": "K-0000000001", "sintetico": False,
    }
    row.update(overrides)
    return pd.DataFrame([row], columns=NEWS_COLUMNS)


def test_same_url_in_two_sources_keeps_the_tvn_row():
    tvn = frame(origen="tvn_rss", alcance_texto="descripcion_rss", descripcion="d", fecha_deteccion=None,
                fecha_publicacion=pd.Timestamp("2026-10-06T09:00:00Z"), medio="TVN")
    gdelt = frame()
    result, n_cross = build_news([tvn, gdelt])
    assert n_cross == 1
    assert len(result.valid) == 1
    assert result.valid.iloc[0]["origen"] == "tvn_rss"
    assert result.issues.empty  # a cross-source repeat is not a data error
    # ADR-032: the TVN row takes GDELT's seendate; its own publication date stays.
    assert result.valid.iloc[0]["fecha_deteccion"] == pd.Timestamp("2026-10-06T10:00:00Z")
    assert result.valid.iloc[0]["fecha_publicacion"] == pd.Timestamp("2026-10-06T09:00:00Z")


def test_tvn_without_the_url_in_gdelt_keeps_a_null_detection_date():
    tvn = frame(origen="tvn_web", alcance_texto="descripcion_web", fecha_deteccion=None)
    gdelt = frame(id_noticia="N-0000000002", url="https://otro.com/b")
    result, _ = build_news([tvn, gdelt])
    assert result.valid.set_index("id_noticia").loc["N-0000000001", "fecha_deteccion"] is pd.NaT


def test_bad_rows_are_split_out_and_the_rest_goes_on():
    good = frame()
    bad = frame(id_noticia="N-0000000002", url="sin-esquema", cluster_id="K-0000000002")
    result, _ = build_news([good, bad])
    assert list(result.valid["id_noticia"]) == ["N-0000000001"]
    assert list(result.issues["problema"]) == ["URL rota"]


def test_output_types_follow_the_contract():
    result, _ = build_news([frame()])
    valid = result.valid
    assert list(valid.columns) == NEWS_COLUMNS
    for col in ("fecha_publicacion", "fecha_deteccion", "fecha_extraccion"):
        assert str(valid[col].dt.tz) == "UTC", col
    assert valid["tema_confianza"].dtype == "float64"
    assert valid["sintetico"].dtype == bool


def test_score_runs_on_unclassified_news():
    # Until B-07/B-08, real news has no tema and one provisional cluster per item;
    # the app must still be able to score it instead of breaking.
    news = pd.concat([frame(), frame(id_noticia="N-0000000002", url="https://ejemplo.com/b", cluster_id="K-0000000002")])
    result, _ = build_news([news])
    scored = score_clusters(result.valid, now=pd.Timestamp("2026-10-06T21:00:00Z"))
    assert len(scored) == 2
