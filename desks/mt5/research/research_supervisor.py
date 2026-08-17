"""research_supervisor: permanent self-healing watchdog for the MT5 research desk.

Restarts any research process that died before writing its DONE marker, forever,
until the work actually completes. Runs as a persistent loop; a scheduled task
(BootTrigger + 5-min tick) guarantees one instance is always alive.

Backoff: if a target dies within 180s of a restart, it is quarantined for 30 min
(prevents infinite restart storms on a crashing script; the crash log in
logs/<name>_super.log always shows why).

Disable permanently: create data/SUPERVISOR_OFF
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

BASE = Path(__file__).resolve().parent.parent
LOGS = BASE / "logs"
STATE = LOGS / "supervisor_state.json"
LOG = LOGS / "supervisor.log"
PYW = Path(sys.executable).parent / "pythonw.exe"
TARGETS = [
    dict(name="hunt12", args=["-u", "-W", "ignore", "research/run_hunt12.py"],
         marker="reports/DONE_hunt12", match="run_hunt12.py"),
    dict(name="hunt16", args=["-u", "-W", "ignore", "research/run_hunt16.py"],
         marker="reports/DONE_hunt16", match="run_hunt16.py"),
    dict(name="placebo", args=["-u", "-W", "ignore", "research/placebo_test.py",
                               "XAUUSD", "AUDCAD", "AUDJPY"],
         marker="reports/DONE_placebo", match="placebo_test.py"),
]


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_running(match: str) -> bool:
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if (p.info["name"] or "").lower().startswith("python") \
                    and any(match in (c or "") for c in (p.info["cmdline"] or [])):
                return True
        except Exception:
            continue
    return False


def already_supervised() -> bool:
    me = psutil.Process().pid
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if p.pid == me:
                continue
            if not (p.info["name"] or "").lower().startswith("python"):
                continue
            cmd = " ".join(p.info["cmdline"] or [])
            if "research_supervisor.py" in cmd:
                return True
        except Exception:
            continue
    return False


def main() -> int:
    if (BASE / "data" / "SUPERVISOR_OFF").exists():
        log("supervisor: disabled (data/SUPERVISOR_OFF present)")
        return 0
    if already_supervised():
        log("supervisor: another instance alive, exiting")
        return 0

    LOGS.mkdir(exist_ok=True)
    state: dict = {}
    try:
        state = json.loads(STATE.read_text("utf-8"))
    except Exception:
        pass
    log("supervisor: started")
    while True:
        if (BASE / "data" / "SUPERVISOR_OFF").exists():
            log("supervisor: disabled flag appeared, exiting")
            return 0
        now = time.time()
        for t in TARGETS:
            if (BASE / t["marker"]).exists():
                continue
            if is_running(t["match"]):
                continue
            st = state.get(t["name"], {})
            last = float(st.get("last_spawn", 0) or 0)
            if now - last < 180:
                log(f"supervisor: {t['name']} keeps dying, quarantined until "
                    f"{datetime.fromtimestamp(last + 1800, timezone.utc).isoformat()}")
                continue
            try:
                sl = open(LOGS / f"{t['name']}_super.log", "ab")
                proc = subprocess.Popen(
                    [str(PYW)] + t["args"], cwd=str(BASE),
                    stdout=sl, stderr=subprocess.STDOUT,
                    creationflags=subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP)
                state[t["name"]] = {"last_spawn": now, "pid": proc.pid}
                STATE.write_text(json.dumps(state), encoding="utf-8")
                log(f"supervisor: respawned {t['name']} pid={proc.pid}")
            except Exception as e:
                log(f"supervisor: FAILED to spawn {t['name']}: {e!r}")
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
