"""R0267: the reduced-form PASSIVE-FILL IMPACT MODEL, and the honest statement of where it can
and cannot be fitted.

THE MAKER PROBLEM THIS SERVES. The desk's largest measured execution wound is passive: a 24.2%
maker fill rate while paying 96.5% of fees, and the ~66bps carry execution gap (R0219) that the
2026-07-31 attribution proved is EXECUTION, not selection. `libs/execution/book_walk.py` already
answers the TAKER side (walk the book, sqrt-law impact). Nothing answered the passive side, and
`libs/execution/excitation.py` -- which randomises how long a quote may rest -- has no functional
form at all, so it can measure points but cannot interpolate between them.

THE MODEL. Two empirical observables, each estimated separately, then combined:

  (a) FILL PROBABILITY DECAYS EXPONENTIALLY IN QUOTE DISTANCE
          P_fill(d) = p0 * exp(-d / lam)
      d in bps from mid, lam the decay length in bps. Quote at the touch and you fill often;
      step away and the probability falls off at a rate lam that is a property of the book.

  (b) SHORT-TERM PRICE RESPONSE IS LINEAR IN SIGNED ORDER FLOW
          r = beta * OFI
      r the forward mid return in bps, OFI the signed traded volume over the same window.
      Linear, through the origin: zero net flow implies zero expected response.

  COMBINED -- the passive impact rate. A resting quote is filled BY someone, and that someone is
  the aggressor whose flow moves the price against the fill. Expected adverse selection per unit
  of passive quoting at distance d is therefore the response scaled by the probability the quote
  is reached:
          impact(d) = beta * ofi_scale * P_fill(d)
  which decays exponentially in d for exactly the reason (a) does. Quoting further out is cheaper
  in adverse selection AND rarer in fills, and this is the curve that prices the trade-off.

WHY (a) CANNOT BE FITTED ON OUR OWN FILLS, MEASURED NOT ASSUMED. The executor's
`_passive_price` returns the best bid for a BUY and the best ask for a SELL -- every quote
this desk has ever placed sits AT THE TOUCH. The offset is therefore always half the spread:
it has ZERO VARIANCE BY CONSTRUCTION, and the placed price is not written to the tape at all (no
field on any of the 531 rows carries it). A regressor with no variance identifies no slope, so
`lam` is UNIDENTIFIED on own fills no matter how many fills accumulate. This is the same
collinearity trap `excitation.py` was built to break for `maker_wait_s`, recurring one axis over
on the offset -- and it is why `identifiability()` below is a first-class part of this module
rather than a footnote. L1.45 is explicit about the remedy: at an operating point the desk never
visits, say UNIDENTIFIED and go buy the observation.

WHAT IS IDENTIFIABLE TODAY, AND IT IS A LOT. `data/moat` holds ~13M recorded L2 snapshots at
20 (Binance) to 25 (Bybit) levels per side, time-aligned to a trade tape that carries AGGRESSOR
DIRECTION on every print. So both observables are estimable COUNTERFACTUALLY: place a hypothetical
quote at each recorded level, compute the queue ahead of it, and count the volume that actually
traded through that level in the following window. That is a real measurement of the book we
quoted into -- it is simply not a measurement of our own order's effect on it, and the two are
labelled distinctly throughout (`basis="counterfactual"` vs `basis="own_fills"`).

THE ONE THING THE COUNTERFACTUAL CANNOT DO, stated so it is never quietly forgotten: it measures
the book AS IT EXISTED WITHOUT OUR ORDER IN IT. Queue position, and any reaction to our own
presence, are unobservable this way. The counterfactual is therefore an UPPER BOUND on fill
probability, inheriting that property from `book_walk.fill_probability`, and it is labelled as
one. Only excitation over a genuine offset arm can close that gap.

REFUSAL PATHS (L1.28a). Every estimator returns a status rather than a number it cannot support:
UNDERPOWERED (too few observations), UNIDENTIFIED (the regressor has no variance, or the fitted
decay has the wrong sign), NO-DATA (nothing to read). A fitted coefficient published from too few
points would step execution decisions on noise, which is strictly worse than leaving them pinned.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

__all__ = [
    "FillDecay",
    "Identifiability",
    "OfiResponse",
    "PassiveImpact",
    "fill_probability_curve",
    "fit_fill_decay",
    "fit_ofi_response",
    "identifiability",
    "passive_impact_curve",
    "signed_flow",
    "window_ofi",
]

#: Fewer than this and a decay length is noise. Matches book_walk.calibrate_impact's own floor of
#: 8 -- the same argument (a two-parameter fit on a handful of points is not a measurement) and
#: deliberately the same number, so the two impact estimators cannot disagree about what "enough"
#: means.
MIN_DECAY_POINTS = 8

#: An OFI response is a single-parameter regression on noisy per-window returns, so it needs more
#: points than the decay fit, not fewer. 30 is the conventional floor below which a slope's
#: standard error is not usefully bounded.
MIN_OFI_POINTS = 30

_UNDERPOWERED = "UNDERPOWERED"
_UNIDENTIFIED = "UNIDENTIFIED"
_NO_DATA = "NO-DATA"
_OK = "OK"


@dataclass(frozen=True)
class FillDecay:
    """P_fill(d) = p0 * exp(-d / lam_bps). `status` is OK only when both are real numbers."""

    lam_bps: float
    p0: float
    r2: float
    n: int
    status: str
    why: str = ""
    basis: str = "counterfactual"

    @property
    def ok(self) -> bool:
        return self.status == _OK

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OfiResponse:
    """r_bps = beta * OFI, fitted through the origin."""

    beta_bps: float
    r2: float
    n: int
    status: str
    why: str = ""
    basis: str = "counterfactual"

    @property
    def ok(self) -> bool:
        return self.status == _OK

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PassiveImpact:
    """The combined reduced form, evaluated on a grid of quote distances."""

    distance_bps: list[float]
    fill_prob: list[float]
    impact_bps: list[float]
    status: str
    why: str = ""
    decay: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Identifiability:
    """Can the decay be fitted from the desk's OWN fills? Measured, not assumed."""

    status: str
    why: str
    n_rows: int
    n_with_offset: int
    offset_variance: float | None = None

    @property
    def ok(self) -> bool:
        return self.status == _OK

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def fill_probability_curve(distance_bps: np.ndarray | list[float], *,
                           lam_bps: float, p0: float = 1.0) -> np.ndarray:
    """The model curve itself: p0 * exp(-d / lam).

    Raises on a non-positive decay length -- a zero or negative `lam` is not a flat curve, it is
    a fit that failed, and silently returning something plottable is how a failed fit reaches a
    decision surface.
    """
    if not np.isfinite(lam_bps) or lam_bps <= 0:
        raise ValueError(f"lam_bps must be finite and positive, got {lam_bps!r}")
    if not np.isfinite(p0) or p0 <= 0:
        raise ValueError(f"p0 must be finite and positive, got {p0!r}")
    d = np.asarray(distance_bps, dtype=float)
    if np.any(d < 0):
        raise ValueError("distance_bps must be non-negative (distance from mid, not signed)")
    return p0 * np.exp(-d / lam_bps)


