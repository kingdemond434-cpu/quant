"""PROBABILITY ENGINES: the interface, the reliability curve, consensus and the dislocation rule.

RESEARCH 11 "Probability and Fair-Value Dislocation" / LAWS 5m. Several independent probability
engines (P1 macro/statistical, P2 options-implied, P3 prediction market, P4 cross-asset, P5
LLM/news, P6 physical/fundamental) each say "p" about an MT5 target over a horizon. This module
is the arithmetic every engine is judged by, and it is pure: no file, no clock, no network, and
nothing here sizes capital.

THE FOUR RULES IT ENFORCES
  * ANTI-LOOKAHEAD. A forecast carries `available_time` and is usable only at or after it
    (`usable`); `resolved_pairs` withholds anything else from the record and COUNTS what it
    withheld, so a curve built from leaked forecasts cannot exist by construction.
  * A RELIABILITY CURVE HAS AN n. "When it says 80%, how often did it happen?" is answered by
    binned frequencies and an isotonic (pool-adjacent-violators) fit, per engine and per regime
    when the caller keys it so. A bin or a table under its minimum n is UNMEASURED -- never 0,
    never 50%, never the raw p dressed as calibrated.
  * THE ENSEMBLE IS CALIBRATED OR ABSENT. An engine with no MEASURED table cannot enter it and is
    named in `excluded`; an ensemble with no member is UNMEASURED and fires nothing.
  * A DISLOCATION IS NET. |p_ensemble - p_market| must clear costs (the probability mass the
    round trip eats out of the market's own distribution) + model uncertainty (member
    disagreement and each member's measured calibration error) + a regime buffer (the regime's
    own calibration error, or a penalty when the regime is UNMEASURED). Below that line nothing
    fires, and the verdict says which term stopped it.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
from typing import Any, Protocol

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"

#: The six engines of RESEARCH 11, by name. Order is the report's order.
ENGINES: tuple[str, ...] = ("P1_macro_statistical", "P2_options_implied",
                            "P3_prediction_market", "P4_cross_asset", "P5_llm_news",
                            "P6_physical_fundamental")
HORIZONS: tuple[str, ...] = ("1h", "4h", "1d", "5d")
HORIZON_BARS: dict[str, int] = {"1h": 1, "4h": 4, "1d": 24, "5d": 120}

#: What a forecast claims. `up` is P(return over the horizon > 0); `exceed_1sd` is P(|return|
#: exceeds the engine's own one-sigma move) -- the claim an implied-volatility surface makes.
CLAIM_UP = "up"
CLAIM_EXCEED = "exceed_1sd"

QUANTILE_KEYS: tuple[str, ...] = ("q05", "q25", "q50", "q75", "q95")
QUANTILE_LEVELS: tuple[float, ...] = (0.05, 0.25, 0.50, 0.75, 0.95)

MIN_N_BIN = 30
MIN_N_TABLE = 100
MIN_N_LEAD = 30
DEFAULT_BINS = 10
REGIME_BUFFER_BASE = 0.02
UNMEASURED_REGIME_PENALTY = 0.25
SHOCK_THRESHOLD = 0.15
EPS = 1e-6


def clip(p: float, eps: float = EPS) -> float:
    return min(1.0 - eps, max(eps, float(p)))


def logit(p: float) -> float:
    q = clip(p)
    return math.log(q / (1.0 - q))


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


# ----------------------------------------------------------------------------- the interface
@dataclass(frozen=True)
class ProbabilityForecast:
    """One engine's claim about one target over one horizon, stamped with when it may be USED."""

    engine: str
    target: str
    horizon: str
    at: datetime
    available_time: datetime
    p: float
    quantiles: Mapping[str, float] = field(default_factory=dict)
    source: str = ""
    claim: str = CLAIM_UP
    regime: str = ""
    n_basis: int = 0
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"engine": self.engine, "target": self.target, "horizon": self.horizon,
                "at": self.at.isoformat(), "available_time": self.available_time.isoformat(),
                "p": round(float(self.p), 6), "quantiles": dict(self.quantiles),
                "source": self.source, "claim": self.claim, "regime": self.regime,
                "n_basis": int(self.n_basis), "note": self.note}


