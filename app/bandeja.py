"""Prioritized inbox (C-12, CU-01). Owner: Cristian.

Pure functions, no Streamlit, so they can be tested. The ranking is José's
`src.score.score_clusters` (agreed public function, CLAUDE.md §3): the app never
computes or fills P. Case cards (outputs/fichas.jsonl, or the stub while that file
is empty) only add the case ID, headline and review state to clusters that have one.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FICHAS_PATH = ROOT / "outputs" / "fichas.jsonl"
FICHAS_STUB_PATH = ROOT / "data" / "stub" / "fichas_stub.jsonl"
CONTEXTO_PATH = ROOT / "data" / "processed" / "contexto.parquet"

TOP_N = 5
COMPONENTS = ["R", "I", "U", "N", "E"]
# Written exactly as the contract defines them.
EVIDENCE_STATES = ["insuficiente", "parcial", "suficiente para el borrador"]
SCORE_RANGES = ["alto", "medio", "bajo"]


def read_cards(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_cards(news_from_stub: bool) -> tuple[list[dict], str | None]:
    """Real case cards if José has written any (the repo ships an empty placeholder).

    The synthetic stub cards are used only while the news also come from the stub:
    synthetic data never sits next to the real corpus (rule 12). With real news and
    no real cards, there are no cards and the path is None.
    """
    cards = read_cards(FICHAS_PATH) if FICHAS_PATH.exists() else []
    if cards:
        return cards, FICHAS_PATH.relative_to(ROOT).as_posix()
    if news_from_stub:
        return read_cards(FICHAS_STUB_PATH), FICHAS_STUB_PATH.relative_to(ROOT).as_posix()
    return [], None


def load_contexto() -> pd.DataFrame | None:
    """Official context from B-14; None until Levi delivers it (score_clusters says so)."""
    return pd.read_parquet(CONTEXTO_PATH) if CONTEXTO_PATH.exists() else None


def build_inbox(scored: pd.DataFrame, news: pd.DataFrame, cards: list[dict]) -> pd.DataFrame:
    """score_clusters output plus what the editor needs to read each row.

    Headline: always the most recent real headline in the cluster, with its news ID,
    so evidence is never mixed with generated text. The case card's title is a
    proposal written by the LLM and goes in its own column.
    """
    by_cluster = {c["cluster_id"]: c for c in cards if c.get("cluster_id")}
    order = news["fecha_deteccion"].fillna(news["fecha_publicacion"])
    titled = news.assign(_order=order)[news["titulo"].notna()]  # a null headline is never the one shown
    latest = titled.sort_values("_order", ascending=False).drop_duplicates("cluster_id")
    latest = latest.set_index("cluster_id")
    synthetic = news.groupby("cluster_id")["sintetico"].any() if "sintetico" in news else pd.Series(dtype=bool)

    rows = []
    for row in scored.itertuples(index=False):
        card = by_cluster.get(row.cluster_id, {})
        top = latest.loc[row.cluster_id] if row.cluster_id in latest.index else None
        rows.append({
            "titular": top["titulo"] if top is not None else None,
            "id_titular": top["id_noticia"] if top is not None else None,
            "titulo_propuesto": card.get("titulo"),
            "id_caso": card.get("id_caso"),
            "estado_revision": card.get("estado_revision"),
            "alertas": len(card.get("alertas") or []),
            "sintetico": bool(synthetic.get(row.cluster_id, False)),
        })
    return pd.concat([scored.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def filter_inbox(inbox: pd.DataFrame, temas=None, estados=None, rangos=None,
                 top_n: int | None = TOP_N) -> pd.DataFrame:
    """Keeps score order. Empty or None filters mean "all"; top_n=None shows every row."""
    view = inbox.sort_values("posicion")
    for column, allowed in (("tema", temas), ("estado_evidencia", estados), ("rango", rangos)):
        if allowed:
            view = view[view[column].isin(allowed)]
    return view.head(top_n) if top_n else view


def records_label(n_registros, n_procedencias) -> str:
    """'N registros · M procedencias'; missing counts are shown as such, never 0."""
    def fmt(value, singular, plural):
        if value is None or pd.isna(value):
            return f"— {plural}"
        value = int(value)
        return f"{value} {singular if value == 1 else plural}"
    return f"{fmt(n_registros, 'registro', 'registros')} · {fmt(n_procedencias, 'procedencia', 'procedencias')}"


def urgency_basis_label(base: str | None) -> str:
    """Which date U was measured from (ADR-013): the outlet's or GDELT's detection."""
    return {"publicacion": "publicación", "deteccion": "detección (GDELT)"}.get(base, "—")


def headline_label(value) -> str:
    """Headline for selectors and titles; a cluster with no headline says so, never 'nan'."""
    return "— (sin titular)" if value is None or pd.isna(value) else str(value)


def inbox_pick(selected: str | None, last_pick: str | None) -> str | None:
    """Cluster the Ficha should jump to after a rerun, or None to leave its selector alone.

    A row selected in the inbox table stays selected across reruns. Applying it on every
    rerun would pin the Ficha selector to that row, so it only counts when it changes.
    """
    return selected if selected is not None and selected != last_pick else None
