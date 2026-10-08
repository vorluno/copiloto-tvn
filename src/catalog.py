"""Data catalog for Notion (B-15): docs/notion/catalogo.csv. Owner: B.

One row per source with the 8 fields the challenge asks for (section 5): Fuente, URL,
Fecha de extracción, Cobertura, Campos, Licencia / condiciones, Transformaciones and
SHA-256, plus the delivered file and its row count. Built from the data and
data/manifest.json, never typed by hand, so rerunning it after a new extraction keeps
the catalog true (coverage, counts and hashes). Notion: Importar -> CSV.

Usage: python -m src.catalog   (after python -m src.manifest)
"""

import json
from pathlib import Path

import pandas as pd

from src import export
from src.ingest import gdelt, tvn_rss, tvn_web, usgs, worldbank
from src.ingest.common import WINDOW_END, WINDOW_START
from src.nlp import classify, cluster, embed, provenance

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MANIFEST_PATH = ROOT / "data" / "manifest.json"
OUTPUT_PATH = ROOT / "docs" / "notion" / "catalogo.csv"
COLUMNS = ["Fuente", "URL", "Fecha de extracción", "Cobertura", "Campos", "Licencia / condiciones",
           "Transformaciones", "SHA-256", "Archivo", "Filas"]
DAY = "%d/%m/%Y"
STAMP = "%d/%m/%Y %H:%M UTC"

NEWS_FIELDS = ("id_noticia, titulo, descripcion, url, medio, dominio, idioma, fecha_publicacion, fecha_deteccion, "
               "fecha_extraccion, origen, alcance_texto, procedencia_id, tema, tema_confianza, cluster_id, sintetico")
NEWS_STEPS = (f"URL normalizada e id_noticia = N- + SHA-1; HTML quitado; fechas a UTC; período 02/10/2025–30/09/2026 "
              f"(sin fecha = fuera); repetidas entre fuentes: se conserva TVN; validación B-05; tema con "
              f"{embed.MODEL_NAME.split('/')[-1]} (umbral {classify.THRESHOLD}); procedencia (agencia, casi copia "
              f"TF-IDF ≥ {provenance.NEAR_DUPLICATE} en 48 h, medio); clusters (distancia ≤ {cluster.DISTANCE_THRESHOLD}, "
              f"≥ {cluster.MIN_SHARED_WORDS} raíces en común, 72 h)")


def _range(dates: pd.Series) -> str:
    dates = dates.dropna()
    return f"{dates.min().strftime(DAY)} a {dates.max().strftime(DAY)}" if len(dates) else "sin fechas"


def _extracted(dates: pd.Series) -> str:
    dates = pd.to_datetime(dates.dropna(), utc=True)
    first, last = dates.min(), dates.max()
    return first.strftime(STAMP) if first == last else f"{first.strftime(STAMP)} a {last.strftime(STAMP)}"


def partial_note(dates: pd.Series) -> str:
    """Says so when the source does not reach both ends of the news period (a month or more short)."""
    dates = dates.dropna()
    month = pd.Timedelta(days=31)
    if len(dates) and (dates.min() - WINDOW_START > month or WINDOW_END - dates.max() > month):
        return (" COBERTURA PARCIAL: el resto del período está pendiente por el límite de consultas de GDELT; "
                "se actualiza al terminar la descarga.")
    return ""


def _files(manifest: dict) -> dict[str, dict]:
    return {f["ruta"]: f for f in manifest["archivos"]}


def news_rows(news: pd.DataFrame, files: dict) -> list[dict]:
    parquet = files.get("data/processed/noticias.parquet", {})
    csv = files.get("data/processed/noticias.csv", {})
    sha = (f"noticias.parquet {parquet.get('sha256', '—')} · noticias.csv {csv.get('sha256', '—')} "
           f"(archivo común de las 3 fuentes de noticias)")
    rows = []
    specs = [
        ("TVN · RSS", "tvn_rss", tvn_rss.FEED_URL, "fecha_publicacion",
         "Feed RSS público: solo lo que el feed tenía al descargar (no guarda histórico)."),
        ("TVN · web (sitemaps)", "tvn_web", tvn_web.SITEMAP_URL.format(key="<YYYY>_<MM>"), "fecha_publicacion",
         f"Hasta {tvn_web.PER_MONTH} artículos por mes, todas las secciones, orden SHA-1 de la URL; metadatos JSON-LD; respeta robots.txt."),
        ("GDELT DOC 2.0", "gdelt", gdelt.API_URL, "fecha_deteccion",
         "4 consultas sobre Panamá (logística, turismo, economía, eventos naturales), una por mes; máx. 250 por consulta; deduplicado por URL. "
         "Fechas = seendate (detección), no publicación."),
    ]
    for name, origin, url, date_col, how in specs:
        group = news[news["origen"] == origin]
        languages = ", ".join(f"{k} {v}" for k, v in group["idioma"].value_counts().head(4).items())
        if origin == "gdelt":
            how += partial_note(group[date_col])
        rows.append({
            "Fuente": name,
            "URL": url,
            "Fecha de extracción": _extracted(group["fecha_extraccion"]),
            "Cobertura": f"{len(group)} noticias; {date_col} {_range(group[date_col])}; idiomas: {languages}; "
                         f"{group['dominio'].nunique()} dominio(s). {how}",
            "Campos": NEWS_FIELDS,
            "Licencia / condiciones": export.GDELT_TERMS if origin == "gdelt" else export.TVN_TERMS,
            "Transformaciones": NEWS_STEPS,
            "SHA-256": sha,
            "Archivo": "data/processed/noticias.parquet · noticias.csv · fuentes.json",
            "Filas": len(group),
        })
    return rows


