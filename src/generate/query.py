"""Answer an editor's question from retrieved evidence (J-10, CU-04). Owner: José.

`answer_question` is the "consulta en español" path: the caller passes the evidence
found for the question (J-06 search once it exists; any list of Evidence until then).
With no evidence there is nothing to cite, so it abstains in code without calling the
model (T06). Otherwise the answer goes through generate_draft and the guard like any
draft: cited claims only, no invented figure, contradictions shown, never "today".
"""

from pathlib import Path

from src.generate.generate import CACHE_DIR, DraftRequest, DraftResult, LLMClient, cache_key, generate_draft
from src.generate.guard import GuardReport
from src.generate.schema import Evidence, SalidaLLM

NO_EVIDENCE = "No hay evidencia en el corpus para esta consulta; no se responde con datos no verificados."


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
        return DraftResult(output, GuardReport(), "sin_evidencia", cache_key([], "none"))
    return generate_draft(request, client=client, offline=offline, cache_dir=cache_dir)
