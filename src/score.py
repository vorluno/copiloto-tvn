"""Priority score P = 30R + 25I + 20U + 15N + 10E per cluster (J-05, ADR-006). Owner: José.

Deterministic, no LLM. Weights, ranges, thresholds and topic reach come from
rules/scoring_v1.yaml. The formulas in that file are documentation for the jury; this
module implements them and `load_rules` refuses to run if their text changes, so the
YAML and the code cannot drift apart silently (a change means a new rules version).

Decisions not spelled out in the YAML (ADR-013):
- Panama relation (R): the cluster has a TVN item (RSS or web) or its text names Panama
  or a Panamanian place (PANAMA_PATTERNS).
- Urgency reference (U): most recent fecha_publicacion in the cluster. GDELT gives no
  outlet date, so when no item has one, the most recent fecha_deteccion is used and
  the row says so (`base_urgencia="deteccion"`). Dates are never copied between fields.
  Recirculated items keep their original date, so an old story scores as old (T03).
- Provenance (E): unique procedencia_id; a missing one falls back to the item's domain,
  so unknown items from the same outlet are not counted as independent (T02).
- Official support: from data/processed/contexto.parquet (B-14). Without it, both
  official flags are False and `contexto_disponible=False` says so.
- Novelty (N): TF-IDF cosine against clusters first seen in the previous 7 days,
  one text per cluster, so duplicates inside a cluster never add up. Swap for the
  B-07 embeddings when they exist.
- Reference time for urgency (ADR-027): by default the latest outlet or detection date in
  the corpus, not the wall clock. The news period is fixed (02/10/2025-30/09/2026), so
  the ranking is the same on every run and does not decay while the demo waits.
"""

import re
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "scoring_v1.yaml"

EXPECTED_FORMULAS = {
    ("I_impacto", "formula"): "0.6 * alcance_tema + 0.4 * hay_indicador_oficial_pertinente",
    ("N_novedad", "formula"): "1 - max_similitud_coseno",
    ("E_evidencia", "formula"): "0.6 * min(1, procedencias / 3) + 0.4 * hay_fuente_oficial",
}
TOPICS = {"economía", "logística/Canal", "turismo", "servicios públicos", "eventos naturales", "regulación"}
# Whole-word patterns over accent-free lowercase text.
PANAMA_PATTERNS = [
    r"panam(a|en[oa]s?)", r"gatun", r"acp", r"colon", r"chiriqui", r"darien", r"bocas del toro",
    r"cocle", r"herrera", r"los santos", r"veraguas", r"san miguelito", r"arraijan",
    r"la chorrera", r"guna yala", r"ngabe",
]
NOVELTY_WINDOW = pd.Timedelta(days=7)
TVN_ORIGINS = {"tvn_rss", "tvn_web"}  # the sponsor's own outlet: always Panama-related (ADR-026)
EVIDENCE_STATES = ("insuficiente", "parcial", "suficiente para el borrador")


