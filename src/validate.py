"""Validation and data-quality report (B-05, test T01). Owner: B.

validate_news splits out news rows with an invalid date, a broken URL, an invalid or
duplicate id, an empty required field or a value outside the contract lists. It never
raises on bad data: valid rows go on and every problem is listed in
outputs/reports/calidad.md. Nullable fields (descripcion, idioma, fecha_publicacion,
fecha_deteccion and the NLP columns) stay null: a null is "no data", not an error,
and is never filled with 0 or with another date.

Dates must be ISO 8601. A value with an offset is converted to UTC; a value without
one is read as UTC (the contract stores every date in UTC). Day-first strings such as
"06/10/2026" are ambiguous and rejected.

The report also summarizes indicadores.csv (B-03) and eventos.geojson (B-04).

Usage: python -m src.validate
"""

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NEWS_PATH = ROOT / "data" / "processed" / "noticias.parquet"
INDICATORS_PATH = ROOT / "data" / "processed" / "indicadores.csv"
EVENTS_PATH = ROOT / "data" / "processed" / "eventos.geojson"
REPORT_PATH = ROOT / "outputs" / "reports" / "calidad.md"

REQUIRED = ["id_noticia", "titulo", "url", "medio", "dominio", "origen", "alcance_texto", "fecha_extraccion"]
DATE_FIELDS = ["fecha_publicacion", "fecha_deteccion", "fecha_extraccion"]
ALLOWED = {"origen": {"tvn_rss", "gdelt"}, "alcance_texto": {"titular/metadatos", "descripcion_rss"}}
BOOL_FIELDS = ["sintetico", "recirculada"]
ID_PATTERN = re.compile(r"N-[0-9a-f]{10}")
ISSUE_COLUMNS = ["fila", "id_noticia", "campo", "problema", "valor"]


@dataclass
class ValidationResult:
    valid: pd.DataFrame
    rejected: pd.DataFrame
    issues: pd.DataFrame
    n_read: int


def _blank_to_none(value):
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None if pd.isna(value) else value


def _parse_date(value) -> tuple[pd.Timestamp | None, bool]:
    """(UTC timestamp or None, ok). None input is a kept null, not an error."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None, True
    if isinstance(value, pd.Timestamp):
        return (value.tz_localize("UTC") if value.tzinfo is None else value.tz_convert("UTC")), True
    try:
        return pd.to_datetime(value, utc=True, format="ISO8601"), True
    except (ValueError, TypeError):
        return None, False


def _url_ok(value: str) -> bool:
    parts = urlparse(value)
    return parts.scheme in {"http", "https"} and "." in parts.netloc


def read_news_csv(path: Path) -> pd.DataFrame:
    """Read a news CSV as text (empty cell -> null); boolean flags become bool."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    for col in BOOL_FIELDS:
        if col in df.columns:
            df[col] = df[col].str.strip().str.lower() == "true"
    return df


