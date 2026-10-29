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

All healthy: GET the ping URL. Anything failing: the box is still alive, so it still sends the
success ping, and POSTs the failing checks to `<url>/log` (recorded on the check, notifies nobody)
because every check here is DESK -- box health is a RED the threads fix (2026-10-29). Only a
check in PRINCIPAL_CHECKS (none today) would POST `<url>/fail`. On the TRANSITION into failing,
one desk page through `libs.ops.alert_channels.send_all` (ledger, hc /log, and a row in
DESK_ALERTS.json; cleared on recovery). "The box is gone" is unchanged: the pings stop and
healthchecks.io pages, which is the one alarm that needs nothing on the box.

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
RESEARCH_MAX_H = 6.0
GATEWAY_MAX_MIN = 30.0
#: MT5-StallWatch (stall_watch.ps1) fires every 30 min (:20 and :50) and writes stall_watch.json
#: at the END of its run, which takes 1-28 min under normal box load. So the file's age just
#: before a healthy write can reach cadence + the previous run's length, and a limit EQUAL to the
#: cadence tripped on any run a few seconds slower than the one before (15 false pages in 24h,
#: measured 2026-10-29: "watchdog age_min 30.7 > 30"). Limit = cadence (the next fire) + one
#: worst-case normal run (bounded by the cadence itself, since a run past it overlaps the next
#: fire) + 5 min margin = 2 x 30 + 5 = 65 min. A watchdog really gone quiet still fails inside
#: ~2 missed fires.
#:
#: THE CADENCE IS THE MEASURED TRIGGER, NOT THE MANIFEST'S. desks/mt5/ops/box_tasks.manifest
#: lists MT5-StallWatch as "every 10 minutes"; the box's own task fires at :20 and :50 (30 min,
#: measured 2026-10-29 from stall_watch.json mtimes). The larger of the two is the safe one for an
#: age limit, and tests/ops/test_alert_audience.py pins WATCHDOG_MAX_MIN >= 2 x the manifest
#: cadence + 5, so the manifest can never be raised past this limit unnoticed.
STALL_WATCH_TRIGGER_MINUTES = (20, 50)        # past the hour, as the box's task fires
WATCHDOG_CADENCE_MIN = 60.0 / len(STALL_WATCH_TRIGGER_MINUTES)
WATCHDOG_MARGIN_MIN = 5.0
WATCHDOG_MAX_MIN = 2 * WATCHDOG_CADENCE_MIN + WATCHDOG_MARGIN_MIN
#: Checks whose failure needs the owner's own hands (hc /fail). Box health never does.
PRINCIPAL_CHECKS: frozenset[str] = frozenset()
#: the desk alert row this heartbeat owns in DESK_ALERTS.json
DESK_ALERT_KEY = "box_heartbeat:unhealthy"
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
    failing = sorted(k for k, v in checks.items() if v["fail"])
    return {"at": dt.isoformat(timespec="seconds"), "checks": checks, "failing": failing,
            "verdict": "FAIL" if failing else "OK"}


def page_title(failing: list[str]) -> str:
    """The transition page's title: which checks failed, e.g. `MT5 box unhealthy: disk, gateway`."""
    return "MT5 box unhealthy" + (f": {', '.join(failing)}" if failing else "")


def _url(paths: tuple[Path, ...] = SECRETS) -> str:
    for p in paths:
        with contextlib.suppress(OSError, ValueError, AttributeError):
            u = str(json.loads(p.read_text("utf-8")).get("url") or "").strip()
            if u.startswith("https://"):
                return u
    return ""


def _ping(url: str, body: str, fail: bool, *, audience: str = "desk") -> str:
    """fail + principal: POST /fail (notifies). Otherwise the success ping -- the box IS alive --
    and, when something desk-level is failing, the detail on /log (recorded, notifies nobody)."""
    data = body.encode("utf-8", "ignore")[:9000]
    base = url.rstrip("/")
    if fail and audience == "principal":
        with urllib.request.urlopen(urllib.request.Request(base + "/fail", data=data),
                                    timeout=TIMEOUT_S) as r:
            return f"http {r.status} fail"
    with urllib.request.urlopen(urllib.request.Request(base, data=data), timeout=TIMEOUT_S) as r:
        detail = f"http {r.status}"
    if fail:
        try:                                    # the liveness ping above already landed
            with urllib.request.urlopen(urllib.request.Request(base + "/log", data=data),
                                        timeout=TIMEOUT_S) as r:
                detail += f"; log http {r.status}"
        except Exception as exc:
            detail += f"; log {type(exc).__name__}"
    return detail


