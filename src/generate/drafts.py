"""Editorial package per cluster (J-08): brief, guion and copy with citations. Owner: José.

`build_package` puts together, for one cluster:
- the evidence: its news items plus the official items (World Bank, USGS) that
  contexto.parquet (B-14) links to it; nothing else can be cited;
- one draft per task through `generate_draft` (cache, offline mode and guard included);
- one retry per task when the guard rejects something, telling the model what failed.
  The retry changes the request, so it gets its own cache entry and replays offline.

If the brief abstains (not enough evidence), guion and copy are not requested: same
abstention, no extra cost. Cut order if time runs short (docs/jose.md): guion, then copy;
the brief with citations is never cut.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path

import pandas as pd

from src.generate.generate import CACHE_DIR, DraftRequest, DraftResult, LLMClient, generate_draft
from src.generate.schema import Evidence, Task, evidence_from_indicator, evidence_from_news, evidence_from_quake

TASKS: tuple[Task, ...] = ("brief", "guion", "copy")
MAX_FEEDBACK_ITEMS = 8


@dataclass
class TaskDraft:
    task: Task
    result: DraftResult
    attempts: int
    skipped: bool = False  # not requested because the brief abstained


@dataclass
class EditorialPackage:
    cluster_id: str
    topic: str
    score: dict
    evidence_state: str
    evidence: list[Evidence]
    drafts: dict[str, TaskDraft] = field(default_factory=dict)
    missing_official: list[str] = field(default_factory=list)  # linked in contexto but not found

    @property
    def abstained(self) -> bool:
        brief = self.drafts.get("brief")
        return brief is not None and brief.result.output.abstencion


def official_index(indicadores: pd.DataFrame | None = None, eventos: dict | None = None) -> dict[str, Evidence]:
    """Every citable official item by ID. Null World Bank values are left out."""
    index: dict[str, Evidence] = {}
    if indicadores is not None:
        for _, row in indicadores.iterrows():
            if (item := evidence_from_indicator(row)) is not None:
                index[item.id] = item
    if eventos is not None:
        for feature in eventos.get("features", []):
            item = evidence_from_quake(feature)
            index[item.id] = item
    return index


def cluster_evidence(
    cluster_id: str,
    news: pd.DataFrame,
    contexto: pd.DataFrame | None = None,
    official: dict[str, Evidence] | None = None,
) -> tuple[list[Evidence], list[str]]:
    """News of the cluster (stable order) + linked official items; also returns missing links."""
    rows = news[news["cluster_id"] == cluster_id].sort_values("id_noticia")
    evidence = [evidence_from_news(row) for _, row in rows.iterrows()]
    missing: list[str] = []
    if contexto is not None:
        for evidence_id in sorted(contexto.loc[contexto["cluster_id"] == cluster_id, "id_evidencia"].unique()):
            item = (official or {}).get(evidence_id)
            if item is None:
                missing.append(evidence_id)
            else:
                evidence.append(item)
    return evidence, missing


def describe_score(row: pd.Series) -> str:
    parts = " ".join(f"{k} {row[k]:.2f}" for k in ("R", "I", "U", "N", "E"))
    return f"P {row['P']:.1f} ({row['rango']}; {parts}; reglas {row['version_reglas']})"


def cluster_topic(cluster_id: str, news: pd.DataFrame, topic: str) -> str:
    """Topic label: theme + most recent headline of the cluster."""
    rows = news[news["cluster_id"] == cluster_id]
    when = rows["fecha_publicacion"].fillna(rows["fecha_deteccion"])
    latest = rows.assign(_when=when).sort_values(["_when", "id_noticia"], ascending=[False, True]).iloc[0]
    return f"{topic} · {latest['titulo']}"


def _feedback(result: DraftResult) -> list[str]:
    report = result.report
    items = [f"afirmación descartada ({d.reason}): {d.texto[:120]}" for d in report.dropped_claims]
    items += [f"cita inválida: {c}" for c in report.dropped_citations]
    items += report.violations
    if report.blocked and report.block_reason:
        items.append(f"salida bloqueada: {report.block_reason}")
    return items[:MAX_FEEDBACK_ITEMS]


def draft_with_retry(
    request: DraftRequest, client: LLMClient | None, offline: bool | None, cache_dir: Path
) -> TaskDraft:
    first = generate_draft(request, client=client, offline=offline, cache_dir=cache_dir)
    if first.report.ok or first.source in ("offline_miss", "error"):
        return TaskDraft(request.task, first, attempts=1)
    retry = generate_draft(replace(request, feedback=_feedback(first)), client=client, offline=offline,
                           cache_dir=cache_dir)
    improved = retry.source not in ("offline_miss", "error") and (
        retry.report.ok or retry.report.claims_kept > first.report.claims_kept
    )
    return TaskDraft(request.task, retry if improved else first, attempts=2)


def build_package(
    cluster_id: str,
    news: pd.DataFrame,
    scored: pd.DataFrame,
    contexto: pd.DataFrame | None = None,
    official: dict[str, Evidence] | None = None,
    tasks: tuple[Task, ...] = TASKS,
    client: LLMClient | None = None,
    offline: bool | None = None,
    cache_dir: Path = CACHE_DIR,
) -> EditorialPackage:
    """Brief, guion and copy for one cluster, every claim cited and checked by the guard."""
    row = scored.set_index("cluster_id").loc[cluster_id]
    evidence, missing = cluster_evidence(cluster_id, news, contexto, official)
    package = EditorialPackage(
        cluster_id=cluster_id,
        topic=cluster_topic(cluster_id, news, row["tema"]),
        score={k: row[k] for k in ("P", "rango", "R", "I", "U", "N", "E", "version_reglas")},
        evidence_state=row["estado_evidencia"],
        evidence=evidence,
        missing_official=missing,
    )
    base = DraftRequest(task="brief", topic=package.topic, evidence=evidence,
                        score_line=describe_score(row), evidence_state=package.evidence_state)
    ordered = ("brief",) + tuple(t for t in tasks if t != "brief") if "brief" in tasks else tasks
    for task in ordered:
        if package.abstained:
            brief = package.drafts["brief"]
            package.drafts[task] = TaskDraft(task, brief.result, attempts=0, skipped=True)
            continue
        package.drafts[task] = draft_with_retry(replace(base, task=task), client, offline, cache_dir)
    return package
