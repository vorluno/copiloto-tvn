"""Official context (B-14): data/processed/contexto.parquet. Owner: B.

Stage 3 of the challenge: relate an event (cluster) to a World Bank indicator or a USGS
earthquake only when the relation holds; no supported relation, no row. Columns:
cluster_id, id_evidencia, tipo (indicador / sismo), regla, nota.

Indicator rule (written, deterministic):
1. The cluster's majority topic allows indicators (TOPIC_INDICATORS), following
   docs/alcance-y-datos.md: economía -> GDP, inflation, unemployment, exports;
   logística/Canal -> exports; servicios públicos -> internet use. Turismo, regulación,
   eventos naturales and otro get none.
2. The cluster's titles or descriptions mention Panama (or a Panamanian institution),
   because only Panama's series is linked.
3. They also name what the indicator measures (KEYWORDS): a news item about prices gets
   inflation, not GDP. A topic alone is not enough.
4. The value cited is Panama's latest year with data (never a null cell); the note says
   it is an annual figure of that year, not a measure of the news date.

Earthquake rule: a USGS event is linked only to an "eventos naturales" cluster that
mentions an earthquake and whose dates are within 72 h of the event. The USGS file covers
2024 and the news period is 2025-10-02 to 2026-09-30, so today this yields no rows: a
2024 quake cannot be the fact behind a 2026 headline.

Usage: python -m src.context
"""

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

from src.nlp.cluster import majority_topic
from src.nlp.provenance import reference_time

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
NEWS_PATH = PROCESSED / "noticias.parquet"
INDICATORS_PATH = PROCESSED / "indicadores.csv"
EVENTS_PATH = PROCESSED / "eventos.geojson"
OUTPUT_PATH = PROCESSED / "contexto.parquet"
COLUMNS = ["cluster_id", "id_evidencia", "tipo", "regla", "nota"]

COUNTRY = "PAN"
QUAKE_WINDOW = pd.Timedelta(hours=72)

TOPIC_INDICATORS = {
    "economía": ["NY.GDP.MKTP.KD.ZG", "FP.CPI.TOTL.ZG", "SL.UEM.TOTL.ZS", "NE.EXP.GNFS.ZS"],
    "logística/Canal": ["NE.EXP.GNFS.ZS"],
    "servicios públicos": ["IT.NET.USER.ZS"],
}
# Written without accents; text is folded before matching; matched at a word start.
# Only specific terms: "empleo" alone ("reciclaje impulsa empleo") or "exportación de
# talento" say nothing about the unemployment rate or exports of goods (7 oct review).
KEYWORDS = {
    "NY.GDP.MKTP.KD.ZG": ["pib", "producto interno bruto", "crecimiento economico", "crecimiento de la economia",
                          "economia crecio", "economia crece", "gdp", "economic growth"],
    "FP.CPI.TOTL.ZG": ["inflacion", "ipc", "indice de precios", "costo de vida", "canasta basica", "alza de precios",
                       "aumento de precios", "inflation", "consumer prices"],
    "SL.UEM.TOTL.ZS": ["desempleo", "desocupacion", "tasa de empleo", "mercado laboral", "unemployment"],
    "NE.EXP.GNFS.ZS": ["exportaciones", "comercio exterior", "exports"],
    "IT.NET.USER.ZS": ["internet", "conectividad", "banda ancha", "telecomunicacion", "fibra optica"],
}
INDICATOR_NAMES = {
    "NY.GDP.MKTP.KD.ZG": "crecimiento del PIB",
    "FP.CPI.TOTL.ZG": "inflación (precios al consumidor)",
    "SL.UEM.TOTL.ZS": "desempleo",
    "NE.EXP.GNFS.ZS": "exportaciones de bienes y servicios",
    "IT.NET.USER.ZS": "uso de internet",
}
PANAMA = [r"panam", r"\binec\b", r"\bmef\b", r"\bima\b", r"\bacp\b", r"\bcss\b", r"\bidaan\b"]
QUAKE_WORDS = ["sismo", "terremoto", "temblor", "earthquake", "quake"]


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _mentions(text: str, words: list[str]) -> list[str]:
    return [w for w in words if re.search(r"\b" + re.escape(w), text)]