def _fold(text: str) -> str:
    """Lowercase without accents, for keyword matching."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def topic_key(topic: str) -> str:
    """'logística/Canal' -> 'logistica_canal', matching the YAML keys."""
    return re.sub(r"[^a-z0-9]+", "_", _fold(topic)).strip("_")


def _interval(text: str) -> tuple[float, float, bool]:
    """'[0, 40)' -> (0, 40, upper_inclusive=False)."""
    m = re.fullmatch(r"\[\s*([\d.]+)\s*,\s*([\d.]+)\s*([)\]])", text.strip())
    if not m:
        raise ValueError(f"invalid range: {text!r}")
    return float(m.group(1)), float(m.group(2)), m.group(3) == "]"


def load_rules(path: Path = RULES_PATH) -> dict:
    rules = yaml.safe_load(path.read_text(encoding="utf-8"))
    for (section, key), expected in EXPECTED_FORMULAS.items():
        found = rules[section][key]
        if " ".join(str(found).split()) != expected:
            raise ValueError(f"{path.name}: {section}.{key} changed ({found!r}); update score.py and the version")
    rules["_ranges"] = {name: _interval(r) for name, r in rules["rangos"].items()}
    return rules


def priority_band(p: float, rules: dict) -> str:
    for name, (low, high, upper_inclusive) in rules["_ranges"].items():
        if low <= p < high or (upper_inclusive and p == high):
            return name
    raise ValueError(f"P={p} outside every range")


def evidence_state(provenances: int, official: bool) -> str:
    """Independent of P (CLAUDE.md §2.10)."""
    if provenances >= 2 and official:
        return "suficiente para el borrador"
    if provenances >= 2 or official:
        return "parcial"
    return "insuficiente"


def _relates_to_panama(group: pd.DataFrame) -> bool:
    # Plain lists, not per-row pandas: this runs once per cluster (~2,000 on the real corpus).
    if any(origin in TVN_ORIGINS for origin in group["origen"].tolist()):
        return True
    parts = [value for c in ("titulo", "descripcion") if c in group for value in group[c].tolist() if isinstance(value, str)]
    text = _fold(" ".join(parts))
    return any(re.search(rf"\b(?:{pattern})\b", text) for pattern in PANAMA_PATTERNS)


def _urgency(hours: float, rules: dict) -> float:
    u = rules["U_urgencia"]
    if hours <= 24:
        return u["le_24h"]
    if hours <= 72:
        return u["le_72h"]
    if hours <= 24 * 7:
        return u["le_7d"]
    return u["mayor"]


def _majority_topic(topics: pd.Series) -> str:
    counts = Counter(topic for topic in topics.tolist() if isinstance(topic, str))
    if not counts:
        return "otro"
    best = max(counts.values())
    return min(topic for topic, n in counts.items() if n == best)


def _novelty(clusters: pd.DataFrame) -> pd.Series:
    """1 - max cosine similarity against clusters first seen in the previous 7 days."""
    if len(clusters) < 2:
        return pd.Series(1.0, index=clusters.index)
    matrix = TfidfVectorizer(strip_accents="unicode", lowercase=True).fit_transform(clusters["_text"])
    sims = cosine_similarity(matrix)
    # prior[i, j]: cluster j was first seen in the 7 days before cluster i (a null date is never prior).
    start = pd.to_datetime(clusters["fecha_primera"], utc=True).to_numpy(dtype="datetime64[ns]")
    known = ~np.isnat(start)
    delta = start[:, None] - start[None, :]
    prior = known[:, None] & known[None, :] & (delta > np.timedelta64(0, "ns")) & (delta <= NOVELTY_WINDOW.to_timedelta64())
    best = np.where(prior, sims, 0.0).max(axis=1)
    return pd.Series(1.0 - best, index=clusters.index).clip(0.0, 1.0)


def corpus_reference_time(news: pd.DataFrame) -> pd.Timestamp:
    """Latest outlet or detection date in the corpus; wall clock only for an empty corpus.
    Extraction time is not used: it says when we downloaded, not when the news happened."""
    dates = pd.concat([news[c].dropna() for c in ("fecha_publicacion", "fecha_deteccion") if c in news])
    return dates.max() if not dates.empty else pd.Timestamp.now(tz="UTC")


def rank(scored: pd.DataFrame) -> pd.DataFrame:
    """Order by P desc; ties: higher urgency first, then cluster ID asc (ADR-006)."""
    ranked = scored.sort_values(["P", "U", "cluster_id"], ascending=[False, False, True], kind="mergesort")
    return ranked.assign(posicion=range(1, len(ranked) + 1))


def score_clusters(
    news: pd.DataFrame,
    contexto: pd.DataFrame | None = None,
    now: pd.Timestamp | None = None,
    rules: dict | None = None,
) -> pd.DataFrame:
    """One row per cluster with P, its 5 components and how each was obtained, ranked.

    `now` defaults to the corpus reference time (latest outlet or detection date), so the
    same snapshot always gives the same ranking; pass it explicitly to score "as of" a date.
    """
    rules = rules or load_rules()
    now = corpus_reference_time(news) if now is None else pd.Timestamp(now).tz_convert("UTC")
    weights = rules["pesos"]
    reach = rules["I_impacto"]["alcance_tema"]
    relevance = rules["R_relevancia"]
    official_by_cluster: dict[str, set[str]] = {}
    if contexto is not None:
        for cluster_id, group in contexto.groupby("cluster_id"):
            official_by_cluster[cluster_id] = set(group["tipo"])

    rows = []
    for cluster_id, group in news.groupby("cluster_id", sort=True):
        topic = _majority_topic(group["tema"])
        on_topic = topic in TOPICS
        panama = _relates_to_panama(group)
        r = relevance["panama_y_tema"] if on_topic and panama else relevance["tema_sin_panama"] if on_topic else relevance["otro"]

        kinds = official_by_cluster.get(cluster_id, set())
        has_indicator = "indicador" in kinds
        has_official = bool(kinds)
        i = 0.6 * reach.get(topic_key(topic), 0.0) + 0.4 * float(has_indicator)

        published = group["fecha_publicacion"].dropna()
        detected = group["fecha_deteccion"].dropna()
        if not published.empty:
            reference, basis = published.max(), "publicacion"
        elif not detected.empty:
            reference, basis = detected.max(), "deteccion"
        else:
            reference, basis = None, "sin_fecha"
        hours = max(0.0, (now - reference).total_seconds() / 3600) if reference is not None else None
        u = _urgency(hours, rules) if hours is not None else rules["U_urgencia"]["mayor"]

        provenance = group["procedencia_id"].fillna(group["dominio"])
        n_provenances = int(provenance.nunique())
        e = 0.6 * min(1.0, n_provenances / 3) + 0.4 * float(has_official)

        first_seen = pd.concat([published, detected]).min() if not (published.empty and detected.empty) else pd.NaT
        rows.append({
            "cluster_id": cluster_id,
            "tema": topic,
            "R": r, "I": round(i, 4), "U": u, "E": round(e, 4),
            "n_registros": len(group),
            "n_procedencias_independientes": n_provenances,
            "relacion_panama": panama,
            "hay_indicador_oficial": has_indicator,
            "hay_fuente_oficial": has_official,
            "contexto_disponible": contexto is not None,
            "fecha_referencia_urgencia": reference,
            "base_urgencia": basis,
            "horas_desde_referencia": None if hours is None else round(hours, 1),
            "recirculada": bool(group.get("recirculada", pd.Series(False)).fillna(False).any()),
            "fecha_primera": first_seen,
            "_text": " ".join(group["titulo"].fillna("")),
        })

    scored = pd.DataFrame(rows)
    if scored.empty:
        return scored
    scored["N"] = _novelty(scored).round(4)
    scored["P"] = sum(weights[k] * scored[k] for k in ("R", "I", "U", "N", "E")).round(1)
    scored["rango"] = scored["P"].map(lambda p: priority_band(p, rules))
    scored["estado_evidencia"] = [
        evidence_state(n, official) for n, official in zip(scored["n_procedencias_independientes"], scored["hay_fuente_oficial"])
    ]
    scored["version_reglas"] = rules["version"]
    scored = rank(scored)
    columns = ["posicion", "cluster_id", "P", "rango", "R", "I", "U", "N", "E", "estado_evidencia", "tema",
               "n_registros", "n_procedencias_independientes", "relacion_panama", "hay_indicador_oficial",
               "hay_fuente_oficial", "contexto_disponible", "fecha_referencia_urgencia", "base_urgencia",
               "horas_desde_referencia", "recirculada", "version_reglas"]
    return scored[columns].reset_index(drop=True)