class Engine(Protocol):
    """`forecast(target, horizon, at)` -> a stamped claim, or None when the engine has nothing
    it may say (which the caller reports as UNMEASURED by name, never as p = 0.5)."""

    @property
    def name(self) -> str: ...

    def forecast(self, target: str, horizon: str, at: datetime) -> ProbabilityForecast | None: ...


def usable(forecast: ProbabilityForecast, at: datetime) -> bool:
    """THE ANTI-LOOKAHEAD RULE: a forecast may be used at `at` only once it was available."""
    return forecast.available_time <= at


@dataclass(frozen=True)
class Resolved:
    """A forecast that has met its outcome: y = 1 if the claim came true, else 0."""

    p: float
    y: float
    regime: str
    at: datetime


@dataclass(frozen=True)
class Record:
    pairs: tuple[Resolved, ...]
    withheld_lookahead: int
    unresolved: int

    def as_dict(self) -> dict[str, Any]:
        return {"n": len(self.pairs), "withheld_lookahead": self.withheld_lookahead,
                "unresolved": self.unresolved}


def resolved_pairs(forecasts: Sequence[ProbabilityForecast],
                   outcome: Callable[[ProbabilityForecast], float | None], *,
                   decision_time: Callable[[ProbabilityForecast], datetime] | None = None,
                   ) -> Record:
    """Pair every forecast with its outcome, WITHHOLDING those not usable at their decision time.

    `decision_time` defaults to the forecast's own `at`: a forecast made at t from an input that
    only became available after t is a leak, and it is counted rather than silently kept."""
    pairs: list[Resolved] = []
    withheld = unresolved = 0
    for f in forecasts:
        when = decision_time(f) if decision_time is not None else f.at
        if not usable(f, when):
            withheld += 1
            continue
        y = outcome(f)
        if y is None:
            unresolved += 1
            continue
        pairs.append(Resolved(p=clip(f.p), y=1.0 if float(y) > 0.5 else 0.0,
                              regime=f.regime, at=f.at))
    return Record(pairs=tuple(pairs), withheld_lookahead=withheld, unresolved=unresolved)


# ----------------------------------------------------------------------------- calibration
@dataclass(frozen=True)
class CalibrationBin:
    lo: float
    hi: float
    n: int
    mean_p: float | None
    freq: float | None
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {"lo": self.lo, "hi": self.hi, "n": self.n,
                "mean_p": None if self.mean_p is None else round(self.mean_p, 4),
                "freq": None if self.freq is None else round(self.freq, 4),
                "status": self.status}


@dataclass(frozen=True)
class CalibrationTable:
    """The reliability curve of one engine (in one regime): bins with n, the isotonic fit, and
    the two summary errors. `calibrate(p)` maps a stated p through the fit; an UNMEASURED table
    returns p unchanged, and the caller must not treat that as calibrated."""

    n: int
    status: str
    bins: tuple[CalibrationBin, ...]
    isotonic: tuple[tuple[float, float], ...]
    brier: float | None
    ece: float | None
    base_rate: float | None
    min_n_bin: int = MIN_N_BIN
    min_n_table: int = MIN_N_TABLE
    why: str = ""

    def calibrate(self, p: float) -> float:
        return calibrate(p, self)

    def as_dict(self) -> dict[str, Any]:
        return {"n": self.n, "status": self.status,
                "bins": [b.as_dict() for b in self.bins],
                "isotonic": [[round(a, 4), round(b, 4)] for a, b in self.isotonic],
                "brier": None if self.brier is None else round(self.brier, 5),
                "ece": None if self.ece is None else round(self.ece, 5),
                "base_rate": None if self.base_rate is None else round(self.base_rate, 4),
                "min_n_bin": self.min_n_bin, "min_n_table": self.min_n_table,
                "why": self.why}


