"""Copiloto TVN Streamlit UI (J-15 minimal redesign over C-12..C-16). Owner: Cristian; built with José.

A sidebar holds the navigation, a question box reachable from every view and the state the
editor must always see. Four views: Mesa (inbox and case card side by side), Preguntar,
Revisión and Fuentes y datos. Only the active view is drawn, so a click reruns one view, not five.
Reads data/processed/noticias.parquet when B has delivered it, otherwise the synthetic stub.
Data stays in UTC; times are converted to Panama time only for display.

Everything on screen is in product words (app/textos.py): no paths, flags, test codes or
function names. Citation IDs, which the challenge requires, stay visible but secondary.
Design checks: ISO 9241-110 (self-descriptive, conforms to expectations, error tolerant,
user in control) and 9241-112 (detectable, distinguishable, concise information).

With OFFLINE=1 nothing touches the network: LLM output is read only from
outputs/cache/ and the UI says so on every view (T10).
"""

import json
import os
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from app import textos as tx
from app.bandeja import (
    EVIDENCE_STATES, HEADLINE_LANGUAGES, SCORE_RANGES, build_inbox, filter_inbox, inbox_pick, language_label,
    load_cards, load_contexto,
)
from app.ficha import action_for, citation_found, cluster_sources, component_points, headline_only
from app.borrador import ANSWER_LIMIT, claims_by_type, draft_rows, evidence_context, query_cards, word_count
from src.generate.drafts import official_index
from src.generate.generate import model_name
from src.generate.guard import injection_in
from src.generate.query import answer_question
from src.search import load_index
from src.ingest.worldbank import read_indicators
from app.revision import card_markdown, case_history
from src.fichas import REVIEWS_PATH, append_review, apply_reviews, latest_reviews, read_reviews
from app.datos import (
    cache_count, files_table, load_catalog, load_manifest, load_quality, news_by_origin, sources_table,
    verify_messages,
)
from src.manifest import verify as verify_manifest
from app.estilo import (
    CSS, abstention_html, action_html, alert_html, brand_html, check_html, claim_html, contradictions_html,
    ficha_head_html, header_html, lead_html, loading_html, md_escape, note_html, page_head_html, score_html,
    section_html, tiles_html,
)
from src.score import score_clusters

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_PATH = ROOT / "data" / "processed" / "noticias.parquet"
STUB_PATH = ROOT / "data" / "stub" / "noticias_stub.parquet"
CACHE_DIR = ROOT / "outputs" / "cache"
OFFICIAL_DIR = ROOT / "data" / "processed"
PITCH_QUERIES_PATH = ROOT / "docs" / "demo" / "consultas_demo.txt"

OFFLINE = os.getenv("OFFLINE", "0") == "1"
VIEWS = {"Mesa": "Mesa", "Consulta": "Preguntar", "Revisión": "Revisión", "Datos": "Fuentes y datos"}
LIST_SIZE = 10  # rows in the Mesa list; "Ver la lista completa" opens the full, selectable table

# Written exactly as the challenge requires (stored as is; shown through tx.REVISION).
REVIEW_STATES = [
    "nuevo",
    "en revisión",
    "requiere evidencia",
    "aprobado como borrador",
    "descartado",
]


@st.cache_data(show_spinner=False)
def load_news() -> tuple[pd.DataFrame, str]:
    path = PROCESSED_PATH if PROCESSED_PATH.exists() else STUB_PATH
    return pd.read_parquet(path), path.relative_to(ROOT).as_posix()


@st.cache_data(show_spinner=False)  # U is measured against the corpus date (ADR-027), not the clock
def load_scores() -> pd.DataFrame:
    return score_clusters(load_news()[0], contexto=load_contexto())


@st.cache_data(show_spinner=False)
def load_inbox(reviews_key: str) -> tuple[pd.DataFrame, list[dict], str | None]:
    """Inbox and case cards with the latest review applied; recomputed only when the review log changes."""
    news, source_path = load_news()
    cards, cards_path = load_cards(news_from_stub=source_path == STUB_PATH.relative_to(ROOT).as_posix())
    cards = apply_reviews(cards, latest_reviews())  # the review log wins over the state in the file
    return build_inbox(load_scores(), news, cards), cards, cards_path


@st.cache_resource(show_spinner=False)
def load_official() -> dict:
    """World Bank and USGS items by ID, to check official citations like the guard does."""
    indicators = OFFICIAL_DIR / "indicadores.csv"
    events = OFFICIAL_DIR / "eventos.geojson"
    return official_index(
        read_indicators(indicators) if indicators.exists() else None,
        json.loads(events.read_text(encoding="utf-8")) if events.exists() else None,
    )


