"""THE EXECUTION / MARKET-IMPACT ALPHA LAB -- what the desk's OWN orders do, and cost, and reveal.

WHY. `latency_lab` times the desk's order; `execution_alpha_miner` mines the tape for states
where waiting pays; `netting_report` counts the spreads netting saves. None of them asks the
question a desk that owns its fills can answer and nobody else can: WHEN THIS DESK TRADES, WHAT
HAPPENS TO THE PRICE, AND WHAT DID THE VENUE DO TO THE ORDER? That is a regression on the desk's
own signed flow against the venue's subsequent mid, and it is the only impact estimate that is
about this account rather than about somebody's paper.

WHAT IS MEASURED, from the desk's own order records joined to its own tape:

    spread_by_session        the venue's spread in the sessions the desk trades
    fill_probability         per order type, with a Wilson interval (n is small and says so)
    rejection_behaviour      by reason, by session, by order type
    slippage                 signed bps against the requested price, per order type
    partial_fills            how often and how much the venue filled less than asked
    stop_behaviour           the pending-stop subset: fill rate and where it printed
    kyle_lambda              price change on signed flow, OLS with a PERMUTATION null
    impact_decomposition     permanent = long-horizon lambda; transient = short - long
    queue_latency_effect     does the desk's own decision-to-send latency buy worse fills
    session_cost_curve       spread + slippage, per session: the cost the sleeve actually pays
    toxicity                 P(adverse markout | fill) over a window -- a STATE, not a score

PURE. Arrays and records in, dicts out; the organ does the joining. Every estimate carries n and
UNMEASURED is a value (L1.28a): with 29 filled rows on this box most per-instrument cells will
read UNMEASURED, and a pooled number normalised per instrument is published beside them with
its basis named. Nothing here sizes, caps or vetoes: an execution cell is a HYPOTHESIS about
where the desk's edge survives its costs, and it goes to the gauntlet like any other.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
#: A non-overlapping partition of the UTC day, so a cost curve sums to the day. Named here and
#: nowhere else in this module; `moat_series.SESSIONS` overlaps on purpose for cell census and
#: is a different question.
SESSIONS: dict[str, tuple[int, int]] = {"asia": (0, 8), "london": (8, 14), "overlap": (14, 16),
                                        "new_york": (16, 22), "late": (22, 24)}
#: Below this many observations a rate is a sample and a regression is not run.
MIN_N = 10
MIN_REGRESSION_N = 12
PERMUTATIONS = 500
#: Toxicity state thresholds on the Wilson interval of P(adverse).
TOXIC_LOWER = 0.6
BENIGN_UPPER = 0.4


@dataclass(frozen=True)
class OrderRecord:
    """One order the desk sent, as far as its records and its tape can say. None is UNMEASURED."""

    instrument: str
    t_ms: float
    side: int                      # +1 buy, -1 sell, 0 unknown
    lots: float
    order_type: str                # market | pending_stop | limit | ...
    session: str
    requested: float | None = None
    fill_price: float | None = None
    filled_frac: float | None = None
    rejected: bool = False
    reject_reason: str = ""
    latency_ms: float | None = None
    mid_before: float | None = None
    mid_short: float | None = None
    mid_long: float | None = None
    spread_bps: float | None = None
    done: bool | None = None           # the venue said DONE, even where no price was recorded

    @property
    def filled(self) -> bool:
        if self.rejected:
            return False
        if self.done is not None:
            return self.done and (self.filled_frac is None or self.filled_frac > 0)
        return self.fill_price is not None and (self.filled_frac is None or self.filled_frac > 0)

    def slippage_bps(self) -> float | None:
        """Signed: positive means the desk paid more than it asked (bought higher / sold lower)."""
        if self.fill_price is None or self.requested is None or self.requested == 0:
            return None
        if self.side == 0:
            return None
        # Rounded at a nanobasis-point: 1e4 * (100.01 - 100) / 100 is 1.0000000000005116 in
        # binary, and a slippage read as "one bp and change" by an exact comparison is noise
        # wearing a measurement's clothes (measured 2026-09-22, the lab's own test).
        return round(float(self.side * (self.fill_price - self.requested) / self.requested * 1e4),
                     9)

    def markout_bps(self, horizon: str) -> float | None:
        """Signed mid move AFTER the fill in the desk's direction: negative is adverse."""
        after = self.mid_short if horizon == "short" else self.mid_long
        if after is None or self.mid_before is None or self.mid_before == 0 or self.side == 0:
            return None
        return float(self.side * (after - self.mid_before) / self.mid_before * 1e4)