def isotonic_fit(pairs: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    """Pool-adjacent-violators: breakpoints (mean p, mean y) of the blocks, non-decreasing in y."""
    rows = sorted((clip(p), float(y)) for p, y in pairs)
    if not rows:
        return ()
    blocks: list[list[float]] = []            # [sum_p, sum_y, n]
    for p, y in rows:
        blocks.append([p, y, 1.0])
        while len(blocks) >= 2 and blocks[-2][1] / blocks[-2][2] > blocks[-1][1] / blocks[-1][2]:
            b = blocks.pop()
            blocks[-1][0] += b[0]
            blocks[-1][1] += b[1]
            blocks[-1][2] += b[2]
    return tuple((b[0] / b[2], b[1] / b[2]) for b in blocks)


def calibrate(p: float, table: CalibrationTable | None) -> float:
    """p through the isotonic fit by linear interpolation between breakpoints (clamped at the
    ends). UNMEASURED or absent table: p unchanged."""
    if table is None or table.status != MEASURED or not table.isotonic:
        return clip(p)
    pts = table.isotonic
    q = clip(p)
    if q <= pts[0][0]:
        return clip(pts[0][1])
    if q >= pts[-1][0]:
        return clip(pts[-1][1])
    for (x0, y0), (x1, y1) in pairwise(pts):
        if x0 <= q <= x1:
            if x1 - x0 < 1e-12:
                return clip(y1)
            return clip(y0 + (y1 - y0) * (q - x0) / (x1 - x0))
    return clip(pts[-1][1])


def reliability_curve(pairs: Sequence[tuple[float, float]], *, bins: int = DEFAULT_BINS,
                      min_n_bin: int = MIN_N_BIN, min_n_table: int = MIN_N_TABLE,
                      ) -> CalibrationTable:
    """The reliability curve of a (p, y) record with the minimum-n UNMEASURED rule applied to
    every bin and to the table as a whole."""
    n = len(pairs)
    if n < min_n_table:
        return CalibrationTable(n=n, status=UNMEASURED, bins=(), isotonic=(), brier=None,
                                ece=None, base_rate=None, min_n_bin=min_n_bin,
                                min_n_table=min_n_table,
                                why=f"{n} resolved forecasts < {min_n_table}")
    width = 1.0 / max(1, bins)
    sums: list[list[float]] = [[0.0, 0.0, 0.0] for _ in range(bins)]
    brier = 0.0
    ysum = 0.0
    for p, y in pairs:
        q = clip(p)
        k = min(bins - 1, int(q / width))
        sums[k][0] += q
        sums[k][1] += float(y)
        sums[k][2] += 1.0
        brier += (q - float(y)) ** 2
        ysum += float(y)
    out: list[CalibrationBin] = []
    ece_num = 0.0
    ece_den = 0.0
    for k, (sp, sy, cnt) in enumerate(sums):
        c = int(cnt)
        if c >= min_n_bin:
            out.append(CalibrationBin(lo=round(k * width, 4), hi=round((k + 1) * width, 4),
                                      n=c, mean_p=sp / cnt, freq=sy / cnt, status=MEASURED))
            ece_num += cnt * abs(sy / cnt - sp / cnt)
            ece_den += cnt
        else:
            out.append(CalibrationBin(lo=round(k * width, 4), hi=round((k + 1) * width, 4),
                                      n=c, mean_p=None, freq=None, status=UNMEASURED))
    return CalibrationTable(n=n, status=MEASURED, bins=tuple(out), isotonic=isotonic_fit(pairs),
                            brier=brier / n, ece=(ece_num / ece_den) if ece_den else None,
                            base_rate=ysum / n, min_n_bin=min_n_bin, min_n_table=min_n_table)


def curves_by_regime(record: Sequence[Resolved], *, bins: int = DEFAULT_BINS,
                     min_n_bin: int = MIN_N_BIN, min_n_table: int = MIN_N_TABLE,
                     ) -> dict[str, CalibrationTable]:
    """One table per regime plus `overall`. A regime the record never saw is simply absent, which
    the caller reads as UNMEASURED."""
    by: dict[str, list[tuple[float, float]]] = {}
    for r in record:
        by.setdefault(r.regime or "unlabelled", []).append((r.p, r.y))
    out = {k: reliability_curve(v, bins=bins, min_n_bin=min_n_bin, min_n_table=min_n_table)
           for k, v in sorted(by.items())}
    out["overall"] = reliability_curve([(r.p, r.y) for r in record], bins=bins,
                                       min_n_bin=min_n_bin, min_n_table=min_n_table)
    return out


# ----------------------------------------------------------------------------- consensus
def dispersion(ps: Sequence[float]) -> float | None:
    """Population standard deviation of the stated probabilities; None below two readings."""
    if len(ps) < 2:
        return None
    m = sum(ps) / len(ps)
    return math.sqrt(sum((p - m) ** 2 for p in ps) / len(ps))


@dataclass(frozen=True)
class Consensus:
    p: float | None
    dispersion: float | None
    n: int
    engines: tuple[str, ...]
    agreement: float | None
    anomalies: Mapping[str, float]
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {"p": None if self.p is None else round(self.p, 6),
                "dispersion": None if self.dispersion is None else round(self.dispersion, 6),
                "n": self.n, "engines": list(self.engines),
                "agreement": None if self.agreement is None else round(self.agreement, 4),
                "anomalies": {k: round(v, 4) for k, v in self.anomalies.items()},
                "status": self.status}


def consensus(readings: Mapping[str, float], weights: Mapping[str, float] | None = None,
              ) -> Consensus:
    """Who agrees, how far apart they are, and who is anomalous (leave-one-out z against the
    other readings, from three readings up). The mean is taken in logit space."""
    names = tuple(sorted(readings))
    if not names:
        return Consensus(None, None, 0, (), None, {}, UNMEASURED)
    w = {k: float((weights or {}).get(k, 1.0)) for k in names}
    tot = sum(w.values()) or 1.0
    lm = sum(w[k] * logit(readings[k]) / tot for k in names)
    ps = [clip(readings[k]) for k in names]
    up = sum(1 for p in ps if p > 0.5)
    down = sum(1 for p in ps if p < 0.5)
    agreement = max(up, down) / len(ps)
    anomalies: dict[str, float] = {}
    if len(ps) >= 3:
        for k in names:
            others = [clip(readings[j]) for j in names if j != k]
            m = sum(others) / len(others)
            sd = dispersion(others) or 0.0
            anomalies[k] = (clip(readings[k]) - m) / max(sd, 0.02)
    return Consensus(p=sigmoid(lm), dispersion=dispersion(ps), n=len(ps), engines=names,
                     agreement=agreement, anomalies=anomalies, status=MEASURED)


@dataclass(frozen=True)
class Lead:
    lag: int
    corr: float | None
    leader: str
    n: int
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {"lag": self.lag, "corr": None if self.corr is None else round(self.corr, 4),
                "leader": self.leader, "n": self.n, "status": self.status}


def _corr(x: Sequence[float], y: Sequence[float]) -> float | None:
    n = min(len(x), len(y))
    if n < 3:
        return None
    mx = sum(x[:n]) / n
    my = sum(y[:n]) / n
    sxx = sum((a - mx) ** 2 for a in x[:n])
    syy = sum((b - my) ** 2 for b in y[:n])
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((a - mx) * (b - my) for a, b in zip(x[:n], y[:n], strict=False))
    return sxy / math.sqrt(sxx * syy)


def lead(a: Sequence[float], b: Sequence[float], *, max_lag: int = 12,
         min_n: int = MIN_N_LEAD) -> Lead:
    """Who leads whom: the lag k maximising |corr(da_t, db_{t+k})| on the two engines' changes.
    k > 0 means `a` moved first. Below `min_n` aligned changes the answer is UNMEASURED."""
    n = min(len(a), len(b))
    da = [a[i + 1] - a[i] for i in range(n - 1)]
    db = [b[i + 1] - b[i] for i in range(n - 1)]
    if len(da) < min_n:
        return Lead(0, None, "none", len(da), UNMEASURED)
    best_k, best_c = 0, 0.0
    found = False
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            c = _corr(da[: len(da) - k] if k else da, db[k:])
        else:
            c = _corr(da[-k:], db[: len(db) + k])
        if c is not None and (not found or abs(c) > abs(best_c)):
            best_k, best_c, found = k, c, True
    if not found:
        return Lead(0, None, "none", len(da), UNMEASURED)
    leader = "a" if best_k > 0 else ("b" if best_k < 0 else "coincident")
    return Lead(best_k, best_c, leader, len(da), MEASURED)


def shock(previous: float | None, current: float, *, threshold: float = SHOCK_THRESHOLD) -> bool:
    """A probability shock: the engine moved by more than `threshold` since its last reading."""
    return previous is not None and abs(clip(current) - clip(previous)) > threshold


# ----------------------------------------------------------------------------- the market side
@dataclass(frozen=True)
class MarketImplied:
    """What the instrument itself prices: its own recent distribution of horizon returns."""

    p: float | None
    quantiles: Mapping[str, float]
    cost_probability: float | None
    n: int
    status: str
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"p": None if self.p is None else round(self.p, 6),
                "quantiles": {k: round(v, 8) for k, v in self.quantiles.items()},
                "cost_probability": (None if self.cost_probability is None
                                     else round(self.cost_probability, 6)),
                "n": self.n, "status": self.status, "why": self.why}


