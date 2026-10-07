"""Development benchmark format (C-06). Owner: Cristian.

Checks the file José's runner reads (src/eval/run_benchmark.py): fields, types, unique
IDs, the challenge's proportion as a ceiling, and that every expected evidence ID
exists in the corpus, so a case never points to evidence the agent cannot see.
"""

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmark" / "benchmark_dev.jsonl"
NEWS = ROOT / "data" / "processed" / "noticias.parquet"
INDICATORS = ROOT / "data" / "processed" / "indicadores.csv"
FIELDS = {"id", "tipo", "consulta", "respuesta_esperada", "ids_evidencia_esperados", "sintetico"}
TARGET = {"sustentada": 20, "contradiccion": 7, "sin_respuesta": 7, "adversarial": 6}  # 40, as 30/10/10/10 of 60


@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return [json.loads(line) for line in BENCHMARK.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_fields_types_and_ids(cases):
    assert cases, "benchmark_dev.jsonl is empty"
    for case in cases:
        assert set(case) == FIELDS, case.get("id")
        assert re.fullmatch(r"BQ-\d{3}", case["id"])
        assert case["tipo"] in TARGET
        assert case["consulta"].strip() and case["respuesta_esperada"].strip()
        assert isinstance(case["sintetico"], bool) and isinstance(case["ids_evidencia_esperados"], list)
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate IDs"


def test_proportion_never_exceeds_the_target(cases):
    counts = Counter(c["tipo"] for c in cases)
    assert all(counts[t] <= n for t, n in TARGET.items()), counts


def test_unanswerable_cases_expect_no_evidence(cases):
    for case in cases:
        if case["tipo"] == "sin_respuesta":
            assert case["ids_evidencia_esperados"] == [], case["id"]


def test_expected_evidence_exists_in_the_corpus(cases):
    expected = {i for c in cases for i in c["ids_evidencia_esperados"]}
    news_ids = set(pd.read_parquet(NEWS, columns=["id_noticia"])["id_noticia"]) if NEWS.exists() else set()
    wb = pd.read_csv(INDICATORS, dtype=str) if INDICATORS.exists() else pd.DataFrame(
        columns=["pais_iso3", "indicador_id", "anio", "valor"])
    wb_ids = {f"WB-{r.pais_iso3}-{r.indicador_id}-{r.anio}" for r in wb.itertuples() if r.valor}
    for evidence_id in expected:
        if evidence_id.startswith("N-"):
            assert evidence_id in news_ids, f"{evidence_id} is not in noticias.parquet"
        elif evidence_id.startswith("WB-"):
            assert evidence_id in wb_ids, f"{evidence_id} is not a non-null World Bank cell"
