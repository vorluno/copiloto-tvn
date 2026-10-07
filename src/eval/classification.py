"""Topic and event metrics against the human labels (B-12). Owner: B.

Reads data/etiquetas_humanas.csv (C-05) and writes outputs/reports/clasificacion.md:

- Topics: macro-F1 of the AI (embeddings) and of the keyword baseline over the 7 labels
  (6 topics + "otro"). The labeled news are split in two fixed halves (by the SHA-1 of
  id_noticia): the topic threshold is calibrated on the first half and every number is
  reported on the second, so the threshold never sees the news it is scored on.
- Events: pairwise precision and recall of cluster_id (AI) and of the TF-IDF duplicates
  (baseline) against cluster_humano, on every labeled item. The clustering rule was
  fixed before the labels were read (0.30 + 2 shared content stems, 7 oct) and is not
  tuned here: a split would separate most labeled pairs. A sensitivity table over the
  distance (same word rule) is shown as exploratory. Rows whose `nota` says they were
  corrected after comparing with the system (#62) are also scored "blind": each one back
  to an event of its own, as in the blind delivery, so the reader sees both numbers.

Every metric comes with numerator and denominator, and the errors are listed.

Usage: python -m src.eval.classification
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.eval.metrics import pairwise, topic_f1
from src.nlp import classify, cluster, embed
from src.nlp.provenance import reference_time

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
LABELS_PATH = ROOT / "data" / "etiquetas_humanas.csv"
REPORT_PATH = ROOT / "outputs" / "reports" / "clasificacion.md"
LABELS = classify.TOPICS + [classify.OTHER]
THRESHOLDS = [round(t, 2) for t in np.arange(0.30, 0.71, 0.05)]
DISTANCES = [0.20, 0.25, 0.30, 0.35, 0.40]


def load_labels(path: Path = LABELS_PATH) -> tuple[pd.DataFrame, list[str]]:
    """Labeled rows with a valid topic and an event number; also the problems found."""
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    allowed = {label.casefold(): label for label in LABELS}
    rows, problems = [], []
    for _, r in raw.iterrows():
        topic = allowed.get(r.get("tema_humano", "").strip().casefold())
        event = r.get("cluster_humano", "").strip()
        if topic is None or not event:
            problems.append(f"{r['id_noticia']}: tema_humano={r.get('tema_humano', '')!r}, cluster_humano={event!r}")
            continue
        rows.append({"id_noticia": r["id_noticia"], "tema_humano": topic, "cluster_humano": event,
                     "etiquetador": r.get("etiquetador", "").strip(), "nota": r.get("nota", "").strip()})
    return pd.DataFrame(rows), problems


SEEN_SYSTEM = "comparar con el sistema"  # C-05 (#62): marks a label corrected after seeing cluster_id


def blind_events(labeled: pd.DataFrame) -> pd.Series:
    """cluster_humano with every row corrected after seeing the system back to an event of its own."""
    seen = labeled["nota"].str.contains(SEEN_SYSTEM, case=False, regex=False)
    return labeled["cluster_humano"].where(~seen, "ciega-" + labeled.index.to_series().astype(str))


def split_halves(ids: pd.Series) -> pd.Series:
    """True for the calibration half: fixed, independent of row order."""
    keys = ids.map(lambda i: hashlib.sha1(i.encode("utf-8")).hexdigest())
    return keys.rank(method="first") <= len(ids) // 2


def ai_scores(ids: list[str]) -> pd.DataFrame:
    """Topic similarities of the labeled news from the stored embeddings."""
    stored = json.loads((PROCESSED / "embeddings_ids.json").read_text(encoding="utf-8"))
    vectors = np.load(PROCESSED / "embeddings.npy")
    position = {nid: k for k, nid in enumerate(stored)}
    return classify.topic_scores(vectors[[position[i] for i in ids]]).set_index(pd.Index(ids))


def predict(scores: pd.DataFrame, threshold: float) -> pd.Series:
    best = scores.idxmax(axis=1)
    return best.where(scores.max(axis=1) >= threshold, classify.OTHER)


def calibrate(scores: pd.DataFrame, truth: pd.Series) -> tuple[float, list[tuple[float, float | None]]]:
    """Threshold with the best macro-F1 on the calibration half; ties keep the current one,
    then the lower threshold."""
    table = [(t, topic_f1(truth.tolist(), predict(scores, t).tolist(), LABELS)["macro_f1"]) for t in THRESHOLDS]
    best = max(table, key=lambda x: (x[1] or 0, x[0] == classify.THRESHOLD, -x[0]))
    return best[0], table


def cluster_sensitivity(news: pd.DataFrame, labeled: pd.DataFrame) -> list[tuple[float, str, str]]:
    stored = json.loads((PROCESSED / "embeddings_ids.json").read_text(encoding="utf-8"))
    vectors = np.load(PROCESSED / "embeddings.npy")
    position = {nid: k for k, nid in enumerate(stored)}
    v = vectors[[position[i] for i in news["id_noticia"]]]
    when = reference_time(news)
    words = [cluster.content_words(t) for t in embed.news_text(news)]
    out = []
    for d in DISTANCES:
        labels = pd.Series(cluster.cluster_labels(v, when, d, words=words), index=news["id_noticia"])
        p, r = pairwise(labeled["cluster_humano"].tolist(), labels.loc[labeled["id_noticia"]].tolist(),
                        labeled["id_noticia"].tolist())
        out.append((d, p.describe(), r.describe()))
    return out


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def build_report(labeled: pd.DataFrame, problems: list[str], news: pd.DataFrame, base: pd.DataFrame,
                 scores: pd.DataFrame, sensitivity: list | None = None) -> str:
    labeled = labeled.set_index("id_noticia")
    calib = split_halves(labeled.index.to_series())
    cal_ids, test_ids = labeled.index[calib.to_numpy()], labeled.index[~calib.to_numpy()]
    threshold, table = calibrate(scores.loc[cal_ids], labeled.loc[cal_ids, "tema_humano"])

    truth = labeled.loc[test_ids, "tema_humano"]
    ai = predict(scores.loc[test_ids], threshold)
    bl = base.set_index("id_noticia").loc[test_ids, "tema"]
    m_ai, m_bl = topic_f1(truth.tolist(), ai.tolist(), LABELS), topic_f1(truth.tolist(), bl.tolist(), LABELS)

    by_id = news.set_index("id_noticia")
    all_ids = labeled.index.tolist()
    p_ai, r_ai = pairwise(labeled["cluster_humano"].tolist(), by_id.loc[all_ids, "cluster_id"].tolist(), all_ids)
    p_bl, r_bl = pairwise(labeled["cluster_humano"].tolist(), base.set_index("id_noticia").loc[all_ids, "cluster_id"].tolist(), all_ids)
    blind = blind_events(labeled)
    n_seen = int((blind != labeled["cluster_humano"]).sum())
    p_ai_b, r_ai_b = pairwise(blind.tolist(), by_id.loc[all_ids, "cluster_id"].tolist(), all_ids)

    labelers = ", ".join(sorted(set(labeled["etiquetador"]) - {""})) or "sin nombre"
    lines = [
        "# Clasificación y agrupación contra etiquetas humanas (B-12)", "",
        f"Generado por `python -m src.eval.classification`. Etiquetas: `data/etiquetas_humanas.csv` ({labelers}).", "",
        "## Muestra y método", "",
        f"- Etiquetadas válidas: **{len(labeled)}**; descartadas por etiqueta vacía o fuera de la lista: {len(problems)}.",
        "- Muestra: 60 noticias en español o inglés elegidas por código (semilla 20261007): 40 al azar + 20 vecinas "
        "(la más parecida dentro de ±72 h), para que haya pares del mismo evento. Etiquetado por una persona que no "
        "construyó el modelo, solo con titular y descripción.",
        f"- **Temas:** el umbral se calibra con una mitad fija ({len(cal_ids)} noticias) y todo se reporta con la otra "
        f"({len(test_ids)}). Umbral elegido: **{threshold:.2f}** (en uso en `classify.THRESHOLD`: {classify.THRESHOLD:.2f}).",
        f"- **Eventos:** precisión y recall por pares sobre las {len(all_ids)} etiquetadas; distancia de cluster "
        f"{cluster.DISTANCE_THRESHOLD:.2f} + {cluster.MIN_SHARED_WORDS} raíces de contenido en común, regla fijada con "
        "9 grupos revisados a mano por José antes de leer estas etiquetas (no se ajusta aquí).",
        "- Muestra chica: una noticia cambia el F1 de un tema varios puntos. Los resultados son indicativos.", "",
        "## Temas: IA vs baseline (mitad de reporte)", "",
        "| Sistema | Macro-F1 | Temas medidos | n |", "| --- | --- | --- | --- |",
        f"| IA (embeddings, umbral {threshold:.2f}) | {_fmt(m_ai['macro_f1'])} | {m_ai['n_temas']} | {m_ai['n']} |",
        f"| Baseline (palabras clave) | {_fmt(m_bl['macro_f1'])} | {m_bl['n_temas']} | {m_bl['n']} |", "",
        "Por tema (VP / FP / FN y F1):", "",
        "| Tema | IA | Baseline | Gana |", "| --- | --- | --- | --- |",
    ]
    for label in LABELS:
        a, b = m_ai["per_topic"][label], m_bl["per_topic"][label]
        if a["f1"] is None and b["f1"] is None:
            winner = "sin casos"
        elif (a["f1"] or 0) > (b["f1"] or 0):
            winner = "IA"
        elif (a["f1"] or 0) < (b["f1"] or 0):
            winner = "baseline"
        else:
            winner = "empate"
        lines.append(f"| {label} | {a['tp']}/{a['fp']}/{a['fn']} · {_fmt(a['f1'])} | "
                     f"{b['tp']}/{b['fp']}/{b['fn']} · {_fmt(b['f1'])} | {winner} |")
    lines += ["", "Calibración del umbral (mitad de calibración):", "", "| Umbral | Macro-F1 |", "| --- | --- |"]
    lines += [f"| {t:.2f}{' ←' if t == threshold else ''} | {_fmt(f)} |" for t, f in table]

    lines += ["", "## Eventos: precisión y recall por pares (todas las etiquetadas)", "",
              "| Sistema | Precisión | Recall |", "| --- | --- | --- |",
              f"| IA (embeddings, distancia {cluster.DISTANCE_THRESHOLD:.2f} + {cluster.MIN_SHARED_WORDS} palabras, 72 h) | {p_ai.describe()} | {r_ai.describe()} |",
              f"| Baseline (TF-IDF ≥ 0.9, 72 h) | {p_bl.describe()} | {r_bl.describe()} |", ""]
    if n_seen:
        lines += [f"**{n_seen} etiquetas de evento se corrigieron después de comparar con el sistema** (columna `nota`, "
                  "#62): no son ciegas. Con la entrega ciega (cada una como evento propio) la IA da precisión "
                  f"{p_ai_b.describe()} y recall {r_ai_b.describe()}. Se reportan las dos: con 3 pares, ninguna es concluyente.", ""]
    if sensitivity:
        lines += ["Sensibilidad a la distancia (exploratoria: se mira con las mismas etiquetas):", "",
                  "| Distancia | Precisión | Recall |", "| --- | --- | --- |"]
        lines += [f"| {d:.2f} | {p} | {r} |" for d, p, r in sensitivity]
        lines.append("")

    lines += ["## Errores de tema (mitad de reporte)", "", "| id_noticia | Titular | Humano | IA | Baseline |",
              "| --- | --- | --- | --- | --- |"]
    for nid in test_ids:
        h, a, b = truth[nid], ai[nid], bl[nid]
        if h != a or h != b:
            title = str(by_id.loc[nid, "titulo"])[:90].replace("|", "/")
            lines.append(f"| {nid} | {title} | {h} | {a}{' ✗' if a != h else ''} | {b}{' ✗' if b != h else ''} |")
    lines += ["", "## Pares mal agrupados por la IA", ""]
    wrong = p_ai.failures + r_ai.failures
    lines += [f"- {c} ({'unidos sin ser el mismo evento' if c in p_ai.failures else 'mismo evento, separados'})"
              for c in wrong] or ["- ninguno"]
    if problems:
        lines += ["", "## Filas descartadas", ""] + [f"- {p}" for p in problems]
    return "\n".join(lines) + "\n"


def main() -> None:
    labeled, problems = load_labels()
    if labeled.empty:
        print(f"No labels yet in {LABELS_PATH.relative_to(ROOT)} ({len(problems)} rows without tema_humano/cluster_humano)")
        return
    news = pd.read_parquet(PROCESSED / "noticias.parquet")
    base = pd.read_parquet(PROCESSED / "baseline.parquet")
    scores = ai_scores(labeled["id_noticia"].tolist())
    report = build_report(labeled, problems, news, base, scores, cluster_sensitivity(news, labeled))
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8", newline="\n")
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)} ({len(labeled)} labeled news)")


if __name__ == "__main__":
    main()
