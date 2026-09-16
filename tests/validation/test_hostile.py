"""Tests for the hostile roster (blueprint item 14).

THE LOAD-BEARING PAIR IN THIS FILE is `test_delayed_entry_holds_for_the_planted_edge` against
`test_delayed_entry_collapses_for_a_same_bar_fill_artefact`. An adversary that cannot tell a real
multi-bar effect from a strategy that peeks at the entry bar's own close is not an adversary, and
the same-bar peek is exactly the defect that took an FVG cell from t=+9 to t=-6 on this desk.

Everything is built from one synthetic tape with a PLANTED, KNOWN mechanism -- an overnight shock
at 00:00 UTC that mean-reverts over the following six hours -- so every verdict here is checked
against ground truth rather than against another measurement of the same unknown.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.validation.hostile import (
    BLOCK,
    BLOCKING_TESTS,
    REPORT,
    HostileReport,
    TradeStats,
    Verdict,
    data_source_substitution,
    delayed_entry,
    dual_engine,
    nearby_instrument_placebo,
    regime_permutation,
    run_all,
    stats_from_r,
    subperiod_removal,
    timestamp_permutation,
    transfer_test,
    worst_year_removal,
)

HOLD = 6
SHOCK_HOUR = 0        # the LAST bar of each 24-bar permutation block; the reversion is in the next
ARTEFACT_HOUR = 9
UNIT = 0.004          # one R, in price fraction


# ---------------------------------------------------------------------------- the planted tape


def make_bars(*, years: float = 3.0, seed: int = 0, revert: float = 0.45,
              start: str = "2023-01-01", edge_span: tuple[float, float] = (0.0, 1.0),
              edge_years: tuple[int, ...] | None = None, px0: float = 2000.0) -> pd.DataFrame:
    """Hourly OHLCV with a mean-reverting overnight effect planted at `SHOCK_HOUR`.

    The shock lands INSIDE the 00:00 bar and `revert` of it is given back over the next six
    hourly bars. The 00:00 bar is the last bar of a 24-bar permutation block and the reversion
    sits at the start of the next one, so a block permutation severs cause from effect -- which
    is what makes `timestamp_permutation` a real null for this edge rather than a relabelling.

    `edge_span` (fraction of the sample) and `edge_years` restrict where the reversion is planted,
    which is how the subperiod and worst-year tests get a tape whose edge is one episode.
    """
    rng = np.random.default_rng(seed)
    n = round(years * 365 * 24)
    index = pd.date_range(start, periods=n, freq="h", tz="UTC")
    hours = np.asarray(index.hour)
    years_of = np.asarray(index.year)

    base = rng.normal(0.0, 0.0008, n)
    shock = np.where(hours == SHOCK_HOUR, rng.normal(0.0, 0.004, n), 0.0)
    lo, hi = round(edge_span[0] * n), round(edge_span[1] * n)
    active = np.zeros(n, dtype=bool)
    active[lo:hi] = True
    if edge_years is not None:
        active &= np.isin(years_of, np.asarray(edge_years))
    rev = np.zeros(n)
    for i in np.flatnonzero((hours == SHOCK_HOUR) & active):
        rev[i + 1:min(i + 1 + HOLD, n)] -= revert * shock[i] / HOLD
    ret = base + shock + rev

    log_c = np.log(px0) + np.cumsum(ret)
    gaps = rng.normal(0.0, 0.00002, n)   # hourly metals/FX bars barely gap between them
    log_o = np.empty(n)
    log_o[0] = log_c[0] - ret[0]
    log_o[1:] = log_c[:-1] + gaps[1:]
    wick = np.abs(rng.normal(0.0, 0.0006, n))
    return pd.DataFrame(
        {"open": np.exp(log_o), "high": np.exp(np.maximum(log_o, log_c) + wick),
         "low": np.exp(np.minimum(log_o, log_c) - wick), "close": np.exp(log_c),
         "volume": rng.integers(100, 1000, n).astype(float)},
        index=index,
    )


def _hours(frame: pd.DataFrame) -> np.ndarray:
    return np.asarray(pd.DatetimeIndex(frame.index).hour)


def evaluate_planted(bars: pd.DataFrame) -> TradeStats:
    """Fade the 00:00 shock: decide on closes, enter at the NEXT open, exit HOLD bars on."""
    o = bars["open"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)
    n = len(c)
    pos = np.arange(n)
    idx = np.flatnonzero((_hours(bars) == SHOCK_HOUR) & (pos >= 1) & (pos + HOLD < n))
    if idx.size == 0:
        return stats_from_r([])
    side = -np.sign(c[idx] / c[idx - 1] - 1.0)
    return stats_from_r((side * (c[idx + HOLD] / o[idx + 1] - 1.0) / UNIT).tolist())


def evaluate_artefact(bars: pd.DataFrame) -> TradeStats:
    """THE DEFECT, in four lines: the entry bar's OWN close decides whether to enter at its open.

    Nothing about the trade list gives this away -- the trades are real, the costs would be real,
    both halves of the sample carry it. It is only visible to a test that re-runs the code against
    an execution tape it did not get to choose.
    """
    o = bars["open"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)
    n = len(c)
    pos = np.arange(n)
    idx = np.flatnonzero((_hours(bars) == ARTEFACT_HOUR) & (pos + HOLD < n))
    idx = idx[c[idx] > o[idx]]
    if idx.size == 0:
        return stats_from_r([])
    return stats_from_r(((c[idx + HOLD] / o[idx] - 1.0) / UNIT).tolist())


def evaluate_drift(bars: pd.DataFrame) -> TradeStats:
    """No mechanism at all: long every 37th bar for HOLD bars. Drift, which the null preserves."""
    n = len(bars)
    o = bars["open"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)
    idx = np.arange(0, n - HOLD - 1, 37)
    if idx.size == 0:
        return stats_from_r([])
    return stats_from_r(((c[idx + HOLD] / o[idx + 1] - 1.0) / UNIT).tolist())


def evaluate_regime_gated(bars: pd.DataFrame) -> TradeStats:
    """The planted rule, taken only when the `regime` column says 1."""
    if "regime" not in bars.columns:
        return stats_from_r([])
    o = bars["open"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)
    reg = bars["regime"].to_numpy(dtype=float)
    n = len(c)
    pos = np.arange(n)
    idx = np.flatnonzero((_hours(bars) == SHOCK_HOUR) & (pos >= 1) & (pos + HOLD < n))
    idx = idx[reg[idx] == 1.0]
    if idx.size == 0:
        return stats_from_r([])
    side = -np.sign(c[idx] / c[idx - 1] - 1.0)
    return stats_from_r((side * (c[idx + HOLD] / o[idx + 1] - 1.0) / UNIT).tolist())


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    return make_bars(years=1.6, seed=11)


@pytest.fixture(scope="module")
def long_bars() -> pd.DataFrame:
    return make_bars(years=3.0, seed=11)


# ---------------------------------------------------------------------------- stats_from_r


def test_stats_from_r_is_the_one_constructor() -> None:
    st = stats_from_r([1.0, -0.5, 2.0, 0.5])
    assert st.n == 4
    assert st.mean_r == pytest.approx(0.75)
    assert st.expectancy == pytest.approx(st.mean_r)
    assert st.t_stat > 0.0
    assert st.per_trade_r == [1.0, -0.5, 2.0, 0.5]


def test_stats_from_r_drops_non_finite_and_refuses_a_t_below_three_trades() -> None:
    st = stats_from_r([1.0, float("nan"), float("inf"), 2.0])
    assert st.n == 2
    assert np.isnan(st.t_stat), "two trades cannot carry a t; 0.0 would read as 'no edge'"
    empty = stats_from_r([])
    assert empty.n == 0 and np.isnan(empty.mean_r) and np.isnan(empty.t_stat)


def test_the_planted_edge_and_the_artefact_both_look_excellent_on_the_trade_series(
        bars: pd.DataFrame) -> None:
    """Ground truth: BOTH score like a certificate. That is why the roster exists."""
    real, fake = evaluate_planted(bars), evaluate_artefact(bars)
    assert real.n > 400 and real.t_stat > 6.0
    assert fake.n > 100 and fake.t_stat > 4.0


# ---------------------------------------------------------------------------- (1) permutation


def test_real_edge_beats_the_timestamp_permutation_null(bars: pd.DataFrame) -> None:
    v = timestamp_permutation(evaluate_planted, bars, seed=0)
    assert v.passed is True
    assert v.severity == BLOCK
    assert v.statistic is not None and v.threshold is not None
    assert v.statistic > v.threshold
    assert v.basis["n_null"] >= 5
    assert v.basis["p_value"] <= 0.05


def test_a_strategy_with_no_mechanism_fails_the_timestamp_permutation(bars: pd.DataFrame) -> None:
    v = timestamp_permutation(evaluate_drift, bars, seed=0)
    assert v.passed is False
    assert v.blocks is True


def test_timestamp_permutation_is_unmeasured_when_nothing_trades(bars: pd.DataFrame) -> None:
    v = timestamp_permutation(lambda _f: stats_from_r([]), bars, seed=0)
    assert v.passed is None
    assert v.blocks is False, "an unmeasured blocking test blocks nothing (L1.28a)"


# ---------------------------------------------------------------------------- (2) regime


def test_regime_permutation_is_unmeasured_without_labels(bars: pd.DataFrame) -> None:
    assert regime_permutation(evaluate_planted, bars, regime=None).passed is None


def test_regime_permutation_keeps_a_real_conditioner(bars: pd.DataFrame) -> None:
    """The conditioner is REAL here: the edge is only taken in labelled blocks, and a shuffle of
    the labels moves the rule off the shocks it was gated to."""
    hours = _hours(bars)
    day = np.arange(len(bars)) // 24
    regime = pd.Series(np.where((day % 2 == 0) | (hours < 0), 1.0, 0.0), index=bars.index)
    v = regime_permutation(evaluate_regime_gated, bars, regime=regime, n_permutations=12, seed=3)
    assert v.passed is not None
    assert v.severity == REPORT
    assert v.basis["n_null"] >= 5


# ---------------------------------------------------------------------------- (3) placebo


def test_placebo_passes_when_the_neighbour_does_not_carry_it(bars: pd.DataFrame) -> None:
    flat = make_bars(years=1.6, seed=77, revert=0.0)
    v = nearby_instrument_placebo(evaluate_planted, bars, bars_neighbour=flat)
    assert v.passed is True
    assert v.statistic is not None and v.statistic < 0.5


def test_placebo_fails_when_the_neighbour_carries_it_too(bars: pd.DataFrame) -> None:
    twin = make_bars(years=1.6, seed=78)
    v = nearby_instrument_placebo(evaluate_planted, bars, bars_neighbour=twin)
    assert v.passed is False
    assert v.severity == REPORT, "a placebo that also pays is a defect report, not a withdrawal"


def test_placebo_is_unmeasured_when_the_frame_is_absent(bars: pd.DataFrame) -> None:
    assert nearby_instrument_placebo(evaluate_planted, bars, bars_neighbour=None).passed is None


# ---------------------------------------------------------------------------- (4) delayed entry


def test_delayed_entry_holds_for_the_planted_edge(bars: pd.DataFrame) -> None:
    v = delayed_entry(evaluate_planted, bars)
    assert v.passed is True
    assert v.severity == BLOCK
    assert v.statistic is not None and v.statistic >= 0.5
    curve = v.basis["curve"]
    assert curve["1"]["retention"] > curve["5"]["retention"] > curve["15"]["retention"], (
        "a six-bar effect must decay monotonically as the entry slides past its horizon")


def test_delayed_entry_collapses_for_a_same_bar_fill_artefact(bars: pd.DataFrame) -> None:
    v = delayed_entry(evaluate_artefact, bars)
    assert v.passed is False
    assert v.blocks is True
    assert v.statistic is not None and v.statistic < 0.5
    assert "fill artefact" in v.why


def test_delayed_entry_is_unmeasured_when_there_is_nothing_to_retain(bars: pd.DataFrame) -> None:
    v = delayed_entry(lambda _f: stats_from_r([-1.0, -2.0, -1.5, -0.5]), bars)
    assert v.passed is None
    assert "nothing to retain" in v.why


# ---------------------------------------------------------------------------- (5) subperiods


def test_subperiod_removal_passes_a_persistent_edge(bars: pd.DataFrame) -> None:
    v = subperiod_removal(evaluate_planted, bars)
    assert v.passed is True
    assert v.statistic is not None and v.statistic > 1.0
    assert v.basis["sign_flipped_folds"] == []
    assert v.basis["n_measured_folds"] == 5
    assert v.severity == REPORT, "no sign flip, so this one reports rather than blocks"


def test_subperiod_removal_fails_when_the_edge_is_one_episode() -> None:
    episodic = make_bars(years=1.6, seed=12, edge_span=(0.8, 1.0))
    v = subperiod_removal(evaluate_planted, episodic)
    assert v.passed is False
    folds = v.basis["folds"]
    worst = min(range(5), key=lambda i: folds[i]["t_stat"])
    assert worst == 4, "removing the fifth that holds the episode must be the worst fold"


def test_subperiod_removal_is_unmeasured_on_a_frame_too_short_to_cut() -> None:
    short = make_bars(years=0.02, seed=5)
    assert subperiod_removal(evaluate_planted, short).passed is None


# ---------------------------------------------------------------------------- (6) worst year


def test_worst_year_removal_passes_a_multi_year_edge(long_bars: pd.DataFrame) -> None:
    v = worst_year_removal(evaluate_planted, long_bars)
    assert v.passed is True
    assert v.severity == BLOCK
    assert v.statistic is not None and v.statistic > 1.5
    assert len(v.basis["years"]) == 3


def test_worst_year_removal_fails_a_single_year_windfall() -> None:
    windfall = make_bars(years=3.0, seed=13, edge_years=(2024,))
    v = worst_year_removal(evaluate_planted, windfall)
    assert v.passed is False
    assert v.basis["best_year"] == 2024
    assert v.blocks is True


def test_worst_year_removal_is_unmeasured_inside_one_calendar_year() -> None:
    one_year = make_bars(years=0.5, seed=14)
    v = worst_year_removal(evaluate_planted, one_year)
    assert v.passed is None
    assert v.blocks is False


# ---------------------------------------------------------------------------- (7)/(8) alt frames


def test_transfer_passes_on_an_instrument_that_carries_the_mechanism(bars: pd.DataFrame) -> None:
    other = make_bars(years=1.6, seed=21, px0=1.25)
    v = transfer_test(evaluate_planted, bars, bars_alt=other)
    assert v.passed is True
    assert v.basis["same_sign"] is True
    assert v.statistic is not None and v.statistic > 1.0


def test_transfer_fails_where_the_mechanism_is_absent(bars: pd.DataFrame) -> None:
    flat = make_bars(years=1.6, seed=22, revert=0.0)
    assert transfer_test(evaluate_planted, bars, bars_alt=flat).passed is False


def test_the_two_alt_tests_never_read_the_same_frame(bars: pd.DataFrame) -> None:
    """One frame cannot be another instrument AND the same instrument."""
    other = make_bars(years=1.6, seed=23)
    assert transfer_test(evaluate_planted, bars, bars_alt=other,
                         alt_is_same_instrument=True).passed is None
    assert data_source_substitution(evaluate_planted, bars, bars_alt=other,
                                    alt_is_same_instrument=False).passed is None


def test_data_source_substitution_agrees_across_two_feeds_of_one_instrument(
        bars: pd.DataFrame) -> None:
    rng = np.random.default_rng(99)
    jitter = np.exp(rng.normal(0.0, 2e-5, len(bars)))
    feed_b = bars.copy()
    for col in ("open", "high", "low", "close"):
        feed_b[col] = bars[col].to_numpy(dtype=float) * jitter
    v = data_source_substitution(evaluate_planted, bars, bars_alt=feed_b,
                                 alt_is_same_instrument=True)
    assert v.passed is True
    assert v.statistic is not None and v.statistic <= 0.30


def test_data_source_substitution_fails_when_the_edge_lives_in_one_feed(
        bars: pd.DataFrame) -> None:
    feed_b = make_bars(years=1.6, seed=24, revert=0.0)
    v = data_source_substitution(evaluate_planted, bars, bars_alt=feed_b,
                                 alt_is_same_instrument=True)
    assert v.passed is False


# ---------------------------------------------------------------------------- dual engine


def test_dual_engine_agrees_with_a_second_implementation(bars: pd.DataFrame) -> None:
    def engine_b(frame: pd.DataFrame) -> TradeStats:
        st = evaluate_planted(frame)
        return stats_from_r([r * 1.02 for r in st.per_trade_r])

    v = dual_engine(evaluate_planted, engine_b, bars)
    assert v.passed is True
    assert v.basis["counts_agree"] is True and v.basis["expectancy_agrees"] is True


def test_dual_engine_catches_a_trade_count_disagreement(bars: pd.DataFrame) -> None:
    def engine_b(frame: pd.DataFrame) -> TradeStats:
        return stats_from_r(evaluate_planted(frame).per_trade_r[::2])

    v = dual_engine(evaluate_planted, engine_b, bars)
    assert v.passed is False
    assert v.basis["counts_agree"] is False
    assert v.basis["trade_count_gap"] > 0.10


def test_dual_engine_catches_an_expectancy_disagreement(bars: pd.DataFrame) -> None:
    def engine_b(frame: pd.DataFrame) -> TradeStats:
        st = evaluate_planted(frame)
        return stats_from_r([r - 0.5 for r in st.per_trade_r])

    v = dual_engine(evaluate_planted, engine_b, bars)
    assert v.passed is False
    assert v.basis["counts_agree"] is True and v.basis["expectancy_agrees"] is False


def test_dual_engine_is_unmeasured_when_an_engine_produces_nothing(bars: pd.DataFrame) -> None:
    v = dual_engine(evaluate_planted, lambda _f: stats_from_r([]), bars)
    assert v.passed is None


# ---------------------------------------------------------------------------- report / blocking


def _v(name: str, passed: bool | None, severity: str) -> Verdict:
    return Verdict(name=name, passed=passed, statistic=1.0, threshold=0.0, why="synthetic",
                   severity=severity)


def test_blocking_is_measured_failure_on_a_blocking_test_only() -> None:
    assert HostileReport(verdicts=(_v("delayed_entry", False, BLOCK),)).blocking is True
    assert HostileReport(verdicts=(_v("transfer_test", False, REPORT),)).blocking is False
    assert HostileReport(verdicts=(_v("delayed_entry", None, BLOCK),)).blocking is False
    assert HostileReport(verdicts=(_v("delayed_entry", True, BLOCK),)).blocking is False


def test_report_counts_and_names_what_blocked() -> None:
    rep = HostileReport(verdicts=(_v("timestamp_permutation", False, BLOCK),
                                  _v("worst_year_removal", True, BLOCK),
                                  _v("transfer_test", None, REPORT)))
    assert (rep.n_passed, rep.n_failed, rep.n_unmeasured) == (1, 1, 1)
    assert rep.blocked_by == ["timestamp_permutation"]
    body = rep.to_dict()
    assert body["blocking"] is True
    assert "BLOCKED BY timestamp_permutation" in body["why"]
    assert body["verdicts"][2]["status"] == "UNMEASURED"
    assert rep.by_name("transfer_test") is not None and rep.by_name("nope") is None


def test_blocking_roster_matches_the_severities_the_tests_emit(bars: pd.DataFrame) -> None:
    rep = run_all(evaluate_planted, bars, seed=1)
    emitted = {v.name for v in rep.verdicts if v.severity == BLOCK}
    assert emitted <= BLOCKING_TESTS
    assert {"timestamp_permutation", "delayed_entry", "worst_year_removal"} <= emitted


# ---------------------------------------------------------------------------- run_all


def test_run_all_returns_the_whole_roster_and_passes_a_real_edge(bars: pd.DataFrame) -> None:
    neighbour = make_bars(years=1.6, seed=31, revert=0.0)
    alt = make_bars(years=1.6, seed=32)
    rep = run_all(evaluate_planted, bars, bars_alt=alt, bars_neighbour=neighbour, seed=5)
    assert [v.name for v in rep.verdicts] == [
        "timestamp_permutation", "regime_permutation", "nearby_instrument_placebo",
        "delayed_entry", "subperiod_removal", "worst_year_removal", "transfer_test",
        "data_source_substitution"]
    assert rep.blocking is False
    assert rep.n_passed + rep.n_failed + rep.n_unmeasured == 8
    assert rep.real is not None and rep.real.n > 400


def test_run_all_blocks_the_fill_artefact(bars: pd.DataFrame) -> None:
    rep = run_all(evaluate_artefact, bars, seed=5)
    assert rep.blocking is True
    assert "delayed_entry" in rep.blocked_by


def test_run_all_is_unmeasured_where_the_frames_are_absent(bars: pd.DataFrame) -> None:
    rep = run_all(evaluate_planted, bars, seed=5)
    for name in ("regime_permutation", "nearby_instrument_placebo", "transfer_test",
                 "data_source_substitution"):
        v = rep.by_name(name)
        assert v is not None and v.passed is None, f"{name} must be UNMEASURED, never False"
    assert rep.n_unmeasured >= 4


def test_run_all_is_deterministic_under_seed(bars: pd.DataFrame) -> None:
    a = run_all(evaluate_planted, bars, seed=7).to_dict()
    b = run_all(evaluate_planted, bars, seed=7).to_dict()
    assert a == b
    c = run_all(evaluate_planted, bars, seed=8).to_dict()
    assert c["verdicts"][0]["threshold"] != a["verdicts"][0]["threshold"]
