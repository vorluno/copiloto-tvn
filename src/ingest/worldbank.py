"""World Bank API v2 ingestion (B-03). Owner: B.

PAN;CRI;COL;DOM;MEX;GTM, 2010:2024, 6 indicators (docs/alcance-y-datos.md §3.B), one
request per indicator. Fills the country x indicator x year grid (6 x 6 x 15 = 540 rows)
with a null valor where the API has no value: missing data is "no data", never 0.
Units come from the indicator table because the API returns `unit` empty. Every row
carries the CC BY 4.0 license, its query URL and the UTC extraction time.

Raw responses go to data/raw/worldbank/ (git-ignored); the grid to
data/processed/indicadores.csv.

Usage: python -m src.ingest.worldbank
"""

import json
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "worldbank"
OUTPUT_PATH = ROOT / "data" / "processed" / "indicadores.csv"

COUNTRIES = ["PAN", "CRI", "COL", "DOM", "MEX", "GTM"]
YEARS = range(2010, 2025)
INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": "% anual",
    "FP.CPI.TOTL.ZG": "% anual",
    "SL.UEM.TOTL.ZS": "% de la fuerza laboral",
    "SP.POP.TOTL": "personas",
    "IT.NET.USER.ZS": "% de la población",
    "NE.EXP.GNFS.ZS": "% del PIB",
}
LICENSE = "CC BY 4.0"
COLUMNS = ["pais_iso3", "indicador_id", "anio", "valor", "unidad", "fuente_url", "fecha_extraccion", "licencia"]

API_URL = "https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}"
PER_PAGE = 1000
TIMEOUT_S = 30


def query_url(indicator: str, page: int | None = None) -> str:
    """Public, reproducible URL of the query for one indicator (also the row's fuente_url)."""
    url = API_URL.format(countries=";".join(COUNTRIES), indicator=indicator)
    url += f"?date={YEARS[0]}:{YEARS[-1]}&format=json&per_page={PER_PAGE}"
    return url if page is None else f"{url}&page={page}"


def parse_response(body: list) -> list[dict]:
    """Return the data records of one API page; raise if the API answered with an error."""
    if len(body) == 1 and "message" in body[0]:
        messages = "; ".join(f"{m.get('key')}: {m.get('value')}" for m in body[0]["message"])
        raise RuntimeError(f"World Bank API error: {messages}")
    return body[1] or []


def fetch_indicator(indicator: str) -> list[dict]:
    """Download every page for one indicator and keep the raw responses."""
    records, page, pages = [], 1, 1
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    while page <= pages:
        response = requests.get(query_url(indicator, page), timeout=TIMEOUT_S)
        response.raise_for_status()
        body = response.json()
        (RAW_DIR / f"{indicator}_p{page}.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        records.extend(parse_response(body))
        pages = body[0].get("pages") or 1
        page += 1
    return records


def build_grid(records_by_indicator: dict[str, list[dict]], extracted_at: str) -> pd.DataFrame:
    """Full country x indicator x year grid; valor stays null wherever the API has no value."""
    values = {}
    for indicator, records in records_by_indicator.items():
        for rec in records:
            year = int(rec["date"])
            if rec["countryiso3code"] in COUNTRIES and year in YEARS and rec["value"] is not None:
                values[(rec["countryiso3code"], indicator, year)] = float(rec["value"])

    rows = [
        {
            "pais_iso3": country,
            "indicador_id": indicator,
            "anio": year,
            "valor": values.get((country, indicator, year)),
            "unidad": unit,
            "fuente_url": query_url(indicator),
            "fecha_extraccion": extracted_at,
            "licencia": LICENSE,
        }
        for country in COUNTRIES
        for indicator, unit in INDICATORS.items()
        for year in YEARS
    ]
    grid = pd.DataFrame(rows, columns=COLUMNS)
    grid["valor"] = grid["valor"].astype("float64")
    return grid


def write_indicators(grid: pd.DataFrame, path: Path = OUTPUT_PATH) -> None:
    """UTF-8 CSV; a null valor is written as an empty cell."""
    path.parent.mkdir(parents=True, exist_ok=True)
    grid.to_csv(path, index=False, encoding="utf-8", na_rep="")


def read_indicators(path: Path = OUTPUT_PATH) -> pd.DataFrame:
    """Read the grid back with the contract types (empty valor -> NaN)."""
    return pd.read_csv(path, encoding="utf-8", dtype={"anio": "int64", "valor": "float64"}, keep_default_na=False, na_values={"valor": [""]})


def main() -> None:
    extracted_at = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    records = {indicator: fetch_indicator(indicator) for indicator in INDICATORS}
    grid = build_grid(records, extracted_at)
    write_indicators(grid)
    missing = grid["valor"].isna().sum()
    print(f"Wrote {len(grid)} rows to {OUTPUT_PATH.relative_to(ROOT)} ({missing} with null valor)")


if __name__ == "__main__":
    main()
