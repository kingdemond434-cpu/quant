"""HURDLE RATE -- the benchmark the desk has never had.

THE GAP: nothing in this desk has ever asked "is this better than doing nothing?". Today's own
data answered it accidentally and badly: the 8,026-trader cohort averaged -1.14% while BTC was
-0.15%, i.e. active leveraged trading UNDERPERFORMED holding. The desk itself is -4% on total
capital over 25 days. Neither number was ever compared to an alternative, so neither could be
judged.

A strategy is not "working" because it is positive. It is working when it beats what you could
have had for free, net of everything. Three benchmarks, hardest first:

  1. RISK-FREE   -- US 3-month T-bill (^IRX). Capital has a price; ignoring it flatters everything.
  2. BUY-AND-HOLD GOLD -- the zero-effort alternative on the desk's flagship MT5 instrument.
  3. 50/50 gold+cash   -- the honest risk-matched comparison for a market-neutral book, since a
                        hedged or netted book should NOT be compared to full XAUUSD beta.

REPOINTED AT THE MT5 UNIVERSE, 2026-09-05. Benchmark 2 was buy-and-hold BTC priced off a retired
exchange's public API, and the file also carried a CARRY DECOMPOSITION over
`web/cashcarry_live.json` -- funding harvested vs fee drag on the old hedged sleeve. Both belonged
to the retired book: that state file has no writer any more, so the block could only ever print
zeros dressed as a decomposition, which is the flattery this organ exists to prevent. The hurdle
question itself is venue-neutral and unchanged, and the benchmark is now the instrument the desk
actually trades -- a HARDER comparison than the old one, not a weaker one.

Benchmark 2 reads the MT5 bar store on disk rather than any venue API. If gold bars are absent it
is reported ABSENT and excluded from the verdict, never defaulted to zero: a benchmark that
silently becomes 0% is one the desk beats by standing still.

Free (Yahoo + the MT5 bar store + the desk's own state). Read-only. Run from repo root, daily.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/hurdle_rate.json"


def _get(u, t=35):
    return json.loads(
        urllib.request.urlopen(
            urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=t
        )
        .read()
        .decode()
    )


def load(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return None


def _gold_hold(days: float) -> float:
    """Buy-and-hold XAUUSD over the desk's own live window, or NaN when it cannot be priced.

    NaN is the refusal, and the caller reports it as ABSENT rather than folding it into the
    verdict. Returning 0.0 on a missing bar store would hand the desk a benchmark it beats by
    doing nothing at all, which is the precise failure this whole organ was built to catch.

    Reads `desks/mt5/**/universe/XAUUSD_*.parquet` -- the same bars the gateway trades against --
    rather than any venue API. That is deliberate: the comparison should be against a return the
    desk could actually have captured, at prices it could actually have filled.
    """
    if days <= 0:
        return float("nan")
    try:
        import pandas as pd
    except ImportError:
        return float("nan")
    for tf in ("H1", "M15", "D1", "H4"):
        for root in (ROOT / "desks/mt5/data/universe", ROOT / "desks/mt5/universe"):
            p = root / f"XAUUSD_{tf}.parquet"
            if not p.exists():
                continue
            try:
                frame = pd.read_parquet(p)
            except (OSError, ValueError):
                continue
            if frame.empty or "close" not in frame.columns:
                continue
            idx = pd.to_datetime(frame.index, utc=True)
            frame = frame.set_index(idx).sort_index()
            window = frame.loc[frame.index[-1] - pd.Timedelta(days=days):]
            if len(window) < 2:
                continue
            return float(window["close"].iloc[-1]) / float(window["close"].iloc[0]) - 1.0
    return float("nan")


def main() -> None:
    port = (load(ROOT / "web/portfolio.json") or {}).get("deployed") or {}
    days = float(port.get("days_live") or 0)
    ret = float(port.get("return_pct") or 0) / 100.0
    if days <= 0:
        print("no live history yet")
        return

    # --- benchmarks over the SAME window ---------------------------------------------------
    try:
        irx = _get(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EIRX?interval=1d&range=1mo"
        )["chart"]["result"][0]
        rf_annual = float([c for c in irx["indicators"]["quote"][0]["close"] if c][-1]) / 100.0
    except Exception:
        rf_annual = 0.045
    rf = rf_annual * (days / 365.0)

    gold = _gold_hold(days)
    half = gold / 2 + rf / 2

    ann = (1 + ret) ** (365 / days) - 1 if days > 0 else 0.0
    print("=== HURDLE RATE -- is this better than doing nothing? ===")
    print(f"    window: {days:.1f} days live\n")
    print(f"  {'DESK':<26} {ret * 100:+8.2f}%   ({ann * 100:+.1f}%/yr annualised)")
    print(f"  {'risk-free (T-bill)':<26} {rf * 100:+8.2f}%   ({rf_annual * 100:.2f}%/yr)")
    print(f"  {'buy-and-hold XAUUSD':<26} {gold * 100:+8.2f}%")
    print(f"  {'50/50 XAUUSD + cash':<26} {half * 100:+8.2f}%   <- risk-matched for a neutral book")

    # A NaN benchmark is ABSENT, not beaten. `ret > nan` is False in Python, so an unreadable bar
    # store used to read as "the desk fails this hurdle" -- wrong in the safe direction, but still
    # a measurement failure wearing a verdict. Excluded and named instead.
    hurdles = {"risk_free": rf, "gold_hold": gold, "half_gold": half}
    absent = sorted(k for k, v in hurdles.items() if v != v)
    beats = {k: ret > h for k, h in hurdles.items() if h == h}
    print()
    for k, v in beats.items():
        print(
            f"  beats {k:<12} {'YES' if v else 'NO'}   "
            f"(excess {(ret - hurdles[k]) * 100:+.2f}%)"
        )

    verdict = (
        "UNMEASURED -- no benchmark could be priced" if not beats
        else "PASSES" if all(beats.values())
        else "FAILS -- does not beat " + ", ".join(k for k, v in beats.items() if not v)
    )
    if absent:
        print(f"\n  ABSENT (excluded from the verdict, NOT scored as beaten): {', '.join(absent)}")
    print(f"\n  HURDLE VERDICT: {verdict}")
    print("  A strategy is not 'working' because it is positive. It works when it beats what you")
    print("  could have had for free, net of everything. Nothing should get capital until it does.")

    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "days": days,
                "desk_return": ret,
                "annualised": ann,
                "risk_free": rf,
                "gold_hold": gold,
                "half_gold": half,
                "beats": beats,
                "absent_benchmarks": absent,
                "verdict": verdict,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
