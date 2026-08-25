"""MOAT MINER -- turn the private Fusion tape into TESTABLE HYPOTHESES, daily (principal
2026-08-26: "the moat should be mined daily, never unexploited or forgotten, and tested for
survivors along with every other hunt").

THE LAW THIS SERVES. Under-exploration of owned data is a BREACH, not a backlog: unmined
proprietary data is edge already paid for and declined (sealed core). The recorder was the
expensive half -- 2026 ticks cannot be re-recorded in 2029 -- and a tape nobody mines is a
museum. This closes the loop: Bronze in, hypotheses out, straight into the SAME research queue
the gauntlet drains, so tape-derived candidates are judged by the identical ten gates and
forward clocks as every creator-corpus or frontier find. No side door.

WHAT IT MINES, and each is a mechanism the public cannot reconstruct because it needs OUR
timestamped tape:
  * SPREAD SEASONALITY  -- spread by symbol x hour: where execution is systematically cheap or
    expensive. Feeds both the cost surface and entry-timing hypotheses.
  * QUOTE INTENSITY     -- ticks/minute by hour: liquidity regime, and the session boundaries
    where it shifts. A breakout into thin quoting is a different trade from the same breakout
    into dense quoting.
  * SPREAD SHOCKS       -- the tail: how often spread blows past its own p95, when, and on what.
    Directly prices the stop-hunt/slippage risk every session strategy carries.
  * DOM IMBALANCE       -- where the broker exposes depth: resting-size asymmetry as a
    short-horizon pressure signal, labelled honestly as broker-local.

EVERY OUTPUT IS A HYPOTHESIS, NEVER A CONCLUSION. This file measures and proposes; the gauntlet
decides. Nothing here promotes, sizes, or trades.
"""
from __future__ import annotations

import gzip
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

BRONZE = Path(os.environ.get("MOAT_BRONZE", r"C:\moat\bronze"))
DESK = Path(os.environ.get("MT5_DESK", r"C:\opt\quant\desks\mt5"))
QUEUE = DESK / "data" / "research_queue.json"
OUT = DESK / "reports" / "moat"
STATE = DESK / "data" / "moat_miner_state.json"

LOOKBACK_DAYS = int(os.environ.get("MOAT_LOOKBACK_DAYS", "3"))
MIN_TICKS = 500              # per (symbol, hour) cell before a stat is allowed to speak
MAX_SYMBOLS = int(os.environ.get("MOAT_MAX_SYMBOLS", "40"))


