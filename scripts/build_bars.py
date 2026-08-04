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


def trades_from(row: dict) -> list[tuple[int, float, float]]:
    """(ms, price, qty) from either schema. Unknown kinds yield nothing.

    Bybit nests its trades and labels size `v` on some payloads and `size` on others; both are
    accepted because a missing quantity silently becomes zero volume, which is a bar that looks
    real and weighs nothing.
    """
    k = row.get("k")
    if k == BINANCE_TRADE:
        try:
            return [(int(row["t"]), float(row["p"]), float(row["q"]))]
        except (KeyError, TypeError, ValueError):
            return []
    if k == BYBIT_TRADE:
        out = []
        for tr in row.get("v") or []:
            if not isinstance(tr, dict):
                continue
            try:
                ms = int(tr.get("T") or row.get("t") or 0)
                px = float(tr.get("p"))
                qty = float(tr.get("v") if tr.get("v") is not None else tr.get("size") or 0.0)
            except (TypeError, ValueError):
                continue
            if ms and px > 0:
                out.append((ms, px, qty))
        return out
    return []


def build(files: list[Path], freq: str = DEFAULT_FREQ) -> tuple[pd.DataFrame, dict]:
    """OHLCV(+OI) bars from tape. Returns (bars, per-venue diagnostics)."""
    px: list[tuple[int, float, float]] = []
    oi: list[tuple[int, float]] = []
    seen: dict[str, int] = defaultdict(int)
    for f in files:
        venue = f.parent.parent.name
        for row in _iter_rows(f):
            t = trades_from(row)
            if t:
                px.extend(t)
                seen[venue] += len(t)
            elif row.get("k") == META_KIND and row.get("oi") is not None:
                try:
                    oi.append((int(row["t"]), float(row["oi"])))
                except (TypeError, ValueError):
                    continue
    if not px:
        return pd.DataFrame(), {"venues": dict(seen), "trades": 0}

    tdf = pd.DataFrame(px, columns=["ms", "price", "qty"])
    tdf["timestamp"] = pd.to_datetime(tdf["ms"], unit="ms", utc=True)
    tdf = tdf.sort_values("timestamp").set_index("timestamp")
    g = tdf["price"].resample(freq)
    bars = pd.DataFrame({
        "open": g.first(), "high": g.max(), "low": g.min(), "close": g.last(),
        "volume": tdf["qty"].resample(freq).sum(),
        "trades": tdf["price"].resample(freq).count(),
    })
    # EMPTY BUCKETS ARE DROPPED, NOT FORWARD-FILLED. A bar carried from the previous close is a
    # price nothing traded at; screens would read the flat stretch as genuine low volatility and
    # every vol-scaled feature downstream would be wrong in the same direction.
    bars = bars[bars["trades"] > 0]
    if oi:
        odf = pd.DataFrame(oi, columns=["ms", "open_interest"])
        odf["timestamp"] = pd.to_datetime(odf["ms"], unit="ms", utc=True)
        # LAST value in the bucket: open interest is a level, not a flow, so summing or averaging
        # it would invent a quantity the venue never reported.
        oser = odf.sort_values("timestamp").set_index("timestamp")["open_interest"]
        o = oser.resample(freq).last()
        bars = bars.join(o)
    bars = bars.reset_index()
    return bars, {"venues": dict(seen), "trades": len(px), "oi_points": len(oi)}


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

    budgeted = files[-FILE_BUDGET:]        # newest first: the recent window is what screens need
    bars, diag = build(budgeted)
    if bars.empty:
        out = {"ts": datetime.now(tz=UTC).isoformat(), "state": "NO TRADES",
               "files_read": len(budgeted), "diagnostics": diag,
               "reason": ("tape present but no TRADE rows parsed. Bars are built from trades, "
                          "never from book mid -- a mid-price series looks like a price and is "
                          "not one, because nothing traded there."),
               "next": "check the recorders are capturing aggTrades/recent-trade, not only depth",
               "bars": 0}
        REPORT.write_text(json.dumps(out, indent=1), "utf-8")
        print(f"build-bars: NO TRADES in {len(budgeted)} files | venues seen: {diag['venues']}")
        return 0

    path = OUT / f"bars_{DEFAULT_FREQ}.parquet"
    try:
        bars.to_parquet(path, index=False)
    except (ImportError, ValueError):
        path = OUT / f"bars_{DEFAULT_FREQ}.csv"
        bars.to_csv(path, index=False)

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "seconds": round(time.time() - t0, 1),
        "files_read": len(budgeted), "files_on_disk": len(files),
        "bars": len(bars), "freq": DEFAULT_FREQ, "artifact": _rel(path),
        "span": [str(bars["timestamp"].iloc[0]), str(bars["timestamp"].iloc[-1])],
        "has_open_interest": "open_interest" in bars.columns,
        "diagnostics": diag,
        "note": ("Bars are built from TRADES, never from book mid: nothing trades at the mid, and "
                 "a synthetic OHLC under every screen would yield ICs about the book rather than "
                 "about executable prices. Empty buckets are DROPPED, not forward-filled -- a "
                 "carried close is a price nothing traded at, and screens would read the flat "
                 "stretch as genuine low volatility."),
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    print(f"build-bars: {len(bars)} bars @{DEFAULT_FREQ} from {len(budgeted)}/{len(files)} files "
          f"-> {_rel(path)} | {out['seconds']}s")
    print(f"  venues: {diag['venues']} | OI: {out['has_open_interest']} | "
          f"{out['span'][0][:16]} -> {out['span'][1][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
