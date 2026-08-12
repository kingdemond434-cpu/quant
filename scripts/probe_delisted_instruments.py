#!/usr/bin/env python3
"""VENUE-SIDE DELISTED-INSTRUMENT PROBE (R0313): ask each venue for its dead names before
reconstructing them by observation.

THE DEFECT IT CLOSES. snapshot_universe.py (R0239) fixes survivorship bias FORWARD -- it records
what existed today so that tomorrow's panel knows. Its own docstring names the gap it leaves:
"it does not retroactively restore delisted history -- that is a reconstruction from
binance.vision delisted-symbol archives, a separate and much larger job". That job is much
smaller than it looks, because some venues simply PUBLISH their dead instruments, and nothing on
this desk had ever asked. Measured 2026-08-12, first run:

    bitmex    /api/v1/instrument                              483 dead vs   17 live
    bybit     /v5/market/instruments-info?status=Closed       936 dead vs  808 live
    coinbase  /products (status=delisted)                     315 dead vs  517 live

Two of the three carry MORE dead instruments than live ones. Those are precisely the names a
universe-built-by-observation cannot see, and they are systematically the LOSERS -- so every
cross-sectional study conditioned on today's listings is biased upward by an amount nobody had
measured. One HTTP call per venue recovers the roster.

WHAT IT DOES NOT CLAIM. A roster of dead symbols is not their price history; it is the universe
membership needed to know what to go and fetch, and to know what is missing. It also does not
make an absent endpoint into a venue defect: Upbit publishes no state field at all (which is the
KR seat's candle-purge finding from the other side, and why R0303 snapshots instead).

ABSENT AND UNREACHABLE ARE KEPT APART, because they demand opposite responses: one means the
venue has nothing to give and reconstruction is the only route, the other means we failed to ask
today and must retry. Collapsing them is how "we checked, there is nothing" gets recorded for a
venue nobody actually reached (L1.55).

Writes data/delisted_instruments.json (the per-venue registry) and, for every venue that has
them, the dead roster itself under data/delisted_rosters/<venue>.json -- a probe that records
only counts would be a catalogue, and a catalogue is half a deliverable (S33).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.ops.lawful import guard  # noqa: E402

OUT = ROOT / "data/delisted_instruments.json"
ROSTERS = ROOT / "data/delisted_rosters"
_UA = {"User-Agent": "Mozilla/5.0 (quant-desk delisted-probe)"}

# Verdicts. AVAILABLE and ABSENT are both MEASUREMENTS; UNREACHABLE is the refusal.
AVAILABLE, PARTIAL, ABSENT, UNREACHABLE = "AVAILABLE", "PARTIAL", "ABSENT", "UNREACHABLE"


def _get(url: str, timeout: int = 30) -> Any:
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=_UA), timeout=timeout).read())


def _split(rows: list[dict], sym_key: str, state_key: str, dead: set[str]) -> dict[str, Any]:
    """Partition a venue instrument list into dead/live by its own state vocabulary."""
    states = Counter(str(r.get(state_key)) for r in rows)
    dead_syms = sorted({str(r.get(sym_key)) for r in rows if str(r.get(state_key)) in dead})
    return {"states": dict(states), "dead": dead_syms,
            "n_live": sum(n for s, n in states.items() if s not in dead)}


def probe_bitmex(*, page: int = 500, max_pages: int = 40) -> dict[str, Any]:
    """PAGINATED. 500 is BitMEX's per-call cap, and the first cut stopped there -- which read
    "500 dead, 0 live" purely because the settled contracts filled the page. Truncation is the
    venue failure mode that never throws: past the cap every derived total stays plausible and
    is silently wrong. Walks until a short page, and says so if it hits the page ceiling."""
    rows: list[dict] = []
    truncated = True
    for i in range(max_pages):
        batch = _get("https://www.bitmex.com/api/v1/instrument"
                     f"?count={page}&start={i * page}&columns=symbol,state,expiry")
        rows.extend(batch)
        if len(batch) < page:
            truncated = False
            break
    r = _split(rows, "symbol", "state", {"Settled", "Delisted", "Unlisted"})
    if truncated:
        r["note"] = (f"TRUNCATED: still full pages at the {max_pages}-page ceiling "
                     f"({len(rows)} rows) -- the roster is a floor, not a total.")
    return {"endpoint": "GET www.bitmex.com/api/v1/instrument (paginated)", **r}


def probe_bybit() -> dict[str, Any]:
    out: dict[str, Any] = {"endpoint": "GET api.bybit.com/v5/market/instruments-info"
                                       "?category=linear&status={Trading,Closed}",
                           "states": {}, "dead": []}
    limit = 1000                                  # the endpoint's documented per-call cap
    for status in ("Trading", "Closed"):
        d = _get("https://api.bybit.com/v5/market/instruments-info"
                 f"?category=linear&status={status}&limit={limit}")
        lst = d.get("result", {}).get("list", []) or []
        out["states"][status] = len(lst)
        if len(lst) >= limit:
            # Short page == complete. A FULL page means the cursor has more behind it, and a
            # roster reported as a total when it is a first page is the same silent truncation.
            out["note"] = (f"TRUNCATED: {status} filled the {limit}-row page; nextPageCursor "
                           "not walked -- treat the roster as a floor, not a total.")
        if status == "Closed":
            out["dead"] = sorted({str(x.get("symbol")) for x in lst})
    out["n_live"] = int(out["states"].get("Trading", 0))
    return out


def probe_coinbase() -> dict[str, Any]:
    rows = _get("https://api.exchange.coinbase.com/products")
    return {"endpoint": "GET api.exchange.coinbase.com/products",
            **_split(rows, "id", "status", {"delisted"})}


def probe_binance_futures() -> dict[str, Any]:
    d = _get("https://fapi.binance.com/fapi/v1/exchangeInfo")
    rows = d.get("symbols", []) or []
    r = _split(rows, "symbol", "status", {"SETTLING", "CLOSE", "DELIVERING", "DELIVERED"})
    # SETTLING is a DATED DELIVERY contract on its way out, not a delisted perp: real, but it
    # does not restore names that have already gone. Graded PARTIAL for that reason, and the
    # binance.vision archive reconstruction R0239 names stays the route for perps.
    r["note"] = ("SETTLING/DELIVERING are dated delivery contracts mid-retirement; a perp that "
                 "was delisted disappears from exchangeInfo entirely, so this does not recover "
                 "already-dead perps -- binance.vision archives remain the route for those.")
    r["partial"] = True
    return {"endpoint": "GET fapi.binance.com/fapi/v1/exchangeInfo", **r}


def probe_okx() -> dict[str, Any]:
    rows = (_get("https://www.okx.com/api/v5/public/instruments?instType=SWAP")
            .get("data", []) or [])
    return {"endpoint": "GET www.okx.com/api/v5/public/instruments?instType=SWAP",
            **_split(rows, "instId", "state", {"suspend", "expired"})}


def probe_kraken_futures() -> dict[str, Any]:
    rows = _get("https://futures.kraken.com/derivatives/api/v3/instruments").get(
        "instruments", []) or []
    states = Counter("tradeable" if r.get("tradeable") else "untradeable" for r in rows)
    return {"endpoint": "GET futures.kraken.com/derivatives/api/v3/instruments",
            "states": dict(states),
            "dead": sorted({str(r.get("symbol")) for r in rows if not r.get("tradeable")}),
            "n_live": states["tradeable"]}


def probe_upbit() -> dict[str, Any]:
    rows = _get("https://api.upbit.com/v1/market/all")
    return {"endpoint": "GET api.upbit.com/v1/market/all",
            "states": {"live": len(rows)}, "dead": [], "n_live": len(rows),
            "note": "no state field is published at all; Upbit also PURGES candles on delisting, "
                    "so the treatment group is erased at the source -- R0303 snapshots forward "
                    "because there is nothing to ask for after the fact."}


PROBES = {
    "bitmex": probe_bitmex,
    "bybit": probe_bybit,
    "coinbase": probe_coinbase,
    "binance_futures": probe_binance_futures,
    "okx": probe_okx,
    "kraken_futures": probe_kraken_futures,
    "upbit": probe_upbit,
}


def grade(result: dict[str, Any]) -> str:
    """AVAILABLE if the venue hands over dead names; ABSENT if it measurably has none to give."""
    if result.get("error"):
        return UNREACHABLE
    if not result.get("dead"):
        return ABSENT
    return PARTIAL if result.get("partial") else AVAILABLE


def _accumulate_roster(root: Path, venue: str, dead: list[str], probed: str,
                       endpoint: str) -> int:
    """UNION the roster with what is already on disk, and return how many names are NEW.

    ARCHIVE WHAT THE VENUE DELETES (the R0303 discipline, same class of loss). A venue's dead
    list is itself a venue-controlled surface: Upbit purges candles on delisting, and nothing
    stops Bybit or BitMEX ageing a symbol off `status=Closed` one day. Overwriting the roster
    each run would make this artifact silently SHRINK, so the one thing it exists to preserve
    would be lost by the act of refreshing it. Monotone by construction instead: first_seen is
    never rewritten, so the file also dates when each name left.
    """
    p = root / f"data/delisted_rosters/{venue}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    known: dict[str, dict[str, str]] = {}
    if p.exists():
        # A corrupt roster is not an empty one: let ValueError/OSError propagate rather than
        # silently start a fresh file over the top of history we cannot re-earn.
        prior = json.loads(p.read_text("utf-8")).get("symbols")
        if isinstance(prior, dict):
            known = {str(k): dict(v) if isinstance(v, dict) else {} for k, v in prior.items()}
        elif isinstance(prior, list):
            # A roster written before symbols carried dates. The NAMES are the irreplaceable part
            # and are carried over unconditionally; their first_seen is honestly unknown rather
            # than back-dated to today, which would assert a measurement nobody made.
            known = {str(s): {"first_seen": "unknown", "last_seen": "unknown"} for s in prior}
        elif prior is not None:
            raise ValueError(f"{p}: 'symbols' is {type(prior).__name__}, not a roster")
    new = 0
    for sym in dead:
        if sym in known:
            known[sym]["last_seen"] = probed
        else:
            known[sym] = {"first_seen": probed, "last_seen": probed}
            new += 1
    p.write_text(json.dumps({"venue": venue, "endpoint": endpoint, "probed": probed,
                             "n_dead": len(known), "n_new_this_run": new,
                             "symbols": dict(sorted(known.items()))}, indent=1), "utf-8")
    return new


def run(venues: list[str], *, root: Path = ROOT) -> dict[str, Any]:
    out: dict[str, Any] = {"probed": datetime.now(tz=UTC).isoformat(), "venues": {}}
    for name in venues:
        try:
            r = PROBES[name]()
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, OSError) as e:
            # REFUSAL, never a zero. "We could not ask" and "there is nothing there" are
            # different claims and only one of them is evidence.
            r = {"error": f"{type(e).__name__}: {e}"}
        verdict = grade(r)
        dead = r.pop("dead", [])
        if dead:
            n_new = _accumulate_roster(root, name, dead, out["probed"], r.get("endpoint", ""))
            r["n_new_this_run"] = n_new
        out["venues"][name] = {**r, "verdict": verdict, "n_dead": len(dead)}
    reached = [v for v in out["venues"].values() if v["verdict"] != UNREACHABLE]
    out["n_venues"] = len(out["venues"])
    out["n_reached"] = len(reached)
    out["n_available"] = sum(1 for v in reached if v["verdict"] in (AVAILABLE, PARTIAL))
    out["n_dead_total"] = sum(int(v["n_dead"]) for v in reached)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--venue", action="append", choices=sorted(PROBES),
                    help="probe only these venues (default: all)")
    ap.add_argument("--json", action="store_true", help="print the registry as JSON")
    args = ap.parse_args(argv)
    guard()

    res = run(args.venue or sorted(PROBES))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1), "utf-8")

    if args.json:
        print(json.dumps(res, indent=1))
    else:
        for name, v in res["venues"].items():
            if v["verdict"] == UNREACHABLE:
                print(f"{name:17s} UNREACHABLE  {v.get('error', '')[:70]}")
            else:
                print(f"{name:17s} {v['verdict']:11s} dead {v['n_dead']:5d} | "
                      f"live {v.get('n_live', 0):5d} | {v.get('endpoint', '')}")
        print(f"\n{res['n_available']}/{res['n_reached']} reachable venues publish dead "
              f"instruments; {res['n_dead_total']} dead names recovered -> {OUT}")
        if res["n_reached"] < res["n_venues"]:
            print(f"UNREACHABLE: {res['n_venues'] - res['n_reached']} venue(s) not asked today "
                  "-- that is not the same as having nothing to give; retry before concluding.")
    # An entirely unreachable run is a refusal, not a clean registry.
    return 0 if res["n_reached"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
