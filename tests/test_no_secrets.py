"""Zero secrets in the repo (delivery checklist, J-14). Owner: José.

Scans every file git tracks with the guard's key patterns; .env must never be tracked and
.env.example must ship with an empty key. A leaked key is rotated, not just deleted (CLAUDE.md).
"""

import re
import subprocess
from pathlib import Path

import pytest

from src.generate.guard import SECRET_PATTERNS

ROOT = Path(__file__).resolve().parents[1]
BINARY = {".parquet", ".npy", ".pdf", ".png", ".jpg", ".jpeg", ".docx"}
FAKE_KEYS = {"sk-or-v1-abcdefghijklmnopqrstuvwxyz0123"}  # test_guard.py: shaped like a key, not one


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout (e.g. a zip download): nothing tracked to scan")
    return [ROOT / line for line in out.splitlines() if line]


def test_no_key_in_any_tracked_file():
    leaks = []
    for path in tracked_files():
        if path.suffix.lower() in BINARY or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            leaks += [f"{path.relative_to(ROOT)}: {m[:12]}…" for m in re.findall(pattern, text) if m not in FAKE_KEYS]
    assert not leaks, leaks


def test_env_is_never_tracked_and_example_has_no_key():
    names = {p.relative_to(ROOT).as_posix() for p in tracked_files()}
    assert ".env" not in names
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^LLM_API_KEY=\s*$", example, re.MULTILINE)
