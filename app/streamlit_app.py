"""Copiloto TVN Streamlit UI. Owner: Cristian (C-12..C-16); skeleton by José (J-03).

Four tabs: Bandeja, Ficha, Borrador, Revisión. Reads data/processed/noticias.parquet
when B has delivered it, otherwise the synthetic stub. Data stays in UTC; times
are converted to Panama time only for display.

With OFFLINE=1 nothing touches the network: LLM output is read only from
outputs/cache/ and the UI says so. UI text is Spanish (editors are the users).
"""

import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from app.bandeja import (
    COMPONENTS, EVIDENCE_STATES, SCORE_RANGES, TOP_N, build_inbox, filter_inbox, load_cards, load_contexto,
    records_label, urgency_basis_label,
)
from src.score import score_clusters

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_PATH = ROOT / "data" / "processed" / "noticias.parquet"
STUB_PATH = ROOT / "data" / "stub" / "noticias_stub.parquet"
CACHE_DIR = ROOT / "outputs" / "cache"

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

inbox_tab, card_tab, draft_tab, review_tab = st.tabs(["Bandeja", "Ficha", "Borrador", "Revisión"])

with inbox_tab:
    st.subheader("Bandeja priorizada")
    scored = load_scores(news)
    cards, cards_path = load_cards()
    inbox = build_inbox(scored, news, cards)
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
        temas = f1.multiselect("Tema", sorted(inbox["tema"].dropna().unique()))
        estados = f2.multiselect("Estado de evidencia", EVIDENCE_STATES)
        rangos = f3.multiselect("Rango de P", SCORE_RANGES)
        show_all = f4.toggle("Ver todos", help=f"Por defecto se muestran los {TOP_N} de mayor P.")
        view = filter_inbox(inbox, temas, estados, rangos, top_n=None if show_all else TOP_N)

        table = pd.DataFrame({
            "#": view["posicion"],
            "Tema": view["tema"].fillna("— (sin dato)"),
            "Titular": view["titular"].fillna("— (sin titular)"),
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
        st.dataframe(
            table, hide_index=True, width="stretch",
            column_config={
                "P": st.column_config.ProgressColumn("P", min_value=0, max_value=100, format="%.1f"),
                **{c: st.column_config.NumberColumn(c, help=f"{component_help[c]} (0–1)", format="%.2f")
                   for c in COMPONENTS},
            },
        )
        st.caption(
            f"Mostrando {len(view)} de {len(inbox)} clusters. R relación con Panamá · I impacto · "
            "U urgencia · N novedad · E evidencia (0–1). Referencia = fecha desde la que se mide U, "
            f"en hora de Panamá (UTC−5). Fichas: `{cards_path}`."
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
    selected_id = st.selectbox(
        "Noticia",
        news["id_noticia"],
        format_func=lambda i: f"{i} · {news.loc[news['id_noticia'] == i, 'titulo'].iloc[0]}",
    )
    row = news.loc[news["id_noticia"] == selected_id].iloc[0]
    if marks := flags(row):
        st.markdown(marks)
    left, right = st.columns(2)
    with left:
        st.markdown(f"**Titular** · `{row['id_noticia']} · titulo`")
        st.write(row["titulo"])
        if pd.notna(row.get("descripcion")):
            st.markdown(f"**Descripción RSS** · `{row['id_noticia']} · descripcion`")
            st.write(row["descripcion"])
        st.markdown(f"**Medio:** {row['medio']} (`{row['dominio']}`)")
        st.markdown(f"**Origen:** {row['origen']} · **Alcance:** {row['alcance_texto']}")
        st.markdown(f"**URL:** {row['url']}")
    with right:
        st.markdown(f"**Publicación:** {to_panama(row['fecha_publicacion'])} · {to_utc(row['fecha_publicacion'])}")
        st.markdown(f"**Detección:** {to_panama(row['fecha_deteccion'])} · {to_utc(row['fecha_deteccion'])}")
        st.markdown(f"**Extracción:** {to_utc(row['fecha_extraccion'])}")
        st.markdown(f"**Tema:** {row['tema']} (confianza {row['tema_confianza']:.2f})")
        same_cluster = news[news["cluster_id"] == row["cluster_id"]]
        st.markdown(
            f"**Cluster {row['cluster_id']}:** {len(same_cluster)} registros, "
            f"{same_cluster['procedencia_id'].nunique()} procedencias independientes"
        )
    if row["alcance_texto"] == "titular/metadatos":
        st.caption("Basado únicamente en titular/metadatos.")
    st.caption("Puntaje P y sus 5 componentes: pendiente (J-05). Estado de evidencia: pendiente.")

with draft_tab:
    st.subheader("Borrador")
    cached = cached_outputs()
    if OFFLINE:
        st.markdown(f"Leyendo solo de `outputs/cache/`: **{len(cached)}** salidas guardadas.")
    st.info("Generación de brief, guion y copy con citas: pendiente (J-07, J-08). "
            "Si no hay evidencia suficiente, el sistema se abstiene.")

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
