"""Answer an editor's question from retrieved evidence (J-10, CU-04). Owner: José.

`answer_question` is the "consulta en español" path: the caller passes the evidence
found for the question (J-06 search once it exists; any list of Evidence until then).
With no evidence there is nothing to cite, so it abstains in code without calling the
model (T06). Otherwise the answer goes through generate_draft and the guard like any
draft: cited claims only, no invented figure, contradictions shown, never "today".
"""

from pathlib import Path

from src.generate.generate import CACHE_DIR, DraftRequest, DraftResult, LLMClient, cache_key, generate_draft
from src.generate.guard import GuardReport, injection_in
from src.generate.schema import Evidence, SalidaLLM

NO_EVIDENCE = "No hay evidencia en el corpus para esta consulta; no se responde con datos no verificados."
QUERY_INJECTION = "posible instrucción inyectada en la consulta: se trata como dato y no se obedece"


def _flag_query_injection(result: DraftResult, question: str) -> DraftResult:
    """T07 for the question itself. The model may answer the legitimate part and silently skip
    the injected order (seen with Gemini on 7 oct, 5 of 6 adversarial queries without an alert);
    the alert is added in code, after the cache, so it never depends on the model."""
    if not injection_in(question) or QUERY_INJECTION in result.output.alertas:
        return result
    result.output = result.output.model_copy(update={"alertas": [*result.output.alertas, QUERY_INJECTION]})
    result.report.fixes.append(f"alerta agregada en código: {QUERY_INJECTION}")
    return result


def answer_question(
    question: str,
    evidence: list[Evidence],
    client: LLMClient | None = None,
    offline: bool | None = None,
    cache_dir: Path = CACHE_DIR,
) -> DraftResult:
    request = DraftRequest(task="respuesta", topic=question.strip(), evidence=evidence)
    if not evidence:
        output = SalidaLLM(abstencion=True, motivo_abstencion=NO_EVIDENCE,
                           verificaciones_pendientes=["Buscar la cifra en una fuente oficial o primaria."])
        return _flag_query_injection(DraftResult(output, GuardReport(), "sin_evidencia", cache_key([], "none")), question)
    return _flag_query_injection(generate_draft(request, client=client, offline=offline, cache_dir=cache_dir), question)