@st.cache_resource(show_spinner=False)
def load_search():
    """J-06 index over the same contract files the app reads."""
    return load_index()


@st.cache_data(show_spinner=False)
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


def flags(row: pd.Series) -> str:
    labels = []
    if row.get("sintetico", False):
        labels.append("de prueba")
    if row.get("recirculada", False):
        labels.append("vuelve a circular")
    if injection_in(row["titulo"] if isinstance(row["titulo"], str) else ""):  # same rule as the guard (J-11)
        labels.append("trae instrucciones para el sistema")
    return " · ".join(labels)


def source_name(id_fuente: str | None) -> str:
    """Who said it, in words: the outlet for a news item, the institution for official data."""
    item = official.get(id_fuente)
    if item is not None:
        return "Banco Mundial" if item.kind == "indicador" else "USGS"
    match = news.loc[news["id_noticia"] == id_fuente, "medio"]
    return str(match.iloc[0]) if not match.empty and pd.notna(match.iloc[0]) else "Fuente"


def cite(cita: dict, check: bool) -> dict:
    """A citation as the editor reads it ('telemetro.com · titular: “…”'), with its ID kept beside it."""
    source = official.get(cita.get("id_fuente"))  # World Bank / USGS: country, year, unit
    return {"label": f"{source_name(cita.get('id_fuente'))} · {tx.cita_fuente(cita.get('campo'))}: “{cita.get('pasaje')}”",
            "ident": cita.get("id_fuente"),
            "found": citation_found(news, cita, official) if check else None,
            "context": evidence_context(source) if source is not None else None}


def cite_text(cita: dict | None) -> str:
    if not cita:
        return "sin cita"
    return f"{source_name(cita.get('id_fuente'))} · {tx.cita_fuente(cita.get('campo'))}: “{cita.get('pasaje')}” ({cita.get('id_fuente')})"


def claims_html(card: dict | None, check: bool) -> str:
    """Claims grouped by type, each with its citations, so a hypothesis never reads as a fact."""
    return "".join(
        claim_html(tx.TIPO_AFIRMACION.get(kind, kind), claim["texto"], [cite(c, check) for c in claim.get("citas") or []])
        for kind, claims in claims_by_type(card) for claim in claims)


def show_answer(result) -> None:
    """A question's answer (DraftResult) exactly as the guard left it, explained in product words."""
    if result.source == "error":
        st.markdown(abstention_html("No pude responder ahora.", tx.motivo(result.output.motivo_abstencion),
                                    "Algo falló"), unsafe_allow_html=True)
        return
    out = result.output.model_dump()
    for alerta in out["alertas"]:
        st.markdown(alert_html(tx.alerta(alerta)), unsafe_allow_html=True)
    if result.source == "offline_miss":
        st.markdown(abstention_html("No tengo esta respuesta guardada.", tx.motivo(out["motivo_abstencion"]) +
                                    " Prueba con una de las preguntas sugeridas.", "Sin conexión"), unsafe_allow_html=True)
    elif out["abstencion"]:
        st.markdown(abstention_html("No encontré información sobre esto.", tx.motivo(out["motivo_abstencion"])),
                    unsafe_allow_html=True)
    elif out["borrador"]:
        _, high = ANSWER_LIMIT
        st.markdown(lead_html(out["borrador"]), unsafe_allow_html=True)
        st.caption(tx.palabras(word_count(out["borrador"]), high))
    else:
        reasons = [r for v in getattr(getattr(result, "report", None), "violations", []) if (r := tx.retiro(v))]
        if reasons:
            st.markdown(alert_html(" ".join(dict.fromkeys(reasons)) + " Te muestro solo los datos que sí tienen fuente.",
                                   "Control de calidad"), unsafe_allow_html=True)
    if html := claims_html(out, check=False):
        st.markdown(section_html("Datos con su fuente") + html, unsafe_allow_html=True)
    if out["contradicciones"]:
        st.markdown(contradictions_html(out["contradicciones"], cite_text), unsafe_allow_html=True)
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
        go("Consulta")  # an empty box still takes the editor to the question view
    st.session_state.mini_q = ""


def open_review(case_id: str) -> None:
    st.session_state.vista = "Revisión"
    st.session_state.review_case = case_id


