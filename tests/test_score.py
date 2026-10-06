"""Priority score P (J-05). Owner: José.

Runs score_clusters on the synthetic stub with a fixed clock, so results are exact.
"""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.score import RULES_PATH, evidence_state, load_rules, priority_band, rank, score_clusters, topic_key

STUB_PATH = Path(__file__).resolve().parents[1] / "data" / "stub" / "noticias_stub.parquet"
NOW = pd.Timestamp("2026-10-06T18:00:00Z")
WEIGHTS = {"R": 30, "I": 25, "U": 20, "N": 15, "E": 10}


@pytest.fixture(scope="module")
def news() -> pd.DataFrame:
    return pd.read_parquet(STUB_PATH)


@pytest.fixture(scope="module")
def scored(news) -> pd.DataFrame:
    return score_clusters(news, now=NOW).set_index("cluster_id")


def test_one_row_per_cluster_with_components(news, scored):
    assert set(scored.index) == set(news["cluster_id"])
    for col in ("P", "R", "I", "U", "N", "E", "rango", "estado_evidencia", "version_reglas"):
        assert scored[col].notna().all(), col
    assert ((scored[["R", "I", "U", "N", "E"]] >= 0) & (scored[["R", "I", "U", "N", "E"]] <= 1)).all().all()


def test_p_is_the_weighted_sum(scored):
    expected = sum(WEIGHTS[k] * scored[k] for k in WEIGHTS)
    assert (scored["P"] - expected).abs().max() <= 0.06


def test_two_runs_give_the_same_order(news):
    first = score_clusters(news, now=NOW)
    second = score_clusters(news.sample(frac=1, random_state=7), now=NOW)
    assert first["cluster_id"].tolist() == second["cluster_id"].tolist()
    assert first["P"].tolist() == second["P"].tolist()


def test_ties_break_by_urgency_then_id(news):
    twin = news[news["cluster_id"] == "C-STUB-05"].assign(cluster_id="C-STUB-00")
    ranked = score_clusters(pd.concat([news, twin]), now=NOW)
    pair = ranked[ranked["cluster_id"].isin(["C-STUB-00", "C-STUB-05"])]
    assert pair["P"].nunique() == 1
    assert pair["cluster_id"].tolist() == ["C-STUB-00", "C-STUB-05"]


def test_rank_breaks_ties_by_urgency_then_id():
    tied = pd.DataFrame({"cluster_id": ["C-B", "C-A", "C-C", "C-D"], "P": [50.0, 50.0, 50.0, 80.0],
                         "U": [0.4, 0.4, 1.0, 0.1]})
    assert rank(tied)["cluster_id"].tolist() == ["C-D", "C-C", "C-A", "C-B"]
    assert rank(tied)["posicion"].tolist() == [1, 2, 3, 4]


def test_t02_duplicates_do_not_triple_evidence(scored):
    # 3 records, two of them the same EFE story: 2 independent provenances, not 3.
    canal = scored.loc["C-STUB-01"]
    assert canal["n_registros"] == 3
    assert canal["n_procedencias_independientes"] == 2
    assert canal["E"] == pytest.approx(0.6 * 2 / 3)


def test_missing_provenance_falls_back_to_domain(news):
    canal = news[news["cluster_id"] == "C-STUB-01"].copy()
    canal["procedencia_id"] = None
    scored = score_clusters(canal, now=NOW).iloc[0]
    assert scored["n_procedencias_independientes"] == canal["dominio"].nunique()


def test_t03_recirculated_item_scores_as_old(scored):
    quake = scored.loc["C-STUB-02"]
    assert quake["recirculada"]
    assert quake["fecha_referencia_urgencia"].year == 2025
    assert quake["U"] == 0.1


def test_detection_date_used_only_without_outlet_date(scored):
    assert scored.loc["C-STUB-04", "base_urgencia"] == "deteccion"
    assert (scored.drop(index="C-STUB-04")["base_urgencia"] == "publicacion").all()


def test_relevance_rule(scored):
    assert scored.loc["C-STUB-01", "R"] == 1.0  # Panama + topic
    assert scored.loc["C-STUB-07", "R"] == 0.5  # topic, no Panama mention
    assert scored.loc["C-STUB-03", "R"] == 0.1  # off-topic (injected instruction)


def test_t08_high_priority_does_not_mean_sufficient_evidence(scored):
    # T08 (score side): a high-priority cluster exposes its 5 components and rules
    # version, and its evidence state is computed apart from P.
    high = scored[scored["rango"] == "alto"]
    assert not high.empty
    assert (high["estado_evidencia"] != "suficiente para el borrador").all()
    assert (high["version_reglas"] == "scoring_v1").all()


def test_official_context_raises_impact_and_evidence(news):
    contexto = pd.DataFrame([{"cluster_id": "C-STUB-01", "id_evidencia": "WB-PAN-NY.GDP.MKTP.KD.ZG-2023",
                              "tipo": "indicador", "regla": "ejemplo", "nota": "sintético"}])
    without = score_clusters(news, now=NOW).set_index("cluster_id").loc["C-STUB-01"]
    with_ctx = score_clusters(news, contexto=contexto, now=NOW).set_index("cluster_id").loc["C-STUB-01"]
    assert not without["contexto_disponible"] and with_ctx["contexto_disponible"]
    assert with_ctx["I"] == pytest.approx(without["I"] + 0.4)
    assert with_ctx["E"] == pytest.approx(without["E"] + 0.4)
    assert with_ctx["estado_evidencia"] == "suficiente para el borrador"


@pytest.mark.parametrize("provenances, official, expected", [
    (1, False, "insuficiente"), (0, False, "insuficiente"), (2, False, "parcial"),
    (1, True, "parcial"), (2, True, "suficiente para el borrador"),
])
def test_evidence_state(provenances, official, expected):
    assert evidence_state(provenances, official) == expected


@pytest.mark.parametrize("p, band", [(0, "bajo"), (39.9, "bajo"), (40, "medio"), (69.9, "medio"),
                                     (70, "alto"), (100, "alto")])
def test_bands_have_no_overlap(p, band):
    assert priority_band(p, load_rules()) == band


def test_topic_keys_match_yaml():
    reach = load_rules()["I_impacto"]["alcance_tema"]
    for topic in ("economía", "logística/Canal", "turismo", "servicios públicos", "eventos naturales", "regulación"):
        assert topic_key(topic) in reach


def test_formula_drift_is_refused(tmp_path):
    rules = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    rules["E_evidencia"]["formula"] = "1.0 * procedencias"
    edited = tmp_path / "scoring_edit.yaml"
    edited.write_text(yaml.safe_dump(rules, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="E_evidencia"):
        load_rules(edited)
