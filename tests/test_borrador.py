"""Draft view (C-14). Owner: Cristian."""

from pathlib import Path

from app.bandeja import read_cards
from app.borrador import WORD_LIMITS, citation_label, claims_by_type, draft_rows, query_cards, word_count
from src.generate import guard

STUB_DIR = Path(__file__).resolve().parents[1] / "data" / "stub"


def test_limits_and_counting_match_the_guard():
    assert WORD_LIMITS == guard.WORD_LIMITS
    for text in ["Basado únicamente en titular/metadatos.", "co-autor d’Ávila 5,1 M≥3", ""]:
        assert word_count(text) == guard.word_count(text)


def test_draft_rows_keep_missing_drafts_as_none():
    card = {"borrador": {"brief": "uno dos tres", "guion": None, "copy": " ".join(["x"] * 81)}}
    rows = {r["tarea"]: r for r in draft_rows(card)}
    assert rows["brief"]["palabras"] == 3 and rows["brief"]["dentro"]
    assert rows["guion"]["texto"] is None and rows["guion"]["dentro"] is None  # not generated ≠ 0 words
    assert rows["copy"]["dentro"] is False
    assert [r["texto"] for r in draft_rows(None)] == [None, None, None]


def test_claims_grouped_facts_first_hypotheses_last():
    card = {"afirmaciones": [{"texto": "h", "tipo": "hipotesis"}, {"texto": "f", "tipo": "hecho"},
                             {"texto": "d", "tipo": "declaracion"}]}
    assert [kind for kind, _ in claims_by_type(card)] == ["hecho", "declaracion", "hipotesis"]


def test_citation_label_and_query_cards():
    assert citation_label({"id_fuente": "N-1", "campo": "titulo", "pasaje": "x"}) == "`N-1 · titulo` · “x”"
    assert citation_label(None) == "— (sin cita)"
    queries = query_cards(read_cards(STUB_DIR / "fichas_stub.jsonl"))
    assert [q["id_caso"] for q in queries] == ["F-STUB-03"] and queries[0]["abstencion"]
