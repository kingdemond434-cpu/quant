#!/usr/bin/env python3
"""FORECAST SCORER (L1.29): resolve price forecasts against venue truth, automatically.

WHY THIS EXISTS. check_calibration fires OVERDUE when forecasts pass their resolve_by unscored --
and it fired with 7 outstanding because the desk had a LOGGER and no SCORER. That asymmetry is the
worst possible one: logging a probability costs nothing and feels like rigour, while only the
scoring turns it into calibration. An unscored forecast log silently inflates confidence exactly
the way the law warns, because every belief looks vindicated when none is ever graded.

WHAT IT RESOLVES. Claims of the shape "SYMBOL trades above X at +Nh" / "Will SYMBOL trade ABOVE X
in N hours' time?" are resolved from Binance klines at the resolve_by minute -- venue truth, not a
cached dashboard. Anything whose claim this cannot parse UNAMBIGUOUSLY is left unresolved and
reported by name: a guessed outcome is worse than an overdue one, because it corrupts the very
measurement the fence exists to protect.

SCORING CONVENTION. outcome=True iff the stated condition HELD at the deadline. p is the desk's
stated probability that it would hold, so Brier/bias fall out of the pair directly. Resolution
uses the CLOSE of the 1m candle containing resolve_by -- a single defined instant, so the answer
cannot drift with when the scorer happens to run.

    python scripts/score_forecasts.py            # dry-run, prints what it would resolve
    python scripts/score_forecasts.py --write     # writes outcomes through fc.resolve()
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from libs.self_improvement import forecast_calibration as fc  # noqa: E402

_UA = {"User-Agent": "Mozilla/5.0 (quant-desk forecast-scorer)"}
# "trades above 63216.2", "trade ABOVE 63007.5", "above the 4h shelf at 62441.9"
_ABOVE = re.compile(r"\b([A-Z]{2,12}USD[TC]?)\b.*?\b(?:trades?|trade)\s+ABOVE\s+([0-9]+\.?[0-9]*)",
                    re.I)
# "LONG BTCUSDT @13.97x stop 0.86% (below the 4h shelf at 62441.9 ...)"
_CONVICTION = re.compile(
    r"LONG\s+([A-Z]{2,12}USD[TC]?)\b.*?stop\s+([0-9.]+)%.*?shelf\s+at\s+([0-9]+\.?[0-9]*)", re.I)


def _price_at(symbol: str, when: datetime) -> float | None:
    """Close of the 1m candle containing `when` -- one defined instant, not 'now'."""
    ms = int(when.timestamp() * 1000)
    url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m"
           f"&startTime={ms - 60_000}&limit=3")
    try:
        rows = json.loads(urllib.request.urlopen(
            urllib.request.Request(url, headers=_UA), timeout=25).read())
    except Exception:
        return None
    if not rows:
        return None
    best = min(rows, key=lambda r: abs(int(r[0]) - ms))
    return float(best[4])


def _low_between(symbol: str, start: datetime, end: datetime) -> float | None:
    """Lowest 1m LOW in [start, end] -- wicks count, because a stop is hit by the wick."""
    ms0, ms1 = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    lows: list[float] = []
    cur = ms0
    while cur < ms1:
        url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m"
               f"&startTime={cur}&endTime={ms1}&limit=1000")
        try:
            rows = json.loads(urllib.request.urlopen(
                urllib.request.Request(url, headers=_UA), timeout=25).read())
        except Exception:
            return None
        if not rows:
            break
        lows.extend(float(r[3]) for r in rows)
        cur = int(rows[-1][0]) + 60_000
        if len(rows) < 1000:
            break
    return min(lows) if lows else None


def main() -> None:
    write = "--write" in sys.argv
    now = datetime.now(tz=UTC)
    log = fc._load()["forecasts"]

    resolved, skipped = [], []
    for key, v in sorted(log.items()):
        if v.get("resolved") or v.get("outcome") is not None:
            continue
        rb = v.get("resolve_by")
        if not rb:
            continue                                  # no deadline => not overdue, not ours
        try:
            deadline = datetime.fromisoformat(str(rb))
            if deadline.tzinfo is None:      # older rows were logged without an offset
                deadline = deadline.replace(tzinfo=UTC)
        except Exception:
            skipped.append((key, "unparseable resolve_by"))
            continue
        if deadline > now:
            continue                                  # not yet due
        claim = str(v.get("claim") or "")

        # CONVICTION CLAIMS resolve under a STATED interpretation, written here so it is auditable
        # rather than applied silently: a levered LONG with a stop X% below a named shelf SURVIVES
        # iff price never traded through that stop before the deadline. Checked on 1m LOWS -- a
        # close-only check would miss a wick through the stop, and that error flatters the desk.
        mc = _CONVICTION.search(claim)
        if mc:
            sym, pct, shelf = mc.group(1).upper(), float(mc.group(2)), float(mc.group(3))
            stop = shelf * (1.0 - pct / 100.0)
            lo = _low_between(sym, datetime.fromisoformat(str(v.get("updated") or rb)), deadline)
            if lo is None:
                skipped.append((key, f"no venue lows for {sym}"))
                continue
            survived = lo > stop
            resolved.append((key, sym, stop, lo, survived, float(v.get("p", 0.5))))
            continue

        m = _ABOVE.search(claim)
        if not m:
            skipped.append((key, f"claim not unambiguously parseable: {claim[:70]}"))
            continue
        symbol, thresh = m.group(1).upper(), float(m.group(2))
        px = _price_at(symbol, deadline)
        if px is None:
            skipped.append((key, f"no venue price for {symbol} at {deadline:%Y-%m-%d %H:%M}"))
            continue
        outcome = px > thresh
        resolved.append((key, symbol, thresh, px, outcome, float(v.get("p", 0.5))))

    print(f"{'WRITING' if write else 'DRY-RUN'} -- {len(resolved)} resolvable, {len(skipped)} skipped\n")
    brier = 0.0
    for key, sym, th, px, out, p in resolved:
        brier += (p - (1.0 if out else 0.0)) ** 2
        print(f"  {key[:44]:<46} {sym:<10} {px:>10,.2f} vs {th:>10,.2f}  "
              f"-> {'TRUE ' if out else 'FALSE'}  (said p={p:.2f})")
        if write:
            fc.resolve(key, bool(out))
    if resolved:
        print(f"\n  Brier score on this batch: {brier / len(resolved):.4f}  "
              f"(0=perfect, 0.25=coin-flip at p=0.5)")
    for key, why in skipped:
        print(f"  SKIPPED {key[:44]:<46} {why}")
    if skipped:
        print("\n  Skipped forecasts stay OVERDUE by design: a guessed outcome corrupts the "
              "measurement the fence exists to protect.")


if __name__ == "__main__":
    main()
