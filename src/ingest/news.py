"""Builds data/processed/noticias.parquet from the news sources (B-01, B-02). Owner: B.

Reads the stored raw snapshots (no network), puts TVN first so an article that GDELT
also lists keeps the TVN row (it has the description), validates with B-05 and writes
the valid rows plus outputs/reports/calidad.md. A repeat across sources is not a data
error, so it is counted in the report instead of being listed as "ID duplicado".

Usage: python -m src.ingest.news
"""

from pathlib import Path

import pandas as pd

from src.ingest import tvn_rss
from src.ingest.common import finalize
from src.validate import ValidationResult, build_report, validate_news, write_report

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "data" / "processed" / "noticias.parquet"


def build_news(frames: list[pd.DataFrame]) -> tuple[ValidationResult, int]:
    """(validation result, rows dropped because another source already had the URL)."""
    frames = [f for f in frames if not f.empty]
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    combined = finalize(combined)
    has_id = combined["id_noticia"].notna()
    repeated = has_id & combined.duplicated("id_noticia", keep="first")
    result = validate_news(combined[~repeated])
    result.valid = finalize(result.valid)
    return result, int(repeated.sum())


def sources() -> list[pd.DataFrame]:
    """TVN first: on a shared URL its row wins."""
    return [tvn_rss.load_snapshots()]


def main() -> None:
    from src.ingest.usgs import read_events
    from src.ingest.worldbank import read_indicators
    from src.validate import EVENTS_PATH, INDICATORS_PATH

    result, n_cross = build_news(sources())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.valid.to_parquet(OUTPUT_PATH, index=False)

    indicators = read_indicators(INDICATORS_PATH) if INDICATORS_PATH.exists() else None
    events = read_events(EVENTS_PATH) if EVENTS_PATH.exists() else None
    generated_at = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    report = build_report(result, indicators, events, generated_at)
    report = report.replace("- Filas separadas:", f"- Repetidas entre fuentes (se conserva TVN): {n_cross}\n- Filas separadas:", 1)
    write_report(report)
    by_source = result.valid["origen"].value_counts().to_dict()
    print(f"Wrote {len(result.valid)} news to {OUTPUT_PATH.relative_to(ROOT)} {by_source}; "
          f"{len(result.rejected)} split out, {n_cross} cross-source repeats")


if __name__ == "__main__":
    main()
