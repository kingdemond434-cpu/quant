#!/usr/bin/env python3
"""THE JUDGE-COVERAGE FENCE -- every mined family is judged every hour, and the backlog falls.

    "the judge should test 100 percent of what this desk ever mines, every hour, 24/7, always"
    "all families should be hunted, all mechanisms, all unknowns, for maximum breadth"
                                                                  -- the principal, 2026-09-23

WHAT THIS ASSERTS, against `desks/mt5/reports/JUDGE_COVERAGE.json`, which
`research/judge_coverage.py` writes at intake every hour:

  * NO FAMILY IS STARVED.  A family holding unjudged cells and absent from the hour's queue is a
    FAILURE. This is the defect that was measured: the judge re-tested a handful of families
    while `cross_asset_residual` (55,190 mined), `overnight_drift` (26,721) and
    `clock_transition` (20,081) waited. Absence from the queue is not low priority, it is never.
  * THE CARRIED BACKLOG FALLS, PER FAMILY.  Rows already in a family's backlog at the previous
    reading and STILL unjudged now are the carried cohort. A cell leaves it exactly one way -- by
    being judged -- so it can only fall, and a family whose carried count did not fall while it
    held backlog and held quota was starved in fact if not in the queue.
  * THE REMAINDER FOLLOWS THE PUBLISHED RANKING.  The floor is the breadth mandate and is
    covered by the starvation check; the remainder is where the return is, and it is spent
    strictly down expected value per judge-second. A family given remainder while a HIGHER-ranked
    family still held undrained backlog means the allocation stopped following its own ranking --
    which is exactly how a future session would quietly revert this to round-robin with the
    report still claiming value ordering.
  * NO FAMILY'S OLDEST UNJUDGED CELL EXCEEDS ITS OWN WINDOW.  A family's window is the hours its
    own quota needs to drain its own backlog, floored at the hour. A family of 55,190 cells is
    not failed for being large and a family of nine is not excused for being small.

WHY THE RATCHET IS ON THE CARRIED COHORT AND NOT ON RAW BACKLOG. Raw backlog rises whenever the
miners outrun the judge -- which is mining working, and mining is unrestricted by the principal's
standing order. A fence on the raw number would fail the desk for mining faster, would be
unsatisfiable in the direction it was pointed, and would be switched off inside a week; the
coverage-drain fence learned that lesson on a wall clock and it is written down there. The
carried cohort is the part intake actually controls: it is the promise that what the desk already
knew it had mined does not sit unjudged forever.

WHAT THIS FENCE NEVER DOES. It removes no cell, caps no book, shrinks no budget and slows no
miner (GROWTH_GOVERNANCE Rule 1). Its only remedy is ORDER -- and order costs nothing, because
the same rows reach the same judge under the same budget either way.

UNMEASURED IS A VERDICT (L1.28a). On a clean checkout there is no report and no ratchet; this
says UNMEASURED and exits 0, because "this machine has no desk state" is not "a law was broken".
On the box `--require-state` promotes an absent report to a FAILURE -- an organ that was
scheduled and produced nothing is exactly the defect L1.49 names. A pass in which the judge
recorded NO verdicts at all is UNMEASURED for the drain checks rather than a failure: nothing
drained because nothing ran, and that is the gauntlet's clock to answer for, not intake's.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
#: A sweep-to-sweep wobble in the pre-warm failure share below this is noise, not a regression.
PREWARM_TOLERANCE = 0.02
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "JUDGE_COVERAGE.json"
#: Consecutive NOT-OK release-file passes (unreadable, torn, vanished, refused write, evidence
#: aside) before FAIL; equal to `judge_coverage.RELEASE_NOT_OK_MAX_PASSES`.
RELEASE_ASIDE_MAX_PASSES = 3
RATCHET = DESK / "data" / "judge_backlog_ratchet.json"
AUDIT = DESK / "reports" / "judge_coverage_fence.json"
#: The hourly `judge_alive` leg's own verdict (`--liveness`), so it never overwrites the
#: coverage fence's audit.
LIVENESS_AUDIT = DESK / "reports" / "judge_alive_fence.json"
#: A FAIL PAGES (audit of 7cf2ece90): `research/issue_board.py` collects alarm files from the
#: repo's `data/`; this one exists exactly while the hourly judge_alive verdict is FAIL.
LIVENESS_ALARM = ROOT / "data" / "JUDGE_ALIVE_ALARM.txt"


def sync_alarm(doc: Mapping[str, Any], path: Path | None = None) -> None:
    """Raise the alarm file on a FAIL; clear it on PASS (amber included). UNMEASURED leaves it
    as it was: absence of evidence neither raises nor clears a page."""
    target = path or LIVENESS_ALARM
    verdict = str(doc.get("verdict") or "")
    with suppress(OSError):
        if verdict == "FAIL":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"judge_alive FAIL at {doc.get('generated_utc')}: "
                              f"{doc.get('why')}\n", encoding="utf-8")
        elif verdict == "PASS" and target.exists():
            target.unlink()
#: THE JUDGE'S OWN PULSE (2026-10-20), written by `desks/mt5/scripts/run_sharded_gauntlet.py`.
#: Coverage alone could not see a sweep that never ends: pid 7324 sat 14 h in its merge while
#: every report here still read a healthy, merely slow judge. The heartbeat carries the sweep's
#: progress and deadlines; the stall artifact names a breach the watchdog acted on.
GAUNTLET_HEARTBEAT = DESK / "reports" / "GAUNTLET_HEARTBEAT.json"
GAUNTLET_STALL = DESK / "reports" / "GAUNTLET_STALL.json"
#: THE OPERATOR HOLD, FENCED (2026-10-27). Any RESIDENT_STOP holds the judge until a human deletes
#: it (run_sharded_gauntlet.resident_stop); a forgotten one held it 108 h on 10-23..27 with no
#: alarm anywhere. The resident publishes `stop.first_honoured_utc` in JUDGE_RESIDENT.json; past
#: STOP_WARN_H of honoured hold this WARNs, past STOP_FAIL_H it FAILs (on the box).
JUDGE_RESIDENT = DESK / "reports" / "JUDGE_RESIDENT.json"
STOP_WARN_H = 12.0
STOP_FAIL_H = 24.0
#: Mirrors `run_sharded_gauntlet.HEARTBEAT_STALE_S`: a RUNNING heartbeat older than this means
#: the sweep's watchdog itself is wedged (it beats at least once a minute).
HEARTBEAT_STALE_S = 600.0

#: A report older than this is stale: the organ runs at intake, hourly, so three hours of silence
#: means the clock stopped. Generous because a box reboot or a long sweep is not a law breach.
STALE_H = 6.0

#: How far past its OWN window a family's oldest unjudged cell may sit before this fails. The
#: slack exists because a window is derived from a quota measured on the previous hour's capacity
#: and the judge's capacity varies with the box; 2x is "this family is not being served", not
#: "this hour ran a little short".
WINDOW_SLACK = 2.0

RULE = ("no family holding unjudged cells is absent from the hour's queue; each family's carried "
        "backlog falls; no family's oldest unjudged cell sits past twice its own drain window "
        "without moving; and the remainder after every floor follows the published "
        "expected-value-per-judge-second ranking")


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, doc: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")


#: How far ahead of this clock a report's `at` may sit and still be read as fresh: the repo's
#: existing tolerance (libs/research/dsr_inputs.FUTURE_SKEW_S, global_research_acceptance
#: MAX_FUTURE_SKEW_S). Beyond it, --require-state reads the stamp as undated.
FUTURE_SKEW_S = 300


def _signed_age_h(stamp: object, now: datetime) -> float | None:
    """Hours since `stamp`, NEGATIVE when it is in the future; None when absent or unparseable."""
    txt = str(stamp or "").strip()
    if not txt:
        return None
    try:
        at = datetime.fromisoformat(txt.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None
    return (now.timestamp() - at.timestamp()) / 3600.0


def _age_h(stamp: object, now: datetime) -> float | None:
    raw = _signed_age_h(stamp, now)
    return None if raw is None else max(0.0, raw)


#: THE PORTABLE HALF NEVER JUDGES BOX STATE (2026-10-20, auditor ruling 2026-10-14 route 2,
#: ordered by the principal). `run_law_gate.py --laws-only` -- the pre-push hook and CI -- sets
#: QUANT_LAWGATE_SOURCE_VIEW=1 on every fence it runs. JUDGE_COVERAGE.json is PUBLISHED TO ORIGIN
#: by the box (sync_shadow_to_git.ps1), so every checkout carries a copy, and this fence judged
#: that copy whenever it was under STALE_H old: a coverage red on the box wedged every push from
#: every laptop, including the push that would heal it -- against the gate's own rule that host
#: state is "STATE, never --laws-only". In a source view the report is therefore NOT READ and the
#: verdict is UNMEASURED with that reason printed. Nothing about the judgement itself changes:
#: `--require-state` (the box's _STATE_FENCES entry) and every run without the source-view flag
#: (the box rotation `run_law_gate.py --rotate`, the full gate, a direct call) judge exactly as
#: before, with the same thresholds, ratchets, tolerance and STALE_H.
SOURCE_VIEW_ENV = "QUANT_LAWGATE_SOURCE_VIEW"
BOX_STATE_ELSEWHERE = ("box state: judged by the box-side state fence (run_law_gate.py "
                       "_STATE_FENCES, check_judge_coverage.py --require-state), not here -- an "
                       "isolated source checkout does not run the producer of JUDGE_COVERAGE.json, "
                       "and a copy published to origin is not a local runtime receipt")


def _source_view(require_state: bool) -> bool:
    """True only for the portable law battery; --require-state always binds."""
    return os.environ.get(SOURCE_VIEW_ENV) == "1" and not require_state


def judge_liveness(now: datetime | None = None, *, heartbeat: Path | None = None,
                   stall: Path | None = None) -> dict[str, Any]:
    """Is the judge alive and getting somewhere? One check row: PASS / WARN / FAIL / UNMEASURED.

    FAIL when the watchdog KILLED a sweep for making no progress (STALLED) and no finished sweep
    has cleared it since, or when a RUNNING heartbeat has gone stale (the watchdog itself is
    wedged). WARN -- amber, never red -- when a sweep is SLOW: past a phase or run threshold but
    still burning CPU (audit HOLD of 2832cebd1: pid 7324 was slow, not stuck, and finished rc 0).
    Absent artifacts are UNMEASURED (L1.28a) -- never a pass dressed as one.
    """
    at = now or datetime.now(tz=UTC)
    hb_doc, st_doc = _read(heartbeat or GAUNTLET_HEARTBEAT), _read(stall or GAUNTLET_STALL)
    hb = hb_doc if isinstance(hb_doc, dict) else {}
    st = st_doc if isinstance(st_doc, dict) else {}
    if not hb and not st:
        return {"metric": "judge_alive", "state": "UNMEASURED",
                "why": "no GAUNTLET_HEARTBEAT.json or GAUNTLET_STALL.json: the sweep watchdog "
                       "has not reported on this tree"}
    if str(st.get("status") or "") == "STALLED":
        return {"metric": "judge_alive", "state": "FAIL", "stall": {
                    k: st.get(k) for k in ("reason", "detail", "stalled_utc", "phase", "shard",
                                           "consecutive", "pid", "lost_s")},
                "why": (f"the judge STALLED ({st.get('reason')}) at {st.get('stalled_utc')} in "
                        f"phase {st.get('phase')}, {st.get('consecutive')} consecutive; no "
                        f"sweep has finished since: {str(st.get('detail') or '')[:200]}")}
    if str(hb.get("status") or "") == "RUNNING":
        beat_h = _age_h(hb.get("beat_utc"), at)
        if beat_h is not None and beat_h * 3600.0 > HEARTBEAT_STALE_S:
            return {"metric": "judge_alive", "state": "FAIL",
                    "why": (f"sweep pid {hb.get('pid')} reads RUNNING but its heartbeat is "
                            f"{beat_h * 60.0:.0f} min old (> {HEARTBEAT_STALE_S / 60.0:.0f} min):"
                            f" the sweep's watchdog is wedged or the process was frozen")}
        past_h = _age_h(hb.get("run_deadline_utc"), at)
        if past_h is not None and past_h * 3600.0 > HEARTBEAT_STALE_S:
            return {"metric": "judge_alive", "state": "WARN",
                    "why": (f"SLOW: sweep pid {hb.get('pid')} is past its run threshold "
                            f"{hb.get('run_deadline_utc')} in phase {hb.get('phase')} and still "
                            f"progressing (idle {hb.get('idle_s')}s); it is left to finish")}
    if str(st.get("status") or "") == "SLOW" or hb.get("slow"):
        slow = st.get("slow") if isinstance(st.get("slow"), dict) else {}
        return {"metric": "judge_alive", "state": "WARN", "slow": slow,
                "why": (f"SLOW: {slow.get('reason') or hb.get('slow')} at "
                        f"{slow.get('slow_utc')} in phase {slow.get('phase') or hb.get('phase')}"
                        f" -- past a threshold, still progressing, not killed")}
    return {"metric": "judge_alive", "state": "PASS",
            "why": (f"heartbeat {hb.get('status') or 'absent'} (phase {hb.get('phase')}, last "
                    f"beat {hb.get('beat_utc')}); stall record {st.get('status') or 'absent'}")}


def judge_stop(now: datetime | None = None, *, resident: Path | None = None) -> dict[str, Any]:
    """How long has the operator hold held the judge? PASS / WARN / FAIL / UNMEASURED.

    The age is re-derived from `stop.first_honoured_utc` against `now` (a stale record still
    ages), falling back to the published `stop_age_s`. Not STOPPED is PASS."""
    at = now or datetime.now(tz=UTC)
    doc = _read(resident or JUDGE_RESIDENT)
    if not isinstance(doc, dict):
        return {"metric": "judge_stop", "state": "UNMEASURED",
                "why": "no readable JUDGE_RESIDENT.json"}
    if str(doc.get("status") or "") != "STOPPED":
        return {"metric": "judge_stop", "state": "PASS",
                "why": f"resident {doc.get('status') or 'absent'}: no operator hold"}
    stop = doc.get("stop") if isinstance(doc.get("stop"), dict) else {}
    age_h = _age_h(stop.get("first_honoured_utc"), at)
    if age_h is None:
        try:
            age_h = float(doc.get("stop_age_s")) / 3600.0  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return {"metric": "judge_stop", "state": "UNMEASURED",
                    "why": f"resident STOPPED ({doc.get('why')}) with no honoured-since stamp"}
    state = "FAIL" if age_h >= STOP_FAIL_H else "WARN" if age_h >= STOP_WARN_H else "PASS"
    return {"metric": "judge_stop", "state": state, "stop_age_h": round(age_h, 2),
            "why": (f"RESIDENT_STOP has held the judge for {age_h:.1f}h since "
                    f"{stop.get('first_honoured_utc')} (WARN {STOP_WARN_H:g}h, FAIL "
                    f"{STOP_FAIL_H:g}h): {doc.get('why')}. Delete the file to resume.")}


_RANK = {"FAIL": 3, "WARN": 2, "UNMEASURED": 1, "PASS": 0}


def liveness_fence(*, require_state: bool = False, now: datetime | None = None,
                   heartbeat: Path | None = None, stall: Path | None = None,
                   resident: Path | None = None) -> dict[str, Any]:
    """The hourly `judge_alive` leg's verdict: the liveness row (and the operator-hold row when
    the desk's real state is read), as a fence document.

    Off the box (no `--require-state`) a FAIL is a WARN, as in `judge`: a commit is never blamed
    for a box incident. UNMEASURED stays UNMEASURED (L1.28a)."""
    row = judge_liveness(now, heartbeat=heartbeat, stall=stall)
    rows = [row]
    if resident is not None or (heartbeat is None and stall is None):
        rows.append(judge_stop(now, resident=resident))
    rows = [{**r, "state": "WARN"} if r["state"] == "FAIL" and not require_state else r
            for r in rows]
    # The liveness row decides, unless another row is WARN or FAIL and worse than it: an
    # unreadable resident record never turns a passing liveness reading UNMEASURED.
    row = rows[0]
    for other in rows[1:]:
        if other["state"] in ("WARN", "FAIL") and _RANK[other["state"]] > _RANK.get(
                row["state"], 1):
            row = other
    # WARN (SLOW, amber) exits 0 and says so in `state`: a slow sweep is never a failed leg.
    verdict = {"PASS": "PASS", "WARN": "PASS", "FAIL": "FAIL"}.get(row["state"], "UNMEASURED")
    return {"generated_utc": (now or datetime.now(tz=UTC)).isoformat(timespec="seconds"),
            "fence": "judge_alive", "verdict": verdict, "state": row["state"],
            "why": row["why"], "checks": rows}


def judge(report: Path | None = None, *, require_state: bool = False,
          now: datetime | None = None, liveness: bool | None = None,
          heartbeat: Path | None = None, stall: Path | None = None) -> dict[str, Any]:
    """The coverage verdict, with the judge's own liveness folded in.

    `liveness` None reads it only for the desk's REAL report (`report` None), so a test that
    hands in its own coverage report is never coloured by whatever the box last published. On
    the box (`--require-state`) a dead or stalled judge FAILS; anywhere else it is a WARN, the
    same split the freshness rule makes, because a commit cannot be blamed for a box incident.
    """
    out = _coverage(report, require_state=require_state, now=now)
    if liveness is None:
        # The source view (pre-push, CI) reads no box-published state, and GAUNTLET_HEARTBEAT /
        # GAUNTLET_STALL are published to origin by sync_shadow_to_git.ps1 exactly as
        # JUDGE_COVERAGE.json is: they are judged on the box, never here (merge resolution of the
        # pager chain's source view with the watchdog's liveness, 2026-10-21).
        liveness = report is None and not _source_view(require_state)
    if not liveness:
        return out
    rows = [judge_liveness(now, heartbeat=heartbeat, stall=stall)]
    if heartbeat is None and stall is None:
        rows.append(judge_stop(now))
    for row in rows:
        if row["state"] == "FAIL" and not require_state:
            row = {**row, "state": "WARN"}
        out.setdefault("checks", []).append(row)
        if row["state"] == "FAIL":
            out["verdict"] = "FAIL"
            out["why"] = f"{row['metric']}: {row['why']}; " + str(out.get("why") or "")
    return out


def _coverage(report: Path | None = None, *, require_state: bool = False,
              now: datetime | None = None) -> dict[str, Any]:
    at = now or datetime.now(tz=UTC)
    path = report or REPORT
    out: dict[str, Any] = {"at": at.isoformat(timespec="seconds"), "rule": RULE,
                           "report": str(path), "checks": []}
    if _source_view(require_state):
        out["verdict"] = "UNMEASURED"
        out["why"] = BOX_STATE_ELSEWHERE
        out["checks"].append({"metric": "box_state", "state": "UNMEASURED",
                              "why": f"{SOURCE_VIEW_ENV}=1: {path.name} not read"})
        return out
    doc = _read(path)
    if not isinstance(doc, dict) or not doc.get("families"):
        out["verdict"] = "FAIL" if require_state else "UNMEASURED"
        out["why"] = (f"{path.name} is absent or carries no family table"
                      + (" and --require-state says this box owes one (L1.49)" if require_state
                         else "; this tree holds no judge-coverage state (L1.28a)"))
        return out

    # A STALE OR UNDATED REPORT FAILS THE BOX (2026-10-21, audit of the coverage pager). Until
    # now `--require-state` appended a freshness FAIL row and then computed the verdict from the
    # family rules alone, so a report the judge had stopped writing hours ago still read PASS with
    # rc 0 whenever its last reading happened to be healthy -- and an `at` that was missing or
    # unparseable skipped the freshness check entirely. On the box the report's own lease is the
    # claim that the organ is running (L1.49), so either case is a failure of the verdict, not a
    # row beside it. The portable and source-view readings are unchanged: stale is UNMEASURED
    # there, and an undated report is judged as before.
    #
    # A FUTURE STAMP IS NOT FRESHNESS (2026-10-21, audit of cbea9e8d9). `_age_h` clamps at zero,
    # so an `at` ahead of this clock read as a report written this instant -- a clock step or a
    # bad writer would hold the lease open forever. Past FUTURE_SKEW_S ahead, --require-state
    # reads the stamp as UNDATED (FAIL); inside the skew it is fresh, and the portable reading is
    # unchanged.
    raw_age = _signed_age_h(doc.get("at"), at)
    future = raw_age is not None and raw_age < -FUTURE_SKEW_S / 3600.0
    age = None if raw_age is None else max(0.0, raw_age)
    if require_state and future:
        age = None
    failures: list[str] = []
    if age is not None and age > STALE_H:
        out["checks"].append({"metric": "freshness", "state": "FAIL" if require_state else "WARN",
                              "why": f"report is {age:.1f}h old, past the {STALE_H:.0f}h lease"})
        if not require_state:
            out["verdict"] = "UNMEASURED"
            out["why"] = "stale exported coverage cannot establish current desk state"
            return out
        failures.append("report_stale")
    elif age is None and require_state:
        out["checks"].append({"metric": "freshness", "state": "FAIL",
                              "why": ((f"report `at` {str(doc.get('at'))[:40]!r} is "
                                       f"{-float(raw_age or 0.0):.2f}h in the future, past the "
                                       f"{FUTURE_SKEW_S}s skew") if future else
                                      f"report `at` is missing or unparseable "
                                      f"({str(doc.get('at'))[:40]!r})")
                                     + f": its age against the {STALE_H:.0f}h lease cannot be "
                                       "shown"})
        failures.append("report_undated")

    fams: dict[str, Any] = {f: r for f, r in (doc.get("families") or {}).items()
                            if isinstance(r, dict)}
    judged_any = sum(int(r.get("judged_window") or 0) for r in fams.values())

    # 1. STARVATION: unjudged cells and no place in the queue.
    starved = sorted((f for f, r in fams.items()
                      if int(r.get("unjudged") or 0) > 0
                      and int(r.get("queued") or 0) == 0
                      and str(r.get("judging_status") or "") != "STUDY_ONLY"),
                     key=lambda f: -int(fams[f].get("unjudged") or 0))
    if starved:
        failures.extend(starved[:10])
        out["checks"].append({
            "metric": "families_starved", "state": "FAIL",
            "why": (f"{len(starved)} family(ies) hold unjudged cells and got no share of the "
                    f"hour: " + ", ".join(f"{f} ({fams[f].get('unjudged')})"
                                          for f in starved[:5]))})
    else:
        out["checks"].append({"metric": "families_starved", "state": "OK",
                              "why": "every family holding unjudged cells is in the queue"})

    # 2. THE CARRIED COHORT FALLS. UNMEASURED on the first reading (no baseline) and on a pass
    #    where the judge recorded nothing at all (nothing ran; that is not intake's failure).
    rows_with_baseline = [(f, r) for f, r in fams.items() if r.get("carried") is not None
                          and int(r.get("prior_unjudged") or 0) > 0]
    if not rows_with_baseline:
        out["checks"].append({"metric": "carried_backlog", "state": "UNMEASURED",
                              "why": "no previous reading to ratchet against"})
    elif judged_any == 0:
        out["checks"].append({"metric": "carried_backlog", "state": "UNMEASURED",
                              "why": ("the judge recorded no verdict in this window -- nothing "
                                      "drained because nothing ran (the gauntlet's clock)")})
    else:
        # Against the COHORT BASE when the report carries it: the prior backlog plus cells the
        # bank re-admitted, minus cells parked as not testable since (neither is judging).
        def _base(r: dict) -> int:
            b = r.get("cohort_base")
            return int(r.get("prior_unjudged") or 0) if b is None else int(b or 0)

        stalled = sorted((f for f, r in rows_with_baseline
                          if _base(r) > 0 and int(r.get("carried") or 0) >= _base(r)
                          and int(r.get("quota") or 0) > 0
                          and str(r.get("judging_status") or "") != "STUDY_ONLY"),
                         key=lambda f: -int(fams[f].get("carried") or 0))
        if stalled:
            failures.extend(stalled[:10])
            out["checks"].append({
                "metric": "carried_backlog", "state": "FAIL",
                "why": (f"{len(stalled)} family(ies) drained nothing they already held: "
                        + ", ".join(f"{f} ({fams[f].get('carried')} carried of "
                                    f"{fams[f].get('prior_unjudged')})" for f in stalled[:5]))})
        else:
            drained = sum(int(r.get("drained") or 0) for _, r in rows_with_baseline)
            out["checks"].append({"metric": "carried_backlog", "state": "OK",
                                  "why": f"{drained} carried cell(s) left the backlog this pass"})

    # 3. NO FAMILY PAST ITS OWN WINDOW -- AND THE AGE IS RATCHETED ON MOVEMENT, NOT ON ITS VALUE.
    #
    # An age RISES by the wall time between two readings whatever the desk does. The coverage-
    # drain fence ratcheted a raw wait and went red on its third live pass for exactly that
    # reason -- 6.0h to 6.3h, eighteen minutes of clock -- and a gate nobody can satisfy is a gate
    # that gets switched off. So what fails here is an age that is past twice the family's own
    # drain window AND DID NOT FALL, in a pass where the family held quota and the judge actually
    # recorded verdicts. That is the controllable defect: a family whose stream is sorted
    # oldest-first, which was served this hour, and whose oldest cell still did not move.
    # The first reading carries no baseline and so enters UNMEASURED, which is how every metric
    # on this desk enters: at its measurement, never at an invented zero.
    def _overdue(f: str, r: dict[str, Any]) -> bool:
        if int(r.get("unjudged") or 0) <= 0 or str(r.get("judging_status") or "") == "STUDY_ONLY":
            return False
        age = r.get("oldest_unjudged_age_h")
        prior = r.get("prior_oldest_age_h")
        if age is None or prior is None or int(r.get("quota") or 0) <= 0 or judged_any == 0:
            return False
        window = float(r.get("window_h") or 1.0)
        return float(age) > WINDOW_SLACK * window and float(age) >= float(prior)

    overdue = sorted((f for f, r in fams.items() if _overdue(f, r)),
                     key=lambda f: -float(fams[f].get("oldest_unjudged_age_h") or 0.0))
    if overdue:
        failures.extend(overdue[:10])
        out["checks"].append({
            "metric": "oldest_unjudged", "state": "FAIL",
            "why": (f"{len(overdue)} family(ies) were served this hour and their oldest cell "
                    f"still did not move, past twice their own drain window: " + ", ".join(
                        f"{f} ({fams[f].get('oldest_unjudged_age_h')}h vs "
                        f"{fams[f].get('window_h')}h window)" for f in overdue[:5]))})
    else:
        stale_age = sorted((f for f, r in fams.items()
                            if r.get("oldest_unjudged_age_h") is not None
                            and int(r.get("unjudged") or 0) > 0
                            and float(r["oldest_unjudged_age_h"]) >
                            WINDOW_SLACK * float(r.get("window_h") or 1.0)),
                           key=lambda f: -float(fams[f].get("oldest_unjudged_age_h") or 0.0))
        out["checks"].append({
            "metric": "oldest_unjudged",
            "state": "OK" if not stale_age else "WARN",
            "why": ("no family's oldest unjudged cell is past its own window" if not stale_age
                    else (f"{len(stale_age)} family(ies) hold a cell past their own window and "
                          f"it is FALLING or unmeasured (oldest "
                          f"{fams[stale_age[0]].get('oldest_unjudged_age_h')}h on "
                          f"{stale_age[0]}) -- published, not failed: an age rises with the "
                          "clock and only its movement is the desk's to control"))})

    # 4. THE REMAINDER FOLLOWED THE PUBLISHED RANKING. The floor is the breadth mandate and is
    #    checked above by starvation; this checks the part that carries the return. Remainder is
    #    spent strictly down expected value per judge-second, so a family that received remainder
    #    while a HIGHER-ranked family still held undrained backlog means the allocation stopped
    #    following its own ranking -- which is exactly how a future session would quietly revert
    #    this to round-robin, with the report still claiming value ordering.
    ranking = [r for r in (doc.get("value_ranking") or ()) if isinstance(r, dict)]
    if not ranking:
        out["checks"].append({"metric": "remainder_follows_ranking", "state": "UNMEASURED",
                              "why": "the report publishes no value ranking"})
    else:
        starved_higher: list[str] = []
        for i, row in enumerate(ranking):
            if int(row.get("remainder") or 0) <= 0:
                continue
            for higher in ranking[:i]:
                room = int(higher.get("unjudged") or 0) - int(higher.get("quota") or 0)
                if int(higher.get("remainder") or 0) == 0 and room > 0:
                    starved_higher.append(f"{row.get('family')} over {higher.get('family')}")
                    break
        if starved_higher:
            failures.extend(starved_higher[:10])
            out["checks"].append({
                "metric": "remainder_follows_ranking", "state": "FAIL",
                "why": ("the remainder did not follow the published expected-value-per-judge-"
                        "second ranking: " + ", ".join(starved_higher[:5]))})
        else:
            top = ranking[0]
            out["checks"].append({
                "metric": "remainder_follows_ranking", "state": "OK",
                "why": (f"remainder spent down the ranking, top {top.get('family')} at "
                        f"{top.get('ev_per_judge_second')} ev/judge-s")})

    # 5. THE UNKNOWN CLASS RATCHETS DOWN AND MAY NOT STALL (principal 2026-09-23). MEASURED on
    #    the box: 44,432 of 60,000 recent verdicts terminated with no named gate -- three
    #    quarters of the judge returning neither a pass nor a reason, the largest single waste on
    #    the desk. `judge_coverage.name_unknowns` gives every one of them a NAMED reason and
    #    `update_unrunnable_bank` filters the unrunnable ones out of intake, so the count must
    #    fall. It FAILS on a rise, and on a STALL while the bank still had cells to filter --
    #    a count that stops falling with work left is how this silently returns. A count already
    #    at zero stalls at zero and passes; the first reading has no baseline and is UNMEASURED.
    tot = doc.get("totals") or {}
    now_unknown = tot.get("unknown_total")
    was_unknown = tot.get("prior_unknown_share")
    unnamed = int(tot.get("unknown_unnamed") or 0)
    share_now = tot.get("unknown_share")
    if now_unknown is None or share_now is None:
        out["checks"].append({"metric": "unknown_ratchet", "state": "UNMEASURED",
                              "why": "no UNKNOWN census in this report"})
    elif unnamed > 0:
        failures.append("unknown_unnamed")
        out["checks"].append({
            "metric": "unknown_ratchet", "state": "FAIL",
            "why": (f"{unnamed} UNKNOWN verdict(s) carry no named reason -- an unnamed terminal "
                    "state is the defect, whatever the cause turns out to be")})
    elif was_unknown is None:
        out["checks"].append({
            "metric": "unknown_ratchet", "state": "UNMEASURED",
            "why": (f"UNKNOWN share enters at its measurement ({float(share_now):.1%}, "
                    f"{now_unknown} cells, all named); no previous reading to ratchet against")})
    else:
        parked = int(tot.get("unrunnable_bank") or 0)
        rose = float(share_now) > float(was_unknown) + 1e-9
        # A STALL IS ONLY A STALL IF THE JUDGE RAN. The share is read from the sealed judge's own
        # verdict file, which does not move between its sweeps -- so without this guard the fence
        # would go red for the crime of being asked twice in one hour, which is precisely how the
        # coverage-drain fence learned that an unsatisfiable gate gets switched off. A RISE still
        # fails unguarded: a share cannot rise without new verdicts arriving.
        has_stalled = (abs(float(share_now) - float(was_unknown)) <= 1e-9
                       and float(share_now) > 0 and parked > 0 and judged_any > 0)
        if rose or has_stalled:
            failures.append("unknown_share")
            out["checks"].append({
                "metric": "unknown_ratchet", "state": "FAIL",
                "why": (f"UNKNOWN share {'rose' if rose else 'stalled at'} "
                        f"{float(was_unknown):.1%} -> {float(share_now):.1%} with {parked} "
                        "cell(s) in the unrunnable bank: the filter is not reaching the judge")})
        else:
            out["checks"].append({
                "metric": "unknown_ratchet", "state": "OK",
                "why": (f"UNKNOWN share {float(was_unknown):.1%} -> {float(share_now):.1%}, "
                        f"{now_unknown} cells, every one named"
                        + ("" if judged_any else
                           " (unchanged because the judge recorded no verdict this window --"
                           " a stall is only a stall if the judge ran)"))})

    # 6. THE JUDGE KEEPS PACE WITH CREATION (principal 2026-09-30: "the cells thing always
    #    permanently fixed"). Measured that day: ~8,300 cells created a day against ~5,300
    #    verdicts, so 1.4M unjudged and growing ~3k a day while the old meter read "25 h to
    #    drain". The drain status is the backlog's own movement between two readings, net of
    #    judging and creation. Two consecutive GROWING readings FAIL. THE REMEDY IS CAPACITY,
    #    NEVER LESS MINING: `research/judging_throughput.py` raises workers and cadence off this
    #    same report, and the unrunnable bank keeps dead cells from eating the judge. A single
    #    GROWING reading WARNs, because one sweep's timing is not a trend.
    drain = tot.get("drain_status")
    prior_drain = tot.get("prior_drain_status")
    if drain is None:
        out["checks"].append({"metric": "judge_keeps_pace", "state": "UNMEASURED",
                              "why": "no drain status in this report"})
    elif drain == "GROWING" and prior_drain == "GROWING":
        failures.append("judge_keeps_pace")
        out["checks"].append({
            "metric": "judge_keeps_pace", "state": "FAIL",
            "why": (f"backlog grew across two readings ({tot.get('backlog_growth_per_hour')}/h; "
                    f"judge sustains {tot.get('capacity_sustained_per_hour')}/h): add judge "
                    "capacity -- never throttle a miner")})
    else:
        out["checks"].append({"metric": "judge_keeps_pace",
                              "state": "WARN" if drain == "GROWING" else "OK",
                              "why": f"drain {drain} (previous {prior_drain})"})

    # 7. BUILD/DATA FAILURES BEFORE JUDGING RATCHET DOWN. Measured 2026-09-30: 20,247 of 29,466
    #    pre-warm builds failed on build or data. Those cells are now parked with a named reason
    #    and re-admitted only when their bars appear or grow, so the share may not rise.
    pw_now, pw_was = tot.get("prewarm_fail_share"), tot.get("prior_prewarm_fail_share")
    if pw_now is None or pw_was is None:
        out["checks"].append({"metric": "prewarm_fail_ratchet", "state": "UNMEASURED",
                              "why": f"pre-warm failure share {pw_now} (previous {pw_was})"})
    elif float(pw_now) > float(pw_was) + PREWARM_TOLERANCE:
        failures.append("prewarm_fail_share")
        out["checks"].append({
            "metric": "prewarm_fail_ratchet", "state": "FAIL",
            "why": (f"pre-warm build/data failure share rose {float(pw_was):.1%} -> "
                    f"{float(pw_now):.1%}: failing cells are reaching the judge again")})
    else:
        out["checks"].append({"metric": "prewarm_fail_ratchet", "state": "OK",
                              "why": f"pre-warm failures {float(pw_was):.1%} -> "
                                     f"{float(pw_now):.1%}"})

    # THE RELEASE FILE OF THE BUILD-INPUT BACKSTOP (judge_coverage v1.4, audit of v1.3). It holds
    # the cells the 90-day backstop released until the judge rules on them. Read UNREADABLE,
    # TORN or VANISHED, the probe parks nothing new and the pass self-heals: WARN. Evidence of a
    # tear set aside for more than RELEASE_ASIDE_MAX_PASSES consecutive passes was never looked
    # at by anyone: FAIL, so it is.
    rf = ((doc.get("build_input_probe") or {}).get("release_file")
          if isinstance(doc.get("build_input_probe"), dict) else None)
    if isinstance(rf, dict):
        # Consecutive NOT-OK passes of any kind (v1.5): unreadable, torn, vanished, a refused
        # write, or evidence aside. `set_aside_passes` is v1.4's narrower count, still honoured.
        n_aside = max(int(rf.get("not_ok_passes") or 0), int(rf.get("set_aside_passes") or 0))
        rstate = str(rf.get("state") or "")
        if n_aside > RELEASE_ASIDE_MAX_PASSES:
            failures.append("build_input_release_file")
            out["checks"].append({
                "metric": "build_input_release_file", "state": "FAIL",
                "why": (f"release file NOT OK for {n_aside} consecutive passes "
                        f"(> {RELEASE_ASIDE_MAX_PASSES}): read {rstate or '?'}, write "
                        f"{rf.get('write')}, set aside {rf.get('set_aside') or []}; a held due "
                        f"cell waits on it -- inspect, then resolve by hand")})
        elif (rstate in ("UNREADABLE", "TORN", "VANISHED", "UNMEASURED")
              or rf.get("set_aside") or rf.get("write") in ("UNREADABLE", "WRITE_FAILED")):
            out["checks"].append({
                "metric": "build_input_release_file", "state": "WARN",
                "why": (f"release file read {rstate or '?'} (write {rf.get('write')}); "
                        f"set aside: {rf.get('set_aside') or []} for {n_aside} pass(es)")})
        else:
            out["checks"].append({"metric": "build_input_release_file", "state": "OK",
                                  "why": f"release file {rstate or 'ABSENT'}"})

    totals = doc.get("totals") or {}
    out["totals"] = {k: totals.get(k) for k in (
        "families_mined", "families_with_backlog", "families_queued", "families_starved",
        "unjudged_total", "carried_total", "study_only_total", "capacity_measured",
        "oldest_unjudged_age_h", "value_at_risk", "value_deferred", "value_forgone_per_hour",
        "hours_to_drain", "capacity_short", "unknown_total", "unknown_share",
        "unknown_unnamed", "never_fires_cells", "unrunnable_parked", "unrunnable_bank",
        "drain_status", "backlog_growth_per_hour", "capacity_sustained_per_hour",
        "prewarm_fail_share", "not_run_named")}
    out["unknown_reasons"] = (doc.get("unknown_reasons") or {}).get("by_reason") or {}
    out["top_value"] = [{k: r.get(k) for k in ("rank", "family", "ev_per_judge_second",
                                               "p_optimistic", "prior_status", "quota",
                                               "floor", "remainder", "value_at_risk")}
                        for r in ranking[:5]]
    out["worst_backlog"] = (doc.get("worst_backlog") or [])[:5]
    out["verdict"] = "FAIL" if failures else "PASS"
    lease = [f for f in ("report_stale", "report_undated") if f in failures]
    rules = sorted(set(failures) - set(lease))
    out["why"] = "; ".join(
        ([f"the report is {'stale past its lease' if 'report_stale' in lease else 'undated'} "
          f"(--require-state)"] if lease else [])
        + ([f"{len(rules)} family(ies) failed a coverage rule: " + ", ".join(rules[:6])]
           if rules else [])) if failures else (
        "every family holding unjudged cells is queued, its carried backlog fell, and none sits "
        "past its own window")
    return out


def render(doc: Mapping[str, Any]) -> list[str]:
    lines = [f"judge coverage: {doc.get('verdict')} -- {doc.get('why')}"]
    for row in doc.get("checks") or ():
        lines.append(f"  [{row.get('state')}] {row.get('metric')}: {row.get('why')}")
    t = doc.get("totals") or {}
    if t.get("unknown_total") is not None:
        lines.append(f"  UNKNOWN {t.get('unknown_total')} ({t.get('unknown_share')}) "
                     f"reasons {doc.get('unknown_reasons')} unnamed {t.get('unknown_unnamed')} "
                     f"bank {t.get('unrunnable_bank')}")
    if t.get("value_at_risk") is not None:
        lines.append(f"  value at risk {t.get('value_at_risk')} / deferred "
                     f"{t.get('value_deferred')} / forgone {t.get('value_forgone_per_hour')}/h"
                     + ("  CAPACITY SHORT -> judging_throughput" if t.get("capacity_short")
                        else ""))
    for row in doc.get("top_value") or ():
        lines.append(f"  #{row.get('rank')} {row.get('family')} ev/judge-s "
                     f"{row.get('ev_per_judge_second')} quota {row.get('quota')}")
    for row in doc.get("worst_backlog") or ():
        lines.append(f"  worst: {row.get('family')} unjudged {row.get('unjudged')} "
                     f"queued {row.get('queued')} oldest {row.get('oldest_unjudged_age_h')}h")
    return lines


#: R0237: the exit code is `fence_exit` over a DECLARED pass set, never "fail on one named status,
#: pass on everything else" -- that sent any unforeseen or misspelled status down `else 0`. The
#: set is exactly the statuses this fence already exited 0 on (behaviour unchanged for every
#: status it can emit); what changes is that a status nobody declared now fails closed.
_PASSING = frozenset({"PASS", "UNMEASURED"})


def _exit(status: object) -> int:
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)
    from libs.ops.fence_exit import fence_exit
    return fence_exit(status, _PASSING, fail=1)


# ------------------------------------------------------------------------ the out-of-band page
#: A RED COVERAGE CHECK PAGES (2026-10-20). Until now a coverage red lived only in records --
#: `data/law_gate.json` from the MT5-LawGate rotation, this fence's audit, check_fence_yield and
#: capability_ratchet -- so a stalled judge (2026-10-20: the report stopped at 19:44Z with zero
#: verdicts in its window) waited for a reader. The box-side run (`--require-state` against the
#: box's own report) now also pages through the desk's existing sender,
#: `libs.ops.alert_channels.send_all`, deduplicated the way `state_publication.page_flow` is:
#: one page when an incident OPENS, a reminder every REPAGE_H hours while it stands, one RESOLVED
#: notice when it clears. It is a side effect only: `judge()` is untouched, and the verdict, the
#: printed lines, the audit and the exit code are byte-identical. A pager failure is recorded in
#: the state file (and one stderr line) and never reaches any of them. The portable run (source
#: view, any run without --require-state, or one pointed at another --report) never pages.
#:
#: The incidents, each its own persisted key:
#:   red           the verdict is FAIL (green, UNMEASURED or no prior state -> red pages)
#:   stale         the report is older than STALE_H while the box runs this fence
#:   zero_judged   a fresh report whose trailing window recorded no verdict in any family
#: Box-local state (desks/mt5/logs/ is gitignored), never published.
PAGE_STATE_REL = "desks/mt5/logs/judge_coverage_page.json"
#: The desk's reminder convention (state_publication.REPAGE_H, run_alerts._DEDUPE_S).
REPAGE_H = 6.0
INCIDENTS = ("red", "stale", "zero_judged")

PageSender = Callable[[str, str], Any]


def _default_page_sender(root: Path) -> PageSender:
    def send(title: str, body: str) -> Any:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from libs.ops import alert_channels
        # Anchored on the repo root so the leg's working directory cannot make an armed box look
        # unarmed. Nothing here reads, prints or records a channel's credentials.
        # DESK: judge-coverage incidents are fence REDs the threads fix.
        return alert_channels.send_all(
            title, body, config=root / "data/secrets/alert_channels.json",
            ledger=root / "data/alert_delivery.jsonl", audience="desk")
    return send


def incidents(doc: Mapping[str, Any], report_doc: Any) -> dict[str, str]:
    """The open incidents in one fence reading, each with a one-line reason."""
    out: dict[str, str] = {}
    if doc.get("verdict") == "FAIL":
        out["red"] = str(doc.get("why") or "judge coverage FAIL")
    fresh = next((c for c in doc.get("checks") or () if c.get("metric") == "freshness"
                  and c.get("state") == "FAIL"), None)
    fams = report_doc.get("families") if isinstance(report_doc, dict) else None
    if fresh is not None:
        out["stale"] = str(fresh.get("why"))
    elif isinstance(fams, dict) and fams:
        rows = [r for r in fams.values() if isinstance(r, dict)]
        with suppress(TypeError, ValueError):
            if rows and sum(int(r.get("judged_window") or 0) for r in rows) == 0:
                out["zero_judged"] = (f"the judge recorded no verdict in any of {len(rows)} "
                                      f"families over the report's window (report at "
                                      f"{report_doc.get('at')})")
    return out


def page_coverage(doc: Mapping[str, Any], report_doc: Any, *, root: Path | None = None,
                  now: datetime | None = None, sender: PageSender | None = None,
                  repage_h: float = REPAGE_H) -> dict[str, Any]:
    """Page opened incidents, reminders and resolutions, deduplicated. Never raises."""
    try:
        return _page_coverage(doc, report_doc, root=root or ROOT,
                              now=now or datetime.now(tz=UTC), sender=sender, repage_h=repage_h)
    except Exception as exc:  # the pager must never touch the verdict
        return {"sent": False, "error": f"{type(exc).__name__}: {exc}"[:200]}


def _page_coverage(doc: Mapping[str, Any], report_doc: Any, *, root: Path, now: datetime,
                   sender: PageSender | None, repage_h: float) -> dict[str, Any]:
    if doc.get("verdict") not in ("PASS", "FAIL"):
        # UNMEASURED neither pages nor clears: absence is not recovery.
        return {"sent": False, "reason": f"{doc.get('verdict')}: nothing to page"}
    path = root / PAGE_STATE_REL
    prev = _read(path)
    prev = prev if isinstance(prev, dict) else {}
    raw_open = prev.get("open")
    open_prev: dict[str, dict[str, Any]] = {
        k: v for k, v in (raw_open.items() if isinstance(raw_open, dict) else ())
        if k in INCIDENTS and isinstance(v, dict)}
    now_open = incidents(doc, report_doc)
    stamp = now.isoformat(timespec="seconds")
    opened = [k for k in INCIDENTS if k in now_open and k not in open_prev]
    resolved = [k for k in INCIDENTS if k in open_prev and k not in now_open]
    due: list[str] = []
    for k in INCIDENTS:
        if k not in now_open or k not in open_prev:
            continue
        last = None
        with suppress(TypeError, ValueError):
            last = datetime.fromisoformat(str(open_prev[k].get("paged_at")))
        # An unreadable or future stamp (a failed send, a clock step) never silences a reminder.
        if last is None or last > now or (now - last).total_seconds() / 3600 >= repage_h:
            due.append(k)
    state_open: dict[str, dict[str, Any]] = {}
    for k in now_open:
        row = dict(open_prev.get(k) or {})
        row.setdefault("opened_at", stamp)
        row["incident"] = f"judge_coverage:{k}@{row['opened_at']}"
        row["why"] = now_open[k][:300]
        state_open[k] = row
    out: dict[str, Any] = {"sent": False, "open": sorted(now_open), "opened": opened,
                           "reminded": due, "resolved": resolved}
    to_page = opened + due
    if to_page or resolved:
        if to_page:
            title = ("JUDGE COVERAGE " + ("RED" if "red" in now_open else "ALERT") + ": "
                     + ", ".join(sorted(now_open)))
        else:
            title = "JUDGE COVERAGE RESOLVED: " + ", ".join(resolved)
        lines = [f"{'OPEN' if k in opened else 'STILL'} {k}: {now_open[k]}" for k in to_page]
        lines += [f"RESOLVED {k} (opened {open_prev[k].get('opened_at')})" for k in resolved]
        lines.append(f"verdict {doc.get('verdict')} -- {doc.get('why')}")
        lines.append(f"measured {doc.get('at')} by check_judge_coverage.py --require-state "
                     f"({Path(str(doc.get('report'))).name})")
        err: object = None
        try:
            res = (sender or _default_page_sender(root))(title, "\n".join(lines)[:3500])
            res = res if isinstance(res, dict) else {}
            err = res.get("error")
        except Exception as exc:
            res, err = {}, f"{type(exc).__name__}: {exc}"
        armed, delivered = res.get("armed"), res.get("delivered")
        # An armed pager that delivered nothing, or a sender that raised, leaves the incident
        # UNPAGED so the next box run retries. NOT ARMED is a recorded state (send_all ledgers
        # it in data/alert_delivery.jsonl), so it counts as sent, exactly as page_flow does.
        failed = bool(err) or (bool(armed) and not delivered)
        out.update({"sent": not failed, "title": title, "armed": armed, "delivered": delivered})
        if err:
            out["error"] = str(err)[:200]
        for k in to_page:
            if failed:
                state_open[k]["last_error"] = out.get("error") or "no armed channel delivered"
                state_open[k]["last_error_at"] = stamp
            else:
                state_open[k]["paged_at"] = stamp
                state_open[k].pop("last_error", None)
                state_open[k].pop("last_error_at", None)
    # tmp + os.replace: a run killed mid-write (the rotation's per-fence timeout) must never leave
    # a half-written state file, which would read as "nothing open" and re-page every incident.
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps({"at": stamp, "verdict": doc.get("verdict"),
                                   "open": state_open,
                                   "last": {k: out.get(k) for k in (
                                       "sent", "title", "armed", "delivered", "error",
                                       "opened", "reminded", "resolved")}},
                                  indent=1, default=str), "utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        with suppress(OSError):
            tmp.unlink(missing_ok=True)
        out["state_write_error"] = f"{type(exc).__name__}: {exc}"[:200]
    return out


def _box_pages(args: argparse.Namespace) -> bool:
    """Only the box-side state run against the box's own report pages.

    The `--liveness` run (the hourly judge_alive leg) carries the watchdog's row alone, not the
    coverage table, and pages through its own `sync_alarm`: reading it here would open or clear
    coverage incidents off a document that never judged coverage (merge resolution, 2026-10-21)."""
    return (bool(args.require_state) and args.report is None
            and not getattr(args, "liveness", False)
            and not _source_view(bool(args.require_state)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ or "")
    ap.add_argument("--require-state", action="store_true",
                    help="box mode: an absent or stale report is a FAILURE, not UNMEASURED")
    ap.add_argument("--report", default=None)
    ap.add_argument("--audit", default=str(AUDIT))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--liveness", action="store_true",
                    help="the hourly judge_alive leg: the sweep watchdog's heartbeat and stall "
                         "record only, written to reports/judge_alive_fence.json")
    args = ap.parse_args(argv)
    if args.liveness:
        doc = liveness_fence(require_state=bool(args.require_state))
        if args.require_state:          # only the box's own verdict pages
            sync_alarm(doc)
        if args.audit == str(AUDIT):
            args.audit = str(LIVENESS_AUDIT)
    else:
        doc = judge(report=Path(args.report) if args.report else None,
                    require_state=bool(args.require_state))
    if args.json:
        print(json.dumps(doc, indent=1, ensure_ascii=False, default=str))
    else:
        for line in render(doc):
            print(line)
    # The audit is the box's record of its own verdict; a source view writes none over it.
    if args.audit and not _source_view(bool(args.require_state)):
        with suppress(OSError):
            _write(Path(args.audit), doc)
    if _box_pages(args):
        page = page_coverage(doc, _read(REPORT))
        if page.get("error") or page.get("state_write_error"):
            print(f"judge coverage pager: {page.get('error') or page.get('state_write_error')}",
                  file=sys.stderr)
    return _exit(doc["verdict"])


__all__ = ["BOX_STATE_ELSEWHERE", "FUTURE_SKEW_S", "GAUNTLET_HEARTBEAT", "GAUNTLET_STALL",
           "INCIDENTS", "PAGE_STATE_REL", "RATCHET", "REPAGE_H", "REPORT", "RULE",
           "SOURCE_VIEW_ENV", "STALE_H", "WINDOW_SLACK", "incidents", "judge", "judge_liveness",
           "liveness_fence", "main", "page_coverage", "render"]


if __name__ == "__main__":                                              # pragma: no cover
    sys.exit(main())
