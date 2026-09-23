"""Turn the XAU residual into a real sleeve, then decide it OUT OF SAMPLE.

residual_alpha.py established that fading the residual once |z| clears ~2 at a
4-bar horizon beats the round trip, and that a date-shuffled null does not. Two
things stood between that and a sleeve, and both are done here:

CHOOSING THE CELL COSTS SAMPLE, SO IT HAS TO BE PAID FOR

Twelve (horizon, threshold) cells were examined. Reporting the best of twelve at
its full-sample t is the oldest way to be wrong on this desk. The parameters are
therefore picked on the TRAIN half only and the verdict is read off the TEST
half, which the selection never saw. A cell that needs the test set to look good
did not survive; it was chosen.

THE SLEEVE MUST BE PRICED BY THE SAME ENGINE AS EVERY OTHER SLEEVE

A parallel P&L path would make this sleeve incomparable to the 1,384 cells the
book is already measured in, and incomparable is how a sleeve gets admitted on a
number nobody else was scored by. Signals go through run_backtest with
Costs.from_symbol(mult=2.0), so R means here what it means everywhere else.

Then admission: SR_new > SR_book * rho. This sleeve is near market neutral, so
the interesting quantity is not its Sharpe but its correlation to a book made
entirely of directional intraday cells -- a low rho is what makes a modest edge
worth owning, and the rule prices that directly.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families                                     # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest           # noqa: E402
from residual_alpha import BETA_WIN, Z_WIN, _panel, rolling_residual  # noqa: E402

UNI = _DESK / "data" / "universe"
OUT = _DESK / "reports" / "residual_sleeve.json"
TARGET = "XAUUSD"
TPY = 252.0
TRAIN_FRAC = 0.60
GRID = [(h, thr) for h in (1, 4, 12, 24) for thr in (1.5, 2.0, 2.5)]
STOP_ATR = 1.5
MIN_TRADES = 40


def build_z(target: str) -> tuple[pd.Series, pd.DataFrame]:
    panel = _panel(target)
    eps = rolling_residual(panel, target)
    mu = eps.rolling(Z_WIN).mean().shift(1)
    sd = eps.rolling(Z_WIN).std().shift(1)
    z = ((eps - mu) / sd).replace([np.inf, -np.inf], np.nan)
    return z, panel


def signals(h1: pd.DataFrame, z: pd.Series, h: int, thr: float,
            rr: float = 3.0) -> list[Signal]:
    """Fade the residual on the bar it CROSSES the gate, not every bar past it.

    Without the crossing condition a wide excursion emits a signal on every bar
    it lasts, and the engine's single-position rule then silently picks whichever
    one happens to survive -- a selection nobody chose and nobody can audit.
    """
    zz = z.reindex(h1.index)
    atr = families._atr(h1, 20)
    a = atr.to_numpy()
    zv = zz.to_numpy()
    o = h1["open"].to_numpy()
    out: list[Signal] = []
    for i in range(1, len(h1) - 2):
        cur, prev = zv[i], zv[i - 1]
        if not np.isfinite(cur) or not np.isfinite(prev):
            continue
        if abs(cur) < thr or abs(prev) >= thr:
            continue
        ai = a[i]
        if not (ai > 0) or np.isnan(ai):
            continue
        side = -1 if cur > 0 else 1           # fade: rich -> short, cheap -> long
        entry = float(o[i + 1])
        stop_dist = STOP_ATR * ai
        out.append(Signal(
            time=h1.index[i], side=side,
            stop=entry - side * stop_dist,
            target=entry + side * stop_dist * rr,
            ttl_bars=h, tag=f"residual_fade.h{h}.z{thr}"))
    return out


def daily_r(trades) -> pd.Series:
    if not trades:
        return pd.Series(dtype=float)
    return pd.Series(
        [t.r_multiple for t in trades],
        index=pd.Index([t.entry_time.date() for t in trades])).groupby(level=0).sum()


def sharpe(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    if len(x) < 2 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / x.std(ddof=1) * math.sqrt(TPY))


def pairwise_rho(a: pd.Series, b: pd.Series) -> float | None:
    com = sorted(set(a.index) & set(b.index))
    if len(com) < 30:
        return None
    x, y = a.reindex(com).to_numpy(float), b.reindex(com).to_numpy(float)
    if x.std() == 0 or y.std() == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def book_series() -> tuple[pd.Series, int]:
    """Edge-weighted daily R of the CURRENT book: the 77 raw-threshold survivors.

    Edge weights, not equal weights -- equal weighting is what made breadth look
    destructive by forcing the best cell to fund the worst, and admission asked
    against a mis-weighted book gives the wrong answer in both directions.
    """
    ser = pd.read_parquet(_DESK / "data" / "full_hunt_series.parquet")
    cands = json.loads((_DESK / "data" / "hunt_candidates.json").read_text("utf-8"))
    cells = [c["cell"] for c in cands if c["cell"] in ser.columns]
    if not cells:
        raise SystemExit("no survivor cell found in full_hunt_series.parquet")
    df = ser[cells].fillna(0.0)
    w = np.maximum(df.mean(axis=0).to_numpy(float), 0.0)
    w = w / w.sum() if w.sum() > 0 else np.ones(len(w)) / len(w)
    s = pd.Series(df.to_numpy(float) @ w, index=df.index)
    s.index = pd.Index([d.date() if hasattr(d, "date") else d for d in s.index])
    return s, len(cells)


def main() -> int:
    global STOP_ATR
    import argparse
    ap = argparse.ArgumentParser()
    # residual_alpha measured the forward return with NO stop. A sleeve carrying
    # a 1.5xATR stop is therefore not the thing that was measured: a reversion
    # trade that converges eventually but overshoots first is stopped out of a
    # move the forecast got right. Making the stop a dial is how that
    # explanation gets tested instead of asserted.
    ap.add_argument("--stop-atr", type=float, default=STOP_ATR)
    args = ap.parse_args()
    STOP_ATR = args.stop_atr
    h1 = families._h1(pd.read_parquet(UNI / f"{TARGET}_H1.parquet"))
    z, _ = build_z(TARGET)
    meta = json.loads((UNI / "universe.json").read_text("utf-8"))[TARGET]
    costs = Costs.from_symbol(meta, mult=2.0)

    valid = z.dropna().index
    if len(valid) < 2000:
        raise SystemExit("residual has too little history")
    split_ts = valid[int(len(valid) * TRAIN_FRAC)]
    print(f"RESIDUAL SLEEVE  {TARGET}   train < {split_ts.date()} <= test")
    print(f"  betas {BETA_WIN} bars, z {Z_WIN} bars, stop {STOP_ATR}xATR, "
          f"costs mult=2.0\n")

    rows = []
    print(f"{'cell':>16}{'tr n':>7}{'tr SR':>9}{'tr E[R]':>10}"
          f"{'te n':>7}{'te SR':>9}{'te E[R]':>10}")
    for h, thr in GRID:
        res = run_backtest(h1, signals(h1, z, h, thr), costs)
        tr = [t for t in res.trades if t.entry_time < split_ts]
        te = [t for t in res.trades if t.entry_time >= split_ts]
        if len(tr) < MIN_TRADES or len(te) < MIN_TRADES // 2:
            continue
        rtr = np.array([t.r_multiple for t in tr])
        rte = np.array([t.r_multiple for t in te])
        row = {
            "cell": f"h{h}.z{thr}", "h": h, "thr": thr,
            "train_n": len(tr), "train_sharpe_pertrade":
                round(float(rtr.mean() / rtr.std(ddof=1)), 4) if rtr.std(ddof=1) else 0.0,
            "train_expectancy_r": round(float(rtr.mean()), 4),
            "test_n": len(te), "test_sharpe_pertrade":
                round(float(rte.mean() / rte.std(ddof=1)), 4) if rte.std(ddof=1) else 0.0,
            "test_expectancy_r": round(float(rte.mean()), 4),
        }
        rows.append((row, te))
        print(f"{row['cell']:>16}{row['train_n']:>7}"
              f"{row['train_sharpe_pertrade']:>9.3f}{row['train_expectancy_r']:>10.4f}"
              f"{row['test_n']:>7}{row['test_sharpe_pertrade']:>9.3f}"
              f"{row['test_expectancy_r']:>10.4f}")
    if not rows:
        print("\nno cell produced enough trades on both halves.")
        return 0

    # THE CELL IS CHOSEN ON TRAIN ONLY. The test column above is printed for
    # every cell so the whole picture is visible, but it takes no part in this.
    best, best_te = max(rows, key=lambda rt: rt[0]["train_expectancy_r"])
    print(f"\nchosen on TRAIN alone: {best['cell']} "
          f"(train E[R] {best['train_expectancy_r']:+.4f})")
    print(f"its OUT-OF-SAMPLE result: n={best['test_n']} "
          f"E[R]={best['test_expectancy_r']:+.4f} "
          f"SR/trade={best['test_sharpe_pertrade']:+.3f}")

    sleeve = daily_r(best_te)
    book, n_cells = book_series()
    rho = pairwise_rho(sleeve, book)
    sr_new = sharpe(sleeve.to_numpy())
    com = sorted(set(sleeve.index) & set(book.index))
    sr_book = sharpe(book.reindex(com).to_numpy()) if len(com) >= 30 else sharpe(
        book.to_numpy())
    print(f"\nADMISSION  (book = {n_cells} raw-threshold survivors, edge-weighted)")
    print(f"  SR_new  = {sr_new:+.3f}   (annualised, OOS trades only)")
    print(f"  SR_book = {sr_book:+.3f}")
    if rho is None:
        print("  rho     = UNMEASURABLE (<30 overlapping days) -> no verdict.")
        print("  An unmeasurable correlation is not a zero correlation, and")
        print("  admitting on the assumption that it is would be the whole")
        print("  point of the rule thrown away.")
        verdict = "UNMEASURABLE"
    else:
        bar = sr_book * rho
        verdict = "ADMIT" if sr_new > bar else "REJECT"
        print(f"  rho     = {rho:+.3f}  on {len(com)} overlapping days")
        print(f"  bar     = SR_book x rho = {bar:+.3f}")
        print(f"  -> {verdict}: SR_new {sr_new:+.3f} "
              f"{'>' if sr_new > bar else '<='} {bar:+.3f}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "target": TARGET, "split": str(split_ts), "train_frac": TRAIN_FRAC,
        "grid_cells": len(rows), "chosen_on_train": best,
        "admission": {"sr_new_oos": round(sr_new, 4),
                      "sr_book": round(sr_book, 4),
                      "rho": None if rho is None else round(rho, 4),
                      "book_cells": n_cells, "verdict": verdict},
        "all_cells": [r for r, _ in rows]}, indent=1), "utf-8")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
