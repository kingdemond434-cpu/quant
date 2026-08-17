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
    for it in load_queue():
        if it.get("status") == "QUEUED" and not (REPORTS / f"DONE_loop_{it['id']}").exists():
            return it
    return None


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(BASE / "logs" / "research_loop.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


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
    log("research_loop started")
    while True:
        item = next_pending()
        if item is None:
            log("queue empty — sleeping 300s")
            time.sleep(300)
            continue
        run_experiment(item)
        try:
            subprocess.run([str(PY), "-u", "-W", "ignore", "research/diagnose.py"],
                           cwd=str(BASE), capture_output=True, text=True, timeout=600)
        except Exception as e:
            log(f"diagnose failed: {e!r}")
        time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())