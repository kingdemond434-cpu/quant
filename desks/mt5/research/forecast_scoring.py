#!/usr/bin/env python3
"""ARCH-03 / DATA-36 / ALLOC-08 -- EVERY FORECAST THE DESK MADE, SCORED AGAINST WHAT HAPPENED.

WHY THIS EXISTS. The desk writes down what it expects in two places and, until this module, read
neither of them back against the world:

  * `data/pf_forecast_log.jsonl` -- one line per allocator pass: the book it solved, the expected
    daily log growth of that book, the CVaR of its worst worlds, the regime mix it believed. The
    allocator's own comment calls it "what makes this loop learn", and nothing ever scored it.
  * `data/forecast_register.jsonl` -- every model's published `Belief` (forecast_contract, P4).
    The contract made every belief SCOREABLE at publication and then nothing scored it.

A forecast that is never compared with its outcome is not a forecast, it is a mood. This module
compares them, with the proper scoring rule for each kind, and publishes the comparison. It also
gives `model_roles.combine` its first real caller: beliefs about one subject at one horizon are
pooled (disagreement shrinks confidence, correlated sources are not independent votes, a
re-published belief is not new evidence), the pool is published with its lineage, and every
source is charged or credited with what it ADDS to the pool on scored history.

THE FROZEN RULES (DATA-36: "no uncontrolled online adaptation"). This module only MEASURES:

  1. The scoring rules are fixed in code: Brier and log loss for PROBABILITY, absolute error for
     MAGNITUDE, CRPS + interval coverage + PIT for DISTRIBUTION, and for the allocator's daily
     forecast a Gaussian read of its own (mean, CVaR) pair. Nothing here is fitted to the
     outcomes it scores, and no score is written back into any model, prior, weight or allocator
     input. A desk that tunes its forecasts on the same outcomes it then reports them against has
     an in-sample report wearing an out-of-sample label.
  2. The pool uses only what each belief STATED (its quantiles, its variance) plus quantities
     measured on outcomes that resolved STRICTLY BEFORE the belief was formed (walk-forward):
     a model's historical squared error where it stated no spread, and the correlation of two
     models' errors. Nothing is persisted between runs except the append-only pool log, which is
     a record, not a parameter -- every run recomputes everything from the ledgers.
  3. ABSENT IS UNMEASURED, NEVER ZERO (L1.28a). A section with no scoreable rows says UNMEASURED
     with the counts that explain why (pending, unresolved, refused, no ledger on this host). A
     zero Brier score and an unmeasured one are different claims and the report never confuses
     them.

WHAT "REALISED" MEANS FOR THE ALLOCATOR. Its forecast is a claim about ACCOUNT log growth over one
day (`pf_allocator.REGIME_FORECAST_H = 1`; the field is literally `expected_log_per_day`). The
outcome is read from the desk's own account records, in this order of preference:

  (a) `data/allocator_trigger_state.json` `equity_closes` -- one equity reading (incl. floating)
      per UTC day, written by the trigger. Deposits and withdrawals between two closes are taken
      out using the deal ledger's balance rows, so a top-up never reads as skill.
  (b) `data/cost_truth_quotes.json` `deals` -- the broker's deal ledger, account currency. The
      CLOSED balance is rebuilt as a running sum; growth over (t, t+1d] is trade P&L (types 0/1:
      profit + swap + commission + fee) over the balance at t. REALISED-ONLY: a position opened
      inside the window and closed after it lands in the next window, so this basis is noisier
      per day than equity and unbiased over many -- the basis is published beside every number.

Overlapping forecasts are not independent evidence: the allocator passes many times a day and
consecutive passes forecast almost the same window. The scored series is therefore the LAST pass
of each UTC day (the same convention as allocator_attribution), and the pass count is reported
beside the day count so nobody reads 300 passes as 300 observations.

THE ALLOCATOR'S DISTRIBUTION. The log keeps two numbers of the world distribution: the mean m and
CVaR_alpha c, the mean of the worst alpha of worlds (robust_elog.WorldConfig.cvar_alpha, 0.20; a
row may carry its own `cvar_alpha`). Under a Gaussian read, c = m - sd * pdf(z_a) / alpha, so
sd = (m - c) * alpha / pdf(z_a) and VaR_a = m + z_a * sd. That supports exactly what ALLOC-08
asks: PIT (is the realised day where the distribution put it?), coverage of the predicted tail
(did realised days fall below VaR_a an alpha share of the time?) and tail SEVERITY (when they did,
was the loss the size CVaR promised?). The Gaussian read is an assumption about shape, stated in
the report; a world population with a fatter left tail than the Gaussian shows up as breaches
that are too deep, which is the failure this is meant to catch. `prob_annual_loss` is a claim at
a 252-day horizon and stays UNMEASURED until the ledgers hold enough non-overlapping years.

THE REGISTER'S OUTCOMES. A belief's outcome is knowable once its window -- `outcome_start` (or
`at`) plus `horizon_s` -- has closed AND a realised value exists, either written on the row itself
(`outcome`, the convention model_self_improvement already reads) or in the append-only outcome
ledger `data/forecast_outcomes.jsonl` ({subject, at, value}), matched to the window end within
OUTCOME_TOL. A closed window with no outcome is UNRESOLVED and counted, never skipped silently:
a model whose beliefs never resolve is a model nobody can grade, which is itself the finding.

INCREMENTAL PREDICTIVE VALUE, LEAVE-ONE-SOURCE-OUT. For every scored event with two or more
sources, the pool is scored with every source and again without each one. delta = score(without)
- score(with), all scores lower-is-better, so a POSITIVE delta means the source made the pool
better. An informative source earns a positive delta; an exact duplicate earns ~0 (its errors
correlate 1 with its twin's, so combine counts it as one vote); a noise source earns a negative
one (it pulls the mean away and its disagreement inflates the variance). This is the number that
decides whether a model is WORTH ITS RENT in the pool, as opposed to merely accurate on its own.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import NormalDist
from types import ModuleType
from typing import Any


def _load_sibling(name: str) -> ModuleType:
    """A sibling research module, loaded BY PATH and shared under its own name.

    Same reason as forecast_contract._load_roles: this file is run as a script by hourly_cycle,
    loaded by path in tests and imported as `research.*`, and only the path is the same in all
    three. Registering under the bare name means forecast_contract's own `model_roles` and ours
    are ONE registry, not two copies that could disagree about a family's roles.
    """
    mod = sys.modules.get(name)
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent /
                                                  f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"{name}.py is missing beside forecast_scoring.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_fc = _load_sibling("forecast_contract")
_roles = _load_sibling("model_roles")

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
FORECAST_LOG = DATA / "pf_forecast_log.jsonl"
REGISTER = _fc.REGISTER
OUTCOMES = DATA / "forecast_outcomes.jsonl"
QUOTES = DATA / "cost_truth_quotes.json"
TRIGGER_STATE = DATA / "allocator_trigger_state.json"
POOL_LOG = DATA / "forecast_pool_log.jsonl"
REPORT = BASE / "reports" / "FORECAST_SCORES.json"

UNMEASURED = "UNMEASURED"

#: The allocator's forecast horizon. pf_allocator.REGIME_FORECAST_H is 1 day and the logged field
#: is `expected_log_per_day`; read as a constant rather than by importing a 5,000-line solver
#: into a scorer. If the allocator's horizon ever changes, its log line must carry it.
ALLOC_HORIZON_S = 86400.0
#: robust_elog.WorldConfig.cvar_alpha. The forecast log does not record alpha; a row that does
#: (`cvar_alpha`) overrides this. Proposed: pf_allocator should log it (see the report).
ALLOC_CVAR_ALPHA = 0.20
#: Probability clip for log loss. A forecast of exactly 0 or 1 that is wrong scores infinity; the
#: clip turns that into a very large finite penalty so one such row cannot NaN the whole table.
LOG_EPS = 1e-6
RELIABILITY_BINS = 10
PIT_BINS = 10
#: Outcome-ledger matching tolerance around the window end: 60 s or 2% of the horizon.
OUTCOME_TOL_FLOOR_S = 60.0
OUTCOME_TOL_FRAC = 0.02
#: Walk-forward minimums before a MEASURED quantity replaces the stated / declared one.
MIN_VAR_HISTORY = 5
MIN_RHO_PAIRS = 10
#: The variance an untracked PROBABILITY source is given when it states none and has no history:
#: the Bernoulli maximum. An unproven model never earns weight it has not shown.
UNTRACKED_PROB_VAR = 0.25

_N = NormalDist()


# =============================================================================== small helpers
def _num(x: Any) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float, str)):
        return None
    try:
        v = float(x)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _ts(x: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _iso(d: datetime) -> str:
    return d.astimezone(UTC).isoformat(timespec="seconds")


def _mean(xs: Sequence[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _rnd(x: float | None, nd: int = 6) -> float | None:
    return None if x is None or not math.isfinite(x) else round(x, nd)


def _std(xs: Sequence[float]) -> float | None:
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    rows.append(r)
    except OSError:
        return []
    return rows


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _unmeasured(why: str, **counts: Any) -> dict[str, Any]:
    return {"status": UNMEASURED, "n": 0, "why": why} | counts


def atomic_write_text(path: Path, text: str, *, retries: int = 5) -> None:
    """Temp + fsync + os.replace, retrying the Windows sharing violation a concurrent reader
    causes. The issue board and the CRO cycle read this report while the hourly leg writes it; a
    torn read of half a score table is a measurement nobody made."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    for i in range(retries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == retries - 1:
                raise
            time.sleep(0.05 * (i + 1))


