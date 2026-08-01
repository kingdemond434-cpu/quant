"""Operator grammar properties.

Three of these are the reason the module looks the way it does, and all three are defect classes
this desk has already been burned by:

  test_a_name_with_no_peers_is_neutral_never_extreme -- a singleton group has no rank, and the two
  obvious defaults (0.0, 1.0) are the operator's two MOST extreme outputs. Defaulting there puts
  the book's largest position in exactly the names carrying no information.

  test_a_dead_neutraliser_leaves_the_candidate_alone -- the `> 0` guard rewritten for projections.
  An all-zero neutraliser sends the whole output to NaN through 0/0; a dust-valued one passes
  `> 0` and subtracts up to 100% of the candidate along a direction that is pure rounding noise,
  then hands it back labelled "neutralised". The naive formula is computed alongside in that test
  so the damage is visible rather than asserted.

  test_too_few_observations_returns_nothing_not_a_perfect_zero -- neutralising k observations
  against k independent vectors returns EXACTLY ZERO, and a zero series reads to a redundancy
  screen as perfect orthogonality. That is a manufactured survivor, not a result.

Both time-series functions carry a prefix-invariance test, which is the standing one: truncating
the input must not change any earlier output. It is the only cheap proof that a rolling window is
trailing, and the version that fails it produces a backtest that is reading the answer.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research.cohort_independence import BENCHMARK_MEAN_CORR, measure
from libs.research.operators import (
    SINGLETON_RANK,
    group_rank,
    ts_backfill,
    ts_information_ratio,
    vector_neut,
)


def _lstsq_residual(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a minus its least-squares fit on b -- the answer vector_neut must agree with."""
    coef, *_ = np.linalg.lstsq(b, a, rcond=None)
    return np.asarray(a - b @ coef, dtype="float64")


# --------------------------------------------------------------------------------- group_rank

def test_group_rank_ranks_within_group_not_globally():
    """The whole point of the operator. Sector B's values are all below sector A's, so a GLOBAL
    rank puts every B name in the bottom half; a group rank gives each sector its own full [0, 1]
    spread, which is the bet that was actually intended."""
    x = np.array([10.0, 20.0, 30.0, 1.0, 2.0, 3.0])
    g = np.array(["A", "A", "A", "B", "B", "B"])
    r = group_rank(x, g)
    assert np.allclose(r, [0.0, 0.5, 1.0, 0.0, 0.5, 1.0])


def test_group_rank_is_bounded_in_zero_one_and_reaches_both_ends():
    rng = np.random.default_rng(11)
    x = rng.normal(size=200)
    g = rng.integers(0, 7, size=200)
    r = group_rank(x, g)
    fin = r[np.isfinite(r)]
    assert fin.min() == 0.0 and fin.max() == 1.0
    assert np.all((fin >= 0.0) & (fin <= 1.0))


def test_a_name_with_no_peers_is_neutral_never_extreme():
    """A rank against no peers is undefined. 0.0 and 1.0 are the operator's two most extreme
    outputs, so defaulting a singleton to either takes the book's largest short (or long) in
    precisely the name about which nothing is known. Unknown must be a no-op, not an action."""
    x = np.array([5.0, 7.0, 9.0, 100.0])
    g = np.array(["A", "A", "A", "LONELY"])
    r = group_rank(x, g)
    assert r[3] == SINGLETON_RANK == 0.5
    assert r[3] not in (0.0, 1.0), "a peerless name must not be a maximal position"
    # and its own value being the largest in the universe changes nothing -- it has no peers.
    x2 = x.copy()
    x2[3] = -1e9
    assert group_rank(x2, g)[3] == 0.5


def test_unequal_group_sizes_are_each_normalised_by_their_own_size():
    """Group size must not leak into position size. Both groups span the full [0, 1] range and the
    two-name group's members sit at the extremes, not compressed toward the middle."""
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 20.0])
    g = np.array(["BIG", "BIG", "BIG", "BIG", "BIG", "SMALL", "SMALL"])
    r = group_rank(x, g)
    assert np.allclose(r[:5], [0.0, 0.25, 0.5, 0.75, 1.0])
    assert np.allclose(r[5:], [0.0, 1.0])


