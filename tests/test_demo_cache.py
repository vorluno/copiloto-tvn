"""make demo-cache (J-12): fill the cache online, then prove the demo walkthrough is complete offline.

A fake model stands in for Gemini (same one as T10); the real run is Levi's with OpenRouter.
"""

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from src.demo_cache import (QUESTIONS_PATH, card_calls, question_calls, read_questions, summarize,
                            write_report)
from src.fichas import build_fichas
from src.generate.guard import SECRET_PATTERNS
from src.search import SearchIndex
from tests.test_t10 import HeadlineModel

ROOT = Path(__file__).resolve().parents[1]
STUB = ROOT / "data" / "stub" / "noticias_stub.parquet"
NOW = pd.Timestamp("2026-10-06T18:00:00Z")
QUESTIONS = ["cortes de agua en San Miguelito", "receta de pizza napolitana"]


class BrokenModel:
    def complete(self, messages, model, temperature):
        raise ConnectionError("provider down")


@pytest.fixture(scope="module")
def news():
    return pd.read_parquet(STUB)


@pytest.fixture(scope="module")
def index(news):
    return SearchIndex.build(news)


@pytest.fixture
def online(news, index, tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_PRICE_INPUT_PER_M", raising=False)
    cache = tmp_path / "cache"
    cards = build_fichas(news, top_n=3, now=NOW, client=HeadlineModel(), offline=False, cache_dir=cache)
    calls = card_calls(cards) + question_calls(QUESTIONS, index, client=HeadlineModel(), offline=False,
                                               cache_dir=cache)
    return cache, cards, calls


def test_online_run_has_no_failures(online):
    _, cards, calls = online
    summary = summarize(calls)
    assert not summary["fallos"]
    assert summary["fuentes"].get("llm", 0) >= len(cards)  # at least one brief per card came from the model
    no_evidence = next(c for c in calls if c.item == "receta de pizza napolitana")
    assert no_evidence.source == "sin_evidencia"  # abstains in code, nothing to cache, not a failure


def test_offline_check_replays_everything_from_cache(online, news, index):
    cache, cards, _ = online
    replay = build_fichas(news, top_n=3, now=NOW, offline=True, cache_dir=cache)
    calls = card_calls(replay) + question_calls(QUESTIONS, index, offline=True, cache_dir=cache)
    summary = summarize(calls)
    assert not summary["fallos"]
    assert set(summary["fuentes"]) <= {"cache", "sin_evidencia", "omitida"}


def test_offline_check_flags_a_question_that_was_never_cached(online, index):
    cache, _, _ = online
    calls = question_calls(["turismo de cruceros en Colón"], index, offline=True, cache_dir=cache)
    assert [c.source for c in summarize(calls)["fallos"]] == ["offline_miss"]


def test_provider_error_is_a_failure(index, tmp_path):
    calls = question_calls(QUESTIONS[:1], index, client=BrokenModel(), offline=False, cache_dir=tmp_path)
    assert [c.source for c in summarize(calls)["fallos"]] == ["error"]
    assert not list(tmp_path.glob("*.json"))  # errors are never cached


def test_report_counts_and_never_assumes_free(online, tmp_path):
    _, cards, calls = online
    summary = summarize(calls)
    text = write_report(cards, calls, summary, offline=False, path=tmp_path / "corrida.md").read_text(encoding="utf-8")
    assert f"Fichas: {len(cards)}" in text
    assert "sin precio en .env" in text and "0.0000 USD" not in text
    assert all(c.item in text for c in calls)


def test_report_cost_with_prices(online, monkeypatch):
    _, _, calls = online
    monkeypatch.setenv("LLM_PRICE_INPUT_PER_M", "1")
    monkeypatch.setenv("LLM_PRICE_OUTPUT_PER_M", "1")
    summary = summarize(calls)
    model = [c for c in calls if c.source in ("llm", "cache")]
    assert summary["costo_usd"] == pytest.approx(2 * len(model) / 1e6)  # the fake model reports 1 + 1 tokens


def test_demo_questions_file(tmp_path):
    sample = tmp_path / "q.txt"
    sample.write_text("# comentario\n\n¿Uno?\n  ¿Dos?  \n", encoding="utf-8")
    assert read_questions(sample) == ["¿Uno?", "¿Dos?"]
    assert read_questions(QUESTIONS_PATH)  # the pitch questions ship with the repo


def test_committed_cache_holds_no_secret():
    # outputs/cache/ is committed for the offline demo: it must never carry a key.
    for path in (ROOT / "outputs" / "cache").glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert not any(re.search(p, text) for p in SECRET_PATTERNS), path.name
        assert "api_key" not in json.loads(text)


MIN_REAL_PROMPT_TOKENS = 200  # the system rules alone are longer; the test models report 1


def _tracked(pattern: str) -> list[Path]:
    import subprocess
    try:
        out = subprocess.run(["git", "ls-files", pattern], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [ROOT / line for line in out.splitlines() if line.endswith((".json", ".jsonl"))]


def test_committed_cache_comes_from_a_real_model():
    # A test-model answer stored under the real model's key would be served as Gemini's in the
    # demo, and `make demo-cache` would never replace it (it happened once: ed04499, fixed).
    for path in _tracked("outputs/cache"):
        usage = json.loads(path.read_text(encoding="utf-8")).get("usage") or {}
        assert (usage.get("prompt_tokens") or 0) >= MIN_REAL_PROMPT_TOKENS, path.name


def test_committed_fichas_come_from_a_real_model():
    for path in _tracked("outputs/fichas.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            card = json.loads(line)
            for task, gen in card["generacion"].items():
                if gen.get("origen") in ("llm", "cache") and gen.get("intentos"):
                    tokens = (gen.get("tokens") or {}).get("prompt_tokens") or 0
                    assert tokens >= MIN_REAL_PROMPT_TOKENS, f"{card['id_caso']} · {task}"
