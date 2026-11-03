"""B023: closures built in a loop must bind THEIR iteration's values, not the last one's.

Both sites below used to be ``def`` closures inside a loop that read loop variables from the
enclosing scope. Each test builds the per-iteration callables the way the production loop does,
keeps them past the loop, and only then calls them: a late-binding closure would answer every
call with the final iteration's values.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from mt5desk import families_orthogonal as fo  # noqa: E402

from research import acquire_datasets as acquisition  # noqa: E402


def test_lvc_bias_gates_keep_their_own_session_day_ages() -> None:
    # Day i has a high touched i bars before the London open; recent means <= 3 bars.
    gates = []
    for age in range(8):
        gates.append(fo._lvc_bias_gate(
            bias_mode="source_shift", bias_block_bars=10, recent_extreme_bars=3,
            source_high_age=age, source_low_age=100 + age,
            session_high_age=100 + age, session_low_age=age))
    # Late binding would make every gate see age 7 (not recent) and answer False everywhere.
    assert [g(1, 0) for g in gates] == [age <= 3 for age in range(8)]
    assert [g(-1, 0) for g in gates] == [False] * 8


def test_lvc_bias_gate_matches_the_rule_it_replaced() -> None:
    kw = {"bias_block_bars": 3, "recent_extreme_bars": 3, "source_high_age": 13,
          "source_low_age": 2, "session_high_age": 0, "session_low_age": 80}
    off = fo._lvc_bias_gate(bias_mode="off", **kw)
    shift = fo._lvc_bias_gate(bias_mode="source_shift", **kw)
    session = fo._lvc_bias_gate(bias_mode="session_relative", **kw)
    assert not off(1, 0) and not off(-1, 0)
    assert (shift(1, 0), shift(-1, 0)) == (False, True)
    assert (session(1, 0), session(-1, 0)) == (True, False)
    assert not session(1, 4)            # past the block window the bias never applies


def test_url_refusers_stamp_their_own_endpoint() -> None:
    reg: dict = {"by_url": {}, "series": {}}
    reasons: list[str] = []
    refusers = []
    for i in range(4):
        refusers.append(acquisition._url_refuser(
            reg, reasons.append, url=f"https://h{i}.test/d.csv", host=f"h{i}.test",
            attempt_at=f"2026-09-30T00:00:0{i}+00:00"))
    for i, refuse_url in enumerate(refusers):
        refuse_url(f"why{i}")
    # Late binding would write all four refusals onto the last URL only.
    assert sorted(reg["by_url"]) == [f"https://h{i}.test/d.csv" for i in range(4)]
    for i in range(4):
        row = reg["by_url"][f"https://h{i}.test/d.csv"]
        assert row == {"host": f"h{i}.test", "series": [], "status": "REFUSED",
                       "at": f"2026-09-30T00:00:0{i}+00:00", "refusal": f"why{i}"}
    assert reasons == [f"why{i}" for i in range(4)]


REPO = DESK.parents[1]


@pytest.mark.skipif(importlib.util.find_spec("ruff") is None,
                    reason="UNMEASURED: ruff is not installed in this interpreter")
def test_no_b023_anywhere_in_the_repository() -> None:
    """The fence. pyproject's ruff config selects B but EXCLUDES desks/mt5 wholesale, so the
    project gate never saw these sites; ``--isolated`` checks every file with B023 alone."""
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--isolated", "--no-cache", "--select", "B023",
         "--output-format", "concise", str(REPO)],
        capture_output=True, text=True, timeout=300, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
