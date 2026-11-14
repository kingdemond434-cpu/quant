"""CRITICAL_SLOWING.json: the early-warning state axis per instrument and for the live book.

GAP_MAP row 40 (Tier-1 gap thread, 2026-10-13): "rolling lag-1 autocorrelation, variance, skew
and flickering trends per MT5 symbol and for the book; published as a PIT state axis for cells
and as an allocator state input". The mathematics is `libs/regime/critical_slowing.py`; this
organ feeds it the desk's own daily closes and publishes the state.

WHAT IT READS. `data/universe/<SYMBOL>_H1.parquet` (D1 when there is no H1), for every symbol in
the hypothesis-discovery lane (`universe_policy.lane`), plus every symbol of a LIVE row in
`data/sleeves.json`. Daily closes are taken on the broker's day (server midnight = 17:00 New
York), which is the FX day the desk trades. The book series is the equal-weight mean of the live
symbols' daily log returns: a state of the BOOK's noise, not of any one leg.

WHAT IT DOES NOT DO. It sizes nothing, gates nothing and is read by no money-path module. The
allocator-input half of row 40 needs `pf_allocator` to read this file, which is money-path work
for the allocator's owner; the regime-cell half is a judged axis charged its trials when a cell
uses it. An instrument with too little tape is UNMEASURED with its count, never CALM (L1.28a).

    python desks/mt5/research/critical_slowing_state.py [--budget-s 240]
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime import critical_slowing as cs  # noqa: E402

SOURCE = "critical_slowing_state"
TIMEFRAMES = ("H1", "D1")
LOOKBACK_DAYS = 400
DEFAULT_BUDGET_S = 240.0


def _at(*parts: str) -> Path:
    """Every path hangs off DESK at call time, so one monkeypatch moves the organ."""
    return DESK.joinpath(*parts)


def report_path() -> Path:
    return _at("reports", "CRITICAL_SLOWING.json")


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:        # a read-only destination is WinError 5 on the box
        with contextlib.suppress(OSError):
            path.chmod(0o644)
        os.replace(tmp, path)


def live_symbols() -> list[str]:
    """Symbols of LIVE rows in data/sleeves.json (read only); [] when unreadable."""
    try:
        doc = json.loads(_at("data", "sleeves.json").read_text("utf-8-sig"))
    except (OSError, ValueError):
        return []
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    out = {str(r.get("symbol")) for r in rows or []
           if isinstance(r, dict) and str(r.get("status") or "").upper() == "LIVE"
           and r.get("symbol")}
    return sorted(out)


def hypothesis_symbols() -> list[str]:
    """Symbols with a bar file whose lane is the hypothesis-discovery lane."""
    try:
        from universe_policy import HYPOTHESIS, lane
    except ImportError:                                    # pragma: no cover
        from research.universe_policy import HYPOTHESIS, lane
    uni = _at("data", "universe")
    names: set[str] = set()
    for tf in TIMEFRAMES:
        for p in uni.glob(f"*_{tf}.parquet"):
            names.add(p.name[: -len(f"_{tf}.parquet")])
    return sorted(s for s in names if lane(s) == HYPOTHESIS)


def daily_log_returns(symbol: str) -> list[float] | None:
    """Daily log returns over the last LOOKBACK_DAYS, or None when no bar file reads."""
    import numpy as np
    import pandas as pd
    for tf in TIMEFRAMES:
        path = _at("data", "universe", f"{symbol}_{tf}.parquet")
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
        except Exception:                                  # a corrupt file is data, not a crash
            continue
        if not isinstance(df.index, pd.DatetimeIndex):
            col = next((c for c in ("time", "date", "timestamp") if c in df.columns), None)
            if col is None:
                continue
            df = df.set_index(pd.DatetimeIndex(pd.to_datetime(df[col], errors="coerce")))
        close_col = next((c for c in ("close", "Close") if c in df.columns), None)
        if close_col is None:
            continue
        close = pd.to_numeric(df[close_col], errors="coerce")
        close = close[close > 0].dropna()
        if close.empty:
            continue
        daily = close.resample("1D").last().dropna()
        daily = daily[daily.index >= daily.index[-1] - pd.Timedelta(days=LOOKBACK_DAYS)]
        r = np.diff(np.log(daily.to_numpy(dtype=float)))
        return [float(x) for x in r if math.isfinite(x)]
    return None


def book_returns(series: dict[str, list[float]], symbols: list[str]) -> list[float]:
    """Equal-weight mean of the live symbols' returns, aligned on their common tail."""
    legs = [series[s] for s in symbols if series.get(s)]
    if not legs:
        return []
    n = min(len(x) for x in legs)
    return [sum(x[len(x) - n + i] for x in legs) / len(legs) for i in range(n)]


