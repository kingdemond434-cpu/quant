#!/usr/bin/env python3
"""POINT-IN-TIME UNIVERSE SNAPSHOT (R0239): record which symbols existed, and in what state, TODAY.

THE DEFECT IT CLOSES. libs/data/crypto_source.list_perp_symbols filters exchangeInfo to
`status == "TRADING"` and throws the rest away, and every ingest builds its universe from that.
So every backfilled panel is conditioned on the symbol SURVIVING TO THE DAY THE BACKFILL RAN --
textbook survivorship bias. LUNA, UST, FTT and SRM are absent from a seven-year history not
because they did not trade but because they died, and their deaths are exactly the observations a
cross-sectional study most needs. The desk's own deep sweep flagged this as unquantified
survivorship inflation on every cross-sectional backtest, i.e. a live false-promotion risk.

WHY IT IS URGENT RATHER THAN IMPORTANT. Most defects wait harmlessly. This one does not: a
point-in-time snapshot NOT TAKEN TODAY CANNOT BE TAKEN TOMORROW. Every day without it is a day
permanently missing from the desk's ability to ask "what could I have traded on this date?" The
call already happens on every run and is discarded -- so the cost of fixing it is one file write,
and the cost of not fixing it compounds daily and is irreversible.

WHAT IT DOES NOT DO, stated so nobody reads more into it than it earns: this fixes the panel
FORWARD. It does not retroactively restore delisted history -- that is a reconstruction from
binance.vision delisted-symbol archives, a separate and much larger job. Today's snapshot is the
first row of a series that only becomes valuable by existing continuously.

Appends one gzipped JSON line per day to data/universe_snapshots.jsonl.gz -- append-only, because
a snapshot that can be rewritten is not a point-in-time record.
"""
from __future__ import annotations

import gzip
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/universe_snapshots.jsonl.gz"
_FAPI = "https://fapi.binance.com"
_UA = {"User-Agent": "Mozilla/5.0 (quant-desk universe-snapshot)"}


def _get(url: str, timeout: int = 30):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=_UA), timeout=timeout).read())


def main() -> None:
    today = datetime.now(tz=UTC).date().isoformat()
    if OUT.exists():
        with gzip.open(OUT, "rt", encoding="utf-8") as fh:
            for line in fh:
                if line.strip() and json.loads(line).get("date") == today:
                    print(f"universe snapshot for {today} already recorded -- append-only, skipping")
                    return

    info = _get(f"{_FAPI}/fapi/v1/exchangeInfo")
    syms = info.get("symbols", []) if isinstance(info, dict) else []
    if not syms:
        raise SystemExit("exchangeInfo returned no symbols -- refusing to write an empty snapshot")

    # EVERY status, not just TRADING. The non-TRADING rows are the entire point: they are what a
    # survivorship-free universe needs and what the live filter has been discarding.
    rows = []
    for s in syms:
        rows.append({
            "symbol": s.get("symbol"), "status": s.get("status"),
            "contractType": s.get("contractType"), "quoteAsset": s.get("quoteAsset"),
            "baseAsset": s.get("baseAsset"),
            "onboardDate": s.get("onboardDate"), "deliveryDate": s.get("deliveryDate"),
        })

    by_status: dict[str, int] = {}
    for r in rows:
        by_status[str(r["status"])] = by_status.get(str(r["status"]), 0) + 1

    rec = {"date": today, "captured_at": datetime.now(tz=UTC).isoformat(),
           "venue": "binance-usdm", "n_symbols": len(rows), "by_status": by_status,
           "note": "POINT-IN-TIME: every status, not just TRADING. The non-TRADING rows are the "
                   "point -- a universe filtered to survivors is survivorship bias by "
                   "construction, and a snapshot not taken today cannot be taken tomorrow.",
           "symbols": rows}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "at", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")

    n_days = 0
    with gzip.open(OUT, "rt", encoding="utf-8") as fh:
        n_days = sum(1 for line in fh if line.strip())
    print(f"universe snapshot {today}: {len(rows)} symbols {by_status}")
    print(f"  -> {OUT.relative_to(ROOT)} ({n_days} day(s) on record)")
    if n_days == 1:
        print("  FIRST ROW. The series is worth exactly nothing today and compounds from here; "
              "its value is continuity, so a missed day is a permanent hole.")
    if "--json" in sys.argv:
        print(json.dumps({"date": today, "n": len(rows), "by_status": by_status}))


if __name__ == "__main__":
    main()
