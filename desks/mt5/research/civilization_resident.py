#!/usr/bin/env python3
"""THE 24/7 RESEARCH-CIVILIZATION RESIDENT (zuck, 2026-09-30).

Runs the #133 mining pipeline restricted to the civilization lanes
(desks/mt5/data/source_rosters/civilizations.yaml + civilizations_frontier.jsonl) in a loop that
"immediately continues": each pass fetches every lane that is due by its cadence class
(continuous 15 min / hourly / daily / weekly), routes records by ontology, parks alpha
candidates, releases them at the judge's drain rate, and publishes
desks/mt5/reports/civilizations/*. Between passes it sleeps only until the next lane is due.

While it runs it writes RESIDENT_HEARTBEAT.json; the hourly `global_mining` leg sees the fresh
heartbeat and leaves these lanes to it, and takes them back the moment the heartbeat is stale,
so the lanes are never idle and never fetched twice.

    python desks/mt5/research/civilization_resident.py --once --budget-s 600
    python desks/mt5/research/civilization_resident.py --loop
    python desks/mt5/research/civilization_resident.py --ingest-only     # graph from artifacts
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mining_supervisor as MS  # noqa: E402

from libs.civilizations import graph as G  # noqa: E402
from libs.mining import acquirer as acq  # noqa: E402
from libs.mining.pit_store import parse_time, utcnow  # noqa: E402

#: the resident's own artifact (written by Resident.after_pass every pass)
REPORT = _DESK / "reports" / "civilizations" / "CIVILIZATION_METRICS.json"
MIN_SLEEP_S = 30
MAX_SLEEP_S = 900


def seconds_to_next_due(pipe: MS.Pipeline) -> float:
    now = utcnow()
    waits = []
    for s in pipe.roster:
        if pipe.civ is None or not pipe.civ.is_civ(s.id):
            continue
        last = parse_time(pipe.cursors.get(s.id).get("last_run"))
        if last is None:
            return MIN_SLEEP_S
        waits.append((last + timedelta(minutes=s.cadence_minutes) - now).total_seconds())
    return max(MIN_SLEEP_S, min(MAX_SLEEP_S, min(waits) if waits else MAX_SLEEP_S))


def one_pass(budget_s: float) -> dict:
    pipe = MS.Pipeline(hooks=MS.desk_hooks(), civ_mode="only",
                       roster=acq.load_roster(root=MS._ROOT))
    if pipe.civ is None:
        return {"error": f"civilizations unavailable: {pipe.civ_error}"}
    pipe.civ.beat(state="pass_start")
    m = pipe.run_pass(budget_s)
    pipe.civ.beat(state="pass_end", next_in_s=seconds_to_next_due(pipe))
    civ = json.loads((pipe.reports.parent / "civilizations" / "CIVILIZATION_METRICS.json")
                     .read_text("utf-8"))
    return {"records_processed": m.get("records_processed"),
            "release": civ.get("release"), "coverage": civ.get("coverage"),
            "fence": civ.get("fence"), "next_in_s": seconds_to_next_due(pipe)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--budget-s", type=float, default=600.0)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--ingest-only", action="store_true")
    ap.add_argument("--max-passes", type=int, default=0, help="0 = forever (with --loop)")
    args = ap.parse_args(argv)
    if args.ingest_only:
        kg = G.KnowledgeGraph(MS.DATA.parent / "civilizations" / "knowledge.db")
        print(json.dumps(G.ingest_all(kg, MS._ROOT), indent=1, default=str))
        return 0
    if not args.loop:
        print(json.dumps(one_pass(args.budget_s), indent=1, default=str))
        return 0
    n = 0
    while True:
        t0 = time.monotonic()
        try:
            out = one_pass(args.budget_s)
        except Exception as exc:
            out = {"error": f"{type(exc).__name__}: {exc}"[:300], "next_in_s": MIN_SLEEP_S}
        print(json.dumps({"pass": n, "took_s": round(time.monotonic() - t0, 1), **out},
                         default=str), flush=True)
        n += 1
        if args.max_passes and n >= args.max_passes:
            return 0
        time.sleep(float(out.get("next_in_s") or MIN_SLEEP_S))


if __name__ == "__main__":
    raise SystemExit(main())
