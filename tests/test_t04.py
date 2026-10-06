"""T04 · Annual World Bank figure. Owner: José (J-08).

Prepared input: Brief about GDP growth.
Expected result: Country, year and unit are cited; never phrased as "today".
Source: section 9 of docs/reto.pdf.

Checked at the guard, which runs on every model answer before it is shown: whatever
the model writes, a World Bank claim without country, year or unit, or written as
"today", never reaches the editor. The live run with the real model is part of C-08.
"""

import pandas as pd
import pytest

from src.generate.guard import guard
from src.generate.schema import evidence_from_indicator

# Synthetic World Bank cell (sintético): only the shape matters.
ROW = pd.Series({"pais_iso3": "PAN", "indicador_id": "NY.GDP.MKTP.KD.ZG", "anio": 2023, "valor": 7.3,
                 "unidad": "% anual", "fuente_url": "https://example.invalid", "licencia": "CC BY 4.0"})


@pytest.mark.parametrize("text, kept", [
    ("Según el Banco Mundial, el PIB de Panamá creció 7.3 % anual en 2023.", True),
    ("Según el Banco Mundial, el PIB de PAN creció 7.3 por ciento en 2023.", True),
    ("El PIB creció 7.3 % anual en 2023.", False),                    # no country
    ("El PIB de Panamá creció 7.3 en 2023.", False),                  # no unit
    ("El PIB de Panamá crece 7.3 % anual.", False),                   # no year
    ("En 2023 el PIB de Panamá creció 7.3 % y hoy sigue igual.", False),  # "today"
])
def test_t04(text, kept):
    """Country, year and unit are cited; never phrased as "today"."""
    indicator = evidence_from_indicator(ROW)
    raw = {"abstencion": False, "afirmaciones": [
        {"texto": text, "tipo": "hecho", "citas": [{"id_fuente": indicator.id, "campo": "valor", "pasaje": "7.3"}]}],
        "preguntas_investigacion": ["¿a?", "¿b?", "¿c?"], "borrador": "Borrador."}
    result = guard(raw, [indicator], "brief")
    assert (len(result.output.afirmaciones) == 1) is kept
    if not kept:
        assert result.output.abstencion  # nothing else to say: abstain, never a bare figure
