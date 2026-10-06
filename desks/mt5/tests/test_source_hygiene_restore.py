"""Source hygiene that the 2026-10-06 research-generation restore repaired, pinned.

1. MOJIBAKE. UTF-8 text decoded as cp1252 and re-encoded (once or more) turns a section sign
   into an eight-character run starting with A-tilde, and a CJK name into a longer one. Four
   such lines reached LIVE in 03dad3864
   (deepening_worker x3 -- one of them inside an artifact's `law` string -- and research_roi x1).
   The patterns below are the multi-pass signatures only, so real Portuguese/French/Hebrew text
   (Portuguese tildes, a multiplication sign before a yen sign) never matches. The patterns are
   written as escapes so this file cannot match itself.
2. B023. A closure defined in a loop that reads the loop's variables sees the LAST iteration's
   values if it is ever called after the loop moves on. `families_orthogonal`'s `bias_active`
   and `acquire_datasets`' `_refuse_url` now bind them as defaults.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCANNED = ("desks", "libs", "research", "scripts", "docs")
MOJIBAKE = re.compile("|".join((
    "\u00c3\u0192",
    "\u00c3\u201a\u00c2",
    "\u00c3\u00a2\u00e2\u201a\u00ac",
    "\u00e2\u20ac[\u2122\u0153\u009d\u201c\u201d\u02dc\u00a6]",
    "\u00c3\u00a4\u00c2",
    "\u00c3\u00a7\u00c2",
    "\u00c3\u00a9\u00c2",
)))


def _sources() -> list[Path]:
    out: list[Path] = []
    for top in SCANNED:
        root = REPO / top
        if root.exists():
            out.extend(p for p in root.rglob("*") if p.suffix in (".py", ".md")
                       and ".git" not in p.parts and p.is_file())
    return out


def test_no_mojibake_in_tracked_sources() -> None:
    hits = []
    for path in _sources():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if MOJIBAKE.search(line):
                hits.append(f"{path.relative_to(REPO)}:{i}")
    assert hits == []


def test_the_repaired_lines_read_as_written() -> None:
    worker = (REPO / "desks/mt5/research/deepening_worker.py").read_text(encoding="utf-8")
    assert worker.count("LAWS §5e") == 3
    roi = (REPO / "desks/mt5/research/research_roi.py").read_text(encoding="utf-8")
    assert "七禾网" in roi


B023_FILES = ("desks/mt5/mt5desk/families_orthogonal.py",
              "desks/mt5/research/acquire_datasets.py")


@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed here")
def test_loop_closures_bind_their_loop_variables() -> None:
    got = subprocess.run(["ruff", "check", "--isolated", "--select", "B023",
                          "--output-format", "concise", *B023_FILES],
                         cwd=REPO, capture_output=True, text=True, timeout=120)
    assert got.returncode == 0, got.stdout + got.stderr


def test_bias_active_binds_the_days_ages() -> None:
    import inspect

    from mt5desk import families_orthogonal as fo

    src = inspect.getsource(fo)
    assert "_src_hi: int = source_high_age" in src and "_ses_lo: int = session_low_age" in src
