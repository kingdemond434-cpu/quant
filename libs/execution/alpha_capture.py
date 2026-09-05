"""Alpha capture: how much of the research edge survives contact with the broker.

    AlphaCapture = realised edge / predicted FRICTIONLESS edge

THE ONE NUMBER. "A strategy with +0.25R theoretical expectancy that loses 0.08R through
execution has 0.17R. Recover 0.04R of that and you've increased actual edge 24% without
discovering another signal." That arithmetic is a capture ratio of 0.68 becoming 0.84, and the
reason it deserves its own module is that no other figure on the desk distinguishes a strategy
that stopped working from a strategy that works exactly as researched and is being taken apart in
the two seconds between the decision and the fill. Those two have identical realised P&L curves
and opposite remedies: the first needs new research, the second needs a different order type.

DENOMINATOR DISCIPLINE. The denominator must be the edge BEFORE execution costs, or the ratio
measures nothing -- a backtest that already charges a modelled spread and then gets divided into
a realised return produces a number near 1.0 whatever the broker does. `frictionless_edge_r`
states its preference order and every row records which basis it used, so a report can say what
fraction of its denominator came from each. A non-positive predicted edge makes the ratio
meaningless (dividing by roughly zero manufactures a spectacular number in either direction) and
returns UNMEASURED rather than a figure.

THE LEAKAGE IS DECOMPOSED, AND THE RESIDUAL IS NAMED. Spread, slippage and commission are the
three costs the desk can attribute to a row. Everything else is the RESIDUAL and is printed as
such -- calling the residual "impact" because impact is the last thing on the list is how a cost
model acquires a term that absorbs its own errors.

ADVERSE SELECTION IS MEASURED SEPARATELY, ON PURPOSE. It is not a line in the leakage identity:
the post-fill markout is not a component of the realised R of a trade that ran for hours, and
adding it to a sum that must reconcile would break the sum. It is reported beside, at every
horizon the corpus carries, with the decomposition microstructure actually supports:

    adverse_selection_r(h) = -E[markout_h | filled]     positive = the market left as we arrived
    transient_r            =  E[markout_5m] - E[markout_1s]
                             positive = the price came BACK, so the early move was our own
                             footprint; negative = it kept going, so the fill carried information
                             the desk did not have. The second is what cannot be executed away.

EVERY CELL CARRIES n AND AN INTERVAL, and below `MIN_N` a cell is UNMEASURED with its numeric
fields None. The ratio's interval is the delta method on a ratio of two PAIRED means -- realised
and predicted come from the same rows, so their covariance is in the variance and dropping it
would report an interval narrower than the evidence.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from libs.execution.fill_corpus import FillRecord, record_from_row

__all__ = [
    "MIN_N",
    "AlphaCapture",
    "adverse_selection",
    "by_key",
    "capture",
    "frictionless_edge_r",
    "precision",
    "report",
    "trend",
]

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
Z95 = 1.959964

#: Fills a cell needs before its capture ratio is a number rather than an anecdote. Deliberately
#: the same floor `digital_twin.MIN_N` uses, so one thin sample does not clear one gate and fail
#: another on the same desk.
MIN_N = 20
#: A predicted frictionless edge below this (in R) is treated as zero: the ratio is a division by
#: noise and reports UNMEASURED instead of a large number with a sign nobody should trust.
MIN_DENOM_R = 0.01
#: How tight the capture ratio has to be before it is worth acting on. The principal's own
#: arithmetic moves the ratio from 0.68 to 0.84, so an interval wider than +/-0.10 cannot tell
#: those two apart and the number, while MEASURED, is not yet a number to steer by.
TARGET_HALF_WIDTH = 0.10


def _f(x: Any) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _as_records(rows: Iterable[FillRecord | Mapping[str, Any]]) -> list[FillRecord]:
    return [r if isinstance(r, FillRecord) else record_from_row(r) for r in rows]


def frictionless_edge_r(rec: FillRecord) -> tuple[float | None, str]:
    """The edge the desk expected BEFORE execution cost, in R, and the basis it came from.

    Preference order, most explicit first:
      1. `posterior_edge_r`   -- the posterior that authorised the size, already in R
      2. `predicted_r_mean`   -- the predicted distribution's mean
      3. `signal_bps` / stop  -- the raw signal in basis points converted to R by the trade's own
                                 initial stop distance, GROSSED BACK UP by `modelled_cost_bps`
                                 when the row carries one, because a signal already net of a
                                 modelled cost is not frictionless

    Every caller records the basis. A report that cannot say which denominators it used cannot
    be compared with itself a month later.
    """
    v = _f(rec.posterior_edge_r)
    if v is not None:
        return v, "posterior_edge_r"
    v = _f(rec.predicted_r_mean)
    if v is not None:
        return v, "predicted_r_mean"
    bps, stop = _f(rec.signal_bps), _f(rec.stop_frac)
    if bps is not None and stop and stop > 0:
        gross = bps + (_f(rec.modelled_cost_bps) or 0.0)
        return (gross * 1e-4) / stop, ("signal_bps+modelled_cost/stop"
                                       if _f(rec.modelled_cost_bps) is not None
                                       else "signal_bps/stop")
    return None, "none"


def _spread_cost_r(rec: FillRecord) -> float | None:
    """The spread this trade actually paid, in R, round trip: ONE quoted spread, not two.

    The reference quote the intent records is already the far side (ask for a buy), so crossing
    once costs half the spread against the mid and the round trip costs exactly the whole quoted
    spread. NOT the simulator's charge: `engine.Costs` uses `mult=2.0` on the registry's MEDIAN
    spread as a deliberately conservative gate ("a median is a median"), and that padding is
    correct for admitting a strategy and wrong here. This function attributes cost that was
    genuinely incurred; charging the gate's safety factor would inflate the attributed spread and
    shrink the RESIDUAL by exactly the padding -- which would hide, inside a conservative
    assumption, the part of the leakage nobody has explained yet.
    """
    s, stop = _f(rec.spread_frac_at_decision), _f(rec.stop_frac)
    if s is None or not stop or stop <= 0:
        return None
    return s / stop


def _mean_ci(xs: Sequence[float]) -> tuple[float, float, float]:
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, m, m
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return m, m - Z95 * se, m + Z95 * se


def _ratio_ci(rs: Sequence[float], ps: Sequence[float]) -> tuple[float, float] | None:
    """Delta-method 95% interval for mean(rs)/mean(ps) on PAIRED samples.

    Var(R/P) ~= (1/P^2) Var(R) + (R^2/P^4) Var(P) - 2 (R/P^3) Cov(R,P), all on the MEANS. The
    covariance term is what makes this honest: realised and predicted come from the same trades
    and move together, so treating them as independent reports an interval narrower than the
    evidence supports.
    """
    n = len(rs)
    if n < 2 or n != len(ps):
        return None
    rb, pb = sum(rs) / n, sum(ps) / n
    if abs(pb) < MIN_DENOM_R:
        return None
    vr = sum((x - rb) ** 2 for x in rs) / (n - 1) / n
    vp = sum((x - pb) ** 2 for x in ps) / (n - 1) / n
    cv = sum((a - rb) * (b - pb) for a, b in zip(rs, ps, strict=True)) / (n - 1) / n
    var = vr / pb ** 2 + (rb ** 2) * vp / pb ** 4 - 2.0 * rb * cv / pb ** 3
    if not math.isfinite(var) or var < 0:
        return None
    half = Z95 * math.sqrt(var)
    q = rb / pb
    return (q - half, q + half)


@dataclass(frozen=True)
class AlphaCapture:
    """One cell: how much of the predicted edge came back, and where the rest went."""

    n: int
    status: str
    realized_edge_r: float | None = None
    predicted_frictionless_edge_r: float | None = None
    ratio: float | None = None
    ratio_ci95: list[float] | None = None
    leakage_r: float | None = None
    #: spread / slippage / commission / residual, all in R, all positive = a cost.
    leakage: dict[str, float | None] = field(default_factory=dict)
    #: How many fills the ratio needs before its interval is tight enough to steer by, and
    #: whether it already is. MEASURED is not the same as USABLE.
    precision: dict[str, Any] = field(default_factory=dict)
    #: How many rows contributed each denominator basis, so the cell can be compared over time.
    denominator_basis: dict[str, int] = field(default_factory=dict)
    why: str = ""

    def to_row(self) -> dict[str, Any]:
        return {"n": self.n, "status": self.status,
                "realized_edge_r": self.realized_edge_r,
                "predicted_frictionless_edge_r": self.predicted_frictionless_edge_r,
                "alpha_capture_ratio": self.ratio, "ratio_ci95": self.ratio_ci95,
                "leakage_r": self.leakage_r, "leakage": self.leakage,
                "precision": self.precision,
                "denominator_basis": self.denominator_basis, "why": self.why}


def capture(records: Iterable[FillRecord | Mapping[str, Any]], *,
            min_n: int = MIN_N) -> AlphaCapture:
    """The capture ratio over one set of fills, with its leakage decomposition.

    Only rows with BOTH a realised R and a frictionless predicted edge are used: a fill with no
    predicted edge cannot contribute to a ratio, and imputing one from the sleeve's average would
    make the denominator partly a function of the numerator's own population.
    """
    recs = _as_records(records)
    pairs: list[tuple[float, float, FillRecord]] = []
    basis: dict[str, int] = {}
    for r in recs:
        real = _f(r.realized_r)
        pred, b = frictionless_edge_r(r)
        if real is None or pred is None:
            continue
        basis[b] = basis.get(b, 0) + 1
        pairs.append((real, pred, r))
    n = len(pairs)
    if n < min_n:
        return AlphaCapture(n=n, status=UNMEASURED, denominator_basis=basis,
                            why=(f"{n} fills carry both a realised R and a frictionless predicted "
                                 f"edge; a capture ratio needs {min_n}"))
    rs = [p[0] for p in pairs]
    ps = [p[1] for p in pairs]
    rb, _, _ = _mean_ci(rs)
    pb, _, _ = _mean_ci(ps)
    if pb < MIN_DENOM_R:
        return AlphaCapture(n=n, status=UNMEASURED, realized_edge_r=round(rb, 6),
                            predicted_frictionless_edge_r=round(pb, 6),
                            denominator_basis=basis,
                            why=(f"predicted frictionless edge is {pb:+.4f}R, below the "
                                 f"{MIN_DENOM_R}R floor: a ratio against it is division by noise, "
                                 "not a measurement of execution"))
    lk: dict[str, float | None] = {}
    for name, fn in (("spread", _spread_cost_r),
                     ("slippage", lambda r: _f(r.slip_r)),
                     ("commission", lambda r: _f(r.commission_r))):
        vals = [v for v in (fn(r) for _, _, r in pairs) if v is not None]
        lk[name] = round(sum(vals) / len(vals), 6) if vals else None
    leak = pb - rb
    attributed = sum(v for v in lk.values() if v is not None)
    lk["residual"] = round(leak - attributed, 6)
    ci = _ratio_ci(rs, ps)
    return AlphaCapture(
        n=n, status=MEASURED, realized_edge_r=round(rb, 6),
        predicted_frictionless_edge_r=round(pb, 6), ratio=round(rb / pb, 6),
        ratio_ci95=([round(ci[0], 6), round(ci[1], 6)] if ci else None),
        leakage_r=round(leak, 6), leakage=lk, denominator_basis=basis,
        precision=precision(n, ci),
        why=("residual is leakage the desk cannot attribute to spread, slippage or commission -- "
             "it is not impact until something measures impact"))


def precision(n: int, ci: tuple[float, float] | None, *,
              target_half_width: float = TARGET_HALF_WIDTH) -> dict[str, Any]:
    """MEASURED IS NOT THE SAME AS USABLE, and this is the field that says so.

    The interval on a ratio narrows as 1/sqrt(n), so the fills needed for a half-width of
    `target_half_width` is `n x (observed_half_width / target)^2`. Reporting it stops the desk
    reading a MEASURED ratio of 1.36 with an interval of [0.69, 2.03] as evidence of anything:
    that interval contains "execution costs a third of the edge" and "execution doubles it".

    This is also the argument for measuring execution on SLIPPAGE and MARKOUTS rather than on
    trade P&L: the numerator's dispersion is what sets this n, and realised R per trade is the
    noisiest numerator on the desk.
    """
    if not ci or n < 2:
        return {"status": UNMEASURED, "why": "no interval yet"}
    half = (ci[1] - ci[0]) / 2.0
    if not (half > 0 and math.isfinite(half)):
        return {"status": UNMEASURED, "why": "degenerate interval"}
    need = math.ceil(n * (half / target_half_width) ** 2)
    ok = half <= target_half_width
    return {"status": MEASURED if ok else UNMEASURED,
            "half_width": round(half, 6), "target_half_width": target_half_width,
            "n_have": n, "n_for_target": need, "shortfall": max(0, need - n),
            "why": ("the interval is tight enough to steer by" if ok else
                    f"the ratio is measured but its interval is +/-{half:.3f}; steering needs "
                    f"+/-{target_half_width:g}, which is {need} fills on this numerator's "
                    "dispersion")}


def by_key(records: Iterable[FillRecord | Mapping[str, Any]], key: str, *,
           min_n: int = MIN_N) -> dict[str, dict[str, Any]]:
    """The capture ratio per value of one field: `sleeve`, `session` or `symbol`.

    Every group is reported, including the ones below `min_n` -- a sleeve whose capture cannot be
    measured yet is a fact the desk needs, and dropping it from the table would make the report
    silently describe only the sleeves that trade often.
    """
    recs = _as_records(records)
    groups: dict[str, list[FillRecord]] = {}
    for r in recs:
        groups.setdefault(str(getattr(r, key, "") or "unknown"), []).append(r)
    return {k: capture(v, min_n=min_n).to_row() for k, v in sorted(groups.items())}


def adverse_selection(records: Iterable[FillRecord | Mapping[str, Any]], *,
                      min_n: int = MIN_N) -> dict[str, Any]:
    """Post-fill markout at every horizon the corpus carries, and the transient/permanent split.

    `adverse_selection_r` is positive when the market moved AGAINST the fill after it printed --
    the desk bought and the price went down. `transient_r` is the 5-minute markout minus the
    1-second one: positive means the price came back, so the initial move was the desk's own
    footprint and a patient order would have avoided it; negative means it kept going, so the
    fill was against someone who knew more, and no order type recovers that. The two have
    different remedies, which is why they are separated rather than summed.
    """
    recs = _as_records(records)
    out: dict[str, Any] = {"min_n": min_n, "unit": "R", "horizons": {}}
    means: dict[str, float] = {}
    for name in ("markout_1s_r", "markout_5s_r", "markout_30s_r", "markout_5m_r"):
        xs = [v for v in (_f(getattr(r, name, None)) for r in recs) if v is not None]
        if len(xs) < min_n:
            out["horizons"][name] = {"n": len(xs), "status": UNMEASURED,
                                     "adverse_selection_r": None, "ci95": None}
            continue
        m, lo, hi = _mean_ci(xs)
        means[name] = m
        out["horizons"][name] = {"n": len(xs), "status": MEASURED,
                                 "markout_r": round(m, 6),
                                 "adverse_selection_r": round(-m, 6),
                                 "ci95": [round(-hi, 6), round(-lo, 6)]}
    if "markout_5m_r" in means and "markout_1s_r" in means:
        t = means["markout_5m_r"] - means["markout_1s_r"]
        out["transient_r"] = round(t, 6)
        out["interpretation"] = ("the price came back after the fill: the early move was the "
                                 "desk's own footprint, and a patient style should recover it"
                                 if t > 0 else
                                 "the price kept going after the fill: the desk was selected "
                                 "against, and no order type recovers information risk")
    else:
        out["transient_r"] = None
        out["interpretation"] = (f"{UNMEASURED}: needs {min_n} fills with both a 1s and a 5m "
                                 "markout, which needs a tick tape covering the fill minute")
    return out


def trend(history: Sequence[Mapping[str, Any]], *, min_points: int = 3) -> dict[str, Any]:
    """The capture ratio's slope over its own history: is execution getting better or worse.

    `history` is this organ's own append-only ledger, newest last, each row carrying `at`, `ratio`
    and `n`. The slope is per RECORDED POINT rather than per day, because the organ's clock, not
    the calendar, decides when a point exists; an OLS slope with fewer than `min_points` is not
    reported at all.
    """
    pts = [(i, _f(r.get("ratio"))) for i, r in enumerate(history)]
    xy = [(float(i), v) for i, v in pts if v is not None]
    if len(xy) < min_points:
        return {"status": UNMEASURED, "n_points": len(xy),
                "why": f"needs {min_points} recorded capture ratios; has {len(xy)}"}
    n = len(xy)
    mx = sum(x for x, _ in xy) / n
    my = sum(y for _, y in xy) / n
    sxx = sum((x - mx) ** 2 for x, _ in xy)
    if sxx <= 0:
        return {"status": UNMEASURED, "n_points": n, "why": "no spread in the point index"}
    slope = sum((x - mx) * (y - my) for x, y in xy) / sxx
    return {"status": MEASURED, "n_points": n, "slope_per_point": round(slope, 6),
            "first": round(xy[0][1], 6), "last": round(xy[-1][1], 6),
            "direction": ("improving" if slope > 0 else
                          "deteriorating" if slope < 0 else "flat")}


def report(records: Iterable[FillRecord | Mapping[str, Any]], *,
           min_n: int = MIN_N, history: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """The whole alpha-capture section: overall, per sleeve, per session, per symbol, adverse
    selection and the trend. Every cell carries its own n and status."""
    recs = _as_records(records)
    #: LIVE ONLY. A demo server fills at the trigger and does not slip, so a demo row drags the
    #: capture ratio toward 1.0 using a fill that could not have leaked. Segregate, never blend
    #: (`mt5desk.markout`'s rule, and the reason it refuses a mixed ledger outright).
    live = [r for r in recs if r.account_kind == "live"]
    use = live if live else recs
    overall = capture(use, min_n=min_n)
    return {
        "unit": "R", "min_n": min_n,
        "n_records": len(recs), "n_live": len(live),
        "population": ("live fills only" if live else
                       f"NO LIVE FILLS -- measured on all {len(recs)} rows, whose account_kind "
                       "is demo or unknown; a demo fill does not slip and inflates capture"),
        "overall": overall.to_row(),
        "by_sleeve": by_key(use, "sleeve", min_n=min_n),
        "by_session": by_key(use, "session", min_n=min_n),
        "by_symbol": by_key(use, "symbol", min_n=min_n),
        "adverse_selection": adverse_selection(use, min_n=min_n),
        "trend": trend(history),
    }