st.set_page_config(page_title="Copiloto TVN", page_icon="📰", layout="wide", initial_sidebar_state="auto")
st.markdown(CSS, unsafe_allow_html=True)

boot = st.empty()
if "booted" not in st.session_state:  # a branded wait on the first load, not the framework's spinner
    boot.markdown(loading_html("Preparando la mesa", "Cargando las noticias y ordenándolas por prioridad…"),
                  unsafe_allow_html=True)
news, source_path = load_news()
has_synthetic = bool("sintetico" in news and news["sintetico"].fillna(False).any())
scored = load_scores()
inbox, cards, cards_path = load_inbox(reviews_key())
_manifest = load_manifest()
DATA_CUT = tx.fecha(_manifest["fecha_corte_UTC"]) if _manifest else None
cards_by_cluster = {c["cluster_id"]: c for c in cards if c.get("cluster_id")}
official = load_official()
n_events = scored["cluster_id"].nunique() if not scored.empty else 0
boot.empty()
st.session_state.booted = True

with st.sidebar:
    st.markdown(brand_html(), unsafe_allow_html=True)
    st.write("")
    st.radio("Sección", list(VIEWS), key="vista", format_func=VIEWS.get, label_visibility="collapsed")
    st.markdown(section_html("Preguntar"), unsafe_allow_html=True)
    with st.form("mini_ask", border=False):
        st.text_input("Tu pregunta", key="mini_q", placeholder="Escribe tu pregunta…", label_visibility="collapsed")
        st.form_submit_button("Preguntar →", on_click=ask_from_sidebar, width="stretch")
    # What the editor must always see: connection mode, corpus and the date of the data.
    st.markdown(header_html(OFFLINE, source_path, len(news), n_events, DATA_CUT, has_synthetic),
                unsafe_allow_html=True)

vista = st.session_state.get("vista", "Mesa")
if OFFLINE:
    # T10: every view says it, not only the sidebar (collapsed on a phone).
    st.warning("Modo sin internet: las respuestas salen de lo ya guardado y una pregunta nueva no se puede "
               "responder ahora.")


