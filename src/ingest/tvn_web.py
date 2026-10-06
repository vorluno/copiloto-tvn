"""TVN website ingestion from its public sitemaps (B-01). Owner: B.

The organization does not deliver a snapshot, so the TVN corpus for the agreed period
(2025-10-02 to 2026-09-30, common.py) is built by scraping, within robots.txt
(https://www.tvn-2.com/robots.txt allows everything except /api/, /buscador/, /tag/):

1. Monthly sitemaps https://www.tvn-2.com/tvn_sitemap_contents_<YYYY>_<MM>.xml list
   every URL of the month (about 2,300). Their lastmod is a modification date, not
   the publication date, so it is not used as one.
2. Up to PER_MONTH articles per month are read in a reproducible order (SHA-1 of the
   normalized URL), across all sections. Only metadata is kept, from the page's
   schema.org NewsArticle (JSON-LD): headline, description and datePublished. The
   article body, images and video are never stored: the page grants no license.
3. The quota counts only articles published inside the period.

origen="tvn_web"; alcance_texto="descripcion_web" when there is a description,
"titular/metadatos" otherwise; fecha_deteccion is null (no seendate) and a missing
datePublished stays null (and is then excluded by the period).

Up to WORKERS pages are downloaded at once, each worker pausing PAUSE_S after every
article (about one page per second in total), and requests carry an identifying
User-Agent. Each sitemap and each
article's extracted metadata is stored under data/raw/tvn_web/ (git-ignored), so a run
resumes without fetching anything twice.

Usage: python -m src.ingest.tvn_web   (src.ingest.news builds the file)
"""

import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd
import requests

from src.ingest.common import WINDOW_END, WINDOW_START, finalize, in_window, news_id, normalize_url, plain_text, provisional_cluster, to_utc

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "tvn_web"
SITEMAP_URL = "https://www.tvn-2.com/tvn_sitemap_contents_{key}.xml"
DISALLOWED = ("/api/", "/buscador/", "/tag/")
PER_MONTH = 100
MAX_CANDIDATES = 2 * PER_MONTH
PAUSE_S = 1.0  # per worker, after each article
WORKERS = 3  # parallel downloads: about 1 page per second in total
TIMEOUT_S = 30
USER_AGENT = "copiloto-tvn/1.0 (hackIAthon; metadata only)"
MEDIO, DOMINIO, IDIOMA = "TVN", "tvn-2.com", "es"
LD_JSON = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
META_PUBLISHED = re.compile(r'<meta[^>]+property="article:published_time"[^>]+content="([^"]+)"', re.I)


def month_keys(start: pd.Timestamp = WINDOW_START, end: pd.Timestamp = WINDOW_END) -> list[str]:
    """Sitemap keys (YYYY_MM) for every month that overlaps the period."""
    months = pd.period_range(start.tz_convert(None), (end - pd.Timedelta(seconds=1)).tz_convert(None), freq="M")
    return [f"{p.year}_{p.month:02d}" for p in months]


def parse_sitemap(content: bytes) -> list[str]:
    """Article URLs of a sitemap, skipping paths that robots.txt disallows."""
    urls = []
    for loc in ET.fromstring(content).iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
        url = (loc.text or "").strip()
        parts = urlsplit(url)
        if parts.netloc.endswith(DOMINIO) and not parts.path.startswith(DISALLOWED):
            urls.append(url)
    return urls


def sample_order(urls: list[str]) -> list[str]:
    """Reproducible order that does not depend on the sitemap's order."""
    return sorted(set(urls), key=lambda u: hashlib.sha1(normalize_url(u).encode("utf-8")).hexdigest())


def _news_article(html_text: str) -> dict | None:
    for block in LD_JSON.findall(html_text):
        try:
            data = json.loads(block, strict=False)
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            kinds = item.get("@type") if isinstance(item, dict) else None
            kinds = kinds if isinstance(kinds, list) else [kinds]
            if any(isinstance(k, str) and k.endswith("Article") for k in kinds):
                return item
    return None


