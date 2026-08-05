#!/usr/bin/env python3
"""CIRCULATING-SUPPLY HISTORY -- the denominator the unlock screen cannot be re-cut without.

WHY THIS IS THE HALF WORTH BUILDING FIRST. `screen_unlock_supply_series` is blocked on two inputs
and they are NOT symmetric:

  * the UNLOCK CALENDAR (numerator) is a published schedule. It exists today, somebody sells it,
    and it can be bought or scraped at any future date with its history intact.
  * the CIRCULATING-SUPPLY SERIES (denominator) is a POINT-IN-TIME observation. Nobody sells a
    trustworthy per-day history of it, and every day this collector does not run is a day that
    can never be recovered. A supply history can only be built FORWARD.

So the collector that must start today is this one, even though it does not on its own unblock the
screen. Starting the recoverable half first and the unrecoverable half later is the wrong order,
and it is the order a desk drifts into because the recoverable half is the one that shows progress.

THE DEFECT THIS EXISTS TO AVOID, named by the screen itself: `defect_1`, using a CURRENT float as
the denominator for a HISTORICAL release. That divides yesterday's unlock by today's supply, which
is a look-ahead so quiet nothing downstream would flag it -- the number is plausible, the units are
right, and it is wrong in the direction that makes unlocks look smaller than they were. Every row
here is stamped with the instant it was OBSERVED and is never back-dated.

NO HISTORY IS FABRICATED. CoinGecko's free tier answers with a CURRENT snapshot and no per-day
history, so this appends one dated row per run and the series accrues from first run. The file
will be short for a long time. That is the honest state, and the artifact reports `days_covered`
so nobody mistakes a two-week series for a testable panel.

    python scripts/collect_circulating_supply.py [--symbols a,b,c] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data.paywall import record as record_paywall  # noqa: E402

OUT = "data/circulating_supply.jsonl"
STATUS = "data/circulating_supply_status.json"

#: The unlocking universe -- assets whose float is still materially schedule-driven, which is where
#: a supply-release effect can exist at all. A mega-cap with 99% of supply already circulating has
#: no mechanism here, so recording it would add rows and no information.
#: CoinGecko ids, not tickers: tickers collide across chains and a collision writes one asset's
#: supply under another's name, which no statistic downstream could detect.
DEFAULT_IDS: tuple[str, ...] = (
    "aptos", "sui", "celestia", "sei-network", "arbitrum", "optimism", "starknet",
    "worldcoin-wld", "jito-governance-token", "pyth-network", "dydx-chain", "immutable-x",
    "blur", "ethena", "jupiter-exchange-solana", "wormhole", "eigenlayer", "ondo-finance",
    "the-open-network", "near", "injective-protocol", "sky", "raydium", "helium",
)

_API = "https://api.coingecko.com/api/v3/coins/"
#: MEASURED, not guessed. At 2.5s the first live run lost 2 of 5 ids to HTTP 429 -- and a 429 is
#: not a missing asset, it is a row the desk will never be able to backfill because a
#: circulating-supply observation is point-in-time. Losing rows to impatience is the one failure
#: this collector cannot repair later, so the pace is set generously and the run simply takes
#: longer. 7s x 24 ids is ~3 minutes, which is nothing for a daily cadence.
_PACE_S = 7.0
#: One retry per id after a 429, backing off further. Beyond that the id is recorded as missed
#: with its reason rather than hammered -- continuing to push a rate limit is how a temporary
#: throttle becomes a durable block on the whole collector.
_RETRY_AFTER_429_S = 20.0
_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0",
       "Accept": "application/json"}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def fetch_one(coin_id: str, *, timeout: float = 25.0) -> tuple[dict[str, Any] | None, str]:
    """(row, error). Never raises -- a scheduled collector must record why, not die."""
    url = (f"{_API}{coin_id}?localization=false&tickers=false&market_data=true"
           "&community_data=false&developer_data=false&sparkline=false")
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            doc = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:100]}"
    md = doc.get("market_data") if isinstance(doc.get("market_data"), dict) else {}
    circ, total, maxs = md.get("circulating_supply"), md.get("total_supply"), md.get("max_supply")
    if not isinstance(circ, (int, float)) or circ <= 0:
        # A missing circulating supply is NOT zero and NOT a row. Writing 0.0 here would make the
        # unlock fraction infinite for that day and the cell would look spectacular.
        return None, "no usable circulating_supply in market_data"
    return {
        "observed_utc": _now(),
        "coin_id": str(doc.get("id") or coin_id),
        "symbol": str(doc.get("symbol") or "").upper(),
        "circulating_supply": float(circ),
        "total_supply": float(total) if isinstance(total, (int, float)) else None,
        "max_supply": float(maxs) if isinstance(maxs, (int, float)) else None,
        "float_fraction": (float(circ) / float(total)
                           if isinstance(total, (int, float)) and total else None),
        "source": "coingecko/coins",
        # THE ANTI-LOOKAHEAD STAMP. This value is knowable from this instant onward and NEVER
        # before it. A consumer pairing it with an earlier bar is using tomorrow's float to judge
        # yesterday's release, which is the screen's own `defect_1`.
        "known_from": _now(),
        "point_in_time": True,
    }, ""


def run(root: Path | None = None, ids: tuple[str, ...] = DEFAULT_IDS) -> dict[str, Any]:
    base = root or _ROOT
    path = base / OUT
    path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for i, cid in enumerate(ids):
        if i:
            time.sleep(_PACE_S)
        row, err = fetch_one(cid)
        if row is None and "429" in err:
            time.sleep(_RETRY_AFTER_429_S)
            row, err = fetch_one(cid)
        if row is None:
            errors[cid] = err
            continue
        rows.append(row)

    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    # DAYS COVERED, not row count. A thousand rows collected in one afternoon is not a series, and
    # reporting the row count would let a one-day file read like a year of history.
    days: set[str] = set()
    try:
        for line in path.read_text("utf-8", errors="ignore").splitlines():
            if line.strip():
                days.add(str(json.loads(line).get("observed_utc", ""))[:10])
    except (OSError, ValueError):
        pass

    # THE PAYWALL IS RECORDED, NOT JUST NARRATED. Writing "402" into a status field and a cron
    # comment is what happened the first time, and DefiLlama's paid tier never reached the §42
    # registry -- the standing rule said to add it and nothing mechanical enforced the rule. One
    # row per run is enough: the fence reads the LATEST encounter per vendor, and a hunt that
    # succeeds flips the registry row rather than the ledger.
    paywall = record_paywall(
        "https://api.llama.fi/emissions", status=402,
        unlocks=("dated token-unlock release rows with known_from -- the NUMERATOR of "
                 "screen_unlock_supply_series (36 declared cells). The denominator "
                 "(circulating-supply history) is already accruing free from CoinGecko, so this "
                 "single feed is the whole remaining blocker on that screen."),
        root=base)

    status = {
        "generated_utc": _now(),
        "paywall_recorded": {k: paywall[k] for k in ("vendor", "status", "verdict", "unlocks")},
        "status": "OK" if rows else "BLOCKED",
        "n_written": len(rows), "n_requested": len(ids),
        "errors": errors,
        "days_covered": len(days),
        "first_day": min(days) if days else None,
        "last_day": max(days) if days else None,
        "note": ("A circulating-supply history can ONLY be built forward -- nobody sells a "
                 "trustworthy per-day series, so every day this does not run is unrecoverable. "
                 "The unlock CALENDAR is the opposite: it is published, and can be obtained later "
                 "with its history intact. That asymmetry is why this half started first."),
        "still_blocking_the_unlock_screen": (
            "data/unlock_events.json -- dated release rows with known_from. DefiLlama's "
            "/emissions and /emission/<protocol> both answer HTTP 402 Payment Required as of "
            "2026-08-05 and defillama.com/api/emissions answers 403, so the calendar is behind a "
            "paid tier. NOT purchased: a licensed vendor feed is the principal's decision, never "
            "a collector's. Recorded as a named blocker with the free half already accruing."),
        "authority": "COLLECTOR ONLY -- writes an observation ledger. Screens nothing, promotes "
                     "nothing, sizes nothing.",
    }
    (base / STATUS).write_text(json.dumps(status, indent=1) + "\n", "utf-8")
    return status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--symbols", default="", help="comma-separated CoinGecko ids")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    ids = tuple(s.strip() for s in args.symbols.split(",") if s.strip()) or DEFAULT_IDS
    st = run(ids=ids)
    if args.json:
        print(json.dumps(st, indent=1))
        return 0
    print(f"circulating supply: {st['status']} -- {st['n_written']}/{st['n_requested']} written, "
          f"{st['days_covered']} day(s) covered ({st['first_day']} .. {st['last_day']})")
    for cid, err in list(st["errors"].items())[:8]:
        print(f"  MISS {cid}: {err}")
    print(f"  STILL BLOCKING the unlock screen: {st['still_blocking_the_unlock_screen'][:110]}...")
    print(f"-> {OUT}")
    return 0 if st["n_written"] else 1


if __name__ == "__main__":
    sys.exit(main())
