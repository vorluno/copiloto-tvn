"""Challenge deliverables noticias.csv + fuentes.json (B-13). Owner: B.

Synthetic rows only; writes to a temporary folder.
"""

import json

import pandas as pd

from src.export import REQUIRED_COLUMNS, sources, write_csv, write_sources
from src.ingest.common import NEWS_COLUMNS, finalize


def news() -> pd.DataFrame:
    rows = [
        {"id_noticia": "N-0000000001", "titulo": "Canal, récord", "descripcion": "Desc", "url": "https://www.tvn-2.com/a",
         "medio": "TVN", "dominio": "tvn-2.com", "idioma": "es", "fecha_publicacion": "2026-09-01T10:00:00Z",
         "fecha_deteccion": None, "fecha_extraccion": "2026-10-06T21:00:00Z", "origen": "tvn_web",
         "alcance_texto": "descripcion_web", "procedencia_id": "P-tvn-2-com", "tema": "logística/Canal",
         "tema_confianza": 0.61, "cluster_id": "K-0000000001", "sintetico": True},
        {"id_noticia": "N-0000000002", "titulo": "Otro", "descripcion": None, "url": "https://b.com/x",
         "medio": "b.com", "dominio": "b.com", "idioma": "en", "fecha_publicacion": None,
         "fecha_deteccion": "2026-09-02T08:30:00Z", "fecha_extraccion": "2026-10-06T22:00:00Z", "origen": "gdelt",
         "alcance_texto": "titular/metadatos", "procedencia_id": "P-b-com", "tema": "otro",
         "tema_confianza": 0.2, "cluster_id": "K-0000000002", "sintetico": True},
    ]
    return finalize(pd.DataFrame(rows))


def test_csv_has_every_contract_column_utc_dates_and_empty_nulls(tmp_path):
    path = tmp_path / "noticias.csv"
    write_csv(news(), path)
    raw = path.read_bytes()
    assert b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf")  # LF, no BOM
    back = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert list(back.columns) == NEWS_COLUMNS
    assert set(REQUIRED_COLUMNS) <= set(back.columns)
    assert back.loc[0, "fecha_publicacion"] == "2026-09-01T10:00:00Z"
    assert back.loc[0, "fecha_deteccion"] == ""  # null stays empty, never filled
    assert back.loc[1, "fecha_publicacion"] == ""
    assert back.loc[1, "descripcion"] == ""
    assert back.loc[0, "titulo"] == "Canal, récord"


def test_sources_list_each_outlet_with_conditions(tmp_path):
    path = tmp_path / "fuentes.json"
    write_sources(news(), path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == sources(news())
    assert {c["origen"] for c in data["consultas"]} == {"tvn_rss", "tvn_web", "gdelt"}
    assert data["n_noticias"] == 2
    by_domain = {m["dominio"]: m for m in data["medios"]}
    assert by_domain["tvn-2.com"]["origen"] == "tvn_web" and by_domain["tvn-2.com"]["n_noticias"] == 1
    assert by_domain["b.com"]["fecha_primera_UTC"] == "2026-09-02T08:30:00Z"
    assert all(m["condiciones_uso"] for m in data["medios"])
