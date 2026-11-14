#!/usr/bin/env python3
"""SPREAD STATE: what the spread normally is at this hour, and how wide is too wide to enter
(trader-brain row #6).

A professional does not cross a spread three times its usual width to put on a position the
book could put on ten minutes later. The desk records `spread_at_decision` on every intent and
the broker's M1 tape holds the spread of every minute, but nothing compared the two at the moment
of entry: rollover (server hour 00) runs 3-17x the day's spread on the exotics, and a sleeve that
fires there pays it in full.

WHAT THIS WRITES (`reports/SPREAD_STATE.json`):
  * `hour_p50_pts[symbol][server_hour]` -- the median spread, in points, of that symbol's ticked
    M1 bars at that SERVER hour, from `research/fusion_spread_tape.read_tape` (the broker's own
    tape; hours stay on the server clock, so the gateway compares them with the hour of the
    live tick's own stamp and no offset is ever applied);
  * `k` -- the multiple of that median above which an entry is DEFERRED, chosen from the desk's
    own fills (markout evidence), or null.

HOW k IS CHOSEN, AND WHY IT CAN BE NULL. Every filled intent with a spread, a fill and a stop is
an observation: `ratio` = its spread over the hour's median, `cost_r` = (half the spread plus the
adverse slippage) over the stop distance -- the share of the trade's risk paid to get in. For each
candidate k in CANDIDATE_K the fills above k are compared with those at or below it; k is the
SMALLEST candidate whose wide fills paid at least COST_MULTIPLE times the median cost of the
normal ones, with at least MIN_WIDE fills above it. No candidate qualifying is a real answer:
k is null and the gateway's gate stays OFF (a deferral the evidence does not support would be a
veto with no growth case, Rule 1). The gate defers, it never kills: the next pass re-decides.

    python desks/mt5/research/spread_state.py [--json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
INTENTS = DESK / "data" / "order_intents.jsonl"
OUT = DESK / "reports" / "SPREAD_STATE.json"

#: Candidate multiples, smallest first. 1.5x is where a quote is plainly off its normal width; 5x
#: is past the widest rollover ratio measured on the majors and inside the exotics' 3-17x band.
CANDIDATE_K = (1.5, 2.0, 3.0, 4.0, 5.0)
#: The wide fills must have paid at least this multiple of the normal fills' median entry cost
#: (in R) for a deferral to be worth a pass: twice the cost is the point where waiting one pass
#: (60 s, research/gateway_resident.py) is cheaper than the edge any certified sleeve shows.
COST_MULTIPLE = 2.0
#: Fills needed above a candidate before it can be chosen: below ten, one bad rollover fill decides
#: the desk's threshold for every symbol.
MIN_WIDE = 10


def _jsonl(p: Path) -> list[dict[str, Any]]:
    try:
        out = []
        for line in p.read_text("utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
        return out
    except OSError:
        return []


def live_symbols() -> list[str]:
    """Symbols of every sleeve that is not retired: the ones the gate can ever be asked about."""
    try:
        doc = json.loads(SLEEVES.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else doc.get("sleeves", doc)
    rows = rows if isinstance(rows, list) else list(rows.values()) if isinstance(rows, dict) else []
    return sorted({str(r.get("symbol")) for r in rows if isinstance(r, dict) and r.get("symbol")
                   and str(r.get("status") or "").upper() != "RETIRED"})


def hour_medians(symbols: list[str], universe: Path = UNIVERSE) -> tuple[dict[str, Any],
                                                                         dict[str, str]]:
    """{symbol: {server_hour: p50_pts}} from the broker's M1 tape, and why any symbol is absent."""
    from research.fusion_spread_tape import read_tape
    out: dict[str, Any] = {}
    why: dict[str, str] = {}
    for sym in symbols:
        try:
            tape = read_tape(universe, sym)
        except Exception as exc:
            why[sym] = f"tape unreadable: {type(exc).__name__}"
            continue
        hours = tape.get("by_server_hour") if tape.get("status") == "MEASURED" else None
        if not hours:
            why[sym] = str(tape.get("why") or "no measured hours")
            continue
        out[sym] = {h: float(v["p50"]) for h, v in hours.items()
                    if isinstance(v, dict) and isinstance(v.get("p50"), (int, float))}
    return out, why


