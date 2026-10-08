"""Page 5 "Casos y evidencias" as Markdown in the repo (J-14, ADR-047). Owner: José.

The organization did not provide Notion (8 oct), so the 8 pages live in docs/notion/.
This page is built from the contract files, never by hand: outputs/fichas.jsonl plus the
latest decision per case in outputs/revisiones.jsonl, with P and R..E from score_clusters
(the same numbers as the inbox). Each case uses the app's own export (card_markdown), so
the page and "Copiar para Notion" never disagree.

    python tools/casos_md.py            # writes docs/notion/casos.md
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.bandeja import build_inbox, read_cards  # noqa: E402
from app.revision import card_markdown  # noqa: E402
from src.fichas import FICHAS_PATH, REVIEWS_PATH, apply_reviews, latest_reviews, load_inputs  # noqa: E402
from src.score import score_clusters  # noqa: E402

OUT_PATH = ROOT / "docs" / "notion" / "casos.md"


def build(cards: list[dict], reviews: dict[str, dict], scored=None, headlines: dict | None = None) -> str:
    """headlines: cluster_id -> the source headline the inbox shows, for cases the model
    gave no title (abstentions). It is labeled as the source's headline, not a title."""
    cards = apply_reviews(cards, reviews)
    headlines = headlines or {}
    cards = [c if c.get("titulo") or not headlines.get(c.get("cluster_id")) else
             {**c, "titulo": f"titular de la fuente: «{headlines[c['cluster_id']]}»"} for c in cards]
    by_cluster = {} if scored is None else scored.set_index("cluster_id").to_dict("index")
    abstained = sum(1 for c in cards if c.get("abstencion"))
    reviewed = sum(1 for c in cards if c.get("revisor"))
    lines = [
        "# 5 · Casos y evidencias",
        "",
        "Generado con `python tools/casos_md.py` desde `outputs/fichas.jsonl` y `outputs/revisiones.jsonl`;",
        "no se edita a mano. P y sus componentes salen de `score_clusters`, igual que en la bandeja.",
        "",
        f"**{len(cards)} casos** · {len(cards) - abstained} con borrador · {abstained} abstenidos por evidencia "
        f"insuficiente · {reviewed} con persona revisora.",
        "",
        "| Caso | Título | P | Estado de evidencia | Estado de revisión | Persona revisora |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in cards:
        score = by_cluster.get(c.get("cluster_id"))
        p = score["P"] if score else (c.get("puntaje") or {}).get("P")
        title = (c.get("titulo") or c.get("consulta") or "—").replace("|", "/")
        lines.append(f"| `{c['id_caso']}` | {title} | {'—' if p is None else f'{p:.1f}'} | "
                     f"{c.get('estado_evidencia') or '—'} | {c.get('estado_revision') or 'nuevo'} | "
                     f"{c.get('revisor') or '— (sin revisar)'} |")
    lines.append("")
    for c in cards:
        score = by_cluster.get(c.get("cluster_id"))
        lines += [card_markdown(c, score=score, action=c.get("accion_recomendada")), "---", ""]
    return "\n".join(lines).rstrip("-\n ") + "\n"


def main() -> None:
    inputs = load_inputs()
    scored = score_clusters(inputs["news"], contexto=inputs.get("contexto"))
    cards = read_cards(FICHAS_PATH)
    inbox = build_inbox(scored, inputs["news"], cards)
    headlines = dict(zip(inbox["cluster_id"], inbox["titular"]))
    text = build(cards, latest_reviews(REVIEWS_PATH), scored, headlines)
    OUT_PATH.write_text(text, encoding="utf-8")
    print(f"{OUT_PATH.relative_to(ROOT)}: {text.count('## F-')} casos")


if __name__ == "__main__":
    main()
