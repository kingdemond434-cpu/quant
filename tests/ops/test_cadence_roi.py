"""Cadence is read off yield, and safety floors are exempt by construction.

The load-bearing test here is the SAFETY FLOOR one: the whole hazard of a cadence optimiser is
that it eventually proposes turning off the organ that has been quietly preventing a tail. That
must be structurally impossible, not merely discouraged.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.ops.cadence_roi import (
    FLOOR_PROTECTED,
    miner_yield_trend,
    recommend,
    recommend_all,
)

_REPO = Path(__file__).resolve().parents[2]


def test_safety_floors_can_never_be_cut() -> None:
    for name in FLOOR_PROTECTED:
        v = recommend(f"scripts/{name}.py", runs_per_day=480.0, regime="SATURATING",
                      evidence="pretend the yield arithmetic says cut it hard")
        assert v.protected
        assert v.runs_per_day_recommended == v.runs_per_day_now, name
        assert "success case" in v.why


def test_saturating_organ_is_cut_and_never_below_once_daily() -> None:
    v = recommend("scripts/mine_research_queue.py", runs_per_day=6.0, regime="SATURATING",
                  evidence="measured yield fall")
    assert v.runs_per_day_recommended == 2.0
    tiny = recommend("scripts/x.py", runs_per_day=1.0, regime="SATURATING", evidence="e")
    assert tiny.runs_per_day_recommended == 1.0     # a cut never silently retires an organ


def test_publication_rate_limit_caps_at_the_upstream_rate() -> None:
    v = recommend("scripts/kimi_hunter.py", runs_per_day=8.0,
                  regime="PUBLICATION_RATE_LIMITED", upstream_publications_per_day=2.0,
                  evidence="e")
    assert v.runs_per_day_recommended == 2.0
    # Polling SLOWER than the upstream is not raised by this module -- it only removes waste.
    slow = recommend("scripts/x.py", runs_per_day=1.0, regime="PUBLICATION_RATE_LIMITED",
                     upstream_publications_per_day=9.0, evidence="e")
    assert slow.runs_per_day_recommended == 1.0


def test_unmeasured_organ_is_left_alone_not_cut() -> None:
    v = recommend("scripts/x.py", runs_per_day=5.0, regime="UNMEASURED", evidence="none")
    assert v.runs_per_day_recommended == 5.0
    assert "UNKNOWN is not a reason to cut" in v.why


def test_unknown_regime_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown regime"):
        recommend("scripts/x.py", runs_per_day=1.0, regime="VIBES", evidence="e")


def test_miner_trend_reads_the_real_ledger_or_says_unmeasured() -> None:
    t = miner_yield_trend(_REPO)
    assert t["status"] in ("MEASURED", "UNMEASURED")
    if t["status"] == "MEASURED":
        assert t["n_runs"] >= 3 and "verdict" in t


def test_recommend_all_reports_the_llm_saving() -> None:
    r = recommend_all(_REPO)
    assert r["llm_runs_per_day_saved"] > 0
    assert r["total_runs_per_day_saved"] >= r["llm_runs_per_day_saved"]
    assert all(v["evidence"] for v in r["verdicts"])       # no cut without grounds


# ------------------------------------------------------------------ the manifest actually moved
def test_manifest_matches_the_recommended_cadences() -> None:
    """A recommendation nobody installed is a docstring. These four lines are the installed cut."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    for sched, script in (("5 1,13 * * *", "scripts/kimi_hunter.py"),
                          ("13 4 * * *", "scripts/build_enforcement_matrix.py"),
                          ("44 4 * * *", "scripts/run_wiring_agent.py"),
                          ("20 5 * * *", "scripts/run_cro.py")):
        assert any(ln.startswith(sched) and script in ln for ln in man.splitlines()), script


def test_miner_cadence_floor_is_documented_against_being_raised() -> None:
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    assert "CADENCE FLOOR 2026-08-11" in man
    assert "MUST NOT be raised" in man
    # And the miner is still scheduled once daily -- documented, not deleted.
    assert any(ln.startswith("0 13 * * *") and "mine_research_queue" in ln
               for ln in man.splitlines())


def test_llm_budget_state_is_json_and_declares_authority() -> None:
    doc = json.loads((_REPO / "docs/policy/CADENCE_POLICY.json").read_text("utf-8"))
    assert doc["llm_runs_per_day_after"] < doc["llm_runs_per_day_before"]
    assert "RECOMMEND" in doc["authority"].upper()
