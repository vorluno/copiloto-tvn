"""LLM drafting with a hash-keyed cache and an offline mode (J-12; drafting flow J-08). Owner: José.

Flow of `generate_draft`:

1. Build the messages: rules in the system message (prompts/brief_v1.txt), evidence in
   <fuente> tags in the user message. Source text is escaped so it cannot close a tag.
2. Cache key = SHA-256 of the canonical request (prompt version, model, temperature,
   messages). Same input -> same key -> same answer, online or offline.
3. Cache hit -> use the stored raw response. Miss + OFFLINE=1 -> abstention, no network.
   Miss online -> call OpenRouter, store the raw response atomically, then use it.
   Provider errors are never cached.
4. The raw response always goes through guard.py, also when read from cache, so a rule
   fix applies to old cache entries too.

Cache files (outputs/cache/<key>.json) hold the request and the raw response; never the
API key.
"""

import hashlib
import html
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import pandas as pd

from src.generate.guard import WORD_LIMITS, GuardReport, guard
from src.generate.schema import Evidence, SalidaLLM, Task

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "outputs" / "cache"
PROMPT_VERSION = "brief_v2"  # v1 kept for history; v2 adds rules 9-10 (J-10)
PROMPT_PATH = Path(__file__).with_name("prompts") / f"{PROMPT_VERSION}.txt"
DEFAULT_MODEL = "google/gemini-2.5-flash"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
TEMPERATURE = 0.0
TASK_LABELS = {"brief": "brief", "guion": "guion de 45-60 segundos", "copy": "copy digital",
               "respuesta": "respuesta a una consulta del editor"}

OFFLINE_MISS = "Sin internet y sin respuesta guardada en caché para esta consulta."
PROVIDER_ERROR = "El proveedor del LLM no respondió; no se generó borrador."


class LLMClient(Protocol):
    def complete(self, messages: list[dict], model: str, temperature: float) -> tuple[str, dict]:
        """Return (raw text, usage dict)."""


class OpenRouterClient:
    """OpenRouter through its OpenAI-compatible API (ADR-005). Reads LLM_API_KEY from env/.env."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: float = 60.0):
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv(ROOT / ".env")
        key = api_key or os.getenv("LLM_API_KEY")
        if not key:
            raise RuntimeError("LLM_API_KEY is not set (copy .env.example to .env)")
        self._client = OpenAI(
            api_key=key,
            base_url=base_url or os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL,
            timeout=timeout,
            max_retries=1,
        )

    def complete(self, messages: list[dict], model: str, temperature: float) -> tuple[str, dict]:
        response = self._client.chat.completions.create(model=model, messages=messages, temperature=temperature)
        usage = response.usage
        return response.choices[0].message.content or "", {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }


@dataclass
class DraftRequest:
    task: Task
    topic: str
    evidence: list[Evidence]
    score_line: str = "sin puntaje"
    evidence_state: str = "sin estado"
    feedback: list[str] = field(default_factory=list)  # guard findings from a rejected attempt


@dataclass
class DraftResult:
    output: SalidaLLM
    report: GuardReport
    source: str  # "cache", "llm", "offline_miss" or "error"
    cache_key: str
    latency_s: float | None = None
    usage: dict = field(default_factory=dict)


def is_offline() -> bool:
    return os.getenv("OFFLINE", "0") == "1"


def model_name() -> str:
    return os.getenv("LLM_MODEL") or DEFAULT_MODEL


def _attr(value: str) -> str:
    return html.escape(str(value), quote=True)


def render_source(item: Evidence) -> str:
    """One <fuente> block; each field is a 'name: value' line the model can cite."""
    attrs = {"id": item.id, "tipo": item.kind}
    if item.scope:
        attrs["alcance"] = item.scope
    if item.kind == "indicador" and "unidad" in item.fields:
        attrs["unidad"] = item.fields["unidad"]
    opening = " ".join(f'{k}="{_attr(v)}"' for k, v in attrs.items())
    lines = "\n".join(f"{name}: {html.escape(text, quote=False)}" for name, text in item.fields.items())
    return f"<fuente {opening}>\n{lines}\n</fuente>"


def build_messages(request: DraftRequest) -> list[dict]:
    low, high = WORD_LIMITS[request.task]
    limit = f"entre {low} y {high} palabras" if low > 1 else f"hasta {high} palabras"
    header = "\n".join([
        f"Tarea: {TASK_LABELS[request.task]} ({limit} en \"borrador\")",
        f"Consulta: {request.topic}" if request.task == "respuesta" else f"Tema: {request.topic}",
        f"Puntaje: {request.score_line} · Estado de evidencia: {request.evidence_state}",
    ])
    if request.feedback:
        fixes = "\n".join(f"- {item}" for item in request.feedback)
        header += f"\n\nTu respuesta anterior fue rechazada por el validador:\n{fixes}\nCorrige solo eso."
    sources = "\n".join(render_source(item) for item in request.evidence)
    return [
        {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8").strip()},
        {"role": "user", "content": f"{header}\n\n{sources}" if sources else f"{header}\n\n(sin fuentes)"},
    ]


def cache_key(messages: list[dict], model: str, temperature: float = TEMPERATURE) -> str:
    canonical = json.dumps(
        {"prompt_version": PROMPT_VERSION, "model": model, "temperature": temperature, "messages": messages},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_cache(key: str, cache_dir: Path = CACHE_DIR) -> dict | None:
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_cache(entry: dict, cache_dir: Path = CACHE_DIR) -> Path:
    """Atomic write: a crash mid-write never leaves a half-written entry."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{entry['key']}.json"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=cache_dir, suffix=".tmp", delete=False) as tmp:
        json.dump(entry, tmp, ensure_ascii=False, indent=2)
    os.replace(tmp.name, path)
    return path


