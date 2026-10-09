"""Live challenge check, "Modo jurado" (J-16). Owner: Cristian; built with José.

Runs, on the server and on demand, the challenge tests (T01-T10, section 9 of the brief) that
do not need the embedding model (the production image does not ship it): a pytest subprocess
with a time limit and a JUnit XML report, read back per challenge test. T02 and T03 run the
real clustering with the embedding model, so they are not run here; their last recorded run
is read from docs/notion/pruebas.csv. Pure functions, no Streamlit; nothing is written in the
repo (the report goes to a temporary folder, pytest's cache is off).
"""

import csv
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET  # the report is written locally by pytest, never external input
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRUEBAS_CSV = ROOT / "docs" / "notion" / "pruebas.csv"
TIMEOUT_S = 120  # ~20-35 s normally; up to 75 s seen on a loaded machine

# Challenge test -> its test file. Fast ones run live; the others need the embedding model.
LIVE_TESTS = {f"T{n:02d}": f"tests/test_t{n:02d}.py" for n in (1, 4, 5, 6, 7, 8, 9, 10)}
MODEL_TESTS = {"T02": "tests/test_t02.py", "T03": "tests/test_t03.py"}
ALL_IDS = sorted([*LIVE_TESTS, *MODEL_TESTS])


@dataclass
class ChallengeResult:
    """One challenge test: how many of its checks passed, failed or were skipped, and the time."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    seconds: float = 0.0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped

    @property
    def status(self) -> str:
        if self.failed:
            return "falla"
        if self.passed:
            return "pasa"
        return "omitida" if self.skipped else "sin_correr"


@dataclass
class LiveRun:
    """Outcome of one live run. `problem` is None, "timeout", "no_report" or "error"."""

    results: dict[str, ChallengeResult] = field(default_factory=dict)
    seconds: float = 0.0
    problem: str | None = None

    @property
    def ok(self) -> bool:
        return self.problem is None and all(r.status == "pasa" for r in self.results.values()) \
            and set(self.results) == set(LIVE_TESTS)


def _test_id(classname: str, file: str | None) -> str | None:
    """'tests.test_t04' or 'tests/test_t04.py' -> 'T04'."""
    m = re.search(r"test_t(\d{2})", file or classname or "")
    return f"T{m.group(1)}" if m else None


def parse_junit(xml_text: str) -> dict[str, ChallengeResult]:
    """JUnit XML from pytest, grouped by challenge test. A testcase with <failure> or <error> fails,
    one with <skipped> is skipped, any other passed."""
    root = ET.fromstring(xml_text)
    results: dict[str, ChallengeResult] = {}
    for case in root.iter("testcase"):
        test_id = _test_id(case.get("classname", ""), case.get("file"))
        if test_id is None:
            continue
        result = results.setdefault(test_id, ChallengeResult())
        result.seconds += float(case.get("time") or 0.0)
        if case.find("failure") is not None or case.find("error") is not None:
            result.failed += 1
        elif case.find("skipped") is not None:
            result.skipped += 1
        else:
            result.passed += 1
    return dict(sorted(results.items()))


def command(report: Path) -> list[str]:
    return [sys.executable, "-m", "pytest", *LIVE_TESTS.values(), "-q", "-p", "no:cacheprovider",
            f"--junitxml={report}"]


def run_live(timeout: float = TIMEOUT_S, root: Path = ROOT) -> LiveRun:
    """Run the fast challenge tests in a subprocess and read their report. Never raises."""
    started = time.perf_counter()
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    with tempfile.TemporaryDirectory(prefix="ctvn-jurado-") as tmp:
        report = Path(tmp) / "reto.xml"
        try:
            subprocess.run(command(report), cwd=root, env=env, capture_output=True, text=True, timeout=timeout,
                           check=False)
        except subprocess.TimeoutExpired:
            return LiveRun(seconds=time.perf_counter() - started, problem="timeout")
        except OSError:
            return LiveRun(seconds=time.perf_counter() - started, problem="error")
        elapsed = time.perf_counter() - started
        if not report.exists():
            return LiveRun(seconds=elapsed, problem="no_report")
        try:
            results = parse_junit(report.read_text(encoding="utf-8"))
        except ET.ParseError:
            return LiveRun(seconds=elapsed, problem="no_report")
    return LiveRun(results=results, seconds=elapsed)


def last_recorded(path: Path = PRUEBAS_CSV) -> dict[str, dict]:
    """Last recorded run of each challenge test from the tests matrix: date (ISO) and 'n/m' passed.
    Only what the matrix states; a missing value stays None."""
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            seen = re.match(r"\s*(Pasa|Falla)\s*\((\d+)/(\d+)\)", row.get("Observado") or "")
            date = re.search(r"(\d{4}-\d{2}-\d{2})", row.get("Evidencia") or "")
            out[row.get("ID")] = {
                "fecha": date.group(1) if date else None,
                "estado": None if seen is None else ("pasa" if seen.group(1) == "Pasa" else "falla"),
                "pasaron": None if seen is None else int(seen.group(2)),
                "de": None if seen is None else int(seen.group(3)),
            }
    return out