def render_ficha(row: pd.Series, cluster_id: str) -> None:
    card = cards_by_cluster.get(cluster_id)
    sources = cluster_sources(news, cluster_id)
    only_headline = headline_only(sources)
    meta = [
        tx.evidencia(row["estado_evidencia"]),
        tx.notas_y_fuentes(row["n_registros"], row["n_procedencias_independientes"]),
        ("Publicada el " if row["base_urgencia"] == "publicacion" else "Detectada el ")
        + tx.fecha(row["fecha_referencia_urgencia"]),
        "Solo tenemos el titular" if only_headline else "",
        "Vuelve a circular: no es nueva" if row["recirculada"] else "",
        "Incluye noticias de prueba" if row["sintetico"] else "",
        f"Revisión: {tx.REVISION.get(row['estado_revision'], row['estado_revision'])}"
        if pd.notna(row["estado_revision"]) else "",
    ]
    proposed = row["titulo_propuesto"] if pd.notna(row["titulo_propuesto"]) else None
    st.markdown(ficha_head_html(f"Prioridad n.º {int(row['posicion'])} · {tx.tema(row['tema'])}",
                                tx.limpiar_titular(row["titular"]), row["P"],
                                f"de 100 · {tx.PRIORIDAD.get(row['rango'], 'prioridad sin dato')}", meta, proposed),
                unsafe_allow_html=True)
    for alerta in (card or {}).get("alertas") or []:
        st.markdown(alert_html(tx.alerta(alerta)), unsafe_allow_html=True)
    abstained = bool(card and card.get("abstencion"))
    if abstained:
        st.markdown(abstention_html(
            "Sin borrador por ahora.",
            ("Solo tenemos el titular de esta noticia: no alcanza para escribir algo con respaldo. "
             if only_headline else "La evidencia no alcanza para escribir algo con respaldo. ")
            + "Hace falta la nota completa u otra fuente independiente.", "El sistema no inventa"),
            unsafe_allow_html=True)
    else:
        st.markdown(action_html(action_for(row["estado_evidencia"], card, bool(row["recirculada"]))),
                    unsafe_allow_html=True)
    if card and card.get("enfoque_interes_publico"):
        st.markdown(section_html("Por qué importa") + lead_html(card["enfoque_interes_publico"], "ctvn-draft"),
                    unsafe_allow_html=True)

    backed, missing_col = st.columns(2, gap="large")
    with backed:
        html = claims_html(card, check=True)
        if not html:
            if card is None:
                html = note_html("Todavía no hay afirmaciones redactadas. Los titulares, tal como salieron:") + "".join(
                    note_html(f"{item.medio}: {tx.limpiar_titular(item.titulo)}") for item in sources.itertuples())
            else:
                html = note_html("Nada todavía: no hay ninguna afirmación con fuente.")
        st.markdown(section_html("Lo que dicen las fuentes") + html, unsafe_allow_html=True)
    with missing_col:
        missing = list((card or {}).get("verificaciones_pendientes") or [])
        if not row["hay_fuente_oficial"]:
            missing.append("No hay un dato oficial que lo respalde (Banco Mundial o USGS).")
        if row["n_procedencias_independientes"] < 2:
            missing.append("Solo hay una fuente original: falta confirmarlo con otra.")
        if n_contra := len((card or {}).get("contradicciones") or []):
            missing.append(f"Hay {n_contra} versión(es) que no coinciden: revísalas abajo.")
        st.markdown(section_html("Qué falta comprobar") + "".join(check_html(m) for m in dict.fromkeys(missing)),
                    unsafe_allow_html=True)
        if questions := (card or {}).get("preguntas_investigacion"):
            st.markdown(section_html("Preguntas para investigar") + "".join(note_html(q) for q in questions),
                        unsafe_allow_html=True)

    if contradictions := (card or {}).get("contradicciones"):
        st.markdown(contradictions_html(contradictions, cite_text), unsafe_allow_html=True)

    points = component_points(row)
    for p in points:
        p["nombre"] = tx.COMPONENTE[p["clave"]]
    st.markdown(section_html("Por qué está arriba") + score_html(points), unsafe_allow_html=True)
    st.caption(f"Total: {row['P']:.1f} de 100. Lo calculan reglas fijas, no la IA.")
    with st.expander("Cómo se calcula"):
        st.markdown(
            f"Prioridad = 30 × relación con Panamá + 25 × impacto + 20 × urgencia + 15 × novedad + 10 × evidencia. "
            f"Cada parte va de 0 a 1. La urgencia se mide desde que la noticia "
            f"{'se publicó' if row['base_urgencia'] == 'publicacion' else 'se detectó'} "
            f"({tx.fecha(row['fecha_referencia_urgencia'])}) contra la fecha más reciente de los datos. "
            f"Una prioridad alta no autoriza a publicar: la evidencia se evalúa aparte.")

    if card and not abstained:
        st.markdown(section_html("Borrador para revisar"), unsafe_allow_html=True)
        drafts = {d["tarea"]: d for d in draft_rows(card)}
        task = st.segmented_control("Formato del borrador", list(tx.FORMATO), format_func=tx.FORMATO.get,
                                    default="brief", key=f"fmt_{cluster_id}", label_visibility="collapsed") or "brief"
        draft = drafts[task]
        if draft["texto"] is None:
            st.markdown(note_html("Este formato no se generó para este tema."), unsafe_allow_html=True)
        else:
            st.markdown(lead_html(draft["texto"], "ctvn-draft"), unsafe_allow_html=True)
            limit = tx.palabras(draft["palabras"], draft["max"])
            st.caption(limit if draft["dentro"] else f"{limit} · se pasa del límite")
    elif card is None:
        st.markdown(note_html("Este tema todavía no tiene borrador."), unsafe_allow_html=True)
    if card:
        st.write("")
        st.button("Marcar revisión →", on_click=open_review, args=(card["id_caso"],), key=f"rev_{cluster_id}",
                  type="primary")

    with st.expander(f"Ver {'la nota' if len(sources) == 1 else f'las {len(sources)} notas'} que lo reportan"):
        st.dataframe(pd.DataFrame({
            "Medio": sources["medio"],
            "Titular": sources["titulo"].map(tx.limpiar_titular),
            "Qué tenemos": sources["alcance_texto"].map(lambda a: tx.ALCANCE.get(a, a)),
            "Publicada": sources["fecha_publicacion"].map(tx.fecha),
            "Detectada": sources["fecha_deteccion"].map(tx.fecha),
            "Enlace": sources["url"],
        }), hide_index=True, width="stretch", column_config={"Enlace": st.column_config.LinkColumn("Enlace")})
    with st.expander("Detalles técnicos"):
        st.markdown(note_html(
            f"Ficha {card['id_caso'] if card else '—'} · evento {cluster_id} · titular {row['id_titular'] or '—'} · "
            f"reglas {row['version_reglas']} · notas: {', '.join(sources['id_noticia'])}"), unsafe_allow_html=True)


