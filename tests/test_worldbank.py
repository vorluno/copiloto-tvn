"""World Bank grid (B-03). Owner: B.

Offline: builds the grid from hand-written API payloads, so no test touches the network.
"""

import pandas as pd
import pytest

from src.ingest.worldbank import (
    COLUMNS,
    COUNTRIES,
    INDICATORS,
    LICENSE,
    YEARS,
    build_grid,
    parse_response,
    read_indicators,
    write_indicators,
)

EXTRACTED_AT = "2026-10-06T19:00:00Z"
GDP = "NY.GDP.MKTP.KD.ZG"


def record(iso3: str, year: int, value, indicator: str = GDP) -> dict:
    """One row as the World Bank API v2 returns it (unit comes empty in practice)."""
    return {
        "indicator": {"id": indicator, "value": "label"},
        "country": {"id": iso3[:2], "value": "label"},
        "countryiso3code": iso3,
        "date": str(year),
        "value": value,
        "unit": "",
        "obs_status": "",
        "decimal": 1,
    }


def payload(records: list[dict]) -> list:
    return [{"page": 1, "pages": 1, "per_page": 1000, "total": len(records)}, records]


@pytest.fixture
def grid() -> pd.DataFrame:
    records = {
        GDP: [
            record("PAN", 2023, 7.3),
            record("PAN", 2022, None),  # API says "no value"
            record("CRI", 2020, 0.0),  # a real zero must stay zero
        ]
    }
    return build_grid(records, EXTRACTED_AT)


def test_scope_matches_the_challenge():
    assert COUNTRIES == ["PAN", "CRI", "COL", "DOM", "MEX", "GTM"]
    assert list(YEARS) == list(range(2010, 2025))
    assert set(INDICATORS) == {
        "NY.GDP.MKTP.KD.ZG",
        "FP.CPI.TOTL.ZG",
        "SL.UEM.TOTL.ZS",
        "SP.POP.TOTL",
        "IT.NET.USER.ZS",
        "NE.EXP.GNFS.ZS",
    }


def test_grid_is_complete_even_without_data(grid):
    assert len(grid) == 6 * 6 * 15 == 540
    assert not grid.duplicated(["pais_iso3", "indicador_id", "anio"]).any()
    assert list(grid.columns) == COLUMNS


def test_missing_values_are_null_never_zero(grid):
    by_key = grid.set_index(["pais_iso3", "indicador_id", "anio"])["valor"]
    assert by_key[("PAN", GDP, 2023)] == pytest.approx(7.3)
    assert pd.isna(by_key[("PAN", GDP, 2022)])  # null from the API
    assert pd.isna(by_key[("MEX", "SP.POP.TOTL", 2015)])  # absent from the API
    assert by_key[("CRI", GDP, 2020)] == 0.0  # real zero kept
    assert (grid["valor"] == 0).sum() == 1


def test_every_row_has_unit_source_date_and_license(grid):
    assert grid["unidad"].notna().all()
    assert (grid.loc[grid["indicador_id"] == "SP.POP.TOTL", "unidad"] == "personas").all()
    assert (grid["licencia"] == LICENSE).all()
    assert (grid["fecha_extraccion"] == EXTRACTED_AT).all()
    assert grid["fuente_url"].str.startswith("https://api.worldbank.org/v2/").all()
    assert grid.loc[grid["indicador_id"] == GDP, "fuente_url"].str.contains(GDP).all()


def test_out_of_scope_records_are_ignored():
    records = {GDP: [record("USA", 2023, 2.5), record("PAN", 2009, 1.0), record("PAN", 2025, 1.0)]}
    grid = build_grid(records, EXTRACTED_AT)
    assert len(grid) == 540
    assert grid["valor"].isna().all()


def test_parse_response_reads_the_data_page():
    rows = parse_response(payload([record("PAN", 2023, 7.3)]))
    assert rows == [record("PAN", 2023, 7.3)]


def test_parse_response_returns_empty_when_there_is_no_data():
    assert parse_response([{"page": 0, "pages": 0, "total": 0}, None]) == []


def test_parse_response_raises_on_api_error():
    error = [{"message": [{"id": "120", "key": "Invalid value", "value": "The provided parameter value is not valid"}]}]
    with pytest.raises(RuntimeError, match="Invalid value"):
        parse_response(error)


def test_csv_round_trip_keeps_nulls(tmp_path, grid):
    path = tmp_path / "indicadores.csv"
    write_indicators(grid, path)
    text = path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == ",".join(COLUMNS)
    back = read_indicators(path)
    assert back["valor"].isna().sum() == grid["valor"].isna().sum()
    assert (back["valor"] == 0).sum() == 1
