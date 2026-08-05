#!/usr/bin/env python3
"""REJECT RE-SCORE FEEDER -- produce the forward scores the rejection-shadow audit consumes.

Closes the gate-leak recovery loop (MAX_SURVIVORS Part 1.2). Plans which rejects to re-score
(near-miss first, capped -- libs.validation.reject_rescore), re-evaluates each on the forward window
that arrived AFTER its rejection, and writes data/reject_forward_scores.json -- exactly the file
run_rejection_shadow.py reads. Incremental: already-scored rejects are kept, new scores merged.

THE RE-EVAL: rebuilding a stored candidate's signal and running it on post-rejection market data
needs the lake + the generator registry. Both are wired below. When the lake cannot produce an
honest forward series (symbol absent, or fewer than ``--min-forward-bars`` bars after the
rejection date) the candidate scores None and the shadow audit reports it unscored -- never a
fabricated number.

WHICH STORE. Default is the crypto store, because it is the only one whose rejects are scorable
here: the June FX-era store (sor_autodiscovery) holds 57 rejects on EURUSD/XAUUSD/US500 whose lake
D1 bars stop 2026-06-19 -- the day before they were rejected -- and whose native H1 series was
never persisted. Those can never be scored on this host, so pointing the loop at them guaranteed a
permanently unscored audit that looked like a wiring bug.

Usage: run_rejection_rescore.py [--db data/sor_crypto.sqlite] [--limit 50] [--min-age-days 30]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from libs.autodiscovery.generators import GENERATORS, net_returns
from libs.autodiscovery.memory import CandidateStore
from libs.autodiscovery.models import MarketSeries
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.store.connection import Database
from libs.validation.dsr import sharpe_ratio
from libs.validation.reject_rescore import plan_rescore

_ROOT = Path(__file__).resolve().parent.parent
_SCORES = _ROOT / "data/reject_forward_scores.json"
_LAKE = _ROOT / "data/lake"
#: ~4bps taker + slippage per side. The forward score must be net of cost for the same reason the
#: original backtest was: a gross-positive reject is not a gate leak, it is a cost failure.
_COST_PER_SIDE = 5e-4


def _spec_for(family: str, subtype: str) -> Any | None:
    """The generator that produced this candidate, by its STORED (family, subtype) strings."""
    for g in GENERATORS:
        if g.family.value == family and g.subtype == subtype:
            return g
    return None


def _lake_frames(lake_root: Path = _LAKE, *, verbose: bool = False) -> dict[str, Any]:
    """Every symbol with D1 bars, keyed by symbol, indexed by timestamp. Read once per run.

    REGISTERING THE INSTRUMENT IS NOT OPTIONAL. ``ParquetLake.read_bars`` resolves a symbol
    through the instrument registry, so an unregistered symbol raises -- and with a bare
    ``except: continue`` that read as "this symbol has no data". It silently dropped all 285
    crypto perps (leaving only the seven fx/metal/index names registered elsewhere at import) and
    the runner reported a clean zero. Unreadable partitions are COUNTED and surfaced rather than
    swallowed, because "no scorable rejects" and "the reader is broken" must never look alike.
    """
    base = lake_root / "bronze"
    if not base.exists():
        return {}
    lake = ParquetLake(str(lake_root))
    out: dict[str, Any] = {}
    failed = 0
    for ac_dir in sorted(base.iterdir()):
        if not ac_dir.is_dir():
            continue
        try:
            asset_class = AssetClass(ac_dir.name)
        except ValueError:
            continue                     # not an asset-class dir (binance_metrics, fed, ...)
        for sym_dir in sorted(ac_dir.iterdir()):
            if not (sym_dir / Timeframe.D1.value).exists():
                continue
            register_instrument(InstrumentSpec(symbol=sym_dir.name, asset_class=asset_class,
                                               description=sym_dir.name))
            try:
                out[sym_dir.name] = lake.read_bars(
                    Layer.BRONZE, sym_dir.name, Timeframe.D1).set_index("timestamp")
            except Exception:            # a corrupt partition must not kill the whole sweep
                failed += 1
    if failed and verbose:
        print(f"  WARNING: {failed} symbol(s) had D1 partitions that would not read")
    return out


def _forward_score(rec: object, frames: dict[str, Any], *, min_forward_bars: int = 30
                   ) -> float | None:
    """Re-evaluate one rejected candidate on its post-rejection forward window.

    NO LOOK-AHEAD, AND NO WARM-UP CHEAT. Positions are built over the FULL history -- a 200-bar
    moving average genuinely needs its 200 prior bars, and computing them from the forward slice
    alone would score a different (shorter-memory) strategy than the one that was rejected. Only
    the RETURNS are then sliced to bars strictly after the rejection date. The signal primitives
    are causal and ``net_returns`` applies lag-1, so a position at t uses only data up to t.
    """
    spec = _spec_for(getattr(rec, "family", ""), getattr(rec, "subtype", ""))
    df = frames.get(getattr(rec, "symbol", ""))
    if spec is None or df is None or len(df) < 2:
        return None
    try:
        series = MarketSeries(
            close=df["close"].to_numpy("float64"), high=df["high"].to_numpy("float64"),
            low=df["low"].to_numpy("float64"), volume=df["volume"].to_numpy("float64"),
            hour=np.array([t.hour for t in df.index], dtype="float64"),
            funding=df["funding"].to_numpy("float64") if "funding" in df.columns else None,
        )
        positions = spec.fn(series, dict(getattr(rec, "params", {}) or {}))
        rets = net_returns(series, positions, cost=_COST_PER_SIDE)
    except Exception:
        return None
    # strategy_returns drops the first bar, so returns align to the index from position 1 on.
    stamps = df.index[1:]
    if len(stamps) != len(rets):
        return None
    cutoff = np.datetime64(str(getattr(rec, "created_at", "")).replace("Z", "").split("+")[0])
    forward = rets[stamps.to_numpy("datetime64[ns]") > cutoff]
    if len(forward) < min_forward_bars:
        return None
    if float(np.std(forward)) == 0.0:
        # The rule never took a position in the forward window. `sharpe_ratio` reports 0.0 for a
        # zero-variance series, but "we measured it and it was flat" is a DIFFERENT claim from
        # "it was never in the market" -- and feeding the second in as a real 0.0 would bias the
        # gate-leak audit toward "no leak" with scores that measured nothing.
        return None
    return round(float(sharpe_ratio(forward)) * float(np.sqrt(252.0)), 6)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/sor_crypto.sqlite")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--min-age-days", type=float, default=30.0)
    p.add_argument("--min-forward-bars", type=int, default=30,
                   help="a Sharpe on fewer bars than this is noise, so score None instead")
    a = p.parse_args()

    db_path = _ROOT / a.db if not Path(a.db).is_absolute() else Path(a.db)
    if not db_path.exists():
        print(f"no candidate ledger at {db_path} -- nothing to re-score")
        return
    store = CandidateStore(Database(db_path, read_only=True))
    all_rejects = store.rejects()
    plan = plan_rescore(
        [(r.id, r.created_at, max(r.metrics.oos_sharpe, r.metrics.annual_sharpe))
         for r in all_rejects],
        min_age_days=a.min_age_days, limit=a.limit,
    )
    print(f"rescore plan: {plan.verdict}")

    by_id = {r.id: r for r in all_rejects}
    scores: dict[str, float] = {}
    if _SCORES.exists():
        try:
            scores = {str(k): float(v) for k, v in json.loads(_SCORES.read_text("utf-8")).items()}
        except Exception:
            scores = {}
    frames = _lake_frames(verbose=True) if plan.selected else {}
    n_new = 0
    unscorable = 0
    for cid in plan.selected:
        if cid in scores:
            continue  # already scored -- incremental
        val = _forward_score(by_id.get(cid), frames, min_forward_bars=a.min_forward_bars)
        if val is None:
            unscorable += 1
            continue
        scores[cid] = val
        n_new += 1

    if n_new:
        _SCORES.parent.mkdir(parents=True, exist_ok=True)
        _SCORES.write_text(json.dumps(scores, indent=1), "utf-8")
        print(f"wrote {n_new} new forward score(s) -> {_SCORES}")
    else:
        print(f"no new forward scores produced ({unscorable} unscorable: no lake symbol, or "
              f"fewer than {a.min_forward_bars} bars after the rejection date) -- the shadow "
              "audit will report unscored, honestly")


if __name__ == "__main__":
    main()
