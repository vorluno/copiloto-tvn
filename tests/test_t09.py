"""T09 · Editorial brief. Owner: José (J-08).

Prepared input: Economic topic with official data.
Expected result: Useful format, citations, facts separated from inferences.
Source: test matrix in docs/c-producto-notion-qa.md (section 9 of the challenge).

Two parts:
- test_t09: the whole path (score -> evidence with the World Bank cell from contexto ->
  prompt -> guard -> case card) on an economy cluster, with a scripted model standing in
  for Gemini. It proves the format the editor gets: title, brief within 250 words, three
  research questions, every claim typed and cited, the World Bank figure with country,
  year and unit. An uncited cause in the first answer is never shown: the guard rejects
  that draft and the retry with its feedback is what the editor gets.
- test_t09_real_brief: the same checks on outputs/fichas.jsonl once `make demo-cache` ran
  with Gemini. Skipped until then; whether the brief is *useful* is still judged by a
  person (Cristian's review sheet, C-08).
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.fichas import build_fichas
from src.generate.drafts import official_index
from src.generate.guard import WORD_LIMITS, word_count

ROOT = Path(__file__).resolve().parents[1]
STUB = ROOT / "data" / "stub" / "noticias_stub.parquet"
FICHAS = ROOT / "outputs" / "fichas.jsonl"
NOW = pd.Timestamp("2026-10-06T18:00:00Z")
CLUSTER = "C-STUB-08"  # economía: banana exports (sintético)
NEWS_ID = "N-22d88654d9"
TITLE = "Exportaciones de banano panameño crecen frente al año anterior"
# Synthetic World Bank cell and its contexto row (sintético): only the shape matters.
CELL = {"pais_iso3": "PAN", "indicador_id": "NE.EXP.GNFS.ZS", "anio": 2024, "valor": 45.2,
        "unidad": "% del PIB", "fuente_url": "https://example.invalid", "licencia": "CC BY 4.0"}
WB_ID = "WB-PAN-NE.EXP.GNFS.ZS-2024"
CONTEXTO = pd.DataFrame([{"cluster_id": CLUSTER, "id_evidencia": WB_ID, "tipo": "indicador",
                          "regla": "tema economía + Panamá + exportaciones (sintético)", "nota": "Dato anual de 2024."}])
CLAIM_TYPES = {"hecho", "declaracion", "inferencia", "hipotesis"}


class EditorModel:
    """Scripted stand-in for Gemini: the brief a careful model should write for this case."""

    def complete(self, messages, model, temperature):
        task = next(line.split()[1] for line in messages[1]["content"].splitlines() if line.startswith("Tarea:"))
        size = {"brief": 140, "guion": 120, "copy": 50}[task]
        claims = [
            {"texto": f"TVN reporta: {TITLE}.", "tipo": "declaracion",
             "citas": [{"id_fuente": NEWS_ID, "campo": "titulo", "pasaje": TITLE}]},
            {"texto": "Según el Banco Mundial, las exportaciones de bienes y servicios de Panamá equivalieron "
                      "al 45.2 % del PIB en 2024.", "tipo": "hecho",
             "citas": [{"id_fuente": WB_ID, "campo": "valor", "pasaje": "45.2"}]},
            {"texto": "Si el crecimiento se confirma, el banano pesaría en las exportaciones del país.",
             "tipo": "inferencia",
             "citas": [{"id_fuente": NEWS_ID, "campo": "titulo", "pasaje": "Exportaciones de banano panameño crecen"}]},
        ]
        if "rechazada por el validador" not in messages[1]["content"]:  # first try: an uncited cause
            claims.append({"texto": "El aumento se debe a mejores precios internacionales.", "tipo": "inferencia",
                           "citas": []})
        intro = "Borrador para revisión: TVN reporta que las exportaciones de banano crecen."
        return json.dumps({
            "abstencion": False,
            "titulo": "Exportaciones de banano: qué se sabe y qué falta verificar",
            "enfoque_interes_publico": "Empleo y divisas de la producción bananera.",
            "afirmaciones": claims,
            "preguntas_investigacion": ["¿Qué volumen exportado reporta la fuente oficial?",
                                        "¿Con qué período se compara el crecimiento?",
                                        "¿Qué dicen los productores y la autoridad agropecuaria?"] if task == "brief" else [],
            "verificaciones_pendientes": ["Cifra de exportación de banano de una fuente oficial."],
            "borrador": intro + " " + " ".join(["texto"] * (size - word_count(intro))),
        }, ensure_ascii=False), {"prompt_tokens": 1, "completion_tokens": 1}


def check_brief_card(card: dict) -> None:
    """The format T09 asks for, on one case card."""
    assert card["titulo"]
    brief = card["borrador"]["brief"]
    assert brief and 1 <= word_count(brief) <= WORD_LIMITS["brief"][1]
    assert len(card["preguntas_investigacion"]) == 3
    assert card["afirmaciones"], "a brief with no cited claim is not a brief"
    for claim in card["afirmaciones"]:
        assert claim["tipo"] in CLAIM_TYPES  # facts, statements and inferences are labeled apart
        assert claim["citas"] and all(c["id_fuente"] in card["ids_fuente"] and c["campo"] for c in claim["citas"])


PLACEHOLDER_TITLES = {"título propuesto", "titulo propuesto", "título", "sin título"}
MIN_DISTINCT_WORDS = 0.35  # share of distinct words; filler like "palabra palabra palabra…" is near 0


def check_not_filler(card: dict) -> None:
    """A real brief, not test-model filler (C-08 found such cards in main once: ed04499, #54)."""
    assert card["titulo"].strip().lower() not in PLACEHOLDER_TITLES, f"{card['id_caso']}: placeholder title"
    words = [w.lower() for w in card["borrador"]["brief"].split()]
    assert len(set(words)) / len(words) >= MIN_DISTINCT_WORDS, f"{card['id_caso']}: repetitive brief (filler)"


def test_t09_rejects_test_model_filler():
    # The exact shape of the cards that once reached main: placeholder title, "palabra" x 100.
    filler = {"id_caso": "F-K-relleno", "titulo": "Título propuesto",
              "borrador": {"brief": "Basado únicamente en titular/metadatos. " + "palabra " * 94}}
    with pytest.raises(AssertionError, match="placeholder title"):
        check_not_filler(filler)
    with pytest.raises(AssertionError, match="repetitive brief"):
        check_not_filler({**filler, "titulo": "Exportaciones de banano"})


def test_t09(tmp_path):
    news = pd.read_parquet(STUB)
    official = official_index(pd.DataFrame([CELL]))
    cards = build_fichas(news, contexto=CONTEXTO, official=official, top_n=None, now=NOW,
                         client=EditorModel(), offline=False, cache_dir=tmp_path)
    card = next(c for c in cards if c["cluster_id"] == CLUSTER)

    assert card["tema"] == "economía" and WB_ID in card["ids_fuente"]
    assert card["estado_evidencia"] == "parcial"  # one outlet + official data: never "ready" on its own
    assert not card["abstencion"]
    check_brief_card(card)

    by_type = {}
    for claim in card["afirmaciones"]:
        by_type.setdefault(claim["tipo"], []).append(claim["texto"])
    assert by_type["hecho"] == ["Según el Banco Mundial, las exportaciones de bienes y servicios de Panamá "
                                "equivalieron al 45.2 % del PIB en 2024."]  # country, year and unit (T04)
    assert by_type["inferencia"] == ["Si el crecimiento se confirma, el banano pesaría en las exportaciones del país."]
    assert not any("precios internacionales" in t for texts in by_type.values() for t in texts)  # uncited cause: never shown
    assert card["generacion"]["brief"]["intentos"] == 2  # rejected once by the guard, fixed on the retry


def test_t09_real_brief():
    """Gemini's briefs in outputs/fichas.jsonl, after `make demo-cache` (Levi, with OpenRouter)."""
    cards = [json.loads(line) for line in FICHAS.read_text(encoding="utf-8").splitlines() if line.strip()] \
        if FICHAS.exists() else []
    real = [c for c in cards if not c.get("sintetico") and c.get("tema") == "economía" and not c["abstencion"]
            and c["generacion"].get("brief", {}).get("origen") in ("llm", "cache")]
    if not real:
        pytest.skip("T09 real: pending `make demo-cache` with Gemini (no economy brief in outputs/fichas.jsonl yet)")
    for card in real:
        check_brief_card(card)
        check_not_filler(card)
