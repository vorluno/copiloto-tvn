"""Provenance (B-06, ADR-007). Owner: B.

procedencia_id names the original source of a news item, so a cluster counts
independent sources instead of records (5 outlets replicating EFE = 1 provenance).
Rules, applied in this order:

1. Default: the outlet itself, "P-<dominio>". Two items of the same outlet are not
   independent of each other.
2. Wire agency: when the title, description or outlet names an agency (EFE, AFP, AP,
   Reuters, Europa Press, Xinhua, Prensa Latina, ANSA, DPA, Bloomberg), the provenance
   is the agency, "P-AG-<agencia>". AP only counts as "(AP)" or "AP:" or "la AP", since
   the bare letters are too ambiguous.
3. Near copies: titles with TF-IDF cosine >= NEAR_DUPLICATE (0.9) on different domains
   within 48 h share one provenance. The group takes the agency if any member names
   one, otherwise the outlet of its earliest item (the likely original).

With only titles and short descriptions this is approximate: an outlet that rewrites an
agency piece without naming it keeps its own provenance. diccionario.md says so.
"""

import re

import numpy as np
import pandas as pd
from scipy.sparse.csgraph import connected_components
from scipy.sparse import coo_matrix
from sklearn.feature_extraction.text import TfidfVectorizer

NEAR_DUPLICATE = 0.9
WINDOW = pd.Timedelta(hours=48)
AGENCIES = {
    "EFE": r"\bEFE\b",
    "AFP": r"\bAFP\b",
    "AP": r"\(AP\)|\bAP:|\bla AP\b|\bAssociated Press\b",
    "Reuters": r"\bReuters\b",
    "Europa Press": r"\bEuropa Press\b",
    "Xinhua": r"\bXinhua\b",
    "Prensa Latina": r"\bPrensa Latina\b",
    "ANSA": r"\bANSA\b",
    "DPA": r"\bDPA\b|\bdpa\b",
    "Bloomberg": r"\bBloomberg\b",
}


def reference_time(news: pd.DataFrame) -> pd.Series:
    """Outlet date when there is one, otherwise GDELT's detection date. Only used to
    compare items in time; the two dates are never merged in the data."""
    return news["fecha_publicacion"].fillna(news["fecha_deteccion"])


def detect_agency(news: pd.DataFrame) -> pd.Series:
    """Agency named in title, description or outlet; null when none."""
    text = news["titulo"].fillna("") + " \n " + news["descripcion"].fillna("") + " \n " + news["medio"].fillna("")
    found = pd.Series(None, index=news.index, dtype=object)
    for agency, pattern in AGENCIES.items():
        hit = text.str.contains(pattern, regex=True) & found.isna()
        found[hit] = agency
    return found


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def near_copy_pairs(news: pd.DataFrame, threshold: float = NEAR_DUPLICATE,
                    window: pd.Timedelta = WINDOW) -> list[tuple[int, int]]:
    """Positional pairs of near-identical titles on different domains within `window`."""
    titles = news["titulo"].fillna("").tolist()
    if len(titles) < 2:
        return []
    vectors = TfidfVectorizer(strip_accents="unicode", lowercase=True).fit_transform(titles)
    sims = (vectors @ vectors.T).tocoo()
    keep = (sims.row < sims.col) & (sims.data >= threshold - 1e-9)
    when = reference_time(news).reset_index(drop=True)
    domain = news["dominio"].to_numpy()
    pairs = []
    for i, j in zip(sims.row[keep], sims.col[keep]):
        if domain[i] != domain[j] and pd.notna(when[i]) and pd.notna(when[j]) and abs(when[i] - when[j]) <= window:
            pairs.append((int(i), int(j)))
    return pairs


def assign_provenance(news: pd.DataFrame, pairs: list[tuple[int, int]] | None = None) -> pd.Series:
    """procedencia_id for each row, same index. `pairs` (positional) can be passed in to
    reuse a precomputed set of near copies; by default TF-IDF titles are used."""
    n = len(news)
    if n == 0:
        return pd.Series([], index=news.index, dtype=object)
    agency = detect_agency(news).to_numpy()
    domain = news["dominio"].fillna(news["medio"]).fillna("desconocido").to_numpy()
    # Rank in time (undated last), so "earliest" never compares a date with a null.
    rank = reference_time(news).rank(method="first", na_option="bottom").to_numpy()
    pairs = near_copy_pairs(news) if pairs is None else pairs

    rows = [i for i, _ in pairs]
    cols = [j for _, j in pairs]
    graph = coo_matrix((np.ones(len(pairs)), (rows, cols)), shape=(n, n))
    _, component = connected_components(graph, directed=False)

    out = np.empty(n, dtype=object)
    for comp in np.unique(component):
        members = np.flatnonzero(component == comp)
        agencies = [a for a in agency[members] if isinstance(a, str)]
        if agencies:
            label = "P-AG-" + _slug(sorted(agencies)[0])
            out[members] = label
            continue
        if len(members) == 1:
            out[members] = "P-" + _slug(domain[members[0]])
            continue
        # The earliest item is the likely original.
        out[members] = "P-" + _slug(domain[members[np.argmin(rank[members])]])
    return pd.Series(out, index=news.index, dtype=object)
