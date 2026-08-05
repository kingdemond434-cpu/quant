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

from libs.autodiscovery.memory import CandidateStore
from libs.store.connection import Database
from libs.validation.reject_rescore import plan_rescore

_ROOT = Path(__file__).resolve().parent.parent
_SCORES = _ROOT / "data/reject_forward_scores.json"

# Lazy per-run caches: lake frames are read once per symbol, the BTC reference once.
_FRAMES: dict[str, object] = {}
_MIN_FWD_BARS = 30


def _frame(symbol: str):
    if symbol not in _FRAMES:
        try:
            from libs.autodiscovery.crypto_adapter import _read_frames
            from libs.data.timeframe import Timeframe
            _FRAMES.update(_read_frames([symbol], Timeframe.D1, "data/lake"))
        except Exception:
            _FRAMES[symbol] = None
    return _FRAMES.get(symbol)


def _forward_score(rec: object) -> float | None:
    """Re-evaluate one rejected candidate on its post-rejection forward window.

    Rebuilds the stored (family, subtype, symbol, params) signal via the SAME generator registry
    the campaign used, on the full lake series (causal rolling windows need their warmup), then
    scores ONLY the bars strictly after ``rec.created_at`` -- genuinely out-of-sample relative to
    the rejection. Same cost model as the campaign default (net_returns, 3bps/turnover). Returns
    None when the lake cannot produce an honest forward series (missing frame, <30 forward bars,
    unknown generator) -- never a guess. Annualized daily Sharpe (sqrt(365), crypto clock).
    """
    if rec is None:
        return None
    try:
        import numpy as np
        import pandas as pd

        from libs.autodiscovery.crypto_adapter import _provider_from_frames
        from libs.autodiscovery.generators import GENERATORS, net_returns
        spec = next((g for g in GENERATORS
                     if g.family.value == rec.family and g.subtype == rec.subtype), None)
        df = _frame(rec.symbol)
        if spec is None or df is None:
            return None
        _frame("BTCUSDT")  # cross-asset generators need the reference leg in the frame cache
        provider = _provider_from_frames({k: v for k, v in _FRAMES.items() if v is not None},
                                         min_bars=_MIN_FWD_BARS)
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
        if len(fwd) < _MIN_FWD_BARS or float(np.std(fwd)) == 0.0:
            return None
        return float(np.mean(fwd) / np.std(fwd) * np.sqrt(365.0))
    except Exception:
        return None  # unreadable inputs surface as unscored, never as a fabricated number


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/sor_crypto.sqlite")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--min-age-days", type=float, default=30.0)
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
    else:
        print("no new forward scores produced (re-eval hook not wired on this host, or all "
              "selected already scored) -- the shadow audit will report unscored, honestly")


if __name__ == "__main__":
    main()
