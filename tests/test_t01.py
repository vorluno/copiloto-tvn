"""T01 · Invalid dates and nulls. Owner: B (B-05).

Prepared input: Synthetic CSV with 3 broken dates and 2 nulls.
Expected result: Errors are split out to the quality report, nulls are kept as nulls, the load continues.
Source: test matrix in docs/c-producto-notion-qa.md (section 9 of the challenge).
"""

import pandas as pd

from src.validate import build_report, read_news_csv, validate_news, write_report

HEADER = "id_noticia,titulo,descripcion,url,medio,dominio,idioma,fecha_publicacion,fecha_deteccion,fecha_extraccion,origen,alcance_texto,sintetico"
ROWS = [
    # valid, with outlet date
    "N-0000000001,Titular uno,Descripción uno,https://www.tvn-2.com/a,TVN,tvn-2.com,es,2026-10-05T14:00:00Z,,2026-10-06T12:00:00Z,tvn_rss,descripcion_rss,true",
    # null 1: GDELT gives no outlet date
    "N-0000000002,Titular dos,,https://ejemplo.com/b,Ejemplo,ejemplo.com,es,,2026-10-05T15:00:00Z,2026-10-06T12:00:00Z,gdelt,titular/metadatos,true",
    # null 2: same, another outlet
    "N-0000000003,Titular tres,,https://otro.com/c,Otro,otro.com,es,,2026-10-05T16:00:00Z,2026-10-06T12:00:00Z,gdelt,titular/metadatos,true",
    # broken date 1: month 13
    "N-0000000004,Titular cuatro,,https://otro.com/d,Otro,otro.com,es,2026-13-45T10:00:00Z,2026-10-05T16:00:00Z,2026-10-06T12:00:00Z,gdelt,titular/metadatos,true",
    # broken date 2: free text
    "N-0000000005,Titular cinco,,https://otro.com/e,Otro,otro.com,es,ayer,2026-10-05T16:00:00Z,2026-10-06T12:00:00Z,gdelt,titular/metadatos,true",
    # broken date 3: day-first, not ISO 8601
    "N-0000000006,Titular seis,Descripción seis,https://www.tvn-2.com/f,TVN,tvn-2.com,es,06/10/2026 25:99,,2026-10-06T12:00:00Z,tvn_rss,descripcion_rss,true",
]


def test_t01(tmp_path):
    """Errors are split out to the quality report, nulls are kept as nulls, the load continues."""
    path = tmp_path / "t01_sintetico.csv"
    path.write_text("\n".join([HEADER, *ROWS]) + "\n", encoding="utf-8")

    result = validate_news(read_news_csv(path))  # the load continues: no exception

    # 3 broken dates split out
    assert sorted(result.rejected["id_noticia"]) == ["N-0000000004", "N-0000000005", "N-0000000006"]
    assert (result.issues["problema"] == "fecha inválida").sum() == 3
    assert set(result.issues["campo"]) == {"fecha_publicacion"}

    # 2 nulls kept as nulls, never filled with fecha_deteccion or 0
    valid = result.valid.set_index("id_noticia")
    assert len(valid) == 3
    assert valid["fecha_publicacion"].isna().sum() == 2
    assert pd.isna(valid.loc["N-0000000002", "fecha_publicacion"])
    assert valid.loc["N-0000000002", "fecha_deteccion"] == pd.Timestamp("2026-10-05T15:00:00Z")
    assert str(valid["fecha_publicacion"].dt.tz) == "UTC"

    # the quality report lists the 3 errors
    report = tmp_path / "calidad.md"
    write_report(build_report(result, None, None, "2026-10-06T21:00:00Z"), report)
    text = report.read_text(encoding="utf-8")
    for bad in ("2026-13-45T10:00:00Z", "ayer", "06/10/2026 25:99"):
        assert bad in text
    assert "Filas válidas: 3" in text
    assert "Filas separadas: 3" in text
