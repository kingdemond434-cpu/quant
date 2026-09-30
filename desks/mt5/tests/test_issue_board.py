"""Silent legs that were killed at the hourly cycle's cap before writing (2026-09-30 census).

Each organ below had its own stopping point ABOVE the leg cap the cycle kills it at, or did its
slow step before writing its artifact, so a pass that ran long wrote nothing. The cycle exports
its cap as QUANT_LEG_BUDGET_S; these pin that each organ now stops inside it.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import job_lock  # noqa: E402
from research import issue_board  # noqa: E402
from side_channels import run_external_backtest as reb  # noqa: E402


def test_issue_board_repairs_stop_inside_the_cap_and_rotate(monkeypatch: pytest.MonkeyPatch,
                                                            tmp_path: Path) -> None:
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "720")
    assert issue_board.repair_budget_s() == pytest.approx(720 - 108)
    monkeypatch.delenv("QUANT_LEG_BUDGET_S")
    assert issue_board.repair_budget_s() is None
    issues = [issue_board.Issue(f"stale:p{i}", "STALLED", "w", "d", "python nope.py", auto=True)
              for i in range(3)]
    done = issue_board.repair(issues, apply=True, budget_s=0.0)
    assert {d["action"] for d in done} == {"NOT_REACHED"}
    assert len(issue_board._rotated(issues)) == 3


def test_issue_board_writes_the_board_before_it_repairs(monkeypatch: pytest.MonkeyPatch,
                                                        tmp_path: Path) -> None:
    report = tmp_path / "ISSUE_BOARD.json"
    monkeypatch.setattr(issue_board, "REPORT", report)
    monkeypatch.setattr(issue_board, "collect", lambda: [])
    seen: list[bool] = []

    def _repair(issues, apply=False, timeout_s=900, budget_s=None):  # type: ignore[no-untyped-def]
        seen.append(report.exists())
        return []
    monkeypatch.setattr(issue_board, "repair", _repair)
    issue_board.run(apply=True)
    assert seen == [True]


def test_admission_never_waits_past_a_quarter_of_the_leg_cap(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "720")
    assert job_lock.admit_patience_s() == 180
    monkeypatch.delenv("QUANT_LEG_BUDGET_S")
    assert job_lock.admit_patience_s() == job_lock.ADMIT_PATIENCE_SECONDS


def test_backtest_stops_inside_the_cycle_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_LEG_BUDGET_S", raising=False)
    assert reb._budget_s() == 45 * 60
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "720")
    monkeypatch.setattr(reb, "_PROCESS_T0", time.time())
    assert reb._budget_s() <= 720 - 108


def test_falsifier_budget_never_exceeds_the_cycle_cap(monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    import contextlib

    from research import falsifier_run as fr
    got: list[float] = []

    def _run(**kw):  # type: ignore[no-untyped-def]
        got.append(kw["budget_sec"])
        return {"n_certificates": 0, "budget_sec": kw["budget_sec"]}

    @contextlib.contextmanager
    def _job(*_a, **_k):  # type: ignore[no-untyped-def]
        yield True
    monkeypatch.setattr(fr, "run", _run)
    monkeypatch.setattr(job_lock, "exclusive_job", _job)
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "300")
    fr.main(["--report", str(tmp_path / "r.json")])
    assert got and got[0] <= 300 - 60
    monkeypatch.delenv("QUANT_LEG_BUDGET_S")
    fr.main(["--report", str(tmp_path / "r.json")])
    assert got[1] == fr.DEFAULT_BUDGET_SEC
