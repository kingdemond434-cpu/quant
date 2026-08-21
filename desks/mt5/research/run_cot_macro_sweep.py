"""Test the desk's four existing COT-conditioned macro families, at the honest bar.

    python research/run_cot_macro_sweep.py

WHY THIS EXISTS NOW

`family2_cot_net_fade`, `family2_cot_change_fade`, `family2_cot_change_momentum` and
`family2_cot_comm_follow` in `mt5desk/families.py` are mature, well-specified macro
hypotheses -- crowding mean-reversion, crowding-unwind, momentum control, and following the
informed counterparty (commercials). They have never been run through the universal gate on
this clone; `reports/hunt2.json` etc. are gitignored and live on the VPS only, so whatever
verdict exists is not visible here.

Eight of the desk's 23 costable symbols map directly to COT data already on disk: AUDUSD,
USDCAD, USDCHF, GBPUSD, USDJPY, NZDUSD, XAUUSD, XAGUSD. 4 families x 8 symbols = 32 cells is a
real, standalone macro sweep this container can run without MT5.

THE SIGN CONVENTION, AND WHY GETTING IT WRONG IS WORSE THAN NOT TESTING

CFTC commodity futures are quoted "USD per unit of the foreign thing" for AUD, GBP, NZD, XAU
and XAG -- being long the future IS being long AUDUSD / GBPUSD / NZDUSD / XAUUSD / XAGUSD, so
`side=+1` from `_cot_entries` maps straight onto `side=+1` for those symbols.

CAD, CHF and JPY futures are quoted the SAME way -- USD per unit of foreign currency -- but the
MT5 symbols for them are inverted: USDCAD is USD-per-CAD's RECIPROCAL, base currency USD. Being
long CAD futures is being long CAD, which is being SHORT USDCAD. Running `_cot_entries`'
`side` unflipped on USDCAD would have gone long USDCAD every time the family wanted long CAD --
backwards on every single trade for three of the eight symbols, and it would not have crashed
or looked wrong; it would have produced a clean, confident, WRONG number. `SIGN_FLIP` below is
the correction, named per symbol so it is checkable rather than buried in arithmetic.

THE BAR IS NOT BORROWED FROM THE DESK'S OTHER SWEEPS. This is its own trial count -- 32 cells --
and its own deflation. Quoting the desk's 368-cell (or larger) bar here would be too lenient by
construction; quoting a smaller ad hoc number would be too lenient by intent. Both are the
"inflated" bar the standing order says to ignore. `multiplicity.deflation(32)` is what this
sweep actually costs and is the only honest number to clear.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=UserWarning)

import json  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from mt5desk.multiplicity import deflation  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
COT = BASE / "data" / "cot"

#: symbol -> COT parquet. Only symbols with BOTH tradable H1 history and matching COT data.
SYMBOL_COT = {
    "AUDUSD": "aud.parquet", "USDCAD": "cad.parquet", "USDCHF": "chf.parquet",
    "GBPUSD": "gbp.parquet", "USDJPY": "jpy.parquet", "NZDUSD": "nzd.parquet",
    "XAUUSD": "gold.parquet", "XAGUSD": "silver.parquet",
}

#: True where the MT5 symbol is the RECIPROCAL of the CFTC futures quoting convention. See the
#: module docstring -- getting this wrong silently reverses every trade for that symbol.
SIGN_FLIP = {"AUDUSD": False, "USDCAD": True, "USDCHF": True,
            "GBPUSD": False, "USDJPY": True, "NZDUSD": False,
            "XAUUSD": False, "XAGUSD": False}

FAMILIES = {
    "cot_net_fade": families.family2_cot_net_fade,
    "cot_change_fade": families.family2_cot_change_fade,
    "cot_change_momentum": families.family2_cot_change_momentum,
    "cot_comm_follow": families.family2_cot_comm_follow,
}


def _entry_of(sig) -> float:
    """Recover the entry price implied by a `_cot_entries` signal.

    `_cot_entries` builds `stop = entry - side*stop_dist` and `target = entry + side*stop_dist*rr`
    (default rr=1.6, unoverridden by any of the four families here) but does not store `entry`
    on the Signal itself. Both equations solve to `entry = stop + side*stop_dist`, and
    `target - stop = side*stop_dist*(rr+1)` gives `stop_dist` without needing it passed in.
    """
    stop_dist = abs(sig.target - sig.stop) / (1 + 1.6)
    return sig.stop + sig.side * stop_dist


def flip_side(sigs: list, symbol: str):
    """Reverse every signal's direction for a USDxxx-quoted symbol. See the module docstring.

    Rebuilds stop/target as the MIRROR of the original about the (recovered) entry, rather than
    swapping the stop/target fields -- swapping only works when the position is symmetric, and
    a mean-reversion vs. momentum family are not guaranteed to be.
    """
    if not SIGN_FLIP[symbol]:
        return sigs
    from dataclasses import replace                                  # noqa: PLC0415
    out = []
    for s in sigs:
        entry = _entry_of(s)
        out.append(replace(s, side=-s.side,
                           stop=2 * entry - s.stop, target=2 * entry - s.target))
    return out


def main() -> int:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    trials = len(FAMILIES) * len(SYMBOL_COT)
    bar = 1.96 + deflation(trials)
    print(f"COT macro sweep: {len(FAMILIES)} families x {len(SYMBOL_COT)} symbols = "
          f"{trials} cells")
    print(f"required t >= {bar:.2f} (deflated for {trials} trials -- this sweep's own count, "
          f"not borrowed from a larger one)\n")

    rows = []
    for sym, cot_file in SYMBOL_COT.items():
        p = UNI / f"{sym}_H1.parquet"
        if not p.exists() or sym not in meta:
            print(f"SKIP {sym}: no H1 parquet or not in universe.json")
            continue
        h1 = pd.read_parquet(p)
        cot = pd.read_parquet(COT / cot_file)
        costs = Costs.from_symbol(meta[sym], mult=2.0)

        for fname, fn in FAMILIES.items():
            sigs = flip_side(fn(h1, cot), sym)
            trades = run_backtest(h1, sigs, costs).trades
            n = len(trades)
            if n < 20:
                rows.append({"symbol": sym, "family": fname, "n": n, "t": float("nan"),
                            "exp": float("nan"), "verdict": "TOO FEW TRADES"})
                continue
            r = np.array([t.r_multiple for t in trades])
            t_stat = float(r.mean() / (r.std(ddof=1) / np.sqrt(n)))
            verdict = "SURVIVOR" if t_stat >= bar else "kill"
            rows.append({"symbol": sym, "family": fname, "n": n, "t": t_stat,
                        "exp": float(r.mean()), "verdict": verdict})

    print(f"{'symbol':<8} {'family':<20} {'n':>5} {'exp R':>8} {'t':>7}  verdict")
    for row in sorted(rows, key=lambda r: (-r["t"] if r["t"] == r["t"] else 999)):
        t_disp = f"{row['t']:7.2f}" if row["t"] == row["t"] else "    n/a"
        print(f"{row['symbol']:<8} {row['family']:<20} {row['n']:5d} "
              f"{row['exp']:+8.4f} {t_disp}  {row['verdict']}")

    survivors = [r for r in rows if r["verdict"] == "SURVIVOR"]
    print(f"\n{len(survivors)} of {len(rows)} cells clear t >= {bar:.2f}.")
    if not survivors:
        print("HONEST RESULT: none of these four macro hypotheses survive the desk's own "
              "multiplicity-corrected bar on this data. That is a real answer, not a failure "
              "of the sweep -- reporting a kill is what the bar is for.")
    out = BASE / "reports" / "cot_macro_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"trials": trials, "required_t": bar, "rows": rows}, indent=2),
                   encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
