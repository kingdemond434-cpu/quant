"""R0123: a PASS is graded against the same horizon as a call, and CANNOT move position size.

Two properties are pinned here and the second one is the safety-critical half. Grading declines is
the point; keeping them out of the pool that shrinks live Kelly probabilities is what makes it safe
to do.
"""
from __future__ import annotations

import json

import pytest

from libs.research.decline_value import (
    DECLINE_KINDS,
    MIN_DECLINES,
    Decline,
    filter_verdict,
    forgone_bps,
    grade,
    make_decline,
    pass_rate,
    scoreable,
)


def _row(**kw):
    base = {"action": "PASS", "symbol": "BTCUSDT", "direction": "LONG", "horizon_hours": 8,
            "probability": 0.62, "pass_reason": "already priced",
            "at": "2026-08-01T00:00:00+00:00", "resolve_by": "2026-08-01T08:00:00+00:00"}
    base.update(kw)
    return base


def _declines(n: int, hits: int) -> list[Decline]:
    return [Decline(key=f"k{i}", symbol="BTCUSDT", direction="LONG", probability=0.6,
                    entry_px=100.0, exit_px=101.0 if i < hits else 99.0,
                    would_have_been_right=i < hits,
                    forgone_bps=100.0 if i < hits else -100.0, pass_reason="no mechanism")
            for i in range(n)]


# ---- grading arithmetic ----------------------------------------------------------------

def test_direction_decides_what_right_means() -> None:
    assert grade("LONG", 100.0, 101.0) is True
    assert grade("LONG", 100.0, 99.0) is False
    assert grade("SHORT", 100.0, 99.0) is True
    assert grade("SHORT", 100.0, 101.0) is False


def test_a_flat_market_grades_both_directions_wrong() -> None:
    """Not a tiebreak. A flat market pays neither leg and still charges two round trips, so
    declining it was correct on BOTH sides -- crediting a flat tape as a hit would manufacture a
    'the filter cost us money' reading out of nothing happening."""
    assert grade("LONG", 100.0, 100.0) is False
    assert grade("SHORT", 100.0, 100.0) is False


def test_forgone_bps_is_signed_by_the_declined_direction() -> None:
    assert forgone_bps("LONG", 100.0, 101.0) == 100.0      # declining cost 100bps
    assert forgone_bps("SHORT", 100.0, 101.0) == -100.0    # declining SAVED 100bps
    assert forgone_bps("LONG", 0.0, 101.0) == 0.0          # refuses to divide by a zero price


def test_unknown_direction_raises_rather_than_guessing() -> None:
    with pytest.raises(ValueError):
        grade("SIDEWAYS", 100.0, 101.0)


# ---- what is gradeable at all ----------------------------------------------------------

def test_a_decline_with_no_symbol_is_ungradeable_and_says_so() -> None:
    """Book row 1 (2026-07-31) carries no symbol. It must be REFUSED, not silently dropped: an
    ungradeable decline that vanishes from the accounting is how the trap stays invisible."""
    ok, why = scoreable(_row(symbol=None))
    assert not ok and "no symbol" in why


def test_a_decline_with_no_direction_is_ungradeable() -> None:
    ok, why = scoreable(_row(direction=None))
    assert not ok and "LONG/SHORT" in why


def test_a_decline_without_a_pre_registered_horizon_is_not_a_forecast() -> None:
    ok, why = scoreable(_row(resolve_by=None))
    assert not ok and "L1.29" in why


def test_a_complete_decline_is_scoreable() -> None:
    ok, why = scoreable(_row())
    assert ok and why == "scoreable"


def test_make_decline_carries_the_models_own_probability() -> None:
    d = make_decline(_row(), 100.0, 101.0, key="k")
    assert d.would_have_been_right and d.probability == 0.62 and d.forgone_bps == 100.0


# ---- the verdict bands -----------------------------------------------------------------

def test_a_coin_flip_filter_is_the_GOOD_case() -> None:
    """The reading that is easiest to get backwards: ~50% is the filter WORKING. A coin-flip
    trade is a losing trade once fees are paid."""
    v = filter_verdict(_declines(40, 20))
    assert v["verdict"] == "WORKING-AS-INTENDED"
    assert "GOOD case" in v["why"]


def test_declining_winners_is_flagged_as_destroying_value() -> None:
    v = filter_verdict(_declines(40, 34))
    assert v["verdict"] == "DESTROYING-VALUE"
    assert v["z_vs_fair_coin"] > 2.0


def test_declining_losers_is_flagged_as_adding_value() -> None:
    v = filter_verdict(_declines(40, 6))
    assert v["verdict"] == "ADDING-VALUE"