def latest_values(indicators: pd.DataFrame, country: str = COUNTRY) -> dict[str, int]:
    """Latest year with a non-null value per indicator for `country`."""
    rows = indicators[(indicators["pais_iso3"] == country) & indicators["valor"].notna()]
    return rows.groupby("indicador_id")["anio"].max().astype(int).to_dict()


def cluster_text(group: pd.DataFrame) -> str:
    return fold(" ".join((group["titulo"].fillna("") + " " + group["descripcion"].fillna("")).tolist()))


def indicator_rows(news: pd.DataFrame, indicators: pd.DataFrame) -> list[dict]:
    years = latest_values(indicators)
    rows = []
    for cluster_id, group in news.groupby("cluster_id", sort=True):
        topic = majority_topic(group["tema"])
        allowed = TOPIC_INDICATORS.get(topic, [])
        if not allowed:
            continue
        text = cluster_text(group)
        if not any(re.search(p, text) for p in PANAMA):
            continue
        for indicator in allowed:
            hits = _mentions(text, KEYWORDS[indicator])
            if not hits or indicator not in years:
                continue
            year = years[indicator]
            rows.append({
                "cluster_id": cluster_id,
                "id_evidencia": f"WB-{COUNTRY}-{indicator}-{year}",
                "tipo": "indicador",
                "regla": f"tema '{topic}' + menciona Panamá + menciona {', '.join(hits[:3])} -> "
                         f"{INDICATOR_NAMES[indicator]} de Panamá, último año con dato",
                "nota": f"Dato anual de {year} (Banco Mundial, CC BY 4.0); no mide la fecha de la noticia. "
                        f"Citar con país, año y unidad.",
            })
    return rows


def quake_rows(news: pd.DataFrame, events: dict) -> list[dict]:
    quakes = []
    for feature in events.get("features", []):
        props = feature.get("properties", {})
        if props.get("id") and props.get("time"):
            quakes.append((props["id"], pd.Timestamp(props["time"]), props.get("place")))
    rows = []
    when = reference_time(news)
    for cluster_id, group in news.assign(_when=when).groupby("cluster_id", sort=True):
        if majority_topic(group["tema"]) != "eventos naturales":
            continue
        if not _mentions(cluster_text(group), QUAKE_WORDS):
            continue
        first, last = group["_when"].min(), group["_when"].max()
        if pd.isna(first):
            continue
        for event_id, time, place in quakes:
            if first - QUAKE_WINDOW <= time <= last + QUAKE_WINDOW:
                rows.append({
                    "cluster_id": cluster_id, "id_evidencia": event_id, "tipo": "sismo",
                    "regla": "tema 'eventos naturales' + menciona un sismo + sismo del USGS a 72 h o menos",
                    "nota": f"USGS: {place}. Solo hechos sísmicos (magnitud, hora, lugar, profundidad); "
                            f"la caja regional no es el territorio de Panamá.",
                })
    return rows


def build_context(news: pd.DataFrame, indicators: pd.DataFrame | None, events: dict | None) -> pd.DataFrame:
    rows = []
    if indicators is not None:
        rows += indicator_rows(news, indicators)
    if events is not None:
        rows += quake_rows(news, events)
    out = pd.DataFrame(rows, columns=COLUMNS)
    return out.sort_values(["cluster_id", "id_evidencia"]).reset_index(drop=True).astype(object)


def main() -> None:
    news = pd.read_parquet(NEWS_PATH)
    indicators = pd.read_csv(INDICATORS_PATH) if INDICATORS_PATH.exists() else None
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8")) if EVENTS_PATH.exists() else None
    context = build_context(news, indicators, events)
    context.to_parquet(OUTPUT_PATH, index=False)
    by_type = context["tipo"].value_counts().to_dict()
    print(f"Wrote {len(context)} links to {OUTPUT_PATH.relative_to(ROOT)} {by_type}; "
          f"{context['cluster_id'].nunique()} clusters with official context")


if __name__ == "__main__":
    main()
