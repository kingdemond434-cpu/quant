#!/usr/bin/env python3
"""REJECT RE-SCORE FEEDER -- produce the forward scores the rejection-shadow audit consumes.

Closes the gate-leak recovery loop (MAX_SURVIVORS Part 1.2). Plans which rejects to re-score
(near-miss first, capped -- libs.validation.reject_rescore), re-evaluates each on the forward window
that arrived AFTER its rejection, and writes data/reject_forward_scores.json -- exactly the file
run_rejection_shadow.py reads. Incremental: already-scored rejects are kept, new scores merged.

THE RE-EVAL (runtime-heavy, honest boundary): rebuilding a stored candidate's signal and running it
on post-rejection market data needs the lake + the generator. That is wired here via the crypto
adapter; if the lake/provider is unavailable (fresh clone, no data) the runner scores nothing and
exits cleanly, leaving the shadow audit to report "unscored" -- never a fabricated score.

Usage: run_rejection_rescore.py [--db data/sor_crypto.sqlite] [--limit 50] [--min-age 30]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from libs.autodiscovery.memory import CandidateStore
from libs.core.time import from_iso8601, utcnow
from libs.store.connection import Database
from libs.validation.reject_rescore import plan_rescore

_ROOT = Path(__file__).resolve().parent.parent
_SCORES = _ROOT / "data/reject_forward_scores.json"

# Lazy per-run caches: lake frames are read once per symbol, the BTC reference once.
_FRAMES: dict[str, object] = {}

#: FORWARD OBSERVATIONS a reject needs before ``_forward_score`` will return a number rather than
#: None. This is the REAL requirement -- everything below is derived from it.
_MIN_FWD_BARS = 30

#: L1.48 EXEMPTION: DATA-WINDOW DEFINITION, not a probation, cooldown or grace period. The
#: planner sees only ``(id, rejected_at, nearness)``; it cannot count bars, so it converts the
#: observation requirement into the only unit a timestamp affords. The number is DERIVED from
#: _MIN_FWD_BARS x the bar's calendar length, so the two can never drift: the old bare
#: ``default=30.0`` looked like a chosen waiting period and would have been silently wrong on any
#: other bar (30 H8 bars arrive in 10 days, not 30). Evidence is still the clock -- what is
#: demanded is OBSERVATIONS, and days are the unit they are counted in on D1.
_D1_BAR_DAYS = 1.0
_MIN_AGE_DAYS = _MIN_FWD_BARS * _D1_BAR_DAYS


def _frame(symbol: str):
    if symbol not in _FRAMES:
        try:
            from libs.autodiscovery.crypto_adapter import _read_frames
            from libs.data.timeframe import Timeframe
            _FRAMES.update(_read_frames([symbol], Timeframe.D1, "data/lake"))
        except Exception:
            _FRAMES[symbol] = None
    return _FRAMES.get(symbol)


def _spec_for(family: str, subtype: str) -> Any | None:
    """The generator that produced this candidate, by its STORED (family, subtype) strings.

    Matches the enum VALUE exactly: a row stored as str(Family.TREND) ("Family.TREND") must MISS,
    because rebuilding the signal under a guessed generator would fabricate a forward Sharpe for a
    different strategy than the one that was rejected.
    """
    from libs.autodiscovery.generators import GENERATORS
    for g in GENERATORS:
        if g.family.value == family and g.subtype == subtype:
            return g
    return None


def _forward_score(rec: object, frames: dict[str, Any] | None = None, *,
                   min_forward_bars: int = _MIN_FWD_BARS) -> float | None:
    """Re-evaluate one rejected candidate on its post-rejection forward window.

    Rebuilds the stored (family, subtype, symbol, params) signal via the SAME generator registry
    the campaign used, on the full lake series (causal rolling windows need their warmup), then
    scores ONLY the bars strictly after ``rec.created_at`` -- genuinely out-of-sample relative to
    the rejection. Same cost model as the campaign default (net_returns, 3bps/turnover). Returns
    None when the lake cannot produce an honest forward series (missing frame, <min_forward_bars
    forward bars, unknown generator) -- never a guess. Annualized daily Sharpe (sqrt(365)).

    ``frames`` is injectable so the None-not-zero honesty paths are testable without a lake;
    None (production) reads through the lazy module cache exactly as before.
    """
    if rec is None:
        return None
    try:
        import numpy as np
        import pandas as pd

        from libs.autodiscovery.crypto_adapter import _provider_from_frames
        from libs.autodiscovery.generators import net_returns
        spec = _spec_for(rec.family, rec.subtype)
        if frames is None:
            df = _frame(rec.symbol)
            if spec is None or df is None:
                return None
            _frame("BTCUSDT")  # cross-asset generators need the reference leg in the frame cache
            pool = {k: v for k, v in _FRAMES.items() if v is not None}
        else:
            df = frames.get(getattr(rec, "symbol", ""))
            if spec is None or df is None:
                return None
            pool = {k: v for k, v in frames.items() if v is not None}
        provider = _provider_from_frames(pool, min_bars=min_forward_bars)
        series = provider(rec.symbol)
        if series is None:
            return None
        positions = spec.fn(series, dict(rec.params))
        rets = net_returns(series, positions)
        cutoff = pd.Timestamp(rec.created_at)
        idx = df.index
        if getattr(idx, "tz", None) is not None and cutoff.tz is None:
            cutoff = cutoff.tz_localize(idx.tz)
        elif getattr(idx, "tz", None) is None and cutoff.tz is not None:
            cutoff = cutoff.tz_localize(None)
        rets = np.asarray(rets)
        # net_returns yields the return REALIZED at each bar after the first (len N-1 vs N bars):
        # align the cutoff mask to the TRAILING len(rets) bars so rets[j] pairs with its own bar.
        mask = np.asarray(idx > cutoff)[-len(rets):]
        fwd = rets[mask]
        if len(fwd) < min_forward_bars or float(np.std(fwd)) == 0.0:
            return None
        return float(np.mean(fwd) / np.std(fwd) * np.sqrt(365.0))
    except Exception:
        return None  # unreadable inputs surface as unscored, never as a fabricated number


def _ages(rejects: list[tuple[str, str, float]]) -> list[tuple[str, float]]:
    """(id, age_days) for every reject whose stamp parses. Unparseable stamps are DROPPED rather
    than defaulted to 0.0: a reject the planner could not date must not be reported as the one
    closest to eligibility."""
    now = utcnow()
    out: list[tuple[str, float]] = []
    for cid, at, _ in rejects:
        try:
            out.append((cid, (now - from_iso8601(at)).total_seconds() / 86400.0))
        except (TypeError, ValueError):
            continue
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/sor_crypto.sqlite")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--min-age-days", type=float, default=_MIN_AGE_DAYS,
                   help=f"derived: {_MIN_FWD_BARS} forward D1 bars (see _MIN_AGE_DAYS)")
    a = p.parse_args()

    db_path = _ROOT / a.db if not Path(a.db).is_absolute() else Path(a.db)
    if not db_path.exists():
        print(f"no candidate ledger at {db_path} -- nothing to re-score")
        return
    store = CandidateStore(Database(db_path, read_only=True))
    # NEARNESS MIXES TWO POPULATIONS OF `annual_sharpe` UNTIL THE STORE TURNS OVER (R0086).
    # Rows written before 2026-08-05 were annualised with the validator's deleted hourly constant
    # (24*260) whatever bars they ran on, so a D1 lab row carries sqrt(6240/365) = 4.135x its
    # honest value; rows written since carry the clock their caller declared. Nothing rewrites
    # history -- see libs/autodiscovery/validation.py -- so ranking them together puts inflated
    # rows ahead of identical honest ones (measured on a 50-slot batch: ~47 slots to pre-fix
    # rows, ~24/50 overlap with the queue an all-honest store would produce).
    # Within ONE population the order is unaffected: the deflation is a single positive constant
    # and `annual_sharpe` dominates the per-bar `oos_sharpe` on both sides of it.
    # A pre-fix row is recognisable by its stored series carrying a NULL `timeframe`
    # (candidate_returns.timeframe), which the lab has populated since the fix.
    rejects = [
        (r.id, r.created_at, max(r.metrics.oos_sharpe, r.metrics.annual_sharpe))
        for r in store.rejects()
    ]
    plan = plan_rescore(rejects, min_age_days=a.min_age_days, limit=a.limit)
    print(f"rescore plan: {plan.verdict}")

    by_id = {r.id: r for r in store.rejects()}
    scores: dict[str, float] = {}
    if _SCORES.exists():
        try:
            scores = {str(k): float(v) for k, v in json.loads(_SCORES.read_text("utf-8")).items()}
        except Exception:
            scores = {}
    n_new = 0
    for cid in plan.selected:
        if cid in scores:
            continue  # already scored -- incremental
        val = _forward_score(by_id.get(cid))
        if val is not None:
            scores[cid] = val
            n_new += 1

    if n_new:
        _SCORES.parent.mkdir(parents=True, exist_ok=True)
        _SCORES.write_text(json.dumps(scores, indent=1), "utf-8")
        print(f"wrote {n_new} new forward score(s) -> {_SCORES}")
    elif not plan.selected:
        # THE MESSAGE MUST NAME THE ORGAN THAT ACTUALLY STOPPED (R0241c). With nothing selected,
        # the re-eval loop never ran, so BOTH causes the old line offered were false -- and the
        # one it named first sends a reader to debug the lake and the crypto adapter, which are
        # fine. This is the L1.55 shape one layer up: a downstream message reporting a
        # downstream cause for an upstream refusal. Shortfall is stated in OBSERVATIONS (L1.48).
        newest = max((age for _, age in _ages(rejects)), default=None)
        short = "" if newest is None else (
            f" The nearest reject has ~{newest / _D1_BAR_DAYS:.0f} of the {_MIN_FWD_BARS} forward "
            f"D1 bars a score needs.")
        print(f"nothing was SELECTED, so no re-eval was attempted -- {plan.verdict}.{short} "
              "This is an input shortfall, NOT a re-eval failure: the lake and the adapter were "
              "never asked.")
    else:
        print(f"{len(plan.selected)} reject(s) selected but no new forward score produced "
              "(re-eval hook not wired on this host, or all selected already scored) -- "
              "the shadow audit will report unscored, honestly")


if __name__ == "__main__":
    main()