def fit_fill_decay(distance_bps: np.ndarray | list[float],
                   fill_prob: np.ndarray | list[float],
                   *, min_points: int = MIN_DECAY_POINTS,
                   basis: str = "counterfactual") -> FillDecay:
    """Fit p = p0 * exp(-d / lam) by OLS of log(p) on d.

    Only strictly-positive probabilities carry information about a decay length -- a zero is
    censored (it says "not observed to fill in this window", not "probability exactly zero"), so
    zeros are DROPPED rather than clipped to a small number. Clipping would invent a data point
    at whatever floor was chosen and drag `lam` toward it.
    """
    d = np.asarray(distance_bps, dtype=float)
    p = np.asarray(fill_prob, dtype=float)
    if d.shape != p.shape:
        raise ValueError(f"distance/probability length mismatch: {d.shape} vs {p.shape}")
    if d.size == 0:
        return FillDecay(float("nan"), float("nan"), float("nan"), 0, _NO_DATA,
                         "no observations supplied", basis)

    usable = np.isfinite(d) & np.isfinite(p) & (p > 0.0) & (d >= 0.0)
    d, p = d[usable], p[usable]
    n = int(d.size)
    if n < min_points:
        return FillDecay(float("nan"), float("nan"), float("nan"), n, _UNDERPOWERED,
                         f"{n} usable points, need {min_points} -- a decay length fitted here "
                         "is noise", basis)
    if float(np.ptp(d)) <= 0.0:
        return FillDecay(float("nan"), float("nan"), float("nan"), n, _UNIDENTIFIED,
                         "quote distance has ZERO VARIANCE across the sample -- a regressor that "
                         "never moves identifies no slope, however many rows accumulate", basis)

    y = np.log(p)
    slope, intercept = np.polyfit(d, y, 1)
    if not np.isfinite(slope) or slope >= 0.0:
        return FillDecay(float("nan"), float("nan"), float("nan"), n, _UNIDENTIFIED,
                         f"fitted slope {slope:.6g} is not negative -- fill probability does not "
                         "decay with distance in this sample, so the model does not apply", basis)

    resid = y - (slope * d + intercept)
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return FillDecay(lam_bps=float(-1.0 / slope), p0=float(np.exp(intercept)),
                     r2=r2, n=n, status=_OK, why="", basis=basis)


