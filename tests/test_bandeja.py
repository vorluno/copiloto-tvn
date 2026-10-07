"""Prioritized inbox (C-12). Owner: Cristian."""

from pathlib import Path

import pandas as pd
import pytest

import app.bandeja as bandeja
from app.bandeja import build_inbox, filter_inbox, load_cards, read_cards, records_label, urgency_basis_label
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


def test_stub_cards_only_next_to_stub_news(tmp_path, monkeypatch):
    # Rule 12: synthetic cards never sit next to the real corpus.
    empty = tmp_path / "fichas.jsonl"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr(bandeja, "FICHAS_PATH", empty)
    stub_cards, stub_path = load_cards(news_from_stub=True)
    assert stub_cards and all(c["sintetico"] for c in stub_cards) and stub_path.endswith("fichas_stub.jsonl")
    assert load_cards(news_from_stub=False) == ([], None)
    real = tmp_path / "real.jsonl"
    real.write_text('{"id_caso": "F-C-1", "cluster_id": "C-1"}\n', encoding="utf-8")
    monkeypatch.setattr(bandeja, "FICHAS_PATH", real)
    monkeypatch.setattr(bandeja, "ROOT", tmp_path)
    assert load_cards(news_from_stub=False) == ([{"id_caso": "F-C-1", "cluster_id": "C-1"}], "real.jsonl")


def test_inbox_selection_moves_the_ficha_only_when_it_changes():
    # Reruns: the table keeps "K-3" selected while the editor picks another case in the Ficha.
    last, moves = None, []
    for selected in ["K-3", "K-3", "K-3", None, "K-3", "K-5"]:
        moves.append(bandeja.inbox_pick(selected, last))
        last = selected
    assert moves == ["K-3", None, None, None, "K-3", "K-5"]


def test_null_headline_is_never_the_one_shown(news):
    # Real corpus: GDELT rows can come without titulo; the newest one must not blank the cluster.
    holes = news.copy()
    cluster = holes.loc[0, "cluster_id"]
    newest = holes[holes["cluster_id"] == cluster].index
    holes.loc[newest, "fecha_deteccion"] = pd.NaT
    extra = holes.loc[[newest[0]]].assign(id_noticia="N-0000000000", titulo=None,
                                          fecha_publicacion=pd.Timestamp("2030-01-01", tz="UTC"))
    holes = pd.concat([holes, extra], ignore_index=True)
    inbox = build_inbox(score_clusters(holes, now=NOW), holes, [])
    row = inbox.set_index("cluster_id").loc[cluster]
    assert pd.notna(row["titular"]) and row["id_titular"] != "N-0000000000"
    assert bandeja.headline_label(None) == bandeja.headline_label(float("nan")) == "— (sin titular)"