def session_of_hour(hour: int) -> str:
    h = int(hour) % 24
    for name, (lo, hi) in SESSIONS.items():
        if lo <= h < hi:
            return name
    return "late"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _q(values: Sequence[float]) -> dict[str, Any]:
    arr = np.asarray([v for v in values if v is not None and math.isfinite(float(v))],
                     dtype=float)
    if arr.size == 0:
        return {"status": UNMEASURED, "n": 0}
    return {"status": MEASURED if arr.size >= MIN_N else "SAMPLE", "n": int(arr.size),
            "mean": round(float(arr.mean()), 4), "p50": round(float(np.median(arr)), 4),
            "p90": round(float(np.percentile(arr, 90)), 4),
            "max": round(float(arr.max()), 4), "min": round(float(arr.min()), 4)}


# ------------------------------------------------------------------------ the venue's terms
def spread_by_session(hours: Sequence[int] | FloatArray, spread_bps: Sequence[float] | FloatArray
                      ) -> dict[str, dict[str, Any]]:
    """Spread quantiles per session of the UTC day, from any tick sample the caller hands in."""
    h = np.asarray(hours, dtype=float)
    s = np.asarray(spread_bps, dtype=float)
    out: dict[str, dict[str, Any]] = {}
    for name, (lo, hi) in SESSIONS.items():
        m = (h >= lo) & (h < hi) & np.isfinite(s)
        out[name] = _q(list(s[m]))
    return out


def fill_probability(orders: Sequence[OrderRecord]) -> dict[str, dict[str, Any]]:
    """Per order type: P(filled | sent) with its Wilson interval. Rejected orders are UNFILLED,
    not excluded -- excluding them is the denominator trick."""
    out: dict[str, dict[str, Any]] = {}
    types = sorted({o.order_type or "unknown" for o in orders})
    for kind in [*types, "all"]:
        rows = [o for o in orders if kind == "all" or (o.order_type or "unknown") == kind]
        n, k = len(rows), sum(1 for o in rows if o.filled)
        ci = wilson(k, n)
        out[kind] = {"status": MEASURED if n >= MIN_N else ("SAMPLE" if n else UNMEASURED),
                     "n": n, "filled": k, "p_fill": None if not n else round(k / n, 4),
                     "ci95": None if ci is None else [round(ci[0], 4), round(ci[1], 4)]}
    return out


def rejection_behaviour(orders: Sequence[OrderRecord]) -> dict[str, Any]:
    n = len(orders)
    rej = [o for o in orders if o.rejected]
    by_reason: dict[str, int] = {}
    by_session: dict[str, dict[str, int]] = {}
    by_type: dict[str, dict[str, int]] = {}
    for o in orders:
        by_session.setdefault(o.session, {"n": 0, "rejected": 0})
        by_session[o.session]["n"] += 1
        by_type.setdefault(o.order_type or "unknown", {"n": 0, "rejected": 0})
        by_type[o.order_type or "unknown"]["n"] += 1
        if o.rejected:
            reason = o.reject_reason or "unstated"
            by_reason[reason] = by_reason.get(reason, 0) + 1
            by_session[o.session]["rejected"] += 1
            by_type[o.order_type or "unknown"]["rejected"] += 1
    ci = wilson(len(rej), n)
    return {"status": MEASURED if n >= MIN_N else ("SAMPLE" if n else UNMEASURED), "n": n,
            "rejected": len(rej), "rate": None if not n else round(len(rej) / n, 4),
            "ci95": None if ci is None else [round(ci[0], 4), round(ci[1], 4)],
            "by_reason": dict(sorted(by_reason.items(), key=lambda kv: -kv[1])),
            "by_session": by_session, "by_order_type": by_type}


