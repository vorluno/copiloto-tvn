"""Copiloto TVN Streamlit UI (J-15 minimal redesign over C-12..C-16). Owner: Cristian; built with José.

A sidebar holds the navigation, a query box reachable from every view and the state the
editor must always see. Four views: Mesa (inbox and case card side by side), Consulta,
Revisión and Datos. Only the active view is drawn, so a click reruns one view, not five.
Reads data/processed/noticias.parquet when B has delivered it, otherwise the synthetic stub.
Data stays in UTC; times are converted to Panama time only for display.

With OFFLINE=1 nothing touches the network: LLM output is read only from
outputs/cache/ and the UI says so. UI text is Spanish (editors are the users).
"""

import json
import os
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from app.bandeja import (
    EVIDENCE_STATES, HEADLINE_LANGUAGES, SCORE_RANGES, build_inbox, filter_inbox,
    headline_label, inbox_pick, language_label, load_cards, load_contexto, records_label, urgency_basis_label,
)
from app.ficha import action_for, citation_found, cluster_sources, component_points, headline_only
from app.borrador import ANSWER_LIMIT, CLAIM_STYLE, claims_by_type, draft_rows, evidence_context, query_cards, word_count
from src.generate.drafts import official_index
from src.generate.generate import model_name
from src.generate.guard import injection_in
from src.generate.query import answer_question
from src.search import load_index
from src.ingest.worldbank import read_indicators
from app.revision import card_markdown, case_history, case_label, panama_time
from src.fichas import REVIEWS_PATH, append_review, apply_reviews, latest_reviews, read_reviews
from app.datos import (
    cache_count, files_table, load_catalog, load_manifest, load_quality, news_by_origin, sources_table,
    verify_messages,
)
from src.manifest import verify as verify_manifest
from app.estilo import (
    CSS, abstention_html, action_html, alert_html, brand_html, check_html, claim_html, contradictions_html,
    evidence_mark, ficha_head_html, header_html, lead_html, md_escape, note_html, page_head_html, score_html,
    section_html, tiles_html,
)
from src.score import score_clusters

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_PATH = ROOT / "data" / "processed" / "noticias.parquet"
STUB_PATH = ROOT / "data" / "stub" / "noticias_stub.parquet"
CACHE_DIR = ROOT / "outputs" / "cache"
OFFICIAL_DIR = ROOT / "data" / "processed"
PITCH_QUERIES_PATH = ROOT / "docs" / "demo" / "consultas_demo.txt"

PANAMA_TZ = "America/Panama"  # UTC-5, no daylight saving
OFFLINE = os.getenv("OFFLINE", "0") == "1"
VIEWS = ["Mesa", "Consulta", "Revisión", "Datos"]
LIST_SIZE = 10  # rows in the Mesa list; "Ver todos" opens the full, selectable table

# Written exactly as the challenge requires.
REVIEW_STATES = [
    "nuevo",
    "en revisión",
    "requiere evidencia",
    "aprobado como borrador",
    "descartado",
]


@st.cache_data
def load_news() -> tuple[pd.DataFrame, str]:
    path = PROCESSED_PATH if PROCESSED_PATH.exists() else STUB_PATH
    return pd.read_parquet(path), path.relative_to(ROOT).as_posix()


@st.cache_data  # U is measured against the corpus date (ADR-027), not the clock: no need to refresh
def load_scores() -> pd.DataFrame:
    return score_clusters(load_news()[0], contexto=load_contexto())


@st.cache_data
def load_inbox(reviews_key: str) -> tuple[pd.DataFrame, list[dict], str | None]:
    """Inbox and case cards with the latest review applied; recomputed only when the review log changes."""
    news, source_path = load_news()
    cards, cards_path = load_cards(news_from_stub=source_path == STUB_PATH.relative_to(ROOT).as_posix())
    cards = apply_reviews(cards, latest_reviews())  # the review log wins over the state in the file
    return build_inbox(load_scores(), news, cards), cards, cards_path


@st.cache_resource
def load_official() -> dict:
    """World Bank and USGS items by ID, to check official citations like the guard does."""
    indicators = OFFICIAL_DIR / "indicadores.csv"
    events = OFFICIAL_DIR / "eventos.geojson"
    return official_index(
        read_indicators(indicators) if indicators.exists() else None,
        json.loads(events.read_text(encoding="utf-8")) if events.exists() else None,
    )