def view_mesa() -> None:
    states = inbox["estado_evidencia"].value_counts() if not inbox.empty else pd.Series(dtype=int)
    st.markdown(page_head_html("Prioridad de hoy", [
        f"{len(news):,} noticias agrupadas en {n_events:,} eventos",
        f"{int((inbox['rango'] == 'alto').sum()) if not inbox.empty else 0:,} de prioridad alta · "
        f"{int(states.get('suficiente para el borrador', 0)):,} con evidencia suficiente",
        "Ordenadas por reglas fijas, no por la IA",
    ]), unsafe_allow_html=True)
    if inbox.empty:
        st.markdown(note_html("Todavía no hay noticias para ordenar."), unsafe_allow_html=True)
        return
    bar_filters, _, bar_ask = st.columns([2, 5, 2], vertical_alignment="center")
    with bar_filters.popover("Filtrar"):
        temas = st.multiselect("Tema", sorted(inbox["tema"].dropna().unique()), format_func=tx.tema, placeholder="Todos")
        estados = st.multiselect("Evidencia", EVIDENCE_STATES, format_func=tx.evidencia, placeholder="Todas")
        rangos = st.multiselect("Prioridad", SCORE_RANGES, format_func=lambda r: tx.PRIORIDAD.get(r, r).capitalize(),
                                placeholder="Todas")
        all_languages = sorted({code for langs in inbox["idiomas"] for code in langs})
        idiomas = st.multiselect(
            "Idioma de las notas", all_languages, default=[c for c in HEADLINE_LANGUAGES if c in all_languages],
            format_func=lambda c: language_label(c).capitalize(), placeholder="Todos",
            help="Muestra los eventos con al menos una nota en esos idiomas. No cambia la prioridad.")
        show_all = st.toggle("Ver la lista completa", help=f"Por defecto se muestran los {LIST_SIZE} más prioritarios.")
    bar_ask.button("Preguntar →", on_click=go, args=("Consulta",), width="stretch", key="ask_mesa")
    if not inbox["contexto_disponible"].all():
        st.markdown(note_html("Todavía no hay datos oficiales vinculados: la prioridad no incluye indicadores ni sismos."),
                    unsafe_allow_html=True)

    view = filter_inbox(inbox, temas, estados, rangos, top_n=None if show_all else LIST_SIZE, idiomas=idiomas)
    by_id = inbox.set_index("cluster_id")
    left, right = st.columns([5, 8], gap="large")
    with left:
        if view.empty:
            st.markdown(note_html("Ningún evento cumple esos filtros. Prueba quitando alguno."), unsafe_allow_html=True)
        elif show_all:
            table = pd.DataFrame({
                "N.º": view["posicion"], "Prioridad": view["P"], "Titular": view["titular"].map(tx.limpiar_titular),
                "Evidencia": view["estado_evidencia"].map(tx.evidencia), "Tema": view["tema"].map(tx.tema),
                "Fuentes": view["n_procedencias_independientes"],
            })
            event = st.dataframe(table, hide_index=True, width="stretch", height=640, on_select="rerun",
                                 selection_mode="single-row", column_config={
                                     "Prioridad": st.column_config.ProgressColumn("Prioridad", min_value=0, max_value=100,
                                                                                  format="%.1f")})
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
                extra = [m for m in ("vuelve a circular" if r["recirculada"] else "", "de prueba" if r["sintetico"] else "",
                                     "trae una alerta" if r["alertas"] else "") if m]
                return md_escape(" · ".join([f"Prioridad {r['P']:.1f}", tx.tema(r["tema"]),
                                             tx.evidencia(r["estado_evidencia"]).lower(),
                                             tx.notas_y_fuentes(r["n_registros"], r["n_procedencias_independientes"]),
                                             *extra]))
            st.radio("Eventos priorizados", ids, key="sel_cluster", label_visibility="collapsed",
                     format_func=lambda c: md_escape(tx.limpiar_titular(by_id.loc[c, "titular"])),
                     captions=[caption(c) for c in ids])
            st.session_state.ficha_sel = st.session_state.sel_cluster
            st.caption(f"Los {len(view)} más prioritarios de {len(inbox):,}. Para ver todos: Filtrar → Ver la lista completa.")
    with right:
        selected = st.session_state.get("ficha_sel")
        if selected not in by_id.index:
            selected = view["cluster_id"].iloc[0] if not view.empty else inbox.sort_values("posicion")["cluster_id"].iloc[0]
        render_ficha(by_id.loc[selected], selected)


