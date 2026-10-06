"""Human review (C-15). Owner: Cristian."""

from pathlib import Path

from app.bandeja import read_cards
from app.revision import card_markdown, case_history, panama_time
from src.fichas import append_review, apply_reviews, latest_reviews, read_reviews

STUB_DIR = Path(__file__).resolve().parents[1] / "data" / "stub"


def test_review_log_round_trip_is_append_only(tmp_path):
    log = tmp_path / "revisiones.jsonl"
    append_review("F-STUB-01", "en revisión", "Cristian", "mirar la fuente", path=log, now="2026-10-07T14:00:00Z")
    append_review("F-STUB-01", "aprobado como borrador", "José", path=log, now="2026-10-07T15:30:00Z")
    records, skipped = read_reviews(log)
    assert len(records) == 2 and skipped == 0  # both decisions kept, nothing rewritten
    history = case_history(records, "F-STUB-01")
    assert [r["estado_revision"] for r in history] == ["aprobado como borrador", "en revisión"]  # newest first
    cards = apply_reviews(read_cards(STUB_DIR / "fichas_stub.jsonl"), latest_reviews(log))
    reviewed = next(c for c in cards if c["id_caso"] == "F-STUB-01")
    assert reviewed["estado_revision"] == "aprobado como borrador" and reviewed["revisor"] == "José"


def test_panama_time_and_missing_dates():
    assert panama_time("2026-10-07T15:30:00Z") == "2026-10-07 10:30 (Panamá)"
    assert panama_time(None) == "— (sin dato)"


def test_markdown_for_notion_has_the_case_fields():
    cards = {c["id_caso"]: c for c in read_cards(STUB_DIR / "fichas_stub.jsonl")}
    md = card_markdown({**cards["F-STUB-01"], "revisor": "José", "fecha_revision": "2026-10-07T15:30:00Z"},
                       action="Verificar antes de aprobar.")
    for expected in ["## F-STUB-01", "Datos sintéticos", "**Persona revisora:** José", "2026-10-07 10:30 (Panamá)",
                     "**Estado de evidencia:** parcial", "**Puntaje P:** 77.0 (alto)", "R 1.00 · I 0.80",
                     "`N-1456290885`", "`N-1456290885 · titulo` · “límite de calado", "### Brief",
                     "**Acción recomendada:** Verificar antes de aprobar."]:
        assert expected in md, expected


def test_markdown_uses_inbox_score_and_keeps_nulls():
    card = {"id_caso": "F-X", "titulo": "t", "puntaje": None, "componentes": None, "abstencion": True,
            "motivo_abstencion": "sin evidencia oficial"}
    md = card_markdown(card)
    assert "**Puntaje P:** — (sin puntaje)" in md and "### Abstención" in md and "sin revisar" in md
    md = card_markdown(card, score={"P": 73.8, "rango": "alto", "version_reglas": "scoring_v1",
                                    "R": 1.0, "I": 0.48, "U": 0.7, "N": None, "E": 0.4})
    assert "73.8 (alto)" in md and "N —" in md  # a missing component is shown as missing, never 0
