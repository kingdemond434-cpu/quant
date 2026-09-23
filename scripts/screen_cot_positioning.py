#!/usr/bin/env python3
"""STAGE-A SCREEN: CFTC SPECULATOR POSITIONING vs FORWARD RETURNS ON THE MT5 UNIVERSE (R0562).

WHY THIS EXISTS. `libs/data/cot_source.py` is a free, weekly, correctly-lagged public-API data
axis with EIGHTEEN PASSING TESTS AND ZERO PRODUCTION CONSUMERS. It had two importers,
scripts/log_swaps.py and scripts/run_mt5_portfolio.py, and both were dead MT5-stack scripts
nothing invoked (R0421) -- so it looked wired while being unreachable for months. An unwired free
data axis is idle capacity (L1.28a), and this one is idle on the desk's own primary market.

THE ROW OFFERED THREE EXITS AND THE MANDATE CLOSED TWO OF THEM. R0562 was raised 2026-08-13 and
said: wire it to a screen, REMAP IT TO CRYPTO CONTRACTS, or record it dormant. Five days later the
principal's MT5 UNIVERSE MANDATE (2026-08-18) made the desk's primary universe the full
MT5/Fusion market and closed every exchange-native market to it -- which makes that remap illegal
and makes `COT_MAP`'s existing keying, already XAUUSD/EURUSD/XTIUSD and nine more, exactly
right. Dormant was the third exit and it is not available either: all eleven mapped
instruments carry D1 bars in this desk's own lake, and the CFTC endpoint answered on 2026-08-20
with a report dated 2026-08-11. Nothing is missing. So: wire it.

THE MECHANISM, AND WHO IS FORCED TO TRADE AGAINST IT (no mechanism means overfit -- a hard kill,
not a discount). CFTC non-commercial ("large speculator") net positioning as a share of open
interest measures how crowded the leveraged, discretionary side of a futures market is. The
counterparty is the COMMERCIAL hedger, who is short the future because they are long the physical
and CANNOT STOP: a gold miner, an oil producer, an exporter with receivables in EUR. That is the
structural forced-trader this desk requires before spending compute. The premium is paid when
crowding unwinds -- spec longs are margined and exit on adverse moves, so an extreme reads as a
depleted marginal buyer. It is a SLOW mechanism (weekly data, positions built over months), which
is why the horizons below are 5d and 20d and NOT next-day.

TIMESTAMP ALIGNMENT, DECLARED (L1.46). The CFTC series is a TUESDAY snapshot published the
following FRIDAY ~15:30 ET. `cot_source.cot_zscore_daily` applies `.shift(1)` on the WEEKLY index
before the daily forward-fill, so a Tuesday-t snapshot first becomes visible on Tuesday t+1 -- a
full week, roughly four days MORE conservative than the real publication lag. The error is
therefore in the safe direction by construction, and the screen understates any true edge rather
than manufacturing one. MT5 D1 bars are Mon-Fri; the COT value is forward-filled onto them, which
stale-repeats within each week and inflates signal autocorrelation. DECLARED, and it is why the
screen is scored on a NON-OVERLAPPING h-day grid with `overlap_periods=1.0`.

EVERY CONSTRUCTION TRIED IS LOGGED, INCLUDING THE LOSERS (the garden-of-forking-paths rule). Two
target constructions x two horizons = four pre-declared cells, all four reported:
  ABSOLUTE  per-instrument forward return   -- the timing reading of the mechanism
  RELATIVE  cross-sectionally demeaned      -- the asset-selection reading
  h = 5d, 20d
Reporting the best cell without counting the others is p-hacking, so all four are DSR-counted
trials and the count is in the artifact.

STAGE A ONLY -- ZERO PROMOTION AUTHORITY. Nothing here reaches capital. A SCREEN-INTERESTING cell
earns a pre-registered forward clock and nothing else; SCREEN-WEAK is graveyard-grade negative
knowledge and is a first-class deliverable. Breadth is MEASURED per cell via
`panel_breadth.measure_panel_breadth` (L1.62): omitting it would leave every cell on the
conservative full-K divisor, unable to be `powered`, and therefore unable to refute anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
from libs.data.cot_source import COT_MAP, cot_zscore_daily  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.research.panel_breadth import measure_panel_breadth  # noqa: E402

OUT = _ROOT / "reports/axis_screens/cot_positioning.json"

#: The mechanism is slow -- weekly data, positions accumulated over months -- so next-day is the
#: wrong horizon and is deliberately absent. Testing it anyway would spend a DSR trial on a cell
#: the mechanism does not predict (the target/horizon-sweep duty is about MECHANISM-appropriate
#: horizons, not about sweeping everything and keeping the best).
HORIZONS_D = (5, 20)

#: Where the lake's D1 bars for the mapped instruments live. All three classes are MT5-native.
CLASSES = ("fx", "metal", "energy")

#: Screened from 2010: the CFTC legacy series runs to the 1980s, but the desk's lake histories are
#: staggered and the 3-year rolling z needs 156 weekly points before it emits anything at all.
SINCE = "2010-01-01"


def load_closes(classes: tuple[str, ...], since: str, lake_root: Path) -> pd.DataFrame:
    """Aligned D1 closes for the mapped instruments, oldest first, from the desk's own lake.

    EVERY LAKE SYMBOL IS REGISTERED BEFORE IT IS READ. `lake.read_bars` goes through
    `instruments.get_spec`, whose built-in catalogue holds eight symbols while the lake holds 88 --
    so an unregistered instrument raises inside the reader and the data reads as ABSENT while
    sitting on disk. That exact gap made an MT5 loader report 6 of 68 readable until 2026-08-19.
    """
    from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
    from libs.data.lake import Layer, ParquetLake
    from libs.data.timeframe import Timeframe

    lake = ParquetLake(str(lake_root))
    cut = pd.Timestamp(since, tz="UTC")
    cols: dict[str, pd.Series] = {}
    missing: list[str] = []
    for sym in COT_MAP:
        found = False
        for cls in classes:
            d = lake_root / "bronze" / cls / sym / Timeframe.D1.value
            if not d.exists():
                continue
            register_instrument(InstrumentSpec(symbol=sym, asset_class=AssetClass(cls),
                                               description=sym))
            frame = lake.read_bars(Layer.BRONZE, sym, Timeframe.D1)
            idx = pd.to_datetime(pd.Series(frame["timestamp"]), utc=True)
            s = pd.Series(np.asarray(frame["close"], dtype="float64"), index=idx).sort_index()
            cols[sym], found = s[s.index >= cut], True
            break
        if not found:
            missing.append(sym)
    if missing:
        # NAMED, NEVER SILENT (L1.60). A mapped instrument absent from the lake is a coverage fact
        # the reader needs; dropping it quietly makes "out of universe" and "unreadable" identical.
        print(f"lake: {len(missing)} mapped instrument(s) absent -- {', '.join(missing)}")
    return pd.DataFrame(cols).sort_index()


def cells(z: pd.DataFrame, closes: pd.DataFrame) -> list[dict[str, Any]]:
    """One screened cell per (construction, horizon). All four reported, winners and losers."""
    out: list[dict[str, Any]] = []
    for h in HORIZONS_D:
        # NON-OVERLAPPING h-day grid. Sampling every h-th row makes the rows time-independent, so
        # the screen is told overlap_periods=1.0 -- deflating by horizon_days on top of an already
        # non-overlapping grid would double-count the very dependence the sampling removed.
        fwd = (closes.shift(-h) / closes - 1.0).iloc[::h]
        sig = z.reindex(fwd.index)
        for construction in ("absolute", "relative"):
            tgt = fwd.sub(fwd.mean(axis=1), axis=0) if construction == "relative" else fwd
            pair = (sig.to_numpy(), tgt.to_numpy())
            ok = np.isfinite(pair[0]) & np.isfinite(pair[1])
            if ok.sum() < 200:
                out.append({"cell": f"{construction}_{h}d", "verdict": "SCREEN-UNMEASURABLE",
                            "why": f"only {int(ok.sum())} paired observations"})
                continue
            breadth = measure_panel_breadth(*pair)
            flat_s, flat_t = pair[0][ok], pair[1][ok]
            rep = stage_a_screen(
                flat_s, flat_t, name=f"cot_positioning_{construction}_{h}d",
                horizon_days=float(h), overlap_periods=1.0,
                panel_width=int(sig.shape[1]),
                xs_neff=breadth.xs_neff if breadth.measured else None,
                target_symbol=f"MT5:{construction}")
            rep["cell"] = f"{construction}_{h}d"
            rep["breadth"] = {"xs_neff": breadth.xs_neff, "measured": breadth.measured,
                              "n_symbols": breadth.n_symbols,
                              "n_symbols_declared": breadth.n_symbols_declared,
                              "mean_corr": breadth.mean_corr, "floor": breadth.floor,
                              "dropped": breadth.dropped, "why": breadth.why}
            out.append(rep)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default=SINCE)
    ap.add_argument("--lake", default=str(_ROOT / "data/lake"),
                    help="lake root. Defaults to this tree's, which in a WORKTREE is usually "
                         "partial or absent -- data/ is gitignored, so a worktree run must be "
                         "pointed at the tree that owns the lake or it will refuse (which is the "
                         "correct outcome: a worktree-blind screen fabricates verdicts)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    _law_guard()

    closes = load_closes(CLASSES, args.since, Path(args.lake))
    if closes.empty:
        print("REFUSED: no mapped instrument readable from the lake -- this is a MISSING INPUT, "
              "not an empty result, and it may not be recorded as a screen (L1.28a)",
              file=sys.stderr)
        return 2

    z = cot_zscore_daily(list(closes.columns), closes.index)
    z = z.dropna(axis=1, how="all")
    if z.empty:
        print("REFUSED: the CFTC fetch returned no usable series for any mapped instrument",
              file=sys.stderr)
        return 2
    closes = closes[list(z.columns)]

    screened = cells(z, closes)
    report = {
        "axis": "cot_positioning",
        "at": datetime.now(tz=UTC).isoformat(),
        "universe": list(z.columns),
        "n_instruments": int(z.shape[1]),
        "since": args.since,
        "lake": args.lake,
        "bars": int(closes.shape[0]),
        "trials_declared": len(HORIZONS_D) * 2,
        "trials_screened": len(screened),
        "source": "publicreporting.cftc.gov legacy futures-only, non-commercial % of OI",
        "alignment": "Tuesday snapshot, weekly .shift(1) then daily ffill -- ~4 days MORE "
                     "conservative than the Friday publication, so error is in the safe direction",
        "promotion_authority": "NONE. Stage A. A SCREEN-INTERESTING cell earns a pre-registered "
                               "forward clock and nothing else (two-stage discovery law).",
        "cells": screened,
    }
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1) + "\n", "utf-8")

    print(f"cot_positioning: {z.shape[1]} instruments, {closes.shape[0]} bars, "
          f"{len(screened)} cells -> {path}")
    for c in screened:
        print(f"  {c['cell']:16s} {c.get('verdict', '?'):22s} "
              f"IC={c.get('ic', float('nan')):+.4f} "
              f"sh_mom={c.get('sharpe_momentum')} sh_rev={c.get('sharpe_reversal')} "
              f"n_eff={c.get('n_eff')} powered={c.get('powered')} "
              f"breadth={c.get('breadth', {}).get('xs_neff')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
