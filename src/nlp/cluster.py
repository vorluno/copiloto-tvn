"""Event clustering (B-08, T02). Owner: B.

Agglomerative clustering with complete linkage on cosine distance between embeddings,
only among news within 72 h of each other: a pair farther apart in time gets the
maximum distance, so with complete linkage no cluster ever holds two items more than
72 h apart. Every item in a cluster is within DISTANCE_THRESHOLD of every other one.

Complete linkage only joins items that are all within the threshold, so each cluster
lies inside one connected component of the "close enough" graph; clustering runs per
component, which keeps memory small on a corpus of thousands of items.

clusters.parquet counts independent provenances, not records (ADR-007): three outlets
replicating one agency are 3 records and 1 provenance.

cluster_id is stable across runs: a single item keeps its provisional id ("K-" + its id
hash), a group gets "K-" + the first 10 hex chars of the SHA-1 of its sorted ids.
"""

import hashlib

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.cluster import AgglomerativeClustering

from src.nlp.provenance import reference_time

WINDOW = pd.Timedelta(hours=72)
DISTANCE_THRESHOLD = 0.30  # cosine distance; 0.35 merged same-topic stories on 7 oct. B-12 measures it on cluster_humano
FAR = 2.0  # maximum cosine distance, used for pairs outside the window or without a date
CLUSTER_COLUMNS = ["cluster_id", "ids_noticia", "n_registros", "n_procedencias_independientes", "tema",
                   "fecha_primera", "fecha_ultima", "n_medios", "medios", "recirculada"]


def _close_pairs(vectors: np.ndarray, when: pd.Series, threshold: float, window: pd.Timedelta):
    """Positional (i, j) pairs with i < j, cosine distance <= threshold and both dated within window."""
    sims = vectors @ vectors.T
    rows, cols = np.nonzero(np.triu(sims >= 1 - threshold, k=1))
    ts = when.reset_index(drop=True)
    ok = [(i, j) for i, j in zip(rows, cols)
          if pd.notna(ts[i]) and pd.notna(ts[j]) and abs(ts[i] - ts[j]) <= window]
    return ok


def cluster_labels(vectors: np.ndarray, when: pd.Series, threshold: float = DISTANCE_THRESHOLD,
                   window: pd.Timedelta = WINDOW) -> np.ndarray:
    """Integer label per row; rows with the same label are one event."""
    n = len(vectors)
    if n == 0:
        return np.zeros(0, dtype=int)
    pairs = _close_pairs(vectors, when, threshold, window)
    graph = coo_matrix((np.ones(len(pairs)), ([i for i, _ in pairs], [j for _, j in pairs])), shape=(n, n))
    _, component = connected_components(graph, directed=False)

    ts = when.reset_index(drop=True)
    labels = np.empty(n, dtype=int)
    next_label = 0
    for comp in np.unique(component):
        members = np.flatnonzero(component == comp)
        if len(members) == 1:
            labels[members] = next_label
            next_label += 1
            continue
        sub = vectors[members]
        dist = np.clip(1 - sub @ sub.T, 0, FAR)
        times = ts.iloc[members].reset_index(drop=True)
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                if pd.isna(times[a]) or pd.isna(times[b]) or abs(times[a] - times[b]) > window:
                    dist[a, b] = dist[b, a] = FAR
        np.fill_diagonal(dist, 0)
        model = AgglomerativeClustering(n_clusters=None, metric="precomputed", linkage="complete",
                                        distance_threshold=threshold + 1e-9)
        sub_labels = model.fit_predict(dist)
        labels[members] = sub_labels + next_label
        next_label += sub_labels.max() + 1
    return labels


def cluster_ids(news_ids: pd.Series, labels: np.ndarray) -> pd.Series:
    """Stable id per row from its group's members."""
    out = pd.Series(index=news_ids.index, dtype=object)
    for label in np.unique(labels):
        idx = news_ids.index[labels == label]
        members = sorted(news_ids.loc[idx])
        if len(members) == 1:
            out[idx] = "K-" + members[0][2:]
        else:
            out[idx] = "K-" + hashlib.sha1("|".join(members).encode("utf-8")).hexdigest()[:10]
    return out


def majority_topic(topics: pd.Series) -> str:
    """Most frequent topic; ties alphabetically (same rule as src/score.py)."""
    counts = topics.dropna().value_counts()
    if counts.empty:
        return "otro"
    return sorted(counts[counts == counts.max()].index)[0]


def build_clusters(news: pd.DataFrame) -> pd.DataFrame:
    """One row per cluster_id from news that already has cluster_id, procedencia_id and tema."""
    when = reference_time(news)
    rows = []
    for cluster_id, group in news.assign(_when=when).groupby("cluster_id", sort=True):
        provenance = group["procedencia_id"].fillna("P-" + group["dominio"].fillna("desconocido"))
        outlets = sorted(group["medio"].dropna().unique())
        rows.append({
            "cluster_id": cluster_id,
            "ids_noticia": sorted(group["id_noticia"]),
            "n_registros": len(group),
            "n_procedencias_independientes": provenance.nunique(),
            "tema": majority_topic(group["tema"]),
            "fecha_primera": group["_when"].min(),
            "fecha_ultima": group["_when"].max(),
            "n_medios": len(outlets),
            "medios": outlets,
            # B-11: any recirculated item marks the event; it keeps its original dates.
            "recirculada": bool(group["recirculada"].any()) if "recirculada" in group else False,
        })
    out = pd.DataFrame(rows, columns=CLUSTER_COLUMNS)
    for col in ("fecha_primera", "fecha_ultima"):
        out[col] = pd.to_datetime(out[col], utc=True)
    return out
