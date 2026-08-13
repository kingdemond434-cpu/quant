"""Execution cost from OTHER TRADERS' PRINTS -- the third basis the desk never had.

WHY THIS EXISTS. `data/cost_model.json` is the most-consumed derivative on this desk: it decides
which names the book may hold (`run_cashcarry_executor._rt_bps` -> `_net_bps` -> `_entry_gate`).
It is produced by walking DISPLAYED DEPTH. L1.45 already states in plain words why that cannot be
the whole answer: "a book-walk measures DISPLAYED depth in a book that existed WITHOUT OUR ORDER
IN IT." The desk wrote that law, built excitation as the remedy, and then bounded the remedy to
its own 531 fills -- because L1.11(b) says "an Execution Reality Model from OUR OWN fills."

That scope word was written to stop the desk trusting a vendor's generic coefficient, which is
correct. It was read as "only our own fills count", which is not the same claim, and it left the
largest execution dataset on the box unread: every print on the tape is a completed execution
experiment, at a known size, with a published aggressor side, against the same book we snapshot,
paid for by somebody else. `libs/execution/passive_impact.py` encodes exactly two bases,
"counterfactual" (book walk) and "own_fills". This module is the missing third: "third_party".

A third-party print is not a vendor model. It is realised execution data we did not pay for.

WHAT THE TAPE ACTUALLY HOLDS (measured 2026-08-12, not assumed -- the proposal that motivated
this module claimed ~48,000 prints/symbol/hour and the real number is 150-2,547, so the power
path below is load-bearing rather than decorative):

    AAVEUSDT   24,688 prints / 6h   median $72    6,392 (25.9%) inside the desk's $65-450 range
    ADAUSDT    17,990 prints / 6h   median $49    4,127 (22.9%) inside it
    1000CATUSDT 1,339 prints / 6h   median $13      203 (15.2%) inside it, 33 above $450

The desk's smallness is the advantage here and it is worth naming: the median print on these
books is $13-$72, so the desk's own $65-450 operating point sits in the DENSEST part of the size
distribution. Nobody sells a cost model there because nobody trades there (S42).

THE UNIT OF OBSERVATION IS THE INTERVAL, NOT THE PRINT, AND THAT IS FORCED BY THE DATA.
Depth is polled every ~5-8.8s; prints arrive continuously. Dozens of prints fall between two
consecutive snapshots, so no single print's displacement is separately observable -- attributing
one snapshot-to-snapshot mid move to one print would be a fabrication. The honest unit is the
INTER-SNAPSHOT INTERVAL: net signed notional of every print inside it, against the mid change
across it. That is Kyle's lambda properly specified, it uses every print rather than a
subsample, and it turns the cadence limitation into a natural aggregation instead of a bias.

ORDERING IS BY FILE POSITION, AND THAT IS AN L1.46 REQUIREMENT RATHER THAN A CONVENIENCE.
On Binance, depth rows are stamped with OUR receipt (c="recv", venue stamps retained in E/T) and
trade rows carry ONLY the venue's (c="venue", no `r` field). The two `t` values are therefore
DIFFERENT CLOCKS, and sorting the merged stream by `t` interleaves them -- the mechanism behind
every timestamp-artifact kill in this desk's graveyard (kimchi_premium, ~73% artifact). Worse,
`clock_provenance.sort_key` cannot rescue it here: for a Binance trade row `recv_ms` returns None,
so the key falls through to the venue `t` while depth rows key on receipt. Mixed, silently.

The recorder is an append-only writer, so FILE ORDER IS RECEIPT ORDER for every row in both
eras -- including the 0%-marker corpus before 2026-08-06 where no venue stamp exists on depth at
all. It needs no timestamp arithmetic, so it cannot commit a cross-clock error. Venue stamps are
used ONLY to report interval duration for QA, never to assign a print to an interval.

CONFOUNDING IS REPORTED, NOT ASSUMED AWAY. Large prints arrive BECAUSE the book is already
moving, so a raw regression of mid change on signed flow over-states impact. The fit therefore
carries a second slope controlling for the previous interval's return, and BOTH are published. If
the controlled slope collapses toward zero the raw number was mostly momentum and the caller is
told so explicitly (`momentum_share`), rather than the estimator quietly reporting the flattering
one.

THE CEILING OF THAT CONTROL, STATED PLAINLY BECAUSE IT IS THE REASON THIS BASIS MAY NEVER SIZE
ANYTHING. The lagged regressor removes flow that CHASES a past move. It cannot touch SIMULTANEITY
INSIDE THE INTERVAL: when the mid moves and prints follow within the same ~6s window, cause and
effect are both inside one observation and no lagged control can separate them. A synthetic book
in which flow is a pure function of the CONTEMPORANEOUS return -- causing none of it -- still fits
a large, highly significant lambda here, and that is pinned by test rather than left as a
footnote. Observational data cannot resolve a counterfactual (L1.45): randomised, exogenous
variation in our OWN orders (`libs/execution/excitation.py`) remains the only instrument on this
desk that can identify the causal slope. This module measures an ASSOCIATION between flow and
price at the desk's operating size, which is a genuine and useful cost prior, and it is not a
causal impact coefficient.

OBSERVATION COUNT IS NOT SAMPLE SIZE (GAP REGISTER row #100). Interval observations at ~6s cadence
are autocorrelated, and two organs on this desk have already derived statistical authority from
sampling frequency. Every confidence interval here is deflated by the AR(1) factor
(1-rho)/(1+rho) taken over the MORE autocorrelated of the residual and flow series, and it is
`n_eff` -- never `n` -- that gates the MEASURED verdict.

ZERO PROMOTION AUTHORITY. This module estimates a cost; it never sizes, promotes or admits
anything. Its output is a basis LABELLED BY BASIS alongside the book walk, never silently merged
into it, and the executor's existing tighten-only rule (`max(modelled, realised)`) is untouched.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from typing import Any, NamedTuple

import numpy as np

from libs.research import clock_provenance as cp

#: Verdicts. An unmeasured book must never read as a cheap one (L1.28a).
MEASURED = "MEASURED"
UNDERPOWERED = "UNDERPOWERED"       # too few independent intervals to separate lambda from noise
UNIDENTIFIED = "UNIDENTIFIED"       # flow carries no usable variance -- the slope is unidentified
NO_DATA = "NO-DATA"                 # no usable depth/print pairing at all

#: An interval needs at least this many INDEPENDENT observations before lambda is believable.
#: Deliberately on n_eff, not n: 20k autocorrelated 6s intervals are not 20k experiments.
MIN_N_EFF = 100.0
#: Below this t-stat the slope is not distinguishable from zero, and "indistinguishable from zero"
#: is a real answer that must not be dressed up as a small cost.
MIN_T = 2.0
#: Flow must actually vary. A book where every interval carries the same net notional cannot
#: identify a slope at any sample size -- that is UNIDENTIFIED, not UNDERPOWERED, and the two
#: demand opposite responses (collect more vs stop asking this question of this book).
MIN_FLOW_SD_USD = 1.0

_BINANCE_DEPTH = "d"
_BINANCE_TRADE = "t"
_BYBIT_DEPTH = "depth"
_BYBIT_TRADE = "trades"


class Interval(NamedTuple):
    """One inter-snapshot interval: what the book did, and what flow crossed it."""

    ret_bps: float
    """Mid return across the interval, in bps. Signed."""
    signed_notional: float
    """Net aggressor-signed USD notional of every print inside the interval. Buy positive."""
    gross_notional: float
    """Unsigned USD notional -- how much actually traded, regardless of direction."""
    n_prints: int
    half_spread_bps: float
    """Half the quoted spread at the interval's opening snapshot. The taker's floor cost."""
    dt_ms: int
    """Venue-clock duration when both stamps exist, else 0. QA only -- never used to assign."""


class ImpactFit(NamedTuple):
    """A fitted impact curve for one (venue, symbol), with its own refusal built in."""

    status: str
    symbol: str
    venue: str
    n: int
    """Raw interval count. Reported for transparency and NEVER used to gate -- see row #100."""
    n_eff: float
    """Autocorrelation-deflated independent observation count. This is what gates."""
    lam_bps_per_1k: float | None
    """Raw Kyle lambda: bps of mid displacement per $1,000 of net signed flow."""
    lam_controlled_bps_per_1k: float | None
    """Same slope, controlling for the previous interval's return (the momentum confound)."""
    t_stat: float | None
    """t of the CONTROLLED slope, on n_eff degrees of freedom."""
    momentum_share: float | None
    """1 - controlled/raw. Near 1 means the raw slope was mostly the book already moving."""
    r2: float | None
    half_spread_bps: float | None
    """Median half-spread -- the floor a taker pays before any impact at all."""
    median_print_usd: float | None
    prints_in_desk_range: int
    """Prints inside $65-450. The desk's operating point, and the identification set for it."""
    flow_p50_usd: float | None
    """Median |net interval flow|. Sets the scale lambda was actually fitted at."""
    identified_to_usd: float | None
    """p99 of |net interval flow| -- the largest order this fit may speak about. See cost_bps."""
    detail: str

    def cost_bps(self, notional_usd: float) -> float | None:
        """Expected TAKER cost in bps for an order of this size, or None when unmeasured.

        Convention, stated because run_cost_model.py states its own and the two must be
        comparable: a taker crossing the spread pays the half-spread immediately, then walks into
        the book, accruing on average HALF the total displacement its own size causes. So

            cost_bps(N) = half_spread_bps + 0.5 * lambda * N

        The full mid displacement lambda*N is what the NEXT trader sees; half of it is what we
        pay. Returns None rather than 0.0 when the fit did not measure -- a book with no measured
        cost is not a free book, and the caller must be able to tell the difference.

        REFUSES ABOVE THE IDENTIFIED RANGE, which is the L1.45 discipline applied to this
        estimator's own output: "at an operating point the desk never visits, say UNIDENTIFIED and
        go buy the observation." lambda is fitted on the net flow that actually crossed these
        books; asking it about an order larger than any flow ever observed is asking it to invent
        a counterfactual, which is the exact error the book walk already makes. Measured
        2026-08-12: a $450 order is inside 96% of AAVEUSDT intervals (median flow $6,517) but
        reaches the 88th percentile on 1000CATUSDT (median flow $42), so the guard binds on
        precisely the thin books where being wrong is most expensive.

        The linear form is also its own caveat: real impact is concave in size, so a lambda fitted
        mostly on small flow OVERSTATES a much larger order. That direction is the safe one for a
        cost estimate, and it is one more reason this output may only ever tighten a gate.
        """
        if self.status != MEASURED:
            return None
        if self.lam_controlled_bps_per_1k is None or self.half_spread_bps is None:
            return None
        if self.identified_to_usd is not None and notional_usd > self.identified_to_usd:
            return None
        return self.half_spread_bps + 0.5 * self.lam_controlled_bps_per_1k * (notional_usd / 1000.0)


