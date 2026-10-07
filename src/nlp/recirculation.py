"""Recirculated news (B-11, T03). Owner: B.

A news item is recirculated when the outlet published it long before it was detected:
fecha_deteccion - fecha_publicacion >= GAP. It keeps its original fecha_publicacion
(never replaced by the detection date), so:

- clustering compares it by its publication date, and it does not join this week's
  event as if it were new;
- src/score.py measures urgency from fecha_publicacion, so an old story scores as old;
- the case card says "No presentar como nuevo" (src/fichas.py, ACTION_RECIRCULATED).

GAP is 7 days: on the 213 GDELT items whose URL carries the outlet's date, detection
came 0 to 1 day after publication (7 oct), so a week is far beyond normal lag.

Limit: the rule needs both dates on one item. Today no source gives both (TVN has no
seendate; GDELT has no outlet date), so the real corpus has no recirculated item. The
open proposal for José is in the B-11 PR: keep GDELT's seendate on a TVN row when GDELT
detected the same URL.
"""

import pandas as pd

GAP = pd.Timedelta(days=7)


def mark_recirculated(news: pd.DataFrame, gap: pd.Timedelta = GAP) -> pd.Series:
    """True when detection came `gap` or more after publication; False when a date is missing."""
    lag = news["fecha_deteccion"] - news["fecha_publicacion"]
    return (lag >= gap).fillna(False).astype(bool)
