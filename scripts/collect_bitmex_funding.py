#!/usr/bin/env python3
"""BitMEX funding-rate decade backfill — phase 1 of BITMEX_DECADE_INGEST_SPEC.md.

One-shot, resumable, public REST (no key): pages /api/v1/funding oldest-first into
data/bitmex_funding.jsonl. ~11k rows for XBTUSD since 2016-05 (~2-5 MB) — the cheapest
8 years of carry-regime evidence available anywhere.

ALIGNMENT DECLARATION (screen duty #4): BitMEX `timestamp` is the funding PAYMENT time
(UTC, 8h grid 04:00/12:00/20:00); the rate applies to the PRECEDING 8h window. Any join
onto daily bars must therefore aggregate payments into the UTC day they were PAID, and a
screen using same-day funding as a signal for same-day return has look-ahead inside the
final window — flag it, never assume it away.

Politeness: unauthenticated limit is 30 req/min; we run well under it (2s/page, ~25 pages).
Idempotent: restart resumes from the last stored timestamp; duplicate keys are dropped.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/bitmex_funding.jsonl"
API = "https://www.bitmex.com/api/v1/funding"
PAGE = 500


def _fetch(symbol: str, start_time: str | None) -> list[dict]:
    q = {"symbol": symbol, "count": str(PAGE), "reverse": "false"}
    if start_time:
        q["startTime"] = start_time
    req = urllib.request.Request(f"{API}?{urllib.parse.urlencode(q)}",
                                 headers={"User-Agent": "quant-desk-ingest/1.0"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:  # 429/5xx/net: back off, retry; final attempt re-raises
            if attempt == 4:
                raise
            wait = 5 * (2 ** attempt)
            print(f"  fetch failed ({exc!r}) -- backing off {wait}s")
            time.sleep(wait)
    return []


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="XBTUSD")
    p.add_argument("--max-pages", type=int, default=60)
    a = p.parse_args()

    seen: set[str] = set()
    last_ts: str | None = None
    if OUT.exists():
        for ln in OUT.read_text("utf-8").splitlines():
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if row.get("symbol") == a.symbol:
                key = f"{row['symbol']}|{row['timestamp']}"
                seen.add(key)
                last_ts = max(last_ts or "", row["timestamp"])
    print(f"resume point: {last_ts or 'genesis'} ({len(seen)} rows held)")

    n_new = 0
    with OUT.open("a", encoding="utf-8") as fh:
        for _page in range(a.max_pages):
            rows = _fetch(a.symbol, last_ts)
            fresh = 0
            for r in rows:
                key = f"{r['symbol']}|{r['timestamp']}"
                if key in seen:
                    continue
                seen.add(key)
                fh.write(json.dumps({"symbol": r["symbol"], "timestamp": r["timestamp"],
                                     "fundingRate": r.get("fundingRate"),
                                     "fundingRateDaily": r.get("fundingRateDaily")}) + "\n")
                fresh += 1
                n_new += 1
                last_ts = max(last_ts or "", r["timestamp"])
            print(f"  page -> {len(rows)} rows, {fresh} new (through {last_ts})")
            if len(rows) < PAGE:
                break
            time.sleep(2)
    print(f"done: +{n_new} new rows -> {OUT} (total held {len(seen)})")


if __name__ == "__main__":
    main()
