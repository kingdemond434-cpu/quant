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
    python -m mt5desk.tape --dry-run      # READ-ONLY: the sides audit, before/after the repair
    python -m mt5desk.tape                # record, resumable, once per call

WHICH SIDE DID THE VENUE ACTUALLY MOVE (2026-09-17). An MT5 tick is a one-sided update as often
as not, `flags` is the only field that says which side moved, and until this date nothing stored
or read it. So when the moat series organ found 41,604 of EURUSD's 42,460 rows for 2026-09-15
carrying ask == bid while XAUUSD carried none, the tape could not answer the only question that
mattered: did the venue quote a locked market, or did a writer repeat the other side?

It can now, and the answer is the venue. Measured across 204,322,244 rows in 2,767 day files:
`ask == prev_ask` on 100.00% of bid-only ticks and `bid == prev_bid` on 100.00% of ask-only ticks
-- the terminal already carries the untouched side -- ZERO rows anywhere carry a missing side,
97.9% of the locked rows are ticks whose flags say BOTH sides moved, both independent writers
(this one and moat_silver's bronze conversion) report the same fraction for the same day, and the
terminal's own `symbol_info().spread`, recorded separately in `contract_terms`, reads 0 points for
EURUSD/GBPUSD/AUDUSD/USDJPY at five separate instants that day and 5-11 for XAUUSD. This account
quotes raw FX and marks up everything else. The zero spread is REAL, and a spread column of 0.0
is a cost of zero only if commission is ignored. `--dry-run` over the last three days
(100,808,613 rows, 1,110 instrument-days) puts the whole of it in the FX classes -- 27.69% of
forex rows and 0.23% of forex-exotic rows locked, and EXACTLY 0.0000% in commodities, equities,
crypto, indices, energy, soft commodities and bonds -- while XAUUSD's ticks carry the same
one-sided composition as EURUSD's (10,203 bid-only against 10,037 ask-only on 2026-09-15) and
none of the lock. A writer that repeated a side would not stop at an asset-class boundary.

What the tape gained is the ability to say so: `sided` on every row, `bid`/`ask` as the
best-known quote with `bid_raw`/`ask_raw` kept wherever a reconstruction changed one, and a
ONE_SIDED line in `tick_integrity` so a locked FX day can never again sit unmeasured.
"""

from __future__ import annotations

import json
import sys
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
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


def _opt_float(info: object, name: str) -> float | None:
    """None when the terminal did not report the field -- absence is never a value (WS-005)."""
    raw = getattr(info, name, None)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _opt_int(info: object, name: str) -> int | None:
    raw = getattr(info, name, None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


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
        # THE BROKER'S OWN FORCED-TRADE ANNOUNCEMENTS, already paid for and previously dropped.
        # `symbol_info` is one call and it carries these; writing eleven of its fields and
        # discarding these cost nothing to keep and is unbuyable once the hour passes.
        #   trade_mode        3 = CLOSEONLY, 0 = DISABLED -- a symbol flipping to CLOSEONLY is a
        #                     dated, published-by-behaviour instruction that every holder must
        #                     exit. Today the desk would learn of it from an order rejection.
        #   margin_initial    an increase is announced deleveraging in a named symbol inside a
        #                     dated window; a decrease permits expansion. Direction-agnostic.
        #   trade_stops_level/freeze_level bound where a stop may LEGALLY sit; the execution model
        #                     currently assumes a stop can be placed anywhere.
        # ABSENT IS None, NEVER 0 (WS-005): `trade_mode == 0` means DISABLED and `margin_* == 0`
        # means no requirement, so defaulting an absent field to zero would make "we did not read
        # it" render identically to "the broker disabled the symbol" -- the exact collapse this
        # desk keeps paying for.
        "trade_mode": _opt_int(info, "trade_mode"),
        "margin_initial": _opt_float(info, "margin_initial"),
        "margin_maintenance": _opt_float(info, "margin_maintenance"),
        "trade_stops_level": _opt_int(info, "trade_stops_level"),
        "freeze_level": _opt_int(info, "freeze_level"),
        "volume_min": _opt_float(info, "volume_min"),
        "volume_max": _opt_float(info, "volume_max"),
        "volume_limit": _opt_float(info, "volume_limit"),
        "spread": _opt_int(info, "spread"),
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


TICK_DEDUPE = ("time_msc", "bid", "ask", "last")

# ------------------------------------------------------------------------- tick sides --
#: MetaTrader's own ENUM_TICK_FLAG. An MT5 tick is a ONE-SIDED update as often as not, and
#: `flags` is the only field that says which side the venue actually moved on that tick.
TICK_FLAG_BID = 2
TICK_FLAG_ASK = 4
TICK_FLAG_LAST = 8
TICK_FLAG_VOLUME = 16
TICK_FLAG_BUY = 32
TICK_FLAG_SELL = 64

#: Everything outside these three bits is masked off before `sided` is derived. Fusion sets bits
#: MetaTrader does not document: measured 2026-09-17, EURUSD / XAUUSD / US500 carry 0x400 and
#: 0x80 alongside the documented ones (flags 1026/1028/1030/1154/1158) while the share CFDs carry
#: the documented bits alone (2/4/6). Guessing at an undocumented bit's meaning would put an
#: invention in a column the tape is supposed to record; masking says only what MT5 defines.
_SIDE_BITS = TICK_FLAG_BID | TICK_FLAG_ASK | TICK_FLAG_LAST

#: The `sided` vocabulary. `both` is not a synonym for "two-sided quote": it means the venue
#: moved BOTH sides on this tick, which is exactly how a genuinely locked quote is distinguished
#: from a carried one. `none` is a tick whose flags name no price side at all (volume-only, or a
#: feed that does not populate flags), and it is a measurement, not a defect.
SIDED_BID, SIDED_ASK, SIDED_BOTH = "bid", "ask", "both"
SIDED_LAST, SIDED_NONE = "last", "none"
SIDED_COLUMN = "sided"


def sided_from_flags(flags: object) -> np.ndarray:
    """Which side each tick updated, as `bid` / `ask` / `both` / `last` / `none`.

    THIS IS WHAT LETS A CARRIED SIDE BE TOLD FROM A QUOTED ONE, and without it the tape cannot
    answer the only question that matters about a zero spread: did the venue quote it, or did a
    writer repeat the other side? Derived from the recorded `flags` and nothing else, so it can
    be recomputed at any time from bytes already on disk and can never drift from them.
    """
    f = np.asarray(flags, dtype=np.int64) & _SIDE_BITS
    out = np.full(f.shape, SIDED_NONE, dtype="<U4")
    has_bid, has_ask = (f & TICK_FLAG_BID) > 0, (f & TICK_FLAG_ASK) > 0
    out[(f & TICK_FLAG_LAST) > 0] = SIDED_LAST
    out[has_bid] = SIDED_BID
    out[has_ask] = SIDED_ASK
    out[has_bid & has_ask] = SIDED_BOTH
    return out


def carry_sides(bid: object, ask: object, *, seed_bid: float = 0.0, seed_ask: float = 0.0
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Fill a MISSING side from the last one this session actually saw. Never overwrite a present
    one. Returns (bid, ask, bid_was_filled, ask_was_filled).

    A SIDE IS MISSING ONLY WHEN IT IS ABSENT -- `<= 0` or NaN -- NEVER MERELY BECAUSE `flags` SAY
    IT DID NOT CHANGE, and that distinction is the whole safety property of this function.
    Measured on this desk's own tape 2026-09-17 across 204,322,244 rows and 2,767 day files:
    `ask == prev_ask` on 100.00% of bid-only ticks and `bid == prev_bid` on 100.00% of ask-only
    ticks, for every instrument -- the terminal ALREADY carries the untouched side forward, and
    zero rows anywhere carry a missing side. So a carry keyed on the flags would rewrite a value
    the venue really published with one this desk inferred, which is how a tape stops being a
    record. This fills only what is genuinely absent (the first ticks of a cold symbol, a feed
    that publishes one side before the other), leaves everything else byte-identical, and is
    therefore a no-op on every row of the tape as it stands today. That is the correct outcome:
    a repair whose measured effect is zero on healthy data is a repair that cannot corrupt it.

    THE SEED IS THE SESSION BOUNDARY. `seed_bid` / `seed_ask` carry the last known quote of the
    SAME day into the next chunk of it; a new day starts at 0.0 and its leading missing rows stay
    missing, because yesterday's last quote is not a fact about today's open.
    """
    b = np.asarray(bid, dtype=np.float64).copy()
    a = np.asarray(ask, dtype=np.float64).copy()
    out: list[np.ndarray] = []
    for series, seed in ((b, float(seed_bid or 0.0)), (a, float(seed_ask or 0.0))):
        known = np.isfinite(series) & (series > 0)
        # One forward-fill, vectorised: index of the most recent known row, or -1 before the
        # first. The seed rides in front as a virtual row 0 so a chunk that continues a session
        # inherits it and one that starts a day does not.
        with_seed = np.concatenate(([seed], series))
        known_seed = np.concatenate(([np.isfinite(seed) and seed > 0], known))
        idx = np.where(known_seed, np.arange(with_seed.size), -1)
        np.maximum.accumulate(idx, out=idx)
        src = idx[1:]
        fill = (~known) & (src >= 0)
        series[fill] = with_seed[src[fill]]
        out.append(fill)
    return b, a, out[0], out[1]


def repair_sides(df: pd.DataFrame) -> pd.DataFrame:
    """Give a tick frame its `sided` column and its best-known two-sided quote. Idempotent.

    WHY THE COLUMNS ARE SHAPED THIS WAY, because the alternative was seriously considered and is
    worse. The tempting design is to leave `bid`/`ask` exactly as delivered and publish the
    reconstruction beside them as `bid_q`/`ask_q`. It is tempting because it never touches the
    record -- and it is wrong, because EVERY consumer on this desk reads `bid` and `ask`
    (`moat_series._read_day`, `tape_features`, `triangle_tape`, `edge_search`, `shadow_execution`
    ...). A correct quote in a column nobody reads is a fix that ships nothing, and this desk's
    own history is a list of producers whose output no reader ever parsed.

    So `bid`/`ask` ARE the best-known quote -- the value to trade, model and price against -- and
    the as-delivered value is preserved in `bid_raw` / `ask_raw` ONLY on the rows where the two
    differ. Those columns are absent entirely when nothing was filled, which on this tape is
    every row of every day: their PRESENCE is itself the signal that a reconstruction happened,
    and their absence costs the file nothing.

    `flags` is never touched. `sided` is recomputed from it on every pass rather than carried, so
    a day file that has been through several merges cannot accumulate a stale answer.

    Expects time order (merge_day sorts immediately before calling this); it does not re-sort,
    because the sort is the expensive part and doing it twice per symbol-day per hour is a real
    cost on the 8 GB box that holds the live terminal.
    """
    if df is None or "bid" not in df.columns or "ask" not in df.columns:
        return df
    out, copied = df, False
    if "flags" in out.columns:
        out, copied = out.copy(), True
        out[SIDED_COLUMN] = sided_from_flags(
            pd.to_numeric(out["flags"], errors="coerce").fillna(0).to_numpy())
    elif SIDED_COLUMN not in out.columns:
        out, copied = out.copy(), True
        out[SIDED_COLUMN] = np.full(len(out), SIDED_NONE, dtype="<U4")
    if not len(out):
        return out

    raw_bid = pd.to_numeric(out["bid"], errors="coerce").to_numpy(dtype=np.float64)
    raw_ask = pd.to_numeric(out["ask"], errors="coerce").to_numpy(dtype=np.float64)
    bid, ask, filled_bid, filled_ask = carry_sides(raw_bid, raw_ask)
    if not (filled_bid.any() or filled_ask.any()):
        return out
    if not copied:
        # NEVER WRITE THROUGH THE CALLER'S FRAME. A repair that edits its argument in place is a
        # repair that surprises the one caller who kept a reference to the original -- and the
        # audit, whose whole contract is that measuring changes nothing, is exactly that caller.
        out = out.copy()
    for name, raw, filled in (("bid", raw_bid, filled_bid), ("ask", raw_ask, filled_ask)):
        prior = (pd.to_numeric(out[f"{name}_raw"], errors="coerce").to_numpy(dtype=np.float64)
                 if f"{name}_raw" in out.columns else np.full(len(out), np.nan))
        keep = np.where(np.isnan(prior) & filled, raw, prior)
        if np.isfinite(keep).any():
            out[f"{name}_raw"] = keep
    out["bid"], out["ask"] = bid, ask
    return out


def sides_summary(df: pd.DataFrame) -> dict[str, int | float]:
    """What one tick frame says about its own sides. Cheap, read-only, no reconstruction.

    The fields a reader needs to judge a zero spread: how many rows the venue moved both sides
    on, how many carry a missing side, and what share of the QUOTED rows are locked. A locked
    share is only interpretable beside `sided_both`: 98% locked on ticks whose flags say BOTH
    sides moved is a venue that quotes zero, while 98% locked on bid-only ticks would be a writer
    repeating a side.
    """
    if df is None or not len(df) or "bid" not in df.columns or "ask" not in df.columns:
        return {"rows": 0}
    bid = pd.to_numeric(df["bid"], errors="coerce").to_numpy(dtype=np.float64)
    ask = pd.to_numeric(df["ask"], errors="coerce").to_numpy(dtype=np.float64)
    quoted = np.isfinite(bid) & np.isfinite(ask) & (bid > 0) & (ask > 0)
    n_q = int(quoted.sum())
    locked = int(np.count_nonzero(quoted & (bid == ask)))
    sided = (df[SIDED_COLUMN].to_numpy() if SIDED_COLUMN in df.columns
             else sided_from_flags(pd.to_numeric(df.get("flags", 0), errors="coerce")
                                   .fillna(0).to_numpy()) if "flags" in df.columns
             else np.full(len(df), SIDED_NONE))
    out: dict[str, int | float] = {
        "rows": len(df), "quoted": n_q, "locked": locked,
        "locked_frac": round(locked / n_q, 6) if n_q else 0.0,
        "missing_bid": int(np.count_nonzero(~(np.isfinite(bid) & (bid > 0)))),
        "missing_ask": int(np.count_nonzero(~(np.isfinite(ask) & (ask > 0)))),
    }
    for name in (SIDED_BID, SIDED_ASK, SIDED_BOTH, SIDED_LAST, SIDED_NONE):
        out[f"sided_{name}"] = int(np.count_nonzero(sided == name))
    return out


def merge_day(prev: pd.DataFrame | None, chunk: pd.DataFrame) -> pd.DataFrame:
    """The union of a day file and the new ticks, deduplicated on (time_msc, bid, ask, last),
    ordered by time_msc, columns aligned to the union and `ts` recomputed from time_msc.

    TWO WRITERS, ONE DAY FILE (measured 2026-09-16). `recorders/tick_recorder` writes
    recv_utc/recv_mono and no `ts`; this writer wrote `ts` and nothing else extra. Concatenating
    the two shapes and handing the frame to pandas' parquet writer raised
    `ArrowInvalid: Column 8 named ts expected length 44656 but got length 0` on every hourly
    pass, so the tape leg had failed for a day while the recorder task kept the tape alive.
    `ts` is now DERIVED from time_msc after the merge, and the file is written through an
    explicit Arrow table (`ticks_table`) so no pandas extension array reaches pyarrow.

    THE SIDES ARE REPAIRED HERE, which is what makes day files already on disk heal without
    anyone rewriting history. `repair_sides` adds `sided` (which side the venue moved, from the
    recorded flags) and fills any side that is genuinely absent from the last one this session
    saw. On the tape as it stands the fill is a measured no-op -- the raw values survive
    byte-for-byte -- so the only thing an existing file gains on its next merge is the column
    that lets a reader tell a carried side from a quoted one.
    """
    frames = [f for f in (prev, chunk) if f is not None and len(f)]
    if not frames:
        return repair_sides(chunk.iloc[0:0].copy())
    cols: list[str] = []
    for f in frames:
        for c in f.columns:
            if c != "ts" and c not in cols:
                cols.append(c)
    both = pd.concat([f.reindex(columns=cols) for f in frames], ignore_index=True)
    subset = [c for c in TICK_DEDUPE if c in both.columns]
    if subset:
        both = both.drop_duplicates(subset=subset)
    if "time_msc" in both.columns:
        both = both.sort_values("time_msc", kind="stable")
    both = repair_sides(both)
    if subset:
        # A SECOND PASS, AFTER THE REPAIR, and it is not redundant. The first dedupe keys on the
        # values as they arrived; a row whose absent side has just been filled can become
        # identical to the same tick that arrived complete in another pull, and two rows for one
        # tick is exactly the duplication the overlap policy exists to remove. Idempotent when
        # nothing was filled, which is every row today.
        both = both.drop_duplicates(subset=subset)
    if "time_msc" in both.columns:
        both["ts"] = pd.to_datetime(both["time_msc"], unit="ms", utc=True)
    return both.reset_index(drop=True)


def ticks_table(df: pd.DataFrame):
    """An explicit Arrow table for a tick frame: every column from its numpy values, `ts` as
    timestamp[ms, UTC] built from time_msc. Nothing here depends on pandas' datetime dtype."""
    import pyarrow as pa
    cols: dict[str, object] = {}
    for c in df.columns:
        if c == "ts":
            continue
        arr = df[c].to_numpy()
        if arr.dtype == object:
            cols[c] = pa.array([None if (x is None or (isinstance(x, float) and np.isnan(x)))
                                else str(x) for x in arr], type=pa.string())
        elif arr.dtype.kind in "US":
            # `sided` arrives as a fixed-width numpy unicode array. Named explicitly rather than
            # left to pyarrow's inference: a column whose type is decided by whichever value
            # happened to be widest is a column whose parquet schema changes between days.
            cols[c] = pa.array(arr.tolist(), type=pa.string())
        else:
            cols[c] = pa.array(arr)
    if "time_msc" in df.columns:
        ms = pd.to_numeric(df["time_msc"], errors="coerce").fillna(0).to_numpy().astype("int64")
        cols["ts"] = pa.array(ms, type=pa.timestamp("ms", tz="UTC"))
    return pa.table(cols)


def write_day(chunk: pd.DataFrame, out: Path) -> int:
    """Merge `chunk` into the day file at `out` and write it (zstd). Returns rows on disk."""
    import pyarrow.parquet as pq
    prev = None
    if out.exists():
        try:
            prev = pd.read_parquet(out)
        except Exception as exc:
            # One historical writer produced parquet whose footer advertised ``ts`` while its
            # physical column had zero values.  Arrow quite correctly refuses the whole table,
            # which used to stop the hourly recorder before it could replace the bad generation.
            # Every tick still has the authoritative integer ``time_msc``.  Salvage all physical
            # columns except the derived ``ts`` and let merge_day rebuild it; never discard or
            # silently replace a file when the remaining tick payload cannot be read.
            try:
                names = pq.ParquetFile(out).schema.names
                salvage = [name for name in names if name != "ts"]
                if "time_msc" not in salvage:
                    raise ValueError("legacy tape has no time_msc recovery column")
                prev = pq.read_table(out, columns=salvage).to_pandas()
            except Exception as salvage_exc:
                raise RuntimeError(
                    f"cannot read or losslessly salvage existing tick day {out}: {salvage_exc}"
                ) from exc
    merged = merge_day(prev, chunk)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".parquet.tmp")
    pq.write_table(ticks_table(merged), tmp, compression="zstd")
    tmp.replace(out)
    return len(merged)


