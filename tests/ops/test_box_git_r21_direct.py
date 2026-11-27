"""Boot r21, DIRECT LIVE (zuck 2026-11-27 11:40Z "no more tests no releases no merges js built n
direct live"; 11:42Z, on keeping only the automatic check on code that places real trades, "ok
only that nth else"). The one gate is the Auditor's CLEAR plus the risk invariants on a
money-path diff; LIVE's head is promoted as soon as it lands and adoption starts at once."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from ops.box_git import box_ci, delivery_leadtime
from ops.box_git import box_loop as L

A, B, C = "a" * 40, "b" * 40, "c" * 40
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]


def test_direct_live_is_on_and_runs_no_full_suite() -> None:
    assert L.DIRECT_LIVE is True
    assert L.heavy_stages() == ("pr",)
    assert "promote" in L.LIGHT  # promotion every light round (90 s)


# ------------------------------------------------------------------ promotion
def test_live_head_is_promotable_as_soon_as_it_lands() -> None:
    anc = lambda a, b: True  # noqa: E731
    assert box_ci.direct_promotable({}, B, anc, lambda a, b: "x.py") == B
    assert box_ci.direct_promotable({"promoted": A}, B, anc, lambda a, b: "x.py") == B


def test_nothing_new_or_only_the_seal_is_never_promoted_again() -> None:
    anc = lambda a, b: True  # noqa: E731
    assert box_ci.direct_promotable({"promoted": B}, B, anc, lambda a, b: "x.py") is None
    # the seal commit a promotion lands on LIVE changes RELEASE.json alone
    assert box_ci.direct_promotable({"promoted": A}, B, anc, lambda a, b: "") is None


def test_a_head_that_does_not_descend_from_the_last_promotion_is_refused() -> None:
    assert box_ci.direct_promotable({"promoted": A}, B, lambda a, b: False,
                                    lambda a, b: "x.py") is None
    assert box_ci.direct_promotable({}, "not-a-sha", lambda a, b: True, lambda a, b: "x") is None


def test_promote_tick_starts_adoption_after_a_promotion(monkeypatch, tmp_path) -> None:
    cfg = SimpleNamespace(state=tmp_path / "ci.json", bare=tmp_path, python="py",
                          remote=lambda: "origin", git_env=lambda who: {})
    monkeypatch.setattr(L, "git", lambda cfg, *a, **k: B if a[0] == "rev-parse" else "x.py")
    monkeypatch.setattr(L, "_run", lambda argv, **k: (0, "promoted\n"))
    monkeypatch.setattr(L, "seal_and_push", lambda cfg, head: head)

    class WT:
        def __init__(self, *a): pass
        def __enter__(self): return tmp_path
        def __exit__(self, *a): return False
    monkeypatch.setattr(L, "worktree", WT)
    started = []
    monkeypatch.setattr(L, "start_adoption", lambda: started.append(1) or "; adoption started")
    out = L.promote_tick(cfg)
    assert out.startswith(f"promote {B[:9]}: rc=0") and "adoption started" in out
    assert started == [1]
    assert box_ci.load_state(cfg.state)["promoted"] == B
    # the next light round has nothing new
    monkeypatch.setattr(L, "git", lambda cfg, *a, **k: B if a[0] == "rev-parse" else "")
    assert L.promote_tick(cfg) == "nothing new to promote"


def test_start_adoption_only_starts_the_box_task() -> None:
    src = (ROOT / "ops" / "box_git" / "box_loop.py").read_text(encoding="utf-8")
    assert '["schtasks.exe", "/Run", "/TN", ADOPT_TASK]' in src
    assert L.ADOPT_TASK == "MT5-AdoptRelease"


# ------------------------------------------------------------------ the one check
def _cfg(tmp_path):
    return SimpleNamespace(work=tmp_path, python="py", ci_jobs=None)


def _patch(monkeypatch, tmp_path, money, risk=(True, "risk-invariants passed (3 suite file(s))")):
    posts, ran = [], []

    class WT:
        def __init__(self, *a): pass
        def __enter__(self): return tmp_path
        def __exit__(self, *a): return False
    monkeypatch.setattr(L, "worktree", WT)
    monkeypatch.setattr(L, "money_changes", lambda *a: money)
    monkeypatch.setattr(L, "post", lambda cfg, sha, st, desc, ctx=None: posts.append(
        (st, desc, ctx)))
    monkeypatch.setattr(L, "risk_job", lambda *a, **k: ran.append(1) or risk)
    return posts, ran


def test_a_non_money_diff_gets_no_check(monkeypatch, tmp_path) -> None:
    posts, ran = _patch(monkeypatch, tmp_path, ([], "0 money-path file(s) of 2"))
    out = L.direct_check(_cfg(tmp_path), {"number": 7}, A, B, ["docs/x.md", "scripts/y.py"])
    assert "not money path" in out and ran == []
    assert posts == [("success", "box: direct live, no money-path file changed "
                      "(0 money-path file(s) of 2): no check applies", (L.RISK_CONTEXT,))]


def test_a_money_diff_runs_the_risk_invariants_and_a_red_blocks(monkeypatch, tmp_path) -> None:
    posts, ran = _patch(monkeypatch, tmp_path, (["libs/risk/x.py"], "1 money-path file(s) of 1"),
                        risk=(False, "risk suites rc=1: 1 failed"))
    out = L.direct_check(_cfg(tmp_path), {"number": 8}, A, B, ["libs/risk/x.py"])
    assert ran == [1] and "risk FAIL" in out
    assert posts[0][0] == "failure" and posts[0][2] == (L.RISK_CONTEXT,)


def test_an_unmeasured_money_reading_still_runs_the_risk_check(monkeypatch, tmp_path) -> None:
    posts, ran = _patch(monkeypatch, tmp_path, (None, "money path UNMEASURED (rc=1): x"))
    L.direct_check(_cfg(tmp_path), {"number": 9}, A, B, ["anything.py"])
    assert ran == [1] and posts[0][0] == "success"


def test_the_classifier_is_replay_shadows_own(tmp_path) -> None:
    import subprocess
    import sys
    lst = tmp_path / "ch.txt"
    lst.write_text("desks/mt5/research/pf_allocator.py\ndocs/LAWS.md\nlibs/risk/x.py\n",
                   encoding="utf-8")
    out = subprocess.run([sys.executable, "-I", "-c", L._MONEY_PROBE, str(lst), str(ROOT)],
                         cwd=ROOT, capture_output=True, text=True, timeout=300).stdout
    assert 'MONEY=["desks/mt5/research/pf_allocator.py", "libs/risk/x.py"]' in out


def test_check_pr_routes_every_pr_to_the_direct_check(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(L, "git", lambda cfg, *a, **k: A if a[0] == "merge-base" else "x.py")
    seen = []
    monkeypatch.setattr(L, "direct_check", lambda cfg, p, base, head, ch: seen.append(
        (base, head, ch)) or "direct")
    hold = L.Hold(1, 3)
    assert L.check_pr(SimpleNamespace(), {"number": 1, "head": {"sha": B}}, hold) == "direct"
    assert seen == [(A, B, ["x.py"])]


# ------------------------------------------------------------------ the merge gate
def test_the_gate_needs_only_the_risk_invariants_in_direct_mode() -> None:
    src = (ROOT / ".github" / "scripts" / "audit_gate.py").read_text(encoding="utf-8")
    assert 'if os.environ.get(DIRECT_ENV, "").strip() in {"1", "true", "yes"}:\n' \
           '                need = (RISK_JOB,)' in src
    loop = (ROOT / "ops" / "box_git" / "box_loop.py").read_text(encoding="utf-8")
    assert 'DIRECT_ENV: "1" if DIRECT_LIVE else ""' in loop


# ------------------------------------------------------------------ the lead-time SLA
def _row(stages):
    return {"pr": 1, "state": "closed", "ci_causes": [],
            "stages": {k: (NOW - timedelta(minutes=m)).isoformat() for k, m in stages.items()}}


def test_direct_sla_wants_production_minutes_after_live_and_no_full_run() -> None:
    r = _row({"clear": 60, "forge_pr": 50, "ci_start": 40, "ci_end": 30, "live": 20})
    assert delivery_leadtime.sla([r], NOW, direct=True)["breaches"]["live"]["n"] == 1
    assert delivery_leadtime.sla([r], NOW)["ok"]  # r20: 180 min for the full run
    r2 = _row({"clear": 60, "forge_pr": 50, "ci_start": 40, "ci_end": 30, "live": 5})
    assert delivery_leadtime.sla([r2], NOW, direct=True)["ok"]
