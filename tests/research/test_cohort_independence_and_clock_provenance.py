"""TWO MODULES THAT EXIST BECAUSE AN ESTIMATOR WAS READ OUTSIDE ITS DOMAIN -- 114 statements,
zero tests until now.

`cohort_independence` reports **64.4 independent bets from 29 crypto perps** if you let it. There
is no arrangement of 29 assets that constitutes 64 independent bets; the equicorrelation formula
was extrapolating past its domain on negative average correlation, and the output was read as a
finding on 2026-08-01. The upper clamp is the fix, and the reason it is not cosmetic is the whole
point of the test below.

`clock_provenance` is the answer to the other half of the same disease: a reader that sorts a
mixed-clock file by raw `t` interleaves two clocks and silently reorders events, which is the
mechanism behind every timestamp-artifact kill in the graveyard.

Both modules share a discipline the tests target directly: **never guess**. An unknown (venue,
kind) reads UNKNOWN rather than defaulting to the common case; a path that is not a moat tape
returns "" rather than attributing a stranger's file to a venue; a degenerate cohort reads
UNMEASURABLE rather than maximally diverse.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.research import clock_provenance as CP
from libs.research import cohort_independence as CI

# ============================================================ cohort_independence


def test_29_perps_can_never_be_64_independent_bets() -> None:
    """THE MISREADING THIS CLAMP EXISTS TO PREVENT, replayed with the measured numbers.

    Removing a common factor from a panel induces negative correlation among residuals BY
    CONSTRUCTION: subtract a cross-sectional mean and they must sum to zero, forcing average
    pairwise correlation to about -1/(N-1). At N=29 that floor is -0.0357 and the measured
    residual correlation was -0.0196 -- 55% of the way to a number pure arithmetic produces from
    data with no structure at all.
    """
    assert CI.effective_bets(29, -0.0196) <= 29.0


def test_effective_bets_is_clamped_to_N_from_above_and_1_from_below() -> None:
    """The low clamp matters for the opposite reason: rho -> 1 must send this to 1, correctly
    saying that a cohort of identical signals is ONE bet however many copies it holds."""
    for n in (2, 10, 101):
        assert CI.effective_bets(n, -0.99) <= n
        assert CI.effective_bets(n, 1.0) == 1.0
        assert 1.0 <= CI.effective_bets(n, 0.3) <= n


def test_uncorrelated_candidates_are_worth_their_full_count() -> None:
    assert CI.effective_bets(20, 0.0) == pytest.approx(20.0)


def test_the_benchmark_cohort_reproduces_its_published_figure() -> None:
    """101 real production alphas at rho=0.159 are worth 6.0 bets. The desk's cohorts are read
    AGAINST this rather than against zero -- zero is unreachable, and comparing to it makes every
    real cohort look broken."""
    assert CI.effective_bets(CI.BENCHMARK_N, CI.BENCHMARK_MEAN_CORR) == pytest.approx(6.0, abs=0.1)


def test_a_single_candidate_is_one_bet() -> None:
    assert CI.effective_bets(1, 0.0) == 1.0
    assert CI.effective_bets(0, 0.0) == 0.0


def test_a_denominator_driven_non_positive_is_capped_at_N_not_returned_negative() -> None:
    """rho below -1/(N-1) makes the denominator non-positive; the formula there returns a NEGATIVE
    or exploding bet count, which is how 64.4 appeared."""
    assert CI.effective_bets(29, -0.5) == 29.0


def test_the_demeaning_floor_is_what_the_arithmetic_produces_from_nothing() -> None:
    """Report the DISTANCE ABOVE it, never the level. Any residual correlation at or below this is
    fully explained by the constraint that residuals sum to zero."""
    assert CI.demeaning_floor(29) == pytest.approx(-1.0 / 28)
    assert CI.demeaning_floor(2) == pytest.approx(-1.0)
    assert CI.demeaning_floor(1) == pytest.approx(-1.0), "never divides by zero"


def _panel(n_obs: int, n: int, rho: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    common = rng.normal(size=(n_obs, 1))
    idio = rng.normal(size=(n_obs, n))
    return np.sqrt(max(rho, 0.0)) * common + np.sqrt(1 - max(rho, 0.0)) * idio


def test_a_redundant_cohort_is_named_as_one_bet_in_many_costumes() -> None:
    ind = CI.measure(_panel(2_000, 12, 0.85))
    assert ind.mean_corr > 2 * CI.BENCHMARK_MEAN_CORR
    assert "one bet in many costumes" in ind.verdict
    assert "widen the MECHANISM space" in ind.verdict
    assert ind.n_eff < 3.0


def test_a_genuinely_distinct_cohort_meets_the_benchmark() -> None:
    ind = CI.measure(_panel(2_000, 12, 0.0, seed=3))
    assert ind.mean_corr <= CI.BENCHMARK_MEAN_CORR
    assert "AT OR BETTER THAN BENCHMARK" in ind.verdict


def test_the_verdict_compares_CORRELATION_not_N_eff() -> None:
    """N_eff depends on cohort size, so scoring on it would rank a small well-diversified cohort
    below a huge redundant one purely for being small -- rewarding exactly the width this desk
    already measured as worthless."""
    small = CI.measure(_panel(2_000, 3, 0.0, seed=4))
    big_redundant = CI.measure(_panel(2_000, 40, 0.8, seed=5))
    assert small.n_eff < big_redundant.n_series
    assert "AT OR BETTER" in small.verdict
    assert "one bet in many costumes" in big_redundant.verdict


def test_a_noise_dominated_estimate_is_FLAGGED_rather_than_silently_tolerated() -> None:
    """With T samples on N series in the Marchenko-Pastur regime the mean off-diagonal correlation
    is biased UPWARD, so redundancy may be overstated -- and a redundancy figure nobody knows is
    inflated is a reason to abandon a good cohort."""
    ind = CI.measure(_panel(10, 20, 0.0, seed=6))
    assert ind.noise_dominated is True
    assert "NOISE-DOMINATED" in ind.verdict


def test_a_well_sampled_cohort_is_not_flagged() -> None:
    assert CI.measure(_panel(2_000, 10, 0.1, seed=7)).noise_dominated is False


def test_a_dead_candidate_is_DROPPED_not_read_as_the_most_diversifying_thing() -> None:
    """A flat series has undefined correlation with everything. NaN-filling it to 0 would inflate
    the independence estimate, so the deadest column in the cohort would score as the best
    diversifier -- exactly backwards."""
    live = _panel(500, 4, 0.6, seed=8)
    with_dead = np.column_stack([live, np.zeros(500)])
    assert CI.measure(with_dead).n_series == 4
    assert CI.measure(with_dead).mean_corr == pytest.approx(CI.measure(live).mean_corr)


@pytest.mark.parametrize("bad", [
    np.zeros((100, 1)),
    np.zeros((100, 0)),
    np.zeros(100),
])
def test_too_few_candidates_is_UNMEASURABLE_rather_than_perfectly_independent(bad) -> None:
    ind = CI.measure(bad)
    assert "UNMEASURABLE" in ind.verdict
    assert np.isnan(ind.mean_corr)


def test_a_cohort_of_only_dead_series_is_UNMEASURABLE() -> None:
    ind = CI.measure(np.zeros((200, 5)))
    assert "UNMEASURABLE" in ind.verdict and "non-degenerate" in ind.verdict


def test_the_summary_states_the_benchmark_it_was_judged_against() -> None:
    """A redundancy number with no benchmark attached invites comparison to zero, which no real
    cohort reaches."""
    s = CI.measure(_panel(1_000, 8, 0.2, seed=9)).summary()
    assert "benchmark" in s and str(CI.BENCHMARK_N) in s


# ============================================================ clock_provenance

def test_an_unknown_stream_reads_UNKNOWN_rather_than_defaulting_to_the_common_case() -> None:
    """A new stream nobody has classified must read UNKNOWN so the fence reports it -- defaulting
    to the common case is being silently wrong on exactly the row that is new."""
    assert CP.clock_of({"k": "brand_new"}, "fut") == CP.CLOCK_UNKNOWN
    assert CP.clock_of({"k": "d"}, "some_new_venue") == CP.CLOCK_UNKNOWN
    assert CP.clock_of({}, "fut") == CP.CLOCK_UNKNOWN


def test_the_explicit_marker_WINS_over_the_historical_table() -> None:
    """The table is knowledge about rows written before the marker existed. A marked row states
    its own provenance and must not be overridden by an inference about its predecessors."""
    assert CP.clock_of({"k": "d", CP.MARKER: CP.CLOCK_VENUE}, "fut") == CP.CLOCK_VENUE
    assert CP.clock_of({"k": "t", CP.MARKER: CP.CLOCK_RECV}, "fut") == CP.CLOCK_RECV


def test_a_nonsense_marker_falls_back_rather_than_being_trusted() -> None:
    assert CP.clock_of({"k": "t", CP.MARKER: "made_up"}, "fut") == CP.CLOCK_VENUE


def test_recv_only_is_DISTINCT_from_recv() -> None:
    """recv means 'we also kept the venue's stamp'; recv_only means 'there is none to keep'.
    Collapsing them would let a permanent VENUE LIMITATION read exactly like a desk defect, and
    the fence would demand a stamp that does not exist until somebody switched it off."""
    assert CP.CLOCK_RECV != CP.CLOCK_RECV_ONLY
    assert CP.clock_of({"k": "d"}, "spot") == CP.CLOCK_RECV_ONLY
    assert CP.clock_of({"k": "d"}, "fut") == CP.CLOCK_RECV
    assert ("spot", "d") in CP.RECV_ONLY_STREAMS


def test_every_recv_only_stream_agrees_with_the_historical_table() -> None:
    """Two declarations of one fact drift. If they ever disagree, the fence is demanding a stamp
    the module itself says does not exist."""
    for venue, kind in CP.RECV_ONLY_STREAMS:
        assert CP._HISTORICAL[(venue, kind)] == CP.CLOCK_RECV_ONLY


def test_a_seconds_stamp_is_REJECTED_rather_than_read_as_1970() -> None:
    """The one units error that produces a plausible-looking number instead of an obvious one."""
    assert CP._as_ms(1_767_225_600) is None            # seconds
    assert CP._as_ms(1_767_225_600_000) == 1_767_225_600_000
    assert CP._as_ms(1_767_225_600_000_000) is None    # microseconds


@pytest.mark.parametrize("bad", [None, "", "abc", [], {}])
def test_an_unparseable_stamp_is_None(bad) -> None:
    assert CP._as_ms(bad) is None


def test_venues_return_stamps_as_str_and_int_interchangeably() -> None:
    assert CP._as_ms("1767225600000") == 1_767_225_600_000


def test_the_venue_stamp_is_found_on_a_new_schema_depth_row() -> None:
    """`E` (event time -- when the venue published) is preferred over `T` (matching time), which
    runs a few ms earlier. Preferring T would understate observation latency systematically."""
    row = {"k": "d", CP.MARKER: CP.CLOCK_RECV, "t": 1_767_225_600_500,
           "E": 1_767_225_600_100, "T": 1_767_225_600_000}
    assert CP.venue_ms(row, "fut") == 1_767_225_600_100


def test_a_spot_depth_row_has_no_venue_stamp_at_all() -> None:
    row = {"k": "d", "t": 1_767_225_600_500}
    assert CP.venue_ms(row, "spot") is None
    assert CP.recv_ms(row, "spot") == 1_767_225_600_500


def test_a_venue_clocked_row_reports_t_as_the_venue_stamp() -> None:
    row = {"k": "t", "t": 1_767_225_600_000}
    assert CP.venue_ms(row, "fut") == 1_767_225_600_000


def test_recv_falls_back_to_the_r_field_on_a_venue_clocked_row() -> None:
    row = {"k": "t", "t": 1_767_225_600_000, "r": 1_767_225_600_250}
    assert CP.recv_ms(row, "fut") == 1_767_225_600_250


def test_delta_is_observation_latency_and_is_None_when_either_clock_is_missing() -> None:
    """This series is structurally unbuyable: a vendor can sell the venue's stamp or THEIR box's
    receipt, never when a message reached OURS -- and it cannot be backfilled afterwards."""
    both = {"k": "t", "t": 1_767_225_600_000, "r": 1_767_225_600_250}
    assert CP.delta_ms(both, "fut") == 250
    assert CP.delta_ms({"k": "t", "t": 1_767_225_600_000}, "fut") is None
    assert CP.delta_ms({"k": "d", "t": 1_767_225_600_000}, "spot") is None


def test_a_bybit_trade_batch_carries_its_own_control_in_its_inner_rows() -> None:
    """The outer row is stamped with OUR poll receipt while every inner trade carries the venue's
    own `time`. That makes Delta measurable RETROSPECTIVELY across the whole existing archive at
    zero collection cost -- the archive contains its own control."""
    row = {"k": "trades", "t": 1_767_225_600_900,
           "v": [{"time": 1_767_225_600_100}, {"time": "1767225600400"},
                 {"time": 1_767_225_600_250}]}
    assert CP.inner_venue_ms(row) == 1_767_225_600_400, "the NEWEST inner stamp, not the first"


def test_inner_venue_stamps_survive_malformed_members() -> None:
    row = {"k": "trades", "v": [{"time": "bad"}, "not-a-dict", {"time": 1_767_225_600_100}]}
    assert CP.inner_venue_ms(row) == 1_767_225_600_100


def test_a_batch_with_no_usable_inner_stamps_is_None_not_zero() -> None:
    assert CP.inner_venue_ms({"k": "trades", "v": []}) is None
    assert CP.inner_venue_ms({"k": "trades", "v": "not a list"}) is None
    assert CP.inner_venue_ms({"k": "trades"}) is None


def test_a_MIXED_CLOCK_file_sorts_monotonically_on_the_common_axis() -> None:
    """A reader that sorts the raw `t` interleaves two clocks and silently reorders events -- the
    mechanism behind every timestamp-artifact kill in the graveyard. Receipt time is the only
    instant the desk observed BOTH kinds of row at."""
    depth = {"k": "d", "t": 1_767_225_600_900}                        # recv-clocked
    trade = {"k": "t", "t": 1_767_225_600_100, "r": 1_767_225_600_800}  # venue-clocked
    rows = [depth, trade]
    by_raw_t = sorted(rows, key=lambda r: r["t"])
    by_key = sorted(rows, key=lambda r: CP.sort_key(r, "fut"))
    assert by_raw_t[0] is trade, "raw t puts the trade first -- on a different clock"
    assert by_key[0] is trade and by_key[1] is depth
    assert CP.sort_key(trade, "fut") == (1_767_225_600_800, 0)


def test_a_row_whose_receipt_cannot_be_recovered_is_FLAGGED_never_dropped() -> None:
    """Dropping it would silently shorten the tape; sorting it in unflagged would put it on the
    wrong axis. The second element carries the distinction."""
    orphan = {"k": "t", "t": 1_767_225_600_000}
    assert CP.sort_key(orphan, "fut") == (1_767_225_600_000, 1)


def test_a_row_with_no_usable_stamp_at_all_sorts_first_and_flagged() -> None:
    assert CP.sort_key({"k": "t"}, "fut") == (0, 1)


def test_the_venue_is_read_from_the_tape_path_and_a_stranger_file_returns_empty() -> None:
    """A silent default here would attribute a stranger's file to a venue and mis-read every clock
    in it."""
    assert CP.venue_of_path("/srv/data/moat/bybit/BTCUSDT/20260806.jsonl.gz") == "bybit"
    assert CP.venue_of_path("/srv/data/elsewhere/BTCUSDT/x.jsonl") == ""
    assert CP.venue_of_path("/srv/data/moat") == ""


def test_clock_fields_can_tell_a_schema_coalesce_from_a_clock_coalesce() -> None:
    """`d.get("b") or d.get("bids")` is two names for ONE quantity; `d.get("t") or d.get("E")` is
    two names for two DIFFERENT instants. Only the second is the L1.46 defect, and a check that
    cannot tell them apart fires on healthy code until somebody switches it off."""
    assert {"t", "E", "T", "vt"} <= CP.CLOCK_FIELDS
    assert not ({"b", "bids", "a", "asks", "p", "q"} & CP.CLOCK_FIELDS)


def test_every_configured_period_names_a_stream_the_module_knows() -> None:
    """A configured constant for a stream nothing classifies is a number the fence would compare
    against nothing -- and a constant that is 64% wrong is inherited as truth by every downstream
    consumer that reads it instead of measuring."""
    for key in CP.CONFIGURED_PERIOD_S:
        assert key in CP._HISTORICAL, key
