"""The synthetic case cards follow the fichas.jsonl contract. Owner: José.

Guards the fixture the frontend (C-12..C-14) is built on: every citation points to a
real stub item and its passage appears verbatim in the cited field.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

STUB_DIR = Path(__file__).resolve().parents[1] / "data" / "stub"
CONTRACT_FIELDS = [
    "id_caso", "modalidad", "ids_fuente", "afirmaciones", "citas", "puntaje",
    "componentes", "estado_evidencia", "borrador", "estado_revision",
]
REVIEW_STATES = {"nuevo", "en revisión", "requiere evidencia", "aprobado como borrador", "descartado"}
EVIDENCE_STATES = {"insuficiente", "parcial", "suficiente para el borrador"}
CLAIM_TYPES = {"hecho", "declaracion", "inferencia", "hipotesis"}


@pytest.fixture(scope="module")
def cards() -> list[dict]:
    with (STUB_DIR / "fichas_stub.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


@pytest.fixture(scope="module")
def news() -> pd.DataFrame:
    return pd.read_parquet(STUB_DIR / "noticias_stub.parquet").set_index("id_noticia")


def test_contract_fields_and_enums(cards):
    for card in cards:
        assert not [f for f in CONTRACT_FIELDS if f not in card], card["id_caso"]
        assert card["estado_revision"] in REVIEW_STATES
        assert card["estado_evidencia"] in EVIDENCE_STATES
        assert card["sintetico"] is True


def test_citations_are_verbatim(cards, news):
    for card in cards:
        claims_citations = [c for claim in card["afirmaciones"] for c in claim["citas"]]
        for citation in claims_citations + card["citas"]:
            assert citation["id_fuente"] in card["ids_fuente"]
            assert citation["pasaje"] in news.loc[citation["id_fuente"], citation["campo"]]


def test_every_claim_is_typed_and_cited(cards):
    for card in cards:
        for claim in card["afirmaciones"]:
            assert claim["tipo"] in CLAIM_TYPES
            assert claim["citas"], f"uncited claim in {card['id_caso']}"


def test_score_matches_formula(cards):
    weights = {"R": 30, "I": 25, "U": 20, "N": 15, "E": 10}
    for card in cards:
        if card["puntaje"] is None:
            assert card["componentes"] is None  # null, never 0
            continue
        expected = sum(weights[k] * v for k, v in card["componentes"].items())
        assert card["puntaje"]["P"] == pytest.approx(expected, abs=0.1)


def test_abstentions_make_no_claims(cards):
    for card in cards:
        if card["abstencion"]:
            assert card["afirmaciones"] == []
            assert card["motivo_abstencion"]
