#!/usr/bin/env python3
"""MINER HEALTH FENCE -- a source that has produced nothing but errors is DOWN, and says so.

WHY THIS EXISTS (measured 2026-08-26, gap-fixer cycle). Six of the desk's 41 miners --
collective2, darwinex, forexpeacearmy, fxblue, myfxbook_outlook, propfirm_boards -- had a 100%
fetch-error rate for seven days. Every hour each one made a request, got 403 or 404, archived a
single `fetch_error` row, and nothing anywhere escalated it. Arrivals over the same window ran
at 24/week against a 160/week baseline.

The detection already existed: scripts/build_research_facts.py computes `error_rate` per miner
and even publishes an `all_errors` list. What was missing was an ACTUATOR -- something whose
exit status a scheduler notices. This desk's recurring defect class is exactly that (a detector
and its actuator both work and the defect can never close), so this file is deliberately small
and does one thing: it FAILS.

THE COUNTING TRAP THIS AVOIDS. An error row is still a row. To anything that measures volume,
a fully dead miner reports `rows_7d: 19` and looks productive -- which is precisely how six dead
channels stayed invisible while their own archives recorded the 403s. Health is therefore
measured as REAL rows (a row that is not an error and not a raw-capture stub), never as rows.

WALLED IS NOT BROKEN. A source in seed_miners.SOURCE_WALLS has a recorded verdict and evidence
(§13 refusal, anti-bot challenge, server 403) and is on a rediscovery cadence. That is a
DISPOSITIONED state, so it is reported and never counted as a defect -- otherwise the fence
would page forever about a decision the desk already made, and a fence that cries wolf is
switched off, which is how the silence comes back (L1.43).

Exit 0 = every unwalled miner has produced real rows recently. Exit 1 = at least one is down.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INTEL = REPO / "desks" / "mt5" / "data" / "intelligence"
# A miner dark for this many consecutive sweeps is down. The sweep is hourly, so this is
# tolerant of a transient 5xx or a brief network blip and intolerant of a dead channel.
DEFAULT_STREAK = 6
ERROR_KINDS = {"fetch_error", "error"}


def _walled() -> dict[str, dict]:
    """The dispositioned walls, imported from the miner module rather than restated here.

    Import the number, never restate it: a second copy of this list would drift from the one
    the miners actually obey, and the fence would grade sources against a registry nobody uses.
    """
    sys.path.insert(0, str(REPO))
    try:
        from desks.mt5.side_channels.seed_miners import SOURCE_WALLS
    except Exception:
        return {}
    return dict(SOURCE_WALLS)


def classify_row(r: object) -> str:
    """THE one definition of what a miner row is: error | walled | stub | real.

    Imported by scripts/build_research_facts.py so the facts pack and this fence cannot
    disagree about which sources are alive. Two copies of this rule would drift, and the
    drift would be invisible -- the pack would certify a source healthy while the fence
    called it dark, and whichever ran second would look like the broken one.
    """
    if not isinstance(r, dict):
        return "stub"
    kind = str(r.get("kind") or "")
    if kind in ERROR_KINDS or kind.endswith("error"):
        return "error"
    if kind == "walled":
        return "walled"
    if r.get("needs_selector_work"):
        return "stub"
    return "real"


def _is_real(r: dict) -> bool:
    """A row that carries actual discovered information."""
    return classify_row(r) == "real"


def scan(streak: int, days: int) -> dict:
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    walls = _walled()
    report: dict[str, dict] = {}
    for src_dir in sorted(p for p in INTEL.iterdir() if p.is_dir()):
        files = sorted(src_dir.glob("discoveries_*.json"))
        if not files:
            continue
        recent = [f for f in files
                  if datetime.fromtimestamp(f.stat().st_mtime, tz=UTC) >= cutoff]
        if not recent:
            continue
        runs, last_err = [], ""
        for f in recent[-max(streak, 1) * 3:]:
            try:
                rows = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rows, list):
                continue
            real = sum(1 for r in rows if _is_real(r))
            runs.append(real)
            if real == 0:
                for r in rows:
                    if isinstance(r, dict) and str(r.get("kind")) in ERROR_KINDS:
                        last_err = str(r.get("title") or "")[:140]
        if not runs:
            continue
        dark = 0
        for real in reversed(runs):
            if real:
                break
            dark += 1
        report[src_dir.name] = {
            "runs_seen": len(runs), "dark_streak": dark,
            "real_rows_recent": sum(runs), "last_error": last_err,
            "walled": src_dir.name in walls,
            "verdict": walls.get(src_dir.name, {}).get("verdict", ""),
        }
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--streak", type=int, default=DEFAULT_STREAK,
                    help="consecutive dark sweeps before a miner counts as down")
    ap.add_argument("--days", type=int, default=3, help="lookback window over archives")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    report = scan(a.streak, a.days)
    if not report:
        print("miner-health: NO ARCHIVES FOUND -- unmeasured, not healthy")
        return 1

    down = {k: v for k, v in report.items()
            if v["dark_streak"] >= a.streak and not v["walled"]}
    walled = {k: v for k, v in report.items() if v["walled"]}
    if a.json:
        print(json.dumps({"down": down, "walled": walled, "all": report}, indent=1))
        return 1 if down else 0

    healthy = len(report) - len(down) - len(walled)
    print(f"miner-health: {len(report)} sources | healthy={healthy} "
          f"walled={len(walled)} DOWN={len(down)}")
    for name, v in sorted(walled.items()):
        print(f"  WALLED  {name:22s} {v['verdict']} (dispositioned, on rediscovery cadence)")
    for name, v in sorted(down.items(), key=lambda kv: -kv[1]["dark_streak"]):
        print(f"  DOWN    {name:22s} {v['dark_streak']} consecutive dark sweeps "
              f"| {v['last_error'] or 'no error row -- produced only stubs'}")
    if down:
        print(f"\nFAIL: {len(down)} miner(s) producing no real rows. Each is either a route "
              f"bug (fix the URL) or a wall (record the verdict in "
              f"seed_miners.SOURCE_WALLS). Silence is neither.")
        return 1
    print("PASS: every unwalled miner produced real rows inside its streak window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
