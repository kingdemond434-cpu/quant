"""The information rate, pinned on the arithmetic that decides whether a speed-up is real.

THE FAILURE THIS FILE GUARDS AGAINST is a report that recommends breadth unconditionally. Widening
the cross-section is worth 64x at rho=0.7 and worth EXACTLY NOTHING at rho=1.0 -- 213 tickers on
one instrument -- and a recommender that cannot tell those apart would send the desk to spend a
month building a wider clock that earns no evidence at all.
"""

from __future__ import annotations

from libs.research.evidence_clock import EvidenceState, effective_n
from libs.research.information_rate import (
    accelerants,
    binding_constraint,
    cross_section_gain,
    measure,
)


def test_CROSS_SECTION_GAIN_IS_ONE_WHEN_THE_SYMBOLS_ARE_ONE_INSTRUMENT() -> None:
    """rho=1.0 is 213 tickers on a single instrument. The gain must be exactly 1.0, not 'small'."""
    assert cross_section_gain(213, 1.0) == 1.0
    assert cross_section_gain(1, 0.0) == 1.0


def test_CROSS_SECTION_GAIN_MATCHES_THE_DEFLATOR_IT_IS_DERIVED_FROM() -> None:
    """The formula is not asserted, it is `effective_n`'s own scaling with the raw multiplier
    put back. If the two ever disagree the report is recommending arithmetic the clock does not
    actually perform, so it is checked against the clock rather than against itself."""
    rho, sym, per_symbol = 0.7, 213, 40
    narrow = EvidenceState(raw_observations=per_symbol, distinct_symbols=1,
                           cross_symbol_rho=rho, distinct_regimes=3)
    wide = EvidenceState(raw_observations=per_symbol * sym, distinct_symbols=sym,
                         cross_symbol_rho=rho, distinct_regimes=3)
    measured = effective_n(wide) / effective_n(narrow)
    assert abs(measured - cross_section_gain(sym, rho)) < 1e-9


def test_CROSS_SECTION_GAIN_FALLS_AS_CORRELATION_RISES() -> None:
    gains = [cross_section_gain(213, r) for r in (0.0, 0.5, 0.7, 0.95, 1.0)]
    assert gains == sorted(gains, reverse=True)
    assert gains[0] > 200 and gains[-1] == 1.0


def test_THE_BINDING_CONSTRAINT_IS_THE_SMALLEST_MULTIPLIER() -> None:
    """They compose multiplicatively, so the smallest is the one worth fixing. A single regime
    (0.5) binds harder than mild serial correlation (0.82)."""
    s = EvidenceState(raw_observations=100, autocorrelation=0.1, distinct_regimes=1)
    name, mult = binding_constraint(s)
    assert name == "regime concentration" and mult == 0.5


def test_EVENT_CLUSTERING_IS_REPORTED_WHEN_IT_BINDS() -> None:
    """500 fills inside one cascade is ONE observation of one cascade -- the deflator a raw trade
    count hides completely."""
    s = EvidenceState(raw_observations=500, distinct_events=3, distinct_regimes=3)
    name, mult = binding_constraint(s)
    assert name == "event clustering"
    assert abs(mult - 3 / 500) < 1e-9


def test_HIGHER_FREQUENCY_IS_ATTENUATED_BY_SERIAL_CORRELATION() -> None:
    """The easiest way to manufacture evidence here would be to treat 3x the bars as 3x the
    information. Sampling one process faster does not make it more independent."""
    sticky = EvidenceState(raw_observations=40, autocorrelation=0.8, distinct_regimes=3)
    clean = EvidenceState(raw_observations=40, autocorrelation=0.0, distinct_regimes=3)
    a_sticky = next(a for a in accelerants(sticky, bars_per_day=1, available_bars_per_day=3)
                    if "bars/day" in a.lever)
    a_clean = next(a for a in accelerants(clean, bars_per_day=1, available_bars_per_day=3)
                   if "bars/day" in a.lever)
    assert a_clean.gain > a_sticky.gain
    assert a_clean.gain == 3.0
    assert a_sticky.gain < 1.1, "a highly autocorrelated series gains almost nothing from 3x bars"


def test_AN_ACCELERANT_THE_DESK_CANNOT_TAKE_IS_NOT_OFFERED() -> None:
    """No wider universe available means no cross-section lever. A speed report that lists data
    projects as if they were config changes is a wish list."""
    s = EvidenceState(raw_observations=40, distinct_symbols=5, cross_symbol_rho=0.5,
                      distinct_regimes=3)
    assert not [a for a in accelerants(s, available_symbols=5) if "cross-section" in a.lever]
    assert [a for a in accelerants(s, available_symbols=200) if "cross-section" in a.lever]


def test_ACCELERANTS_ARE_RANKED_BY_MEASURED_GAIN() -> None:
    s = EvidenceState(raw_observations=40, autocorrelation=0.3, distinct_symbols=1,
                      cross_symbol_rho=0.6, distinct_regimes=1)
    ranked = accelerants(s, available_symbols=213, bars_per_day=1, available_bars_per_day=3)
    assert [a.gain for a in ranked] == sorted([a.gain for a in ranked], reverse=True)
    assert "cross-section" in ranked[0].lever, (
        "at rho=0.6 across 213 symbols the breadth lever dominates by two orders of magnitude")


def test_THE_RATE_PROJECTS_A_REMAINING_WAIT() -> None:
    s = EvidenceState(raw_observations=40, distinct_regimes=3)
    r = measure("slow_clock", s, days_elapsed=40.0, required=100.0)
    assert r.effective_per_day is not None
    assert abs(r.effective_per_day - 1.0) < 1e-9
    assert r.days_remaining is not None and abs(r.days_remaining - 60.0) < 1e-9


def test_ZERO_ELAPSED_DAYS_PROJECTS_NOTHING(  ) -> None:
    """UNMEASURED is a real answer (L1.28a). A division that produced a confident infinity here
    would read as 'never graduates', which is a different and false claim."""
    r = measure("day_zero", EvidenceState(raw_observations=0), days_elapsed=0.0)
    assert r.effective_per_day is None and r.days_remaining is None


def test_A_CLOCK_THAT_HAS_ARRIVED_OWES_ZERO_MORE_DAYS() -> None:
    s = EvidenceState(raw_observations=400, distinct_regimes=3)
    r = measure("done", s, days_elapsed=40.0, required=30.0)
    assert r.days_remaining == 0.0


def test_THE_REPORT_NEVER_LOWERS_THE_REQUIREMENT() -> None:
    """`required` is an input and appears unchanged in the output. Every lever here changes how
    fast evidence ARRIVES; the one edit that would make the exercise self-defeating is changing
    how much is needed."""
    s = EvidenceState(raw_observations=40, distinct_regimes=1)
    r = measure("x", s, days_elapsed=40.0, required=30.0, available_symbols=213)
    assert r.required == 30.0
    assert r.as_row()["required"] == 30.0


def test_THE_ROW_IS_JSON_SHAPED() -> None:
    s = EvidenceState(raw_observations=40, distinct_regimes=2, distinct_symbols=3,
                      cross_symbol_rho=0.4)
    row = measure("c", s, days_elapsed=10.0, available_symbols=100).as_row()
    import json
    assert json.loads(json.dumps(row))["clock"] == "c"
    assert row["accelerants"] and "gain" in row["accelerants"][0]
