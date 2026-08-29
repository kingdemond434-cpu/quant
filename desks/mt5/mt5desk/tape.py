"""The MT5 tape: every tick this desk can see, recorded before it is gone.

REPLACES THE CRYPTO L2 RECORDERS. Those wrote Binance/Bybit book diffs into data/moat/{fut,spot,
perp,bybit} and filled the VPS. Irish retail rules make the crypto leg spot-only, the desk has
moved to MT5, and a tape nobody will trade on is pure cost. The obligation it carried was real
though, and it transfers rather than disappears: every unrecorded second is permanently unbuyable
at any price. Pre-recorder tick data does not exist free at any broker, and this archive only
grows.

WHAT MT5 ACTUALLY GIVES YOU, WHICH IS LESS THAN "L2"

`copy_ticks_from(..., COPY_TICKS_ALL)` returns real quote updates: bid, ask, last, volume, and
flags saying which of those changed. That is a genuine tick tape and it supports everything in
constitution section 23 -- quote-change imbalance, tick direction, micro momentum, spread
expansion and contraction, price-update intensity, burstiness, gap frequency.

DEPTH IS A DIFFERENT MATTER AND MOST RETAIL CFD BROKERS DO NOT HAVE IT. `market_book_add` /
`market_book_get` exist in the API, but a CFD broker is not an exchange: there is no central book
behind the symbol, and the call typically returns nothing or a synthetic single level echoing the
spread you already have. This module therefore PROBES for depth and records it only if the broker
genuinely supplies more than one level per side. It never synthesises a book from bid/ask.

That probe result is load-bearing beyond this file. Constitution section 222 -- the liquidity
survival engine, cancel/refill hazards, absorption versus fragile display -- needs real depth. If
this broker has none, section 222 cannot be built on this venue at all, and building it on a
fabricated book would produce a model of the fabrication. `probe_depth()` answers that question
with evidence instead of assumption.

    python -m mt5desk.tape --probe        # what does this broker actually expose?
    python -m mt5desk.tape                # record, resumable, once per call
"""

from __future__ import annotations

import json
import sys
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

# Derive from this module rather than importing the newer config.DATA alias. The live VPS lineage
# can legitimately lag that convenience constant; the desk's own location is invariant on both
# Windows and Linux and prevents a collector from resolving a legacy C:\\ path on Linux.
DATA = Path(__file__).resolve().parents[1] / "data"
TAPE = DATA / "tape"
TICKS = TAPE / "ticks"
DEPTH = TAPE / "depth"
TERMS = TAPE / "contract_terms"
STATE = TAPE / "tape_state.json"
PROBE = TAPE / "depth_probe.json"

#: Never ask for more than this in one call. A cold symbol with years of history would otherwise
#: try to materialise the whole tape in memory.
MAX_TICKS_PER_CALL = 2_000_000

#: How far back a symbol with no recorded state starts. Deliberately short: the point is to stop
#: losing NEW seconds, and a broker's tick history is usually thin anyway.
COLD_START_DAYS = 7


def contract_terms_row(symbol: str, info: object, at: datetime) -> dict:
    """Point-in-time broker financing and contract terms; never backfilled from today's values."""
    return {
        "observed_at": at.isoformat(timespec="seconds"),
        "symbol": symbol,
        "swap_long": float(info.swap_long),
        "swap_short": float(info.swap_short),
        "swap_mode": int(info.swap_mode),
        "swap_rollover3days": int(info.swap_rollover3days),
        # `point` AND `digits` ARE PART OF THE UNIT, not decoration. In POINTS mode the money
        # value is a function of point*contract_size, and the error hides on exactly the majors a
        # spot-check tries first (point*contract_size == 1.0 on a 5-digit major, 100 on a 3-digit
        # JPY cross). Recorded rather than re-derived because `symbol_info` reports TODAY's value
        # and a past night's is unbuyable at any price: a field re-derived from tomorrow's
        # registry silently re-prices yesterday's tape.
        "point": float(getattr(info, "point", 0.0) or 0.0),
        "digits": int(getattr(info, "digits", 0) or 0),
        "contract_size": float(info.trade_contract_size),
        "tick_size": float(info.trade_tick_size),
        "tick_value": float(info.trade_tick_value),
        "currency_profit": str(getattr(info, "currency_profit", "")),
        "currency_margin": str(getattr(info, "currency_margin", "")),
    }


