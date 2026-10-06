"""TVN RSS ingestion (B-01). Owner: B.

Feed: https://www.tvn-2.com/rss/ (reference [2] of the challenge). Metadata only:
title, link, outlet date and description; the RSS description grants no license over
the article, video or images. alcance_texto is "descripcion_rss" when there is a
description and "titular/metadatos" otherwise. fecha_deteccion stays null (the RSS has
no seendate) and a missing pubDate stays null (never the extraction time).

The feed only keeps about one day of news, so every run stores the raw XML as
data/raw/tvn_rss/tvn_rss_<extraction UTC>.xml and the corpus is rebuilt from every
stored snapshot: an item keeps the extraction time of the first snapshot that had it.

Usage: python -m src.ingest.tvn_rss   (downloads one snapshot; src.ingest.news builds the file)
"""

from pathlib import Path

import feedparser
import pandas as pd
import requests

from src.ingest.common import finalize, in_window, news_id, plain_text, provisional_cluster, to_utc

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "tvn_rss"
FEED_URL = "https://www.tvn-2.com/rss/"
MEDIO, DOMINIO, IDIOMA = "TVN", "tvn-2.com", "es"
TIMEOUT_S = 30
STAMP = "%Y%m%dT%H%M%SZ"


def snapshot_path(extracted_at: pd.Timestamp, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / f"tvn_rss_{extracted_at.strftime(STAMP)}.xml"


def _published(entry) -> pd.Timestamp | None:
    raw = entry.get("published")
    if not raw:
        return None
    try:
        return pd.to_datetime(raw, utc=True)
    except (ValueError, TypeError):
        return None


def parse_feed(content: bytes, extracted_at: pd.Timestamp) -> pd.DataFrame:
    """One row per feed item in the noticias.parquet contract."""
    rows = []
    for entry in feedparser.parse(content).entries:
        link = (entry.get("link") or "").strip()
        description = plain_text(entry.get("summary"))
        rows.append({
            "id_noticia": news_id(link) if link else None,
            "titulo": plain_text(entry.get("title")),
            "descripcion": description,
            "url": link or None,
            "medio": MEDIO,
            "dominio": DOMINIO,
            "idioma": IDIOMA,
            "fecha_publicacion": _published(entry),
            "fecha_deteccion": None,
            "fecha_extraccion": extracted_at,
            "origen": "tvn_rss",
            "alcance_texto": "descripcion_rss" if description else "titular/metadatos",
            "sintetico": False,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return finalize(df)
    df["fecha_publicacion"] = to_utc(df["fecha_publicacion"])
    df["cluster_id"] = provisional_cluster(df["id_noticia"].fillna("N-"))
    return finalize(df)


def fetch_snapshot(raw_dir: Path = RAW_DIR) -> Path:
    """Download the feed once and store the raw XML."""
    extracted_at = pd.Timestamp.now(tz="UTC").floor("s")
    response = requests.get(FEED_URL, timeout=TIMEOUT_S, headers={"User-Agent": "copiloto-tvn/1.0 (hackIAthon)"})
    response.raise_for_status()
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(extracted_at, raw_dir)
    path.write_bytes(response.content)
    return path


def load_snapshots(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Every stored snapshot, deduplicated by id (first extraction wins), within the window."""
    frames = []
    for path in sorted(raw_dir.glob("tvn_rss_*.xml")):
        extracted_at = pd.to_datetime(path.stem.removeprefix("tvn_rss_"), format=STAMP, utc=True)
        frames.append(parse_feed(path.read_bytes(), extracted_at))
    if not frames:
        return finalize(pd.DataFrame())
    df = pd.concat(frames, ignore_index=True).sort_values("fecha_extraccion", kind="stable")
    df = df.drop_duplicates("id_noticia", keep="first")
    latest = df["fecha_extraccion"].max()
    return finalize(df[in_window(df, latest, "fecha_publicacion")])


def main() -> None:
    path = fetch_snapshot()
    print(f"Saved {path.relative_to(ROOT)}; {len(load_snapshots())} TVN items in the window")


if __name__ == "__main__":
    main()
