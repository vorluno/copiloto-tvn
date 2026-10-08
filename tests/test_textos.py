"""Product words (J-15): every contract value has a name on screen and nothing internal leaks. Owner: Cristian."""

import pandas as pd

from app import textos as tx
from app.bandeja import EVIDENCE_STATES, SCORE_RANGES
from app.borrador import WORD_LIMITS
from app.ficha import WEIGHTS


def test_every_contract_value_has_a_product_name():
    assert all(state in tx.EVIDENCIA for state in EVIDENCE_STATES)
    assert all(rango in tx.PRIORIDAD for rango in SCORE_RANGES)
    assert set(tx.FORMATO) == set(WORD_LIMITS) and set(tx.COMPONENTE) == set(WEIGHTS)
    assert set(tx.REVISION) == {"nuevo", "en revisión", "requiere evidencia", "aprobado como borrador", "descartado"}


def test_headline_spacing_is_fixed_and_words_untouched():
    assert tx.limpiar_titular("¿ Cómo está el empleo en Panamá ? Presidente afirma") == \
        "¿Cómo está el empleo en Panamá? Presidente afirma"
    assert tx.limpiar_titular("Canal de Panamá : 33 tránsitos , calado") == "Canal de Panamá: 33 tránsitos, calado"
    assert tx.limpiar_titular(None) == "Sin titular"


def test_dates_are_panama_time_day_first_and_nulls_say_so():
    assert tx.fecha(pd.Timestamp("2026-09-30T19:00:00Z")) == "30/09/2026, 2:00 p. m."
    assert tx.fecha("2026-10-08T14:33:00Z") == "08/10/2026, 9:33 a. m."
    assert tx.fecha(pd.NaT) == "sin fecha" and tx.fecha(None) == "sin fecha"


def test_replicas_of_one_source_are_said_as_such():
    assert tx.notas_y_fuentes(7, 7) == "7 notas de 7 fuentes independientes"
    assert tx.notas_y_fuentes(5, 1) == "5 notas, todas de la misma fuente original"
    assert tx.notas_y_fuentes(1, 1) == "1 nota de 1 fuente independiente"


def test_guard_messages_never_reach_the_screen_raw():
    raw = "posible instrucción inyectada en la consulta: se trata como dato y no se obedece"
    assert "inyectada" not in tx.alerta(raw) and "No la seguí" in tx.alerta(raw)
    assert tx.retiro("borrador descartado: puede contener afirmaciones sin sustento").startswith("Quité")
    assert tx.retiro("brief: 2 preguntas, se exigen 3") is None
    assert "corpus" not in tx.motivo("No hay evidencia en el corpus para esta consulta; no se responde con datos no verificados.")
