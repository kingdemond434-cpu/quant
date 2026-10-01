#!/usr/bin/env python
"""THE CAPACITY RESTART: raise the commit ceiling and the chart depth, in one window.

The principal authorised two changes that both need a restart of the box that trades. This
encodes the preconditions, the ORDER, and the verification, because none of it should be done by
hand at six in the morning.

WHAT CHANGES, AND WHY EACH IS WORTH A RESTART.

(1) THE PAGE FILE. `GetPerformanceInfo` reports `CommitPeak == CommitLimit == 245.95 GB` exactly
    (96 GB RAM + a 150 GB system-managed page file). At the ceiling the first allocation to fail
    is a freshly spawned judge worker importing numpy, which breaks the pool and discards the
    whole pass: 77 BrokenProcessPool, 23 `OSError: handle is closed`, 17 MemoryError and 12
    `ImportError: DLL load failed ... the paging file is too small` -- 129 of 168 recorded pass
    deaths, 77%. `PagingFiles = "C:\\pagefile.sys 262144 393216"` takes CommitLimit to ~480 GB
    against 911 GB free on C:.

(2) MaxBars. `common.ini [Charts] MaxBars=100000` caps M1 at ~100,000 bars on 248 of 248
    symbols -- measured 101,169 to 104,465 on every frame sampled, never once at a venue end --
    while the terminal holds 22.46 GB of .hcc with minute history back to 2020 for 108 symbols.
    A fast M1 mechanism therefore gets ~91 trading days of evidence instead of the years that
    are already on disk.

WHY 2,000,000 AND NOT MORE, with the arithmetic, because "never Unlimited" needs a reason:

    MqlRates is 60 bytes a bar (time 8, OHLC 4x8, tick_volume 8, spread 4, real_volume 8).
    100,000 M1 bars  = 69 calendar days  ~= 91 trading days   (what the desk has today)
    2,000,000 M1 bars = 1,389 calendar days ~= 992 trading days (10.9x), which reaches the
    2020-onward minute history the 108 deepest symbols actually hold.

    Ceiling cost, if every chart that CAN reach the cap were hot at full depth at once:
        M1   248 symbols x 2,000,000 x 60 B = 29.8 GB
        M5   199 x ~508,000 (7y, under the cap) x 60 B =  6.1 GB
        M15  119 x ~169,000 x 60 B                     =  1.2 GB
        M30/H1/H4/D1: a few hundred MB between them
        -> ~37 GB ceiling, and only for charts actually touched.

    The depth lane's "1,736 hot charts at 1M bars is ~100 GB" over-counts twice: only M1 has
    enough history to reach a seven-figure cap on most symbols, and 1,736 charts are never hot
    together. 37 GB sits inside 96 GB of RAM beside the judge's 15-worker pool (~30 GB), and
    well inside the new 480 GB commit limit. Unlimited is refused on purpose: it would let one
    symbol's M1 take unbounded commit and put the judge back at the ceiling this restart exists
    to clear.

THE ORDER MATTERS AND IS THE POINT. MetaTrader READS common.ini at startup and REWRITES it at
shutdown, so an edit made while the terminal is up is discarded when it next closes. The terminal
is therefore stopped FIRST, the file is edited SECOND, and the box is restarted THIRD -- so
nothing rewrites the value between the edit and the read. common.ini is UTF-16LE with a BOM and
is rewritten as UTF-16LE; writing UTF-8 would make the terminal ignore the whole file.

    python scripts/restart_for_capacity.py                 # preconditions only, changes nothing
    python scripts/restart_for_capacity.py --stage         # page file + MaxBars, NO restart
    python scripts/restart_for_capacity.py --stage --restart
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

#: The repo this file sits in (C:\opt\quant on the trading box), never a hard-coded copy of it.
ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "CAPACITY_RESTART.json"
COMMON_INI = Path(r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal"
                  r"\930119AA53207C8778B41171FBFFB46F\config\common.ini")

PAGEFILE_VALUE = r"C:\pagefile.sys 262144 393216"
MAXBARS = 2_000_000
MEM_MM = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"

#: Windows whose chance must have passed before anything restarts the box. The desk had not
#: placed since 05:56Z the previous day; taking its window away to save a reboot is the wrong
#: trade in every direction.
WINDOWS_UTC = ((4, "gold_asia"), (5, "family lane"))
#: The commit freeze. The restart sits after it by construction.
FREEZE_END_H = 6


def _read(path: Path):
    return json.loads(path.read_text("utf-8"))


def preconditions(now: datetime | None = None) -> dict:
    """All three, measured. Any failure REFUSES the restart -- the note is never trusted."""
    now = now or datetime.now(UTC)
    checks: list[dict] = []

    # (1) the windows have had their chance, and we are past the freeze
    passed = [n for h, n in WINDOWS_UTC if now.hour >= h or now.hour < 3]
    windows_done = all(now.hour > h for h, _n in WINDOWS_UTC) and now.hour >= FREEZE_END_H
    checks.append({
        "check": "windows_had_their_chance",
        "ok": bool(windows_done),
        "detail": (f"now {now.strftime('%H:%MZ')}; gold_asia 04:00Z and family 05:00Z must both "
                   f"be past and the freeze ends {FREEZE_END_H:02d}:00Z"),
        "passed_windows": passed,
    })

    # (2) E8 flat -- positions, never the guard
    try:
        eg = _read(DESK / "reports" / "E8_GOLD.json")
        wins = (eg.get("state") or {}).get("windows") or {}
        open_ids = [w for w, v in wins.items() if isinstance(v, dict) and v.get("position_id")]
        checks.append({"check": "e8_flat", "ok": not open_ids,
                       "detail": f"windows carrying a position_id: {open_ids or 'none'}; "
                                 f"guard={eg.get('guard')!r} (guard is NOT flatness)",
                       "state_date": (eg.get("state") or {}).get("date")})
    except (OSError, ValueError) as exc:
        checks.append({"check": "e8_flat", "ok": False,
                       "detail": f"E8_GOLD.json unreadable ({exc}): UNMEASURED refuses"})

    # (3) MT5 flat AND the gateway permitted to take risk
    try:
        acc = _read(DESK / "data" / "account_state.json")
        n = int(acc.get("open_positions") or 0)
        checks.append({"check": "mt5_flat", "ok": n == 0,
                       "detail": f"open_positions={n}, equity={acc.get('equity')}"})
    except (OSError, ValueError) as exc:
        checks.append({"check": "mt5_flat", "ok": False,
                       "detail": f"account_state.json unreadable ({exc}): UNMEASURED refuses"})
    try:
        ri = _read(DESK / "data" / "release_identity.json")
        checks.append({"check": "allows_new_risk", "ok": bool(ri.get("allows_new_risk")),
                       "detail": f"verdict={ri.get('verdict')} age_h={ri.get('age_h')}; "
                                 f"{str(ri.get('reason'))[:160]}"})
    except (OSError, ValueError) as exc:
        checks.append({"check": "allows_new_risk", "ok": False,
                       "detail": f"release_identity.json unreadable ({exc}): UNMEASURED refuses"})

    return {"at": now.isoformat(timespec="seconds"), "checks": checks,
            "ok": all(c["ok"] for c in checks)}


def read_maxbars() -> tuple[int | None, str]:
    """MaxBars and the encoding, from the terminal's own file. UTF-16LE with a BOM."""
    raw = COMMON_INI.read_bytes()
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    txt = raw.decode(enc, errors="replace")
    m = re.search(r"MaxBars\s*=\s*(\d+)", txt)
    return (int(m.group(1)) if m else None), enc


