"""Spanish search over the evidence (J-06). Owner: José.

Built on the synthetic stub plus synthetic World Bank cells and a USGS event, so the
expectations do not move when the real corpus is refreshed.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.generate.drafts import official_index
from src.generate.query import answer_question
from src.search import SearchIndex

STUB = Path(__file__).resolve().parents[1] / "data" / "stub" / "noticias_stub.parquet"


@pytest.fixture(scope="module")
def news() -> pd.DataFrame:
    return pd.read_parquet(STUB)


@pytest.fixture(scope="module")
def index(news) -> SearchIndex:
    # Synthetic official data (sintético): inflation for 2 years, GDP, one quake.
    cells = pd.DataFrame([
        {"pais_iso3": "PAN", "indicador_id": "FP.CPI.TOTL.ZG", "anio": 2023, "valor": 1.5, "unidad": "% anual"},
        {"pais_iso3": "PAN", "indicador_id": "FP.CPI.TOTL.ZG", "anio": 2024, "valor": 0.7, "unidad": "% anual"},
        {"pais_iso3": "PAN", "indicador_id": "FP.CPI.TOTL.ZG", "anio": 2022, "valor": None, "unidad": "% anual"},
        {"pais_iso3": "PAN", "indicador_id": "NY.GDP.MKTP.KD.ZG", "anio": 2023, "valor": 7.2, "unidad": "% anual"},
    ])
    quake = {"features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [-80.0, 7.5, 10.0]},
                           "properties": {"id": "us-sintetico-1", "magnitude": 4.6, "place": "30 km S of Panama",
                                          "time": "2024-05-01T10:00:00.000Z"}}]}
    return SearchIndex.build(news, official_index(cells, quake))


def test_finds_the_cluster_by_its_words(index):
    result = index.search("calado del Canal de Panamá")
    assert not result.sin_evidencia
    top_ids = {h.id_evidencia for h in result.hits[:3]}
    canal = {"N-1456290885", "N-1c36f376ec", "N-ff62fc5537"}  # C-STUB-01
    assert top_ids & canal


@pytest.mark.parametrize("query", ["receta de pizza napolitana", "precio del bitcoin hoy", "clima en Noruega mañana", "", "¿?"])
def test_unrelated_query_is_sin_evidencia(index, query):
    result = index.search(query)
    assert result.sin_evidencia and result.evidence == []


def test_world_bank_hit_points_to_the_citable_value(index):
    hit = index.search("inflación de Panamá").hits[0]
    assert hit.campo == "valor" and hit.texto == hit.evidence.fields["valor"]
    assert hit.id_evidencia == "WB-PAN-FP.CPI.TOTL.ZG-2024"  # tie on text -> most recent year


def test_year_in_query_wins(index):
    assert index.search("inflación de Panamá en 2023").hits[0].id_evidencia == "WB-PAN-FP.CPI.TOTL.ZG-2023"


def test_null_cell_is_never_found(index):
    assert all(h.id_evidencia != "WB-PAN-FP.CPI.TOTL.ZG-2022" for h in index.search("inflación de Panamá 2022").hits)


def test_quake_is_found_as_seismic_evidence(index):
    hit = next(h for h in index.search("sismo cerca de Panamá").hits if h.evidence.kind == "sismo")
    assert hit.id_evidencia == "us-sintetico-1" and hit.campo == "place"


def test_news_hit_text_is_the_field_the_model_can_quote(index):
    for hit in index.search("cortes de agua en San Miguelito").hits:
        if hit.evidence.kind == "noticia":
            assert hit.texto == hit.evidence.fields[hit.campo]


def test_k_and_unique_evidence(index):
    result = index.search("Panamá", k=4)
    assert len(result.hits) <= 4
    ids = [e.id for e in result.evidence]
    assert len(ids) == len(set(ids))


class Recorder:
    def __init__(self):
        self.user = None

    def complete(self, messages, model, temperature):
        self.user = messages[1]["content"]
        return json.dumps({"abstencion": True, "motivo_abstencion": "prueba"}), {}


def test_search_feeds_only_its_hits_to_the_model(index, tmp_path):
    result = index.search("cortes de agua en San Miguelito")
    model = Recorder()
    answer_question(result.query, result.evidence, client=model, offline=False, cache_dir=tmp_path)
    sent = {line.split('"')[1] for line in model.user.splitlines() if line.startswith("<fuente id=")}
    assert sent == {e.id for e in result.evidence}


def test_sin_evidencia_never_reaches_the_model(index, tmp_path):
    class NoNetwork:
        def complete(self, *a, **k):
            raise AssertionError("must not be called")
    result = index.search("receta de pizza napolitana")
    out = answer_question(result.query, result.evidence, client=NoNetwork(), offline=False, cache_dir=tmp_path)
    assert out.output.abstencion and out.source == "sin_evidencia"


def test_null_title_is_skipped_not_a_crash(news):
    # The real corpus has GDELT rows with a null titulo: nothing to index or cite there.
    holes = news.copy()
    holes.loc[0, "titulo"] = None
    holes.loc[1, "medio"] = None
    index = SearchIndex.build(holes)
    assert all(p.text for p in index.passages)
    assert not any(p.evidence.id == holes.loc[0, "id_noticia"] and p.field == "titulo" for p in index.passages)
