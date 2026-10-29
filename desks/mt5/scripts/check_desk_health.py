"""Is the desk actually running? Asked on the box, answered in plain English.

WHY THIS EXISTS (2026-09-05). The desk produced nothing for days while every fence stayed
green, and each diagnosis had to be inferred from artifacts read on a machine that cannot reach
this one. Two of those inferences were wrong: an eleven-day-old `retcode 10027` was read as
"AutoTrading is off right now" when the principal had it switched on, and a gateway lock path
was called live when the box had already fixed it. The box knows all of this directly. Nobody
had written the questions down in a form it could be asked.

WHAT IT REPORTS, and nothing more:
  * the scheduled tasks that drive the desk -- present, enabled, when they last ran, what they
    returned;
  * whether the MT5 terminal and the gateway are actually resident;
  * how old the artifacts each leg is supposed to produce are;
  * whether `py -3` resolves, since a launcher pointing at a Python that does not exist on this
    machine is exactly the failure that started all of this.

ON A CLOCK, WITH AN ARTIFACT (2026-09-30). It used to print and nothing else, and nothing ran it:
a diagnostic only a person at the box ever saw. It now runs as the core-plan hourly leg
`desk_health` with `--out`, which also writes every finding as JSON to
desks/mt5/reports/DESK_HEALTH.json (published by sync_shadow_to_git.ps1), so a reader off the box
gets the same answer. Exit 0 always: it is a report, and every PROBLEM is in the document.

WHAT IT DOES NOT DO. It starts nothing, stops nothing, kills nothing, and writes nothing outside
its own report. It is safe to run while the desk is trading, which is the point: a diagnostic
you hesitate to run is a diagnostic you do not run.

STALE IS NOT DEAD, AND MISSING IS NOT ZERO. An artifact this cannot read is reported as
UNREADABLE, and a task Windows will not describe is reported UNKNOWN. Both are findings. The one
thing this must never do is print a reassuring line about something it could not actually check.

THE PUBLISHED REPORT CARRIES NO LOCAL PATH AND NO RAW EXCEPTION TEXT (BARS_STATE v2.2). It rides
the sync to the public repository. Every error finding says only the exception's type and errno
(`_exc_reason`); `desk_root` is published repo-relative; and `report()` passes every published
string through `_publishable`, which replaces the desk and repo roots and any remaining absolute
path (a drive letter, a UNC share, a POSIX root) with a placeholder -- because a finding also
quotes text other organs wrote (a sync refusal line, an alert line). The console output is local
and keeps the full paths.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent
OUT = DESK / "reports" / "DESK_HEALTH.json"

#: Every finding of this run, in order: (section, level, message). The JSON report is this list.
_FINDINGS: list[dict[str, str]] = []
_SECTION = [""]

#: task name -> what it drives, and how stale its evidence may be before it is a finding.
TASKS: tuple[tuple[str, str], ...] = (
    ("MT5-Gateway", "places and manages orders -- the money path"),
    ("MT5-Hourly", "the hourly chain: health, mining, sync"),
    ("MT5-Shadow", "forward evidence for candidate sleeves"),
    ("MT5-Gauntlet", "judges the docket and mints certificates"),
)

#: process -> why it matters. Matched on the command line, never killed.
PROCS: tuple[tuple[str, str], ...] = (
    ("terminal64", "the MT5 terminal itself"),
    # Either process IS the gateway pass: MT5-Gateway starts run_gateway_loop once a minute and
    # MT5-GatewayResident keeps gateway_resident running when the Interactive task cannot start
    # (Install-QuantWindows.ps1). Reading only the first called a healthy resident loop "NOT
    # running" (DESK_HEALTH 2026-10-12).
    ("run_gateway_loop|gateway_resident", "the gateway pass"),
    ("run_deadman_switch", "the Tier-3 protective rail"),
)

#: artifact -> (what produced it, hours after which it is a finding)
ARTIFACTS: tuple[tuple[str, str, float], ...] = (
    ("data/gateway_state.json", "the gateway, every pass", 1.0),
    ("data/hypotheses/edge_search_results.json", "the SEARCH leg", 3.0),
    ("data/hypotheses/orthogonal_candidates.json", "the SWEEP leg", 3.0),
    ("reports/UNIVERSAL_SURVIVORS.json", "the gauntlet's canon", 6.0),
    ("reports/pf_allocation.json", "the allocator", 0.5),
    # Whether the box's state reaches origin (verdict inside: FLOWING / STALLED), and the gate
    # verdict digest that rides the same publication -- both from the hourly publish_state leg.
    ("reports/BOX_STATE_FLOW.json", "publish_state's delivery meter", 2.0),
    ("reports/GATE_VERDICT_DIGEST.json", "publish_state's gate verdict digest", 2.0),
)


def _section(title: str) -> None:
    _SECTION[0] = title
    print(title)


def _exc_reason(exc: BaseException) -> str:
    """What a published finding may say about an error: its type and errno, never str(exc)."""
    errno = getattr(exc, "errno", None)
    return type(exc).__name__ + (f" errno={errno}" if isinstance(errno, int) else "")


#: Absolute paths that survive the root substitution: a drive letter (C:\ or C:/), a UNC or
#: doubled-backslash root, and a POSIX root: a `/` not preceded by a word character, a dot, a
#: colon, another slash or a placeholder's `>`. So `n/a`, `8/12`, a URL and a repo-relative
#: `data/x.json` are untouched.
_ABS_PATH = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s'\"<>|,;)]*"
    r"|\\\\[^\s'\"<>|,;)]+"
    r"|(?<![\w.:/~>-])/[^\s'\"<>|,;)]+")
PATH_PLACEHOLDER = "<path>"


def _publishable(text: str) -> str:
    """A string fit for the public repository: no desk/repo root, no absolute local path."""
    out = str(text)
    for root, tag in ((DESK, "<desk_root>"), (ROOT, "<repo>")):
        for form in {str(root), root.as_posix()}:
            if len(form) > 1:
                out = out.replace(form, tag)
    return _ABS_PATH.sub(PATH_PLACEHOLDER, out)


def _desk_root_published() -> str:
    try:
        return DESK.resolve().relative_to(ROOT.resolve()).as_posix()
    except (ValueError, OSError):
        return "<desk_root>"


def _note(level: str, msg: str) -> None:
    _FINDINGS.append({"section": _SECTION[0], "level": level, "message": msg})


def _ok(msg: str) -> None:
    _note("OK", msg)
    print(f"  [ OK ]      {msg}")


def _bad(msg: str) -> None:
    _note("PROBLEM", msg)
    print(f"  [PROBLEM]   {msg}")


def _unknown(msg: str) -> None:
    _note("UNKNOWN", msg)
    print(f"  [UNKNOWN]   {msg}")


def _run(args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 124, _exc_reason(exc)


def check_python() -> None:
    _section("PYTHON")
    print(f"  running as: {sys.executable}")
    rc, out = _run(["py", "-3", "-c", "import sys; print(sys.executable)"])
    if rc == 0 and out.strip():
        exe = out.strip().splitlines()[-1]
        print(f"  `py -3` -> {exe}")
        # The interpreter's location is a local path: the report names only the executable.
        name = re.split(r"[\\/]", exe)[-1]
        _ok(f"`py -3` resolves to {name}")
    else:
        _bad("`py -3` does NOT work on this machine. Every .cmd launcher uses it, so every "
             "scheduled task that runs one exits immediately, doing nothing, reporting success.")
    print()


#: 0 = success, 267009 = currently running, 267011 = has not run yet (ops/process_health.py).
_HEALTHY_CODES = frozenset({0, 267009, 267011})
#: 0x800710E0: the scheduler refused to start this trigger. schtasks prints it SIGNED
#: (-2147020576) and the cmdlets UNSIGNED (2147946720); both are this one code.
_REFUSED = 0x800710E0


def _result_code(raw: str) -> int | None:
    """One task result as ONE unsigned number, whichever tool printed it; None if unreadable."""
    text = str(raw or "").strip()
    try:
        code = int(text, 16) if text.lower().startswith("0x") else int(text)
    except ValueError:
        return None
    return code + 0x1_0000_0000 if code < 0 else code


def check_tasks() -> None:
    _section("SCHEDULED TASKS  (what drives the desk)")
    for name, what in TASKS:
        rc, out = _run(["schtasks", "/Query", "/TN", name, "/FO", "LIST", "/V"])
        if rc != 0:
            _bad(f"{name} is NOT INSTALLED on this machine -- {what}. Nothing runs it, so "
                 f"nothing it produces will ever appear.")
            continue
        fields = {}
        for line in out.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fields[k.strip().lower()] = v.strip()
        status = fields.get("scheduled task state", fields.get("status", "?"))
        state = fields.get("status", status)
        last_run = fields.get("last run time", "?")
        last_res = fields.get("last result", "?")
        code = _result_code(last_res)
        if status.lower() in {"disabled"}:
            _bad(f"{name} is INSTALLED BUT DISABLED -- {what}. Enable it in Task Scheduler.")
        elif state.lower() == "running" or code in _HEALTHY_CODES:
            _ok(f"{name}: {state}, last run {last_run}, result {last_res} -- {what}")
        elif code == _REFUSED:
            _bad(f"{name}: the trigger at {last_run} was REFUSED and nothing ran (0x800710E0) and "
                 f"no instance is running now -- either the task's Interactive principal had no "
                 f"desktop session, or the previous run was still going when the trigger fired "
                 f"(IgnoreNew) -- {what}")
        else:
            _bad(f"{name} last run {last_run} and returned {last_res} (non-zero = it failed) "
                 f"-- {what}")
    print()


def _process_blob() -> tuple[int, str]:
    """Every process name and command line. psutil first: CIM has HUNG on the trading box
    (CLAUDE.md), and this now runs on an hourly clock; PowerShell/CIM only when psutil is absent."""
    try:
        import psutil
    except ImportError:
        return _run(["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Process | ForEach-Object { $_.Name + ' ' + "
                     "$_.CommandLine }"], timeout=90)
    lines = []
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            lines.append(f"{p.info.get('name') or ''} {' '.join(p.info.get('cmdline') or [])}")
        except Exception:  # a process that vanished mid-walk is not a finding
            continue
    return 0, "\n".join(lines)


def check_processes() -> None:
    _section("RUNNING NOW")
    rc, out = _process_blob()
    if rc != 0:
        _unknown("could not read the process list, so nothing below is claimed either way")
        print()
        return
    blob = out.lower()
    for needle, what in PROCS:
        if any(n.lower() in blob for n in needle.split("|")):
            _ok(f"{what} is running ({needle})")
        else:
            _bad(f"{what} is NOT running ({needle} is absent from the process list)")
    print()


def check_artifacts() -> None:
    _section("WHAT THE DESK HAS ACTUALLY PRODUCED")
    now = time.time()
    for rel, producer, max_h in ARTIFACTS:
        p = DESK / rel
        if not p.exists():
            p = ROOT / rel
        if not p.exists():
            _bad(f"{rel} does not exist -- {producer} has never written it here")
            continue
        try:
            age_h = (now - p.stat().st_mtime) / 3600.0
        except OSError as exc:
            _unknown(f"{rel} could not be read ({_exc_reason(exc)}); UNREADABLE is not the same "
                     f"as absent")
            continue
        if age_h <= max_h:
            _ok(f"{rel} is {age_h:.1f}h old -- {producer}")
        else:
            _bad(f"{rel} is {age_h:.1f}h old (expected under {max_h:.0f}h) -- {producer} has "
                 f"stopped producing")
    print()


#: BARS_STATE.json (research/bars_state.py, core leg `bars_state`, run just before this one).
BARS_STATE = DESK / "data" / "BARS_STATE.json"
#: Hours after which the newest bar / newest tick on the box is a finding while the market is open,
#: and how old the report itself may be. The ages are the report's TRUE-UTC ages (converted through
#: the server anchor), never a broker stamp subtracted from UTC.
BAR_STALE_H = 2.0
TICK_STALE_H = 2.0
BARS_REPORT_STALE_H = 2.0
#: The FX weekend: server Saturday and Sunday, plus the first server hour of Monday. Bars and ticks
#: legitimately stop for ~48h; a Friday close read on Sunday is not a dead feed. Broker H1 stamps
#: run Fri 23:00 -> Mon 00:00 (49 broker hours), which is 48h of true UTC across the March US
#: change and 50h across the November one; 52h covers both plus the first Monday hour.
#: The allowance is granted ONLY on a POSITIVE reading of the weekend: when the market state is
#: unknown (no anchor), the weekday limit applies and a breach reads UNKNOWN, never OK (v2.1).
WEEKEND_STALE_H = 52.0



def _market_closed(now: datetime) -> bool | None:
    """Is the FX market in its weekend at `now` (server clock = New York + 7h)? None if unknown."""
    try:
        from zoneinfo import ZoneInfo
        if str(DESK) not in sys.path:
            sys.path.insert(0, str(DESK))
        from prop.e8_guard import SERVER_ANCHOR_TZ, SERVER_MIDNIGHT_ET_HOUR
        server = (now.astimezone(ZoneInfo(SERVER_ANCHOR_TZ))
                  + timedelta(hours=24 - int(SERVER_MIDNIGHT_ET_HOUR)))
    except Exception:
        return None
    return server.weekday() >= 5 or (server.weekday() == 0 and server.hour < 1)


def check_bars_state(path: Path | None = None, now: datetime | None = None) -> None:
    """THE BOX'S BAR AND TICK FEED, read from BARS_STATE.json: newest bar age, newest tick age."""
    _section("ARE THE BOX'S BARS AND TICKS FRESH  (data/BARS_STATE.json)")
    p = path or (DESK / "data" / BARS_STATE.name)
    now = now or datetime.now(UTC)
    try:
        doc = json.loads(p.read_text("utf-8"))
    except FileNotFoundError:
        _unknown("data/BARS_STATE.json is absent -- leg bars_state has not run here; bar and "
                 "tick freshness is UNMEASURED, not fine")
        print()
        return
    except (OSError, ValueError) as exc:
        _unknown(f"data/BARS_STATE.json unreadable ({_exc_reason(exc)})")
        print()
        return
    summary = doc.get("summary") if isinstance(doc, dict) else None
    if not isinstance(summary, dict):
        _unknown("BARS_STATE.json carries no summary -- freshness is UNMEASURED")
        print()
        return
    try:
        gen = datetime.fromisoformat(str(doc.get("generated_at")))
        rep_age = (now - gen).total_seconds() / 3600.0
    except (TypeError, ValueError):
        rep_age = None
    if rep_age is None:
        _unknown("BARS_STATE.json has no readable generated_at")
    elif rep_age > BARS_REPORT_STALE_H:
        _bad(f"BARS_STATE.json is {rep_age:.1f}h old (expected under {BARS_REPORT_STALE_H:.0f}h) "
             f"-- leg bars_state has stopped producing")
    closed = _market_closed(now)
    for what, key, mkey, verdict_key, limit in (
            ("bar", "newest_bar_age_h", "newest_bar_file_mtime_age_h", "bars_verdict",
             BAR_STALE_H),
            ("tick", "newest_tick_age_h", "newest_tick_file_mtime_age_h", "tape_verdict",
             TICK_STALE_H)):
        lim = WEEKEND_STALE_H if closed is True else limit
        age = summary.get(key)
        verdict = summary.get(verdict_key) or "UNMEASURED"
        when = summary.get(f"newest_{what}_time_utc")
        if not isinstance(age, (int, float)):
            mt = summary.get(mkey)
            extra = (f"; the youngest measured file was written {mt:.1f}h ago"
                     if isinstance(mt, (int, float)) else "")
            _unknown(f"newest {what} age is UNMEASURED ({verdict_key} {verdict}){extra}")
            continue
        line = (f"newest {what} {age:.1f}h old (UTC {when}; {verdict_key} {verdict}; limit "
                f"{lim:.0f}h{', market weekend' if closed else ''}"
                f"{', market state unknown' if closed is None else ''})")
        if age > lim and closed is None:
            _unknown(f"{line} -- over the weekday limit, and without the server anchor this "
                     f"cannot tell a weekend from a dead {what} feed")
        elif age > lim:
            _bad(f"{line} -- the box's {what} feed is STALE")
        elif verdict != "MEASURED":
            _unknown(f"{line}, but only part of the {what} store measured")
        else:
            _ok(line)
    print()


