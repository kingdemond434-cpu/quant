"""A PROMOTION CANDIDATE's verdict is re-taken on its current ledger every pass.

Measured 2026-11-04: 11 of 131 candidates on live shadow_state.json no longer cleared the bar
that promoted them (US30 car asia: +0.117R at maturity, -0.135R at n=130), yet five readers
counted them as positive evidence because the verdict was taken once and never revisited.
"""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK))

import shadow_forward as sf  # noqa: E402


def test_a_candidate_that_still_clears_the_bar_is_kept():
    st = {"n": 48, "exp_r": 0.664, "max_dd_r": -2.46}
    assert sf.lapsed_candidate(st) is None


def test_negative_expectancy_lapses():
    why = sf.lapsed_candidate({"n": 130, "exp_r": -0.1346, "max_dd_r": -26.1})
    assert why and "n=130" in why


def test_positive_but_below_the_promotion_bar_lapses():
    # EURZAR carry: +0.0406R is positive but not > PROMOTE_MIN_EXP (0.05).
    assert sf.lapsed_candidate({"n": 134, "exp_r": 0.0406, "max_dd_r": -12.0})


def test_drawdown_through_the_bar_lapses():
    assert sf.lapsed_candidate({"n": 90, "exp_r": 0.2, "max_dd_r": sf.PROMOTE_MIN_DD - 0.1})


def test_the_bar_is_the_maturity_bar_itself():
    edge = {"n": 60, "exp_r": sf.PROMOTE_MIN_EXP, "max_dd_r": -1.0}
    assert sf.lapsed_candidate(edge)          # maturity needs exp > MIN, so == MIN lapses
    above = {"n": 60, "exp_r": sf.PROMOTE_MIN_EXP + 1e-9, "max_dd_r": sf.PROMOTE_MIN_DD + 1e-9}
    assert sf.lapsed_candidate(above) is None


def test_an_unmeasured_row_is_never_demoted():
    assert sf.lapsed_candidate({"n": 60, "exp_r": "UNMEASURED", "max_dd_r": -1.0}) is None
    assert sf.lapsed_candidate({"n": 60}) is None


def _row(**kw):
    base = {"status": "PROMOTION CANDIDATE", "n": 130, "exp_r": -0.1346, "max_dd_r": -26.1,
            "forward_start": "2026-09-26T00:00:00+00:00"}
    base.update(kw)
    return base


def test_a_lapsed_non_live_candidate_is_demoted_with_its_missed_growth_line():
    st = _row()
    act = sf.rejudge_candidate("K", st, 40.0, live=lambda _k: False)
    assert act and act.startswith("VERDICT LAPSED")
    assert st["status"] == "KILL" and st["demoted_from"] == "PROMOTION CANDIDATE"
    assert st["forward_start"] == "2026-09-26T00:00:00+00:00"      # the clock is not touched
    mg = st["rejudge_missed_growth"]
    assert mg["status"] == "MEASURED" and mg["r_per_day_forgone"] == 0.0
    assert mg["trades_per_day"] == 130 / 40.0 and mg["order_authority"] is False


def test_a_live_candidate_is_never_demoted():
    st = _row()
    assert sf.rejudge_candidate("K", st, 40.0, live=lambda _k: True) is None
    assert st["status"] == "PROMOTION CANDIDATE"


def test_an_unreadable_registry_leaves_the_verdict_and_says_so():
    st = _row()
    assert sf.rejudge_candidate("K", st, 40.0, live=lambda _k: None) is None
    assert st["status"] == "PROMOTION CANDIDATE" and st["rejudge"].startswith("UNMEASURED")


def test_two_sided_a_demoted_row_that_clears_the_bar_again_is_restored():
    st = _row()
    sf.rejudge_candidate("K", st, 40.0, live=lambda _k: False)
    st.update({"n": 190, "exp_r": 0.12, "max_dd_r": -20.0})   # the clock kept accruing
    act = sf.rejudge_candidate("K", st, 60.0, live=lambda _k: False)
    assert act and act.startswith("VERDICT RESTORED")
    assert st["status"] == "PROMOTION CANDIDATE"
    assert "demoted_from" not in st and len(st["demotions_before"]) == 1
    assert st["rejudge_missed_growth"]["r_per_day_forgone"] > 0


def test_a_maturity_kill_is_never_restored_by_this_rule():
    st = _row(status="KILL", exp_r=0.3, max_dd_r=-2.0)          # no demoted_from
    assert sf.rejudge_candidate("K", st, 40.0, live=lambda _k: False) is None
    assert st["status"] == "KILL"


def test_a_demoted_row_still_below_the_bar_stays_demoted():
    st = _row()
    sf.rejudge_candidate("K", st, 40.0, live=lambda _k: False)
    assert sf.rejudge_candidate("K", st, 41.0, live=lambda _k: False) is None
    assert st["status"] == "KILL"


def test_the_pass_calls_the_rejudge_for_every_row_past_the_maturity_branch():
    src = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    assert "_act = rejudge_candidate(key, st, days_active)" in src
