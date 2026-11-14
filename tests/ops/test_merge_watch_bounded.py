"""The merge-pipeline watcher is bounded (2026-11-13): it read ~1,300 gh calls per run with no
clock, so the box sweep hit its 30-min task limit every run. These pin the bound."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "mp_bounded", ROOT / "scripts" / "merge_pipeline_watch.py"
)
assert _spec and _spec.loader
mp = importlib.util.module_from_spec(_spec)
sys.modules["mp_bounded"] = mp
_spec.loader.exec_module(mp)

HEAD = "a" * 40


def _pr(n: int, draft: bool = True, head: str | None = None, upd: str = "2026-11-13") -> dict:
    return {"number": n, "draft": draft, "updated_at": upd,
            "head": {"sha": head or f"{n:040d}", "ref": f"b{n}"}}  # fmt: skip


def _clear(n: int, sha: str, at: str = "2026-11-13T10:00:00Z") -> dict[str, Any]:
    return {"issue_url": f"https://api.github.com/repos/o/r/issues/{n}",
            "author_association": "OWNER", "created_at": at, "updated_at": at,
            "body": f"AUDIT CLEAR {sha[:12]} merge"}  # fmt: skip


class FakeGh:
    """Answers the watcher's gh paths and counts calls; `slow` advances a fake clock."""

    def __init__(self, prs: list[dict], comments: list[dict], clock: list[float], step: float):
        self.prs, self.comments, self.clock, self.step = prs, comments, clock, step
        self.calls: list[str] = []

    def __call__(self, path: str, timeout: float = 0) -> Any:
        self.calls.append(path)
        self.clock[0] += self.step
        if "/pulls?state=open" in path:
            return self.prs if path.endswith("&page=1") else []
        if "/pulls?state=closed" in path:
            return []
        if "/actions/runs" in path:
            return {"workflow_runs": []}
        if "/commits?sha=" in path:
            return []
        if "/issues/comments?" in path:
            return self.comments if path.endswith("&page=1") else []
        if path.endswith("/status"):
            return {"statuses": []}
        if "/check-runs" in path:
            return {"check_runs": []}
        raise AssertionError(path)


def _run(monkeypatch: pytest.MonkeyPatch, prs: list[dict], comments: list[dict], budget: float,
         step: float = 1.0) -> tuple[dict, FakeGh]:  # fmt: skip
    clock = [0.0]
    gh = FakeGh(prs, comments, clock, step)
    monkeypatch.setattr(mp, "_gh", gh)
    monkeypatch.setattr(mp.time, "monotonic", lambda: clock[0])
    return mp.collect("o/r", budget_s=budget), gh


def test_clears_come_from_one_listing_not_a_call_per_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    prs = [_pr(n) for n in range(1, 301)]
    rep, gh = _run(monkeypatch, prs, [_clear(7, f"{7:040d}")], budget=10_000)
    assert sum("/issues/comments?" in c for c in gh.calls) == 1
    assert not any(f"/issues/{n}/comments" in c for c in gh.calls for n in range(1, 301))
    row = next(r for r in rep["prs"] if r["pr"] == 7)
    assert row["clear_at"] == "2026-11-13T10:00:00Z"
    assert rep["coverage"]["unread"] == 0 and rep["coverage"]["clears_complete"]


def test_the_budget_stops_reads_and_priority_prs_go_first(monkeypatch: pytest.MonkeyPatch) -> None:
    prs = [_pr(n, upd=f"2026-11-{n % 28 + 1:02d}") for n in range(1, 201)]
    prs.append(_pr(500, draft=False))
    prs.append(_pr(501, head=HEAD))
    rep, gh = _run(monkeypatch, prs, [_clear(501, HEAD)], budget=30)
    reads = [c for c in gh.calls if "/check-runs" in c]
    assert len(reads) < 40  # bounded, not one per PR
    first_two = " ".join(reads[:2])
    assert f"/commits/{500:040d}/check-runs" in first_two  # the ready PR
    assert f"/commits/{HEAD}/check-runs" in first_two  # the CLEARed draft
    cov = rep["coverage"]
    assert cov["unread"] > 150 and cov["priority_unread"] == []
    assert not any(r.startswith("WATCH_PARTIAL") for r in rep["red"])


def test_a_priority_pr_left_unread_is_red(monkeypatch: pytest.MonkeyPatch) -> None:
    prs = [_pr(n, draft=False) for n in range(1, 50)]
    rep, _ = _run(monkeypatch, prs, [], budget=12)
    assert rep["status"] == "RED"
    assert any(r.startswith("WATCH_PARTIAL") for r in rep["red"])
    assert rep["coverage"]["priority_unread"]


def test_a_cut_clear_listing_is_red(monkeypatch: pytest.MonkeyPatch) -> None:
    full = [_clear(1, "f" * 40) for _ in range(100)]
    clock = [0.0]

    def gh(path: str, timeout: float = 0) -> Any:
        clock[0] += 5.0
        if "/issues/comments?" in path:
            return full  # always a full page: the listing never ends inside the budget
        return FakeGh([_pr(1)], [], [0.0], 0)(path)

    monkeypatch.setattr(mp, "_gh", gh)
    monkeypatch.setattr(mp.time, "monotonic", lambda: clock[0])
    rep = mp.collect("o/r", budget_s=60)
    assert rep["coverage"]["clears_complete"] is False
    assert "WATCH_PARTIAL: the CLEAR listing was cut by the budget" in rep["red"]


def test_every_gh_call_times_out_and_kills_its_child(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run(cmd: list[str], **kw: Any) -> Any:
        seen.update(kw)
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])

    monkeypatch.setattr(mp.subprocess, "run", run)
    with pytest.raises(RuntimeError, match=r"timed out after 45\.0s"):
        mp._gh("repos/o/r/pulls")
    assert seen["timeout"] == mp.GH_TIMEOUT_S


def test_the_budget_is_far_under_the_sweep_task_limit() -> None:
    # the sweep runs live-first, the gate and adopt-rows before the watch, all inside 30 min
    assert mp.BUDGET_S + 2 * mp.GH_TIMEOUT_S <= 10 * 60
    assert "--budget-s" in (ROOT / "scripts/merge_pipeline_watch.py").read_text(encoding="utf-8")
