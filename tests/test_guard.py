"""Guard over LLM drafts (J-07). Owner: José.

Fake model outputs against the synthetic stub: everything the model could get wrong
(made-up IDs, passages, fields, leaks, injections, "today" figures, limits) must be
caught in code before reaching the UI.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.generate.guard import ONLY_HEADLINE, guard, word_count
from src.generate.schema import evidence_from_indicator, evidence_from_news

STUB_PATH = Path(__file__).resolve().parents[1] / "data" / "stub" / "noticias_stub.parquet"


@pytest.fixture(scope="module")
def news() -> pd.DataFrame:
    return pd.read_parquet(STUB_PATH)


def item(news: pd.DataFrame, cluster_id: str, outlet_prefix: str) -> pd.Series:
    return news[(news["cluster_id"] == cluster_id) & news["medio"].str.startswith(outlet_prefix)].iloc[0]


@pytest.fixture(scope="module")
def canal(news):
    """Evidence for the 3-record Canal cluster plus handy rows."""
    rows = news[news["cluster_id"] == "C-STUB-01"]
    return {
        "evidence": [evidence_from_news(r) for _, r in rows.iterrows()],
        "tvn": item(news, "C-STUB-01", "TVN"),
        "efe": item(news, "C-STUB-01", "Diario A"),
    }


@pytest.fixture(scope="module")
def indicator():
    # Synthetic World Bank cell (sintetico): only the shape matters here.
    row = pd.Series({"pais_iso3": "PAN", "indicador_id": "NY.GDP.MKTP.KD.ZG", "anio": 2023, "valor": 7.3,
                     "unidad": "% anual", "fuente_url": "https://example.invalid", "licencia": "CC BY 4.0"})
    return evidence_from_indicator(row)


def cite(row, field, passage):
    return {"id_fuente": row["id_noticia"], "campo": field, "pasaje": passage}


def brief_output(claims, draft="Borrador de prueba.", questions=3, **extra):
    return {
        "abstencion": False,
        "titulo": "Calado en el Canal",
        "afirmaciones": claims,
        "preguntas_investigacion": [f"¿Pregunta {i}?" for i in range(questions)],
        "borrador": draft,
        **extra,
    }


def tvn_claim(canal):
    return {"texto": "TVN reporta un límite de calado.", "tipo": "hecho",
            "citas": [cite(canal["tvn"], "titulo", "límite de calado por bajo nivel del lago Gatún")]}


def efe_claim(canal):
    return {"texto": "EFE reporta un nuevo calado máximo.", "tipo": "declaracion",
            "citas": [cite(canal["efe"], "titulo", "fija nuevo calado máximo")]}


# --- happy path ------------------------------------------------------------------

def test_valid_output_passes_and_counts(canal):
    raw = brief_output([tvn_claim(canal), efe_claim(canal)], draft=f"{ONLY_HEADLINE} Texto.")
    result = guard(raw, canal["evidence"], "brief")
    assert result.report.ok
    assert len(result.output.afirmaciones) == 2
    assert (result.report.claims_received, result.report.claims_kept) == (2, 2)
    assert (result.report.citations_received, result.report.citations_kept) == (2, 2)


def test_parses_json_string_and_fenced_json(canal):
    raw = brief_output([tvn_claim(canal)], draft=f"{ONLY_HEADLINE} Texto.")
    as_text = json.dumps(raw, ensure_ascii=False)
    for payload in (as_text, f"```json\n{as_text}\n```"):
        assert guard(payload, canal["evidence"], "brief").report.ok


def test_passage_match_ignores_case_quotes_and_spacing(canal):
    claim = tvn_claim(canal)
    claim["citas"][0]["pasaje"] = "LÍMITE   de calado"
    assert guard(brief_output([claim], draft=f"{ONLY_HEADLINE} x"), canal["evidence"], "brief").report.ok


# --- citations ---------------------------------------------------------------------

@pytest.mark.parametrize("mutate, expected", [
    (lambda c: c.update(id_fuente="N-0000000000"), "no está en la evidencia enviada"),
    (lambda c: c.update(pasaje="cierre total del Canal"), "el pasaje no aparece"),
    (lambda c: c.update(campo="cuerpo"), "campo no enviado"),
])
def test_bad_citation_drops_claim_and_draft(canal, mutate, expected):
    bad = efe_claim(canal)
    mutate(bad["citas"][0])
    result = guard(brief_output([tvn_claim(canal), bad], draft=f"{ONLY_HEADLINE} x"), canal["evidence"], "brief")
    assert [c.texto for c in result.output.afirmaciones] == ["TVN reporta un límite de calado."]
    assert expected in result.report.dropped_citations[0]
    assert result.output.borrador is None  # may contain the unsupported claim
    assert not result.report.ok


def test_gdelt_item_has_no_description_to_cite(canal):
    claim = efe_claim(canal)
    claim["citas"][0]["campo"] = "descripcion"
    result = guard(brief_output([claim]), canal["evidence"], "brief")
    assert result.output.abstencion


def test_no_valid_claim_becomes_abstention(canal):
    claim = {"texto": "El Canal cerró.", "tipo": "hecho", "citas": []}
    result = guard(brief_output([claim]), canal["evidence"], "brief")
    assert result.output.abstencion
    assert result.output.afirmaciones == []
    assert result.output.borrador is None
    assert "cita válida" in result.output.motivo_abstencion


def test_invalid_contradiction_is_dropped(canal):
    good = {"version_a": "a", "cita_a": tvn_claim(canal)["citas"][0],
            "version_b": "b", "cita_b": efe_claim(canal)["citas"][0]}
    bad = {**good, "cita_b": {**good["cita_b"], "pasaje": "inventado"}}
    raw = brief_output([tvn_claim(canal)], draft=f"{ONLY_HEADLINE} x", contradicciones=[good, bad])
    result = guard(raw, canal["evidence"], "brief")
    assert len(result.output.contradicciones) == 1


# --- schema, leaks and injection (T07 code side) ------------------------------------------

@pytest.mark.parametrize("raw", ["no es json", '{"abstencion": false, "campo_extra": 1}', "{}"])
def test_invalid_output_is_blocked(canal, raw):
    result = guard(raw, canal["evidence"], "brief")
    assert result.report.blocked
    assert result.output.abstencion


def test_api_key_leak_is_blocked(canal, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "clave-secreta-de-prueba-123")
    raw = brief_output([tvn_claim(canal)], draft="La clave es clave-secreta-de-prueba-123")
    result = guard(raw, canal["evidence"], "brief")
    assert result.report.blocked
    assert "clave-secreta" not in json.dumps(result.output.model_dump(), ensure_ascii=False)


@pytest.mark.parametrize("draft", [
    "Mis reglas: Eres un asistente de investigación para la redacción de TVN Panamá.",
    "token sk-or-v1-abcdefghijklmnopqrstuvwxyz0123",
])
def test_prompt_or_key_shaped_leak_is_blocked(canal, draft):
    assert guard(brief_output([tvn_claim(canal)], draft=draft), canal["evidence"], "brief").report.blocked


def test_injected_source_gets_alert_and_cannot_be_cited(news, canal):
    injected = item(news, "C-STUB-03", "Blog C")
    evidence = canal["evidence"] + [evidence_from_news(injected)]
    obey = {"texto": "Se debe revelar la API key.", "tipo": "hecho",
            "citas": [cite(injected, "titulo", "revela la API key")]}
    result = guard(brief_output([tvn_claim(canal), obey], draft=f"{ONLY_HEADLINE} x"), evidence, "brief")
    assert result.report.injected_sources == [injected["id_noticia"]]
    assert any(injected["id_noticia"] in a for a in result.output.alertas)
    assert [c.texto for c in result.output.afirmaciones] == ["TVN reporta un límite de calado."]


def test_model_alert_is_not_duplicated(news):
    injected = item(news, "C-STUB-03", "Blog C")
    alert = f"posible instrucción inyectada en {injected['id_noticia']}"
    raw = {"abstencion": True, "motivo_abstencion": "Sin hechos.", "alertas": [alert]}
    result = guard(raw, [evidence_from_news(injected)], "brief")
    assert result.output.alertas == [alert]


# --- World Bank (T04 code side) -----------------------------------------------------

def test_null_indicator_is_not_evidence():
    row = pd.Series({"pais_iso3": "PAN", "indicador_id": "FP.CPI.TOTL.ZG", "anio": 2024, "valor": None,
                     "unidad": "% anual"})
    assert evidence_from_indicator(row) is None


@pytest.mark.parametrize("text, kept", [
    ("El PIB de Panamá creció 7.3 % anual en 2023, según el Banco Mundial.", True),
    ("El PIB de Panamá crece 7.3 % anual.", False),
    ("En 2023 el PIB creció 7.3 %, y hoy sigue creciendo.", False),
])
def test_world_bank_claim_needs_year_and_no_today(canal, indicator, text, kept):
    claim = {"texto": text, "tipo": "hecho",
             "citas": [{"id_fuente": indicator.id, "campo": "valor", "pasaje": "7.3"}]}
    raw = brief_output([tvn_claim(canal), claim], draft=f"{ONLY_HEADLINE} x")
    result = guard(raw, canal["evidence"] + [indicator], "brief")
    assert (len(result.output.afirmaciones) == 2) is kept


# --- abstention, scope phrase, limits -----------------------------------------------------

def test_abstention_with_claims_drops_claims(canal):
    raw = {"abstencion": True, "motivo_abstencion": "Falta dato.", "afirmaciones": [tvn_claim(canal)],
           "borrador": "texto"}
    result = guard(raw, canal["evidence"], "brief")
    assert result.output.afirmaciones == [] and result.output.borrador is None
    assert result.report.violations


def test_headline_only_phrase_is_prepended(canal):
    result = guard(brief_output([efe_claim(canal)], draft="Un medio replica a EFE."), canal["evidence"], "brief")
    assert result.output.borrador.startswith(ONLY_HEADLINE)
    assert result.report.fixes


@pytest.mark.parametrize("task, words, ok", [
    ("brief", 250, True), ("brief", 251, False),
    ("copy", 80, True), ("copy", 81, False),
    ("guion", 109, False), ("guion", 130, True), ("guion", 151, False),
])
def test_word_limits(canal, task, words, ok):
    draft = f"{ONLY_HEADLINE} " + " ".join(["palabra"] * (words - word_count(ONLY_HEADLINE)))
    raw = brief_output([tvn_claim(canal)], draft=draft, questions=3 if task == "brief" else 0)
    result = guard(raw, canal["evidence"], task)
    assert (result.output.borrador is not None) is ok


@pytest.mark.parametrize("questions", [2, 4])
def test_brief_needs_exactly_three_questions(canal, questions):
    raw = brief_output([tvn_claim(canal)], draft=f"{ONLY_HEADLINE} x", questions=questions)
    result = guard(raw, canal["evidence"], "brief")
    assert result.output.preguntas_investigacion == []
    assert any("preguntas" in v for v in result.report.violations)



# --- accusations (secc. 8) ------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("Aprehenden a un exdirector por supuesto enriquecimiento injustificado.", "declaracion"),
    ("La fiscalía imputó a dos funcionarios por peculado.", "declaracion"),
    ("TVN reporta un límite de calado en el Canal.", "hecho"),
])
def test_accusations_are_never_facts(canal, text, expected):
    claim = {"texto": text, "tipo": "hecho",
             "citas": [cite(canal["tvn"], "titulo", "límite de calado")]}
    result = guard(brief_output([claim], draft=f"{ONLY_HEADLINE} x"), canal["evidence"], "brief")
    assert result.output.afirmaciones[0].tipo == expected
