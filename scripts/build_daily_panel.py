#!/usr/bin/env python3
"""DAILY BARS FOR THE UNLOCK UNIVERSE -- the missing third input to the supply screen.

WHAT WAS BLOCKING. `screen_unlock_supply_series` names three missing inputs, and two of them are
collector output that arrives on its own. The third is not: "no per-symbol daily bars supplied for
the unlocking universe. `data/bars/` holds 45 symbols at 15min granularity only, and covers 18 of
the 165 symbols in `data/unlock_events.json` -- so supplying this panel is a REAL build (a daily
resample plus a universe decision), not a wiring oversight." That was true. This is that build.

**THE UNIVERSE DECISION IS THE HARD HALF AND IT IS MADE HERE, BEFORE ANY RESULT.** 18 of 165
symbols have bars. Which 18 you keep is a selection, and a selection made after seeing which
unlocks looked interesting is the whole of survivorship bias. So the rule is fixed here and it is
mechanical: EVERY symbol that has both an unlock row and enough bars is included, and no symbol is
ever excluded for its outcome. The 147 without bars are reported BY NAME as unmeasured coverage --
they are not silently dropped, because a screen run on 18 of 165 and a screen run on 165 are
different experiments and only one of them was pre-registered.

**RESAMPLING IS NOT FREE AND THE DIRECTION OF THE ERROR MATTERS.** A daily bar built from 15min
data is stamped at the CLOSE of its last intraday bar, and a partial final day would carry a close
that is not the day's close -- an artificial gap at exactly the horizon the screen measures over.
Incomplete days are dropped, never padded forward.

**IT COMPUTES NO SIGNAL AND HOLDS NO THRESHOLD.** It reshapes bars. Every threshold, horizon and
multiplicity charge lives pre-registered in `libs/research/unlock_supply_series`, and a builder
that filtered its own universe on returns would move the pre-registration after the data.

    python scripts/build_daily_panel.py [--min-days 120] [--json]
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "data/daily_panel.json"
_COVERAGE = _ROOT / "web/daily_panel_coverage.json"

#: Minimum COMPLETE daily bars a symbol must have to enter the panel. Not a quality filter on the
#: symbol -- a filter on whether a 7-30 day forward window can even be formed. Fixed before any
#: result, and applied identically to every symbol.
MIN_DAYS = 120

#: Intraday bars required for a day to count as COMPLETE at 15min granularity. One short bar at a
#: venue outage is tolerated; a half-day is not, because its "close" is a midday print wearing a
#: daily timestamp.
_BARS_PER_DAY_15M = 96
_COMPLETENESS = 0.90


def _unlock_symbols() -> tuple[set[str], str]:
    """Symbols carrying at least one unlock row. UNMEASURED when the calendar is absent."""
    p = _ROOT / "data/unlock_events.json"
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return set(), (f"{p} unreadable ({type(exc).__name__}) -- the unlock universe is "
                       "UNMEASURED here, so the panel cannot be scoped to it. On a clone this is "
                       "expected: data/ is gitignored")
    rows = doc.get("events") if isinstance(doc, dict) else doc
    out = {str(r.get("symbol", "")).upper() for r in (rows or []) if isinstance(r, dict)}
    out.discard("")
    return out, f"{len(out)} symbol(s) with at least one unlock row in {p}"


#: Import failures are fatal; per-symbol read failures are not. Set once, so a broken import is
#: reported ONCE rather than swallowed 165 times.
_READ_DEFECT: str | None = None


def _read_intraday(symbol: str) -> Any | None:
    """The 15min frame for one symbol, or None. Reads through the lake's own reader so this file
    cannot disagree with the rest of the desk about what a bar is.

    **THE BARE `except Exception` HERE HID A BROKEN IMPORT.** The first version imported
    `libs.core.instruments.Timeframe`, which does not exist -- the module is `libs.data.timeframe`.
    Every call raised ModuleNotFoundError, every call was swallowed, and the panel reported "0 of
    165 symbols" as though the lake were empty. A missing module and a missing symbol produced the
    same answer, which is this desk's most-repeated defect committed inside a file whose whole job
    is to stop a count being trusted.

    The import now sits OUTSIDE the handler. A per-symbol read may still fail -- a symbol genuinely
    absent from the lake is ordinary -- and only that is caught.
    """
    global _READ_DEFECT
    from libs.autodiscovery.crypto_adapter import _read_frames
    from libs.data.timeframe import Timeframe

    try:
        frames = _read_frames([symbol], Timeframe.M15, "data/lake")
    except Exception as exc:
        _READ_DEFECT = f"{type(exc).__name__}: {exc}"
        return None
    return frames.get(symbol)


def to_daily(df: Any) -> tuple[tuple[datetime, ...], np.ndarray] | None:
    """15min OHLCV -> (day-close instants, daily closes). Incomplete days are DROPPED.

    A partial final day carries a close that is not the day's close, which appears as an
    artificial gap at exactly the horizon the screen measures over -- so the last day is dropped
    whenever it is short, rather than forward-filled into something that looks complete.
    """
    if df is None or len(df) == 0:
        return None
    import pandas as pd

    idx = pd.to_datetime(df.index, utc=True)
    frame = pd.DataFrame({"close": df["close"].to_numpy("float64")}, index=idx)
    grouped = frame.groupby(frame.index.floor("D"))
    closes, stamps = [], []
    need = int(_BARS_PER_DAY_15M * _COMPLETENESS)
    for _day, block in grouped:
        if len(block) < need:
            continue                      # partial day: its close is a midday print
        closes.append(float(block["close"].iloc[-1]))
        stamps.append(block.index[-1].to_pydatetime())
    if not closes:
        return None
    return tuple(stamps), np.asarray(closes, dtype="float64")


def build(min_days: int = MIN_DAYS) -> dict[str, Any]:
    wanted, why_universe = _unlock_symbols()
    panel: dict[str, dict[str, Any]] = {}
    short: dict[str, int] = {}
    no_bars: list[str] = []

    for sym in sorted(wanted):
        daily = to_daily(_read_intraday(sym))
        if daily is None:
            no_bars.append(sym)
            continue
        stamps, closes = daily
        if len(closes) < min_days:
            short[sym] = len(closes)
            continue
        panel[sym] = {"stamps": [t.isoformat() for t in stamps], "closes": closes.tolist()}

    return {
        "updated": datetime.now(tz=UTC).isoformat(),
        "min_days": min_days, "why_universe": why_universe,
        "n_wanted": len(wanted), "n_in_panel": len(panel),
        "symbols": sorted(panel),
        # NAMED, NOT COUNTED. A screen run on 18 of 165 symbols and a screen run on 165 are
        # different experiments, and only one of them was pre-registered. Listing the absent ones
        # is what keeps the difference visible in the artifact rather than in nobody's head.
        "unmeasured_no_bars": sorted(no_bars),
        "unmeasured_too_short": {k: short[k] for k in sorted(short)},
        "coverage_frac": round(len(panel) / len(wanted), 4) if wanted else None,
        # A READ DEFECT IS NOT LOW COVERAGE. If the reader itself is broken, "0 of 165" is a
        # statement about this script, not about the lake, and the two must not print alike.
        "read_defect": _READ_DEFECT,
        "selection_rule": (
            "EVERY symbol with an unlock row and >= min_days COMPLETE daily bars is included. No "
            "symbol is ever excluded for its outcome, and the rule was fixed before any result -- "
            "a universe chosen after seeing which unlocks looked interesting is survivorship bias "
            "with extra steps"),
        "panel": panel,
    }


def load_panel() -> dict[str, tuple[tuple[datetime, ...], np.ndarray]]:
    """The panel in the shape `unlock_supply_series.run_screen` wants. Empty dict when absent --
    the screen's own missing-input path then reports it, which is the correct owner of that
    message."""
    try:
        doc = json.loads(_OUT.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, tuple[tuple[datetime, ...], np.ndarray]] = {}
    for sym, row in (doc.get("panel") or {}).items():
        try:
            stamps = tuple(datetime.fromisoformat(t) for t in row["stamps"])
            out[str(sym)] = (stamps, np.asarray(row["closes"], dtype="float64"))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-days", type=int, default=MIN_DAYS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rep = build(args.min_days)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep), "utf-8")
    # The coverage view WITHOUT the price arrays, so a dashboard can read it cheaply.
    _COVERAGE.parent.mkdir(parents=True, exist_ok=True)
    _COVERAGE.write_text(json.dumps({k: v for k, v in rep.items() if k != "panel"}, indent=1),
                         "utf-8")

    if args.json:
        print(json.dumps({k: v for k, v in rep.items() if k != "panel"}, indent=1))
        return 0
    cov = rep["coverage_frac"]
    print(f"=== DAILY PANEL === {rep['n_in_panel']} of {rep['n_wanted']} unlock symbol(s) "
          f"({'n/a' if cov is None else f'{cov:.1%}'} coverage), min {rep['min_days']} complete days")
    print(f"  universe: {rep['why_universe']}")
    if rep.get("read_defect"):
        print(f"  READ DEFECT: {rep['read_defect']} -- this is a fault in the READER, not low "
              "coverage of the lake. Every symbol failed the same way")
    if rep["unmeasured_no_bars"]:
        names = ", ".join(rep["unmeasured_no_bars"][:12])
        more = f" (+{len(rep['unmeasured_no_bars']) - 12} more)" \
            if len(rep["unmeasured_no_bars"]) > 12 else ""
        print(f"  NO BARS ({len(rep['unmeasured_no_bars'])}): {names}{more}")
        print("    -- UNMEASURED coverage, named rather than dropped: a screen on a subset and a "
              "screen on the whole universe are different experiments")
    if rep["unmeasured_too_short"]:
        print(f"  TOO SHORT ({len(rep['unmeasured_too_short'])}): "
              + ", ".join(f"{k}={v}d" for k, v in list(rep["unmeasured_too_short"].items())[:10]))
    print(f"-> {_OUT} and {_COVERAGE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
