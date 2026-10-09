"""Preguntar when the answer abstains but the search did find passages (J-16). Owner: Cristian.

The guard may refuse to answer (no passage answers the question) while the search still found
related items. Hiding them reads as "nothing found"; showing them as an answer would be worse.
So they are listed as the closest findings, clearly marked as not a verified answer: headline,
outlet and date in Panama time (publication or detection, never mixed). Pure functions, no
Streamlit; every value from the data goes through html.escape (a headline is external text).
"""

from html import escape

import pandas as pd

from app import textos as tx

CLOSEST_LIMIT = 5


def _news_date(news: pd.DataFrame, news_id: str) -> str:
    """'Publicada el 30/09/2026' or 'Detectada el …' (GDELT gives no outlet date); never one for the other."""
    row = news.loc[news["id_noticia"] == news_id]
    if row.empty:
        return "sin fecha"
    published, detected = row["fecha_publicacion"].iloc[0], row["fecha_deteccion"].iloc[0]
    if pd.notna(published):
        return f"Publicada el {tx.fecha(published, con_hora=False)}"
    if pd.notna(detected):
        return f"Detectada el {tx.fecha(detected, con_hora=False)}"
    return "sin fecha"


def closest(hits: list, news: pd.DataFrame, limit: int = CLOSEST_LIMIT) -> list[dict]:
    """One row per evidence item (a headline and its summary are one finding), in search order."""
    rows, seen = [], set()
    for hit in hits or []:
        evidence = hit.evidence
        if hit.id_evidencia in seen:
            continue
        seen.add(hit.id_evidencia)
        if evidence.kind == "noticia":
            rows.append({"titular": tx.limpiar_titular(evidence.fields.get("titulo") or hit.texto),
                         "fuente": evidence.fields.get("medio") or "Medio sin nombre",
                         "fecha": _news_date(news, hit.id_evidencia)})
        elif evidence.kind == "indicador":  # rule 9: country, year and unit, never "today"
            f = evidence.fields
            name = tx.INDICADOR.get(f.get("indicador_id"), "Indicador del Banco Mundial")
            country = tx.PAIS.get(f.get("pais_iso3"), f.get("pais_iso3") or "país sin dato")
            rows.append({"titular": f"{name} · {country}, {f.get('anio', 'año sin dato')}: {f.get('valor')} "
                                    f"{f.get('unidad') or ''}".strip(),
                         "fuente": "Banco Mundial", "fecha": f"Año {f.get('anio', 'sin dato')}"})
        else:  # USGS earthquake
            f = evidence.fields
            rows.append({"titular": f"Sismo de magnitud {f.get('magnitude', 'sin dato')} · {f.get('place') or 'lugar sin dato'}",
                         "fuente": "USGS", "fecha": tx.fecha(f.get("time"), con_hora=False)})
        if len(rows) >= limit:
            break
    return rows


def closest_html(rows: list[dict]) -> str:
    items = "".join(
        f'<div class="ctvn-row"><span class="ctvn-type">{escape(r["fuente"])} · {escape(r["fecha"])}</span>'
        f'<span>{escape(r["titular"])}</span></div>' for r in rows)
    return (f'<p class="ctvn-near">{escape(tx.LO_MAS_CERCANO)}</p>{items}'
            f'<div class="ctvn-action ctvn-unverified"><span>Sin verificar</span><p>{escape(tx.NO_VERIFICADO)}</p></div>')


def scroll_script(anchor: str, nonce: str) -> str:
    """Bring the answer into view (on a phone it renders below the suggested questions).
    `nonce` makes each answer a new element, so the script runs again."""
    # Retried while Streamlit lays the page out: an early scroll can stop short of the anchor.
    return (f'<script data-n="{escape(nonce)}">(function(){{function go(){{var el=document.getElementById("{escape(anchor)}");'
            'var calm=window.matchMedia&&window.matchMedia("(prefers-reduced-motion: reduce)").matches;'
            'if(el){el.scrollIntoView({behavior:calm?"auto":"smooth",block:"start"});}}'
            '[60,400,1000].forEach(function(ms){setTimeout(go,ms);});})();</script>')