def test_missing_values_and_missing_labels_both_return_nan():
    """Two different unknowns, one answer: block. A missing VALUE has no rank, and filling it with
    the group midpoint would put a live position on an observation that does not exist. A missing
    LABEL is not swept into a catch-all bucket, because a catch-all is a fake peer group and its
    ranks are indistinguishable downstream from real ones."""
    x = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
    g = np.array(["A", "A", "A", "A", None], dtype=object)
    r = group_rank(x, g)
    assert np.isnan(r[2]), "missing value -> no rank"
    assert np.isnan(r[4]), "missing group label -> no rank, and no catch-all bucket"
    assert np.allclose(r[[0, 1, 3]], [0.0, 0.5, 1.0]), "the NaN must not consume a rank slot"
    assert np.isnan(group_rank(np.array([1.0, 2.0]), np.array([np.nan, np.nan]))).all()


def test_ties_rank_at_the_midpoint_and_do_not_depend_on_column_order():
    """Averaged ties, not positional ones. Competition-style tie breaking would make the operator
    depend on universe ORDER, so relabelling the columns would change the portfolio -- a silent,
    untraceable source of run-to-run difference."""
    g = np.array(["A", "A", "A", "A"])
    assert np.allclose(group_rank(np.array([3.0, 3.0, 3.0, 3.0]), g), 0.5)
    r = group_rank(np.array([1.0, 5.0, 5.0, 9.0]), g)
    assert np.allclose(r, [0.0, 0.5, 0.5, 1.0])
    perm = [3, 1, 0, 2]
    r2 = group_rank(np.array([1.0, 5.0, 5.0, 9.0])[perm], g[perm])
    assert np.allclose(r2, r[perm])


def test_group_rank_on_a_panel_uses_each_rows_own_cross_section():
    """2-D is (obs x names) and each row ranks independently -- a rank must never see another
    day's cross-section. Sector membership is allowed to vary per row, because in crypto it does:
    a token moves from 'new listing' to a real sector, and pinning it to its first-observed label
    would rank it forever against peers it no longer has."""
    x = np.array([[1.0, 2.0, 30.0, 40.0],
                  [4.0, 3.0, 40.0, 30.0]])
    static = np.array(["A", "A", "B", "B"])
    assert np.allclose(group_rank(x, static), [[0.0, 1.0, 0.0, 1.0], [1.0, 0.0, 1.0, 0.0]])
    moving = np.array([["A", "A", "B", "B"],
                       ["A", "B", "A", "B"]])
    r = group_rank(x, moving)
    assert np.allclose(r[0], [0.0, 1.0, 0.0, 1.0])
    assert np.allclose(r[1], [0.0, 0.0, 1.0, 1.0])


def test_group_rank_removes_the_sector_bet_a_global_rank_silently_takes():
    """The webinar's measured claim, reproduced as a mechanism rather than a fitness number: the
    worked example changed `rank` to `group_rank` and nothing else, and drawdown fell from ~30% to
    ~6%. The reason is here -- with one sector systematically richer than the rest, a global rank's
    top decile IS that sector, so the 'signal' is a concentrated sector bet nobody chose. Group
    rank puts it at zero by construction."""
    rng = np.random.default_rng(12)
    n_per, n_sec = 25, 4
    sector = np.repeat(np.arange(n_sec), n_per)
    level = np.repeat(np.array([3.0, 0.0, 0.0, 0.0]), n_per)   # sector 0 is structurally richer
    x = level + rng.normal(0.0, 0.5, n_sec * n_per)

    top_global = np.argsort(-x)[:n_per]
    frac_global = float(np.mean(sector[top_global] == 0))
    top_grouped = np.argsort(-group_rank(x, sector))[:n_per]
    frac_grouped = float(np.mean(sector[top_grouped] == 0))

    assert frac_global > 0.95, "a global rank on level-shifted sectors IS a sector bet"
    assert frac_grouped < 0.40, f"group rank must dilute it, got {frac_grouped:.2f}"


def test_group_rank_rejects_a_mismatched_group_map():
    with pytest.raises(ValueError):
        group_rank(np.array([1.0, 2.0, 3.0]), np.array(["A", "B"]))
    with pytest.raises(ValueError):
        group_rank(np.zeros((2, 2, 2)), np.array(["A", "B"]))


# --------------------------------------------------------------------------------- vector_neut

def test_residual_is_orthogonal_to_the_neutraliser():
    rng = np.random.default_rng(13)
    b = rng.normal(size=400)
    a = 0.8 * b + 0.6 * rng.normal(size=400)
    r = vector_neut(a, b)
    assert abs(float(r @ b)) < 1e-12 * float(np.sqrt((r @ r) * (b @ b)))


