#!/usr/bin/env python3
"""IS THE DESK ACTUALLY RUNNING? -- production, not process status.

WHY THIS EXISTS, AND IT IS THE SAME LESSON THREE TIMES. `systemctl is-active` proves a process is
alive, never that it PRODUCED. This desk has been burned by that exact gap repeatedly: a panel that
exited clean and appended no verdict, an organ whose timer fired for weeks against a crashed
script, a watchdog that died on 2026-07-11 and left the pager silent and the forward clocks frozen
for ELEVEN AND A HALF DAYS while everything looked scheduled.

The failure is always the same shape -- the launcher is fine and the artifact is stale -- so the
question this asks is never "is it running" but "when did it last WRITE something".

AND THE GAP THAT PROMPTED IT. Auditing the repository's own deploy surface found that the desk's
main loop had no launcher at all: nothing started the cadence engine, the pager, the process
supervisor, or the Tier-3 ruin rail. Recorders and diggers had units; the organs that keep the
desk ALIVE did not. That is invisible to any check that only looks at the units which exist, so
this walks the FLOORS -- the freshness contract run_cadence itself enforces -- and asks of each
one: what writes this, what starts that, and when did it last happen?

FIVE PRODUCTION VERDICTS, AND THE SECOND ONE IS THE POINT:
  RUNNING    the artifact exists and is inside its floor
  STALE      it exists and is past its floor -- scheduled but not producing, the class above
  FAILED     it is fresh but records an unsuccessful production cycle
  INVALID    it cannot prove when or what the producer did
  MISSING    it has never been written, or nothing in the repository starts its producer

Exit code is 1 unless every required artifact is RUNNING, so this gates a deploy rather than
decorating it.
Read-only. No keys, no order paths.
"""
from __future__ import annotations

import argparse
import getpass
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = ROOT / "data/deployment_verification.json"

#: artifact -> (max age hours, the unit that must produce it, what it means when it is stale).
#: The ages mirror run_cadence's own _FLOORS_S0 where they overlap; the rest are the cadence of
#: the organ that writes them. Nothing here is aspirational -- every entry names a producer that
#: exists in the repository.
FLOORS: dict[str, tuple[float, str, str]] = {
    "data/.last_alerts.json": (
        1.0, "quant-alerts.timer",
        "the pager has not ticked -- the desk cannot tell you anything is wrong"),
    "data/cadence_state.json": (
        2.0, "quant-cadence.timer",
        "the cadence engine has not run: the panel, the moat screen, survivor promotion and the "
        "forward-clock review all hang off this tick, and every one of them is owed"),
    # THE TWO MOAT FLOORS WERE REMOVED 2026-09-05 (universe mandate). `data/moat_mine.json` and
    # `data/moat_screen.json` were held to 6h floors by quant-moat-miner.service and
    # quant-moat-screen.service. The miner (scripts/mine_moat.py), the screen
    # (scripts/screen_moat.py) and both unit files went with the crypto-exchange desk whose
    # self-recorded L2 tape they read.
    #
    # This is the one file where a stale entry does REAL damage rather than sitting inert: the
    # header above promises "every entry names a producer that exists in the repository", and a
    # floor whose producer is gone reports MISSING on every deploy for ever -- exit code 1, a
    # deploy gate that can never go green, and therefore a gate somebody switches off.
    "data/max_audit_report.json": (
        30.0, "quant-daily-max.timer",
        "the daily maximisation sweep has not run, so nothing is auditing the desk"),
    "data/intelligence/midnight_codex_status.json": (
        30.0, "quant-midnight-frontier.timer",
        "the daily Codex controller has not completed the deterministic frontier, checkpointed "
        "its work and handed the same state back to Claude"),
}

MIDNIGHT_STATUS = "data/intelligence/midnight_codex_status.json"
MIDNIGHT_SUCCESS = "CHECKPOINTED_FOR_CLAUDE"

#: Tape roots: absence here is the upstream blocker every other moat defect resolves to.
TAPE = ("data/moat",)

