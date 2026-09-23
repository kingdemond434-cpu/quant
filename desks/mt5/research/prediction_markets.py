#!/usr/bin/env python3
"""PREDICTION-MARKET INTELLIGENCE -- a second opinion with a track record, priced in probability.

WHAT A PREDICTION MARKET IS TO THIS DESK, and what it is not. It is NOT a venue to trade: there is
no order here, no position, no capital and no execution path, and the fractional-Kelly numbers
below are a REFERENCE for comparison and carry `sizing_authority: false` in their own payload. It
is a FORECAST SOURCE with two properties nothing else on this desk has -- it states a probability
rather than a direction, and it RESOLVES, so every forecast it ever made can be scored against
what actually happened. That is the rarest thing in research: a source that can be wrong on the
record.

FIVE THINGS THIS MODULE MEASURES.

  CALIBRATION, FITTED PER CATEGORY. A market at 0.70 is not 70% likely in general; it is roughly
  70% likely in the categories where that market is calibrated and systematically off in the ones
  where it is not. So the recalibration `logit(p_true) = a + b logit(p_market)` is fitted PER
  CATEGORY, PER HORIZON, PER LIQUIDITY BUCKET, and the slope 1.18 the world publishes enters as
  ONE PRIOR on a ladder. b > 1 means the market is under-confident and its extremes should be
  pushed out; b < 1 means it is over-confident. The favourite/longshot asymmetry is measured
  separately on the two halves of the probability range, because a single slope averages away the
  bias it exists to find.

  RESOLUTION TRUTH. Every forecast is stored BEFORE the contract resolves, with its stamp. That
  ordering is the whole discipline: a forecast recorded after the fact is not a forecast. Brier,
  log loss and expected calibration error are then computed per source, per model and per seat --
  so a reasoning seat's probability contributions and the market's own can be ranked on the same
  scale as the desk's classical `BetaBinary` baseline.

  THE DISAGREEMENT VECTOR [p_market, p_news, p_macro, p_options, p_smart]. Agreement across five
  independent readings is a crowded consensus. DISAGREEMENT is where one reading holds information
  the others have not priced, and it is the feature series worth keeping.

  DEPENDENCY CONSTRAINTS. Related contracts must obey logic: a partition of exhaustive outcomes
  sums to one, and "A implies B" means p(A) <= p(B). When they do not, the deviation is the
  intelligence -- it says which leg the market has not thought about yet. THE DEVIATIONS ARE NEVER
  TRADED HERE. This desk cannot execute on those venues and would not: the value is the macro read
  the inconsistency reveals about the MT5 instruments it can trade.

  LEAD/LAG AGAINST THE DESK'S OWN INSTRUMENTS. Event odds against gold, the dollar, rates, oil and
  USDJPY, with a BLOCK-PERMUTATION NULL on the peak -- because a cross-correlation maximum over
  twenty-five lags is essentially always somewhere, and a peak without a null is a number that
  means nothing.

ACCESS IS A LABEL, NOT A DOOR (LAWS 5e, 2026-09-23). Every venue below carries the three
independent labels the desk's access policy defines (`access_label`, `credibility`,
`predictive_state`), and EVERY ONE OF THEM IS READ AND TESTED. A venue's published terms bear on
what the desk may REDISTRIBUTE, never on whether it may read the published odds; the old
`machine_use_allowed=false -> never scraped` reading, and the ACCESS_UNCLEAR quarantine beside it,
were discovery brakes the desk imposed on itself and both are deleted. What remains refused is the
hard boundary's five acts -- no credential is invented, no access control or paywall is bypassed.
`--no-fetch` (the default) runs the whole module off fixtures and touches no network at all.

    python desks/mt5/research/prediction_markets.py --no-fetch
    python desks/mt5/research/prediction_markets.py --budget-s 180
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.models.classical_baselines import BetaBinary, nelder_mead  # noqa: E402
from research import source_civilizations as SC  # noqa: E402

UNMEASURED = "UNMEASURED"
REPORT = DESK / "reports" / "PREDICTION_MARKETS.json"
FORECASTS = DESK / "data" / "prediction_forecasts.jsonl"

#: The MT5 legs an event probability is allowed to inform. Prediction-market data is a SENSOR for
#: these and never a universe of its own (mandate 2026-08-18).
MACRO_LEGS: tuple[str, ...] = ("XAUUSD", "USDX", "USDJPY", "XTIUSD", "US500", "NAS100")

#: The five independent readings of the same question. `p_market` is the contract, `p_news` the
#: claims store's own reading, `p_macro` a model over the macro state, `p_options` an implied
#: probability where a surface is readable, `p_smart` the smart-participant posterior.
DISAGREEMENT_LEGS: tuple[str, ...] = ("p_market", "p_news", "p_macro", "p_options", "p_smart")

MIN_FORECASTS = 40
#: Probability bins for the expected-calibration-error computation.
CAL_BINS: tuple[float, ...] = (0.0, 0.05, 0.15, 0.3, 0.5, 0.7, 0.85, 0.95, 1.0)
#: The published favourite/longshot correction enters as ONE RUNG of the desk's own ladder.
SLOPE_PRIOR = SC.PRIORS["calibration_slope"]
#: Momentum in a contract's own probability is a feature and it is BOUNDED: an unbounded momentum
#: term on a probability series is a trend-follower on a number that cannot trend past 1.
MOMENTUM_CAP = 0.10
#: Deviation above which a logical inconsistency is worth recording as intelligence.
DEPENDENCY_TRIGGER = 0.03


# --------------------------------------------------------------------------- the venue catalogue
@dataclass(frozen=True)
class Venue:
    """One prediction-market venue and the labels its provenance carries.

    `machine_use_allowed` is DERIVED from the access label rather than asserted separately, so the
    two can never drift apart. Since LAWS 5e (2026-09-23) that derivation is True for EVERY label
    that is not one of the five refused acts -- PUBLIC_WITH_TERMS and ACCESS_UNCLEAR included --
    because the field now answers "is this venue read at all", not "do the terms permit a
    crawler". What the terms withhold is `redistribute_allowed`.
    """

    name: str
    root: str
    api: str
    access_label: str
    credibility: str
    predictive_state: str
    categories: tuple[str, ...]
    note: str = ""

    @property
    def machine_use_allowed(self) -> bool:
        return bool(SC.ACCESS_BEHAVIOUR[self.access_label]["machine_use_allowed"])

    @property
    def redistribute_allowed(self) -> bool:
        """THE FIELD THAT REPLACED THE BRAKE: may the desk republish this venue's rows?"""
        return bool(SC.ACCESS_BEHAVIOUR[self.access_label]["redistribute_allowed"])

    @property
    def terms_note(self) -> str:
        """The routing label carried with every row read from this venue."""
        return f"{self.access_label}: {SC.ACCESS_BEHAVIOUR[self.access_label]['why']}"

    def as_row(self) -> dict[str, Any]:
        verdict = SC.classify_source({"source_id": f"venue:{self.name}", "url": self.root,
                                      "access_label": self.access_label,
                                      "credibility": self.credibility,
                                      "predictive_state": self.predictive_state})
        # The venue's own derived labels WIN over the generic ones `classify_source` returns for
        # a row that carries no licence text of its own.
        return {**verdict, "venue": self.name, "root": self.root, "api": self.api,
                "categories": list(self.categories), "note": self.note,
                "machine_use_allowed": self.machine_use_allowed,
                "redistribute_allowed": self.redistribute_allowed,
                "terms_note": self.terms_note}


