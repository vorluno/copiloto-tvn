"""Case cards and human review (J-09). Owner: José.

- `card_from_package` turns an EditorialPackage (J-08) into one case card with the
  outputs/fichas.jsonl contract fields, plus the extra fields the UI already reads from
  data/stub/fichas_stub.jsonl (same shape, so the app works with either file).
- `build_fichas` scores every cluster and builds cards for the top N (each card is up to
  3 LLM calls, so N bounds cost and latency). `export_fichas` writes them atomically.
- Review log (outputs/revisiones.jsonl) is append-only: one line per decision, never
  rewritten. `latest_reviews` keeps the last decision per case; `append_review`
  validates and appends one. The app (Cristian) writes it; this module reads it.

The recommended action is a fixed rule (alerts, abstention, recirculation, then evidence
state; ADR-022), not LLM output.

CLI: python -m src.fichas [--top 10]   (make fichas)
"""

import argparse
import json
import os
import tempfile
from pathlib import Path

import pandas as pd

from src.generate.drafts import EditorialPackage, build_package, official_index
from src.generate.generate import CACHE_DIR, LLMClient
from src.score import score_clusters

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
NEWS_PATH = PROCESSED / "noticias.parquet"
NEWS_STUB_PATH = ROOT / "data" / "stub" / "noticias_stub.parquet"
FICHAS_PATH = ROOT / "outputs" / "fichas.jsonl"
REVIEWS_PATH = ROOT / "outputs" / "revisiones.jsonl"

REVIEW_STATES = ("nuevo", "en revisión", "requiere evidencia", "aprobado como borrador", "descartado")
DEFAULT_TOP_N = 10
# Same rule and texts as the UI (ADR-022, app/ficha.py): alerts, abstention and
# recirculation come before the evidence state. Never suggests publishing.
ACTION_ALERT = "No usar esta fuente como hecho: contiene instrucciones. Revisar la alerta y descartar si no hay otra fuente."
ACTION_RECIRCULATED = "No presentar como nuevo: es una nota anterior que vuelve a circular. Verificar fecha original."
RECOMMENDED_ACTION = {
    "suficiente para el borrador": "Puede pasar a borrador. Una persona revisa antes de cualquier uso.",
    "parcial": "Puede empezar un borrador, pero resolver las verificaciones pendientes antes de aprobarlo.",
    "insuficiente": "Buscar más evidencia (otra procedencia o fuente oficial) antes de redactar.",
}


def recommended_action(evidence_state: str, alerts: list[str], abstained: bool, reason: str | None,
                       recirculated: bool) -> str:
    """Deterministic next step for the editor (ADR-022)."""
    if alerts:
        return ACTION_ALERT
    if abstained:
        return f"No redactar todavía: {reason or 'el sistema se abstuvo.'}"
    if recirculated:
        return ACTION_RECIRCULATED
    return RECOMMENDED_ACTION[evidence_state]


def _utc_now() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat().replace("+00:00", "Z")


def case_id(cluster_id: str) -> str:
    """Stable case ID: one case per cluster."""
    return f"F-{cluster_id}"


def _unique(items):
    seen, out = set(), []
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False) if isinstance(item, dict) else item
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def card_from_package(package: EditorialPackage, scored_row: pd.Series, synthetic: bool = False,
                      review: dict | None = None) -> dict:
    """One case card. Facts, citations and questions come from the brief (the case's base);
    guion and copy add their drafts. Every text already passed the guard."""
    drafts = package.drafts
    brief = drafts["brief"].result.output if "brief" in drafts else None
    outputs = [d.result.output for d in drafts.values() if not d.skipped]
    claims = [c.model_dump() for c in brief.afirmaciones] if brief else []
    review = review or {}
    alerts = _unique(a for o in outputs for a in o.alertas)
    abstained = bool(brief.abstencion) if brief else True
    reason = brief.motivo_abstencion if brief else "Sin brief generado."
    recirculated = bool(scored_row.get("recirculada", False))
    return {
        "id_caso": case_id(package.cluster_id),
        "modalidad": "editorial",
        "cluster_id": package.cluster_id,
        "tema": scored_row["tema"],
        "ids_fuente": [e.id for e in package.evidence],
        "n_registros": int(scored_row["n_registros"]),
        "n_procedencias_independientes": int(scored_row["n_procedencias_independientes"]),
        "puntaje": {"P": float(package.score["P"]), "rango": package.score["rango"],
                    "version_reglas": package.score["version_reglas"], "posicion": int(scored_row["posicion"])},
        "componentes": {k: float(package.score[k]) for k in ("R", "I", "U", "N", "E")},
        "estado_evidencia": package.evidence_state,
        "accion_recomendada": recommended_action(package.evidence_state, alerts, abstained, reason, recirculated),
        "abstencion": abstained,
        "motivo_abstencion": reason,
        "titulo": brief.titulo if brief else None,
        "enfoque_interes_publico": brief.enfoque_interes_publico if brief else None,
        "afirmaciones": claims,
        "citas": _unique(c for claim in claims for c in claim["citas"]),
        "contradicciones": [c.model_dump() for c in brief.contradicciones] if brief else [],
        "preguntas_investigacion": brief.preguntas_investigacion if brief else [],
        "verificaciones_pendientes": _unique(v for o in outputs for v in o.verificaciones_pendientes),
        "borrador": {task: (d.result.output.borrador if not d.skipped else None) for task, d in drafts.items()},
        "alertas": alerts,
        "evidencia_oficial_faltante": package.missing_official,
        "generacion": {task: {"origen": d.result.source, "intentos": d.attempts,
                              "afirmaciones": [d.result.report.claims_kept, d.result.report.claims_received],
                              "citas": [d.result.report.citations_kept, d.result.report.citations_received],
                              "latencia_s": d.result.latency_s, "tokens": d.result.usage or {}}
                       for task, d in drafts.items()},
        "estado_revision": review.get("estado_revision", "nuevo"),
        "revisor": review.get("revisor"),
        "fecha_revision": review.get("fecha_revision"),
        "recirculada": recirculated,
        "sintetico": synthetic,
        "generado_en": _utc_now(),
    }