# =============================================================================== proper rules
def brier(p: float, y: float) -> float:
    return (p - y) ** 2


def log_loss(p: float, y: float) -> float:
    q = min(1.0 - LOG_EPS, max(LOG_EPS, p))
    return -(y * math.log(q) + (1.0 - y) * math.log(1.0 - q))


def crps_gaussian(mu: float, sd: float, y: float) -> float:
    """Closed-form CRPS of N(mu, sd^2) at y; sd <= 0 degenerates to absolute error."""
    if not sd > 0:
        return abs(y - mu)
    z = (y - mu) / sd
    return sd * (z * (2.0 * _N.cdf(z) - 1.0) + 2.0 * _N.pdf(z) - 1.0 / math.sqrt(math.pi))


def quantiles_of(value: Any) -> tuple[list[tuple[float, float]], bool] | None:
    """{tau: q} -> sorted [(tau, q)] and whether the values had to be REARRANGED to be monotone.

    NOT A VALIDATOR. Validating a DISTRIBUTION belief's quantiles at publication belongs to the
    contract (another thread owns that clause); if `forecast_contract.quantile_defects` exists
    the scorer defers to it in `_row_defects`. Here a crossed set is rearranged (sorting the
    values, Chernozhukov et al.'s monotone rearrangement, which never worsens any quantile loss)
    and FLAGGED, so a crossing model is visible in the report without being unscoreable.
    """
    if not isinstance(value, Mapping) or not value:
        return None
    pairs: list[tuple[float, float]] = []
    for k, v in value.items():
        t, q = _num(k), _num(v)
        if t is None or q is None or not 0.0 < t < 1.0:
            return None
        pairs.append((t, q))
    pairs.sort()
    vals = [q for _t, q in pairs]
    srt = sorted(vals)
    return [(t, q) for (t, _), q in zip(pairs, srt, strict=True)], srt != vals


def crps_quantiles(pairs: Sequence[tuple[float, float]], y: float) -> float:
    """CRPS by its quantile decomposition: CRPS = 2 * integral of the pinball loss over tau.

    Approximated by the trapezoid over the stated levels (a single level degenerates to twice its
    pinball loss). Exact as the grid fills [0, 1]; on a coarse grid it is a consistent proper
    score for the stated quantiles, which is the claim the model actually made.
    """
    losses = [(t, (t - (1.0 if y < q else 0.0)) * (y - q)) for t, q in pairs]
    if len(losses) == 1:
        return 2.0 * losses[0][1]
    # integrate over [0,1]: flat extension of the end losses to the edges, trapezoid inside
    total = losses[0][0] * losses[0][1] + (1.0 - losses[-1][0]) * losses[-1][1]
    for (t0, l0), (t1, l1) in itertools.pairwise(losses):
        total += (t1 - t0) * (l0 + l1) / 2.0
    return 2.0 * total


def pit_quantiles(pairs: Sequence[tuple[float, float]], y: float) -> float:
    """F(y) under the piecewise-linear CDF through the stated quantiles. Outside the stated
    range the mass beyond the end quantile is split evenly (tau_min/2, (1+tau_max)/2): the model
    said nothing about where inside its tail, so the PIT says no more than it did."""
    t0, q0 = pairs[0]
    tn, qn = pairs[-1]
    if y < q0:
        return t0 / 2.0
    if y > qn:
        return (1.0 + tn) / 2.0
    for (ta, qa), (tb, qb) in itertools.pairwise(pairs):
        if qa <= y <= qb:
            return ta if qb == qa else ta + (tb - ta) * (y - qa) / (qb - qa)
    return tn


def median_sd_of(pairs: Sequence[tuple[float, float]]) -> tuple[float, float | None]:
    """A Gaussian read of stated quantiles, for pooling: median, and sd from the widest
    symmetric pair (q_{1-t} - q_t) / (2 z_{1-t}); None when the belief states no spread."""
    taus = [t for t, _ in pairs]
    qs = [q for _, q in pairs]
    if 0.5 in taus:
        med = qs[taus.index(0.5)]
    elif taus[0] < 0.5 < taus[-1]:
        med = next(qa + (qb - qa) * (0.5 - ta) / (tb - ta)
                   for (ta, qa), (tb, qb) in itertools.pairwise(pairs)
                   if ta <= 0.5 <= tb)
    else:
        med = qs[len(qs) // 2]
    lookup = {round(t, 9): q for t, q in pairs}
    for t, q in pairs:
        hi = lookup.get(round(1.0 - t, 9))
        if t < 0.5 and hi is not None and hi > q:
            return med, (hi - q) / (2.0 * _N.inv_cdf(1.0 - t))
    if len(pairs) >= 2 and qs[-1] > qs[0]:
        return med, (qs[-1] - qs[0]) / (_N.inv_cdf(taus[-1]) - _N.inv_cdf(taus[0]))
    return med, None


def central_intervals(pairs: Sequence[tuple[float, float]]) -> list[tuple[float, float, float]]:
    """(nominal coverage, lo, hi) for every symmetric pair (t, 1-t), t < 0.5."""
    lookup = {round(t, 9): q for t, q in pairs}
    out = []
    for t, q in pairs:
        hi = lookup.get(round(1.0 - t, 9))
        if t < 0.5 and hi is not None:
            out.append((round(1.0 - 2.0 * t, 6), q, hi))
    return out


# =============================================================================== summaries
def reliability_table(ps: Sequence[float], ys: Sequence[float],
                      bins: int = RELIABILITY_BINS) -> dict[str, Any]:
    """Reliability diagram plus the Murphy decomposition BS = REL - RES + UNC.

    REL is the calibration term (0 = perfectly reliable); RES is what the forecasts sort out of
    the base rate; UNC is the base rate's own variance. A biased forecaster shows in REL and in
    the bins, not merely in a worse Brier that could equally be bad resolution.
    """
    n = len(ps)
    base = sum(ys) / n
    rows = []
    rel = res = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, p in enumerate(ps) if (lo <= p < hi) or (b == bins - 1 and p == 1.0)]
        if not idx:
            continue
        mp = sum(ps[i] for i in idx) / len(idx)
        fy = sum(ys[i] for i in idx) / len(idx)
        rel += len(idx) * (mp - fy) ** 2
        res += len(idx) * (fy - base) ** 2
        rows.append({"bin": [round(lo, 3), round(hi, 3)], "n": len(idx),
                     "mean_forecast": _rnd(mp), "observed_freq": _rnd(fy)})
    return {"bins": rows, "reliability": _rnd(rel / n), "resolution": _rnd(res / n),
            "uncertainty": _rnd(base * (1.0 - base))}


