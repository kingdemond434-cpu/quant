"""PROBATION -- unwired organs run on a clock, in rotation, until someone promotes them.

`wiring_ceo` writes data/probation_queue.json: every organ that nothing schedules and that can
run standalone. This leg (heavy plan, hourly; also the daily cycle) takes the organs least
recently exercised, runs each under a bounded budget -- `--dry-run` when the organ takes it,
plain otherwise -- and records the outcome. Nothing here edits the cycle: an organ earns its
named leg through the docket, with this evidence attached (how many clean runs, how long, what
it printed). What probation removes is the state the principal named: a build that has never
run, sitting in the tree while the desk grows around it.

NEVER MONEY. The queue excludes anything whose name touches the gateway, releases, the deadman,
orders or the tree (wiring_ceo.NEVER_PROBATION); this runner refuses the same names a second
time, so a mistaken queue entry cannot reach them.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
QUEUE = DESK / "data" / "probation_queue.json"
STATE = DESK / "data" / "probation_state.json"
OUT = DESK / "reports" / "PROBATION.json"
NEVER = ("gateway", "e8_", "promoter", "run_gateway", "adopt", "seal", "release", "deadman",
         "kill", "close", "order", "executor", "install", "reboot", "no_log", "reclaim",
         "delete", "wipe", "prune", "rotate", "migrate", "sync_", "push", "commit")


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def pick(queue: list[dict[str, Any]], state: dict[str, Any], k: int) -> list[dict[str, Any]]:
    """The k organs least recently run (never-run first), refusing money-path names."""
    rows = [q for q in queue if isinstance(q, dict) and q.get("organ")
            and not any(t in str(q["organ"]).lower() for t in NEVER)]
    last = state.get("last_run") if isinstance(state.get("last_run"), dict) else {}
    rows.sort(key=lambda q: (str(last.get(str(q["organ"])) or ""), str(q["organ"])))
    return rows[:k]


def run_one(row: dict[str, Any], budget_s: int, cwd: Path | None = None) -> dict[str, Any]:
    organ = str(row["organ"])
    path = ROOT / organ
    if not path.exists():
        return {"organ": organ, "status": "MISSING", "why": f"{organ} is not in the tree"}
    args = [sys.executable, "-u", "-W", "ignore", str(path)]
    if row.get("dry_run"):
        args.append("--dry-run")
    work = cwd or (ROOT / "desks" / "mt5" if organ.startswith("desks/mt5/") else ROOT)
    t0 = time.monotonic()
    try:
        r = subprocess.run(args, capture_output=True, text=True, cwd=str(work),
                           timeout=budget_s, check=False)
        return {"organ": organ, "status": "OK" if r.returncode == 0 else "EXIT",
                "exit_code": r.returncode, "seconds": round(time.monotonic() - t0, 1),
                "dry_run": bool(row.get("dry_run")),
                "tail": (r.stdout or r.stderr or "").strip().splitlines()[-3:]}
    except subprocess.TimeoutExpired:
        return {"organ": organ, "status": "TIMEOUT", "seconds": budget_s,
                "dry_run": bool(row.get("dry_run")),
                "why": f"exceeded {budget_s}s; the organ needs its own budgeted leg"}
    except OSError as exc:
        return {"organ": organ, "status": "FAILED_TO_START", "why": f"{type(exc).__name__}: {exc}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--per-pass", type=int, default=8)
    ap.add_argument("--budget-s", type=int, default=120)
    ap.add_argument("--dry-run", action="store_true", help="list what would run")
    a = ap.parse_args(argv)
    queue = _read(QUEUE).get("queue") or []
    state = _read(STATE)
    chosen = pick(queue, state, a.per_pass)
    print(f"probation: {len(queue)} queued, running {len(chosen)} this pass")
    if a.dry_run:
        for c in chosen:
            print(f"  would run {c['organ']}{' --dry-run' if c.get('dry_run') else ''}")
        return 0
    results = [run_one(c, int(c.get("budget_s") or a.budget_s)) for c in chosen]
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    last = state.get("last_run") if isinstance(state.get("last_run"), dict) else {}
    hist = state.get("history") if isinstance(state.get("history"), dict) else {}
    for r in results:
        last[r["organ"]] = now
        h = hist.setdefault(r["organ"], {"runs": 0, "clean": 0})
        h["runs"] = int(h.get("runs", 0)) + 1
        h["clean"] = int(h.get("clean", 0)) + (1 if r.get("status") == "OK" else 0)
        h["last_status"] = r.get("status")
        if isinstance(r.get("seconds"), (int, float)):
            prev_s = h.get("seconds")
            h["seconds"] = (round(max(float(prev_s), float(r["seconds"])), 1)
                            if isinstance(prev_s, (int, float)) else round(float(r["seconds"]), 1))
        print(f"  {r['organ']:<58} {r.get('status'):<8} {r.get('seconds', '')}s")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"last_run": last, "history": hist, "at": now}, indent=1),
                     encoding="utf-8")
    promotable = sorted((k for k, v in hist.items() if int(v.get("clean", 0)) >= 3),
                        key=lambda k: -int(hist[k].get("clean", 0)))
    doc = {"at": now, "n_queued": len(queue), "ran": results, "history": hist,
           "promotable": promotable,
           "rule": ("least recently run first; three clean runs make an organ PROMOTABLE to a "
                    "named leg -- the promotion is a docket task with this evidence")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)
    print(f"  promotable: {len(promotable)} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
