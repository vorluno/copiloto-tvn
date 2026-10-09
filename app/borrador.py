"""Draft view (C-14): brief, script and social copy as the guard left them. Owner: Cristian.

Pure functions, no Streamlit. The app shows drafts and never edits them. It asks for a new
one only through José's public build_package / generate_draft (J-16), with the same requests
`make fichas` sends, so cache, offline mode and guard apply unchanged. Word limits mirror
src/generate/guard.py (a test keeps them in sync).
"""

import os
import re
from dataclasses import replace
from pathlib import Path

from app.revision import panama_time

# Same ranges the guard enforces (guard.WORD_LIMITS).
WORD_LIMITS = {"brief": (1, 250), "guion": (110, 150), "copy": (1, 80)}
ANSWER_LIMIT = (1, 150)  # guard.WORD_LIMITS["respuesta"], for the query box (CU-04)
TASK_LABELS = {"brief": "Brief (≤250 palabras)", "guion": "Guion (45–60 s · 110–150 palabras)",
               "copy": "Copy digital (≤80 palabras)"}
# How each claim type is shown, so a hypothesis never reads like a fact.
CLAIM_STYLE = {
    "hecho": ("✅", "Hecho", "Respaldado por la cita."),
    "declaracion": ("🗣️", "Declaración", "Lo dice una fuente; se atribuye, no se afirma."),
    "inferencia": ("🔎", "Inferencia", "Deducción a partir de las fuentes; no es un hecho reportado."),
    "hipotesis": ("❓", "Hipótesis", "Por verificar; no usar como hecho."),
}


def word_count(text: str) -> int:
    """Same tokenization as the guard."""
    return len(re.findall(r"\w+(?:[-'’]\w+)*", text))


def draft_rows(card: dict | None) -> list[dict]:
    """One row per task: text, word count and whether it fits its range. Missing stays None."""
    drafts = (card or {}).get("borrador") or {}
    rows = []
    for task, (low, high) in WORD_LIMITS.items():
        text = drafts.get(task)
        words = word_count(text) if text else None
        rows.append({"tarea": task, "etiqueta": TASK_LABELS[task], "texto": text, "palabras": words,
                     "min": low, "max": high, "dentro": None if words is None else low <= words <= high})
    return rows


def claims_by_type(card: dict | None) -> list[tuple[str, list[dict]]]:
    """Claims grouped in a fixed order: facts first, hypotheses last. Empty groups dropped."""
    claims = (card or {}).get("afirmaciones") or []
    return [(kind, group) for kind in CLAIM_STYLE if (group := [c for c in claims if c.get("tipo") == kind])]


def citation_label(cita: dict | None) -> str:
    """`ID · campo` · “pasaje”, the citation format the challenge requires."""
    if not cita:
        return "— (sin cita)"
    return f"`{cita.get('id_fuente')} · {cita.get('campo')}` · “{cita.get('pasaje')}”"


def evidence_context(evidence) -> str:
    """What makes a piece of evidence readable on its own (rule 9 for World Bank: country, year
    and unit). `evidence` is a src.generate.schema.Evidence; missing fields show as '—'."""
    if evidence is None:
        return "—"
    f = evidence.fields
    if evidence.kind == "indicador":
        return f"{f.get('pais_iso3', '—')} · {f.get('anio', '—')} · {f.get('unidad', '—')} · Banco Mundial"
    if evidence.kind == "sismo":
        when = panama_time(f.get("time")) if f.get("time") else "—"  # rule 6: the UI shows Panama time
        return f"M {f.get('magnitude', '—')} · {f.get('place', '—')} · {when} · USGS"
    return f"{f.get('medio', '—')}" + (" · solo titular/metadatos" if evidence.headline_only else "")


def query_cards(cards: list[dict]) -> list[dict]:
    """Cards that answer a free-text query (CU-04) instead of a cluster."""
    return [c for c in cards if c.get("consulta") and not c.get("cluster_id")]


# --- Live drafting for any event (J-16) ----------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
DRAFT_TASKS = ("brief", "guion", "copy")


