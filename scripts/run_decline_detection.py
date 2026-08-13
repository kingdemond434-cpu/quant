#!/usr/bin/env python3
"""THE PRODUCER FOR data/decline_events.json -- the file the rebound book has always read and
nothing has ever written.

`run_opportunity_books.rebound_section()` opens this artifact, finds nothing, and reports
"every drawdown is unclassified, so a forced-deleveraging flush and a fundamental repricing look
identical". That is an honest UNMEASURED and it has been the answer since the book shipped,
because the desk owned a dip-buying classifier with no eyes: `drawdown_rebound` could rule on a
`DeclineEvent` and nothing built one from market data. This script is the eyes' entry point.

    python scripts/run_decline_detection.py                # detect + write the book's input
    python scripts/run_decline_detection.py --screen       # also run Stage-A on the signal

WHAT IT WRITES: `events` (every decline with its classification) and `history` (realised
bounce / max-adverse / recovery per mechanism), which are exactly the two inputs
`rebound_estimate` needs and has never had.

**IT PROMOTES NOTHING.** With `--screen` the per-bar signal goes through `stage_a_screen`, the
same gate every other candidate faces, and a pass earns a FORWARD CLOCK -- never capital. The
two-stage law is not relaxed for a strategy just because its mechanism is well argued; buying
crashes is precisely the family where a rule is right often enough to keep running and wrong
exactly when the losses are large.

**OI, FUNDING AND VOLUME DECIDE WHETHER THIS TRADES AT ALL.** On OHLCV alone the classifier
cannot separate a cascade from a repricing and returns MIXED_UNKNOWN, which emits no signal. That
is the safety property, and the honest consequence is that a lake without the enriched series
produces detections and no actionable events. The script says so in as many words rather than
quietly widening the rule.
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.research.decline_detector import (
    conditional_history,
    detect_declines,
    rebound_signal,
    summarise,
)

_OUT = Path("data/decline_events.json")
_LAKE = "data/lake"
#: THE DESK'S OWN OPEN-INTEREST ARCHIVE, and the reason this strategy can exist at all.
#: `scripts/collect_binance_metrics.py` snapshots OI daily precisely BECAUSE Binance serves only
#: ~30 days of it -- so this file is history the desk manufactured and nobody else has. Measured
#: on the live box 2026-08-13 without it: 1093 declines detected across five symbols and ZERO
#: actionable, every one falling to IDIOSYNCRATIC_ASSET_FAILURE or MIXED_UNKNOWN, because OI is
#: what the classifier calls the single best cascade signature -- forced selling DESTROYS open
#: interest and informed selling does not have to.
_OI_ARCHIVE = Path("data/crypto_metrics.parquet")
#: Enriched per-bar columns the classifier needs to name a cascade. Absent columns stay None and
#: the event falls to MIXED_UNKNOWN rather than being guessed into a tradeable answer.
_ENRICHED = {
    "oi_cleared": ("oi_cleared_fraction", "oi_change_frac"),
    "funding": ("funding_rate", "funding"),
    "volume_multiple": ("volume_multiple",),
    "liquidation_notional": ("liquidation_notional", "liquidations"),
    "spread_multiple": ("spread_multiple",),
    "cross_venue_divergence": ("cross_venue_divergence",),
    "breadth_down": ("breadth_down",),
}


def _oi_cleared_series(symbol: str, index: Any) -> np.ndarray | None:
    """Fraction of open interest destroyed over the trailing window, aligned to the bar index.

    ONLY WHERE THE ARCHIVE ACTUALLY COVERS THE BAR. The desk began snapshotting OI on a date, so
    every decline before that date has no OI evidence and MUST stay unclassified -- returning 0.0
    there would be a measured "no OI was cleared", which reads as evidence AGAINST a cascade
    rather than as absence of evidence. NaN is carried through instead, and `_at` in the detector
    leaves the field at its UNMEASURED default for those bars.

    The drop is measured peak-to-trough over a trailing window rather than day-over-day: a cascade
    clears OI across the whole fall, and a single-day difference would miss a two-day flush and
    understate every one of them.
    """
    if not _OI_ARCHIVE.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_parquet(_OI_ARCHIVE)
        rows = df[df["symbol"] == symbol]
        if rows.empty or "open_interest" not in rows.columns:
            return None
        s = (rows.set_index(pd.to_datetime(rows["ts"], utc=True))["open_interest"]
             .astype("float64").sort_index())
        s = s[~s.index.duplicated(keep="last")]
        idx = pd.to_datetime(index, utc=True)
        aligned = s.reindex(idx.normalize(), method=None)
        peak = aligned.rolling(7, min_periods=2).max()
        cleared = (peak - aligned) / peak.where(peak > 0)
        return np.asarray(cleared.to_numpy(), dtype="float64")
    except Exception:
        # Reported by absence, never by a zero: an unreadable archive must not manufacture the
        # claim that no open interest was cleared.
        return None


def _column(df: Any, names: tuple[str, ...]) -> np.ndarray | None:
    for n in names:
        if n in getattr(df, "columns", []):
            return np.asarray(df[n].to_numpy(), dtype="float64")
    return None


def _volume_multiple(df: Any) -> np.ndarray | None:
    """Volume as a multiple of its own trailing median -- derived, because the raw column exists
    in every lake and the multiple exists in none."""
    if "volume" not in getattr(df, "columns", []):
        return None
    v = np.asarray(df["volume"].to_numpy(), dtype="float64")
    if v.size < 30:
        return None
    med = np.array([np.median(v[max(0, i - 29):i + 1]) or 1.0 for i in range(v.size)])
    return np.where(med > 0, v / med, 1.0)


def detect_for(symbol: str, df: Any) -> list[Any]:
    close = np.asarray(df["close"].to_numpy(), dtype="float64")
    kw: dict[str, Any] = {}
    for arg, names in _ENRICHED.items():
        col = _column(df, names)
        if col is not None:
            kw[arg] = col
    if "volume_multiple" not in kw:
        vm = _volume_multiple(df)
        if vm is not None:
            kw["volume_multiple"] = vm
    if "oi_cleared" not in kw:
        oi = _oi_cleared_series(symbol, df.index)
        if oi is not None:
            kw["oi_cleared"] = oi
    return detect_declines(close, symbol=symbol, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT,XRPUSDT")
    ap.add_argument("--horizon", type=int, default=24)
    ap.add_argument("--screen", action="store_true",
                    help="also run the signal through the canonical Stage-A gate")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    try:
        from libs.autodiscovery.crypto_adapter import _read_frames
        from libs.data.timeframe import Timeframe
        frames = _read_frames(symbols, Timeframe.D1, _LAKE)
    except Exception as exc:
        frames = {}
        print(f"decline-detection: lake unreadable ({type(exc).__name__}: {exc}) -- "
              "UNMEASURED, and no artifact is written. An empty events file would read as "
              "'no declines happened', which is a different and false claim.")
        return 1

    all_events: list[dict[str, Any]] = []
    history: dict[str, list[tuple[float, float, float]]] = {}
    per_symbol: dict[str, Any] = {}
    for sym in symbols:
        df = frames.get(sym)
        # ROW COUNT, NOT COLUMN PRESENCE. The lake returns a well-formed EMPTY DataFrame with the
        # right five columns when a symbol has no partitions, so a column check passes and the
        # symbol reports "0 declines" -- absence resolving to a measurement (WS-005), and the
        # artifact would then claim no decline ever happened rather than that nothing was read.
        if df is None or "close" not in getattr(df, "columns", []) or len(df) == 0:
            per_symbol[sym] = {"status": "ABSENT"}
            continue
        found = detect_for(sym, df)
        close = np.asarray(df["close"].to_numpy(), dtype="float64")
        for mech, rows in conditional_history(found, close, horizon=args.horizon).items():
            history.setdefault(mech, []).extend(rows)
        for d in found:
            row = asdict(d.event)
            row["mechanism"] = d.mechanism
            all_events.append(row)
        per_symbol[sym] = summarise(found)

    if not any(v.get("status") != "ABSENT" for v in per_symbol.values()):
        print("decline-detection: no symbol had readable bars -- UNMEASURED, nothing written")
        return 1

    payload = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "events": all_events,
        "history": {k: [list(x) for x in v] for k, v in history.items()},
        "per_symbol": per_symbol,
        "horizon_bars": args.horizon,
        "note": ("Input for libs/research/drawdown_rebound via run_opportunity_books. `history` is "
                 "measured from each event's CONFIRMATION bar, never its low: the low is knowable "
                 "only in hindsight, and measuring from it would flatter every number by exactly "
                 "the part of the move no strategy could have captured."),
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=1), "utf-8")

    n_act = sum(int(v.get("n_actionable", 0)) for v in per_symbol.values()
                if isinstance(v, dict))
    print(f"decline-detection: {len(all_events)} decline(s) across {len(symbols)} symbol(s); "
          f"{n_act} actionable -> {_OUT}")
    for sym, s in per_symbol.items():
        if isinstance(s, dict) and s.get("n_declines"):
            print(f"  {sym:<10} {s['n_declines']:>3} declines  {s['by_mechanism']}")
    if not n_act:
        print("  NONE ACTIONABLE -- expected without OI/funding/volume: the classifier refuses to "
              "name a cascade without positive evidence, and an unclassified dip is not tradeable.")

    if args.screen:
        _screen(symbols, frames, args.horizon)
    return 0


def _screen(symbols: list[str], frames: dict[str, Any], horizon: int) -> None:
    """Run the per-bar signal through the canonical Stage-A gate. Earns a clock, never capital."""
    from libs.research.axis_screen import stage_a_screen

    for sym in symbols:
        df = frames.get(sym)
        if df is None or "close" not in getattr(df, "columns", []) or len(df) == 0:
            continue
        close = np.asarray(df["close"].to_numpy(), dtype="float64")
        found = detect_for(sym, df)
        sig = rebound_signal(close.size, found)
        if sig.sum() < 3:
            print(f"  screen {sym}: {int(sig.sum())} actionable event(s) -- too few to screen. "
                  "UNDERPOWERED is the verdict, not a weak edge.")
            continue
        fwd = np.zeros_like(close)
        fwd[:-1] = close[1:] / close[:-1] - 1.0
        res = stage_a_screen(sig, fwd, name=f"dip_rebound_{sym.lower()}",
                             horizon_days=1.0, target_symbol=sym)
        print(f"  screen {sym}: {res.get('verdict')} ic={res.get('ic')} "
              f"sharpe={res.get('sharpe')}")


if __name__ == "__main__":
    raise SystemExit(main())
