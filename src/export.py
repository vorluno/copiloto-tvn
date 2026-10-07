"""Deliverables with the challenge's file names (B-13): noticias.csv + fuentes.json. Owner: B.

- data/processed/noticias.csv: every column of noticias.parquet, recirculada included (a superset of the
  challenge's minimum fields, section 7), UTF-8 without BOM, LF line ends, dates as
  ISO 8601 UTC ("2026-09-30T14:05:00Z"), nulls as empty cells (never 0).
- data/processed/fuentes.json: the three ways news entered the corpus (TVN RSS, TVN web,
  GDELT API) with their URL and terms, and one entry per outlet (medio, dominio, origen)
  with its number of news, date range and conditions of use. Neither TVN nor GDELT grant
  rights over the linked articles, so only titles, URLs and metadata are delivered.

Usage: python -m src.export   (also run at the end of `make nlp`)
"""

import json
from pathlib import Path

import pandas as pd

from src.ingest import gdelt, tvn_rss, tvn_web
from src.ingest.common import DATE_COLUMNS, NEWS_COLUMNS, WINDOW_END, WINDOW_START

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
NEWS_PATH = PROCESSED / "noticias.parquet"
CSV_PATH = PROCESSED / "noticias.csv"
SOURCES_PATH = PROCESSED / "fuentes.json"
# The challenge's minimum fields for noticias.csv (section 7); all are in NEWS_COLUMNS.
REQUIRED_COLUMNS = ["id_noticia", "titulo", "url", "medio", "idioma", "fecha_publicacion", "fecha_deteccion",
                    "fecha_extraccion", "tema", "origen", "alcance_texto"]

TVN_TERMS = ("Metadatos públicos de TVN (titular, descripción, fecha y URL). La descripción no da licencia "
             "sobre el artículo, sus videos ni imágenes: no se guarda ni se redistribuye el cuerpo.")
GDELT_TERMS = ("GDELT Project: uso libre citando la fuente (gdeltproject.org). La API no transfiere derechos "
               "de los medios enlazados: solo titular, URL y metadatos.")
OUTLET_TERMS = {
    "tvn_rss": TVN_TERMS,
    "tvn_web": TVN_TERMS,
    "gdelt": "Medio enlazado por GDELT. Sin derechos sobre el artículo: solo titular, URL y metadatos; "
             "para leerlo, ir a la URL del medio.",
}
ISO = "%Y-%m-%dT%H:%M:%SZ"


def _iso(series: pd.Series) -> pd.Series:
    """UTC ISO 8601 text; a null date stays null (an empty cell in the CSV)."""
    return series.dt.tz_convert("UTC").dt.strftime(ISO).where(series.notna(), None)


EXTRA_COLUMNS = ["recirculada"]  # announced extras (B-11), kept when present


def news_csv(news: pd.DataFrame) -> pd.DataFrame:
    out = news.reindex(columns=NEWS_COLUMNS + [c for c in EXTRA_COLUMNS if c in news]).copy()
    for col in DATE_COLUMNS:
        out[col] = _iso(pd.to_datetime(out[col], utc=True))
    return out


def write_csv(news: pd.DataFrame, path: Path = CSV_PATH) -> None:
    news_csv(news).to_csv(path, index=False, encoding="utf-8", na_rep="", lineterminator="\n")


def sources(news: pd.DataFrame) -> dict:
    when = news["fecha_publicacion"].fillna(news["fecha_deteccion"])
    outlets = []
    for (origin, domain), group in news.assign(_when=when).groupby(["origen", "dominio"], sort=True):
        first, last = group["_when"].min(), group["_when"].max()
        outlets.append({
            "medio": group["medio"].mode().iat[0] if group["medio"].notna().any() else None,
            "dominio": domain,
            "origen": origin,
            "n_noticias": int(len(group)),
            "fecha_primera_UTC": first.strftime(ISO) if pd.notna(first) else None,
            "fecha_ultima_UTC": last.strftime(ISO) if pd.notna(last) else None,
            "condiciones_uso": OUTLET_TERMS.get(origin),
        })
    outlets.sort(key=lambda o: (-o["n_noticias"], o["origen"], o["dominio"]))
    counts = news["origen"].value_counts()
    return {
        "periodo_UTC": [WINDOW_START.strftime(ISO), (WINDOW_END - pd.Timedelta(seconds=1)).strftime(ISO)],
        "n_noticias": int(len(news)),
        "consultas": [
            {"origen": "tvn_rss", "nombre": "TVN · feed RSS público", "url": tvn_rss.FEED_URL,
             "n_noticias": int(counts.get("tvn_rss", 0)), "condiciones_uso": TVN_TERMS},
            {"origen": "tvn_web", "nombre": "TVN · sitemaps públicos de tvn-2.com (metadatos JSON-LD)",
             "url": tvn_web.SITEMAP_URL.format(key="<YYYY>_<MM>"), "n_noticias": int(counts.get("tvn_web", 0)),
             "condiciones_uso": TVN_TERMS + " Respeta robots.txt."},
            {"origen": "gdelt", "nombre": "GDELT DOC 2.0 API (ArtList)", "url": gdelt.API_URL,
             "consultas": list(gdelt.QUERIES.values()), "n_noticias": int(counts.get("gdelt", 0)),
             "condiciones_uso": GDELT_TERMS},
        ],
        "medios": outlets,
    }


def write_sources(news: pd.DataFrame, path: Path = SOURCES_PATH) -> None:
    path.write_text(json.dumps(sources(news), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    news = pd.read_parquet(NEWS_PATH)
    write_csv(news)
    write_sources(news)
    n_outlets = len(json.loads(SOURCES_PATH.read_text(encoding="utf-8"))["medios"])
    print(f"Wrote {CSV_PATH.relative_to(ROOT)} ({len(news)} rows) and {SOURCES_PATH.relative_to(ROOT)} ({n_outlets} outlets)")


if __name__ == "__main__":
    main()