def pit_summary(pits: Sequence[float], bins: int = PIT_BINS) -> dict[str, Any]:
    """PIT histogram, mean (0.5 if unbiased), variance (1/12 if correctly dispersed: lower =
    overdispersed / too wide, higher = underdispersed / overconfident) and the KS distance."""
    n = len(pits)
    hist = [0] * bins
    for u in pits:
        hist[min(bins - 1, max(0, int(u * bins)))] += 1
    srt = sorted(pits)
    ks = max(max(abs((i + 1) / n - u), abs(i / n - u)) for i, u in enumerate(srt))
    m = sum(pits) / n
    var = sum((u - m) ** 2 for u in pits) / n
    return {"n": n, "histogram": hist, "mean": _rnd(m), "variance": _rnd(var),
            "uniform_variance": round(1.0 / 12.0, 6), "ks_distance": _rnd(ks),
            "reading": ("overconfident (PIT variance above 1/12: outcomes land in the tails "
                        "too often)" if var > 1.0 / 12.0 * 1.2 else
                        "underconfident (PIT variance below 1/12: intervals too wide)"
                        if var < 1.0 / 12.0 * 0.8 else "dispersion consistent with uniform")}


def summarise_probability(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not items:
        return _unmeasured("no resolved PROBABILITY belief in this cell")
    ps = [float(i["p"]) for i in items]
    ys = [float(i["y"]) for i in items]
    n = len(ps)
    mp = sum(ps) / n
    return {"status": "MEASURED", "n": n, "rule": "brier + log_loss",
            "brier": _rnd(sum(brier(p, y) for p, y in zip(ps, ys, strict=True)) / n),
            "log_loss": _rnd(sum(log_loss(p, y) for p, y in zip(ps, ys, strict=True)) / n),
            "mean_forecast": _rnd(mp), "base_rate": _rnd(sum(ys) / n),
            "calibration_in_the_large": _rnd(mp - sum(ys) / n),
            "reliability": reliability_table(ps, ys),
            "sharpness": {"mean_distance_from_half": _rnd(sum(abs(p - 0.5) for p in ps) / n * 2),
                          "forecast_variance": _rnd(sum((p - mp) ** 2 for p in ps) / n)}}


def summarise_magnitude(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not items:
        return _unmeasured("no resolved MAGNITUDE belief in this cell")
    err = [float(i["y"]) - float(i["x"]) for i in items]
    signed = [(float(i["x"]) > 0) == (float(i["y"]) > 0) for i in items
              if float(i["x"]) != 0 and float(i["y"]) != 0]
    n = len(err)
    return {"status": "MEASURED", "n": n, "rule": "absolute_error",
            "mae": _rnd(sum(abs(e) for e in err) / n),
            "signed_error": _rnd(sum(err) / n),
            "rmse": _rnd(math.sqrt(sum(e * e for e in err) / n)),
            "sign_hit_rate": _rnd(sum(signed) / len(signed)) if signed else None,
            "n_signed": len(signed)}


def summarise_distribution(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not items:
        return _unmeasured("no resolved DISTRIBUTION belief in this cell")
    n = len(items)
    cov: dict[float, list[int]] = defaultdict(list)
    width: dict[float, list[float]] = defaultdict(list)
    for i in items:
        for nom, lo, hi in central_intervals(i["pairs"]):
            cov[nom].append(1 if lo <= float(i["y"]) <= hi else 0)
            width[nom].append(hi - lo)
    meds = [median_sd_of(i["pairs"])[0] for i in items]
    return {"status": "MEASURED", "n": n, "rule": "crps (+ coverage, pit)",
            "crps": _rnd(sum(crps_quantiles(i["pairs"], float(i["y"])) for i in items) / n),
            "median_abs_error": _rnd(sum(abs(float(i["y"]) - m)
                                         for i, m in zip(items, meds, strict=True)) / n),
            "signed_error_vs_median": _rnd(sum(float(i["y"]) - m
                                               for i, m in zip(items, meds, strict=True)) / n),
            "coverage": {f"{nom:.2f}": {"nominal": nom, "n": len(h),
                                        "observed": _rnd(sum(h) / len(h)),
                                        "gap": _rnd(sum(h) / len(h) - nom)}
                         for nom, h in sorted(cov.items())},
            "pit": pit_summary([pit_quantiles(i["pairs"], float(i["y"])) for i in items]),
            "sharpness_mean_width": {f"{nom:.2f}": _rnd(sum(w) / len(w))
                                     for nom, w in sorted(width.items())},
            "quantiles_rearranged": sum(1 for i in items if i.get("rearranged"))}


SUMMARISERS = {"PROBABILITY": summarise_probability, "MAGNITUDE": summarise_magnitude,
               "DISTRIBUTION": summarise_distribution}


def breakdown(items: Sequence[Mapping[str, Any]], kind: str) -> dict[str, Any]:
    """Overall plus by regime, source (model_id), event class (subject prefix), horizon bucket."""
    fn = SUMMARISERS[kind]
    out: dict[str, Any] = {"overall": fn(items)}
    for dim in ("regime", "source", "event_class", "bucket"):
        groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for i in items:
            groups[str(i.get(dim) or "unlabelled")].append(i)
        out[f"by_{dim}"] = {k: fn(v) for k, v in sorted(groups.items())}
    return out


# =============================================================================== regime join
def regime_label(regime: Any) -> str | None:
    """A regime probability dict -> its modal label; a string passes through."""
    if isinstance(regime, str) and regime:
        return regime
    if isinstance(regime, Mapping):
        best = [(float(v), str(k)) for k, v in regime.items() if _num(v) is not None]
        if best:
            return max(best)[1]
    return None


class RegimeTimeline:
    """The allocator's believed regime at any instant: the modal label of the last pass at or
    before it. A belief formed at t is labelled with the regime the DESK believed at t -- not the
    one later known to have prevailed, which would be lookahead in the breakdown itself."""

    def __init__(self, log_rows: Iterable[Mapping[str, Any]]) -> None:
        pts = []
        for r in log_rows:
            t, lab = _ts(r.get("t")), regime_label(r.get("regime"))
            if t is not None and lab:
                pts.append((t, lab))
        pts.sort()
        self.pts = pts

    def at(self, when: datetime | None) -> str | None:
        if when is None or not self.pts:
            return None
        lab = None
        for t, label in self.pts:
            if t > when:
                break
            lab = label
        return lab


def event_class(subject: str) -> str:
    """The subject's prefix: `XAUUSD.asia/up` -> `XAUUSD`, `macro:cpi` -> `macro`."""
    return re.split(r"[/:|.]", str(subject or ""), maxsplit=1)[0] or "unlabelled"


# =============================================================================== the account
@dataclass
class AccountPath:
    """The desk's realised account, from the deal ledger and (if present) daily equity closes."""

    trades: list[tuple[float, float]] = field(default_factory=list)   # (epoch, trade P&L)
    flows: list[tuple[float, float]] = field(default_factory=list)    # (epoch, deposit/wd)
    start: float | None = None
    end: float | None = None
    equity_closes: dict[str, float] = field(default_factory=dict)
    account: Any = None

    def balance_at(self, epoch: float) -> float:
        return sum(a for e, a in self.trades if e <= epoch) + \
            sum(a for e, a in self.flows if e <= epoch)

    def closed_growth(self, t0: float, t1: float) -> float | None:
        if self.start is None or self.end is None or t0 < self.start or t1 > self.end:
            return None
        b0 = self.balance_at(t0)
        pnl = sum(a for e, a in self.trades if t0 < e <= t1)
        if b0 <= 0 or b0 + pnl <= 0:
            return None
        return math.log((b0 + pnl) / b0)

    def equity_growth(self, day: str) -> float | None:
        """log(E_{day+1} - flows in between) / E_day), from the trigger's daily closes."""
        d0 = _ts(day + "T00:00:00+00:00")
        if d0 is None:
            return None
        d1 = (d0 + timedelta(days=1)).date().isoformat()
        e0, e1 = self.equity_closes.get(day), self.equity_closes.get(d1)
        if e0 is None or e1 is None or e0 <= 0:
            return None
        lo, hi = d0.timestamp() + 86400.0, d0.timestamp() + 2 * 86400.0
        flow = sum(a for e, a in self.flows if lo <= e < hi)
        return math.log((e1 - flow) / e0) if e1 - flow > 0 else None


def _find_key(doc: Any, key: str) -> Any:
    if isinstance(doc, Mapping):
        if key in doc:
            return doc[key]
        for v in doc.values():
            got = _find_key(v, key)
            if got is not None:
                return got
    elif isinstance(doc, list):
        for v in doc:
            got = _find_key(v, key)
            if got is not None:
                return got
    return None


def account_path(quotes: Mapping[str, Any] | None,
                 trigger_state: Mapping[str, Any] | None = None) -> AccountPath:
    ap = AccountPath()
    deals = (quotes or {}).get("deals")
    if isinstance(deals, list):
        for d in deals:
            if not isinstance(d, Mapping):
                continue
            ep = _num(d.get("epoch"))
            if ep is None:
                t = _ts(d.get("at"))
                ep = t.timestamp() if t else None
            if ep is None:
                continue
            amt = sum(_num(d.get(k)) or 0.0 for k in ("profit", "swap", "comm", "fee"))
            (ap.trades if d.get("type") in (0, 1) else ap.flows).append((ep, amt))
        ap.trades.sort()
        ap.flows.sort()
        eps = [e for e, _ in ap.trades + ap.flows]
        if eps:
            ap.start = min(eps)
            asof = _ts((quotes or {}).get("at"))
            ap.end = asof.timestamp() if asof else max(eps)
    ap.account = (quotes or {}).get("account")
    closes = _find_key(trigger_state, "equity_closes") if trigger_state else None
    if isinstance(closes, Mapping):
        ap.equity_closes = {str(k)[:10]: float(v) for k, v in closes.items()
                            if _num(v) is not None and float(v) > 0}
    return ap


# =============================================================================== (a) allocator
def _alloc_sd(m: float, c: float, alpha: float) -> float | None:
    """sd of the Gaussian whose CVaR_alpha is c and mean m; None if no spread was stated."""
    if not (0.0 < alpha < 1.0) or not m > c:
        return None
    return (m - c) * alpha / _N.pdf(_N.inv_cdf(alpha))


def score_allocator(log_rows: Sequence[Mapping[str, Any]], ap: AccountPath,
                    now: datetime) -> dict[str, Any]:
    """The allocator's daily forecasts against the realised account, last pass of each UTC day."""
    passes = [r for r in log_rows if _ts(r.get("t")) is not None
              and _num(r.get("expected_log_per_day")) is not None]
    if not passes:
        return _unmeasured("pf_forecast_log.jsonl absent or holds no readable pass on this host",
                           passes=0)
    by_day: dict[str, Mapping[str, Any]] = {}
    for r in sorted(passes, key=lambda r: _ts(r["t"]) or now):
        by_day[(_ts(r["t"]) or now).date().isoformat()] = r
    counts = {"passes": len(passes), "days": len(by_day), "pending": 0,
              "outside_ledger": 0, "no_spread": 0}
    use_equity = len(ap.equity_closes) >= 2
    basis = ("EQUITY: daily equity closes (incl. floating) from allocator_trigger_state.json, "
             "deposits/withdrawals removed via deal-ledger balance rows" if use_equity else
             "CLOSED-BALANCE: cost_truth_quotes.json deal ledger, trade P&L over (t, t+1d] / "
             "balance at t -- realised only, open risk lands in the window it closes in")
    scored: list[dict[str, Any]] = []
    for day, r in sorted(by_day.items()):
        t = _ts(r["t"])
        assert t is not None
        if t + timedelta(seconds=ALLOC_HORIZON_S) > now:
            counts["pending"] += 1
            continue
        y = (ap.equity_growth(day) if use_equity else
             ap.closed_growth(t.timestamp(), t.timestamp() + ALLOC_HORIZON_S))
        if y is None:
            counts["outside_ledger"] += 1
            continue
        m = float(r["expected_log_per_day"])
        c = _num(r.get("expected_cvar_per_day"))
        alpha = _num(r.get("cvar_alpha")) or ALLOC_CVAR_ALPHA
        sd = _alloc_sd(m, c, alpha) if c is not None else None
        if sd is None:
            counts["no_spread"] += 1
        scored.append({"day": day, "t": r["t"], "decision_id": r.get("decision_id"),
                       "m": m, "c": c, "alpha": alpha, "sd": sd, "y": y,
                       "regime": regime_label(r.get("regime")) or "unlabelled",
                       "mode": r.get("mode"), "binding": r.get("binding"),
                       "heat": _num(r.get("total_heat"))})
    if not scored:
        return _unmeasured("no allocator forecast day has a realised outcome on this host "
                           f"(ledger covers {_cov(ap)})", basis=basis, **counts)
    doc = {"status": "MEASURED", "basis": basis, "horizon_s": ALLOC_HORIZON_S,
           "cvar_alpha_assumed": ALLOC_CVAR_ALPHA, "ledger_coverage": _cov(ap),
           "account": ap.account, **counts, "overall": _alloc_summary(scored)}
    for dim in ("regime", "mode", "binding"):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for s in scored:
            groups[str(s.get(dim) or "unlabelled")].append(s)
        doc[f"by_{dim}"] = {k: _alloc_summary(v) for k, v in sorted(groups.items())}
    doc["prob_annual_loss"] = _unmeasured(
        "a 252-trading-day claim; the ledgers hold "
        f"{len(scored)} scored day(s), not one non-overlapping year", scored_days=len(scored))
    doc["scored_days_tail"] = [{k: (_rnd(v, 8) if isinstance(v, float) else v)
                                for k, v in s.items()} for s in scored[-60:]]
    return doc


def _cov(ap: AccountPath) -> str:
    if ap.start is None or ap.end is None:
        return "no deal ledger"
    return (f"{_iso(datetime.fromtimestamp(ap.start, UTC))} .. "
            f"{_iso(datetime.fromtimestamp(ap.end, UTC))}")


def _alloc_summary(scored: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(scored)
    err = [s["y"] - s["m"] for s in scored]
    signed = [(s["m"] > 0) == (s["y"] > 0) for s in scored if s["m"] != 0 and s["y"] != 0]
    out: dict[str, Any] = {
        "n": n, "mean_forecast": _rnd(sum(s["m"] for s in scored) / n, 8),
        "mean_realised": _rnd(sum(s["y"] for s in scored) / n, 8),
        "signed_error": _rnd(sum(err) / n, 8),
        "mae": _rnd(sum(abs(e) for e in err) / n, 8),
        "rmse": _rnd(math.sqrt(sum(e * e for e in err) / n), 8),
        "realised_sd": _rnd(_std([s["y"] for s in scored]), 8),
        "sign_hit_rate": _rnd(sum(signed) / len(signed)) if signed else None,
        "n_signed": len(signed)}
    sp = [s for s in scored if s["sd"]]
    if not sp:
        out["distribution"] = _unmeasured(
            "no scored day stated a spread (mean <= CVaR, or CVaR missing: an empty book)")
        return out
    pits = [_N.cdf((s["y"] - s["m"]) / s["sd"]) for s in sp]
    var_hits, breach_y, breach_c = [], [], []
    p_loss, y_loss = [], []
    for s in sp:
        var_a = s["m"] + _N.inv_cdf(s["alpha"]) * s["sd"]
        hit = s["y"] < var_a
        var_hits.append(hit)
        if hit:
            breach_y.append(s["y"])
            breach_c.append(s["c"])
        p_loss.append(_N.cdf(-s["m"] / s["sd"]))
        y_loss.append(1.0 if s["y"] < 0 else 0.0)
    alpha = sum(s["alpha"] for s in sp) / len(sp)
    k, nn = sum(var_hits), len(var_hits)
    z = (k - nn * alpha) / math.sqrt(nn * alpha * (1 - alpha)) if nn else None
    out["distribution"] = {
        "status": "MEASURED", "n": nn, "shape": "Gaussian read of (mean, CVaR_alpha)",
        "pit": pit_summary(pits),
        "tail_coverage": {
            "nominal_breach_rate": _rnd(alpha), "observed_breach_rate": _rnd(k / nn),
            "breaches": k, "z_vs_nominal": _rnd(z, 3),
            "reading": ("tail UNDER-represented: realised days fall below the predicted VaR "
                        "more often than alpha" if z is not None and z > 2 else
                        "tail OVER-stated: fewer breaches than alpha" if z is not None and z < -2
                        else "breach rate consistent with alpha")},
        "tail_severity": ({"mean_realised_in_breach": _rnd(sum(breach_y) / len(breach_y), 8),
                           "mean_predicted_cvar": _rnd(sum(breach_c) / len(breach_c), 8),
                           "shortfall": _rnd(sum(breach_y) / len(breach_y)
                                             - sum(breach_c) / len(breach_c), 8)}
                          if breach_y else _unmeasured("no breach of the predicted VaR yet")),
        "crps": _rnd(sum(crps_gaussian(s["m"], s["sd"], s["y"]) for s in sp) / nn, 8),
        "sharpness_mean_sd": _rnd(sum(s["sd"] for s in sp) / nn, 8),
        "p_day_loss": summarise_probability([{"p": p, "y": y}
                                              for p, y in zip(p_loss, y_loss, strict=True)])}
    return out


# =============================================================================== (b) register
def _window_end(row: Mapping[str, Any]) -> datetime | None:
    start = _ts(row.get("outcome_start")) or _ts(row.get("at"))
    h = _num(row.get("horizon_s"))
    if start is None or h is None:
        return None
    return start + timedelta(seconds=h)


class OutcomeBook:
    """Realised values by subject, from the outcome ledger, matched to a window end."""

    def __init__(self, rows: Iterable[Mapping[str, Any]]) -> None:
        self.by_subject: dict[str, list[tuple[datetime, float, int]]] = defaultdict(list)
        for i, r in enumerate(rows):
            t, v = _ts(r.get("at")), _num(r.get("value"))
            if t is not None and v is not None and r.get("subject"):
                self.by_subject[str(r["subject"])].append((t, v, i))
        for v in self.by_subject.values():
            v.sort()

    def match(self, subject: str, end: datetime, horizon_s: float,
              now: datetime) -> tuple[float, str, datetime] | None:
        tol = max(OUTCOME_TOL_FLOOR_S, OUTCOME_TOL_FRAC * horizon_s)
        best = None
        for t, v, i in self.by_subject.get(subject, ()):
            if t > now:
                continue
            d = abs((t - end).total_seconds())
            if d <= tol and (best is None or d < best[0]):
                best = (d, v, f"L{i}", t)
        return None if best is None else (best[1], best[2], best[3])


def resolve(row: Mapping[str, Any], book: OutcomeBook,
            now: datetime) -> tuple[str, float | None, str | None]:
    """(status, outcome, event_id). status in PENDING / UNRESOLVED / RESOLVED / UNREADABLE."""
    end = _window_end(row)
    if end is None:
        return "UNREADABLE", None, None
    if end > now:
        return "PENDING", None, None
    inline = _num(row.get("outcome"))
    if inline is not None:
        at = _ts(row.get("outcome_at")) or end
        if at > now:
            return "PENDING", None, None
        return "RESOLVED", inline, f"I|{row.get('subject')}|{_iso(end)[:16]}|{inline:.12g}"
    got = book.match(str(row.get("subject")), end, float(row["horizon_s"]), now)
    if got is None:
        return "UNRESOLVED", None, None
    return "RESOLVED", got[0], got[1]


def _row_defects(row: Mapping[str, Any]) -> list[str]:
    """Defer to the contract's quantile validator when it exists (owned elsewhere)."""
    fn = getattr(_fc, "quantile_defects", None)
    if row.get("kind") == "DISTRIBUTION" and callable(fn):
        try:
            return list(fn(row.get("value")) or [])
        except Exception as exc:   # a validator that throws is itself a defect, never a pass
            return [f"quantile validator raised {type(exc).__name__}: {exc}"]
    return []


def _scored_item(row: Mapping[str, Any], y: float, regimes: RegimeTimeline,
                 event_id: str) -> dict[str, Any] | str:
    kind = row.get("kind")
    lab = regime_label(row.get("regime")) or regimes.at(_ts(row.get("at")))
    base = {"source": str(row.get("model_id") or "unattributed"),
            "event_class": str(row.get("event_class") or event_class(str(row.get("subject")))),
            "regime": lab or "unlabelled", "bucket": row.get("bucket")
            or _fc.bucket_of(float(row["horizon_s"])), "y": y, "event_id": event_id,
            "subject": row.get("subject")}
    if kind == "PROBABILITY":
        p = _num(row.get("value"))
        if p is None or y not in (0.0, 1.0):
            return "PROBABILITY outcome is not 0/1 or the value is unreadable"
        return base | {"p": p}
    if kind == "MAGNITUDE":
        x = _num(row.get("value"))
        return "MAGNITUDE value unreadable" if x is None else base | {"x": x}
    if kind == "DISTRIBUTION":
        bad = _row_defects(row)
        if bad:
            return "; ".join(bad)
        q = quantiles_of(row.get("value"))
        if q is None:
            return "DISTRIBUTION quantiles unreadable"
        return base | {"pairs": q[0], "rearranged": q[1]}
    return f"kind {kind!r} has no scoring rule"


def score_register(rows: Sequence[Mapping[str, Any]], book: OutcomeBook,
                   regimes: RegimeTimeline, now: datetime) -> tuple[dict[str, Any],
                                                                    list[dict[str, Any]]]:
    """Every knowable register row, scored by its kind's rule and broken out. Also returns the
    resolved rows (with outcome and event id) for the pool's history."""
    counts = {"rows": len(rows), "refused": 0, "pending": 0, "unresolved": 0,
              "unreadable": 0, "unscoreable": 0, "scored": 0}
    items: dict[str, list[dict[str, Any]]] = defaultdict(list)
    resolved: list[dict[str, Any]] = []
    unscoreable: dict[str, int] = defaultdict(int)
    for r in rows:
        if r.get("status") == "REFUSED":
            counts["refused"] += 1
            continue
        status, y, eid = resolve(r, book, now)
        if status != "RESOLVED":
            counts[status.lower()] += 1
            continue
        assert y is not None and eid is not None
        it = _scored_item(r, y, regimes, eid)
        if isinstance(it, str):
            counts["unscoreable"] += 1
            unscoreable[it[:80]] += 1
            continue
        counts["scored"] += 1
        items[str(r["kind"])].append(it)
        resolved.append(dict(r) | {"_y": y, "_event": eid})
    if not rows:
        doc = _unmeasured("forecast_register.jsonl absent or empty on this host -- no model has "
                          "published a belief here, so there is nothing to score", **counts)
    elif not counts["scored"]:
        doc = _unmeasured("no register row is both due and resolved", **counts)
    else:
        doc = {"status": "MEASURED", **counts}
    doc["unscoreable_reasons"] = dict(unscoreable)
    doc["by_kind"] = {k: breakdown(items.get(k, []), k) for k in _fc.RULES}
    return doc, resolved


# =============================================================================== (c) the pool
def _kind_class(kind: Any) -> str:
    return "probability" if kind == "PROBABILITY" else "real"


def _inputs_as_of(row: Mapping[str, Any]) -> str:
    stamps = [str(p[1]) for p in row.get("feature_available_at") or ()
              if isinstance(p, (list, tuple)) and len(p) == 2 and _ts(p[1]) is not None]
    return max(stamps, key=lambda s: _ts(s) or datetime.min.replace(tzinfo=UTC)) \
        if stamps else str(row.get("at"))


def _point(row: Mapping[str, Any]) -> tuple[float | None, float | None]:
    """(mean, stated variance) of a belief, as the pool reads it."""
    kind = row.get("kind")
    if kind == "DISTRIBUTION":
        q = quantiles_of(row.get("value"))
        if q is None:
            return None, None
        med, sd = median_sd_of(q[0])
        return med, (sd * sd if sd else None)
    v = _num(row.get("value"))
    stated = _num(row.get("variance"))
    if stated is None and _num(row.get("sd")) is not None:
        stated = float(row["sd"]) ** 2
    return v, (stated if stated and stated > 0 else None)


@dataclass
class History:
    """Walk-forward error history: per model, (resolved_at, error) for every resolved belief.
    Only entries resolved STRICTLY BEFORE a cut are ever read, so nothing measured here can see
    the outcome it is used to pool for."""

    errors: dict[str, list[tuple[datetime, str, float, str]]] = field(
        default_factory=lambda: defaultdict(list))

    @classmethod
    def build(cls, resolved: Sequence[Mapping[str, Any]]) -> History:
        h = cls()
        for r in resolved:
            mean, _ = _point(r)
            end = _window_end(r)
            if mean is None or end is None:
                continue
            h.errors[str(r.get("model_id"))].append(
                (end, str(r["_event"]), float(r["_y"]) - mean, _kind_class(r.get("kind"))))
        for v in h.errors.values():
            v.sort()
        return h

    def mse(self, model: str, before: datetime, kc: str) -> tuple[float | None, int]:
        e = [x for t, _ev, x, k in self.errors.get(model, ()) if t < before and k == kc]
        return (sum(x * x for x in e) / len(e), len(e)) if len(e) >= MIN_VAR_HISTORY \
            else (None, len(e))

    def rho(self, a: str, b: str, before: datetime) -> tuple[float | None, int]:
        ea = {ev: x for t, ev, x, _k in self.errors.get(a, ()) if t < before}
        eb = {ev: x for t, ev, x, _k in self.errors.get(b, ()) if t < before}
        common = sorted(set(ea) & set(eb))
        if len(common) < MIN_RHO_PAIRS:
            return None, len(common)
        xa = [ea[k] for k in common]
        xb = [eb[k] for k in common]
        ma, mb = sum(xa) / len(xa), sum(xb) / len(xb)
        sab = sum((p - ma) * (q - mb) for p, q in zip(xa, xb, strict=True))
        saa = sum((p - ma) ** 2 for p in xa)
        sbb = sum((q - mb) ** 2 for q in xb)
        if saa <= 0 or sbb <= 0:
            # identical constant errors are one source, not an undefined correlation
            return (1.0 if xa == xb else 0.0), len(common)
        # A NEGATIVE measured correlation is clipped to 0: it would let two sources pool to more
        # precision than independence allows, and on a short history that is noise, not hedge.
        return min(1.0, max(0.0, sab / math.sqrt(saa * sbb))), len(common)


def to_estimate(row: Mapping[str, Any], history: History,
                cut: datetime) -> tuple[Any | None, str, dict[str, Any]]:
    """Register row -> model_roles.Estimate, or (None, reason). Also returns lineage."""
    mean, var = _point(row)
    kc = _kind_class(row.get("kind"))
    var_basis = "stated"
    if mean is None:
        return None, "value unreadable", {}
    if var is None:
        mse, n = history.mse(str(row.get("model_id")), cut, kc)
        if mse is not None and mse > 0:
            var, var_basis = mse, f"walk-forward MSE over {n} prior resolved belief(s)"
        elif kc == "probability":
            var, var_basis = UNTRACKED_PROB_VAR, "untracked: Bernoulli maximum 0.25"
        else:
            return None, (f"states no spread and has {n} < {MIN_VAR_HISTORY} prior resolved "
                          "beliefs to measure one -- UNMEASURED, not pooled at a guessed "
                          "precision"), {}
    est = _roles.Estimate(model_id=str(row.get("model_id")), family=str(row.get("family") or ""),
                          subject=str(row.get("subject")), horizon_s=float(row["horizon_s"]),
                          role=str(row.get("role") or ""), mean=float(mean),
                          variance=float(var), inputs_as_of=_inputs_as_of(row),
                          confidence=float(_num(row.get("confidence")) or 1.0))
    lineage = {"model_id": est.model_id, "family": est.family, "role": est.role,
               "at": row.get("at"), "training_cutoff": row.get("training_cutoff"),
               "model_version": row.get("model_version") or row.get("version"),
               "inputs_as_of": est.inputs_as_of, "fingerprint": est.fingerprint(),
               "mean": _rnd(est.mean, 8), "variance": _rnd(est.variance, 10),
               "variance_basis": var_basis}
    return est, "", lineage


def pool_beliefs(rows: Sequence[Mapping[str, Any]], history: History | None = None,
                 cut: datetime | None = None, *,
                 drop: str | None = None) -> dict[str, Any]:
    """THE CALLER `model_roles.combine` NEVER HAD. All beliefs for ONE subject at ONE horizon in
    ONE role -> one pooled forecast with lineage.

    1. Each row becomes an Estimate (stated spread, else walk-forward MSE, else excluded).
    2. Estimates are folded through `model_roles.update` in publication order: a fingerprint
       already consumed is a no-op (a re-published belief is not new evidence) and a model's new
       estimate REPLACES its old one (one model, one vote). Feeding the same rows twice, or a
       register with duplicated lines, yields the identical pool -- that is the idempotence.
    3. `combine` pools them: precision weights, a'Sa under the source correlation, Cochran's-Q
       disagreement inflation. The correlation passed is MEASURED on errors resolved before
       `cut` where MIN_RHO_PAIRS exist, else combine's declared table applies.
    `drop` leaves one model out (the leave-one-source-out arm of incremental value).
    """
    history = history or History()
    rows = sorted((r for r in rows if str(r.get("model_id")) != drop),
                  key=lambda r: (_ts(r.get("at")) or datetime.min.replace(tzinfo=UTC),
                                 str(r.get("model_id"))))
    if not rows:
        return {"status": UNMEASURED, "why": "no belief to pool", "mean": None}
    subjects = {str(r.get("subject")) for r in rows}
    horizons = {float(r.get("horizon_s") or 0) for r in rows}
    roles = {str(r.get("role") or "") for r in rows}
    if len(subjects) > 1 or len(horizons) > 1 or len(roles) > 1:
        raise ValueError(f"pool_beliefs pools ONE subject/horizon/role; got {sorted(subjects)} "
                         f"{sorted(horizons)} {sorted(roles)}")
    cut = cut or max((_ts(r.get("at")) for r in rows if _ts(r.get("at"))),
                     default=datetime.now(UTC))
    state = _roles.BeliefState()
    excluded: list[dict[str, str]] = []
    lineage: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for r in rows:
        est, why, lin = to_estimate(r, history, cut)
        if est is None:
            excluded.append({"model_id": str(r.get("model_id")), "why": why})
            continue
        try:
            state, applied = _roles.update(state, est)
        except _roles.RoleViolation as exc:
            excluded.append({"model_id": est.model_id, "why": str(exc)})
            continue
        if applied:
            lineage[est.model_id] = lin
        else:
            duplicates += 1
    role = next(iter(roles))
    ests = state.estimates(next(iter(subjects)), next(iter(horizons)), role)
    measured: dict[frozenset[str], float] = {}
    rho_basis: dict[str, Any] = {}
    for i, a in enumerate(ests):
        for b in ests[i + 1:]:
            if a.model_id == b.model_id:
                continue
            r_ab, n_ab = history.rho(a.model_id, b.model_id, cut)
            key = "|".join(sorted((a.model_id, b.model_id)))
            if r_ab is not None:
                measured[frozenset({a.model_id, b.model_id})] = r_ab
                rho_basis[key] = {"rho": _rnd(r_ab, 4), "n": n_ab, "basis": "MEASURED errors"}
            else:
                rho_basis[key] = {"rho": _rnd(_roles.source_rho(a, b), 4), "n": n_ab,
                                  "basis": f"DECLARED (< {MIN_RHO_PAIRS} co-resolved)"}
    try:
        pooled = _roles.combine(ests, role or "", measured_rho=measured)
    except ValueError as exc:
        return {"status": UNMEASURED, "why": str(exc), "mean": None}
    excluded += [{"model_id": m, "why": w} for m, w in pooled.excluded]
    used = [e for e in ests if e.model_id not in {m for m, _ in pooled.excluded}]
    sw = sum(1.0 / e.variance for e in used) or 1.0
    for e in used:
        lineage[e.model_id]["weight"] = _rnd((1.0 / e.variance) / sw, 6)
    kc = _kind_class(rows[-1].get("kind"))
    mean = pooled.mean
    if mean is not None and kc == "probability":
        mean = min(1.0, max(0.0, mean))
    lin_list = [lineage[e.model_id] for e in used]
    fp = hashlib.sha256(json.dumps([*sorted(x["fingerprint"] for x in lin_list), role],
                                   separators=(",", ":")).encode()).hexdigest()[:32]
    return {"status": "MEASURED" if mean is not None else UNMEASURED,
            "subject": pooled.subject, "horizon_s": pooled.horizon_s, "role": role,
            "kind_class": kc, "mean": mean, "variance": pooled.variance,
            "sd": math.sqrt(pooled.variance) if pooled.variance else None,
            "confidence": pooled.confidence, "n_sources": pooled.n_sources,
            "n_effective": pooled.n_effective, "disagreement_q": pooled.disagreement_q,
            "inflation": pooled.inflation, "why": pooled.why, "lineage": lin_list,
            "excluded": excluded, "duplicates_ignored": duplicates, "source_rho": rho_basis,
            "pool_fingerprint": fp}


def pool_score(p: Mapping[str, Any], y: float) -> float | None:
    """Lower is better: Brier for a pooled probability, Gaussian CRPS for a pooled real."""
    if p.get("mean") is None:
        return None
    if p.get("kind_class") == "probability":
        return brier(float(p["mean"]), y)
    return crps_gaussian(float(p["mean"]), float(p.get("sd") or 0.0), y)


def incremental_value(resolved: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Leave-one-source-out on every resolved event with >= 2 sources, walk-forward."""
    history = History.build(resolved)
    events: dict[tuple[str, float, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for r in resolved:
        events[(str(r["_event"]), float(r["horizon_s"]), str(r.get("role") or ""),
                str(r.get("subject")))].append(r)
    per_model: dict[str, list[float]] = defaultdict(list)
    sole: dict[str, int] = defaultdict(int)
    pool_scores: list[float] = []
    mean_source_scores: list[float] = []
    n_events = 0
    for (_eid, _h, _role, _subj), rows in sorted(
            events.items(), key=lambda kv: min(_ts(r.get("at")) or datetime.max.replace(
                tzinfo=UTC) for r in kv[1])):
        cut = min(_ts(r.get("at")) or datetime.max.replace(tzinfo=UTC) for r in rows)
        y = float(rows[0]["_y"])
        full = pool_beliefs(rows, history, cut)
        s_full = pool_score(full, y)
        if s_full is None:
            continue
        n_events += 1
        pool_scores.append(s_full)
        used = [x["model_id"] for x in full["lineage"]]
        singles = []
        for m in used:
            solo = pool_beliefs([r for r in rows if str(r.get("model_id")) == m], history, cut)
            s = pool_score(solo, y)
            if s is not None:
                singles.append(s)
        if singles:
            mean_source_scores.append(sum(singles) / len(singles))
        if len(used) < 2:
            for m in used:
                sole[m] += 1
            continue
        for m in used:
            s_wo = pool_score(pool_beliefs(rows, history, cut, drop=m), y)
            if s_wo is not None:
                per_model[m].append(s_wo - s_full)
    if not n_events:
        return _unmeasured("no resolved event could be pooled", events=len(events))
    models = {}
    for m in sorted(set(per_model) | set(sole)):
        d = per_model.get(m, [])
        sd = _std(d)
        models[m] = ({"status": "MEASURED", "n_events": len(d), "mean_delta": _rnd(_mean(d), 8),
                      "se": _rnd(sd / math.sqrt(len(d)), 8) if sd is not None else None,
                      "sole_source_events": sole.get(m, 0),
                      "reading": ("ADDS value (pool worse without it)" if (_mean(d) or 0) > 0
                                  else "adds nothing or HURTS (pool as good or better "
                                  "without it)")}
                     if d else _unmeasured("never pooled beside another source",
                                           sole_source_events=sole.get(m, 0)))
    return {"status": "MEASURED", "events_scored": n_events,
            "pool_mean_score": _rnd(_mean(pool_scores), 8),
            "mean_single_source_score": _rnd(_mean(mean_source_scores), 8),
            "score_rule": "Brier (probability) / Gaussian CRPS (real); lower is better",
            "delta_definition": "score(pool without source) - score(pool with it); "
                                "positive = the source makes the pool better",
            "by_source": models}


def live_pools(rows: Sequence[Mapping[str, Any]], resolved: Sequence[Mapping[str, Any]],
               now: datetime) -> list[dict[str, Any]]:
    """Pool every subject/horizon/role whose beliefs are still OPEN (formed, window not closed)."""
    history = History.build(resolved)
    groups: dict[tuple[str, float, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("status") == "REFUSED":
            continue
        at, end = _ts(r.get("at")), _window_end(r)
        if at is None or end is None or at > now or end <= now:
            continue
        groups[(str(r.get("subject")), float(r["horizon_s"]), str(r.get("role") or ""),
                _kind_class(r.get("kind")))].append(r)
    out = []
    for (_s, _h, _role, _kc), g in sorted(groups.items()):
        p = pool_beliefs(g, history, now)
        p["published_at"] = _iso(now)
        out.append(p)
    return out


def append_pool_log(pools: Sequence[Mapping[str, Any]], path: Path | None = None) -> int:
    """Append pooled forecasts not yet logged (keyed by pool fingerprint). Idempotent: the same
    beliefs pooled again on the next hour add nothing, so the log never double-counts a pool."""
    path = path if path is not None else POOL_LOG
    seen = {r.get("pool_fingerprint") for r in read_jsonl(path)}
    new = [p for p in pools if p.get("mean") is not None and p["pool_fingerprint"] not in seen]
    if not new:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for p in new:
            fh.write(json.dumps(p, default=str) + "\n")
    return len(new)


# =============================================================================== the report
HOURLY_LEG_PROPOSAL = (
    'PROPOSED, NOT APPLIED -- in hourly_cycle.py beside `fcx = _costed("forecast_contract", '
    'forecast_contract)`: `fsc = _costed("forecast_scoring", lambda: _producer('
    '"forecast_scoring", "research/forecast_scoring.py"))`, recorded in the pass summary as '
    '"forecast_scoring": fsc, and FORECAST_SCORES.json registered in issue_board with a 3600 s '
    "freshness budget. It reads only; the only file it appends to is data/forecast_pool_log.jsonl."
)


def build_report(*, now: datetime | None = None, log_rows: Sequence[Mapping[str, Any]] | None
                 = None, register_rows: Sequence[Mapping[str, Any]] | None = None,
                 outcome_rows: Sequence[Mapping[str, Any]] | None = None,
                 quotes: Mapping[str, Any] | None = None,
                 trigger_state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Pure given its inputs; reads the desk's ledgers for any input left as None."""
    now = now or datetime.now(UTC)
    log_rows = read_jsonl(FORECAST_LOG) if log_rows is None else log_rows
    register_rows = read_jsonl(REGISTER) if register_rows is None else register_rows
    outcome_rows = read_jsonl(OUTCOMES) if outcome_rows is None else outcome_rows
    quotes = _read_json(QUOTES) if quotes is None else quotes
    trigger_state = _read_json(TRIGGER_STATE) if trigger_state is None else trigger_state
    ap = account_path(quotes if isinstance(quotes, Mapping) else None,
                      trigger_state if isinstance(trigger_state, Mapping) else None)
    regimes = RegimeTimeline(log_rows)
    alloc = score_allocator(log_rows, ap, now)
    reg, resolved = score_register(register_rows, OutcomeBook(outcome_rows), regimes, now)
    pools = live_pools(register_rows, resolved, now)
    inc = (incremental_value(resolved) if resolved else
           _unmeasured("no resolved register belief: incremental value needs scored history"))
    return {
        "measured_at": _iso(now),
        "frozen_rules": {
            "online_adaptation": "NONE -- scores are measured, never written back to any model, "
                                 "prior, weight or allocator input",
            "rules": dict(_fc.RULES) | {"ALLOCATOR": "Gaussian read of (mean, CVaR_alpha): "
                                        "PIT, VaR-breach coverage, tail severity, CRPS"},
            "pool": "stated spreads + walk-forward MSE and error correlation measured only on "
                    "outcomes resolved before each belief; recomputed every run",
            "absent": "UNMEASURED with counts, never zero"},
        "allocator_forecasts": alloc,
        "register": reg,
        "pool": {"incremental_value": inc, "live": pools,
                 "live_count": len(pools)},
        "dimensions": {
            "sign": "MAGNITUDE sign_hit_rate; allocator sign_hit_rate",
            "magnitude": "MAGNITUDE mae/signed_error; allocator mae/signed_error",
            "vol": "DISTRIBUTION coverage/PIT/sharpness; allocator PIT and tail coverage",
            "horizon": "every register cell broken out by_bucket",
            "source": "by_source; pool incremental_value.by_source",
            "regime": "by_regime (the desk's believed regime at the belief's `at`)",
            "event_class": "by_event_class (subject prefix)",
            "allocator_decision": alloc.get("status"),
            "transmission": _unmeasured("no register subject publishes a transmission claim "
                                        "(macro shock -> sleeve); scored the day one does"),
            "execution": _unmeasured("execution forecasts (slippage, fill) are not published "
                                     "to the register; execution_twin keeps its own ledger"),
        },
        "hourly_cycle_proposal": HOURLY_LEG_PROPOSAL,
        "allocator_log_proposal": "pf_allocator should log cvar_alpha and the horizon on each "
                                  "forecast line; until then this scorer assumes "
                                  f"{ALLOC_CVAR_ALPHA} and {ALLOC_HORIZON_S:.0f}s",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--now", help="score as of this ISO time (default: now)")
    ap.add_argument("--out", type=Path, default=REPORT)
    ap.add_argument("--no-pool-log", action="store_true",
                    help="do not append live pools to data/forecast_pool_log.jsonl")
    args = ap.parse_args(argv)
    now = _ts(args.now) if args.now else datetime.now(UTC)
    if now is None:
        ap.error(f"--now {args.now!r} is not an ISO timestamp")
    doc = build_report(now=now)
    if not args.no_pool_log:
        doc["pool"]["appended_to_log"] = append_pool_log(doc["pool"]["live"])
    atomic_write_text(args.out, json.dumps(doc, indent=1, default=str))
    a, r = doc["allocator_forecasts"], doc["register"]
    print(f"forecast scoring -> {args.out}")
    print(f"   allocator: {a.get('status')}  days={a.get('days')}  passes={a.get('passes')}  "
          f"basis={str(a.get('basis', ''))[:40]}")
    ov = a.get("overall") or {}
    if ov:
        dist = ov.get("distribution") or {}
        tc = dist.get("tail_coverage") or {}
        print(f"      signed error {ov.get('signed_error')}  sign hit {ov.get('sign_hit_rate')}  "
              f"VaR breaches {tc.get('observed_breach_rate')} vs {tc.get('nominal_breach_rate')}"
              f"  PIT var {(dist.get('pit') or {}).get('variance')}")
    print(f"   register: {r.get('status')}  rows={r.get('rows')} scored={r.get('scored')} "
          f"pending={r.get('pending')} unresolved={r.get('unresolved')}")
    print(f"   pool: {len(doc['pool']['live'])} live pooled forecast(s); incremental value "
          f"{doc['pool']['incremental_value'].get('status')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
