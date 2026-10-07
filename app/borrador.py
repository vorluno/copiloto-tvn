"""Draft view (C-14): brief, script and social copy as the guard left them. Owner: Cristian.

Pure functions, no Streamlit. The app only shows drafts; it never edits or generates
them. Word limits mirror src/generate/guard.py (a test keeps them in sync).
"""

import re

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
        return f"M {f.get('magnitude', '—')} · {f.get('place', '—')} · {f.get('time', '—')} · USGS"
    return f"{f.get('medio', '—')}" + (" · solo titular/metadatos" if evidence.headline_only else "")


def query_cards(cards: list[dict]) -> list[dict]:
    """Cards that answer a free-text query (CU-04) instead of a cluster."""
    return [c for c in cards if c.get("consulta") and not c.get("cluster_id")]