def test_orthogonal_is_not_uncorrelated_without_an_intercept():
    """Caught while writing these tests, and it is the difference between the function working and
    the function delivering. `vector_neut` removes the projection onto `b` ITSELF; correlation is
    the projection onto `b` AFTER DEMEANING, and the two coincide only at zero mean. So plain
    neutralisation leaves a residual that is exactly dot-orthogonal but only APPROXIMATELY
    uncorrelated: -5.2e-04 on centred data, and -3.4e-02 once `a` carries an ordinary drift, which
    is sixty-six times worse and is the case every live signal is in. An intercept column takes it
    to 1.1e-17. Since `cohort_independence.measure` reports a Pearson correlation, the intercept is
    not optional for the redundancy use, and both numbers are pinned so the gap cannot reopen."""
    rng = np.random.default_rng(13)
    b = rng.normal(size=400)
    a = 0.8 * b + 0.6 * rng.normal(size=400) + 2.5      # a real drift, as any live signal has
    plain = float(np.corrcoef(vector_neut(a, b), b)[0, 1])
    assert abs(plain) > 1e-8, f"dot-orthogonality alone leaves {plain:.2e} of correlation"

    with_intercept = np.column_stack([np.ones(400), b])
    fixed = float(np.corrcoef(vector_neut(a, with_intercept), b)[0, 1])
    assert abs(fixed) < 1e-12, f"an intercept column takes it to machine zero, got {fixed:.2e}"


def test_neutralising_against_several_vectors_equals_least_squares():
    """Sequential modified Gram-Schmidt, documented in the module as the deliberate choice over
    `lstsq`. On a full-rank neutraliser set the two must agree exactly -- if they did not, the
    'explicit about degeneracy' argument for MGS would be covering a plain arithmetic error."""
    rng = np.random.default_rng(14)
    b = rng.normal(size=(300, 5))
    a = b @ np.array([1.0, -2.0, 0.5, 0.0, 3.0]) + rng.normal(size=300)
    assert np.allclose(vector_neut(a, b), _lstsq_residual(a, b), atol=1e-9)


def test_a_rank_deficient_cohort_still_gives_the_right_residual():
    """The case MGS was chosen for. A cohort measured at 15.9% mean pairwise correlation produces
    near-collinear neutralisers routinely, and `lstsq` answers a rank-deficient problem with a
    silent minimum-norm solution. The RESIDUAL is unique even when the coefficients are not, so
    dropping the duplicate direction must not change the answer -- and it does not."""
    rng = np.random.default_rng(15)
    b0 = rng.normal(size=(200, 3))
    b = np.column_stack([b0, b0[:, 0], b0[:, 1] + 1e-14 * rng.normal(size=200)])
    a = rng.normal(size=200)
    r = vector_neut(a, b)
    assert np.all(np.isfinite(r))
    assert np.allclose(r, _lstsq_residual(a, b0), atol=1e-8)


def test_a_dead_neutraliser_leaves_the_candidate_alone():
    """The `> 0` guard rewritten for projections, and the naive formula is computed alongside so
    the damage is visible rather than asserted.

      all-zero b  -> a.b / b.b is 0/0, so the naive residual is NaN EVERYWHERE. A successful-looking
                     call returns a series with no data in it.
      dust-valued b -> b.b passes `> 0`. The projection's magnitude is bounded, but its direction
                     comes out of catastrophic cancellation, so the naive residual differs from `a`
                     by an O(|a|) amount along an axis that means nothing -- and is returned
                     labelled 'neutralised', which is the version nobody investigates.
    """
    a = np.array([4.0, -6.0, 1.0, 2.0, -3.0])

    zeros = np.zeros(5)
    with np.errstate(invalid="ignore", divide="ignore"):
        naive_zero = a - np.divide(a @ zeros, zeros @ zeros) * zeros
    assert not np.isfinite(naive_zero).any(), "0/0 wipes the series -- this is the bug"
    assert np.array_equal(vector_neut(a, zeros), a), "nothing to remove means remove nothing"

    dust = np.zeros(5)
    dust[0], dust[1] = 1e-30, -1e-30
    naive_dust = a - (float(a @ dust) / float(dust @ dust)) * dust
    assert np.max(np.abs(naive_dust - a)) > 1.0, "dust direction eats an O(|a|) chunk of a"
    assert np.array_equal(vector_neut(a, dust), a)
    assert np.all(np.isfinite(vector_neut(a, dust)))


