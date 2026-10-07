"""Official context (B-14, T04 support). Owner: B.

Synthetic clusters and a tiny indicator grid; no real data.
"""

import pandas as pd

from src.context import COLUMNS, build_context, latest_values


def news(rows: list[tuple[str, str, str, str]]) -> pd.DataFrame:
    """(cluster_id, tema, titulo, fecha UTC)."""
    df = pd.DataFrame([{"id_noticia": f"N-{i:010x}", "cluster_id": c, "tema": t, "titulo": ti, "descripcion": None,
                        "fecha_publicacion": f, "fecha_deteccion": None} for i, (c, t, ti, f) in enumerate(rows)])
    for col in ("fecha_publicacion", "fecha_deteccion"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


INDICATORS = pd.DataFrame([
    {"pais_iso3": "PAN", "indicador_id": "FP.CPI.TOTL.ZG", "anio": 2023, "valor": 1.5},
    {"pais_iso3": "PAN", "indicador_id": "FP.CPI.TOTL.ZG", "anio": 2024, "valor": None},  # null: not citable
    {"pais_iso3": "PAN", "indicador_id": "SL.UEM.TOTL.ZS", "anio": 2024, "valor": 7.0},
    {"pais_iso3": "CRI", "indicador_id": "FP.CPI.TOTL.ZG", "anio": 2024, "valor": 0.8},
])


def test_latest_year_skips_null_values():
    assert latest_values(INDICATORS) == {"FP.CPI.TOTL.ZG": 2023, "SL.UEM.TOTL.ZS": 2024}


def test_linked_only_with_topic_panama_and_the_measured_thing():
    df = news([
        ("K-1", "economía", "Inflación en Panamá sube por alza de precios", "2026-09-01T10:00:00Z"),
        ("K-2", "economía", "Inflación en Argentina supera el 100%", "2026-09-01T10:00:00Z"),       # not Panama
        ("K-3", "economía", "Panamá firma acuerdo con bancos", "2026-09-01T10:00:00Z"),              # nothing measured
        ("K-4", "turismo", "Desempleo en Panamá baja según el INEC", "2026-09-01T10:00:00Z"),        # topic without indicators
        ("K-5", "economía", "Reciclaje impulsa empleo en Panamá", "2026-09-01T10:00:00Z"),           # "empleo" is not the rate
    ])
    out = build_context(df, INDICATORS, None)
    assert list(out.columns) == COLUMNS
    assert out[["cluster_id", "id_evidencia", "tipo"]].values.tolist() == [["K-1", "WB-PAN-FP.CPI.TOTL.ZG-2023", "indicador"]]
    assert "2023" in out.loc[0, "nota"] and "no mide la fecha de la noticia" in out.loc[0, "nota"]


def test_quake_linked_only_within_72h():
    events = {"features": [{"properties": {"id": "us1", "time": "2024-03-01T00:00:00Z", "place": "south of Panama"}}]}
    df = news([
        ("K-1", "eventos naturales", "Sismo sacude Chiriquí", "2024-03-02T10:00:00Z"),
        ("K-2", "eventos naturales", "Sismo sacude Chiriquí", "2026-03-02T10:00:00Z"),   # two years later
        ("K-3", "eventos naturales", "Inundaciones en Darién", "2024-03-01T05:00:00Z"),   # not a quake
    ])
    out = build_context(df, None, events)
    assert out[["cluster_id", "id_evidencia", "tipo"]].values.tolist() == [["K-1", "us1", "sismo"]]


def test_no_relation_means_no_rows():
    out = build_context(news([("K-1", "otro", "Partido de fútbol en Panamá", "2026-09-01T10:00:00Z")]), INDICATORS, {"features": []})
    assert out.empty and list(out.columns) == COLUMNS
