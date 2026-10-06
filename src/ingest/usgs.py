"""USGS FDSN earthquake ingestion (B-04). Owner: B.

format=geojson, 2024, lat 5 to 12, lon -86 to -76, M>=3, earthquakes only. Keeps every
event the query returns, without a fixed count. The regional box is not Panama's
territory: `place` is kept exactly as USGS writes it, and these rows only back seismic
facts (never floods, damage or losses).

Each feature carries the contract properties (id, magnitude, time, updated, longitude,
latitude, depth, place, status, url) with times as ISO 8601 UTC and missing values as
null. The collection's `metadata` records the query URL, extraction time and license.

Raw response goes to data/raw/usgs/ (git-ignored); the output to
data/processed/eventos.geojson.

Usage: python -m src.ingest.usgs
"""

import json
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "usgs"
OUTPUT_PATH = ROOT / "data" / "processed" / "eventos.geojson"

API_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
BOX = {"minlatitude": 5, "maxlatitude": 12, "minlongitude": -86, "maxlongitude": -76}
START, END = "2024-01-01", "2024-12-31T23:59:59"
MIN_MAGNITUDE = 3
LICENSE = "Dominio público (USGS)"
PROPERTIES = ["id", "magnitude", "time", "updated", "longitude", "latitude", "depth", "place", "status", "url"]
TIMEOUT_S = 60


def query_url() -> str:
    """Public, reproducible URL of the query (also the collection's fuente_url)."""
    params = {"format": "geojson", "starttime": START, "endtime": END, **BOX,
              "minmagnitude": MIN_MAGNITUDE, "eventtype": "earthquake", "orderby": "time-asc"}
    return f"{API_URL}?{urlencode(params, safe=':')}"


def parse_response(body: dict) -> list[dict]:
    """Return the features; raise if the API reports an error status."""
    status = body.get("metadata", {}).get("status", 200)
    if status != 200:
        raise RuntimeError(f"USGS API error: status {status}")
    return body.get("features") or []


def fetch_events() -> list[dict]:
    """Download the query and keep the raw response."""
    response = requests.get(query_url(), timeout=TIMEOUT_S)
    response.raise_for_status()
    body = response.json()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "eventos_2024.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return parse_response(body)


def _iso_utc(epoch_ms: int | None) -> str | None:
    if epoch_ms is None:
        return None
    return pd.Timestamp(epoch_ms, unit="ms", tz="UTC").strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _coordinate(coords: list, index: int) -> float | None:
    return coords[index] if len(coords) > index else None


def build_collection(features: list[dict], extracted_at: str, source_url: str) -> dict:
    """GeoJSON FeatureCollection with flat contract properties, one feature per event id."""
    by_id = {}
    for feat in features:
        props = feat.get("properties") or {}
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        by_id[feat["id"]] = {
            "type": "Feature",
            "geometry": feat.get("geometry"),
            "properties": {
                "id": feat["id"],
                "magnitude": props.get("mag"),
                "time": _iso_utc(props.get("time")),
                "updated": _iso_utc(props.get("updated")),
                "longitude": _coordinate(coords, 0),
                "latitude": _coordinate(coords, 1),
                "depth": _coordinate(coords, 2),
                "place": props.get("place"),
                "status": props.get("status"),
                "url": props.get("url"),
            },
        }
    ordered = sorted(by_id.values(), key=lambda f: (f["properties"]["time"] or "", f["properties"]["id"]))
    return {
        "type": "FeatureCollection",
        "metadata": {
            "fuente_url": source_url,
            "fecha_extraccion": extracted_at,
            "licencia": LICENSE,
            "n_eventos": len(ordered),
        },
        "features": ordered,
    }


def write_events(collection: dict, path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection, ensure_ascii=False, indent=1), encoding="utf-8")


def read_events(path: Path = OUTPUT_PATH) -> pd.DataFrame:
    """One row per event with the contract columns."""
    collection = json.loads(path.read_text(encoding="utf-8"))
    return pd.DataFrame([f["properties"] for f in collection["features"]], columns=PROPERTIES)


def main() -> None:
    extracted_at = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    collection = build_collection(fetch_events(), extracted_at, query_url())
    write_events(collection)
    print(f"Wrote {collection['metadata']['n_eventos']} events to {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