@st.cache_resource
def load_search():
    """J-06 index over the same contract files the app reads."""
    return load_index()


@st.cache_data
def pitch_queries() -> list[str]:
    if not PITCH_QUERIES_PATH.exists():
        return []
    lines = PITCH_QUERIES_PATH.read_text(encoding="utf-8").splitlines()
    return [q.strip() for q in lines if q.strip() and not q.startswith("#")]


def reviews_key() -> str:
    """Changes whenever a decision is appended, so the cached inbox picks it up."""
    if not REVIEWS_PATH.exists():
        return "none"
    stat = REVIEWS_PATH.stat()
    return f"{stat.st_mtime_ns}-{stat.st_size}"


def to_panama(ts: pd.Timestamp) -> str:
    """Panama local time for display; nulls are shown as such, never filled."""
    if pd.isna(ts):
        return "— (sin dato)"
    return ts.tz_convert(PANAMA_TZ).strftime("%Y-%m-%d %H:%M") + " (Panamá)"


def flags(row: pd.Series) -> str:
    labels = []
    if row.get("sintetico", False):
        labels.append("sintético")
    if row.get("recirculada", False):
        labels.append("recirculada")
    if injection_in(row["titulo"] if isinstance(row["titulo"], str) else ""):  # same rule as the guard (J-11)
        labels.append("posible instrucción inyectada")
    return " · ".join(labels)


def citation_text(cita: dict | None) -> str:
    """ID · campo · “pasaje”, the citation format the challenge requires."""
    if not cita:
        return "— (sin cita)"
    return f"{cita.get('id_fuente')} · {cita.get('campo')} · “{cita.get('pasaje')}”"


def claims_html(card: dict | None, check: bool) -> str:
    """Claims grouped by type, each with its citations, so a hypothesis never reads as a fact.

    With `check`, every citation is looked up in its source like the guard does (✓ / ✗).
    """
    blocks = []
    for kind, claims in claims_by_type(card):
        _icon, label, meaning = CLAIM_STYLE[kind]
        for claim in claims:
            cites = []
            for cita in claim.get("citas") or []:
                source = official.get(cita.get("id_fuente"))  # World Bank / USGS: country, year, unit
                cites.append({"label": citation_text(cita),
                              "found": citation_found(news, cita, official) if check else None,
                              "context": evidence_context(source) if source is not None else None})
            blocks.append(claim_html(f"{label} · {meaning}", claim["texto"], cites))
    return "".join(blocks)


def show_answer(result) -> None:
    """A query answer (DraftResult) exactly as the guard left it."""
    if result.source == "error":
        st.markdown(alert_html("No se pudo consultar el modelo (falta LLM_API_KEY o falló el proveedor). "
                               "No se muestra ninguna respuesta.", "Error"), unsafe_allow_html=True)
        return
    out = result.output.model_dump()
    for alerta in out["alertas"]:
        st.markdown(alert_html(f"{alerta}. La fuente se trata como dato, nunca como instrucción."), unsafe_allow_html=True)
    if result.source == "offline_miss":
        st.markdown(abstention_html("Sin respuesta en caché.", "Modo sin internet: esta consulta no está en la caché, "
                                    "así que no hay respuesta guardada. No se inventa una.", "T10 · sin internet"),
                    unsafe_allow_html=True)
    elif out["abstencion"]:
        st.markdown(abstention_html("Sin respuesta.", out["motivo_abstencion"] or "La evidencia no alcanza."),
                    unsafe_allow_html=True)
    elif out["borrador"]:
        low, high = ANSWER_LIMIT
        words = word_count(out["borrador"])
        st.markdown(lead_html(out["borrador"]), unsafe_allow_html=True)
        st.caption(f"{words} palabras · rango {low}–{high} · "
                   + ("dentro del límite" if low <= words <= high else "fuera del límite"))
    elif violations := getattr(getattr(result, "report", None), "violations", None):
        # The guard removed the running text: say so, and show only what kept its citation.
        st.markdown(alert_html(" · ".join(v[:1].upper() + v[1:] for v in violations) + ". Se muestran solo las afirmaciones que conservan su cita.",
                               "Guard · texto retirado"), unsafe_allow_html=True)
    if html := claims_html(out, check=False):
        st.markdown(section_html("Afirmaciones con su cita") + html, unsafe_allow_html=True)
    if out["contradicciones"]:
        st.markdown(contradictions_html(out["contradicciones"], citation_text), unsafe_allow_html=True)
    if out["verificaciones_pendientes"]:
        st.markdown(section_html("Qué falta comprobar")
                    + "".join(check_html(p) for p in out["verificaciones_pendientes"]), unsafe_allow_html=True)


