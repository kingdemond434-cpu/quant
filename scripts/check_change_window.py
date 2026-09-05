#!/usr/bin/env python3
"""STERILE COCKPIT (L1.38) -- the money path does not change during the windows where a change
cannot be validated before it matters.

CROSS-DOMAIN TRANSFER (capability-hunt lens 6, aviation safety). Airlines forbid non-essential
activity below 10,000 feet -- not because the crew is less capable then, but because THAT is when
an error has no time to be caught. This desk has the identical structure and no equivalent rule:
an autonomous box that ships ~10 commits/day into the same tree the executor runs from, with a
10-minute auto-deploy, and a launch window during which a money-path defect fires exactly once,
for real, on real capital.

READ THIS BEFORE ASSUMING IT IS TIMIDITY -- it is the opposite, and the distinction is precise:
  * It freezes ONLY the money path (executor, connectors, risk rails, sizing, capital events)
    and ONLY inside a declared window.
  * RESEARCH, MINING, DATA ACQUISITION, FENCES AND EXPLORATION ARE EXPLICITLY UNAFFECTED and keep
    running at full cadence -- L1.28b(f) makes raw acquisition untouchable, and L1.25a forbids
    slowing a hunt for any reason. A frozen money path during launch week costs NOTHING in
    discovery; the desk keeps hunting at 100% and simply stages the money-path change until the
    window closes.
  * A FIX FOR A LIVE DEFECT IS ALWAYS ALLOWED. This freezes IMPROVEMENTS, never REPAIRS: if the
    money path is broken, changing it is the safest available act, and refusing that would be
    the timid reading this desk bans.

WINDOWS (each is a period where an error cannot be caught before it costs real capital):
  GATE0_LAUNCH   from the first recorded capital event until +7 days of live operation
  FIRST_FILLS    while the execution tape has fewer than 20 recorded live fills
  RAIL_BREACH    while a ruin/derisk rail is live -- the book is already unwinding; a code
                 change mid-unwind is how a bad day becomes a terminal one

STATUS: OPEN (change freely) / STERILE (money-path improvements staged, repairs allowed) /
UNMEASURED (cannot tell -- treated as STERILE, because the cost of a wrong OPEN is unbounded and
the cost of a wrong STERILE is a delayed improvement).

    python scripts/check_change_window.py [--paths a.py b.py] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: This one gates on `verdict`, which is computed as a strict ALLOW/BLOCK binary, so it did not
#: have the fall-through hole the other seven had. Routed through the same helper anyway so that
#: a THIRD verdict value added later fails closed instead of joining the `else 0` branch -- the
#: property is that no future editor has to remember this file. Zero behaviour change today.
_PASSING = frozenset({"ALLOW"})

#: The money path: code whose defects can only be discovered by losing money.
#: NARROWED 2026-09-05 (universe mandate): run_cashcarry_executor.py, run_live_guard.py and
#: data/cashcarry_config.json went with the retired book. This is a PREFIX scope over changed
#: paths, so a dead entry is inert rather than dangerous -- but an inert entry also cannot be
#: distinguished from a live one by reading the tuple, and the whole point of naming the money
#: path explicitly is that a reader can tell what it covers. desks/mt5/ is added because that is
#: where money now moves: the gateway, the netting policy and the execution policy are precisely
#: "code whose defects can only be discovered by losing money".
MONEY_PATH = (
    "libs/execution/", "libs/risk/",
    "scripts/record_capital_event.py",
    "scripts/run_deadman_switch.py",
    "desks/mt5/mt5desk/gateway.py", "desks/mt5/mt5desk/netting.py",
    "desks/mt5/mt5desk/execution_policy.py",
)

LAUNCH_WINDOW_DAYS = 7
MIN_FILLS_FOR_CONFIDENCE = 20

#: The executor's published book state (run_cashcarry_executor.py:43). NOT cashcarry_state.json,
#: which nothing has ever written -- see _rail_live.
_STATE_REL = "data/cashcarry_positions.json"


def _capital_event_age_days(root: Path, now: datetime) -> float | None:
    """Days since the FIRST recorded capital event (the launch moment). None = never launched."""
    try:
        rows = [json.loads(ln) for ln in
                (root / "data/capital_events.jsonl").read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return None
    stamps = [r.get("at") for r in rows if isinstance(r, dict) and r.get("at")]
    if not stamps:
        return None
    try:
        first = datetime.fromisoformat(str(min(stamps)))
    except ValueError:
        return None
    first = first if first.tzinfo else first.replace(tzinfo=UTC)
    return (now - first).total_seconds() / 86400.0


def _n_fills(root: Path) -> int | None:
    p = root / "data/moat/execution_tape/cashcarry_trades.jsonl"
    try:
        return sum(1 for ln in p.read_text("utf-8").splitlines() if ln.strip())
    except OSError:
        return None


def _rail_live(root: Path) -> tuple[bool | None, str]:
    """Is a ruin/derisk rail live? (verdict, why) -- None means UNMEASURED, never "no rail".

    R0333: this read pointed at data/cashcarry_state.json, a file no organ writes, so the
    RAIL_BREACH window could only ever be measured through the kill file. The executor publishes
    `last_risk_action` (run_cashcarry_executor.py, latched each tick) into
    data/cashcarry_positions.json. The three failure modes are now named separately: an absent
    file, a torn/unparseable one and one whose schema lacks the key are different facts about
    the box, and none of them is evidence that no rail is live.
    """
    if (root / "data/CASHCARRY_KILL").exists():
        return True, "CASHCARRY_KILL present"
    p = root / _STATE_REL
    try:
        raw = p.read_text("utf-8")
    except FileNotFoundError:
        return None, f"absent ({_STATE_REL} never written on this box)"
    except OSError as exc:
        return None, f"unreadable ({type(exc).__name__} on {_STATE_REL})"
    try:
        st = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"unparseable ({_STATE_REL} is not valid JSON, line {exc.lineno})"
    if not isinstance(st, dict):
        return None, f"unparseable ({_STATE_REL} holds a {type(st).__name__}, not an object)"
    try:
        action = str(st["last_risk_action"])
    except KeyError:
        return None, f"schema-missing-key (`last_risk_action` absent from {_STATE_REL})"
    return action in ("flatten", "pause_opens"), f"last_risk_action={action!r}"


def touches_money_path(paths: list[str]) -> list[str]:
    return [p for p in paths if any(p.startswith(m) or m.rstrip("/") in p for m in MONEY_PATH)]


def build_report(root: Path | None = None, now: datetime | None = None,
                 paths: list[str] | None = None) -> dict[str, Any]:
    root = root or _ROOT
    now = now or datetime.now(tz=UTC)
    reasons: list[str] = []
    unmeasured: list[str] = []

    age = _capital_event_age_days(root, now)
    if age is not None and age <= LAUNCH_WINDOW_DAYS:
        reasons.append(f"GATE0_LAUNCH: {age:.1f}d since first capital event "
                       f"(window {LAUNCH_WINDOW_DAYS}d)")
    fills = _n_fills(root)
    if fills is None:
        unmeasured.append("execution tape unreadable -- cannot count live fills")
    elif age is not None and fills < MIN_FILLS_FOR_CONFIDENCE:
        reasons.append(f"FIRST_FILLS: {fills} live fills recorded (< {MIN_FILLS_FOR_CONFIDENCE})")
    rail, rail_why = _rail_live(root)
    if rail is None:
        unmeasured.append(f"executor state {rail_why} -- cannot tell if a rail is live")
    elif rail:
        reasons.append(f"RAIL_BREACH: a ruin/derisk rail is live ({rail_why}) -- "
                       "the book is unwinding")

    if age is None:
        # PRE-LAUNCH IS ALWAYS OPEN, even when tape/state are unreadable: with no capital event
        # ever recorded there is provably no live capital a change could harm, so the
        # unmeasured->STERILE asymmetry does not apply. (First run of this fence got that wrong
        # and would have blocked the very session that was fixing the money path pre-launch.)
        status, note = "OPEN", ("pre-launch: no capital event recorded, so no live capital can "
                                "be harmed by a money-path change")
        unmeasured = []
    elif reasons:
        status, note = "STERILE", "money-path IMPROVEMENTS staged; repairs always allowed"
    elif unmeasured:
        # A wrong OPEN costs unbounded real capital; a wrong STERILE costs a delayed improvement.
        status, note = "UNMEASURED", ("cannot prove the window is safe -- treated as STERILE, "
                                      "because the asymmetry is not close")
    else:
        status, note = "OPEN", "outside every declared window"

    offending = touches_money_path(paths or [])
    return {
        "generated": now.isoformat(), "status": status,
        "law": "L1.38 -- the money path does not change inside a window where the change cannot "
               "be validated before it costs real capital. Research/mining/fences are UNAFFECTED.",
        "windows_active": reasons, "unmeasured": unmeasured, "note": note,
        "days_since_launch": None if age is None else round(age, 2),
        "live_fills": fills,
        "money_path_files_in_change": offending,
        "verdict": ("BLOCK" if offending and status in ("STERILE", "UNMEASURED") else "ALLOW"),
        "next_action": (
            "stage the improvement on a branch and land it when the window closes. If this IS a "
            "repair for a live defect, say so in the commit and proceed -- this law freezes "
            "improvements, never repairs. Research, mining, data acquisition, fences and "
            "exploration are not affected and must not be slowed (L1.25a, L1.28b(f))."),
    }


#: The ONLY way a money-path commit is read as a repair. Deliberately an EXPLICIT marker and not
#: a keyword sniff: "fix" appears in most commit subjects on this desk, so a keyword list would
#: classify ~everything as REPAIR and weld this gate permanently OPEN -- a gate that accepts ~100%
#: carries zero information (L1.43), which is the failure this was built to avoid, not cause.
#: Requiring the operator to WRITE the declaration is the point: it is an assertion that a live
#: defect exists, and an undeclared money-path commit stays frozen by default (fail-closed).
REPAIR_MARKER = "L1.38: repair"


def classify_commits(base: str, head: str = "HEAD", root: Path | None = None) -> list[dict]:
    """Classify every commit in base..head as REPAIR / IMPROVEMENT / NON-MONEY-PATH.

    R0426. This fence judged a WINDOW and a PATH SET and never a DIFF, so it could not answer the
    only question an operator actually has: *can I restart this process right now?* The unit of
    deployment is a PROCESS RESTART, not a commit -- so a repair sitting behind a deliberately
    withheld improvement cannot be shipped without also shipping the improvement, and the fence
    had no vocabulary for saying which pending commits were which.

    UNDECLARED IS AN IMPROVEMENT, NEVER A REPAIR. That is the conservative direction and the one
    that matches the law: the cost of wrongly staging a repair is a delayed fix, the cost of
    wrongly shipping an improvement into a live window is unbounded.
    """
    root = root or _ROOT
    import subprocess
    try:
        raw = subprocess.run(
            ["git", "log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e", f"{base}..{head}"],
            cwd=root, capture_output=True, text=True, timeout=30, check=True).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        return [{"sha": None, "kind": "UNMEASURED",
                 "why": f"git log {base}..{head} failed: {type(exc).__name__}"}]
    out: list[dict] = []
    for rec in (r.strip() for r in raw.split("\x1e") if r.strip()):
        sha, subject, body = [*rec.split("\x1f"), "", ""][:3]
        try:
            files = subprocess.run(
                ["git", "show", "--pretty=", "--name-only", sha],
                cwd=root, capture_output=True, text=True, timeout=30, check=True
            ).stdout.split()
        except (subprocess.SubprocessError, OSError) as exc:
            # NOT swallowed to NON-MONEY-PATH: a commit whose files cannot be listed is UNKNOWN,
            # and treating unknown as harmless is precisely the false-OPEN this law forbids.
            out.append({"sha": sha[:8], "subject": subject[:90], "kind": "UNMEASURED",
                        "why": f"cannot list files ({type(exc).__name__})"})
            continue
        money = touches_money_path(files)
        if not money:
            kind, why = "NON-MONEY-PATH", "touches no money-path file -- the freeze does not apply"
        elif REPAIR_MARKER.lower() in f"{subject}\n{body}".lower():
            kind, why = "REPAIR", f"declares {REPAIR_MARKER!r} -- repairs are always allowed"
        else:
            kind, why = "IMPROVEMENT", (
                f"touches the money path and does NOT declare {REPAIR_MARKER!r}, so it is "
                "treated as an improvement and stays staged inside a window")
        out.append({"sha": sha[:8], "subject": subject[:90], "kind": kind, "why": why,
                    "money_path_files": money})
    return out


def restart_verdict(base: str, head: str = "HEAD", root: Path | None = None,
                    status: str | None = None) -> dict[str, Any]:
    """Can the money-path units be restarted onto HEAD right now, and if not, which commit blocks?

    Turns 'can I restart?' from an argument into a lookup. `base` is what the RUNNING process has
    -- the sha it was started from (max_audit._proc_start gives the start time when the sha is
    not recorded; a restart-time sha stamp is the better input and is what a caller should pass).
    """
    status = status or str(build_report(root=root).get("status") or "UNMEASURED")
    commits = classify_commits(base, head, root=root)
    blocking = [c for c in commits if c["kind"] in ("IMPROVEMENT", "UNMEASURED")]
    repairs = [c for c in commits if c["kind"] == "REPAIR"]
    if status == "OPEN":
        verdict, why = "ALLOW", "the change window is OPEN -- nothing is frozen"
    elif not commits:
        verdict, why = "ALLOW", f"no commits between {base[:8]} and {head}"
    elif not blocking and not repairs:
        # DISTINCT FROM "all repairs". The first run printed "0 pending money-path commit(s), ALL
        # declared repairs", which reads as a judgement about repairs when the real answer is that
        # the freeze never applied -- two different facts, and only one of them involves L1.38.
        verdict, why = "ALLOW", (
            f"none of the {len(commits)} pending commit(s) touch the money path -- the freeze "
            "does not apply to any of them")
    elif not blocking:
        verdict, why = "ALLOW", (
            f"{len(repairs)} pending money-path commit(s), ALL declared repairs -- a repair is "
            "always allowed to deploy, even inside a window")
    else:
        verdict, why = "BLOCK", (
            f"{len(blocking)} pending money-path change(s) are not declared repairs, so a restart "
            f"would ship them into a {status} window alongside any repair")
    return {"verdict": verdict, "why": why, "window_status": status, "base": base[:8],
            "n_commits": len(commits), "n_repairs": len(repairs), "n_blocking": len(blocking),
            "blocking": blocking, "commits": commits,
            "next_action": (
                "land the repair on its own by declaring "
                f"{REPAIR_MARKER!r} in its commit and restarting onto a tree that carries only "
                "declared repairs; or wait for the window to close. Never restart onto a tree "
                "holding an undeclared money-path change." if verdict == "BLOCK" else
                "restart is permitted by L1.38")}


def held_units(status: str | None = None) -> list[str]:
    """Supervised units an UNATTENDED deploy must not restart right now (L1.38).

    THE GAP THIS CLOSES, found 2026-08-12 by asking what the deploy-path repair would switch on.
    scripts/run_stale_daemon_repair.py consults this window before restarting anything, but
    deploy/pull_deploy.sh -- which restarts supervised processes every 10 minutes on the box that
    owns the book -- never did. That was invisible because its dirty-tree refusal had made it a
    no-op for eight days, so the unguarded restart had simply never been reachable. Repairing the
    deploy path without this would have ARMED it: the first commit touching libs/execution/ would
    have restarted quant-cashcarry inside a live RAIL_BREACH window, which is exactly the
    "ships whatever is on disk into the money path" move L1.38 exists to prevent.

    An empty list means "restart freely". Deliberately NOT the deadman: that is TIER_RUIN and
    deploy_plan already refuses to restart it by tier, a stronger guarantee than a window.
    """
    from libs.ops.deploy_plan import units_touching
    status = status or str(build_report().get("status") or "UNMEASURED")
    if status == "OPEN":
        return []
    return list(units_touching(MONEY_PATH))


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", nargs="*", default=[], help="changed files to judge")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--held-units", action="store_true",
                    help="print units an unattended deploy must not restart now, one per line")
    ap.add_argument("--can-restart", metavar="BASE_SHA",
                    help="classify commits BASE_SHA..HEAD as repair/improvement and answer "
                         "whether the money-path units can be restarted onto HEAD (R0426)")
    args = ap.parse_args()
    if args.can_restart:
        # A QUERY like --held-units: it must not write the fence artifact. Its exit code IS the
        # answer (0 = restart allowed, 1 = blocked) so a deploy script can gate on it directly.
        rv = restart_verdict(args.can_restart)
        if args.json:
            print(json.dumps(rv, indent=2))
        else:
            print(f"restart onto HEAD: {rv['verdict']} -- {rv['why']}")
            for c in rv["commits"]:
                print(f"  {c['kind']:<16}{c.get('sha') or '?':<10}{c.get('subject', '')[:64]}")
            if rv["verdict"] == "BLOCK":
                print(f"  next: {rv['next_action']}")
        return 0 if rv["verdict"] == "ALLOW" else 1
    if args.held_units:
        # A QUERY, not a fence run: it must not write the report artifact and must not exit
        # non-zero on a sterile window, or the caller cannot tell "held these" from "I crashed".
        for unit in held_units():
            print(unit)
        return 0
    rep = build_report(paths=args.paths)
    out = _ROOT / "data/change_window.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"change window (L1.38): {rep['status']} -- {rep['note']}")
        for r in rep["windows_active"]:
            print(f"  WINDOW  {r}")
        if rep["money_path_files_in_change"]:
            print(f"  {rep['verdict']}   money-path files: {rep['money_path_files_in_change']}")
    if args.report_only:
        return 0
    return fence_exit(rep["verdict"], _PASSING)


if __name__ == "__main__":
    sys.exit(main())
