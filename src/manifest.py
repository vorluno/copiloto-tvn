"""Data manifest (B-10). Owner: B.

Writes data/manifest.json: for every delivered data file its SHA-256, size, row count,
the exact queries it comes from, license, excluded rows and why, and the
transformations applied. `verify()` recomputes the hashes (B-17 `make verify` uses it),
so the jury can check that the files are the ones described.

Row exclusions are read from outputs/reports/calidad.md (B-05), the report written by
the same `make news` run, so the manifest never recounts them differently.

Usage: python -m src.manifest            (write)
       python -m src.manifest --verify   (check hashes; exit 1 on a mismatch)
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest import gdelt, tvn_rss, tvn_web, usgs, worldbank
from src.ingest.common import WINDOW_END, WINDOW_START
from src.nlp import classify, cluster, embed, provenance

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MANIFEST_PATH = ROOT / "data" / "manifest.json"
QUALITY_PATH = ROOT / "outputs" / "reports" / "calidad.md"
VERSION = "1.0"

TVN_LICENSE = ("Metadatos públicos de TVN (titular, descripción, fecha y URL). Sin licencia sobre el "
               "artículo: no se guarda el cuerpo, imágenes ni video.")
GDELT_LICENSE = "GDELT Project: uso libre citando la fuente (gdeltproject.org). Solo titular y metadatos."


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path) -> int | None:
    suffix = path.suffix
    if suffix == ".parquet":
        return len(pd.read_parquet(path))
    if suffix == ".csv":
        return len(pd.read_csv(path))
    if suffix == ".geojson":
        return len(json.loads(path.read_text(encoding="utf-8"))["features"])
    if suffix == ".npy":
        return int(np.load(path, mmap_mode="r").shape[0])
    if path.name == "embeddings_ids.json":
        return len(json.loads(path.read_text(encoding="utf-8")))
    return None


def _null_values(path: Path) -> int | None:
    return int(pd.read_csv(path)["valor"].isna().sum()) if path.exists() else None


def quality_counts(text: str) -> dict:
    """Numbers of the news section of calidad.md; null when the report lacks one."""
    def grab(label: str) -> int | None:
        match = re.search(re.escape(label) + r"[^:]*:\s*(\d+)", text)
        return int(match.group(1)) if match else None
    return {"filas_leidas": grab("Filas leídas"), "repetidas_entre_fuentes": grab("Repetidas entre fuentes"),
            "filas_separadas": grab("Filas separadas"), "generado": (re.search(r"Generado: (\S+)", text) or [None, None])[1]}


def _news_entry(path: Path, quality: dict) -> dict:
    news = pd.read_parquet(path)
    by_origin = news["origen"].value_counts().to_dict()
    return {
        "descripcion": "Noticias del período con tema, procedencia y evento (contrato noticias.parquet).",
        "por_origen": {k: int(v) for k, v in by_origin.items()},
        "periodo_UTC": [WINDOW_START.isoformat(), (WINDOW_END - pd.Timedelta(seconds=1)).isoformat()],
        "consultas": [
            {"fuente": "tvn_rss", "url": tvn_rss.FEED_URL},
            {"fuente": "tvn_web", "url": tvn_web.SITEMAP_URL.format(key="<YYYY>_<MM>"),
             "regla": f"hasta {tvn_web.PER_MONTH} artículos por mes, orden SHA-1 de la URL; solo JSON-LD NewsArticle; "
                      f"respeta robots.txt (excluye {', '.join(tvn_web.DISALLOWED)})"},
            *[{"fuente": "gdelt", "url": gdelt.API_URL, "query": q, "tema_consulta": key,
               "parametros": {"mode": "ArtList", "format": "json", "maxrecords": gdelt.MAX_RECORDS, "sort": "DateDesc"},
               "ventanas": "un mes calendario por consulta"} for key, q in gdelt.QUERIES.items()],
        ],
        "licencia": {"tvn_rss": TVN_LICENSE, "tvn_web": TVN_LICENSE, "gdelt": GDELT_LICENSE},
        "filas_excluidas": {
            "fuera_del_periodo_o_sin_fecha": "se descartan en la ingesta (sin fecha no se puede probar que esté en el período)",
            "repetidas_entre_fuentes": quality["repetidas_entre_fuentes"],
            "repetidas_motivo": "misma URL normalizada en dos fuentes: se conserva la fila de TVN (trae descripción)",
            "separadas_por_validacion": quality["filas_separadas"],
            "separadas_motivo": "fecha inválida, URL rota o campo obligatorio vacío (B-05, outputs/reports/calidad.md)",
        },
        "transformaciones": [
            "id_noticia = 'N-' + 10 primeros hex del SHA-1 de la URL normalizada",
            "fechas a UTC; fecha_publicacion = la del medio; fecha_deteccion = seendate de GDELT (en TVN, solo si GDELT vio la misma URL: ADR-032); nunca se mezclan",
            "HTML y entidades quitados de titulo y descripcion",
            f"tema por similitud con {embed.MODEL_NAME}; bajo {classify.THRESHOLD} -> 'otro' (B-07)",
            f"procedencia_id: agencia > casi copia (TF-IDF >= {provenance.NEAR_DUPLICATE}, 48 h, otro dominio) > medio (B-06)",
            f"cluster_id: enlace completo, distancia coseno <= {cluster.DISTANCE_THRESHOLD}, ventana 72 h (B-08)",
        ],
    }


def entries(quality: dict) -> dict[str, dict]:
    """Per-file metadata other than hash, size and rows."""
    model = json.loads((PROCESSED / "embeddings_modelo.json").read_text(encoding="utf-8")) \
        if (PROCESSED / "embeddings_modelo.json").exists() else {}
    derived = "Derivado de noticias.parquet (sin consultas propias)."
    return {
        "data/processed/noticias.parquet": _news_entry(PROCESSED / "noticias.parquet", quality),
        "data/processed/noticias.csv": {
            "descripcion": "Entregable del reto (secc. 6–7): las mismas filas y columnas de noticias.parquet en CSV UTF-8 (B-13).",
            "consultas": "Las de noticias.parquet.", "licencia": "La de cada noticia (ver fuentes.json).",
            "transformaciones": ["fechas como texto ISO 8601 UTC (Z)", "nulos como celda vacía, nunca 0", "fin de línea LF"]},
        "data/processed/fuentes.json": {
            "descripcion": "Entregable del reto (secc. 6): consultas usadas y cada medio con origen, cantidad, fechas y condiciones de uso (B-13).",
            "consultas": "Las de noticias.parquet.", "licencia": "Condiciones por medio dentro del archivo.",
            "transformaciones": ["un registro por (origen, dominio)"]},
        "data/processed/clusters.parquet": {
            "descripcion": "Un evento por fila: noticias, registros, procedencias independientes, tema y fechas (B-08).",
            "consultas": derived, "licencia": "La de cada noticia (ver noticias.parquet).",
            "transformaciones": ["agrupa por cluster_id", "n_procedencias_independientes = procedencia_id únicos",
                                 "tema = el más frecuente (empate: orden alfabético)",
                                 "fecha_primera/ultima = fecha del medio o, si no hay, de detección"]},
        "data/processed/baseline.parquet": {
            "descripcion": "Tema, procedencia y cluster sin embeddings (palabras clave + TF-IDF), para comparar (B-09).",
            "consultas": derived, "licencia": "La de cada noticia (ver noticias.parquet).",
            "transformaciones": ["tema por palabras clave", "duplicados: TF-IDF >= 0.9 en 72 h"]},
        "data/processed/embeddings.npy": {
            "descripcion": "Vector normalizado por noticia, en el orden de embeddings_ids.json (B-07).",
            "consultas": derived, "licencia": "La de cada noticia; modelo bajo Apache 2.0.",
            "modelo": model.get("modelo"), "revision_modelo": model.get("revision"),
            "transformaciones": ["texto = titulo + descripcion (si existe)"]},
        "data/processed/embeddings_ids.json": {"descripcion": "id_noticia de cada fila de embeddings.npy.",
                                               "consultas": derived, "licencia": "—"},
        "data/processed/embeddings_modelo.json": {"descripcion": "Modelo y revisión usados para los embeddings.",
                                                  "consultas": derived, "licencia": "—"},
        "data/processed/contexto.parquet": {
            "descripcion": "Eventos relacionados con un indicador del Banco Mundial o un sismo del USGS por una regla escrita; sin relación sustentada, sin fila (B-14).",
            "consultas": "Derivado de noticias.parquet, indicadores.csv y eventos.geojson.",
            "licencia": "Banco Mundial CC BY 4.0; USGS dominio público.",
            "transformaciones": ["regla en src/context.py: tema + menciona Panamá + menciona lo que mide el indicador",
                                 "valor citado: último año con dato de Panamá (nunca nulo)",
                                 "sismo solo si está a 72 h o menos del evento (catálogo 2024 vs noticias 2025-2026: 0 filas)"]},
        "data/processed/indicadores.csv": {
            "descripcion": "Banco Mundial: cuadrícula país x indicador x año con nulos explícitos (B-03).",
            "consultas": [{"indicador": i, "url": worldbank.query_url(i), "unidad": u} for i, u in worldbank.INDICATORS.items()],
            "licencia": worldbank.LICENSE,
            "filas_excluidas": "ninguna: 6 países x 6 indicadores x 15 años = 540; valor nulo donde falta (nunca 0)",
            "valores_nulos": _null_values(PROCESSED / "indicadores.csv"),
            "transformaciones": ["una fila por combinación", "unidad por indicador"]},
        "data/processed/eventos.geojson": {
            "descripcion": "USGS: sismos M>=3 de 2024 en la caja lat 5–12, lon −86 a −76 (B-04).",
            "consultas": [{"url": usgs.query_url()}],
            "licencia": usgs.LICENSE,
            "filas_excluidas": "ninguna: todos los sismos que devuelve la consulta",
            "transformaciones": ["propiedades del contrato; time y updated a ISO 8601 UTC"],
            "advertencia": "La caja regional no es el territorio de Panamá; solo hechos sísmicos."},
    }


def build_manifest() -> dict:
    quality = quality_counts(QUALITY_PATH.read_text(encoding="utf-8")) if QUALITY_PATH.exists() else quality_counts("")
    files = []
    for rel, meta in entries(quality).items():
        path = ROOT / rel
        if not path.exists():
            continue
        files.append({"ruta": rel, "sha256": sha256(path), "bytes": path.stat().st_size, "filas": _rows(path), **meta})
    news = pd.read_parquet(PROCESSED / "noticias.parquet")
    cutoff = news["fecha_extraccion"].max()
    return {
        "version": VERSION,
        "generado_UTC": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fecha_corte_UTC": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ") if pd.notna(cutoff) else None,
        "fecha_corte_nota": "última fecha_extraccion del corpus de noticias; nada posterior se pidió a las fuentes",
        "reporte_calidad": {"ruta": "outputs/reports/calidad.md", **quality},
        "reproducir": ["make data (necesita internet)", "make news", "make nlp", "python -m src.manifest"],
        "archivos": files,
    }


def write(manifest: dict, path: Path = MANIFEST_PATH) -> None:
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")


def verify(path: Path = MANIFEST_PATH) -> list[str]:
    """Problems found: a missing file or a hash that does not match. Empty = all good."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    for entry in manifest["archivos"]:
        file = ROOT / entry["ruta"]
        if not file.exists():
            problems.append(f"{entry['ruta']}: missing")
        elif sha256(file) != entry["sha256"]:
            problems.append(f"{entry['ruta']}: SHA-256 differs from the manifest")
    return problems


def main() -> None:
    if "--verify" in sys.argv:
        problems = verify()
        for p in problems:
            print(p)
        print("Manifest OK" if not problems else f"{len(problems)} problem(s)")
        sys.exit(1 if problems else 0)
    manifest = build_manifest()
    write(manifest)
    print(f"Wrote {MANIFEST_PATH.relative_to(ROOT)} with {len(manifest['archivos'])} files")


if __name__ == "__main__":
    main()