def _server_hour(utc_iso: Any) -> int | None:
    """The broker server's wall-clock hour at a true-UTC instant."""
    try:
        t = datetime.fromisoformat(str(utc_iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    try:
        import pandas as pd
        from mt5desk.broker_clock import broker_to_utc
        u = pd.Timestamp(t).tz_convert("UTC").tz_localize(None)
        # broker_to_utc(x) = x - offset(x); read at x = u, the offset is the server's lead on UTC
        # (it moves only at a DST switch, an hour either side of which this can be off by one).
        off = u - broker_to_utc(u).tz_convert("UTC").tz_localize(None)
        return int((u + off).hour)
    except Exception:
        return None


def observations(medians: dict[str, Any], intents: Path = INTENTS) -> list[dict[str, float]]:
    """(ratio, cost_r) for every filled intent with a spread, a fill, a stop and a point size."""
    obs = []
    for r in _jsonl(intents):
        sym = str(r.get("symbol") or "")
        try:
            spread = float(r["spread_at_decision"])
            fill, want, sl = float(r["fill_price"]), float(r["intended"]), float(r["sl"])
            point = float(r["point"])
        except (KeyError, TypeError, ValueError):
            continue
        hour = _server_hour(r.get("time"))
        p50 = (medians.get(sym) or {}).get(str(hour)) if hour is not None else None
        risk = abs(want - sl)
        if not p50 or p50 <= 0 or point <= 0 or risk <= 0 or fill <= 0:
            continue
        side = str(r.get("side") or "").lower()
        slip = (fill - want) if side in ("buy", "1", "long") else (want - fill)
        obs.append({"ratio": (spread / point) / p50,
                    "cost_r": (0.5 * spread + max(slip, 0.0)) / risk})
    return obs


def choose_k(obs: list[dict[str, float]]) -> tuple[float | None, list[dict[str, Any]]]:
    rows = []
    chosen = None
    for k in CANDIDATE_K:
        wide = [o["cost_r"] for o in obs if o["ratio"] > k]
        normal = [o["cost_r"] for o in obs if o["ratio"] <= k]
        base = statistics.median(normal) if normal else None
        mean_wide = statistics.fmean(wide) if wide else None
        ok = bool(wide) and len(wide) >= MIN_WIDE and base is not None and base > 0 \
            and mean_wide is not None and mean_wide >= COST_MULTIPLE * base
        rows.append({"k": k, "n_wide": len(wide), "n_normal": len(normal),
                     "median_cost_r_normal": base, "mean_cost_r_wide": mean_wide,
                     "qualifies": ok})
        if ok and chosen is None:
            chosen = k
    return chosen, rows


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    syms = live_symbols()
    medians, absent = hour_medians(syms)
    obs = observations(medians)
    k, ladder = choose_k(obs)
    return {"generated_utc": now.isoformat(timespec="seconds"),
            "status": "MEASURED" if medians else "UNMEASURED",
            "k": k, "k_status": "CHOSEN" if k is not None else "NO_EVIDENCE",
            "k_ladder": ladder, "n_fills": len(obs),
            "cost_multiple": COST_MULTIPLE, "min_wide": MIN_WIDE,
            "clock": "hours are the broker SERVER's wall clock (the live tick's own stamp)",
            "hour_p50_pts": medians, "absent": absent,
            "rule": "the gateway defers a new entry while the live spread exceeds k x this "
                    "symbol's median at this server hour; k null leaves the gate off",
            "valid_until": (now + timedelta(hours=26)).isoformat(timespec="seconds")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    if not a.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
        tmp.replace(OUT)
    if a.json:
        print(json.dumps(doc, default=str))
    else:
        print(f"spread_state: {doc['status']} k={doc['k']} ({doc['k_status']}, "
              f"{doc['n_fills']} fills, {len(doc['hour_p50_pts'])} symbols)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
