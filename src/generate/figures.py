"""Figures in text vs. figures in the evidence (J-10). Owner: José.

Two checks the guard runs in code, whatever the model says:

- `unsupported_figures(text, fields)`: every number in a generated text must exist in
  the evidence it relies on (rounded or truncated to the precision the text uses, with
  "mil" / "millones" scales). An invented figure is never shown (T06).
- `find_conflicts(evidence)`: two news items giving different figures with the same
  unit (e.g. "45 pies" vs "47 pies") are a contradiction to show, not to resolve (T05).
  Only comparable figures count (J-16): same unit, news dates within a week when both are
  known, and the same measured thing (the words around both figures share a content word).
  "2.2 metros" of waves and a "mirador a 300 metros" are not a contradiction, and neither are
  two earthquakes months apart.

Numbers are read in Spanish and English notation: "7,2" and "7.2" are the same value;
"4.515.577" and "4,515,577" are thousands. When a token is ambiguous ("1.350"), every
reading is tried, so the check never rejects a figure that is really in the source.
"""

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations

from src.generate.schema import Evidence

# Generated text: numbers glued to letters (IDs like N-1a2b) are not figures.
NUMBER = re.compile(r"(?<![A-Za-z0-9-])\d+(?:[.,]\d+)*(?![0-9A-Za-z])")
# Sources: every digit run counts, so ISO dates ("2026-10-05T14:10") back "5 de octubre".
SOURCE_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
SCALES = [(re.compile(r"^\s*mil\s+mill(?:ón|on|ones)\b", re.I), 1e9),
          (re.compile(r"^\s*mill(?:ón|on|ones)\b", re.I), 1e6),
          (re.compile(r"^\s*mil\b", re.I), 1e3)]
UNITS = {
    "%": "%", "por ciento": "%", "pies": "pies", "metros": "metros", "m": "metros", "km": "km",
    "kilómetros": "km", "dólares": "dólares", "usd": "dólares", "us$": "dólares", "balboas": "balboas",
    "buques": "buques", "barcos": "buques", "tránsitos": "tránsitos", "grados": "grados",
    "personas": "personas", "habitantes": "personas", "pasajeros": "pasajeros", "turistas": "turistas",
    "toneladas": "toneladas", "megavatios": "MW", "mw": "MW", "litros": "litros", "galones": "galones",
}
UNIT_AFTER = re.compile(r"^\s*(%|por ciento|[a-záéíóúñ$]+)", re.I)
MAGNITUDE = re.compile(r"magnitud\s*$", re.I)


@dataclass(frozen=True)
class Figure:
    raw: str
    values: frozenset[tuple[float, int]]  # (value, decimals) readings
    scale: float
    unit: str | None
    start: int = field(default=-1, compare=False)  # span in the text it came from
    end: int = field(default=-1, compare=False)


def _readings(token: str) -> set[tuple[float, int]]:
    """All plausible (value, decimals) readings of a numeric token."""
    seps = [c for c in token if c in ".,"]
    if not seps:
        return {(float(token), 0)}
    if len(set(seps)) == 2:  # "1.234,5" or "1,234.5": the last separator is the decimal one
        cut = max(token.rfind("."), token.rfind(","))
        integer, frac = re.sub(r"[.,]", "", token[:cut]), token[cut + 1:]
        return {(float(f"{integer}.{frac}"), len(frac))}
    groups = re.split(r"[.,]", token)
    out: set[tuple[float, int]] = set()
    if 1 <= len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:]):  # "1.350", "4,515,577"
        out.add((float("".join(groups)), 0))
    if len(seps) == 1:  # "7,2" / "7.2"
        out.add((float(f"{groups[0]}.{groups[1]}"), len(groups[1])))
    return out


def extract(text: str, pattern: re.Pattern = NUMBER) -> list[Figure]:
    figures = []
    for match in pattern.finditer(text):
        rest = text[match.end():]
        scale = next((factor for pattern, factor in SCALES if pattern.match(rest)), 1.0)
        unit = None
        if MAGNITUDE.search(text[: match.start()]):
            unit = "magnitud"
        elif (u := UNIT_AFTER.match(rest)) and u.group(1).lower() in UNITS:
            unit = UNITS[u.group(1).lower()]
        if (readings := _readings(match.group())):
            figures.append(Figure(match.group(), frozenset(readings), scale, unit, match.start(), match.end()))
    return figures


def _source_values(texts: list[str]) -> list[float]:
    values = []
    for text in texts:
        for figure in extract(text, SOURCE_NUMBER):
            values += [v * figure.scale for v, _ in figure.values]
    return values


