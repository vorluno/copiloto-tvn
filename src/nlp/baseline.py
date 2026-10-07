"""Non-embedding baseline (B-09, ADR-004). Owner: B.

Same output columns as the AI (id_noticia, tema, tema_confianza, procedencia_id,
cluster_id), so B-12 compares both with the same code:

- tema: the topic whose keywords appear most often in title + description (accents and
  case ignored; keywords of 4 letters or less are whole words, longer ones also match as
  prefixes). No keyword -> "otro". Ties go to the
  first topic in TOPICS order. tema_confianza = share of the matched keywords that
  belong to the chosen topic.
- duplicates: TF-IDF cosine on titles >= DUPLICATE (0.9) within 72 h is one cluster
  (connected pairs); everything else is its own cluster. No embeddings anywhere.
- procedencia_id: the B-06 rules, which already use TF-IDF only.
"""

import re
import unicodedata

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer

from src.nlp.classify import OTHER, TOPICS
from src.nlp.cluster import WINDOW, cluster_ids
from src.nlp.provenance import assign_provenance, reference_time

DUPLICATE = 0.9
OUTPUT_COLUMNS = ["id_noticia", "tema", "tema_confianza", "procedencia_id", "cluster_id"]

# Stems: "export" matches exportación, exportaciones... Written without accents.
KEYWORDS = {
    "economía": ["economi", "inflacion", "precio", "empleo", "desempleo", "salario", "pib", "credito", "banco",
                 "bancari", "inversion", "impuesto", "deuda", "presupuesto", "export", "import", "comercio",
                 "canasta", "costo de vida", "mercado", "fiscal", "dgi", "mef", "economy", "inflation", "prices"],
    "logística/Canal": ["canal", "esclusa", "transito", "buque", "naviera", "puerto", "portuari", "contenedor",
                        "carga", "logistic", "calado", "gatun", "acp", "maritim", "shipping", "vessel", "port"],
    "turismo": ["turis", "turista", "hotel", "hoteler", "crucero", "visitante", "aerolinea", "vuelo", "tocumen",
                "atp", "playa", "tourism", "tourist"],
    "servicios públicos": ["idaan", "agua potable", "electricidad", "luz", "apagon", "basura", "recoleccion",
                           "metro", "mibus", "transporte publico", "hospital", "css", "seguro social",
                           "escuela", "meduca", "minsa", "carretera", "acueducto", "potabilizadora"],
    "eventos naturales": ["sismo", "terremoto", "temblor", "lluvia", "inundacion", "deslizamiento", "sequia",
                          "el nino", "la nina", "tormenta", "huracan", "sinaproc", "vaguada", "earthquake",
                          "flood", "drought", "storm"],
    "regulación": ["ley", "decreto", "asamblea", "reforma", "resolucion", "norma", "reglament", "superintendencia",
                   "regulador", "asep", "corte suprema", "fallo", "gaceta oficial", "proyecto de ley",
                   "regulation", "law"],
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _pattern(keyword: str) -> re.Pattern:
    """Short keywords (ley, luz, acp...) must be whole words, or "ley" would match "leyenda"."""
    end = r"\b" if len(keyword) <= 4 else ""
    return re.compile(r"\b" + re.escape(keyword) + end)


PATTERNS = {topic: [_pattern(k) for k in words] for topic, words in KEYWORDS.items()}


def keyword_topic(text: str) -> tuple[str, float]:
    folded = _fold(text)
    hits = {topic: sum(len(p.findall(folded)) for p in PATTERNS[topic]) for topic in TOPICS}
    total = sum(hits.values())
    if total == 0:
        return OTHER, 0.0
    best = max(TOPICS, key=lambda t: hits[t])  # max keeps the first topic on ties
    return best, round(hits[best] / total, 4)


def duplicate_labels(news: pd.DataFrame, threshold: float = DUPLICATE, window: pd.Timedelta = WINDOW) -> np.ndarray:
    n = len(news)
    if n < 2:
        return np.arange(n)
    vectors = TfidfVectorizer(strip_accents="unicode", lowercase=True).fit_transform(news["titulo"].fillna(""))
    sims = (vectors @ vectors.T).tocoo()
    keep = (sims.row < sims.col) & (sims.data >= threshold - 1e-9)
    when = reference_time(news).reset_index(drop=True)
    pairs = [(i, j) for i, j in zip(sims.row[keep], sims.col[keep])
             if pd.notna(when[i]) and pd.notna(when[j]) and abs(when[i] - when[j]) <= window]
    graph = coo_matrix((np.ones(len(pairs)), ([i for i, _ in pairs], [j for _, j in pairs])), shape=(n, n))
    return connected_components(graph, directed=False)[1]


def run_baseline(news: pd.DataFrame) -> pd.DataFrame:
    news = news.reset_index(drop=True)
    text = (news["titulo"].fillna("") + " " + news["descripcion"].fillna("")).tolist()
    topics = [keyword_topic(t) for t in text]
    return pd.DataFrame({
        "id_noticia": news["id_noticia"],
        "tema": pd.Series([t for t, _ in topics], dtype=object),
        "tema_confianza": pd.Series([c for _, c in topics], dtype="float64"),
        "procedencia_id": assign_provenance(news).to_numpy(),
        "cluster_id": cluster_ids(news["id_noticia"], duplicate_labels(news)).to_numpy(),
    })[OUTPUT_COLUMNS]
