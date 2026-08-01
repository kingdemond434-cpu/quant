"""OPERATOR GRAMMAR -- functional forms, not trade ideas, aimed at the ONE thing this desk has
measured as its binding constraint.

WHY THIS FILE EXISTS, and it is not "more candidates". `libs/research/cohort_independence.py`
already settled that question with numbers: 101 real production alphas average 15.9% pairwise
correlation, which under the equicorrelation approximation is 101 / (1 + 100 * 0.159) = 6.0
independent bets. Widening the same cohort from 101 to 420 candidates buys
420 / (1 + 419 * 0.159) = 6.2 -- THREE TENTHS of one extra bet for four times the multiplicity
burden. Breadth is not the lever. ORTHOGONALITY is. A candidate that is 15.9% correlated to
everything already in the book is, to a first approximation, already in the book.

WHY OPERATORS AND NOT FORMULAS. The 2026-08-01 transcript batch (a WorldQuant BRAIN webinar; the
same institution behind the 101-alpha study cited above) is mostly a catalogue of specific alpha
expressions, and those are worth nothing here -- a published formula is a crowded formula, and a
crowded formula on crypto perpetuals is somebody else's exit liquidity. The OPERATORS underneath
them are a different object. `rank`, `group_rank`, `vector_neut`, `ts_backfill` carry no view, no
universe and no crowding; they are algebra. Algebra ports when the formulas built from it do not.
That is the whole reason this file is operators rather than a fifth family of signals.

WHAT IS BUILT, in descending order of how much it should matter to this desk:

  1. `vector_neut` -- THE MOST VALUABLE FUNCTION HERE, by a distance. It is the direct mechanical
     attack on the redundancy measured above: hand it a new candidate and the cohort it must be
     distinct from, and it returns the part of the candidate that the cohort cannot explain. This
     turns "we hope the new candidate is different" into "the new candidate is orthogonal by
     construction, and what survives the orthogonalisation is the only part worth testing". Run on
     the benchmark cohort the arithmetic is stark: dragging 101 alphas from rho = 0.159 to
     rho = 0.05 moves them from 6.0 to 101 / (1 + 100 * 0.05) = 16.8 independent bets. Nothing
     else in this file has that leverage. MEASURED, not argued: on a synthetic cohort of 10
     candidates sharing one common factor, `cohort_independence.measure` reads
     rho = 0.845 -> 1.2 independent bets; neutralising each candidate against a 6-alpha incumbent
     set plus an intercept takes the SAME ten candidates to rho = 0.035 -> 7.6 bets. Ten
     candidates that were worth one are worth seven, with no new data and no new mechanism.

  2. `group_rank` -- rank within peer group rather than globally. The webinar's worked example
     changed `rank` to `group_rank` and NOTHING ELSE, and moved the expression from
     below-submittable fitness to submittable while cutting maximum drawdown from roughly 30% to
     roughly 6%. The reason is not statistical cleverness: a default probability, a leverage
     ratio, a book-to-price is only interpretable against industry peers, so a global rank of a
     ratio spends most of its variance on the industry composition of the universe. The crypto
     analogue is exact -- ranking a funding rate globally ranks L1s against memecoins against
     LSTs, and the resulting "signal" is mostly a sector bet nobody chose to take.

  3. `ts_backfill` -- forward-fill, capped at `d` periods, never from the future. The webinar is
     explicit about the part that is not obvious: an unfilled gap does not merely lose data, it
     INFLATES TURNOVER. A NaN -> value transition reads to a position sizer as flat -> fully-on
     and is charged a round trip, whether or not the underlying view changed at all. That makes a
     data-coverage defect present itself as a strategy that trades too much, which is the wrong
     diagnosis and gets the wrong fix.

  4. `ts_information_ratio` -- ts_mean(x, d) / ts_std(x, d). The "is the mean also STABLE" template:
     it asks not whether a quantity is high but whether it has been reliably high, which is the
     same question a Sharpe ratio asks and the same question this desk's gates ask.

AXIS CONVENTION, stated once and enforced everywhere below. Arrays are 1-D or 2-D. A 2-D array is
ALWAYS (observations x names) -- time down the rows, instruments across the columns, matching
`libs/research/crypto_xsec.py` and every panel in the repo. Cross-sectional operators
(`group_rank`) act ACROSS a row; time-series operators (`ts_backfill`, `ts_information_ratio`) act
DOWN a column. `vector_neut` is the one operator that is used both ways, so it defines its
contraction axis explicitly as the LAST axis of `a` -- see its docstring.

NO LOOKAHEAD ANYWHERE. Every `ts_` function here computes out[i] from x[..i] only, and both are
covered by prefix-invariance tests (truncating the input cannot change an earlier output). This is
not a formality: the desk's own `ewma_variance` carries the same warning because the off-by-one is
the difference between a forecast and a description, and the version that reads its own bar
produces a spectacular backtest that is simply reading the answer.

FLOATING-POINT DUST IS A NAMED ENEMY IN THIS FILE. On 2026-08-01 a `rv > 0` guard in
`volatility_signals.py` let the variance of a constant series (~5e-38, not 0.0) through and shipped
a prediction premium of 1.4e31 -- a colossal fictional signal that fired on every bar of every
pegged, halted or frozen series. Every divisor here is guarded by a MEANINGFUL floor rather than
`> 0`, and the floors are chosen in the same units and with the same reasoning as that file's
`_VAR_FLOOR`.

STATUS: DRAFTED, NOT BUILT. Per the desk's own standard, a module with tests and no production
importer is drafted. Nothing in `scripts/` imports this yet. The two wirings that would make it
built, in order of value: (a) `scripts/run_generation_diversity.py`, which already scores cohort
novelty, should neutralise each new candidate's return series against the accepted cohort before
scoring -- currently it MEASURES redundancy it could instead REMOVE; (b) the cross-sectional
funding signal in `libs/research/crypto_xsec.py` currently ranks funding globally and would be a
one-line `group_rank` change against a sector map, which is precisely the change the webinar
measured as worth 24 points of drawdown. Neither is done here, and this file must not be described
as built until one of them is.

NOT ADOPTED from the same source, recorded rather than dropped:
  * `trade_when` / event-conditioned position holding. It is a genuinely good operator, but its
    value is entirely in the event definition and this desk has no event feed clean enough to
    condition on -- the operator would be a wrapper around an untrusted boolean.
  * The catalogue of specific alpha expressions. Published formula, published crowding. The desk
    has measured what happens to a signal everyone else can read.
  * `scale`/`decay_linear` and friends. Real operators, but the repo already has position sizing
    and smoothing it trusts, and duplicating them here would create two answers to one question.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "group_rank",
    "ts_backfill",
    "ts_information_ratio",
    "vector_neut",
]

#: Squared-norm floor for any vector this file is asked to project onto.
#:
#: THE `> 0` VERSION OF THIS GUARD IS THE BUG CLASS THAT SHIPPED A 1.4e31 SIGNAL IN
#: `volatility_signals.py` ON 2026-08-01, and it arrives here in two shapes rather than one:
#:
#:   b.b EXACTLY 0 (an all-zero neutraliser: an empty cohort column, a symbol with no history) ->
#:   0/0 -> the projection is NaN and the ENTIRE neutralised series comes back NaN, silently, from
#:   what looked like a successful call.
#:
#:   b.b FLOAT DUST (a constant, pegged, halted or frozen column, or one that is a difference of
#:   two near-identical series) -> `> 0` passes. The projection's MAGNITUDE is still bounded by
#:   |a| -- that part of the arithmetic is safe -- but its DIRECTION is computed by catastrophic
#:   cancellation and is therefore pure rounding noise. So the caller gets up to 100% of `a`
#:   subtracted along a direction that means nothing, and receives it labelled "neutralised". That
#:   is worse than a visibly absurd number, because a visibly absurd number gets investigated.
#:
#: The inputs that trigger it are the boring real ones this desk already knows: a pegged pair, a
#: halted market, a dead altcoin, any symbol whose feed froze.
#:
#: Held equal to that file's `_VAR_FLOOR` deliberately, because it is the same quantity in the
#: same units: b.b is a sum of squares, so 1e-20 corresponds to a Euclidean norm of 1e-10 -- ten
#: orders of magnitude below any real price increment, and twenty above float dust.
_DOT_FLOOR = 1e-20

#: Relative rank floor for the multi-vector case. After earlier directions have been removed from
#: a neutraliser column, a residual norm below this FRACTION of the column's original norm means
#: the column carries no direction the basis does not already have -- i.e. it is a duplicate.
#:
#: 1e-10 sits six orders above float64 epsilon (2.2e-16), which leaves room for the error that
#: accumulates through Gram-Schmidt, and far below anything a real alpha column contains. The
#: DIRECTION of the error when this floor is wrong is what makes it safe: dropping a column leaves
#: MORE of the cohort inside the residual, so the failure mode is under-neutralising and honestly
#: reporting residual correlation. The opposite floor choice would manufacture false orthogonality,
#: which is the failure this desk cannot detect downstream.
_RANK_REL_FLOOR = 1e-10

#: Standard-deviation floor for `ts_information_ratio`'s divisor. sqrt(_DOT_FLOOR), i.e. the same
#: 1e-10 in return-standard-deviation units used by `volatility_signals._VAR_FLOOR`. A window whose
#: dispersion is below this has no measurable dispersion, and mean/dust is not a large information
#: ratio -- it is a division by zero that forgot to say so.
_STD_FLOOR = 1e-10

#: Rank assigned to a name that is the only member of its group.
#:
#: NOT 0.0 AND NOT 1.0, and this is the most consequential defaulting decision in the file. 0 and 1
#: are the two most EXTREME positions a rank operator can express, so defaulting a singleton to
#: either one takes the book's largest short (or largest long) in exactly the names about which the
#: operator knows nothing at all. A universe with a handful of orphan sectors -- which is the
#: normal state of a crypto sector map, where new listings arrive without peers -- would then have
#: its biggest bets concentrated entirely in the names with no peer information. 0.5 is the neutral
#: point of a [0, 1] rank: it carries no view, so a singleton contributes no position rather than a
#: maximal one. Unknown must produce a no-op, never an action.
SINGLETON_RANK = 0.5


def _as_panel(x: np.ndarray) -> tuple[np.ndarray, tuple[int, ...]]:
    """Reshape a 1-D or 2-D array to a (obs x names) working copy, remembering the original shape.

    A 1-D input to a time-series operator is a single series, so it becomes (obs x 1). Nothing here
    accepts 3-D: a panel with a third axis is almost always a shape bug at the call site, and
    guessing which axis is time would be exactly the kind of ambiguous branch that must block.
    """
    a = np.asarray(x, dtype="float64")
    if a.ndim == 1:
        return a.reshape(-1, 1).copy(), a.shape
    if a.ndim == 2:
        return a.copy(), a.shape
    raise ValueError(f"expected a 1-D series or a 2-D (obs x names) panel, got ndim={a.ndim}")


def _group_codes(group: np.ndarray) -> np.ndarray:
    """Integer group codes, with -1 marking a MISSING label.

    Missing is NaN for numeric label arrays, and None or blank for string/object ones. A name whose
    group is unknown is NOT swept into a catch-all bucket: a catch-all is a fake peer group, and a
    rank computed against fake peers is indistinguishable from a real one downstream. Unknown
    blocks -- `group_rank` returns NaN for those names.
    """
    g = np.asarray(group)
    if g.dtype.kind in "fc":
        missing = ~np.isfinite(g.astype("float64"))
    elif g.dtype.kind in "iub":
        missing = np.zeros(g.shape, dtype=bool)
    else:
        missing = np.array(
            [v is None
             or (isinstance(v, float) and not np.isfinite(v))
             or (isinstance(v, str) and v.strip() == "")
             for v in g.reshape(-1)],
            dtype=bool,
        ).reshape(g.shape)
    codes = np.full(g.shape, -1, dtype="int64")
    present = ~missing
    if present.any():
        _, inv = np.unique(g[present], return_inverse=True)
        codes[present] = np.asarray(inv).reshape(-1)
    return codes


def _average_ranks(v: np.ndarray) -> np.ndarray:
    """Ranks 1..m with TIES AVERAGED.

    Ties must be averaged rather than broken by position. Competition-style or first-seen tie
    breaking would make the operator depend on column ORDER, so relabelling the universe would
    change the portfolio -- a silent, untraceable source of run-to-run difference. Averaging also
    gives the right degenerate answer: a group whose members are all equal ranks entirely at the
    midpoint, i.e. no view, which is what "these names are indistinguishable" should mean.
    """
    n = int(v.size)
    order = np.argsort(v, kind="stable")
    sv = v[order]
    ranks = np.empty(n, dtype="float64")
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sv[j + 1] == sv[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0     # mean of the ranks i+1 .. j+1
        i = j + 1
    return ranks


def _group_rank_1d(v: np.ndarray, codes: np.ndarray) -> np.ndarray:
    """One cross-section: rank each finite, labelled value against its own group only."""
    out = np.full(v.shape, np.nan, dtype="float64")
    valid = np.isfinite(v) & (codes >= 0)
    if not valid.any():
        return out
    for c in np.unique(codes[valid]):
        idx = np.flatnonzero(valid & (codes == c))
        m = int(idx.size)
        if m == 1:
            out[idx[0]] = SINGLETON_RANK
            continue
        # (r - 1) / (m - 1) rather than r / (m + 1): the endpoints must actually REACH 0 and 1.
        # An interior-only mapping shrinks every group's spread, and shrinks it MORE for small
        # groups, which quietly turns group size into a position weight nobody chose.
        out[idx] = (_average_ranks(v[idx]) - 1.0) / (m - 1.0)
    return out


def group_rank(x: np.ndarray, group: np.ndarray) -> np.ndarray:
    """Rank within peer group, returned in [0, 1]. Cross-sectional: acts ACROSS a row.

    `x` is a 1-D cross-section (names,) or a 2-D panel (observations x names).
    `group` is either one label per name -- shape (names,), a static sector map -- or the same
    shape as `x`, which is the case that matters for crypto because sector membership is not
    static: a token migrates from "new listing" to "L2" to "dead", and pinning it to its
    first-observed sector would rank it against peers it no longer has.

    WHY THIS IS WORTH MORE THAN IT LOOKS. The webinar's worked example changed `rank` to
    `group_rank` and nothing else, and the expression went from below-submittable fitness to
    submittable with maximum drawdown falling from roughly 30% to roughly 6%. The mechanism is
    interpretive, not statistical: a ratio is only meaningful against peers, so a GLOBAL rank of a
    per-name ratio spends most of its variance on universe composition. Rank funding globally
    across crypto perpetuals and the top decile is whatever sector is hot this month; rank it
    within sector and it is the names that are expensive RELATIVE TO THINGS THAT TRADE LIKE THEM,
    which is the bet that was actually intended.

    HANDLING, all three cases deliberate:
      * group of size 1 -> `SINGLETON_RANK` (0.5). See that constant: 0 and 1 are the operator's
        most extreme outputs and must never be the default for a name with no peers.
      * non-finite `x` -> NaN out. There is no rank for a value that does not exist, and filling
        it with the group midpoint would put a real position on a missing observation.
      * missing group label -> NaN out. No catch-all bucket; see `_group_codes`.
    Unequal group sizes need no special handling because each group is normalised by its own
    (m - 1), which is the entire point of ranking within group.
    """
    a = np.asarray(x, dtype="float64")
    if a.ndim not in (1, 2):
        raise ValueError(f"expected a 1-D cross-section or 2-D (obs x names) panel, got {a.ndim}-D")
    g = np.asarray(group)
    codes = _group_codes(g)
    if a.ndim == 1:
        if codes.shape != a.shape:
            raise ValueError(f"group shape {g.shape} does not match cross-section {a.shape}")
        return _group_rank_1d(a, codes)
    if codes.shape == (a.shape[1],):
        codes = np.broadcast_to(codes, a.shape)
    elif codes.shape != a.shape:
        raise ValueError(f"group shape {g.shape} must be (names,) or {a.shape}")
    out = np.empty(a.shape, dtype="float64")
    for t in range(a.shape[0]):
        out[t] = _group_rank_1d(a[t], codes[t])
    return out


def _neutralise_1d(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """One contraction: `a` is (n,), `b` is (n, k). Returns the part of `a` orthogonal to span(b).

    MODIFIED GRAM-SCHMIDT, NOT `lstsq`, and the choice is not stylistic. Both give the same answer
    when `b` has full column rank; they differ exactly where this desk lives. The cohort this
    function exists to neutralise against is MEASURED at 15.9% mean pairwise correlation, so `b` is
    routinely near-collinear -- redundant alphas are the input, not the exception. On a
    rank-deficient `b`, `lstsq` silently returns the minimum-norm solution: it produces coefficients
    without ever announcing that the problem was degenerate, and those coefficients are unstable to
    floating-point noise in exactly the near-duplicate directions the desk has the most of. MGS
    with an explicit floor makes the same decision VISIBLE and auditable -- a column whose residual
    direction has collapsed is DROPPED, by a stated rule, and the residual is still exactly correct
    for the span that survives.
    """
    out = np.full(a.shape, np.nan, dtype="float64")
    n = int(a.size)
    if n == 0 or b.shape[1] == 0:
        return a.astype("float64", copy=True)

    # Complete cases only. A projection coefficient estimated from a partly-missing overlap is not
    # a small error; it is a different number. See the NaN policy in `vector_neut`.
    complete = np.isfinite(a) & np.all(np.isfinite(b), axis=1)
    n_ok = int(complete.sum())
    if n_ok < 2:
        return out

    av = a[complete]
    bv = b[complete]
    basis: list[np.ndarray] = []
    for j in range(bv.shape[1]):
        col = bv[:, j].astype("float64", copy=True)
        orig = float(col @ col)
        if orig <= _DOT_FLOOR:
            continue                                    # a dead column has no direction at all
        for q in basis:
            col = col - float(q @ col) * q
        nrm2 = float(col @ col)
        if nrm2 <= _DOT_FLOOR or nrm2 <= (_RANK_REL_FLOOR ** 2) * orig:
            continue                                    # duplicate of a direction already removed
        basis.append(col / np.sqrt(nrm2))

    # DEGREES OF FREEDOM, and this guard blocks a manufactured survivor rather than a crash.
    # Neutralising k observations against k independent vectors returns EXACTLY ZERO, and a
    # column of zeros has correlation NaN-or-nothing with the cohort -- i.e. the redundancy screen
    # would read a fabricated perfect-orthogonality result as a triumph. Requiring two spare
    # observations is the minimum at which the residual is a measurement rather than an identity.
    if n_ok < len(basis) + 2:
        return out

    resid = av.astype("float64", copy=True)
    for q in basis:
        resid = resid - float(q @ resid) * q
    out[complete] = resid
    return out


def vector_neut(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The component of `a` orthogonal to `b`:  a - (a.b / b.b) * b.

    THE MOST VALUABLE FUNCTION IN THIS FILE, because it is the only one that attacks the constraint
    this desk has actually measured. `cohort_independence.py` puts 101 professional alphas at 15.9%
    mean pairwise correlation = 6.0 independent bets, and shows that going 101 -> 420 candidates
    buys 0.3 of one extra bet. Adding candidates does not fix that; SUBTRACTING the part of each
    new candidate that the existing cohort already explains does. Neutralising every new candidate
    against the accepted cohort drives mean pairwise correlation toward and below the 0.159
    benchmark BY CONSTRUCTION instead of hoping for it, and what remains after the subtraction is
    the only part of the candidate that was ever new information. Same formula, run forward:
    101 alphas at rho = 0.05 are 16.8 independent bets rather than 6.0.

    A second, quieter use: the same call is how you test whether a "new mechanism" is a repackaging
    of an old one. Neutralise the candidate against the incumbent and re-run the gate. If the edge
    survives, it is genuinely new; if it evaporates, the desk just re-discovered something it owns.

    SHAPES AND THE CONTRACTION AXIS. The projection is contracted over THE LAST AXIS OF `a`, and
    `b` is either the same shape as `a` (one neutraliser) or that shape with one extra trailing
    axis of length k (several). The two forms this supports:

      * REDUNDANCY FORM -- `a` is (obs,), one candidate's return series; `b` is (obs,) or (obs, k),
        the incumbent cohort. Contraction is over time, and the result is the candidate's return
        series with the cohort's explanatory power removed.
      * CROSS-SECTIONAL FORM -- `a` is (obs x names), `b` is (obs x names) or (obs x names x k).
        Each ROW is neutralised independently against that row's own neutralisers, which is the
        BRAIN convention: today's alpha vector made orthogonal to today's market/sector/size vector.
        Doing this per-row rather than pooled matters, because a beta estimated over the whole
        sample is not the beta that applied on any given day.

    SEVERAL NEUTRALISERS: sequential MODIFIED GRAM-SCHMIDT over the columns of `b`, which equals
    least squares against all of `b` at once when `b` has full column rank, and differs from it
    only by being explicit about what it dropped when `b` does not. The reasoning is in
    `_neutralise_1d`, and it is a real choice: `lstsq`'s minimum-norm fallback hides exactly the
    degeneracy a 15.9%-correlated cohort guarantees.

    B.B IS FLOORED, NOT `> 0`-CHECKED. See `_DOT_FLOOR` for the two failure shapes: an exactly-zero
    neutraliser turns the whole output NaN via 0/0, and a dust-valued one passes `> 0` while its
    projection DIRECTION is pure rounding noise, so up to 100% of `a` gets subtracted along a
    meaningless axis and returned labelled "neutralised". A neutraliser below the floor is skipped
    -- `a` comes back with nothing removed for that direction, which is the honest answer, and it
    is the same class of guard that the 1.4e31 incident of 2026-08-01 was missing.

    ORTHOGONAL IS NOT THE SAME AS UNCORRELATED, and on this desk the difference is the whole
    deliverable. This function removes the projection onto `b` ITSELF; correlation is the
    projection onto `b` AFTER BOTH SERIES ARE DEMEANED. They coincide only when the means are zero.
    So `vector_neut(a, b)` leaves a residual whose dot product with `b` is exactly zero but whose
    measured Pearson correlation with `b` is merely small -- on a 400-observation draw it comes out
    at -5.2e-04 rather than 1e-16 with both series centred, and at -3.4e-02 once `a` carries an
    ordinary drift, which is sixty-six times worse and is the case every live signal is in. Adding
    an intercept column takes the same figure to 1.1e-17. Since `cohort_independence.measure` is a
    Pearson correlation, THE INTERCEPT IS NOT OPTIONAL for the redundancy use: pass
    `np.column_stack([np.ones(n), cohort])` (or demean everything first) and the measured
    correlation goes to machine zero instead of merely toward it. Measured, not assumed -- the
    tests pin both numbers.

    NaN POLICY: an observation that is missing in `a` OR in any column of `b` comes back NaN. This
    is deliberately strict and it is a blocking choice, not a convenience. Passing the raw `a[i]`
    through at those points would leave the un-neutralised -- that is, the still-cohort-correlated
    -- observations inside a series the caller has been told is orthogonal, which is precisely the
    thing the function exists to prevent. If gaps in `b` are costing too much data, the remedy is
    `ts_backfill` on `b` BEFORE neutralising, not a softer rule here.
    """
    aa = np.asarray(a, dtype="float64")
    bb = np.asarray(b, dtype="float64")
    if aa.ndim not in (1, 2):
        raise ValueError(f"`a` must be 1-D or 2-D (obs x names), got {aa.ndim}-D")
    if bb.ndim == aa.ndim and bb.shape == aa.shape:
        bb = bb[..., None]
    if bb.ndim != aa.ndim + 1 or bb.shape[:aa.ndim] != aa.shape:
        raise ValueError(
            f"`b` must be {aa.shape} or {(*aa.shape, 'k')} to neutralise `a` of shape {aa.shape}, "
            f"got {bb.shape}")
    if aa.ndim == 1:
        return _neutralise_1d(aa, bb)
    out = np.empty(aa.shape, dtype="float64")
    for t in range(aa.shape[0]):
        out[t] = _neutralise_1d(aa[t], bb[t])
    return out


