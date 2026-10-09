"""Weights simulator for Fuentes y datos (J-16). Owner: Cristian; built with José.

"What if the weights were different?": the jury can move the five weights and see how the
top 10 would change, to argue for (or against) a new rules version. It never rescores the
corpus: it reuses the components R, I, U, N, E that src.score already computed for each event
and only recombines them, P = sum(weight x component), with the same rounding, ranges and
tie-break as src.score (rank, priority_band). Nothing is written: the official order stays the
one from rules/scoring_v1.yaml. Pure functions, no Streamlit.
"""

import pandas as pd

from src.score import load_rules, priority_band, rank

COMPONENTS = ("R", "I", "U", "N", "E")


def official_rules() -> dict:
    """Version, weights and ranges exactly as rules/scoring_v1.yaml has them (validated by src.score)."""
    return load_rules()


def normalize(weights: dict) -> dict[str, float]:
    """Scale the five weights so they add up to 100. All zero (or missing) falls back to equal weights."""
    raw = {k: max(0.0, float(weights.get(k) or 0.0)) for k in COMPONENTS}
    total = sum(raw.values())
    if total <= 0:
        return {k: 100.0 / len(COMPONENTS) for k in COMPONENTS}
    return {k: 100.0 * v / total for k, v in raw.items()}


def is_official(weights: dict, rules: dict) -> bool:
    norm = normalize(weights)
    return all(abs(norm[k] - float(rules["pesos"][k])) < 1e-9 for k in COMPONENTS)


def simulate(scored: pd.DataFrame, weights: dict, rules: dict) -> pd.DataFrame:
    """Every event re-ranked with the normalized weights.

    Returns cluster_id, the official position, P and range, the simulated ones and `cambio`
    (official position minus simulated: positive means it goes up). Same tie-break as src.score.
    """
    if scored.empty:
        return pd.DataFrame(columns=["cluster_id", "posicion_oficial", "P_oficial", "rango_oficial",
                                     "posicion", "P", "rango", "cambio"])
    norm = normalize(weights)
    base = scored[["cluster_id", "posicion", "P", "rango", *COMPONENTS]].rename(
        columns={"posicion": "posicion_oficial", "P": "P_oficial", "rango": "rango_oficial"})
    p = sum(norm[k] * base[k] for k in COMPONENTS).round(1)
    ranked = rank(base.assign(P=p))  # P desc, then U desc, then cluster_id asc (ADR-006)
    ranked["rango"] = ranked["P"].map(lambda value: priority_band(value, rules) if pd.notna(value) else None)
    ranked["cambio"] = ranked["posicion_oficial"] - ranked["posicion"]
    return ranked.reset_index(drop=True)


def top(simulated: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return simulated.sort_values("posicion").head(n)


def left_top(simulated: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Events in the official top n that the simulation pushes out of it."""
    out = simulated[(simulated["posicion_oficial"] <= n) & (simulated["posicion"] > n)]
    return out.sort_values("posicion_oficial")
