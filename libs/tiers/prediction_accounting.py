"""LIVE PREDICTION ACCOUNTING AND REALITY OUTRANKING BACKTESTS (Tier S layers 13, 26, 27).

PREDICTION ACCOUNTING. A model that says BUY EURUSD has predicted almost nothing. Every forecast
the desk registers is a DISTRIBUTION made before the outcome: mean and sd of the return (in R or
log units), P(positive), expected holding time, predicted slippage. When the outcome arrives it is
scored:

    CRPS           the Gaussian continuous ranked probability score (lower is better)
    PIT            the forecast CDF at the outcome; calibrated forecasts give uniform PITs
    coverage90     share of outcomes inside the 90% interval (should be ~0.90)
    brier          on P(positive)
    overconfidence sd of standardised errors (>1: intervals too narrow)

A forecast registered AFTER its outcome is refused (`register` checks the clock) -- that is the
whole point -- and a sleeve trading with no registered forecast is counted as UNACCOUNTED.

REALITY OUTRANKS BACKTESTS. Each research factory (hunt/miner/source) has made backtest claims;
forward and live evidence either bear them out or do not. Its HONESTY multiplier is the shrunk
ratio of realised to claimed edge (live weighted over forward, forward over nothing), bounded to
[0, 1.5]. The posterior for any new discovery from that factory is its backtest claim times its
factory's honesty, and the researcher market prices the factory's future compute with it: a
factory that systematically exaggerates backtests is penalised automatically.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from libs.tiers.replay import parse_t

_SQRT2 = math.sqrt(2.0)
_SQRTPI = math.sqrt(math.pi)


def _phi(z: float) -> float:
    return math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)


def _cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / _SQRT2))


def crps_gauss(mu: float, sd: float, x: float) -> float:
    sd = max(sd, 1e-12)
    z = (x - mu) / sd
    return sd * (z * (2 * _cdf(z) - 1) + 2 * _phi(z) - 1 / _SQRTPI)


@dataclass(frozen=True)
class Forecast:
    key: str
    made_at: str
    horizon_end: str
    mu: float
    sd: float
    p_positive: float | None = None
    exp_hold_h: float | None = None
    exp_slippage: float | None = None
    source: str = ""


class RegistrationError(ValueError):
    pass


def register(ledger: list[Forecast], f: Forecast, outcome_time: str | None = None) -> None:
    if outcome_time is not None:
        mt, ot = parse_t(f.made_at), parse_t(outcome_time)
        if mt is None or ot is None or mt >= ot:
            raise RegistrationError(f"{f.key}: forecast made {f.made_at} is not before its "
                                    f"outcome {outcome_time}")
    if f.sd <= 0:
        raise RegistrationError(f"{f.key}: a forecast needs sd > 0")
    ledger.append(f)


def score(forecasts: Iterable[Forecast], outcomes: Mapping[str, list[tuple[str, float]]]
          ) -> dict[str, Any]:
    """outcomes: key -> [(time, realised)]. Each forecast is matched to the first outcome after
    it was made and at or before its horizon end."""
    crps: list[float] = []
    pits: list[float] = []
    zs: list[float] = []
    brier: list[float] = []
    inside = 0
    n = 0
    per_source: dict[str, list[float]] = {}
    for f in forecasts:
        mt, he = parse_t(f.made_at), parse_t(f.horizon_end)
        cand = [(parse_t(t), x) for t, x in outcomes.get(f.key, [])]
        hit = next((x for t, x in sorted(((t, x) for t, x in cand if t is not None),
                                         key=lambda tx: tx[0])
                    if mt is not None and t > mt and (he is None or t <= he)), None)
        if hit is None:
            continue
        n += 1
        c = crps_gauss(f.mu, f.sd, hit)
        crps.append(c)
        z = (hit - f.mu) / max(f.sd, 1e-12)
        zs.append(z)
        pits.append(_cdf(z))
        inside += int(abs(z) <= 1.6449)
        if f.p_positive is not None:
            brier.append((f.p_positive - (1.0 if hit > 0 else 0.0)) ** 2)
        per_source.setdefault(f.source or "?", []).append(c)
    hist = [0] * 10
    for p in pits:
        hist[min(9, int(p * 10))] += 1
    uni = None
    if pits:
        exp = len(pits) / 10
        uni = sum((h - exp) ** 2 / exp for h in hist)
    sdz = (math.sqrt(sum(z * z for z in zs) / len(zs))) if zs else None
    return {"n_scored": n, "crps": (sum(crps) / n) if n else None,
            "coverage90": (inside / n) if n else None,
            "brier": (sum(brier) / len(brier)) if brier else None,
            "pit_histogram": hist, "pit_chi2": uni, "overconfidence": sdz,
            "per_source_crps": {k: sum(v) / len(v) for k, v in sorted(per_source.items())}}


def unaccounted(traded: Iterable[tuple[str, str]], forecasts: Iterable[Forecast]
                ) -> dict[str, Any]:
    """traded: (key, time). A trade with no forecast made before it is UNACCOUNTED."""
    by: dict[str, list[str]] = {}
    for f in forecasts:
        by.setdefault(f.key, []).append(f.made_at)
    total = miss = 0
    keys: set[str] = set()
    for k, t in traded:
        total += 1
        tt = parse_t(t)
        ok = any((parse_t(m) or tt) < tt for m in by.get(k, [])) if tt else False
        if not ok:
            miss += 1
            keys.add(k)
    return {"trades": total, "unaccounted": miss,
            "accounted_share": ((total - miss) / total) if total else None,
            "unaccounted_keys": sorted(keys)[:30]}


@dataclass
class Claim:
    factory: str
    key: str
    claimed_edge: float
    forward_edge: float | None = None
    forward_n: int = 0
    live_edge: float | None = None
    live_n: int = 0


def honesty(claims: Iterable[Claim], prior_n: float = 30.0, live_weight: float = 2.0
            ) -> dict[str, Any]:
    by: dict[str, list[Claim]] = {}
    for c in claims:
        by.setdefault(c.factory, []).append(c)
    out: dict[str, Any] = {}
    for fac, cs in by.items():
        num = den = w = 0.0
        for c in cs:
            if c.claimed_edge <= 0:
                continue
            for edge, n, mult in ((c.forward_edge, c.forward_n, 1.0),
                                  (c.live_edge, c.live_n, live_weight)):
                if edge is None or n <= 0:
                    continue
                weight = n * mult
                num += weight * edge
                den += weight * c.claimed_edge
                w += weight
        ratio = (num / den) if den > 0 else 1.0
        shrunk = (w * ratio + prior_n * 1.0) / (w + prior_n)
        out[fac] = {"claims": len(cs), "evidence_weight": round(w, 2),
                    "raw_ratio": round(ratio, 4) if den > 0 else None,
                    "honesty": round(max(0.0, min(1.5, shrunk)), 4)}
    worst = sorted(out.items(), key=lambda kv: float(kv[1]["honesty"]))
    return {"factories": out, "most_exaggerating": [k for k, _v in worst[:5]]}


def posterior_edge(claimed: float, factory_honesty: float) -> float:
    return claimed * factory_honesty


def as_rows(forecasts: Iterable[Forecast]) -> list[dict[str, Any]]:
    return [asdict(f) for f in forecasts]