#: Units that must be ENABLED for the above to be possible at all. `quant-deadman.service` is
#: deliberately absent: it moves funds and is Tier-3, so it is reported separately and never
#: required by an automated check.
REQUIRED_UNITS = (
    # CRYPTO RECORDERS RETIRED 2026-08-17. Irish retail rules make the crypto leg spot-only,
    # the desk trades MT5, and these three had grown to 19GB on a 37GB disk while feeding
    # nothing that trades. Their obligation transferred to mt5desk.tape -- see constitution
    # section 224. Expecting them here reported a healthy desk as broken.

    # quant-moat-miner.service and quant-moat-screen.service removed 2026-09-05 with the moat
    # pipeline, for the same reason the recorders were removed above: requiring a unit that no
    # longer exists reports a healthy desk as broken.
    "quant-watchdog.timer", "quant-alerts.timer", "quant-cadence.timer", "quant-daily-max.timer",
    "quant-midnight-frontier.timer",
)

# The midnight timer may be installed as a machine unit by root or as a persistent user unit by
# the quant account. A user unit is not persistent merely because `is-enabled` says enabled:
# without loginctl linger it disappears when the last login session closes and cannot fire at
# midnight. Other critical units remain system-scope only.
EITHER_SCOPE_UNITS = frozenset({"quant-midnight-frontier.timer"})

TIER3 = ("quant-deadman.service",)


def _now_epoch() -> float:
    return time.time()


def _age_h(p: Path) -> float | None:
    try:
        return (_now_epoch() - p.stat().st_mtime) / 3600.0
    except OSError:
        return None


