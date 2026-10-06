"""USGS earthquakes (B-04). Owner: B.

Offline: builds eventos.geojson from hand-written FDSN payloads, so no test touches the network.
"""

import json

import pytest

from src.ingest.usgs import (
    BOX,
    LICENSE,
    PROPERTIES,
    build_collection,
    parse_response,
    query_url,
    read_events,
    write_events,
)

EXTRACTED_AT = "2026-10-06T21:00:00Z"


def feature(event_id: str, time_ms: int | None = 1735513210566, mag=4.0, place="9 km NW of San Juan del Sur, Nicaragua", depth=100.943) -> dict:
    """One event as the FDSN API returns it (subset of properties)."""
    return {
        "type": "Feature",
        "id": event_id,
        "properties": {
            "mag": mag,
            "place": place,
            "time": time_ms,
            "updated": 1741473552040,
            "url": f"https://earthquake.usgs.gov/earthquakes/eventpage/{event_id}",
            "status": "reviewed",
            "type": "earthquake",
        },
        "geometry": {"type": "Point", "coordinates": [-85.9299, 11.3207, depth]},
    }


def payload(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "metadata": {"status": 200, "count": len(features)}, "features": features}


def test_query_matches_the_challenge():
    url = query_url()
    assert BOX == {"minlatitude": 5, "maxlatitude": 12, "minlongitude": -86, "maxlongitude": -76}
    for part in ("format=geojson", "starttime=2024-01-01", "endtime=2024-12-31T23:59:59", "minmagnitude=3",
                 "minlatitude=5", "maxlatitude=12", "minlongitude=-86", "maxlongitude=-76", "eventtype=earthquake"):
        assert part in url


def test_properties_follow_the_contract():
    collection = build_collection([feature("us1")], EXTRACTED_AT, query_url())
    props = collection["features"][0]["properties"]
    assert list(props) == PROPERTIES
    assert props["id"] == "us1"
    assert props["magnitude"] == 4.0
    assert (props["longitude"], props["latitude"], props["depth"]) == (-85.9299, 11.3207, 100.943)
    assert props["place"] == "9 km NW of San Juan del Sur, Nicaragua"  # kept as is, never "Panamá"


def test_times_are_iso_utc():
    props = build_collection([feature("us1")], EXTRACTED_AT, query_url())["features"][0]["properties"]
    assert props["time"] == "2024-12-29T23:00:10.566Z"
    assert props["updated"] == "2025-03-08T22:39:12.040Z"


def test_missing_values_stay_null():
    collection = build_collection([feature("us1", mag=None, place=None, depth=None)], EXTRACTED_AT, query_url())
    props = collection["features"][0]["properties"]
    assert props["magnitude"] is None
    assert props["place"] is None
    assert props["depth"] is None


def test_geometry_and_provenance_are_kept():
    collection = build_collection([feature("us1")], EXTRACTED_AT, query_url())
    assert collection["type"] == "FeatureCollection"
    assert collection["features"][0]["geometry"] == {"type": "Point", "coordinates": [-85.9299, 11.3207, 100.943]}
    meta = collection["metadata"]
    assert meta["fuente_url"] == query_url()
    assert meta["fecha_extraccion"] == EXTRACTED_AT
    assert meta["licencia"] == LICENSE
    assert meta["n_eventos"] == 1


def test_duplicates_are_dropped_and_order_is_stable():
    collection = build_collection([feature("us2", time_ms=1720000000000), feature("us1"), feature("us2", time_ms=1720000000000)], EXTRACTED_AT, query_url())
    assert [f["properties"]["id"] for f in collection["features"]] == ["us2", "us1"]  # by time, then id


def test_parse_response_raises_on_error_status():
    with pytest.raises(RuntimeError, match="400"):
        parse_response({"metadata": {"status": 400}, "features": []})


def test_parse_response_returns_features():
    assert parse_response(payload([feature("us1")])) == [feature("us1")]


def test_file_round_trip(tmp_path):
    path = tmp_path / "eventos.geojson"
    collection = build_collection([feature("us1", place=None)], EXTRACTED_AT, query_url())
    write_events(collection, path)
    assert json.loads(path.read_text(encoding="utf-8")) == collection
    events = read_events(path)
    assert list(events.columns) == PROPERTIES
    assert events["place"].isna().all()
