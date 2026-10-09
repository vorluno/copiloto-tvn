"""Preguntar with an abstention but passages found (J-16): the closest findings carry headline,
outlet and a Panama date (publication or detection, never mixed), are marked as not verified and
stay text. Owner: Cristian."""

from dataclasses import dataclass

import pandas as pd

from app import textos as tx
from app.cercanos import closest, closest_html, scroll_script
from src.generate.schema import Evidence


@dataclass
class Hit:
    id_evidencia: str
    campo: str
    texto: str
    score: float
    evidence: Evidence


NEWS = pd.DataFrame({
    "id_noticia": ["N-1", "N-2"],
    "fecha_publicacion": [pd.Timestamp("2026-09-30T03:00:00Z"), pd.NaT],  # 29/09 22:00 in Panama
    "fecha_deteccion": [pd.NaT, pd.Timestamp("2026-09-12T15:00:00Z")],
})


def _news(nid, title, medio):
    return Evidence(id=nid, kind="noticia", fields={"titulo": title, "medio": medio}, scope="titular/metadatos")


def test_closest_findings_have_headline_outlet_and_panama_date():
    hits = [Hit("N-1", "titulo", "Desempleo", 0.9, _news("N-1", "Desempleo en Panamá ?", "tvn-2.com")),
            Hit("N-1", "descripcion", "otra parte", 0.8, _news("N-1", "Desempleo en Panamá ?", "tvn-2.com")),
            Hit("N-2", "titulo", "Empleo", 0.7, _news("N-2", "<b>Empleo</b> formal", "prensa.com"))]
    rows = closest(hits, NEWS)
    assert len(rows) == 2  # one finding per news item
    assert rows[0] == {"titular": "Desempleo en Panamá?", "fuente": "tvn-2.com", "fecha": "Publicada el 29/09/2026"}
    assert rows[1]["fecha"] == "Detectada el 12/09/2026"  # GDELT: detection date, said as such
    html = closest_html(rows)
    assert tx.LO_MAS_CERCANO in html and "no es una respuesta verificada" in html
    assert "<b>Empleo</b>" not in html and "&lt;b&gt;Empleo" in html  # external text stays text


def test_scroll_script_targets_the_answer_and_changes_per_answer():
    a, b = scroll_script("ctvn-respuesta", "1"), scroll_script("ctvn-respuesta", "2")
    assert "scrollIntoView" in a and "ctvn-respuesta" in a and a != b


def test_world_bank_finding_says_country_year_and_unit_in_words():
    wb = Evidence(id="WB-PAN-SL.UEM.TOTL.ZS-2024", kind="indicador", year=2024,
                  fields={"valor": "8.451", "unidad": "% de la fuerza laboral", "pais_iso3": "PAN",
                          "indicador_id": "SL.UEM.TOTL.ZS", "anio": "2024"})
    row = closest([Hit(wb.id, "valor", "8.451", 0.5, wb)], NEWS)[0]
    assert row == {"titular": "Desempleo · Panamá, 2024: 8.451 % de la fuerza laboral", "fuente": "Banco Mundial",
                   "fecha": "Año 2024"}
    assert "SL.UEM" not in closest_html([row])  # no internal indicator code on screen