def quantiles(values: Sequence[float], levels: Sequence[float] = QUANTILE_LEVELS,
              keys: Sequence[str] = QUANTILE_KEYS) -> dict[str, float]:
    xs = sorted(float(v) for v in values)
    if not xs:
        return {}
    out: dict[str, float] = {}
    for key, lv in zip(keys, levels, strict=False):
        pos = lv * (len(xs) - 1)
        lo = math.floor(pos)
        hi = min(len(xs) - 1, lo + 1)
        out[key] = xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)
    return out


def market_implied(returns: Sequence[float], *, cost: float, min_n: int = MIN_N_TABLE,
                   ) -> MarketImplied:
    """p = the recent frequency of a positive horizon return; the quantiles of that same
    distribution; and the probability mass a round trip of `cost` (in return units) eats."""
    rs = [float(r) for r in returns if r == r]
    if len(rs) < min_n:
        return MarketImplied(None, {}, None, len(rs), UNMEASURED,
                             why=f"{len(rs)} horizon returns < {min_n}")
    p = sum(1 for r in rs if r > 0) / len(rs)
    eaten = sum(1 for r in rs if abs(r) <= abs(cost)) / len(rs)
    return MarketImplied(p=p, quantiles=quantiles(rs), cost_probability=eaten, n=len(rs),
                         status=MEASURED)


