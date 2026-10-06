"""Case cards and review log (J-09). Owner: José.

A generic fake model cites the headline of the first source it receives, so every
cluster gets a cited answer. The injected-instruction cluster checks that the guard's
alert reaches the card.
"""

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from app.bandeja import build_inbox, read_cards
from app.ficha import recommended_action as ui_action
from src.fichas import (
    REVIEW_STATES, recommended_action, append_review, apply_reviews, build_fichas, case_id, export_fichas,
    latest_reviews, read_reviews,
)
from src.generate.guard import ONLY_HEADLINE, word_count
from src.score import score_clusters

STUB_PATH = Path(__file__).resolve().parents[1] / "data" / "stub" / "noticias_stub.parquet"
NOW = pd.Timestamp("2026-10-06T18:00:00Z")
CONTRACT_FIELDS = ["id_caso", "modalidad", "ids_fuente", "afirmaciones", "citas", "puntaje", "componentes",
                   "estado_evidencia", "borrador", "estado_revision"]


class HeadlineModel:
    """Cites the first words of the first <fuente> headline; sizes the draft per task."""

    def __init__(self):
        self.calls = 0

    def complete(self, messages, model, temperature):
        self.calls += 1
        user = messages[1]["content"]
        task = re.search(r"^Tarea: (\w+)", user, re.M).group(1)
        source_id = re.search(r'<fuente id="([^"]+)"', user).group(1)
        headline = re.search(r"^titulo: (.+)$", user, re.M).group(1)
        passage = " ".join(headline.split()[:4])
        size = {"brief": 100, "guion": 120, "copy": 40}[task]
        return json.dumps({
            "abstencion": False, "titulo": "Título propuesto",
            "afirmaciones": [{"texto": f"Un medio reporta: {passage}.", "tipo": "declaracion",
                              "citas": [{"id_fuente": source_id, "campo": "titulo", "pasaje": passage}]}],
            "preguntas_investigacion": ["¿Uno?", "¿Dos?", "¿Tres?"] if task == "brief" else [],
            "verificaciones_pendientes": ["Confirmar con fuente oficial."],
            "borrador": f"{ONLY_HEADLINE} " + " ".join(["palabra"] * (size - word_count(ONLY_HEADLINE))),
        }, ensure_ascii=False), {"prompt_tokens": 1, "completion_tokens": 1}


class NoNetwork:
    def complete(self, *args, **kwargs):
        raise AssertionError("offline mode must not call the LLM")


@pytest.fixture(scope="module")
def news() -> pd.DataFrame:
    return pd.read_parquet(STUB_PATH)


@pytest.fixture
def cards(news, tmp_path):
    return build_fichas(news, top_n=None, now=NOW, client=HeadlineModel(), offline=False, cache_dir=tmp_path)


def test_one_card_per_cluster_in_ranking_order(cards, news):
    scored = score_clusters(news, now=NOW)
    assert [c["cluster_id"] for c in cards] == scored["cluster_id"].tolist()
    assert [c["id_caso"] for c in cards] == [case_id(c) for c in scored["cluster_id"]]
    for card in cards:
        assert not [f for f in CONTRACT_FIELDS if f not in card]
        assert card["accion_recomendada"] == recommended_action(
            card["estado_evidencia"], card["alertas"], card["abstencion"], card["motivo_abstencion"], card["recirculada"])
        assert card["estado_revision"] == "nuevo" and card["sintetico"] is True


def test_top_n_bounds_llm_calls(news, tmp_path):
    model = HeadlineModel()
    cards = build_fichas(news, top_n=2, now=NOW, client=model, offline=False, cache_dir=tmp_path)
    assert len(cards) == 2 and model.calls == 6  # brief, guion, copy per case


def test_cards_carry_cited_claims_and_generation_trace(cards):
    canal = next(c for c in cards if c["cluster_id"] == "C-STUB-01")
    assert canal["afirmaciones"] and all(claim["citas"] for claim in canal["afirmaciones"])
    assert {c["id_fuente"] for c in canal["citas"]} <= set(canal["ids_fuente"])
    assert set(canal["borrador"]) == {"brief", "guion", "copy"}
    assert canal["generacion"]["brief"]["origen"] == "llm"
    assert canal["puntaje"]["version_reglas"] == "scoring_v1"


