"""T05 · Two incompatible claims. Owner: José (J-10).

Prepared input: 2 news items with different figures (synthetic).
Expected result: Shows both versions with their sources and "verificación pendiente";
does not pick one arbitrarily.
Source: section 9 of docs/reto.pdf.

Checked at the guard, so it holds whatever the model does: the contradiction and the
pending verification are added in code if the model misses them, and a claim that takes
one side as fact is downgraded to an attributed statement.
"""

from src.generate.guard import guard
from src.generate.schema import Evidence

# Synthetic sources (sintético): same event, different figures.
A = Evidence(id="N-t05aaaaaaa", kind="noticia", scope="titular/metadatos",
             fields={"titulo": "Canal fija calado máximo de 44 pies por la sequía", "medio": "Diario A (sintético)"})
B = Evidence(id="N-t05bbbbbbb", kind="noticia", scope="titular/metadatos",
             fields={"titulo": "ACP limita el calado a 47 pies desde el lunes", "medio": "Portal B (sintético)"})


def answer(**extra):
    return {"abstencion": False, "titulo": "Calado en el Canal",
            "afirmaciones": [{"texto": "El calado máximo es de 44 pies.", "tipo": "hecho",
                              "citas": [{"id_fuente": A.id, "campo": "titulo", "pasaje": "44 pies"}]}],
            "preguntas_investigacion": ["¿a?", "¿b?", "¿c?"],
            "borrador": "Basado únicamente en titular/metadatos. El calado máximo es de 44 pies.", **extra}


def test_t05():
    """Model picks one figure and ignores the other: both are shown with a pending verification."""
    out = guard(answer(), [A, B], "brief").output
    assert len(out.contradicciones) == 1
    pair = {out.contradicciones[0].cita_a.id_fuente, out.contradicciones[0].cita_b.id_fuente}
    assert pair == {A.id, B.id}
    assert {out.contradicciones[0].cita_a.pasaje, out.contradicciones[0].cita_b.pasaje} == {"44", "47"}
    assert any("Verificación pendiente" in v and "44" in v and "47" in v for v in out.verificaciones_pendientes)
    assert out.afirmaciones[0].tipo == "declaracion"  # not stated as fact while sources disagree


def test_t05_model_already_reports_it():
    contradiction = {"version_a": "44 pies", "cita_a": {"id_fuente": A.id, "campo": "titulo", "pasaje": "44 pies"},
                     "version_b": "47 pies", "cita_b": {"id_fuente": B.id, "campo": "titulo", "pasaje": "47 pies"}}
    out = guard(answer(contradicciones=[contradiction]), [A, B], "brief").output
    assert len(out.contradicciones) == 1  # not duplicated


def test_t05_also_on_abstention():
    out = guard({"abstencion": True, "motivo_abstencion": "Fuentes en desacuerdo."}, [A, B], "brief").output
    assert out.abstencion and any("Verificación pendiente" in v for v in out.verificaciones_pendientes)
