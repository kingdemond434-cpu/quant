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
import os
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
if os.name == "nt":
    PYW = Path(sys.executable).parent / "pythonw.exe"
    CHILD_LOGS = Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / "opencode" / "logs"
else:
    PYW = Path(sys.executable)
    CHILD_LOGS = LOGS / "child"
TARGETS = [
    dict(name="hunt12", args=["-u", "-W", "ignore", "research/run_hunt12.py"],
         marker="reports/DONE_hunt12", match="run_hunt12.py"),
    dict(name="hunt16", args=["-u", "-W", "ignore", "research/run_hunt16.py"],
         marker="reports/DONE_hunt16", match="run_hunt16.py"),
    dict(name="placebo", args=["-u", "-W", "ignore", "research/placebo_test.py",
                               "XAUUSD", "AUDCAD", "AUDJPY"],
         marker="reports/DONE_placebo", match="placebo_test.py"),
    dict(name="hunt17", args=["-u", "-W", "ignore", "research/run_hunt17.py"],
         marker="reports/DONE_hunt17", match="run_hunt17.py"),
    dict(name="fragility", args=["-u", "-W", "ignore", "research/fragility.py"],
         marker="reports/DONE_fragility", match="fragility.py"),
    dict(name="qquant_gates",
         python=r"C:\Users\dell\quant-platform\.venv\Scripts\python.exe",
         args=["-u", "-W", "ignore", "research/qquant_gates.py", "--workers", "8"],
         marker="reports/DONE_qquant_gates", match="qquant_gates.py"),
    dict(name="regime_oos", args=["-u", "-W", "ignore", "research/regime_discovery.py"],
         marker="reports/DONE_regime_oos", match="regime_discovery.py"),
    dict(name="merge", args=["-u", "-W", "ignore", "research/merge_qquant.py"],
         marker="reports/DONE_merge", match="merge_qquant.py"),
    dict(name="research_loop", args=["-u", "-W", "ignore", "research/research_loop.py"],
         marker="reports/DONE_loop_final", match="research_loop.py"),
    dict(name="hunt19", args=["-u", "-W", "ignore", "research/run_hunt19.py"],
         marker="reports/DONE_hunt19", match="run_hunt19.py"),
    dict(name="hunt20", args=["-u", "-W", "ignore", "research/run_hunt20.py"],
         marker="reports/DONE_hunt20", match="run_hunt20.py"),
    dict(name="hunt21", args=["-u", "-W", "ignore", "research/run_hunt21.py"],
         marker="reports/DONE_hunt21", match="run_hunt21.py"),
    dict(name="hunt22", args=["-u", "-W", "ignore", "research/run_hunt22.py"],
         marker="reports/DONE_hunt22", match="run_hunt22.py"),
    dict(name="hunt23", args=["-u", "-W", "ignore", "research/run_hunt23.py"],
         marker="reports/DONE_hunt23", match="run_hunt23.py"),
    dict(name="macro_desk", args=["-u", "-W", "ignore", "research/macro_desk.py"],
         marker="reports/DONE_macro_never", match="macro_desk.py"),
    dict(name="options_desk", args=["-u", "-W", "ignore", "research/options_desk.py"],
         marker="reports/DONE_options_never", match="options_desk.py"),
    dict(name="crowding_miner", args=["-u", "-W", "ignore", "research/crowding_miner.py"],
         marker="reports/DONE_crowding_never", match="crowding_miner.py"),
    dict(name="news_desk", args=["-u", "-W", "ignore", "research/news_desk.py"],
         marker="reports/DONE_news_final", match="news_desk.py"),
    dict(name="signal_gate", args=["-u", "-W", "ignore",
                                   "research/signal_gate.py", "run_hunt18"],
         marker="reports/DONE_signal_gate_never", match="signal_gate.py"),
    dict(name="universal",
         python=r"C:\Users\dell\quant-platform\.venv\Scripts\python.exe",
         args=["-u", "-W", "ignore", "research/universal_gate.py"],
         marker="reports/DONE_universal_hunt23", match="universal_gate.py"),
    dict(name="meta_desk",
python=r"C:\Users\dell\quant-platform\.venv\Scripts\python.exe",
          args=["-u", "-W", "ignore", "research/meta_desk.py"],
          marker="reports/DONE_meta", match="meta_desk.py"),
    dict(name="allocation",
          python=r"C:\Users\dell\quant-platform\.venv\Scripts\python.exe",
          args=["-u", "-W", "ignore", "research/allocation.py"],
          marker="reports/DONE_allocation", match="allocation.py"),
]


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


CHILD_LOGS = CHILD_LOGS  # resolved above (platform-aware)


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
        if now - float(state.get("last_verify", 0) or 0) > 3600:
            try:
                subprocess.run(
                    [str(Path(sys.executable)), "-u", "-W", "ignore",
                     "research/verify_universal_state.py"],
                    cwd=str(BASE), capture_output=True, text=True, timeout=240)
                state["last_verify"] = now
                try:
                    STATE.write_text(json.dumps(state), encoding="utf-8")
                except Exception:
                    pass
            except Exception as e:
                log(f"universal-state verify failed: {e!r}")
        for t in TARGETS:
            if (BASE / "data" / f"HOLD_{t['name']}").exists():
                continue
            if (BASE / "data" / "VPS_AUTHORITY").exists() \
                    and t["name"] in ("universal", "merge", "allocation"):
                continue
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
                CHILD_LOGS.mkdir(parents=True, exist_ok=True)
                sl = open(CHILD_LOGS / f"{t['name']}_super.log", "ab")
                py = sys.executable if os.name != "nt" else (t.get("python") or PYW)
                kwargs = {"stdout": sl, "stderr": subprocess.STDOUT}
                if os.name == "nt":
                    kwargs["creationflags"] = subprocess.DETACHED_PROCESS \
                        | subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    kwargs["start_new_session"] = True
                proc = subprocess.Popen([str(py)] + t["args"], cwd=str(BASE), **kwargs)
                state[t["name"]] = {"last_spawn": now, "pid": proc.pid}
                STATE.write_text(json.dumps(state), encoding="utf-8")
                log(f"supervisor: respawned {t['name']} pid={proc.pid}")
            except Exception as e:
                log(f"supervisor: FAILED to spawn {t['name']}: {e!r}")
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
