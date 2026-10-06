"""T08 · High-priority case. Owner: José (J-05) for the score; Cristian (C-13) for the UI.

Prepared input: Cluster with P >= 70.
Expected result: Shows the 5 components and the rule version; does not enable publishing.
Source: section 9 of docs/reto.pdf.

Score side covered here; the "no publish" part is UI (C-13/C-15: there is no publish
action, only review states) and is checked in the C-08 run.
"""

from pathlib import Path

import pandas as pd

from src.score import score_clusters

STUB_PATH = Path(__file__).resolve().parents[1] / "data" / "stub" / "noticias_stub.parquet"


def test_t08():
    """High priority exposes R, I, U, N, E and the rules version; evidence state is not implied by P."""
    scored = score_clusters(pd.read_parquet(STUB_PATH), now=pd.Timestamp("2026-10-06T18:00:00Z"))
    high = scored[scored["P"] >= 70]
    assert not high.empty
    for _, row in high.iterrows():
        assert all(pd.notna(row[c]) for c in ("R", "I", "U", "N", "E"))
        assert row["version_reglas"] == "scoring_v1"
        assert row["rango"] == "alto"
    # Same band, different evidence states: priority does not decide evidence.
    assert high["estado_evidencia"].nunique() > 1