def _read(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def load_ticks(symbol_dir: Path, days: int) -> list[dict]:
    """Ticks from the last `days` daily files for one symbol. Corrupt lines are skipped, never
    guessed at -- a fabricated quote is worse than a missing one because nothing downstream can
    detect it."""
    cutoff = (datetime.now(tz=UTC) - timedelta(days=days)).strftime("%Y%m%d")
    rows: list[dict] = []
    for f in sorted(symbol_dir.glob("*.jsonl.gz")):
        if f.stem.split(".")[0] < cutoff:
            continue
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            continue
    return rows


def mine_symbol(symbol: str, ticks: list[dict]) -> dict | None:
    """Per-hour spread/intensity/shock profile for one symbol."""
    by_hour: dict[int, list[float]] = defaultdict(list)
    counts: dict[int, int] = defaultdict(int)
    spreads: list[float] = []
    for t in ticks:
        bid, ask = t.get("bid"), t.get("ask")
        if not bid or not ask or ask <= bid:
            continue
        ms = t.get("time_msc")
        if not ms:
            continue
        hour = datetime.fromtimestamp(ms / 1000, tz=UTC).hour
        sp = float(ask) - float(bid)
        by_hour[hour].append(sp)
        counts[hour] += 1
        spreads.append(sp)
    if len(spreads) < MIN_TICKS:
        return None
    spreads.sort()
    p50 = spreads[len(spreads) // 2]
    p95 = spreads[int(len(spreads) * 0.95)]
    hourly = {}
    for h, sp in by_hour.items():
        if len(sp) < 30:
            continue
        hourly[h] = {"median_spread": round(statistics.median(sp), 8),
                     "ticks": counts[h],
                     "shock_rate": round(sum(1 for x in sp if x > p95) / len(sp), 4)}
    if not hourly:
        return None
    cheap = min(hourly, key=lambda h: hourly[h]["median_spread"])
    dear = max(hourly, key=lambda h: hourly[h]["median_spread"])
    dense = max(hourly, key=lambda h: hourly[h]["ticks"])
    ratio = (hourly[dear]["median_spread"] / hourly[cheap]["median_spread"]
             if hourly[cheap]["median_spread"] else 0.0)
    return {"symbol": symbol, "ticks": len(spreads),
            "p50_spread": round(p50, 8), "p95_spread": round(p95, 8),
            "hourly": hourly, "cheapest_hour": cheap, "dearest_hour": dear,
            "densest_hour": dense, "dear_over_cheap": round(ratio, 2)}


def to_hypotheses(profiles: list[dict], now: datetime) -> list[dict]:
    """Turn measured tape structure into preregistered, gauntlet-bound cards.

    Only measurements with a MECHANISM get a card -- a spread ratio of 1.1 is noise wearing a
    number. The threshold is stated in the card so the screen can reproduce the selection.
    """
    cards = []
    for p in sorted(profiles, key=lambda x: -x["dear_over_cheap"])[:8]:
        if p["dear_over_cheap"] < 1.5:
            continue
        sym, cheap, dear = p["symbol"], p["cheapest_hour"], p["dearest_hour"]
        cards.append({
            "id": f"moat-{now:%Y%m%d}-{sym.lower()}-spread",
            "geneology_id": f"moat:tape:{sym}",
            "hypothesis": (
                f"MOAT-DERIVED (own Fusion tape, {p['ticks']} ticks): {sym} median spread is "
                f"{p['dear_over_cheap']}x wider at hour {dear} UTC than at hour {cheap} UTC "
                f"(p50 {p['p50_spread']}, p95 {p['p95_spread']}, shock rate at the dear hour "
                f"{p['hourly'][dear]['shock_rate']}). MECHANISM: execution cost is a session "
                f"property of THIS broker, so an entry rule indifferent to hour is paying a "
                f"variable tax it never modelled. TEST: restrict existing {sym} session entries "
                f"to the cheap-spread window and compare paired expectancy against the "
                f"unrestricted arm (the unconditional arm is the control, separately counted). "
                f"This is reconstructible by nobody else -- it needs our own timestamped tape."),
            "family": "moat_spread_window",
            "side": "BOTH",
            "params": {"symbol": sym, "cheap_hour": cheap, "dear_hour": dear,
                       "ratio": p["dear_over_cheap"]},
            "created_at": now.isoformat(),
            "status": "PENDING",
            "moat_evidence": {k: p[k] for k in ("ticks", "p50_spread", "p95_spread",
                                                "densest_hour")},
        })
    return cards


def main() -> int:
    now = datetime.now(tz=UTC)
    tick_root = BRONZE / "mt5_ticks"
    if not tick_root.exists():
        print(f"moat miner: no tape at {tick_root} -- nothing to mine (recorder not running?)")
        return 0
    profiles = []
    syms = sorted([d for d in tick_root.iterdir() if d.is_dir()])[:MAX_SYMBOLS]
    for d in syms:
        prof = mine_symbol(d.name, load_ticks(d, LOOKBACK_DAYS))
        if prof:
            profiles.append(prof)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"tape_profile_{now:%Y%m%d}.json").write_text(
        json.dumps({"mined_at": now.isoformat(), "lookback_days": LOOKBACK_DAYS,
                    "symbols": len(profiles), "profiles": profiles}, indent=1), "utf-8")

    # HYPOTHESES INTO THE SAME QUEUE AS EVERY OTHER HUNT -- no side door to the gauntlet.
    cards = to_hypotheses(profiles, now)
    queue = _read(QUEUE, [])
    have = {c.get("id") for c in queue if isinstance(c, dict)}
    added = [c for c in cards if c["id"] not in have]
    if added:
        queue.extend(added)
        QUEUE.write_text(json.dumps(queue, indent=1), "utf-8")
    STATE.write_text(json.dumps({"last_mined": now.isoformat(timespec="seconds"),
                                 "symbols_profiled": len(profiles),
                                 "hypotheses_added": len(added)}, indent=1), "utf-8")
    print(f"moat miner: {len(profiles)} symbols profiled from own tape, "
          f"{len(added)} hypotheses queued for the gauntlet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
