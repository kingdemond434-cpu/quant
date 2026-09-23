#!/usr/bin/env python3
"""FORECAST SCORER (L1.29): resolve price forecasts against venue truth, automatically.

WHY THIS EXISTS. check_calibration fires OVERDUE when forecasts pass their resolve_by unscored --
and it fired with 7 outstanding because the desk had a LOGGER and no SCORER. That asymmetry is the
worst possible one: logging a probability costs nothing and feels like rigour, while only the
scoring turns it into calibration. An unscored forecast log silently inflates confidence exactly
the way the law warns, because every belief looks vindicated when none is ever graded.

WHAT IT RESOLVES. Claims of the shape "SYMBOL trades above X at +Nh" / "Will SYMBOL trade ABOVE X
in N hours' time?" are resolved from the MT5/Fusion bar store at the resolve_by minute -- venue
truth, not a cached dashboard. Anything whose claim this cannot parse UNAMBIGUOUSLY is left
unresolved and reported by name: a guessed outcome is worse than an overdue one, because it
corrupts the very measurement the fence exists to protect.

REPOINTED AT THE MT5 DESK, 2026-09-05 (universe mandate). This scorer used to read a retired
exchange's public klines endpoint. That market is closed to this desk, so venue truth is now
`desks/mt5/universe/<SYMBOL>_<TF>.parquet` -- the same bars the MT5 gateway trades against, which
is a STRICTER definition of truth than the old one: the desk is now graded on prices it can
actually fill at. The refusal path is unchanged and is the reason
this repoint is safe: a symbol with no MT5 bars is reported by name as unresolvable and stays
OVERDUE, exactly as an unreachable endpoint did. Nothing is guessed to fill the gap.

SCORING CONVENTION. outcome=True iff the stated condition HELD at the deadline. p is the desk's
stated probability that it would hold, so Brier/bias fall out of the pair directly. Resolution
uses the CLOSE of the 1m candle containing resolve_by -- a single defined instant, so the answer
cannot drift with when the scorer happens to run.

    python scripts/score_forecasts.py            # dry-run, prints what it would resolve
    python scripts/score_forecasts.py --write     # writes outcomes through fc.resolve()
"""
from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from libs.self_improvement import forecast_calibration as fc  # noqa: E402

#: Where MT5 venue truth lives on disk. Both roots are real on the trading box; the second is the
#: acquisition target and the first is what the research side reads, so BOTH are searched rather
#: than one being guessed. Order is deliberate: the acquired store wins when a symbol is in both.
_MT5_BAR_ROOTS: tuple[Path, ...] = (ROOT / "desks/mt5/data/universe", ROOT / "desks/mt5/universe")

#: Finest-to-coarsest. A forecast resolves at a defined instant, so the finest bar available is the
#: least wrong answer -- and the timeframe actually used travels with the verdict rather than being
#: assumed, because "resolved on H1" and "resolved on M15" are different claims about precision.
_MT5_TIMEFRAMES: tuple[str, ...] = ("M5", "M15", "M30", "H1", "H4", "D1")
# THE SYMBOL ALPHABET INCLUDES DIGITS, and leaving them out failed in BOTH directions (R0367).
# These patterns were `[A-Z]{2,12}USD[TC]?`, so `S2USDT` matched nothing at all -- 46 forecasts
# aged past their deadline ungraded and check_calibration sat OVERDUE, which is not merely a red
# fence: an ungraded forecast never counts its miss, so the measured hit-rate can only rise, and
# `report()`'s bias term feeds calibrated_confidence and from there Kelly leverage. A calibration
# input that cannot fall is exactly the over-confidence L1.29 exists to catch.
# The quieter half is worse. On a multiplier ticker the old pattern still matched -- but it
# matched the WRONG INSTRUMENT: `1000PEPEUSDT` yielded `PEPEUSDT`, a different contract priced
# 1000x apart, so the forecast would have been resolved against the wrong series and scored as a
# confident hit or miss on a number that was never the claim. Silently returning a plausible
# wrong answer beats loudly returning none, in the only direction that matters here.
# "trades above 63216.2", "trade ABOVE 63007.5", "above the 4h shelf at 62441.9"
_ABOVE = re.compile(r"\b([A-Z0-9]{2,12}USD[TC]?)\b.*?\b(?:trades?|trade)\s+ABOVE\s+([0-9]+\.?[0-9]*)",
                    re.I)
# "LONG BTCUSDT @13.97x stop 0.86% (below the 4h shelf at 62441.9 ...)"
# "SHORT SOLUSDT @7.34x stop 1.63% (... 73.47 cap ...)" -- mirror of the LONG pattern.
_CONVICTION_SHORT = re.compile(
    r"SHORT\s+([A-Z0-9]{2,12}USD[TC]?)\b.*?stop\s+([0-9.]+)%.*?([0-9]+\.[0-9]+)", re.I)
_CONVICTION = re.compile(
    r"LONG\s+([A-Z0-9]{2,12}USD[TC]?)\b.*?stop\s+([0-9.]+)%.*?shelf\s+at\s+([0-9]+\.?[0-9]*)", re.I)


