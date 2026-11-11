"""CAN EACH RUIN RAIL ACTUALLY FIRE, AND HOW OLD IS THE HALT REALLY?

WHAT HAPPENED, measured 2026-11-11 by the noon CRO pass, and it is two defects wearing one coat.

The Fusion gateway had been halted since **2026-10-30T19:51:04Z** -- 11.7 days, 26,043 consecutive
`gateway paused` passes -- and the one fence that exists to shout about it,
`check_research_health`, had been reporting:

    TRADING HALTED for 0.0 day(s) -- THE DESK IS NOT TRADING.

0.0 days, every pass, for twelve days. Not a bug in the arithmetic: the age was taken from the
mtime of `desks/mt5/data/GATEWAY_PAUSED`, and the ruin rail REWRITES that marker every five
minutes while the halt stands ("HALT FILE WRITTEN" in `logs/fusion_deadman.log`). The alarm
measured the age of its own heartbeat. An eleven-day halt and a one-minute halt read identically,
and the one that reads like a blip is the one that gets ignored. The marker's own first line is
rewritten too, so the ORIGINAL halt instant survives nowhere except the gateway log.

THE SECOND DEFECT IS WHY NOTHING ELSE CAUGHT IT. `proposals/fusion_deadman.py` reads its entire
view of the account out of `desks/mt5/data/gateway_state.json`:

    st = _read(STATE, {})
    account = {"equity": st.get("equity", 0.0), "margin_free": st.get("margin_free", 0.0), ...}
    positions = st.get("position") or []

and `gateway.main()` returns at `if gateway_paused()` BEFORE it connects, reads
`mt5.account_info()` or saves state. So the halt freezes the only input the rail that wrote it
has. Measured on this box: the file's last write was 2026-10-30T19:50:13Z, one minute before the
first paused pass. Eleven days of readings, all of them the same snapshot.

That snapshot cannot reach five of the rail's seven rails AT ALL:

    EQUITY_FLOOR     fires -- on equity 266.01, frozen on 10-30, re-affirmed 170 times a day
    DAILY_LOSS       the opening-balance arm needs day_start_equity.date == today's broker day;
                     the frozen file says 2026-10-30, so it can never match again
    MARGIN           needs `margin_free`, A KEY gateway_state.json HAS NEVER CARRIED -> 0.0 ->
                     `free_margin > 0` is False -> the rail is unreachable, halt or no halt
    POSITION_COUNT   needs `position`; the file holds null -> [] -> never > MAX_OPEN_POSITIONS
    SIZE_GUARD       same [] -> the stamp's own census reads judged 0, unmeasured 0
    STALE_HEARTBEAT  keyed off open positions, so [] silences it too
    WEEKLY_LOSS      reads the live ledger, not this file: the one rail still looking at reality

So the account's "whole defence" was one reachable rail, latched on a dead number, and a halt
whose age was reported as zero. Nothing in this repository asked either question, because every
fence here reads an artifact and judges its CONTENTS -- and this artifact was present, parseable
and confidently wrong. ABSENCE OF ALARM IS NOT HEALTH (constitution 22); an input a rail cannot
reach is UNMEASURED, never a passing reading (L1.28a).

WHAT THIS FENCE DOES, AND WHAT IT DELIBERATELY DOES NOT.

It measures and names. It reports the halt's REAL age from a durable origin record (seeded by a
bounded backwards scan of the gateway log, never from the marker's mtime), the age of the rail's
input, a per-rail REACHABLE / UNREACHABLE census with the exact missing key, and the LATCHED
verdict -- the halt is older than its own input's last refresh, so the condition that would clear
it can no longer be observed.

It never deletes the marker, never writes the rail's stamp, never re-arms and never sizes
anything. Re-arming places live orders and this box takes no autonomous fixer on the money path
(the same standing rule `check_research_health` records at its own halt branch). Clearing a halt
is the principal's act. Saying out loud, hourly, that the halt is eleven days old and that five of
seven rails cannot fire is this file's whole job -- and it is the job that was missing.

    python scripts/check_halt_rail_integrity.py
    python scripts/check_halt_rail_integrity.py --json

Exit 0 clean, 2 RED (a latched halt, or a rail input too stale to judge while the desk is
halted), 3 UNMEASURED (the inputs cannot be read at all). 2 and 3 are NOT registered in
`hourly_cycle.VERDICT_EXITS`, by the same reasoning that keeps `silent_organs` out of it: a
declared verdict records as `verdict_exit=N`, which every streak reader counts as ok, and a RED
that pages nobody is the defect this file exists to end.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
MARKER = DESK / "data" / "GATEWAY_PAUSED"
RAIL_INPUT = DESK / "data" / "gateway_state.json"
RAIL_STAMP = DESK / "data" / "fusion_deadman_state.json"
ACCOUNT_STATE = DESK / "data" / "account_state.json"
GATEWAY_LOG = DESK / "logs" / "gateway.log"
#: The durable halt origin. The marker cannot hold it: the rail rewrites the marker, and its first
#: line with it, every five minutes. Box-local state, like every other `data/` record.
ORIGIN = DESK / "data" / "halt_origin.json"
OUT = DESK / "reports" / "HALT_RAIL_INTEGRITY.json"

#: The line the gateway logs on a paused pass, verbatim from `gateway.main()`.
PAUSED_LINE = "gateway paused"
#: Lines in the gateway log that are NOT a gateway pass and so cannot end a paused streak. The
#: loop wrapper's process recycle is the measured case; see `halt_start_from_log`.
TRANSPARENT_LINES: tuple[str, ...] = ("RESIDENT:",)
#: How far back the log is read to seed an origin we do not already hold. 11.7 days of paused
#: passes measured 2.9 MB, so 32 MB covers months -- and a miss is reported as a LOWER_BOUND,
#: never as a fresh halt. Bounded on purpose: gateway.log was 101 MB on the box that trades, and
#: an hourly fence that reads all of it is a defect of its own.
LOG_TAIL_BYTES = 32 * 1024 * 1024

#: The rail's input must be younger than this to be a reading of the present. DERIVATION: the
#: rail's own `STALE_HEARTBEAT_MIN` is 45 minutes ("a gateway that has not reconciled while
#: positions are open is unmanaged risk, and 45 minutes is already 3 missed 15-minute passes"), so
#: the input it judges may not be older than the staleness its own rail calls unmanaged.
RAIL_INPUT_MAX_AGE_MIN = 45.0

#: Every rail in `proposals/fusion_deadman.evaluate`, with the `gateway_state.json` key it needs
#: to be able to fire at all, and whether a missing or empty value silences it. WEEKLY_LOSS is
#: listed with no key because it reads the live ledger, not this file.
RAILS: tuple[tuple[str, str | None, str], ...] = (
    ("EQUITY_FLOOR", "equity", "a positive equity reading"),
    ("DAILY_LOSS", "day_start_equity", "an opening balance dated to today's broker day"),
    ("MARGIN", "margin_free", "free margin; the rail needs free_margin > 0 to judge"),
    ("POSITION_COUNT", "position", "the open book; [] can never exceed the cap"),
    ("SIZE_GUARD", "position", "the open book; [] judges no position's size"),
    ("STALE_HEARTBEAT", "position", "the open book; the rail is keyed off open positions"),
    ("WEEKLY_LOSS", None, "the live ledger, read directly -- not this file"),
)


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    """(document, why). Unreadable and absent are DIFFERENT and both are reported."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, f"{path.name} absent"
    except (OSError, ValueError) as exc:
        return None, f"{path.name} unreadable ({type(exc).__name__})"
    return (doc, "read") if isinstance(doc, dict) else (None, f"{path.name} is not an object")


