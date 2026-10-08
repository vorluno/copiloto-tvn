"""Validez de sustento (reto, secc. 9.1): tally of the human review in sustento_revision.csv.

`make eval` writes one row per citation of every claim shown to the editor. A person reads
each cited passage and writes "sí" or "no" in `valida` (does this passage back the claim?),
plus their name in `revisor`. A claim is supported when at least one of its citations is
marked "sí"; it is unsupported when every marked citation says "no"; unmarked claims are not
counted. Goal: ≥ 90 % over ≥ 30 reviewed claims. This script never fills `valida`.

    python tools/sustento.py   # prints the result and writes outputs/reports/sustento.md
"""

import csv
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "outputs" / "reports" / "sustento_revision.csv"
OUT_PATH = ROOT / "outputs" / "reports" / "sustento.md"
YES, NO = {"si", "s", "yes", "1", "x", "true"}, {"no", "n", "0", "false"}
GOAL, MIN_CLAIMS = 0.90, 30


def _mark(value: str | None) -> bool | None:
    folded = unicodedata.normalize("NFKD", (value or "").strip().casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return True if folded in YES else False if folded in NO else None


def tally(rows: list[dict]) -> dict:
    claims: dict[tuple, list] = defaultdict(list)
    reviewers = set()
    for row in rows:
        mark = _mark(row.get("valida"))
        claims[(row["id_consulta"], row["afirmacion"])].append(mark)
        if mark is not None and (row.get("revisor") or "").strip():
            reviewers.add(row["revisor"].strip())
    supported, unsupported = [], []
    for key, marks in claims.items():
        if any(m is True for m in marks):
            supported.append(key)
        elif marks and any(m is False for m in marks) and not any(m is True for m in marks):
            unsupported.append(key)
    reviewed = len(supported) + len(unsupported)
    return {"claims": len(claims), "reviewed": reviewed, "supported": len(supported),
            "unsupported": unsupported, "reviewers": sorted(reviewers),
            "rate": len(supported) / reviewed if reviewed else None}


def report(result: dict) -> str:
    rate = result["rate"]
    verdict = ("sin revisar todavía" if rate is None else
               f"{result['supported']}/{result['reviewed']} ({rate:.0%})")
    ok = rate is not None and rate >= GOAL and result["reviewed"] >= MIN_CLAIMS
    lines = ["# Validez de sustento (revisión humana)", "",
             f"Afirmaciones mostradas: {result['claims']} · revisadas: {result['reviewed']} · "
             f"persona(s) revisora(s): {', '.join(result['reviewers']) or '—'}", "",
             f"**Resultado: {verdict}** · meta ≥ {GOAL:.0%} sobre ≥ {MIN_CLAIMS} afirmaciones: "
             + ("cumple" if ok else "no cumple todavía"), ""]
    if result["unsupported"]:
        lines += ["## Afirmaciones sin sustento", ""] + [f"- {q}: {text}" for q, text in result["unsupported"]]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    if not CSV_PATH.exists():
        sys.exit(f"Falta {CSV_PATH.relative_to(ROOT)}: correr OFFLINE=1 make eval")
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        result = tally(list(csv.DictReader(f)))
    text = report(result)
    OUT_PATH.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