def auto_resolvable(claim: str) -> bool:
    """Can this scorer grade that claim WITHOUT judgement? The three patterns above, and nothing
    else. Exported so `check_calibration` can name -- before the deadline rather than after -- the
    forecasts no organ and no parser can ever score. Those rows fire OVERDUE the day they come due
    and can never be cleared, which pins the L1.29 fence and is how a fence gets switched off
    (L1.43). Reads the same compiled patterns `main()` dispatches on, so the two cannot drift."""
    return any(p.search(claim or "") for p in (_CONVICTION_SHORT, _CONVICTION, _ABOVE))


def mt5_bars(symbol: str):
    """Every MT5 bar this desk holds for `symbol`, finest timeframe first, or ``None``.

    Returns ``(frame, source)``. ``None`` means the desk has NO venue truth for that symbol, which
    is a refusal the callers report by name -- never a zero, never a nearest-neighbour substitute.
    A forecast graded against the wrong instrument is worse than one left OVERDUE (R0367 measured
    exactly that: `1000PEPEUSDT` resolving as `PEPEUSDT`, a contract priced 1000x apart).
    """
    try:
        import pandas as pd
    except ImportError:
        return None
    sym = symbol.upper()
    for tf in _MT5_TIMEFRAMES:
        for root in _MT5_BAR_ROOTS:
            p = root / f"{sym}_{tf}.parquet"
            if not p.exists():
                continue
            try:
                frame = pd.read_parquet(p)
            except (OSError, ValueError):
                continue                      # unreadable file is not a price; keep looking
            if frame.empty or not {"high", "low", "close"} <= set(frame.columns):
                continue
            idx = pd.to_datetime(frame.index, utc=True)
            return frame.set_index(idx).sort_index(), f"mt5:{sym}_{tf}"
    return None


def fetch_bars(symbol: str, start_ms: int, end_ms: int, bar: str = "15m"
               ) -> tuple[list[tuple[int, float, float, float, float]], str]:
    """OHLC rows in [start_ms, end_ms] as ``(ts_ms, o, h, l, c)``, or ``([], reason)``.

    THE CONTRACT IS "EMPTY WITH A REASON", NEVER A MARK. `run_calibration_probe` grades a forecast
    on `bars[-1][4]`, so a fabricated bar here becomes a graded hit or miss on a price that never
    traded -- and calibration is the one number the Kelly sizer consumes. It inherits this shape
    from `resolve_paper_book.fetch_bars`, deleted 2026-09-05 under the universe mandate;
    the signature is kept identical so the two live callers did not have to change their handling
    of the refusal, which is the part that must not drift.

    `bar` is accepted and reported for provenance but not honoured as a resample: the store's
    finest available timeframe is used, and the caller is told which via the returned source.
    Silently returning a coarser bar under a finer name is the misreporting this desk fences.
    """
    got = mt5_bars(symbol)
    if got is None:
        return [], (f"UNRESOLVABLE -- no MT5 bars for {symbol.upper()} under "
                    f"{'/'.join(str(r.name) for r in _MT5_BAR_ROOTS)}")
    frame, src = got
    try:
        import pandas as pd
        lo = pd.Timestamp(start_ms, unit="ms", tz="UTC")
        hi = pd.Timestamp(end_ms, unit="ms", tz="UTC")
    except (ImportError, ValueError) as exc:
        return [], f"UNRESOLVABLE -- {type(exc).__name__}: {str(exc)[:60]}"
    window = frame.loc[lo:hi]
    if window.empty:
        return [], f"UNRESOLVABLE -- {src} holds no bar in [{lo:%Y-%m-%d %H:%M}, {hi:%Y-%m-%d %H:%M}]"
    rows = [(int(ts.timestamp() * 1000), float(r.open), float(r.high), float(r.low), float(r.close))
            for ts, r in window.iterrows()]
    return rows, f"{src}(requested {bar})"


def _price_at(symbol: str, when: datetime) -> float | None:
    """Close of the finest MT5 bar containing `when` -- one defined instant, not 'now'."""
    got = mt5_bars(symbol)
    if got is None:
        return None
    frame, _src = got
    at_or_before = frame.loc[:when]
    if at_or_before.empty:
        return None
    return float(at_or_before["close"].iloc[-1])


def _high_between(symbol: str, start: datetime, end: datetime) -> float | None:
    """Highest MT5 HIGH in [start, end] -- the mirror of _low_between, for SHORT stops."""
    got = mt5_bars(symbol)
    if got is None:
        return None
    window = got[0].loc[start:end]
    return float(window["high"].max()) if not window.empty else None


def _low_between(symbol: str, start: datetime, end: datetime) -> float | None:
    """Lowest MT5 LOW in [start, end] -- wicks count, because a stop is hit by the wick."""
    got = mt5_bars(symbol)
    if got is None:
        return None
    window = got[0].loc[start:end]
    return float(window["low"].min()) if not window.empty else None


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
        ms = _CONVICTION_SHORT.search(claim)
        if ms:
            sym, pct, lvl = ms.group(1).upper(), float(ms.group(2)), float(ms.group(3))
            stop = lvl * (1.0 + pct / 100.0)      # a SHORT stops out ABOVE the level
            hi = _high_between(sym, datetime.fromisoformat(str(v.get("updated") or rb)), deadline)
            if hi is None:
                skipped.append((key, f"no venue highs for {sym}"))
                continue
            survived = hi < stop
            resolved.append((key, sym, stop, hi, survived, float(v.get("p", 0.5))))
            continue

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