def slippage(orders: Sequence[OrderRecord]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    types = sorted({o.order_type or "unknown" for o in orders if o.filled})
    for kind in [*types, "all"]:
        vals = [s for s in (o.slippage_bps() for o in orders
                            if o.filled and (kind == "all" or (o.order_type or "unknown") == kind))
                if s is not None]
        out[kind] = _q(vals)
    return out


def partial_fills(orders: Sequence[OrderRecord]) -> dict[str, Any]:
    filled = [o for o in orders if o.filled and o.filled_frac is not None]
    partial = [o for o in filled if 0 < float(o.filled_frac or 0.0) < 1.0]
    n = len(filled)
    return {"status": MEASURED if n >= MIN_N else ("SAMPLE" if n else UNMEASURED), "n": n,
            "partial": len(partial), "rate": None if not n else round(len(partial) / n, 4),
            "filled_frac": _q([float(o.filled_frac or 0.0) for o in partial])}


def stop_behaviour(orders: Sequence[OrderRecord]) -> dict[str, Any]:
    """The pending-stop subset: how often a placed stop printed, and how far from its level."""
    stops = [o for o in orders if "stop" in (o.order_type or "").lower()]
    filled = [o for o in stops if o.filled]
    ci = wilson(len(filled), len(stops))
    return {"status": MEASURED if len(stops) >= MIN_N else ("SAMPLE" if stops else UNMEASURED),
            "n": len(stops), "filled": len(filled),
            "p_fill": None if not stops else round(len(filled) / len(stops), 4),
            "ci95": None if ci is None else [round(ci[0], 4), round(ci[1], 4)],
            "rejected": sum(1 for o in stops if o.rejected),
            "slippage_bps": _q([s for s in (o.slippage_bps() for o in filled) if s is not None]),
            "note": "a stop that never printed is UNFILLED evidence about the level, not a"
                    " missing row"}


# -------------------------------------------------------------------------------- impact
def kyle_lambda(flow: Sequence[float] | FloatArray, dprice_bps: Sequence[float] | FloatArray, *,
                permutations: int = PERMUTATIONS, rng_seed: int = 20260922,
                min_n: int = MIN_REGRESSION_N) -> dict[str, Any]:
    """dp = alpha + lambda * q by OLS, with a permutation null on the flow's SIGNS.

    Permuting signs (not rows) keeps the size distribution and the price-change distribution
    exactly as observed and asks only whether the DIRECTION of the desk's flow explains the
    direction of the move. p is two-sided on |lambda|. Below `min_n` it is UNMEASURED.
    """
    q = np.asarray(flow, dtype=float)
    y = np.asarray(dprice_bps, dtype=float)
    keep = np.isfinite(q) & np.isfinite(y) & (q != 0)
    q, y = q[keep], y[keep]
    n = int(q.size)
    if n < min_n or float(np.var(q)) <= 0:
        return {"status": UNMEASURED, "n": n,
                "why": f"fewer than {min_n} signed flow observations or no size variation"}

    def _slope(qq: FloatArray) -> float:
        qc = qq - qq.mean()
        return float((qc * (y - y.mean())).sum() / (qc * qc).sum())

    lam = _slope(q)
    resid = y - (y.mean() + lam * (q - q.mean()))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 0.0 if ss_tot <= 0 else 1.0 - float((resid ** 2).sum()) / ss_tot
    rng = np.random.default_rng(rng_seed)
    null = np.asarray([_slope(np.abs(q) * rng.choice([-1.0, 1.0], size=n))
                       for _ in range(max(0, permutations))])
    p = float(np.mean(np.abs(null) >= abs(lam))) if null.size else None
    return {"status": MEASURED, "n": n, "lambda_bps_per_unit": round(lam, 6),
            "r2": round(r2, 4), "p_permutation": p, "permutations": int(null.size),
            "null_sd": None if not null.size else round(float(null.std()), 6),
            "basis": "OLS of signed mid change (bps) on signed flow; null = permuted flow signs"}


def normalised_flow(orders: Sequence[OrderRecord]) -> dict[str, float]:
    """Signed lots per instrument, divided by that instrument's own median lot so that the
    pooled regression is in comparable units. {order index: flow}. Unknown side is skipped."""
    lots_by: dict[str, list[float]] = {}
    for o in orders:
        if o.filled and o.side != 0 and o.lots > 0:
            lots_by.setdefault(o.instrument, []).append(o.lots)
    med = {k: float(np.median(v)) for k, v in lots_by.items()}
    out: dict[str, float] = {}
    for i, o in enumerate(orders):
        if o.filled and o.side != 0 and o.lots > 0 and med.get(o.instrument, 0.0) > 0:
            out[str(i)] = o.side * o.lots / med[o.instrument]
    return out


def impact_decomposition(orders: Sequence[OrderRecord], *, permutations: int = PERMUTATIONS,
                         rng_seed: int = 20260922) -> dict[str, Any]:
    """Permanent impact is the long-horizon lambda; transient is the short-horizon lambda minus
    the permanent one (what reverted). Both carry their permutation p and n."""
    flows = normalised_flow(orders)
    rows: dict[str, tuple[list[float], list[float]]] = {"short": ([], []), "long": ([], [])}
    for i, o in enumerate(orders):
        f = flows.get(str(i))
        if f is None:
            continue
        for horizon in ("short", "long"):
            m = o.markout_bps(horizon)
            if m is not None:
                # markout is the mid move signed in the desk's direction, and the flow carries
                # the same sign, so it IS the price change in the flow's direction: dp = m.
                rows[horizon][0].append(f)
                rows[horizon][1].append(m)
    short = kyle_lambda(rows["short"][0], rows["short"][1], permutations=permutations,
                        rng_seed=rng_seed)
    long_ = kyle_lambda(rows["long"][0], rows["long"][1], permutations=permutations,
                        rng_seed=rng_seed)
    permanent = long_.get("lambda_bps_per_unit")
    transient = (None if permanent is None or short.get("lambda_bps_per_unit") is None
                 else round(float(short["lambda_bps_per_unit"]) - float(permanent), 6))
    return {"status": MEASURED if short["status"] == MEASURED and long_["status"] == MEASURED
            else UNMEASURED, "short_horizon": short, "long_horizon": long_,
            "permanent_bps_per_unit": permanent, "transient_bps_per_unit": transient,
            "unit": "one median lot of the instrument, signed",
            "basis": "permanent = long-horizon lambda; transient = short - long"}


def queue_latency_effect(orders: Sequence[OrderRecord], *, permutations: int = PERMUTATIONS,
                         rng_seed: int = 20260922) -> dict[str, Any]:
    """Does a slower decision-to-send buy a worse fill? Spearman rank correlation between the
    desk's own latency and its signed slippage, with a permutation p."""
    pairs = [(o.latency_ms, o.slippage_bps()) for o in orders
             if o.filled and o.latency_ms is not None and o.slippage_bps() is not None]
    n = len(pairs)
    if n < MIN_REGRESSION_N:
        return {"status": UNMEASURED, "n": n,
                "why": f"fewer than {MIN_REGRESSION_N} fills carry both a latency and a slippage"}
    lat = np.asarray([p[0] for p in pairs], dtype=float)
    slp = np.asarray([p[1] for p in pairs], dtype=float)

    def _rank(x: FloatArray) -> FloatArray:
        order = np.argsort(x, kind="stable")
        ranks = np.empty(x.size, dtype=float)
        ranks[order] = np.arange(1, x.size + 1, dtype=float)
        return ranks

    def _rho(a: FloatArray, b: FloatArray) -> float:
        ra, rb = _rank(a), _rank(b)
        if np.std(ra) == 0 or np.std(rb) == 0:
            return 0.0
        return float(np.corrcoef(ra, rb)[0, 1])

    rho = _rho(lat, slp)
    rng = np.random.default_rng(rng_seed)
    null = np.asarray([_rho(lat, rng.permutation(slp)) for _ in range(max(0, permutations))])
    return {"status": MEASURED, "n": n, "spearman_rho": round(rho, 4),
            "p_permutation": float(np.mean(np.abs(null) >= abs(rho))) if null.size else None,
            "latency_ms": _q(list(lat)), "slippage_bps": _q(list(slp))}


def session_cost_curve(orders: Sequence[OrderRecord],
                       spreads: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per session: the half-spread the venue quotes plus the slippage the desk paid on top --
    the cost a sleeve certified in that session actually bears. Half-spread because a market
    order crosses once."""
    out: dict[str, dict[str, Any]] = {}
    for name in SESSIONS:
        rows = [o for o in orders if o.session == name]
        slips = [s for s in (o.slippage_bps() for o in rows if o.filled) if s is not None]
        sp = spreads.get(name) or {}
        half = None if sp.get("p50") is None else float(sp["p50"]) / 2.0
        mean_slip = None if not slips else float(np.mean(slips))
        total = (None if half is None else round(half + (mean_slip or 0.0), 4))
        out[name] = {"status": (MEASURED if half is not None and len(slips) >= MIN_N
                                else (UNMEASURED if half is None and not slips else "PARTIAL")),
                     "n_orders": len(rows), "n_filled": sum(1 for o in rows if o.filled),
                     "half_spread_bps": None if half is None else round(half, 4),
                     "slippage_mean_bps": None if mean_slip is None else round(mean_slip, 4),
                     "cost_bps": total,
                     "basis": "half of the session's p50 spread + mean signed slippage; a"
                              " session with no fills carries the spread term only"}
    return out


def toxicity(orders: Sequence[OrderRecord], *, horizon: str = "short") -> dict[str, Any]:
    """P(adverse markout | fill) over the window the caller chose, as a STATE:

        TOXIC       the Wilson lower bound is above TOXIC_LOWER
        BENIGN      the upper bound is below BENIGN_UPPER
        MIXED       measured, neither
        UNMEASURED  fewer than MIN_N fills with a markout
    """
    marks = [m for m in (o.markout_bps(horizon) for o in orders if o.filled) if m is not None]
    n = len(marks)
    if n < MIN_N:
        return {"state": UNMEASURED, "n": n, "horizon": horizon,
                "why": f"fewer than {MIN_N} fills carry a {horizon}-horizon markout"}
    adverse = sum(1 for m in marks if m < 0)
    ci = wilson(adverse, n)
    assert ci is not None
    state = "TOXIC" if ci[0] > TOXIC_LOWER else ("BENIGN" if ci[1] < BENIGN_UPPER else "MIXED")
    return {"state": state, "n": n, "horizon": horizon, "adverse": adverse,
            "p_adverse": round(adverse / n, 4), "ci95": [round(ci[0], 4), round(ci[1], 4)],
            "markout_bps": _q(marks),
            "basis": f"adverse = mid moved against the fill within the {horizon} horizon"}


def execution_cells(orders: Sequence[OrderRecord],
                    spreads_by_instrument: Mapping[str, Mapping[str, Mapping[str, Any]]]
                    ) -> list[dict[str, Any]]:
    """One row per (instrument, session) the desk has traded: cost, toxicity and fill rate,
    each MEASURED or not. These are the execution-conditioned cells research can seed from."""
    out: list[dict[str, Any]] = []
    keys = sorted({(o.instrument, o.session) for o in orders})
    for inst, sess in keys:
        rows = [o for o in orders if o.instrument == inst and o.session == sess]
        sp = (spreads_by_instrument.get(inst) or {}).get(sess) or {}
        fills = fill_probability(rows)["all"]
        tox = toxicity(rows)
        slips = _q([s for s in (o.slippage_bps() for o in rows if o.filled) if s is not None])
        measured = fills["status"] == MEASURED or tox["state"] != UNMEASURED
        out.append({"instrument": inst, "session": sess, "n": len(rows),
                    "status": MEASURED if measured else UNMEASURED,
                    "p_fill": fills.get("p_fill"), "p_fill_ci95": fills.get("ci95"),
                    "spread_p50_bps": sp.get("p50"), "slippage": slips, "toxicity": tox})
    return out
