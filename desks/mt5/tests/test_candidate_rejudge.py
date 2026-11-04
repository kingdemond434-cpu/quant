"""A PROMOTION CANDIDATE's verdict is re-taken on its current ledger every pass.

Measured 2026-11-04: 11 of 131 candidates on live shadow_state.json no longer cleared the bar
that promoted them (US30 car asia: +0.117R at maturity, -0.135R at n=130), yet five readers
counted them as positive evidence because the verdict was taken once and never revisited.
"""
from __future__ import annotations

import ast
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


def test_only_a_non_live_candidate_is_demoted_and_the_clock_is_not_withdrawn():
    """The demotion branch must gate on the registry's live set and only rewrite status."""
    src = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    hits = [n for n in ast.walk(tree) if isinstance(n, ast.If)
            and isinstance(n.test, ast.Compare)
            and isinstance(n.test.left, ast.Name) and n.test.left.id == "_live"
            and any(isinstance(c, ast.Constant) and c.value is False
                    for c in n.test.comparators)]
    assert len(hits) == 1, "the demotion must run only when the registry says NOT live"
    body = ast.unparse(hits[0])
    assert "'KILL'" in body and "demoted_from" in body
    for forbidden in ("forward_start", "retire", "del state", "pop("):
        assert forbidden not in body, f"demotion must not touch {forbidden}"
