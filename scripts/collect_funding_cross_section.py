#!/usr/bin/env python3
"""THE CROSS-SECTIONAL FUNDING SNAPSHOT -- the denominator a crowding measure cannot exist without.

WHY THIS COLLECTOR EXISTS. `libs/data/crypto_source.current_funding()` returns the funding rate for
EVERY USD-M perp at ONE instant -- 855 symbols in a single REST call -- and five production callers
fetch it, rank it, trade off it, and throw it away. Nothing on this desk has ever written it down.

That discard is what makes "are our own edges being crowded?" unanswerable. Crowding is not a
statement about a rate, it is a statement about a rate RELATIVE to its cross-section: a competitor
who finds our carry names compresses OUR names, not the universe. Without the universe at the same
instant there is no residual to take, and the desk's incumbent organ
(`scripts/run_carry_crowding.py`) is forced to measure the top-20 AVERAGE instead -- which contains
our own names, so it dilutes exactly the signal it is looking for and subtracts the rest of it as
the benchmark. A market-wide compression and a targeted one are indistinguishable in that number.

THE DATA IS IRREPLACEABLE, WHICH IS WHY THIS SHIPS BEFORE THE FENCE IT FEEDS (L1.28b(f)).
`premiumIndex` is a SNAPSHOT endpoint: it serves the current instant and no history. A day not
collected is a day of denominator that cannot be bought, reconstructed or back-filled at any price.
The fence reading this tape will honestly report NO-DATA until the tape has depth; that is the
correct order, and the reverse -- fence first, tape later -- would have the fence reporting on an
empty universe for exactly as long.

WHAT IT ALSO STOPS DISCARDING (L1.47). The same payload carries `nextFundingTime` and, per symbol,
the venue's own stamp. `funding_clock.py`'s header records that `nextFundingTime` had ZERO
occurrences repo-wide though it arrives in a payload the desk already reads every cycle. This
collector keeps it, which makes the per-symbol funding INTERVAL derivable from observed successive
settlement stamps rather than assumed at 8h -- the assumption that under-counts the highest-funding
alts by 2x.

CLOCK PROVENANCE (L1.46). Every row declares its stamping clock. `t` is OUR receipt time and `tv`
is the venue's own `time` field from the payload; the `c` marker is `venue` because the venue
publishes a stamp we retain beside ours. A timestamp whose clock is undeclared is an assumption
wearing a measurement's clothes, and 82% of this desk's tape was written that way.

    python scripts/collect_funding_cross_section.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data.crypto_source import _FAPI, _get  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.research import clock_provenance as cp  # noqa: E402

#: Append-only tape. One JSON object per snapshot, holding the whole cross-section, because the
#: cross-section IS the unit of observation -- splitting it per symbol would lose the instant that
#: makes the rows comparable, which is the entire point of the artifact.
OUT = _ROOT / "data/funding_cross_section.jsonl"

#: A snapshot with fewer symbols than this is a partial payload, not a cross-section. Binance
#: serves ~850; a truncated response would silently narrow the universe and bias every percentile
#: taken against it, so it is REFUSED rather than written.
MIN_SYMBOLS = 200


def snapshot(payload: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """One cross-sectional row: every perp's funding rate at one receipt instant.

    Pure given ``payload`` so the shape is testable without a venue. Refuses a thin payload rather
    than writing a narrowed universe -- a percentile is only as honest as its denominator.
    """
    recv_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    if payload is None:
        got = _get(f"{_FAPI}/fapi/v1/premiumIndex")
        payload = got if isinstance(got, list) else []
    rates: dict[str, float] = {}
    next_ms: dict[str, int] = {}
    venue_ms: list[int] = []
    # EVERY DISCARD IS COUNTED (L2.4). A malformed element that vanishes silently is a shrinking
    # universe nothing can see -- and the universe IS the denominator here, so a quiet 10% loss
    # would bias every percentile taken against this row without changing anything visible.
    malformed = {"element": 0, "rate": 0, "next_funding": 0, "venue_stamp": 0}
    for d in payload:
        if not isinstance(d, dict) or not d.get("symbol"):
            malformed["element"] += 1
            continue
        sym = str(d["symbol"])
        try:
            rates[sym] = float(d.get("lastFundingRate", 0.0))
        except (TypeError, ValueError):
            malformed["rate"] += 1
            continue
        nft = d.get("nextFundingTime")
        if nft:
            try:
                next_ms[sym] = int(nft)
            except (TypeError, ValueError):
                malformed["next_funding"] += 1
        tv = d.get("time")
        if tv:
            try:
                venue_ms.append(int(tv))
            except (TypeError, ValueError):
                malformed["venue_stamp"] += 1
    return {
        "t": recv_ms,
        # The venue stamps every element of the payload identically; retaining the median keeps a
        # single venue truth per row beside ours so `t - tv` stays a first-class, unbuyable series.
        "tv": sorted(venue_ms)[len(venue_ms) // 2] if venue_ms else None,
        cp.MARKER: cp.CLOCK_VENUE if venue_ms else cp.CLOCK_RECV_ONLY,
        "venue": "binance_usdm",
        "kind": "funding_cross_section",
        "n": len(rates),
        "malformed": {k: v for k, v in malformed.items() if v},
        "rates": rates,
        "next_funding_ms": next_ms,
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    args = ap.parse_args()

    row = snapshot()
    if row["n"] < MIN_SYMBOLS:
        # REFUSAL PATH (L1.41): a thin payload is a venue or network fault, not a small universe.
        # Writing it would poison every percentile taken against this row, permanently.
        print(f"funding cross-section: REFUSED -- {row['n']} symbols is below the {MIN_SYMBOLS} "
              f"floor; a truncated payload would narrow the universe and bias every percentile")
        return 2

    if not args.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")

    delta = (row["t"] - row["tv"]) if row["tv"] else None
    print(f"funding cross-section: {row['n']} symbols -> {OUT.name} "
          f"(clock={row[cp.MARKER]}, recv-venue delta={delta}ms, "
          f"next_funding stamps={len(row['next_funding_ms'])})"
          + (f" MALFORMED={row['malformed']}" if row["malformed"] else "")
          + (" [DRY RUN, nothing written]" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