def set_maxbars(value: int = MAXBARS) -> dict:
    """Rewrite MaxBars IN PLACE, preserving UTF-16LE. The caller must have stopped the terminal:
    MetaTrader rewrites this file at shutdown and would discard the edit."""
    raw = COMMON_INI.read_bytes()
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    txt = raw.decode(enc, errors="replace")
    before = re.search(r"MaxBars\s*=\s*(\d+)", txt)
    if not before:
        return {"ok": False, "why": "no MaxBars key in [Charts]; refusing to guess the layout"}
    new = re.sub(r"MaxBars\s*=\s*\d+", f"MaxBars={value}", txt, count=1)
    backup = COMMON_INI.with_name(COMMON_INI.name + f".bak.{int(time.time())}")
    backup.write_bytes(raw)
    COMMON_INI.write_bytes(new.encode(enc))
    after, _ = read_maxbars()
    return {"ok": after == value, "from": int(before.group(1)), "to": after,
            "encoding": enc, "backup": str(backup)}


def set_pagefile(value: str = PAGEFILE_VALUE) -> dict:
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MEM_MM, 0,
                        winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
        before, _t = winreg.QueryValueEx(k, "PagingFiles")
        winreg.SetValueEx(k, "PagingFiles", 0, winreg.REG_MULTI_SZ, [value])
        after, _t2 = winreg.QueryValueEx(k, "PagingFiles")
    return {"ok": list(after) == [value], "from": before, "to": after,
            "note": "applies at the next boot; nothing changes until the restart"}


