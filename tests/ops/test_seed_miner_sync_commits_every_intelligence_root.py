"""The VPS's hourly intelligence sync commits BOTH trees the compiler reads.

MEASURED 2026-09-08: ops/run_seed_miners_hourly.sh committed desks/mt5/data/intelligence and
not the repo-root data/intelligence, which is where both LLM seats donate
(libs/ops/deepseek_cycle.py DONATE_DIR, scripts/kimi_hunter.py DONATE_DIR). Zero seat donation
files were tracked on either branch: a donation sat untracked on the VPS until an unrelated
tracked change under data/ let the DeepSeek factory's blanket add sweep it up. The compiler on
the box reads only what git carries, so an untracked donation is an unread one.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops" / "run_seed_miners_hourly.sh"
SRC = SCRIPT.read_text("utf-8")


def _intel_paths() -> list[str]:
    m = re.search(r"INTEL_PATHS=\((.*?)\)", SRC, re.S)
    assert m, "INTEL_PATHS array not found"
    return [ln.strip() for ln in m.group(1).splitlines() if ln.strip()
            and not ln.strip().startswith("#")]


def test_both_intelligence_roots_are_synced() -> None:
    paths = _intel_paths()
    assert "desks/mt5/data/intelligence" in paths
    assert "data/intelligence" in paths, "the seats' donation tree is not committed"


def test_the_seats_donate_under_the_synced_root() -> None:
    ds = pytest.importorskip("libs.ops.deepseek_cycle")
    K = pytest.importorskip("scripts.kimi_hunter")
    assert ds.DONATE_DIR.startswith("data/intelligence/")
    assert K.DONATE_DIR.relative_to(K.ROOT).as_posix().startswith("data/intelligence/")


def test_untracked_donations_are_reason_enough_to_commit() -> None:
    assert "git ls-files --others --exclude-standard" in SRC


def test_the_script_parses() -> None:
    if not Path("/bin/bash").exists():
        pytest.skip("no bash")
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
