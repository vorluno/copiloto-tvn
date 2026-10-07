"""Schemas for LLM drafting (J-07). Owner: José.

- `SalidaLLM`: the JSON the model must return (docs/jose.md, "Esquema JSON"), validated
  with Pydantic. Field names are Spanish because they are part of the data contract.
  One change from jose.md: `cita_a` / `cita_b` in contradictions are full citations
  (id_fuente + campo + pasaje) instead of free text, so the guard can verify them.
- `Evidence`: one source item exactly as it is sent to the model inside a <fuente> tag.
  The guard only accepts citations to these items and fields.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

ClaimType = Literal["hecho", "declaracion", "inferencia", "hipotesis"]
Task = Literal["brief", "guion", "copy", "respuesta"]
EvidenceKind = Literal["noticia", "indicador", "sismo"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Cita(_Strict):
    id_fuente: str = Field(min_length=1)
    campo: str = Field(min_length=1)
    pasaje: str = Field(min_length=1)


class Afirmacion(_Strict):
    texto: str = Field(min_length=1)
    tipo: ClaimType
    citas: list[Cita] = Field(default_factory=list)


class Contradiccion(_Strict):
    version_a: str
    cita_a: Cita
    version_b: str
    cita_b: Cita


class SalidaLLM(_Strict):
    abstencion: bool
    motivo_abstencion: str | None = None
    titulo: str | None = None
    enfoque_interes_publico: str | None = None
    afirmaciones: list[Afirmacion] = Field(default_factory=list)
    contradicciones: list[Contradiccion] = Field(default_factory=list)
    preguntas_investigacion: list[str] = Field(default_factory=list)
    verificaciones_pendientes: list[str] = Field(default_factory=list)
    borrador: str | None = None
    alertas: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class Evidence:
    """A citable source item: its ID, kind, text scope and the fields sent to the model."""

    id: str
    kind: EvidenceKind
    fields: dict[str, str]
    scope: str | None = None  # alcance_texto for news; None for official data
    year: int | None = None  # reference year for World Bank indicators
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def headline_only(self) -> bool:
        return self.kind == "noticia" and self.scope == "titular/metadatos"


def _iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).tz_convert("UTC").isoformat().replace("+00:00", "Z")


def evidence_from_news(row: pd.Series) -> Evidence:
    """News item from noticias.parquet. Null fields are not sent, so they cannot be cited."""
    fields = {name: row[name] for name in ("titulo", "medio", "descripcion") if name in row and pd.notna(row[name])}
    if (published := _iso(row.get("fecha_publicacion"))) is not None:
        fields["fecha_publicacion"] = published
    return Evidence(id=row["id_noticia"], kind="noticia", fields=fields, scope=row["alcance_texto"])


def evidence_from_indicator(row: pd.Series) -> Evidence | None:
    """World Bank cell from indicadores.csv. A null value is not evidence: returns None."""
    if pd.isna(row["valor"]):
        return None
    year = int(row["anio"])
    return Evidence(
        id=f"WB-{row['pais_iso3']}-{row['indicador_id']}-{year}",
        kind="indicador",
        fields={
            "valor": f"{row['valor']}",
            "unidad": row["unidad"],
            "pais_iso3": row["pais_iso3"],
            "indicador_id": row["indicador_id"],
            "anio": str(year),
        },
        year=year,
        meta={"fuente_url": row.get("fuente_url"), "licencia": row.get("licencia")},
    )


def evidence_from_quake(feature: dict) -> Evidence:
    """USGS event from eventos.geojson (a GeoJSON Feature). Only seismic facts are sent."""
    props = feature.get("properties", {})
    coords = (feature.get("geometry") or {}).get("coordinates") or [None, None, None]
    fields = {"place": props.get("place"), "magnitude": props.get("mag", props.get("magnitude"))}
    depth = props.get("depth")
    raw_time = props.get("time")
    if raw_time is not None:  # raw USGS gives epoch ms; a normalized file may give ISO text
        ts = pd.Timestamp(raw_time, unit="ms", tz="UTC") if isinstance(raw_time, (int, float)) else pd.Timestamp(raw_time)
        fields["time"] = _iso(ts if ts.tzinfo else ts.tz_localize("UTC"))
    if depth is None and len(coords) > 2:
        depth = coords[2]
    if depth is not None:
        fields["depth_km"] = depth
    event_id = feature.get("id") or props.get("id")  # raw USGS: top level; eventos.geojson: properties
    if not event_id:
        raise ValueError("USGS feature without id")
    return Evidence(
        id=str(event_id),
        kind="sismo",
        fields={k: str(v) for k, v in fields.items() if v is not None},
        meta={"url": props.get("url"), "status": props.get("status")},
    )
