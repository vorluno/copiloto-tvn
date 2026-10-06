"""Editorial package per cluster (J-08). Owner: José.

A scripted fake model answers per task (read from the prompt). It can fail on purpose on
the first attempt, to check the retry, and it records every call, to check what is sent
and that offline mode never calls it.
"""

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from src.generate.drafts import build_package, cluster_evidence, official_index
from src.generate.guard import ONLY_HEADLINE, WORD_LIMITS, word_count
from src.score import score_clusters

STUB_PATH = Path(__file__).resolve().parents[1] / "data" / "stub" / "noticias_stub.parquet"
NOW = pd.Timestamp("2026-10-06T18:00:00Z")
WB_ID = "WB-PAN-NY.GDP.MKTP.KD.ZG-2023"


@pytest.fixture(scope="module")
def news() -> pd.DataFrame:
    return pd.read_parquet(STUB_PATH)


@pytest.fixture(scope="module")
def indicadores() -> pd.DataFrame:
    # Synthetic World Bank cells (sintético): one with value, one null.
    return pd.DataFrame([
        {"pais_iso3": "PAN", "indicador_id": "NY.GDP.MKTP.KD.ZG", "anio": 2023, "valor": 7.3,
         "unidad": "% anual", "fuente_url": "https://example.invalid", "fecha_extraccion": "2026-10-06T12:00:00Z",
         "licencia": "CC BY 4.0"},
        {"pais_iso3": "PAN", "indicador_id": "FP.CPI.TOTL.ZG", "anio": 2024, "valor": None,
         "unidad": "% anual", "fuente_url": "https://example.invalid", "fecha_extraccion": "2026-10-06T12:00:00Z",
         "licencia": "CC BY 4.0"},
    ])


@pytest.fixture(scope="module")
def contexto() -> pd.DataFrame:
    return pd.DataFrame([
        {"cluster_id": "C-STUB-01", "id_evidencia": WB_ID, "tipo": "indicador", "regla": "ejemplo", "nota": "sintético"},
        {"cluster_id": "C-STUB-01", "id_evidencia": "WB-PAN-FP.CPI.TOTL.ZG-2024", "tipo": "indicador",
         "regla": "ejemplo", "nota": "valor nulo: no es evidencia"},
    ])


def words(n: int) -> str:
    return " ".join(["palabra"] * n)


class ScriptedModel:
    """Answers per task from the prompt; `bad_first` tasks fail once before the feedback arrives."""

    def __init__(self, news: pd.DataFrame, bad_first: set[str] = frozenset(), abstain: bool = False):
        self.tvn = news[(news["cluster_id"] == "C-STUB-01") & (news["origen"] == "tvn_rss")].iloc[0]
        self.bad_first, self.abstain = set(bad_first), abstain
        self.calls: list[tuple[str, bool]] = []

    def complete(self, messages, model, temperature):
        user = messages[1]["content"]
        task = re.search(r"^Tarea: (\w+)", user, re.M).group(1)
        retry = "rechazada por el validador" in user
        self.calls.append((task, retry))
        if self.abstain:
            return json.dumps({"abstencion": True, "motivo_abstencion": "La evidencia no alcanza."}), {}
        claims = [{"texto": "TVN reporta un límite de calado en el Canal.", "tipo": "hecho",
                   "citas": [{"id_fuente": self.tvn["id_noticia"], "campo": "titulo", "pasaje": "límite de calado"}]}]
        if WB_ID in user:
            claims.append({"texto": "Según el Banco Mundial, el PIB de Panamá creció 7.3 % anual en 2023.",
                           "tipo": "hecho", "citas": [{"id_fuente": WB_ID, "campo": "valor", "pasaje": "7.3"}]})
        size = {"brief": 120, "guion": 130, "copy": 40}[task]
        if task in self.bad_first and not retry:
            size = {"brief": 300, "guion": 60, "copy": 120}[task]
        answer = {
            "abstencion": False, "titulo": "Calado en el Canal", "enfoque_interes_publico": "Tránsito por el Canal.",
            "afirmaciones": claims,
            "preguntas_investigacion": ["¿Desde cuándo?", "¿Qué buques?", "¿Qué dato oficial?"] if task == "brief" else [],
            "verificaciones_pendientes": ["Falta comunicado oficial."],
            "borrador": f"{ONLY_HEADLINE} {words(size - word_count(ONLY_HEADLINE))}",
        }
        return json.dumps(answer, ensure_ascii=False), {"prompt_tokens": 10, "completion_tokens": 5}


