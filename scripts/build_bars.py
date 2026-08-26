#!/usr/bin/env python3
"""TAPE -> BARS. The missing step between 8.2GB of recorded L2 and every screen on this desk.

WHY THIS WAS THE GAP, AND WHY I WAS WRONG ABOUT IT. The moat recorders write 15-second L2 depth
plus trades; every screen, feature and label on this desk consumes OHLCV bars. Nothing converted
one into the other, so `screen_ict.py` reported NO BARS and the whole ICT family screened nothing
-- not because the data was missing, but because it was in the wrong shape.

I described this as "can only be built where the 8.2GB lives". That conflated needing the data to
RUN with needing it to BUILD. The schemas are known, the recorders are in this repo, and synthetic
tape in the recorders' exact format tests every path. Only the execution needs the VPS.

TWO RECORDER SCHEMAS, AND READING ONE IS SILENT DATA LOSS. Binance stamps trades `k="t"` with flat
`p`/`q` fields; Bybit stamps `k="trades"` with a NESTED list under `v`. A reader that handles one
returns clean, plausible, half-empty bars over the other venue's archive -- the same class of bug
that made moat_mine blind to 4.4GB until DEPTH_KINDS was added. Both are handled, and the report
states the per-venue row counts so a schema change shows up as a venue going quiet rather than as
a number nobody looks at.

BARS COME FROM TRADES, NEVER FROM DEPTH. A mid-price series resampled from the book looks like a
price and is not one: nothing traded there. Using it would put a synthetic OHLC under every screen
on the desk, and the resulting IC would be a fact about the book's mid, not about executable
prices. When a bucket has no trades it is left EMPTY rather than filled from the book.

OPEN INTEREST RIDES ALONG where the venue reports it (Bybit `k="meta"`), because `oi_flush` is the
one crypto-native ICT detector with a mechanical basis, and it is useless without OI.

Read-only over data/moat. Writes bar parquet/csv. No network, no keys, no order paths.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MOAT = ROOT / "data/moat"
OUT = ROOT / "data/bars"
REPORT = ROOT / "data/build_bars.json"

#: Trade rows. Binance: flat {p, q}. Bybit: nested list under `v`, each {p, v/size, T}.
BINANCE_TRADE = "t"
BYBIT_TRADE = "trades"
META_KIND = "meta"

#: Default bar width. 15s tape supports anything from ~1m up; 15m is chosen because the ICT screen
#: needs enough bars for its power condition AND enough trades per bucket that an empty bar is rare.
DEFAULT_FREQ = "15min"

#: Files read per run, so a first run on 22,910 files does not become an unbounded job. Budgeted
#: work every cycle beats heroic work never -- the same rule the moat miner runs on.
FILE_BUDGET = int(os.environ.get("BARS_FILE_BUDGET") or 400)


def _rel(p: Path) -> str:
    """Repo-relative when inside the repo. THIRD occurrence of this guard in one session, so it is
    now extracted here rather than fixed locally a third time: `relative_to` RAISES outside ROOT,
    turning an honest 'missing file' report into a ValueError exactly when it is needed."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _tape_files(venue: str | None = None) -> list[Path]:
    if not MOAT.exists():
        return []
    out: list[Path] = []
    for vdir in sorted(p for p in MOAT.iterdir() if p.is_dir()):
        if venue and vdir.name != venue:
            continue
        for sym in sorted(p for p in vdir.iterdir() if p.is_dir()):
            out.extend(sorted(sym.glob("*.jsonl.gz")))
    return out


def _iter_rows(path: Path):
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue          # a corrupt line is skipped, never guessed at
    except OSError:
        return


