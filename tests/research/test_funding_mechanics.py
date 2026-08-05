"""VENUE FUNDING MECHANICS (L1.47) -- the visible FR is a transformed PI, and the transform bites.

Every test here pins a MECHANISM, not a number the implementation happens to produce. The five
facts came from a venue-mechanics primer (muzineco, Advent Calendar 2023 day 8) and each one
corrupts a carry estimate silently: a clamp that throws away 10bp of premium per print, an impact
notional that varies ~7000x across symbols on one venue, an interval that switches under a
fixed-grid join, a payment that lands a period after the stamp it is joined on, and a cap that
turns a measurement into a censored lower bound.

THE REFUSAL TESTS MATTER MOST. An unknown venue must return None everywhere. The defect being
prevented is not "a wrong constant" -- it is a caller silently receiving Binance mechanics for a
venue nobody read, which is how a look-ahead gets into a screen while every function looks fine.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from libs.research.funding_mechanics import (
    BP,
    comparable_across_venues,
    detect_cap_events,
    detect_interval_switches,
    fr_is_pinned,
    hidden_carry_spread_bp,
    imn_depth_context,
    is_cap_pinned,
    mechanics,
    payment_stamp,
    pi_range_from_fr,
    settlement_lag_periods,
    uniform_interval,
    verify_funding_series,
)

_T0 = datetime(2026, 8, 1, tzinfo=UTC)


# ---------------------------------------------------------------- 1. the clamp dead-band
def test_the_interest_anchor_print_hides_a_ten_bp_pi_range():
    """The headline fact: FR == 0.01% on Binance says only that PI was in [-0.04%, +0.06%]."""
    r = pi_range_from_fr(0.0001, "binance")
    assert r is not None and r.pinned
    assert r.lo == pytest.approx(-0.0004)
    assert r.hi == pytest.approx(0.0006)
    assert r.width_bp == pytest.approx(10.0)


def test_a_print_outside_the_dead_band_inverts_to_an_exact_point():
    """Escaped prints carry full information -- the range must collapse, not stay conservative."""
    hi = pi_range_from_fr(0.0006, "binance")     # above the anchor -> P = F + half
    assert hi is not None and not hi.pinned
    assert hi.lo == hi.hi == pytest.approx(0.0011)

    lo = pi_range_from_fr(-0.0006, "binance")    # below the anchor -> P = F - half
    assert lo is not None and not lo.pinned
    assert lo.lo == lo.hi == pytest.approx(-0.0011)
    assert lo.width_bp == 0.0


def test_the_inversion_round_trips_through_the_venue_formula():
    """Independent check: push PI through F = P + clamp(I - P, +-half) and invert it back."""
    interest, half = 0.0001, 0.0005
    for pi in (-0.004, -0.0011, -0.0004, 0.0, 0.0006, 0.0011, 0.004):
        fr = pi + max(-half, min(half, interest - pi))
        got = pi_range_from_fr(fr, "binance")
        assert got is not None
        assert got.lo - 1e-12 <= pi <= got.hi + 1e-12, f"PI {pi} fell outside its own inversion"


def test_okx_has_no_clamp_so_fr_is_pi_exactly():
    """The venues are NOT interchangeable -- this is the whole reason the table exists."""
    r = pi_range_from_fr(0.0001, "okx")
    assert r is not None and not r.pinned
    assert r.lo == r.hi == pytest.approx(0.0001)
    assert fr_is_pinned(0.0001, "okx") is False
    assert fr_is_pinned(0.0001, "binance") is True


def test_dydx_additive_offset_is_removed_before_inversion():
    r = pi_range_from_fr(0.0001 + 0.0000125, "dydx")
    assert r is not None and r.lo == pytest.approx(0.0001)


def test_cross_venue_fr_comparison_is_refused_when_quantization_differs():
    """Ranking a quantized series against an unquantized one partly ranks the transform."""
    assert comparable_across_venues(["binance", "bybit"]) is True
    assert comparable_across_venues(["binance", "okx"]) is False
    assert comparable_across_venues(["binance", "kraken"]) is False   # unread venue


# ---------------------------------------------------------------- 2. IMN-scaled depth
def test_a_thin_alt_book_is_flagged_against_the_btc_reference():
    """~$120 of HNT book against ~$880k of BTC -- an FR extreme is not the same evidence."""
    hnt = imn_depth_context(120.0)
    assert hnt.thin and hnt.ratio < 0.001
    assert "THIN" in hnt.note

    btc = imn_depth_context(880_000.0)
    assert not btc.thin and btc.ratio == pytest.approx(1.0)


def test_the_thinness_threshold_is_the_callers_to_own():
    """It is a STATED PRIOR, not a measurement, so it must be overridable rather than baked in."""
    assert imn_depth_context(10_000.0, thin_ratio=0.001).thin is False
    assert imn_depth_context(10_000.0, thin_ratio=0.5).thin is True


# ---------------------------------------------------------------- 3. interval switching
def test_an_8h_to_4h_switch_is_located_not_averaged():
    stamps = [_T0 + timedelta(hours=8 * i) for i in range(4)]
    stamps += [stamps[-1] + timedelta(hours=4 * i) for i in range(1, 4)]
    got = detect_interval_switches(stamps)
    assert len(got) == 1
    _, before, after = got[0]
    assert (before, after) == pytest.approx((8.0, 4.0))


def test_a_switched_series_refuses_to_report_a_single_interval():
    """A mean interval across a switch describes no period of the series. Refuse, do not average."""
    steady = [_T0 + timedelta(hours=8 * i) for i in range(5)]
    assert uniform_interval(steady) == pytest.approx(8.0)

    switched = steady + [steady[-1] + timedelta(hours=2 * i) for i in range(1, 4)]
    assert uniform_interval(switched) is None


def test_too_few_stamps_report_no_switch_rather_than_inventing_one():
    assert detect_interval_switches([_T0, _T0 + timedelta(hours=8)]) == []
    assert uniform_interval([_T0]) is None


# ---------------------------------------------------------------- 4. payment-timing alignment
def test_okx_and_bitmex_pay_one_period_late_and_the_others_do_not():
    """THE LOOK-AHEAD FENCE. Joining on the computation stamp reads an unpaid payment."""
    assert settlement_lag_periods("okx") == 1
    assert settlement_lag_periods("bitmex") == 1
    assert settlement_lag_periods("binance") == 0
    assert settlement_lag_periods("bybit") == 0


def test_payment_stamp_shifts_exactly_one_interval_on_the_late_venues():
    assert payment_stamp(_T0, "binance", 8.0) == _T0
    assert payment_stamp(_T0, "okx", 8.0) == _T0 + timedelta(hours=8)
    assert payment_stamp(_T0, "bitmex", 4.0) == _T0 + timedelta(hours=4)


def test_payment_stamp_refuses_a_nonpositive_interval():
    assert payment_stamp(_T0, "binance", 0.0) is None


# ---------------------------------------------------------------- 5. discretionary caps
def test_a_print_sitting_on_a_cap_is_a_censored_lower_bound():
    assert is_cap_pinned(0.0075, "binance") is True
    assert is_cap_pinned(-0.0075, "binance") is True      # sign-symmetric ladder
    assert is_cap_pinned(0.0050, "binance") is False


def test_dydx_is_uncapped_so_nothing_is_ever_cap_pinned():
    """The tail is genuinely unbounded there -- claiming a cap would invent a ceiling."""
    assert mechanics("dydx").caps == ()
    assert is_cap_pinned(0.03, "dydx") is False


def test_a_cap_ladder_move_is_detected_and_ordinary_variation_is_not():
    series = [(_T0 + timedelta(hours=8 * i), r) for i, r in
              enumerate([0.00375, 0.00375, 0.0020, 0.0075, 0.0075])]
    got = detect_cap_events(series, "binance")
    assert len(got) == 1
    _, old, new = got[0]
    assert (old, new) == pytest.approx((0.00375, 0.0075))

    quiet = [(_T0 + timedelta(hours=8 * i), r) for i, r in enumerate([0.0001, 0.0002, 0.0003])]
    assert detect_cap_events(quiet, "binance") == []


# ---------------------------------------------------------------- the refusal path
@pytest.mark.parametrize("fn,args", [
    (pi_range_from_fr, (0.0001,)),
    (fr_is_pinned, (0.0001,)),
    (hidden_carry_spread_bp, (0.0001,)),
    (settlement_lag_periods, ()),
    (is_cap_pinned, (0.0001,)),
])
def test_every_entry_point_refuses_an_unread_venue(fn, args):
    """THE DEFECT THIS PREVENTS is a caller silently getting Binance mechanics for a venue nobody
    read -- which is how a full-period look-ahead enters a screen with no symptom."""
    assert fn(*args, "kraken") is None


def test_mechanics_are_only_present_for_venues_actually_read():
    assert mechanics("kraken") is None
    assert mechanics("") is None
    assert mechanics("BINANCE").venue == "binance"      # case/whitespace tolerant, not guessing


# ---------------------------------------------------------------- the verification layer
def test_the_checklist_refuses_an_unread_venue_rather_than_reporting_clean():
    """An unmeasured series must never read as a healthy one (L1.28a)."""
    rep = verify_funding_series(venue="kraken", stamps=[_T0], rates=[0.0001])
    assert rep["status"] == "REFUSED"
    assert "binance" in rep["known_venues"]


def test_the_checklist_names_every_condition_it_finds():
    stamps = [_T0 + timedelta(hours=8 * i) for i in range(3)]
    stamps += [stamps[-1] + timedelta(hours=4 * i) for i in range(1, 3)]
    rates = [0.0001, 0.0001, 0.00375, 0.0075, 0.0002]
    rep = verify_funding_series(venue="okx", stamps=stamps, rates=rates, imn_usd=120.0)

    assert rep["status"] == "CONDITIONS"
    assert rep["interval_switches"] == 1
    assert rep["cap_events"] == 1
    assert rep["capped_prints"] == 2
    assert rep["pays_one_period_late"] is True
    assert rep["uniform_interval_h"] is None
    blob = " ".join(rep["findings"])
    assert "ONE PERIOD LATE" in blob and "THIN" in blob and "CENSORED" in blob


def test_the_checklist_reports_clean_on_a_well_behaved_series():
    stamps = [_T0 + timedelta(hours=8 * i) for i in range(4)]
    rep = verify_funding_series(venue="binance", stamps=stamps,
                                rates=[0.0006, 0.0007, 0.0008, 0.0009])
    assert rep["status"] == "CLEAN"
    assert rep["findings"] == []
    assert rep["uniform_interval_h"] == pytest.approx(8.0)


def test_the_checklist_refuses_misaligned_inputs():
    """A silent zip() truncation here would drop the tail of a series without a word."""
    with pytest.raises(ValueError, match="align 1:1"):
        verify_funding_series(venue="binance", stamps=[_T0], rates=[0.0001, 0.0002])


def test_bp_constant_is_the_desks_stored_unit():
    """Rates are decimal fractions (crypto_source.py stores float(fundingRate)), not percents."""
    assert BP == 0.0001
    assert hidden_carry_spread_bp(0.0001, "binance") == pytest.approx(10.0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
