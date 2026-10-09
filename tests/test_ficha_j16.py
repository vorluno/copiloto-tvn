"""Case card for any event (J-16): live drafting, why a format is missing, citation dates,
readable figures, folded sources and the small text fixes. Owner: Cristian; built with José.

The live path cannot run against the real model here: a scripted fake client (the same one
tests/test_drafts.py uses) stands in for it, and NoNetwork proves offline never calls out.
"""

import pandas as pd
import pytest

from app import textos as tx
from app.borrador import (
    can_draft_live, draft_package, group_citations, has_model_key, package_failed, redraft_guion, task_gaps,
)
from app.estilo import busy_css, claim_html, scroll_js
from app.revision import card_markdown
from src.fichas import card_from_package
from src.generate.guard import WORD_LIMITS, word_count
from tests.test_drafts import NOW, NoNetwork, ScriptedModel, STUB_PATH
from src.score import score_clusters


@pytest.fixture(scope="module")
def stub_news() -> pd.DataFrame:
    return pd.read_parquet(STUB_PATH)


@pytest.fixture(scope="module")
def stub_scored(stub_news):
    return score_clusters(stub_news, now=NOW)


# --- 1. a draft for any event ---------------------------------------------------------------------

def test_live_draft_sends_what_make_fichas_sends_one_step_at_a_time(stub_news, stub_scored, tmp_path):
    model, steps = ScriptedModel(stub_news), []
    package = draft_package("C-STUB-01", stub_news, stub_scored, client=model, offline=False, cache_dir=tmp_path,
                            on_step=steps.append)
    assert steps == ["brief", "guion", "copy"]
    assert [t for t, _ in model.calls] == ["brief", "guion", "copy"]
    assert not package_failed(package)
    for task, draft in package.drafts.items():
        low, high = WORD_LIMITS[task]
        assert draft.result.report.ok and low <= word_count(draft.result.output.borrador) <= high
    # Same requests as make fichas: replayed offline from the same cache, never calling out.
    replay = draft_package("C-STUB-01", stub_news, stub_scored, client=NoNetwork(), offline=True, cache_dir=tmp_path)
    assert all(d.result.source == "cache" for d in replay.drafts.values())
    # The card the app shows is the one make fichas writes.
    row = stub_scored.set_index("cluster_id").loc["C-STUB-01"]
    card = card_from_package(package, row)
    assert card["id_caso"] == "F-C-STUB-01" and all(card["borrador"].values())


def test_live_draft_keeps_the_abstention_rule(stub_news, stub_scored, tmp_path):
    model = ScriptedModel(stub_news, abstain=True)
    package = draft_package("C-STUB-01", stub_news, stub_scored, client=model, offline=False, cache_dir=tmp_path)
    assert model.calls == [("brief", False)]
    assert package.drafts["guion"].skipped and package.drafts["copy"].skipped
    assert "evidencia suficiente" in tx.formato_ausente("guion", task_gaps(package)["guion"])


def test_offline_without_saved_draft_fails_softly(stub_news, stub_scored, tmp_path):
    package = draft_package("C-STUB-01", stub_news, stub_scored, client=NoNetwork(), offline=True, cache_dir=tmp_path)
    assert package_failed(package)
    assert "conexión" in tx.SIN_CONEXION_REDACCION and "guardados" in tx.SIN_CONEXION_REDACCION


