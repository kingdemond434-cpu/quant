"""R0143 return targeting -- no stated return number may become an objective.

Doctrine since 2026-07-12: "Don't chase a CAGR target (targeting a return number corrupts a
survival-constrained optimizer into over-leverage). Max safe growth; let the number fall out."
Three prior rulings existed and a "What 300% net CAGR actually requires" section still landed,
caught by the principal rather than by a check.
"""
from __future__ import annotations

from scripts.check_return_targeting import build_report, scan_text


def test_it_catches_the_exact_regression_that_produced_it():
    hits = scan_text("## What 300% net CAGR actually requires\n"
                     "Growth is g x N. The target needs roughly a 38% hit rate.")
    assert hits and hits[0]["figure"].startswith("300")


def test_analysis_numbers_are_not_targets():
    # Return figures are legitimate and necessary as analysis. A fence that flagged every
    # percentage would be switched off within a day, and the doctrine would be unenforced again.
    for ok in ("Cost-adjusted breakeven is 31.1%, not 25%.",
               "the kill floor is 25% -- a standard error below breakeven",
               "measured noise is 0.64% on PAXG and 1.28% on SOL",
               "at 20% risk per trade P(-90% drawdown) is 96%"):
        assert scan_text(ok) == [], ok


def test_stating_a_target_in_order_to_forbid_it_is_allowed():
    # Without this the doctrine line itself trips the fence -- an own goal in the literal sense.
    assert scan_text("Don't chase a CAGR target; targeting a return number corrupts a "
                     "survival-constrained optimizer into over-leverage.") == []
    assert scan_text("There is deliberately no CAGR target in this document, and a 300% figure "
                     "is not something to hit.") == []


def test_coverage_percentages_are_not_return_figures():
    # First live run flagged three of these in the constitution: 100% is overwhelmingly a COVERAGE
    # figure on this desk (ratchet floors, breadth), not a return.
    assert scan_text("every metric is a RATCHET and the target is 100% breadth coverage") == []
    assert scan_text("conversion must push to 100% daily -- that is the goal") == []


def test_a_target_split_across_a_line_wrap_is_still_caught():
    assert scan_text("our stated target for this sleeve, once the clock has run,\n"
                     "is a 300% net CAGR") != []


def test_the_governed_surfaces_are_clean_now():
    rep = build_report()
    assert rep["status"] == "OK", rep["detail"]


def test_an_unreadable_governed_file_is_not_a_pass(tmp_path):
    rep = build_report(tmp_path)
    assert rep["status"] == "UNMEASURED" and rep["unreadable"]


def test_the_fence_states_that_removing_a_target_is_not_timidity():
    rep = build_report()
    assert "NOT a reduction in ambition" in rep["not_timidity"]
    assert "L1.28" in rep["not_timidity"]
