"""T06 · Unanswerable query. Owner: José (J-10).

Prepared input: Question about a figure that is not in the corpus.
Expected result: Explicit abstention, no invented figure or citation.
Source: section 9 of docs/reto.pdf.

Three ways the answer can go wrong are covered: nothing retrieved (abstain in code,
no model call), the model invents a figure behind a real citation (dropped), and the
model abstains on its own (kept, with its reason).
"""

import json

import pandas as pd

from src.generate.query import NO_EVIDENCE, answer_question
from src.generate.schema import evidence_from_indicator

QUESTION = "¿Cuál fue la inflación de Panamá en septiembre de 2026?"
# Synthetic World Bank cell (sintético): annual 2024 value, the corpus has nothing monthly for 2026.
CELL = evidence_from_indicator(pd.Series({"pais_iso3": "PAN", "indicador_id": "FP.CPI.TOTL.ZG", "anio": 2024,
                                          "valor": 0.69, "unidad": "% anual"}))


class Scripted:
    def __init__(self, answer: dict):
        self.answer, self.calls = answer, 0

    def complete(self, messages, model, temperature):
        self.calls += 1
        assert QUESTION in messages[1]["content"]
        return json.dumps(self.answer, ensure_ascii=False), {}


class NoNetwork:
    def complete(self, *args, **kwargs):
        raise AssertionError("no evidence: the model must not be called")


def test_t06(tmp_path):
    """Nothing retrieved: explicit abstention in code, the model is never asked."""
    result = answer_question(QUESTION, [], client=NoNetwork(), offline=False, cache_dir=tmp_path)
    assert result.output.abstencion and result.output.motivo_abstencion == NO_EVIDENCE
    assert result.output.afirmaciones == [] and result.output.borrador is None


def test_t06_invented_figure_behind_real_citation(tmp_path):
    model = Scripted({"abstencion": False, "afirmaciones": [
        {"texto": "La inflación de Panamá en septiembre de 2026 fue 2,1 %.", "tipo": "hecho",
         "citas": [{"id_fuente": CELL.id, "campo": "valor", "pasaje": "0.69"}]}],
        "borrador": "La inflación fue 2,1 % en septiembre de 2026."})
    result = answer_question(QUESTION, [CELL], client=model, offline=False, cache_dir=tmp_path)
    assert model.calls == 1
    assert result.output.abstencion and result.output.afirmaciones == []
    assert "2,1" not in json.dumps(result.output.model_dump(), ensure_ascii=False)


def test_t06_model_abstains(tmp_path):
    model = Scripted({"abstencion": True,
                      "motivo_abstencion": "Solo hay datos anuales del Banco Mundial hasta 2024; no hay cifra mensual de 2026."})
    result = answer_question(QUESTION, [CELL], client=model, offline=False, cache_dir=tmp_path)
    assert result.output.abstencion and "2024" in result.output.motivo_abstencion


def test_t06_figure_check_alone_catches_it(tmp_path):
    # Country, year and unit are right; only the figure is invented (0.69 in the source).
    model = Scripted({"abstencion": False, "afirmaciones": [
        {"texto": "Según el Banco Mundial, la inflación de Panamá fue 2,1 % anual en 2024.", "tipo": "hecho",
         "citas": [{"id_fuente": CELL.id, "campo": "valor", "pasaje": "0.69"}]}],
        "borrador": "Dato anual."})
    result = answer_question(QUESTION, [CELL], client=model, offline=False, cache_dir=tmp_path)
    assert result.output.abstencion
    assert any("cifra sin respaldo" in d.reason for d in result.report.dropped_claims)


def test_t06_invented_figure_only_in_draft(tmp_path):
    model = Scripted({"abstencion": False, "afirmaciones": [
        {"texto": "Según el Banco Mundial, la inflación de Panamá fue 0,69 % anual en 2024.", "tipo": "hecho",
         "citas": [{"id_fuente": CELL.id, "campo": "valor", "pasaje": "0.69"}]}],
        "borrador": "En 2024 fue 0,69 % anual; en septiembre de 2026 rondaría el 1,5 %."})
    result = answer_question(QUESTION, [CELL], client=model, offline=False, cache_dir=tmp_path)
    assert len(result.output.afirmaciones) == 1  # the supported claim stays
    assert result.output.borrador is None
    assert any("cifras sin respaldo" in v and "1,5" in v for v in result.report.violations)
