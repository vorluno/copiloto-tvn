"""Spanish search over the evidence (J-06). Owner: José.

`SearchIndex.build(news, official)` indexes one passage per citable field:
- news: `titulo` and `descripcion` (the exact text the model can quote);
- World Bank cells: a Spanish descriptor ("inflación · Panamá · 2024 · % anual") used only
  to find the cell; the hit points to its `valor` field, which is what gets cited;
- USGS events: "sismo magnitud … place … fecha", pointing to `place`.

`search(query)` returns the k closest passages with their evidence ID, field and score.
A hit needs both a minimum similarity and a minimum coverage: at least half of the
query's content words (stemmed) must appear in the passage. Lexical similarity alone
cannot tell "precio del bitcoin" from "precios al consumidor"; coverage can. With no
hit left the result is "sin evidencia", so the caller abstains (T06).

Backend: TF-IDF over crude Spanish stems (first 5 letters: "inflación" and
"inflacionaria" -> "infla"), numbers left out so rows that differ only by year tie
exactly and the most recent wins ("inflación de Panamá" -> 2024 first). A year in the
query boosts passages with that year ("PIB de Panamá en 2023" -> 2023). Words are split on
any non-letter ("Minsa–CSS" -> minsa, css; GDELT's "S & P" and "S&P" -> sp), and how a question
is phrased ("qué decidió", "cuánto", "dijo") is not content. Fully offline;
the B-07 embeddings can replace the ranking through `vectorizer`, the gates stay.
Known limit: lexical matching, so a stray shared word can still pass the gates
("resultado del Super Bowl" finds a local football result); the guard and the model
then decline to answer from it.

CLI: python -m src.search "¿qué pasa con el Canal?"
"""

import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.generate.schema import Evidence, evidence_from_news

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_K = 10
THRESHOLD = 0.10  # minimum cosine similarity
YEAR_BOOST = 0.15  # added when the passage has a year the query asks for
MIN_COVERAGE = 0.5  # share of the query's content stems found in the passage
# Calibrated on the 6 Oct snapshot (55 TVN items + World Bank + USGS); see tests/test_search.py.
SIN_EVIDENCIA = "sin evidencia"

INDICATOR_NAMES = {
    "NY.GDP.MKTP.KD.ZG": "crecimiento del PIB economía producto interno bruto",
    "FP.CPI.TOTL.ZG": "inflación precios al consumidor costo de vida",
    "SL.UEM.TOTL.ZS": "desempleo tasa de desocupación empleo",
    "SP.POP.TOTL": "población habitantes",
    "IT.NET.USER.ZS": "uso de internet conectividad usuarios",
    "NE.EXP.GNFS.ZS": "exportaciones de bienes y servicios comercio exterior",
}
COUNTRY_NAMES = {"PAN": "Panamá", "CRI": "Costa Rica", "COL": "Colombia", "DOM": "República Dominicana",
                 "MEX": "México", "GTM": "Guatemala"}
STOPWORDS = {"el", "la", "los", "las", "de", "del", "en", "y", "a", "que", "por", "con", "para", "un", "una",
             "se", "su", "al", "lo", "es", "qué", "cuál", "cómo", "cuántos", "cuántas", "hay", "sobre"}
# How an editor phrases a question, not what it is about: kept out of coverage and ranking.
QUESTION_WORDS = {"cuánto", "cuánta", "cuáles", "dónde", "cuándo", "quién", "quiénes", "pasa", "pasó", "sabe",
                  "dijo", "dice", "dicen", "reporta", "reportan", "anunció", "decidió", "hubo", "tendrá",
                  "tuvo", "fue", "son", "está", "están", "ya", "actual", "entre", "tras"}


