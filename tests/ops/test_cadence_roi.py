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


# ------------------------------------------------------------------ the manifest holds
def test_openrouter_cadences_are_held_at_original() -> None:
    """PRINCIPAL DIRECTIVE 2026-08-11: never cut GPT, DeepSeek or Kimi cadence.

    Four cuts were applied and reverted the same day. Two of them (the enforcement matrix and the
    wiring agent) rested on my own misclassification -- both make ZERO model calls, so cutting
    them saved no spend at all. This test pins the restored schedule so a future 'optimisation'
    cannot quietly re-cut a seat the principal has ruled is not to be cut.
    """
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    for sched, script in (("5 */3 * * *", "scripts/kimi_hunter.py"),
                          ("13 */6 * * *", "scripts/build_enforcement_matrix.py"),
                          ("44 */6 * * *", "scripts/run_wiring_agent.py"),
                          ("20 5,11,17,23 * * *", "scripts/run_cro.py")):
        assert any(ln.startswith(sched) and script in ln for ln in man.splitlines()), script
    assert "CADENCE CUT 2026-08-11" not in man, "a reverted cut left its marker behind"
    assert "CADENCE HELD 2026-08-11" in man


def test_miner_cadence_floor_is_documented_against_being_raised() -> None:
    """The one genuine cadence decision that STANDS -- and it is a floor, not a cut: the miner was
    already 1/day in the manifest. What changed is that raising it now has to argue with a
    measurement."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    assert "CADENCE FLOOR 2026-08-11" in man and "MUST NOT be raised" in man
    assert any(ln.startswith("0 13 * * *") and "mine_research_queue" in ln
               for ln in man.splitlines())


def test_policy_artifact_records_the_hold_and_the_true_spenders() -> None:
    doc = json.loads((_REPO / "docs/policy/CADENCE_POLICY.json").read_text("utf-8"))
    assert doc["llm_runs_per_day_saved"] == 0.0          # nothing was cut in the end
    assert "HELD AT ORIGINAL" in doc["openrouter_cadence"]
    # Only the three real spenders are named as such.
    assert set(doc["true_llm_spenders"]) == {
        "scripts/run_cro.py", "scripts/kimi_hunter.py", "scripts/run_survivor_panel.py"}
    assert "RECOMMEND" in doc["authority"].upper()
    # And the unbounded-prompt risk is on the record rather than in a chat message.
    assert "never sheds a ROW" in doc["open_risk_unbounded_prompt"]


# ------------------------------------------------------------------ the Claude-local cuts
# PRINCIPAL DIRECTIVE 2026-08-11: cut Claude-local session burn hard, without losing ROI.
# These pin the three properties that make each cut honest rather than merely smaller.

def test_recommendation_worker_is_hourly_not_every_twenty_minutes() -> None:
    """72/day was 74% of the desk's entire local Claude budget for one queue-drainer."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    assert not any(ln.startswith("*/20 * * * *") and "run_recommendation_worker.sh" in ln
                   for ln in man.splitlines())
    assert any(ln.startswith("0 * * * *") and "run_recommendation_worker.sh" in ln
               for ln in man.splitlines())


def test_capability_hunt_keeps_every_slice_after_the_cut() -> None:
    """THE LOAD-BEARING ONE. The six runs pass slice indices 0-5; a naive frequency cut would
    have dropped four slices and called it a cadence change. Every slice must still be scheduled."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    lines = [ln for ln in man.splitlines()
             if "run_capability_hunt.sh" in ln and (ln[:1].isdigit())]
    slices = sorted(ln.split("run_capability_hunt.sh ")[1].split()[0] for ln in lines)
    assert slices == ["0", "1", "2", "3", "4", "5"], f"slice coverage lost: {slices}"
    # ...and no single day carries more than two of them.
    from collections import Counter
    per_day: Counter = Counter()
    for ln in lines:
        for d in ln.split()[4].split(","):
            per_day[d] += 1
    assert max(per_day.values()) <= 2, f"a day still carries {max(per_day.values())} hunts"


def test_cro_ai_runs_once_daily() -> None:
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    assert any(ln.startswith("45 2 * * *") and "run_cro_ai.sh" in ln for ln in man.splitlines())
    assert "45 2,14,20 * * *" not in man


def test_worker_effort_is_capped_below_max() -> None:
    sh = (_REPO / "ops/run_recommendation_worker.sh").read_text("utf-8")
    assert "--effort high" in sh and "--effort max" not in sh.split("FALSIFIER")[-1]


def test_diggers_were_left_alone() -> None:
    """Explicitly pinned: the four discovery diggers are the desk's actual research surface and
    were RECOMMENDED to be left alone. A future cadence sweep must not quietly take them."""
    man = (_REPO / "ops/crontab.manifest").read_text("utf-8")
    for d in ("run_dataaxis_dig.sh", "run_frontier_rotation.sh",
              "run_prospector_dig.sh", "run_litminer_dig.sh"):
        n = sum(1 for ln in man.splitlines() if d in ln and ln[:1].isdigit())
        assert n >= 3, f"{d} lost scheduled runs ({n})"