def test_injected_source_becomes_alert_not_claim(cards):
    injected = next(c for c in cards if c["cluster_id"] == "C-STUB-03")
    assert injected["abstencion"] and injected["afirmaciones"] == []
    assert any("instrucción inyectada" in a for a in injected["alertas"])


def test_offline_rebuild_is_identical_except_timestamp(news, tmp_path):
    online = build_fichas(news, top_n=3, now=NOW, client=HeadlineModel(), offline=False, cache_dir=tmp_path)
    offline = build_fichas(news, top_n=3, now=NOW, client=NoNetwork(), offline=True, cache_dir=tmp_path)
    strip = lambda cs: [{k: v for k, v in c.items() if k not in ("generado_en", "generacion")} for c in cs]
    assert strip(online) == strip(offline)
    assert all(g["origen"] == "cache" for c in offline for g in c["generacion"].values())


def test_export_roundtrip_feeds_the_inbox(cards, news, tmp_path):
    path = export_fichas(cards, tmp_path / "fichas.jsonl")
    assert list(tmp_path.glob("*.tmp")) == []
    loaded = read_cards(path)
    assert [c["id_caso"] for c in loaded] == [c["id_caso"] for c in cards]
    inbox = build_inbox(score_clusters(news, now=NOW), news, loaded)  # Cristian's C-12 reads it as is
    assert inbox["id_caso"].notna().all()


# --- review log ----------------------------------------------------------------------------

def test_review_log_is_append_only_and_last_wins(tmp_path):
    log = tmp_path / "revisiones.jsonl"
    append_review("F-C-STUB-01", "en revisión", "Cristian", path=log, now="2026-10-06T19:00:00Z")
    append_review("F-C-STUB-01", "aprobado como borrador", "José", nota="ok", path=log, now="2026-10-06T19:05:00Z")
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2
    latest = latest_reviews(log)["F-C-STUB-01"]
    assert (latest["estado_revision"], latest["revisor"]) == ("aprobado como borrador", "José")


def test_review_validation_and_bad_lines(tmp_path):
    log = tmp_path / "revisiones.jsonl"
    with pytest.raises(ValueError):
        append_review("F-X", "publicado", "José", path=log)
    with pytest.raises(ValueError):
        append_review("F-X", "nuevo", "  ", path=log)
    log.write_text('no es json\n{"id_caso": "F-X", "estado_revision": "inventado"}\n', encoding="utf-8")
    append_review("F-X", "descartado", "Cristian", path=log)
    records, skipped = read_reviews(log)
    assert [r["estado_revision"] for r in records] == ["descartado"] and skipped == 2


def test_reviews_apply_to_cards(cards, tmp_path):
    log = tmp_path / "revisiones.jsonl"
    append_review(cards[0]["id_caso"], "requiere evidencia", "Cristian", path=log)
    reviewed = apply_reviews(cards, latest_reviews(log))
    assert reviewed[0]["estado_revision"] == "requiere evidencia" and reviewed[0]["revisor"] == "Cristian"
    assert all(c["estado_revision"] == "nuevo" for c in reviewed[1:])
    assert set(REVIEW_STATES) == {"nuevo", "en revisión", "requiere evidencia", "aprobado como borrador", "descartado"}


@pytest.mark.parametrize("state", ["insuficiente", "parcial", "suficiente para el borrador"])
@pytest.mark.parametrize("alerts, abstained, recirculated", [
    ([], False, False), (["posible instrucción inyectada en N-x"], False, False),
    ([], True, False), ([], False, True), (["a"], True, True),
])
def test_backend_and_ui_recommend_the_same(state, alerts, abstained, recirculated):
    # One rule, two places (ADR-022): the card field and the UI fallback must agree.
    card = {"alertas": alerts, "abstencion": abstained, "motivo_abstencion": "falta un dato oficial."}
    assert recommended_action(state, alerts, abstained, card["motivo_abstencion"], recirculated) == \
        ui_action(state, card, recirculated)
    assert "publicar" not in recommended_action(state, alerts, abstained, None, recirculated).lower()
