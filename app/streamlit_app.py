"""Copiloto TVN Streamlit UI. Owner: Cristian (C-12..C-16); skeleton by José (J-03).

Four tabs: Bandeja, Ficha, Borrador, Revisión. Reads data/processed/noticias.parquet
when B has delivered it, otherwise the synthetic stub. Data stays in UTC; times
are converted to Panama time only for display.

With OFFLINE=1 nothing touches the network: LLM output is read only from
outputs/cache/ and the UI says so. UI text is Spanish (editors are the users).
"""

import json
import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from app.bandeja import (
    COMPONENTS, EVIDENCE_STATES, HEADLINE_LANGUAGES, SCORE_RANGES, TOP_N, build_inbox, filter_inbox,
    headline_label, inbox_pick, language_label, load_cards, load_contexto, records_label, urgency_basis_label,
)
from app.ficha import (
    CLAIM_TYPES, action_for, citation_found, cluster_sources, component_points, headline_only,
)
from app.borrador import (
    ANSWER_LIMIT, CLAIM_STYLE, citation_label, claims_by_type, draft_rows, evidence_context, query_cards,
    word_count,
)
from src.generate.drafts import official_index
from src.generate.query import answer_question
from src.search import load_index
from src.ingest.worldbank import read_indicators
from app.revision import card_markdown, case_history, case_label, panama_time
from src.fichas import append_review, apply_reviews, latest_reviews, read_reviews
from app.datos import (
    cache_count, files_table, load_catalog, load_manifest, load_quality, news_by_origin, sources_table,
    verify_messages,
)
from src.manifest import verify as verify_manifest
from app.estilo import CSS, chip, claim_type_chip, event_card_html, evidence_chip, header_html, tiles_html
from src.score import score_clusters

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_PATH = ROOT / "data" / "processed" / "noticias.parquet"
STUB_PATH = ROOT / "data" / "stub" / "noticias_stub.parquet"
CACHE_DIR = ROOT / "outputs" / "cache"
OFFICIAL_DIR = ROOT / "data" / "processed"

PANAMA_TZ = "America/Panama"  # UTC-5, no daylight saving
OFFLINE = os.getenv("OFFLINE", "0") == "1"

# Written exactly as the challenge requires.
REVIEW_STATES = [
    "nuevo",
    "en revisión",
    "requiere evidencia",
    "aprobado como borrador",
    "descartado",
]

# Placeholder heuristic so T07 cases are visible in the inbox; the real defense
# lives in src/generate/guard.py (J-11).
INJECTION_PATTERN = re.compile(
    r"ignora (tus|las) (instrucciones|reglas)|revela|api key|configuraci[oó]n|system prompt",
    re.IGNORECASE,
)


@st.cache_data
def load_news() -> tuple[pd.DataFrame, str]:
    path = PROCESSED_PATH if PROCESSED_PATH.exists() else STUB_PATH
    return pd.read_parquet(path), path.relative_to(ROOT).as_posix()


@st.cache_data  # U is measured against the corpus date (ADR-027), not the clock: no need to refresh
def load_scores(news: pd.DataFrame) -> pd.DataFrame:
    return score_clusters(news, contexto=load_contexto())


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


def show_claims(card: dict | None) -> None:
    """Claims grouped by type with their citations, so a hypothesis never reads as a fact."""
    if not (groups := claims_by_type(card)):
        return
    st.markdown("#### Afirmaciones por tipo")
    for kind, claims in groups:
        _icon, label, meaning = CLAIM_STYLE[kind]
        st.markdown(f"{claim_type_chip(kind, label)} <span style='color:#4A505C'>{meaning}</span>",
                    unsafe_allow_html=True)
        for claim in claims:
            cites = " · ".join(citation_label(c) for c in claim.get("citas") or [])
            st.markdown(f"- {claim['texto']}  \n  {cites}")