def official_rows(files: dict) -> list[dict]:
    rows = []
    wb = files.get("data/processed/indicadores.csv")
    if wb:
        grid = pd.read_csv(PROCESSED / "indicadores.csv")
        rows.append({
            "Fuente": "Banco Mundial · Indicators API v2",
            "URL": worldbank.API_URL.format(countries=";".join(worldbank.COUNTRIES), indicator="<indicador>")
                   + f"?date={worldbank.YEARS[0]}:{worldbank.YEARS[-1]}&format=json&per_page={worldbank.PER_PAGE}",
            "Fecha de extracción": _extracted(grid["fecha_extraccion"]),
            "Cobertura": f"{', '.join(worldbank.COUNTRIES)} × {len(worldbank.INDICATORS)} indicadores "
                         f"({', '.join(worldbank.INDICATORS)}) × {worldbank.YEARS[0]}–{worldbank.YEARS[-1]} = {len(grid)} "
                         f"combinaciones; {int(grid['valor'].isna().sum())} sin dato (nulo). Series anuales: no miden el presente.",
            "Campos": "pais_iso3, indicador_id, anio, valor (nullable), unidad, fuente_url, fecha_extraccion, licencia",
            "Licencia / condiciones": f"{worldbank.LICENSE}, con atribución al Banco Mundial; revisar excepciones de terceros por indicador.",
            "Transformaciones": "Una consulta por indicador; cuadrícula completa país × indicador × año con nulo donde falta "
                                "(nunca 0); unidad por indicador; contexto oficial por regla escrita (B-14).",
            "SHA-256": wb["sha256"],
            "Archivo": wb["ruta"],
            "Filas": wb["filas"],
        })
    ev = files.get("data/processed/eventos.geojson")
    if ev:
        events = json.loads((PROCESSED / "eventos.geojson").read_text(encoding="utf-8"))
        mags = [f["properties"]["magnitude"] for f in events["features"] if f["properties"].get("magnitude") is not None]
        times = pd.to_datetime([f["properties"]["time"] for f in events["features"]], utc=True)
        rows.append({
            "Fuente": "USGS · FDSN Event Web Service",
            "URL": usgs.query_url(),
            "Fecha de extracción": pd.Timestamp(events["metadata"]["fecha_extraccion"]).strftime(STAMP),
            "Cobertura": f"{len(events['features'])} sismos, {times.min().strftime(DAY)} a {times.max().strftime(DAY)}, "
                         f"magnitud {min(mags)}–{max(mags)}; caja lat 5–12, lon −86 a −76 (no es el territorio de Panamá). "
                         f"Solo hechos sísmicos.",
            "Campos": "id, magnitude, time, updated, longitude, latitude, depth, place, status, url",
            "Licencia / condiciones": usgs.LICENSE + "; confirmar condiciones de elementos de terceros.",
            "Transformaciones": "Todos los eventos devueltos; propiedades del contrato; time y updated a ISO 8601 UTC.",
            "SHA-256": ev["sha256"],
            "Archivo": ev["ruta"],
            "Filas": ev["filas"],
        })
    return rows


def build_catalog() -> pd.DataFrame:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    files = _files(manifest)
    news = pd.read_parquet(PROCESSED / "noticias.parquet")
    return pd.DataFrame(news_rows(news, files) + official_rows(files), columns=COLUMNS)


def main() -> None:
    catalog = build_catalog()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(OUTPUT_PATH, index=False, encoding="utf-8", lineterminator="\n")
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} with {len(catalog)} sources")


if __name__ == "__main__":
    main()
