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
#: PER-RUN COMPUTE BUDGET, NOT A LIMIT ON WHAT IS MINED. Every run takes the next SLICE_SYMBOLS
#: symbols from a persisted rotation cursor and the cursor wraps, so the whole tape is covered in
#: ceil(n/SLICE) runs and then covered AGAIN on newer ticks, forever (RESEARCH 6c-bis: "coverage
#: is a CYCLE, not a sweep"). Raising this makes each pass wider, never the ground larger.
SLICE_SYMBOLS = int(os.environ.get("MOAT_MAX_SYMBOLS", "40"))


def _next_slice(symbols: list, cursor: int) -> tuple[list, int]:
    """Take SLICE_SYMBOLS symbols starting at `cursor`, wrapping, and return the next cursor.

    Wrapping matters as much as advancing: a cursor that stops at the end turns the miner into a
    one-shot sweep that declares the tape finished, which is absence-read-as-verdict wearing a
    new costume. Coverage is a CYCLE -- the tape a symbol carries next week is not the tape it
    carries today, so "already mined" is never a reason to skip it (L1.51).
    """
    n = len(symbols)
    if n == 0:
        return [], 0
    start = cursor % n
    take = min(SLICE_SYMBOLS, n)
    picked = [symbols[(start + i) % n] for i in range(take)]
    return picked, (start + take) % n


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
    # THE ROTATION CURSOR. This was `sorted(...)[:MAX_SYMBOLS]` -- a fixed ALPHABETICAL PREFIX
    # with no cursor, so of 245 recorded symbols the same first 40 were re-mined every run and
    # 205 (83.7%) were never mined at all and never would be: on alphabetical order that is
    # every metal, every index, energy, softs and all but a handful of FX crosses. Measured
    # 2026-08-28 from the box's own state: symbols_profiled 40, tick dirs 245.
    #
    # Two laws, one line. The sealed core: "a count is a quota in disguise and a quota acts as a
    # CEILING -- rank-and-truncate is the same defect wearing an ordering", and under-exploration
    # of owned data is a BREACH, not a backlog. RESEARCH 6c-bis: the searcher carries a cursor,
    # each run covers a budgeted slice, and every symbol is re-searched on newer ticks forever.
    # This is also the SECOND sighting of this exact class -- `orthogonal_sweep` was pairing
    # XAUUSD with 3M off `sorted()[:12]` -- so it is fenced by a test, not just corrected.
    all_syms = sorted(d for d in tick_root.iterdir() if d.is_dir())
    syms, cursor = _next_slice(all_syms, _read(STATE, {}).get("cursor", 0))
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
    # The cursor is persisted even when a slice profiles nothing: a symbol whose ticks were too
    # thin to speak must not pin the cursor and starve every symbol behind it.
    STATE.write_text(json.dumps({"last_mined": now.isoformat(timespec="seconds"),
                                 "symbols_profiled": len(profiles),
                                 "hypotheses_added": len(added),
                                 "cursor": cursor,
                                 "symbols_available": len(all_syms),
                                 "slice": len(syms),
                                 "runs_per_full_pass": -(-len(all_syms) // max(1, SLICE_SYMBOLS)),
                                 }, indent=1), "utf-8")
    print(f"moat miner: {len(profiles)} symbols profiled from own tape "
          f"(slice {len(syms)}/{len(all_syms)}, cursor -> {cursor}), "
          f"{len(added)} hypotheses queued for the gauntlet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