def check_state_flow() -> None:
    """A FRESH meter that says STALLED is still a stall: read its verdict, not only its age."""
    _section("IS THE BOX'S STATE REACHING ORIGIN")
    p = DESK / "reports" / "BOX_STATE_FLOW.json"
    try:
        doc = json.loads(p.read_text("utf-8"))
    except FileNotFoundError:
        _unknown("reports/BOX_STATE_FLOW.json is absent -- delivery is UNMEASURED, not fine")
        print()
        return
    except (OSError, ValueError) as exc:
        _unknown(f"reports/BOX_STATE_FLOW.json unreadable ({_exc_reason(exc)})")
        print()
        return
    verdict = str(doc.get("verdict") or "UNMEASURED")
    line = f"{verdict}: {doc.get('why')}"
    if verdict == "FLOWING":
        _ok(line)
    elif verdict == "STALLED":
        _bad(f"{line} (unpushed local commits: {doc.get('local_commits_not_on_origin')}, "
             f"last sync refusal: {(doc.get('sync_log') or {}).get('last_refusal_line')})")
    else:
        _unknown(line)
    # A PAGE TO NO ONE IS THE SAME SILENCE: whether any alert channel is armed rides the meter.
    alerts = doc.get("alerts") if isinstance(doc.get("alerts"), dict) else None
    if alerts is None:
        _unknown("alert arming not recorded in BOX_STATE_FLOW.json -- whether a STALLED page "
                 "reaches anyone is UNMEASURED")
    elif alerts.get("line"):
        _bad(f"{alerts['line']} (configure data/secrets/alert_channels.json on this box)")
    else:
        kinds = ", ".join(alerts.get("kinds") or [])
        _ok(f"alerts armed: {alerts.get('armed')} channel(s) ({kinds})")
    print()


