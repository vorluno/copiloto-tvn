"""TVN RSS ingestion (B-01) and shared news helpers. Owner: B.

Offline: parses hand-written RSS, so no test touches the network.
"""

import re

import pandas as pd

from src.ingest.common import NEWS_COLUMNS, news_id, normalize_url
from src.ingest.tvn_rss import load_snapshots, parse_feed, snapshot_path

EXTRACTED_AT = pd.Timestamp("2026-10-06T21:00:00Z")


def item(title: str, link: str, pub: str | None, description: str | None) -> str:
    parts = [f"<title>{title}</title>", f"<link>{link}</link>"]
    if pub:
        parts.append(f"<pubDate>{pub}</pubDate>")
    if description is not None:
        parts.append(f"<description><![CDATA[{description}]]></description>")
    return "<item>" + "".join(parts) + "</item>"


def feed(*items: str) -> bytes:
    body = "".join(items)
    return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Tvn Panamá - Portada</title>{body}</channel></rss>'.encode("utf-8")


FEED = feed(
    item("MOP solicita $43.1 millones", "https://www.tvn-2.com/nacionales/mop_1_1.html", "Tue, 06 Oct 2026 18:57:35 +0000",
         "<p>La discusión &amp; el presupuesto.</p>"),
    item("Sin descripción", "https://www.tvn-2.com/nacionales/sin_1_2.html", "Tue, 06 Oct 2026 08:00:00 -0500", None),
    item("Sin fecha", "https://www.tvn-2.com/nacionales/sinfecha_1_3.html", None, "Texto"),
)


def test_url_normalization_drops_noise():
    base = "https://www.tvn-2.com/nacionales/mop_1_1.html"
    assert normalize_url("HTTPS://WWW.TVN-2.com/nacionales/mop_1_1.html/") == base
    assert normalize_url(base + "#comentarios") == base
    assert normalize_url(base + "?utm_source=x&utm_medium=y") == base
    assert normalize_url(base + "?page=2&utm_source=x") == base + "?page=2"


def test_news_id_is_stable_and_follows_the_contract():
    a = news_id("https://www.tvn-2.com/a.html?utm_source=rss")
    assert a == news_id("https://www.tvn-2.com/a.html")
    assert re.fullmatch(r"N-[0-9a-f]{10}", a)


def test_parse_feed_follows_the_contract():
    df = parse_feed(FEED, EXTRACTED_AT)
    assert list(df.columns) == NEWS_COLUMNS
    assert len(df) == 3
    assert (df["origen"] == "tvn_rss").all()
    assert (df["medio"] == "TVN").all() and (df["dominio"] == "tvn-2.com").all()
    assert df["fecha_deteccion"].isna().all()  # RSS has no seendate
    assert (df["fecha_extraccion"] == EXTRACTED_AT).all()
    assert not df["sintetico"].any()


def test_description_is_plain_text_and_sets_alcance():
    df = parse_feed(FEED, EXTRACTED_AT).set_index("titulo")
    assert df.loc["MOP solicita $43.1 millones", "descripcion"] == "La discusión & el presupuesto."
    assert df.loc["MOP solicita $43.1 millones", "alcance_texto"] == "descripcion_rss"
    assert pd.isna(df.loc["Sin descripción", "descripcion"])
    assert df.loc["Sin descripción", "alcance_texto"] == "titular/metadatos"


def test_publication_date_is_utc_and_never_backfilled():
    df = parse_feed(FEED, EXTRACTED_AT).set_index("titulo")
    assert df.loc["Sin descripción", "fecha_publicacion"] == pd.Timestamp("2026-10-06T13:00:00Z")
    assert pd.isna(df.loc["Sin fecha", "fecha_publicacion"])  # not the extraction date


def test_nlp_columns_wait_for_b07_b08():
    df = parse_feed(FEED, EXTRACTED_AT)
    assert df["tema"].isna().all() and df["tema_confianza"].isna().all()
    assert df["procedencia_id"].isna().all()
    # provisional: each item is its own event until B-08 groups them
    assert df["cluster_id"].is_unique
    assert (df["cluster_id"] == "K-" + df["id_noticia"].str[2:]).all()


def test_snapshots_accumulate_and_keep_first_extraction(tmp_path):
    first = pd.Timestamp("2026-10-05T21:00:00Z")
    snapshot_path(first, tmp_path).write_bytes(feed(item("Ayer", "https://www.tvn-2.com/a_1_1.html", "Mon, 05 Oct 2026 12:00:00 +0000", "x")))
    snapshot_path(EXTRACTED_AT, tmp_path).write_bytes(feed(
        item("Ayer", "https://www.tvn-2.com/a_1_1.html", "Mon, 05 Oct 2026 12:00:00 +0000", "x"),
        item("Hoy", "https://www.tvn-2.com/b_1_2.html", "Tue, 06 Oct 2026 12:00:00 +0000", "y"),
    ))
    df = load_snapshots(tmp_path).set_index("titulo")
    assert sorted(df.index) == ["Ayer", "Hoy"]
    assert df.loc["Ayer", "fecha_extraccion"] == first


def test_window_drops_items_older_than_30_days(tmp_path):
    snapshot_path(EXTRACTED_AT, tmp_path).write_bytes(feed(
        item("Vieja", "https://www.tvn-2.com/v_1_1.html", "Fri, 04 Sep 2026 12:00:00 +0000", "x"),
        item("Reciente", "https://www.tvn-2.com/r_1_2.html", "Tue, 06 Oct 2026 12:00:00 +0000", "y"),
        item("Sin fecha", "https://www.tvn-2.com/s_1_3.html", None, "z"),
    ))
    df = load_snapshots(tmp_path)
    assert sorted(df["titulo"]) == ["Reciente", "Sin fecha"]  # no date: kept, cannot be judged
