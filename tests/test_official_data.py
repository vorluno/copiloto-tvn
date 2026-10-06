"""Levi's official data (B-03, B-04) as citable evidence (J-08). Owner: José.

Runs on the committed data/processed files, so a re-extraction is checked too.
Counts come from the files themselves, never hard-coded.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.generate.drafts import official_index
from src.generate.guard import guard
from src.ingest.usgs import read_events
from src.ingest.worldbank import read_indicators

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
pytestmark = pytest.mark.skipif(
    not (PROCESSED / "indicadores.csv").exists() or not (PROCESSED / "eventos.geojson").exists(),
    reason="official data not extracted yet (B-03, B-04)",
)


@pytest.fixture(scope="module")
def indicators() -> pd.DataFrame:
    return read_indicators(PROCESSED / "indicadores.csv")


@pytest.fixture(scope="module")
def events() -> dict:
    return json.loads((PROCESSED / "eventos.geojson").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def index(indicators, events):
    return official_index(indicators, events)


def test_every_non_null_indicator_and_every_quake_is_citable(index, indicators, events):
    kinds = pd.Series([e.kind for e in index.values()]).value_counts()
    assert kinds.get("indicador", 0) == indicators["valor"].notna().sum()
    assert kinds.get("sismo", 0) == len(events["features"])


def test_quake_ids_are_the_usgs_ids(index):
    quake_ids = {e.id for e in index.values() if e.kind == "sismo"}
    assert quake_ids == set(read_events(PROCESSED / "eventos.geojson")["id"])
    assert "None" not in quake_ids


def test_real_world_bank_cell_passes_guard_only_with_country_year_unit(index):
    cell = index["WB-PAN-NY.GDP.MKTP.KD.ZG-2023"]
    figure = cell.fields["valor"][:4]
    cite = {"id_fuente": cell.id, "campo": "valor", "pasaje": figure}

    def kept(text: str) -> bool:
        raw = {"abstencion": False, "preguntas_investigacion": ["¿a?", "¿b?", "¿c?"], "borrador": "x",
               "afirmaciones": [{"texto": text, "tipo": "hecho", "citas": [cite]}]}
        return bool(guard(raw, [cell], "brief").output.afirmaciones)

    assert kept(f"Según el Banco Mundial, el PIB de Panamá creció {figure} % anual en 2023.")
    assert not kept(f"El PIB de Panamá crece {figure} % hoy.")


def test_real_quake_backs_seismic_facts_only(index):
    quake = next(e for e in index.values() if e.kind == "sismo")
    cite = {"id_fuente": quake.id, "campo": "magnitude", "pasaje": quake.fields["magnitude"]}

    def kept(text: str) -> bool:
        raw = {"abstencion": False, "preguntas_investigacion": ["¿a?", "¿b?", "¿c?"], "borrador": "x",
               "afirmaciones": [{"texto": text, "tipo": "hecho", "citas": [cite]}]}
        return bool(guard(raw, [quake], "brief").output.afirmaciones)

    assert kept(f"El USGS registró un sismo de magnitud {quake.fields['magnitude']}.")
    assert not kept(f"El sismo de magnitud {quake.fields['magnitude']} causó pérdidas económicas.")