# Callbacks run before the script, so they may move the views and the widgets' values.
def go(view: str) -> None:
    st.session_state.vista = view


def ask(question: str) -> None:
    st.session_state.vista = "Consulta"
    st.session_state.consulta_q = question
    st.session_state.run_q = question


def ask_from_sidebar() -> None:
    if question := (st.session_state.get("mini_q") or "").strip():
        ask(question)
    else:
        go("Consulta")  # an empty box still takes the editor to the query view
    st.session_state.mini_q = ""


def open_review(case_id: str) -> None:
    st.session_state.vista = "Revisión"
    st.session_state.review_case = case_id


st.set_page_config(page_title="Copiloto TVN", page_icon="📰", layout="wide", initial_sidebar_state="auto")
st.markdown(CSS, unsafe_allow_html=True)

news, source_path = load_news()
has_synthetic = bool("sintetico" in news and news["sintetico"].fillna(False).any())
scored = load_scores()
inbox, cards, cards_path = load_inbox(reviews_key())
_manifest = load_manifest()
DATA_CUT = to_panama(pd.Timestamp(_manifest["fecha_corte_UTC"])) if _manifest else None
cards_by_cluster = {c["cluster_id"]: c for c in cards if c.get("cluster_id")}
official = load_official()
n_events = scored["cluster_id"].nunique() if not scored.empty else 0

with st.sidebar:
    st.markdown(brand_html(), unsafe_allow_html=True)
    st.write("")
    st.radio("Sección", VIEWS, key="vista", label_visibility="collapsed")
    st.markdown(section_html("Preguntar"), unsafe_allow_html=True)
    with st.form("mini_ask", border=False):
        st.text_input("Pregunta en español", key="mini_q", placeholder="Pregunta en español",
                      label_visibility="collapsed")
        st.form_submit_button("Preguntar →", on_click=ask_from_sidebar, width="stretch")
    # One block with what the editor must always see: offline or online, data cut, corpus and data source.
    st.markdown(header_html(OFFLINE, source_path, len(news), n_events, DATA_CUT, has_synthetic),
                unsafe_allow_html=True)

vista = st.session_state.get("vista", "Mesa")
if OFFLINE:
    # T10: every view says it, not only the sidebar (collapsed on a phone).
    st.warning("Sin internet (OFFLINE=1, T10): nada llama a la red; el modelo se sirve solo desde la caché "
               "y una consulta sin caché se abstiene.")


