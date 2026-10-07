"""Data and quality screen (C-16). Owner: Cristian."""

import json

from app.datos import (
    cache_count, files_table, load_catalog, load_manifest, news_by_origin, sources_table, verify_messages,
)


def test_real_manifest_and_catalog_render():
    manifest = load_manifest()
    table = files_table(manifest)
    assert len(table) == len(manifest["archivos"]) and table["SHA-256"].str.len().eq(12).all()
    assert sum(news_by_origin(manifest).values()) == next(
        a["filas"] for a in manifest["archivos"] if a["ruta"].endswith("noticias.parquet"))
    sources = sources_table(load_catalog())
    assert not sources.empty and sources["Licencia / condiciones"].notna().all()


def test_missing_values_stay_visible(tmp_path):
    manifest = {"archivos": [{"ruta": "data/x.json", "sha256": None, "bytes": None, "filas": None}]}
    row = files_table(manifest).iloc[0]
    assert (row["Filas"], row["Tamaño"], row["SHA-256"], row["Licencia"]) == ("—", "—", "—", "—")
    assert files_table(None).empty and news_by_origin(None) == {}
    assert load_manifest(tmp_path / "nope.json") is None and load_catalog(tmp_path / "nope.csv") == []


def test_verify_messages_in_spanish_and_cache_count(tmp_path):
    msgs = verify_messages(["data/a.csv: missing", "data/b.parquet: SHA-256 differs from the manifest"])
    assert msgs == ["`data/a.csv`: falta el archivo",
                    "`data/b.parquet`: el SHA-256 no coincide con el manifest (el archivo cambió)"]
    assert verify_messages([]) == []
    (tmp_path / "k1.json").write_text(json.dumps({}), encoding="utf-8")
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    assert cache_count(tmp_path) == 1 and cache_count(tmp_path / "nope") == 0