# ----------------------------------------------------------------------------- the ensemble
@dataclass(frozen=True)
class Ensemble:
    """The calibrated members and their pooled claim; the excluded, by name and reason."""

    p: float | None
    uncertainty: float | None
    n: int
    members: Mapping[str, float]
    raw: Mapping[str, float]
    excluded: Mapping[str, str]
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {"p": None if self.p is None else round(self.p, 6),
                "uncertainty": None if self.uncertainty is None else round(self.uncertainty, 6),
                "n": self.n, "members": {k: round(v, 6) for k, v in self.members.items()},
                "raw": {k: round(v, 6) for k, v in self.raw.items()},
                "excluded": dict(self.excluded), "status": self.status}


def ensemble(readings: Mapping[str, float], tables: Mapping[str, CalibrationTable | None],
             weights: Mapping[str, float] | None = None) -> Ensemble:
    """Only an engine with a MEASURED table enters, and it enters CALIBRATED. Uncertainty pools
    the members' disagreement (as a standard error), their measured calibration errors and the
    sampling error of the calibration records themselves."""
    members: dict[str, float] = {}
    excluded: dict[str, str] = {}
    eces: list[float] = []
    ses: list[float] = []
    for name, p in sorted(readings.items()):
        t = tables.get(name)
        if t is None or t.status != MEASURED:
            excluded[name] = (t.why if t is not None and t.why else
                              "no reliability curve for this engine in this regime")
            continue
        cp = calibrate(p, t)
        members[name] = cp
        eces.append(float(t.ece if t.ece is not None else 0.0))
        ses.append(math.sqrt(cp * (1.0 - cp) / max(1, t.n)))
    if not members:
        return Ensemble(None, None, 0, {}, dict(readings), excluded, UNMEASURED)
    con = consensus(members, weights)
    disp = con.dispersion or 0.0
    unc = math.sqrt(disp * disp / len(members) + (sum(e * e for e in eces) / len(eces))
                    + (sum(s * s for s in ses) / len(ses)))
    return Ensemble(p=con.p, uncertainty=unc, n=len(members), members=members,
                    raw=dict(readings), excluded=excluded, status=MEASURED)


