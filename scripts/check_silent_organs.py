#!/usr/bin/env python3
"""EVERY SILENT ORGAN, BY NAME, AND A FENCE THAT TURNS RED ON A NEW ONE.

THE PRINCIPAL'S STANDING ORDER: eliminate silent research organs to 100%, every day.

WHY A PER-ORGAN LIST, NOT A NUMBER. The CRO noon pass of 2026-09-30 read "101 silent scheduled
failures (71 NOT_SCHEDULED)" off `tier1_scorecard`, which sums two counters: process_health's
FAILING+NOT_SCHEDULED and the hourly cycle's LEG_FAILED/TIMEOUT legs. A sum cannot be triaged --
nobody can act on 101 -- and it hid its own largest defect: the contract table held exactly 71
organs that day, and exactly 71 were NOT_SCHEDULED, because a scheduler read that returned
nothing was joined as "no organ is scheduled". Named rows would have shown the hourly cycle
itself on that list while it was writing the ledger the review read.

WHAT IT READS, both written by organs that already run:

    desks/mt5/reports/process_health.json   every scheduled task and contract (MT5-ProcessHealth)
    desks/mt5/data/sync_marker.json         every hourly-cycle leg's last outcome (MT5-Hourly)

A task row is SILENT when its verdict is NOT_SCHEDULED, FAILING, NO_ARTIFACT or STALE. A leg is
SILENT when it raised (LEG_FAILED), was killed at its cap (a `timeout_s` with no exit code, which
`_producer` returns WITHOUT a status field -- so the scorecard's status-only count missed every
one of them), or its script is MISSING.

THE FENCE. The previous reading is this organ's own artifact. An organ silent now and not silent
then is NEW; any NEW organ turns the fence RED and the process exits 2. An unreadable, stale or
existence-only input turns it UNMEASURED and the process exits 3. NEITHER is a declared verdict
in `hourly_cycle.VERDICT_EXITS` any more (audit R2, 2026-09-30): a declared verdict records as
`verdict_exit=2`, which every streak and completion reader counts as ok, so a RED fence paged
nobody. Both exits now record as `exit_code=N`, and two readers page on the artifact itself:
`box_heartbeat.py` (MT5-BoxHeartbeat, every 5 min, pages through `alert_channels.send_all`) and
`issue_board.silent_organ_issues` (the hourly board and the dashboard). Silence that persists
stays AMBER with its streak counted, so a standing defect never goes quiet by becoming familiar.
An organ that recovers is listed under `cleared`.

UNMEASURED IS NEVER ZERO (L1.28a). A missing input is named. So is a STALE one: an input older
than `INPUT_MAX_AGE_MIN` is a reading of a machine that has stopped, not of this hour, and a probe
fed 14-day-old inputs read GREEN before this rule. A scheduler reading that only LISTED the task
directory (`existence_only`, the schtasks-timeout fallback) proves which tasks exist and nothing
about how they ran, so it is unread here. A leg recorded as SKIPPED, SKIPPED_BY_PLAN, ROTATED_OUT
or UNMEASURED -- or with no record at all -- is an UNMEASURED row, never a pass.

    python scripts/check_silent_organs.py            # write the artifact, exit 2 on a new one
    python scripts/check_silent_organs.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
PROCESS_HEALTH = DESK / "reports" / "process_health.json"
SYNC_MARKER = DESK / "data" / "sync_marker.json"
OUT = DESK / "reports" / "SILENT_ORGANS.json"
#: The watchdog's escalations (ops/never_stale.py). It pages nobody on its own -- nothing read
#: NEVER_STALE.json -- so its NEEDS_HUMAN rows are carried here as fence items (audit R2).
NEVER_STALE = DESK / "reports" / "NEVER_STALE.json"

SILENT_TASK_VERDICTS = frozenset({"NOT_SCHEDULED", "FAILING", "NO_ARTIFACT", "STALE"})
SILENT_LEG_STATUSES = frozenset({"LEG_FAILED", "TIMEOUT", "MISSING"})
#: A leg outcome that says the leg did not run (or could not judge) this pass: nobody looked.
UNMEASURED_LEG_STATUSES = frozenset({"UNMEASURED", "SKIPPED", "SKIPPED_BY_PLAN", "ROTATED_OUT"})
#: The fence's own leg. Its exit code is this artifact's verdict, not a fresh silence to fence on
#: (counting it would make every RED fence re-announce itself the next hour).
SELF_LEG = "silent_organs"
#: How old an input may be before its reading is a reading of the past. process_health runs every
#: 60 min (ops/organ_contract.py MT5-ProcessHealth); the hourly cycle's marker is rewritten each
#: pass, and a heavy pass may run past two hours. Twice the cadence, and the marker's worst pass.
INPUT_MAX_AGE_MIN = {"process_health": 120.0, "sync_marker": 180.0}
#: Exit code for "a new organ went silent" (and for an escalation nothing else pages).
RED_EXIT = 2
#: Exit code for "the fence could not see": an unreadable, stale or existence-only input.
UNMEASURED_EXIT = 3


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _age_min(path: Path, now: datetime) -> float | None:
    try:
        return round((now.timestamp() - path.stat().st_mtime) / 60.0, 1)
    except OSError:
        return None


def _stamp_age_min(stamp: Any, path: Path, now: datetime) -> float | None:
    """Minutes since the input was WRITTEN BY ITS PRODUCER: the content stamp when it parses
    (a copy or a checkout rewrites mtime, never the stamp), else the file's mtime."""
    if isinstance(stamp, str) and stamp:
        try:
            t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=UTC)
            return round((now - t).total_seconds() / 60.0, 1)
        except ValueError:
            pass
    return _age_min(path, now)


