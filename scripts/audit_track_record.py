#!/usr/bin/env python3
"""ADJUDICATE A TRACK RECORD SOMEBODY ELSE IS SHOWING YOU.

THE CLAIM THAT MOTIVATED THIS. A gold EA on MT5, advertised as FVG/ICT-based, reported at 5-10%
per week and 30-40% per month. Compounded, that is 12x-141x and 23x-57x per year against a
Medallion benchmark of roughly 66%/yr gross -- the best record that exists. Numbers in that range
are not "very good"; they are a different kind of object, and the right response is measurement,
because the mechanism that produces them leaves fingerprints in the trade list.

WHAT TO ASK FOR AND WHY IT IS THE ONLY THING THAT SETTLES IT. An equity curve or a screenshot
cannot separate edge from sizing -- the information is not in it. A CLOSED-TRADE LIST can, because
the martingale/grid rule that produces a smooth 5%/week is visible in how size responds to the
previous trade's outcome. In MT5: right-click the History tab -> Report -> save as HTML/XLSX, or
export the Deals view to CSV. What this script needs from it is one row per closed trade, in
chronological order, with a profit column and a volume/lots column.

  python3 scripts/audit_track_record.py statement.csv --equity 10000

CSV columns are matched case-insensitively against common MT5/broker exports (profit/pnl/p&l,
volume/lots/size). Anything unmatched is reported rather than guessed at, because guessing which
column is size would silently invert every statistic in the audit.

NO PROMOTION AUTHORITY, AND NO ENDORSEMENT AUTHORITY EITHER. A clean verdict here means "the
returns were not manufactured by the sizing rules this can see". It is not a finding of edge, and
it is deliberately worded so it cannot be quoted as one.

Read-only. No network, no keys, no order paths.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.validation.errors import ValidationError  # noqa: E402
from libs.validation.track_record import (  # noqa: E402
    audit_trades,
    compound,
    years_to_significance,
)

#: Column aliases, lowercased. Order matters: the first hit wins.
PNL_COLS = ("profit", "pnl", "p&l", "net profit", "netprofit", "result", "gain")
SIZE_COLS = ("volume", "lots", "size", "quantity", "qty", "lot")


def _pick(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lower = {str(c).strip().lower(): c for c in df.columns}
    for n in names:
        if n in lower:
            return lower[n]
    for n in names:                       # substring fallback: "Profit, USD" and similar
        for k, orig in lower.items():
            if n in k:
                return orig
    return None


def _numeric(s: pd.Series) -> pd.Series:
    """Broker exports carry thousands separators, spaces and parenthesised negatives."""
    # \xa0 is deliberate: MT5's HTML/XLSX exports use a NO-BREAK SPACE as the thousands
    # separator, and leaving it in makes every profit column parse as NaN.
    txt = (s.astype(str).str.replace("[\\s\xa0,]", "", regex=True)
           .str.replace(r"^\((.*)\)$", r"-\1", regex=True))
    return pd.to_numeric(txt, errors="coerce")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", help="CSV of closed trades, one row per trade, chronological")
    ap.add_argument("--equity", type=float, default=None,
                    help="starting account equity; anchors drawdown and ruin in account terms")
    ap.add_argument("--claim-weekly", type=float, default=None,
                    help="claimed weekly return as a fraction, e.g. 0.07 -- compounded for you")
    ap.add_argument("--out", default=None, help="write the audit as JSON here")
    a = ap.parse_args()

    src = Path(a.path)
    if not src.exists():
        print(f"track-record: {src} not found")
        return 1
    try:
        df = pd.read_csv(src)
    except (OSError, ValueError, pd.errors.ParserError) as e:
        print(f"track-record: {src.name} unreadable: {str(e)[:120]}")
        return 1

    pcol, scol = _pick(df, PNL_COLS), _pick(df, SIZE_COLS)
    if pcol is None:
        print(f"track-record: no profit column found. Looked for {PNL_COLS}; "
              f"the file has {list(df.columns)[:12]}")
        return 1
    pnl = _numeric(df[pcol]).dropna()
    size = None
    if scol is not None:
        size = _numeric(df[scol]).reindex(pnl.index)
        if size.isna().any():
            print(f"track-record: '{scol}' has {int(size.isna().sum())} unparseable rows -- "
                  "auditing WITHOUT sizes rather than filling them, since an invented size would "
                  "silently invert every sizing statistic here")
            size = None

    try:
        au = audit_trades(pnl.to_numpy(), None if size is None else size.to_numpy(),
                          starting_equity=a.equity)
    except ValidationError as e:
        print(f"track-record: refused -- {e}")
        return 1

    print(f"track-record: {au.n_trades} trades from {src.name} "
          f"(profit='{pcol}', size='{scol or 'ABSENT'}')")
    print(f"  VERDICT: {au.verdict}")
    print(f"  win rate {au.win_rate:.1%} | payoff {au.payoff_ratio:.2f} | "
          f"total {au.total_pnl:,.2f} | max DD {au.max_drawdown:,.2f}")
    print(f"  size after loss {au.size_after_loss:.4g} vs after win {au.size_after_win:.4g} "
          f"(ratio {au.escalation_ratio:.2f}) | loss-depth slope {au.loss_depth_slope:+.2f}")
    print(f"  deepest losing run {au.deepest_loss_streak} | ruin {au.ruin_probability:.1%}"
          + ("  <-- LOWER BOUND" if au.ruin_is_lower_bound else ""))
    # THE T-STAT IS WHAT THIS FILE CAN HONESTLY SUPPORT. Annualising a Sharpe needs trades per
    # YEAR, and a bare trade list carries no dates -- so `years_to_significance` is not called on
    # a per-trade figure here. Feeding it the t-statistic (which is what an earlier draft did)
    # would have produced a confident number with no meaning, the exact error this desk keeps
    # finding in its own reports.
    tstat = au.sharpe_per_trade * (au.n_trades ** 0.5)
    print(f"  per-trade Sharpe {au.sharpe_per_trade:.3f} | t-stat {tstat:.2f} over "
          f"{au.n_trades} trades"
          + ("" if abs(tstat) >= 2.0 else "  <-- not distinguishable from zero"))
    for r in au.reasons:
        print(f"  - {r}")
    if a.claim_weekly:
        w = a.claim_weekly
        print(f"  CLAIM CHECK: {w:.1%}/week compounds to {compound(w, 52):,.1f}x per year "
              f"({compound(w, 4):,.2f}x per month). Medallion, the best record that exists, runs "
              f"about 1.66x per year gross.")

    if a.out:
        Path(a.out).write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(), "source": src.name,
            "columns": {"pnl": pcol, "size": scol},
            **dict(vars(au)),
            "t_stat": tstat,
            "years_to_significance_at_sharpe_1": years_to_significance(1.0),
            "authority": ("NONE. A clean verdict means the returns were not manufactured by the "
                          "sizing rules this can see -- it is not a finding of edge."),
        }, indent=1, default=str), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