def _age_min(path: Path, now: datetime) -> float | None:
    try:
        return (now - datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)).total_seconds() / 60.0
    except OSError:
        return None


def _iso(value: object) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return at if at.tzinfo else at.replace(tzinfo=UTC)


def _broker_day(now: datetime) -> str:
    """The rail's own broker day (server midnight == 17:00 America/New_York), by its own rule."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    et = now.astimezone(ZoneInfo("America/New_York"))
    return (et + timedelta(hours=7)).strftime("%Y-%m-%d")


def halt_start_from_log(log: Path | None = None, tail_bytes: int = LOG_TAIL_BYTES
                        ) -> tuple[str | None, str, int]:
    """(first instant of the current unbroken paused streak, basis, paused passes counted).

    Read backwards over a bounded tail: the streak starts at the OLDEST paused line with no GATEWAY
    PASS line before it inside the window. If the window never reaches one, the halt is older than
    the window and the basis says LOWER_BOUND -- an honest floor, which is the whole point. A halt
    that is not in progress returns (None, ...).

    ONLY A GATEWAY PASS BREAKS THE STREAK, and getting this wrong cost a measurement. The loop
    wrapper (`research/run_gateway_loop.py`) writes `RESIDENT: started pid ...` into the same log
    when it recycles the process, and the box recycles every 120 passes -- so counting any
    non-paused line as a live pass dated an 11.7-day halt at 2.0 hours, the newest recycle. The
    recycle line is TRANSPARENT: it proves the wrapper restarted, never that a pass traded. A line
    this list does not know still breaks the streak, which errs toward a SHORTER reported halt, so
    `paused_passes` is published beside the age as grammar-free corroboration of the duration.

    `log` resolves to the module's GATEWAY_LOG AT CALL TIME, never at definition time: as a default
    argument it froze the worktree's own path into a `--root` run against the box, which then
    reported the halt's age as unreadable while reading that same halt's marker perfectly well.
    """
    log = log or GATEWAY_LOG
    try:
        size = log.stat().st_size
        with log.open("rb") as fh:
            fh.seek(max(0, size - tail_bytes))
            chunk = fh.read()
    except OSError as exc:
        return None, f"gateway log unreadable ({type(exc).__name__})", 0
    lines = [ln for ln in chunk.decode("utf-8", "replace").splitlines() if ln.strip()]
    if not lines:
        return None, "gateway log holds no lines in the read window", 0
    passes = [ln for ln in lines if not any(t in ln for t in TRANSPARENT_LINES)]
    if not passes or PAUSED_LINE not in passes[-1]:
        return None, "the newest gateway pass was not paused", 0
    start: str | None = None
    counted = 0
    for line in reversed(passes):
        if PAUSED_LINE not in line:
            if not start:
                return None, "no paused streak found", 0
            return start, (f"first paused pass after the last live pass in the log "
                           f"({len(lines)} lines read, {counted} paused passes)"), counted
        counted += 1
        stamp = line.split(" ", 1)[0]
        if _iso(stamp) is not None:
            start = stamp
    return start, (f"LOWER_BOUND: every one of the {counted} passes in the read window is paused, "
                   f"so the halt began at or before this instant"), counted


def halt_origin(halted: bool, now: datetime, *, write: bool = True) -> dict[str, Any]:
    """The durable origin record. Seeded from the log, then simply kept; dropped when the halt is.

    THE MARKER CANNOT HOLD THIS and that is the defect this function answers: the rail rewrites
    `GATEWAY_PAUSED` -- mtime and first line both -- every five minutes it stays halted.
    """
    held, why = _read_json(ORIGIN)
    if not halted:
        if write and ORIGIN.exists():
            with contextlib.suppress(OSError):
                ORIGIN.unlink()
        return {"halt_since": None, "basis": "not halted", "held": False}
    since = str(held.get("halt_since")) if held and held.get("halt_since") else None
    basis = str(held.get("basis") or "held") if held else None
    if held and since and _iso(since) is not None:
        return {"halt_since": since, "basis": basis or "held", "held": True,
                "paused_passes": held.get("paused_passes")}
    since, basis, passes = halt_start_from_log()
    rec = {"halt_since": since, "basis": basis or why, "paused_passes": passes,
           "first_observed_at": now.isoformat(timespec="seconds"),
           "why": "the marker is rewritten every rail pass, so its mtime is not the halt's age"}
    if write and since:
        try:
            ORIGIN.parent.mkdir(parents=True, exist_ok=True)
            ORIGIN.write_text(json.dumps(rec, indent=1), encoding="utf-8")
        except OSError:
            pass
    return {**rec, "held": False}


def rail_census(state: dict[str, Any] | None, now: datetime) -> list[dict[str, Any]]:
    """Per rail: can it fire on the input the rail actually reads? REACHABLE is not 'quiet'."""
    out: list[dict[str, Any]] = []
    for name, key, needs in RAILS:
        if key is None:
            out.append({"rail": name, "verdict": "REACHABLE", "needs": needs,
                        "why": "reads the live ledger directly, not gateway_state.json"})
            continue
        if state is None:
            out.append({"rail": name, "verdict": "UNMEASURED", "needs": needs,
                        "why": "gateway_state.json could not be read"})
            continue
        present = key in state
        value = state.get(key)
        verdict, why = "REACHABLE", f"{key} present"
        if not present:
            verdict = "UNREACHABLE"
            why = f"gateway_state.json carries no {key!r} key, so the rail reads its empty default"
        elif value in (None, [], {}, 0, 0.0):
            verdict = "UNREACHABLE"
            why = f"{key} is {value!r}; the rail's guard cannot pass on it"
        elif key == "day_start_equity" and isinstance(value, dict):
            # The opening-balance arm compares the anchor's date with the current broker day.
            anchor = str(value.get("date") or "")
            today = _broker_day(now)
            if anchor != today:
                verdict = "UNREACHABLE"
                why = (f"day_start_equity is dated {anchor or 'nothing'}, not today's broker day "
                       f"{today}; a stale anchor is no opening balance")
        out.append({"rail": name, "verdict": verdict, "needs": needs, "why": why})
    return out


def _first_line() -> str | None:
    try:
        for line in MARKER.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                return line.strip()
    except OSError:
        return None
    return None


def measure(now: datetime | None = None, *, write_origin: bool = True) -> dict[str, Any]:
    """Pure-ish: reads the box's artifacts, writes only the origin record. No halt is touched."""
    now = now or datetime.now(tz=UTC)
    halted = MARKER.exists()
    marker_age = _age_min(MARKER, now) if halted else None
    origin = halt_origin(halted, now, write=write_origin)
    since = _iso(origin.get("halt_since"))
    halt_hours = round((now - since).total_seconds() / 3600.0, 2) if since else None

    state, state_why = _read_json(RAIL_INPUT)
    input_age = _age_min(RAIL_INPUT, now)
    recon = _iso((state or {}).get("last_reconcile"))
    input_verdict = "UNMEASURED"
    if state is not None and input_age is not None:
        input_verdict = "FRESH" if input_age <= RAIL_INPUT_MAX_AGE_MIN else "STALE"

    stamp, stamp_why = _read_json(RAIL_STAMP)
    stamp_at = _iso((stamp or {}).get("checked_at"))
    census = rail_census(state, now)
    reachable = [r["rail"] for r in census if r["verdict"] == "REACHABLE"]
    unreachable = [r["rail"] for r in census if r["verdict"] == "UNREACHABLE"]

    # THE LATCH. The halt is older than its own input's last refresh, so the rail is re-reading a
    # snapshot taken before the halt began -- the condition that would clear the halt can no longer
    # be observed, and no new breach can be seen either. This is a structural verdict, not a
    # threshold: it holds whenever the input predates the halt.
    latched = bool(halted and input_age is not None and halt_hours is not None
                   and input_age / 60.0 >= halt_hours)
    # Does the rail's own stamp quote the frozen file? Equality of the judged equity and the frozen
    # equity is the proof that the halt is being re-affirmed from the snapshot, not re-measured.
    judged = ((stamp or {}).get("readings") or {}).get("equity")
    frozen = (state or {}).get("equity")
    quotes_frozen = judged is not None and frozen is not None and judged == frozen

    account, account_why = _read_json(ACCOUNT_STATE)
    breaches: list[str] = []
    if state is None:
        breaches.append(f"RAIL INPUT UNMEASURED: {state_why} -- the ruin rail judges nothing")
    if halted and latched and halt_hours is not None and input_age is not None:
        breaches.append(
            f"HALT LATCHED for {halt_hours:.1f}h ({halt_hours / 24:.1f} days): the rail's only "
            f"input {RAIL_INPUT.name} is {input_age / 60.0:.1f}h old, older than the halt itself, "
            f"so the clear condition can no longer be observed"
            + (f" -- the stamp re-affirms the frozen equity {frozen}" if quotes_frozen else ""))
    if halted and input_verdict == "STALE" and not latched and input_age is not None:
        breaches.append(f"RAIL INPUT STALE while halted: {RAIL_INPUT.name} is "
                        f"{input_age:.0f} min old (limit {RAIL_INPUT_MAX_AGE_MIN:.0f})")
    if unreachable:
        breaches.append(f"RAILS UNREACHABLE ({len(unreachable)} of {len(census)}): "
                        + ", ".join(unreachable)
                        + " -- each reads a key the input does not carry or carries empty")
    if halted and marker_age is not None and halt_hours is not None and marker_age < 60 \
            and halt_hours > 1:
        breaches.append(
            f"MARKER AGE IS NOT HALT AGE: {MARKER.name} was rewritten {marker_age:.0f} min ago "
            f"while the halt is {halt_hours:.1f}h old -- any fence reading its mtime reports ~0 "
            f"days")

    verdict = "OK"
    if state is None and stamp is None:
        verdict = "UNMEASURED"
    elif breaches:
        verdict = "RED"
    return {
        "at": now.isoformat(timespec="seconds"),
        "verdict": verdict,
        "law": ("a rail that cannot reach its input is not quiet, it is blind; and the age of a "
                "marker its own writer rewrites is never the age of the halt"),
        "halt": {
            "halted": halted,
            "halt_since": origin.get("halt_since"),
            "halt_hours": halt_hours,
            "halt_days": round(halt_hours / 24.0, 2) if halt_hours is not None else None,
            "basis": origin.get("basis"),
            "origin_held": origin.get("held"),
            "paused_passes": origin.get("paused_passes"),
            "marker_age_min": None if marker_age is None else round(marker_age, 1),
            "marker_age_is_not_halt_age": True,
            "marker_first_line": _first_line(),
        },
        "rail_input": {
            "path": "desks/mt5/data/gateway_state.json",
            "verdict": input_verdict,
            "age_min": None if input_age is None else round(input_age, 1),
            "age_hours": None if input_age is None else round(input_age / 60.0, 2),
            "max_age_min": RAIL_INPUT_MAX_AGE_MIN,
            "why": state_why,
            "equity": frozen,
            "last_reconcile": None if recon is None else recon.isoformat(),
            "last_reconcile_age_hours": (None if recon is None else
                                         round((now - recon).total_seconds() / 3600.0, 2)),
            "carries_account_identity": any(
                k in (state or {}) for k in ("login", "account", "server", "venue")),
            "identity_why": ("gateway_state.json carries no login, account, server or venue key: "
                             "the rail judges an equity number with no account attached"),
        },
        "rail_stamp": {
            "verdict": "MEASURED" if stamp else "UNMEASURED",
            "why": stamp_why,
            "mode": (stamp or {}).get("mode"),
            "halt_codes": (stamp or {}).get("halt_codes"),
            "checked_at": None if stamp_at is None else stamp_at.isoformat(),
            "checked_age_min": (None if stamp_at is None else
                                round((now - stamp_at).total_seconds() / 60.0, 1)),
            "judged_equity": judged,
            "quotes_frozen_input": quotes_frozen,
        },
        "rails": census,
        "rails_reachable": len(reachable),
        "rails_total": len(census),
        "rails_unreachable": unreachable,
        "latched": latched,
        "live_terminal": {
            "verdict": "MEASURED" if account else "UNMEASURED",
            "why": account_why,
            "venue": (account or {}).get("venue"),
            "server": (account or {}).get("server"),
            "equity": (account or {}).get("equity"),
            "updated_at": (account or {}).get("updated_at"),
            "note": ("the live terminal's own account, for comparison only: this fence never "
                     "joins it to the rail's input, because the input names no account"),
        },
        "breaches": breaches,
        "never_does": ["delete GATEWAY_PAUSED", "write the rail's stamp", "re-arm", "size"],
    }