def test_a_neutraliser_that_explains_everything_leaves_nothing_and_says_so():
    a = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    r = vector_neut(a, 2.5 * a)
    assert np.all(np.isfinite(r)) and np.allclose(r, 0.0, atol=1e-12)


def test_an_already_orthogonal_candidate_survives_untouched():
    a = np.array([1.0, -1.0, 1.0, -1.0, 1.0, -1.0])
    b = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    assert np.allclose(vector_neut(a, b), a, atol=1e-12)


def test_too_few_observations_returns_nothing_not_a_perfect_zero():
    """A manufactured survivor, blocked. Neutralising k observations against k independent vectors
    returns EXACTLY zero -- and a zero series reads to a redundancy screen as perfect
    orthogonality, i.e. the most diversifying candidate the desk has ever seen. The least-squares
    residual is computed here to show that is genuinely what the unguarded answer would be."""
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    assert np.allclose(_lstsq_residual(a, b), 0.0, atol=1e-12), "unguarded: a perfect fake"
    assert np.isnan(vector_neut(a, b)).all(), "block rather than report fabricated orthogonality"
    # against ONE neutraliser: two observations leave one spare and are refused, three are allowed.
    assert np.isnan(vector_neut(np.array([1.0, 2.0]), np.array([3.0, 5.0]))).all()
    assert np.isfinite(vector_neut(np.array([1.0, 2.0, 3.0]), np.array([3.0, 5.0, 7.0]))).all()


def test_missing_data_blocks_rather_than_passing_through_unneutralised():
    """Deliberately strict, and the strictness is the point. If an observation missing from `b`
    let `a`'s raw value through, the surviving points would be exactly the ones with no cohort
    correction applied -- the still-correlated ones -- inside a series the caller has been told is
    orthogonal. The remedy for gaps is `ts_backfill` on `b`, not a softer rule here."""
    rng = np.random.default_rng(16)
    b = rng.normal(size=50)
    a = 0.9 * b + 0.4 * rng.normal(size=50)
    b_gap = b.copy()
    b_gap[7] = np.nan
    out = vector_neut(a, b_gap)
    assert np.isnan(out[7]), "an observation with no neutraliser cannot be neutralised"
    assert out[7] != a[7]
    assert np.isfinite(out[np.arange(50) != 7]).all()
    a_gap = a.copy()
    a_gap[3] = np.nan
    assert np.isnan(vector_neut(a_gap, b)[3])
    assert np.isnan(vector_neut(np.full(20, np.nan), b[:20])).all()


def test_cross_sectional_form_neutralises_each_row_on_its_own():
    """(obs x names) with (obs x names x k): today's alpha vector made orthogonal to today's
    neutralisers. Per-row rather than pooled, because a beta estimated over the whole sample is
    not the beta that applied on any given day -- here the loading flips sign between rows and a
    pooled fit would split the difference and leave both rows correlated."""
    rng = np.random.default_rng(17)
    mkt = rng.normal(size=(2, 40))
    a = np.vstack([2.0 * mkt[0] + 0.3 * rng.normal(size=40),
                   -2.0 * mkt[1] + 0.3 * rng.normal(size=40)])
    r = vector_neut(a, mkt)
    assert r.shape == a.shape
    for t in range(2):
        assert abs(float(r[t] @ mkt[t])) < 1e-9 * float(np.sqrt((r[t] @ r[t]) * (mkt[t] @ mkt[t])))
    b3 = np.stack([mkt, np.ones((2, 40))], axis=-1)          # market + intercept
    r3 = vector_neut(a, b3)
    assert r3.shape == a.shape
    for t in range(2):
        assert abs(float(r3[t].sum())) < 1e-9 * float(np.abs(a[t]).sum())


