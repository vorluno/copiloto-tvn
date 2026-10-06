"""Human review (C-15, stage 7). Owner: Cristian.

Pure functions, no Streamlit. Decisions are written with src.fichas.append_review to
outputs/revisiones.jsonl (append-only, J-09); this module only formats. The Markdown
is what Cristian pastes into the Notion database "Casos y evidencias" (ADR-008).
"""

import pandas as pd

COMPONENT_ORDER = ["R", "I", "U", "N", "E"]
TASK_TITLES = {"brief": "Brief", "guion": "Guion", "copy": "Copy digital"}
PANAMA_TZ = "America/Panama"


def panama_time(utc_text: str | None) -> str:
    """ISO UTC text -> Panama time for display; missing stays visible as such."""
    if not utc_text:
        return "— (sin dato)"
    ts = pd.Timestamp(utc_text)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
    return ts.tz_convert(PANAMA_TZ).strftime("%Y-%m-%d %H:%M") + " (Panamá)"


def case_history(records: list[dict], id_caso: str) -> list[dict]:
    """Every decision for one case, newest first. The log itself is never rewritten."""
    return [r for r in reversed(records) if r.get("id_caso") == id_caso]


def _cite(c: dict) -> str:
    return f"`{c.get('id_fuente')} · {c.get('campo')}` · “{c.get('pasaje')}”"


def card_markdown(card: dict, score: dict | None = None, action: str | None = None) -> str:
    """The case card as Markdown for Notion: ID, sources, P and its components, evidence
    state, claims with citations, what is missing, drafts and the review.

    `score` (P, rango, version_reglas and R..E) comes from score_clusters when the cluster
    exists, so Notion shows the same numbers as the inbox; otherwise the card's own.
    """
    puntaje = card.get("puntaje") or {}
    comps = card.get("componentes") or {}
    if score:
        puntaje = {k: score.get(k) for k in ("P", "rango", "version_reglas")}
        comps = {k: score.get(k) for k in COMPONENT_ORDER}
    lines = [f"## {card['id_caso']} · {card.get('titulo') or card.get('consulta') or '—'}", ""]
    if card.get("sintetico"):
        lines += ["> 🧪 Datos sintéticos (sintetico=true): no es un caso real.", ""]
    p = puntaje.get("P")
    lines += [
        f"- **Estado de revisión:** {card.get('estado_revision') or 'nuevo'}",
        f"- **Persona revisora:** {card.get('revisor') or '— (sin revisar)'}",
        f"- **Fecha de revisión:** {panama_time(card.get('fecha_revision'))}",
        f"- **Estado de evidencia:** {card.get('estado_evidencia') or '—'}",
        "- **Puntaje P:** " + ("— (sin puntaje)" if p is None else
                               f"{p:.1f} ({puntaje.get('rango')}) · reglas `{puntaje.get('version_reglas')}`"),
    ]
    if comps:
        lines.append("- **Componentes:** " + " · ".join(
            f"{k} {'—' if comps.get(k) is None else f'{comps[k]:.2f}'}" for k in COMPONENT_ORDER))
    lines.append("- **Fuentes:** " + (", ".join(f"`{i}`" for i in card.get("ids_fuente") or []) or "—"))
    if action:
        lines.append(f"- **Acción recomendada:** {action}")
    lines.append("")

    if card.get("abstencion"):
        lines += ["### Abstención", card.get("motivo_abstencion") or "—", ""]
    if claims := card.get("afirmaciones"):
        lines.append("### Afirmaciones")
        for claim in claims:
            cites = " · ".join(_cite(c) for c in claim.get("citas") or []) or "— (sin cita)"
            lines.append(f"- **{claim.get('tipo')}:** {claim.get('texto')} — {cites}")
        lines.append("")
    if contras := card.get("contradicciones"):
        lines.append("### Contradicciones (verificación pendiente)")
        for c in contras:
            lines.append(f"- A: {c.get('version_a')} — {_cite(c.get('cita_a') or {})}")
            lines.append(f"  B: {c.get('version_b')} — {_cite(c.get('cita_b') or {})}")
        lines.append("")
    missing = list(card.get("verificaciones_pendientes") or []) + list(card.get("alertas") or [])
    if missing:
        lines += ["### Qué falta y alertas"] + [f"- {m}" for m in missing] + [""]
    for task, title in TASK_TITLES.items():
        if text := (card.get("borrador") or {}).get(task):
            lines += [f"### {title} (borrador para revisión humana)", text, ""]
    return "\n".join(lines).rstrip() + "\n"
