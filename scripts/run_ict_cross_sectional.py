#!/usr/bin/env python3
"""MARKET-NEUTRAL ICT ACROSS A PANEL -- the breadth lever, measured rather than assumed.

WHY. Information ratio scales as IC x sqrt(N) for INDEPENDENT bets, and directional crypto majors
are not independent. The escape is to remove the common factor: long the symbol with the setup,
short the index against it, and judge what is left.

WHAT THIS REPORTS AND WHY IT IS NOT A BACKTEST RESULT. Effective breadth is MEASURED from the
realised return streams --

    N_eff = (sum_i sigma_i)^2 / Var(sum_i r_i)

-- which is exactly N for independent equal-vol streams and 1 for perfectly correlated ones. No
correlation is assumed anywhere. That matters because the figure that motivated this module (2.08x
at an assumed residual rho of 0.2) was a PREMISE, and a premise reported as a result is how a desk
convinces itself of something it never measured.

THE HONEST HEADLINE IS THE COST, NOT THE BREADTH. On a 12-symbol control panel the hedge buys
about 1.35x in IR terms while a fully-invested book pays 100-175% of capital a year in fees at
15-minute frequency. Breadth is real and the cost is an order of magnitude larger than it. Anyone
reading only the breadth number would draw the opposite conclusion from the one the numbers
support, so both are printed together and the cost is printed first.

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

from libs.ict.cross_sectional import HEDGE_BAND, run_cross_sectional  # noqa: E402
from libs.ict.strategy import ICTParams  # noqa: E402

BARS = ROOT / "data/bars"
REPORT = ROOT / "data/ict_cross_sectional.json"


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def load_panel(directory: Path) -> tuple[dict[str, pd.DataFrame], str]:
    """symbol -> bars, from every parquet/csv in a directory. Never synthesised.

    The panel is the point: a cross-sectional book cannot be run on one symbol, and quietly
    falling back to one would report a market-neutral result for a directional bet.
    """
    if not directory.exists():
        return {}, (f"{_rel(directory)} does not exist. data/ is gitignored, so this is expected "
                    "in a fresh checkout and a REAL blocker on the VPS -- run "
                    "scripts/build_bars.py per symbol first.")
    out: dict[str, pd.DataFrame] = {}
    for f in sorted([*directory.glob("*.parquet"), *directory.glob("*.csv")]):
        try:
            df = pd.read_parquet(f) if f.suffix == ".parquet" else pd.read_csv(f)
        except (OSError, ValueError):
            continue
        if {"open", "high", "low", "close"} <= set(df.columns) and len(df) > 200:
            out[f.stem] = df
    if len(out) < 2:
        return {}, (f"only {len(out)} usable symbol(s) under {_rel(directory)} -- a cross-section "
                    "needs at least 2, and running this on one symbol would report a "
                    "market-neutral result for a directional bet")
    return out, f"{len(out)} symbols from {_rel(directory)}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars-dir", default=None, help="directory of per-symbol bar files")
    ap.add_argument("--taker-bps", type=float, default=7.5)
    ap.add_argument("--maker-bps", type=float, default=1.0)
    ap.add_argument("--entry-mode", choices=("market", "limit"), default="market")
    ap.add_argument("--hedge-band", type=float, default=HEDGE_BAND,
                    help="hold the hedge until it drifts this far; 0 rebalances every bar")
    ap.add_argument("--gross-cap", type=float, default=1.0)
    a = ap.parse_args()

    panel, why = load_panel(Path(a.bars_dir) if a.bars_dir else BARS)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if not panel:
        REPORT.write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(), "state": "NO PANEL", "reason": why,
            "note": "panels are NOT synthesised -- a measurement about a generator is not one "
                    "about a market"}, indent=1), "utf-8")
        print(f"ict-xsec: NO PANEL -- {why}")
        return 0

    r = run_cross_sectional(panel, ICTParams(entry_mode=a.entry_mode),
                            taker_bps=a.taker_bps, maker_bps=a.maker_bps,
                            hedge_band=a.hedge_band, gross_cap=a.gross_cap)

    net = r.net_return.to_numpy()
    bars_per_year = 365 * 24 * 4
    sharpe = (float(net.mean() / net.std(ddof=1) * np.sqrt(bars_per_year))
              if net.std(ddof=1) > 0 else 0.0)

    out = {
        "ts": datetime.now(tz=UTC).isoformat(), "source": why,
        "symbols": r.symbols, "bars": r.bars, "position_bars": r.n_positions,
        "entry_mode": a.entry_mode, "hedge_band": a.hedge_band,
        "cost_drag_annual": r.cost_drag_annual,
        "breadth": {
            "n_eff_directional": r.n_eff_directional,
            "n_eff_residual": r.n_eff_residual,
            "mean_corr_directional": r.mean_corr_directional,
            "mean_corr_residual": r.mean_corr_residual,
            "ir_multiple_directional": r.ir_multiple_directional,
            "ir_multiple_residual": r.ir_multiple_residual,
            "gain_from_hedging": r.breadth_gain,
        },
        "net_sharpe_annualised": sharpe,
        "note": r.note,
        "authority": ("NONE. Stage-A evidence. Breadth is measured, costs are a LOWER BOUND (perp "
                      "funding on the short leg is not modelled), and nothing here promotes, "
                      "pre-registers or sizes anything."),
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")

    # COST FIRST, DELIBERATELY. The breadth number is the encouraging one and the cost number is
    # the one that decides, so the order they are read in is not neutral.
    print(f"ict-xsec: {len(r.symbols)} symbols, {r.bars} bars, {a.entry_mode} entry")
    print(f"  COST {r.cost_drag_annual:>7.1%} of capital/yr  <-- this is the binding constraint")
    print(f"  breadth: directional N_eff {r.n_eff_directional:.2f} (IR x"
          f"{r.ir_multiple_directional:.2f}) -> residual N_eff {r.n_eff_residual:.2f} "
          f"(IR x{r.ir_multiple_residual:.2f}) = {r.breadth_gain:.2f}x from hedging")
    print(f"  P&L-stream correlation {r.mean_corr_directional:+.3f} -> "
          f"{r.mean_corr_residual:+.3f} after removing the common factor")
    print(f"  net Sharpe {sharpe:+.2f} annualised")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