def render_ficha(row: pd.Series, cluster_id: str) -> None:
    card = cards_by_cluster.get(cluster_id)
    sources = cluster_sources(news, cluster_id)
    eyebrow = f"Ficha #{int(row['posicion']):02d} · {row['tema'] or '— (sin dato)'} · " + (
        card["id_caso"] if card else "sin ficha generada (J-12)")
    meta = [
        f"{evidence_mark(row['estado_evidencia'])} evidencia {row['estado_evidencia']}",
        records_label(row["n_registros"], row["n_procedencias_independientes"]),
        f"U desde {urgency_basis_label(row['base_urgencia'])} {to_panama(row['fecha_referencia_urgencia'])}",
        "solo titular/metadatos" if headline_only(sources) else "",
        "sintético" if row["sintetico"] else "",
        "recirculada" if row["recirculada"] else "",
        f"revisión: {row['estado_revision']}" if pd.notna(row["estado_revision"]) else "",
    ]
    proposed = row["titulo_propuesto"] if pd.notna(row["titulo_propuesto"]) else None
    st.markdown(ficha_head_html(eyebrow, headline_label(row["titular"]), row["P"], row["rango"], meta, proposed),
                unsafe_allow_html=True)
    for alerta in (card or {}).get("alertas") or []:
        st.markdown(alert_html(f"{alerta}. La fuente se trata como dato, nunca como instrucción."),
                    unsafe_allow_html=True)
    abstained = bool(card and card.get("abstencion"))
    if abstained:
        st.markdown(abstention_html("El sistema se abstuvo.", f"{card.get('motivo_abstencion') or ''} No hay borrador: "
                                    "la evidencia no alcanza y no se rellena con texto inventado."), unsafe_allow_html=True)
    else:
        st.markdown(action_html(action_for(row["estado_evidencia"], card, bool(row["recirculada"]))),
                    unsafe_allow_html=True)
    if card and card.get("enfoque_interes_publico"):
        st.markdown(section_html("Qué se reporta") + lead_html(card["enfoque_interes_publico"], "ctvn-draft"),
                    unsafe_allow_html=True)

    backed, missing_col = st.columns(2, gap="large")
    with backed:
        html = claims_html(card, check=True)
        if not html:
            if card is None:
                html = note_html("Sin afirmaciones generadas todavía. Titulares de las fuentes, tal cual:") + "".join(
                    note_html(f"{item.id_noticia} · titulo · {item.titulo}") for item in sources.itertuples())
            elif abstained:
                html = note_html("Nada todavía: la evidencia no alcanza para afirmar algo con cita.")
            else:
                html = note_html("Nada respaldado todavía: no hay afirmaciones con cita.")
        st.markdown(section_html("Qué está respaldado") + html, unsafe_allow_html=True)
    with missing_col:
        missing = list((card or {}).get("verificaciones_pendientes") or [])
        if not row["hay_fuente_oficial"]:
            missing.append("Sin fuente oficial vinculada (Banco Mundial o USGS)"
                           + ("." if row["contexto_disponible"] else "; el contexto oficial (B-14) aún no existe."))
        if row["n_procedencias_independientes"] < 2:
            missing.append("Una sola procedencia independiente: falta corroboración.")
        if n_contra := len((card or {}).get("contradicciones") or []):
            missing.append(f"{n_contra} contradicción(es) entre fuentes: verificación pendiente (abajo).")
        st.markdown(section_html("Qué falta comprobar") + "".join(check_html(m) for m in dict.fromkeys(missing)),
                    unsafe_allow_html=True)
        if questions := (card or {}).get("preguntas_investigacion"):
            st.markdown(section_html("Preguntas de investigación") + "".join(note_html(q) for q in questions),
                        unsafe_allow_html=True)

    if contradictions := (card or {}).get("contradicciones"):
        st.markdown(contradictions_html(contradictions, citation_text), unsafe_allow_html=True)

    st.markdown(section_html("Por qué está arriba") + score_html(component_points(row)), unsafe_allow_html=True)
    st.caption(f"P = {row['P']:.1f} · reglas {row['version_reglas']} · U medida desde "
               f"{urgency_basis_label(row['base_urgencia'])}, {to_panama(row['fecha_referencia_urgencia'])}.")
    if card and (card.get("puntaje") or {}).get("valores_de_ejemplo"):
        st.caption(f"La ficha de ejemplo trae P = {card['puntaje']['P']:.1f}; aquí se muestra el de score.py.")

    if card and not abstained:
        st.markdown(section_html("Borrador para revisión"), unsafe_allow_html=True)
        drafts = {d["tarea"]: d for d in draft_rows(card)}
        names = {"brief": "Brief", "guion": "Guion 45–60 s", "copy": "Copy"}
        task = st.segmented_control("Formato del borrador", list(names), format_func=names.get, default="brief",
                                    key=f"fmt_{cluster_id}", label_visibility="collapsed") or "brief"
        draft = drafts[task]
        if draft["texto"] is None:
            st.markdown(note_html("No generado."), unsafe_allow_html=True)
        else:
            st.markdown(lead_html(draft["texto"], "ctvn-draft"), unsafe_allow_html=True)
            fits = "dentro del límite" if draft["dentro"] else "fuera del límite"
            st.caption(f"{draft['etiqueta']} · {draft['palabras']} palabras · rango {draft['min']}–{draft['max']} · {fits}")
    elif card is None:
        st.markdown(note_html("Este evento todavía no tiene ficha ni borrador (se generan con make demo-cache, J-12)."),
                    unsafe_allow_html=True)
    if card:
        st.write("")
        st.button(f"Revisar la ficha {card['id_caso']} →", on_click=open_review, args=(card["id_caso"],),
                  key=f"rev_{cluster_id}")

    with st.expander(f"Quién lo reporta · {len(sources)} registro(s)"):
        st.dataframe(pd.DataFrame({
            "ID": sources["id_noticia"],
            "Medio": sources["medio"],
            "Procedencia": sources["procedencia_id"].fillna("— (sin dato)"),
            "Origen": sources["origen"],
            "Alcance": sources["alcance_texto"],
            "Publicación (Panamá)": sources["fecha_publicacion"].map(to_panama),
            "Detección (Panamá)": sources["fecha_deteccion"].map(to_panama),
            "URL": sources["url"],
        }), hide_index=True, width="stretch", column_config={"URL": st.column_config.LinkColumn("URL")})


