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


LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _is_loopback(address) -> bool:
    """Wifi off still leaves the machine's own loopback: asyncio on Windows opens a
    socket pair over 127.0.0.1, and that never leaves the computer."""
    return isinstance(address, tuple) and str(address[0]) in LOOPBACK


@pytest.fixture
def no_network(monkeypatch):
    """Wifi off: every connection that would leave the machine raises."""
    real_connect, real_create = socket.socket.connect, socket.create_connection

    def connect(sock, address, *args, **kwargs):
        if _is_loopback(address) or sock.family == getattr(socket, "AF_UNIX", None):
            return real_connect(sock, address, *args, **kwargs)
        raise AssertionError("T10: network access attempted while offline")

    def create_connection(address, *args, **kwargs):
        if _is_loopback(address):
            return real_create(address, *args, **kwargs)
        raise AssertionError("T10: network access attempted while offline")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    # A proxy listening on loopback would relay to the internet: wifi off means no proxy either.
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
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
    # An IP literal, not a hostname: with the wifi really off DNS fails first (gaierror) and the
    # test would never reach the cut it is checking.
    import requests
    with pytest.raises(AssertionError, match="network access attempted"):
        requests.get("https://93.184.216.34", timeout=5)


def test_t10_loopback_is_not_network(no_network):
    # Windows: asyncio's socketpair connects to 127.0.0.1; that is not the internet.
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(server.getsockname())
    finally:
        client.close()
        server.close()
    with pytest.raises(AssertionError, match="network access attempted"):
        socket.create_connection(("93.184.216.34", 443), timeout=5)


def test_streamlit_usage_stats_are_off():
    """Streamlit's telemetry would call data.streamlit.io from the demo; T10 forbids any call."""
    import tomllib

    config = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"
    assert tomllib.loads(config.read_text(encoding="utf-8"))["browser"]["gatherUsageStats"] is False