def record_contract_terms(symbols: list[str]) -> dict:
    """Accrue the missing point-in-time swap history from the connected Fusion terminal."""
    import MetaTrader5 as mt5

    at = datetime.now(UTC)
    rows, failures = [], {}
    for symbol in symbols:
        info = mt5.symbol_info(symbol)
        if info is None:
            failures[symbol] = "symbol_info unavailable"
            continue
        try:
            rows.append(contract_terms_row(symbol, info, at))
        except (AttributeError, TypeError, ValueError) as exc:
            failures[symbol] = f"{type(exc).__name__}: {exc}"
    if rows:
        path = TERMS / f"{at.date().isoformat()}.parquet"
        frame = pd.DataFrame(rows)
        if path.exists():
            frame = pd.concat([pd.read_parquet(path), frame], ignore_index=True)
        frame = frame.drop_duplicates(subset=["observed_at", "symbol"], keep="last")
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False, compression="zstd")
    return {"observed_at": at.isoformat(timespec="seconds"), "rows": len(rows),
            "failures": failures}


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return default


def probe_depth(symbols: list[str]) -> dict:
    """Does this broker supply real depth, or only the spread restated as a book?

    Returns a verdict per symbol. A book of one level per side is NOT depth -- it is the top of
    book the tick tape already carries, and treating it as an order book would produce imbalance
    and refill features computed from a single quote.
    """
    import MetaTrader5 as mt5

    out: dict[str, dict] = {}
    for sym in symbols:
        rec = {"subscribed": False, "levels": 0, "verdict": "NO_DEPTH"}
        try:
            rec["subscribed"] = bool(mt5.market_book_add(sym))
            if rec["subscribed"]:
                book = mt5.market_book_get(sym)
                if book:
                    bids = sum(1 for b in book if getattr(b, "type", None) in (1, 3))
                    asks = sum(1 for b in book if getattr(b, "type", None) in (2, 4))
                    rec["levels"] = len(book)
                    rec["bid_levels"], rec["ask_levels"] = bids, asks
                    if bids > 1 and asks > 1:
                        rec["verdict"] = "REAL_DEPTH"
                    elif len(book):
                        rec["verdict"] = "TOP_OF_BOOK_ONLY"
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            with suppress(Exception):
                mt5.market_book_release(sym)
        out[sym] = rec

    real = [s for s, r in out.items() if r["verdict"] == "REAL_DEPTH"]
    verdict = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "symbols": out,
        "symbols_with_real_depth": real,
        "section_222_buildable": bool(real),
        "note": ("Constitution 222 (liquidity survival: cancel/refill hazard, absorption vs "
                 "fragile display) requires more than one level per side. Where verdict is "
                 "NO_DEPTH or TOP_OF_BOOK_ONLY, 222 is NOT buildable on this venue and must not "
                 "be built on a book synthesised from bid/ask -- that would model the synthesis. "
                 "The tick tape below is unaffected and supports section 23 in full."),
    }
    TAPE.mkdir(parents=True, exist_ok=True)
    PROBE.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return verdict


def record_ticks(symbols: list[str]) -> dict:
    """Append every tick since the last recorded one, per symbol. Resumable and idempotent.

    Stored as one parquet per symbol per UTC day. Parquet rather than the crypto recorder's
    jsonl.gz because ticks are a fixed numeric schema: columnar storage is roughly an order of
    magnitude smaller for this shape, and the previous format is what filled the disk.
    """
    import MetaTrader5 as mt5

    state = _load(STATE, {})
    now = datetime.now(UTC)
    summary: dict[str, dict] = {}

    for sym in symbols:
        last = state.get(sym, {}).get("last_tick_ms")
        start = (datetime.fromtimestamp(last / 1000.0, tz=UTC) + timedelta(milliseconds=1)
                 if last else now - timedelta(days=COLD_START_DAYS))
        try:
            ticks = mt5.copy_ticks_range(sym, start, now, mt5.COPY_TICKS_ALL)
        except Exception as exc:
            summary[sym] = {"error": f"{type(exc).__name__}: {exc}"}
            continue
        if ticks is None or len(ticks) == 0:
            summary[sym] = {"new_ticks": 0, "from": start.isoformat(timespec="seconds")}
            continue
        if len(ticks) > MAX_TICKS_PER_CALL:
            ticks = ticks[:MAX_TICKS_PER_CALL]

        df = pd.DataFrame(ticks)
        # time_msc is milliseconds since epoch; `time` is second-resolution and collapses bursts.
        df["ts"] = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
        df = df.sort_values("ts")
        written = 0
        for day, chunk in df.groupby(df["ts"].dt.date):
            out = TICKS / sym / f"{day.isoformat()}.parquet"
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                # Append by rewriting the day: ticks arrive strictly forward, so the union is
                # deduplicated on (ts, bid, ask) rather than assumed disjoint.
                prev = pd.read_parquet(out)
                chunk = (pd.concat([prev, chunk], ignore_index=True)
                         .drop_duplicates(subset=["time_msc", "bid", "ask", "last"])
                         .sort_values("ts"))
            chunk.to_parquet(out, index=False)
            written += len(chunk)
        state[sym] = {"last_tick_ms": int(df["time_msc"].iloc[-1]),
                      "last_run": now.isoformat(timespec="seconds"),
                      "last_tick_utc": str(df["ts"].iloc[-1])}
        summary[sym] = {"new_ticks": len(df), "rows_on_disk_touched": written,
                        "through": str(df["ts"].iloc[-1])}

    TAPE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return summary


