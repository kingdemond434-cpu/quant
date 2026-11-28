"""live_first_ci reaches LIVE's oldest queued runs, and CLEARed-first cannot eat the budget.

11-11 09:45Z: 1,223 runs queued. `_queued` reads the newest 500, so LIVE's push runs of 11-10
(and the PR runs ahead of them) were never seen: "0 ahead of LIVE". The same call spent its
whole budget in CLEARed-first comment reads and cancelled nothing.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _lf() -> Any:
    spec = importlib.util.spec_from_file_location("lf_reach", ROOT / "scripts/live_first_ci.py")
    assert spec and spec.loader
    lf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lf)
    return lf


OLD = "2000-01-01T00:00:00Z"


def _world(lf: Any, calls: list[tuple[str, str]], comments_cost: list[int] | None = None):
    live = {"id": 1, "event": "push", "head_branch": lf.LIVE, "created_at": OLD}
    old_pr = {"id": 2, "event": "pull_request", "head_branch": "b1", "head_sha": "h1",
              "created_at": "1999-12-31T00:00:00Z"}  # fmt: skip
    new_pr = {"id": 3, "event": "pull_request", "head_branch": "b2", "head_sha": "h2",
              "created_at": "2099-01-01T00:00:00Z"}  # fmt: skip
    runs = {2: {**old_pr, "status": "queued", "run_attempt": 1}}

    def gh(path: str, method: str = "GET") -> Any:
        calls.append((method, path))
        if f"branch={lf.LIVE}&status=queued" in path:
            return {"workflow_runs": [live]}
        if "status=queued&created=%3C" in path:
            return {"workflow_runs": [old_pr]}
        if "status=queued" in path:  # the newest pages: none of LIVE's old runs
            return {"workflow_runs": [new_pr]}
        if "/pulls?" in path:
            return [{"head": {"ref": "b1", "sha": "h1"}, "number": 11},
                    {"head": {"ref": "b2", "sha": "h2"}, "number": 12}]  # fmt: skip
        if "/comments?" in path:
            if comments_cost is not None:
                comments_cost.append(1)
            return []
        if path.endswith("/cancel"):
            runs[2] = {**runs[2], "status": "completed", "conclusion": "cancelled"}
            return None
        if path.endswith("/rerun"):
            return None
        if path.endswith("/jobs") or "/jobs?" in path:
            return {"jobs": []}
        rid = int(path.rsplit("/", 1)[1].split("?")[0])
        return runs.get(rid, {"status": "in_progress"})

    return gh


def test_an_old_live_run_past_the_newest_pages_still_moves_runs_behind_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    lf = _lf()
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(lf, "_gh", _world(lf, calls))
    assert lf.run("o/r", lf.LIVE, tmp_path / "s.json", settle_s=0, sleep=lambda s: None) == 0
    assert ("POST", "repos/o/r/actions/runs/2/cancel") in calls
    assert ("POST", "repos/o/r/actions/runs/2/rerun") in calls
    assert ("POST", "repos/o/r/actions/runs/3/cancel") not in calls  # queued after LIVE


def test_a_failed_older_read_leaves_the_call_as_it_was(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    lf = _lf()

    def boom(*a: Any) -> Any:
        raise RuntimeError("HTTP 502")

    monkeypatch.setattr(lf, "_older", boom)
    monkeypatch.setattr(lf, "_queued", lambda repo: [])
    monkeypatch.setattr(lf, "_heads", lambda repo: {})
    assert lf.run("o/r", lf.LIVE, tmp_path / "s.json", settle_s=0, sleep=lambda s: None) == 0


def test_older_reads_nothing_more_when_no_live_run_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    lf = _lf()
    calls: list[str] = []

    def gh(path: str, method: str = "GET") -> Any:
        calls.append(path)
        return {"workflow_runs": []}

    monkeypatch.setattr(lf, "_gh", gh)
    from datetime import UTC, datetime

    assert lf._older("o/r", lf.LIVE, datetime.now(UTC)) == []
    assert len(calls) == 1 and "created=" not in calls[0]


def test_older_pages_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    lf = _lf()
    calls: list[str] = []
    live = {"id": 1, "event": "push", "head_branch": lf.LIVE, "created_at": OLD}

    def gh(path: str, method: str = "GET") -> Any:
        calls.append(path)
        if "branch=" in path:
            return {"workflow_runs": [live]}
        return {"workflow_runs": [{"id": i, "event": "pull_request"} for i in range(100)]}

    monkeypatch.setattr(lf, "_gh", gh)
    from datetime import UTC, datetime

    lf._older("o/r", lf.LIVE, datetime.now(UTC))
    assert sum("created=" in c for c in calls) == lf.OLDER_PAGES


def test_cleared_first_stops_at_its_share_and_live_first_still_cancels(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    lf = _lf()
    calls: list[tuple[str, str]] = []
    cost: list[int] = []
    monkeypatch.setattr(lf, "_gh", _world(lf, calls, cost))
    # every clock read is 50 s later: CLEARed-first's 40% of 300 s ends after two reads
    t = iter(range(0, 100_000, 50))
    assert lf.run("o/r", lf.LIVE, tmp_path / "s.json", settle_s=0, sleep=lambda s: None,
                  clock=lambda: float(next(t))) == 0  # fmt: skip
    assert ("POST", "repos/o/r/actions/runs/2/cancel") in calls


def test_the_shares_are_pinned() -> None:
    lf = _lf()
    assert lf.CLEARED_SHARE == 0.4 and lf.OLDER_PAGES == 10 and lf.BUDGET_S == 300.0