def parse_article(html_text: str, url: str, fetched_at: pd.Timestamp) -> dict | None:
    """Contract row from the page's NewsArticle metadata; None if the page is not an article."""
    article = _news_article(html_text)
    title = plain_text(article.get("headline")) if article else None
    if not title:
        return None
    description = plain_text(article.get("description"))
    raw_date = article.get("datePublished")
    if not raw_date and (meta := META_PUBLISHED.search(html_text)):
        raw_date = meta.group(1)
    try:
        published = pd.to_datetime(raw_date, utc=True) if raw_date else None
    except (ValueError, TypeError):
        published = None
    return {
        "id_noticia": news_id(url),
        "titulo": title,
        "descripcion": description,
        "url": url,
        "medio": MEDIO,
        "dominio": DOMINIO,
        "idioma": IDIOMA,
        "fecha_publicacion": published,
        "fecha_deteccion": None,
        "fecha_extraccion": fetched_at,
        "origen": "tvn_web",
        "alcance_texto": "descripcion_web" if description else "titular/metadatos",
        "sintetico": False,
    }


def _http_get(url: str) -> bytes:
    response = requests.get(url, timeout=TIMEOUT_S, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.content


def _in_period(published: str | None) -> bool:
    if not published:
        return False
    stamp = pd.Timestamp(published)
    return WINDOW_START <= stamp < WINDOW_END


def _fetch_record(url: str, path: Path, get, sleep) -> dict | None:
    """Stored record for one URL, fetching it if needed; None on a network error (retried later)."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    fetched_at = pd.Timestamp.now(tz="UTC").floor("s")
    try:
        content = get(url)
    except requests.RequestException:
        return None
    row = parse_article(content.decode("utf-8", errors="replace"), url, fetched_at)
    record = {"url": url, "skip": True} if row is None else {k: (v.isoformat() if isinstance(v, pd.Timestamp) else v) for k, v in row.items()}
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    sleep(PAUSE_S)
    return record


def collect(months: list[str], raw_dir: Path = RAW_DIR, get=_http_get, sleep=time.sleep, workers: int = WORKERS) -> dict[str, int]:
    """Fetch up to PER_MONTH in-period articles per month; returns the count kept per month.

    Candidates are taken in sample order in batches of at most `workers` and of at most
    the articles still missing, so parallel and sequential runs keep the same articles
    and never overshoot the quota.
    """
    (raw_dir / "sitemaps").mkdir(parents=True, exist_ok=True)
    (raw_dir / "articles").mkdir(parents=True, exist_ok=True)
    kept_by_month = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for key in months:
            sitemap_path = raw_dir / "sitemaps" / f"contents_{key}.xml"
            if not sitemap_path.exists():
                sitemap_path.write_bytes(get(SITEMAP_URL.format(key=key)))
                sleep(PAUSE_S)
            candidates = sample_order(parse_sitemap(sitemap_path.read_bytes()))[:MAX_CANDIDATES]
            kept, pos = 0, 0
            while kept < PER_MONTH and pos < len(candidates):
                batch = candidates[pos: pos + min(workers, PER_MONTH - kept)]
                pos += len(batch)
                paths = [raw_dir / "articles" / f"{news_id(url)}.json" for url in batch]
                for record in pool.map(lambda args: _fetch_record(*args, get, sleep), zip(batch, paths)):
                    if record and not record.get("skip") and _in_period(record.get("fecha_publicacion")):
                        kept += 1
            kept_by_month[key] = kept
    return kept_by_month


def load_articles(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Every stored article inside the period, deduplicated by id."""
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((raw_dir / "articles").glob("*.json"))] if (raw_dir / "articles").exists() else []
    df = pd.DataFrame([r for r in records if not r.get("skip")])
    if df.empty:
        return finalize(df)
    for col in ("fecha_publicacion", "fecha_extraccion"):
        df[col] = to_utc(df[col])
    df = df.sort_values("fecha_extraccion", kind="stable").drop_duplicates("id_noticia", keep="first")
    df["cluster_id"] = provisional_cluster(df["id_noticia"])
    return finalize(df[in_window(df, "fecha_publicacion")])


def main() -> None:
    kept = collect(month_keys())
    print(f"TVN web: {sum(kept.values())} articles in the period {kept}")


if __name__ == "__main__":
    main()
