"""Copiloto TVN Streamlit skeleton (J-03). Owner: José.

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
    st.subheader("Bandeja")
    st.caption(
        "Horas en Panamá (UTC−5); los datos se guardan en UTC. "
        "Publicación = fecha del medio; detección = seendate de GDELT. No se mezclan."
    )
    # Newest first by detection, falling back to publication only for ordering.
    order_key = news["fecha_deteccion"].fillna(news["fecha_publicacion"])
    inbox = news.assign(_order=order_key).sort_values("_order", ascending=False)
    view = pd.DataFrame({
        "ID": inbox["id_noticia"],
        "Titular": inbox["titulo"],
        "Medio": inbox["medio"],
        "Tema": inbox["tema"],
        "Cluster": inbox["cluster_id"],
        "Publicación (Panamá)": inbox["fecha_publicacion"].map(to_panama),
        "Detección (Panamá)": inbox["fecha_deteccion"].map(to_panama),
        "Marcas": inbox.apply(flags, axis=1),
    })
    st.dataframe(view, hide_index=True, width="stretch")
    st.caption(f"{len(news)} noticias · {news['cluster_id'].nunique()} clusters · "
               f"{news['procedencia_id'].nunique()} procedencias. Puntaje P pendiente (J-05).")

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