def view_consulta() -> None:
    _, mid, _ = st.columns([1, 6, 1])
    with mid:
        st.markdown(page_head_html("¿Qué quieres saber?", [
            "Respondo solo con lo que dicen las fuentes", "Cada dato lleva su fuente",
            "Si no hay información, te lo digo",
        ]), unsafe_allow_html=True)
        st.write("")
        with st.form("consulta", border=False):
            text, send = st.columns([5, 1.7], vertical_alignment="bottom")
            question = text.text_input("Tu pregunta", key="consulta_q",
                                       placeholder="Por ejemplo: ¿cuál fue la inflación de Panamá en 2024?")
            sent = send.form_submit_button("Preguntar →", type="primary", width="stretch")
        if queries := pitch_queries():
            st.markdown(section_html("Prueba con estas preguntas"), unsafe_allow_html=True)
            with st.container(key="pitch"):
                for i, q in enumerate(queries, 1):
                    st.button(f"{i:02d} {q}", key=f"pq_{i}", on_click=ask, args=(q,), width="stretch")
        if sent and not question.strip():
            st.markdown(note_html("Escribe una pregunta primero."), unsafe_allow_html=True)
        pending = question.strip() if sent and question.strip() else st.session_state.pop("run_q", None)
        if pending:
            # A real stage per step (search, writing, checking), never a clock-driven bar.
            with st.status(f"Buscando en {len(news):,} noticias y datos oficiales…", expanded=True) as status:
                bar = st.progress(0.1)
                found = load_search().search(pending)
                bar.progress(0.4)
                if found.hits:
                    st.write(f"Encontré {len(found.hits)} fragmentos que hablan del tema.")
                    status.update(label="Escribiendo la respuesta con sus fuentes…")
                else:
                    st.write("No encontré nada sobre este tema en las fuentes.")
                answer = answer_question(pending, found.evidence)  # no evidence → abstains without the model
                bar.progress(0.8)
                report = getattr(answer, "report", None)
                if report is not None and getattr(report, "claims_received", 0):
                    st.write(f"Revisé que cada dato tenga su fuente: {report.claims_kept} de "
                             f"{report.claims_received} pasaron.")
                bar.progress(1.0)
                origin = tx.ORIGEN_RESPUESTA.get(answer.source, "respuesta")
                timing = f" · {answer.latency_s:.1f} s" if answer.latency_s else ""
                if answer.source in ("offline_miss", "error"):  # say what happened; a failure is never "Listo ✓"
                    status.update(label="Sin conexión: esta pregunta no está guardada" if answer.source == "offline_miss"
                                  else "El servicio de IA no respondió", state="error", expanded=False)
                else:
                    status.update(label=f"Listo · {origin}{timing}", state="complete", expanded=False)
            st.session_state.last_answer = {"q": pending, "hits": found.hits, "answer": answer, "origin": origin + timing}
        last = st.session_state.get("last_answer")
        if not last:
            st.markdown(note_html("Escribe tu pregunta o elige una de la lista. Cada dato sale con su fuente; "
                                  "si no hay información, te lo digo en vez de inventar."), unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="ctvn-ask">Respuesta a «{escape(last["q"])}»</div>', unsafe_allow_html=True)
            show_answer(last["answer"])
            if last["hits"]:
                with st.expander(f"Ver los {len(last['hits'])} fragmentos que encontré"):
                    st.dataframe(pd.DataFrame([{
                        "Fuente": source_name(h.id_evidencia), "Dónde": tx.cita_fuente(h.campo), "Texto": h.texto,
                        "Contexto": evidence_context(h.evidence), "Coincidencia": round(h.score, 2), "ID": h.id_evidencia,
                    } for h in last["hits"]]), hide_index=True, width="stretch")
        if saved := query_cards(cards):
            with st.expander(f"Preguntas respondidas antes · {len(saved)}"):
                for qcard in saved:
                    st.markdown(f"**{md_escape(qcard['consulta'])}**" + (" · de prueba" if qcard.get("sintetico") else ""))
                    if qcard.get("abstencion"):
                        st.markdown(note_html(f"Sin respuesta: {tx.motivo(qcard.get('motivo_abstencion'))}"),
                                    unsafe_allow_html=True)
                    else:
                        st.markdown(note_html((qcard.get("borrador") or {}).get("brief") or "—"), unsafe_allow_html=True)


def case_title(card: dict) -> str:
    """A case as the editor knows it: its headline (or the AI's suggested title) and where it stands."""
    row = inbox.loc[inbox["cluster_id"] == card.get("cluster_id")]
    title = card.get("titulo") or (row["titular"].iloc[0] if not row.empty else None) or card.get("consulta")
    state = tx.REVISION.get(card.get("estado_revision") or "nuevo", "Nuevo")
    return f"{tx.limpiar_titular(title)} — {state}"


def view_revision() -> None:
    st.markdown(page_head_html("Revisión", [
        "Tú decides el estado de cada tema", "Queda registrado con tu nombre y la hora",
        "Aprobar un borrador no lo publica",
    ]), unsafe_allow_html=True)
    if flash := st.session_state.pop("review_saved", None):
        st.success(flash)
    if not cards:
        st.markdown(note_html("Todavía no hay temas para revisar."), unsafe_allow_html=True)
        return
    rank = dict(zip(inbox["cluster_id"], inbox["posicion"]))
    by_case = {c["id_caso"]: c for c in sorted(
        cards, key=lambda c: (rank.get(c.get("cluster_id"), float("inf")), c["id_caso"]))}
    if st.session_state.get("review_case") not in by_case:
        # Last case the editor chose wins over the Mesa link: never jump to another card.
        remembered = st.session_state.get("review_case_pick")
        linked = cards_by_cluster.get(st.session_state.get("ficha_sel"), {}).get("id_caso")
        st.session_state.review_case = next(c for c in (remembered, linked, next(iter(by_case))) if c in by_case)
    left, right = st.columns([7, 5], gap="large")
    with left:
        case_id = st.selectbox("Tema a revisar", list(by_case), key="review_case",
                               format_func=lambda i: case_title(by_case[i]), filter_mode="contains")
        st.session_state.review_case_pick = case_id
        rcard = by_case[case_id]
        current = rcard.get("estado_revision") or "nuevo"
        who = f"{rcard['revisor']} · {tx.fecha(rcard.get('fecha_revision'))}" if rcard.get("revisor") else "nadie lo ha revisado"
        st.markdown(f'<div class="ctvn-meta"><span>Ahora: {escape(tx.REVISION.get(current, current))}</span>'
                    f'<span>{escape(who)}</span></div>', unsafe_allow_html=True)
        with st.form("revision", border=False):
            # Keyed per case so the widget keeps its identity when the current state changes.
            state_key = f"review_state_{case_id}"
            if st.session_state.get(state_key) not in REVIEW_STATES:
                st.session_state[state_key] = current if current in REVIEW_STATES else REVIEW_STATES[0]
            new_state = st.radio("Nuevo estado", REVIEW_STATES, horizontal=True, key=state_key, format_func=tx.REVISION.get)
            reviewer = st.text_input("Tu nombre", placeholder="Quién revisa")
            note = st.text_area("Nota (opcional)", placeholder="¿Por qué decides esto?")
            submitted = st.form_submit_button("Guardar decisión →", type="primary")
        if submitted:
            if not reviewer.strip():
                st.error("Escribe tu nombre: cada decisión lleva quién la tomó.")
            else:
                record = append_review(case_id, new_state, reviewer, note.strip())
                st.session_state.review_saved = (
                    f"Guardado: «{tx.REVISION[record['estado_revision']]}», por {record['revisor']}, "
                    f"el {tx.fecha(record['fecha_revision'])}.")
                st.rerun()
        records, skipped = read_reviews()
        if history := case_history(records, case_id):
            st.markdown(section_html("Historial de este tema"), unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([{
                "Fecha": tx.fecha(r.get("fecha_revision")), "Estado": tx.REVISION.get(r["estado_revision"], r["estado_revision"]),
                "Persona": r.get("revisor"), "Nota": r.get("nota") or "—",
            } for r in history]), hide_index=True, width="stretch")
        if skipped:
            st.warning(f"{skipped} registro(s) del historial no se pudieron leer y se ignoran.")
    with right:
        st.markdown(section_html("Llevar a Notion"), unsafe_allow_html=True)
        scored_row = scored.set_index("cluster_id").loc[rcard["cluster_id"]].to_dict() \
            if rcard.get("cluster_id") in set(scored["cluster_id"]) else None
        markdown = card_markdown(rcard, scored_row, action_for(
            rcard.get("estado_evidencia"), rcard, bool((scored_row or {}).get("recirculada", rcard.get("recirculada")))))
        st.markdown(note_html("La ficha completa, lista para pegar en la base «Casos y evidencias»."), unsafe_allow_html=True)
        st.download_button("Descargar la ficha (.md)", markdown, file_name=f"{case_id}.md", mime="text/markdown")
        with st.expander("Ver el texto para copiar"):
            st.code(markdown, language="markdown")


def view_datos() -> None:
    cached = cache_count(CACHE_DIR)
    st.markdown(page_head_html("Fuentes y datos", [
        "De dónde sale cada noticia", "Con qué licencia se usa", "Cómo comprobar que nada cambió",
    ]), unsafe_allow_html=True)
    manifest = load_manifest()
    if manifest is None:
        st.markdown(note_html("Todavía no hay registro de los archivos de datos."), unsafe_allow_html=True)
    else:
        origins = news_by_origin(manifest)
        tvn = sum(v for k, v in origins.items() if k.startswith("tvn"))
        cut_time = tx.fecha(manifest["fecha_corte_UTC"]).split(", ")[-1]
        st.markdown(tiles_html([
            ("Noticias", f"{sum(origins.values()):,}" if origins else "—",
             f"{tvn:,} de TVN · {origins.get('gdelt', 0):,} de medios del mundo (GDELT)"),
            ("Datos al", tx.fecha(manifest["fecha_corte_UTC"], con_hora=False), f"{cut_time}, hora de Panamá"),
            ("Respuestas guardadas", f"{cached:,}", "IA: Gemini 2.5 Flash, sin creatividad (temperatura 0)"),
        ]), unsafe_allow_html=True)

        st.markdown(section_html("Fuentes y licencias"), unsafe_allow_html=True)
        catalog = load_catalog()
        if catalog:
            st.dataframe(sources_table(catalog), hide_index=True, width="stretch")
            st.caption("De TVN solo guardamos titular, resumen, fecha y enlace: nunca el texto completo, imágenes ni video.")
        else:
            st.markdown(note_html("Todavía no hay catálogo de fuentes."), unsafe_allow_html=True)

        st.markdown(section_html("Comprobar los datos"), unsafe_allow_html=True)
        st.markdown(note_html(f"Cada uno de los {len(manifest['archivos'])} archivos tiene una huella (SHA-256). Si alguien "
                              "cambiara un solo dato, la huella no coincidiría."), unsafe_allow_html=True)
        if st.button("Comprobar que los datos no cambiaron", type="primary"):
            with st.spinner("Calculando la huella de cada archivo…"):
                problems = verify_messages(verify_manifest())
            if problems:
                st.error("Hay archivos que no coinciden:\n\n" + "\n".join(f"- {p}" for p in problems))
            else:
                st.success(f"Los {len(manifest['archivos'])} archivos están intactos: coinciden con su huella.")
        with st.expander(f"Ver los {len(manifest['archivos'])} archivos y su huella"):
            st.dataframe(files_table(manifest), hide_index=True, width="stretch")
        with st.expander("Cómo reproducir los datos (equipo técnico)"):
            st.markdown("\n".join(f"1. `{step}`" for step in manifest.get("reproducir", [])))
            st.caption(f"Modelo: {model_name()} · temperatura 0 · " +
                       ("sin internet: solo respuestas guardadas" if OFFLINE else "en línea: guardadas primero, luego el modelo"))

    quality = load_quality()
    st.markdown(section_html("Calidad de los datos"), unsafe_allow_html=True)
    if quality:
        with st.expander("Ver el reporte de calidad"):
            st.markdown(quality)
    else:
        st.markdown(note_html("Todavía no hay reporte de calidad."), unsafe_allow_html=True)

    with st.expander(f"Ver todas las noticias ({len(news):,})"):
        order_key = news["fecha_deteccion"].fillna(news["fecha_publicacion"])
        corpus = news.assign(_order=order_key).sort_values("_order", ascending=False)
        st.dataframe(pd.DataFrame({
            "Titular": corpus["titulo"].map(tx.limpiar_titular),
            "Medio": corpus["medio"],
            "Tema": corpus["tema"].map(tx.tema),
            "Publicada": corpus["fecha_publicacion"].map(tx.fecha),
            "Detectada": corpus["fecha_deteccion"].map(tx.fecha),
            "Marcas": corpus.apply(flags, axis=1),
        }), hide_index=True, width="stretch")


{"Mesa": view_mesa, "Consulta": view_consulta, "Revisión": view_revision, "Datos": view_datos}[vista]()