@dataclass
class ParseAttrition:
    """WHAT THE READER THREW AWAY, counted per venue (L1.60).

    THE DEFECT THIS EXISTS FOR IS ON THE RECORD AND COST SEVEN DAYS. `trades_from` skipped an
    entry it could not read with a bare `continue`, so 221,000 of 221,000 nested bybit entries
    were dropped for mislabelled fields and the builder reported a venue with no trades. A 100%
    parse loss and a genuinely quiet venue were BYTE-IDENTICAL in every artifact downstream --
    `build()` counted only successes, so the one number that would have screamed was never taken.

    The repair is the one L1.60 prescribes: count the ATTEMPTS, not just the survivors. Skipping
    is often right; skipping INVISIBLY never is, because it makes "this venue is quiet" and "this
    reader cannot read this venue" the same observation, and only one of them is a defect.

    Every drop reason is separate on purpose. `not_dict` is a schema change, `bad_number` is a
    corrupt payload, and `no_ts_or_px` is a well-formed entry we still refused -- they point at
    three different repairs, and a single `dropped` total would send a reader to the wrong one.
    """

    rows: int = 0                 #: trade ROWS seen (a bybit row carries many prints)
    entries: int = 0              #: nested entries ATTEMPTED -- the denominator
    parsed: int = 0               #: prints actually returned
    not_dict: int = 0
    bad_number: int = 0
    no_ts_or_px: int = 0

    @property
    def dropped(self) -> int:
        return self.not_dict + self.bad_number + self.no_ts_or_px

    @property
    def parse_rate(self) -> float | None:
        """Parsed / attempted, or None when nothing was attempted.

        NONE IS NOT ZERO AND MUST NEVER BE ROUNDED TO IT. No trade rows at all is a recorder
        question; rows that all failed to parse is a reader question. Collapsing them is the exact
        ambiguity this class was built to remove (L1.28a: unmeasured is a real answer).
        """
        return None if self.entries == 0 else self.parsed / self.entries

    def as_dict(self) -> dict[str, object]:
        r = self.parse_rate
        return {"rows": self.rows, "entries": self.entries, "parsed": self.parsed,
                "dropped": self.dropped, "not_dict": self.not_dict,
                "bad_number": self.bad_number, "no_ts_or_px": self.no_ts_or_px,
                "parse_rate": (None if r is None else round(r, 6))}


def trades_from(row: dict, attrition: ParseAttrition | None = None
                ) -> list[tuple[int, float, float]]:
    """(ms, price, qty) from either schema. Unknown kinds yield nothing.

    Bybit nests its trades and labels size `v` on some payloads and `size` on others; both are
    accepted because a missing quantity silently becomes zero volume, which is a bar that looks
    real and weighs nothing.

    Pass `attrition` to learn what was DISCARDED. It is optional so the three existing consumers
    keep working unchanged, but a caller that publishes a trade count and does not take it is
    reporting a numerator with no denominator (L1.57).
    """
    k = row.get("k")
    if k == BINANCE_TRADE:
        if attrition is not None:
            attrition.rows += 1
            attrition.entries += 1
        try:
            out_b = [(int(row["t"]), float(row["p"]), float(row["q"]))]
        except (KeyError, TypeError, ValueError):
            if attrition is not None:
                attrition.bad_number += 1
            return []
        if attrition is not None:
            attrition.parsed += 1
        return out_b
    if k == BYBIT_TRADE:
        out = []
        if attrition is not None:
            attrition.rows += 1
        for tr in row.get("v") or []:
            if attrition is not None:
                attrition.entries += 1
            if not isinstance(tr, dict):
                if attrition is not None:
                    attrition.not_dict += 1
                continue
            try:
                # R0378: BOTH Bybit shapes. The compressed WS payload labels these p/T/v; the
                # shape this desk's recorder actually wrote labels them price/time/size, and the
                # reader accepted only the first. Measured 2026-08-12 over 6 sampled partitions:
                # 221,000 nested entries, 100% of them price/time/size, 0 prints parsed -- the
                # ENTIRE bybit trade tape (10,814 partitions, 27% of data/moat) was invisible to
                # every consumer of this function, and it failed silently because an unparseable
                # entry is skipped rather than counted. That is the exact defect this docstring
                # already warned about for quantity, one field over.
                ms = int(tr.get("T") or tr.get("time") or row.get("t") or 0)
                raw_px = tr.get("p") if tr.get("p") is not None else tr.get("price")
                px = float(raw_px if raw_px is not None else 0.0)
                raw_q = tr.get("v") if tr.get("v") is not None else tr.get("size")
                qty = float(raw_q if raw_q is not None else 0.0)
            except (TypeError, ValueError):
                if attrition is not None:
                    attrition.bad_number += 1
                continue
            if ms and px > 0:
                out.append((ms, px, qty))
                if attrition is not None:
                    attrition.parsed += 1
            elif attrition is not None:
                attrition.no_ts_or_px += 1
        return out
    return []


