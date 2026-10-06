"""Metrics (B-12, J-13): macro-F1 for AI vs baseline, pairwise cluster precision/recall, citation coverage, correct abstention, median and p95 latency. Always reported with numerator and denominator. Owners: B and José.

This file has two parts:
- Copilot metrics (J-13, José): below. Every metric is a `Ratio` (numerator,
  denominator, failures) so the report never hides errors behind a percentage.
- Classification and clustering metrics (B-12, Levi): to be added at the end.
"""

import math
from dataclasses import dataclass, field


@dataclass
class Ratio:
    name: str
    numerator: int = 0
    denominator: int = 0
    failures: list[str] = field(default_factory=list)
    goal: str = ""

    def add(self, ok: bool, case: str = "") -> None:
        self.denominator += 1
        if ok:
            self.numerator += 1
        elif case:
            self.failures.append(case)

    @property
    def value(self) -> float | None:
        """Share in [0, 1]; None when nothing was measured (never 0 by default)."""
        return None if self.denominator == 0 else self.numerator / self.denominator

    def describe(self) -> str:
        if self.value is None:
            return "sin casos"
        return f"{self.numerator}/{self.denominator} ({self.value:.0%})"


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile (q in 0..100); None for an empty list."""
    data = sorted(v for v in values if v is not None)
    if not data:
        return None
    rank = max(1, math.ceil(q / 100 * len(data)))
    return data[rank - 1]


def median(values: list[float]) -> float | None:
    data = sorted(v for v in values if v is not None)
    if not data:
        return None
    mid = len(data) // 2
    return data[mid] if len(data) % 2 else (data[mid - 1] + data[mid]) / 2


def cost_usd(prompt_tokens: int | None, completion_tokens: int | None,
             price_in_per_m: float | None, price_out_per_m: float | None) -> float | None:
    """USD for one call; None if tokens or prices are unknown (never assumed free)."""
    if None in (prompt_tokens, completion_tokens, price_in_per_m, price_out_per_m):
        return None
    return prompt_tokens / 1e6 * price_in_per_m + completion_tokens / 1e6 * price_out_per_m


# --- B-12 (Levi): macro-F1 de tema, precisión/recall por pares de clusters --------------------
