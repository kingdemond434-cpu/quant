"""Hurst/DFA regime-flip state per symbol, from the H1 bars the desk already holds (C row 120).

    python desks/mt5/research/dfa_flip_state.py            # one pass
    python desks/mt5/research/dfa_flip_state.py --symbol XAUUSD

For every hypothesis-lane symbol with a held `data/universe/<SYM>_H1.parquet`, this rolls a DFA
exponent over daily closes (`libs.regime.dfa_flip`), holds a mean-reverting / trending state with
a hysteresis band around 0.5, and lists the dated flips. It fetches nothing.

CLOSED BARS ONLY. The newest calendar day of each file is dropped before anything is computed,
because on the box it is still forming; every value and every flip carries `asof`, the last bar
of the day that produced it.

WHAT CONSUMES IT. `family_regime_transition(dfa_gate=..., dfa_fresh_days=...)` recomputes the same
events from the frame it is handed (so a backtest never reads this file and cannot see the
future through it); this report is the live view of the same state -- which symbols flipped,
when, and which way -- for the regime router, the issue board and a reader.

Report-only. It mints no cell, donates nothing and changes no sizing.

Clock: `hourly_cycle:dfa_flip_state` (layer `information`).
Artifact: desks/mt5/reports/DFA_FLIP_STATE.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pandas as pd  # noqa: E402

from libs.regime import dfa_flip  # noqa: E402

UNI = _DESK / "data" / "universe"
REPORT = _DESK / "reports" / "DFA_FLIP_STATE.json"
#: Daily closes each pass reads per symbol: the estimate window plus enough history for the
#: hysteresis state to have settled. Bounded so the hourly cost does not grow with the file.
HISTORY_DAYS = 750
#: Flips listed per symbol in the report (newest first).
RECENT_FLIPS = 10
FAMILY = "regime_transition"


def _may_hypothesise(sym: str) -> bool:
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        return False
    try:
        return bool(may_hypothesise(sym, FAMILY))
    except Exception:
        return False


def _bars(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(path, columns=["close"])
    except (OSError, ValueError, ImportError, KeyError):
        return None
    if df.empty:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    return df[~df.index.isna()].sort_index()


def symbol_state(bars: pd.DataFrame, now: datetime | None = None) -> dict[str, Any]:
    """One symbol's row: current exponent and held state, plus its dated flips."""
    tail = bars[bars.index >= bars.index.max() - pd.Timedelta(days=int(HISTORY_DAYS * 1.5))]
    daily, events = dfa_flip.flip_events_from_bars(tail, drop_last=True)
    alpha = daily["dfa_alpha"].dropna() if "dfa_alpha" in daily else pd.Series(dtype=float)
    if alpha.empty:
        return {"status": "UNMEASURED",
                "why": f"{len(daily)} closed days, under the {dfa_flip.DEFAULT_WINDOW}-day window"}
    last_day = alpha.index[-1]
    now = now or datetime.now(tz=UTC)
    last = events[-1] if events else None
    return {
        "status": "MEASURED",
        "closed_days": len(daily),
        "asof": pd.Timestamp(daily["asof"].loc[last_day]).isoformat(),
        "dfa_alpha": round(float(alpha.iloc[-1]), 4),
        "state": daily["dfa_state"].loc[last_day] or "inside_band_unset",
        "flips_total": len(events),
        "last_flip": last,
        "days_since_last_flip": (round((now - pd.Timestamp(last["asof"]).to_pydatetime())
                                       .total_seconds() / 86400, 2) if last else None),
        "recent_flips": list(reversed(events[-RECENT_FLIPS:])),
    }


def run(symbols: list[str] | None = None, budget_s: float = 600.0,
        uni: Path = UNI, report: Path = REPORT) -> dict[str, Any]:
    started = time.monotonic()
    paths = sorted(uni.glob("*_H1.parquet"))
    wanted = set(symbols) if symbols else None
    rows: dict[str, dict[str, Any]] = {}
    skipped: dict[str, str] = {}
    for path in paths:
        sym = path.stem.removesuffix("_H1")
        if wanted is not None and sym not in wanted:
            continue
        if not _may_hypothesise(sym):
            skipped[sym] = "not in the hypothesis lane for regime_transition (universe_policy)"
            continue
        if time.monotonic() - started > budget_s:
            skipped[sym] = "pass budget exhausted"
            continue
        bars = _bars(path)
        if bars is None:
            skipped[sym] = "held H1 file unreadable or empty"
            continue
        rows[sym] = symbol_state(bars)
    measured = {s: r for s, r in rows.items() if r.get("status") == "MEASURED"}
    out = {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "method": {"estimator": "DFA-1 on daily log returns of held H1 closes",
                   "window_days": dfa_flip.DEFAULT_WINDOW,
                   "scales_days": list(dfa_flip.DEFAULT_SCALES),
                   "upper": dfa_flip.DEFAULT_UPPER, "lower": dfa_flip.DEFAULT_LOWER,
                   "closed_bars_only": "newest calendar day dropped; every value stamped asof"},
        "consumer": "mt5desk/family_regime_transition.py dfa_gate (recomputes from its own frame)",
        "symbols_held": len(paths),
        "symbols_measured": len(measured),
        "symbols_unmeasured": sorted(s for s, r in rows.items() if r.get("status") != "MEASURED"),
        "trending": sorted(s for s, r in measured.items() if r["state"] == dfa_flip.TRENDING),
        "mean_reverting": sorted(s for s, r in measured.items()
                                 if r["state"] == dfa_flip.MEAN_REVERTING),
        "flips_last_7d": sorted(
            ({"symbol": s, **r["last_flip"]} for s, r in measured.items()
             if r["last_flip"] and r["days_since_last_flip"] is not None
             and r["days_since_last_flip"] <= 7), key=lambda e: e["asof"], reverse=True),
        "skipped": skipped,
        "symbols": rows,
        "elapsed_s": round(time.monotonic() - started, 2),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=600.0)
    a = ap.parse_args(argv)
    rep = run(symbols=a.symbol, budget_s=a.budget_s)
    print(f"DFA FLIP STATE  {rep['symbols_measured']} measured, {len(rep['trending'])} trending, "
          f"{len(rep['mean_reverting'])} mean-reverting, {len(rep['flips_last_7d'])} flips in 7d")
    print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