def view_mesa() -> None:
    states = inbox["estado_evidencia"].value_counts() if not inbox.empty else pd.Series(dtype=int)
    st.markdown(page_head_html("Prioridad de hoy", [
        f"{len(news):,} noticias · {n_events:,} eventos",
        f"{int((inbox['rango'] == 'alto').sum()) if not inbox.empty else 0:,} en rango alto · "
        f"{int(states.get('suficiente para el borrador', 0)):,} ■ · {int(states.get('parcial', 0)):,} ◧ · "
        f"{int(states.get('insuficiente', 0)):,} □",
        "P = 30R + 25I + 20U + 15N + 10E · determinista, sin LLM",
    ]), unsafe_allow_html=True)
    if inbox.empty:
        st.markdown(note_html("Todavía no hay clusters para priorizar."), unsafe_allow_html=True)
        return
    bar_filters, _, bar_ask = st.columns([2, 5, 2], vertical_alignment="center")
    with bar_filters.popover("Filtros"):
        temas = st.multiselect("Tema", sorted(inbox["tema"].dropna().unique()), placeholder="Todos")
        estados = st.multiselect("Estado de evidencia", EVIDENCE_STATES, placeholder="Todos")
        rangos = st.multiselect("Rango de P", SCORE_RANGES, placeholder="Todos")
        all_languages = sorted({code for langs in inbox["idiomas"] for code in langs})
        idiomas = st.multiselect(
            "Idioma", all_languages, default=[c for c in HEADLINE_LANGUAGES if c in all_languages],
            format_func=language_label, placeholder="Todos",
            help="Clusters con al menos una noticia en esos idiomas. No cambia el puntaje.")
        show_all = st.toggle("Ver todos (tabla)", help=f"Por defecto se muestran los {LIST_SIZE} de mayor P.")
    bar_ask.button("Preguntar →", on_click=go, args=("Consulta",), width="stretch", key="ask_mesa")
    if not inbox["contexto_disponible"].all():
        st.markdown(note_html("Sin contexto oficial todavía (contexto.parquet, B-14): I y E no incluyen "
                              "indicadores del Banco Mundial ni sismos del USGS."), unsafe_allow_html=True)

    view = filter_inbox(inbox, temas, estados, rangos, top_n=None if show_all else LIST_SIZE, idiomas=idiomas)
    by_id = inbox.set_index("cluster_id")
    left, right = st.columns([5, 8], gap="large")
    with left:
        if view.empty:
            st.markdown(note_html("Ningún evento con esos filtros."), unsafe_allow_html=True)
        elif show_all:
            table = pd.DataFrame({
                "#": view["posicion"], "P": view["P"], "Titular": view["titular"].fillna("— (sin titular)"),
                "Evidencia": view["estado_evidencia"], "Tema": view["tema"].fillna("— (sin dato)"),
                "Procedencias": view["n_procedencias_independientes"],
            })
            event = st.dataframe(table, hide_index=True, width="stretch", height=640, on_select="rerun",
                                 selection_mode="single-row", column_config={
                                     "P": st.column_config.ProgressColumn("P", min_value=0, max_value=100, format="%.1f")})
            # Only a new selection moves the case; otherwise it would stay pinned to this row.
            picked = view.iloc[event.selection.rows[0]]["cluster_id"] if event.selection.rows else None
            if (target := inbox_pick(picked, st.session_state.get("inbox_pick"))) is not None:
                st.session_state.ficha_sel = target
            st.session_state.inbox_pick = picked
            st.caption(f"{len(view):,} de {len(inbox):,} eventos. Elige una fila para ver su ficha.")
        else:
            ids = list(view["cluster_id"])
            # The radio's state is dropped while another view is shown; ficha_sel remembers the case.
            if st.session_state.get("sel_cluster") not in ids:
                st.session_state.sel_cluster = st.session_state.get("ficha_sel") if st.session_state.get("ficha_sel") in ids else ids[0]

            def caption(c: str) -> str:
                r = by_id.loc[c]
                extra = [m for m in ("recirculada" if r["recirculada"] else "", "sintético" if r["sintetico"] else "",
                                     f"{r['alertas']} alerta(s)" if r["alertas"] else "") if m]
                return md_escape(" · ".join([f"{int(r['posicion']):02d}", f"P {r['P']:.1f}",
                                             f"{evidence_mark(r['estado_evidencia'])} {r['estado_evidencia']}",
                                             str(r["tema"] or "— (sin dato)"),
                                             f"{int(r['n_procedencias_independientes'])} proc.", *extra]))
            st.radio("Eventos priorizados", ids, key="sel_cluster", label_visibility="collapsed",
                     format_func=lambda c: md_escape(headline_label(by_id.loc[c, "titular"])),
                     captions=[caption(c) for c in ids])
            st.session_state.ficha_sel = st.session_state.sel_cluster
            st.caption(f"{len(view)} de {len(inbox):,} eventos · ■ suficiente · ◧ parcial · □ insuficiente")
    with right:
        selected = st.session_state.get("ficha_sel")
        if selected not in by_id.index:
            selected = view["cluster_id"].iloc[0] if not view.empty else inbox.sort_values("posicion")["cluster_id"].iloc[0]
        render_ficha(by_id.loc[selected], selected)


