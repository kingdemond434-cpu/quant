"""Discovery legs stop by themselves inside their cap, write, and resume where they stopped.

Noon CRO 2026-09-30: sweep, compile_candidates, descendants, probation, discovery_compiler and
conversion_maximiser all timed out and moved 0 artifacts.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import hourly_cycle as hc  # noqa: E402
from research import miner_candidate_compiler as mcc  # noqa: E402
from research import orthogonal_sweep as osw  # noqa: E402


def test_self_budget_is_read_off_the_call() -> None:
    assert hc._self_budget_s(("--once", "--budget-s", "900")) == 900.0
    assert hc._self_budget_s(("--budget-s=240",)) == 240.0
    assert hc._self_budget_s(("--max-rows", "5",)) is None
    assert hc._self_stop_floor_s(("--budget-s", "900")) == 900 + 135
    assert hc._self_stop_floor_s(("--budget-s", "240")) == 240 + 60


def test_a_priced_cap_never_lands_below_the_organs_own_stop(monkeypatch, tmp_path) -> None:
    seen: dict = {}
    monkeypatch.setattr(hc, "_priced_budget", lambda name, base: (120, {}))

    def _fake_run(cmd, **kw):
        seen["timeout"] = kw["timeout"]
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    monkeypatch.setattr(hc, "_run_tree", _fake_run)
    out = hc._producer_impl("conversion_maximiser", "research/conversion_maximiser.py",
                            ("--once", "--budget-s", "900"))
    assert seen["timeout"] == 1035 and out["budget_s"] == 1035


def test_legs_that_timed_out_now_declare_their_stop() -> None:
    src = " ".join((_DESK / "research" / "hourly_cycle.py").read_text("utf-8").split())
    for script in ("probation_runner", "orthogonal_sweep", "miner_candidate_compiler"):
        assert f'"research/{script}.py", "--budget-s"' in src, script


@pytest.fixture
def roots(tmp_path, monkeypatch):
    a = tmp_path / "intel"
    a.mkdir()
    monkeypatch.setattr(mcc, "INTEL_ROOTS", (a,))
    monkeypatch.setattr(mcc, "CURSOR", tmp_path / "cursor.json")
    yield a
    mcc._set_budget(None)


def test_compiler_intake_stop_parks_the_cursor_on_the_unread_row(roots, monkeypatch) -> None:
    path = roots / "big.jsonl"
    path.write_text("\n".join(json.dumps({"title": f"row-{i}", "symbol": "EURUSD"})
                               for i in range(4)) + "\n", "utf-8")
    calls = {"n": 0}

    def _past(key: str) -> bool:
        calls["n"] += 1
        return key == "intake_by" and calls["n"] > 2

    monkeypatch.setattr(mcc, "_past", _past)
    rows = mcc.recent_rows(mcc.datetime.now(tz=mcc.UTC))
    assert [r["title"] for _, r in rows] == ["row-0", "row-1"]
    assert mcc._LAST_INTAKE["bound_hit"] is True
    assert mcc._LAST_INTAKE["cursor_row_offset"] == 2
    mcc._save_cursor()
    monkeypatch.setattr(mcc, "_past", lambda key: False)
    rows = mcc.recent_rows(mcc.datetime.now(tz=mcc.UTC))
    assert [r["title"] for _, r in rows] == ["row-2", "row-3"], "resumes exactly, drops nothing"


def test_compiler_positions_track_every_returned_row(roots) -> None:
    (roots / "a.jsonl").write_text("\n".join(json.dumps({"title": f"r{i}"}) for i in range(3)),
                                   "utf-8")
    rows = mcc.recent_rows(mcc.datetime.now(tz=mcc.UTC))
    assert len(mcc._POSITIONS) == len(rows) == 3
    assert [i for _, i in mcc._POSITIONS] == [0, 1, 2]


def test_sweep_cursor_round_trips_and_wraps(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(osw, "CURSOR", tmp_path / "c.json")
    assert osw._read_cursor(10) == 0
    osw._write_cursor(7, 10, complete=False)
    assert osw._read_cursor(10) == 7
    assert osw._read_cursor(5) == 2, "a shrunken universe wraps rather than overruns"
    assert osw._read_cursor(0) == 0