def record_ticks(symbols: list[str]) -> dict:
    """Append every tick since the last recorded one, per symbol. Resumable and idempotent.

    Stored as one parquet per symbol per UTC day. Parquet rather than the crypto recorder's
    jsonl.gz because ticks are a fixed numeric schema: columnar storage is roughly an order of
    magnitude smaller for this shape, and the previous format is what filled the disk.

    EVERY ROW LANDS WITH ITS `sided` AND ITS BEST-KNOWN TWO-SIDED QUOTE, because `write_day` goes
    through `merge_day` -> `repair_sides`. The per-symbol summary carries `sides`, so a run that
    starts recording a one-sided feed says so on the cycle it happens rather than being found
    months later by whoever notices a zero median spread.
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
            # Append by rewriting the day through `write_day`: the union of what is on disk and
            # the new ticks, deduplicated on (time_msc, bid, ask, last), `ts` derived, written
            # as an explicit Arrow table (see merge_day for the failure this replaced).
            written += write_day(chunk, out)
        state[sym] = {"last_tick_ms": int(df["time_msc"].iloc[-1]),
                      "last_run": now.isoformat(timespec="seconds"),
                      "last_tick_utc": str(df["ts"].iloc[-1])}
        summary[sym] = {"new_ticks": len(df), "rows_on_disk_touched": written,
                        "through": str(df["ts"].iloc[-1]),
                        "sides": sides_summary(repair_sides(df))}

    TAPE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return summary


def asset_class_of(symbol: str) -> str:
    """The instrument's class, lower-cased, or "" when the desk cannot say.

    Routed through `research/universe_policy.asset_class_of` -- MetaTrader's OWN registry entry,
    never a symbol list in this file. The mandate is explicit that a hand-kept list is right on
    the day it is written and silently wrong afterwards, and a zero-spread rule keyed on one
    would stop applying to the next FX cross the broker lists. The fallback reads the same
    registry file directly, so a caller that cannot import the research package still gets the
    broker's answer; "" means UNCLASSIFIED, which is a verdict and never a permission.
    """
    sym = str(symbol or "").strip().upper()
    if not sym:
        return ""
    try:
        # GUARDED, because this is called once per instrument-day. The unguarded insert grew
        # sys.path by one entry per call and would put thousands of duplicates in front of every
        # import the integrity pass makes afterwards.
        desk = str(Path(__file__).resolve().parents[1])
        if desk not in sys.path:
            sys.path.insert(0, desk)
        from research.universe_policy import asset_class_of as _registry_class
        return str(_registry_class(sym) or "")
    except Exception:
        row = _load(DATA / "universe" / "universe.json", {}).get(sym)
        declared = row.get("asset_class") if isinstance(row, dict) else ""
        return " ".join(str(declared or "").strip().lower().replace("_", " ").split())


@lru_cache(maxsize=4096)
def is_fx(symbol: str) -> bool:
    """Is this instrument a currency pair, according to the broker's own registry?

    Cached: `tick_integrity` asks this once per symbol-day and again per row while totalling, and
    the registry behind it does not change inside a process. The cache is on the QUESTION, not on
    the registry -- `universe_policy` already caches the file it reads.
    """
    return asset_class_of(symbol).startswith(("forex", "fx"))


def day_files(symbol: str, root: Path | None = None) -> list[tuple[str, Path]]:
    """Every day file for one symbol as (ISO day, path), oldest first.

    TWO NAMING CONVENTIONS SHARE THIS DIRECTORY AND BOTH ARE REAL. `YYYY-MM-DD.parquet` is this
    module's own writer; `YYYYMMDD.parquet` is `moat/moat_silver.py` converting the streaming
    recorder's bronze. A reader that knows only one of them silently measures half the tape --
    and half the tape is exactly the shape of evidence that produces a confident wrong answer.
    """
    d = (root or TICKS) / symbol
    out: list[tuple[str, Path]] = []
    if not d.is_dir():
        return out
    for p in d.glob("*.parquet"):
        stem = p.stem
        if len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
            out.append((stem, p))
        elif len(stem) == 8 and stem.isdigit():
            out.append((f"{stem[:4]}-{stem[4:6]}-{stem[6:]}", p))
    return sorted(out)


#: A day whose quoted ticks are locked (ask == bid) above this share, on an instrument the
#: broker's registry calls a currency pair, is ONE_SIDED and is named as such. Defined here
#: beside the measurement so the audit and `tick_integrity` cannot be judged at two lines.
ONE_SIDED_FX_FRAC = 0.20


def audit_sides(symbols: list[str] | None = None, days: int = 3,
                root: Path | None = None) -> dict:
    """READ-ONLY. What the tape's sides look like before and after the repair, per instrument-day.

    Nothing here writes: it reads the last `days` day files per symbol, runs `repair_sides` in
    memory and reports both fractions. The repair itself runs only in the tests and on the next
    real merge -- a measurement that silently rewrites the thing it is measuring cannot be used
    to decide whether the rewrite was a good idea.
    """
    tick_root = root or TICKS
    if symbols:
        syms = list(symbols)
    elif tick_root.is_dir():
        syms = sorted(d.name for d in tick_root.iterdir() if d.is_dir())
    else:
        syms = []
    rows: list[dict] = []
    for sym in syms:
        # THE LAST N CALENDAR DAYS, NOT THE LAST N FILES, and the difference is not cosmetic: two
        # writers lay down two files for the same day under two naming conventions, so "the last
        # three files" is the last day and a half for a symbol both of them cover and the last
        # three days for a symbol only one does. A window whose length depends on which writers
        # happened to run is a window no two symbols can be compared across.
        files = day_files(sym, tick_root)
        wanted = set(sorted({d for d, _ in files})[-max(1, int(days)):])
        for day, path in files:
            if day not in wanted:
                continue
            try:
                df = pd.read_parquet(path, columns=["time_msc", "bid", "ask", "flags"])
            except Exception as exc:
                rows.append({"symbol": sym, "day": day, "file": path.name,
                             "error": f"{type(exc).__name__}: {exc}"})
                continue
            df = df.sort_values("time_msc", kind="stable")
            before = sides_summary(df)
            after = sides_summary(repair_sides(df))
            rows.append({
                "symbol": sym, "day": day, "file": path.name,
                # WHICH WRITER LAID THIS FILE DOWN. Both write into one directory under two
                # naming conventions, and seeing the SAME fraction from two independent pulls of
                # the same day is the evidence that separates a feed property from a writer bug.
                "writer": "hourly" if "-" in path.stem else "silver",
                "asset_class": asset_class_of(sym), "fx": is_fx(sym),
                "rows": before.get("rows", 0),
                "zero_spread_frac_before": before.get("locked_frac", 0.0),
                "zero_spread_frac_after": after.get("locked_frac", 0.0),
                "filled_bid": int(before.get("missing_bid", 0)) - int(after.get("missing_bid", 0)),
                "filled_ask": int(before.get("missing_ask", 0)) - int(after.get("missing_ask", 0)),
                "sided_both": after.get("sided_both", 0), "sided_bid": after.get("sided_bid", 0),
                "sided_ask": after.get("sided_ask", 0), "sided_last": after.get("sided_last", 0),
                "sided_none": after.get("sided_none", 0),
            })
    ok = [r for r in rows if "error" not in r]
    fx = [r for r in ok if r["fx"]]
    return {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "tape_root": str(tick_root), "days_back": int(days),
        "symbols": len(syms), "instrument_days": len(rows),
        "unreadable": len(rows) - len(ok),
        "rows_scanned": sum(int(r["rows"]) for r in ok),
        "sides_filled": sum(int(r["filled_bid"]) + int(r["filled_ask"]) for r in ok),
        "fx_instrument_days_over_line": sum(
            1 for r in fx if r["zero_spread_frac_after"] > ONE_SIDED_FX_FRAC),
        "fx_instrument_days": len(fx),
        "rows": rows,
    }


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


def _dry_run(argv: list[str]) -> int:
    """`--dry-run`: measure the sides on the tape already on disk and change nothing.

    Kept ahead of the MetaTrader import on purpose -- the audit reads parquet, so it must run on
    a box with no terminal, in CI, and while the terminal is busy holding live positions.
    """
    days = 3
    for i, a in enumerate(argv):
        if a == "--days" and i + 1 < len(argv):
            with suppress(ValueError):
                days = int(argv[i + 1])
    syms = [s for a in argv for s in ([] if not a.startswith("--symbols=")
                                      else a.split("=", 1)[1].split(","))]
    rep = audit_sides(syms or None, days)
    if "--json" in argv:
        print(json.dumps(rep, indent=1, default=str))
        return 0
    print(f"tape sides audit (READ-ONLY): {rep['tape_root']}  last {rep['days_back']} day "
          f"file(s) per symbol  {rep['symbols']} symbols  {rep['instrument_days']} "
          f"instrument-days  {rep['rows_scanned']:,} rows")
    print(f"  sides filled by the repair: {rep['sides_filled']}   unreadable files: "
          f"{rep['unreadable']}")
    print(f"  FX instrument-days over the {ONE_SIDED_FX_FRAC:.0%} ONE_SIDED line: "
          f"{rep['fx_instrument_days_over_line']} of {rep['fx_instrument_days']}")
    print(f"  {'symbol':<18}{'day':<12}{'writer':<8}{'class':<16}{'rows':>10}"
          f"{'zero%before':>13}{'zero%after':>12}{'sided both/bid/ask':>22}")
    rows = sorted((r for r in rep["rows"] if "error" not in r),
                  key=lambda r: -float(r["zero_spread_frac_after"]))
    for r in rows[:40]:
        print(f"  {r['symbol']:<18}{r['day']:<12}{r['writer']:<8}"
              f"{(r['asset_class'] or '-'):<16}"
              f"{r['rows']:>10,}{r['zero_spread_frac_before']:>13.4%}"
              f"{r['zero_spread_frac_after']:>12.4%}"
              f"{r['sided_both']:>10,}/{r['sided_bid']:,}/{r['sided_ask']:,}")
    for r in (r for r in rep["rows"] if "error" in r):
        print(f"  UNREADABLE {r['symbol']}/{r['day']}: {r['error']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--dry-run" in argv:
        return _dry_run(argv)
    import MetaTrader5 as mt5
    from mt5desk.config import terminal_path

    if mt5.terminal_info() is None and not mt5.initialize(path=terminal_path()):
        print(f"mt5 init failed: {_explain(mt5.last_error())}")
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


def _explain(err: object) -> str:
    """Route the raw MT5 error through the shared explanation -- see h1_source.

    Imported lazily and falling back to the bare error: a diagnostic helper must never be the
    reason a producer cannot start.
    """
    try:
        from research.h1_source import explain_init_failure
    except ImportError:
        try:
            from h1_source import explain_init_failure  # type: ignore[no-redef]
        except ImportError:
            return f"{err}"
    return explain_init_failure(err)
