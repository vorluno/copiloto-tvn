"""NLP pipeline (B-06, B-07, B-08, B-09): `make nlp`. Owner: B.

Reads data/processed/noticias.parquet (from `make news`), then:

1. embeddings (B-07)          -> data/processed/embeddings.npy (+ ids, model)
2. tema, tema_confianza (B-07)
3. procedencia_id (B-06)
4. cluster_id (B-08)          -> data/processed/clusters.parquet
5. baseline (B-09)            -> data/processed/baseline.parquet, same columns as the AI
6. export (B-13)              -> data/processed/noticias.csv + fuentes.json
7. official context (B-14)    -> data/processed/contexto.parquet

and rewrites noticias.parquet with the four contract columns filled. No network once the
embedding model is in the local cache.

Usage: python -m src.nlp.run
"""

import json
from pathlib import Path

import pandas as pd

from src import context, export
from src.ingest.common import finalize
from src.nlp import baseline, classify, cluster, embed, provenance

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
NEWS_PATH = PROCESSED / "noticias.parquet"
CLUSTERS_PATH = PROCESSED / "clusters.parquet"
BASELINE_PATH = PROCESSED / "baseline.parquet"


def enrich(news: pd.DataFrame, vectors) -> pd.DataFrame:
    """news with tema, tema_confianza, procedencia_id and cluster_id from the AI pipeline."""
    out = news.reset_index(drop=True).copy()
    topics = classify.classify(vectors)
    out["tema"] = topics["tema"].to_numpy()
    out["tema_confianza"] = topics["tema_confianza"].to_numpy()
    out["procedencia_id"] = provenance.assign_provenance(out).to_numpy()
    labels = cluster.cluster_labels(vectors, provenance.reference_time(out))
    out["cluster_id"] = cluster.cluster_ids(out["id_noticia"], labels).to_numpy()
    return finalize(out)


def main() -> None:
    news = pd.read_parquet(NEWS_PATH)
    vectors = embed.embed_news(news)
    embed.save(news, vectors)
    enriched = enrich(news, vectors)
    clusters = cluster.build_clusters(enriched)
    enriched.to_parquet(NEWS_PATH, index=False)
    clusters.to_parquet(CLUSTERS_PATH, index=False)
    base = baseline.run_baseline(news)
    base.to_parquet(BASELINE_PATH, index=False)
    export.write_csv(enriched)
    export.write_sources(enriched)
    indicators = pd.read_csv(context.INDICATORS_PATH) if context.INDICATORS_PATH.exists() else None
    events = json.loads(context.EVENTS_PATH.read_text(encoding="utf-8")) if context.EVENTS_PATH.exists() else None
    links = context.build_context(enriched, indicators, events)
    links.to_parquet(context.OUTPUT_PATH, index=False)

    grouped = clusters[clusters["n_registros"] > 1]
    print(f"{len(enriched)} news -> {len(clusters)} clusters ({len(grouped)} with 2+ records, "
          f"largest {clusters['n_registros'].max()}); topics {enriched['tema'].value_counts().to_dict()}; "
          f"{enriched['procedencia_id'].nunique()} provenances")
    print(f"Baseline topics {base['tema'].value_counts().to_dict()}; "
          f"{base['cluster_id'].nunique()} baseline clusters; {len(links)} official context links")


if __name__ == "__main__":
    main()