#: THE DECLARED VENUES. Honest readings, not optimistic ones: a documented public REST endpoint
#: with published terms is PUBLIC_WITH_TERMS, and a venue whose terms this box has not read is
#: ACCESS_UNCLEAR. BOTH ARE READ AND TESTED (LAWS 5e, 2026-09-23) -- the label routes
#: REDISTRIBUTION and provenances the row; it has never decided whether the desk may look. An
#: unresolved access question is a note on the row, not a reason to leave the odds unread.
VENUES: tuple[Venue, ...] = (
    Venue("polymarket", "https://polymarket.com", "https://gamma-api.polymarket.com/markets",
          "PUBLIC_WITH_TERMS", "RELIABLE", "UNTESTED",
          ("macro", "rates", "elections", "geopolitics", "commodities"),
          note="a documented public API exists and is read; the published terms bound "
               "REDISTRIBUTION of the odds, not reading them (LAWS 5e)"),
    Venue("kalshi", "https://kalshi.com", "https://api.elections.kalshi.com/trade-api/v2/markets",
          "PUBLIC_WITH_TERMS", "AUTHORITATIVE", "UNTESTED",
          ("macro", "rates", "cpi", "payrolls", "fed", "weather"),
          note="a CFTC-regulated venue with a documented API and published terms; the regulated "
               "status is why credibility is AUTHORITATIVE and access is still WITH TERMS"),
    Venue("manifold", "https://manifold.markets", "https://api.manifold.markets/v0/markets",
          "PUBLIC_WITH_TERMS", "UNRELIABLE", "UNTESTED", ("macro", "tech", "meta"),
          note="play-money: the incentive to be right is weak, so the credibility label carries "
               "the discount and the rows are KEPT rather than deleted"),
    Venue("metaculus", "https://www.metaculus.com", "https://www.metaculus.com/api2/questions/",
          "PUBLIC_WITH_TERMS", "RELIABLE", "UNTESTED", ("macro", "geopolitics", "science"),
          note="a forecasting community with published resolution records rather than a market"),
    Venue("iem", "https://iemweb.biz.uiowa.edu", "", "ACCESS_UNCLEAR", "AUTHORITATIVE", "UNTESTED",
          ("elections",),
          note="an academic market with no documented machine endpoint read from this box: "
               "ACCESS_UNCLEAR is a PROVENANCE NOTE, not a quarantine -- the venue is mined and "
               "tested with the label attached; what is missing is an endpoint, not permission"),
)
BY_NAME: dict[str, Venue] = {v.name: v for v in VENUES}


