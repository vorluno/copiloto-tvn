"""Multilingual CPU embeddings (B-07, ADR-003). Owner: B.

Input text: title + description when there is one. The vectors are L2-normalized, so a
dot product is the cosine similarity. data/processed/embeddings.npy holds one row per
news item in the order of embeddings_ids.json; embeddings_modelo.json records the model
name and revision, so a different model never reuses stale vectors.

The model is downloaded once to the Hugging Face cache and then loaded from it
(HF_HUB_OFFLINE=1 works), so the demo needs no internet.

Usage: python -m src.nlp.embed
"""

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
NEWS_PATH = PROCESSED / "noticias.parquet"
EMBEDDINGS_PATH = PROCESSED / "embeddings.npy"
IDS_PATH = PROCESSED / "embeddings_ids.json"
MODEL_INFO_PATH = PROCESSED / "embeddings_modelo.json"

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# e5 models expect a role prefix; paraphrase models take the raw text.
PREFIXES = {"intfloat/multilingual-e5-small": "query: "}


@lru_cache(maxsize=2)
def load_model(name: str = MODEL_NAME):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name, device="cpu")


def model_info(name: str = MODEL_NAME) -> dict:
    """Model name and the Hugging Face revision found in the local cache."""
    model = load_model(name)
    revision = None
    try:
        from huggingface_hub import scan_cache_dir

        for repo in scan_cache_dir().repos:
            if repo.repo_id == name:
                revision = max(repo.revisions, key=lambda r: r.last_modified).commit_hash
    except Exception:  # informative only; never block the pipeline on the cache layout
        pass
    return {"modelo": name, "revision": revision, "dimension": model.get_embedding_dimension(),
            "texto": "titulo + descripcion (si existe)", "normalizado": True}


def news_text(news: pd.DataFrame) -> pd.Series:
    """Title plus description when there is one."""
    return (news["titulo"].fillna("") + ". " + news["descripcion"].fillna("")).str.strip(" .")


def encode(texts: list[str], name: str = MODEL_NAME, batch_size: int = 64) -> np.ndarray:
    prefix = PREFIXES.get(name, "")
    vectors = load_model(name).encode([prefix + t for t in texts], batch_size=batch_size,
                                      normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vectors, dtype=np.float32)


def embed_news(news: pd.DataFrame, name: str = MODEL_NAME, cache: bool = True) -> np.ndarray:
    """Vectors for `news` in its row order. With `cache`, rows already stored for the same
    model are reused and only new ids are encoded."""
    ids = news["id_noticia"].tolist()
    known: dict[str, np.ndarray] = {}
    if cache and EMBEDDINGS_PATH.exists() and IDS_PATH.exists() and MODEL_INFO_PATH.exists():
        if json.loads(MODEL_INFO_PATH.read_text(encoding="utf-8")).get("modelo") == name:
            stored = np.load(EMBEDDINGS_PATH)
            known = dict(zip(json.loads(IDS_PATH.read_text(encoding="utf-8")), stored))
    missing = [i for i, nid in enumerate(ids) if nid not in known]
    if missing:
        fresh = encode(news_text(news.iloc[missing]).tolist(), name)
        known.update({ids[i]: v for i, v in zip(missing, fresh)})
    return np.stack([known[nid] for nid in ids]) if ids else np.zeros((0, 0), dtype=np.float32)


def save(news: pd.DataFrame, vectors: np.ndarray, name: str = MODEL_NAME) -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    np.save(EMBEDDINGS_PATH, vectors)
    # newline="\n": the same bytes (and SHA-256 in the manifest) on every OS.
    IDS_PATH.write_text(json.dumps(news["id_noticia"].tolist()), encoding="utf-8", newline="\n")
    MODEL_INFO_PATH.write_text(json.dumps(model_info(name), ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def main() -> None:
    news = pd.read_parquet(NEWS_PATH)
    vectors = embed_news(news)
    save(news, vectors)
    print(f"Wrote {vectors.shape} embeddings to {EMBEDDINGS_PATH.relative_to(ROOT)} ({MODEL_NAME})")


if __name__ == "__main__":
    main()