def tape_features(sym: str, day: str) -> pd.DataFrame | None:
    """Section 23 features from one day of tape. Derived, never stored -- the tape is the asset.

    Deliberately microstructure-only. Nothing here is a signal; these are the inputs a signal
    would be tested against, and every one is computable from bid/ask alone, so they survive a
    broker with no depth.
    """
    path = TICKS / sym / f"{day}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path).sort_values("ts").set_index("ts")
    mid = (df["bid"] + df["ask"]) / 2.0
    out = pd.DataFrame(index=df.index)
    out["mid"] = mid
    out["spread"] = df["ask"] - df["bid"]
    out["spread_bps"] = out["spread"] / mid * 1e4
    out["d_mid"] = mid.diff()
    out["tick_dir"] = out["d_mid"].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    # Update intensity and burstiness: how fast quotes arrive, not where they are.
    gap_s = pd.Series(df.index, index=df.index).diff().dt.total_seconds()
    out["inter_quote_s"] = gap_s.values
    out["update_intensity_1m"] = out["tick_dir"].abs().rolling("60s").sum()
    out["spread_expansion"] = out["spread"].diff()
    out["quote_gap"] = (out["d_mid"].abs() > 5 * out["d_mid"].abs().rolling("300s").median())
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    import MetaTrader5 as mt5
    from mt5desk.config import terminal_path

    if mt5.terminal_info() is None and not mt5.initialize(path=terminal_path()):
        print(f"mt5 init failed: {mt5.last_error()}")
        return 1

    uni = _load(DATA / "universe" / "universe.json", {})
    symbols = sorted(uni) or ["XAUUSD", "USDJPY", "EURJPY", "GBPJPY", "CADJPY"]

    if "--probe" in argv:
        v = probe_depth(symbols)
        for s, r in v["symbols"].items():
            print(f"  {s:<10} {r['verdict']:<18} levels={r.get('levels', 0)}")
        print(f"\nreal depth on {len(v['symbols_with_real_depth'])}/{len(symbols)} symbols")
        print(f"constitution 222 buildable here: {v['section_222_buildable']}")
        return 0

    terms = record_contract_terms(symbols)
    if "--terms-only" in argv:
        # THE FINANCING LEG IS SECONDS OF WORK; THE TICK PULL IS MINUTES. Binding them meant the
        # cheap perishable stream could only be scheduled at the expensive one's cadence, so a
        # swap reprice between tick runs was permanently unbuyable. Measured on the desk's own
        # panel: 81 of 248 symbols repriced inside a single three-day window.
        print(f"{terms['rows']:,} point-in-time contract/swap rows recorded to {TERMS}")
        if terms.get("failures"):
            print(f"{len(terms['failures'])} symbol(s) failed: "
                  f"{', '.join(sorted(terms['failures'])[:8])}")
        return 0

    summary = record_ticks(symbols)
    total = sum(r.get("new_ticks", 0) for r in summary.values())
    for s, r in sorted(summary.items()):
        if r.get("error"):
            print(f"  {s:<10} ERROR {r['error']}")
        else:
            print(f"  {s:<10} +{r.get('new_ticks', 0):>9,} ticks  through {r.get('through', '-')}")
    print(f"\n{total:,} new ticks recorded to {TICKS}")
    print(f"{terms['rows']:,} point-in-time contract/swap rows recorded to {TERMS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