def venue_terms() -> dict[str, Any]:
    """The access decision for every venue, as the report publishes it."""
    rows = [v.as_row() for v in VENUES]
    return {"venues": rows,
            "api_only": [r["venue"] for r in rows if r["route"] == "API_OR_MANUAL"],
            # ALWAYS EMPTY since 2026-09-23. The key stays so an old reader finds an explicit
            # empty list rather than a missing path.
            "quarantined": [r["venue"] for r in rows if r["quarantined"]],
            "refused": [r["venue"] for r in rows if r["refused"]],
            "mined": [r["venue"] for r in rows if r["machine_use_allowed"]],
            "redistributable": [r["venue"] for r in rows if r["redistribute_allowed"]],
            "scraped": [],
            "rule": "every venue is READ AND TESTED (LAWS 5e, 2026-09-23): PUBLIC_WITH_TERMS and "
                    "ACCESS_UNCLEAR are routing and provenance labels that withhold "
                    "REDISTRIBUTION, never reading; the quarantine was deleted; and nothing here "
                    "defeats an access control or invents a credential"}


# --------------------------------------------------------------------------- helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _clip(p: float, eps: float = 1e-6) -> float:
    return float(min(max(float(p), eps), 1.0 - eps))


def _logit(p: float) -> float:
    q = _clip(p)
    return math.log(q / (1.0 - q))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(min(x, 60.0), -60.0)))


# --------------------------------------------------------------------------- 1. calibration
def fit_recalibration(p: Sequence[float], y: Sequence[float]) -> dict[str, Any]:
    """Fit logit(p_true) = a + b logit(p_market) by Bernoulli maximum likelihood.

    Least squares on binned frequencies would throw away the sample size in each bin and would
    give a slope that depends on where somebody drew the bins. The likelihood does not: every
    forecast contributes exactly once, at its own probability, and the fit is the two-parameter
    logistic regression this problem actually is.
    """
    x = np.asarray([_logit(v) for v in p], dtype=float)
    t = np.asarray([1.0 if float(v) > 0.5 else 0.0 for v in y], dtype=float)
    if x.size < MIN_FORECASTS or float(np.std(x)) == 0 or len(set(t.tolist())) < 2:
        return {"verdict": UNMEASURED,
                "why": f"{x.size} forecasts (need {MIN_FORECASTS}), a constant probability, or "
                       "one-sided outcomes", "n": int(x.size)}

    def nll(theta: np.ndarray) -> float:
        z = np.clip(theta[0] + theta[1] * x, -60.0, 60.0)
        pr = 1.0 / (1.0 + np.exp(-z))
        pr = np.clip(pr, 1e-9, 1 - 1e-9)
        val = -float(np.sum(t * np.log(pr) + (1 - t) * np.log(1 - pr)))
        return val if math.isfinite(val) else 1e12

    theta, neg = nelder_mead(nll, np.array([0.0, 1.0]), iters=500, step=0.5)
    a, b = float(theta[0]), float(theta[1])
    return {"verdict": "MEASURED", "n": int(x.size), "intercept": a, "slope": b,
            "loglik": -neg,
            "reading": ("under-confident: push the extremes out" if b > 1.05 else
                        "over-confident: pull the extremes in" if b < 0.95 else
                        "slope within 5% of 1: no recalibration earned"),
            "published_prior": SLOPE_PRIOR.published, "prior_ladder": list(SLOPE_PRIOR.rungs()),
            "nearest_rung": min(SLOPE_PRIOR.rungs(), key=lambda r: abs(r - b))}


def recalibrate(p: float, fit: Mapping[str, Any]) -> float:
    """Apply a fitted recalibration; an UNMEASURED fit returns the market's own number unchanged.

    Unchanged rather than nudged toward the published 1.18: applying somebody else's slope to a
    category nobody has fitted is exactly the inherited-overfit this desk refuses.
    """
    if fit.get("verdict") != "MEASURED":
        return _clip(p)
    return _sigmoid(float(fit["intercept"]) + float(fit["slope"]) * _logit(p))


