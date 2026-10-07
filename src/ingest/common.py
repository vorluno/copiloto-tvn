"""Shared helpers for the news sources (B-01, B-02). Owner: B.

- NEWS_COLUMNS: the noticias.parquet contract (CLAUDE.md §3) plus `sintetico`.
- id_noticia: "N-" + first 10 hex chars of the SHA-1 of the normalized URL, stable
  across runs and sources.
- Window: [WINDOW_START, WINDOW_END) = 2025-10-02 to 2026-09-30 in UTC, agreed on
  6 oct (answers alcance-y-datos.md §6.2): it excludes [2024-01-01, 2025-10-01) and
  the current, incomplete month. A news item without a date is excluded.
- Until B-07/B-08, tema/tema_confianza/procedencia_id stay null and every item is its
  own provisional cluster ("K-" + its id hash), so scoring and the app keep working
  without inventing a topic or a grouping.
"""

import hashlib
import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import pandas as pd

NEWS_COLUMNS = [
    "id_noticia", "titulo", "descripcion", "url", "medio", "dominio", "idioma",
    "fecha_publicacion", "fecha_deteccion", "fecha_extraccion", "origen",
    "alcance_texto", "procedencia_id", "tema", "tema_confianza", "cluster_id", "sintetico",
]
DATE_COLUMNS = ["fecha_publicacion", "fecha_deteccion", "fecha_extraccion"]
# Period agreed on 6 oct: 2025-10-02 to the last full month (September 2026), in UTC.
WINDOW_START = pd.Timestamp("2025-10-02T00:00:00Z")
WINDOW_END = pd.Timestamp("2026-10-01T00:00:00Z")  # exclusive
TRACKING_PARAMS = re.compile(r"^(utm_\w+|fbclid|gclid|ocid|cmpid)$", re.IGNORECASE)
TAG = re.compile(r"<[^>]+>")


def normalize_url(url: str) -> str:
    """Lowercase, no fragment, no tracking parameters, no trailing slash."""
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, "")).lower().rstrip("/")


def news_id(url: str) -> str:
    return "N-" + hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()[:10]


def provisional_cluster(news_ids: pd.Series) -> pd.Series:
    """One cluster per item until B-08 groups events."""
    return "K-" + news_ids.str[2:]


def plain_text(value: str | None) -> str | None:
    """Strip HTML tags and entities; empty text becomes null."""
    if value is None:
        return None
    text = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", value))).strip()
    return text or None


def to_utc(values) -> pd.Series:
    return pd.to_datetime(pd.Series(values, dtype=object), utc=True)


def in_window(df: pd.DataFrame, date_column: str) -> pd.Series:
    """True when the date falls in [WINDOW_START, WINDOW_END). A null date is excluded:
    it cannot be shown to fall inside the period."""
    dates = df[date_column]
    return dates.notna() & (dates >= WINDOW_START) & (dates < WINDOW_END)


def finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Contract column order and types."""
    out = df.reindex(columns=NEWS_COLUMNS)
    for col in DATE_COLUMNS:
        out[col] = pd.to_datetime(out[col], utc=True)
    out["tema_confianza"] = out["tema_confianza"].astype("float64")
    out["sintetico"] = out["sintetico"].fillna(False).astype(bool)
    for col in ("procedencia_id", "tema"):
        out[col] = out[col].astype(object)
    return out.reset_index(drop=True)
