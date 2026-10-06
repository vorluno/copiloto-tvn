"""Case card view (C-13, stage 5). Owner: Cristian.

Pure functions, no Streamlit. A card explains one cluster: what is reported, who
reports it, what is backed, what is missing and the recommended action. Scores come
from score_clusters; claims and citations from the case card when there is one.
"""

import pandas as pd

from src.generate.guard import normalize

# P = 30R + 25I + 20U + 15N + 10E (CLAUDE.md §1, rules/scoring_v1.yaml).
WEIGHTS = {"R": 30, "I": 25, "U": 20, "N": 15, "E": 10}
COMPONENT_NAMES = {"R": "Relación con Panamá", "I": "Impacto", "U": "Urgencia",
                   "N": "Novedad", "E": "Evidencia"}
CLAIM_TYPES = {"hecho": "Hecho", "declaracion": "Declaración",
               "inferencia": "Inferencia", "hipotesis": "Hipótesis"}


def component_points(scored_row) -> list[dict]:
    """Each component's 0–1 value and the points it adds to P. Nulls stay null."""
    rows = []
    for key, weight in WEIGHTS.items():
        value = scored_row.get(key)
        missing = value is None or pd.isna(value)
        rows.append({"clave": key, "nombre": COMPONENT_NAMES[key], "peso": weight,
                     "valor": None if missing else float(value),
                     "puntos": None if missing else round(weight * float(value), 1)})
    return rows


def cluster_sources(news: pd.DataFrame, cluster_id: str) -> pd.DataFrame:
    """Who reports it: the cluster's news, newest first by detection, else publication."""
    items = news[news["cluster_id"] == cluster_id]
    order = items["fecha_deteccion"].fillna(items["fecha_publicacion"])
    return items.assign(_order=order).sort_values("_order", ascending=False).drop(columns="_order")


def citation_found(news: pd.DataFrame, cita: dict, official: dict | None = None) -> bool:
    """True if the cited passage appears in the cited field, compared the way the guard does.

    News items are looked up in noticias; World Bank and USGS items in `official`
    (src.generate.drafts.official_index), so an official citation the guard accepted
    is not shown as missing.
    """
    passage, field = cita.get("pasaje"), cita.get("campo")
    if not passage:
        return False
    item = (official or {}).get(cita.get("id_fuente"))
    if item is not None:
        text = item.fields.get(field)
    else:
        match = news[news["id_noticia"] == cita.get("id_fuente")]
        if match.empty or field not in match.columns:
            return False
        text = match.iloc[0][field]
    return isinstance(text, str) and normalize(passage) in normalize(text)


def action_for(estado_evidencia: str, card: dict | None, recirculada: bool) -> str:
    """The card's own recommended action when there is a card; the same rule otherwise."""
    return (card or {}).get("accion_recomendada") or recommended_action(estado_evidencia, card, recirculada)


def headline_only(sources: pd.DataFrame) -> bool:
    """Rule 8: any source with only headline/metadata limits what the draft can say."""
    return bool((sources["alcance_texto"] == "titular/metadatos").any())


def recommended_action(estado_evidencia: str, card: dict | None, recirculada: bool) -> str:
    """Deterministic next step for the editor (ADR-022). Never 'publish'.

    Fallback only: a case card already carries `accion_recomendada` from the same rule
    in src/fichas.py; tests/test_fichas.py keeps both in sync.
    """
    card = card or {}
    if card.get("alertas"):
        return "No usar esta fuente como hecho: contiene instrucciones. Revisar la alerta y descartar si no hay otra fuente."
    if card.get("abstencion"):
        return f"No redactar todavía: {card.get('motivo_abstencion') or 'el sistema se abstuvo.'}"
    if recirculada:
        return "No presentar como nuevo: es una nota anterior que vuelve a circular. Verificar fecha original."
    if estado_evidencia == "suficiente para el borrador":
        return "Puede pasar a borrador. Una persona revisa antes de cualquier uso."
    if estado_evidencia == "parcial":
        return "Puede empezar un borrador, pero resolver las verificaciones pendientes antes de aprobarlo."
    return "Buscar más evidencia (otra procedencia o fuente oficial) antes de redactar."
