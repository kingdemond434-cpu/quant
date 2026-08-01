"""The external calibration, pinned -- including the two properties that make it safe to keep.

What these tests actually protect:

  1. THE CAVEAT. This module's whole risk is that somebody reads 1.25 and types it into a gate.
     The caveat is the only thing standing between the reader and that mistake, so its deletion is
     treated as a test failure in both places it lives -- the module docstring and the text
     `gap_report()` carries into JSON.
  2. THE DIRECTION OF EVERY RATIO. A floor is stricter when it is HIGHER; a position cap is
     stricter when it is LOWER. Get that inversion wrong and the report claims this desk is three
     times SAFER on concentration than an institutional pipeline when it is three times more
     concentrated. That row is asserted explicitly.
  3. THE UNKNOWN BRANCH. An unreadable input must not come back as COMPARABLE.
"""
from __future__ import annotations

import json
import math

import libs.validation.brain_calibration as bc
from libs.validation.brain_calibration import (
    BRAIN,
    BRAIN_IS_SCORE_WEIGHT,
    BRAIN_NEAR_SUBMITTABLE_FITNESS_SHORTFALL,
    BRAIN_NEAR_SUBMITTABLE_FRACTION,
    BRAIN_OOS_SCORE_WEIGHT,
    BRAIN_RECENT_SHARPE_FLOOR,
    BRAIN_RECENT_SHARPE_FLOOR_UPPER,
    BRAIN_SELF_CORRELATION_CAP,
    BRAIN_SHARPE_BAR,
    BRAIN_SHARPE_TARGET,
    BRAIN_STAGE2_ACCEPTANCE_FRACTION,
    BRAIN_TRUNCATION_BAND,
    BRAIN_TRUNCATION_DEFAULT,
    BRAIN_TS_BACKFILL_FITNESS_AFTER,
    BRAIN_TS_BACKFILL_FITNESS_BEFORE,
    DESK_REAL_EDGE_BAND,
    DESK_SENSITIVITY_FLOOR_SHARPE,
    SOURCE_NOTES,
    annualisation_caveat,
    compare,
    gap_report,
)
from libs.validation.robustness_filters import REAL_EDGE_OOS_SHARPE_BAND

#: Every load-bearing clause of the caveat, lowercased. Asserted phrase by phrase rather than as
#: one blob so that a partial deletion -- the likely accident, someone trimming "a wordy paragraph"
#: -- fails just as loudly as removing the whole thing.
CAVEAT_PHRASES = (
    "comparable in order of magnitude",
    "never be pasted into a gate",
    "misused this module",
    "us equity",
    "crypto perps",
    "1.25",
)


# --------------------------------------------------------------------------------- constants

def test_every_sharpe_constant_is_in_a_plausible_range():
    """A live pipeline's Sharpe thresholds live in single digits below ~3. Anything outside that
    is a transcription error, and a transcription error in a calibration reference propagates as
    confidence."""
    for name, value in (("sharpe_bar", BRAIN_SHARPE_BAR),
                        ("sharpe_target", BRAIN_SHARPE_TARGET),
                        ("recent_floor", BRAIN_RECENT_SHARPE_FLOOR),
                        ("recent_floor_upper", BRAIN_RECENT_SHARPE_FLOOR_UPPER)):
        assert 0.1 <= value <= 3.0, f"{name}={value}"
    assert BRAIN_RECENT_SHARPE_FLOOR <= BRAIN_RECENT_SHARPE_FLOOR_UPPER
    assert BRAIN_SHARPE_BAR <= BRAIN_SHARPE_TARGET, "the target cannot sit below the bar"


def test_every_fraction_constant_is_a_fraction():
    for name, value in (("is_weight", BRAIN_IS_SCORE_WEIGHT),
                        ("oos_weight", BRAIN_OOS_SCORE_WEIGHT),
                        ("near_submittable", BRAIN_NEAR_SUBMITTABLE_FRACTION),
                        ("fitness_shortfall", BRAIN_NEAR_SUBMITTABLE_FITNESS_SHORTFALL),
                        ("self_corr_cap", BRAIN_SELF_CORRELATION_CAP),
                        ("stage2_acceptance", BRAIN_STAGE2_ACCEPTANCE_FRACTION),
                        ("truncation_default", BRAIN_TRUNCATION_DEFAULT)):
        assert 0.0 < value < 1.0, f"{name}={value}"


def test_out_of_sample_carries_three_quarters_of_the_score():
    """The single most transferable number in the transcript, and the one most likely to be
    'simplified' later: a live pipeline weights in-sample at 25%."""
    assert BRAIN_IS_SCORE_WEIGHT == 0.25
    assert math.isclose(BRAIN_IS_SCORE_WEIGHT + BRAIN_OOS_SCORE_WEIGHT, 1.0)
    assert math.isclose(BRAIN.oos_score_weight, 0.75)


def test_truncation_default_sits_inside_its_stated_band():
    lo, hi = BRAIN_TRUNCATION_BAND
    assert 0.0 < lo < hi <= 0.20, BRAIN_TRUNCATION_BAND
    assert lo <= BRAIN_TRUNCATION_DEFAULT <= hi