def show_answer(result) -> None:
    """A query answer (DraftResult) exactly as the guard left it."""
    if result.source == "error":
        st.error("No se pudo consultar el modelo (falta `LLM_API_KEY` o falló el proveedor). "
                 "No se muestra ninguna respuesta.")
        return
    if result.source == "offline_miss":
        st.warning("Modo sin internet: esta consulta no está en la caché, así que no hay respuesta guardada.")
    out = result.output.model_dump()
    for alerta in out["alertas"]:
        st.warning(f"⚠️ Alerta (T07): {alerta}")
    if out["abstencion"]:
        st.error(f"**Sin respuesta (abstención, T06).** {out['motivo_abstencion'] or ''}")
    elif out["borrador"]:
        low, high = ANSWER_LIMIT
        words = word_count(out["borrador"])
        st.write(out["borrador"])
        st.caption(f"{words} palabras · rango {low}–{high} · "
                   + ("dentro del límite" if low <= words <= high else "⚠️ fuera del límite"))
    show_claims(out)
    show_contradictions(out["contradicciones"])
    for pending in out["verificaciones_pendientes"]:
        st.markdown(f"- Verificación pendiente: {pending}")
    origin = {"cache": "caché", "llm": "modelo", "sin_evidencia": "sin llamar al modelo (no hay evidencia)",
              "offline_miss": "sin internet y sin caché"}.get(result.source, result.source)
    st.caption(f"Origen: {origin}" + (f" · {result.latency_s:.1f} s" if result.latency_s else ""))


def show_contradictions(items: list[dict] | None) -> None:
    """T05: both versions side by side, each with its citation; never resolved by the app."""
    if not items:
        return
    st.markdown("#### Contradicciones (T05) · verificación pendiente")
    for c in items:
        side_a, side_b = st.columns(2)
        side_a.markdown(f"**Versión A:** {c.get('version_a')}  \n{citation_label(c.get('cita_a'))}")
        side_b.markdown(f"**Versión B:** {c.get('version_b')}  \n{citation_label(c.get('cita_b'))}")


def to_panama(ts: pd.Timestamp) -> str:
    """Panama local time for display; nulls are shown as such, never filled."""
    if pd.isna(ts):
        return "— (sin dato)"
    return ts.tz_convert(PANAMA_TZ).strftime("%Y-%m-%d %H:%M") + " (Panamá)"


def to_utc(ts: pd.Timestamp) -> str:
    if pd.isna(ts):
        return "—"
    return ts.tz_convert("UTC").strftime("%Y-%m-%d %H:%M UTC")


def flags(row: pd.Series) -> str:
    labels = []
    if row.get("sintetico", False):
        labels.append("🧪 sintético")
    if row.get("recirculada", False):
        labels.append("♻️ recirculada")
    if INJECTION_PATTERN.search(str(row["titulo"])):
        labels.append("⚠️ posible instrucción inyectada")
    return " · ".join(labels)


def cached_outputs() -> list[Path]:
    return sorted(p for p in CACHE_DIR.glob("*.json"))