def test_it_drives_measured_cohort_correlation_to_the_benchmark():
    """The reason the module exists, measured with the desk's own instrument.

    `cohort_independence.measure` reads a candidate cohort against the published benchmark of 101
    alphas at 15.9% mean pairwise correlation = 6.0 independent bets. Ten candidates that all load
    on one common factor come in far above that. Neutralising each against the INCUMBENT cohort --
    which is the operational move, not a statistical trick -- puts them at or under the benchmark
    and multiplies the independent bets they represent. Measured here: rho 0.845 -> 1.2 bets
    becomes rho 0.035 -> 7.6 bets, on the SAME ten candidates, with no new data and no new
    mechanism. Contrast the module docstring's other number -- going 101 -> 420 candidates buys
    0.3 of one extra bet. Subtracting shared structure is the lever; adding candidates is not."""
    rng = np.random.default_rng(18)
    n_obs = 600
    factor = rng.normal(size=n_obs)
    # The intercept column is deliberate, not decoration: `measure` reports Pearson correlations,
    # and dot-orthogonality alone does not zero those. See the test above.
    incumbents = np.column_stack(
        [np.ones(n_obs)] + [factor + 0.25 * rng.normal(size=n_obs) + 1.0 for _ in range(6)])
    candidates = np.column_stack(
        [0.9 * factor + 0.4 * rng.normal(size=n_obs) + 0.5 for _ in range(10)])

    before = measure(candidates)
    neutral = np.column_stack([vector_neut(candidates[:, j], incumbents)
                               for j in range(candidates.shape[1])])
    assert np.isfinite(neutral).all()
    after = measure(neutral)

    assert before.mean_corr > 3 * BENCHMARK_MEAN_CORR, f"setup check: {before.mean_corr:.3f}"
    assert after.mean_corr < BENCHMARK_MEAN_CORR, (
        f"neutralised cohort must reach the benchmark: {before.summary()} -> {after.summary()}")
    assert after.n_eff > 3.0 * before.n_eff


def test_vector_neut_rejects_shapes_it_cannot_interpret():
    with pytest.raises(ValueError):
        vector_neut(np.zeros(5), np.zeros(4))
    with pytest.raises(ValueError):
        vector_neut(np.zeros((3, 4)), np.zeros((3, 5)))
    with pytest.raises(ValueError):
        vector_neut(np.zeros((2, 2, 2)), np.zeros((2, 2, 2)))


# --------------------------------------------------------------------------------- ts_backfill

def test_ts_backfill_is_prefix_invariant():
    """The standing test. out[i] may depend on x[..i] and nothing else, so truncating the input
    cannot move an earlier output. A backfill that reached forward would be the purest possible
    lookahead: it would hand every gap the answer that arrives after it."""
    rng = np.random.default_rng(19)
    x = rng.normal(size=(500, 6))
    x[rng.random(x.shape) < 0.25] = np.nan
    full = ts_backfill(x, 5)
    for cut in (37, 120, 400):
        assert np.allclose(full[:cut], ts_backfill(x[:cut], 5), equal_nan=True)
    small = x[:60]
    ref = ts_backfill(small, 5)
    for cut in range(1, 61):                       # every cut point, not a lucky sample of three
        assert np.allclose(ref[:cut], ts_backfill(small[:cut], 5), equal_nan=True)


def test_ts_backfill_fills_forward_only_never_backward():
    x = np.array([np.nan, np.nan, 3.0, np.nan, np.nan, 6.0])
    out = ts_backfill(x, 2)
    assert np.isnan(out[0]) and np.isnan(out[1]), "a leading gap has no past to fill from"
    assert np.allclose(out[2:], [3.0, 3.0, 3.0, 6.0])


def test_the_cap_holds_and_a_long_outage_is_not_bridged_in_hops():
    """Age is counted from the last OBSERVED value, not the last filled one. If it were counted
    from the filled value, a `d`-period cap would reconstruct an outage of any length in `d`-length
    hops -- an uncapped fill wearing a cap's name. That matters because a frozen constant is the
    lowest-volatility series in any universe, and every inverse-volatility scheme downstream, this
    repo's `crypto_xsec` included, hands the lowest-volatility name the largest weight."""
    x = np.array([1.0, np.nan, np.nan, np.nan, np.nan, np.nan, 7.0])
    out = ts_backfill(x, 2)
    assert np.allclose(out[:3], [1.0, 1.0, 1.0])
    assert np.isnan(out[3:6]).all(), "beyond the cap the value is stale, not missing-and-fillable"
    assert out[6] == 7.0
    assert np.array_equal(ts_backfill(x, 0), x, equal_nan=True), "d=0 must be the identity"


