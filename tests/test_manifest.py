"""Data manifest (B-10). Owner: B.

Uses temporary files, so it does not depend on the real data or rewrite data/manifest.json.
"""

import hashlib
import json

from src import manifest


def test_sha256_matches_hashlib(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"copiloto" * 1000)
    assert manifest.sha256(f) == hashlib.sha256(b"copiloto" * 1000).hexdigest()


def test_verify_flags_a_changed_and_a_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "ROOT", tmp_path)
    good, changed = tmp_path / "good.csv", tmp_path / "changed.csv"
    good.write_text("a\n1\n", encoding="utf-8")
    changed.write_text("a\n1\n", encoding="utf-8")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"archivos": [
        {"ruta": "good.csv", "sha256": manifest.sha256(good)},
        {"ruta": "changed.csv", "sha256": manifest.sha256(changed)},
        {"ruta": "gone.csv", "sha256": "0" * 64},
    ]}), encoding="utf-8")
    changed.write_text("a\n2\n", encoding="utf-8")
    assert manifest.verify(path) == ["changed.csv: SHA-256 differs from the manifest", "gone.csv: missing"]


def test_quality_counts_reads_the_report_and_leaves_missing_numbers_null():
    text = ("Generado: 2026-10-06T22:57:44Z (UTC)\n- Filas leídas: 2462\n- Filas válidas: 2462\n"
            "- Repetidas entre fuentes (se conserva TVN): 3\n- Filas separadas: 0\n")
    assert manifest.quality_counts(text) == {"filas_leidas": 2462, "repetidas_entre_fuentes": 3,
                                             "filas_separadas": 0, "generado": "2026-10-06T22:57:44Z"}
    assert manifest.quality_counts("")["filas_separadas"] is None
