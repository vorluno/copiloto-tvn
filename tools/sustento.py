"""Validez de sustento (reto, secc. 9.1): tally of the human review in sustento_revision.csv.

`make eval` writes one row per citation of every claim shown to the editor. A person reads
each cited passage and writes "sí" or "no" in `valida` (does this passage back the claim?),
plus their name in `revisor`. A claim is supported when at least one of its citations is
marked "sí"; it is unsupported when every marked citation says "no"; unmarked claims are not
counted. Goal: ≥ 90 % over ≥ 30 reviewed claims.

`prevalidacion_ia` / `motivo_ia` hold an automatic pre-review (Claude, 8 oct). It is shown
apart and never counts as the human review. A person who has read it and agrees can copy
it into the empty `valida` cells under their own name with --confirmar; the report then
says the human review confirmed the pre-review, so the method stays visible.

    python tools/sustento.py                     # prints the result, writes outputs/reports/sustento.md
    python tools/sustento.py --confirmar "José"  # a person adopts the pre-review as their review
"""

import argparse
import csv
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "outputs" / "reports" / "sustento_revision.csv"
OUT_PATH = ROOT / "outputs" / "reports" / "sustento.md"
YES, NO = {"si", "s", "yes", "1", "x", "true"}, {"no", "n", "0", "false"}
CONFIRMED = "confirmado sobre la pre-revisión automática"
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
    pre = defaultdict(list)
    for row in rows:
        pre[(row["id_consulta"], row["afirmacion"])].append(_mark(row.get("prevalidacion_ia")))
    pre_ok = sum(1 for marks in pre.values() if any(m is True for m in marks))
    pre_done = sum(1 for marks in pre.values() if any(m is not None for m in marks))
    confirmed = any(CONFIRMED in (row.get("nota") or "") for row in rows)
    supported, unsupported = [], []
    for key, marks in claims.items():
        if any(m is True for m in marks):
            supported.append(key)
        elif marks and any(m is False for m in marks) and not any(m is True for m in marks):
            unsupported.append(key)
    reviewed = len(supported) + len(unsupported)
    return {"claims": len(claims), "reviewed": reviewed, "supported": len(supported),
            "unsupported": unsupported, "reviewers": sorted(reviewers),
            "rate": len(supported) / reviewed if reviewed else None,
            "pre_ok": pre_ok, "pre_done": pre_done, "confirmed": confirmed}


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
    if result.get("confirmed"):
        lines += ["Método: la persona revisora leyó la pre-revisión automática y la adoptó como suya "
                  "(`--confirmar`); las filas lo dicen en `nota`.", ""]
    if result.get("pre_done"):
        lines += [f"Pre-revisión automática (Claude, no cuenta como revisión humana): "
                  f"{result['pre_ok']}/{result['pre_done']} afirmaciones con sustento.", ""]
    if result["unsupported"]:
        lines += ["## Afirmaciones sin sustento", ""] + [f"- {q}: {text}" for q, text in result["unsupported"]]
    return "\n".join(lines).rstrip() + "\n"


def confirm(rows: list[dict], reviewer: str) -> int:
    """A person adopts the pre-review: fills only empty `valida` cells, under their name."""
    changed = 0
    for row in rows:
        if _mark(row.get("valida")) is None and _mark(row.get("prevalidacion_ia")) is not None:
            row["valida"], row["revisor"] = row["prevalidacion_ia"], reviewer
            row["nota"] = "; ".join(x for x in ((row.get("nota") or "").strip(), CONFIRMED) if x)
            changed += 1
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description="Validez de sustento (revisión humana)")
    parser.add_argument("--confirmar", metavar="NOMBRE", help="la persona adopta la pre-revisión como su revisión")
    args = parser.parse_args()
    if not CSV_PATH.exists():
        sys.exit(f"Falta {CSV_PATH.relative_to(ROOT)}: correr OFFLINE=1 make eval")
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    if args.confirmar:
        n = confirm(rows, args.confirmar.strip())
        with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        print(f"{n} filas confirmadas por {args.confirmar.strip()}")
    result = tally(rows)
    text = report(result)
    OUT_PATH.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