def validate_news(df: pd.DataFrame) -> ValidationResult:
    """Split rows with problems from valid rows; never raises on bad data."""
    df = df.reset_index(drop=True)
    text_cols = [c for c in df.columns if c not in BOOL_FIELDS and not pd.api.types.is_numeric_dtype(df[c])]
    clean = df.copy()
    for col in text_cols:
        if not pd.api.types.is_datetime64_any_dtype(df[col]):
            clean[col] = df[col].map(_blank_to_none).astype(object)

    issues = []

    def flag(i: int, field: str, problem: str) -> None:
        raw = df.at[i, field] if field in df.columns else None
        issues.append({"fila": i, "id_noticia": clean.at[i, "id_noticia"] if "id_noticia" in clean else None,
                       "campo": field, "problema": problem, "valor": None if raw is None or pd.isna(raw) else str(raw)})

    parsed = {field: [] for field in DATE_FIELDS if field in clean.columns}
    seen_ids = set()
    for i in clean.index:
        for field in REQUIRED:
            if field not in clean.columns or clean.at[i, field] is None:
                flag(i, field, "campo obligatorio vacío")
        for field in parsed:
            stamp, ok = _parse_date(clean.at[i, field])
            parsed[field].append(stamp)
            if not ok:
                flag(i, field, "fecha inválida")
        url = clean.at[i, "url"] if "url" in clean else None
        if url is not None and not _url_ok(url):
            flag(i, "url", "URL rota")
        news_id = clean.at[i, "id_noticia"] if "id_noticia" in clean else None
        if news_id is not None:
            if not ID_PATTERN.fullmatch(news_id):
                flag(i, "id_noticia", "ID inválido")
            elif news_id in seen_ids:
                flag(i, "id_noticia", "ID duplicado")
            seen_ids.add(news_id)
        for field, allowed in ALLOWED.items():
            value = clean.at[i, field] if field in clean else None
            if value is not None and value not in allowed:
                flag(i, field, "valor fuera de lista")
        if "fecha_deteccion" in parsed and clean.at[i, "origen"] == "tvn_rss" and parsed["fecha_deteccion"][-1] is not None:
            flag(i, "fecha_deteccion", "fecha_deteccion en tvn_rss")

    for field, stamps in parsed.items():
        clean[field] = pd.to_datetime(pd.Series(stamps, index=clean.index, dtype=object), utc=True)

    issues_df = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    bad_rows = set(issues_df["fila"])
    keep = ~clean.index.isin(bad_rows)
    return ValidationResult(clean[keep].reset_index(drop=True), clean[~keep].reset_index(drop=True), issues_df, len(df))


def _cell(value) -> str:
    return "" if value is None else str(value).replace("|", "\\|").replace("\n", " ")


def _null_table(df: pd.DataFrame) -> list[str]:
    lines = ["| columna | nulos |", "| --- | --- |"]
    lines += [f"| {col} | {int(n)} |" for col, n in df.isna().sum().items()]
    return lines


def build_report(news: ValidationResult | None, indicators: pd.DataFrame | None, events: pd.DataFrame | None, generated_at: str) -> str:
    """Markdown quality report (in Spanish: read by the team and the jury)."""
    out = [
        "# Reporte de calidad de datos",
        "",
        f"Generado: {generated_at} (UTC) · B-05 · `src/validate.py`",
        "",
        "Las filas con errores se separan y la carga sigue. Los nulos permitidos se conservan como nulos (nunca 0).",
        "",
        "## Noticias (`noticias.parquet`)",
        "",
    ]
    if news is None:
        out.append("El archivo no existe todavía (B-01, B-02).")
    else:
        out += [f"- Filas leídas: {news.n_read}", f"- Filas válidas: {len(news.valid)}", f"- Filas separadas: {len(news.rejected)}", ""]
        if not news.issues.empty:
            out += ["### Problemas por tipo", "", "| problema | filas |", "| --- | --- |"]
            out += [f"| {p} | {n} |" for p, n in news.issues.groupby("problema")["fila"].nunique().items()]
            out += ["", "### Detalle", "", "| id_noticia | campo | problema | valor |", "| --- | --- | --- | --- |"]
            out += [f"| {_cell(r.id_noticia)} | {r.campo} | {r.problema} | {_cell(r.valor)} |" for r in news.issues.itertuples()]
            out.append("")
        out += ["### Nulos por columna (filas válidas)", "", *_null_table(news.valid)]
    for title, df, owner in (("Banco Mundial (`indicadores.csv`)", indicators, "B-03"), ("USGS (`eventos.geojson`)", events, "B-04")):
        out += ["", f"## {title}", ""]
        if df is None:
            out.append(f"El archivo no existe todavía ({owner}).")
        else:
            out += [f"- Filas: {len(df)}", "", *_null_table(df)]
    return "\n".join(out) + "\n"


def write_report(text: str, path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    from src.ingest.usgs import read_events
    from src.ingest.worldbank import read_indicators

    news = validate_news(pd.read_parquet(NEWS_PATH)) if NEWS_PATH.exists() else None
    indicators = read_indicators(INDICATORS_PATH) if INDICATORS_PATH.exists() else None
    events = read_events(EVENTS_PATH) if EVENTS_PATH.exists() else None
    generated_at = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    write_report(build_report(news, indicators, events, generated_at))
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