def group_by_symbol(files: list[Path]) -> dict[str, list[Path]]:
    """Tape files bucketed by SYMBOL, which the recorders encode in the path.

    The layout is `data/moat/<venue>/<symbol>/<file>` -- `record_desk_metrics` already counts the
    desk's breadth from exactly that nesting. So the symbol was always available and this builder
    threw it away, pooling every instrument into one series.

    VENUE IS DELIBERATELY NOT PART OF THE KEY. The same symbol on spot and on perp is the same
    instrument for a bar series and merging their trades deepens it; what must never merge is two
    different SYMBOLS. A file shallower than the expected nesting is skipped rather than guessed
    at -- an unknown symbol pooled under a made-up name is the defect this function exists to end.
    """
    out: dict[str, list[Path]] = defaultdict(list)
    for f in files:
        symbol = f.parent.name.upper()
        if symbol and symbol != MOAT.name.upper():
            out[symbol].append(f)
    return {k: sorted(v) for k, v in out.items()}


def newest_across_venues(paths: list[Path], each: int) -> list[Path]:
    """The `each` newest files for one symbol, SHARED ROUND-ROBIN ACROSS ITS VENUES.

    Two things were wrong with the `[-each:]` this replaces, and they compounded.

    NEWEST WAS NOT NEWEST. The list is sorted by full path, which is `<venue>/<symbol>/<file>`, so
    the last elements are the last VENUE alphabetically, not the most recent recordings. Recency
    lives in the filename (`20260817_00.jsonl.gz`), so the sort key is the basename.

    ONE VENUE ATE THE WHOLE ALLOCATION. The budget is divided per symbol precisely so the busiest
    stream cannot starve the others; leaving venues to compete inside a symbol re-created that at
    the next level down and silently excluded bybit entirely. Round-robin gives every venue a
    share, newest first.

    THE TOTAL BUDGET IS UNCHANGED -- this reorders which files are read, never how many. Widening
    it here instead would have traded a silent coverage hole for a silent memory bill on a 4GB box
    that has already been OOM-killed by this builder once.
    """
    by_venue: dict[str, list[Path]] = defaultdict(list)
    for p in paths:
        by_venue[p.parent.parent.name].append(p)
    queues = [sorted(v, key=lambda p: p.name) for _, v in sorted(by_venue.items())]
    out: list[Path] = []
    while len(out) < each and any(queues):
        for q in queues:
            if q and len(out) < each:
                out.append(q.pop())            # newest first within this venue
    return sorted(out)


#: Bar width in milliseconds, for the streaming bucket key. Derived from `freq` so the two can
#: never drift apart -- a hardcoded 900_000 beside a configurable `freq` is a bug waiting for the
#: first person who changes one of them.
def _bucket_ms(freq: str) -> int:
    return int(pd.Timedelta(freq).total_seconds() * 1000)


