"""Case card view (C-13). Owner: Cristian."""

from pathlib import Path

import pandas as pd
import pytest

from app.bandeja import read_cards
from app.ficha import citation_found, cluster_sources, component_points, headline_only, recommended_action

STUB_DIR = Path(__file__).resolve().parents[1] / "data" / "stub"


@pytest.fixture(scope="module")
def news() -> pd.DataFrame:
    return pd.read_parquet(STUB_DIR / "noticias_stub.parquet")


@pytest.fixture(scope="module")
def cards() -> dict:
    return {c["id_caso"]: c for c in read_cards(STUB_DIR / "fichas_stub.jsonl")}


def test_stub_citations_are_found_and_fakes_are_not(news, cards):
    for claim in cards["F-STUB-01"]["afirmaciones"]:
        assert all(citation_found(news, cita) for cita in claim["citas"])
    real = cards["F-STUB-01"]["afirmaciones"][0]["citas"][0]
    assert not citation_found(news, {**real, "pasaje": "una cifra que nadie dijo"})
    assert not citation_found(news, {**real, "id_fuente": "N-0000000000"})
    assert not citation_found(news, {**real, "campo": "descripcion_inexistente"})


def test_components_add_up_to_p_and_keep_nulls():
    row = {"R": 1.0, "I": 0.48, "U": 0.7, "N": 0.9172, "E": 0.4}
    assert sum(c["puntos"] for c in component_points(row)) == pytest.approx(73.8, abs=0.1)
    missing = component_points({**row, "E": None})[-1]
    assert missing["valor"] is None and missing["puntos"] is None  # never 0


def test_sources_and_headline_only(news):
    sources = cluster_sources(news, "C-STUB-01")
    assert len(sources) == 3 and set(sources["cluster_id"]) == {"C-STUB-01"}
    assert headline_only(sources)  # GDELT items carry only headline/metadata


def test_recommended_action_never_says_publish(cards):
    alert = recommended_action("insuficiente", cards["F-STUB-04"], False)
    assert "instrucciones" in alert
    assert "No presentar como nuevo" in recommended_action("insuficiente", None, True)
    assert "borrador" in recommended_action("parcial", cards["F-STUB-01"], False)
    assert "más evidencia" in recommended_action("insuficiente", None, False)
    for state in ("insuficiente", "parcial", "suficiente para el borrador"):
        assert "publicar" not in recommended_action(state, None, False).lower()