def view_consulta() -> None:
    _, mid, _ = st.columns([1, 6, 1])
    with mid:
        st.markdown(page_head_html("Pregúntale al corpus", [
            "cada afirmación con su cita", "sin evidencia, se abstiene",
            "sin internet: solo caché" if OFFLINE else f"{model_name()} · temperatura 0",
        ]), unsafe_allow_html=True)
        st.write("")
        with st.form("consulta", border=False):
            text, send = st.columns([5, 1.7], vertical_alignment="bottom")
            question = text.text_input("Pregunta en español", key="consulta_q",
                                       placeholder="¿Cuál fue la inflación de Panamá en 2023?")
            sent = send.form_submit_button("Consultar →", type="primary", width="stretch")
        if queries := pitch_queries():
            st.markdown(section_html("Consultas del pitch · ya en caché"), unsafe_allow_html=True)
            with st.container(key="pitch"):
                for i, q in enumerate(queries, 1):
                    st.button(f"{i:02d} {q}", key=f"pq_{i}", on_click=ask, args=(q,), width="stretch")
        pending = question.strip() if sent and question.strip() else st.session_state.pop("run_q", None)
        if pending:
            with st.status("Consultando el corpus…", expanded=True) as status:
                st.write("1 · Búsqueda en el corpus (TF-IDF por raíces, reproducible)")
                found = load_search().search(pending)
                if found.hits:
                    st.write(f"2 · {len(found.hits)} pasajes encontrados · redactando con citas "
                             + ("desde la caché" if OFFLINE else "(caché primero, luego el modelo)"))
                else:
                    st.write("2 · Sin evidencia: no se llama al modelo")
                answer = answer_question(pending, found.evidence)  # no evidence → abstains without the model
                report = getattr(answer, "report", None)
                if report is not None and getattr(report, "claims_received", 0):
                    st.write(f"3 · Guard: {report.claims_kept}/{report.claims_received} afirmaciones y "
                             f"{report.citations_kept}/{report.citations_received} citas pasan")
                origin = {"cache": "caché", "llm": "modelo", "sin_evidencia": "sin llamar al modelo",
                          "offline_miss": "sin internet y sin caché", "error": "error"}.get(answer.source, answer.source)
                timing = f" · {answer.latency_s:.1f} s" if answer.latency_s else ""
                status.update(label=f"Listo · origen: {origin}{timing}", state="complete", expanded=False)
            st.session_state.last_answer = {"q": pending, "hits": found.hits, "answer": answer, "origin": origin + timing}
        last = st.session_state.get("last_answer")
        if not last:
            st.markdown(note_html("Escribe una pregunta o elige una consulta del pitch. Cada afirmación sale con "
                                  "su cita; si la evidencia no alcanza, el sistema se abstiene."), unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ctvn-eyebrow" style="margin-top:22px">// Respuesta · origen: '
                        f'{escape(last["origin"])}</div>', unsafe_allow_html=True)
            show_answer(last["answer"])
            if last["hits"]:
                with st.expander(f"Evidencia encontrada · {len(last['hits'])} pasajes (búsqueda J-06)"):
                    st.dataframe(pd.DataFrame([{"ID": h.id_evidencia, "Campo": h.campo, "Pasaje": h.texto,
                                                "Fuente · contexto": evidence_context(h.evidence),
                                                "Similitud": h.score} for h in last["hits"]]),
                                 hide_index=True, width="stretch")
        if saved := query_cards(cards):
            with st.expander(f"Consultas guardadas en las fichas · {len(saved)}"):
                for qcard in saved:
                    st.markdown(f"**{md_escape(qcard['consulta'])}**" + (" · sintético" if qcard.get("sintetico") else ""))
                    if qcard.get("abstencion"):
                        st.markdown(note_html(f"Sin respuesta (abstención): {qcard.get('motivo_abstencion')}"),
                                    unsafe_allow_html=True)
                    else:
                        st.markdown(note_html((qcard.get("borrador") or {}).get("brief") or "—"), unsafe_allow_html=True)


