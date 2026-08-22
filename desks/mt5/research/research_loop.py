"""research_loop.py — the autonomous no-handoff iteration loop.

Picks the next QUEUED experiment from data/research_queue.json, executes it through
the full institutional pipeline (run_hunt18 -> battery -> registry -> diagnosis ->
descendants back into the queue), then moves on. Runs forever; the research
supervisor keeps it alive; each experiment is idempotent (DONE_loop_<id> marker).

This is the proof of end-to-end wiring: hypothesis -> implementation -> test ->
diagnose -> next experiment, with no human handoff. LLM = researcher + operator;
the economic mechanism must still explain why money should exist.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
QUEUE = BASE / "data" / "research_queue.json"
REPORTS = BASE / "reports"
PY = Path(sys.executable)


def load_queue() -> list[dict]:
    if not QUEUE.exists():
        return []
    try:
        return json.loads(QUEUE.read_text("utf-8"))
    except Exception:
        return []


def next_pending() -> dict | None:
    q = load_queue()
    alive = runner_alive()
    for it in q:
        if it.get("status") == "QUEUED" and not (REPORTS / f"DONE_loop_{it['id']}").exists():
            return it
        if it.get("status") == "RUNNING" and not alive \
                and not (REPORTS / f"DONE_loop_{it['id']}").exists():
            it["status"] = "QUEUED"
            try:
                QUEUE.write_text(json.dumps(q, indent=2), encoding="utf-8")
            except Exception:
                pass
            log(f"stale RUNNING reset to QUEUED: {it['id']} (no live runner)")
            return it
    return None


def runner_alive() -> bool:
    import psutil
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if (p.info["name"] or "").lower().startswith("python") \
                    and any("run_hunt18" in (c or "") for c in (p.info["cmdline"] or [])):
                return True
        except Exception:
            continue
    return False


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(BASE / "logs" / "research_loop.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def until_next_hour() -> float:
    now = datetime.now(timezone.utc)
    nxt = now.replace(minute=0, second=0, microsecond=0)
    nxt = nxt.replace(hour=nxt.hour + 1)
    return min(3600.0, max(60.0, (nxt - now).total_seconds()))


def hourly_demo_snapshot() -> None:
    """Hourly hypothesis->demo ledger: queue state + latest hunt18 battery demos."""
    q = load_queue()
    counts: dict[str, int] = {}
    for it in q:
        counts[it.get("status", "?")] = counts.get(it.get("status", "?"), 0) + 1
    done = sorted(REPORTS.glob("DONE_loop_*"))
    demos = []
    for f in sorted(REPORTS.glob("hunt18_*.json"))[-8:]:
        try:
            d = json.loads(f.read_text("utf-8"))
            demos.append({"id": f.stem,
                          "survivors": len(d.get("survivors", [])),
                          "cells": len(d.get("all", []))})
        except Exception:
            pass
    row = {"ts": datetime.now(timezone.utc).isoformat(),
           "queue": counts, "queued_pending": int(next_pending() is not None),
           "experiments_done": len(done), "recent_demos": demos}
    with open(REPORTS / "hypothesis_demo.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    log(f"hourly demo snapshot: queue={counts} done={len(done)}")


def run_experiment(item: dict) -> int:
    exp_id = item["id"]
    log(f"starting {exp_id}: {item.get('family')} {item.get('side')} "
        f"{item.get('params')} [{item.get('hypothesis', '')[:80]}]")
    r = subprocess.run([str(PY), "-u", "-W", "ignore",
                        "research/run_hunt18.py", exp_id],
                       cwd=str(BASE), capture_output=True, text=True, timeout=7200)
    tail = "\n".join(r.stdout.splitlines()[-6:])
    log(f"{exp_id} rc={r.returncode}\n{tail}")
    if r.returncode != 0:
        log(f"{exp_id} FAILED: {r.stderr[-600:]}")
        return r.returncode
    return 0


def main() -> int:
    log("research_loop started (hourly hypothesis->demo cadence)")
    while True:
        item = next_pending()
        if item is None:
            log(f"queue empty — next hourly tick in {until_next_hour():.0f}s")
            time.sleep(until_next_hour())
            hourly_demo_snapshot()
            continue
        run_experiment(item)
        try:
            subprocess.run([str(PY), "-u", "-W", "ignore", "research/diagnose.py"],
                           cwd=str(BASE), capture_output=True, text=True, timeout=600)
        except Exception as e:
            log(f"diagnose failed: {e!r}")
        hourly_demo_snapshot()
        # A non-empty queue is work, not a clock. The old unconditional hourly sleep left every
        # second and later hypothesis idle even though the sole worker was free. Continue directly;
        # the queue-empty branch above remains the low-cost backoff.
        log("experiment finished; draining the next queued hypothesis immediately")


if __name__ == "__main__":
    sys.exit(main())