def _rebind(root: Path) -> None:
    """Point every path at another checkout. For reading the LIVE tree from a worktree copy, and
    for tests: one place, so no reader has to wonder which tree a number came from."""
    global ROOT, DESK, MARKER, RAIL_INPUT, RAIL_STAMP, ACCOUNT_STATE, GATEWAY_LOG, ORIGIN, OUT
    ROOT = root.resolve()
    DESK = ROOT / "desks" / "mt5"
    MARKER = DESK / "data" / "GATEWAY_PAUSED"
    RAIL_INPUT = DESK / "data" / "gateway_state.json"
    RAIL_STAMP = DESK / "data" / "fusion_deadman_state.json"
    ACCOUNT_STATE = DESK / "data" / "account_state.json"
    GATEWAY_LOG = DESK / "logs" / "gateway.log"
    ORIGIN = DESK / "data" / "halt_origin.json"
    OUT = DESK / "reports" / "HALT_RAIL_INTEGRITY.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print the report")
    ap.add_argument("--no-write", action="store_true", help="do not write report or origin")
    ap.add_argument("--root", help="measure another checkout (pair with --no-write to read only)")
    args = ap.parse_args(argv)
    if args.root:
        _rebind(Path(args.root))
    rep = measure(write_origin=not args.no_write)
    if not args.no_write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(f".json.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(rep, indent=1), encoding="utf-8")
        os.replace(tmp, OUT)
    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        h = rep["halt"]
        print(f"{rep['verdict']}: halted={h['halted']} for "
              f"{h['halt_hours']}h ({h['halt_days']} days, basis {h['basis']}); "
              f"rails reachable {rep['rails_reachable']}/{rep['rails_total']}; "
              f"input {rep['rail_input']['verdict']} "
              f"{rep['rail_input']['age_hours']}h; latched={rep['latched']}")
        for b in rep["breaches"]:
            print(f"  - {b}")
    if rep["verdict"] == "UNMEASURED":
        return 3
    return 2 if rep["verdict"] == "RED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