def calibration_error(p: Sequence[float], y: Sequence[float],
                      bins: Sequence[float] = CAL_BINS) -> dict[str, Any]:
    """Expected calibration error plus the per-bin table it is computed from.

    The table is returned as well as the headline, because a single ECE hides WHERE the miss is,
    and the favourite/longshot question is entirely about where.
    """
    pv = np.asarray([_clip(v) for v in p], dtype=float)
    yv = np.asarray([1.0 if float(v) > 0.5 else 0.0 for v in y], dtype=float)
    if pv.size == 0:
        return {"verdict": UNMEASURED, "why": "no forecasts"}
    rows: list[dict[str, Any]] = []
    total, ece = 0, 0.0
    for lo, hi in itertools.pairwise(bins):
        m = (pv >= lo) & (pv < hi if hi < 1.0 else pv <= hi)
        if not bool(np.any(m)):
            continue
        mean_p, freq, n = float(pv[m].mean()), float(yv[m].mean()), int(m.sum())
        rows.append({"bin": [lo, hi], "n": n, "mean_p": mean_p, "observed": freq,
                     "gap": freq - mean_p})
        ece += n * abs(freq - mean_p)
        total += n
    return {"verdict": "MEASURED", "ece": ece / total if total else None, "bins": rows,
            "n": int(pv.size)}


def favourite_longshot(p: Sequence[float], y: Sequence[float]) -> dict[str, Any]:
    """The asymmetry, measured on the two halves of the range rather than averaged into one slope.

    The classic finding is that longshots are over-priced and favourites under-priced. If it holds
    here, the gap (observed frequency minus stated probability) is NEGATIVE in the low-p half and
    POSITIVE in the high-p half -- and those are two different corrections, which is precisely
    what one global slope cannot express.
    """
    pv = np.asarray([_clip(v) for v in p], dtype=float)
    yv = np.asarray([1.0 if float(v) > 0.5 else 0.0 for v in y], dtype=float)
    lo, hi = pv < 0.5, pv >= 0.5
    if int(lo.sum()) < 10 or int(hi.sum()) < 10:
        return {"verdict": UNMEASURED,
                "why": f"{int(lo.sum())} longshots and {int(hi.sum())} favourites: fewer than 10 "
                       "on a side is not an asymmetry"}
    g_lo = float(yv[lo].mean() - pv[lo].mean())
    g_hi = float(yv[hi].mean() - pv[hi].mean())
    return {"verdict": "MEASURED", "longshot_gap": g_lo, "favourite_gap": g_hi,
            "n_longshot": int(lo.sum()), "n_favourite": int(hi.sum()),
            "asymmetry": g_hi - g_lo,
            "classic_pattern": bool(g_lo < 0 and g_hi > 0),
            "reading": ("longshots over-priced and favourites under-priced, as the literature "
                        "reports" if (g_lo < 0 and g_hi > 0) else
                        "the classic favourite/longshot pattern does NOT hold on this sample")}


def bounded_momentum(series: Sequence[float], *, cap: float = MOMENTUM_CAP,
                     lookback: int = 5) -> dict[str, Any]:
    """Recent drift in a contract's own probability, BOUNDED. A probability cannot trend to
    infinity, so a momentum feature over one must be clipped or it will invent one."""
    v = np.asarray([_clip(x) for x in series], dtype=float)
    if v.size < lookback + 1:
        return {"verdict": UNMEASURED, "why": f"{v.size} points under a {lookback} lookback"}
    raw = float(v[-1] - v[-1 - lookback])
    return {"verdict": "MEASURED", "raw": raw, "bounded": float(np.clip(raw, -cap, cap)),
            "cap": cap, "lookback": lookback, "last": float(v[-1])}


