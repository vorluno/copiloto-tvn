"""Validation and quality report (B-05). Owner: B."""

from pathlib import Path

import pandas as pd
import pytest

from src.validate import build_report, validate_news

STUB_PATH = Path(__file__).resolve().parents[1] / "data" / "stub" / "noticias_stub.parquet"
NOW = "2026-10-06T21:00:00Z"


def row(**overrides) -> dict:
    base = {
        "id_noticia": "N-0000000001",
        "titulo": "Titular",
        "descripcion": None,
        "url": "https://ejemplo.com/a",
        "medio": "Ejemplo",
        "dominio": "ejemplo.com",
        "idioma": "es",
        "fecha_publicacion": None,
        "fecha_deteccion": "2026-10-05T15:00:00Z",
        "fecha_extraccion": "2026-10-06T12:00:00Z",
        "origen": "gdelt",
        "alcance_texto": "titular/metadatos",
    }
    return {**base, **overrides}


def problems(**overrides) -> set[tuple[str, str]]:
    result = validate_news(pd.DataFrame([row(**overrides)]))
    return set(zip(result.issues["campo"], result.issues["problema"]))


def test_contract_stub_is_fully_valid():
    stub = pd.read_parquet(STUB_PATH)
    result = validate_news(stub)
    assert len(result.valid) == len(stub)
    assert result.rejected.empty
    assert result.issues.empty


def test_a_clean_row_passes():
    assert problems() == set()


@pytest.mark.parametrize("url", ["ejemplo.com/a", "ftp://ejemplo.com/a", "https://", "http//ejemplo.com", "javascript:alert(1)"])
def test_broken_url_is_split_out(url):
    assert ("url", "URL rota") in problems(url=url)


@pytest.mark.parametrize("field", ["id_noticia", "titulo", "url", "medio", "dominio", "origen", "alcance_texto", "fecha_extraccion"])
def test_empty_required_field_is_split_out(field):
    assert (field, "campo obligatorio vacío") in problems(**{field: "  "})


def test_nullable_fields_are_not_errors():
    assert problems(descripcion=None, fecha_publicacion=None, idioma=None) == set()


def test_invalid_id_is_split_out():
    assert ("id_noticia", "ID inválido") in problems(id_noticia="N-XYZ")


def test_duplicate_id_keeps_the_first():
    df = pd.DataFrame([row(), row(titulo="Otro")])
    result = validate_news(df)
    assert len(result.valid) == 1
    assert result.valid.iloc[0]["titulo"] == "Titular"
    assert list(result.issues["problema"]) == ["ID duplicado"]


def test_value_outside_the_contract_list():
    assert ("origen", "valor fuera de lista") in problems(origen="twitter")
    assert ("alcance_texto", "valor fuera de lista") in problems(alcance_texto="texto completo")


def test_tvn_web_is_an_allowed_source():
    assert problems(origen="tvn_web", alcance_texto="descripcion_web", fecha_deteccion=None,
                    fecha_publicacion="2025-10-31T23:55:16Z") == set()


def test_tvn_web_never_has_a_detection_date():
    found = problems(origen="tvn_web", alcance_texto="descripcion_web", fecha_deteccion="2026-10-05T15:00:00Z")
    assert ("fecha_deteccion", "fecha_deteccion en tvn_web") in found


def test_tvn_keeps_gdelt_seendate_only_for_the_same_url():
    # ADR-032: same id_noticia = same normalized URL; the date must be GDELT's.
    tvn = row(origen="tvn_web", alcance_texto="descripcion_web", fecha_deteccion="2026-10-05T15:00:00Z")
    seen = pd.Series({"N-0000000001": pd.Timestamp("2026-10-05T15:00:00Z")})
    assert validate_news(pd.DataFrame([tvn]), gdelt_seen=seen).issues.empty
    other_date = pd.Series({"N-0000000001": pd.Timestamp("2026-10-01T00:00:00Z")})
    assert len(validate_news(pd.DataFrame([tvn]), gdelt_seen=other_date).rejected) == 1
    other_url = pd.Series({"N-0000000002": pd.Timestamp("2026-10-05T15:00:00Z")})
    assert len(validate_news(pd.DataFrame([tvn]), gdelt_seen=other_url).rejected) == 1


def test_missing_title_in_a_text_column_is_split_out():
    # 7 oct: on a pandas string column with real titles, a NaN title passed validation.
    df = pd.DataFrame([row(), row(id_noticia="N-0000000002", url="https://ejemplo.com/b", titulo=float("nan"))])
    result = validate_news(df)
    assert list(result.valid["id_noticia"]) == ["N-0000000001"]
    assert ("titulo", "campo obligatorio vacío") in set(zip(result.issues["campo"], result.issues["problema"]))


def test_rss_never_has_a_detection_date():
    found = problems(origen="tvn_rss", alcance_texto="descripcion_rss", fecha_deteccion="2026-10-05T15:00:00Z")
    assert ("fecha_deteccion", "fecha_deteccion en tvn_rss") in found


def test_dates_are_converted_to_utc():
    result = validate_news(pd.DataFrame([row(fecha_publicacion="2026-10-05T09:00:00-05:00")]))
    assert result.valid.iloc[0]["fecha_publicacion"] == pd.Timestamp("2026-10-05T14:00:00Z")
    assert str(result.valid["fecha_publicacion"].dt.tz) == "UTC"


def test_one_row_with_several_problems_is_split_out_once():
    result = validate_news(pd.DataFrame([row(url="nada", titulo="", fecha_deteccion="mañana")]))
    assert len(result.rejected) == 1
    assert len(result.issues) == 3


def test_report_summarizes_every_source():
    news = validate_news(pd.DataFrame([row(), row(id_noticia="N-0000000002", url="mala")]))
    indicadores = pd.DataFrame({"pais_iso3": ["PAN", "PAN"], "valor": [1.5, None]})
    eventos = pd.DataFrame({"id": ["us1"], "place": [None]})
    text = build_report(news, indicadores, eventos, NOW)
    assert NOW in text
    assert "Filas válidas: 1" in text and "Filas separadas: 1" in text
    assert "| N-0000000002 | url | URL rota | mala |" in text
    assert "indicadores.csv" in text and "eventos.geojson" in text
    assert "| valor | 1 |" in text  # null count per column
    assert "| place | 1 |" in text


def test_report_says_when_a_source_is_missing():
    text = build_report(None, None, None, NOW)
    assert text.count("no existe todavía") == 3
