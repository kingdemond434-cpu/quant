"""THE CROSS-EVENT EXCITATION MATRIX, MEASURED HOURLY (Roman row 0832, 2026-10-06).

Who excites whom, fitted on the desk's own bars with the shared multivariate Hawkes MLE in
`libs/research/point_process.py`:

  * WITHIN a symbol: the five bar events `families_roman.bar_events` defines (buy, sell, large
    print, spread depletion) plus vol shocks (|return| above 2.5 bipower sigma), so a reader can
    see whether depletion excites selling, or large prints excite jumps, on that instrument.
  * ACROSS assets: jumps on the US 10-year note, the dollar (EURUSD, oriented as USD strength) and
    gold on one hourly clock -- the row's "Treasury shock to USD to gold" chain. The row's crypto
    liquidation leg is out of scope (crypto exchanges are never hunted; Fusion CFDs carry no
    liquidation tape).

Called from `research/elitequant_breadth.py --once` (the hourly leg) inside its own time budget.
Writes `reports/CROSS_EXCITATION.json`: status RAN with one matrix per fitted set, or UNMEASURED
with the reason; a set whose bars or events are missing is listed with why, never dropped.
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import point_process as pp  # noqa: E402

OUT = BASE / "reports" / "CROSS_EXCITATION.json"
SYMBOLS = ("XAUUSD", "EURUSD", "USDJPY", "US500", "XTIUSD", "GER40")
#: The cross-asset chain: (symbol, orientation). EURUSD is inverted so its jump reads as USD.
CHAIN = (("UST10Y", 1), ("EURUSD", -1), ("XAUUSD", 1))
WINDOW = 3000
JUMP_K = 2.5


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _jumps(r: np.ndarray, n: int = 120) -> np.ndarray:
    ab = np.abs(r)
    bip = pd.Series(ab * np.roll(ab, 1)).rolling(n).mean().shift(1).to_numpy()
    sigma = np.sqrt(math.pi / 2.0 * bip)
    return (ab > JUMP_K * sigma) & np.isfinite(sigma) & (sigma > 0)


def _fit(masks: dict[str, np.ndarray], span: int) -> dict[str, Any]:
    names = [k for k, m in masks.items() if int(m.sum()) >= 5]
    missing = sorted(set(masks) - set(names))
    if len(names) < 2:
        return {"status": "UNMEASURED", "why": f"fewer than two event types with >= 5 events "
                                               f"(thin: {missing})"}
    times = np.concatenate([np.flatnonzero(masks[k]) for k in names]).astype(float)
    types = np.concatenate([np.full(int(masks[k].sum()), i) for i, k in enumerate(names)])
    f = pp.fit(times, types, d=len(names), span=float(span), max_events=2500)
    if f is None:
        return {"status": "UNMEASURED", "why": "the fit did not converge"}
    return {"status": "RAN", **pp.excitation_table(f, names),
            **({"thin_types_left_out": missing} if missing else {})}


def within_symbol(symbol: str) -> dict[str, Any]:
    from mt5desk import families_roman as rm
    from mt5desk.families import _h1
    from research import proposer_common as pc

    d = pc.bars(symbol)
    if d is None or len(d) < WINDOW:
        return {"status": "UNMEASURED", "why": "no H1 bars of the window's length"}
    h = _h1(d).iloc[-WINDOW:]
    ev = rm.bar_events(h)
    r = np.diff(np.log(h["close"].to_numpy(dtype=float)), prepend=np.nan)
    ev["vshock"] = _jumps(r)
    return _fit(ev, len(h))


def cross_asset() -> dict[str, Any]:
    from mt5desk import families_cross_sectional as xs

    series = {}
    for sym, _orient in CHAIN:
        got = xs._load_series(sym)
        if got is None:
            return {"status": "UNMEASURED", "why": f"no H1 bars for {sym}"}
        series[sym] = got
    hours = sorted(set().union(*(set((t // 3_600_000_000_000).tolist())
                                 for t, _ in series.values())))[-WINDOW:]
    grid = np.asarray(hours, dtype="int64")
    masks = {}
    for sym, orient in CHAIN:
        t, c = series[sym]
        h = t // 3_600_000_000_000
        s = pd.Series(np.log(c.astype(float)), index=h)
        s = s[~s.index.duplicated(keep="last")].reindex(grid)
        r = s.diff().to_numpy() * orient
        jumps = _jumps(np.nan_to_num(r, nan=0.0))
        masks[f"{sym}_jump"] = jumps & np.isfinite(r)
    return {**_fit(masks, len(grid)), "chain": [s for s, _ in CHAIN]}


def run(budget_s: float = 120.0, write: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    sets: dict[str, Any] = {}
    for sym in SYMBOLS:
        if time.monotonic() - started > budget_s:
            sets[sym] = {"status": "UNMEASURED", "why": "time budget reached; next pass"}
            continue
        try:
            sets[sym] = within_symbol(sym)
        except Exception as exc:
            sets[sym] = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}
    try:
        sets["chain:UST10Y->USD->XAUUSD"] = cross_asset()
    except Exception as exc:
        sets["chain:UST10Y->USD->XAUUSD"] = {"status": "UNMEASURED",
                                             "why": f"{type(exc).__name__}: {exc}"[:200]}
    ran = sorted(k for k, v in sets.items() if v.get("status") == "RAN")
    rep = {"generated_at": _now(), "row": "ROMAN-0832",
           "status": "RAN" if ran else "UNMEASURED", "ran": ran, "sets": sets,
           "window_bars": WINDOW, "seconds": round(time.monotonic() - started, 1),
           "method": "multivariate exponential Hawkes MLE, libs/research/point_process.py"}
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(rep, indent=1, sort_keys=True, default=str), "utf-8")
        tmp.replace(OUT)
    return rep


if __name__ == "__main__":
    out = run()
    print(f"cross_excitation: {out['status']} ran={out['ran']}")