def test_ts_backfill_example_is_an_improvement_of_a_believable_size():
    assert BRAIN_TS_BACKFILL_FITNESS_AFTER > BRAIN_TS_BACKFILL_FITNESS_BEFORE
    gain = BRAIN_TS_BACKFILL_FITNESS_AFTER / BRAIN_TS_BACKFILL_FITNESS_BEFORE - 1.0
    assert 0.0 < gain < 0.5, f"{gain:.3f} -- one data fix, not a new mechanism"
    assert math.isclose(gain, 0.109, abs_tol=0.005)


def test_desk_numbers_are_the_real_ones():
    """The desk side must be imported or cited, never retyped. If REAL_EDGE_OOS_SHARPE_BAND moves,
    this module must move with it rather than quietly comparing against a stale copy."""
    assert DESK_REAL_EDGE_BAND == REAL_EDGE_OOS_SHARPE_BAND
    assert DESK_SENSITIVITY_FLOOR_SHARPE == 5.0, "gate_power_audit.md §1: 85.42% power at SR 5.0"
    lo, hi = DESK_REAL_EDGE_BAND
    assert 0.0 < lo < hi < 3.0


def test_every_brain_constant_carries_a_confidence_marker_and_a_quote():
    """Several of these are spoken asides. An aside with no marker becomes a hard threshold six
    months later, so the marking is part of the data, not documentation."""
    named = [n for n in dir(bc) if n.startswith("BRAIN_")]
    assert len(named) >= 12
    for name in named:
        assert name in SOURCE_NOTES, f"{name} has no recorded provenance"
    for name, (confidence, quote) in SOURCE_NOTES.items():
        assert confidence in {"STATED", "APPROXIMATE", "DERIVED"}, name
        assert len(quote) > 10, f"{name} quote is too thin to audit"
    assert SOURCE_NOTES["BRAIN_SHARPE_TARGET"][0] == "APPROXIMATE", "1.25 was a spoken aside"
    assert SOURCE_NOTES["BRAIN_OOS_SCORE_WEIGHT"][0] == "DERIVED", "75% is never spoken"


# --------------------------------------------------------------------------------- compare()

def test_headline_gap_is_four_times():
    c = compare(DESK_SENSITIVITY_FLOOR_SHARPE, DESK_REAL_EDGE_BAND)
    assert c.stricter == "DESK"
    assert math.isclose(c.ratio_floor_to_target, 4.0)
    assert math.isclose(c.ratio_floor_to_bar, 5.0)
    assert math.isclose(c.ratio_floor_to_band_top, 5.0 / 1.5)
    assert "4.0x" in c.verdict and "DESK STRICTER" in c.verdict


def test_direction_flips_when_the_desk_floor_drops_below_the_external_bar():
    c = compare(0.5, (0.5, 1.5))
    assert c.stricter == "BRAIN"
    assert "BRAIN STRICTER" in c.verdict
    assert math.isclose(c.ratio_floor_to_target, 0.4)


def test_near_agreement_is_reported_as_comparable_rather_than_a_winner():
    """These conventions agree to an order of magnitude and no further. Declaring a winner on a
    few percent would be reading precision that provably is not there."""
    for floor in (1.1, 1.25, 1.4):
        assert compare(floor, (0.5, 1.5)).stricter == "COMPARABLE"


def test_ratio_scales_exactly_with_the_floor():
    for floor in (2.0, 5.0, 12.5):
        assert math.isclose(compare(floor, (0.5, 1.5)).ratio_floor_to_target,
                            floor / BRAIN_SHARPE_TARGET)


def test_unreadable_input_reports_unknown_and_never_comparable():
    """The ambiguous branch must BLOCK. A fabricated 4.0x is indistinguishable from a measured one
    once it is sitting in a report, so no ratio is produced at all."""
    bad = [
        (math.nan, (0.5, 1.5)),
        (math.inf, (0.5, 1.5)),
        (5.0, (math.nan, 1.5)),
        (0.0, (0.5, 1.5)),
        (-3.0, (0.5, 1.5)),
        (1e-9, (0.5, 1.5)),
        (5.0, (1.5, 0.5)),
        (5.0, (0.0, 0.0)),
    ]
    for floor, band in bad:
        c = compare(floor, band)
        assert c.stricter == "UNKNOWN", (floor, band, c.stricter)
        assert "UNCOMPARABLE" in c.verdict
        assert math.isnan(c.ratio_floor_to_bar)
        assert math.isnan(c.ratio_floor_to_target)
        assert math.isnan(c.ratio_floor_to_band_top)


def test_a_denominator_of_dust_produces_no_ratio_rather_than_a_huge_one():
    """`> 0` is not a floor. This desk shipped a 1.4e31 fake signal on 2026-08-01 by dividing by
    variance dust that cleared a `> 0` guard, and the same arithmetic is available here."""
    assert math.isnan(bc._ratio(5.0, 1e-12))
    assert math.isnan(bc._ratio(5.0, 0.0))
    assert math.isnan(bc._ratio(5.0, math.nan))


