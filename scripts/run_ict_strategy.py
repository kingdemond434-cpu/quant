#!/usr/bin/env python3
"""BACKTEST THE ICT SETUP AND AUDIT ITS OWN TRADE LIST WITH THE TOOL BUILT TO DOUBT OTHERS.

WHY IT AUDITS ITSELF. `scripts/audit_track_record.py` exists because a gold EA was advertised at
5-10%/week and the desk had no way to adjudicate it. A crypto ICT strategy built in response to
that claim, and then exempted from the same audit, would be the exact double standard the desk
keeps convicting other organs of. So every run here pushes its own closed trades through
`libs.validation.track_record` and prints the verdict alongside the equity curve. The expected and
correct result is NO-RISK-LOADING-FOUND -- sizing is fixed-fractional by construction -- and the
value is that a future edit which breaks that property fails loudly instead of producing a nicer
equity curve.

COSTS ARE ON BY DEFAULT, and that is not a detail. A 15-minute crypto setup strategy turning over
this often is decided by fees and slippage, not by the pattern: gross of costs is a number about
the detector, net of costs is a number about the desk. The default 5bp slippage plus taker fee is
deliberately pessimistic for a retail-size account on a liquid perp.

WHAT A GOOD RESULT HERE DOES NOT BUY. Nothing is promoted, pre-registered or sized from this
script. It is evidence for stage A, on one symbol, and the desk's prior is 420 candidates screened
and 420 rejected. A profitable curve here is the START of validation -- CPCV, Romano-Wolf, the
gauntlet -- not a substitute for it.

Read-only over bars. Writes one artifact. No keys, no order paths.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ict.strategy import ICTParams, schedule  # noqa: E402
from libs.validation.errors import ValidationError  # noqa: E402
from libs.validation.track_record import audit_trades  # noqa: E402

BARS = ROOT / "data/bars"
REPORT = ROOT / "data/ict_strategy.json"


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def load_bars(path: Path | None = None) -> tuple[pd.DataFrame | None, str]:
    """Bars from an explicit file or data/bars/, or an honest reason there are none.

    NEVER SYNTHESISED. A backtest run on generated data measures the generator, and the number it
    produces would enter the record wearing the same vocabulary as a real one.
    """
    if path is not None:
        if not path.exists():
            return None, f"{_rel(path)} does not exist"
        files = [path]
    else:
        if not BARS.exists():
            return None, (f"{_rel(BARS)} does not exist. data/ is gitignored, so this is expected "
                          "in a fresh checkout and a REAL blocker on the VPS -- run "
                          "scripts/build_bars.py against the recorder tape first.")
        files = sorted([*BARS.glob("*.parquet"), *BARS.glob("*.csv")])
        if not files:
            return None, f"no parquet/csv under {_rel(BARS)}"
    f = files[0]
    try:
        df = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f)
    except (OSError, ValueError) as e:
        return None, f"{f.name} unreadable: {str(e)[:100]}"
    need = {"open", "high", "low", "close"}
    if not need <= set(df.columns):
        return None, f"{f.name} lacks OHLC -- has {sorted(df.columns)[:8]}"
    return df, f.name


def trade_pnl(bars: pd.DataFrame, taken, cost_frac: float) -> tuple[np.ndarray, np.ndarray]:
    """(pnl per closed trade, size per trade) in equity-fraction terms, net of round-trip cost.

    ENTRY IS FILLED AT THE NEXT BAR'S OPEN, not at the signal bar's close. The strategy signals on
    a close and the engine executes on the following open, so pricing the fill at the close books
    a price the desk could not have got and quietly removes overnight/gap risk from every trade.
    It flatters the result, which is why it is the version that has to go.

    Exit is filled at the stop or target LEVEL, not at the extreme of the bar that touched it --
    filling at the extreme books the best price available inside a bar nobody could have timed.
    """
    open_, high, low, close = (bars["open"].to_numpy(), bars["high"].to_numpy(),
                               bars["low"].to_numpy(), bars["close"].to_numpy())
    n = len(bars)
    pnls, sizes = [], []
    for s in taken:
        if s.entry_i + 1 >= n:
            continue                       # signalled on the last bar: never filled, never counted
        risk_frac = abs(s.entry_price - s.stop) / s.entry_price
        if risk_frac <= 0:
            continue
        # Size uses the SIGNAL-time risk distance, which is what a live desk would have sized on.
        size = min(ICTParams().risk_fraction / risk_frac, ICTParams().max_leverage)
        fill = float(open_[s.entry_i + 1])
        exit_px = float(close[-1])
        for j in range(s.entry_i + 1, n):
            if s.direction > 0:
                if low[j] <= s.stop:
                    exit_px = s.stop
                    break
                if high[j] >= s.target:
                    exit_px = s.target
                    break
            else:
                if high[j] >= s.stop:
                    exit_px = s.stop
                    break
                if low[j] <= s.target:
                    exit_px = s.target
                    break
        gross = s.direction * (exit_px - fill) / fill
        pnls.append(size * (gross - 2.0 * cost_frac))     # in and out
        sizes.append(size)
    return np.asarray(pnls, dtype="float64"), np.asarray(sizes, dtype="float64")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars", default=None, help="explicit bar file; defaults to data/bars/")
    ap.add_argument("--cost-bps", type=float, default=7.5,
                    help="one-way cost in basis points (slippage + taker fee). Default 7.5bp.")
    ap.add_argument("--risk", type=float, default=0.01, help="fraction of equity risked per trade")
    ap.add_argument("--rr", type=float, default=2.0, help="target as a multiple of stop distance")
    ap.add_argument("--require-ote", action="store_true",
                    help="require the retrace to land in the 62-79%% OTE band")
    a = ap.parse_args()

    df, src = load_bars(Path(a.bars) if a.bars else None)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if df is None:
        out = {"ts": datetime.now(tz=UTC).isoformat(), "state": "NO BARS", "reason": src,
               "note": ("bars are NOT synthesised when absent -- a backtest on generated data "
                        "measures the generator, and its number would enter the record wearing "
                        "the same vocabulary as a real one")}
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
        print(f"ict-strategy: NO BARS -- {src}")
        return 0

    p = ICTParams(risk_fraction=a.risk, reward_multiple=a.rr, require_ote=a.require_ote)
    tgt, taken = schedule(df, p)
    cost = a.cost_bps / 10_000.0
    pnl, size = trade_pnl(df, taken, cost)

    out: dict = {
        "ts": datetime.now(tz=UTC).isoformat(), "source": src, "bars": len(df),
        "params": {"risk_fraction": p.risk_fraction, "reward_multiple": p.reward_multiple,
                   "setup_window": p.setup_window, "entry_window": p.entry_window,
                   "require_ote": p.require_ote, "cost_bps_one_way": a.cost_bps},
        "setups_completed": len(taken), "trades": int(pnl.size),
        "exposure_frac": float((tgt != 0).mean()),
        "authority": ("NONE. Stage-A evidence on one symbol. The desk's prior is 420 screened and "
                      "420 rejected; a good curve here is the START of validation, not a "
                      "substitute for it."),
    }

    if pnl.size >= 2:
        eq = float(np.prod(1.0 + pnl))
        out |= {
            "net_return_multiple": eq,
            "win_rate": float((pnl > 0).mean()),
            "mean_trade": float(pnl.mean()),
            "t_stat": float(pnl.mean() / (pnl.std(ddof=1) / np.sqrt(pnl.size)))
            if pnl.std(ddof=1) > 0 else 0.0,
        }
        # THE SELF-AUDIT. The tool built to doubt someone else's EA is pointed at our own trades.
        try:
            au = audit_trades(pnl, size, starting_equity=1.0, n_boot=500)
            out["self_audit"] = {"verdict": au.verdict, "escalation_ratio": au.escalation_ratio,
                                 "loss_depth_slope": au.loss_depth_slope,
                                 "ruin_probability": au.ruin_probability,
                                 "reasons": list(au.reasons)}
        except ValidationError as e:
            out["self_audit"] = {"verdict": "REFUSED", "why": str(e)}
    else:
        out["state"] = "TOO FEW TRADES"
        out["note"] = (f"{pnl.size} closed trade(s) -- an observation count is not a sample size, "
                       "and no return statistic computed on this would mean anything.")

    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    print(f"ict-strategy: {len(taken)} setups taken over {len(df)} bars from {src} "
          f"| exposure {out['exposure_frac']:.1%}")
    if pnl.size >= 2:
        print(f"  net x{out['net_return_multiple']:.3f} at {a.cost_bps}bp/side | "
              f"win {out['win_rate']:.1%} | t={out['t_stat']:.2f} on {pnl.size} trades"
              + ("" if abs(out["t_stat"]) >= 2 else "  <-- not distinguishable from zero"))
        sa = out.get("self_audit", {})
        print(f"  SELF-AUDIT: {sa.get('verdict')} "
              f"(escalation {sa.get('escalation_ratio'):.2f})"
              if isinstance(sa.get("escalation_ratio"), float) else
              f"  SELF-AUDIT: {sa.get('verdict')}")
    else:
        print(f"  {out.get('note')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
