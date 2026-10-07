"""Data catalog for Notion (B-15). Owner: B."""

import pandas as pd

from src.catalog import COLUMNS, build_catalog, partial_note

REQUIRED = ["Fuente", "URL", "Fecha de extracción", "Cobertura", "Campos", "Licencia / condiciones",
            "Transformaciones", "SHA-256"]


def test_partial_coverage_is_said_only_when_a_month_or_more_is_missing():
    full = pd.Series(pd.to_datetime(["2025-10-03T00:00:00Z", "2026-09-29T00:00:00Z"]))
    september = pd.Series(pd.to_datetime(["2026-09-01T00:00:00Z", "2026-09-30T00:00:00Z"]))
    assert partial_note(full) == ""
    assert "COBERTURA PARCIAL" in partial_note(september)


def test_catalog_has_the_eight_required_fields_filled_for_every_source():
    catalog = build_catalog()  # reads the delivered data/processed files and data/manifest.json
    assert list(catalog.columns) == COLUMNS
    assert set(REQUIRED) <= set(catalog.columns)
    assert {"TVN · RSS", "TVN · web (sitemaps)", "GDELT DOC 2.0"} <= set(catalog["Fuente"])
    assert catalog[REQUIRED].notna().all().all()
    assert (catalog[REQUIRED].astype(str).apply(lambda c: c.str.strip()) != "").all().all()
