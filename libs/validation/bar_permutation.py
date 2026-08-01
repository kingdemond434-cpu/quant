"""BAR PERMUTATION -- a null built from the real asset, with the temporal order destroyed.

PROVENANCE. neurotrader's "In-Sample and Walk-Forward Monte Carlo Permutation Tests" (2026-08-01
batch), which is the Aronson/Masters construction: decompose OHLC bars into gaps and intra-bar
moves, shuffle each independently, reassemble. Adopted because it is a NUMBERS-AND-METHOD source,
the category that has converted 4/4 on this desk against 0/13 for spoken mechanisms.

WHAT THIS DESK ALREADY HAS, AND WHY THIS IS NOT A SECOND CORRECTION. The source's headline use --
re-optimise a parameter grid on each permutation to price the optimisation's selection bias -- is
NOT adopted, and the reason is measured rather than stylistic. `libs.autodiscovery.generators`
declares its param variants UP FRONT (`GeneratorSpec.param_variants`) and expands every variant
into its own candidate that then pays the full cohort multiplicity correction. The parameter
search is therefore ALREADY priced, as trials. Wrapping a second search-bias correction around it
is the double-correction defect class (rubric #4) -- the same shape as the DSR-plus-Romano-Wolf
stack the 2026-08-01 audit found, which had driven gate power to ~0%.

WHAT IS GENUINELY MISSING, and it is the null. Every null this desk owns is one of:

    stationary block bootstrap   -- resamples blocks, so it PRESERVES short-horizon serial
                                    dependence: it cannot answer "did the order matter"
    positive_control.null_cohort -- parametric Student-t draws: right dispersion, but no fat-tail
                                    clustering, no intra-bar geometry, not this asset
    reality_check / Romano-Wolf  -- cross-sectional over the candidate cohort, not over data

None of them is "this asset's own bars, temporally scrambled". That null is what isolates the one
question a price-pattern strategy lives or dies on: is there information in the SEQUENCE, or only
in the marginal distribution the asset would have handed you anyway?

THE PROPERTY THAT MAKES IT DISCRIMINATE, and it is exact rather than approximate. Total log return
over the permuted window EQUALS the real total log return, because close-to-close log return
decomposes as gap + intra-bar close move and shuffling preserves both sums. So a candidate that is
simply LONG A TRENDING ASSET scores identically on the permutation and gets p ~ 1: the drift is
still there, the timing is gone. That is precisely the asset-drift discrimination
`robustness_filters` declined to buy with a blanket Sharpe cap, obtained here without rejecting
exceptional strategies along with it.

WHERE THIS DEPARTS FROM THE SOURCE, because the departure was forced by measurement. The source
shuffles gaps and intra-bar moves with two INDEPENDENT permutations. Close-to-close return is
their sum and the two are negatively correlated in real bars, so independent shuffling drops the
covariance term and INFLATES the permuted variance -- the null becomes easier to beat than the
asset. The buy-and-hold control measured it directly: a rule with zero timing skill by
construction scored p = 0.007, so every p-value the module produced was inflated by that much.
Carrying each gap with its own bar makes close-to-close returns an exact PERMUTATION of the real
ones: every moment preserved, order still destroyed, and buy-and-hold's p-value back up around
0.9 where a zero-skill rule belongs. (Not exactly 1.0 -- reassembly is a cumulative sum and
accumulates rounding near 1e-12, so the tie is broken by float dust. The mathematical statement is
exact; the floating one is not, and the tests pin both.) `permutation_moment_report` still
MEASURES all of this rather than asserting it, because a construction that is right today is not
automatically right after the next edit.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: The source's figures, kept because they are calibration and not taste. 1,000 permutations gives
#: a p-value resolution of 1/1001; 100 is the hard floor below which the smallest attainable
#: p-value (1/101 = 0.0099) sits right on top of the 1% threshold and the test cannot resolve it.
DEFAULT_PERMUTATIONS = 1_000
MIN_PERMUTATIONS = 100


@dataclass(frozen=True)
class Bars:
    """Log-space OHLC. Log because the decomposition is additive there and only there."""

    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray

    def __post_init__(self) -> None:
        n = len(self.close)
        if any(len(a) != n for a in (self.open, self.high, self.low)):
            raise ValueError("open/high/low/close must be the same length")
        if n < 3:
            raise ValueError(f"need at least 3 bars to permute, got {n}")

    def __len__(self) -> int:
        return len(self.close)


def to_log_bars(o: np.ndarray, h: np.ndarray, low: np.ndarray, c: np.ndarray) -> Bars:
    """Price-space OHLC -> log-space Bars, rejecting anything the decomposition cannot represent.

    NON-POSITIVE PRICES RAISE rather than producing -inf and propagating silently through the
    shuffle into a reassembled series full of NaN. A zero or negative price in an OHLC feed is a
    corrupt bar, not a market event.
    """
    arrs = [np.asarray(x, dtype="float64") for x in (o, h, low, c)]
    if any(not np.all(np.isfinite(a)) for a in arrs):
        raise ValueError("OHLC contains non-finite values -- clean the feed, do not permute it")
    if any(np.any(a <= 0.0) for a in arrs):
        raise ValueError("OHLC contains non-positive prices -- the log decomposition is undefined")
    lo_, lh, ll, lc = (np.log(a) for a in arrs)
    return Bars(open=lo_, high=lh, low=ll, close=lc)


def invalid_bars(b: Bars) -> np.ndarray:
    """Bars violating high >= max(open, close) or low <= min(open, close).

    The permutation's high/low guarantee is INHERITED from the input: it holds on every permuted
    bar if and only if it held on every real one. Checking the input is therefore not hygiene, it
    is the precondition of the output guarantee.
    """
    hi_ok = b.high >= np.maximum(b.open, b.close)
    lo_ok = b.low <= np.minimum(b.open, b.close)
    bad: np.ndarray = ~(hi_ok & lo_ok)
    return bad


def permute_bars(b: Bars, *, rng: np.random.Generator, start: int = 0) -> Bars:
    """One permutation: shuffle gaps and intra-bar geometry, reassemble.

    THE INTRA-BAR TRIPLE MOVES AS A UNIT. (high-open, low-open, close-open) are shuffled with a
    SINGLE index permutation, not three. Shuffling them independently would pair a bar's high with
    another bar's close and routinely produce close > high -- a series no exchange could emit,
    against which any high/low-touching rule scores nonsense. Keeping the triple together also
    preserves each bar's internal character: a bar that closed on its high still closes on its
    high, somewhere else in time.

    THE GAP TRAVELS WITH ITS OWN BAR, and this is a CORRECTION to the source construction rather
    than a restatement of it. Aronson/Masters and the neurotrader video shuffle the gap series and
    the intra-bar series with two INDEPENDENT permutations. That is measurably biased, and the
    buy-and-hold control in tests/validation/test_bar_permutation_discrimination.py caught it:
    real gaps and real intra-bar closes are negatively correlated (a gap partly reverses inside
    the bar), close-to-close return is their SUM, and independent shuffling drops the covariance
    term and inflates the permuted variance. The permuted series then had systematically lower
    Sharpe than the real one, and BUY-AND-HOLD -- which has zero timing skill by construction --
    scored p = 0.007. Every p-value the module produced was inflated by that much.

    Carrying the gap with its own bar fixes it at the root rather than approximately: close-to-
    close log returns become an exact PERMUTATION of the real ones, so mean, variance and every
    higher moment are preserved, while the ORDER -- the only thing under test -- is still
    destroyed. Buy-and-hold then scores ~0.9 instead of 0.007, and the residual gap from 1.0 is
    cumulative-sum rounding near 1e-12, not bias.

    ``start`` FREEZES A PREFIX. Bars before ``start`` are copied through untouched and only the
    suffix is shuffled. This is the walk-forward variant: optimise or fit on real in-sample data,
    then ask whether the out-of-sample stretch could have arisen with no temporal signal in it.
    Permuting the whole series would also scramble the data the rule was fitted on and would
    answer a different question.
    """
    n = len(b)
    if not 0 <= start < n - 1:
        raise ValueError(f"start must be in [0, {n - 1}), got {start}")

    # Gaps are defined against the PREVIOUS close, so index 0 has none. When start == 0 the first
    # bar is the anchor and its gap is not part of the shuffled pool.
    first = max(start, 1)
    gaps = b.open[first:] - b.close[first - 1:-1]
    d_high = b.high[first:] - b.open[first:]
    d_low = b.low[first:] - b.open[first:]
    d_close = b.close[first:] - b.open[first:]

    m = len(gaps)
    # ONE index set for the gap AND the whole intra-bar triple -- see the docstring. Independent
    # permutations were the source's construction and they are biased; a second permutation here
    # would silently reintroduce a p = 0.007 buy-and-hold.
    perm = rng.permutation(m)
    g, dh, dl, dc = gaps[perm], d_high[perm], d_low[perm], d_close[perm]

    out_o, out_h = b.open.copy(), b.high.copy()
    out_l, out_c = b.low.copy(), b.close.copy()
    # Sequential because each bar's open is anchored to the PREVIOUS permuted close: the series is
    # a cumulative sum of shuffled increments, which is what makes the reassembled path a real
    # path rather than a cloud of independent points.
    for k in range(m):
        i = first + k
        out_o[i] = out_c[i - 1] + g[k]
        out_h[i] = out_o[i] + dh[k]
        out_l[i] = out_o[i] + dl[k]
        out_c[i] = out_o[i] + dc[k]
    return Bars(open=out_o, high=out_h, low=out_l, close=out_c)


def permutation_pvalue(real_stat: float, perm_stats: np.ndarray) -> float:
    """The quasi-p-value, with the +1 that stops it ever being zero.

    ``(#{permuted >= real} + 1) / (N + 1)``. The +1 counts the REAL series as one of its own
    reference draws, which is not a fudge: under the null the real series is exchangeable with the
    permutations, so excluding it biases the p-value down. Without it a strategy that beat all
    1,000 permutations reports p = 0 -- "impossible under the null" from 1,000 draws, which no
    finite sample can license. The floor is 1/(N+1), and that is the honest resolution limit.

    NON-FINITE PERMUTATION STATS ARE DROPPED AND THE DENOMINATOR SHRINKS WITH THEM. A permuted run
    that produced no trades and hence no Sharpe is not evidence that the real result is special;
    counting it as a loss for the null would inflate significance in exactly the direction a
    researcher wants.
    """
    s = np.asarray(perm_stats, dtype="float64")
    s = s[np.isfinite(s)]
    if s.size < MIN_PERMUTATIONS:
        raise ValueError(
            f"{s.size} usable permutations, need at least {MIN_PERMUTATIONS}: below that the "
            f"smallest attainable p-value ({1 / (s.size + 1):.4f} here) cannot resolve a 1% "
            "threshold and the test reports significance it did not measure")
    if not np.isfinite(real_stat):
        return 1.0
    return float((np.sum(s >= real_stat) + 1) / (s.size + 1))


def permutation_moment_report(b: Bars, perms: list[Bars]) -> dict[str, object]:
    """What the permutation actually preserved, measured rather than claimed.

    Exists because the source asserts the permutation "preserves the statistical moments" and that
    is only partly true. Drift is preserved EXACTLY (algebra, tested); close-to-close variance is
    not, and by how much depends on the gap/intra-bar covariance in the specific asset. A caller
    reading a p-value deserves to see how far its null sits from the real series.
    """
    def cc(x: Bars) -> np.ndarray:
        return np.diff(x.close)

    real_cc = cc(b)
    real_drift = float(b.close[-1] - b.close[0])
    drifts = np.array([float(p.close[-1] - p.close[0]) for p in perms])
    variances = np.array([float(np.var(cc(p), ddof=1)) for p in perms])
    real_var = float(np.var(real_cc, ddof=1))
    ac1 = np.array([float(np.corrcoef(cc(p)[:-1], cc(p)[1:])[0, 1]) for p in perms])
    real_ac1 = float(np.corrcoef(real_cc[:-1], real_cc[1:])[0, 1])
    return {
        "n_permutations": len(perms),
        "drift_preserved_exactly": bool(np.allclose(drifts, real_drift, atol=1e-9)),
        "real_total_log_return": real_drift,
        "max_abs_drift_error": float(np.max(np.abs(drifts - real_drift))) if perms else None,
        "real_cc_variance": real_var,
        "median_permuted_cc_variance": float(np.median(variances)) if perms else None,
        "variance_ratio_median": float(np.median(variances) / real_var) if real_var > 0 else None,
        "real_lag1_autocorr": real_ac1,
        "median_permuted_lag1_autocorr": float(np.median(ac1)) if perms else None,
        "note": ("with each gap carried on its own bar, close-to-close returns are an exact "
                 "reordering of the real ones, so drift AND variance are preserved (ratio ~1.0) "
                 "up to cumulative-sum rounding. A variance ratio drifting away from 1.0 means "
                 "the gap/bar pairing has been broken and the null is biased -- that is the "
                 "defect the buy-and-hold control caught at p=0.007. lag-1 autocorrelation going "
                 "to ~0 is the null working."),
    }