def _declared_verdict_exits() -> dict[str, tuple[int, ...]]:
    """hourly_cycle.VERDICT_EXITS, read from its source (importing the cycle would start a pass's
    worth of imports). Unreadable -> {} -- every non-zero exit is then a failure, the safe side."""
    import ast
    try:
        tree = ast.parse((DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return {}
    for node in tree.body:
        target = (node.target if isinstance(node, ast.AnnAssign) else
                  node.targets[0] if isinstance(node, ast.Assign) and node.targets else None)
        if isinstance(target, ast.Name) and target.id == "VERDICT_EXITS" and node.value:
            try:
                val = ast.literal_eval(node.value)
            except ValueError:
                return {}
            return {str(k): tuple(v) for k, v in val.items()} if isinstance(val, dict) else {}
    return {}


def task_silences(doc: Any) -> list[dict[str, Any]]:
    """Silent rows of process_health, one per organ."""
    out: list[dict[str, Any]] = []
    for r in (doc.get("processes") if isinstance(doc, dict) else None) or []:
        if not isinstance(r, dict):
            continue
        verdict = str(r.get("verdict") or "")
        if verdict in SILENT_TASK_VERDICTS:
            out.append({"organ": str(r.get("name") or ""), "source": "task",
                        "verdict": verdict, "why": str(r.get("why") or "")[:240],
                        "artifact": r.get("artifact")})
    return out


def escalation_silences(doc: Any) -> list[dict[str, Any]]:
    """never_stale's NEEDS_HUMAN rows that no task row already names -- each one a RED item."""
    out: list[dict[str, Any]] = []
    for e in (doc.get("escalated") if isinstance(doc, dict) else None) or []:
        if not isinstance(e, dict):
            continue
        out.append({"organ": f"escalated:{e.get('task') or '?'}", "source": "escalation",
                    "verdict": f"NEEDS_HUMAN:{e.get('verdict') or '?'}",
                    "why": str(e.get("diagnosis") or e.get("why") or "")[:240],
                    "artifact": None})
    return out


def leg_verdict(leg: Any, name: str = "",
                verdict_exits: dict[str, tuple[int, ...]] | None = None) -> tuple[str, str] | None:
    """(verdict, why) for a silent or UNMEASURED leg outcome, or None when the leg ran clean.

    A leg with no record (None) and a leg that reports it did not run -- SKIPPED, SKIPPED_BY_PLAN,
    ROTATED_OUT, UNMEASURED -- read UNMEASURED: this pass holds no measurement of it (audit,
    2026-09-30). A non-zero exit that the leg has not declared a verdict is a failure, exactly as
    the cycle's own ledger records it (`exit_code=N`)."""
    if leg is None:
        return "UNMEASURED", "no record of this leg in the pass: nobody looked"
    if not isinstance(leg, dict):
        return None
    status = str(leg.get("status") or "").upper()
    if leg.get("error"):
        return "LEG_FAILED", str(leg.get("error"))[:240]
    if status in SILENT_LEG_STATUSES:
        return status, str(leg.get("why") or leg.get("note") or "")[:240]
    if leg.get("timeout_s") and leg.get("exit_code") is None:
        return "TIMEOUT", (f"killed at its {leg.get('timeout_s')}s cap before it finished; "
                           "whatever it had not written is lost for the hour")
    if status in UNMEASURED_LEG_STATUSES:
        return "UNMEASURED", (f"{status}: did not run or could not judge this pass -- "
                              + str(leg.get("why") or leg.get("plan") or ""))[:240]
    code = leg.get("exit_code")
    if isinstance(code, int) and code != 0 and name != SELF_LEG \
            and code not in (verdict_exits or {}).get(name, ()):
        return "EXIT_NONZERO", (f"exit_code={code}, not a declared verdict exit -- "
                                + str(leg.get("tail") or "").strip()[-160:])
    return None


def leg_silences(marker: Any) -> list[dict[str, Any]]:
    """Silent and UNMEASURED legs of the last completed hourly pass, one per leg."""
    out: list[dict[str, Any]] = []
    if not isinstance(marker, dict):
        return out
    exits = _declared_verdict_exits()
    for name, leg in sorted(marker.items()):
        if name == "last_cycle":
            continue
        v = leg_verdict(leg, name, exits)
        if v:
            row = {"organ": f"leg:{name}", "source": "leg", "verdict": v[0], "why": v[1],
                   "artifact": None}
            if v[0] == "UNMEASURED":
                row["unread"] = True
            out.append(row)
    return out


def build(*, health_path: Path | None = None, marker_path: Path | None = None,
          previous: Any = None, now: datetime | None = None,
          never_stale_path: Path | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    health_path = health_path or PROCESS_HEALTH
    marker_path = marker_path or SYNC_MARKER
    health, marker = _read(health_path), _read(marker_path)
    unmeasured: list[dict[str, str]] = []
    # A STALE INPUT IS AN UNREAD ONE (audit 2026-09-30: 14-day-old inputs read GREEN). Its rows
    # describe a pass that ended days ago, so they are neither counted nor allowed to clear.
    ages = {"process_health": _stamp_age_min((health or {}).get("at") if isinstance(health, dict)
                                             else None, health_path, now),
            "sync_marker": _stamp_age_min((marker or {}).get("last_cycle")
                                          if isinstance(marker, dict) else None, marker_path, now)}
    stale = {k: a for k, a in ages.items() if a is not None and a > INPUT_MAX_AGE_MIN[k]}
    if not isinstance(health, dict):
        unmeasured.append({"what": "scheduled tasks and contracts",
                           "why": f"{health_path.name} is absent or unreadable -- "
                                  "ops/process_health.py has not run on this host"})
    elif "process_health" in stale:
        unmeasured.append({"what": "scheduled tasks and contracts",
                           "why": f"{health_path.name} is STALE: {stale['process_health']:.0f} "
                                  f"min old against {INPUT_MAX_AGE_MIN['process_health']:.0f} -- "
                                  "MT5-ProcessHealth has stopped writing it"})
        health = None
    elif isinstance(health.get("scheduler"), dict) and not health["scheduler"].get("read"):
        # EXISTENCE-ONLY IS UNREAD (audit 2026-09-30). The schtasks-timeout fallback lists the
        # task directory: it proves a task exists, never how its last run ended, so FAILING is
        # unmeasurable and the fence must say so rather than read the listing as a measurement.
        sch = health["scheduler"]
        unmeasured.append({"what": "scheduling verdicts (NOT_SCHEDULED / FAILING)",
                           "why": ("process_health could not read the scheduler"
                                   + (" (existence-only: the task directory was listed, which "
                                      "proves a task exists and not how it ran)"
                                      if sch.get("existence_only") else "")
                                   + ": " + str(sch.get("why") or ""))})
    if not isinstance(marker, dict):
        unmeasured.append({"what": "hourly-cycle legs",
                           "why": f"{marker_path.name} is absent or unreadable -- the hourly "
                                  "cycle has not completed a pass on this host"})
    elif "sync_marker" in stale:
        unmeasured.append({"what": "hourly-cycle legs",
                           "why": f"{marker_path.name} is STALE: {stale['sync_marker']:.0f} min "
                                  f"old against {INPUT_MAX_AGE_MIN['sync_marker']:.0f} -- the "
                                  "hourly cycle has not completed a pass since"})
        marker = None

    health_unread = not isinstance(health, dict)
    scheduler_unread = (not health_unread and isinstance(health.get("scheduler"), dict)
                        and not health["scheduler"].get("read"))
    marker_unread = not isinstance(marker, dict)
    # What each organ reads as NOW in process_health, so a row whose verdict went UNMEASURED can
    # be told apart from a row that recovered.
    now_task_verdict = {str(r.get("name") or ""): str(r.get("verdict") or "")
                        for r in ((health or {}).get("processes") or [] if not health_unread
                                  else []) if isinstance(r, dict)}
    silent = task_silences(health) + leg_silences(marker)
    unread_legs = sorted(r["organ"] for r in silent if r.get("unread"))
    if unread_legs:
        unmeasured.append({"what": f"{len(unread_legs)} hourly-cycle leg(s)",
                           "why": "no measurement this pass (SKIPPED / SKIPPED_BY_PLAN / "
                                  "ROTATED_OUT / UNMEASURED / no record): "
                                  + ", ".join(unread_legs[:12])
                                  + (" ..." if len(unread_legs) > 12 else "")})
    # An escalation about a task already on the list is the same organ twice; only the ones no
    # other row names (the scheduler itself, a capital fault) are added.
    named = {r["organ"] for r in silent}
    watchdog = _read(never_stale_path or NEVER_STALE)
    silent += [e for e in escalation_silences(watchdog)
               if e["organ"].split(":", 1)[1] not in named]
    if isinstance(watchdog, dict) and watchdog.get("status") == "UNMEASURED":
        # The watchdog refused to judge (its health reading was absent or stale), so it escalated
        # nothing -- an empty escalation list that means "nobody looked", not "nothing wrong".
        unmeasured.append({"what": "watchdog escalations (NEVER_STALE)",
                           "why": str(watchdog.get("why") or "never_stale reported UNMEASURED")})
    prev_rows: dict[str, dict[str, Any]] = {}
    if isinstance(previous, dict):
        prev_rows = {str(r.get("organ")): r for r in previous.get("organs") or []
                     if isinstance(r, dict)}
    # ANY previous reading is a baseline, including an UNMEASURED one: its rows are what was
    # known to be silent, and a box whose scheduler never answers must still be able to go RED
    # on a leg that newly failed.
    has_baseline = isinstance(previous, dict) and isinstance(previous.get("organs"), list)
    stamp = now.isoformat(timespec="seconds")
    new: list[str] = []
    for row in silent:
        before = prev_rows.get(row["organ"])
        row["first_seen"] = (before or {}).get("first_seen") or stamp
        row["passes_silent"] = int((before or {}).get("passes_silent") or 0) + 1
        # NEW means newly KNOWN silent: absent before, or only UNMEASURED before (a failure seen
        # for the first time after an unread pass is still a first sighting). An UNMEASURED row
        # is never new -- it turns the fence UNMEASURED, not RED.
        if has_baseline and row["verdict"] != "UNMEASURED" and (
                before is None or str(before.get("verdict") or "") == "UNMEASURED"):
            new.append(row["organ"])
    now_names = {r["organ"] for r in silent}

    def _unmeasured_now(prev: dict[str, Any]) -> bool:
        """A previously silent row whose source could not be read this pass is NOT cleared --
        nobody looked. (Audit R1: a scheduler timeout marked three NOT_SCHEDULED rows cleared.)"""
        src = str(prev.get("source") or "")
        if src == "leg":
            return marker_unread
        if src == "task":
            if health_unread:
                return True
            verdict = now_task_verdict.get(str(prev.get("organ") or ""))
            return verdict in (None, "UNMEASURED") and (scheduler_unread or verdict is not None)
        return src != "escalation"

    cleared: list[str] = []
    for name, prev in sorted(prev_rows.items()):
        if name in now_names:
            continue
        if _unmeasured_now(prev):
            # CARRIED FORWARD with its streak and first-seen intact (audit R1b): the organ is
            # still on the list, now marked UNMEASURED, until a reading says otherwise.
            # passes_silent COUNTS THIS PASS TOO (audit 2026-09-30): the streak is how long the
            # organ has been on the list, and an unread pass does not take it off.
            silent.append({**prev, "verdict": "UNMEASURED", "carried": True,
                           "passes_silent": int(prev.get("passes_silent") or 0) + 1,
                           "last_verdict": prev.get("last_verdict") or prev.get("verdict"),
                           "why": "silent at the last reading; its source was unreadable this "
                                  "pass, so it cannot be called cleared"})
        else:
            cleared.append(name)

    by_verdict: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for r in silent:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1

    escalated = [r["organ"] for r in silent if r["source"] == "escalation"]
    # THE FENCE is separate from the STATUS. Status says what is known (UNMEASURED whenever any
    # source was unreadable -- audit R1); the fence says whether a person must act now: a NEW
    # silent organ, or a watchdog escalation nothing else pages (audit R2).
    fence = "RED" if (new or escalated) else ("UNMEASURED" if unmeasured else
                                             ("AMBER" if silent else "GREEN"))
    if unmeasured:
        status = "UNMEASURED"
    elif new or escalated:
        status = "RED"
    elif silent:
        status = "AMBER"
    else:
        status = "GREEN"
    silent.sort(key=lambda r: (r["organ"] not in new, -r["passes_silent"], r["organ"]))
    return {
        "measured_at": stamp,
        "at": stamp,
        "status": status,
        "fence": fence,
        "escalated": escalated,
        # A count is only a count when every source was read; otherwise it is a floor.
        "n_silent": len(silent) if not unmeasured else None,
        "n_silent_floor": sum(1 for r in silent if not r.get("unread")),
        "n_unmeasured_legs": len(unread_legs),
        "by_verdict": by_verdict,
        "by_source": by_source,
        "new_silent": sorted(new),
        "cleared": cleared,
        "baseline": "previous reading of this artifact" if has_baseline else
                    "none -- first reading; the next pass fences against this one",
        "inputs": {
            "process_health": {"path": str(health_path.relative_to(ROOT))
                               if health_path.is_relative_to(ROOT) else str(health_path),
                               "age_min": _age_min(health_path, now),
                               "at": health.get("at") if isinstance(health, dict) else None},
            "sync_marker": {"path": str(marker_path.relative_to(ROOT))
                            if marker_path.is_relative_to(ROOT) else str(marker_path),
                            "age_min": _age_min(marker_path, now),
                            "at": marker.get("last_cycle") if isinstance(marker, dict) else None},
            "max_age_min": INPUT_MAX_AGE_MIN,
            "stale": stale,
        },
        "unmeasured": unmeasured,
        "organs": silent,
        "rule": ("an organ silent now and not silent in the previous reading is NEW and turns "
                 "the fence RED; persisting silence is AMBER with its streak; UNMEASURED is "
                 "never zero"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(previous=_read(a.out))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    tmp.replace(a.out)
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        n = doc["n_silent"] if doc["n_silent"] is not None else f">={doc['n_silent_floor']}"
        print(f"silent organs: {n}  status {doc['status']}  fence {doc['fence']}  new {len(doc['new_silent'])}  "
              f"cleared {len(doc['cleared'])}  {doc['by_verdict']}")
        for r in doc["organs"]:
            flag = "NEW " if r["organ"] in doc["new_silent"] else "    "
            print(f"  {flag}{r['verdict']:<14}{r['organ']:<44}x{r['passes_silent']:<4}"
                  f"{r['why'][:70]}")
        for u in doc["unmeasured"]:
            print(f"  UNMEASURED {u['what']}: {u['why']}")
        print(f"-> {a.out}")
    return (RED_EXIT if doc["fence"] == "RED" else
            UNMEASURED_EXIT if doc["fence"] == "UNMEASURED" else 0)


if __name__ == "__main__":
    sys.exit(main())