def check_stall_watch_alerts() -> None:
    """stall_watch.json's alerts_* keys (the ten-minute watcher's reading) had no reader."""
    _section("DOES A STALL PAGE ANYONE  (stall_watch.json, every ten minutes)")
    p = DESK / "data" / "stall_watch.json"
    try:
        doc = json.loads(p.read_text("utf-8-sig"))
    except FileNotFoundError:
        _unknown("data/stall_watch.json is absent -- MT5-StallWatch has not run here")
        print()
        return
    except (OSError, ValueError) as exc:
        _unknown(f"data/stall_watch.json unreadable ({_exc_reason(exc)})")
        print()
        return
    if not isinstance(doc, dict) or ("alerts_armed" not in doc and "alerts_line" not in doc):
        _unknown("stall_watch.json carries no alerts_* keys -- stall_watch.ps1 predates the "
                 "state flow watcher; arming is UNMEASURED")
    elif doc.get("alerts_line"):
        _bad(f"{doc['alerts_line']} (stall_watch {doc.get('checked_at')}, watcher verdict "
             f"{doc.get('state_flow_watch')})")
    else:
        _ok(f"alerts armed: {doc.get('alerts_armed')} channel(s) (stall_watch "
            f"{doc.get('checked_at')})")
    print()


#: libs.ops.alert_channels.DESK_ALERT_FRESH_H, read from the artifact when it states one
DESK_ALERT_FRESH_H = 25.0