def signed_flow(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    """(timestamp_ms, SIGNED size) for every print. The primitive the repo did not have.

    THE CLAIM THIS EXISTS TO REFUTE is "direction is not published", which a previous trade
    reader asserted while returning unsigned size. It is false for every tape the desk has ever
    recorded, and the error is load-bearing: unsigned volume cannot estimate an order-flow
    IMBALANCE at all, which is the one quantity the module is for.

      A maker flag (k="t"):     "m" is buyer-is-maker. m=True -> the buyer was passive, so the
                                AGGRESSOR was a seller -> -1. m=False -> aggressor bought -> +1.
      An explicit side (k="trades"): each print in "v" carries "side", already the TAKER side.

    MT5 ticks carry the same information in a third spelling -- a tick flagged BUY or SELL names
    the aggressor directly -- so a reader for that tape adds a branch here rather than a module.

    Rows whose direction genuinely cannot be read are DROPPED, not signed zero -- a zero is a real
    flow observation meaning "balanced", and manufacturing one from an unreadable row would bias
    every downstream imbalance toward the middle.
    """
    ts: list[float] = []
    qty: list[float] = []
    for r in rows:
        kind = r.get("k")
        if kind == "t":                                    # Binance aggTrade
            m, q = r.get("m"), r.get("q")
            if m is None or q is None:
                continue
            try:
                size = float(q)
            except (TypeError, ValueError):
                continue
            ts.append(float(r.get("t", 0.0)))
            qty.append(-size if bool(m) else size)
        elif kind == "trades":                             # Bybit batch
            for tr in r.get("v") or []:
                side = str(tr.get("side", "")).upper()
                raw = tr.get("size", tr.get("v"))
                if side not in ("BUY", "SELL") or raw is None:
                    continue
                try:
                    size = float(raw)
                except (TypeError, ValueError):
                    continue
                ts.append(float(tr.get("time", r.get("t", 0.0)) or 0.0))
                qty.append(size if side == "BUY" else -size)
    if not ts:
        return np.empty(0, dtype=float), np.empty(0, dtype=float)
    t = np.asarray(ts, dtype=float)
    q = np.asarray(qty, dtype=float)
    order = np.argsort(t, kind="stable")
    return t[order], q[order]


def window_ofi(t_ms: np.ndarray, signed_qty: np.ndarray,
               edges_ms: np.ndarray | list[float]) -> np.ndarray:
    """Net signed volume in each [edges[i], edges[i+1]) bucket -- the order-flow imbalance.

    Normalised by the GROSS volume in the same window, so the result is a dimensionless
    imbalance in [-1, 1] comparable across symbols of wildly different notional. An empty
    window is 0.0 imbalance, which is correct here (no flow means no imbalance) and distinct
    from the unreadable-row case handled in `signed_flow`.
    """
    e = np.asarray(edges_ms, dtype=float)
    if e.size < 2:
        raise ValueError("need at least two bucket edges")
    if np.any(np.diff(e) <= 0):
        raise ValueError("bucket edges must be strictly increasing")
    net = np.zeros(e.size - 1, dtype=float)
    if t_ms.size == 0:
        return net
    idx = np.searchsorted(e, t_ms, side="right") - 1
    inside = (idx >= 0) & (idx < net.size)
    if not np.any(inside):
        return net
    i, q = idx[inside], signed_qty[inside]
    gross = np.bincount(i, weights=np.abs(q), minlength=net.size)
    signed = np.bincount(i, weights=q, minlength=net.size)
    nz = gross > 0
    net[nz] = signed[nz] / gross[nz]
    return net


def fit_ofi_response(ofi: np.ndarray | list[float], ret_bps: np.ndarray | list[float],
                     *, min_points: int = MIN_OFI_POINTS,
                     basis: str = "counterfactual") -> OfiResponse:
    """Fit r = beta * OFI through the origin.

    Through the origin deliberately: an intercept here would absorb any drift in the sample and
    report it as a flow response. Zero net flow must predict zero expected move, or the model is
    measuring the period rather than the mechanism.
    """
    x = np.asarray(ofi, dtype=float)
    y = np.asarray(ret_bps, dtype=float)
    if x.shape != y.shape:
        raise ValueError(f"ofi/return length mismatch: {x.shape} vs {y.shape}")
    usable = np.isfinite(x) & np.isfinite(y)
    x, y = x[usable], y[usable]
    n = int(x.size)
    if n == 0:
        return OfiResponse(float("nan"), float("nan"), 0, _NO_DATA,
                           "no observations supplied", basis)
    if n < min_points:
        return OfiResponse(float("nan"), float("nan"), n, _UNDERPOWERED,
                           f"{n} usable points, need {min_points} -- a response coefficient "
                           "fitted here would step execution on noise", basis)
    denom = float(x @ x)
    if denom <= 0.0:
        return OfiResponse(float("nan"), float("nan"), n, _UNIDENTIFIED,
                           "order-flow imbalance is identically zero across the sample -- no "
                           "variation to regress against", basis)
    beta = float((x @ y) / denom)
    resid = y - beta * x
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum(y ** 2))          # through-origin R2 is against zero, not the mean
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return OfiResponse(beta_bps=beta, r2=r2, n=n, status=_OK, why="", basis=basis)


