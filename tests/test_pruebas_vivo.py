"""Live challenge check (J-16): the JUnit report is read per challenge test, failures and skips
count as such, a timeout says so, and T02/T03 read their last recorded run. Owner: Cristian."""

import subprocess

from app import pruebas_vivo as pv
from app import textos as tx

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="0" failures="1" skipped="1" tests="5" time="3.2">
<testcase classname="tests.test_t01" name="test_t01" time="0.10" />
<testcase classname="tests.test_t04" name="test_t04[a]" time="0.20" />
<testcase classname="tests.test_t04" name="test_t04[b]" time="0.30"><failure message="boom">trace</failure></testcase>
<testcase classname="tests.test_t10" name="test_t10_app" time="1.50"><skipped message="no app" /></testcase>
<testcase classname="tests.test_t10" name="test_t10" time="0.25" />
<testcase classname="tests.test_t07" name="test_t07" time="0.05"><error message="setup">x</error></testcase>
</testsuite></testsuites>"""


def test_junit_is_grouped_by_challenge_test():
    results = pv.parse_junit(JUNIT)
    assert list(results) == ["T01", "T04", "T07", "T10"]
    assert results["T01"].status == "pasa" and results["T01"].total == 1
    assert results["T04"].status == "falla" and (results["T04"].passed, results["T04"].failed) == (1, 1)
    assert abs(results["T04"].seconds - 0.5) < 1e-9
    assert results["T07"].status == "falla"  # an error in setup is not a pass
    assert results["T10"].status == "pasa" and results["T10"].skipped == 1


def test_a_run_is_ok_only_when_every_live_test_passes():
    results = pv.parse_junit(JUNIT)
    assert not pv.LiveRun(results=results).ok
    all_pass = {t: pv.ChallengeResult(passed=1) for t in pv.LIVE_TESTS}
    assert pv.LiveRun(results=all_pass).ok
    assert not pv.LiveRun(results=all_pass, problem="timeout").ok


def test_live_set_skips_the_model_tests_and_every_test_has_product_words():
    assert set(pv.LIVE_TESTS) == {"T01", "T04", "T05", "T06", "T07", "T08", "T09", "T10"}
    assert set(pv.MODEL_TESTS) == {"T02", "T03"}
    assert set(tx.PRUEBA_RETO) == set(pv.ALL_IDS)
    assert all((pv.ROOT / path).exists() for path in [*pv.LIVE_TESTS.values(), *pv.MODEL_TESTS.values()])
    cmd = pv.command(pv.ROOT / "r.xml")
    assert cmd[1:3] == ["-m", "pytest"] and "no:cacheprovider" in cmd and not any("t02" in c or "t03" in c for c in cmd)


def test_timeout_and_missing_report_are_reported_not_raised(monkeypatch, tmp_path):
    def too_slow(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    monkeypatch.setattr(pv.subprocess, "run", too_slow)
    assert pv.run_live(timeout=1).problem == "timeout"
    monkeypatch.setattr(pv.subprocess, "run", lambda *a, **k: None)  # ran, wrote nothing
    assert pv.run_live(timeout=1).problem == "no_report"


def test_last_recorded_run_is_read_from_the_matrix(tmp_path):
    path = tmp_path / "pruebas.csv"
    path.write_text("ID,Prueba,Observado,Evidencia\n"
                    'T02,Tres registros,"Pasa (3/3): 3 medios","make test sobre main, 2026-10-07 (Windows)"\n'
                    "T03,Recirculada,Sin dato,—\n", encoding="utf-8")
    recorded = pv.last_recorded(path)
    assert recorded["T02"] == {"fecha": "2026-10-07", "estado": "pasa", "pasaron": 3, "de": 3}
    assert recorded["T03"] == {"fecha": None, "estado": None, "pasaron": None, "de": None}
    assert pv.last_recorded(tmp_path / "missing.csv") == {}
    assert {"T02", "T03"} <= set(pv.last_recorded())  # the real matrix has them
