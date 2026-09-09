"""INFORMATION FLOW -- nonlinear directed information between two series, and whether it
survives a third.

THE MEASURED GAP (external Tier-1 audit, 2026-09-09). The desk's causal engine
(`libs.research.causal_graph`) already had Granger-style incremental information, lagged
cross-correlation with a block bootstrap, a vol-state split and a circular-shift permutation
null. It had NO transfer entropy and NO conditional mutual information: a grep for
`transfer_entropy` / `conditional_mutual` / `mutual_info` across `libs/` and `desks/` returned
exactly ONE hit -- the field name `mutual_info` in `desks/mt5/side_channels/alpha_recombination.py`
-- and no implementation behind it. The Tier-1 ledger's G7 "LANDED" claim rested on
`causal_graph.conditional_information`, which is a LINEAR deltaR2 with confounders in the base
regression. That test is real and it stays. It is not this one.

WHY THESE TWO AND NOT MORE GRANGER. Granger causality is linear: it asks whether X's PAST
reduces the residual VARIANCE of Y. Transfer entropy is its information-theoretic
generalisation -- it asks whether X's past reduces the residual UNCERTAINTY of Y, which detects
directed dependence a regression coefficient cannot see. The desk's book is full of that kind:
a driver that matters through its magnitude rather than its sign (vol -> carry crosses), or
through a threshold (a yield move that only bites past a level), is invisible to a correlation
and to a deltaR2 and plain to an entropy. Conditional mutual information is the second half:
it asks whether X -> Y survives once Z is known, which is the whole difference between a
MECHANISM and a SHARED DRIVER. This desk trades a book in which nearly every pair shares one
driver -- the dollar -- so CMI is the test that decides whether an admitted edge is anything at
all. Neither replaces Granger; both are read BESIDE it, and an edge that passes one and fails
the other is exactly the edge worth looking at.

THE BIAS THAT MAKES A NAIVE MI USELESS. The plug-in (maximum-likelihood) estimator of mutual
information is biased UPWARD, and the bias does not vanish with independence -- for two
independent series binned into b bins each, E[MI_plugin] ~ (b-1)^2 / 2N nats, which at b=4 and
N=500 is 0.009 nats of pure fiction. Left uncorrected, an estimator run over hundreds of pairs
manufactures dependence out of noise and reports it as discovery. Every estimator here applies
the MILLER-MADOW correction and names it in its result: each plug-in entropy H_hat is corrected
to H_hat + (K_obs - 1) / 2N, where K_obs is the number of OCCUPIED cells, and the corrections
compose through the entropy identities below. At b=4 that correction is worth -(b-1)^2/2N on
independent data -- it cancels the leading bias term exactly when every cell is occupied.

NEGATIVE VALUES ARE KEPT, NOT CLAMPED. A corrected MI or CMI can come out slightly below zero.
Zero is the truth being estimated and the correction is a subtraction, so half the draws on
independent data must land below it. Clamping at zero would put the upward bias straight back
in -- the exact defect the correction exists to remove -- so a negative value is returned as it
stands and means "no dependence this bin count can resolve".

THE REFUSAL CONTRACT. Every estimator returns an `Estimate`, and `Estimate.value is None` with
a filled `why` whenever the sample cannot support the histogram. The floor is stated, not
sensed: a joint histogram over `d` discretised variables has `bins ** d` cells and needs
`MIN_OBS_PER_CELL` (5) observations per cell.

    MI(X;Y)        d=2  ->  4**2 =  16 cells  ->  floor   80 observations
    CMI(X;Y|Z)     d=3  ->  4**3 =  64 cells  ->  floor  320 observations
    TE (k=1)       d=3  ->  4**3 =  64 cells  ->  floor  320 observations
    CMI, 2 parents d=4  ->  4**4 = 256 cells  ->  floor 1280 observations

WHY bins=4 IS THE DEFAULT AND NOT 5. `causal_graph.MIN_N` is 500 aligned observations, and no
edge is measured below it. At bins=4 the CMI/TE floor is 320, so every edge the Granger test
was allowed to judge can also be judged here. At bins=5 the floor is 5 * 125 = 625, ABOVE
MIN_N -- the information test would silently refuse a class of edges the linear test admits,
and the annotation would be missing exactly where the audit wanted it. Four bins is the coarsest
grid that still separates two tails from two middles, and it is chosen to fit the floor the
desk already enforces rather than the other way round.

WHAT THIS MODULE REFUSES TO DO. It admits nothing, refuses no edge, moves no threshold and
touches no sizing. It is an estimator library: the caller publishes the numbers beside the
verdict the caller already reached.

BINNING IS EQUIPROBABLE BY QUANTILE EDGES, TIES KEPT TOGETHER. Returns are fat-tailed, so
equal-WIDTH bins put ~95% of a gold series in one cell and measure nothing. Quantile edges give
each bin roughly equal mass. Ties are NOT split across bins: a series that is 90% zeros
collapses into one large bin, which is honest about its information content. The alternative --
ranking and splitting ties by position -- makes a constant series into a monotone function of
TIME, which correlates with any trending target and manufactures flow out of nothing. A series
whose discretisation leaves fewer than two occupied bins is refused rather than measured.

Units are NATS (natural log). For equiprobable bins the maximum MI is log(bins) = 1.386 nats
at bins=4; a self-information check `MI(X;X)` returns exactly that, which is the arithmetic the
tests pin.

numpy only -- no scipy, no sklearn. No I/O, no network, no state.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

__all__ = [
    "DEFAULT_BINS",
    "MAX_N",
    "MIN_OBS_PER_CELL",
    "N_PERM",
    "Estimate",
    "conditional_mutual_information",
    "mutual_information",
    "significance",
    "transfer_entropy",
]

#: Cells per discretised variable. See the module docstring: chosen so the CMI/TE floor (320)
#: sits below `causal_graph.MIN_N` (500), which bins=5 (floor 625) would not.
DEFAULT_BINS = 4
#: Observations a joint histogram needs PER CELL before any estimate is returned.
MIN_OBS_PER_CELL = 5
#: Permutation draws. The same count `causal_graph` uses for its circular-shift null, so a
#: p-value here and a p-value there have the same resolution: the smallest reportable is
#: 1 / (1 + 200) = 0.00498.
N_PERM = 200
#: Most recent observations used, matching `causal_graph.MAX_N` so a transfer entropy and a
#: Granger verdict on the same edge saw the same bars.
MAX_N = 20_000
#: Radix guard: the joint code is a mixed-radix int64, so bins ** d must stay well inside it.
_MAX_CELLS = 1 << 40
#: Above this cardinality the joint histogram is counted by sort rather than by bincount.
_BINCOUNT_MAX = 1 << 22
#: Miller-Madow, named on every result so a consumer never has to guess what was applied.
CORRECTION = "miller-madow"


@dataclass(frozen=True)
class Estimate:
    """One information quantity in nats, or a refusal.

    `value is None` IS the refusal, and `why` says what was missing -- an estimator here never
    returns a number it cannot support. `plugin` is the uncorrected maximum-likelihood value,
    kept so a caller (and the test suite) can see how much bias the correction removed.
    """

    value: float | None
    plugin: float | None = None
    n: int = 0
    bins: int = DEFAULT_BINS
    cells: int = 0
    floor: int = 0
    why: str = ""
    correction: str = CORRECTION

    def __bool__(self) -> bool:
        return self.value is not None

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "plugin": self.plugin, "n": self.n, "bins": self.bins,
                "cells": self.cells, "floor": self.floor, "why": self.why,
                "correction": self.correction}


def _refused(why: str, *, n: int = 0, bins: int = DEFAULT_BINS, cells: int = 0,
             floor: int = 0) -> Estimate:
    return Estimate(value=None, plugin=None, n=n, bins=bins, cells=cells, floor=floor, why=why)


# ------------------------------------------------------------------------------ discretising
def _as_matrix(a: Any, name: str, n: int | None = None) -> np.ndarray:
    """A 1-d series or an (n, k) block of columns, as float64 (n, k)."""
    m = np.asarray(a, dtype="float64")
    if m.ndim == 1:
        m = m[:, None]
    if m.ndim != 2 or m.size == 0:
        raise ValueError(f"{name} must be a 1-d series or a 2-d (n, k) block of series")
    if n is not None and m.shape[0] != n:
        raise ValueError(f"{name} has {m.shape[0]} rows, expected {n} aligned with the others")
    return m


def _digitise(col: np.ndarray, bins: int) -> np.ndarray:
    """Equiprobable bins by quantile EDGES. Ties fall in the same bin, so a degenerate series
    stays degenerate instead of being turned into a ramp; `_occupied` then refuses it."""
    edges = np.quantile(col, np.linspace(0.0, 1.0, bins + 1)[1:-1])
    return np.searchsorted(edges, col, side="right").astype(np.int64)


def _join(cols: Sequence[np.ndarray], bins: int) -> tuple[np.ndarray, int]:
    """Mixed-radix joint code of already-digitised columns, and its cardinality."""
    out = np.zeros(cols[0].size, dtype=np.int64)
    size = 1
    for c in cols:
        out = out * bins + c
        size *= bins
    return out, size


def _entropy(codes: np.ndarray, n: int, size: int) -> tuple[float, int]:
    """Plug-in Shannon entropy in nats, and the number of OCCUPIED cells (Miller-Madow's K)."""
    if size <= _BINCOUNT_MAX:
        counts = np.bincount(codes, minlength=size)
    else:
        counts = np.unique(codes, return_counts=True)[1]
    counts = counts[counts > 0]
    p = counts.astype("float64") / float(n)
    return float(-(p * np.log(p)).sum()), int(counts.size)


def _mm(h: float, k: int, n: int) -> float:
    """Miller-Madow: the plug-in entropy is biased DOWNWARD by (K - 1) / 2N, where K is the
    number of occupied cells. Adding it back to each entropy propagates through the MI and CMI
    identities into a correction that removes the leading upward bias of the information."""
    return h + (k - 1) / (2.0 * n)


def _prepare(blocks: Sequence[tuple[str, np.ndarray]], bins: int, max_n: int,
             ) -> tuple[list[np.ndarray], int, str]:
    """Drop non-finite rows across every block, keep the most recent `max_n`, discretise.

    Returns (digitised columns in block order, n, why) -- `why` non-empty means refuse.
    """
    stacked = np.column_stack([m for _, m in blocks])
    ok = np.all(np.isfinite(stacked), axis=1)
    stacked = stacked[ok]
    if stacked.shape[0] > max_n:
        stacked = stacked[-max_n:]
    n = int(stacked.shape[0])
    if n < 2:
        return [], n, f"{n} finite aligned observations: nothing to estimate"
    cols = [_digitise(stacked[:, j], bins) for j in range(stacked.shape[1])]
    at = 0
    for name, m in blocks:
        for j in range(m.shape[1]):
            if np.unique(cols[at + j]).size < 2:
                col = f"{name} column {j}" if m.shape[1] > 1 else name
                return [], n, (f"{col} occupies a single bin after discretisation -- it is "
                               f"constant or so tied that {bins} quantile edges collapse")
        at += m.shape[1]
    return cols, n, ""


def _floor(cells: int, min_obs_per_cell: int) -> int:
    return int(cells) * int(min_obs_per_cell)


def _check_bins(bins: int, dims: int) -> None:
    if int(bins) < 2:
        raise ValueError(f"bins must be >= 2 (got {bins}); one bin carries no information")
    if float(bins) ** dims > _MAX_CELLS:
        raise ValueError(f"bins={bins} over {dims} variables is {bins ** dims} cells; the joint "
                         f"code is an int64 mixed radix and refuses beyond {_MAX_CELLS}")


# -------------------------------------------------------------------------------- estimators
def mutual_information(x: Any, y: Any, *, bins: int = DEFAULT_BINS, max_n: int = MAX_N,
                       min_obs_per_cell: int = MIN_OBS_PER_CELL) -> Estimate:
    """I(X;Y) = H(X) + H(Y) - H(X,Y) in nats, on equiprobable bins, Miller-Madow corrected.

    Symmetric and undirected: it says the two series share information, never which way it
    ran. Zero means independent AT THIS BIN COUNT -- a dependence finer than the quantile grid
    is invisible here, which is the price of a histogram estimator and is why the grid is
    stated on every result.

    REFUSES below `bins ** 2 * min_obs_per_cell` observations (80 at the defaults) and when
    either series occupies a single bin after discretisation.
    """
    _check_bins(bins, 2)
    xm = _as_matrix(x, "x")
    ym = _as_matrix(y, "y", n=xm.shape[0])
    if xm.shape[1] != 1 or ym.shape[1] != 1:
        raise ValueError("mutual_information takes two 1-d series; condition with "
                         "conditional_mutual_information instead of widening x or y")
    cells = int(bins) ** 2
    floor = _floor(cells, min_obs_per_cell)
    cols, n, why = _prepare([("x", xm), ("y", ym)], bins, max_n)
    if why:
        return _refused(why, n=n, bins=bins, cells=cells, floor=floor)
    if n < floor:
        return _refused(
            f"n={n} below the floor of {floor} = {cells} cells ({bins} bins x {bins} bins) "
            f"x {min_obs_per_cell} observations per cell", n=n, bins=bins, cells=cells,
            floor=floor)
    cx, cy = cols[0], cols[1]
    hx, kx = _entropy(cx, n, bins)
    hy, ky = _entropy(cy, n, bins)
    cxy, sxy = _join([cx, cy], bins)
    hxy, kxy = _entropy(cxy, n, sxy)
    plugin = hx + hy - hxy
    value = _mm(hx, kx, n) + _mm(hy, ky, n) - _mm(hxy, kxy, n)
    return Estimate(value=float(value), plugin=float(plugin), n=n, bins=int(bins), cells=cells,
                    floor=floor)


def conditional_mutual_information(x: Any, y: Any, z: Any, *, bins: int = DEFAULT_BINS,
                                   max_n: int = MAX_N,
                                   min_obs_per_cell: int = MIN_OBS_PER_CELL) -> Estimate:
    """I(X;Y|Z) = H(X,Z) + H(Y,Z) - H(X,Y,Z) - H(Z) in nats, Miller-Madow corrected.

    THE TEST THAT SEPARATES A MECHANISM FROM A SHARED DRIVER. I(X;Y) is large whenever X and Y
    are both moved by something; I(X;Y|Z) is large only when X and Y still share information
    once Z is held fixed. On this book Z is usually the dollar, and an edge whose MI is large
    and whose CMI is ~0 is not an edge -- it is two instruments reading the same clock.

    `z` is one series or an (n, k) block of conditioning series. Each column costs a factor of
    `bins` in the histogram, so the floor grows as bins ** (2 + k): 320 observations for one
    conditioner at the defaults, 1280 for two, 5120 for three. That growth is the honest cost
    of conditioning and the estimator REFUSES rather than spreading a thin sample over cells.

    WHAT IT CANNOT DO, AND HOW TO READ IT ANYWAY. Conditioning is only as fine as the grid. A
    confounder binned into 4 quantiles is held fixed only to WITHIN a quantile, so the
    within-bin variation of Z survives and leaves X and Y with residual shared information that
    is not a mechanism. Measured 2026-09-09, N = 6000, bins = 4, six seeds:

        pure shared driver   Z~N(0,1), X = Z+0.3e1, Y = Z+0.3e2
                             MI 0.58-0.60 nats, CMI 0.025-0.029 nats  (95-96% removed)
        real mechanism too   Y = Z + 0.8X + 0.3e2
                             MI 0.82-0.85 nats, CMI 0.138-0.142 nats  (~5x the residual above)

    A finer grid shrinks the residual and raises the floor: at bins=6 the shared-driver CMI
    falls to 0.011 nats (1.6% of MI) and the floor rises to 1080 observations, at bins=8 to
    0.015 nats and 2560. Nor is a DISCRETE driver exempt -- quantile edges computed on tied
    values land ON a cluster rather than between two, so a 4-state driver in 4 bins is recovered
    imperfectly and leaves 0.01-0.06 nats of its own.

    THE CONSEQUENCE, AND IT IS THE IMPORTANT LINE IN THIS MODULE. That residual is real
    conditional dependence GIVEN THE BINNED Z, so a permutation test finds it significant: the
    within-Z null returns p = 0.005 for the pure shared driver above, exactly as it does for the
    genuine mechanism. THE P-VALUE THEREFORE DOES NOT SEPARATE A MECHANISM FROM A SHARED DRIVER
    AND MUST NOT BE READ AS IF IT DID. What separates them is the MAGNITUDE: CMI at ~4% of MI
    is a driver, CMI at ~17% of MI with the same conditioner is something else. Read the ratio,
    use the p-value only to rule out the case where even the residual is noise.
    """
    xm = _as_matrix(x, "x")
    n_rows = xm.shape[0]
    ym = _as_matrix(y, "y", n=n_rows)
    zm = _as_matrix(z, "z", n=n_rows)
    if xm.shape[1] != 1 or ym.shape[1] != 1:
        raise ValueError("x and y must each be a single 1-d series; only z may have columns")
    kz = int(zm.shape[1])
    _check_bins(bins, 2 + kz)
    cells = int(bins) ** (2 + kz)
    floor = _floor(cells, min_obs_per_cell)
    cols, n, why = _prepare([("x", xm), ("y", ym), ("z", zm)], bins, max_n)
    if why:
        return _refused(why, n=n, bins=bins, cells=cells, floor=floor)
    if n < floor:
        return _refused(
            f"n={n} below the floor of {floor} = {cells} cells ({bins} bins over "
            f"{2 + kz} variables) x {min_obs_per_cell} observations per cell", n=n, bins=bins,
            cells=cells, floor=floor)
    cx, cy, cz = cols[0], cols[1], cols[2:]
    zc, sz = _join(cz, bins)
    xzc, sxz = _join([cx, *cz], bins)
    yzc, syz = _join([cy, *cz], bins)
    xyzc, sxyz = _join([cx, cy, *cz], bins)
    hz, kz_obs = _entropy(zc, n, sz)
    hxz, kxz = _entropy(xzc, n, sxz)
    hyz, kyz = _entropy(yzc, n, syz)
    hxyz, kxyz = _entropy(xyzc, n, sxyz)
    plugin = hxz + hyz - hxyz - hz
    value = (_mm(hxz, kxz, n) + _mm(hyz, kyz, n) - _mm(hxyz, kxyz, n) - _mm(hz, kz_obs, n))
    return Estimate(value=float(value), plugin=float(plugin), n=n, bins=int(bins), cells=cells,
                    floor=floor)


def transfer_entropy(source: Any, target: Any, *, lag: int = 1, k: int = 1,
                     bins: int = DEFAULT_BINS, max_n: int = MAX_N,
                     min_obs_per_cell: int = MIN_OBS_PER_CELL) -> Estimate:
    """TE(source -> target) = I(source_{t-lag} ; target_t | target_{t-1..t-k}) in nats.

    IT IS THAT CMI, NOT A COUSIN OF IT. The body builds the three lagged blocks and hands them
    straight to `conditional_mutual_information`; there is no second entropy implementation
    here, so the two quantities CANNOT drift apart under maintenance. The tests pin the identity
    by constructing the same blocks by hand and asserting equality of the returned value.

    WHY IT IS DIRECTED WHEN MI IS NOT. Conditioning on the target's OWN past is what makes this
    a flow rather than a coincidence: whatever the target could already have predicted about
    itself is removed before the source is asked to contribute. What is left is the uncertainty
    about target_t that only the source's past resolves. That is the information-theoretic
    statement of the Granger question, and unlike the regression form it does not require the
    dependence to be linear, monotone, or even signed.

    `lag` >= 1 -- a contemporaneous "flow" is not a flow, and `causal_graph._pairs` refuses lag
    0 for the same reason. `k` is how many of the target's own lags are conditioned on; each one
    costs a factor of `bins` in the histogram, so k=1 (floor 320) is the default and k=2 (floor
    1280) needs a long series to be worth asking for.

    REFUSES when the series is shorter than max(lag, k) + the CMI floor, and inherits every
    refusal `conditional_mutual_information` can make.
    """
    if int(lag) < 1:
        raise ValueError(f"lag must be >= 1 (got {lag}); X_t -> Y_{{t+h}} needs h >= 1")
    if int(k) < 1:
        raise ValueError(f"k must be >= 1 (got {k}); transfer entropy conditions on at least "
                         "one own lag of the target, or it is a plain mutual information")
    s = _as_matrix(source, "source")
    t = _as_matrix(target, "target", n=s.shape[0])
    if s.shape[1] != 1 or t.shape[1] != 1:
        raise ValueError("transfer_entropy takes two 1-d series")
    lag, k = int(lag), int(k)
    n_raw = s.shape[0]
    start = max(lag, k)
    cells = int(bins) ** (2 + k)
    floor = _floor(cells, min_obs_per_cell)
    if n_raw - start < 2:
        return _refused(
            f"series of {n_raw} leaves {max(0, n_raw - start)} usable rows after dropping the "
            f"first max(lag={lag}, k={k})={start}", n=max(0, n_raw - start), bins=bins,
            cells=cells, floor=floor)
    src_past = s[start - lag:n_raw - lag, 0]
    tgt_now = t[start:, 0]
    tgt_past = np.column_stack([t[start - j:n_raw - j, 0] for j in range(1, k + 1)])
    est = conditional_mutual_information(src_past, tgt_now, tgt_past, bins=bins, max_n=max_n,
                                         min_obs_per_cell=min_obs_per_cell)
    if est.value is None:
        return replace(est, why=f"transfer entropy at lag={lag}, k={k}: {est.why}")
    return est


# ------------------------------------------------------------------------ the permutation null
def _shuffled(src: np.ndarray, rng: np.random.Generator, mode: str, within: np.ndarray | None,
              min_shift: int) -> np.ndarray:
    n = src.size
    if mode == "circular_shift":
        return np.roll(src, int(rng.integers(min_shift, n - min_shift)))
    if within is None:
        return rng.permutation(src)
    out = src.copy()
    for g in np.unique(within):
        idx = np.flatnonzero(within == g)
        if idx.size > 1:
            out[idx] = src[rng.permutation(idx)]
    return out


def significance(stat_fn: Callable[..., Estimate], source: Any, *rest: Any,
                 n_perm: int = N_PERM, seed: int = 0, mode: str = "shuffle",
                 within: Any | None = None, bins: int = DEFAULT_BINS,
                 min_shift: int | None = None, **kwargs: Any) -> dict[str, Any]:
    """Empirical p-value for any estimator here, by permuting THE SOURCE ONLY.

    AN EFFECT SIZE WITH NO NULL IS NOT EVIDENCE. Every information quantity in this module is
    non-negative in expectation under dependence and noisily non-zero under independence, so
    "TE = 0.004 nats" says nothing on its own. The null answers the only question that matters:
    how large would this statistic have been if the directed relation were destroyed and
    nothing else changed?

    WHY THE SOURCE AND ONLY THE SOURCE. A permutation is a bijection, so both marginal
    distributions survive it exactly -- the source keeps its own histogram, the target keeps
    its own past, and the ONLY thing broken is the correspondence between them. Permuting the
    target instead would break the target's own autocorrelation, which is part of the
    conditioning set, and would test a different hypothesis.

    THE THREE NULLS, AND WHEN EACH IS THE RIGHT ONE.

    `mode="shuffle"` (default) draws a free permutation of the source. Correct for MI and for
    any source without memory. On an AUTOCORRELATED source it is ANTI-CONSERVATIVE: it destroys
    the source's own persistence as well as the relation, so the null statistic is smaller than
    it should be and p is too small. `causal_graph.incremental_information` learned this and
    uses a circular shift for exactly this reason.

    `mode="circular_shift"` rolls the source by a random offset of at least `min_shift`
    (default: 5% of the sample, never below 10). The source's autocorrelation survives intact
    and only the alignment with the target is destroyed -- the conservative null, and the one
    to use on bar returns.

    `within=<series>` restricts the permutation to blocks of equal (discretised) `within`, and
    is THE correct null for a conditional statistic. A free shuffle of X breaks X's relation to
    Z as well as to Y, so it tests plain independence while the statistic measures conditional
    independence -- the null and the statistic then answer different questions. Permuting X
    only among rows sharing a Z-bin keeps X-Z and destroys X-Y|Z. Pass `within=z` alongside
    `conditional_mutual_information`; it aligns index-for-index with `source`, so it is not
    available for `transfer_entropy`, whose conditioning set is built inside the estimator.

    WHAT A SMALL P DOES NOT MEAN. For a CONDITIONAL statistic it does not mean "mechanism". The
    coarse grid leaves residual dependence given the binned conditioner, and that residual is
    itself significant -- measured 2026-09-09, a pure shared driver returns p = 0.005 under the
    within-Z null, the same p as a genuine mechanism. The p-value says the statistic is bigger
    than noise; only the magnitude against the unconditioned MI says what it is. See
    `conditional_mutual_information`.

    Returns a dict, never an exception, carrying `p_value` (None when the observed estimate
    refused, with `why` copied from it), `observed`, `null_mean`, `null_sd`, `n_null` and the
    `mode` used. The p-value is (1 + #{null >= observed}) / (1 + draws) -- the +1 is the
    observed statistic counting itself, so the smallest reportable p at 200 draws is 0.00498
    and a p of exactly 0 is never claimed.
    """
    if mode not in ("shuffle", "circular_shift"):
        raise ValueError(f"unknown mode {mode!r}; use 'shuffle' or 'circular_shift'")
    obs = stat_fn(source, *rest, bins=bins, **kwargs)
    out: dict[str, Any] = {
        "observed": obs.value, "p_value": None, "null_mean": None, "null_sd": None,
        "n_null": 0, "n_perm": int(n_perm), "mode": mode, "n": obs.n, "bins": obs.bins,
        "floor": obs.floor, "cells": obs.cells, "correction": obs.correction,
        "within": within is not None, "why": obs.why,
    }
    if obs.value is None:
        return out
    src = np.asarray(source, dtype="float64").reshape(-1)
    n = src.size
    shift_floor = int(min_shift) if min_shift is not None else max(10, n // 20)
    if mode == "circular_shift" and n - shift_floor <= shift_floor:
        out["why"] = (f"series of {n} is too short for a circular-shift null with a minimum "
                      f"offset of {shift_floor}")
        return out
    wg: np.ndarray | None = None
    if within is not None:
        w = np.asarray(within, dtype="float64").reshape(-1)
        if w.size != n:
            raise ValueError("`within` must align index-for-index with `source`")
        wg = _digitise(w, int(bins))
    rng = np.random.default_rng(seed)
    draws: list[float] = []
    for _ in range(int(n_perm)):
        got = stat_fn(_shuffled(src, rng, mode, wg, shift_floor), *rest, bins=bins, **kwargs)
        if got.value is not None:
            draws.append(float(got.value))
    if len(draws) < int(n_perm) // 2:
        out["n_null"] = len(draws)
        out["why"] = (f"only {len(draws)} of {n_perm} permutation draws produced an estimate; "
                      "a null this thin is not a null")
        return out
    null = np.asarray(draws, dtype="float64")
    out.update({
        "p_value": float((1.0 + float((null >= float(obs.value)).sum())) / (1.0 + null.size)),
        "null_mean": float(null.mean()),
        "null_sd": float(null.std(ddof=1)) if null.size > 1 else 0.0,
        "n_null": int(null.size),
        "min_shift": shift_floor if mode == "circular_shift" else None,
    })
    return out
