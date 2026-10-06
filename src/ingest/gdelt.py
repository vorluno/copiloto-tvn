"""GDELT DOC 2.0 ingestion (B-02). Owner: B.

mode=ArtList, format=json, maxrecords=250, one query per topic (QUERIES) and per
calendar month of the agreed period (2025-10-02 to 2026-09-30, common.py), because
each request returns at most 250 articles; a month that hits 250 is reported as
saturated. Articles are deduplicated by normalized URL and kept only when their
seendate falls inside the period.

GDELT gives no outlet date: seendate goes to fecha_deteccion and fecha_publicacion
stays null (never copied). Only headline and metadata: alcance_texto is
"titular/metadatos" and descripcion is null. GDELT has no outlet name, so medio is the
domain.

GDELT asks for one request every 5 seconds but in practice blocks longer: requests
are spaced by PAUSE_S, a rate-limit answer is retried with a growing wait, and if it
persists the run stops cleanly, keeps what it saved and lists what is pending
(`--resume` finishes the newest run without repeating requests). Raw answers go to
data/raw/gdelt/<extraction UTC>/<query>_<window start>.json and the corpus is rebuilt
from every stored run (first extraction wins), like the TVN RSS.

Usage: python -m src.ingest.gdelt [--resume]   (src.ingest.news builds the file)
"""

import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from src.ingest.common import WINDOW_END, WINDOW_START, finalize, in_window, news_id, provisional_cluster

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "gdelt"
API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
QUERIES = {
    "logistica": '(Panama OR Panamá) (canal OR logística OR logistica OR puerto OR shipping)',
    "turismo": '(Panama OR Panamá) (turismo OR tourism OR turistas)',
    "economia": '(Panama OR Panamá) (economía OR economia OR economy OR inflación OR empleo)',
    "eventos_naturales": '(Panama OR Panamá) (sismo OR terremoto OR inundación OR inundaciones OR earthquake OR flood)',
}
MAX_RECORDS = 250
PAUSE_S = 20
RETRY_WAITS_S = (30, 60, 120)
TIMEOUT_S = 60
STAMP = "%Y%m%dT%H%M%SZ"
# GDELT language name -> ISO 639-1; a name not listed is kept as GDELT writes it (lowercase).
LANGUAGES = {
    "spanish": "es", "english": "en", "portuguese": "pt", "french": "fr", "german": "de", "italian": "it",
    "chinese": "zh", "greek": "el", "ukrainian": "uk", "polish": "pl", "arabic": "ar", "korean": "ko",
    "indonesian": "id", "russian": "ru", "japanese": "ja", "croatian": "hr", "malayalam": "ml", "turkish": "tr",
    "romanian": "ro", "bengali": "bn", "lithuanian": "lt", "czech": "cs", "persian": "fa", "serbian": "sr",
    "dutch": "nl", "swedish": "sv", "hindi": "hi", "vietnamese": "vi", "hebrew": "he", "catalan": "ca",
}


class RateLimited(Exception):
    """GDELT answered with its plain-text rate-limit message instead of JSON."""