def _f(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _mid_and_half_spread(rec: dict[str, Any]) -> tuple[float, float] | None:
    """Touch mid and half-spread in bps from a depth row of either recorder schema.

    None on a crossed or empty book: bid >= ask is a stitching artifact of two snapshot halves,
    not an arbitrage, and letting one such row through would dominate every downstream mean.
    """
    bids, asks = rec.get("b"), rec.get("a")
    if not bids or not asks:
        return None
    try:
        bp, ap = _f(bids[0][0]), _f(asks[0][0])
    except (IndexError, TypeError, KeyError):
        return None
    if bp is None or ap is None or bp <= 0 or ap <= 0 or bp >= ap:
        return None
    mid = 0.5 * (bp + ap)
    return mid, (ap - bp) / mid * 1e4 / 2.0


def _prints(rec: dict[str, Any], venue: str) -> Iterator[tuple[float, float]]:
    """Every (signed_notional_usd, gross_notional_usd) in one trade row.

    Binance carries one print per row; Bybit batches them under "v". The aggressor sign is the
    load-bearing field and it is easy to invert: Binance `m` is TRUE when the BUYER was the maker,
    which means the aggressor SOLD. Bybit publishes the aggressor directly as `side`. Inverting
    either one flips every number this module produces while the code still runs, so both are
    pinned by test rather than trusted.
    """
    kind = rec.get("k")
    if kind == _BINANCE_TRADE:
        px, qty = _f(rec.get("p")), _f(rec.get("q"))
        if px is None or qty is None or px <= 0 or qty <= 0:
            return
        notl = px * qty
        yield (-notl if bool(rec.get("m")) else notl), notl
    elif kind == _BYBIT_TRADE:
        batch = rec.get("v")
        if not isinstance(batch, list):
            return
        for tr in batch:
            if not isinstance(tr, dict):
                continue
            px, qty = _f(tr.get("price")), _f(tr.get("size"))
            if px is None or qty is None or px <= 0 or qty <= 0:
                continue
            notl = px * qty
            # Bybit names the AGGRESSOR in `side`, the opposite convention to Binance's `m`.
            yield (notl if str(tr.get("side", "")).lower() == "buy" else -notl), notl


def intervals(records: Iterable[dict[str, Any]], venue: str) -> list[Interval]:
    """Walk one symbol's records IN FILE ORDER into inter-snapshot intervals.

    File order is receipt order (append-only writer), which is the only axis valid across both
    corpus eras and the only one that cannot commit the cross-clock error L1.46 exists to stop.
    Prints seen before the first depth row are dropped: they have no opening book to price
    against, and inventing one would be a fabricated observation.
    """
    out: list[Interval] = []
    open_mid: float | None = None
    open_half: float = 0.0
    open_venue_ms: int | None = None
    signed = gross = 0.0
    n_prints = 0

    for rec in records:
        kind = rec.get("k")
        if kind in (_BINANCE_DEPTH, _BYBIT_DEPTH):
            state = _mid_and_half_spread(rec)
            if state is None:
                continue
            mid, half = state
            v_ms = cp.venue_ms(rec, venue)
            if open_mid is not None:
                dt = (v_ms - open_venue_ms) if (v_ms is not None and open_venue_ms is not None
                                                and v_ms >= open_venue_ms) else 0
                out.append(Interval(
                    ret_bps=(mid / open_mid - 1.0) * 1e4,
                    signed_notional=signed,
                    gross_notional=gross,
                    n_prints=n_prints,
                    half_spread_bps=open_half,
                    dt_ms=dt,
                ))
            open_mid, open_half, open_venue_ms = mid, half, v_ms
            signed = gross = 0.0
            n_prints = 0
        elif kind in (_BINANCE_TRADE, _BYBIT_TRADE):
            if open_mid is None:
                continue                      # no opening book -- cannot price this print
            batch = list(_prints(rec, venue))
            signed += sum(s for s, _ in batch)
            gross += sum(g for _, g in batch)
            n_prints += len(batch)
    return out


def _ar1(x: np.ndarray) -> float:
    """Lag-1 autocorrelation, clipped to [0, 0.999]. Negative autocorrelation is treated as zero.

    Clipping the negative side is the conservative choice: negative serial correlation would
    INFLATE n_eff above n, and claiming more independent observations than intervals observed is
    exactly the row-#100 defect pointed the other way.
    """
    if x.size < 3:
        return 0.0
    sd = float(np.std(x))
    if sd <= 0.0 or not math.isfinite(sd):
        return 0.0
    c = x - float(np.mean(x))
    denom = float(np.dot(c, c))
    if denom <= 0.0:
        return 0.0
    rho = float(np.dot(c[:-1], c[1:]) / denom)
    if not math.isfinite(rho):
        return 0.0
    return min(max(rho, 0.0), 0.999)


def effective_n(residual: np.ndarray, flow: np.ndarray) -> float:
    """Independent-observation count after AR(1) deflation (GAP REGISTER row #100).

    n_eff = n * (1-rho)/(1+rho), taking rho from the MORE autocorrelated of the two series. The
    standard Bartlett result is stated for the mean of a series; applying it to a regression slope
    is an approximation, and it is used here because it errs toward FEWER independent observations
    than the naive count -- the direction that costs the desk a verdict rather than manufactures
    one.
    """
    n = int(residual.size)
    if n <= 2:
        return float(max(n, 0))
    rho = max(_ar1(residual), _ar1(flow))
    return float(n) * (1.0 - rho) / (1.0 + rho)


def fit(obs: list[Interval], *, symbol: str = "", venue: str = "",
        desk_lo: float = 65.0, desk_hi: float = 450.0) -> ImpactFit:
    """Fit lambda over these intervals, refusing rather than guessing when the data cannot carry it.

    Two regressions are run and both are reported:
        raw         ret ~ a + lambda * flow
        controlled  ret ~ a + lambda * flow + beta * ret_prev
    The controlled slope is the one that gates and the one `cost_bps` uses, because the raw slope
    absorbs the book's own momentum -- large prints arrive when the book is already moving.
    """
    def _refuse(status: str, detail: str, n: int = 0, n_eff: float = 0.0,
                **kw: Any) -> ImpactFit:
        base: dict[str, Any] = {
            "status": status, "symbol": symbol, "venue": venue, "n": n, "n_eff": n_eff,
            "lam_bps_per_1k": None, "lam_controlled_bps_per_1k": None, "t_stat": None,
            "momentum_share": None, "r2": None, "half_spread_bps": None,
            "median_print_usd": None, "prints_in_desk_range": 0, "flow_p50_usd": None,
            "identified_to_usd": None, "detail": detail,
        }
        base.update(kw)
        return ImpactFit(**base)

    if len(obs) < 3:
        return _refuse(NO_DATA, f"{len(obs)} intervals -- no usable depth/print pairing", len(obs))

    ret = np.array([o.ret_bps for o in obs], dtype=float)
    flow = np.array([o.signed_notional for o in obs], dtype=float)
    finite = np.isfinite(ret) & np.isfinite(flow)
    ret, flow = ret[finite], flow[finite]
    kept = [o for o, ok in zip(obs, finite, strict=True) if ok]
    if ret.size < 3:
        return _refuse(NO_DATA, "no finite intervals", int(ret.size))

    half = float(np.median([o.half_spread_bps for o in kept]))
    gross = [o.gross_notional / o.n_prints for o in kept if o.n_prints > 0]
    med_print = float(np.median(gross)) if gross else None
    in_range = sum(1 for g in gross if desk_lo <= g <= desk_hi)
    # The range lambda may speak about. Taken over NON-ZERO |net flow|: intervals with no prints
    # carry no size information, and leaving them in would drag the percentile down and make the
    # fit look narrower than the flow it was actually estimated from.
    abs_flow = np.abs(flow)
    nz = abs_flow[abs_flow > 0]
    flow_p50 = float(np.median(nz)) if nz.size else None
    identified_to = float(np.percentile(nz, 99)) if nz.size >= 10 else None
    ctx: dict[str, Any] = {"half_spread_bps": round(half, 4),
                           "median_print_usd": round(med_print, 2) if med_print else None,
                           "prints_in_desk_range": in_range,
                           "flow_p50_usd": round(flow_p50, 2) if flow_p50 else None,
                           "identified_to_usd": round(identified_to, 2) if identified_to else None}

    flow_sd = float(np.std(flow))
    if flow_sd < MIN_FLOW_SD_USD:
        return _refuse(UNIDENTIFIED,
                       f"net flow sd ${flow_sd:.2f} < ${MIN_FLOW_SD_USD:.2f} -- slope "
                       "unidentified at any sample size", int(ret.size), **ctx)

    # ---- raw slope -------------------------------------------------------------------------
    x_raw = np.column_stack([np.ones(ret.size), flow])
    beta_raw, *_ = np.linalg.lstsq(x_raw, ret, rcond=None)
    lam_raw = float(beta_raw[1])

    # ---- controlled slope: previous interval's return as the momentum confound ---------------
    ret_prev = np.concatenate([[0.0], ret[:-1]])
    x_ctl = np.column_stack([np.ones(ret.size), flow, ret_prev])
    beta_ctl, *_ = np.linalg.lstsq(x_ctl, ret, rcond=None)
    lam_ctl = float(beta_ctl[1])
    resid = ret - x_ctl @ beta_ctl

    n_eff = effective_n(resid, flow)
    dof = n_eff - x_ctl.shape[1]
    if dof <= 1.0:
        return _refuse(UNDERPOWERED,
                       f"n_eff {n_eff:.1f} over {ret.size} intervals leaves no degrees of "
                       "freedom", int(ret.size), n_eff, **ctx)

    # SE of the flow slope, with the n_eff deflation applied to the residual variance. Using
    # n_eff here rather than n is the whole point of row #100: the naive SE on 6s intervals is
    # optimistic by the square root of the autocorrelation factor.
    ss_res = float(np.dot(resid, resid))
    sigma2 = ss_res / dof * (ret.size / n_eff)
    try:
        xtx_inv = np.linalg.inv(x_ctl.T @ x_ctl)
    except np.linalg.LinAlgError:
        return _refuse(UNIDENTIFIED, "design matrix singular -- flow collinear with the "
                       "intercept", int(ret.size), n_eff, **ctx)
    var_lam = sigma2 * float(xtx_inv[1, 1])
    if not math.isfinite(var_lam) or var_lam <= 0:
        return _refuse(UNIDENTIFIED, "non-finite slope variance", int(ret.size), n_eff, **ctx)
    t_stat = lam_ctl / math.sqrt(var_lam)

    ss_tot = float(np.dot(ret - ret.mean(), ret - ret.mean()))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else None
    momentum_share = (1.0 - lam_ctl / lam_raw) if lam_raw != 0.0 else None

    # per $1,000 of flow, for a number a human can read
    scale = 1000.0
    common: dict[str, Any] = dict(
        symbol=symbol, venue=venue, n=int(ret.size), n_eff=round(n_eff, 1),
        lam_bps_per_1k=round(lam_raw * scale, 6),
        lam_controlled_bps_per_1k=round(lam_ctl * scale, 6),
        t_stat=round(t_stat, 3),
        momentum_share=round(momentum_share, 4) if momentum_share is not None else None,
        r2=round(r2, 5) if r2 is not None else None, **ctx)

    if n_eff < MIN_N_EFF:
        return ImpactFit(status=UNDERPOWERED,
                         detail=f"n_eff {n_eff:.1f} < {MIN_N_EFF:.0f} required "
                                f"(raw n {ret.size})", **common)
    if abs(t_stat) < MIN_T:
        return ImpactFit(status=UNDERPOWERED,
                         detail=f"|t| {abs(t_stat):.2f} < {MIN_T} -- slope not distinguishable "
                                "from zero", **common)
    if lam_ctl <= 0.0:
        # A negative fitted slope means buys pushed the mid DOWN over the interval. That is not a
        # negative cost the desk may book; it is evidence the specification has not captured this
        # book, and it must refuse rather than hand the entry gate a discount.
        return ImpactFit(status=UNIDENTIFIED,
                         detail=f"controlled slope {lam_ctl * scale:.4f} bps/$1k is non-positive "
                                "-- specification does not describe this book", **common)
    return ImpactFit(status=MEASURED,
                     detail=f"lambda {lam_ctl * scale:.4f} bps/$1k, t={t_stat:.2f} on "
                            f"n_eff {n_eff:.0f}", **common)