def ts_backfill(x: np.ndarray, d: int) -> np.ndarray:
    """Forward-fill each series with its last OBSERVED value, for at most `d` periods. Trailing.

    Time-series: acts DOWN a column. `x` is (obs,) or (obs x names); the output has the same shape.

    WHY FILLING IS NOT COSMETIC. The obvious reading is that a gap loses one observation. The
    expensive reading, and the one the webinar is explicit about, is that a gap INFLATES TURNOVER:
    a NaN -> value transition reads to a position sizer as flat -> fully-on, and a value -> NaN
    transition as a full liquidation, so every hole in the data is charged a round trip at the
    desk's real cost tiers even though the view never changed. A universe with patchy coverage
    therefore presents as a strategy that trades too much -- which invites the wrong fix (slow the
    signal down) for the actual problem (the feed has holes).

    WHY THE CAP `d` IS THE WHOLE FUNCTION. An uncapped forward fill is not a fill, it is a fiction:
    it carries a delisted name's last price forward forever, and a frozen constant is the
    lowest-realised-volatility series in any universe, so every inverse-volatility weighting scheme
    downstream -- including `crypto_xsec.xsec_funding_returns` -- will hand it the LARGEST weight.
    A dead asset becoming the book's biggest position is the failure mode this cap exists to stop.
    `d` is therefore an assertion about how long a stale value stays economically meaningful, and
    it should be short relative to the signal's own horizon.

    NEVER FROM THE FUTURE. out[i] depends only on x[..i]. Age is counted from the last OBSERVED
    value, not the last filled one, so a gap longer than `d` leaves its tail NaN rather than being
    bridged in `d`-length hops -- otherwise a long outage would be silently reconstructed from one
    stale print. Prefix invariance is asserted in the tests.
    """
    if d < 0:
        raise ValueError(f"d must be >= 0 (a negative fill window would read the future), got {d}")
    panel, shape = _as_panel(x)
    if d == 0 or panel.size == 0:
        return panel.reshape(shape)
    last = np.full(panel.shape[1], np.nan, dtype="float64")
    age = np.zeros(panel.shape[1], dtype="int64")
    for i in range(panel.shape[0]):
        row = panel[i]
        seen = np.isfinite(row)
        last = np.where(seen, row, last)
        age = np.where(seen, 0, age + 1)
        fill = (~seen) & np.isfinite(last) & (age <= d)
        panel[i] = np.where(fill, last, row)
    return panel.reshape(shape)