def calibrate(forecasts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Calibration by CATEGORY x HORIZON BUCKET x LIQUIDITY BUCKET, each fitted on its own rows.

    A cell under `MIN_FORECASTS` is UNMEASURED BY NAME and keeps its row in the table, because the
    cells nobody has enough data for are the ones a reader most needs to know about -- a table
    that silently omits them reads as if every category were calibrated.
    """
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for f in forecasts:
        if f.get("outcome") is None or f.get("p") is None:
            continue
        key = "|".join((str(f.get("category") or "unknown"),
                        str(f.get("horizon_bucket") or f.get("horizon") or "unknown"),
                        str(f.get("liquidity_bucket") or "unknown")))
        groups.setdefault(key, []).append(f)
    out: dict[str, Any] = {}
    for key, rows in sorted(groups.items()):
        p = [float(r["p"]) for r in rows]
        y = [float(r["outcome"]) for r in rows]
        fit = fit_recalibration(p, y)
        out[key] = {"n": len(rows), "fit": fit, "ece": calibration_error(p, y),
                    "favourite_longshot": favourite_longshot(p, y)}
    fitted = [k for k, v in out.items() if v["fit"].get("verdict") == "MEASURED"]
    return {"cells": out, "n_cells": len(out), "fitted_cells": fitted,
            "unmeasured_cells": [k for k in out if k not in fitted],
            "rule": "one recalibration per category x horizon x liquidity, fitted on its own "
                    "rows; the published 1.18 is a rung on the ladder, never the answer"}


# --------------------------------------------------------------------------- 2. resolution truth
def record_forecast(row: Mapping[str, Any], *, path: Path | None = None,
                    dry_run: bool = False) -> dict[str, Any]:
    """Store a forecast BEFORE the contract resolves. That ordering is the entire discipline.

    A row that arrives already carrying an outcome is refused: it is not a forecast, it is a
    recollection, and a scoreboard that admits recollections measures nothing.
    """
    if row.get("outcome") is not None:
        return {"stored": False,
                "why": "this row already carries an outcome: a forecast is recorded BEFORE "
                       "resolution or it is not a forecast"}
    out = {"stored_at": _now(), "forecast_id": str(row.get("forecast_id") or ""),
           "source": str(row.get("source") or ""), "kind": str(row.get("kind") or "market"),
           "category": str(row.get("category") or "unknown"),
           "horizon_bucket": str(row.get("horizon_bucket") or "unknown"),
           "liquidity_bucket": str(row.get("liquidity_bucket") or "unknown"),
           "p": _clip(float(row.get("p", 0.5))), "resolves_at": str(row.get("resolves_at") or ""),
           "question": str(row.get("question") or "")[:300]}
    if not dry_run:
        p = path or FORECASTS
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(out, sort_keys=True) + "\n")
    return {"stored": True, "row": out}


def score_forecasts(forecasts: Sequence[Mapping[str, Any]], *,
                    by: str = "source") -> dict[str, Any]:
    """Brier, log loss and calibration error per source / model / seat, against two references.

    THE TWO REFERENCES MATTER AS MUCH AS THE SCORES. A Brier of 0.21 is meaningless on its own: it
    is good against a base rate of 0.5 and terrible against one of 0.05. So every group is scored
    beside the constant base-rate forecast AND beside `BetaBinary`, the desk's permanent
    calibrated-binary baseline, so "did this source beat knowing nothing" is answered on the same
    page as the score.
    """
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for f in forecasts:
        if f.get("outcome") is None or f.get("p") is None:
            continue
        groups.setdefault(str(f.get(by) or "unknown"), []).append(f)
    out: dict[str, Any] = {}
    for key, rows in sorted(groups.items()):
        p = np.asarray([_clip(float(r["p"])) for r in rows], dtype=float)
        y = np.asarray([1.0 if float(r["outcome"]) > 0.5 else 0.0 for r in rows], dtype=float)
        base = float(y.mean())
        brier = float(np.mean((p - y) ** 2))
        logloss = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
        base_brier = float(np.mean((base - y) ** 2))
        beta = BetaBinary().fit(y)
        out[key] = {
            "n": int(p.size), "brier": brier, "log_loss": logloss,
            "base_rate": base, "base_rate_brier": base_brier,
            "brier_skill_vs_base": (1.0 - brier / base_brier) if base_brier > 0 else None,
            "beta_baseline_logscore": beta.score(y) if beta.state.get("fitted") else UNMEASURED,
            "log_score": float(np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
            "calibration": calibration_error(p.tolist(), y.tolist()),
            "beats_beta_baseline": (bool(float(np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
                                         > beta.score(y)) if beta.state.get("fitted")
                                    else UNMEASURED)}
    return {"grouped_by": by, "groups": out, "n_groups": len(out),
            "rule": "every score sits beside the base rate and the BetaBinary baseline; a score "
                    "without a reference is not a measurement"}


# --------------------------------------------------------------------------- 3. disagreement
def disagreement_vector(readings: Mapping[str, Any]) -> dict[str, Any]:
    """[p_market, p_news, p_macro, p_options, p_smart] and what their spread says.

    A missing leg is UNMEASURED and stays in the vector as None -- it is never imputed from the
    others, because imputing a leg from its neighbours manufactures the agreement the vector
    exists to measure.
    """
    vec: list[float | None] = [(_clip(float(readings[k]))
                                if isinstance(readings.get(k), (int, float))
                                else None) for k in DISAGREEMENT_LEGS]
    have = [v for v in vec if v is not None]
    if len(have) < 2:
        return {"verdict": UNMEASURED, "legs": dict(zip(DISAGREEMENT_LEGS, vec, strict=True)),
                "why": f"{len(have)} readable leg(s): a disagreement needs two opinions"}
    arr = np.asarray(have, dtype=float)
    spread = float(arr.max() - arr.min())
    logits = np.asarray([_logit(v) for v in have], dtype=float)
    return {"verdict": "MEASURED", "legs": dict(zip(DISAGREEMENT_LEGS, vec, strict=True)),
            "n_legs": len(have), "mean": float(arr.mean()), "spread": spread,
            "logit_spread": float(logits.max() - logits.min()),
            "stance": "disagreement" if spread >= 0.15 else "agreement",
            "most_bullish": DISAGREEMENT_LEGS[int(np.argmax([v if v is not None else -1
                                                             for v in vec]))],
            "most_bearish": DISAGREEMENT_LEGS[int(np.argmin([v if v is not None else 2
                                                             for v in vec]))],
            "unmeasured_legs": [k for k, v in zip(DISAGREEMENT_LEGS, vec, strict=True)
                                if v is None]}


# --------------------------------------------------------------------------- 4. dependencies
def dependency_deviations(contracts: Mapping[str, float], *,
                          sum_to_one: Sequence[Sequence[str]] = (),
                          implications: Sequence[tuple[str, str]] = (),
                          tolerance: float = DEPENDENCY_TRIGGER) -> dict[str, Any]:
    """Logical consistency between related contracts. THE DEVIATIONS ARE INTELLIGENCE, NOT TRADES.

    Two constraints, and they are the only two that are pure logic rather than opinion:

      * a SUM-TO-ONE group is a partition of exhaustive, mutually exclusive outcomes, so its
        probabilities must sum to one and any excess is over-pricing spread across the group;
      * an IMPLICATION CHAIN "A implies B" forces p(A) <= p(B), so p(A) - p(B) > 0 is a market
        that has priced a specific event above the general one containing it.

    A violation says the venue has not propagated a piece of reasoning yet, which is a MACRO read
    about what participants are and are not thinking about. This desk cannot execute on those
    venues and does not try: no arbitrage, no order, no position -- the output is a named
    inconsistency and its size.
    """
    groups: list[dict[str, Any]] = []
    for i, members in enumerate(sum_to_one):
        known = [m for m in members if m in contracts]
        if len(known) < 2:
            groups.append({"group": i, "members": list(members), "verdict": UNMEASURED,
                           "why": f"{len(known)} of {len(members)} legs priced"})
            continue
        total = float(sum(_clip(contracts[m]) for m in known))
        complete = len(known) == len(members)
        groups.append({"group": i, "members": list(members), "verdict": "MEASURED",
                       "sum": total, "deviation": total - 1.0 if complete else None,
                       "complete": complete,
                       "violation": bool(complete and abs(total - 1.0) > tolerance),
                       "why": ("an exhaustive partition must sum to one" if complete else
                               "partial group: the sum is a lower bound, not a deviation")})
    chains: list[dict[str, Any]] = []
    for a, b in implications:
        if a not in contracts or b not in contracts:
            chains.append({"implies": [a, b], "verdict": UNMEASURED,
                           "why": "one leg of the implication is not priced"})
            continue
        pa, pb = _clip(contracts[a]), _clip(contracts[b])
        dev = pa - pb
        chains.append({"implies": [a, b], "verdict": "MEASURED", "p_a": pa, "p_b": pb,
                       "deviation": dev, "violation": bool(dev > tolerance),
                       "why": f"{a} implies {b}, so p({a}) must not exceed p({b})"})
    violations = ([g for g in groups if g.get("violation")]
                  + [c for c in chains if c.get("violation")])
    return {"sum_to_one": groups, "implications": chains, "violations": violations,
            "n_violations": len(violations), "tolerance": tolerance,
            "traded": False,
            "rule": "deviations are macro intelligence about what the market has not priced; "
                    "this desk does not trade them and holds no account on these venues"}


# --------------------------------------------------------------------------- 5. lead / lag
def lead_lag_vs_instrument(odds: Sequence[float], instrument: Sequence[float], *,
                           max_lag: int = 12, permutations: int = 200) -> dict[str, Any]:
    """Event odds against one of the desk's own instruments, with a block-permutation null.

    Delegated to `source_civilizations.lead_lag` so one implementation owns the null. A positive
    peak lag means the odds LEAD the instrument, which is the only direction that would be worth
    anything; a negative one means the desk's own tape already knew.
    """
    out = SC.lead_lag(odds, instrument, max_lag=max_lag, permutations=permutations)
    if out.get("verdict") == "MEASURED":
        lag = int(out["peak_lag"])
        out["direction"] = ("odds lead the instrument" if lag > 0 else
                            "the instrument leads the odds" if lag < 0 else "contemporaneous")
        out["significant"] = bool(float(out["p_value"]) <= 0.05)
    return out


# --------------------------------------------------------------------------- 6. Kelly reference
def kelly_reference(p: float, price: float, *, fraction: float = 0.25) -> dict[str, Any]:
    """The fractional-Kelly stake a binary contract WOULD imply. A COMPARISON BASELINE ONLY.

    For a YES bought at `price`, f* = (p - price) / (1 - price); for the NO side,
    f* = (price - p) / price. Both are the standard binary Kelly and both are reported so a reader
    can see which side the edge is on.

    IT IS NEVER A SIZING AUTHORITY ON THIS DESK, and the payload says so in its own field. Capital
    here is the allocator's decision by delta E[log W] against the whole book's covariance; a
    per-contract Kelly ignores every other position and would size a correlated book far past what
    the survival envelope allows. What it IS good for is a reference: when the allocator's fraction
    and this number disagree by an order of magnitude, one of the two has a bad input.
    """
    q = _clip(price)
    pp = _clip(p)
    f_yes = (pp - q) / (1.0 - q)
    f_no = (q - pp) / q
    side = "yes" if f_yes >= f_no else "no"
    full = max(f_yes, f_no)
    return {"p": pp, "price": q, "edge": pp - q, "side": side,
            "full_kelly": float(full), "fraction": fraction,
            "fractional_kelly": float(max(0.0, full) * fraction),
            "f_yes": float(f_yes), "f_no": float(f_no),
            "sizing_authority": False,
            "rule": "a REFERENCE for comparison against the allocator's delta E[log W] fraction; "
                    "it never sizes anything, because a per-contract Kelly cannot see the book"}


# --------------------------------------------------------------------------- fixtures and intake
def fixture_markets() -> list[dict[str, Any]]:
    """The offline market set `--no-fetch` runs on. Synthetic, stamped, and clearly labelled.

    A fixture is not a claim about any venue's real prices; it exists so every function here is
    exercised on a box with no network and so a test never has to reach one.
    """
    rng = np.random.default_rng(3)
    rows: list[dict[str, Any]] = []
    for i in range(720):
        cat = ("rates", "macro", "geopolitics")[i % 3]
        p = float(np.clip(rng.beta(2.0, 2.0), 0.02, 0.98))
        true_p = _sigmoid(1.18 * _logit(p))          # the planted slope the fit must recover
        rows.append({"forecast_id": f"fx{i}", "source": "fixture", "kind": "market",
                     "category": cat, "horizon_bucket": ("short", "long")[i % 2],
                     "liquidity_bucket": ("thin", "deep")[i % 2], "p": p,
                     "outcome": float(rng.random() < true_p),
                     "question": f"fixture contract {i}", "resolves_at": "2026-12-31T00:00:00Z",
                     "fixture": True})
    return rows


def load_markets(*, fetch: bool = False, fixtures: Sequence[Mapping[str, Any]] | None = None,
                 venue: str = "") -> dict[str, Any]:
    """Market rows for this pass. `fetch=False` (the default) NEVER touches the network.

    With `fetch=True` the venue's ACCESS LABEL decides, not a flag: a PUBLIC_WITH_TERMS venue is
    used through its documented API only, and this box carries no API credentials for any of them,
    so the honest outcome here is UNMEASURED with the reason named rather than a scrape.
    """
    if fixtures is not None:
        return {"source": "fixtures", "rows": [dict(r) for r in fixtures],
                "fetched": False, "n": len(list(fixtures))}
    if not fetch:
        rows = fixture_markets()
        return {"source": "builtin_fixture", "rows": rows, "fetched": False, "n": len(rows),
                "why": "--no-fetch: the whole module runs offline"}
    v = BY_NAME.get(venue)
    if v is None:
        return {"source": venue or "?", "rows": [], "fetched": False, "n": 0,
                "verdict": UNMEASURED, "why": f"no venue named {venue!r} is registered"}
    if not v.machine_use_allowed:
        # REACHED ONLY BY A REFUSED LABEL (PRIVATE / CONFIDENTIAL_MNPI / STOLEN_UNAUTHORIZED) --
        # one of the five acts of the hard boundary. A terms, licence or unclear-access label has
        # not landed here since LAWS 5e (2026-09-23).
        return {"source": v.name, "rows": [], "fetched": False, "n": 0, "verdict": "REFUSED",
                "terms_note": v.terms_note,
                "why": (f"HARD BOUNDARY {v.access_label}: "
                        f"{SC.ACCESS_BEHAVIOUR[v.access_label]['why']}")}
    return {"source": v.name, "rows": [], "fetched": False, "n": 0, "verdict": UNMEASURED,
            "terms_note": v.terms_note,
            "why": (f"{v.name} is MINED AND TESTED under its {v.access_label} label; no API "
                    "credential for its documented endpoint exists on this box, so THIS reading "
                    "is UNMEASURED -- a missing endpoint, never a refusal")}


# --------------------------------------------------------------------------- discoveries
def odds_discoveries(cells: Sequence[Mapping[str, Any]], *, dry_run: bool = False,
                     conn: Any = None) -> list[str]:
    """Event odds x rates / gold / oil / USDJPY as registry discoveries.

    The hypothesis is never "the contract is mispriced". It is that a resolving probability about a
    macro event is a CONDITIONER on the MT5 instrument that event repriced -- which is testable on
    the desk's own bars, by the desk's own ten gates, with no position on any venue.
    """
    out: list[str] = []
    for cell in cells:
        sym = str(cell.get("symbol") or "")
        if sym not in MACRO_LEGS:
            continue
        spec = {"symbol": sym, "category": str(cell.get("category") or "macro"),
                "stance": str(cell.get("stance") or "disagreement")}
        if dry_run:
            out.append(f"dry:odds:{sym}:{spec['category']}:{spec['stance']}")
            continue
        did, _ = R.record_discovery(
            source_id=f"prediction_markets:{spec['category']}", source_type="prediction_market",
            mechanism=(f"event probability ({spec['category']}) as a {spec['stance']} conditioner "
                       f"on {sym}")[:400],
            origin="EXTERNAL", generator="bl888m:prediction_markets",
            assets=[sym], sessions=["all"], horizons=["H4"], regimes=[""],
            information="event",
            economic_rationale=("a resolving probability is a second opinion with a track record; "
                                "where it disagrees with the tape, one of them holds information "
                                "the other has not priced"),
            exact_rule_if_known=(f"condition a {sym} sleeve on the recalibrated probability of the "
                                 f"{spec['category']} contract and its {spec['stance']} with the "
                                 "desk's own reading"),
            required_data=["prediction_market_odds", f"{sym}_H4.parquet"],
            falsifier=(f"{sym} forward returns do not separate across the odds distribution, "
                       "recalibrated or raw"),
            novelty=0.7, confidence=0.35, payload=dict(cell), conn=conn)
        out.append(did)
    return out


# --------------------------------------------------------------------------- the organ
def run_pass(*, no_fetch: bool = True, budget_s: float = 180.0, dry_run: bool = False,
             fixtures: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    loaded = load_markets(fetch=not no_fetch, fixtures=fixtures)
    rows = loaded["rows"]
    cal = calibrate(rows)
    scored = score_forecasts(rows, by="source")
    contracts = {r["forecast_id"]: float(r["p"]) for r in rows[:6]}
    ids = list(contracts)
    deps = dependency_deviations(
        contracts, sum_to_one=[ids[:3]] if len(ids) >= 3 else [],
        implications=[(ids[0], ids[1])] if len(ids) >= 2 else [])
    vector = disagreement_vector({"p_market": rows[0]["p"] if rows else None,
                                  "p_news": rows[1]["p"] if len(rows) > 1 else None})
    kelly = kelly_reference(0.62, 0.50)
    cells = [{"symbol": s, "category": "rates", "stance": vector.get("stance", "disagreement")}
             for s in MACRO_LEGS if (time.monotonic() - started) < budget_s]
    conn = None if dry_run else R.connect()
    try:
        minted = odds_discoveries(cells, dry_run=dry_run, conn=conn)
    finally:
        if conn is not None:
            conn.close()
    report = {
        "generated_at": _now(), "no_fetch": no_fetch, "dry_run": dry_run,
        "elapsed_s": round(time.monotonic() - started, 2),
        "terms": venue_terms(),
        "source": loaded["source"], "n_rows": loaded["n"],
        "calibration": cal, "resolution_scores": scored,
        "disagreement_legs": list(DISAGREEMENT_LEGS), "disagreement_example": vector,
        "dependency": deps, "kelly_reference": kelly,
        "macro_legs": list(MACRO_LEGS), "discoveries": len(minted),
        "momentum_cap": MOMENTUM_CAP,
        "rule": "a prediction market is a FORECAST SOURCE that resolves, never a venue this desk "
                "trades; calibration is fitted per category, deviations are intelligence, and the "
                "Kelly number is a reference with no sizing authority",
    }
    if not dry_run:
        _atomic(REPORT, report)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="prediction-market intelligence")
    ap.add_argument("--no-fetch", action="store_true", default=True,
                    help="run entirely off fixtures (the default)")
    ap.add_argument("--fetch", dest="no_fetch", action="store_false",
                    help="allow the API path where a venue's terms and a credential permit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=float, default=180.0)
    a = ap.parse_args(argv)
    rep = run_pass(no_fetch=bool(a.no_fetch), budget_s=float(a.budget_s),
                   dry_run=bool(a.dry_run))
    print(json.dumps({k: rep[k] for k in ("generated_at", "no_fetch", "n_rows", "elapsed_s",
                                          "discoveries")}
                     | {"fitted_cells": rep["calibration"]["fitted_cells"],
                        "violations": rep["dependency"]["n_violations"]},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
