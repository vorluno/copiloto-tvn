"""Sample of 60 news for the human labels (C-05). Owner: B; labels by C.

The labels are the yardstick for B-07 (topics) and B-08 (events), so the 60 news are
chosen by code with a fixed seed, never by hand. A plain random sample from a year of
news almost never holds two items of the same event, which makes cluster_humano
useless for B-08. So:

- N_SEEDS news are drawn at random from the news in Spanish or English (the languages
  the labeler can judge);
- for N_NEIGHBORS of them, the most similar other news (TF-IDF cosine on title and
  description) published or detected within +-72 h is added: the same window B-08
  uses. Some neighbors are the same event and some are only similar; both are needed
  to measure grouping.

The CSV comes out in a shuffled order with no mark of which news are pairs, so the
labeler is not primed. Which news were neighbors goes to
outputs/reports/muestra_etiquetas.md (read it after labeling). A CSV that already has
labels is never overwritten.

Usage: python -m src.nlp.label_sample [--seed N]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[2]
NEWS_PATH = ROOT / "data" / "processed" / "noticias.parquet"
OUTPUT_PATH = ROOT / "data" / "etiquetas_humanas.csv"
REPORT_PATH = ROOT / "outputs" / "reports" / "muestra_etiquetas.md"

SEED = 20261007
N_TOTAL = 60
N_NEIGHBORS = 20
N_SEEDS = N_TOTAL - N_NEIGHBORS
WINDOW = pd.Timedelta(hours=72)
LANGUAGES = {"es", "en"}
LABEL_COLUMNS = ["id_noticia", "tema_humano", "cluster_humano", "etiquetador", "nota"]
READING_COLUMNS = ["titulo", "descripcion", "medio", "origen", "fecha_utc"]
OUTPUT_COLUMNS = LABEL_COLUMNS + READING_COLUMNS


def _reference_time(news: pd.DataFrame) -> pd.Series:
    """Outlet date when there is one, otherwise GDELT's detection date (only to pair news)."""
    return news["fecha_publicacion"].fillna(news["fecha_deteccion"])


def build_sample(news: pd.DataFrame, seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(CSV rows in shuffled order, pairs: seed_id, neighbor_id, similarity)."""
    pool = news[news["idioma"].isin(LANGUAGES)].reset_index(drop=True)
    when = _reference_time(pool)
    text = (pool["titulo"].fillna("") + " " + pool["descripcion"].fillna("")).str.strip()
    vectors = TfidfVectorizer(strip_accents="unicode", lowercase=True).fit_transform(text)
    rng = np.random.default_rng(seed)

    chosen, taken, pairs = [], set(), []
    for idx in rng.permutation(len(pool)):
        if len(chosen) >= N_TOTAL:
            break
        if idx in taken:
            continue
        chosen.append(idx)
        taken.add(idx)
        if len(pairs) >= N_NEIGHBORS or len(chosen) >= N_TOTAL or pd.isna(when[idx]):
            continue
        close = np.flatnonzero(((when - when[idx]).abs() <= WINDOW).to_numpy())
        close = np.array([c for c in close if c != idx and c not in taken], dtype=int)
        if close.size == 0:
            continue
        similarity = (vectors[close] @ vectors[idx].T).toarray().ravel()
        best = int(np.argmax(similarity))
        if similarity[best] <= 0:
            continue
        neighbor = int(close[best])
        chosen.append(neighbor)
        taken.add(neighbor)
        pairs.append((pool.at[idx, "id_noticia"], pool.at[neighbor, "id_noticia"], round(float(similarity[best]), 3)))

    picked = pool.loc[rng.permutation(chosen)].reset_index(drop=True)
    sample = pd.DataFrame({
        "id_noticia": picked["id_noticia"],
        "tema_humano": "", "cluster_humano": "", "etiquetador": "", "nota": "",
        "titulo": picked["titulo"],
        "descripcion": picked["descripcion"].fillna(""),
        "medio": picked["medio"],
        "origen": picked["origen"],
        "fecha_utc": _reference_time(picked).dt.strftime("%Y-%m-%dT%H:%M:%SZ").fillna(""),
    }, columns=OUTPUT_COLUMNS)
    return sample, pd.DataFrame(pairs, columns=["seed_id", "neighbor_id", "similarity"])


def write_sample(sample: pd.DataFrame, path: Path = OUTPUT_PATH) -> None:
    """UTF-8 CSV; refuses to overwrite a file that already holds labels."""
    if path.exists():
        existing = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
        labels = [c for c in LABEL_COLUMNS[1:] if c in existing.columns]
        if not existing.empty and (existing[labels] != "").any().any():
            raise FileExistsError(f"{path} already has labels; not overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(path, index=False, encoding="utf-8")


def build_report(news: pd.DataFrame, sample: pd.DataFrame, pairs: pd.DataFrame, seed: int) -> str:
    pool = news["idioma"].isin(LANGUAGES).sum()
    lines = [
        "# Muestra para etiquetas humanas (C-05)",
        "",
        "**Leer después de etiquetar:** dice qué noticias se eligieron como pares.",
        "",
        f"- Semilla: {seed} · corpus: {len(news)} noticias · elegibles (es/en): {pool}",
        f"- Muestra: {len(sample)} = {len(sample) - len(pairs)} al azar + {len(pairs)} vecinas (TF-IDF, ±72 h)",
        f"- Por origen: {sample['origen'].value_counts().to_dict()}",
        "",
        "| noticia base | vecina | similitud |",
        "| --- | --- | --- |",
        *[f"| {p.seed_id} | {p.neighbor_id} | {p.similarity} |" for p in pairs.itertuples()],
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else SEED
    news = pd.read_parquet(NEWS_PATH)
    sample, pairs = build_sample(news, seed)
    write_sample(sample)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(build_report(news, sample, pairs, seed), encoding="utf-8")
    print(f"Wrote {len(sample)} news to {OUTPUT_PATH.relative_to(ROOT)} ({len(pairs)} neighbor pairs, seed {seed})")


if __name__ == "__main__":
    main()
