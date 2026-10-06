"""T10 · No internet. Owner: José (J-12).

Prepared input: Wifi off, OFFLINE=1.
Expected result: Full walkthrough served from cache; documented fallback.
Source: section 9 of docs/reto.pdf.

The pitch walkthrough is replayed with the network cut at socket level (any connection
attempt fails the test): case cards (inbox order, brief, script, copy), a cached query,
a new query (explicit "not in cache"), a query with no evidence, and the app itself.
The cache is filled first by a fake model, standing in for the online run with Gemini.
"""

import json
import socket
from pathlib import Path

import pandas as pd
import pytest

from src.fichas import build_fichas
from src.generate.guard import ONLY_HEADLINE, word_count
from src.generate.query import answer_question
from src.search import SearchIndex

STUB = Path(__file__).resolve().parents[1] / "data" / "stub" / "noticias_stub.parquet"
NOW = pd.Timestamp("2026-10-06T18:00:00Z")
QUERY = "cortes de agua en San Miguelito"


class HeadlineModel:
    """Stands in for Gemini during the online run that fills the cache."""

    def complete(self, messages, model, temperature):
        user = messages[1]["content"]
        task = next(line.split()[1] for line in user.splitlines() if line.startswith("Tarea:"))
        source = user.split('<fuente id="')[1].split('"')[0]
        title = next(line[len("titulo: "):] for line in user.splitlines() if line.startswith("titulo: "))
        passage = " ".join(title.split()[:3])
        size = {"brief": 100, "guion": 120, "copy": 40, "respuesta": 60}[task]
        return json.dumps({
            "abstencion": False, "titulo": "Título propuesto",
            "afirmaciones": [{"texto": f"Un medio reporta: {passage}.", "tipo": "declaracion",
                              "citas": [{"id_fuente": source, "campo": "titulo", "pasaje": passage}]}],
            "preguntas_investigacion": ["¿Uno?", "¿Dos?", "¿Tres?"] if task == "brief" else [],
            "borrador": f"{ONLY_HEADLINE} " + " ".join(["palabra"] * (size - word_count(ONLY_HEADLINE))),
        }, ensure_ascii=False), {"prompt_tokens": 1, "completion_tokens": 1}


@pytest.fixture
def no_network(monkeypatch):
    """Wifi off: every outbound connection raises."""
    def refuse(*args, **kwargs):
        raise AssertionError("T10: network access attempted while offline")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setenv("OFFLINE", "1")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")


@pytest.fixture(scope="module")
def news() -> pd.DataFrame:
    return pd.read_parquet(STUB)


@pytest.fixture
def warmed(news, tmp_path):
    """Online run before the demo: fill the cache for the cards and one query."""
    cache = tmp_path / "cache"
    cards = build_fichas(news, top_n=3, now=NOW, client=HeadlineModel(), offline=False, cache_dir=cache)
    index = SearchIndex.build(news)
    answer = answer_question(QUERY, index.search(QUERY).evidence, client=HeadlineModel(), offline=False,
                             cache_dir=cache)
    return {"cache": cache, "cards": cards, "index": index, "answer": answer}


def test_t10(news, warmed, no_network):
    """Full walkthrough served from cache with the network cut."""
    cache = warmed["cache"]
    cards = build_fichas(news, top_n=3, now=NOW, offline=None, cache_dir=cache)  # OFFLINE=1 from env
    strip = lambda cs: [{k: v for k, v in c.items() if k not in ("generado_en", "generacion")} for c in cs]
    assert strip(cards) == strip(warmed["cards"])  # same inbox order, briefs, scripts and copies
    assert all(g["origen"] == "cache" for c in cards for g in c["generacion"].values())

    cached = answer_question(QUERY, warmed["index"].search(QUERY).evidence, offline=None, cache_dir=cache)
    assert cached.source == "cache" and cached.output == warmed["answer"].output


def test_t10_new_query_says_it_is_not_cached(warmed, no_network):
    query = "turismo de cruceros en Colón"
    result = answer_question(query, warmed["index"].search(query).evidence, offline=None, cache_dir=warmed["cache"])
    assert result.source == "offline_miss" and result.output.abstencion
    assert "caché" in result.output.motivo_abstencion


def test_t10_no_evidence_needs_no_cache(warmed, no_network):
    result = answer_question("receta de pizza napolitana", [], offline=None, cache_dir=warmed["cache"])
    assert result.source == "sin_evidencia" and result.output.abstencion


def test_t10_app_runs_offline_and_says_so(no_network):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"),
                            default_timeout=120).run()
    assert not app.exception
    assert any("sin internet" in w.value.lower() for w in app.warning)


def test_t10_network_is_really_cut(no_network):
    # Guards the guard: if this passed with the network on, T10 would prove nothing.
    import requests
    with pytest.raises(AssertionError, match="network access attempted"):
        requests.get("https://example.com", timeout=5)