def regime_buffer(table: CalibrationTable | None, *, base: float = REGIME_BUFFER_BASE,
                  penalty: float = UNMEASURED_REGIME_PENALTY) -> float:
    """The regime's own calibration error on top of a flat base; an UNMEASURED regime carries
    the penalty instead, which keeps a dislocation from firing on a curve nobody measured."""
    if table is None or table.status != MEASURED:
        return base + penalty
    return base + float(table.ece or 0.0)


@dataclass(frozen=True)
class Dislocation:
    edge: float | None
    threshold: float | None
    fired: bool
    side: int
    costs: float | None
    uncertainty: float | None
    regime_buffer: float
    status: str
    why: str

    def as_dict(self) -> dict[str, Any]:
        return {"edge": None if self.edge is None else round(self.edge, 6),
                "threshold": None if self.threshold is None else round(self.threshold, 6),
                "fired": self.fired, "side": self.side,
                "costs": None if self.costs is None else round(self.costs, 6),
                "uncertainty": None if self.uncertainty is None else round(self.uncertainty, 6),
                "regime_buffer": round(self.regime_buffer, 6),
                "status": self.status, "why": self.why}


def dislocation(ens: Ensemble, market: MarketImplied, *, costs: float | None = None,
                uncertainty: float | None = None, regime_buffer: float = 0.0) -> Dislocation:
    """Fires only when the calibrated ensemble disagrees with the market-implied state by more
    than costs + model uncertainty + the regime buffer. `costs` defaults to the market's own
    cost probability, `uncertainty` to the ensemble's."""
    if ens.status != MEASURED or ens.p is None:
        return Dislocation(None, None, False, 0, costs, uncertainty, regime_buffer, UNMEASURED,
                           "ensemble UNMEASURED: no calibrated member")
    if market.status != MEASURED or market.p is None:
        return Dislocation(None, None, False, 0, costs, uncertainty, regime_buffer, UNMEASURED,
                           f"market-implied state UNMEASURED: {market.why}")
    c = float(costs if costs is not None else (market.cost_probability or 0.0))
    u = float(uncertainty if uncertainty is not None else (ens.uncertainty or 0.0))
    threshold = c + u + float(regime_buffer)
    edge = float(ens.p) - float(market.p)
    fired = abs(edge) > threshold
    side = 0 if not fired else (1 if edge > 0 else -1)
    if fired:
        why = (f"|edge| {abs(edge):.4f} > costs {c:.4f} + uncertainty {u:.4f} + "
               f"regime buffer {regime_buffer:.4f}")
    else:
        biggest = max((c, "costs"), (u, "uncertainty"), (regime_buffer, "regime buffer"))[1]
        why = (f"|edge| {abs(edge):.4f} <= threshold {threshold:.4f}; largest term: {biggest}")
    return Dislocation(edge, threshold, fired, side, c, u, float(regime_buffer), MEASURED, why)


# ----------------------------------------------------------------------------- V(a) scheduling
def value_of_cell(*, edge: float | None, threshold: float | None, dispersion: float | None,
                  n_engines: int, novelty: float = 1.0, cost_s: float = 1.0) -> float:
    """V(a) of testing a cell: the excess edge above its threshold (what a fired cell is worth)
    plus the engines' disagreement (what a test RESOLVES), weighted by novelty, per unit cost.
    UNMEASURED edge contributes nothing but the disagreement still has value."""
    excess = 0.0
    if edge is not None and threshold is not None:
        excess = max(0.0, abs(float(edge)) - float(threshold))
    disp = float(dispersion or 0.0)
    return round((4.0 * excess + disp + 0.01 * max(0, n_engines)) * max(0.0, novelty)
                 / max(1e-6, cost_s), 8)


def schedule(values: Mapping[str, float], *, capacity: int) -> list[str]:
    """The `capacity` highest-valued cells, highest first; ties broken by key so the order is
    stable across passes."""
    ranked = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[: max(0, capacity)]]
