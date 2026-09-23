#!/usr/bin/env python3
"""SELF-HEALING REGISTRY REPAIR -- because the producers that break it live on other boxes.

WHY THIS IS AN ORGAN AND NOT A ONE-SHOT SCRIPT.

`desks/mt5/data/universe/universe.json` has three writers (`fetch_universe.py`,
`expand_universe.py`, `scripts/download_all_symbols.py`). Each writes its own schema with
`write_text(json.dumps(...))`, so whichever ran last decides which fields exist. On 2026-08-26
the winner wrote no `tick_value` at all, and:

  * every account-currency cost on the desk went to 0.0 (there is no other field that carries a
    price in the account's own currency),
  * `classify_all` returned 0 usable instruments out of 197 -- an empty universe that reads
    exactly like a universe with nothing worth trading (WS-005),
  * `cost_hash` flipped, and because cost is part of sleeve identity that TERMINALLY broke 11
    live forward clocks, which is the desk's readiness blocker.

Those three producers run on Windows boxes this box has no code-sync path to. A fix committed
here to `expand_universe.py` is INERT until someone re-deploys it, and the desk has already paid
for assuming otherwise. So the durable protection is not only the patched producer: it is this
organ, which runs on a schedule, re-merges whatever a clobbering writer destroyed, and fails
loudly in `--check` mode when something it cannot repair appears.

WHAT IT WILL NOT DO. It never invents a spread. A raw account really does fill USDJPY and GBPUSD
at zero spread (`execution_quality.json` measured it), so a zero reading is preserved as a
reading, not "corrected" to something plausible. It repairs fields that were DELETED; it does not
overrule fields that were MEASURED.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
DESK = BASE / "desks" / "mt5"
sys.path.insert(0, str(DESK))

from mt5desk.universe_registry import (  # noqa: E402
    ACCOUNT_CCY,
    backfill_tick_values,
    defects,
    merge,
)

UNIVERSE = DESK / "data" / "universe"
REGISTRY = UNIVERSE / "universe.json"
BROKER_TV = UNIVERSE / "broker_tick_values.json"
EXECQ = DESK / "reports" / "execution_quality.json"
REPORT = DESK / "reports" / "universe_registry_repair.json"


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def parquet_facts() -> tuple[dict[str, int], dict[str, float]]:
    """`(bars, last_close)` per symbol, straight off the H1 parquets on disk.

    The bar count is the answer to "does this symbol have history", and a writer that reports 0
    beside a 50,000-row file is stubbing, not measuring. The closes are what make `tick_value`
    derivable at all.
    """
    import pandas as pd  # keep the import cost off `--check`-only callers

    bars: dict[str, int] = {}
    closes: dict[str, float] = {}
    for path in sorted(UNIVERSE.glob("*_H1.parquet")):
        sym = path.name[: -len("_H1.parquet")]
        try:
            frame = pd.read_parquet(path, columns=["close"])
        except (OSError, ValueError, KeyError):
            continue
        bars[sym] = len(frame)
        if len(frame):
            closes[sym] = float(frame["close"].iloc[-1])
    return bars, closes


def realized_spread_pts(registry: dict[str, Any]) -> dict[str, float]:
    """Median spread AT FILL, in points, from this desk's own tape. Reality outranks the snapshot.

    `execution_quality.json` records `spread_at_fill` in PRICE; points are price / tick_size. A
    symbol the desk has actually filled has already answered the question a terminal snapshot only
    estimates, and a registry reading of 0 that this contradicts is a refuted measurement.
    """
    out: dict[str, float] = {}
    for key, row in (_read(EXECQ).get("by_symbol_session") or {}).items():
        stats = row.get("spread_at_fill") or {}
        median = stats.get("median")
        if not stats.get("n") or median is None:
            continue
        sym = str(key).split(".")[0]
        tick = (registry.get(sym) or {}).get("tick_size")
        if not tick:
            continue
        pts = abs(float(median)) / float(tick)
        out[sym] = max(out.get(sym, 0.0), pts)
    return out


def repair(*, check_only: bool) -> int:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    registry = _read(REGISTRY)
    if not registry:
        print(f"FAIL: {REGISTRY} is empty or unreadable -- that is not a universe with nothing "
              f"worth trading, it is an absent universe (L1.28a)")
        return 1

    # THE CANON RATCHET (2026-08-27). Twice tonight a rogue writer replaced the whole-broker
    # registry with a 23-row ancient copy, and this organ then faithfully repaired the stump --
    # laundering the shrink into a clean-looking artifact one sync later. The registry's symbol
    # SET only ratchets up: rows missing versus the canon superset are restored from it (their
    # fields then re-repaired below like everything else), and the canon itself grows whenever
    # the registry does. Shrinking the hunted universe is announced by retirement, never by a
    # smaller file.
    canon_path = REGISTRY.parent / "universe.canon.json"
    canon = _read(canon_path) or {}
    missing = {s: dict(row) for s, row in canon.items()
               if s not in registry and isinstance(row, dict)}
    if missing:
        registry.update(missing)
        print(f"RATCHET: {len(missing)} symbol(s) restored from the canon superset "
              f"(a writer shrank the registry; shrinkage is never repaired into)")

    bars, closes = parquet_facts()
    realized = realized_spread_pts(registry)
    before = defects(registry, parquet_bars=bars, realized_spread_pts=realized)

    if check_only:
        for line in before:
            print(f"DEFECT: {line}")
        print(f"{'FAIL' if before else 'OK'}: {len(before)} defect(s) over "
              f"{len(registry)} symbol(s)")
        return 1 if before else 0

    # 1. The venue's own tick_values, wherever the desk still holds them. A broker-reported
    #    number beats a derived one and is restored first.
    broker = (_read(BROKER_TV).get("tick_value") or {})
    restored = merge(registry, {s: {"tick_value": v} for s, v in broker.items() if s in registry},
                     source="broker_reported", now=now)

    # 2. Bar counts from the files themselves -- never from whichever writer last guessed.
    restored = merge(restored, {s: {"bars": n} for s, n in bars.items() if s in restored},
                     source="parquet_on_disk", now=now)

    # 3. WHERE THE REGISTRY HAS NO SPREAD BUT THE DESK HAS FILLS, REALITY WINS (L1.4). A
    #    `symbol_info.spread` snapshot of 0 on CADJPY is refuted by three fills at 1 point of
    #    this desk's own tape. Only the ABSENT direction is filled: a positive registry reading
    #    is never lowered to a realised one, because that direction makes trading look cheaper
    #    and could manufacture a survivor. Raising a zero can only ever make a candidate harder.
    refuted = {sym: {"median_spread_pts": round(pts, 2)}
               for sym, pts in realized.items()
               if sym in restored and float(restored[sym].get("median_spread_pts") or 0) <= 0
               and pts > 0}
    restored = merge(restored, refuted, source="realized_fills", now=now)

    # 4. Derive what remains. Reports what it could NOT derive rather than filling a zero.
    filled, underivable = backfill_tick_values(restored, closes, now=now)

    after = defects(restored, parquet_bars=bars, realized_spread_pts=realized)
    REGISTRY.write_text(json.dumps(restored, indent=1, sort_keys=True) + "\n", "utf-8")
    if len(restored) >= len(canon):
        canon_path.write_text(json.dumps(restored, indent=1, sort_keys=True) + "\n", "utf-8")

    payload = {
        "repaired_at": now, "account_ccy": ACCOUNT_CCY, "symbols": len(restored),
        "broker_tick_values_restored": sum(1 for s in broker if s in registry),
        "tick_values_derived": filled,
        "spreads_from_realized_fills": sorted(refuted),
        "underivable_tick_value": underivable,
        "defects_before": before, "defects_after": after,
        "note": ("a symbol in `underivable_tick_value` has no readable quote currency (share "
                 "CFDs) or no bridge to the account currency. It stays UNCOSTED and visible "
                 "rather than being given a zero that would backtest as free trading."),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=1) + "\n", "utf-8")

    print(f"symbols={len(restored)} broker_tick_values={payload['broker_tick_values_restored']} "
          f"derived={filled} underivable={len(underivable)} "
          f"spread_from_fills={len(refuted)}")
    print(f"defects {len(before)} -> {len(after)}")
    for line in after:
        print(f"  REMAINS: {line}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="report defects and exit non-zero; change nothing (fence mode)")
    return repair(check_only=ap.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
