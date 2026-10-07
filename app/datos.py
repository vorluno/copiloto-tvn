"""Data and quality screen (C-16). Owner: Cristian.

Pure functions, no Streamlit. Everything shown comes from files B already writes:
data/manifest.json (B-10), docs/notion/catalogo.csv (B-15) and outputs/reports/calidad.md
(B-05). Integrity is checked with src.manifest.verify (B-17, `make verify`).
"""

import csv
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "manifest.json"
CATALOG_PATH = ROOT / "docs" / "notion" / "catalogo.csv"
QUALITY_PATH = ROOT / "outputs" / "reports" / "calidad.md"


def load_manifest(path: Path = MANIFEST_PATH) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_catalog(path: Path = CATALOG_PATH) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_quality(path: Path = QUALITY_PATH) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _size(n_bytes) -> str:
    if n_bytes is None:
        return "—"
    return f"{n_bytes / 1_048_576:.1f} MB" if n_bytes >= 1_048_576 else f"{n_bytes / 1024:.0f} KB"


def files_table(manifest: dict | None) -> pd.DataFrame:
    """One row per delivered file: path, rows, size, short hash and license. Missing stays '—'."""
    rows = []
    for entry in (manifest or {}).get("archivos", []):
        license_ = entry.get("licencia")
        if isinstance(license_, dict):  # noticias.parquet: one license per origin
            license_ = "Por origen (ver Fuentes)"
        rows.append({
            "Archivo": entry["ruta"],
            "Filas": "—" if entry.get("filas") is None else f"{entry['filas']:,}",
            "Tamaño": _size(entry.get("bytes")),
            "SHA-256": (entry.get("sha256") or "—")[:12],
            "Licencia": license_ or "—",
            "Descripción": entry.get("descripcion") or "—",
        })
    return pd.DataFrame(rows, columns=["Archivo", "Filas", "Tamaño", "SHA-256", "Licencia", "Descripción"])


def sources_table(catalog: list[dict]) -> pd.DataFrame:
    """Sources with coverage and license, as the catalog (B-15) writes them."""
    return pd.DataFrame([{
        "Fuente": r.get("Fuente"), "Cobertura": r.get("Cobertura"), "Licencia / condiciones": r.get("Licencia / condiciones"),
        "Fecha de extracción": r.get("Fecha de extracción"), "Filas": r.get("Filas"),
    } for r in catalog], columns=["Fuente", "Cobertura", "Licencia / condiciones", "Fecha de extracción", "Filas"])


def news_by_origin(manifest: dict | None) -> dict[str, int]:
    for entry in (manifest or {}).get("archivos", []):
        if entry["ruta"].endswith("noticias.parquet"):
            return entry.get("por_origen") or {}
    return {}


def verify_messages(problems: list[str]) -> list[str]:
    """src.manifest.verify output in Spanish, for the editor and the jury."""
    out = []
    for p in problems:
        path, _, what = p.partition(": ")
        if what == "missing":
            out.append(f"`{path}`: falta el archivo")
        elif "SHA-256" in what:
            out.append(f"`{path}`: el SHA-256 no coincide con el manifest (el archivo cambió)")
        else:
            out.append(f"`{path}`: {what}")
    return out


def cache_count(cache_dir: Path) -> int:
    return sum(1 for _ in cache_dir.glob("*.json")) if cache_dir.exists() else 0