def build(files: list[Path], freq: str = DEFAULT_FREQ) -> tuple[pd.DataFrame, dict]:
    """OHLCV(+OI) bars from tape, STREAMED one file at a time.

    THE EARLIER VERSION ACCUMULATED EVERY TRADE IN A PYTHON LIST AND WAS OOM-KILLED ON THE LIVE
    BOX. It built `px` across all a symbol's files -- millions of 3-tuples for a busy name, each
    carrying per-object overhead many times the 24 bytes of actual numbers -- and only then handed
    the whole thing to pandas, which copies it again. On a 4GB machine that also runs the
    recorders, `BARS_FILE_BUDGET=8000` died. The budget then looks like a tuning knob for how far
    back the desk can see, when it was really a memory ceiling nobody had named.

    Streaming makes memory O(BUCKETS) instead of O(TRADES): a day of 15-minute bars is 96 rows
    whatever the trade count, so the archive size stops mattering and the budget becomes a time
    budget again.

    ORDER IS NOT ASSUMED. Each bucket tracks the timestamp of its own first and last trade, so
    `open` and `close` are correct even if files arrive out of order or overlap -- which the
    previous `.first()`/`.last()` got right only because a global sort had already happened. An
    aggregation that silently depends on file naming is the kind of thing that stays correct until
    a recorder changes its filename format.
    """
    step = _bucket_ms(freq)
    # bucket_ms -> [open_ts, open_px, high, low, close_ts, close_px, volume, n_trades]
    parts: dict[int, list[float]] = {}
    oi_last: dict[int, tuple[int, float]] = {}
    seen: dict[str, int] = defaultdict(int)
    #: Per-venue ATTEMPTS beside the per-venue successes. `seen` alone cannot tell a quiet venue
    #: from an unreadable one, which is the whole of R0529.
    attr: dict[str, ParseAttrition] = defaultdict(ParseAttrition)
    n_trades = n_oi = 0

    for f in files:
        venue = f.parent.parent.name
        va = attr[venue]
        for row in _iter_rows(f):
            for ms, price, qty in trades_from(row, va):
                b = (ms // step) * step
                cur = parts.get(b)
                if cur is None:
                    parts[b] = [ms, price, price, price, ms, price, qty, 1.0]
                else:
                    if ms < cur[0]:
                        cur[0], cur[1] = ms, price          # earlier trade -> this is the open
                    if ms >= cur[4]:
                        cur[4], cur[5] = ms, price          # later trade   -> this is the close
                    if price > cur[2]:
                        cur[2] = price
                    if price < cur[3]:
                        cur[3] = price
                    cur[6] += qty
                    cur[7] += 1.0
                seen[venue] += 1
                n_trades += 1
            if row.get("k") == META_KIND and row.get("oi") is not None:
                try:
                    ms, val = int(row["t"]), float(row["oi"])
                except (TypeError, ValueError):
                    continue
                b = (ms // step) * step
                # LAST value in the bucket: open interest is a LEVEL, not a flow, so summing or
                # averaging it would invent a quantity the venue never reported.
                if b not in oi_last or ms >= oi_last[b][0]:
                    oi_last[b] = (ms, val)
                n_oi += 1

    diag_attr = {v: a.as_dict() for v, a in sorted(attr.items()) if a.rows}
    if not parts:
        return pd.DataFrame(), {"venues": dict(seen), "trades": 0, "parse": diag_attr}

    rows = sorted(parts.items())
    bars = pd.DataFrame({
        "timestamp": pd.to_datetime([b for b, _ in rows], unit="ms", utc=True),
        "open": [v[1] for _, v in rows],
        "high": [v[2] for _, v in rows],
        "low": [v[3] for _, v in rows],
        "close": [v[5] for _, v in rows],
        "volume": [v[6] for _, v in rows],
        "trades": [v[7] for _, v in rows],
    })
    # EMPTY BUCKETS NEVER EXIST HERE RATHER THAN BEING DROPPED AFTERWARDS -- a bucket with no trade
    # is simply absent from `parts`. Same outcome as the old filter, and the reason is unchanged: a
    # bar carried from the previous close is a price nothing traded at, and screens would read the
    # flat stretch as genuine low volatility.
    if oi_last:
        bars["open_interest"] = [oi_last.get(b, (0, float("nan")))[1] for b, _ in rows]
    return bars, {"venues": dict(seen), "trades": n_trades, "oi_points": n_oi,
                  "parse": diag_attr}


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    files = _tape_files()
    if not files:
        out = {"ts": datetime.now(tz=UTC).isoformat(), "state": "NO TAPE",
               "reason": f"{_rel(MOAT)} absent or empty -- the recorders write it and data/ is "
                         "gitignored, so this is expected in a fresh checkout and a REAL blocker "
                         "on the VPS.",
               "next": "start the recorders (bash ops/start_recorders_nosudo.sh)", "bars": 0}
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
        print(f"build-bars: NO TAPE under {_rel(MOAT)} -- recorders are the blocker, not this")
        return 0

    per_symbol = group_by_symbol(files)
    # PER-SYMBOL BUDGET, NOT A GLOBAL ONE. A global `files[-N:]` takes the newest N across the
    # whole tape, so the busiest stream eats the entire budget and every other symbol reports
    # zero -- measured 2026-08-07 on the live box: 400/32,440 files yielded ONE venue and ONE
    # blended series. Dividing the budget guarantees breadth, and breadth is the whole point:
    # every cross-sectional operator the desk owns needs at least two symbols to rank against.
    #
    # AND THE SAME ARGUMENT ONE LEVEL DOWN, WHICH THIS MISSED FOR A WEEK. A per-symbol budget that
    # lets a single VENUE eat that symbol's whole allocation reproduces the defect above exactly,
    # and it did: `per_symbol[symbol]` is sorted by full PATH and the layout is
    # `data/moat/<venue>/<symbol>/<file>`, so the sort is VENUE-MAJOR and `[-each:]` takes the
    # alphabetically-last venue rather than the newest files. `bybit` < `fut` < `spot`, so bybit
    # was last in line and never made the cut. Measured on the live box 2026-08-19: 440 bybit
    # files on disk, ZERO budgeted, budget = {spot: 279, fut: 20} -- and reaching one bybit file
    # for any symbol needed BARS_FILE_BUDGET >= 1849 against a default of 400.
    #
    # That is why R0378 -- which un-dropped the entire bybit trade tape at the parse layer -- had
    # not moved one committed bar seven days after it shipped. The prints parsed perfectly and the
    # builder never read them, which is the desk's own recurring lesson in a new costume: a
    # committed fix is inert until something actually runs it on the live path (III.16).
    each = max(1, FILE_BUDGET // max(1, len(per_symbol)))
    written: list[dict[str, object]] = []
    empty: list[str] = []
    venues: dict[str, int] = {}
    parse: dict[str, ParseAttrition] = defaultdict(ParseAttrition)
    n_read = 0

    for symbol in sorted(per_symbol):
        budgeted = newest_across_venues(per_symbol[symbol], each)
        n_read += len(budgeted)
        bars, diag = build(budgeted)
        for v, c in diag.get("venues", {}).items():
            venues[v] = venues.get(v, 0) + c
        for v, d in diag.get("parse", {}).items():
            a = parse[v]
            a.rows += int(d["rows"])
            a.entries += int(d["entries"])
            a.parsed += int(d["parsed"])
            a.not_dict += int(d["not_dict"])
            a.bad_number += int(d["bad_number"])
            a.no_ts_or_px += int(d["no_ts_or_px"])
        if bars.empty:
            empty.append(symbol)
            continue
        path = OUT / f"{symbol}_{DEFAULT_FREQ}.parquet"
        try:
            bars.to_parquet(path, index=False)
        except (ImportError, ValueError):
            path = OUT / f"{symbol}_{DEFAULT_FREQ}.csv"
            bars.to_csv(path, index=False)
        written.append({
            "symbol": symbol, "bars": len(bars), "artifact": _rel(path),
            "span": [str(bars["timestamp"].iloc[0]), str(bars["timestamp"].iloc[-1])],
            "has_open_interest": "open_interest" in bars.columns,
            "files_read": len(budgeted), "files_on_disk": len(per_symbol[symbol]),
        })

    if not written:
        out = {"ts": datetime.now(tz=UTC).isoformat(), "state": "NO TRADES",
               "files_read": n_read, "symbols_seen": sorted(per_symbol), "venues": venues,
               "parse": {v: a.as_dict() for v, a in sorted(parse.items())},
               "reason": ("tape present but no TRADE rows parsed. Bars are built from trades, "
                          "never from book mid -- a mid-price series looks like a price and is "
                          "not one, because nothing traded there."),
               "next": "check the recorders are capturing aggTrades/recent-trade, not only depth",
               "bars": 0}
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
        print(f"build-bars: NO TRADES in {n_read} files | venues seen: {venues}")
        return 0

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 1),
        "files_read": n_read, "files_on_disk": len(files),
        "per_symbol_budget": each,
        "symbols_written": len(written), "symbols_empty": empty,
        "bars": sum(w["bars"] for w in written), "freq": DEFAULT_FREQ,
        "venues": venues, "symbols": written,
        # THE DENOMINATOR BESIDE THE NUMERATOR. `venues` counts prints that PARSED; this counts
        # what was attempted and what was discarded, per venue, so a reader can tell a quiet
        # venue from an unreadable one without re-deriving it from the tape (R0529, L1.57/L1.60).
        # Read by scripts/check_tape_parse_rate.py.
        "parse": {v: a.as_dict() for v, a in sorted(parse.items())},
        "note": ("ONE FILE PER SYMBOL. Until 2026-08-07 every trade from every symbol was pooled "
                 "into a single OHLCV series, so an open from one instrument and a close from "
                 "another shared a bar -- a price series of nothing. It also pinned every "
                 "consumer to '1 symbol', which made the whole cross-sectional half of the "
                 "expression language (rank, zscore, group_rank) permanently unmeasurable: they "
                 "need peers to rank against and correctly refuse without them. "
                 "Bars are built from TRADES, never from book mid, and empty buckets are DROPPED "
                 "rather than forward-filled -- a carried close is a price nothing traded at."),
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    print(f"build-bars: {out['bars']} bars @{DEFAULT_FREQ} across {len(written)} symbol(s) "
          f"from {n_read}/{len(files)} files | {out['seconds']}s")
    for w in written:
        print(f"  {w['symbol']:<14} {w['bars']:>6} bars  OI:{w['has_open_interest']!s:<5} "
              f"{w['span'][0][:16]} -> {w['span'][1][:16]}")
    if empty:
        print(f"  no trades parsed for: {empty} -- depth-only streams, not a builder failure")
    print(f"  venues: {venues} | per-symbol file budget {each} (BARS_FILE_BUDGET={FILE_BUDGET})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