def view_revision() -> None:
    st.markdown(page_head_html("Revisión", [
        "una persona decide cada estado", "el registro solo se agrega, nunca se reescribe",
        "aprobar como borrador no es publicar",
    ]), unsafe_allow_html=True)
    if flash := st.session_state.pop("review_saved", None):
        st.success(flash)
    if not cards:
        st.markdown(note_html("Todavía no hay fichas para revisar (se generan con make demo-cache, J-12)."),
                    unsafe_allow_html=True)
        return
    rank = dict(zip(inbox["cluster_id"], inbox["posicion"]))
    by_case = {c["id_caso"]: c for c in sorted(
        cards, key=lambda c: (rank.get(c.get("cluster_id"), float("inf")), c["id_caso"]))}
    if st.session_state.get("review_case") not in by_case:
        # Last case the editor chose wins over the Ficha link: never jump to another card.
        remembered = st.session_state.get("review_case_pick")
        linked = cards_by_cluster.get(st.session_state.get("ficha_sel"), {}).get("id_caso")
        st.session_state.review_case = next(c for c in (remembered, linked, next(iter(by_case))) if c in by_case)
    left, right = st.columns([7, 5], gap="large")
    with left:
        case_id = st.selectbox("Ficha", list(by_case), key="review_case", format_func=lambda i: case_label(by_case[i]),
                               filter_mode="contains")
        st.session_state.review_case_pick = case_id
        rcard = by_case[case_id]
        current = rcard.get("estado_revision") or "nuevo"
        who = f" · {rcard['revisor']} · {panama_time(rcard.get('fecha_revision'))}" if rcard.get("revisor") else ""
        st.markdown(f'<div class="ctvn-meta"><span>Estado actual: {escape(current)}{escape(who)}</span></div>',
                    unsafe_allow_html=True)
        with st.form("revision", border=False):
            # Keyed per case so the widget keeps its identity when the current state changes.
            state_key = f"review_state_{case_id}"
            if st.session_state.get(state_key) not in REVIEW_STATES:
                st.session_state[state_key] = current if current in REVIEW_STATES else REVIEW_STATES[0]
            new_state = st.radio("Nuevo estado", REVIEW_STATES, horizontal=True, key=state_key)
            reviewer = st.text_input("Persona revisora", placeholder="Nombre de quien revisa")
            note = st.text_area("Nota", placeholder="Por qué se decide esto (opcional)")
            submitted = st.form_submit_button("Guardar decisión →", type="primary")
        if submitted:
            if not reviewer.strip():
                st.error("Falta la persona revisora: toda decisión lleva quién la tomó.")
            else:
                record = append_review(case_id, new_state, reviewer, note.strip())
                st.session_state.review_saved = (
                    f"Guardado: {case_id} → {record['estado_revision']} · {record['revisor']} · "
                    f"{panama_time(record['fecha_revision'])}")
                st.rerun()
        records, skipped = read_reviews()
        if history := case_history(records, case_id):
            st.markdown(section_html("Historial de esta ficha"), unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([{
                "Fecha (Panamá)": panama_time(r.get("fecha_revision")), "Estado": r["estado_revision"],
                "Persona revisora": r.get("revisor"), "Nota": r.get("nota") or "—",
            } for r in history]), hide_index=True, width="stretch")
        if skipped:
            st.warning(f"{skipped} línea(s) de revisiones.jsonl no son válidas y se ignoran.")
    with right:
        st.markdown(section_html("Copiar para Notion"), unsafe_allow_html=True)
        scored_row = scored.set_index("cluster_id").loc[rcard["cluster_id"]].to_dict() \
            if rcard.get("cluster_id") in set(scored["cluster_id"]) else None
        markdown = card_markdown(rcard, scored_row, action_for(
            rcard.get("estado_evidencia"), rcard, bool((scored_row or {}).get("recirculada", rcard.get("recirculada")))))
        st.caption("Copia con el ícono de la esquina y pega en la base \"Casos y evidencias\" (ADR-008).")
        st.code(markdown, language="markdown")
        st.download_button("Descargar .md", markdown, file_name=f"{case_id}.md", mime="text/markdown")


