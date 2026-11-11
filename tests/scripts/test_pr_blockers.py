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


def test_a_failed_read_is_unmeasured_and_never_loses_the_table() -> None:
    def fetch(path: str) -> Any:
        if "/pulls?" in path:
            return [_pr(number=n) for n in range(1, 10)]
        raise RuntimeError("gh: HTTP 503")

    rows = pb.collect("o/r", NOW, fetch, registry=lambda repo: [])
    assert len(rows) == 9 and {r["blocker"] for r in rows} == {"UNMEASURED"}
    assert "HTTP 503" in rows[0]["gate_says"]
    assert "reads in a row failed" in rows[-1]["gate_says"]  # stops calling after MAX_MISSES


def test_the_leg_budget_marks_the_rest_unmeasured() -> None:
    t = iter(range(0, 1000, 10))

    def fetch(path: str) -> Any:
        if "/pulls?" in path:
            return [_pr(number=n) for n in range(1, 6)]
        return {}

    rows = pb.collect("o/r", NOW, fetch, registry=lambda repo: [],
                      clock=lambda: float(next(t)), budget_s=25)  # fmt: skip
    assert [r["blocker"] for r in rows][:2] == ["AUDIT_MISSING", "AUDIT_MISSING"]
    assert rows[-1]["blocker"] == "UNMEASURED" and "budget" in rows[-1]["gate_says"]


def test_budget_reads_the_cycle_cap(monkeypatch: Any) -> None:
    monkeypatch.delenv("QUANT_LEG_BUDGET_S", raising=False)
    assert pb._budget_s() == float("inf")
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "600")
    assert pb._budget_s() == 570.0
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "10")
    assert pb._budget_s() == 30.0


def test_it_is_an_hourly_core_leg_and_published() -> None:
    hc = (ROOT / "desks/mt5/research/hourly_cycle.py").read_text(encoding="utf-8")
    assert '"box_state_freshness", "desk_health", "pr_blockers",' in hc
    assert '_producer("pr_blockers", "scripts/pr_blockers.py")' in hc
    assert '"pr_blockers": pbk' in hc
    # its own name: `prb` is the probation leg's result, so reusing it reported the wrong leg
    assert 'pbk = _costed("pr_blockers"' in hc and 'prb = _costed("pr_blockers"' not in hc
    for f in ("libs/ops/release.py", "desks/mt5/mt5desk/release_identity.py",
              "desks/mt5/scripts/sync_shadow_to_git.ps1"):  # fmt: skip
        assert "desks/mt5/reports/PR_BLOCKERS.json" in (ROOT / f).read_text(encoding="utf-8")
    assert "!desks/mt5/reports/PR_BLOCKERS.json" in (ROOT / ".gitignore").read_text()
    oc = (ROOT / "ops/organ_contract.py").read_text(encoding="utf-8")
    assert '"MT5-HourlyCore (pr blockers)"' in oc