def test_ts_backfill_kills_the_phantom_turnover_a_gap_creates():
    """The cost argument, made in cost units. A NaN -> value transition reads to a position sizer
    as flat -> fully-on and is charged a round trip even though the view never changed, so holes in
    the feed present as a strategy that trades too much -- the wrong diagnosis and the wrong fix."""
    held = np.full(60, 1.0)
    holed = held.copy()
    holed[[10, 11, 25, 40, 41]] = np.nan          # three gaps: two 2-bar, one 1-bar
    turnover = lambda p: float(np.abs(np.diff(np.nan_to_num(p))).sum())  # noqa: E731
    assert turnover(held) == 0.0
    assert turnover(holed) == 6.0, "three gaps = three phantom round trips, on an unchanged view"
    assert turnover(ts_backfill(holed, 3)) == 0.0


def test_ts_backfill_treats_each_name_independently():
    x = np.array([[1.0, np.nan], [np.nan, 2.0], [np.nan, np.nan]])
    out = ts_backfill(x, 1)
    assert np.allclose(out[0], [1.0, np.nan], equal_nan=True)
    assert np.allclose(out[1], [1.0, 2.0])
    assert np.allclose(out[2], [np.nan, 2.0], equal_nan=True)


def test_ts_backfill_survives_every_degenerate_input():
    """Constant, all-NaN, single element, empty: safe outputs, no exceptions, nothing invented."""
    const = np.full(20, 4.0)
    assert np.array_equal(ts_backfill(const, 5), const)
    allnan = np.full(20, np.nan)
    assert np.isnan(ts_backfill(allnan, 5)).all(), "no past value exists, so nothing may be filled"
    assert np.array_equal(ts_backfill(np.array([7.0]), 5), np.array([7.0]))
    assert np.isnan(ts_backfill(np.array([np.nan]), 5)).all()
    assert ts_backfill(np.zeros(0), 5).shape == (0,)
    assert ts_backfill(np.zeros((0, 3)), 5).shape == (0, 3)
    assert ts_backfill(np.zeros((4, 0)), 5).shape == (4, 0)


def test_a_negative_fill_window_is_refused():
    with pytest.raises(ValueError):
        ts_backfill(np.zeros(5), -1)


# ------------------------------------------------------------------------ ts_information_ratio

def test_ts_information_ratio_is_prefix_invariant():
    rng = np.random.default_rng(20)
    x = rng.normal(0.001, 0.02, size=(400, 4))
    x[rng.random(x.shape) < 0.1] = np.nan
    full = ts_information_ratio(x, 20)
    for cut in (25, 90, 300):
        assert np.allclose(full[:cut], ts_information_ratio(x[:cut], 20), equal_nan=True)
    small = x[:60]
    ref = ts_information_ratio(small, 20)
    for cut in range(1, 61):                       # every cut point, not a lucky sample of three
        assert np.allclose(ref[:cut], ts_information_ratio(small[:cut], 20), equal_nan=True)


def test_the_window_ends_at_the_current_bar_and_starts_d_minus_one_back():
    """Convention stated in the docstring, pinned here. out[i] covers x[i-d+1..i] inclusive, which
    uses no future data but IS a description of the window ending now rather than a forecast of
    the next one -- a caller trading on out[i] must be able to observe x[i] first."""
    x = np.arange(1.0, 8.0)
    out = ts_information_ratio(x, 3)
    assert np.isnan(out[:2]).all(), "the first d-1 windows are not full"
    for i in range(2, 7):
        w = x[i - 2:i + 1]
        assert np.isclose(out[i], w.mean() / w.std(ddof=1))


def test_a_stable_mean_scores_above_a_volatile_one_with_the_same_mean():
    """The template's whole claim: not 'is it large' but 'has it been reliably large'."""
    steady = np.full(80, 1.0) + np.tile([0.01, -0.01], 40)
    choppy = np.full(80, 1.0) + np.tile([5.0, -5.0], 40)
    assert float(ts_information_ratio(steady, 20)[-1]) > 20.0
    assert float(ts_information_ratio(choppy, 20)[-1]) < 1.0


def test_the_information_ratio_is_scale_free():
    rng = np.random.default_rng(21)
    x = rng.normal(0.002, 0.01, 300)
    a = ts_information_ratio(x, 30)
    b = ts_information_ratio(x * 1000.0, 30)
    ok = np.isfinite(a) & np.isfinite(b)
    assert ok.any() and np.allclose(a[ok], b[ok], atol=1e-9)