def passive_impact_curve(decay: FillDecay, response: OfiResponse,
                         *, distance_bps: np.ndarray | list[float],
                         ofi_scale: float = 1.0) -> PassiveImpact:
    """Combine the two halves into the passive impact rate at each quote distance.

    Refuses unless BOTH halves are OK. A curve built from one good fit and one failed one would
    be a plottable object carrying a fabricated number, which is the L1.55 failure exactly: an
    artifact that is well-formed, young, and built from an input that was never measured.
    """
    d = np.asarray(distance_bps, dtype=float)
    if not decay.ok or not response.ok:
        bad = [f"decay={decay.status}" if not decay.ok else "",
               f"response={response.status}" if not response.ok else ""]
        why = "; ".join(w for w in bad if w)
        return PassiveImpact([], [], [], _UNIDENTIFIED,
                             f"cannot combine: {why} -- refusing to publish a curve with a "
                             "fabricated half", decay.as_dict(), response.as_dict())
    p = fill_probability_curve(d, lam_bps=decay.lam_bps, p0=decay.p0)
    impact = response.beta_bps * float(ofi_scale) * p
    return PassiveImpact([float(v) for v in d], [float(v) for v in p],
                         [float(v) for v in impact], _OK, "",
                         decay.as_dict(), response.as_dict())


#: Tape fields that would record where a passive quote was actually placed. None of these exists
#: today; the list is the CONTRACT the executor must satisfy before own-fill identification is
#: possible, and it is checked rather than described.
_OFFSET_FIELDS = ("quote_px", "placed_px", "quote_offset_bps", "spot_quote_px", "fut_quote_px")


def identifiability(tape_rows: list[dict[str, Any]]) -> Identifiability:
    """Is the fill-decay curve identifiable from the desk's OWN fills? Measured on the tape.

    THE ANSWER TODAY IS NO, AND NOT FOR WANT OF ROWS. `_passive_price` quotes at the touch on
    every order, so the placement offset is a constant; and no tape field records it in any case.
    This function exists so that fact is re-derived from the artifact on every run rather than
    trusted from this docstring -- the day an offset arm is added to the excitation design, the
    verdict flips on its own and nobody has to remember to come back.
    """
    n = len(tape_rows)
    if n == 0:
        return Identifiability(_NO_DATA, "execution tape is empty", 0, 0)
    present = [f for f in _OFFSET_FIELDS if any(f in r for r in tape_rows)]
    if not present:
        return Identifiability(
            _UNIDENTIFIED,
            "NO tape field records where the passive quote was placed (looked for: "
            f"{', '.join(_OFFSET_FIELDS)}). Separately, run_cashcarry_executor._passive_price "
            "quotes at the touch on every order, so the offset would be a CONSTANT even if it "
            "were recorded -- a regressor with no variance identifies no slope. Own-fill "
            "identification needs an OFFSET ARM in the excitation design, not more fills.",
            n, 0)
    offsets = [float(r[f]) for r in tape_rows for f in present
               if isinstance(r.get(f), (int, float))]
    k = len(offsets)
    if k < MIN_DECAY_POINTS:
        return Identifiability(_UNDERPOWERED,
                               f"{k} rows carry a placement offset, need {MIN_DECAY_POINTS}",
                               n, k)
    var = float(np.var(np.asarray(offsets, dtype=float)))
    if var <= 0.0:
        return Identifiability(_UNIDENTIFIED,
                               "placement offset is recorded but CONSTANT across every row -- "
                               "still no variance to identify a decay length",
                               n, k, var)
    return Identifiability(_OK, "", n, k, var)
