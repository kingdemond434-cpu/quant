#!/usr/bin/env python3
"""JOB MANIFEST -- every scheduled job publishes success, freshness, hashes and last-valid output.

WHY (principal 2026-08-26: "every job must publish success, failure, freshness, input/output
hashes and last-valid output; alert on stale data, missing consumers, orphan modules and
zero-yield miners"). This desk has repeatedly discovered that a job was dead only by reading its
artifact by hand, hours or days later:

  * the tick tape raised ModuleNotFoundError EVERY HOUR and exited 0, so 16.2M ticks went
    unrecorded while the cycle printed "cycle done";
  * shadow_cycle exited 1 every 15 minutes on a Windows ACL error for an unknown period;
  * `promotion_gate.py` published NO-PRODUCER and returned 0, which the cadence scored as a duty
    fired -- for its entire existence;
  * a certifier rewrote the survivors file from n=1 to n=0 with exit code 0.

Exit codes are the wrong instrument. Every one of those jobs "succeeded". What distinguishes a
working organ from a dead one is whether its OUTPUT moved, and that is what this checks: an
artifact's hash, its age, and whether anything downstream reads it.

WHAT IS ALERTED, and why each is a distinct failure rather than one:

  STALE      -- the artifact exists but is older than the job's own cadence allows. The job is
                scheduled and silent; something is failing without saying so.
  FROZEN     -- the artifact is fresh but its CONTENT HASH has not changed across runs. The job
                runs, writes, and produces the same bytes: a loop that is turning without
                cutting. Distinct from STALE because the timestamp looks healthy.
  IDLE       -- fresh, byte-identical, AND the producer declared `unchanged_because` on this
                write: its input population is empty, so identical bytes are the correct output.
                Counted and printed, never alarmed. Without this, `decay_live.json` with an empty
                roster was FROZEN on 55 consecutive checks and blocked rung 0 of live readiness --
                a red that could clear only by deploying capital, which is the always-red detector
                this desk retires on sight (L1.37). The AGE check stays armed, so a producer that
                actually dies still goes STALE while carrying its declaration.
  MISSING    -- declared but never produced. An owed build, not a passing check (L1.28a).
  NO-CONSUMER-- produced, but nothing reads it. Either the consumer is unwired (a gap) or the
                artifact is dead weight; both are defects, and neither is visible from the job.
  EMPTY      -- fresh, moving, and its PAYLOAD says nothing was measured: n = 0, status
                UNMEASURED, an empty roster. Until 2026-09-08 this read OK, because age was the
                only instrument: execution_quality.json rewritten on time with 0 decisions was
                green. A row may declare an emptiness predicate (its third element) and the
                verdict then reads EMPTY rather than OK. Counted and printed, never alarmed --
                alarming it would rebuild the always-red detector L1.37 retires -- and it never
                replaces STALE, FROZEN or IDLE: an empty artifact that also stopped moving is
                still reported for having stopped.

RESEARCH LATENCY rides on the same report (2026-09-08). The blueprint's SLOs (start < 1h,
screen < 10m, gauntlet verdict < 24h) had no number anywhere on the desk; the hypothesis graph
carries every BORN and every verdict with a timestamp, so three rows are computed from it --
time-to-first-screen, time-to-gauntlet-verdict, time-to-certificate -- each naming the
timestamps it joins, and UNMEASURED with the count when no node has both ends. They are
published and printed, never alarmed: a research backlog is a fact for the principal and
research_productivity, not a repair request.

The manifest lives in data/job_manifest.json and RATCHETS: a job that has ever produced an
artifact is expected to keep producing one. Last-valid output and its hash are retained so a
regression can be pinpointed to a run rather than a day.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.repair_invoke import request_repair

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
STATE = ROOT / "data" / "job_manifest.json"
ALARM = ROOT / "data" / "JOB_MANIFEST_ALARM.txt"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"

#: An emptiness predicate: the parsed artifact -> why its payload measures nothing, or None.
EmptyFn = Callable[[Any], str | None]


def _empty_execution_quality(doc: Any) -> str | None:
    """shadow_execution.summarise: `decisions` and `filled` are the sample sizes."""
    if not isinstance(doc, dict):
        return None
    n = int(doc.get("decisions") or 0)
    if n == 0:
        return "decisions=0: no shadow decision to measure execution on"
    if int(doc.get("filled") or 0) == 0:
        return f"filled=0 of {n} decision(s): no fill to price"
    return None


def _empty_decay_live(doc: Any) -> str | None:
    """decay_monitor: `roster_state` UNMEASURED or an empty roster is a report about nothing."""
    if not isinstance(doc, dict):
        return None
    if str(doc.get("roster_state") or "") == "UNMEASURED":
        return f"roster_state=UNMEASURED: {doc.get('roster_why') or 'roster unreadable'}"
    if doc.get("live_sleeves") in (None, 0):
        return f"live_sleeves={doc.get('live_sleeves')!r}: nothing to decay"
    return None


def _empty_counterfactual(doc: Any) -> str | None:
    """counterfactual_replay: status UNMEASURED, or no priced row, is a world nobody replayed."""
    if not isinstance(doc, dict):
        return None
    status = str(doc.get("status") or "")
    if status == "UNMEASURED":
        return f"status=UNMEASURED: {doc.get('why') or ''}".rstrip(": ")
    ds = doc.get("dataset") if isinstance(doc.get("dataset"), dict) else {}
    priced = int(ds.get("rows_priced") or doc.get("rows_priced") or 0)
    if status and priced == 0:
        return f"status={status} with rows_priced=0: no decision was priced"
    return None


#: artifact -> (max_age_hours, who consumes it[, emptiness predicate]). The consumer is named so
#: "nothing reads this" is a checkable claim rather than an impression; the predicate, where a
#: row carries one, is what lets "rewritten on time with nothing in it" read EMPTY.
JOBS: dict[str, tuple[float, str] | tuple[float, str, EmptyFn]] = {
    "desks/mt5/reports/UNIVERSAL_SURVIVORS.json": (26.0, "shadow_admission, promoter, dashboard"),
    "desks/mt5/reports/shadow/shadow_state.json": (3.0, "promoter, reconciler, dashboard"),
    "desks/mt5/reports/shadow/scalp_shadow_state.json": (3.0, "shadow_cycle, dashboard"),
    "desks/mt5/reports/shadow/qquant_shadow_state.json": (3.0, "promoter, dashboard"),
    "desks/mt5/reports/execution_quality.json": (36.0, "promoter (promotion gate), dashboard",
                                                 _empty_execution_quality),
    # sleeve_registry.json is DELIBERATELY NOT HERE. `freeze()` is idempotent -- it returns
    # early once a key is frozen -- so the file only changes when a NEW sleeve enrols and an
    # unchanged registry is the HEALTHY state. Gauging it by age (it carried a 3.0h window)
    # made it red whenever the desk was well, and it was only ever GREEN because
    # `pull_desk_state.sh` restamped it every two minutes without `scp -p`. The property
    # that matters -- no clock RUNS without a frozen identity -- is measured every pass by
    # `forward_reconcile` as IDENTITY_UNFROZEN, and forward_reconcile.json IS age-gauged
    # below because it rewrites on every run. Do not "restore" this row: age is the wrong
    # instrument here, not a missing one.
    "desks/mt5/data/decay_live.json": (26.0, "dashboard, gateway risk", _empty_decay_live),
    "desks/mt5/data/forward_reconcile.json": (26.0, "operator audit"),
    # THE VETO RAILS' EVIDENCE. missed_growth reads it (desks/mt5/research/missed_growth.py:54)
    # to bill every rail, and its UNMEASURED state -- no bars cover the decision minutes on this
    # host -- was indistinguishable from a measured world by age alone.
    "desks/mt5/reports/COUNTERFACTUAL_WORLD.json": (26.0, "missed_growth (veto rails), dashboard",
                                                    _empty_counterfactual),
    "data/gauntlet_survivors.json": (26.0, "promotion_gate"),
    "web/desk_state.json": (0.5, "dashboard (Dell/phone)"),
    "data/authority_ratchet.json": (1.0, "earned-evidence floors"),
    "data/sameday_pipeline.json": (2.0, "same-day fence"),
    # A FIX THAT NEVER REACHED THE BOX IS NOT A FIX. Measured 2026-08-27: the only
    # code-sync path ships a hardcoded four-file list, so the whole forward/promotion
    # chain the desk box executes was outside it and `h1_source.py` had silently
    # diverged. Nothing measured that, which is why it lasted.
    "data/desk_code_parity.json": (1.0, "desk-parity fence (is the box running this code)"),
    # A register silently rolled back six hours is worse than a missing one: it still reads
    # as authoritative. Measured 2026-08-27, two heals in 44 seconds.
    "data/doc_replay_fence.json": (0.5, "doc replay fence (stale-snapshot rollback)"),
    # THE ONE NUMBER THE PATH TO LIVE CAPITAL TURNS ON, and until 2026-08-27 nothing measured
    # it. The whole forward book was silently re-based to day zero three times in 32 hours
    # (registry history: 08-26T01:42, 08-27T01:13, 08-27T03:31) against a `days >= 14`
    # promotion bar, while the shadow watchdog reported OPERATING/defects:[] throughout. If
    # this artifact goes stale the ratchet has stopped and the next re-base is invisible again.
    "data/forward_clock_ratchet.json": (1.5, "forward-clock ratchet (silent re-base detector)"),
    # 17 live timers -- including the mt5-suite ratchet, the universe-registry cost repair and
    # six research seats -- were firing from ~/.config/systemd/user with no committed copy
    # anywhere (measured 2026-08-27). A rebuilt box schedules none of them and nothing says so.
    "data/unit_parity.json": (2.0, "unit parity (live timer with no committed unit)"),
    # GAP 161: forward_reconcile.json was observed going a full day BACKWARD mid-session while
    # still reading as authoritative. If this artifact goes stale the rollback detector has
    # stopped and the desk's record of its own live book can regress unnoticed again.
    "data/artifact_monotonic.json": (0.5, "artifact rollback fence (stamp went backward)"),
}


def _read(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _job_row(value: tuple) -> tuple[float, str, EmptyFn | None]:
    """(max_age_h, consumer, emptiness predicate or None) from a two- or three-element row."""
    max_age_h, consumer = float(value[0]), str(value[1])
    empty_fn = value[2] if len(value) > 2 and callable(value[2]) else None
    return max_age_h, consumer, empty_fn


# ---------------------------------------------------------------------------- research latency
#: name -> (target hours or None, consumer, the timestamps joined). A None target is a row that
#: is MEASURED and reported but has no SLO: a certificate waits on forward evidence by law
#: (promotion bar days >= 14), so a latency target on it would contradict the forward floor.
LATENCY_SLOS: dict[str, tuple[float | None, str, str]] = {
    "time_to_first_screen": (
        1.0, "research_productivity, the principal",
        "BORN.at -> the first LATER row of any other fate (JUDGED, FAILED, CERTIFIED, RETIRED, "
        "BURIED) for the same node id in desks/mt5/data/hypothesis_graph.jsonl. Blueprint: start "
        "< 1h and screen < 10m; the graph cannot separate the two, so their sum bounds this row"),
    "time_to_gauntlet_verdict": (
        24.0, "research_productivity, the principal",
        "BORN.at -> the first LATER FAILED or CERTIFIED row for the same node id. Blueprint: "
        "gauntlet verdict < 24h"),
    "time_to_certificate": (
        None, "research_productivity, the principal",
        "BORN.at -> the first LATER CERTIFIED row for the same node id. No target: the "
        "certificate waits on forward evidence by law"),
}
_SCREEN_FATES = frozenset({"JUDGED", "FAILED", "CERTIFIED", "RETIRED", "BURIED"})
_VERDICT_FATES = frozenset({"FAILED", "CERTIFIED"})
_CERT_FATES = frozenset({"CERTIFIED"})
_LATENCY_FATES = {"time_to_first_screen": _SCREEN_FATES,
                  "time_to_gauntlet_verdict": _VERDICT_FATES,
                  "time_to_certificate": _CERT_FATES}


def _parse_at(s: Any) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _quantile(samples: list[float], q: float) -> float:
    if len(samples) == 1:
        return samples[0]
    return float(statistics.quantiles(samples, n=100, method="inclusive")[int(q * 100) - 1])


def latency_rows(graph_path: Path | None = None, now: datetime | None = None) -> dict[str, dict]:
    """The three research-latency rows from the hypothesis graph's own timestamps.

    Per node id the FIRST BORN row is the start; each SLO's end is the first row of its fate
    set whose `at` is LATER than that start. A node whose verdict row is not later than its
    BORN row (the backfill wrote verdicts before the compiler re-registered the cell) is
    counted as `unordered`, never as a negative latency; a node born with no end yet is `open`
    and its oldest age is reported, because a backlog is the latency the SLO is about.
    """
    graph_path = GRAPH if graph_path is None else graph_path   # resolved at call, not at def
    now = now or datetime.now(tz=UTC)
    out: dict[str, dict] = {}
    if not graph_path.exists():
        for name, (target, consumer, basis) in LATENCY_SLOS.items():
            out[name] = {"status": "UNMEASURED", "n": 0, "target_h": target,
                         "consumer": consumer, "basis": basis,
                         "why": f"{graph_path} absent: no timestamps to join"}
        return out
    born: dict[str, datetime] = {}
    later: dict[str, list[tuple[datetime, str]]] = {}
    n_rows = 0
    try:
        with graph_path.open("r", encoding="utf-8") as fh:
            for ln in fh:
                if not ln.strip():
                    continue
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                n_rows += 1
                nid, fate, at = str(r.get("id") or ""), str(r.get("fate") or ""), _parse_at(
                    r.get("at"))
                if not nid or at is None:
                    continue
                if fate == "BORN":
                    if nid not in born or at < born[nid]:
                        born[nid] = at
                else:
                    later.setdefault(nid, []).append((at, fate))
    except OSError as exc:
        for name, (target, consumer, basis) in LATENCY_SLOS.items():
            out[name] = {"status": "UNMEASURED", "n": 0, "target_h": target,
                         "consumer": consumer, "basis": basis, "why": f"unreadable: {exc}"}
        return out
    for name, (target, consumer, basis) in LATENCY_SLOS.items():
        fates = _LATENCY_FATES[name]
        samples: list[float] = []
        unordered = 0
        open_ages: list[float] = []
        for nid, t0 in born.items():
            ends = sorted(at for at, fate in later.get(nid, []) if fate in fates)
            after = [at for at in ends if at > t0]
            if after:
                samples.append((after[0] - t0).total_seconds() / 3600.0)
            elif ends:
                unordered += 1
            else:
                open_ages.append((now - t0).total_seconds() / 3600.0)
        row: dict[str, Any] = {"n": len(samples), "target_h": target, "consumer": consumer,
                               "basis": basis, "graph_rows": n_rows, "born_nodes": len(born),
                               "open": len(open_ages), "unordered": unordered,
                               "oldest_open_h": (round(max(open_ages), 2) if open_ages
                                                 else None)}
        if not samples:
            row.update(status="UNMEASURED",
                       why=(f"0 node(s) carry a BORN row followed by a later "
                            f"{'/'.join(sorted(fates))} row; {len(open_ages)} open, "
                            f"{unordered} unordered (verdict not later than BORN)"))
        else:
            samples.sort()
            p50, p90 = _quantile(samples, 0.5), _quantile(samples, 0.9)
            row.update(p50_h=round(p50, 2), p90_h=round(p90, 2), max_h=round(samples[-1], 2))
            if target is None:
                row.update(status="NO_TARGET", why="measured; no SLO by design (see basis)")
            elif p90 <= target:
                row.update(status="OK", why="")
            else:
                row.update(status="SLOW",
                           why=f"p90 {p90:.1f}h > target {target}h on {len(samples)} node(s)")
        out[name] = row
    return out


def _unchanged_because(path: Path) -> str | None:
    """A producer's own declaration that its output cannot move, or None.

    The contract is one optional top-level string field, `unchanged_because`, re-asserted on every
    write -- so the declaration goes stale exactly when the artifact does, and a producer cannot
    leave a permanent excuse behind. Only JSON objects can declare; anything else is judged as
    before.
    """
    doc = _read(path)
    why = (doc or {}).get("unchanged_because") if isinstance(doc, dict) else None
    return str(why) if isinstance(why, str) and why.strip() else None


def main() -> int:
    now = datetime.now(tz=UTC)
    state = _read(STATE) or {"jobs": {}}
    jobs = state.setdefault("jobs", {})
    findings: list[str] = []
    # IDLE is reported but is NOT a breach: it never reaches ALARM and never makes
    # this fence exit non-zero, because a correct organ with nothing to do is not a
    # failure. It is still printed and still counted in the summary.
    findings_idle: list[str] = []
    # EMPTY is reported and counted like IDLE, never alarmed: the payload says nothing was
    # measured, which is a reading, not a breach -- and an always-red row here would be the
    # detector L1.37 retires. It replaces only OK; STALE, IDLE and FROZEN keep precedence.
    findings_empty: list[str] = []
    rows: dict[str, dict] = {}

    for rel, spec in JOBS.items():
        max_age_h, consumer, empty_fn = _job_row(spec)
        path = ROOT / rel
        prior = jobs.get(rel, {})
        if not path.exists():
            rows[rel] = {"status": "MISSING", "consumer": consumer}
            if prior.get("ever_produced"):
                findings.append(
                    f"MISSING {rel}: produced before (last good {prior.get('last_valid_at')}) "
                    f"and now absent -- a produced artifact that vanishes is a regression, not a "
                    f"quiet day. Consumer: {consumer}")
            else:
                findings.append(f"MISSING {rel}: declared but NEVER produced -- an owed build. "
                                f"Consumer: {consumer}")
            jobs[rel] = {**prior, "status": "MISSING", "checked_at": now.isoformat()}
            continue

        digest = _hash(path)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        age_h = (now - mtime).total_seconds() / 3600
        status = "OK"
        checks_per_window = max(3, int(max_age_h * 2))   # manifest runs ~every 30 minutes
        if age_h > max_age_h:
            status = "STALE"
            findings.append(
                f"STALE {rel}: {age_h:.1f}h old, limit {max_age_h}h. The job is scheduled and "
                f"silent -- exit codes do not catch this, only the artifact does. "
                f"Consumer: {consumer}")
        # FROZEN MUST BE JUDGED AGAINST THE ARTIFACT'S OWN CADENCE, not a flat count. This read
        # "identical across 3 checks", but the manifest runs every 30 minutes while some artifacts
        # are DAILY -- execution_quality legitimately holds the same bytes across ~48 checks and
        # was reported FROZEN for it, which is a false alarm that trains the reader to ignore the
        # real ones. The honest test is whether the content has stood still for longer than the
        # job's own update interval allows.
        elif (digest and digest == prior.get("hash")
                and prior.get("hash_runs", 0) >= checks_per_window
                and (_idle := _unchanged_because(path))):
            # THE PRODUCER MAY DECLARE WHY ITS BYTES CANNOT MOVE. An organ whose input population
            # is empty writes the same output correctly and forever: `decay_live.json` with an
            # empty roster was FROZEN across 55 consecutive checks and blocked rung 0 of live
            # readiness, a red that could only clear by deploying capital. That is the always-red
            # detector this desk retires on sight (L1.37). IDLE is still COUNTED and still
            # printed, so this hides nothing -- and the age check above is untouched, so an organ
            # that genuinely dies still goes STALE while carrying its declaration.
            status = "IDLE"
            findings_idle.append(f"IDLE {rel}: {_idle} Consumer: {consumer}")
        elif (digest and digest == prior.get("hash")
                and prior.get("hash_runs", 0) >= checks_per_window):
            status = "FROZEN"
            findings.append(
                f"FROZEN {rel}: fresh ({age_h:.1f}h) but byte-identical across "
                f"{prior['hash_runs'] + 1} checks -- longer than its own {max_age_h}h update "
                f"window allows, so the job is running and writing the same output rather than "
                f"simply not being due yet. A loop turning without cutting. "
                f"Consumer: {consumer}")
        elif empty_fn is not None and (_why_empty := empty_fn(_read(path))):
            status = "EMPTY"
            findings_empty.append(
                f"EMPTY {rel}: fresh ({age_h:.1f}h) and moving, but the payload measures "
                f"nothing -- {_why_empty}. Consumer: {consumer}")

        rows[rel] = {"status": status, "age_h": round(age_h, 2), "hash": digest,
                     "consumer": consumer}
        jobs[rel] = {
            "status": status, "hash": digest,
            "hash_runs": (prior.get("hash_runs", 0) + 1) if digest == prior.get("hash") else 0,
            "checked_at": now.isoformat(timespec="seconds"),
            "ever_produced": True,
            "last_valid_at": (mtime.isoformat(timespec="seconds") if status == "OK"
                              else prior.get("last_valid_at")),
            "last_valid_hash": digest if status == "OK" else prior.get("last_valid_hash"),
            "max_age_h": max_age_h, "consumer": consumer,
        }

    # RETIRE THE ROWS THIS RUN NO LONGER EVALUATES, LOUDLY. `jobs` persists across runs and was
    # never pruned, so an artifact dropped from JOBS left its last verdict behind forever while
    # `summary` -- computed from `rows`, this run's evaluations -- silently stopped counting it.
    # Measured 2026-08-28: `jobs` held 17 rows and 2 FROZEN, `summary` said 16 and 1, and the
    # extra was `desks/mt5/data/sleeve_registry.json`, deliberately retired 19 hours earlier with
    # a good reason (age is the wrong instrument for an idempotent registry) and still reading
    # FROZEN to anything that walked `jobs`. Two consumers, two answers, one file. The row moves
    # to `retired` with the day it left rather than being deleted: a deliberate retirement stays
    # visible, and an ACCIDENTAL one -- a JOBS line dropped in an edit -- is discoverable here
    # instead of looking like the artifact was never monitored.
    retired = state.setdefault("retired", {})
    for rel in [k for k in jobs if k not in JOBS]:
        retired[rel] = {**jobs.pop(rel), "retired_at": now.isoformat(timespec="seconds"),
                        "note": "no longer declared in JOBS; last verdict frozen as-is"}
        findings.append(
            f"RETIRED {rel}: dropped from the manifest, last status "
            f"{retired[rel].get('status')}. If that was deliberate this line is the record; if a "
            f"JOBS entry was lost in an edit, the artifact is now unmonitored and this is how you "
            f"find out.")

    # RESEARCH LATENCY, from the graph's own timestamps. Published on the state and printed;
    # never a finding (see the module docstring).
    try:
        latency = latency_rows()
    except Exception as exc:                       # a broken graph is a reading, not a crash
        latency = {name: {"status": "UNMEASURED", "n": 0, "target_h": t, "consumer": c,
                          "basis": b, "why": f"{type(exc).__name__}: {exc}"}
                   for name, (t, c, b) in LATENCY_SLOS.items()}
    state["research_latency"] = latency

    state["checked_at"] = now.isoformat(timespec="seconds")
    state["summary"] = {s: sum(1 for r in rows.values() if r["status"] == s)
                        for s in sorted({r["status"] for r in rows.values()})}
    # THE SUMMARY MUST DESCRIBE THE ROWS. Anything reading `jobs` and anything reading `summary`
    # now count the same population. Reported rather than asserted: a liveness organ that dies on
    # its own consistency check is a worse failure than the miscount it was checking for, and an
    # `assert` vanishes entirely under -O.
    if not (sum(state["summary"].values()) == len(jobs) == len(rows)):
        findings.append(
            f"SELF-INCONSISTENT: summary counts {sum(state['summary'].values())}, jobs holds "
            f"{len(jobs)}, this run evaluated {len(rows)}. Two consumers of this file will "
            f"disagree until that is one number.")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, default=str), "utf-8")

    for line in findings_idle:
        print(f"  {line}")
    for line in findings_empty:
        print(f"  {line}")
    for name, row in latency.items():
        measured = (f"p50={row['p50_h']}h p90={row['p90_h']}h n={row['n']}"
                    if row.get("n") else row.get("why", ""))
        print(f"  LATENCY {name}: {row['status']} {measured}"
              + (f" (target {row['target_h']}h)" if row.get("target_h") else "")
              + (f"; open={row['open']} oldest_open={row['oldest_open_h']}h"
                 if row.get("open") else ""))
    if not findings:
        if ALARM.exists():
            ALARM.unlink()
        print(f"job manifest: all {len(rows)} artifact(s) fresh and moving {state['summary']}")
        return 0

    body = (f"JOB MANIFEST {now.isoformat(timespec='seconds')}\n\n"
            + "\n".join(f"  - {f}" for f in findings) + "\n")
    ALARM.write_text(body, "utf-8")
    print(body)
    request_repair("job-manifest breach")
    return 1


if __name__ == "__main__":
    sys.exit(main())
