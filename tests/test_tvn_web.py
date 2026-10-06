"""TVN website ingestion from its public sitemaps (B-01). Owner: B.

Offline: parses hand-written sitemaps and article pages, so no test touches the network.
"""

import json

import pandas as pd

from src.ingest.common import NEWS_COLUMNS
from src.ingest.tvn_web import (
    PER_MONTH,
    collect,
    load_articles,
    month_keys,
    parse_article,
    parse_sitemap,
    sample_order,
)

FETCHED_AT = pd.Timestamp("2026-10-06T22:00:00Z")


def page(headline: str | None = "Ejecutivo frena ley", description: str | None = "El presidente devolvió el proyecto &amp; más.",
         published: str | None = "2025-10-31T23:55:16+00:00", kind: str = "NewsArticle") -> str:
    ld = {"@context": "https://schema.org", "@type": kind}
    if headline:
        ld["headline"] = headline
    if description:
        ld["description"] = description
    if published:
        ld["datePublished"] = published
    return (
        '<html><head><meta name="description" content="El ">'
        f'<meta property="og:title" content="{headline or ""}">'
        f'<script type="application/ld+json">{json.dumps(ld)}</script></head><body>cuerpo</body></html>'
    )


def sitemap(*urls: str) -> bytes:
    body = "".join(f"<url><loc>{u}</loc><lastmod>2025-10-31T23:55:16Z</lastmod></url>" for u in urls)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'.encode()


def test_months_cover_the_period():
    keys = month_keys()
    assert keys[0] == "2025_10" and keys[-1] == "2026_09" and len(keys) == 12


def test_sitemap_skips_paths_disallowed_by_robots():
    urls = parse_sitemap(sitemap("https://www.tvn-2.com/nacionales/a_1_1.html", "https://www.tvn-2.com/tag/canal",
                                 "https://www.tvn-2.com/buscador/?q=x", "https://www.tvn-2.com/api/x"))
    assert urls == ["https://www.tvn-2.com/nacionales/a_1_1.html"]


def test_sample_order_is_reproducible_and_independent_of_input_order():
    urls = [f"https://www.tvn-2.com/n/{i}_1_{i}.html" for i in range(50)]
    assert sample_order(urls) == sample_order(list(reversed(urls)))
    assert sorted(sample_order(urls)) == sorted(urls)


def test_article_metadata_follows_the_contract():
    row = parse_article(page(), "https://www.tvn-2.com/nacionales/a_1_1.html", FETCHED_AT)
    assert row["titulo"] == "Ejecutivo frena ley"
    assert row["descripcion"] == "El presidente devolvió el proyecto & más."  # from JSON-LD, not the broken meta
    assert row["fecha_publicacion"] == pd.Timestamp("2025-10-31T23:55:16Z")
    assert row["fecha_deteccion"] is None
    assert row["fecha_extraccion"] == FETCHED_AT
    assert row["origen"] == "tvn_web"
    assert row["alcance_texto"] == "descripcion_web"
    assert (row["medio"], row["dominio"], row["idioma"]) == ("TVN", "tvn-2.com", "es")
    assert "cuerpo" not in json.dumps(row, default=str)  # never the article body


def test_article_without_description_is_headline_only():
    row = parse_article(page(description=None), "https://www.tvn-2.com/a_1_1.html", FETCHED_AT)
    assert row["descripcion"] is None
    assert row["alcance_texto"] == "titular/metadatos"


def test_article_without_date_keeps_it_null():
    row = parse_article(page(published=None), "https://www.tvn-2.com/a_1_1.html", FETCHED_AT)
    assert row["fecha_publicacion"] is None


def test_page_that_is_not_an_article_is_skipped():
    assert parse_article(page(kind="WebPage"), "https://www.tvn-2.com/seccion", FETCHED_AT) is None
    assert parse_article("<html></html>", "https://www.tvn-2.com/x", FETCHED_AT) is None


def test_collect_keeps_per_month_quota_and_resumes(tmp_path):
    urls = [f"https://www.tvn-2.com/n/{i}_1_{i}.html" for i in range(PER_MONTH + 30)]
    fetched = []

    def fake_get(url):
        if url.endswith(".xml"):
            return sitemap(*urls)
        fetched.append(url)
        n = int(url.rsplit("_", 1)[1].split(".")[0])
        published = "2025-09-30T12:00:00+00:00" if n % 10 == 0 else "2025-10-15T12:00:00+00:00"  # some out of the period
        return page(headline=f"Nota {n}", published=published).encode()

    collect(["2025_10"], tmp_path, get=fake_get, sleep=lambda s: None)
    df = load_articles(tmp_path)
    assert len(df) == PER_MONTH  # quota counts only articles inside the period
    assert list(df.columns) == NEWS_COLUMNS
    first_round = len(fetched)
    collect(["2025_10"], tmp_path, get=fake_get, sleep=lambda s: None)
    assert len(fetched) == first_round  # nothing fetched twice