def view_datos() -> None:
    cached = cache_count(CACHE_DIR)
    st.markdown(page_head_html("Datos y calidad", [
        "sin internet (OFFLINE=1, T10): solo caché" if OFFLINE else "en línea: caché primero, luego el modelo",
        f"{cached} salidas del modelo guardadas", "licencias y SHA-256 en data/manifest.json",
    ]), unsafe_allow_html=True)
    if OFFLINE:
        st.markdown(note_html(f"Modo sin internet (OFFLINE=1, T10). Nada llama a la red: el modelo se sirve solo desde "
                              f"outputs/cache/ ({cached} salidas guardadas) y las consultas sin caché se abstienen."),
                    unsafe_allow_html=True)
    else:
        st.markdown(note_html(f"En línea: una consulta nueva va al modelo y su respuesta se guarda en outputs/cache/ "
                              f"({cached} salidas). Para la demo sin internet: OFFLINE=1 make demo."), unsafe_allow_html=True)

    manifest = load_manifest()
    if manifest is None:
        st.markdown(note_html("Todavía no hay data/manifest.json (B-10)."), unsafe_allow_html=True)
    else:
        origins = news_by_origin(manifest)
        st.markdown(tiles_html([
            ("Noticias", f"{sum(origins.values()):,}" if origins else "—",
             " · ".join(f"{k}: {v:,}" for k, v in origins.items())),
            ("Corte de datos", to_panama(pd.Timestamp(manifest["fecha_corte_UTC"])).replace(" (Panamá)", ""), "Panamá"),
            ("Archivos en el manifest", f"{len(manifest.get('archivos', []))}", ""),
        ]), unsafe_allow_html=True)
        st.caption("Corte en hora de Panamá; los archivos guardan UTC.")

        st.markdown(section_html("Fuentes y licencias"), unsafe_allow_html=True)
        catalog = load_catalog()
        if catalog:
            st.dataframe(sources_table(catalog), hide_index=True, width="stretch")
            st.caption("Del catálogo de datos (docs/notion/catalogo.csv, B-15). De TVN solo se guardan metadatos: "
                       "nunca el cuerpo, imágenes ni video.")
        else:
            st.caption("Sin catálogo todavía (docs/notion/catalogo.csv, B-15).")

        st.markdown(section_html("Archivos entregados"), unsafe_allow_html=True)
        st.dataframe(files_table(manifest), hide_index=True, width="stretch")
        if st.button("Verificar SHA-256 (make verify)"):
            problems = verify_messages(verify_manifest())
            if problems:
                st.error("La verificación encontró problemas:\n\n" + "\n".join(f"- {p}" for p in problems))
            else:
                st.success(f"Los {len(manifest['archivos'])} archivos coinciden con el SHA-256 del manifest.")
        with st.expander("Cómo reproducir los datos"):
            st.markdown("\n".join(f"1. `{step}`" for step in manifest.get("reproducir", [])))

    quality = load_quality()
    st.markdown(section_html("Reporte de calidad"), unsafe_allow_html=True)
    if quality:
        with st.expander("Ver outputs/reports/calidad.md (B-05)"):
            st.markdown(quality)
    else:
        st.caption("Sin reporte de calidad todavía (B-05).")

    with st.expander(f"Noticias del corpus · {len(news):,}"):
        order_key = news["fecha_deteccion"].fillna(news["fecha_publicacion"])
        corpus = news.assign(_order=order_key).sort_values("_order", ascending=False)
        st.dataframe(pd.DataFrame({
            "ID": corpus["id_noticia"],
            "Titular": corpus["titulo"],
            "Medio": corpus["medio"],
            "Tema": corpus["tema"],
            "Cluster": corpus["cluster_id"],
            "Publicación (Panamá)": corpus["fecha_publicacion"].map(to_panama),
            "Detección (Panamá)": corpus["fecha_deteccion"].map(to_panama),
            "Marcas": corpus.apply(flags, axis=1),
        }), hide_index=True, width="stretch")


{"Mesa": view_mesa, "Consulta": view_consulta, "Revisión": view_revision, "Datos": view_datos}[vista]()