def _at_precision(value: float, decimals: int) -> set[float]:
    """The value rounded and truncated to `decimals` places (both are honest renderings)."""
    factor = 10 ** decimals
    return {round(value, decimals), math.trunc(value * factor) / factor}


def supported(figure: Figure, source_values: list[float]) -> bool:
    """True if some reading of the figure equals a source value rounded or truncated
    to the precision the text uses ("7,2" and "7,1" both come from 7.166; "8" does not)."""
    for value, decimals in figure.values:
        for source in source_values:
            if any(abs(candidate - value) < 1e-9 for candidate in _at_precision(source / figure.scale, decimals)):
                return True
    return False


def unsupported_figures(text: str, source_texts: list[str]) -> list[str]:
    """Numbers in `text` that appear nowhere in `source_texts`."""
    values = _source_values(source_texts)
    return [f.raw for f in extract(text) if not supported(f, values)]


@dataclass(frozen=True)
class Conflict:
    id_a: str
    raw_a: str
    id_b: str
    raw_b: str
    unit: str

    def involves(self, a: str, b: str) -> bool:
        return {a, b} == {self.id_a, self.id_b}


# Comparability of two figures (J-16).
DATE_WINDOW_DAYS = 7  # two news items further apart than this describe different moments
CONTEXT_BEFORE, CONTEXT_AFTER = 4, 3  # content words read around a figure to know what it measures
WORD = re.compile(r"[^\W\d_]+")
# Words that quantify or frame a figure without saying what is measured ("más de 120 mil", "hasta").
NOT_SUBJECT = {
    "del", "las", "los", "una", "unos", "unas", "por", "para", "con", "que", "sus", "desde", "hasta", "entre",
    "mas", "menos", "casi", "cerca", "alred", "apena", "solo", "segun", "sobre", "tras", "este", "esta",
    "mil", "millo", "milla", "magni", "magnitud", "the", "and", "for", "with",
    "pies", "metro", "kilom", "dolar", "balbo", "grado", "cient",  # unit words: shared by any two figures
}


def _stem(word: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFKD", word.casefold()) if not unicodedata.combining(c))
    return plain[:5]


def _content_stems(text: str) -> list[str]:
    stems = [_stem(w) for w in WORD.findall(text) if len(w) >= 3]
    return [s for s in stems if s not in NOT_SUBJECT]


def _subject(text: str, figure: Figure) -> set[str]:
    """Content words right before and after a figure: what the number measures."""
    after = text[figure.end:]
    if (unit := UNIT_AFTER.match(after)) and unit.group(1).lower() in UNITS:
        after = after[unit.end():]
    return set(_content_stems(text[:figure.start])[-CONTEXT_BEFORE:] + _content_stems(after)[:CONTEXT_AFTER])


def evidence_date(item: Evidence) -> datetime | None:
    """When a news item is from: fecha_publicacion, else GDELT's fecha_deteccion (meta, never sent to the
    model). Used only to tell whether two items describe the same moment; neither field is rewritten."""
    raw = item.fields.get("fecha_publicacion") or item.meta.get("fecha_deteccion")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def same_period(a: Evidence, b: Evidence) -> bool:
    """False only when both news dates are known and further apart than DATE_WINDOW_DAYS."""
    date_a, date_b = evidence_date(a), evidence_date(b)
    if date_a is None or date_b is None:
        return True
    return abs((date_a - date_b).total_seconds()) <= DATE_WINDOW_DAYS * 86400


def find_conflicts(evidence: list[Evidence]) -> list[Conflict]:
    """Pairs of news items that give different, comparable figures: same unit, same period
    and the same measured thing. When comparability is unclear, no conflict is reported."""
    by_item = []
    for item in evidence:
        if item.kind != "noticia":
            continue
        text = " ".join(item.fields.get(f, "") for f in ("titulo", "descripcion"))
        by_item.append((item, [(f, _subject(text, f)) for f in extract(text) if f.unit]))
    conflicts = []
    for (item_a, figs_a), (item_b, figs_b) in combinations(by_item, 2):
        if not same_period(item_a, item_b):
            continue
        for fa, subject_a in figs_a:
            for fb, subject_b in figs_b:
                if fa.unit != fb.unit or not subject_a & subject_b:
                    continue
                values_a = {round(v * fa.scale, 6) for v, _ in fa.values}
                values_b = {round(v * fb.scale, 6) for v, _ in fb.values}
                if not values_a & values_b:
                    conflicts.append(Conflict(item_a.id, fa.raw, item_b.id, fb.raw, fa.unit))
    return conflicts