def stop_terminal() -> dict:
    """Stop the gateway resident first (it would restart the terminal), then the terminal."""
    out = []
    try:
        import psutil
    except ImportError:
        return {"ok": False, "why": "psutil unavailable"}
    for match, label in (("gateway_resident.py", "gateway resident"),
                         ("terminal64.exe", "terminal")):
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(p.info["cmdline"] or [])
                hit = (match in cmd) or ((p.info["name"] or "").lower() == match)
            except Exception:
                continue
            if not hit:
                continue
            try:
                p.terminate()
                out.append({"label": label, "pid": p.info["pid"], "signal": "terminate"})
            except Exception as exc:
                out.append({"label": label, "pid": p.info["pid"], "error": repr(exc)[:80]})
        time.sleep(6)
    time.sleep(10)
    still = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info["cmdline"] or [])
            if "gateway_resident.py" in cmd or (p.info["name"] or "").lower() == "terminal64.exe":
                still.append(p.info["pid"])
        except Exception:
            continue
    return {"ok": not still, "stopped": out, "still_running": still}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--stage", action="store_true",
                    help="apply the page file and MaxBars (stops the terminal); no restart")
    ap.add_argument("--restart", action="store_true", help="restart the box after staging")
    ap.add_argument("--force", action="store_true",
                    help="stage even if a precondition fails (never used unattended)")
    a = ap.parse_args(argv)

    pre = preconditions()
    doc: dict = {"at": pre["at"], "preconditions": pre,
                 "maxbars_now": read_maxbars()[0], "target_maxbars": MAXBARS,
                 "pagefile_target": PAGEFILE_VALUE, "staged": False, "restarted": False}
    print(f"preconditions: {'ALL OK' if pre['ok'] else 'REFUSED'}")
    for c in pre["checks"]:
        print(f"  {'ok  ' if c['ok'] else 'FAIL'} {c['check']}: {c['detail']}")
    print(f"  MaxBars now: {doc['maxbars_now']} -> target {MAXBARS}")

    if a.stage and (pre["ok"] or a.force):
        doc["stop_terminal"] = stop_terminal()
        print(f"  terminal stopped: {doc['stop_terminal']['ok']} "
              f"{doc['stop_terminal'].get('still_running')}")
        if doc["stop_terminal"]["ok"]:
            doc["maxbars"] = set_maxbars()
            doc["pagefile"] = set_pagefile()
            doc["staged"] = bool(doc["maxbars"]["ok"] and doc["pagefile"]["ok"])
            print(f"  MaxBars: {doc['maxbars']}")
            print(f"  PagingFiles: {doc['pagefile']}")
        else:
            print("  REFUSING to edit common.ini while the terminal is up: it would be "
                  "overwritten at the next shutdown")
    elif a.stage:
        print("  REFUSING to stage: a precondition failed and --force was not given")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"  -> {OUT}")

    if a.restart and doc["staged"]:
        print("  restarting in 15s ...")
        time.sleep(15)
        subprocess.run(["shutdown", "/r", "/t", "5", "/c",
                        "capacity restart: page file + MaxBars"], check=False, timeout=120)
        doc["restarted"] = True
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    elif a.restart:
        print("  NOT restarting: staging did not complete")

    return 0 if (pre["ok"] or not a.stage) else 1


if __name__ == "__main__":
    sys.exit(main())