def generate_draft(
    request: DraftRequest,
    client: LLMClient | None = None,
    offline: bool | None = None,
    cache_dir: Path = CACHE_DIR,
) -> DraftResult:
    """Draft for one task, served from cache when possible; never touches the network offline."""
    offline = is_offline() if offline is None else offline
    model = model_name()
    messages = build_messages(request)
    key = cache_key(messages, model)

    cached = read_cache(key, cache_dir)
    if cached is not None:
        result = guard(cached["response_text"], request.evidence, request.task)
        return DraftResult(result.output, result.report, "cache", key, cached.get("latency_s"), cached.get("usage", {}))

    if offline:
        result = guard({"abstencion": True, "motivo_abstencion": OFFLINE_MISS}, request.evidence, request.task)
        return DraftResult(result.output, result.report, "offline_miss", key)

    started = time.perf_counter()
    try:
        client = client or OpenRouterClient()  # inside: a missing key is a provider error, not a crash
        text, usage = client.complete(messages, model, TEMPERATURE)
    except Exception as exc:  # no key, provider down, timeout, bad key: show an abstention, cache nothing
        result = guard({"abstencion": True, "motivo_abstencion": PROVIDER_ERROR}, request.evidence, request.task)
        result.report.violations.append(f"error del proveedor: {type(exc).__name__}")
        return DraftResult(result.output, result.report, "error", key)
    latency = round(time.perf_counter() - started, 3)

    write_cache({
        "key": key,
        "created_at": pd.Timestamp.now(tz="UTC").isoformat().replace("+00:00", "Z"),
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "temperature": TEMPERATURE,
        "task": request.task,
        "evidence_ids": [item.id for item in request.evidence],
        "messages": messages,
        "response_text": text,
        "usage": usage,
        "latency_s": latency,
    }, cache_dir)
    result = guard(text, request.evidence, request.task)
    return DraftResult(result.output, result.report, "llm", key, latency, usage)


def _smoke() -> None:
    """`make llm-check`: one real brief for the stub Canal cluster; prints what happened."""
    from src.generate.schema import evidence_from_news

    news = pd.read_parquet(ROOT / "data" / "stub" / "noticias_stub.parquet")
    rows = news[news["cluster_id"] == "C-STUB-01"]
    request = DraftRequest(task="brief", topic="Calado en el Canal (stub sintético)",
                           evidence=[evidence_from_news(r) for _, r in rows.iterrows()],
                           evidence_state="parcial")
    result = generate_draft(request)
    report = result.report
    print(f"source={result.source} model={model_name()} offline={is_offline()} latency_s={result.latency_s}")
    print(f"usage={result.usage} cache_key={result.cache_key[:12]}…")
    print(f"guard ok={report.ok} claims={report.claims_kept}/{report.claims_received} "
          f"citations={report.citations_kept}/{report.citations_received}")
    for item in report.dropped_claims:
        print(f"  dropped claim: {item.reason} · {item.texto[:80]}")
    for item in report.dropped_citations + report.violations:
        print(f"  {item}")
    print(json.dumps(result.output.model_dump(), ensure_ascii=False, indent=2)[:2000])


if __name__ == "__main__":
    _smoke()