def check_desk_alerts(path: Path | None = None, now: datetime | None = None) -> None:
    """DESK PAGES MUST REACH SOMETHING THAT ACTS (2026-10-29). A desk-audience page no longer
    rings the owner's phone; libs.ops.alert_channels.send_all records it in DESK_ALERTS.json
    instead, and every row seen inside the freshness window is a PROBLEM here -- the RED the
    threads read. A resolved condition removes its row; an abandoned one ages out."""
    _section("DESK ALERTS  (reports/DESK_ALERTS.json, written by every desk page)")
    p = path or DESK / "reports" / "DESK_ALERTS.json"
    try:
        doc = json.loads(p.read_text("utf-8-sig"))
    except FileNotFoundError:
        _ok("no desk alert recorded (DESK_ALERTS.json absent)")
        print()
        return
    except (OSError, ValueError) as exc:
        _unknown(f"reports/DESK_ALERTS.json unreadable ({_exc_reason(exc)})")
        print()
        return
    rows = doc.get("alerts") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        _unknown("DESK_ALERTS.json carries no alerts list -- desk alerts are UNMEASURED")
        print()
        return
    fresh_h = doc.get("fresh_h")
    hours = float(fresh_h) if isinstance(fresh_h, (int, float)) else DESK_ALERT_FRESH_H
    floor = (now or datetime.now(UTC)) - timedelta(hours=hours)
    fresh = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            seen = datetime.fromisoformat(str(r.get("last_seen")))
            if seen < floor:
                continue
        except (ValueError, TypeError):
            _unknown(f"desk alert {r.get('key')!r} has no readable last_seen")
            continue
        fresh += 1
        label = str(r.get("title") or f"title sha {r.get('title_sha') or '?'}")[:120]
        _bad(f"desk alert {r.get('key')}: {label} (source {r.get('source') or '?'}, first "
             f"{r.get('first_seen')}, last {r.get('last_seen')}) -- follow the key to its source")
    if not fresh:
        _ok(f"no desk alert seen in the last {hours:g}h ({len(rows)} older row(s))")
    print()


