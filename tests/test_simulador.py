"""Weights simulator (J-16): same order as src.score with the official weights, weights normalized
to 100, re-ranking from the components already scored, and fast enough to feel live. Owner: Cristian."""

import time

import pandas as pd

from app import simulador as sim
from app import textos as tx
from src.score import load_rules, priority_band, rank


def _scored(n: int = 6) -> pd.DataFrame:
    """A small scored table shaped like score_clusters, ranked with its official weights."""
    rows = [
        {"cluster_id": "C-a", "R": 1.0, "I": 0.5, "U": 0.1, "N": 0.2, "E": 0.2},
        {"cluster_id": "C-b", "R": 0.1, "I": 0.9, "U": 1.0, "N": 1.0, "E": 1.0},
        {"cluster_id": "C-c", "R": 1.0, "I": 0.8, "U": 0.4, "N": 0.9, "E": 0.6},
        {"cluster_id": "C-d", "R": 0.5, "I": 0.3, "U": 1.0, "N": 0.1, "E": 0.2},
        {"cluster_id": "C-e", "R": 1.0, "I": 0.3, "U": 0.7, "N": 0.5, "E": 0.2},
        {"cluster_id": "C-f", "R": 1.0, "I": 0.3, "U": 0.4, "N": 0.5, "E": 0.2},
    ][:n]
    rules = load_rules()
    df = pd.DataFrame(rows)
    df["P"] = sum(rules["pesos"][k] * df[k] for k in sim.COMPONENTS).round(1)
    df["rango"] = df["P"].map(lambda p: priority_band(p, rules))
    return rank(df).reset_index(drop=True)


def test_weights_are_normalized_to_100():
    norm = sim.normalize({"R": 10, "I": 10, "U": 0, "N": 0, "E": 0})
    assert norm == {"R": 50.0, "I": 50.0, "U": 0.0, "N": 0.0, "E": 0.0}
    norm = sim.normalize({"R": 60, "I": 50, "U": 40, "N": 30, "E": 20})
    assert abs(sum(norm.values()) - 100) < 1e-9 and abs(norm["R"] - 30) < 1e-9
    assert sum(sim.normalize({"R": 0, "I": 0, "U": 0, "N": 0, "E": 0}).values()) == 100  # all zero: equal weights


def test_official_weights_give_the_official_order():
    rules = load_rules()
    scored = _scored()
    out = sim.simulate(scored, rules["pesos"], rules)
    assert list(out["cluster_id"]) == list(scored["cluster_id"])
    assert (out["cambio"] == 0).all() and list(out["P"]) == list(scored["P"])
    assert sim.is_official(rules["pesos"], rules) and sim.is_official({k: 2 * v for k, v in rules["pesos"].items()}, rules)


def test_other_weights_reorder_and_count_places_moved():
    rules = load_rules()
    scored = _scored()
    out = sim.simulate(scored, {"R": 0, "I": 0, "U": 100, "N": 0, "E": 0}, rules)
    # Only urgency counts: C-b and C-d (U=1.0) go first; tie broken by cluster_id, like src.score.
    assert list(out["cluster_id"][:2]) == ["C-b", "C-d"]
    assert list(out["P"][:2]) == [100.0, 100.0] and list(out["rango"][:2]) == ["alto", "alto"]
    moved = out.set_index("cluster_id")
    for cid, row in moved.iterrows():
        assert row["cambio"] == row["posicion_oficial"] - row["posicion"]
    assert tx.puestos(3) == "↑ 3" and tx.puestos(-2) == "↓ 2" and tx.puestos(0) == "="


def test_events_pushed_out_of_the_top_are_listed():
    rules = load_rules()
    out = sim.simulate(_scored(), {"R": 0, "I": 0, "U": 100, "N": 0, "E": 0}, rules)
    gone = sim.left_top(out, n=2)
    assert set(gone["cluster_id"]) == set(_scored()["cluster_id"][:2]) - {"C-b", "C-d"}


def test_simulation_does_not_touch_the_official_table_and_is_fast():
    rules = load_rules()
    big = pd.concat([_scored().assign(cluster_id=lambda d, i=i: d["cluster_id"] + f"-{i}") for i in range(1500)])
    big = rank(big).reset_index(drop=True)  # 9,000 events, more than the real corpus
    before = big.copy()
    started = time.perf_counter()
    out = sim.simulate(big, {"R": 10, "I": 40, "U": 20, "N": 20, "E": 10}, rules)
    assert time.perf_counter() - started < 1.0
    pd.testing.assert_frame_equal(big, before)
    assert len(out) == len(big) and out["posicion"].tolist() == list(range(1, len(big) + 1))