st.set_page_config(page_title="Copiloto TVN", page_icon="📰", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

news, source_path = load_news()
has_synthetic = bool("sintetico" in news and news["sintetico"].fillna(False).any())
scored = load_scores(news)
_manifest = load_manifest()
DATA_CUT = to_panama(pd.Timestamp(_manifest["fecha_corte_UTC"])) if _manifest else None
# One bar with what the editor must always see: offline or online, data cut, corpus and data source.
st.markdown(header_html(OFFLINE, source_path, len(news), scored["cluster_id"].nunique() if not scored.empty else 0,
                        DATA_CUT, has_synthetic), unsafe_allow_html=True)
cards, cards_path = load_cards(news_from_stub=source_path == STUB_PATH.relative_to(ROOT).as_posix())
CARDS_LABEL = f"`{cards_path}`" if cards_path else "sin fichas todavía (`make demo-cache`, J-12)"
cards = apply_reviews(cards, latest_reviews())  # the review log wins over the state in the file
cards_by_cluster = {c["cluster_id"]: c for c in cards if c.get("cluster_id")}
official = load_official()
inbox = build_inbox(scored, news, cards)

inbox_tab, card_tab, draft_tab, review_tab, data_tab = st.tabs(
    ["Bandeja", "Ficha", "Borrador", "Revisión", "Datos y calidad"])

with inbox_tab:
    st.subheader("Bandeja priorizada")
    st.caption(
        f"Puntaje P = 30R + 25I + 20U + 15N + 10E (`{', '.join(scored['version_reglas'].unique())}`, "
        "determinista, sin LLM). Prioridad alta **no** habilita publicar: el estado de evidencia va aparte."
    )
    if inbox.empty:
        st.info("Todavía no hay clusters para priorizar.")
    else:
        states = inbox["estado_evidencia"].value_counts()
        st.markdown(tiles_html([
            ("Eventos en rango alto", f"{int((inbox['rango'] == 'alto').sum()):,}", f"de {len(inbox):,}"),
            ("Suficiente para el borrador", f"{int(states.get('suficiente para el borrador', 0)):,}", ""),
            ("Parcial", f"{int(states.get('parcial', 0)):,}", ""),
            ("Insuficiente", f"{int(states.get('insuficiente', 0)):,}", ""),
        ]), unsafe_allow_html=True)
        if not inbox["contexto_disponible"].all():
            st.warning("Sin contexto oficial todavía (`contexto.parquet`, B-14): I y E no incluyen "
                       "indicadores del Banco Mundial ni sismos del USGS.")
        f1, f2, f3, f4, f5 = st.columns([2, 2, 2, 2, 1])
        temas = f1.multiselect("Tema", sorted(inbox["tema"].dropna().unique()), placeholder="Todos")
        estados = f2.multiselect("Estado de evidencia", EVIDENCE_STATES, placeholder="Todos")
        rangos = f3.multiselect("Rango de P", SCORE_RANGES, placeholder="Todos")
        all_languages = sorted({code for langs in inbox["idiomas"] for code in langs})
        idiomas = f4.multiselect(
            "Idioma", all_languages, default=[c for c in HEADLINE_LANGUAGES if c in all_languages],
            format_func=language_label, placeholder="Todos",
            help="Clusters con al menos una noticia en esos idiomas. No cambia el puntaje.")
        show_all = f5.toggle("Ver todos", help=f"Por defecto se muestran los {TOP_N} de mayor P.")
        view = filter_inbox(inbox, temas, estados, rangos, top_n=None if show_all else TOP_N, idiomas=idiomas)

        if not show_all:
            # Top of the inbox as cards; "Ver todos" keeps the compact, selectable table.
            for row in view.itertuples():
                marks = " · ".join(m for m in (
                    "🧪 sintético" if row.sintetico else "", "♻️ recirculada" if row.recirculada else "",
                    f"⚠️ {row.alertas} alerta(s)" if row.alertas else "") if m)
                meta = (f"{records_label(row.n_registros, row.n_procedencias_independientes)} · U desde "
                        f"{urgency_basis_label(row.base_urgencia)} {to_panama(row.fecha_referencia_urgencia)}")
                with st.container(border=True):
                    st.markdown(event_card_html(row.posicion, row.P, row.rango, row.tema, row.estado_evidencia,
                                                headline_label(row.titular), meta, row.id_titular,
                                                {c: getattr(row, c) for c in COMPONENTS}, marks),
                                unsafe_allow_html=True)
                    # Runs before the Ficha selectbox exists in this run, so it can set its value.
                    if st.button("Abrir ficha", key=f"abrir_{row.cluster_id}"):
                        st.session_state.ficha_cluster = row.cluster_id
                        st.session_state.abierta = row.cluster_id
                    if st.session_state.get("abierta") == row.cluster_id:
                        st.caption("Abierta en la pestaña **Ficha**.")
        table = pd.DataFrame({
            "#": view["posicion"],
            "Tema": view["tema"].fillna("— (sin dato)"),
            "Titular": view["titular"].fillna("— (sin titular)"),
            "ID titular": view["id_titular"],
            "Título propuesto": view["titulo_propuesto"].fillna("—"),
            "P": view["P"],
            "Rango": view["rango"],
            **{c: view[c] for c in COMPONENTS},
            "Evidencia": view["estado_evidencia"],
            "Registros · procedencias": [records_label(n, m) for n, m in
                                         zip(view["n_registros"], view["n_procedencias_independientes"])],
            "Referencia (Panamá)": view["fecha_referencia_urgencia"].map(to_panama),
            "Según": view["base_urgencia"].map(urgency_basis_label),
            "Ficha": view["id_caso"].fillna("— (sin ficha)"),
            "Revisión": view["estado_revision"].fillna("—"),
            "Marcas": [" · ".join(m for m in (
                "🧪 sintético" if row.sintetico else "",
                "♻️ recirculada" if row.recirculada else "",
                f"⚠️ {row.alertas} alerta(s)" if row.alertas else "",
            ) if m) for row in view.itertuples()],
        })
        component_help = {"R": "Relación con Panamá", "I": "Impacto", "U": "Urgencia",
                          "N": "Novedad", "E": "Evidencia"}
        if show_all:
            event = st.dataframe(
                table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
                column_config={
                    "P": st.column_config.ProgressColumn("P", min_value=0, max_value=100, format="%.1f"),
                    **{c: st.column_config.NumberColumn(c, help=f"{component_help[c]} (0–1)", format="%.2f")
                       for c in COMPONENTS},
                },
            )
            # Runs before the Ficha selectbox is created, so it can set its value. Only a new
            # selection moves the Ficha; otherwise its selector would stay pinned to this row.
            picked = view.iloc[event.selection.rows[0]]["cluster_id"] if event.selection.rows else None
            if (target := inbox_pick(picked, st.session_state.get("inbox_pick"))) is not None:
                st.session_state.ficha_cluster = target
            st.session_state.inbox_pick = picked
        st.caption(
            f"Mostrando {len(view)} de {len(inbox)} clusters. R relación con Panamá · I impacto · "
            "U urgencia · N novedad · E evidencia (0–1). Referencia = fecha desde la que se mide U, "
            f"en hora de Panamá (UTC−5). Fichas: {CARDS_LABEL}. Abre un caso con **Abrir ficha**, o con "
            "**Ver todos** elige una fila de la tabla."
        )

    with st.expander(f"Noticias del corpus ({len(news)})"):
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

with card_tab:
    st.subheader("Ficha")
    if inbox.empty:
        st.info("Todavía no hay clusters para explicar.")
    else:
        by_id = inbox.set_index("cluster_id")
        if st.session_state.get("ficha_cluster") not in by_id.index:
            st.session_state.ficha_cluster = inbox.sort_values("posicion")["cluster_id"].iloc[0]
        cluster_id = st.selectbox(
            "Cluster", list(inbox.sort_values("posicion")["cluster_id"]), key="ficha_cluster",
            format_func=lambda c: f"#{by_id.loc[c, 'posicion']} · {by_id.loc[c, 'tema']} · "
                                  f"{headline_label(by_id.loc[c, 'titular'])}",
            # "contains", not the default fuzzy match: with 8,421 clusters, "#2 ·" fuzzy-matched #2199 first.
            filter_mode="contains",
        )
        row = by_id.loc[cluster_id]
        card = cards_by_cluster.get(cluster_id)
        sources = cluster_sources(news, cluster_id)

        st.markdown(f"### {headline_label(row['titular'])}")
        st.caption(f"Titular real más reciente · `{row['id_titular']} · titulo`")
        if pd.notna(row["titulo_propuesto"]):
            st.markdown(f"*Título propuesto (generado, para revisión):* {row['titulo_propuesto']}")
        st.markdown('<div class="ctvn-chips">' + "".join(m for m in (
            chip(row["tema"] or "— (sin dato)"), chip(f"P {row['P']:.1f} · {row['rango']}", row["rango"]),
            evidence_chip(row["estado_evidencia"]),
            chip(records_label(row["n_registros"], row["n_procedencias_independientes"])),
            chip(f"Ficha {card['id_caso']}" if card else "Sin ficha generada (J-12)"),
            chip("🧪 sintético", "synthetic") if row["sintetico"] else "",
            chip("♻️ recirculada") if row["recirculada"] else "",
        ) if m) + "</div>", unsafe_allow_html=True)
        if headline_only(sources):
            st.caption("Basado únicamente en titular/metadatos.")
        st.info(f"**Acción recomendada:** {action_for(row['estado_evidencia'], card, bool(row['recirculada']))}")
        for alerta in (card or {}).get("alertas", []):
            st.warning(f"⚠️ {alerta}")

        left, right = st.columns([3, 2])
        with left, st.container(border=True):
            st.markdown("#### Qué se reporta")
            if card and card.get("enfoque_interes_publico"):
                st.markdown(f"*Enfoque de interés público:* {card['enfoque_interes_publico']}")
            claims = (card or {}).get("afirmaciones") or []
            if claims:
                for claim in claims:
                    st.markdown(f"- **{CLAIM_TYPES.get(claim['tipo'], claim['tipo'])}** · {claim['texto']}")
            elif card and card.get("abstencion"):
                st.markdown(f"El sistema se abstuvo: {card.get('motivo_abstencion')}")
            else:
                st.caption("Sin afirmaciones generadas todavía. Titulares de las fuentes, tal cual:")
                for item in sources.itertuples():
                    st.markdown(f"- `{item.id_noticia} · titulo` {item.titulo}")

            st.markdown("#### Qué está respaldado")
            if claims:
                for claim in claims:
                    st.markdown(f"**{claim['texto']}**")
                    for cita in claim["citas"]:
                        mark = "✅" if citation_found(news, cita, official) else "❌ pasaje no encontrado en la fuente"
                        source = official.get(cita["id_fuente"])  # World Bank / USGS: show country, year, unit
                        extra = f" · *{evidence_context(source)}*" if source is not None else ""
                        st.markdown(f"{mark} `{cita['id_fuente']} · {cita['campo']}` · “{cita['pasaje']}”{extra}")
            else:
                st.caption("Nada respaldado todavía: no hay afirmaciones con cita.")

            st.markdown("#### Qué falta")
            missing = list((card or {}).get("verificaciones_pendientes") or [])
            if not row["hay_fuente_oficial"]:
                missing.append("Sin fuente oficial vinculada (Banco Mundial o USGS)"
                               + ("." if row["contexto_disponible"] else "; el contexto oficial (B-14) aún no existe."))
            if row["n_procedencias_independientes"] < 2:
                missing.append("Una sola procedencia independiente: falta corroboración.")
            for item in dict.fromkeys(missing):
                st.markdown(f"- {item}")
            if n_contra := len((card or {}).get("contradicciones") or []):
                st.markdown(f"- {n_contra} contradicción(es) entre fuentes: verificación pendiente (abajo).")
            if questions := (card or {}).get("preguntas_investigacion"):
                st.markdown("*Preguntas de investigación:*")
                for q in questions:
                    st.markdown(f"- {q}")

        with right, st.container(border=True):
            st.markdown("#### Puntaje")
            for comp in component_points(row):
                if comp["valor"] is None:
                    st.caption(f"{comp['clave']} · {comp['nombre']}: sin dato")
                else:
                    st.progress(comp["valor"], text=f"{comp['clave']} · {comp['nombre']}: "
                                f"{comp['valor']:.2f} × {comp['peso']} = {comp['puntos']:.1f} pts")
            st.caption(
                f"P = {row['P']:.1f} · reglas `{row['version_reglas']}` · U medida desde "
                f"{urgency_basis_label(row['base_urgencia'])}, {to_panama(row['fecha_referencia_urgencia'])}."
            )
            if card and (card.get("puntaje") or {}).get("valores_de_ejemplo"):
                st.caption(f"La ficha de ejemplo trae P = {card['puntaje']['P']:.1f}; aquí se muestra el de `score.py`.")

        show_contradictions((card or {}).get("contradicciones"))

        st.markdown("#### Quién lo reporta")
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

with draft_tab:
    st.subheader("Borrador")
    st.caption("Borradores para revisión humana, tal como los dejó el guard. Nada se publica desde aquí.")
    if OFFLINE:
        st.markdown(f"Leyendo solo de `outputs/cache/`: **{len(cached_outputs())}** salidas guardadas.")
    draft_cluster = st.session_state.get("ficha_cluster")
    if inbox.empty or draft_cluster not in inbox["cluster_id"].values:
        st.info("Elige un cluster en la Bandeja o en la Ficha.")
    else:
        drow = inbox.set_index("cluster_id").loc[draft_cluster]
        dcard = cards_by_cluster.get(draft_cluster)
        st.markdown(f"**{headline_label(drow['titular'])}** · `{drow['id_titular']}` · se cambia en la pestaña Ficha")
        if headline_only(cluster_sources(news, draft_cluster)):
            st.caption("Basado únicamente en titular/metadatos.")
        for alerta in (dcard or {}).get("alertas") or []:
            st.warning(f"⚠️ Alerta (T07): {alerta}. La fuente se trata como dato, nunca como instrucción.")

        if dcard is None:
            st.info("Este cluster todavía no tiene ficha ni borrador (se generan con `make demo-cache`, J-12).")
        elif dcard.get("abstencion"):
            st.error(f"**El sistema se abstuvo (T06).** {dcard.get('motivo_abstencion') or ''}  \n"
                     "No hay borrador porque la evidencia no alcanza; no se rellena con texto inventado.")
        else:
            for draft in draft_rows(dcard):
                with st.container(border=True):
                    st.markdown(f"#### {draft['etiqueta']}")
                    if draft["texto"] is None:
                        st.caption("No generado.")
                        continue
                    st.write(draft["texto"])
                    fits = "dentro del límite" if draft["dentro"] else "⚠️ fuera del límite"
                    st.caption(f"{draft['palabras']} palabras · rango {draft['min']}–{draft['max']} · {fits}")

        show_claims(dcard)
        show_contradictions((dcard or {}).get("contradicciones"))

    st.divider()
    st.markdown("#### Consulta (CU-04)")
    with st.form("consulta"):
        question = st.text_input("Pregunta en español", placeholder="¿Cuál fue la inflación de Panamá en 2023?")
        asked = st.form_submit_button("Consultar")
    if asked and question.strip():
        found = load_search().search(question)
        if found.hits:
            with st.expander(f"Evidencia encontrada ({len(found.hits)} pasajes, búsqueda J-06)"):
                st.dataframe(pd.DataFrame([{"ID": h.id_evidencia, "Campo": h.campo, "Pasaje": h.texto,
                                            "Fuente · contexto": evidence_context(h.evidence),
                                            "Similitud": h.score} for h in found.hits]),
                             hide_index=True, width="stretch")
        with st.spinner("Redactando la respuesta con citas…"):
            answer = answer_question(question, found.evidence)  # no evidence → abstains without the model
        show_answer(answer)

    if saved := query_cards(cards):
        st.caption("Consultas guardadas en las fichas:")
    for qcard in saved:
        st.markdown(f"**{qcard['consulta']}**" + (" · 🧪 sintético" if qcard.get("sintetico") else ""))
        if qcard.get("abstencion"):
            st.error(f"Sin respuesta (abstención): {qcard.get('motivo_abstencion')}")
        else:
            st.write((qcard.get("borrador") or {}).get("brief") or "—")

with review_tab:
    st.subheader("Revisión")
    st.caption("Una persona decide el estado de cada ficha. Cada decisión se agrega a "
               "`outputs/revisiones.jsonl` y nunca se reescribe. Aprobar como borrador **no** es publicar.")
    if flash := st.session_state.pop("review_saved", None):
        st.success(flash)
    if not cards:
        st.info("Todavía no hay fichas para revisar (se generan con `make demo-cache`, J-12).")
    else:
        rank = dict(zip(inbox["cluster_id"], inbox["posicion"]))
        by_case = {c["id_caso"]: c for c in sorted(
            cards, key=lambda c: (rank.get(c.get("cluster_id"), float("inf")), c["id_caso"]))}
        if st.session_state.get("review_case") not in by_case:
            # Last case the editor chose wins over the Ficha link: never jump to another card.
            remembered = st.session_state.get("review_case_pick")
            linked = cards_by_cluster.get(st.session_state.get("ficha_cluster"), {}).get("id_caso")
            st.session_state.review_case = next(c for c in (remembered, linked, next(iter(by_case))) if c in by_case)
        case_id = st.selectbox("Ficha", list(by_case), key="review_case", format_func=lambda i: case_label(by_case[i]),
                               filter_mode="contains")
        st.session_state.review_case_pick = case_id
        rcard = by_case[case_id]
        current = rcard.get("estado_revision") or "nuevo"
        who = f" · {rcard['revisor']} · {panama_time(rcard.get('fecha_revision'))}" if rcard.get("revisor") else ""
        st.markdown(f"Estado actual: **{current}**{who}")

        with st.form("revision"):
            # Keyed per case so the widget keeps its identity when the current state changes.
            state_key = f"review_state_{case_id}"
            if st.session_state.get(state_key) not in REVIEW_STATES:
                st.session_state[state_key] = current if current in REVIEW_STATES else REVIEW_STATES[0]
            new_state = st.radio("Nuevo estado", REVIEW_STATES, horizontal=True, key=state_key)
            reviewer = st.text_input("Persona revisora", placeholder="Nombre de quien revisa")
            note = st.text_area("Nota", placeholder="Por qué se decide esto (opcional)")
            submitted = st.form_submit_button("Guardar decisión")
        if submitted:
            if not reviewer.strip():
                st.error("Falta la persona revisora: toda decisión lleva quién la tomó.")
            else:
                record = append_review(case_id, new_state, reviewer, note.strip())
                st.session_state.review_saved = (
                    f"Guardado: `{case_id}` → **{record['estado_revision']}** · {record['revisor']} · "
                    f"{panama_time(record['fecha_revision'])}")
                st.rerun()

        records, skipped = read_reviews()
        if history := case_history(records, case_id):
            st.markdown("#### Historial de esta ficha")
            st.dataframe(pd.DataFrame([{
                "Fecha (Panamá)": panama_time(r.get("fecha_revision")), "Estado": r["estado_revision"],
                "Persona revisora": r.get("revisor"), "Nota": r.get("nota") or "—",
            } for r in history]), hide_index=True, width="stretch")
        if skipped:
            st.warning(f"{skipped} línea(s) de `revisiones.jsonl` no son válidas y se ignoran.")

        st.markdown("#### Copiar para Notion")
        scored_row = scored.set_index("cluster_id").loc[rcard["cluster_id"]].to_dict() \
            if rcard.get("cluster_id") in set(scored["cluster_id"]) else None
        markdown = card_markdown(rcard, scored_row, action_for(
            rcard.get("estado_evidencia"), rcard, bool((scored_row or {}).get("recirculada", rcard.get("recirculada")))))
        st.caption("Copia con el ícono de la esquina y pega en la base \"Casos y evidencias\" (ADR-008).")
        st.code(markdown, language="markdown")
        st.download_button("Descargar .md", markdown, file_name=f"{case_id}.md", mime="text/markdown")

with data_tab:
    st.subheader("Datos y calidad")
    cached = cache_count(CACHE_DIR)
    if OFFLINE:
        st.warning(f"**Modo sin internet (OFFLINE=1, T10).** Nada llama a la red: el LLM se sirve solo desde "
                   f"`outputs/cache/` ({cached} salidas guardadas) y las consultas sin caché se abstienen.")
    else:
        st.info(f"En línea: el LLM se consulta y cada respuesta se guarda en `outputs/cache/` ({cached} salidas). "
                "Para la demo sin internet: `OFFLINE=1 make demo`.")

    manifest = load_manifest()
    if manifest is None:
        st.info("Todavía no hay `data/manifest.json` (B-10).")
    else:
        origins = news_by_origin(manifest)
        m1, m2, m3 = st.columns(3)
        m1.metric("Noticias", f"{sum(origins.values()):,}" if origins else "—",
                  help=" · ".join(f"{k}: {v:,}" for k, v in origins.items()) or None)
        m2.metric("Corte de datos", to_panama(pd.Timestamp(manifest["fecha_corte_UTC"])).replace(" (Panamá)", ""),
                  help=f"{manifest.get('fecha_corte_nota', '')} · {manifest['fecha_corte_UTC']} UTC")
        m3.metric("Archivos en el manifest", len(manifest.get("archivos", [])))
        st.caption("Corte en hora de Panamá; los archivos guardan UTC.")

        st.markdown("#### Fuentes y licencias")
        catalog = load_catalog()
        if catalog:
            st.dataframe(sources_table(catalog), hide_index=True, width="stretch")
            st.caption("Del catálogo de datos (`docs/notion/catalogo.csv`, B-15). De TVN solo se guardan metadatos: "
                       "nunca el cuerpo, imágenes ni video.")
        else:
            st.caption("Sin catálogo todavía (`docs/notion/catalogo.csv`, B-15).")

        st.markdown("#### Archivos entregados")
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
    st.markdown("#### Reporte de calidad")
    if quality:
        with st.expander("Ver `outputs/reports/calidad.md` (B-05)"):
            st.markdown(quality)
    else:
        st.caption("Sin reporte de calidad todavía (B-05).")