def check_gateway_state() -> None:
    _section("THE GATEWAY'S OWN LAST WORD")
    p = DESK / "data" / "gateway_state.json"
    if not p.exists():
        _bad("data/gateway_state.json is absent -- the gateway has never written state here")
        print()
        return
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        _unknown(f"gateway_state.json could not be parsed ({_exc_reason(exc)})")
        print()
        return
    rec = doc.get("last_reconcile")
    print(f"  last reconcile with the broker: {rec}")
    deployed = doc.get("deployed") or {}
    print(f"  sleeves deployed: {len(deployed)}"
          + ("" if deployed else "   <- nothing is deployed"))
    seen = []
    for key, br in (doc.get("brackets") or {}).items():
        for o in (br.get("orders") or []):
            code = o.get("retcode")
            if code is not None:
                seen.append((key, code, str(o.get("comment") or "")[:60]))
    if not seen:
        print("  no order results recorded -- the gateway has not attempted an order")
    for key, code, comment in seen[:6]:
        note = "  <- 10027 means the terminal's AutoTrading button was off AT THAT TIME" \
            if code == 10027 else ""
        print(f"  {key}: retcode {code} {comment}{note}")
    if seen:
        print("  NOTE: these are the LAST results recorded, not necessarily current. Read them")
        print("        together with the reconcile time above before concluding anything.")
    print()