def test_live_drafting_needs_network_and_key(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    assert can_draft_live(offline=False)
    assert not can_draft_live(offline=True)
    monkeypatch.delenv("LLM_API_KEY")
    assert not has_model_key(env_file=tmp_path / "missing.env")


# --- 2. why a format is missing, and one more try ------------------------------------------------

def test_missing_script_says_why_in_newsroom_words():
    gap = {"source": "cache", "violations": ["guion: 88 palabras, fuera de [110, 150]"], "abstencion": False,
           "motivo": None, "skipped": False}
    text = tx.formato_ausente("guion", gap)
    assert "88 palabras" in text and "entre 110 y 150" in text and "45–60 segundos" in text
    assert "fuera de [" not in text  # the guard's own wording never reaches the screen
    assert tx.palabras_guion(gap) == 88
    assert "no tenemos registrado" in tx.formato_ausente("guion", None)
    assert tx.formato_ausente("copy", {"source": "cache", "violations": ["copy: 95 palabras, fuera de [1, 80]"]}) \
        .startswith("El texto para redes salió con 95 palabras")


def test_redo_asks_for_110_to_150_words_through_feedback(stub_news, stub_scored, tmp_path):
    model = ScriptedModel(stub_news)
    seen = []
    original = model.complete

    def spy(messages, model_name, temperature):
        seen.append(messages)
        return original(messages, model_name, temperature)

    model.complete = spy
    result = redraft_guion("C-STUB-01", stub_news, stub_scored, words=88, client=model, offline=False,
                           cache_dir=tmp_path)
    user = seen[0][1]["content"]
    assert "rechazada por el validador" in user and "entre 110 y 150 palabras" in user
    assert result.report.ok and 110 <= word_count(result.output.borrador) <= 150


# --- 3, 4, 5. citations: dates, figures, grouping and folding --------------------------------------

def test_citation_dates_say_publication_or_detection():
    assert tx.fecha_cita("2026-09-30T03:15:00Z") == "publicada el 29/09/2026"  # Panama time
    assert tx.fecha_cita(None, "2026-09-30T23:15:00Z") == "detectada el 30/09/2026"
    assert tx.fecha_cita(pd.NaT, pd.NaT) is None


def test_long_decimals_are_rounded_only_for_reading():
    assert tx.cifras("El desempleo fue 0.69322555100446 % en 2024") == "El desempleo fue 0.69 % en 2024"
    assert tx.cifras("Creció 3,14159 y 7.3 y 12.345") == "Creció 3,14 y 7.3 y 12.345"
    assert tx.cifras(None) == ""


def test_one_world_bank_datum_is_one_source_with_its_passages_literal():
    citas = [{"id_fuente": "WB-PAN-X-2024", "campo": c, "pasaje": p}
             for c, p in (("valor", "0.69322555100446"), ("unidad", "%"), ("anio", "2024"), ("pais_iso3", "PAN"))]
    citas.append({"id_fuente": "N-1", "campo": "titulo", "pasaje": "Titular"})
    citas.append(dict(citas[0]))  # an exact repeat is dropped
    groups = group_citations(citas)
    assert [g["id_fuente"] for g in groups] == ["WB-PAN-X-2024", "N-1"]
    assert groups[0]["partes"][0] == ("valor", "0.69322555100446") and len(groups[0]["partes"]) == 4
    assert tx.cita_fuente("anio") == "año" and tx.cita_fuente("pais_iso3") == "país"  # no raw field names


def test_sources_fold_after_the_first():
    cites = [{"label": f"Medio {i}", "ident": f"N-{i}", "found": True, "context": "publicada el 30/09/2026"}
             for i in range(3)]
    html = claim_html("Hecho", "Texto", cites, tx.ver_fuentes(len(cites)))
    head, folded = html.split("<details", 1)
    assert "Medio 0" in head and "Medio 1" not in head and "Ver las 3 fuentes" in folded
    assert "<details" not in claim_html("Hecho", "Texto", cites[:1], tx.ver_fuentes(1))


def test_running_and_scroll_snippets_are_scoped():
    assert ".st-key-ficha" in busy_css("ficha", "redaccion") and "redaccion" in busy_css("ficha", "redaccion")
    js = scroll_js(".st-key-ficha")
    assert "scrollIntoView" in js and "innerWidth>640" in js


# --- 7. details -----------------------------------------------------------------------------------

def test_small_texts_agree_and_say_the_data_date():
    assert tx.ver_notas(1) == "Ver la nota que lo reporta"
    assert tx.ver_notas(7) == "Ver las 7 notas que lo reportan"
    title = tx.titulo_mesa(pd.Timestamp("2026-09-30T23:15:00Z"))
    assert title == "Prioridad al 30/09/2026" and "hoy" not in title.lower()


def test_downloaded_card_is_titled_by_its_headline_when_the_ai_gave_none():
    card = {"id_caso": "F-K-1", "titulo": None, "estado_evidencia": "insuficiente", "abstencion": True}
    assert card_markdown(card, headline="Canal de Panamá aumenta tránsitos").startswith(
        "## F-K-1 · Canal de Panamá aumenta tránsitos")
    assert card_markdown(card).startswith("## F-K-1 · —")
