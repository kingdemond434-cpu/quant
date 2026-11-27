"""pr_tick checks PRs until its budget is spent, release trains first (11-26: one PR per 1-2 h
pass left 86 open PRs, the release trains among them, days from their checks)."""
from __future__ import annotations

import contextlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import box_loop as L  # noqa: E402


def _pr(n: int, ref: str) -> dict:
    return {"number": n, "head": {"ref": ref, "sha": f"{n:040d}"}}


class Forge:
    def __init__(self, prs):
        self.prs = prs

    def gh(self, path):
        if "/pulls?" in path:
            return self.prs
        if "/check-runs" in path:
            return {"check_runs": []}
        return []


def _wire(monkeypatch, prs, clock):
    seen: list[int] = []
    monkeypatch.setattr(L, "_forge", lambda cfg, user: Forge(prs))
    monkeypatch.setattr(L, "checked", lambda runs: False)
    monkeypatch.setattr(L, "audited_clear", lambda comments, head: True)
    monkeypatch.setattr(L, "git", lambda cfg, *a: "")
    monkeypatch.setattr(L, "worktree", lambda cfg, head: contextlib.nullcontext(Path(".")))
    monkeypatch.setattr(L, "fast_path", lambda: True)
    monkeypatch.setattr(L, "post", lambda *a, **k: None)
    monkeypatch.setattr(L.RES, "_measure", lambda cfg: (500.0, [0.0] * 18, 64.0))

    def risk(cfg, root, base, head):
        seen.append(int(head))
        clock[0] += 600
        return True, "ok"
    monkeypatch.setattr(L, "fast_risk", risk)
    monkeypatch.setattr(L, "fast_replay", lambda cfg, base, head, changed: (True, "ok"))
    monkeypatch.setattr(L.time, "monotonic", lambda: clock[0])
    return seen


def test_trains_first_then_oldest():
    prs = [_pr(9, "claude/x"), _pr(40, "claude/train-4"), _pr(3, "claude/y"),
           _pr(31, "claude/train-2"), _pr(35, "claude/release-train-3")]
    assert [p["number"] for p in L.pr_order(prs)] == [31, 35, 40, 3, 9]


def test_many_prs_are_checked_in_one_pass_until_the_budget(monkeypatch):
    monkeypatch.setattr(L, "DIRECT_LIVE", False)  # pins r20 behaviour (r21 is direct live)
    prs = [_pr(n, f"claude/p{n}") for n in range(1, 11)]
    clock = [0.0]
    seen = _wire(monkeypatch, prs, clock)
    out = L.pr_tick(None, budget_s=1500)          # type: ignore[arg-type]
    assert seen == [1, 2, 3]                       # 600 s each: the third starts at 1200 s
    assert out.count("fast path") == 3 and "budget spent" in out


def test_a_pr_in_hand_always_finishes_and_one_always_runs(monkeypatch):
    monkeypatch.setattr(L, "DIRECT_LIVE", False)  # pins r20 behaviour (r21 is direct live)
    clock = [0.0]
    seen = _wire(monkeypatch, [_pr(1, "claude/a"), _pr(2, "claude/b")], clock)
    out = L.pr_tick(None, budget_s=0)              # type: ignore[arg-type]
    assert seen == [1] and "budget spent" in out


def test_nothing_waiting(monkeypatch):
    clock = [0.0]
    _wire(monkeypatch, [], clock)
    assert L.pr_tick(None) == "no PR waiting for checks"   # type: ignore[arg-type]
