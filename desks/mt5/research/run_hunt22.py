"""Hunt #22: EVENT-HOUR EFFECTS (docs/NEWS_LINEAGE.md NEWS_034/035/036 precursor).

Honest label: event-TIME effects, no surprise conditioning yet (no licensed
calendar source on the box). Uses US macro-release windows:
  - 08:30 ET window -> UTC hours 12 (EDT) and 13 (EST)
  - 14:00 ET window (FOMC/2pm) -> UTC hours 18 (EDT) and 19 (EST)
Families (per symbol, direction decided by the initial bar move):
  usmacro_drift   after the 08:30-window bar, trade in the direction of its
                  initial reaction (continuation), hold 4 bars
  usmacro_rev     opposite (initial-reaction reversal)
  us1400_drift    same for the 14:00 window
  us1400_rev      same, reversal
No survivor claims here: universal_gate.py 10-gate pass is the only gate.
Marker reports/DONE_hunt22.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest  # noqa: E402
from run_hunt17 import _atr, resample  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
ATR_K = 1.2
WINDOWS = {"usmacro": (12,), "us1400": (16,)}  # H4 bars: hour 12 contains 08:30 ET
# (12:30/13:30 UTC); hour 16 bar contains 14:00 ET (18:00/19:00 UTC)


def _sig(t, side, ref, atr_v, rr=1.5, ttl=4, tag=""):
    risk = atr_v * ATR_K
    if risk <= 0 or risk != risk:
        raise ValueError("no atr")
    return Signal(time=t, side=side, stop=ref - side * risk,
                  target=ref + side * risk * rr, ttl_bars=ttl, tag=tag)


def _event_sigs(h4, win_hours: tuple, mode: str, rr=1.5, ttl=4, tag=""):
    c = h4["close"].to_numpy(float)
    o = h4["open"].to_numpy(float)
    a = _atr(h4, 14)
    out = []
    for i in range(2, len(h4) - 1):
        if h4.index[i - 1].hour not in win_hours:
            continue
        move = c[i - 1] - o[i - 1]
        if abs(move) <= 0:
            continue
        side = 1 if move > 0 else -1
        if mode == "drift":
            pass  # trade the initial move direction
        else:  # reversal
            side = -side
        try:
            out.append(_sig(h4.index[i], side, float(c[i]), float(a.iloc[i]), rr, ttl, tag))
        except ValueError:
            pass
    return out


FAMILIES = {
    "usmacro_drift": lambda h4, d1, side: _event_sigs(h4, WINDOWS["usmacro"], "drift", tag="usmacro_drift"),
    "usmacro_rev": lambda h4, d1, side: _event_sigs(h4, WINDOWS["usmacro"], "rev", tag="usmacro_rev"),
    "us1400_drift": lambda h4, d1, side: _event_sigs(h4, WINDOWS["us1400"], "drift", tag="us1400_drift"),
    "us1400_rev": lambda h4, d1, side: _event_sigs(h4, WINDOWS["us1400"], "rev", tag="us1400_rev"),
}
SYMS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "EURJPY", "GBPJPY", "AUDUSD",
        "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURCHF", "AUDJPY", "CADJPY",
        "NZDJPY", "CHFJPY", "BTCUSD", "ETHUSD", "AUDCAD", "AUDNZD", "NZDCAD", "XAGUSD"]


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))
    log = open(BASE / "logs" / "hunt22_console.txt", "w", encoding="utf-8")
    partial = BASE / "reports" / "hunt22_partial.json"
    done, results = [], []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text("utf-8"))
            done, results = saved.get("done", []), list(saved.get("all", []))
        except Exception:
            pass

    def tprint(*a) -> None:
        msg = " ".join(str(x) for x in a)
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    tprint(f"{'cell':<32} {'n':>5} {'exp':>7} {'t':>5} {'PF':>5} {'maxDD':>7}")
    for sym in SYMS:
        if not (UNI / f"{sym}_H1.parquet").exists():
            continue
        h1 = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
        h4, d1 = resample(h1)
        m = meta.get(sym, {})
        costs = Costs(spread_per_lot=0.48 if sym == "XAUUSD" else max(
            m.get("median_spread_pts", 1) * m.get("tick_size", 1e-5) * m.get("contract_size", 1e5),
            0.05), commission_per_lot=3.50, contract_oz=m.get("contract_size", 1e5))
        for fname, fn in FAMILIES.items():
            tag = f"{sym}.{fname}"
            if tag in done:
                continue
            sigs = fn(h4, d1, 1)
            if len(sigs) < 60:
                done.append(tag)
                continue
            r = run_backtest(h4, sigs, costs).stats()
            tprint(f"{tag:<32} {r['n']:5d} {r['expectancy_r']:+7.3f} {r['t_stat']:5.2f} "
                   f"{r['profit_factor']:5.2f} {r['max_dd_r']:7.1f}")
            results.append(dict(sym=sym, fam=fname, side="REACT", n=r["n"],
                                exp=r["expectancy_r"], t=r["t_stat"],
                                pf=r["profit_factor"], maxdd=r["max_dd_r"]))
            done.append(tag)
            partial.write_text(json.dumps({"done": done, "all": results}, indent=2),
                               encoding="utf-8")
    (BASE / "reports" / "hunt22.json").write_text(
        json.dumps({"survivors": [], "all": results,
                    "note": "EVENT-TIME effects only (no surprise conditioning); "
                            "survivor claims only via universal_gate.py 10-gate pass",
                    "swept_at": datetime.now(timezone.utc).isoformat()},
                   indent=2, default=str), encoding="utf-8")
    tprint(f"\n{len(results)} cells swept. Survivor claims pending universal 10-gate pass.")
    (BASE / "reports" / "DONE_hunt22").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")


if __name__ == "__main__":
    main()