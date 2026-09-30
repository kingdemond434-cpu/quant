#!/usr/bin/env python3
"""The trading box's own outside alarm: ping an external dead-man every 5 minutes, and fail it
loudly when an organ on the box has gone quiet.

    python desks/mt5/scripts/box_heartbeat.py            # MT5-BoxHeartbeat, every 5 minutes
    python desks/mt5/scripts/box_heartbeat.py --dry-run  # measure and report, ping nothing

WHY (infra survey, 2026-09-30). The VPS pings healthchecks.io at the end of every
`scripts/run_alerts.py` pass, so a dead VPS pages someone. The box that holds the live terminal
had no such ping: `stall_watch.ps1` writes `stall_watch.json` and pages nobody, and
`desk_staleness` disarms the gateway after DAYS of research silence but tells no human in the
meantime. A box that loses power, network or its scheduler was therefore discovered by whoever
next looked. The external check inverts that: healthchecks.io pages when the pings STOP, which
is the only alarm that still works when the machine that would raise it is gone.

WHAT IT CHECKS, on hour scales (the disarm rule works in days; this is its early warning):

    research   newest `desk_staleness.HEARTBEATS` write older than RESEARCH_MAX_H
    gateway    `reports/DESK_STALE.json` (written every gateway pass) older than GATEWAY_MAX_MIN
               while the FX market is open -- a closed market legitimately stops the pass
    watchdog   `data/stall_watch.json` older than WATCHDOG_MAX_MIN
    disk       free space on the repo's drive under DISK_MIN_GB
    silent     `reports/SILENT_ORGANS.json` fence RED (a NEW silent organ or an escalation) or
               UNMEASURED (an input unreadable, stale or existence-only), or the census older
               than SILENT_MAX_MIN -- audit R2, 2026-09-30: the fence paged nobody before this

All healthy: GET the ping URL. Anything failing: POST `<url>/fail` with the failing checks, and
whenever a check JOINS the failing set (or the silent fence names a new organ), one page through `libs.ops.alert_channels.send_all` (whatever is
armed there; unarmed is recorded, never silent). A failing check does not stop the ping: `/fail`
is itself a ping, so "the box is alive and something on it is wrong" and "the box is gone" stay
two different pages.

CREDENTIAL. The check's ping URL, in `data/secrets/box_heartbeat_url.json` (`{"url":
"https://hc-ping.com/<uuid>"}`), a SEPARATE check from the VPS's `heartbeat_url.json` so the two
machines never answer for each other. Absent: status NOT_ARMED in the report, exit 0, nothing
pinged -- a missing credential is a recorded state, never a crash and never a claimed pass. The
URL is never printed or written to the report.

Writes `desks/mt5/reports/BOX_HEARTBEAT.json` (a state path; the box may write it).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SECRETS = (ROOT / "data" / "secrets" / "box_heartbeat_url.json",
           BASE / "data" / "secrets" / "box_heartbeat_url.json")
OUT = BASE / "reports" / "BOX_HEARTBEAT.json"
GATEWAY_BEAT = BASE / "reports" / "DESK_STALE.json"
WATCHDOG_BEAT = BASE / "data" / "stall_watch.json"
SILENT_ORGANS = BASE / "reports" / "SILENT_ORGANS.json"
#: The census is an hourly leg plus an issue-board clock; three hours is two missed passes.
SILENT_MAX_MIN = 180.0
RESEARCH_MAX_H = 6.0
GATEWAY_MAX_MIN = 30.0
WATCHDOG_MAX_MIN = 30.0
DISK_MIN_GB = 5.0
TIMEOUT_S = 10.0


def fx_open(now: datetime) -> bool:
    """The FX week: Sunday 22:00 UTC to Friday 21:00 UTC (the conservative ends of both DST
    phases, so a closed hour is never read as open)."""
    wd, h = now.weekday(), now.hour + now.minute / 60.0
    if wd == 5:
        return False
    if wd == 6:
        return h >= 22.0
    if wd == 4:
        return h < 21.0
    return True


def _age_min(p: Path, now: float) -> float | None:
    try:
        return (now - p.stat().st_mtime) / 60.0
    except OSError:
        return None


def measure(now: float | None = None, *, research: dict[str, Any] | None = None,
            disk_free_gb: float | None = None) -> dict[str, Any]:
    """Every check's reading and whether it fails. A beat that does not exist FAILS: absence is
    not health (L1.28a)."""
    t = now if now is not None else time.time()
    dt = datetime.fromtimestamp(t, tz=UTC)
    if research is None:
        try:
            from mt5desk import desk_staleness as ds
            research = ds.staleness(now=t)
        except Exception as exc:        # an unreadable clock is a failing check, never a pass
            research = {"age_days": None, "why": f"unreadable: {type(exc).__name__}"}
    checks: dict[str, dict[str, Any]] = {}
    r_age = research.get("age_days")
    checks["research"] = {"age_h": None if r_age is None else round(float(r_age) * 24, 2),
                          "max_h": RESEARCH_MAX_H,
                          "fail": r_age is None or float(r_age) * 24 > RESEARCH_MAX_H}
    g = _age_min(GATEWAY_BEAT, t)
    is_open = fx_open(dt)
    checks["gateway"] = {"age_min": None if g is None else round(g, 1), "max_min": GATEWAY_MAX_MIN,
                         "market_open": is_open,
                         "fail": is_open and (g is None or g > GATEWAY_MAX_MIN)}
    w = _age_min(WATCHDOG_BEAT, t)
    checks["watchdog"] = {"age_min": None if w is None else round(w, 1),
                          "max_min": WATCHDOG_MAX_MIN, "fail": w is None or w > WATCHDOG_MAX_MIN}
    if disk_free_gb is None:
        try:
            disk_free_gb = shutil.disk_usage(ROOT).free / 1024 ** 3
        except OSError:
            disk_free_gb = None
    checks["disk"] = {"free_gb": None if disk_free_gb is None else round(disk_free_gb, 2),
                      "min_gb": DISK_MIN_GB,
                      "fail": disk_free_gb is None or disk_free_gb < DISK_MIN_GB}
    checks["silent"] = silent_check(t)
    failing = sorted(k for k, v in checks.items() if v["fail"])
    return {"at": dt.isoformat(timespec="seconds"), "checks": checks, "failing": failing,
            "verdict": "FAIL" if failing else "OK"}


def silent_check(now: float, path: Path | None = None) -> dict[str, Any]:
    """The silent-organ fence as a heartbeat check. RED and UNMEASURED fail; so does a census
    that is missing or older than SILENT_MAX_MIN (a fence that stopped is not a GREEN one)."""
    p = path or SILENT_ORGANS
    age = _age_min(p, now)
    doc: Any = None
    with contextlib.suppress(OSError, ValueError):
        doc = json.loads(p.read_text("utf-8"))
    fence = str(doc.get("fence") or doc.get("status") or "") if isinstance(doc, dict) else ""
    new = sorted(str(n) for n in (doc.get("new_silent") or [])) if isinstance(doc, dict) else []
    return {"fence": fence or None, "age_min": None if age is None else round(age, 1),
            "max_min": SILENT_MAX_MIN, "new_silent": new[:12],
            "fail": (age is None or age > SILENT_MAX_MIN or not fence
                     or fence in ("RED", "UNMEASURED"))}


def _url(paths: tuple[Path, ...] = SECRETS) -> str:
    for p in paths:
        with contextlib.suppress(OSError, ValueError, AttributeError):
            u = str(json.loads(p.read_text("utf-8")).get("url") or "").strip()
            if u.startswith("https://"):
                return u
    return ""


def _ping(url: str, body: str, fail: bool) -> str:
    endpoint = url.rstrip("/") + ("/fail" if fail else "")
    req = urllib.request.Request(endpoint, data=body.encode("utf-8", "ignore")[:9000])
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return f"http {r.status}"


def run(*, dry_run: bool = False, out: Path = OUT, secrets: tuple[Path, ...] = SECRETS,
        reading: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = reading or measure()
    prev: dict[str, Any] = {}
    with contextlib.suppress(OSError, ValueError):
        prev = json.loads(out.read_text("utf-8"))
    body = (f"box {doc['verdict']}: " + (", ".join(
        f"{k} {json.dumps({a: b for a, b in doc['checks'][k].items() if a != 'fail'})}"
        for k in doc["failing"]) or "all organs fresh"))
    url = _url(secrets)
    if not url:
        doc["ping"] = {"status": "NOT_ARMED",
                       "why": "no data/secrets/box_heartbeat_url.json; nothing outside the box "
                              "will notice if it dies"}
    elif dry_run:
        doc["ping"] = {"status": "DRY_RUN"}
    else:
        try:
            doc["ping"] = {"status": "SENT", "detail": _ping(url, body, bool(doc["failing"]))}
        except Exception as exc:
            doc["ping"] = {"status": "ERROR", "detail": type(exc).__name__}
    # PAGE ON EVERY NEW FAILURE, not only on the first (audit R2): a box already failing `disk`
    # must still page when the silent fence turns RED, and a RED fence naming a NEW organ pages
    # again even though the `silent` check was already failing.
    prev_failing = set(prev.get("failing") or []) if prev.get("verdict") == "FAIL" else set()
    prev_new = set(((prev.get("checks") or {}).get("silent") or {}).get("new_silent") or [])
    now_new = set((doc["checks"].get("silent") or {}).get("new_silent") or [])
    newly = doc["verdict"] == "FAIL" and (bool(set(doc["failing"]) - prev_failing)
                                          or ("silent" in doc["failing"]
                                              and bool(now_new - prev_new)))
    doc["paged"] = None
    if newly and not dry_run:
        try:
            from libs.ops.alert_channels import send_all
            res = send_all("MT5 box unhealthy", body)
            doc["paged"] = {k: v for k, v in res.items() if k in ("armed", "delivered", "status")}
        except Exception as exc:
            doc["paged"] = {"status": "ERROR", "detail": type(exc).__name__}
    doc["since"] = (prev.get("since") if doc["verdict"] == prev.get("verdict") and prev.get("since")
                    else doc["at"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run)
    print(json.dumps({"verdict": doc["verdict"], "failing": doc["failing"],
                      "ping": doc["ping"]["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
