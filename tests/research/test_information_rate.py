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


# ============================================================ the universe count (VPS regression)

def test_THE_UNIVERSE_IS_COUNTED_AT_THE_SYMBOL_DEPTH(tmp_path, monkeypatch) -> None:
    """MEASURED ON THE LIVE BOX 2026-08-14: this reported `1 symbol` on a desk holding many,
    because the lake is `<layer>/<asset_class>/<symbol>/<timeframe>/` and the first version listed
    the top level -- which counts LAYERS. It silently withheld the largest accelerant the desk has.
    A count wrong toward "no lever available" is not the safe error; it is the one that leaves
    every clock slow.
    """
    import scripts.run_information_rate as R

    lake = tmp_path / "lake"
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        d = lake / "bronze" / "crypto" / sym / "D1"
        d.mkdir(parents=True)
        (d / "part-0.parquet").write_bytes(b"x")
    monkeypatch.setattr(R, "_LAKE", lake)
    n, why = R._universe_size()
    assert n == 3, why
    assert "3 symbol(s)" in why


def test_A_SYMBOL_DIRECTORY_WITHOUT_BARS_IS_NOT_A_SYMBOL(tmp_path, monkeypatch) -> None:
    """`write_bars` creates the partition even for an empty frame, so a bare directory records a
    symbol the desk TRIED to collect and did not get. Counting it prices the lever against data
    that is not there."""
    import scripts.run_information_rate as R

    lake = tmp_path / "lake"
    (lake / "bronze" / "crypto" / "BTCUSDT" / "D1").mkdir(parents=True)
    (lake / "bronze" / "crypto" / "BTCUSDT" / "D1" / "part-0.parquet").write_bytes(b"x")
    (lake / "bronze" / "crypto" / "GHOSTUSDT" / "D1").mkdir(parents=True)   # no parquet
    monkeypatch.setattr(R, "_LAKE", lake)
    n, _ = R._universe_size()
    assert n == 1


def test_AN_ABSENT_LAKE_OFFERS_THE_LEVER_TO_NOBODY(tmp_path, monkeypatch) -> None:
    import scripts.run_information_rate as R

    monkeypatch.setattr(R, "_LAKE", tmp_path / "nothing-here")
    n, why = R._universe_size()
    assert n == 1 and "NOT offered" in why


def test_THE_TIMEFRAME_IS_HONOURED(tmp_path, monkeypatch) -> None:
    """An H8 clock and a D1 clock do not have the same universe available, and reporting D1's
    breadth for an H8 signal recommends widening onto bars nobody collected at that frequency."""
    import scripts.run_information_rate as R

    lake = tmp_path / "lake"
    for sym, tf in (("BTCUSDT", "D1"), ("ETHUSDT", "D1"), ("BTCUSDT", "H8")):
        d = lake / "bronze" / "crypto" / sym / tf
        d.mkdir(parents=True, exist_ok=True)
        (d / "part-0.parquet").write_bytes(b"x")
    monkeypatch.setattr(R, "_LAKE", lake)
    assert R._universe_size("D1")[0] == 2
    assert R._universe_size("H8")[0] == 1


def test_AN_UNMEASURED_CORRELATION_PUBLISHES_A_RANGE_NOT_A_NUMBER() -> None:
    """THE DEFECT THIS PINS, caught by running the report on the live box 2026-08-14.

    `cross_symbol_rho` defaults to 0.0 when unmeasured, and 0.0 is exactly the value at which this
    lever looks BEST. The report published "213x available" for a macro timing clock whose true
    cross-sectional correlation is high enough to make the real figure a small fraction of that: a
    defaulted zero read as a measurement, in the flattering direction, on the number that decides
    where the desk spends a month of build time.
    """
    unmeasured = EvidenceState(raw_observations=40, distinct_regimes=3, measured=False)
    a = next(x for x in accelerants(unmeasured, available_symbols=213)
             if "cross-section" in x.lever)
    assert a.gain is None and a.measured is False
    assert a.gain_high is not None and a.gain_high > 200      # rho=0
    assert a.gain_low is not None and a.gain_low < 25         # rho=0.9
    assert "UNMEASURED" in a.why


def test_AN_UNMEASURED_LEVER_CANNOT_OUTRANK_A_MEASURED_ONE_ON_A_DEFAULT() -> None:
    """Ranking uses the CONSERVATIVE end, so an unmeasured lever competes on its floor rather than
    on the optimistic end of a two-order-of-magnitude range."""
    unmeasured = EvidenceState(raw_observations=40, autocorrelation=0.0, distinct_regimes=3,
                               measured=False)
    ranked = accelerants(unmeasured, available_symbols=213, bars_per_day=1,
                         available_bars_per_day=3)
    xs = next(a for a in ranked if "cross-section" in a.lever)
    assert xs.rank_key == xs.gain_low


def test_A_MEASURED_CORRELATION_STILL_PUBLISHES_A_NUMBER() -> None:
    """The range is for absence, not a blanket downgrade. A clock that HAS measured its
    cross-symbol correlation gets the point estimate it earned."""
    measured = EvidenceState(raw_observations=40, distinct_regimes=3, cross_symbol_rho=0.7,
                             measured=True)
    a = next(x for x in accelerants(measured, available_symbols=213) if "cross-section" in x.lever)
    assert a.gain is not None and abs(a.gain - cross_section_gain(213, 0.7)) < 1e-9
    assert a.measured is True
