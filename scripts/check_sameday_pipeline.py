#!/usr/bin/env python3
"""SAME-DAY PIPELINE FENCE (principal 2026-08-26: "all these things must happen same day --
the discovery, backtest, 10 gates, then 14 day with AUDNZD, then live -- make it canonical").

THE LAW THIS ENFORCES (LAWS L1.58, RESEARCH §6d). The front half of the pipeline --
DISCOVERY -> BACKTEST -> TEN-GATE GAUNTLET -> FORWARD ENROLMENT -- carries no waiting room. A
candidate discovered today is gauntleted today and, if it certifies, is on a forward clock today.
The back half is the 14-day forward window, which is a MEASUREMENT and cannot be hurried.

WHY THE FRONT HALF IS FREE AND THE BACK HALF IS NOT. Enrolment costs nothing: shadow trades risk
no capital, so a day spent un-enrolled buys no safety, it only destroys evidence that would
otherwise already be accruing. Every such day is subtracted directly from compounding -- this is
the principal's catch-up law (LAWS §2a: utilisation must catch up to raw growth) in its sharpest
form. But the forward window itself is the one thing that must never be compressed, because it
is the only evidence in the whole system that was not available during selection.

WHAT THIS FENCE ACTUALLY CHECKS -- three failures, each one measured tonight:

  1. CERTIFIED BUT NOT ENROLLED. A certificate in UNIVERSAL_SURVIVORS.json with no forward clock.
     This is the exact shape of GAP 129 (the certifier itself sat unscheduled for days) and of
     the five external asia sleeves, which certified while nothing put them on a clock.

  2. ENROLLED WITHOUT A PRE-REGISTRATION STAMP. A forward row missing `forward_start`. Without
     that stamp `days_active` was computed from the first trade the sleeve EVER took, so rows
     arrived at the gate 8/14 through a "forward" window measured over the period they were
     being selected in. A clock that starts before the hypothesis is frozen is not evidence.

  3. AN ENROLLED SLEEVE THAT DOES NOT FIRE. AUDNZD sat at n=0 trades over 2 days on the clock.
     A sleeve taking no trades is not accumulating evidence for OR against itself -- it will
     reach day 14 with nothing to judge and cure nothing (L1.28a: unmeasured is never a verdict).
     Silence must be reported as silence rather than counted as patience.

This fence reports and fires the repair organ. It never promotes, never enrolls, and never
touches the forward window -- a fence that could shorten the measurement it guards is not a fence.
"""
from __future__ import annotations

import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from libs.ops.forward_clock import forward_days, overstated_rows
from libs.ops.repair_invoke import request_repair

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
CERTS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SHADOW = DESK / "reports" / "shadow"
ALARM = ROOT / "data" / "SAMEDAY_ALARM.txt"
REPORT = ROOT / "data" / "sameday_pipeline.json"

#: A certificate older than this with no forward clock is a latency defect, not a race.
ENROL_GRACE_HOURS = 24
#: An enrolled sleeve silent this long has a firing problem, not a patience problem.
SILENT_DAYS = 3
#: A live clock refreshed less often than this is idle -- the cycle runs every 15 minutes.
IDLE_HOURS = 3.0
#: Verdicts that stop a clock. Everything else is still counting and still owes a stamp.
#: Matched by PREFIX so RETIRED_ORPHAN / RETIRED_GATE_FAIL / RETIRED_UNRECONSTRUCTIBLE (written
#: by forward_reconcile) count as stopped. An exact-string set silently kept 31 retired rows
#: reading as live clocks.
_TERMINAL_PREFIXES = ("RETIRED", "KILL", "QUARANTIN", "DEAD", "REJECT")


def _is_terminal(status) -> bool:
    s = str(status or "").upper()
    return s.startswith(_TERMINAL_PREFIXES) or s == "PROMOTED"


def read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def forward_rows() -> dict[str, dict]:
    """Every forward clock the desk keeps, from whichever state file owns it."""
    rows: dict[str, dict] = {}
    for f in [*sorted(SHADOW.glob("*_state.json")), SHADOW / "shadow_state.json"]:
        data = read(f)
        if not isinstance(data, dict):
            continue
        for key, val in data.items():
            if isinstance(val, dict) and ("status" in val or "forward_start" in val):
                rows[key] = val
    return rows


#: Symbols this desk can actually replay. A certificate for anything else cannot enrol, ever.
_UNIVERSE = Path(__file__).resolve().parent.parent / "desks" / "mt5" / "data" / "universe"


