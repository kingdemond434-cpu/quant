from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts import pr_blockers as pb

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
HEAD = "a" * 40


def _pr(**kw: Any) -> dict[str, Any]:
    return {"number": 7, "title": "t", "head": {"sha": HEAD}, "draft": False, **kw}


def _green() -> tuple[str, list[str]]:
    return "green", []


def _clear(hours_ago: float = 30.0, sha: str = HEAD, verdict: str = "CLEAR") -> dict[str, Any]:
    return {"pr": 7, "sha": sha, "verdict": verdict,
            "at": (NOW - timedelta(hours=hours_ago)).isoformat()}  # fmt: skip


def test_the_gate_constants_match_the_gate() -> None:
    spec = importlib.util.spec_from_file_location("ag", ROOT / ".github/scripts/audit_gate.py")
    assert spec and spec.loader
    ag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ag)
    assert tuple(ag.GATING_JOBS) == pb.GATING_JOBS
    assert ag.REGISTRY_HOLD_H == pb.VETO_H


def test_each_blocker_in_merge_path_order() -> None:
    c = pb.classify
    assert c(NOW, _pr(mergeable=False), _clear(), _green(), None)["blocker"] == "CONFLICT"
    assert c(NOW, _pr(), None, _green(), None)["blocker"] == "AUDIT_MISSING"
    assert c(NOW, _pr(), _clear(verdict="HOLD"), _green(), None)["blocker"] == "AUDIT_HOLD"
    assert c(NOW, _pr(), _clear(sha="b" * 40), _green(), None)["blocker"] == "AUDIT_STALE"
    assert c(NOW, _pr(), _clear(), ("failed", ["quality"]), None)["blocker"] == "CI_FAILED"
    assert c(NOW, _pr(), _clear(), ("pending", ["quality"]), None)["blocker"] == "CI_PENDING"
    assert c(NOW, _pr(), _clear(hours_ago=3), _green(), None)["blocker"] == "VETO_WINDOW"
    off = {
        "description": "registry: authority: LIVE's root digest is not the pinned one, "
        "so the path is off"
    }
    assert c(NOW, _pr(), _clear(), _green(), off)["blocker"] == "GATE_PATH_OFF"
    assert c(NOW, _pr(), _clear(), _green(), None)["blocker"] == "READY"


def test_also_lists_every_other_blocker() -> None:
    got = pb.classify(NOW, _pr(), None, ("pending", ["quality"]), None)
    assert got["blocker"] == "AUDIT_MISSING" and got["also"] == ["CI_PENDING"]


def test_ci_state_newest_run_wins_and_missing_jobs_are_pending() -> None:
    runs = [
        {"name": "quality", "status": "completed", "conclusion": "failure", "started_at": "1"},
        {"name": "quality", "status": "completed", "conclusion": "success", "started_at": "2"},
        {
            "name": "mt5-money-path",
            "status": "completed",
            "conclusion": "success",
            "started_at": "1",
        },
    ]
    assert pb.ci_state(runs) == ("pending", ["coverage-floor"])
    runs.append(
        {
            "name": "coverage-floor",
            "status": "completed",
            "conclusion": "skipped",
            "started_at": "1",
        }
    )
    assert pb.ci_state(runs) == ("green", [])
    runs.append(
        {
            "name": "coverage-floor",
            "status": "completed",
            "conclusion": "cancelled",
            "started_at": "3",
        }
    )
    assert pb.ci_state(runs) == ("failed", ["coverage-floor"])
    assert pb.ci_state([{"name": "other", "status": "queued"}])[0] == "pending"


def test_collect_reads_and_never_writes() -> None:
    calls: list[str] = []

    def fetch(path: str) -> Any:
        calls.append(path)
        if "/pulls?" in path:
            return [_pr()]
        if path.endswith("/pulls/7"):
            return {"mergeable": True, "mergeable_state": "clean"}
        if "/check-runs" in path:
            return {"check_runs": [{"name": j, "status": "completed", "conclusion": "success",
                                    "started_at": "1"} for j in pb.GATING_JOBS]}  # fmt: skip
        return {"statuses": []}

    rows = pb.collect("o/r", NOW, fetch, registry=lambda repo: [])
    assert rows[0]["blocker"] == "AUDIT_MISSING"
    assert all("/merge" not in c and "/comments" not in c for c in calls)


def test_table_has_one_line_per_pr() -> None:
    rows = [pb.classify(NOW, _pr(number=n), None, _green(), None) for n in (1, 2)]
    md = pb.table(rows, "now")
    assert md.count("| #") == 2 and "AUDIT_MISSING 2" in md
