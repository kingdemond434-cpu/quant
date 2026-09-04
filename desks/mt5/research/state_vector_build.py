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
  ASSETS    Every symbol the BOOK ACTUALLY TRADES, on daily and H4. Scoped to the book on
            purpose -- fitting regimes for instruments nobody holds spends the budget on
            questions nobody asked, and the scope grows by itself as the book does.
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
ASSET_CLOCKS = ("daily", "H4")

#: Spread percentiles that name a liquidity state. Derived from the instrument's OWN recorded
#: tape, so a wide-spread instrument is not permanently "toxic" for being itself.
LIQ_BANDS = ((0.25, "cheap"), (0.75, "normal"), (0.95, "wide"), (1.01, "toxic"))
#: Hours either side of a scheduled release that count as its pre/post phases.
EVENT_PRE_H = 2
EVENT_SHOCK_H = 1
EVENT_DRIFT_H = 6


def _close(symbol: str) -> pd.Series | None:
    path = UNI / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path, columns=["close"])
    except (OSError, ValueError, ImportError, KeyError):
        return None
    if df.empty:
        return None
    idx = pd.to_datetime(df.index, utc=True, errors="coerce")
    s = pd.Series(df["close"].to_numpy(dtype=float), index=idx).dropna()
    return s if s.size else None


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


def event_state(now: datetime) -> tuple[dict, str]:
    """Where the market sits in a scheduled release's life, not merely whether vol is high.

    PRE / SHOCK / DISCOVERY / DRIFT / NORMAL are qualitatively different information processes: a
    pre-event tape is thin and one-sided, a shock is price discovery with no reliable mean, and
    post-event drift is a different bet again. Tagging the whole window "high volatility" throws
    the distinction away, and it is the distinction every event sleeve is actually about.
    """
    try:
        from research import orthogonal_sweep as inputs
        idx = inputs._event_index()
        if idx is None or len(idx) == 0:
            return {"phase": "NORMAL", "basis": "no calendar vintages recorded"}, ""
        stamps = pd.DatetimeIndex(pd.to_datetime(idx, utc=True, errors="coerce")).dropna()
        if stamps.empty:
            return {"phase": "NORMAL", "basis": "calendar vintages carry no usable stamps"}, ""
        delta_h = (stamps - pd.Timestamp(now)).total_seconds() / 3600.0
        ahead = float(delta_h[delta_h > 0].min()) if (delta_h > 0).any() else float("inf")
        behind = float(-delta_h[delta_h <= 0].max()) if (delta_h <= 0).any() else float("inf")
        if behind <= EVENT_SHOCK_H:
            phase = "SHOCK"
        elif behind <= EVENT_SHOCK_H * 2:
            phase = "DISCOVERY"
        elif behind <= EVENT_DRIFT_H:
            phase = "DRIFT"
        elif ahead <= EVENT_PRE_H:
            phase = "PRE"
        else:
            phase = "NORMAL"
        return {"phase": phase, "hours_to_next": round(ahead, 2),
                "hours_since_last": round(behind, 2), "n_events": int(stamps.size)}, ""
    except Exception as exc:                                    # noqa: BLE001
        return {}, f"event: {type(exc).__name__}: {exc}"


def liquidity_state(symbols: list[str]) -> tuple[dict, str]:
    """Current spread against each instrument's OWN recorded history, named as a state.

    The allocator can like an edge and still be right to wait: an alpha worth 0.3R is not worth
    taking through a spread in its own 97th percentile. This measures that, per symbol, from the
    venue's tape rather than from the registry's median.
    """
    try:
        from research import orthogonal_sweep as inputs
        per: dict[str, dict] = {}
        for sym in symbols[:12]:
            hourly = pd.date_range(end=pd.Timestamp.now(tz=UTC), periods=24 * 30, freq="h")
            spread, _flow = inputs._tape_series(sym, hourly)
            if spread is None or spread.dropna().empty:
                continue
            s = spread.dropna()
            cur = float(s.iloc[-1])
            pct = float((s <= cur).mean())
            state = next(name for edge, name in LIQ_BANDS if pct <= edge)
            per[sym] = {"spread": round(cur, 8), "percentile": round(pct, 4), "state": state,
                        "n_hours": int(s.size)}
        if not per:
            return {"state": "UNMEASURED", "basis": "no tape recorded for any book symbol"}, ""
        worst = max(per.values(), key=lambda d: d["percentile"])
        return {"state": worst["state"], "worst_percentile": worst["percentile"],
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
            gaps[tag] = f"no H1 parquet for {sym}"
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
    event, why = event_state(now)
    if why:
        gaps["event"] = why
    liquidity, why = liquidity_state(book)
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
