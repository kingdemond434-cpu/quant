"""ORDER-BOOK MICROSTRUCTURE STATE -- the alignment and de-contamination primitives for the
Stage-A screen of the desk's #1 ranked untested mechanism class.

WHY THIS MODULE EXISTS AND WHAT IT REFUSES TO DO. `scripts/screen_orderbook_state.py` asks whether
resting-depth STATE at a bar boundary predicts the NEXT bar's return. Every prior attempt on the
neighbouring class died the same death -- book state is CONCURRENT with price, so a raw correlation
is a restatement of the move that just happened wearing the vocabulary of a forecast. This module
holds the two things that decide whether that death is avoided:

  (1) THE ALIGNMENT. Fixed, wall-clock-anchored, half-open bars, and a target priced only from
      prints AT OR AFTER the bar's right edge, so the signal can never touch the window it is
      asked to predict. `Alignment` carries the rule as data and every artifact echoes it --
      charter section 26 clause 4: unstated alignment voids the screen.
  (2) THE RESIDUALISATION. `residualise` orthogonalises the state against the SAME-BAR return
      using a beta fitted on STRICTLY PRIOR bars only. A full-sample beta would be the same leak
      `moat_features._expanding_z` was written to kill -- the residual at bar k would depend on
      returns that had not happened yet -- and it would be invisible, because it looks like
      preprocessing rather than like a decision.

WHAT THE RESIDUAL IS AND WHY IT IS TRADEABLE. resid[k] = state[k] - (a_k + b_k * r[k]), where r[k]
is the return realised OVER bar k and (a_k, b_k) come from bars strictly before k. Every input is
in the information set at the bar's right edge, so the residual is computable at the moment the
decision is taken. That is the whole point: subtracting the concurrent return is only legitimate
because the concurrent return is already known when the bet is placed. Subtracting the NEXT bar's
return would not be, and nothing here can do it -- `residualise` never indexes forward.

NO I/O, NO TAPE PARSING OF ITS OWN. Depth rows are parsed by `libs.hypmax.moat_mine._depth_snaps`
-- the audited reader that sorts levels, drops crossed books and understands BOTH recorder schemas
(`k="d"` from run_recorder{,_spot}.py, `k="depth"` from run_recorder_bybit.py). A second reader
here would be a second place for the mixed-schema silent-zero bug that already scarred
`moat_audit.py`. Trade PRICES are passed in as arrays by the caller, which parses them with the
one existing price reader (`scripts.build_bars.trades_from`), so this module stays pure numeric and
testable without a tape.

Pure numpy. Zero promotion authority.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from libs.hypmax.moat_mine import _depth_snaps

__all__ = [
    "CONSTRUCTIONS",
    "FORMS",
    "MIN_RESID_OBS",
    "STATE_NAMES",
    "Alignment",
    "bar_close_states",
    "boundary_prices",
    "contiguous_mask",
    "period_returns",
    "residualise",
    "snapshot_states",
    "withdrawal_asymmetry",
]

#: Prior bars an expanding orthogonalisation needs before its beta means anything. A residual taken
#: against a beta fitted on ten points is a statement about ten points, and it would be handed to
#: the screen wearing the same name as a converged one.
MIN_RESID_OBS = 60

#: Per-snapshot primitives every construction is built from. Named here so the caller cannot
#: silently screen a state this module never computed.
STATE_NAMES = ("obi_touch", "obi_deep", "slope_asym", "spread_bps", "depth_bid", "depth_ask")

#: The two forms every construction is screened in. BOTH are reported, always: reporting only the
#: residualised form would hide the contamination measurement, and reporting only the raw form is
#: the mistake that killed coinbase-premium, turkey-premium and kimchi.
FORMS = ("raw", "residualised")

#: Levels summed for the "deep" primitives. The touch is public everywhere; the shape behind it is
#: what the recorded tape actually owns.
_DEEP_LEVELS = 20

#: Points needed per side before a depth-decay slope is fitted. Three levels through a straight
#: line is not a slope, it is an interpolation.
_MIN_SLOPE_POINTS = 4


@dataclass(frozen=True)
class Alignment:
    """THE TIMESTAMP RULE, AS DATA -- so it is echoed into every artifact rather than described.

    Bars are FIXED, WALL-CLOCK-ANCHORED and HALF-OPEN in UTC milliseconds:

        bar k  = [ k * bar_ms, (k + 1) * bar_ms )        right edge b_k = (k + 1) * bar_ms

    SIGNAL. state[k] is read from the LAST depth snapshot whose timestamp lies strictly inside
    bar k, i.e. t < b_k. Its decision time is b_k.

    TARGET. p[k] is the first trade print at or after (b_k + decision_lag_ms); the return realised
    OVER bar k is r[k] = p[k] / p[k-1] - 1. That is exactly `axis_screen`'s contract --
    "target_ret[t] = return realised over period t" -- and the harness performs the forward shift
    itself, pairing state[k] with r[k+1]. Handing it an already-shifted target makes it shift
    twice, which is the misalignment signature its own lookahead rail fires on (`screen_moat.py`
    lost fourteen of nineteen hypotheses to precisely that).

    SO THE PREDICTED WINDOW IS [b_k, b_{k+1}) AND THE BAR CONTAINING THE SNAPSHOT IS NOT IN IT.
    The snapshot at t sits in [b_k - bar_ms, b_k); the return it is asked to predict starts at the
    first print at or after b_k. No print inside the snapshot's own bar can enter the forward
    return, and no snapshot at or after b_k can enter the signal.

    DECLARED LOOK-AHEAD RISK, and it is the one this construction cannot design away.
    r[k] closes on the same print p[k] that opens r[k+1]. The residualised form therefore assumes
    the desk observes p[k] and transacts at p[k], which is a ZERO-LATENCY fill and an upper bound
    on anything achievable. `decision_lag_ms` exists to price that away: set it to the desk's
    measured round trip and the target is taken from the first print at or after b_k + lag, which
    can only ever WEAKEN the reading. It defaults to 0 so the primary screen reports the optimistic
    bound explicitly rather than burying a latency assumption in a comment; a cell that survives at
    0 and dies at a realistic lag was never an edge, and the artifact must be able to say so.
    """

    bar_ms: int
    decision_lag_ms: int = 0

    def __post_init__(self) -> None:
        if self.bar_ms <= 0:
            raise ValueError("bar_ms must be positive")
        if self.decision_lag_ms < 0:
            raise ValueError("decision_lag_ms must not be negative")

    @property
    def horizon_days(self) -> float:
        """Bar width in days -- what `axis_screen` needs to annualise and to deflate n_eff."""
        return float(self.bar_ms) / 86_400_000.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "bar_ms": int(self.bar_ms),
            "decision_lag_ms": int(self.decision_lag_ms),
            "horizon_days": self.horizon_days,
            "bar_boundary": "half-open [k*bar_ms, (k+1)*bar_ms) in UTC ms, wall-clock anchored",
            "signal_at": "last depth snapshot with t strictly < the bar right edge b_k",
            "target_priced_at": "first trade print with t >= b_k + decision_lag_ms",
            "same_period_return": "r[k] = p[k]/p[k-1] - 1, the return realised OVER bar k",
            "forward_pairing": "the harness pairs state[k] with r[k+1]; window [b_k, b_{k+1})",
            "excludes_current_bar": True,
            "lookahead_risk": (
                "r[k] closes on the same print that opens r[k+1], so decision_lag_ms=0 assumes a "
                "zero-latency fill and is an UPPER BOUND; re-run at the measured round trip "
                "before believing any survivor"
            ),
        }


def snapshot_states(rows: list[dict[str, Any]]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Per-snapshot book-STATE primitives from raw tape rows.

    Delegates parsing to `moat_mine._depth_snaps`, which sorts levels, drops crossed books and
    accepts both recorder schemas. Returns (snapshot ms ascending, {name: values}) over
    `STATE_NAMES`; an unmeasurable primitive is NaN, never zero -- a zero imbalance is a real and
    balanced book, which is the opposite of "this snapshot could not be read".
    """
    snaps = _depth_snaps(rows)
    n = len(snaps)
    ms = np.zeros(n, dtype="int64")
    out = {k: np.full(n, np.nan) for k in STATE_NAMES}
    for i, (t_ms, bp, bs, ap, asz) in enumerate(snaps):
        ms[i] = t_ms
        b0, a0 = float(bs[0]), float(asz[0])
        if b0 + a0 > 0:
            out["obi_touch"][i] = (b0 - a0) / (b0 + a0)
        bd = float(bs[:_DEEP_LEVELS].sum())
        ad = float(asz[:_DEEP_LEVELS].sum())
        out["depth_bid"][i] = bd
        out["depth_ask"][i] = ad
        if bd + ad > 0:
            out["obi_deep"][i] = (bd - ad) / (bd + ad)
        mid = (float(bp[0]) + float(ap[0])) / 2.0
        if mid > 0:
            out["spread_bps"][i] = (float(ap[0]) - float(bp[0])) / mid * 1e4
            sb = _side_slope(bp[:_DEEP_LEVELS], bs[:_DEEP_LEVELS], mid)
            sa = _side_slope(ap[:_DEEP_LEVELS], asz[:_DEEP_LEVELS], mid)
            out["slope_asym"][i] = sb - sa
    return ms, out


