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


def test_live_first_cancels_before_any_comment_read_and_in_parallel(tmp_path: Path) -> None:
    """2026-11-13 20:05Z box log: "98 ahead of LIVE or a CLEARed PR", "budget spent", 2
    cancelled. Comment reads came first and the cancels went out one at a time at 13-60 s each.
    Now LIVE's order is cancelled before any comment is read, from one fresh listing (no read
    per run), WORKERS at a time; every cancelled run is owed its re-run."""
    import threading
    import time as _time

    lf = _lf()
    live = {"id": 1, "event": "push", "head_branch": lf.LIVE, "created_at": OLD,
            "status": "queued"}  # fmt: skip
    prs = [{"id": 100 + i, "event": "pull_request", "head_branch": f"b{i}", "head_sha": f"h{i}",
            "created_at": "1999-12-31T00:00:00Z", "status": "queued", "run_attempt": 1}
           for i in range(24)]  # fmt: skip
    order: list[str] = []
    live_now = {"n": 0, "peak": 0}
    lock = threading.Lock()

    def gh(path: str, method: str = "GET") -> Any:
        if path.endswith("/cancel"):
            with lock:
                order.append("cancel")
                live_now["n"] += 1
                live_now["peak"] = max(live_now["peak"], live_now["n"])
            _time.sleep(0.05)
            with lock:
                live_now["n"] -= 1
            return None
        if "/comments" in path:
            order.append("comments")
            return []
        if "status=queued" in path:
            return {"workflow_runs": [live, *prs]}
        if "/pulls?" in path:
            return [{"number": i + 1, "head": {"ref": f"b{i}", "sha": f"h{i}"}} for i in range(24)]
        if "status=cancelled" in path:
            return {"workflow_runs": []}
        if "/actions/runs/" in path and method == "GET":
            order.append("read")  # the settle pass, after the cancels
            return {"status": "queued", "run_attempt": 1}
        return None

    lf._gh = gh
    lf.run("o/r", lf.LIVE, tmp_path / "s.json", settle_s=0, sleep=lambda s: None)
    assert order.count("cancel") == 24
    first_cancel = order.index("cancel")
    assert "read" not in order[:first_cancel]  # one fresh listing, no read per run
    assert order.index("comments") > max(i for i, o in enumerate(order) if o == "cancel")
    assert live_now["peak"] > 1  # the cancels went out in parallel
    import json

    owed = json.loads((tmp_path / "s.json").read_text())["owed"]
    assert sorted(r["id"] for r in owed) == [100 + i for i in range(24)]
