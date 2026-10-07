"""Prepare the offline demo: one online run that fills outputs/cache/ (J-12). Owner: José.

`make demo-cache` (needs LLM_API_KEY and internet), in order:
1. case cards for the top N clusters by P -> outputs/fichas.jsonl (brief, guion, copy);
2. every question in docs/demo/consultas_demo.txt, exactly as the app's query box asks it
   (same search, same evidence, so the same cache key);
3. outputs/reports/corrida_llm.md: where each answer came from, what the guard dropped,
   latency, tokens and cost (cost only with LLM_PRICE_* in .env, never assumed free).

Re-running only pays for what is not cached yet. `OFFLINE=1 make demo-cache` runs the same
walkthrough without network and fails if anything is missing from the cache: the check to
do before rehearsing the demo. Exit 1 when a call failed or, offline, when an answer is not
cached, so a demo is never rehearsed on a half-filled cache.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.eval.metrics import cost_usd, median, percentile
from src.fichas import DEFAULT_TOP_N, ROOT, build_fichas, export_fichas, latest_reviews, load_inputs
from src.generate.generate import CACHE_DIR, is_offline, model_name
from src.generate.query import answer_question
from src.search import load_index

QUESTIONS_PATH = ROOT / "docs" / "demo" / "consultas_demo.txt"
REPORT_PATH = ROOT / "outputs" / "reports" / "corrida_llm.md"


@dataclass
class Call:
    item: str  # case id + task, or the question
    task: str
    source: str  # cache, llm, offline_miss, error, sin_evidencia, omitida
    claims: tuple[int, int] | None
    latency_s: float | None
    usage: dict


def read_questions(path: Path = QUESTIONS_PATH) -> list[str]:
    if not path.exists():
        return []
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def card_calls(cards: list[dict]) -> list[Call]:
    calls = []
    for card in cards:
        for task, gen in card["generacion"].items():
            item = f"{card['id_caso']} · {task}"
            if gen.get("intentos") == 0:  # not requested: the brief abstained (counted once, on the brief)
                calls.append(Call(item, task, "omitida", None, None, {}))
                continue
            claims = tuple(gen["afirmaciones"]) if gen.get("afirmaciones") else None
            calls.append(Call(item, task, gen["origen"], claims, gen.get("latencia_s"), gen.get("tokens") or {}))
    return calls


def question_calls(questions: list[str], index=None, client=None, offline: bool | None = None,
                   cache_dir: Path = CACHE_DIR) -> list[Call]:
    index = index or load_index()
    calls = []
    for question in questions:
        result = answer_question(question, index.search(question).evidence, client=client, offline=offline,
                                 cache_dir=cache_dir)
        report = result.report
        calls.append(Call(question, "respuesta", result.source, (report.claims_kept, report.claims_received),
                          result.latency_s, result.usage or {}))
    return calls


def _price(name: str) -> float | None:
    value = os.getenv(name, "").strip()
    return float(value) if value else None


def summarize(calls: list[Call]) -> dict:
    model_calls = [c for c in calls if c.source in ("llm", "cache")]
    latencies = [c.latency_s for c in model_calls if c.latency_s is not None]
    tokens_in = [c.usage.get("prompt_tokens") for c in model_calls]
    tokens_out = [c.usage.get("completion_tokens") for c in model_calls]
    known = None not in tokens_in + tokens_out and bool(model_calls)
    cost = cost_usd(sum(tokens_in), sum(tokens_out), _price("LLM_PRICE_INPUT_PER_M"),
                    _price("LLM_PRICE_OUTPUT_PER_M")) if known else None
    kept = sum(c.claims[0] for c in model_calls if c.claims)
    received = sum(c.claims[1] for c in model_calls if c.claims)
    return {
        "fuentes": pd.Series([c.source for c in calls], dtype=object).value_counts().to_dict(),
        "mediana_s": median(latencies), "p95_s": percentile(latencies, 95), "n_latencias": len(latencies),
        "tokens_entrada": sum(tokens_in) if known else None, "tokens_salida": sum(tokens_out) if known else None,
        "costo_usd": cost, "afirmaciones": (kept, received),
        "fallos": [c for c in calls if c.source in ("error", "offline_miss")],
    }


def _fmt(value, unit: str = "", digits: int = 2) -> str:
    return "sin dato" if value is None else f"{value:.{digits}f}{unit}" if isinstance(value, float) else f"{value}{unit}"


def write_report(cards: list[dict], calls: list[Call], summary: dict, offline: bool, path: Path = REPORT_PATH) -> Path:
    kept, received = summary["afirmaciones"]
    cost = "sin precio en .env (LLM_PRICE_*)" if summary["costo_usd"] is None else f"{summary['costo_usd']:.4f} USD"
    lines = [
        "# Corrida del LLM para la demo (J-12)",
        "",
        f"- Generado: {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%dT%H:%M:%SZ')} · modelo `{model_name()}` · "
        f"{'OFFLINE=1 (solo caché)' if offline else 'en línea'}",
        f"- Fichas: {len(cards)} · llamadas: {len(calls)} · origen: "
        + ", ".join(f"{k} {v}" for k, v in summary["fuentes"].items()),
        f"- Afirmaciones que pasaron el guard: {kept}/{received}" if received else
        "- Afirmaciones que pasaron el guard: sin casos",
        f"- Latencia por llamada (medida al generar; la caché la conserva): mediana {_fmt(summary['mediana_s'], ' s')}, "
        f"p95 {_fmt(summary['p95_s'], ' s')} (n = {summary['n_latencias']})",
        f"- Tokens: entrada {_fmt(summary['tokens_entrada'])}, salida {_fmt(summary['tokens_salida'])} · "
        f"costo: {cost}",
        "",
        "| Caso o consulta | Tarea | Origen | Afirmaciones (quedan/recibidas) | Latencia s |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in calls:
        claims = f"{c.claims[0]}/{c.claims[1]}" if c.claims else "—"
        lines.append(f"| {c.item} | {c.task} | {c.source} | {claims} | {_fmt(c.latency_s)} |")
    if summary["fallos"]:
        lines += ["", "**Faltan respuestas:** " + "; ".join(f"{c.item} ({c.source})" for c in summary["fallos"])]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def main() -> int:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description="Fill (or, with OFFLINE=1, check) the demo cache")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N, help="clusters by P to draft")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    offline = is_offline()

    cards = build_fichas(**load_inputs(), top_n=args.top or None, reviews=latest_reviews())
    if not offline:  # offline is a check: it must not rewrite what the online run produced
        export_fichas(cards)
    calls = card_calls(cards) + question_calls(read_questions())
    summary = summarize(calls)
    report = write_report(cards, calls, summary, offline)

    print(f"{len(cards)} fichas y {len(read_questions())} consultas · origen: {summary['fuentes']}")
    print(f"Reporte: {report.relative_to(ROOT)}")
    if summary["fallos"]:
        what = "sin respuesta en caché" if offline else "fallaron (¿LLM_API_KEY? ¿red?)"
        print(f"{len(summary['fallos'])} llamadas {what}:", file=sys.stderr)
        for c in summary["fallos"]:
            print(f"  {c.item} · {c.source}", file=sys.stderr)
        return 1
    print("Caché completa para la demo sin internet." if offline else "Listo. Comprueba con: OFFLINE=1 make demo-cache")
    return 0


if __name__ == "__main__":
    sys.exit(main())