def _systemctl(*args: str) -> str:
    try:
        r = subprocess.run(["systemctl", *args], capture_output=True, text=True, timeout=20,
                           check=False)
        return (r.stdout or r.stderr or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _loginctl(*args: str) -> str:
    try:
        r = subprocess.run(["loginctl", *args], capture_output=True, text=True, timeout=20,
                           check=False)
        return (r.stdout or r.stderr or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _user_linger_state() -> str:
    """Return loginctl's durable-user-manager state for the account running this verifier."""
    return _loginctl(
        "show-user", getpass.getuser(), "--property=Linger", "--value"
    ).strip().lower()


def _enabled(value: str) -> bool:
    return value.startswith("enabled")


def _zero_exit_code(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def _midnight_status_health(p: Path) -> tuple[float | None, str | None]:
    """Return embedded event age and any semantic failure in the midnight status artifact.

    Git checkout, restore and deployment can all give an old payload a fresh filesystem mtime.
    The controller writes an authoritative ``updated_at`` event time, so using mtime here would
    certify a cycle that never ran on this host.
    """
    try:
        payload = json.loads(p.read_text("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"unreadable status JSON ({type(exc).__name__})"
    if not isinstance(payload, dict):
        return None, "status JSON must be an object"

    raw_stamp = payload.get("updated_at")
    if not isinstance(raw_stamp, str) or not raw_stamp.strip():
        return None, "status has no authoritative updated_at timestamp"
    try:
        stamp = datetime.fromisoformat(raw_stamp.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("timestamp has no timezone")
        age_h = (_now_epoch() - stamp.astimezone(UTC).timestamp()) / 3600.0
    except (OverflowError, TypeError, ValueError) as exc:
        return None, f"invalid updated_at timestamp ({exc})"
    if age_h < -(5.0 / 60.0):
        return None, f"updated_at is {-age_h:.2f}h in the future"
    age_h = max(0.0, age_h)

    failures = []
    status = payload.get("status")
    if status != MIDNIGHT_SUCCESS:
        failures.append(f"status={status!r}, expected {MIDNIGHT_SUCCESS!r}")
    if not _zero_exit_code(payload.get("controller_rc")):
        failures.append(f"controller_rc={payload.get('controller_rc')!r}, expected 0")
    if not _zero_exit_code(payload.get("pipeline_rc")):
        failures.append(f"pipeline_rc={payload.get('pipeline_rc')!r}, expected 0")
    if payload.get("persistent_workers_controller_independent") is not True:
        failures.append("persistent_workers_controller_independent is not true")
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        failures.append("reason is missing")
    return age_h, "; ".join(failures) or None


def check_units() -> list[dict]:
    """Is each unit installed and enabled? Absent systemd (a dev box) reports UNKNOWN, not OK.

    Claiming a clean bill of health on a machine that cannot even answer the question is how a
    verifier becomes decoration.
    """
    have_systemd = bool(_systemctl("--version"))
    out = []
    for unit in REQUIRED_UNITS:
        if not have_systemd:
            out.append({"unit": unit, "state": "UNKNOWN",
                        "why": "no systemd on this host -- run this ON THE VPS"})
            continue
        system_enabled = _systemctl("is-enabled", unit) or "not-found"
        system_active = _systemctl("is-active", unit) or "unknown"
        if unit not in EITHER_SCOPE_UNITS:
            ok = _enabled(system_enabled)
            out.append({"unit": unit, "enabled": system_enabled, "active": system_active,
                        "scope": "system", "state": "OK" if ok else "NOT-ENABLED",
                        "why": "" if ok else (
                            f"systemctl reports {system_enabled!r}. Installed unit files are not "
                            "running units -- `enable --now` is what survives a reboot.")})
            continue

        user_enabled = _systemctl("--user", "is-enabled", unit) or "not-found"
        user_active = _systemctl("--user", "is-active", unit) or "unknown"
        linger = _user_linger_state() if _enabled(user_enabled) else "not-checked"
        system_ok = _enabled(system_enabled) and system_active == "active"
        user_ok = _enabled(user_enabled) and user_active == "active" and linger == "yes"
        ok = system_ok or user_ok
        scope = "system" if system_ok else "user" if user_ok else "none"
        why = ""
        if not ok:
            why = (
                f"system scope reports enabled={system_enabled!r}, active={system_active!r}; "
                f"user scope reports enabled={user_enabled!r}, active={user_active!r}, "
                f"Linger={linger!r}. The timer must be enabled and active either as a system "
                "unit or as a user unit with loginctl linger=yes so it can fire while the quant "
                "user is logged out."
            )
        out.append({
            "unit": unit,
            "enabled": system_enabled if system_ok else user_enabled,
            "active": system_active if system_ok else user_active,
            "scope": scope,
            "system_enabled": system_enabled,
            "system_active": system_active,
            "user_enabled": user_enabled,
            "user_active": user_active,
            "user_linger": linger,
            "state": "OK" if ok else "NOT-ENABLED",
            "why": why,
        })
    for unit in TIER3:
        p = ROOT / "ops" / unit
        st = _systemctl("is-enabled", unit) if have_systemd else ""
        out.append({"unit": unit, "state": "TIER-3", "enabled": st or "unknown",
                    "why": ("the ruin rail. This check NEVER requires it: it moves funds, so "
                            "arming it is the principal's act, not a script's. "
                            + ("unit file present" if p.exists() else "UNIT FILE MISSING"))})
    return out


def check_production() -> list[dict]:
    """The real question: when did each organ last WRITE something?"""
    out = []
    for rel, (max_h, unit, meaning) in sorted(FLOORS.items()):
        p = ROOT / rel
        semantic_failure = None
        if rel == MIDNIGHT_STATUS and p.exists():
            age, semantic_failure = _midnight_status_health(p)
        else:
            age = _age_h(p)
        if age is None:
            state = "INVALID" if p.exists() else "MISSING"
            prefix = semantic_failure or "never written"
            out.append({"artifact": rel, "state": state, "unit": unit, "age_h": None,
                        "floor_h": max_h, "why": f"{prefix}. {meaning}"})
        elif age > max_h:
            semantic_suffix = f" Last result is also unhealthy: {semantic_failure}." \
                if semantic_failure else ""
            out.append({"artifact": rel, "state": "STALE", "unit": unit,
                        "age_h": round(age, 2), "floor_h": max_h,
                        "why": (f"{age:.1f}h old against a {max_h}h floor -- scheduled but not "
                                f"PRODUCING. {meaning}{semantic_suffix}")})
        elif semantic_failure:
            out.append({"artifact": rel, "state": "FAILED", "unit": unit,
                        "age_h": round(age, 2), "floor_h": max_h,
                        "why": (f"fresh status artifact records an unsuccessful cycle: "
                                f"{semantic_failure}. {meaning}")})
        else:
            out.append({"artifact": rel, "state": "RUNNING", "unit": unit,
                        "age_h": round(age, 2), "floor_h": max_h, "why": ""})
    return out


def check_tape() -> list[dict]:
    """Is the archive GROWING? Every moat organ downstream resolves to this one fact."""
    out = []
    for rel in TAPE:
        root = ROOT / rel
        files = list(root.rglob("*.jsonl.gz")) if root.exists() else []
        total = sum(f.stat().st_size for f in files) if files else 0
        newest = max((f.stat().st_mtime for f in files), default=0.0)
        age = (_now_epoch() - newest) / 3600.0 if newest else None
        if not files:
            out.append({"path": rel, "state": "MISSING", "files": 0,
                        "why": ("no tape at all. The recorders are the ONLY thing that writes "
                                "here, and no mining, screening or promotion action closes it. "
                                "This is the upstream blocker every moat defect resolves to.")})
        elif age is not None and age > 2.0:
            out.append({"path": rel, "state": "STALE", "files": len(files),
                        "bytes": total, "newest_age_h": round(age, 2),
                        "why": (f"{len(files)} files but the newest is {age:.1f}h old -- the "
                                "recorders have stopped. Every second unrecorded is permanently "
                                "unbuyable; this is the only cost on the desk money cannot fix "
                                "afterwards.")})
        else:
            out.append({"path": rel, "state": "RUNNING", "files": len(files), "bytes": total,
                        "newest_age_h": round(age, 2) if age is not None else None, "why": ""})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="artifact only, no human output")
    a = ap.parse_args()

    units, production, tape = check_units(), check_production(), check_tape()
    bad_units = [u for u in units if u["state"] == "NOT-ENABLED"]
    bad_prod = [p for p in production if p["state"] != "RUNNING"]
    bad_tape = [t for t in tape if t["state"] in ("MISSING", "STALE")]
    ok = not (bad_units or bad_prod or bad_tape)

    out = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verdict": "DEPLOYED" if ok else "INCOMPLETE",
        "units": units, "production": production, "tape": tape,
        "note": ("PRODUCTION, NOT PROCESS STATUS. `systemctl is-active` proves a process is alive "
                 "and never that it produced -- the failure that left this desk with a silent "
                 "pager and frozen forward clocks for 11.5 days while every timer looked healthy. "
                 "Every check here asks when an artifact was last WRITTEN."),
        "authority": "NONE. Reports. Starts nothing, enables nothing, moves no funds.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    if a.json:
        print(json.dumps(out, indent=1, default=str))
        return 0 if ok else 1

    print(f"deployment: {out['verdict']}")
    print("\n  UNITS")
    for u in units:
        mark = {"OK": "ok  ", "NOT-ENABLED": "FAIL",
                "TIER-3": "t3  ", "UNKNOWN": "?   "}[u["state"]]
        print(f"    [{mark}] {u['unit']:<32} {u.get('enabled', '')}")
        if u["why"] and u["state"] != "OK":
            print(f"            {u['why'][:104]}")
    print("\n  PRODUCTION (when did it last WRITE?)")
    for p in production:
        mark = "ok  " if p["state"] == "RUNNING" else "FAIL"
        age = f"{p['age_h']}h" if p["age_h"] is not None else "never"
        print(f"    [{mark}] {p['artifact']:<32} {age:>9} / {p['floor_h']}h floor")
        if p["why"]:
            print(f"            {p['why'][:104]}")
    print("\n  TAPE")
    for t in tape:
        mark = "ok  " if t["state"] == "RUNNING" else "FAIL"
        print(f"    [{mark}] {t['path']:<32} {t.get('files', 0)} files")
        if t["why"]:
            print(f"            {t['why'][:104]}")
    if ok:
        print("\n  Everything the repository can start is started and PRODUCING.")
    else:
        print(f"\n  {len(bad_units)} unit(s), {len(bad_prod)} artifact(s), {len(bad_tape)} tape "
              "root(s) not right. Fix these before believing any number this desk reports.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