def build(budget_s: float = DEFAULT_BUDGET_S) -> dict[str, Any]:
    t0 = time.monotonic()
    live = live_symbols()
    try:
        hyp = hypothesis_symbols()
        lane_note = "universe_policy.lane"
    except Exception as exc:                               # registry unreadable: live only
        hyp, lane_note = [], f"UNMEASURED: {type(exc).__name__}"
    symbols = sorted(set(hyp) | set(live))
    rows: dict[str, dict[str, Any]] = {}
    series: dict[str, list[float]] = {}
    for sym in symbols:
        if time.monotonic() - t0 > budget_s:
            rows[sym] = {"state": "UNMEASURED", "why": "time budget exhausted"}
            continue
        r = daily_log_returns(sym)
        if r is None:
            rows[sym] = {"state": "UNMEASURED", "why": "no readable H1/D1 bar file"}
            continue
        series[sym] = r
        rows[sym] = cs.early_warning(r)
    book = cs.early_warning(book_returns(series, live)) if live else {
        "state": "UNMEASURED", "why": "no LIVE sleeve in data/sleeves.json"}
    book["symbols"] = live
    counts: dict[str, int] = {}
    for row in rows.values():
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    warning = sorted((s for s, r in rows.items() if r["state"] == "WARNING"),
                     key=lambda s: -(rows[s].get("score") or 0.0))
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": SOURCE,
        "gap_map_row": 40,
        "params": {"window": cs.WINDOW, "trend_windows": cs.TREND_WINDOWS,
                   "tau_rising": cs.TAU_RISING, "warning_count": cs.WARNING_COUNT,
                   "surrogates": cs.SURROGATES, "surrogate_p": cs.SURROGATE_P,
                   "bimodal_bc": round(cs.BIMODAL_BC, 4), "bar": "daily (broker day)",
                   "lookback_days": LOOKBACK_DAYS},
        "universe": {"symbols": len(symbols), "hypothesis_lane": len(hyp),
                     "live_symbols": len(live), "lane_rule": lane_note},
        "counts": dict(sorted(counts.items())),
        "warning": warning,
        "book": book,
        "symbols": rows,
        "consumers": {"allocator_state_input": "NOT WIRED (money path: pf_allocator's owner)",
                      "regime_cells": "available as a PIT axis; trials charged when used"},
        "elapsed_s": round(time.monotonic() - t0, 2),
        "rule": ("Kendall trend of trailing-window lag-1 AC, variance, |skew| and bimodality "
                 "of daily log returns (Dakos et al. 2012), each beating shuffled surrogates at p<=0.05; "
                 "two or more rising together is "
                 "WARNING, one is RISING; too little tape is UNMEASURED, never CALM. Sizes "
                 "nothing."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--budget-s", type=float,
                    default=float(os.environ.get("QUANT_LEG_BUDGET_S") or DEFAULT_BUDGET_S))
    args = ap.parse_args(argv)
    doc = build(max(5.0, float(args.budget_s) - 15.0))
    try:
        _write_atomic(report_path(), doc)
    except OSError as exc:
        print(f"critical_slowing: report not written ({type(exc).__name__})")
        return 1
    print(f"critical_slowing: {doc['universe']['symbols']} symbol(s) {doc['counts']}; "
          f"book {doc['book']['state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
