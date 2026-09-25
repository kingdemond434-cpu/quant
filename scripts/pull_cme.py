#!/usr/bin/env python3
"""CME FOUNDATION PULL -- Databento GLBX.MDP3 -> Bronze (stdlib only, freeze carve-out).

STRATEGY (credits are ONE-TIME, $125): buy the BROAD CHEAP layer now, hold the expensive
targeted layer until a specific hypothesis demands it.
  foundation (this script): daily+hourly bars, settlements, contract definitions for BTC and
      ETH futures across the full available history  ~= $2 total (<2% of credits)
  reserve (NOT spent):      MBP-10 depth at ~$0.76/day -- surgical days only (cascades, CPI,
      FOMC, expiry weeks) once a card actually needs microstructure. Bulk MBP-1 at $45/6mo is
      explicitly rejected as poor value.
This gives the desk the CME basis series -- the institutional leg the perp book trades against
-- as an owned, permanent Bronze asset. Verify-don't-trust applies before any pipeline uses it.
"""
from __future__ import annotations

import base64
import json
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import certifi

ROOT = Path("/home/quant/quant-platform")
BRONZE = ROOT / "data/lake/bronze/cme"
KEY = json.loads((ROOT / "data/secrets/databento.json").read_text())["api_key"]
CTX = ssl.create_default_context(cafile=certifi.where())
AUTH = base64.b64encode(f"{KEY}:".encode()).decode()

# (schema, start, end) -- symbols applied per product below
FOUNDATION = [                                     # ordered SMALL-FIRST so wins land early;
    ("ohlcv-1d",   "2018-01-01", "2026-07-20"),   # the giant definition stream goes LAST
    ("statistics", "2018-01-01", "2026-07-20"),
    ("ohlcv-1h",   "2021-01-01", "2026-07-20"),
    ("definition", "2018-01-01", "2026-07-20"),
]
PRODUCTS = ["BTC.FUT", "ETH.FUT"]


def _get(ep: str, **p) -> bytes:
    url = f"https://hist.databento.com/v0/{ep}?" + urllib.parse.urlencode(p)
    r = urllib.request.Request(url, headers={"Authorization": f"Basic {AUTH}"})
    with urllib.request.urlopen(r, timeout=120, context=CTX) as resp:
        return resp.read()


def _stream_to(out: Path, ep: str, **p) -> int:
    """Chunked download -> .part file -> atomic rename. The socket timeout applies to
    EVERY chunk read, so a stalled stream dies in 120s instead of hanging forever
    (2026-07-21: the first attempt sat 33min on one .read())."""
    url = f"https://hist.databento.com/v0/{ep}?" + urllib.parse.urlencode(p)
    r = urllib.request.Request(url, headers={"Authorization": f"Basic {AUTH}"})
    part = out.with_suffix(out.suffix + ".part")
    got = 0
    with urllib.request.urlopen(r, timeout=120, context=CTX) as resp, part.open("wb") as f:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if got % (20 << 20) < (1 << 20):
                print(f"      ... {got/1e6:.0f} MB", flush=True)
    part.replace(out)
    return got


def cost(schema, start, end, symbols) -> float:
    return float(json.loads(_get("metadata.get_cost", dataset="GLBX.MDP3", schema=schema,
                                 start=start, end=end, symbols=symbols, stype_in="parent",
                                 mode="historical")))


def main() -> None:
    BRONZE.mkdir(parents=True, exist_ok=True)
    plan = []
    total = 0.0
    for sym in PRODUCTS:
        for schema, s, e in FOUNDATION:
            c = cost(schema, s, e, sym)
            plan.append((sym, schema, s, e, c))
            total += c
    print("PLAN:")
    for sym, schema, s, e, c in plan:
        print(f"  {sym:<9} {schema:<11} {s}..{e}  ${c:.2f}")
    print(f"  {'TOTAL':<9} {'':<11} {'':<22}  ${total:.2f}")

    if total > 8.0:
        raise SystemExit(f"ABORT: plan costs ${total:.2f}, above the $8 self-imposed cap for a "
                         "foundation pull. Re-scope before spending.")
    if "--go" not in sys.argv:
        print("\n(dry run -- rerun with --go to execute)")
        return

    for sym, schema, s, e, c in plan:
        out = BRONZE / f"{sym.replace('.','_')}_{schema}_{s}_{e}.csv"
        if out.exists() and out.stat().st_size > 0:
            print(f"  SKIP (have it): {out.name}")
            continue
        print(f"  pulling {sym} {schema} (${c:.2f}) ...", flush=True)
        n = _stream_to(out, "timeseries.get_range", dataset="GLBX.MDP3", schema=schema,
                       start=s, end=e, symbols=sym, stype_in="parent", encoding="csv")
        print(f"    -> {out.name}  {n:,} bytes")

    print("\nBRONZE contents:")
    for p in sorted(BRONZE.iterdir()):
        print(f"  {p.name:<52} {p.stat().st_size:>12,} bytes")


if __name__ == "__main__":
    main()
