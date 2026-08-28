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
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
# BASE ON THE PATH, AT MODULE LEVEL. `record_tape()` runs BEFORE `daily()`, and `daily_cycle` is
# the module that happened to insert BASE -- so every hourly run reached `from mt5desk import
# tape` with BASE still absent and died on ModuleNotFoundError. MEASURED 2026-08-27: 66
# consecutive "tick tape FAILED" lines since the log was created on 08-22, i.e. five days of
# broker-native ticks never recorded. That tape is the desk's own moat data and it CANNOT be
# backfilled -- a tick nobody recorded is gone, unlike a bar you can re-download. Depending on
# another module's import side effect for your own path is the bug; this makes it explicit.
for _p in (str(BASE), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# THE INTERPRETER THAT IS ACTUALLY RUNNING, never a path typed once and left behind. These were
# hardcoded to C:\Users\dell\...\Python312, which is the OLD box: this desk runs as
# Administrator on Python314, so the path did not exist and `start()` could never launch
# anything. Verified 2026-08-28 -- dell pythonw.exe: False, Administrator pythonw.exe: True.
# The failure was perfectly silent. `health()` read a hunt as dead, called `start()`,
# Start-Process failed against a nonexistent binary in a detached hidden window, and the cycle
# recorded "restarted": True. So the one repair this cycle performs has never once worked here,
# and it reported success every time.
# Deriving from sys.executable means a box move, a Python upgrade or a different user cannot
# break it again -- the interpreter running this file is by definition the one that exists.
PYE = sys.executable or "python.exe"
_pyw = Path(PYE).with_name("pythonw.exe")
PY = str(_pyw) if _pyw.exists() else PYE

EXPECTED = {
    "hunt12": ("pythonw.exe", "run_hunt12.py"),
    "hunt16": ("pythonw.exe", "run_hunt16.py"),
}


def procs() -> str | None:
    """The running python command lines, or None when they COULD NOT BE READ.

    None is not an empty list, and the difference decides whether this cycle launches processes.
    Measured 2026-08-28: on a loaded box the PowerShell CIM query exceeded 60 seconds, the
    TimeoutExpired propagated, and the ENTIRE hourly cycle died -- a health check killing the
    thing it was checking, and doing it precisely when the box was busy, which is exactly when
    the cycle matters most. MT5-Hourly had failed twice in a row on this before the stall
    watchdog surfaced it.

    Returning "" instead would be worse than crashing: every `script in blob` test would read
    False, `health()` would conclude both hunts were dead, and it would launch duplicates onto
    the box that was already too loaded to answer the query. Absence never resolves to a clean
    verdict (L1.28a) -- and here the wrong verdict is actively harmful.
    """
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" "
             "| ForEach-Object { $_.CommandLine }"],
            capture_output=True, text=True, timeout=180)
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"  procs(): UNMEASURED ({type(exc).__name__}) -- launching nothing this pass")
        return None
    return (out.stdout or "") + (out.stderr or "")


def start(script: str) -> None:
    subprocess.Popen(
        ["powershell", "-NoProfile", "-Command",
         f"Start-Process -FilePath '{PY}' -ArgumentList "
         f"'-u','-W','ignore','research\\{script}' -WorkingDirectory "
         f"'{BASE}' -WindowStyle Hidden"],
        creationflags=0x08000000)


def _cmd_lines() -> str | None:
    """cmd.exe command lines, or None when unreadable. Same rule as procs()."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='cmd.exe'\" "
             "| ForEach-Object { $_.CommandLine }"],
            capture_output=True, text=True, timeout=180)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return out.stdout or ""


def health() -> dict:
    blob = procs()
    res: dict = {}
    if blob is None:
        # UNMEASURED, so nothing is declared dead and nothing is launched. A pass that cannot
        # see the process table has no business starting processes.
        for name in EXPECTED:
            res[name] = {"alive": None, "note": "process table unreadable; no launch attempted"}
        res["gateway_cmd"] = {"alive": None, "note": "process table unreadable"}
        return res
    for name, (_, script) in EXPECTED.items():
        alive = script in blob
        res[name] = {"alive": alive}
        if not alive:
            start(script)
            res[name]["restarted"] = True
    # `str.find` RETURNS -1 WHEN NOT FOUND, AND bool(-1) IS TRUE -- so this read "alive" exactly
    # when MT5Gateway.cmd was absent, and False only in the one case where it sat at position 0.
    # An inverted health check is worse than none: it reports green for the failure it exists to
    # catch. Membership testing says what was meant.
    cmds = _cmd_lines()
    if "MT5Gateway.cmd" in blob:
        res["gateway_cmd"] = {"alive": True}
    elif cmds is None:
        res["gateway_cmd"] = {"alive": None, "note": "cmd table unreadable"}
    else:
        res["gateway_cmd"] = {"alive": "MT5Gateway" in cmds}
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
