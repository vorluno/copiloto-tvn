"""Validez de sustento: the tally of the human review (tools/sustento.py)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sustento", ROOT / "tools" / "sustento.py")
sustento = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sustento)


def row(q, claim, valida, revisor="Cristian"):
    return {"id_consulta": q, "afirmacion": claim, "valida": valida, "revisor": revisor}


def test_a_claim_is_supported_if_one_citation_backs_it_and_unmarked_ones_do_not_count():
    rows = [row("BQ-1", "a", "sí"), row("BQ-1", "a", "no"),  # one citation backs it: supported
            row("BQ-2", "b", "No"),                           # every marked citation says no
            row("BQ-3", "c", "", revisor="")]                 # not reviewed
    result = sustento.tally(rows)
    assert (result["claims"], result["reviewed"], result["supported"]) == (3, 2, 1)
    assert result["unsupported"] == [("BQ-2", "b")] and result["reviewers"] == ["Cristian"]
    assert "no cumple todavía" in sustento.report(result)  # 50 % and fewer than 30 claims


def test_goal_needs_ninety_percent_over_thirty_claims():
    rows = [row(f"BQ-{i}", "x", "si") for i in range(29)] + [row("BQ-99", "y", "no")]
    text = sustento.report(sustento.tally(rows))
    assert "29/30 (97%)" in text and "cumple" in text and "no cumple" not in text


def test_empty_review_says_so():
    assert "sin revisar todavía" in sustento.report(sustento.tally([row("BQ-1", "a", "", "")]))


def test_pre_review_is_shown_apart_and_only_counts_once_a_person_confirms_it():
    rows = [dict(row("BQ-1", "a", "", ""), prevalidacion_ia="sí"), dict(row("BQ-2", "b", "", ""), prevalidacion_ia="no")]
    before = sustento.report(sustento.tally(rows))
    assert "sin revisar todavía" in before and "Pre-revisión automática" in before and "1/2" in before
    assert sustento.confirm(rows, "José") == 2
    after = sustento.tally(rows)
    assert (after["reviewed"], after["supported"], after["reviewers"]) == (2, 1, ["José"])
    assert after["confirmed"] and "adoptó como suya" in sustento.report(after)
    assert sustento.confirm(rows, "Otra") == 0  # never overwrites a human mark
