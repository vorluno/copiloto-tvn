"""The synthetic stub follows the noticias.parquet contract (J-02). Owner: José.

This test runs for real (not skipped): if someone changes the contract, it fails
here before it fails in the app.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

STUB_PATH = Path(__file__).resolve().parents[1] / "data" / "stub" / "noticias_stub.parquet"

CONTRACT_COLUMNS = [
    "id_noticia", "titulo", "url", "medio", "dominio", "idioma",
    "fecha_publicacion", "fecha_deteccion", "fecha_extraccion", "origen",
    "alcance_texto", "procedencia_id", "tema", "tema_confianza", "cluster_id",
]
TOPICS = {
    "economía", "logística/Canal", "turismo", "servicios públicos",
    "eventos naturales", "regulación", "otro",
}


@pytest.fixture(scope="module")
def stub() -> pd.DataFrame:
    return pd.read_parquet(STUB_PATH)


def test_has_contract_columns(stub):
    missing = [c for c in CONTRACT_COLUMNS if c not in stub.columns]
    assert not missing, f"missing contract columns: {missing}"


def test_ten_synthetic_rows(stub):
    assert len(stub) == 10
    assert stub["sintetico"].all()


def test_ids_are_stable_and_unique(stub):
    assert stub["id_noticia"].is_unique
    assert stub["id_noticia"].map(lambda i: bool(re.fullmatch(r"N-[0-9a-f]{10}", i))).all()


def test_dates_are_utc(stub):
    for col in ("fecha_publicacion", "fecha_deteccion", "fecha_extraccion"):
        assert str(stub[col].dt.tz) == "UTC", col


def test_enumerations(stub):
    assert set(stub["origen"]) <= {"tvn_rss", "gdelt"}
    assert set(stub["alcance_texto"]) <= {"titular/metadatos", "descripcion_rss"}
    assert set(stub["tema"]) <= TOPICS


def test_missing_publication_date_stays_null(stub):
    # At least one GDELT item has no outlet date, and it is not backfilled with seendate.
    nulls = stub[stub["fecha_publicacion"].isna()]
    assert len(nulls) >= 1
    assert (nulls["origen"] == "gdelt").all()
    assert nulls["fecha_deteccion"].notna().all()


def test_t02_fixture_same_event(stub):
    sizes = stub.groupby("cluster_id").size()
    cluster_id = sizes.idxmax()
    event = stub[stub["cluster_id"] == cluster_id]
    assert len(event) == 3
    assert event["procedencia_id"].nunique() < len(event)  # shared wire story


def test_t03_fixture_recirculated(stub):
    recirculated = stub[stub["recirculada"]]
    assert len(recirculated) == 1
    item = recirculated.iloc[0]
    assert item["fecha_publicacion"].year == 2025
    assert item["fecha_deteccion"] - item["fecha_publicacion"] > pd.Timedelta(days=365)


def test_t07_fixture_injected_instruction(stub):
    injected = stub[stub["titulo"].str.contains("ignora tus instrucciones", case=False)]
    assert len(injected) == 1