def run(*, dry_run: bool = False, out: Path = OUT, secrets: tuple[Path, ...] = SECRETS,
        reading: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = reading or measure()
    prev: dict[str, Any] = {}
    with contextlib.suppress(OSError, ValueError):
        prev = json.loads(out.read_text("utf-8"))
    # A CRASHING JUDGE STALL PAGER IS A FAILING CHECK (audit of e759c01f6). `main` records the
    # pager's exit in this file after each run; a failed one fails the NEXT heartbeat, so the
    # healthchecks.io /fail route -- which needs no alert channel -- says so off the box.
    js = prev.get("judge_stall_pager") if isinstance(prev, dict) else None
    if isinstance(js, dict) and "ok" in js:
        doc.setdefault("checks", {})["judge_stall_pager"] = {
            "rc": js.get("rc"), "at": js.get("at"), "fail": not js.get("ok")}
        doc["failing"] = sorted(k for k, v in doc["checks"].items() if v.get("fail"))
        doc["verdict"] = "FAIL" if doc["failing"] else "OK"
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
            aud = ("principal" if set(doc["failing"]) & PRINCIPAL_CHECKS else "desk")
            doc["ping"] = {"status": "SENT",
                           "detail": _ping(url, body, bool(doc["failing"]), audience=aud)}
        except Exception as exc:
            doc["ping"] = {"status": "ERROR", "detail": type(exc).__name__}
    newly = doc["verdict"] == "FAIL" and prev.get("verdict") != "FAIL"
    doc["paged"] = None
    if newly and not dry_run:
        try:
            from libs.ops.alert_channels import send_all
            # DESK, every check including gateway and disk. The owner's words (2026-10-29): "only
            # notify me on things which need me or Else it's confusing handle rest n don't tell
            # me". Our reading of them, not his words: box health never needs him -- it is a RED
            # the threads fix. The title names the failing checks so the ledger, hc /log and the
            # DESK_ALERTS.json row say WHICH organ, not just "unhealthy".
            res = send_all(page_title(doc["failing"]), body, audience="desk",
                           key=DESK_ALERT_KEY, source="box_heartbeat")
            doc["paged"] = {k: v for k, v in res.items() if k in ("armed", "delivered", "status")}
        except Exception as exc:
            doc["paged"] = {"status": "ERROR", "detail": type(exc).__name__}
    if (doc["verdict"] == "OK" and prev.get("verdict") == "FAIL" and not dry_run):
        with contextlib.suppress(Exception):    # recovered: stop holding the desk RED
            from libs.ops.alert_channels import clear_desk_alert
            clear_desk_alert(DESK_ALERT_KEY)   # same (default) artifact send_all wrote
    doc["since"] = (prev.get("since") if doc["verdict"] == prev.get("verdict") and prev.get("since")
                    else doc["at"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1), "utf-8")
    return doc


#: THE JUDGE STALL PAGER RIDES THIS CLOCK (2026-10-21). A stalled judge is an organ gone quiet,
#: and this is the five-minute watchdog that already runs on the box, so `judge_stall_pager.py`
#: is invoked here rather than given a task of its own that would wait on a human to install it.
#: A bounded subprocess: its outcome is its own (JUDGE_STALL.json and its page state), and
#: nothing it does -- a hang, a crash, a pager failure -- can touch this heartbeat's ping,
#: verdict or exit code.
JUDGE_STALL = BASE / "scripts" / "judge_stall_pager.py"
#: Inside the task's 2-minute ExecutionTimeLimit, after this heartbeat has already pinged and
#: written its report.
JUDGE_STALL_TIMEOUT_S = 60.0


def _judge_stall(out: Path = OUT) -> dict[str, Any]:
    """Run the pager, bounded, and record its exit in this heartbeat's own report. Never raises.

    The rc is recorded rather than discarded (audit of e759c01f6): exit 0 is a pager that ran;
    anything else -- a send error, an unwritable state, a crash, the timeout -- is `ok: false`,
    and `run` turns it into a failing check on the next heartbeat."""
    import subprocess
    at = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        r = subprocess.run([sys.executable, "-W", "ignore", str(JUDGE_STALL)], cwd=str(ROOT),
                           capture_output=True, timeout=JUDGE_STALL_TIMEOUT_S, check=False)
        rec: dict[str, Any] = {"at": at, "rc": r.returncode, "ok": r.returncode == 0}
    except subprocess.TimeoutExpired:
        rec = {"at": at, "rc": "TIMEOUT", "ok": False}
    except Exception as exc:
        rec = {"at": at, "rc": f"ERROR {type(exc).__name__}", "ok": False}
    with contextlib.suppress(OSError, ValueError, TypeError):
        doc = json.loads(out.read_text("utf-8"))
        doc["judge_stall_pager"] = rec
        tmp = out.with_name(f"{out.name}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), "utf-8")
        tmp.replace(out)
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run)
    if not a.dry_run:
        _judge_stall()
    print(json.dumps({"verdict": doc["verdict"], "failing": doc["failing"],
                      "ping": doc["ping"]["status"]}))
    if not a.dry_run:
        print(json.dumps({"account_key_alerts": deliver_account_key_alerts()}))
    return 0


def deliver_account_key_alerts() -> dict[str, Any]:
    """Deliver the account-key alert outbox (v5f): the order path only enqueues, this 5-minute
    task delivers, so no page is ever sent between order_send and a bracket leg. NEVER RAISES."""
    try:
        from libs.ops import provenance
        res = provenance.deliver_pending()
        return {k: res.get(k) for k in ("rows", "sent", "ledger", "error")}
    except Exception as exc:
        return {"error": type(exc).__name__}


if __name__ == "__main__":
    raise SystemExit(main())