def test_a_small_sample_is_UNMEASURED_however_extreme_it_reads() -> None:
    """The live case on 2026-08-05: 6 declines, 67% right. That is not a finding, and calling it
    one would be the premature-surrender error pointed the other way."""
    v = filter_verdict(_declines(6, 4))
    assert v["verdict"] == "UNMEASURED"
    assert f"6/{MIN_DECLINES}" in v["why"]
    assert "lower bar" in v["why"]                          # the fix is more declines, not a nudge


def test_no_declines_is_unmeasured_not_zero() -> None:
    v = filter_verdict([])
    assert v["verdict"] == "UNMEASURED" and "not the same as none" in v["why"]


# ---- the participation half ------------------------------------------------------------

def test_an_all_pass_book_is_flagged_however_calibrated_it_looks() -> None:
    """A filter can be perfectly calibrated on its declines and still contribute nothing by
    declining everything. That is a property of the BOOK, invisible in any single row."""
    r = pass_rate([{"action": "PASS"}] * 9)
    assert r["flag"] == "ALL-PASS" and r["n_call"] == 0
    assert "NEVER made a call" in r["why"]


def test_a_mixed_book_is_ok() -> None:
    r = pass_rate([{"action": "PASS"}] * 6 + [{"action": "CALL"}] * 4)
    assert r["flag"] == "OK" and r["pass_rate"] == 0.6


def test_an_empty_book_is_empty_not_ok() -> None:
    assert pass_rate([])["flag"] == "EMPTY"


# ---- THE SAFETY PROPERTY: declines must never move live position size ------------------

def test_declines_are_excluded_from_the_sizing_calibration_pool(tmp_path, monkeypatch) -> None:
    """THE ONE THAT MATTERS. report()'s bias is consumed by calibrated_confidence, which shrinks
    the probability run_conviction_trader hands to kelly_leverage. Declines are asserted mostly at
    p=0.50 and would swamp the handful of real calls -- moving LIVE POSITION SIZE on trades the
    desk never took. This desk has already paid for that once: a mis-pooled calibration set
    inverted the measured bias and sized a self-rated no-edge call at 6.00x, because the risk cap
    bounds SIZE and can never restore the SIGN of an edge."""
    import libs.self_improvement.forecast_calibration as fc
    store = tmp_path / "forecast_log.json"
    monkeypatch.setattr(fc, "_LOG", store)

    # Five real calls, every one of them WRONG at high confidence -> strongly over-confident.
    for i in range(5):
        fc.log_forecast(f"call:{i}", 0.9, "discretionary",
                        resolve_by="2026-08-01T00:00:00+00:00", claim=f"call {i}")
        fc.resolve(f"call:{i}", False)
    sizing = fc.report()
    assert sizing["n_resolved"] == 5 and sizing["bias"] == pytest.approx(0.9)

    # Forty declines, all right, at p=0.5. Pooled, they would drag the bias from +0.9 to ~+0.14
    # and hand live sizing a near-zero correction on a book that is badly over-confident.
    for i in range(40):
        fc.log_forecast(f"llm_trader:pass:{i}", 0.5, "discretionary_pass",
                        resolve_by="2026-08-01T00:00:00+00:00", claim=f"DECLINED {i}")
        fc.resolve(f"llm_trader:pass:{i}", True)

    after = fc.report()
    assert after["n_resolved"] == 5, "declines leaked into the sizing pool"
    assert after["bias"] == pytest.approx(0.9), "declines moved the bias that sizes live capital"
    assert after["n_excluded"]["non_sizing_kind"] == 40    # excluded, and SAID so -- never hidden

    # And they are still visible when explicitly asked for -- excluded, not discarded.
    whole = fc.report(exclude_kinds=())
    assert whole["n_resolved"] == 45


def test_backfilled_declines_are_also_out_of_the_sizing_pool() -> None:
    """Both decline kinds are excluded. A retroactively registered row is weaker evidence, not
    stronger, so it must not reach sizing either."""
    import libs.self_improvement.forecast_calibration as fc
    assert set(DECLINE_KINDS) == set(fc.NON_SIZING_KINDS)
    assert "discretionary_pass_backfill" in fc.NON_SIZING_KINDS
    assert "discretionary" not in fc.NON_SIZING_KINDS       # real calls DO size


def test_the_live_report_if_present_is_internally_consistent() -> None:
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "reports/llm_trader_decline_value.json"
    if not p.exists():
        pytest.skip("grader has not run on this box")
    rep = json.loads(p.read_text("utf-8"))
    assert rep["declines"]["n_declines"] == len(rep["graded_detail"])
    assert rep["participation"]["n_pass"] + rep["participation"]["n_call"] <= rep[
        "participation"]["n_rows"]
