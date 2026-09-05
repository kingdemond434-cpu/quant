"""Build the desk's description of the world once, so every consumer reads the same one.

WHY A PRODUCER AND NOT AN INLINE CALL. Measured on this host a `RegimeEngine` fit costs ~8.5ms
per observation -- 17s for 2,000 daily bars. The allocator's fast clock is five minutes and it
runs three clocks; a state vector assembled inside it would eat the clock it exists to inform.
So this runs on the hourly cycle, caches every fit against the bar it saw, and writes one
artifact. `pf_allocator` reads it in milliseconds and says how old it was.

WHAT IT BUILDS

  GLOBAL    XAUUSD daily -- UNCHANGED, deliberately. It is what the allocator's world draw
            already trusts, and swapping the book-wide regime in the same change that introduces
            per-asset regimes would make the two indistinguishable in the artifact. Per-asset
            states enter as INFORMATION first; they take authority only by earning it.
  FACTORS   The six role instruments from `economic_drivers.ROLES` -- USDX, UST10Y, US500,
            XAUUSD, XBRUSD, XCUUSD -- on the daily clock. A "USD regime" here is USDX's regime:
            a state about something the desk can hold, not a synthesised index.
  ASSETS    Every symbol the BOOK ACTUALLY TRADES, on weekly / daily / H4 / H1 / M15 / M5.
            Scoped to the book on purpose -- fitting regimes for instruments nobody holds spends
            the budget on questions nobody asked, and the scope grows by itself as the book does.
            The intraday tiers are attempted for every symbol and REFUSED for any whose finest
            parquet is hourly: resampling H1 closes to "15min" produces hourly bars wearing a
            finer label, and a state vector reporting a fifteen-minute regime the desk has no
            data for is worse than one reporting a gap. They light up by themselves when the
            bars arrive -- this desk currently holds three M15 files and no M5.
  SESSION   The broker-stamp phase, from the same `session_phase` the evidence conditioner uses.
  EVENT     Where the market is in a scheduled release's life, from the calendar vintages.
  LIQUIDITY What execution costs right now against its own history, from the venue's tape.

EVERY HOLE IS RECORDED. A symbol with too little history, a factor whose parquet is missing, a
tape that was never recorded -- each lands in `gaps` with its reason. A state vector that quietly
substitutes the global regime for a missing asset state would let gold's regime masquerade as
GBPUSD's, and nobody downstream could tell.

    python research/state_vector_build.py
    python research/state_vector_build.py --budget-s 600
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.regime.asset_state import CLOCKS, FitCache, fit_asset_state       # noqa: E402
from libs.regime.state_vector import StateVector                            # noqa: E402
from mt5desk.economic_drivers import ROLES                                  # noqa: E402

UNI = BASE / "data" / "universe"
OUT = BASE / "data" / "state_vector.json"
CACHE = BASE / "data" / "state_fits.json"
CANON = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"

#: Clocks each scope is fitted on. Factors are daily because a dollar or real-rate regime is a
#: daily object; asking USDX what it is doing this hour is a different question and a noisier one.
FACTOR_CLOCKS = ("daily",)
#: Clocks attempted per book symbol, slowest to fastest. The intraday tiers are attempted for
#: every symbol and REFUSED by `_series` for any whose finest parquet is hourly -- so they cost
#: nothing where the data is absent and appear by themselves where it arrives. Scoping them by a
#: hardcoded symbol list would mean a newly downloaded M15 file changed nothing until someone
#: edited this file.
ASSET_CLOCKS = ("weekly", "daily", "H4", "H1", "M15", "M5")
#: Parquet suffixes searched per symbol, FINEST FIRST. A finer file serves every coarser clock by
#: resampling; a coarser one cannot serve a finer clock at all.
BAR_SUFFIXES = ("M5", "M15", "H1")



def _close(symbol: str) -> pd.Series | None:
    """The finest bars this desk holds for the symbol. Finer serves coarser; never the reverse."""
    for suffix in BAR_SUFFIXES:
        path = UNI / f"{symbol}_{suffix}.parquet"
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path, columns=["close"])
        except (OSError, ValueError, ImportError, KeyError):
            continue
        if df.empty:
            continue
        idx = pd.to_datetime(df.index, utc=True, errors="coerce")
        s = pd.Series(df["close"].to_numpy(dtype=float), index=idx).dropna()
        if s.size:
            return s
    return None


def book_symbols() -> list[str]:
    """Instruments the certified book actually holds, from the canon rather than a list."""
    try:
        doc = json.loads(CANON.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    out: set[str] = set()
    for cert in (doc.get("survivors") or {}).values():
        if not isinstance(cert, dict):
            continue
        sym = cert.get("sym") or (cert.get("shadow_spec") or {}).get("symbol")
        if isinstance(sym, str) and sym:
            out.add(sym.upper())
    return sorted(out)


def session_state(now: datetime) -> tuple[dict, str]:
    try:
        from research.session_phase import broker_utc_offset_h, phase_at
        off, source = broker_utc_offset_h()
        if off is None:
            return ({"phase": None, "broker_utc_offset_source": source},
                    "session: broker UTC offset unknown -- refusing to assume UTC")
        return {"phase": phase_at(now, broker_utc_offset_h=off), "broker_utc_offset_h": off,
                "broker_utc_offset_source": source}, ""
    except Exception as exc:                                    # noqa: BLE001
        return {}, f"session: {type(exc).__name__}: {exc}"


def event_state(now: datetime, symbols: list[str]) -> tuple[dict, str]:
    """Where each book instrument sits in the life of a release that concerns IT.

    Delegates to `libs.regime.event_state`, which scopes releases BY CURRENCY: a Bank of England
    print is an event for GBP pairs and an ordinary Tuesday for AUDJPY. The version this replaces
    classified the whole desk from the nearest event on the calendar regardless of what it was
    about, so every instrument entered SHOCK whenever anything anywhere printed.
    """
    try:
        from libs.regime.event_state import NORMAL, classify, parse_rows, relevant
        from research import orthogonal_sweep as inputs

        rows = parse_rows(_calendar_rows())
        if not rows:
            return {"phase": NORMAL, "basis": "no calendar vintages with usable stamps"}, ""
        meta = _meta()
        per: dict[str, dict] = {}
        for sym in symbols[:24]:
            scoped = relevant(rows, sym, meta)
            shock, since = _event_moves(sym, now, scoped)
            st = classify(now, [r["_stamp"] for r in scoped], symbol=sym, rows=scoped,
                          shock_move=shock, move_since=since)
            per[sym] = st.to_dict()
        if not per:
            return {"phase": NORMAL, "basis": "no book symbols to scope events to"}, ""
        # The desk-level phase is the most urgent any book instrument is in: a book with one
        # sleeve in SHOCK is not in NORMAL, and reporting an average would describe nobody.
        order = {p: i for i, p in enumerate(
            ("SHOCK", "PRICE_DISCOVERY", "POST_EVENT_REVERSAL", "POST_EVENT_DRIFT",
             "PRE_EVENT", "NORMALIZATION", "NORMAL"))}
        worst = min(per.values(), key=lambda d: order.get(str(d.get("phase")), 99))
        return {"phase": worst["phase"], "n_calendar_rows": len(rows),
                "per_symbol": per}, ""
    except Exception as exc:                                    # noqa: BLE001
        return {}, f"event: {type(exc).__name__}: {exc}"


def _calendar_rows() -> list[dict]:
    """Every calendar vintage row the miner has recorded, newest files last."""
    root = BASE / "data" / "intelligence" / "ff_calendar_vintage"
    out: list[dict] = []
    seen: set[str] = set()
    if not root.exists():
        return out
    for path in sorted(root.glob("*.json"))[-60:]:
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        rows = doc if isinstance(doc, list) else (doc.get("rows") or doc.get("discoveries") or [])
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            key = f"{row.get('event_date')}|{row.get('title')}"
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
    return out


def _meta() -> dict:
    try:
        return json.loads((UNI / "universe.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _event_moves(symbol: str, now: datetime, scoped: list[dict]) -> tuple[float | None, float | None]:
    """The instrument's log move during the last release's shock window, and since it.

    DRIFT and REVERSAL occupy the same minutes after the same print, so only the tape can tell
    them apart. Returns (None, None) whenever the bars cannot answer, and `classify` then reports
    PRICE_DISCOVERY rather than guessing a direction.
    """
    from libs.regime.event_state import SHOCK_MIN

    past = [r["_stamp"] for r in scoped if r["_stamp"] <= now]
    if not past:
        return None, None
    last = max(past)
    close = _close(symbol)
    if close is None or close.empty:
        return None, None
    try:
        before = close[close.index <= pd.Timestamp(last)]
        shock_end = pd.Timestamp(last) + pd.Timedelta(minutes=SHOCK_MIN)
        during = close[(close.index > pd.Timestamp(last)) & (close.index <= shock_end)]
        after = close[close.index > shock_end]
        if before.empty or during.empty:
            return None, None
        p0, p1 = float(before.iloc[-1]), float(during.iloc[-1])
        shock = float(np.log(p1 / p0)) if p0 > 0 and p1 > 0 else None
        since = (float(np.log(float(after.iloc[-1]) / p1))
                 if (not after.empty and p1 > 0 and float(after.iloc[-1]) > 0) else None)
        return shock, since
    except (ValueError, TypeError, ZeroDivisionError):
        return None, None


def liquidity_state(symbols: list[str], now: datetime,
                    event: dict | None = None) -> tuple[dict, str]:
    """Execution conditions per instrument, named as a state by `libs.regime.liquidity_state`.

    The version this replaces sorted the current spread into four percentile bands. It could not
    say WHY an instrument was expensive, and the answer decides what to do: a rollover ends on a
    clock, a news window ends with the release, a degraded feed means stop rather than size down.
    """
    try:
        from libs.regime.liquidity_state import UNMEASURED, classify
        from research import orthogonal_sweep as inputs
        from research.session_phase import broker_utc_offset_h

        off, _src = broker_utc_offset_h()
        broker_hour = ((now.hour + off) % 24) if off is not None else None
        news_syms = set()
        for sym, st in ((event or {}).get("per_symbol") or {}).items():
            if str(st.get("phase")) in {"PRE_EVENT", "SHOCK", "PRICE_DISCOVERY"}:
                news_syms.add(sym)

        per: dict[str, dict] = {}
        for sym in symbols[:12]:
            hourly = pd.date_range(end=pd.Timestamp(now), periods=24 * 60, freq="h")
            spread, flow = inputs._tape_series(sym, hourly)
            hist = list(spread.dropna()) if spread is not None else None
            act = list(flow.abs().dropna()) if flow is not None else None
            mins = None
            if spread is not None and not spread.dropna().empty:
                mins = float((pd.Timestamp(now) - spread.dropna().index[-1]).total_seconds() / 60)
            st = classify(sym, hist, activity_history=act, broker_hour=broker_hour,
                          in_news_window=(sym in news_syms), minutes_since_tick=mins)
            per[sym] = st.to_dict()
        if not per:
            return {"state": UNMEASURED, "basis": "no book symbols to measure"}, ""
        order = {s: i for i, s in enumerate(
            ("BROKER_DEGRADED", "TOXIC", "NEWS", "ROLLOVER", "THIN", "NORMAL", UNMEASURED))}
        worst = min(per.values(), key=lambda d: order.get(str(d.get("state")), 99))
        return {"state": worst["state"], "broker_hour": broker_hour,
                "per_symbol": per}, ""
    except Exception as exc:                                    # noqa: BLE001
        return {}, f"liquidity: {type(exc).__name__}: {exc}"


def build(budget_s: float = 900.0, symbols: list[str] | None = None) -> StateVector:
    now = datetime.now(tz=UTC)
    cache = FitCache(path=CACHE)
    gaps: dict[str, str] = {}
    started = time.monotonic()

    def _left() -> float:
        return budget_s - (time.monotonic() - started)

    def _fit(sym: str, clock: str, tag: str):
        if _left() <= 0:
            gaps[tag] = "state-vector budget exhausted before this fit"
            return None
        close = _close(sym)
        if close is None:
            gaps[tag] = f"no bars for {sym} (searched {', '.join(BAR_SUFFIXES)})"
            return None
        st, why = fit_asset_state(close, sym, clock, cache=cache)
        if st is None:
            gaps[tag] = f"{sym}@{clock}: {why}"
        return st

    global_state = _fit("XAUUSD", "daily", "global")

    factors = {}
    for role, candidates in ROLES.items():
        sym = next((c for c in candidates if (UNI / f"{c}_H1.parquet").exists()), None)
        if sym is None:
            gaps[f"factor:{role}"] = f"none of {candidates} has H1 bars here"
            continue
        for clock in FACTOR_CLOCKS:
            st = _fit(sym, clock, f"factor:{role}@{clock}")
            if st is not None:
                factors[role] = st

    book = symbols if symbols is not None else book_symbols()
    assets = {}
    for sym in book:
        for clock in ASSET_CLOCKS:
            st = _fit(sym, clock, f"asset:{sym}@{clock}")
            if st is not None:
                assets[f"{sym}@{clock}"] = st

    session, why = session_state(now)
    if why:
        gaps["session"] = why
    event, why = event_state(now, book)
    if why:
        gaps["event"] = why
    # Liquidity reads the event state: a NEWS window is an execution condition with a known cause
    # and a known end, and classifying it as merely "wide" loses the part that decides what to do.
    liquidity, why = liquidity_state(book, now, event)
    if why:
        gaps["liquidity"] = why

    cache.flush()
    return StateVector(at=now.isoformat(), global_state=global_state, assets=assets,
                       factors=factors, session=session, event=event, liquidity=liquidity,
                       gaps=gaps)


def load(max_age_s: float = 7200.0) -> tuple[StateVector | None, str]:
    """Read the artifact, REFUSING a stale one rather than conditioning on yesterday's world."""
    try:
        sv = StateVector.from_dict(json.loads(OUT.read_text("utf-8")))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, f"state vector unreadable: {type(exc).__name__}: {exc}"
    age = sv.age_seconds()
    if age > max_age_s:
        return None, f"state vector is {age / 3600:.1f}h old (limit {max_age_s / 3600:.1f}h)"
    return sv, f"state vector {sv.id} age {age / 60:.0f}m"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--symbol", action="append", default=None)
    args = ap.parse_args()

    sv = build(budget_s=args.budget_s, symbols=args.symbol)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(sv.to_dict(), indent=1, default=str), "utf-8")

    g = sv.global_state
    print(f"STATE VECTOR {sv.id}  {sv.at}")
    if g:
        print(f"  GLOBAL   {g.symbol}@{g.clock}: {g.top} age={g.age_bars} "
              f"P(exit {min(g.p_leave) if g.p_leave else '?'})="
              f"{min(g.p_leave.values()) if g.p_leave else float('nan'):.1%} "
              f"H={min(g.entropy.values()) if g.entropy else float('nan'):.2f}")
    for role, st in sorted(sv.factors.items()):
        print(f"  FACTOR   {role:7s} {st.symbol:8s} {st.top:14s} age={st.age_bars}")
    for key, st in sorted(sv.assets.items()):
        print(f"  ASSET    {key:18s} {st.top:14s} age={st.age_bars} "
              f"conf={st.engine_confidence:.2f}")
    print(f"  SESSION  {sv.session.get('phase')}   EVENT {sv.event.get('phase')}   "
          f"LIQUIDITY {sv.liquidity.get('state')}")
    for k, v in sorted(sv.gaps.items()):
        print(f"  GAP      {k}: {v}")
    print(f"written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
