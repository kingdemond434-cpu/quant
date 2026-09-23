"""Transfer entropy and conditional mutual information, checked against known ground truth.

A 514-line estimator with no test is not a capability, it is a claim -- and this module's own
docstrings make claims sharp enough to check: that the Miller-Madow correction removes the
plug-in bias rather than merely being applied, that CMI separates a mechanism from a shared
driver where MI cannot, that transfer entropy is directed and IS the conditional mutual
information on lagged blocks rather than a second implementation of it, that every estimator
refuses below a stated floor instead of spreading a thin sample over cells, and -- the claim
most worth pinning, because it is the one a user would otherwise get wrong -- that the p-value
does NOT separate a mechanism from a shared driver, only the magnitude does.

Every case below is built from a generator whose answer is known before the estimator runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research import information_flow as inf  # noqa: E402

N = 4_000


def _rng(seed: int = 7) -> np.random.Generator:
    return np.random.default_rng(seed)


# ------------------------------------------------------------------------ the bias correction
def test_independent_series_estimate_near_zero_and_the_correction_is_what_gets_them_there():
    """THE DEFECT THE CORRECTION EXISTS FOR, measured. The plug-in estimator is biased UPWARD
    and the bias does not vanish with independence, so an uncorrected estimator run over many
    pairs manufactures dependence out of noise. Over 40 independent draws the corrected mean
    must straddle zero while the plug-in mean sits clearly above it."""
    rng = _rng()
    corrected, plugin = [], []
    for _ in range(40):
        est = inf.mutual_information(rng.normal(size=600), rng.normal(size=600))
        assert est, est.why
        corrected.append(est.value)
        plugin.append(est.plugin)
    assert np.mean(plugin) > 0.0, "the plug-in estimator was not biased upward in this sample"
    assert abs(np.mean(corrected)) < np.mean(plugin), (
        f"the correction did not shrink the bias: plugin {np.mean(plugin):.5f} -> corrected "
        f"{np.mean(corrected):.5f}")
    assert abs(np.mean(corrected)) < 0.004, (
        f"corrected MI on independent data averaged {np.mean(corrected):.5f} nats, which is "
        f"dependence the data does not contain")


def test_a_negative_estimate_is_returned_and_never_clamped():
    """Zero is the truth being estimated and the correction is a subtraction, so roughly half
    the draws on independent data must land BELOW zero. Clamping would put the upward bias
    straight back in -- the exact defect the correction removes."""
    rng = _rng(11)
    vals = [inf.mutual_information(rng.normal(size=400), rng.normal(size=400)).value
            for _ in range(40)]
    assert any(v < 0.0 for v in vals), (
        "no corrected estimate came out below zero across 40 independent draws; the estimator "
        "is clamping and the bias is back")


def test_a_real_dependence_is_seen_and_dwarfs_the_independent_case():
    rng = _rng()
    x = rng.normal(size=N)
    y = x + 0.05 * rng.normal(size=N)
    dep = inf.mutual_information(x, y)
    ind = inf.mutual_information(x, rng.normal(size=N))
    assert dep and ind
    assert dep.value > 20 * max(abs(ind.value), 1e-3), (dep.value, ind.value)


# -------------------------------------------------------------------------- the refusal contract
def test_every_estimator_refuses_below_its_stated_floor_and_names_the_arithmetic():
    """The floor is STATED, not sensed: bins ** d cells x MIN_OBS_PER_CELL. A refusal carries
    the floor it failed, so a caller can see what sample would have answered."""
    rng = _rng()
    short = rng.normal(size=40)
    est = inf.mutual_information(short, rng.normal(size=40))
    assert est.value is None and not est
    assert est.floor == inf.DEFAULT_BINS ** 2 * inf.MIN_OBS_PER_CELL == 80
    assert "below the floor" in est.why and str(est.floor) in est.why

    z = rng.normal(size=200)
    cmi = inf.conditional_mutual_information(rng.normal(size=200), rng.normal(size=200), z)
    assert cmi.value is None
    assert cmi.floor == inf.DEFAULT_BINS ** 3 * inf.MIN_OBS_PER_CELL == 320

    te = inf.transfer_entropy(rng.normal(size=200), rng.normal(size=200))
    assert te.value is None and "transfer entropy at lag=1, k=1" in te.why


def test_conditioning_costs_a_factor_of_bins_per_column_and_the_floor_says_so():
    rng = _rng()
    two = np.column_stack([rng.normal(size=500), rng.normal(size=500)])
    est = inf.conditional_mutual_information(rng.normal(size=500), rng.normal(size=500), two)
    assert est.value is None
    assert est.floor == inf.DEFAULT_BINS ** 4 * inf.MIN_OBS_PER_CELL == 1280


def test_a_flat_series_is_refused_rather_than_reported_as_independent():
    rng = _rng()
    est = inf.mutual_information(np.ones(N), rng.normal(size=N))
    assert est.value is None and est.why


# ------------------------------------------- mechanism vs shared driver: the claim that matters
def _shared_driver(n: int = N, seed: int = 3):
    """X and Y are both the dollar plus noise. MI(X;Y) large, CMI(X;Y|Z) ~ 0 -- two instruments
    reading the same clock, and not an edge."""
    rng = _rng(seed)
    z = rng.normal(size=n)
    return z + 0.4 * rng.normal(size=n), z + 0.4 * rng.normal(size=n), z


def _mechanism(n: int = N, seed: int = 3):
    """The same shared driver, plus a genuine X -> Y channel on top of it."""
    rng = _rng(seed)
    z = rng.normal(size=n)
    x = z + 0.4 * rng.normal(size=n)
    return x, z + 0.9 * x + 0.4 * rng.normal(size=n), z


def test_conditioning_kills_a_shared_driver_and_spares_a_mechanism():
    """THE WHOLE POINT OF CMI ON THIS BOOK. Nearly every pair here shares one driver, so an
    edge whose MI is large and whose CMI collapses is not an edge. Both cases are built from
    the SAME driver and the same noise scale, so the only difference is the channel."""
    xs, ys, zs = _shared_driver()
    xm, ym, zm = _mechanism()
    mi_s = inf.mutual_information(xs, ys)
    cmi_s = inf.conditional_mutual_information(xs, ys, zs)
    mi_m = inf.mutual_information(xm, ym)
    cmi_m = inf.conditional_mutual_information(xm, ym, zm)
    assert mi_s and cmi_s and mi_m and cmi_m
    assert mi_s.value > 0.3, f"the shared driver did not even produce an MI: {mi_s.value}"
    assert cmi_s.value < 0.15 * mi_s.value, (
        f"conditioning left {cmi_s.value:.4f} of {mi_s.value:.4f} nats on a pure shared "
        f"driver; CMI is not removing the confounder")
    assert cmi_m.value > 4 * cmi_s.value, (
        f"a genuine mechanism ({cmi_m.value:.4f}) is not separated from a shared driver "
        f"({cmi_s.value:.4f}); the estimator cannot do the one job it is here for")


def test_the_p_value_does_not_separate_them_and_the_module_says_so():
    """THE HONEST WARNING, PINNED. The coarse grid leaves residual dependence given the binned
    conditioner, and that residual is itself significant -- so a pure shared driver and a
    genuine mechanism BOTH return a small p under the within-Z null. Only the magnitude tells
    them apart. If this ever stops being true the docstring is wrong and must change with it."""
    xs, ys, zs = _shared_driver()
    xm, ym, zm = _mechanism()
    p_s = inf.significance(inf.conditional_mutual_information, xs, ys, zs,
                           within=zs, n_perm=60, seed=1)
    p_m = inf.significance(inf.conditional_mutual_information, xm, ym, zm,
                           within=zm, n_perm=60, seed=1)
    assert p_s["p_value"] is not None and p_m["p_value"] is not None
    assert p_s["p_value"] < 0.05 and p_m["p_value"] < 0.05, (p_s, p_m)
    assert "does not mean" in inf.significance.__doc__ or \
        "WHAT A SMALL P DOES NOT MEAN" in inf.significance.__doc__


# --------------------------------------------------------------------------- transfer entropy
def test_transfer_entropy_is_directed():
    """X drives Y one bar later and nothing runs the other way. TE(X->Y) must exceed
    TE(Y->X) by a wide margin -- this is what MI, which is symmetric, cannot say."""
    rng = _rng(5)
    x = rng.normal(size=N)
    y = np.empty(N)
    y[0] = rng.normal()
    for t in range(1, N):
        y[t] = 0.3 * y[t - 1] + 0.9 * x[t - 1] + 0.3 * rng.normal()
    fwd = inf.transfer_entropy(x, y)
    rev = inf.transfer_entropy(y, x)
    assert fwd and rev
    assert fwd.value > 0.2, f"the planted flow was not detected: {fwd.value}"
    assert fwd.value > 5 * max(rev.value, 1e-3), (fwd.value, rev.value)


def test_transfer_entropy_IS_the_conditional_mutual_information_on_lagged_blocks():
    """Pinned as an identity, because the docstring claims there is no second entropy
    implementation in the module and that is the reason the two cannot drift apart."""
    rng = _rng(9)
    x = rng.normal(size=1500)
    y = np.concatenate([[0.0], 0.8 * x[:-1] + 0.4 * rng.normal(size=1499)])
    lag = k = 1
    start = max(lag, k)
    by_hand = inf.conditional_mutual_information(
        x[start - lag:len(x) - lag], y[start:],
        np.column_stack([y[start - j:len(y) - j] for j in range(1, k + 1)]))
    assert inf.transfer_entropy(x, y, lag=lag, k=k).value == by_hand.value


def test_transfer_entropy_refuses_a_contemporaneous_or_memoryless_request():
    rng = _rng()
    a, b = rng.normal(size=N), rng.normal(size=N)
    with pytest.raises(ValueError, match="lag must be >= 1"):
        inf.transfer_entropy(a, b, lag=0)
    with pytest.raises(ValueError, match="k must be >= 1"):
        inf.transfer_entropy(a, b, k=0)


def test_mutual_information_refuses_to_be_widened_into_a_conditional_one():
    rng = _rng()
    block = np.column_stack([rng.normal(size=N), rng.normal(size=N)])
    with pytest.raises(ValueError, match="condition with"):
        inf.mutual_information(block, rng.normal(size=N))


# ---------------------------------------------------------------------------- the null models
def test_a_free_shuffle_is_anti_conservative_on_an_autocorrelated_source():
    """The reason `circular_shift` exists. A free permutation destroys the source's OWN
    persistence as well as its relation to the target, so its null statistic is smaller than
    it should be and the p-value it returns is too small. Both nulls are run on the same
    unrelated pair, where the honest answer is 'no flow'."""
    rng = _rng(13)
    src = np.empty(N)
    src[0] = rng.normal()
    for t in range(1, N):
        src[t] = 0.95 * src[t - 1] + rng.normal()
    tgt = rng.normal(size=N)
    free = inf.significance(inf.mutual_information, src, tgt, n_perm=60, seed=2, mode="shuffle")
    shift = inf.significance(inf.mutual_information, src, tgt, n_perm=60, seed=2,
                             mode="circular_shift")
    assert free["null_mean"] is not None and shift["null_mean"] is not None
    assert shift["null_mean"] > free["null_mean"], (
        f"the circular-shift null ({shift['null_mean']:.5f}) did not sit above the free-shuffle "
        f"null ({free['null_mean']:.5f}); the conservative null is not conservative")
    assert shift["min_shift"] and free["min_shift"] is None


def test_a_p_value_of_exactly_zero_is_never_claimed():
    """(1 + #{null >= observed}) / (1 + draws): the observed statistic counts itself, so the
    smallest reportable p at n draws is 1/(1+n) and never 0."""
    rng = _rng(4)
    x = rng.normal(size=N)
    out = inf.significance(inf.mutual_information, x, x + 0.05 * rng.normal(size=N),
                           n_perm=50, seed=0)
    assert out["p_value"] == pytest.approx(1.0 / 51.0)


def test_significance_returns_a_refusal_rather_than_raising_when_the_estimate_refused():
    rng = _rng()
    out = inf.significance(inf.mutual_information, rng.normal(size=30), rng.normal(size=30),
                           n_perm=10)
    assert out["p_value"] is None and out["why"]


def test_every_result_names_the_correction_and_the_grid_it_was_measured_on():
    """A number with no stated grid is not reproducible: the histogram estimator's answer is
    only defined relative to its bin count, and the correction is only checkable if named."""
    rng = _rng()
    est = inf.mutual_information(rng.normal(size=N), rng.normal(size=N))
    d = est.to_dict()
    assert d["correction"] == inf.CORRECTION == "miller-madow"
    assert d["bins"] == inf.DEFAULT_BINS and d["n"] == N and d["cells"] == 16
    assert d["plugin"] is not None and d["plugin"] != d["value"], (
        "plugin and corrected are identical; either the correction is inert or it is not "
        "being reported")