# --- review log (append-only) ----------------------------------------------------------------

def append_review(id_caso: str, estado_revision: str, revisor: str, nota: str = "",
                  path: Path = REVIEWS_PATH, now: str | None = None) -> dict:
    """Validate and append one review decision; returns the stored record."""
    if estado_revision not in REVIEW_STATES:
        raise ValueError(f"estado_revision must be one of {REVIEW_STATES}")
    if not id_caso or not revisor or not revisor.strip():
        raise ValueError("id_caso and revisor are required")
    record = {"id_caso": id_caso, "estado_revision": estado_revision, "revisor": revisor.strip(),
              "fecha_revision": now or _utc_now(), "nota": nota}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_reviews(path: Path = REVIEWS_PATH) -> tuple[list[dict], int]:
    """All valid review records in file order, and how many lines were skipped as invalid."""
    if not path.exists():
        return [], 0
    records, skipped = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if record.get("id_caso") and record.get("estado_revision") in REVIEW_STATES:
            records.append(record)
        else:
            skipped += 1
    return records, skipped


def latest_reviews(path: Path = REVIEWS_PATH) -> dict[str, dict]:
    """Last decision per case (file order: the log is append-only)."""
    latest: dict[str, dict] = {}
    for record in read_reviews(path)[0]:
        latest[record["id_caso"]] = record
    return latest


def apply_reviews(cards: list[dict], reviews: dict[str, dict]) -> list[dict]:
    """Cards with their latest review state; cases never reviewed stay "nuevo"."""
    out = []
    for card in cards:
        review = reviews.get(card["id_caso"], {})
        out.append({**card, "estado_revision": review.get("estado_revision", card.get("estado_revision", "nuevo")),
                    "revisor": review.get("revisor", card.get("revisor")),
                    "fecha_revision": review.get("fecha_revision", card.get("fecha_revision"))})
    return out


# --- build and export --------------------------------------------------------------------------

def load_inputs() -> dict:
    """Contract files if present; the synthetic stub for news until B-01/B-02 land."""
    from src.ingest.worldbank import read_indicators

    news = pd.read_parquet(NEWS_PATH if NEWS_PATH.exists() else NEWS_STUB_PATH)
    contexto_path = PROCESSED / "contexto.parquet"
    indicators_path, events_path = PROCESSED / "indicadores.csv", PROCESSED / "eventos.geojson"
    return {
        "news": news,
        "contexto": pd.read_parquet(contexto_path) if contexto_path.exists() else None,
        "official": official_index(
            read_indicators(indicators_path) if indicators_path.exists() else None,
            json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else None,
        ),
    }


def build_fichas(news: pd.DataFrame, contexto: pd.DataFrame | None = None, official: dict | None = None,
                 top_n: int | None = DEFAULT_TOP_N, now: pd.Timestamp | None = None,
                 client: LLMClient | None = None, offline: bool | None = None, cache_dir: Path = CACHE_DIR,
                 reviews: dict[str, dict] | None = None) -> list[dict]:
    """Cards for the top N clusters by P (all clusters if top_n is None), in ranking order."""
    scored = score_clusters(news, contexto=contexto, now=now)
    selected = scored if top_n is None else scored.head(top_n)
    synthetic = news.groupby("cluster_id")["sintetico"].any() if "sintetico" in news else pd.Series(dtype=bool)
    reviews = reviews or {}
    cards = []
    for _, row in selected.iterrows():
        package = build_package(row["cluster_id"], news, scored, contexto=contexto, official=official,
                                client=client, offline=offline, cache_dir=cache_dir)
        cards.append(card_from_package(package, row, synthetic=bool(synthetic.get(row["cluster_id"], False)),
                                       review=reviews.get(case_id(row["cluster_id"]))))
    return cards


def export_fichas(cards: list[dict], path: Path = FICHAS_PATH) -> Path:
    """Atomic JSONL write: the app never reads a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as tmp:
        for card in cards:
            tmp.write(json.dumps(card, ensure_ascii=False, default=str) + "\n")
    os.replace(tmp.name, path)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build outputs/fichas.jsonl (J-09)")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N, help="clusters by P (0 = all)")
    args = parser.parse_args()
    inputs = load_inputs()
    cards = build_fichas(**inputs, top_n=args.top or None, reviews=latest_reviews())
    path = export_fichas(cards)
    sources = pd.Series([g["origen"] for c in cards for g in c["generacion"].values()]).value_counts().to_dict()
    abstained = sum(c["abstencion"] for c in cards)
    print(f"{len(cards)} fichas -> {path.relative_to(ROOT)} · abstenciones: {abstained} · origen: {sources}")


if __name__ == "__main__":
    main()
