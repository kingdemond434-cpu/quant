"""INDEPENDENT SURVIVORS, NOT SURVIVOR COUNT.

"Boost our survivor count" is the wrong target and it gets worse the harder you work at it: near-
duplicates are the cheapest thing a generator can make, so a programme rewarded on the raw count
produces exactly those. The count rises, the portfolio does not diversify, and the drawdown when
the single underlying mechanism fails is N times the size everyone thought it was.

This is the redundancy filter the desk did not have. DSR, PBO, CPCV and the trial ledger all police
whether a candidate is REAL. Nothing asked whether it was NEW.
"""

from __future__ import annotations

import numpy as np

from libs.alpha_factory.independence import (
    MIN_OVERLAP,
    assess,
    cluster,
    pairwise_corr,
)

_RNG = np.random.default_rng(11)


def _series(n: int = 400) -> np.ndarray:
    return _RNG.normal(size=n)


def test_A_NEAR_DUPLICATE_IS_REDUNDANT_HOWEVER_GOOD_IT_LOOKS() -> None:
    """The whole point. A candidate 95% correlated with an existing survivor is that survivor
    again -- its standalone Sharpe is irrelevant to the question this module asks."""
    base = _series()
    v = assess(base * 1.02 + _RNG.normal(scale=0.05, size=base.size), {"existing": base})
    assert v.verdict == "REDUNDANT"
    assert v.nearest == "existing" and v.max_abs_corr is not None and v.max_abs_corr > 0.9


def test_AN_INVERSE_DUPLICATE_IS_ALSO_REDUNDANT() -> None:
    """ABSOLUTE correlation, not signed. A candidate at -0.95 is the same bet inverted: no new
    information, and holding both pays two sets of fees to express approximately nothing."""
    base = _series()
    assert assess(-base, {"existing": base}).verdict == "REDUNDANT"


def test_A_GENUINELY_NEW_SERIES_IS_INDEPENDENT() -> None:
    """The other half of the bar: a filter that rejects everything cannot steer research."""
    v = assess(_series(), {"existing": _series()})
    assert v.verdict == "INDEPENDENT"


def test_AN_EMPTY_SURVIVOR_SET_MAKES_THE_FIRST_INDEPENDENT() -> None:
    """The desk's live branch: 434 candidates, 0 survivors. With nothing to be redundant against
    the first is independent by definition -- and the verdict says outright that this is not a
    statement about quality."""
    v = assess(_series(), {})
    assert v.verdict == "INDEPENDENT"
    assert "says nothing about its quality" in v.reason


def test_A_SHORT_OVERLAP_IS_UNMEASURED_NOT_INDEPENDENT() -> None:
    """THE DANGEROUS DEFAULT. A correlation on 12 shared bars is noise with a decimal point. If
    that resolved to 0.0 it would read as 'independent' -- the most flattering possible reading --
    and every duplicate with a short overlap would be admitted as a discovery."""
    short = _series(12)
    v = assess(short, {"existing": _series(12)})
    assert v.verdict == "UNMEASURED"
    assert "NOT independence" in v.reason
    assert pairwise_corr(short, _series(12)) is None


def test_A_CONSTANT_SERIES_IS_UNMEASURABLE_RATHER_THAN_UNCORRELATED() -> None:
    """Zero variance makes correlation undefined, and numpy would hand back nan. Reporting nan as
    a low correlation would admit a flat line as a diversifying strategy."""
    assert pairwise_corr(np.zeros(200), _series(200)) is None


def test_PARTIAL_COMPARISON_IS_DISCLOSED_ON_AN_INDEPENDENT_VERDICT() -> None:
    """An INDEPENDENT verdict resting on a pool that could not be fully compared must say so, or
    the reader assumes the whole pool was checked."""
    v = assess(_series(400), {"long": _series(400), "short": _series(10)})
    assert v.verdict == "INDEPENDENT"
    assert "partial pool" in v.reason


# ------------------------------------------------------------------ the count that actually matters

def test_TWENTY_VARIANTS_OF_ONE_FACTOR_COLLAPSE_TO_ONE_MECHANISM() -> None:
    """The headline result. A desk reporting twenty survivors here has made ONE discovery, and the
    difference is the number it would have claimed."""
    base = _series()
    survivors = {f"v{i}": base + _RNG.normal(scale=0.05, size=base.size) for i in range(20)}
    rep = cluster(survivors)
    assert rep.n_survivors == 20
    assert rep.n_independent == 1
    assert "collapse to 1 mechanism" in " ".join(rep.notes)


def test_GENUINELY_DISTINCT_SURVIVORS_STAY_DISTINCT() -> None:
    survivors = {f"s{i}": _series() for i in range(5)}
    assert cluster(survivors).n_independent == 5


def test_MIXED_POOL_COUNTS_MECHANISMS_NOT_MEMBERS() -> None:
    """Two families of three. Six survivors, two mechanisms."""
    a, b = _series(), _series()
    survivors = {}
    for i in range(3):
        survivors[f"a{i}"] = a + _RNG.normal(scale=0.03, size=a.size)
        survivors[f"b{i}"] = b + _RNG.normal(scale=0.03, size=b.size)
    rep = cluster(survivors)
    assert rep.n_survivors == 6 and rep.n_independent == 2
    assert sorted(len(c) for c in rep.clusters) == [3, 3]


def test_UNMEASURABLE_PAIRS_MAKE_THE_COUNT_AN_UPPER_BOUND_AND_SAY_SO() -> None:
    """Pairs that could not be compared are treated as separate clusters -- they might be -- so
    the independent count can only be too HIGH. The report must not let that pass silently."""
    survivors = {"long_a": _series(400), "long_b": _series(400), "tiny": _series(5)}
    rep = cluster(survivors)
    assert rep.unmeasured_pairs > 0
    assert "UPPER BOUND" in " ".join(rep.notes)


def test_THE_HEADLINE_LEADS_WITH_MECHANISMS() -> None:
    """What gets read is what gets optimised. The sentence has to put the independent count first,
    because 'twenty survivors' is the number a desk talks itself into being proud of."""
    base = _series()
    rep = cluster({f"v{i}": base + _RNG.normal(scale=0.05, size=base.size) for i in range(20)})
    assert rep.headline.startswith("1 INDEPENDENT")
    assert "20 survivor" in rep.headline


def test_AN_EMPTY_POOL_IS_ZERO_NOT_AN_ERROR() -> None:
    """The desk's current state must render, not raise, inside a reporting pass."""
    rep = cluster({})
    assert rep.n_survivors == 0 and rep.n_independent == 0
    assert MIN_OVERLAP > 0