def has_model_key(env_file: Path = ROOT / ".env") -> bool:
    """True if a model key is configured (environment or .env), without reading it anywhere else."""
    if os.getenv("LLM_API_KEY"):
        return True
    if not env_file.exists():
        return False
    from dotenv import dotenv_values
    return bool(dotenv_values(env_file).get("LLM_API_KEY"))


def can_draft_live(offline: bool | None = None) -> bool:
    """A new draft needs the network and a model key; without them only saved drafts exist."""
    from src.generate.generate import is_offline
    offline = is_offline() if offline is None else offline
    return not offline and has_model_key()


def draft_package(cluster_id, news, scored, contexto=None, official=None, client=None, offline=None,
                  cache_dir=None, on_step=None):
    """Brief, guion and copy for one event with exactly the requests `make fichas` sends.

    It calls build_package one task at a time so the UI can say which step is running, and
    keeps build_package's rule: if the brief abstains, guion and copy are not requested.
    `on_step(task)` is called before each task.
    """
    from src.generate.drafts import TaskDraft, build_package
    from src.generate.generate import CACHE_DIR

    package = None
    for task in DRAFT_TASKS:
        if on_step:
            on_step(task)
        if package is not None and package.abstained:
            package.drafts[task] = TaskDraft(task, package.drafts["brief"].result, attempts=0, skipped=True)
            continue
        part = build_package(cluster_id, news, scored, contexto=contexto, official=official, tasks=(task,),
                             client=client, offline=offline, cache_dir=cache_dir or CACHE_DIR)
        if package is None:
            package = part
        else:
            package.drafts[task] = part.drafts[task]
    return package


def task_gaps(package) -> dict[str, dict]:
    """What the quality check recorded per format, to explain a missing draft in plain words."""
    return {task: {"source": d.result.source, "violations": list(d.result.report.violations),
                   "abstencion": bool(d.result.output.abstencion), "motivo": d.result.output.motivo_abstencion,
                   "skipped": d.skipped}
            for task, d in package.drafts.items()}


def package_failed(package) -> bool:
    """Nothing came back from the model (offline without cache, or provider error)."""
    return package.drafts["brief"].result.source in ("offline_miss", "error")


def redraft_guion(cluster_id, news, scored, contexto=None, official=None, words: int | None = None,
                  client=None, offline=None, cache_dir=None):
    """One more script attempt asking explicitly for 110-150 words, through DraftRequest.feedback.

    Same request as build_package's guion (topic, evidence, score line, evidence state); only
    the feedback the retry mechanism already uses is added, so the prompt does not change.
    """
    from src.generate.drafts import cluster_evidence, cluster_topic, describe_score
    from src.generate.generate import CACHE_DIR, DraftRequest, generate_draft

    row = scored.set_index("cluster_id").loc[cluster_id]
    evidence, _ = cluster_evidence(cluster_id, news, contexto, official)
    low, high = WORD_LIMITS["guion"]
    feedback = ([f"guion: {words} palabras, fuera de [{low}, {high}]"] if words else []) + [
        f"El guion debe tener entre {low} y {high} palabras en \"borrador\" (45-60 segundos de lectura)."]
    base = DraftRequest(task="guion", topic=cluster_topic(cluster_id, news, row["tema"]), evidence=evidence,
                        score_line=describe_score(row), evidence_state=row["estado_evidencia"])
    return generate_draft(replace(base, feedback=feedback), client=client, offline=offline,
                          cache_dir=cache_dir or CACHE_DIR)


def group_citations(citas: list[dict] | None) -> list[dict]:
    """A claim's citations, one entry per source item, in first-seen order.

    A World Bank datum cited by value, unit, year and country is one source, not four.
    Each entry: id_fuente and its (campo, pasaje) parts, duplicates dropped.
    """
    groups: dict = {}
    for c in citas or []:
        g = groups.setdefault(c.get("id_fuente"), {"id_fuente": c.get("id_fuente"), "partes": []})
        part = (c.get("campo"), c.get("pasaje"))
        if part not in g["partes"]:
            g["partes"].append(part)
    return list(groups.values())
