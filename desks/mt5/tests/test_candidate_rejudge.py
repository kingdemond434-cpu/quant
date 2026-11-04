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


def test_lapse_kill_recover_restores_with_forward_start_unchanged_throughout():
    start = "2026-09-26T00:00:00+00:00"
    st = _row(n=130, cum_r=-17.5, exp_r=-0.1346, forward_start=start)
    sf.rejudge_candidate("K", st, 40.0, live=lambda _k: False)
    assert st["status"] == "KILL" and st["forward_start"] == start
    assert st["demoted_n"] == 130 and st["demoted_cum_r"] == -17.5
    # 70 more trades at +0.5R each: the ledger recovers past the bar.
    st.update({"n": 200, "cum_r": 17.5, "exp_r": 0.0875, "max_dd_r": -20.0})
    act = sf.rejudge_candidate("K", st, 60.0, live=lambda _k: False)
    assert act and "RESTORED" in act
    assert st["status"] == "PROMOTION CANDIDATE" and st["forward_start"] == start
    assert st["restored_at"] and "clears the maturity bar" in st["restored_why"]
    hist = st["demotions_before"][0]
    assert hist["n_at_demotion"] == 130 and hist["since"] == {"n": 70, "exp_r": 0.5}
    assert "n" in st and st["n"] == 200                   # no counter reset, no new clock


def test_the_report_bills_each_demotion_against_the_candidates_it_kept():
    kept = _row(status="PROMOTION CANDIDATE", n=60, cum_r=12.0, exp_r=0.2, max_dd_r=-3.0)
    gone = _row(n=130, cum_r=-17.5)
    sf.rejudge_candidate("G", gone, 40.0, live=lambda _k: False)
    gone.update({"n": 145, "cum_r": -19.0, "exp_r": -0.131})      # 15 trades at -0.1R since
    back = _row(n=100, cum_r=-1.0, exp_r=-0.01)
    sf.rejudge_candidate("B", back, 40.0, live=lambda _k: False)
    back.update({"n": 120, "cum_r": 9.0, "exp_r": 0.075, "max_dd_r": -5.0})
    sf.rejudge_candidate("B", back, 50.0, live=lambda _k: False)
    rep = sf.rejudge_report({"K": kept, "G": gone, "B": back, "updated_at": "x"}, at="now")
    by = {(ln["key"], ln["event"]): ln for ln in rep["missed_growth"]}
    assert by[("G", "demoted")]["n_since"] == 15
    assert abs(by[("G", "demoted")]["exp_since"] + 0.1) < 1e-12
    assert by[("G", "demoted")]["verdict"] == "EARNS_ITS_PLACE"
    assert by[("B", "restored")]["exp_since"] == 0.5
    assert by[("B", "restored")]["verdict"] == "COSTS_GROWTH"
    assert rep["kept_candidates"] == 2 and rep["n_demoted_now"] == 1 and rep["n_restored"] == 1


def test_a_fresh_demotion_is_unmeasured_not_a_clean_verdict():
    gone = _row(n=130, cum_r=-17.5)
    sf.rejudge_candidate("G", gone, 40.0, live=lambda _k: False)
    rep = sf.rejudge_report({"G": gone}, at="now")
    assert rep["missed_growth"][0]["verdict"] == "UNMEASURED"


def test_missed_growth_carries_the_rejudge_lines():
    import missed_growth as mg
    assert mg.CANDIDATE_REJUDGE.name == "candidate_rejudge_shadow_state.json"
    src = (DESK / "research" / "missed_growth.py").read_text(encoding="utf-8")
    assert '"shadow_candidate_rejudge": organ_published_lines(' in src
