"""Page 5 "Casos y evidencias" built from the contract files (J-14, ADR-047)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("casos_md", ROOT / "tools" / "casos_md.py")
casos_md = importlib.util.module_from_spec(spec)
spec.loader.exec_module(casos_md)


def cards():
    return [
        {"id_caso": "F-K-1", "cluster_id": "K-1", "titulo": "Título del modelo", "estado_evidencia": "parcial",
         "puntaje": {"P": 80.0, "rango": "alto", "version_reglas": "scoring_v1"}},
        {"id_caso": "F-K-2", "cluster_id": "K-2", "titulo": None, "abstencion": True,
         "motivo_abstencion": "Una sola fuente.", "estado_evidencia": "insuficiente"},
    ]


def test_latest_review_shows_and_untitled_case_uses_the_source_headline():
    reviews = {"F-K-1": {"id_caso": "F-K-1", "estado_revision": "aprobado como borrador", "revisor": "Cristian",
                         "fecha_revision": "2026-10-08T15:00:00Z", "nota": ""}}
    text = casos_md.build(cards(), reviews, headlines={"K-1": "otro titular", "K-2": "Titular real de la fuente"})
    assert "| `F-K-1` | Título del modelo | 80.0 | parcial | aprobado como borrador | Cristian |" in text
    assert "titular de la fuente: «Titular real de la fuente»" in text
    assert "otro titular" not in text  # a model title is never replaced
    assert "1 con borrador · 1 abstenidos" in text and "1 con persona revisora" in text


def test_without_reviews_every_case_says_it_is_unreviewed():
    text = casos_md.build(cards(), {})
    assert text.count("— (sin revisar)") >= 2 and "0 con persona revisora" in text