class NoNetwork:
    def complete(self, *args, **kwargs):
        raise AssertionError("offline mode must not call the LLM")


@pytest.fixture(scope="module")
def scored(news):
    return score_clusters(news, now=NOW)


def test_package_has_three_drafts_within_limits(news, scored, tmp_path):
    model = ScriptedModel(news)
    package = build_package("C-STUB-01", news, scored, client=model, offline=False, cache_dir=tmp_path)
    assert [t for t, _ in model.calls] == ["brief", "guion", "copy"]
    assert package.score["version_reglas"] == "scoring_v1" and package.evidence_state == "parcial"
    for task, draft in package.drafts.items():
        out = draft.result.output
        assert draft.result.report.ok, (task, draft.result.report)
        low, high = WORD_LIMITS[task]
        assert low <= word_count(out.borrador) <= high
        assert all(claim.citas for claim in out.afirmaciones)
    assert len(package.drafts["brief"].result.output.preguntas_investigacion) == 3


def test_rejected_draft_is_retried_with_feedback(news, scored, tmp_path):
    model = ScriptedModel(news, bad_first={"guion"})
    package = build_package("C-STUB-01", news, scored, client=model, offline=False, cache_dir=tmp_path)
    assert model.calls.count(("guion", False)) == 1 and model.calls.count(("guion", True)) == 1
    assert package.drafts["guion"].attempts == 2
    assert package.drafts["guion"].result.report.ok


def test_brief_abstention_skips_other_tasks(news, scored, tmp_path):
    model = ScriptedModel(news, abstain=True)
    package = build_package("C-STUB-01", news, scored, client=model, offline=False, cache_dir=tmp_path)
    assert model.calls == [("brief", False)]
    assert package.abstained
    assert package.drafts["guion"].skipped and package.drafts["copy"].skipped


def test_offline_replays_the_whole_package_from_cache(news, scored, tmp_path):
    model = ScriptedModel(news, bad_first={"brief"})
    online = build_package("C-STUB-01", news, scored, client=model, offline=False, cache_dir=tmp_path)
    offline = build_package("C-STUB-01", news, scored, client=NoNetwork(), offline=True, cache_dir=tmp_path)
    for task in ("brief", "guion", "copy"):
        assert offline.drafts[task].result.source == "cache"
        assert offline.drafts[task].result.output == online.drafts[task].result.output


def test_official_evidence_comes_only_from_contexto(news, scored, indicadores, contexto, tmp_path):
    official = official_index(indicadores)
    assert WB_ID in official and "WB-PAN-FP.CPI.TOTL.ZG-2024" not in official  # null value is not evidence
    evidence, missing = cluster_evidence("C-STUB-01", news, contexto, official)
    assert [e.id for e in evidence if e.kind == "indicador"] == [WB_ID]
    assert missing == ["WB-PAN-FP.CPI.TOTL.ZG-2024"]

    model = ScriptedModel(news)
    package = build_package("C-STUB-01", news, score_clusters(news, contexto=contexto, now=NOW), contexto=contexto,
                            official=official, client=model, offline=False, cache_dir=tmp_path)
    brief = package.drafts["brief"].result.output
    assert any(c.id_fuente == WB_ID for claim in brief.afirmaciones for c in claim.citas)
    assert package.evidence_state == "suficiente para el borrador"


def test_unknown_cluster_fails_loudly(news, scored, tmp_path):
    with pytest.raises(KeyError):
        build_package("C-NO-EXISTE", news, scored, client=NoNetwork(), offline=True, cache_dir=tmp_path)
