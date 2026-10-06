"""Figures in text vs. evidence (J-10). Owner: José."""

import pytest

from src.generate.figures import extract, find_conflicts, unsupported_figures
from src.generate.schema import Evidence

SOURCE = ["7.16634016390665", "2023", "4515577", "2026-10-05T14:10:00Z", "magnitud 5,1"]


@pytest.mark.parametrize("text", [
    "El PIB creció 7,2 % en 2023", "creció 7.16 %", "creció 7,1 %", "creció 7 %",
    "4,5 millones de habitantes", "5 millones de habitantes", "el 5 de octubre de 2026", "sismo de magnitud 5,1",
    "sin cifras",
])
def test_supported(text):
    assert unsupported_figures(text, SOURCE) == []


@pytest.mark.parametrize("text, missing", [
    ("creció 8 %", ["8"]), ("creció 7,3 %", ["7,3"]), ("en 2024", ["2024"]),
    ("6 millones de habitantes", ["6"]), ("magnitud 6,2", ["6,2"]),
])
def test_unsupported(text, missing):
    assert unsupported_figures(text, SOURCE) == missing


def test_number_notations():
    readings = {f.raw: sorted(f.values) for f in extract("1.350 buques, 7,2 %, 1.234,5 dólares, 4,515,577")}
    assert readings["1.350"] == [(1.35, 3), (1350.0, 0)]  # ambiguous: both readings are tried
    assert readings["7,2"] == [(7.2, 1)]
    assert readings["1.234,5"] == [(1234.5, 1)]
    assert readings["4,515,577"] == [(4515577.0, 0)]
    assert extract("caso N-1a2b3c y ID N-0000000001") == []  # IDs glued to letters are not figures


def news(id_, title):
    return Evidence(id=id_, kind="noticia", fields={"titulo": title}, scope="titular/metadatos")


def test_conflicts_need_same_unit_and_different_value():
    a = news("N-a", "Canal fija calado máximo de 44 pies")
    b = news("N-b", "Calado limitado a 47 pies por la sequía")
    c = news("N-c", "Calado de 44 pies desde el lunes; 30 buques en espera")
    conflicts = find_conflicts([a, b, c])
    assert {(x.id_a, x.id_b, x.unit) for x in conflicts} == {("N-a", "N-b", "pies"), ("N-b", "N-c", "pies")}


def test_same_value_in_other_notation_is_not_a_conflict():
    assert find_conflicts([news("N-a", "1.350 buques"), news("N-b", "1350 buques")]) == []
    assert find_conflicts([news("N-a", "sismo de magnitud 5,1"), news("N-b", "magnitud 5.1")]) == []
    assert len(find_conflicts([news("N-a", "sismo de magnitud 5,1"), news("N-b", "sismo de magnitud 5,6")])) == 1