def ts_information_ratio(x: np.ndarray, d: int) -> np.ndarray:
    """ts_mean(x, d) / ts_std(x, d) over the trailing `d` obs, inclusive of the current one.

    Time-series: acts DOWN a column. `x` is (obs,) or (obs x names); the output has the same shape.

    WHAT IT ASKS. Not "is this quantity large" but "has it been RELIABLY large" -- the mean divided
    by the dispersion around it, which is the same question a Sharpe ratio asks and the same
    question every gate in this repo asks before it lets anything through. As a signal transform it
    is a stability filter: a series that spent the window oscillating between +5 and -5 has the
    same mean as one that sat quietly at 0 and a far worse information ratio, and only the second
    of those is something a position can be sized on.

    WINDOW CONVENTION, stated because the off-by-one is the entire integrity of the thing. out[i]
    is computed from x[i-d+1 .. i] INCLUSIVE of bar i, which is the standard `ts_` convention and
    contains no lookahead -- it depends only on data available at i. It is however a DESCRIPTION of
    the window ending now, not a forecast of the next one, so a caller trading on out[i] must be
    able to observe x[i] before acting. If x[i] is a close and the trade is at that same close, lag
    it. The first d-1 rows are NaN because the window is not yet full.

    THE DIVISOR IS FLOORED, NOT `> 0`-CHECKED, and this is the case where that distinction is most
    dangerous. A constant series -- a pegged pair, a halted market, a dead altcoin, any frozen feed
    -- has a sample standard deviation of floating-point dust rather than exactly 0.0, so a `> 0`
    guard passes and mean/dust returns an information ratio of order 1e15. That signal is enormous,
    perfectly stable, fires on every bar, and is entirely fictional; the 1.4e31 premium this desk
    shipped on 2026-08-01 was the same arithmetic. Below `_STD_FLOOR` the answer is NaN: a series
    with no dispersion has no information ratio, and saying so is the only safe output.

    Missing data: the window needs at least max(2, d // 2) finite observations -- the same
    half-window rule `volatility_signals.realised_variance` uses -- and ddof=1, matching it, so a
    window is never scored off one or two prints.
    """
    if d < 2:
        raise ValueError(f"d must be >= 2 (ts_std of a single observation is undefined), got {d}")
    panel, shape = _as_panel(x)
    n_obs = panel.shape[0]
    out = np.full(panel.shape, np.nan, dtype="float64")
    min_obs = max(2, d // 2)
    for i in range(d - 1, n_obs):
        w = panel[i - d + 1:i + 1]
        fin = np.isfinite(w)
        cnt = fin.sum(axis=0)
        safe = np.where(fin, w, 0.0)
        mean = safe.sum(axis=0) / np.maximum(cnt, 1)
        dev2 = np.where(fin, (w - mean) ** 2, 0.0).sum(axis=0)
        sd = np.sqrt(dev2 / np.maximum(cnt - 1, 1))
        ok = (cnt >= min_obs) & (sd > _STD_FLOOR)
        out[i] = np.where(ok, mean / np.where(ok, sd, 1.0), np.nan)
    return out.reshape(shape)
