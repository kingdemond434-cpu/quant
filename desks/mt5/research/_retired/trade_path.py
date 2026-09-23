"""Trade-Path Desk seed: winner/loser path mining on the armed gold book.

For each trade: exit reason, holding time, MAE/MFE (R-units, bar-path approx),
session, convexity structure, and a rolling-expectancy decay scan (Regime Desk).

Approximations: trigger fills intrabar at the trigger level; MAE/MFE use the
bar path between entry bar and exit bar (high/low of bars in between, not
intrabar ticks). Everything below is evidence about the exit/payoff geometry
of the ALREADY-VALIDATED signal - it does not re-validate the signal itself.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
COSTS = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100)


def path_metrics(h1: pd.DataFrame, t) -> dict:
    lo = h1.index.get_indexer([t.entry_time], method="nearest")[0]
    hi = h1.index.get_indexer([t.exit_time], method="nearest")[0]
    seg = h1.iloc[lo : hi + 1]
    if len(seg) == 0:
        return {"mae_r": 0.0, "mfe_r": 0.0, "bars": 0}
    risk = abs(t.entry - t.stop)
    if risk <= 0:
        return {"mae_r": 0.0, "mfe_r": 0.0, "bars": len(seg)}
    if t.side > 0:
        mae = float((t.entry - seg["low"].min()) / risk)
        mfe = float((seg["high"].max() - t.entry) / risk)
    else:
        mae = float((seg["high"].max() - t.entry) / risk)
        mfe = float((t.entry - seg["low"].min()) / risk)
    return {"mae_r": mae, "mfe_r": mfe, "bars": len(seg)}


def main() -> None:
    h1 = pd.read_parquet(BASE / "data" / "universe" / "XAUUSD_H1.parquet")
    h1 = families._h1(h1)
    all_trades = []
    for win, p in WINDOWS.items():
        sigs = families.family_session_range_breakout(h1, **p)
        res = run_backtest(h1, sigs, COSTS)
        for t in res.trades:
            m = path_metrics(h1, t)
            all_trades.append(dict(
                win=win, r=t.r_multiple, reason=t.reason, hold_bars=t.bars_held,
                entry_hour=t.entry_time.hour, month=str(t.entry_time.to_period("M")),
                mae_r=m["mae_r"], mfe_r=m["mfe_r"]))
    df = pd.DataFrame(all_trades)
    n = len(df)
    out = [f"trades: {n}  exp_R: {df['r'].mean():+.3f}  PF: "
           f"{df[df.r>0].r.sum()/-df[df.r<0].r.sum():.2f}"]
    rs = df["r"].to_numpy()
    order = np.argsort(rs)[::-1]
    for q in (0.10, 0.05, 0.01):
        k = max(1, int(n * q))
        out.append(f"top {q*100:.0f}% ({k}) trades -> {rs[order[:k]].sum()/rs.sum()*100:.0f}% of total R")
    out.append(f"win_rate: {(rs>0).mean()*100:.1f}%  avg win {rs[rs>0].mean():+.2f}R  "
               f"avg loss {rs[rs<0].mean():+.2f}R  kurt {pd.Series(rs).kurt():.1f}")
    out.append("exit attribution:")
    for reason, g in df.groupby("reason"):
        out.append(f"  {reason:<10} n={len(g):5d}  share={len(g)/n*100:4.1f}%  "
                   f"exp={g['r'].mean():+.3f}  mean bars={g['hold_bars'].mean():5.1f}")
    out.append("MAE/MFE structure:")
    mae = df["mae_r"]; mfe = df["mfe_r"]
    out.append(f"  winners that touched <-0.5R before winning: {(mae[(rs>0)] < -0.5).mean()*100:.0f}%")
    out.append(f"  winners that touched <-1.0R before winning: {(mae[(rs>0)] < -1.0).mean()*100:.0f}%")
    out.append(f"  losers that were >+0.5R before losing:     {(mfe[(rs<0)] > 0.5).mean()*100:.0f}%")
    out.append(f"  losers that were >+1.0R before losing:     {(mfe[(rs<0)] > 1.0).mean()*100:.0f}%")
    out.append(f"  median MAE winners {mae[rs>0].median():+.2f}R  losers {mae[rs<0].median():+.2f}R")
    out.append(f"  median MFE winners {mfe[rs>0].median():+.2f}R  losers {mfe[rs<0].median():+.2f}R")
    out.append("by window:")
    for win, g in df.groupby("win"):
        out.append(f"  {win:<10} n={len(g):4d} exp={g['r'].mean():+.3f}  "
                   f"hit%={(g['r']>0).mean()*100:4.1f}  bars={g['hold_bars'].mean():5.1f}")
    out.append("decay scan (rolling 90-trade expectancy, full window stats):")
    rw = df["r"].rolling(90).mean()
    out.append(f"  full-sample exp {df['r'].mean():+.3f}  first-25% {df['r'].iloc[:max(1,int(n*.25))].mean():+.3f}  "
               f"last-25% {df['r'].iloc[-max(1,int(n*.25)):].mean():+.3f}")
    worst = df["r"].rolling(90).mean().min()
    out.append(f"  worst 90-trade rolling exp {worst:+.3f}  (never-below-zero: "
               f"{bool(worst > 0)})")
    text = "\n".join(out)
    print(text, flush=True)
    (BASE / "docs" / "TRADE_PATH_REPORT.md").write_text(
        f"# Trade-Path Desk: armed gold book path mining\n\n"
        f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} - {n} trades, "
        f"bar-path MAE/MFE approximation (intrabar unknown)._\n\n```\n{text}\n```\n",
        encoding="utf-8")
    (BASE / "reports" / "trade_path.json").write_text(
        json.dumps({"n": n, "exp_r": float(df["r"].mean()),
                    "by_reason": {r: dict(n=int(len(g)), exp=float(g["r"].mean()))
                                  for r, g in df.groupby("reason")},
                    "top10_pct_share": float(rs[order[:max(1, int(n*.1))]].sum() / rs.sum()),
                    "losers_plus1R": float((mfe[(rs<0)] > 1.0).mean()),
                    "winners_mae_neg1R": float((mae[(rs>0)] < -1.0).mean()),
                    "worst_90_rolling": float(worst),
                    "swept_at": datetime.now(timezone.utc).isoformat()},
                   indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()