"""Prioritized inbox (C-12). Owner: Cristian."""

from pathlib import Path

import pandas as pd
import pytest

from app.bandeja import build_inbox, filter_inbox, read_cards, records_label, urgency_basis_label
from src.score import score_clusters

STUB_DIR = Path(__file__).resolve().parents[1] / "data" / "stub"
NOW = pd.Timestamp("2026-10-06 20:00", tz="UTC")  # fixed so U does not depend on the clock


@pytest.fixture(scope="module")
def news() -> pd.DataFrame:
    return pd.read_parquet(STUB_DIR / "noticias_stub.parquet")


@pytest.fixture(scope="module")
def inbox(news) -> pd.DataFrame:
    cards = read_cards(STUB_DIR / "fichas_stub.jsonl")
    return build_inbox(score_clusters(news, now=NOW), news, cards)


def test_one_row_per_cluster_with_score_untouched(inbox, news):
    assert sorted(inbox["cluster_id"]) == sorted(news["cluster_id"].dropna().unique())
    expected = score_clusters(news, now=NOW).set_index("cluster_id")["P"]
    assert inbox.set_index("cluster_id")["P"].equals(expected.loc[inbox["cluster_id"]])


def test_top_n_keeps_score_order_and_filters(inbox):
    top = filter_inbox(inbox)
    assert len(top) == 5
    assert list(top["P"]) == sorted(top["P"], reverse=True)
    only = filter_inbox(inbox, estados=["parcial"], top_n=None)
    assert set(only["estado_evidencia"]) == {"parcial"}


def test_cards_join_by_cluster(inbox):
    canal = inbox.set_index("cluster_id").loc["C-STUB-01"]
    assert canal["id_caso"] == "F-STUB-01"
    # The headline is real evidence; the card's generated title goes in its own column.
    assert canal["titulo_propuesto"] == "Límite de calado en el Canal por bajo nivel de Gatún"
    assert canal["titular"] != canal["titulo_propuesto"]
    assert canal["id_titular"].startswith("N-")
    no_card = inbox[inbox["id_caso"].isna()]
    assert not no_card.empty and no_card["estado_revision"].isna().all()  # null, not "nuevo"
    assert no_card["titular"].notna().all() and no_card["titulo_propuesto"].isna().all()


def test_labels_keep_nulls_visible():
    assert records_label(3, 2) == "3 registros · 2 procedencias"
    assert records_label(1, 1) == "1 registro · 1 procedencia"
    assert records_label(None, float("nan")) == "— registros · — procedencias"
    assert urgency_basis_label("deteccion") == "detección (GDELT)"
    assert urgency_basis_label(None) == "—"
