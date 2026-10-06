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
    COMPONENTS, EVIDENCE_STATES, SCORE_RANGES, TOP_N, build_inbox, filter_inbox, load_cards, load_contexto,
    records_label, urgency_basis_label,
)
from app.ficha import (
    CLAIM_TYPES, action_for, citation_found, cluster_sources, component_points, headline_only,
)
from app.borrador import CLAIM_STYLE, citation_label, claims_by_type, draft_rows, query_cards
from src.generate.drafts import official_index
from src.ingest.worldbank import read_indicators
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


@st.cache_data(ttl=600)  # U depends on the current time, so refresh every 10 min
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
st.title("Copiloto TVN")
st.caption("Borradores para revisión humana. Nada se publica desde aquí.")

if OFFLINE:
    st.warning("Modo sin internet (OFFLINE=1): las salidas del LLM se sirven solo desde `outputs/cache/`.")

news, source_path = load_news()
has_synthetic = "sintetico" in news and news["sintetico"].fillna(False).any()
if has_synthetic:
    st.info(f"Datos: `{source_path}` · contiene noticias **sintéticas** (sintetico=true).")
else:
    st.info(f"Datos: `{source_path}`")

scored = load_scores(news)
cards, cards_path = load_cards()
cards_by_cluster = {c["cluster_id"]: c for c in cards if c.get("cluster_id")}
official = load_official()
inbox = build_inbox(scored, news, cards)

inbox_tab, card_tab, draft_tab, review_tab = st.tabs(["Bandeja", "Ficha", "Borrador", "Revisión"])