def _plain(word: str) -> str:
    decomposed = unicodedata.normalize("NFKD", word.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip("¿?¡!.,;:()\"'|«»“”")


STOP = {_plain(w) for w in STOPWORDS | QUESTION_WORDS}


def words_only(text: str) -> list[str]:
    """TF-IDF features: stems without numbers, so rows that differ only by year score the same."""
    return [s for s in stems(text) if not s[0].isdigit()]


def years(text: str) -> set[str]:
    return {s for s in stems(text) if len(s) == 4 and s.isdigit() and s.startswith(("19", "20"))}


AMPERSAND = re.compile(r"\b(\w)\s*&\s*(\w)\b")  # "S&P" and GDELT's "S & P" -> "sp"
TOKEN = re.compile(r"[^\W_]+")  # letters and digits; dashes, slashes and "|" split words


def stems(text: str) -> list[str]:
    """Content words of a Spanish text, accent-free and cut to 5 letters; numbers kept whole."""
    out = []
    for raw in TOKEN.findall(AMPERSAND.sub(r"\1\2", text)):
        word = _plain(raw)
        if len(word) < 2 or word in STOP:
            continue
        out.append(word if word[0].isdigit() else word[:5])
    return out


@dataclass
class Passage:
    evidence: Evidence
    field: str  # field to cite
    text: str  # text used for matching
    recency: float  # sort key for ties (epoch seconds or year)


@dataclass
class Hit:
    id_evidencia: str
    campo: str
    texto: str
    score: float
    evidence: Evidence


@dataclass
class SearchResult:
    query: str
    hits: list[Hit] = field(default_factory=list)
    best_score: float = 0.0

    @property
    def sin_evidencia(self) -> bool:
        return not self.hits

    @property
    def evidence(self) -> list[Evidence]:
        """Unique evidence items in hit order, ready for answer_question."""
        seen, out = set(), []
        for hit in self.hits:
            if hit.id_evidencia not in seen:
                seen.add(hit.id_evidencia)
                out.append(hit.evidence)
        return out


def _news_passages(news: pd.DataFrame) -> list[Passage]:
    passages = []
    for _, row in news.iterrows():
        item = evidence_from_news(row)
        when = row["fecha_publicacion"] if pd.notna(row["fecha_publicacion"]) else row.get("fecha_deteccion")
        recency = pd.Timestamp(when).timestamp() if when is not None and pd.notna(when) else 0.0
        for name in ("titulo", "descripcion"):
            if name in item.fields:
                passages.append(Passage(item, name, item.fields[name], recency))
    return passages


def _official_passages(official: dict[str, Evidence]) -> list[Passage]:
    passages = []
    for item in official.values():
        if item.kind == "indicador":
            f = item.fields
            text = " ".join([INDICATOR_NAMES.get(f["indicador_id"], f["indicador_id"]),
                             COUNTRY_NAMES.get(f["pais_iso3"], f["pais_iso3"]), f["anio"], f["unidad"], "Banco Mundial"])
            passages.append(Passage(item, "valor", text, float(item.year or 0)))
        elif item.kind == "sismo":
            f = item.fields
            text = f"sismo terremoto temblor magnitud {f.get('magnitude', '')} {f.get('place', '')} {f.get('time', '')[:10]}"
            passages.append(Passage(item, "place", text, pd.Timestamp(f["time"]).timestamp() if "time" in f else 0.0))
    return passages


class SearchIndex:
    def __init__(self, passages: list[Passage], vectorizer=None):
        self.passages = passages
        self.vectorizer = vectorizer or TfidfVectorizer(analyzer=words_only, sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform([p.text for p in passages]) if passages else None
        self.passage_stems = [set(stems(p.text)) for p in passages]
        self.passage_years = [years(p.text) for p in passages]

    @classmethod
    def build(cls, news: pd.DataFrame | None = None, official: dict[str, Evidence] | None = None, vectorizer=None):
        passages = (_news_passages(news) if news is not None else []) + _official_passages(official or {})
        return cls(passages, vectorizer)

    def search(self, query: str, k: int = DEFAULT_K, threshold: float = THRESHOLD,
               min_coverage: float = MIN_COVERAGE) -> SearchResult:
        result = SearchResult(query=query)
        query_stems = set(stems(query))
        if self.matrix is None or not query_stems:
            return result
        scores = cosine_similarity(self.vectorizer.transform([query]), self.matrix)[0]
        if asked := years(query):
            scores = scores + [YEAR_BOOST if asked & self.passage_years[i] else 0.0 for i in range(len(scores))]
        order = sorted(range(len(scores)), key=lambda i: (-round(float(scores[i]), 6), -self.passages[i].recency, i))
        result.best_score = float(scores[order[0]])
        for i in order:
            if len(result.hits) == k or scores[i] < threshold:
                break
            if len(query_stems & self.passage_stems[i]) / len(query_stems) < min_coverage:
                continue
            p = self.passages[i]
            result.hits.append(Hit(p.evidence.id, p.field, p.evidence.fields.get(p.field, p.text),
                                   round(float(scores[i]), 4), p.evidence))
        return result


def load_index() -> SearchIndex:
    """Index over the contract files present (news falls back to the stub)."""
    from src.fichas import load_inputs

    inputs = load_inputs()
    return SearchIndex.build(inputs["news"], inputs["official"])


def main() -> None:
    query = " ".join(sys.argv[1:]) or "¿Qué se reporta sobre el Canal de Panamá?"
    result = load_index().search(query)
    if result.sin_evidencia:
        print(f"{SIN_EVIDENCIA} (mejor similitud {result.best_score:.3f}; umbral {THRESHOLD}, cobertura {MIN_COVERAGE})")
        return
    for hit in result.hits:
        print(json.dumps({"id": hit.id_evidencia, "campo": hit.campo, "score": hit.score,
                          "texto": hit.texto[:110]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
