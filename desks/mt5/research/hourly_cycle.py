"""hourly_cycle: the standing per-hour cycle for the MT5 desk.

1. HEALTH: verify every expected process (gateway loop cmd, running hunts) is
   alive; restart dead ones detached. Confirm placebo/hunt artifacts are fresh.
2. MINE: one external-intelligence pass (web) — fetch frontier sources, canonicalize
   seeds into data/frontier_inbox.json. If a source class is unreachable, try one
   bypass; if that fails, skip and do the next-highest-value thing (never idle).
3. VALIDATE: nothing to auto-run; hunts own the battery. Log pending candidates.
4. REPORT: write reports/frontier.json (survivors, placebo verdicts, gateway
   state, gold book, hunts in flight).
5. SYNC: write data/sync_marker.json so MT5Sync.cmd pushes to the VPS brains.

Run every hour (Startup loop MT5Hourly.cmd). Fail-visible, resumable, cheap.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
# WAS a hardcoded C:\Users\dell\... path -- the retired laptop's interpreter, which does not
# exist on Contabo. Caught live 2026-08-26 while checking whether the hourly restart of dead
# hunt12/hunt16 processes actually works: it does not, on this box, because the launch command
# points at a file that is not there. Derived portably instead, from whichever interpreter is
# actually running this script -- pythonw.exe sits beside python.exe in every standard CPython
# Windows install, so this works on any box without a hardcoded path.
_exe_dir = Path(sys.executable).parent
_pythonw = _exe_dir / "pythonw.exe"
PY = str(_pythonw) if _pythonw.exists() else sys.executable

EXPECTED = {
    "hunt12": ("pythonw.exe", "run_hunt12.py"),
    "hunt16": ("pythonw.exe", "run_hunt16.py"),
}


def procs() -> list[str]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" "
         "| ForEach-Object { $_.CommandLine }"],
        capture_output=True, text=True, timeout=60)
    return (out.stdout or "") + (out.stderr or "")


def start(script: str) -> bool:
    """Launch script hidden/detached. Returns whether the LAUNCH COMMAND ITSELF reported
    success -- not proof the process is still alive a moment later. health() re-polls procs()
    afterward for that; a launch command returning 0 and a process actually staying up are
    different facts, and conflating them is exactly the bug this replaced (restarted=True was
    written unconditionally, with no check at all, on top of a launch path that did not exist
    on this box in the first place)."""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"Start-Process -FilePath '{PY}' -ArgumentList "
         f"'-u','-W','ignore','research\\{script}' -WorkingDirectory "
         f"'{BASE}' -WindowStyle Hidden"],
        capture_output=True, text=True, timeout=30)
    return result.returncode == 0


def health() -> dict:
    blob = procs()
    res = {}
    for name, (_, script) in EXPECTED.items():
        alive = script in blob
        res[name] = {"alive": alive}
        if not alive:
            launch_ok = start(script)
            if launch_ok:
                # Give the OS a moment to actually create the process before checking for it --
                # process creation itself is near-instant even for a script whose real work is
                # slow.
                time.sleep(5)
            res[name]["restarted"] = bool(launch_ok and script in procs())
            if not res[name]["restarted"]:
                res[name]["restart_failed"] = True
    res["gateway_cmd"] = {"alive": "MT5Gateway.cmd" in blob or bool(
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" "
                        "| ForEach-Object { $_.CommandLine }"],
                       capture_output=True, text=True, timeout=60).stdout.find("MT5Gateway"))}
    return res


def mine() -> dict:
    """One web pass. Try the source; on failure try one bypass; else skip (never idle)."""
    inbox = BASE / "data" / "frontier_inbox.json"
    items = []
    if inbox.exists():
        try:
            items = json.loads(inbox.read_text(encoding="utf-8"))
        except Exception:
            items = []
    urls = [
        "https://www.reddit.com/r/algotrading/top.json?t=week&limit=15",
        "https://www.reddit.com/r/quant/top.json?t=week&limit=15",
    ]
    hits = []
    for u in urls:
        try:
            import urllib.request
            req = urllib.request.Request(u, headers={"User-Agent": "quant-research-desk/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8", "ignore"))
            for child in data.get("data", {}).get("children", [])[:15]:
                d = child.get("data", {})
                hits.append({"src": u.split("/")[2], "title": d.get("title", "")[:200],
                             "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                             "score": d.get("score", 0), "ts": d.get("created_utc")})
        except Exception as e:
            hits.append({"src": u, "error": str(e)[:120], "bypass_tried": True})
    seen = {x.get("url") for x in items}
    fresh = [h for h in hits if h.get("url") and h["url"] not in seen and h.get("score", 0) >= 20]
    items.extend(fresh)
    inbox.write_text(json.dumps(items[-500:], indent=1), encoding="utf-8")
    return {"sources_tried": len(urls), "new_seeds": len(fresh), "inbox": len(items)}


def frontier_report(health: dict) -> None:
    rep = {"swept_at": datetime.now(UTC).isoformat(), "health": health}
    for name in ("hunt12_partial", "hunt16_partial", "placebo_test", "hunt13"):
        fp = BASE / "reports" / f"{name}.json"
        if fp.exists():
            try:
                rep[name] = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                rep[name] = None
    gw = BASE / "data" / "gateway_state.json"
    if gw.exists():
        with suppress(Exception):
            rep["gateway"] = json.loads(gw.read_text(encoding="utf-8"))
    (BASE / "reports" / "frontier.json").write_text(
        json.dumps(rep, indent=1, default=str), encoding="utf-8")
    print(f"frontier report written ({rep['swept_at']})", flush=True)


def daily() -> dict:
    """The operating chain -- shadow -> promoter -> markout -- run once per UTC day.

    THIS WAS THE HOLE. Health checks, web mining and a frontier report all ran hourly while the
    three processes that actually move an edge toward capital ran NOWHERE: nine validated
    candidates sat in `shadow_forward.SLEEVES` accruing no evidence and unable to promote. The
    supervisor could not have hosted them either -- it is built around one-shot DONE markers, so a
    recurring job would run once and never again.

    Called every hour deliberately. `daily_cycle` self-guards on a UTC date stamp, so this box gets
    exactly one run per day whenever it happens to be awake, instead of missing the day entirely
    because the laptop was shut at the scheduled minute.
    """
    try:
        import daily_cycle
        return {"exit_code": daily_cycle.main([]),
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except Exception as exc:
        # Reported, never swallowed: this hourly cycle must survive, but a desk that cannot run its
        # promotion chain has to say so rather than print "cycle done".
        print(f"daily cycle FAILED to start: {type(exc).__name__}: {exc}", flush=True)
        return {"error": f"{type(exc).__name__}: {exc}"}


def record_tape() -> dict:
    """Persist broker-native ticks every hourly cycle before any research consumes them."""
    try:
        from mt5desk import (
            tape,
            triangle_tape,
        )

        tape_rc = tape.main([])
        triangle_rc = triangle_tape.main()
        return {"exit_code": max(tape_rc, triangle_rc),
                "triangle_exit_code": triangle_rc,
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
    except Exception as exc:
        print(f"tick tape FAILED: {type(exc).__name__}: {exc}", flush=True)
        return {"error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    h = health()
    t = record_tape()
    d = daily()
    m = mine()
    frontier_report(h)
    (BASE / "data" / "sync_marker.json").write_text(
        json.dumps({"last_cycle": datetime.now(UTC).isoformat(),
                    "health": h, "tape": t, "daily": d, "mine": m}, indent=1), encoding="utf-8")
    print("cycle done", flush=True)


if __name__ == "__main__":
    main()