with inbox_tab:
    st.subheader("Bandeja priorizada")
    st.caption(
        f"Puntaje P = 30R + 25I + 20U + 15N + 10E (`{', '.join(scored['version_reglas'].unique())}`, "
        "determinista, sin LLM). Prioridad alta **no** habilita publicar: el estado de evidencia va aparte."
    )
    if inbox.empty:
        st.info("Todavía no hay clusters para priorizar.")
    else:
        if not inbox["contexto_disponible"].all():
            st.warning("Sin contexto oficial todavía (`contexto.parquet`, B-14): I y E no incluyen "
                       "indicadores del Banco Mundial ni sismos del USGS.")
        f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
        temas = f1.multiselect("Tema", sorted(inbox["tema"].dropna().unique()), placeholder="Todos")
        estados = f2.multiselect("Estado de evidencia", EVIDENCE_STATES, placeholder="Todos")
        rangos = f3.multiselect("Rango de P", SCORE_RANGES, placeholder="Todos")
        show_all = f4.toggle("Ver todos", help=f"Por defecto se muestran los {TOP_N} de mayor P.")
        view = filter_inbox(inbox, temas, estados, rangos, top_n=None if show_all else TOP_N)

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
        event = st.dataframe(
            table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
            column_config={
                "P": st.column_config.ProgressColumn("P", min_value=0, max_value=100, format="%.1f"),
                **{c: st.column_config.NumberColumn(c, help=f"{component_help[c]} (0–1)", format="%.2f")
                   for c in COMPONENTS},
            },
        )
        if event.selection.rows:
            # Runs before the Ficha selectbox is created, so it can set its value.
            st.session_state.ficha_cluster = view.iloc[event.selection.rows[0]]["cluster_id"]
        st.caption(
            f"Mostrando {len(view)} de {len(inbox)} clusters. R relación con Panamá · I impacto · "
            "U urgencia · N novedad · E evidencia (0–1). Referencia = fecha desde la que se mide U, "
            f"en hora de Panamá (UTC−5). Fichas: `{cards_path}`. Elige una fila para abrirla en **Ficha**."
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
            format_func=lambda c: f"#{by_id.loc[c, 'posicion']} · {by_id.loc[c, 'tema']} · {by_id.loc[c, 'titular']}",
        )
        row = by_id.loc[cluster_id]
        card = cards_by_cluster.get(cluster_id)
        sources = cluster_sources(news, cluster_id)

        st.markdown(f"### {row['titular']}")
        st.caption(f"Titular real más reciente · `{row['id_titular']} · titulo`")
        if pd.notna(row["titulo_propuesto"]):
            st.markdown(f"*Título propuesto (generado, para revisión):* {row['titulo_propuesto']}")
        st.markdown(" · ".join(m for m in (
            f"**{row['tema']}**", f"P **{row['P']:.1f}** ({row['rango']})",
            f"Evidencia: **{row['estado_evidencia']}**",
            records_label(row["n_registros"], row["n_procedencias_independientes"]),
            f"Ficha `{card['id_caso']}`" if card else "Sin ficha generada (J-09)",
            "🧪 sintético" if row["sintetico"] else "", "♻️ recirculada" if row["recirculada"] else "",
        ) if m))
        if headline_only(sources):
            st.caption("Basado únicamente en titular/metadatos.")
        st.info(f"**Acción recomendada:** {action_for(row['estado_evidencia'], card, bool(row['recirculada']))}")
        for alerta in (card or {}).get("alertas", []):
            st.warning(f"⚠️ {alerta}")

        left, right = st.columns([3, 2])
        with left:
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
                        st.markdown(f"{mark} `{cita['id_fuente']} · {cita['campo']}` · “{cita['pasaje']}”")
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

        with right:
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
        st.markdown(f"**{drow['titular']}** · `{drow['id_titular']}` · se cambia en la pestaña Ficha")
        if headline_only(cluster_sources(news, draft_cluster)):
            st.caption("Basado únicamente en titular/metadatos.")
        for alerta in (dcard or {}).get("alertas") or []:
            st.warning(f"⚠️ Alerta (T07): {alerta}. La fuente se trata como dato, nunca como instrucción.")

        if dcard is None:
            st.info("Este cluster todavía no tiene ficha ni borrador (se generan con `make fichas`, J-09).")
        elif dcard.get("abstencion"):
            st.error(f"**El sistema se abstuvo (T06).** {dcard.get('motivo_abstencion') or ''}  \n"
                     "No hay borrador porque la evidencia no alcanza; no se rellena con texto inventado.")
        else:
            for draft in draft_rows(dcard):
                st.markdown(f"#### {draft['etiqueta']}")
                if draft["texto"] is None:
                    st.caption("No generado.")
                    continue
                st.write(draft["texto"])
                fits = "dentro del límite" if draft["dentro"] else "⚠️ fuera del límite"
                st.caption(f"{draft['palabras']} palabras · rango {draft['min']}–{draft['max']} · {fits}")

        if dcard and (groups := claims_by_type(dcard)):
            st.markdown("#### Afirmaciones por tipo")
            for kind, claims in groups:
                icon, label, meaning = CLAIM_STYLE[kind]
                st.markdown(f"**{icon} {label}** · *{meaning}*")
                for claim in claims:
                    cites = " · ".join(citation_label(c) for c in claim.get("citas") or [])
                    st.markdown(f"- {claim['texto']}  \n  {cites}")

        show_contradictions((dcard or {}).get("contradicciones"))

    st.divider()
    st.markdown("#### Consulta (CU-04)")
    st.text_input("Pregunta en español", disabled=True,
                  placeholder="¿Cuál fue la inflación de Panamá en 2023?",
                  help="Se activa cuando esté la búsqueda semántica (J-06).")
    st.caption("La caja se activa con la búsqueda semántica (J-06). Consultas ya respondidas:")
    for qcard in query_cards(cards):
        st.markdown(f"**{qcard['consulta']}**")
        if qcard.get("abstencion"):
            st.error(f"Sin respuesta (abstención): {qcard.get('motivo_abstencion')}")
        else:
            st.write((qcard.get("borrador") or {}).get("brief") or "—")

with review_tab:
    st.subheader("Revisión")
    st.caption("Estado de revisión por ficha. Por ahora solo vive en esta sesión; "
               "persistencia en fichas.jsonl con quién y cuándo en J-09.")
    if "review" not in st.session_state:
        st.session_state.review = {}
    review_id = st.selectbox("Ficha", news["id_noticia"], key="review_id")
    current = st.session_state.review.get(review_id, REVIEW_STATES[0])
    new_state = st.radio("Estado", REVIEW_STATES, index=REVIEW_STATES.index(current), horizontal=True)
    st.session_state.review[review_id] = new_state
    st.markdown(f"`{review_id}` → **{new_state}**")