def snapshot_dir(extracted_at: pd.Timestamp, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / extracted_at.strftime(STAMP)


def date_windows(start: pd.Timestamp = WINDOW_START, end: pd.Timestamp = WINDOW_END) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Contiguous [start, end) windows, one per calendar month of the period."""
    edges = [start, *(m for m in pd.date_range(start, end, freq="MS") if start < m < end), end]
    return list(zip(edges[:-1], edges[1:]))


def parse_response(text: str) -> list[dict]:
    try:
        body = json.loads(text)
    except json.JSONDecodeError as exc:
        if "limit requests" in text.lower():
            raise RateLimited(text[:120]) from exc
        raise RuntimeError(f"GDELT returned non-JSON: {text[:120]!r}") from exc
    return body.get("articles") or []


def _domain(value: str | None) -> str | None:
    value = (value or "").strip().lower()
    return value.removeprefix("www.") or None


def parse_articles(articles: list[dict], extracted_at: pd.Timestamp) -> pd.DataFrame:
    """One row per unique URL in the noticias.parquet contract."""
    rows = []
    for art in articles:
        url = (art.get("url") or "").strip()
        language = (art.get("language") or "").strip()
        rows.append({
            "id_noticia": news_id(url) if url else None,
            "titulo": (art.get("title") or "").strip() or None,
            "descripcion": None,
            "url": url or None,
            "medio": _domain(art.get("domain")),
            "dominio": _domain(art.get("domain")),
            "idioma": LANGUAGES.get(language.lower(), language.lower() or None),
            "fecha_publicacion": None,
            "fecha_deteccion": pd.to_datetime(art.get("seendate"), format=STAMP, utc=True, errors="coerce"),
            "fecha_extraccion": extracted_at,
            "origen": "gdelt",
            "alcance_texto": "titular/metadatos",
            "sintetico": False,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return finalize(df)
    df = df.drop_duplicates("id_noticia", keep="first")
    df["cluster_id"] = provisional_cluster(df["id_noticia"].fillna("N-"))
    return finalize(df)


def _request(query: str, start: pd.Timestamp, end: pd.Timestamp) -> str:
    params = {"query": query, "mode": "ArtList", "format": "json", "maxrecords": MAX_RECORDS, "sort": "DateDesc",
              "startdatetime": start.strftime("%Y%m%d%H%M%S"), "enddatetime": end.strftime("%Y%m%d%H%M%S")}
    for wait in (*RETRY_WAITS_S, None):
        response = requests.get(API_URL, params=params, timeout=TIMEOUT_S, headers={"User-Agent": "copiloto-tvn/1.0 (hackIAthon)"})
        try:
            if response.status_code == 429:
                raise RateLimited(response.text[:120])
            response.raise_for_status()
            parse_response(response.text)
            return response.text
        except RateLimited:
            if wait is None:
                raise
            time.sleep(wait)
    raise AssertionError("unreachable")


def fetch_run(raw_dir: Path = RAW_DIR, request=None, sleep=time.sleep, resume: Path | None = None) -> tuple[Path, list[str], list[str]]:
    """Download every query x window, saving each answer as it arrives.

    Returns (run folder, saturated requests, pending requests). A persistent rate limit
    stops the run without raising: what was saved stays, the rest is listed as pending
    and `resume=<folder>` finishes it later without repeating saved requests.
    """
    request = request or _request
    if resume is not None:
        folder, extracted_at = resume, pd.to_datetime(resume.name, format=STAMP, utc=True)
    else:
        extracted_at = pd.Timestamp.now(tz="UTC").floor("s")
        folder = snapshot_dir(extracted_at, raw_dir)
    folder.mkdir(parents=True, exist_ok=True)
    # Newest window first, every topic per window: a run cut by the rate limit still
    # covers all four topics and the most recent days.
    todo = [(key, query, start, end) for start, end in reversed(date_windows()) for key, query in QUERIES.items()]
    saturated, pending = [], []
    for key, query, start, end in todo:
        path = folder / f"{key}_{start.strftime('%Y%m%d')}.json"
        label = f"{key} {start:%Y-%m-%d}"
        if any(raw_dir.glob(f"*/{path.name}")) or path.exists():
            continue  # the period is fixed: a request saved by any run is not asked again
        if pending:  # blocked already: list the rest without asking again
            pending.append(label)
            continue
        try:
            text = request(query, start, end)
        except RateLimited:
            pending.append(label)
            continue
        path.write_text(text, encoding="utf-8")
        if len(parse_response(text)) >= MAX_RECORDS:
            saturated.append(label)
        sleep(PAUSE_S)
    return folder, saturated, pending


def load_snapshots(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Every stored run, deduplicated by id (first extraction wins), within the window."""
    frames = []
    for folder in sorted(p for p in raw_dir.glob("*") if p.is_dir()):
        extracted_at = pd.to_datetime(folder.name, format=STAMP, utc=True)
        articles = [a for path in sorted(folder.glob("*.json")) for a in parse_response(path.read_text(encoding="utf-8"))]
        frames.append(parse_articles(articles, extracted_at))
    frames = [f for f in frames if not f.empty]
    if not frames:
        return finalize(pd.DataFrame())
    df = pd.concat(frames, ignore_index=True).sort_values("fecha_extraccion", kind="stable")
    df = df.drop_duplicates("id_noticia", keep="first")
    return finalize(df[in_window(df, "fecha_deteccion")])


def main() -> None:
    runs = sorted(p for p in RAW_DIR.glob("*") if p.is_dir()) if RAW_DIR.exists() else []
    resume = runs[-1] if "--resume" in sys.argv and runs else None
    folder, saturated, pending = fetch_run(resume=resume)
    df = load_snapshots()
    print(f"Saved {folder.relative_to(ROOT)}; {len(df)} unique GDELT articles in the window")
    if saturated:
        print(f"Saturated (hit {MAX_RECORDS}): {', '.join(saturated)}")
    if pending:
        print(f"GDELT rate limit: {len(pending)} requests pending. Run again later with --resume: {', '.join(pending)}")


if __name__ == "__main__":
    main()