def tradeable_symbols() -> set[str]:
    """Registry symbols with bars on disk -- the set enrolment can draw a clock from.

    Read from BOTH the registry and the parquet directory because either alone is a lie: a
    registry row with no bars cannot be replayed, and bars for a symbol the registry dropped
    are not tradeable. Empty means "could not read", never "nothing is tradeable" -- the caller
    treats an empty set as no opinion rather than condemning every certificate (L1.28a).
    """
    syms: set[str] = set()
    with contextlib.suppress(OSError, ValueError):
        reg = json.loads((_UNIVERSE / "universe.json").read_text("utf-8"))
        syms |= set(reg) if isinstance(reg, dict) else {
            str(r.get("symbol")) for r in reg if isinstance(r, dict)}
    with contextlib.suppress(OSError):
        syms |= {p.stem.removesuffix("_H1") for p in _UNIVERSE.glob("*_H1.parquet")}
    return {s for s in syms if s}


def main() -> int:
    now = datetime.now(tz=UTC)
    certs = (read(CERTS) or {}).get("survivors") or {}
    tradeable = tradeable_symbols()
    rows = forward_rows()
    live_rows = {k: v for k, v in rows.items() if not _is_terminal(v.get("status"))}
    findings: list[str] = []

    # 1. certified but never put on a clock -----------------------------------------------
    for name, cert in certs.items():
        spec = cert.get("shadow_spec") or {}
        sym = spec.get("symbol") or ""
        sel = spec.get("selector") or ""
        # a clock counts if any forward row names this symbol+selector, however keyed
        matching = [k for k in live_rows if sym and sym in k and (not sel or sel in k)]
        enrolled = bool(matching)
        if enrolled:
            # ENROLLED AND STARVED IS ITS OWN FINDING. A row whose status is BLOCKED_* exists
            # because the forward engine tried and could not evaluate it (no bars from the
            # terminal, runtime inputs missing, an evaluation error). That is still forward
            # evidence not collected, and the row carries the cure; reporting it as "enrolled"
            # would hide exactly the certificates that need a hand.
            blocked = [k for k in matching
                       if str(live_rows[k].get("status") or "").upper().startswith("BLOCKED")]
            if blocked and len(blocked) == len(matching):
                k = blocked[0]
                findings.append(
                    f"CERTIFIED-BLOCKED: {name} is on a clock that cannot accrue -- "
                    f"{live_rows[k].get('status')}: "
                    f"{live_rows[k].get('last_error') or 'no reason recorded'}. The certificate "
                    f"stands; the cure is on the trading box (bars, inputs), not in the gate.")
            continue
        # The external gauntlet stamps `gated_at`; older writers used `certified_at` / `at`.
        stamp = (cert.get("certified_at") or cert.get("gated_at") or cert.get("at") or "")
        age_h = 999.0
        with contextlib.suppress(ValueError):
            age_h = (now - datetime.fromisoformat(stamp)).total_seconds() / 3600
        # A CERTIFICATE FOR A SYMBOL THE DESK CANNOT REPLAY IS NOT "WAITING TO ENROL".
        # Measured 2026-09-01: six `external.AFG.*` certificates had passed all ten gates for a
        # symbol with no AFG_H1.parquet and no registry row -- AFG has never appeared in this
        # registry in any commit. They reported CERTIFIED-NOT-ENROLLED every 30 minutes forever,
        # and the message told the reader to wait for an enrolment that can never happen. The
        # cause is upstream (the external backtest certifies on a wider symbol set than the desk
        # can trade), and naming it is what makes the finding actionable instead of noise.
        # An empty `tradeable` means the universe was unreadable, which is no opinion, not a
        # licence to condemn every certificate.
        if tradeable and sym and sym not in tradeable:
            findings.append(
                f"CERTIFIED-UNTRADEABLE: {name} passed all ten gates on symbol {sym!r}, which "
                f"is absent from the universe registry AND has no {sym}_H1.parquet. It can "
                f"never enrol a forward clock, so this is not a same-day lag -- either the "
                f"symbol is restored to the universe or the certificate is retired. A gate that "
                f"cannot be cashed is not a survivor (L1.49).")
            continue
        if age_h > ENROL_GRACE_HOURS:
            findings.append(
                f"CERTIFIED-NOT-ENROLLED: {name} passed all ten gates "
                f"{format(age_h, '.0f') if age_h < 999 else 'an unknown number of'} hours ago and has "
                f"no forward clock. Same-day law: certification and enrolment are one act -- "
                f"every hour here is forward evidence permanently not collected.")

    # 2. clocks with no pre-registration stamp --------------------------------------------
    # ANY LIVE CLOCK, NOT JUST `ACTIVE`. The first cut of this check tested `status == "ACTIVE"`
    # and reported a clean desk -- because on THIS box all 36 rows read QUARANTINED_UNCERTIFIED
    # while the same 36 rows on the desk box read ACTIVE. A fence whose green depends on which
    # machine it runs on is not a fence (L1.43). Terminal verdicts are excluded; everything else
    # is a clock still counting and must carry its stamp.
    unstamped = [k for k, v in rows.items()
                 if not _is_terminal(v.get("status")) and not v.get("forward_start")]
    if unstamped:
        findings.append(
            f"UNSTAMPED-CLOCK: {len(unstamped)} active forward row(s) carry no `forward_start`, "
            f"so their day count runs from the first trade ever taken rather than from "
            f"pre-registration -- evidence gathered during selection is being counted as "
            f"forward evidence. Rows: {', '.join(sorted(unstamped)[:6])}"
            + (" ..." if len(unstamped) > 6 else ""))

    # 3b. NEVER IDLE (principal 2026-08-26: "all work n accumulate trades never idle"). A clock
    # that has not been REFRESHED recently is idle even if it holds trades: the engine replays
    # on every shadow cycle (15 min), so a row whose state is hours old means the cycle is
    # erroring, the task is dead, or the engine skipped it. Measured tonight: shadow_cycle had
    # been exiting 1 every 15 minutes on a PermissionError, and a once-per-day guard in the
    # engine had been making 15-minute cycles no-ops.
    stale_rows = []
    for key, val in rows.items():
        if _is_terminal(val.get("status")):
            continue
        stamp = val.get("last_attempt_at") or val.get("updated_at") or val.get("last_source_bar")
        if not stamp:
            continue
        try:
            age_h = (now - datetime.fromisoformat(str(stamp))).total_seconds() / 3600
        except ValueError:
            continue
        if age_h > IDLE_HOURS:
            stale_rows.append(f"{key} ({age_h:.1f}h)")
    if stale_rows:
        findings.append(
            f"IDLE-CLOCK: {len(stale_rows)} live clock(s) have not been refreshed in over "
            f"{IDLE_HOURS}h -- the shadow cycle replays every 15 minutes, so this means the "
            f"cycle is failing or the engine is skipping them. Evidence stops accruing while "
            f"the day counter keeps running, which is the worst combination: the clock matures "
            f"on stale data. Rows: {', '.join(sorted(stale_rows)[:6])}"
            + (" ..." if len(stale_rows) > 6 else ""))

    # 3. enrolled and silent ---------------------------------------------------------------
    for key, val in rows.items():
        if _is_terminal(val.get("status")):
            continue
        # DERIVED from the pre-registration stamp, never read back from `days_active`: that
        # stored field was computed from the first trade ever taken on rows written before
        # 2026-08-26, so it both invented silence (a fresh clock reading day 9) and hid it.
        days = forward_days(val, now) or 0
        if days >= SILENT_DAYS and int(val.get("n") or 0) == 0:
            findings.append(
                f"SILENT-SLEEVE: {key} has been on the forward clock {days} days and has taken "
                f"0 trades. It will reach the verdict with nothing to judge -- this is a firing "
                f"defect (signal, data feed, or session filter), not patience.")

    # 4. a stored day count that outruns its own stamp -----------------------------------
    # The promote lanes gate on `days_active >= 14`. A row carrying the pre-correction number
    # would satisfy a forward window it never served, which is the one thing the back half of
    # this pipeline exists to prevent. Report it where the fence already looks.
    overstated = overstated_rows(live_rows, now)
    if overstated:
        worst = max(overstated.values(), key=lambda v: v["overstated_by"])
        findings.append(
            f"CLOCK-OVERSTATED: {len(overstated)} live clock(s) store a `days_active` larger "
            f"than their own `forward_start` allows -- worst by {worst['overstated_by']} day(s) "
            f"(stored {worst['stored']}, derived {worst['derived']}). A promote lane reading the "
            f"stored field would clear a 14-day window the sleeve has not served. Rows: "
            + ", ".join(sorted(overstated)[:6]) + (" ..." if len(overstated) > 6 else ""))

    REPORT.write_text(json.dumps(
        {"checked_at": now.isoformat(timespec="seconds"),
         "certificates": len(certs), "forward_clocks": len(live_rows),
         "retired_rows_preserved": len(rows) - len(live_rows),
         "unstamped": len(unstamped), "findings": findings}, indent=1), "utf-8")

    if not findings:
        if ALARM.exists():
            ALARM.unlink()
        print(f"same-day pipeline: ok ({len(certs)} certificate(s), "
              f"{len(live_rows)} live forward clock(s), "
              f"{len(rows) - len(live_rows)} retired row(s) preserved)")
        return 0

    body = (f"SAME-DAY PIPELINE BREACH {now.isoformat(timespec='seconds')}\n\n"
            + "\n".join(f"  - {f}" for f in findings) + "\n")
    ALARM.write_text(body, "utf-8")
    print(body)
    request_repair("same-day pipeline breach")
    return 1


if __name__ == "__main__":
    sys.exit(main())