def _side_slope(px: np.ndarray, size: np.ndarray, mid: float) -> float:
    """log(size) regressed on distance-from-mid in bps, one side only. NaN when unfittable.

    ONE SIDE, NOT BOTH TOGETHER. `moat_mine.book_slope` fits the pooled book and answers "is depth
    concentrated at the touch"; the ASYMMETRY of the two sides is a different question -- which
    side is thin BEHIND the quote -- and pooling averages exactly the difference being asked about.
    """
    d = np.abs(np.asarray(px, dtype="float64") - mid) / mid * 1e4
    s = np.asarray(size, dtype="float64")
    ok = (d > 0) & (s > 0) & np.isfinite(d) & np.isfinite(s)
    if int(ok.sum()) < _MIN_SLOPE_POINTS:
        return float("nan")
    x = d[ok]
    y = np.log(s[ok])
    xv = float(((x - x.mean()) ** 2).sum())
    if xv <= 0:
        return float("nan")
    return float(((x - x.mean()) * (y - y.mean())).sum() / xv)


def bar_close_states(
    snap_ms: np.ndarray, states: dict[str, np.ndarray], *, alignment: Alignment
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Collapse per-snapshot states to ONE observation per bar, taken at the bar's right edge.

    Returns (right edges b_k in UTC ms, {name: state at the last snapshot inside bar k}).

    THE LAST SNAPSHOT, NOT THE MEAN OF THE BAR. An average over the bar is a summary of a window
    that ENDS at b_k, so it is still causal -- but it is not the state a decision taken at b_k
    would see, and the mechanism under test is about the book's condition at the moment of the
    bet. `moat_microstructure.resample` averages deliberately for a different question (it wants
    the quantity with signal in it, not the quantity a trader observes); this screen needs the
    observable one, because a survivor here has to be actionable at b_k.

    Bars with no snapshot simply do not appear -- the edges array is not guaranteed contiguous, and
    `contiguous_mask` is what turns that into a dropped period rather than a mispriced one.
    """
    ms = np.asarray(snap_ms, dtype="int64")
    if ms.size == 0:
        return np.zeros(0, dtype="int64"), {k: np.zeros(0) for k in states}
    idx = ms // int(alignment.bar_ms)
    last = np.ones(idx.size, dtype=bool)
    last[:-1] = idx[:-1] != idx[1:]
    edges = (idx[last] + 1) * int(alignment.bar_ms)
    return edges.astype("int64"), {k: np.asarray(v, dtype="float64")[last] for k, v in
                                   states.items()}


def contiguous_mask(edges_ms: np.ndarray, *, alignment: Alignment) -> np.ndarray:
    """True where the period ENDING at this bar really spanned one bar width.

    A recorder outage -- or two non-adjacent days screened together -- puts a gap in the edge
    series. Without this, one "60-second period" can be twelve hours and carry twelve hours of
    return into a sample whose every other observation carries a minute; that single point
    dominates an IC computed over hundreds, in whichever direction the overnight move happened to
    go. The first bar has no preceding period and is always False, matching `period_returns`, which
    leaves it NaN for the same reason.
    """
    e = np.asarray(edges_ms, dtype="int64")
    m = np.zeros(e.size, dtype=bool)
    if e.size < 2:
        return m
    m[1:] = np.diff(e) == int(alignment.bar_ms)
    return m


def boundary_prices(
    trade_ms: np.ndarray, trade_px: np.ndarray, edges_ms: np.ndarray, *, alignment: Alignment
) -> np.ndarray:
    """The first print AT OR AFTER each bar's right edge (plus any declared decision lag).

    NaN where no print exists after the edge: no trade means no obtainable price, and a carried
    forward last price would report a fill the desk could not have had.

    `side="left"` is the load-bearing argument. It selects the first print with t >= target; the
    bar is half-open, so a print landing exactly on b_k belongs to the NEXT bar and is a price
    obtainable strictly after the state was observed. Using the last print at or BEFORE the edge --
    which an earlier version of the moat screen did -- lands 14 seconds BEFORE the signal on this
    tape and prices the very move the feature was measured during.
    """
    t = np.asarray(trade_ms, dtype="int64")
    p = np.asarray(trade_px, dtype="float64")
    e = np.asarray(edges_ms, dtype="int64")
    if t.size == 0 or e.size == 0:
        return np.full(e.size, np.nan)
    i = np.searchsorted(t, e + int(alignment.decision_lag_ms), side="left")
    have = i < t.size
    return np.where(have, p[np.clip(i, 0, p.size - 1)], np.nan)


def period_returns(prices: np.ndarray) -> np.ndarray:
    """r[k] = p[k]/p[k-1] - 1, the return realised OVER bar k. NaN at k=0 and on missing prints.

    CONTEMPORANEOUS BY CONSTRUCTION, and it must stay that way: `axis_screen` does its own forward
    shift, so a target that is already forward gets shifted twice and the harness reads the result
    as misalignment rather than as edge.
    """
    p = np.asarray(prices, dtype="float64")
    out = np.full(p.size, np.nan)
    if p.size < 2:
        return out
    prev = np.where(p[:-1] > 0, p[:-1], np.nan)
    out[1:] = p[1:] / prev - 1.0
    return out


def residualise(
    signal: np.ndarray, same_period_ret: np.ndarray, *, min_obs: int = MIN_RESID_OBS
) -> np.ndarray:
    """Orthogonalise a state series against the SAME-BAR return, with a STRICTLY PRIOR beta.

    THE ENTIRE CONTAMINATION DEFENCE OF THIS SCREEN. Book state is concurrent with price -- the
    side that just got hit is the thin one -- so a raw forward IC is very largely a restatement of
    the bar that just finished. This subtracts that restatement BEFORE the series is asked to
    predict anything, which is the escalation the desk's own graveyard prescribes for exactly this
    failure mode ("orthogonalize FIRST or screen at the mechanism's native horizon",
    docs/graveyard.md, cm_mvrv_btc_daily_level).

    resid[k] = signal[k] - (a_k + b_k * ret[k]), with (a_k, b_k) the ordinary least squares fit
    over bars j < k on which both series are finite. STRICTLY PRIOR: bar k never contributes to
    its own beta. A full-sample beta -- one line of numpy, and what `axis_screen` necessarily uses
    for its own internal diagnostic because it is handed only the finished arrays -- makes resid[k]
    a function of returns that had not happened yet. That is the same leak class as full-sample
    normalisation, and the reason it survives review is that it looks like preprocessing.

    NaN until `min_obs` prior finite pairs exist, wherever either input is NaN, and wherever the
    prior returns had zero dispersion (no beta is identified against a constant).

    THIS FUNCTION CANNOT LOOK FORWARD. Every cumulative sum below is shifted by one before use, so
    index k reads strictly from indices < k. That is the property the tests pin by perturbing a
    future observation and asserting the earlier residuals are bit-identical.
    """
    s = np.asarray(signal, dtype="float64")
    r = np.asarray(same_period_ret, dtype="float64")
    if s.size != r.size:
        raise ValueError(f"signal/return length mismatch: {s.size} vs {r.size}")
    out = np.full(s.size, np.nan)
    if s.size == 0:
        return out
    ok = np.isfinite(s) & np.isfinite(r)
    sv = np.where(ok, s, 0.0)
    rv = np.where(ok, r, 0.0)

    def _prior(a: np.ndarray) -> np.ndarray:
        return np.concatenate(([0.0], a[:-1]))

    n = _prior(np.cumsum(ok.astype("float64")))
    s_s = _prior(np.cumsum(sv))
    s_r = _prior(np.cumsum(rv))
    s_rr = _prior(np.cumsum(rv * rv))
    s_sr = _prior(np.cumsum(sv * rv))

    den = n * s_rr - s_r * s_r
    with np.errstate(invalid="ignore", divide="ignore"):
        beta = np.where(den > 0.0, (n * s_sr - s_s * s_r) / np.where(den > 0.0, den, 1.0), np.nan)
        alpha = np.where(n > 0.0, (s_s - beta * s_r) / np.where(n > 0.0, n, 1.0), np.nan)
        resid = s - alpha - beta * r
    usable = ok & (n >= float(min_obs)) & np.isfinite(resid)
    out[usable] = resid[usable]
    return out


def withdrawal_asymmetry(depth_bid: np.ndarray, depth_ask: np.ndarray) -> np.ndarray:
    """Fractional drop in bid-side resting depth MINUS the same on the ask side, bar to bar.

    Positive = the bid side pulled harder than the offer. This is the one construction in the set
    that is a DYNAMIC rather than a level, and it is here because the class's own economic
    definition names withdrawal explicitly: a resting order that does not withdraw in time is
    picked off, so the side that withdraws first is the side that believes it is about to be.

    NaN at index 0 (no previous bar) and wherever the previous depth was zero. Drops are NOT netted
    against additions on the same side; netting would average the exact event of interest into
    invisibility, which is `moat_mine.withdrawal_rate`'s own argument.
    """
    b = np.asarray(depth_bid, dtype="float64")
    a = np.asarray(depth_ask, dtype="float64")
    if b.size != a.size:
        raise ValueError(f"depth length mismatch: {b.size} vs {a.size}")
    out = np.full(b.size, np.nan)
    if b.size < 2:
        return out
    with np.errstate(invalid="ignore", divide="ignore"):
        db = (b[:-1] - b[1:]) / np.where(b[:-1] > 0, b[:-1], np.nan)
        da = (a[:-1] - a[1:]) / np.where(a[:-1] > 0, a[:-1], np.nan)
    out[1:] = db - da
    return out


#: THE PRE-REGISTERED CONSTRUCTION SET. Five, fixed, named before any result -- the family the
#: multiplicity charge is computed over. Adding a sixth after seeing the first five is the
#: garden-of-forking-paths the charter's clause 3 forbids, and it would silently deflate the
#: correction every other cell was judged against.
CONSTRUCTIONS: dict[str, Callable[[dict[str, np.ndarray]], np.ndarray]] = {
    # STATE -- where resting size is, at the moment of the decision.
    "obi_touch": lambda s: s["obi_touch"],
    "obi_deep": lambda s: s["obi_deep"],
    # SHAPE -- which side is thin BEHIND the quote, which no public feed publishes.
    "book_slope_asymmetry": lambda s: s["slope_asym"],
    # COST STATE -- what the book is charging to be crossed.
    "spread_state": lambda s: s["spread_bps"],
    # DYNAMIC -- which side is getting out of the way.
    "withdrawal_asymmetry": lambda s: withdrawal_asymmetry(s["depth_bid"], s["depth_ask"]),
}