def report(checked_at: str) -> dict[str, Any]:
    """The run's findings as a document; PROBLEM and UNKNOWN counted, never folded into OK."""
    counts = {lvl: sum(1 for f in _FINDINGS if f["level"] == lvl)
              for lvl in ("OK", "PROBLEM", "UNKNOWN")}
    verdict = ("PROBLEM" if counts["PROBLEM"] else "UNMEASURED" if counts["UNKNOWN"] or not
               _FINDINGS else "OK")
    findings = [{k: _publishable(v) for k, v in f.items()} for f in _FINDINGS]
    return {"schema": "desk_health/1", "checked_at": checked_at,
            "desk_root": _desk_root_published(),
            "verdict": verdict, "counts": counts, "findings": findings}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Is the desk actually running?")
    ap.add_argument("--out", nargs="?", const=str(OUT), default=None,
                    help=f"also write the findings as JSON (default path {OUT})")
    args = ap.parse_args(argv)
    _FINDINGS.clear()
    checked_at = datetime.now(UTC).isoformat(timespec="seconds")
    os.chdir(DESK)
    print(f"desk root: {DESK}")
    print(f"checked  : {time.strftime('%Y-%m-%d %H:%M:%S')} local\n")
    check_python()
    check_tasks()
    check_processes()
    check_artifacts()
    check_bars_state()
    check_state_flow()
    check_stall_watch_alerts()
    check_desk_alerts()
    check_gateway_state()
    print("Every [PROBLEM] line above is a thing to fix. [UNKNOWN] means this could not check,")
    print("which is a finding too -- it is never the same as OK.")
    if args.out:
        out = Path(args.out)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report(checked_at), indent=2), "utf-8")
            print(f"report: {out}")
        except OSError as exc:
            print(f"report NOT written ({_exc_reason(exc)})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