def test_summary_names_both_sides_and_the_ratio():
    s = compare(DESK_SENSITIVITY_FLOOR_SHARPE, DESK_REAL_EDGE_BAND).summary()
    assert "5.00" in s and "1.25" in s and "4.00x" in s and "DESK" in s


# --------------------------------------------------------------------------------- the caveat

def test_the_caveat_is_present_in_the_module_docstring():
    """A calibration module whose caveat got deleted is more dangerous than no calibration module:
    the numbers survive, the reason not to use them directly does not."""
    doc = (bc.__doc__ or "").lower()
    for phrase in CAVEAT_PHRASES:
        assert phrase in doc, f"caveat clause missing from module docstring: {phrase!r}"


def test_the_caveat_travels_with_the_report():
    text = annualisation_caveat().lower()
    for phrase in CAVEAT_PHRASES:
        assert phrase in text, f"caveat clause missing from annualisation_caveat(): {phrase!r}"
    assert annualisation_caveat() == gap_report()["caveat"]


def test_the_module_says_out_loud_that_it_is_not_a_gate():
    doc = (bc.__doc__ or "").lower()
    assert "calibration reference" in doc
    assert "no decision path" in doc
    assert gap_report()["status"].startswith("CALIBRATION REFERENCE")


# --------------------------------------------------------------------------------- gap_report()

def test_gap_report_is_strictly_json_serialisable():
    """allow_nan=False on purpose: json.dumps will happily emit bare NaN, which is not valid JSON
    and dies in whatever reads the artefact rather than here."""
    text = json.dumps(gap_report(), allow_nan=False, sort_keys=True)
    back = json.loads(text)
    assert back["rows"], "a report with no rows is not a report"
    assert back["comparison"]["stricter"] == "DESK"
    assert math.isclose(back["comparison"]["ratio_floor_to_target"], 4.0)


def test_every_row_carries_its_provenance_and_direction():
    for row in gap_report()["rows"]:
        assert row["brain_confidence"] in {"STATED", "APPROXIMATE", "DERIVED"}, row["quantity"]
        assert row["brain_quote"], row["quantity"]
        assert row["desk_source"], row["quantity"]
        assert row["direction"], row["quantity"]
        assert isinstance(row["brain_value"], float)


def test_a_cap_is_stricter_when_it_is_lower():
    """THE INVERSION ROW. The desk's 25% single-name cap against BRAIN's 8% default means the desk
    is three times MORE concentrated. Reporting every ratio as 'above 1 means stricter' would
    print that as a safety margin."""
    row = _row_named("max single-name weight")
    assert row["higher_is_stricter"] is False
    assert math.isclose(row["ratio_desk_over_brain"], 0.25 / 0.08)
    assert row["direction"].startswith("DESK LOOSER by 3.1x"), row["direction"]


def test_the_floor_row_reads_the_other_way():
    row = _row_named("gate sensitivity floor vs submission target (Sharpe)")
    assert row["higher_is_stricter"] is True
    assert row["direction"].startswith("DESK STRICTER by 4.0x"), row["direction"]


def test_the_two_independent_sources_agree_exactly_at_the_bottom_of_the_band():
    """The strongest row in the file: a 131,441-backtest sweep and a live institutional pipeline
    put the bottom of actionable edge at the same 0.5 Sharpe, from unrelated data."""
    row = _row_named("real-edge band, lower (OOS Sharpe)")
    assert math.isclose(row["ratio_desk_over_brain"], 1.0)
    assert row["direction"] == "COMPARABLE"


def test_absent_desk_checks_are_reported_as_absent_not_omitted_and_not_zero():
    """An absent check that vanishes from a comparison table reads as a passed one. Same defect
    class as a benchmark-less asset_drift gate returning True."""
    absent = [r for r in gap_report()["rows"] if r["desk_value"] is None]
    assert len(absent) >= 2
    for row in absent:
        assert row["ratio_desk_over_brain"] is None, "null, never 0.0 -- 0.0 is a measurement"
        assert "NO DESK COUNTERPART" in row["direction"]
        assert "ABSENT" in row["desk_source"]


def test_gap_report_accepts_an_alternative_desk_position():
    """The point of the module is to re-run the comparison after the gate moves, so the desk can
    see the gap close in a number rather than assert that it did."""
    r = gap_report(desk_floor_sharpe=1.3, desk_band=(0.5, 1.5))
    assert r["comparison"]["stricter"] == "COMPARABLE"
    assert math.isclose(r["comparison"]["ratio_floor_to_target"], 1.3 / 1.25)


def test_gap_report_stays_serialisable_when_the_comparison_is_unknown():
    r = gap_report(desk_floor_sharpe=math.nan, desk_band=(0.5, 1.5))
    assert r["comparison"]["stricter"] == "UNKNOWN"
    assert r["comparison"]["ratio_floor_to_target"] is None
    json.dumps(r, allow_nan=False)


def _row_named(quantity: str) -> dict:
    rows = [r for r in gap_report()["rows"] if r["quantity"] == quantity]
    assert len(rows) == 1, f"expected exactly one row named {quantity!r}, got {len(rows)}"
    return rows[0]
