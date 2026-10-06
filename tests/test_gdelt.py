"""GDELT DOC 2.0 ingestion (B-02). Owner: B.

Offline: parses hand-written ArtList payloads, so no test touches the network.
"""

import json

import pandas as pd
import pytest

from src.ingest.common import NEWS_COLUMNS
from src.ingest.gdelt import (
    QUERIES,
    RateLimited,
    date_windows,
    fetch_run,
    load_snapshots,
    parse_articles,
    parse_response,
    snapshot_dir,
)

EXTRACTED_AT = pd.Timestamp("2026-10-06T21:00:00Z")


def article(url: str, seendate: str = "20261006T143000Z", language: str = "Spanish", domain: str = "www.prensa.com", title: str = "Titular") -> dict:
    return {"url": url, "url_mobile": "", "title": title, "seendate": seendate, "socialimage": "",
            "domain": domain, "language": language, "sourcecountry": "Panama"}


def test_queries_cover_the_four_topics():
    assert set(QUERIES) == {"logistica", "turismo", "economia", "eventos_naturales"}
    assert all("Panama" in q for q in QUERIES.values())


def test_windows_split_the_period_without_gaps_or_overlap():
    end = pd.Timestamp("2026-10-06T21:00:00Z")
    windows = date_windows(end, days=30, step_days=6)
    assert len(windows) == 5
    assert windows[0][0] == end - pd.Timedelta(days=30)
    assert windows[-1][1] == end
    assert all(a[1] == b[0] for a, b in zip(windows, windows[1:]))


def test_articles_follow_the_contract():
    df = parse_articles([article("https://www.prensa.com/a")], EXTRACTED_AT)
    assert list(df.columns) == NEWS_COLUMNS
    row = df.iloc[0]
    assert row["origen"] == "gdelt"
    assert row["alcance_texto"] == "titular/metadatos"
    assert pd.isna(row["descripcion"])
    assert row["dominio"] == "prensa.com" and row["medio"] == "prensa.com"
    assert row["idioma"] == "es"
    assert row["fecha_extraccion"] == EXTRACTED_AT
    assert not row["sintetico"]


def test_languages_become_iso_codes():
    df = parse_articles([article("https://x.com/a", language="Greek"), article("https://x.com/b", language="Ukrainian"),
                         article("https://x.com/c", language="Klingon")], EXTRACTED_AT).set_index("url")
    assert df.loc["https://x.com/a", "idioma"] == "el"
    assert df.loc["https://x.com/b", "idioma"] == "uk"
    assert df.loc["https://x.com/c", "idioma"] == "klingon"  # unknown: GDELT's name, never invented


def test_seendate_is_detection_never_publication():
    row = parse_articles([article("https://www.prensa.com/a")], EXTRACTED_AT).iloc[0]
    assert row["fecha_deteccion"] == pd.Timestamp("2026-10-06T14:30:00Z")
    assert pd.isna(row["fecha_publicacion"])


def test_same_url_from_two_queries_is_one_row():
    df = parse_articles([article("https://www.prensa.com/a"), article("https://www.prensa.com/a?utm_source=gdelt")], EXTRACTED_AT)
    assert len(df) == 1


def test_parse_response_detects_rate_limit():
    with pytest.raises(RateLimited):
        parse_response("Please limit requests to one every 5 seconds or contact ...")


def test_parse_response_without_articles_is_empty():
    assert parse_response("{}") == []
    assert parse_response(json.dumps({"articles": [article("https://x.com/a")]})) == [article("https://x.com/a")]


def test_fetch_stops_cleanly_on_rate_limit_and_keeps_what_it_got(tmp_path):
    calls = []

    def fake_request(query, start, end):
        calls.append(query)
        if len(calls) == 3:
            raise RateLimited("Please limit requests")
        return json.dumps({"articles": [article(f"https://x.com/{len(calls)}")]})

    folder, saturated, pending = fetch_run(tmp_path, request=fake_request, sleep=lambda s: None)
    assert len(list(folder.glob("*.json"))) == 2  # the two answers before the block are saved
    assert len(pending) == len(QUERIES) * 5 - 2  # everything else is listed, nothing raised
    assert saturated == []


def test_fetch_asks_every_topic_for_the_newest_window_first(tmp_path):
    calls = []

    def fake_request(query, start, end):
        calls.append((query, start))
        return json.dumps({"articles": []})

    fetch_run(tmp_path, request=fake_request, sleep=lambda s: None)
    first = calls[: len(QUERIES)]
    assert {q for q, _ in first} == set(QUERIES.values())  # a partial run still covers every topic
    assert len({s for _, s in first}) == 1
    assert first[0][1] == max(s for _, s in calls)  # newest window first


def test_fetch_resumes_without_repeating_saved_requests(tmp_path):
    calls = []

    def fake_request(query, start, end):
        calls.append((query, start))
        return json.dumps({"articles": []})

    folder, _, _ = fetch_run(tmp_path, request=fake_request, sleep=lambda s: None)
    first_round = len(calls)
    _, _, pending = fetch_run(tmp_path, request=fake_request, sleep=lambda s: None, resume=folder)
    assert len(calls) == first_round  # nothing requested twice
    assert pending == []


def test_pending_never_lists_requests_already_saved(tmp_path):
    def blocked(query, start, end):
        raise RateLimited("Please limit requests")

    folder, _, _ = fetch_run(tmp_path, request=lambda q, s, e: json.dumps({"articles": []}), sleep=lambda s: None)
    saved = sorted(folder.glob("*.json"))
    saved[0].unlink()  # one request missing, the other 19 saved
    _, _, pending = fetch_run(tmp_path, request=blocked, sleep=lambda s: None, resume=folder)
    assert len(pending) == 1


def test_snapshots_accumulate_and_respect_the_window(tmp_path):
    first = pd.Timestamp("2026-10-05T21:00:00Z")
    for extracted, articles in (
        (first, [article("https://x.com/a", seendate="20261005T100000Z")]),
        (EXTRACTED_AT, [article("https://x.com/a", seendate="20261005T100000Z"),
                        article("https://x.com/b", seendate="20261006T100000Z"),
                        article("https://x.com/vieja", seendate="20260801T100000Z")]),
    ):
        folder = snapshot_dir(extracted, tmp_path)
        folder.mkdir(parents=True)
        (folder / "economia_20260906.json").write_text(json.dumps({"articles": articles}), encoding="utf-8")
    df = load_snapshots(tmp_path).set_index("url")
    assert sorted(df.index) == ["https://x.com/a", "https://x.com/b"]
    assert df.loc["https://x.com/a", "fecha_extraccion"] == first