def test_a_zero_variance_window_has_no_information_ratio_rather_than_1e15():
    """The 1.4e31 bug, in its ts_ form. numpy returns dust rather than exactly 0.0 for the
    dispersion of a constant series, so a `> 0` divisor guard passes and mean/dust comes back as an
    information ratio of order 1e15 -- enormous, perfectly stable, firing on every bar, and
    entirely fictional. The series that do this are the common real ones: a pegged pair, a halted
    market, a dead altcoin, a frozen feed. NaN is the only safe answer."""
    for const in (np.full(200, 0.001), np.full(200, 1e6), np.zeros(200)):
        out = ts_information_ratio(const, 20)
        assert not np.isfinite(out).any(), f"a flat series must have no IR, got {np.nanmax(out)}"
    mixed = np.concatenate([np.full(40, 2.0), np.arange(40.0)])
    out = ts_information_ratio(mixed, 20)
    assert not np.isfinite(out[:40]).any()
    assert np.isfinite(out[-1])


def test_ts_information_ratio_survives_every_degenerate_input():
    """All-NaN, single element, too-short input, an all-NaN column beside a live one."""
    assert not np.isfinite(ts_information_ratio(np.full(50, np.nan), 10)).any()
    assert not np.isfinite(ts_information_ratio(np.array([3.0]), 10)).any()
    assert ts_information_ratio(np.array([3.0]), 10).shape == (1,)
    assert ts_information_ratio(np.zeros(0), 5).shape == (0,)
    rng = np.random.default_rng(22)
    panel = np.column_stack([rng.normal(1.0, 0.2, 60), np.full(60, np.nan)])
    out = ts_information_ratio(panel, 20)
    assert np.isfinite(out[-1, 0]) and not np.isfinite(out[:, 1]).any()


def test_a_window_that_is_mostly_missing_is_not_scored():
    """Half-window rule, matching `volatility_signals.realised_variance`. Two prints out of twenty
    can produce any information ratio at all, and it would be reported with the same confidence as
    one built from a full window."""
    x = np.full(40, np.nan)
    x[[30, 31]] = [1.0, 1.02]
    assert not np.isfinite(ts_information_ratio(x, 20)).any()
    x2 = np.full(40, np.nan)
    x2[20:36] = np.linspace(1.0, 2.0, 16)
    assert np.isfinite(ts_information_ratio(x2, 20)[35])


def test_a_window_shorter_than_two_is_refused():
    with pytest.raises(ValueError):
        ts_information_ratio(np.zeros(10), 1)


# ------------------------------------------- group_zscore: magnitude, when magnitude is signal

def test_group_zscore_standardises_within_each_group():
    from libs.research.operators import group_zscore
    x = np.array([[1.0, 2.0, 3.0, 10.0, 20.0, 30.0]])
    g = np.array([0, 0, 0, 1, 1, 1])
    z = group_zscore(x, g)[0]
    assert np.allclose(z[:3], z[3:]), "same shape within each group -> same z, whatever the scale"
    assert z[1] == pytest.approx(0.0) and z[4] == pytest.approx(0.0)


def test_group_zscore_keeps_the_magnitude_that_group_rank_discards():
    """The selection principle in one assertion. Rank sees only order, so a mild outlier and an
    extreme one look identical; z-score does not. That is the whole reason to prefer it when the
    source is expensive to move and a large reading is itself evidence."""
    from libs.research.operators import group_rank, group_zscore
    g = np.array([0, 0, 0])
    mild = np.array([[1.0, 2.0, 3.0]])
    extreme = np.array([[1.0, 2.0, 100.0]])
    assert np.allclose(group_rank(mild, g), group_rank(extreme, g)), "rank cannot tell them apart"
    assert not np.allclose(group_zscore(mild, g), group_zscore(extreme, g))


def test_a_group_with_no_dispersion_returns_no_view_not_an_enormous_one():
    """`> 0` on a standard deviation does not survive floating-point dust -- that exact guard
    produced a 1.4e31 signal on this desk. A group whose members all agree has no information."""
    from libs.research.operators import group_zscore
    z = group_zscore(np.array([[5.0, 5.0, 5.0]]), np.array([0, 0, 0]))
    assert np.all(np.isfinite(z)) and np.all(z == 0.0)


def test_a_singleton_group_is_neutral_under_both_operators():
    from libs.research.operators import SINGLETON_RANK, group_rank, group_zscore
    x, g = np.array([[7.0]]), np.array([0])
    assert group_zscore(x, g)[0, 0] == 0.0, "0.0 is z-score's neutral"
    assert group_rank(x, g)[0, 0] == SINGLETON_RANK, "0.5 is rank's neutral"
