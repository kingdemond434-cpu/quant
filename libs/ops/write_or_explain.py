#!/usr/bin/env python3
"""THE WRITE-OR-EXPLAIN CONTRACT -- an organ that produces nothing must SAY SO, by name.

THE DISEASE THIS EXISTS TO END, measured 2026-09-23 in eight separate failures on one day:

    an organ that produces nothing is indistinguishable from an organ with nothing to produce.

Every one of the eight was SILENT. Not one raised, not one logged, not one reddened a board:

    1. the law-gate battery had no Windows clock at all and was silent for 270 hours
    2. `producer_census` ran as a leg, exited rc=0 in ZERO seconds, and wrote nothing --
       its artifact sat 655 minutes stale against a 6-hour horizon with nothing complaining
    3. `coverage_tensor` exited rc=1 on EVERY pass: 199 of 204 ledger rows on the trading box
       carry `exit_code=1` with `output_hash: null`, and `COVERAGE_TENSOR.json` has NEVER
       existed on that box. An absent artifact read exactly like an organ with nothing to say.
    4. `ground_depth` and `independence_intake` run perfectly by hand and their legs never fire
       on the box -- ZERO compute-ledger rows each -- so both artifacts were simply absent
    5. the registry verdict sync died inside a 28 MB file, wrote no cursor, stranded 3,368
       verdicts, and reported nothing
    6. `certificate_truth` matched a status set that did not contain the string the retirement
       stamp writes, so the count FLAPPED between passes and neither reading was flagged
    7. preregistration is dead desk-wide behind a BARE EXCEPT in `donate` (another builder owns
       the fix; it is the same shape and it is why the bare-except audit ships with this)
    8. builder work sitting uncommitted on the box is reverted by the hourly adoption, silently

THE CONTRACT. Every leg already declares an artifact in the cycle's leg registry (the
`artifact` field of `docs/research/tier1_program.json`, keyed by `scheduled_by:
hourly_cycle:<leg>`). So the boundary can be enforced ONCE, for EVERY leg, instead of organ by
organ -- which is the only version of this that stays true as legs are added:

    stat the declared artifact immediately BEFORE the leg, and immediately AFTER.

    artifact mtime advanced              -> OK
    leg exited NON-ZERO                  -> LEG_FAILED, loud, carrying the exit code and the
                                            last lines of STDERR. Never swallowed.
    leg exited ZERO and nothing moved    -> SILENT_NO_OP. Its own defect class, naming the leg
                                            and the artifact. This is the one that has cost the
                                            most and until now had no name at all.
    nothing moved, but a NAMED REASON    -> DECLARED_NO_OP. Legitimate. A leg with nothing to
                                            write says so; silence is not a reason.

A leg that declares NO artifact is UNDECLARED -- reported, never counted as a pass (L1.28a:
absence is never a clean verdict). A leg that declares an artifact and produces no contract row
AT ALL in the window is NEVER_OBSERVED, which is failure 4's shape: the leg is not firing.

WHY THE EXISTENCE FILTER HAD TO GO, and it is the single most important line in this module.
`hourly_cycle._leg_artifacts` resolves a declared artifact with `if cand.exists()` and drops it
otherwise. That is exactly backwards for this purpose: on the trading box `COVERAGE_TENSOR.json`
has never been written, so the existence filter made `coverage_tensor` declare NOTHING, and a leg
that declares nothing cannot be caught failing to write. The organ that had never once succeeded
was the one organ the provenance envelope could not see. `declared_artifacts` here resolves the
DECLARED HOME whether or not anything is there yet -- an absent artifact is the signal, not a
reason to look away.

NEVER FAILS THE LEG, for the reason the compute ledger and the event log do not: an organ that
dies because its telemetry failed is worse than one that runs untelemetered. Every entry point
here is total; `observe` catches its own recording errors and returns the verdict regardless.

THE LEDGER IS APPEND-ONLY JSONL AND THE ARTIFACT IS DERIVED. The departments run CONCURRENTLY as
separate processes (`HOURLY_PLAN=dept:<name>`), so a read-modify-write of one summary JSON per
leg would race and lose rows. An `O_APPEND` line per leg cannot; the summary is rebuilt from the
lines by `scripts/check_write_or_explain.py`, which is also the fence.

HOW A SUBPROCESS LEG DECLARES A NO-OP. In-process legs return a dict and name `noop_reason`.
A subprocess cannot, so it prints ONE line to stdout or stderr::

    WRITE_OR_EXPLAIN: NO_OP nothing to compile -- 0 new donations since cursor 4821

and the contract reads it out of the captured tail. One print, no dependency, no import.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
#: libs/ops/write_or_explain.py -> repo root
REPO = _HERE.parents[2]
BASE = REPO / "desks" / "mt5"

#: The append-only contract ledger: one line per observed leg boundary. State path, so the
#: adoption keeps the box's own copy (`libs.ops.release.STATE_PREFIXES`).
#: `WRITE_OR_EXPLAIN_LEDGER` redirects it, which is how a test gets an isolated ledger and how a
#: session probes the live box without writing into the repo it is measuring.
LEDGER = Path(os.environ.get("WRITE_OR_EXPLAIN_LEDGER")
              or (BASE / "data" / "write_or_explain.jsonl"))
#: The published artifact, derived from the ledger.
ARTIFACT = BASE / "reports" / "WRITE_OR_EXPLAIN.json"
#: How far back a leg must have been observed before it counts as NEVER_OBSERVED. Six hours is
#: the horizon the desk already uses for a producer artifact, and it comfortably spans one pass
#: of every department plan.
WINDOW_H = 6.0
#: Where the leg registry declares each leg's artifact.
PROGRAM = REPO / "docs" / "research" / "tier1_program.json"

# ---------------------------------------------------------------- the verdict vocabulary
OK = "OK"
DECLARED_NO_OP = "DECLARED_NO_OP"
SILENT_NO_OP = "SILENT_NO_OP"
LEG_FAILED = "LEG_FAILED"
LEG_TIMEOUT = "LEG_TIMEOUT"
UNDECLARED = "UNDECLARED"
SKIPPED = "SKIPPED"
NEVER_OBSERVED = "NEVER_OBSERVED"

#: The verdicts that are DEFECTS -- each one a thing that was silent before today.
DEFECTS: frozenset[str] = frozenset({SILENT_NO_OP, LEG_FAILED, LEG_TIMEOUT, NEVER_OBSERVED})
#: The verdicts that are a clean pass. Enumerating PASSES, never failures (R0237): a verdict
#: added next year by someone who never reads this module fails closed.
PASSING: frozenset[str] = frozenset({OK, DECLARED_NO_OP, SKIPPED})

#: Keys an in-process leg may use to name its reason for writing nothing. EXPLICIT ONLY.
#:
#: `reason`, `why` and `note` are DELIBERATELY NOT HERE on their own. Dozens of legs already
#: return a `note` or a `why` about something unrelated, and accepting those would let a leg
#: launder its silence through a field it was already filling for another purpose -- the contract
#: would then read GREEN on exactly the organs it was built to catch. A no-op is declared on
#: purpose or it is not declared. `tail` is absent for the same reason: captured stdout is
#: exhaust, not a declaration.
_REASON_KEYS: tuple[str, ...] = ("noop_reason", "no_op_reason", "nothing_to_write",
                                 "declared_no_op", "skip_reason")
#: ...unless the leg's own STATUS says it is a no-op, in which case the generic fields are the
#: reason it is already carrying and there is nothing to launder.
_NOOP_STATUSES: frozenset[str] = frozenset({"NOOP", "NO_OP", "NOTHING_TO_DO", "NOTHING_TO_WRITE",
                                            "DECLARED_NO_OP", "IDLE", "EMPTY", "UP_TO_DATE"})
_SOFT_REASON_KEYS: tuple[str, ...] = ("reason", "why", "note", "detail")
#: The stdout/stderr marker a SUBPROCESS leg prints to declare a no-op.
_NOOP_MARKER = re.compile(r"WRITE_OR_EXPLAIN:\s*NO[_ ]?OP\b[:\s-]*(?P<reason>.*)", re.IGNORECASE)

#: Statuses that mean the leg never ran under this plan, so there is nothing to judge.
_SKIP_STATUSES: frozenset[str] = frozenset({"SKIPPED_BY_PLAN", "SKIPPED"})

_LEG_TABLE: dict[str, list[str]] | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ------------------------------------------------------------------ the declared artifacts
#: A repo-relative artifact path inside a declaration that is often PROSE, not a path.
#:
#: MEASURED 2026-09-23: 122 of the 243 hourly legs declare their artifact as something other than
#: a bare path -- `"desks/mt5/reports/MODEL_ZOO.json generator_entrants"`, `"a.json + b.json +
#: c.json"`, `"web/desk_state.json graph"`, `"reports/pf_allocation.json (`objective_terms`:
#: cost_of_w, ...)"`. Taking the whole string as a filename would give HALF THE DESK a path that
#: can never exist, and every one of those legs would read SILENT_NO_OP forever -- a fence that is
#: wrong about half its population is one nobody will act on (L1.43). So the paths are extracted.
#: LONGEST EXTENSION FIRST. Regex alternation is ORDERED, so `json|jsonl` matched `json` inside
#: `task_queue.jsonl` and handed back `desks/mt5/data/task_queue.json` -- a path that does not
#: exist, for a leg that writes perfectly well. Caught 2026-09-23 on `queue_cycle`.
_PATH_RE = re.compile(r"(?<![\w./-])((?:[\w.-]+/)+[\w.*-]+\.(?:jsonl|json|csv|parquet|parq|npz|"
                      r"txt|md|yaml|yml|sqlite|db))(?![\w.-])")


def artifact_paths(declaration: str) -> list[str]:
    """The repo-relative path(s) inside one `artifact` declaration, in order, de-duplicated.

    GLOBS ARE DROPPED. `data/.job_locks/*.peaks.json` names a pattern, not a file; statting it
    would report a path that never exists and manufacture a permanent false defect. A leg whose
    whole declaration is a glob therefore declares nothing here and reads UNDECLARED, which is an
    honest UNMEASURED rather than an invented failure.
    """
    out: list[str] = []
    for m in _PATH_RE.finditer(str(declaration)):
        p = m.group(1)
        if "*" in p or "?" in p or p in out:
            continue
        out.append(p)
    return out


def leg_table(*, refresh: bool = False) -> dict[str, list[str]]:
    """Every leg that DECLARES an artifact, mapped to the repo-relative path(s) it declares.

    Read from the cycle's own leg registry, so a leg added to the programme is covered the hour
    it lands and nothing here has to be maintained in parallel. Unreadable registry -> empty
    table, which the fence reports as UNMEASURED rather than as a clean desk.
    """
    global _LEG_TABLE
    if _LEG_TABLE is not None and not refresh:
        return _LEG_TABLE
    table: dict[str, list[str]] = {}
    try:
        doc = json.loads(PROGRAM.read_text(encoding="utf-8-sig"))
        for item in doc.get("items", []):
            art = str(item.get("artifact") or "").strip()
            sched = str(item.get("scheduled_by") or "")
            if not art or "hourly_cycle:" not in sched:
                continue
            for tok in sched.split(","):
                tok = tok.strip()
                if not tok.startswith("hourly_cycle:"):
                    continue
                # "hourly_cycle:coverage_tensor (meta department resident)" -> coverage_tensor
                leg = tok.split(":", 1)[1].split()[0].strip()
                if not leg:
                    continue
                paths = table.setdefault(leg, [])
                paths.extend(p for p in artifact_paths(art) if p not in paths)
        # A leg whose every declaration was prose or a glob declares NOTHING here. It reads
        # UNDECLARED (an honest UNMEASURED) rather than carrying an empty list into the report.
        table = {leg: paths for leg, paths in table.items() if paths}
    except (OSError, ValueError, TypeError):
        table = {}
    _LEG_TABLE = table
    return table


def declared_artifacts(leg: str) -> list[Path]:
    """The DECLARED HOME of leg `leg`'s artifact(s), whether or not anything is there.

    NO EXISTENCE FILTER. See the module docstring: filtering on existence is what made the one
    organ that had never succeeded invisible to the only check that could have caught it.
    """
    out: list[Path] = []
    for rel in leg_table().get(leg, []):
        cand = REPO / rel
        alt = BASE / rel
        # Prefer whichever root already holds it; with neither, the repo-relative declaration IS
        # the declared home and that is what we watch.
        out.append(cand if cand.exists() or not alt.exists() else alt)
    return out


# ------------------------------------------------------------------------------ the stat
def snapshot(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    """Stat every declared artifact. An unreadable path is recorded as absent, not skipped."""
    out: dict[str, dict[str, Any]] = {}
    for p in paths:
        try:
            st = p.stat()
            out[str(p)] = {"exists": True, "mtime_ns": int(st.st_mtime_ns),
                           "size": int(st.st_size)}
        except OSError:
            out[str(p)] = {"exists": False, "mtime_ns": 0, "size": -1}
    return out


def _moved(before: Mapping[str, dict[str, Any]],
           after: Mapping[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(paths that ADVANCED, paths that did NOT). Advanced = appeared, or mtime/size changed.

    Size is consulted as well as mtime because a coarse filesystem clock can land a rewrite in
    the same tick as the stat before it; a rewrite that changes neither is a rewrite of identical
    bytes, which for this contract is honestly indistinguishable from not writing at all.
    """
    wrote: list[str] = []
    still: list[str] = []
    for key, aft in after.items():
        bef = before.get(key) or {"exists": False, "mtime_ns": 0, "size": -1}
        appeared = not bef.get("exists") and bool(aft.get("exists"))
        changed = bool(aft.get("exists")) and (
            int(aft.get("mtime_ns") or 0) > int(bef.get("mtime_ns") or 0)
            or int(aft.get("size") or -1) != int(bef.get("size") or -1))
        (wrote if appeared or changed else still).append(key)
    return wrote, still


# ----------------------------------------------------------------------------- the reason
def named_reason(result: object) -> str:
    """The leg's own NAMED REASON for writing nothing, or "" if it offered none.

    Two protocols, because the legs come in two shapes: an in-process leg returns a dict and
    names a key; a subprocess leg prints one marker line. Anything else is silence.
    """
    if isinstance(result, Mapping):
        for key in _REASON_KEYS:
            val = result.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()[:400]
        if str(result.get("status") or "").upper() in _NOOP_STATUSES:
            for key in _SOFT_REASON_KEYS:
                val = result.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()[:400]
            return f"status={str(result.get('status')).upper()} (no further reason given)"
        for field in ("tail", "stderr_tail", "stdout_tail"):
            blob = result.get(field)
            if isinstance(blob, str):
                m = _NOOP_MARKER.search(blob)
                if m:
                    return (m.group("reason") or "declared no-op").strip()[:400] or "declared"
    elif isinstance(result, str):
        m = _NOOP_MARKER.search(result)
        if m:
            return (m.group("reason") or "declared no-op").strip()[:400] or "declared"
    return ""


def _stderr_tail(result: object, limit: int = 1200) -> str:
    if not isinstance(result, Mapping):
        return ""
    for field in ("stderr_tail", "stderr", "error", "tail"):
        blob = result.get(field)
        if isinstance(blob, str) and blob.strip():
            return blob.strip()[-limit:]
    return ""


def _exit_code(result: object) -> int | None:
    if isinstance(result, Mapping):
        code = result.get("exit_code")
        if isinstance(code, bool):
            return int(code)
        if isinstance(code, int):
            return code
    return None


# ----------------------------------------------------------------------------- the verdict
def judge(leg: str, before: Mapping[str, dict[str, Any]],
          after: Mapping[str, dict[str, Any]], result: object, *,
          raised: str = "", wall_s: float | None = None,
          verdict_exits: Sequence[int] = ()) -> dict[str, Any]:
    """The whole contract, in one total function. Never raises; never returns None.

    `raised` carries an exception the leg threw (the caller's except branch); `verdict_exits`
    are the exit codes this leg declares as VERDICTS rather than failures (a measurement organ
    must never be able to stop the desk by reporting bad news) -- a verdict exit is judged on
    whether it WROTE, exactly like a zero exit, so an organ cannot buy silence with an exit code.
    """
    wrote, still = _moved(before, after)
    declared = sorted(set(before) | set(after))
    rec: dict[str, Any] = {
        "leg": leg, "at": _now(), "wall_s": round(float(wall_s), 3) if wall_s is not None else None,
        "declared": [_rel(p) for p in declared], "wrote": [_rel(p) for p in wrote],
        "did_not_move": [_rel(p) for p in still],
        "exit_code": _exit_code(result), "reason": "", "stderr_tail": "", "verdict": OK,
        "detail": "",
    }
    status = ""
    if isinstance(result, Mapping):
        status = str(result.get("status") or "").upper()

    # 1. someone stopped the pass, or the plan does not own this leg: nothing to judge.
    if status in _SKIP_STATUSES:
        rec["verdict"] = SKIPPED
        rec["detail"] = f"not this clock's leg ({status})"
        return rec

    # 2. THE LEG RAISED, or reported an error, or its script is MISSING. Loud, always.
    err = raised or (str(result.get("error")) if isinstance(result, Mapping)
                     and result.get("error") else "")
    if err or status in {"LEG_FAILED", "MISSING", "ERROR"}:
        rec["verdict"] = LEG_FAILED
        rec["stderr_tail"] = (err or _stderr_tail(result))[:1200]
        why = str(result.get("why")) if isinstance(result, Mapping) and result.get("why") else ""
        rec["detail"] = (f"{leg} FAILED ({status or 'raised'}): "
                         f"{(err or why or rec['stderr_tail'] or 'no detail')[:300]}")
        return rec

    # 3. TIMEOUT: the leg was stopped part-way. A defect of its own, never a pass.
    if isinstance(result, Mapping) and result.get("timeout_s") and rec["exit_code"] is None:
        rec["verdict"] = LEG_TIMEOUT
        rec["detail"] = (f"{leg} exceeded its cycle budget of {result.get('timeout_s')}s and was "
                         f"stopped; {len(wrote)} of {len(declared)} declared artifact(s) moved")
        return rec

    code = rec["exit_code"]
    is_verdict_exit = code is not None and code in tuple(verdict_exits)

    # 4. NON-ZERO EXIT that the leg has NOT declared as a verdict: loud, with the code and stderr.
    if code is not None and code != 0 and not is_verdict_exit:
        rec["verdict"] = LEG_FAILED
        rec["stderr_tail"] = _stderr_tail(result)
        rec["detail"] = (f"{leg} exited {code}; {len(wrote)} of {len(declared)} declared "
                         f"artifact(s) moved. stderr: {rec['stderr_tail'][-400:] or '(empty)'}")
        return rec

    # 5. It exited cleanly (or on a declared verdict code). Did it WRITE?
    if not declared:
        rec["verdict"] = UNDECLARED
        rec["detail"] = (f"{leg} declares no artifact in the leg registry, so the contract "
                         f"cannot tell a silent no-op from a good pass -- UNMEASURED, not a pass")
        return rec
    if wrote:
        rec["verdict"] = OK
        rec["detail"] = (f"{leg} wrote {len(wrote)} of {len(declared)} declared artifact(s)"
                         + (f" (verdict exit {code})" if is_verdict_exit else ""))
        return rec

    # 6. NOTHING MOVED. The whole point of the module: did it SAY WHY?
    reason = named_reason(result)
    absent = [p for p in still if not (after.get(p) or {}).get("exists")]
    if reason:
        rec["verdict"] = DECLARED_NO_OP
        rec["reason"] = reason
        rec["detail"] = f"{leg} wrote nothing and said why: {reason}"
        return rec
    rec["verdict"] = SILENT_NO_OP
    rec["detail"] = (
        f"{leg} exited {0 if code is None else code} and NOT ONE of its {len(declared)} declared "
        f"artifact(s) moved, with no named reason: {', '.join(rec['did_not_move'][:3])}"
        + (f" ({len(absent)} of them do not exist at all)" if absent else "")
        + f"{'' if wall_s is None else f'; the leg took {wall_s:.2f}s'}")
    return rec


def _rel(p: str | Path) -> str:
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except (ValueError, OSError):
        return str(p)


# ------------------------------------------------------------------------------ recording
def record(rec: Mapping[str, Any], *, ledger: Path | None = None) -> bool:
    """Append one contract row. O_APPEND, one line, so concurrent departments cannot lose rows.

    Returns whether it was written. NEVER RAISES -- a telemetry failure must not fail the leg,
    and the caller treats False as "unrecorded" rather than as a reason to stop.
    """
    # A TEST MUST NOT WRITE INTO DESK STATE (R0748). `test_hourly_cycle_legs_are_callable` drives
    # `_costed` with simulated failing legs, so without this the suite appends phantom legs
    # ("boom", "bad") to the box's own contract ledger and the fence then reports them as real
    # defects. A test that wants the ledger names one, via `ledger=` or WRITE_OR_EXPLAIN_LEDGER.
    if ledger is None and os.environ.get("PYTEST_CURRENT_TEST") \
            and not os.environ.get("WRITE_OR_EXPLAIN_LEDGER"):
        return False
    path = ledger or LEDGER
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(dict(rec), default=str, ensure_ascii=False) + "\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        return True
    except (OSError, ValueError, TypeError):
        return False


def observe(leg: str, before: Mapping[str, dict[str, Any]], result: object, *,
            raised: str = "", wall_s: float | None = None,
            verdict_exits: Sequence[int] = (), record_row: bool = True) -> dict[str, Any]:
    """The one call a cycle runner makes AFTER a leg: stat again, judge, record, return.

    Total by construction. Any failure inside becomes a row describing that failure rather than
    an exception escaping into the leg's own result -- the contract is not allowed to become the
    ninth silent failure of the day.
    """
    try:
        after = snapshot(declared_artifacts(leg))
        rec = judge(leg, before, after, result, raised=raised, wall_s=wall_s,
                    verdict_exits=verdict_exits)
    except Exception as exc:
        rec = {"leg": leg, "at": _now(), "verdict": LEG_FAILED, "declared": [], "wrote": [],
               "did_not_move": [], "exit_code": None, "reason": "", "stderr_tail": "",
               "detail": f"write-or-explain contract itself failed for {leg}: "
                         f"{type(exc).__name__}: {exc}"}
    if record_row:
        rec["recorded"] = record(rec)
        maybe_publish()
    return rec


# ---------------------------------------------------------------- the derived summary
def _age_h(stamp: object) -> float | None:
    try:
        dt = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (datetime.now(UTC) - dt).total_seconds() / 3600.0


def latest_by_leg(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The most recent contract row per leg. Rows are appended in order, so last wins."""
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        leg = str(row.get("leg") or "")
        if leg:
            out[leg] = row
    return out


def build_report(*, window_h: float = WINDOW_H) -> dict[str, Any]:
    rows = read_ledger()
    declared = leg_table()
    rep: dict[str, Any] = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "window_h": window_h, "ledger": str(LEDGER), "ledger_rows": len(rows),
        "legs_declaring_artifact": len(declared),
        "silent_no_ops": [], "failed": [], "never_observed": [], "declared_no_ops": [],
        "undeclared": [], "ok": [], "scanned": 0, "status": "UNMEASURED", "detail": "",
    }
    if not declared:
        rep["detail"] = (f"the leg registry at {PROGRAM.name} declares no artifacts, so the "
                         f"contract has nothing to enforce -- UNMEASURED, not clean")
        return rep
    if not rows:
        rep["detail"] = (f"no contract ledger at {LEDGER}: no leg boundary has been observed "
                         f"on this machine yet")
        return rep

    latest = latest_by_leg(rows)
    fresh = {leg: r for leg, r in latest.items()
             if (_age_h(r.get("at")) is None or (_age_h(r.get("at")) or 0.0) <= window_h)}
    for leg, row in sorted(fresh.items()):
        verdict = str(row.get("verdict") or "")
        entry = {"leg": leg, "verdict": verdict, "at": row.get("at"),
                 "wall_s": row.get("wall_s"), "exit_code": row.get("exit_code"),
                 "declared": row.get("declared") or [],
                 "did_not_move": row.get("did_not_move") or [],
                 "reason": row.get("reason") or "", "detail": row.get("detail") or "",
                 "stderr_tail": (row.get("stderr_tail") or "")[-600:]}
        if verdict == SILENT_NO_OP:
            rep["silent_no_ops"].append(entry)
        elif verdict in (LEG_FAILED, LEG_TIMEOUT):
            rep["failed"].append(entry)
        elif verdict == DECLARED_NO_OP:
            rep["declared_no_ops"].append(entry)
        elif verdict == UNDECLARED:
            rep["undeclared"].append(entry)
        elif verdict == OK:
            rep["ok"].append(entry)
    # A LEG THAT DECLARES AN ARTIFACT AND WAS NEVER OBSERVED IS NOT FIRING (failure 4's shape).
    for leg in sorted(declared):
        seen = latest.get(leg)
        age = _age_h(seen.get("at")) if seen else None
        if seen is None:
            rep["never_observed"].append(
                {"leg": leg, "verdict": NEVER_OBSERVED, "declared": declared[leg],
                 "detail": f"{leg} declares {declared[leg][0]} and has NEVER been observed at a "
                           f"leg boundary on this machine"})
        elif age is not None and age > window_h:
            rep["never_observed"].append(
                {"leg": leg, "verdict": NEVER_OBSERVED, "declared": declared[leg],
                 "last_seen_h": round(age, 2),
                 "detail": f"{leg} has not reached a leg boundary for {age:.1f} h "
                           f"(window {window_h} h); its clock is not firing"})
    rep["scanned"] = len(fresh)
    n_sil, n_fail = len(rep["silent_no_ops"]), len(rep["failed"])
    n_never = len(rep["never_observed"])
    if n_sil or n_fail:
        rep["status"] = "BREACH"
        rep["detail"] = (f"{n_sil} leg(s) exited clean and wrote NOTHING with no named reason; "
                         f"{n_fail} failed or timed out; {n_never} declare an artifact and never "
                         f"reached a leg boundary in {window_h} h")
    elif n_never:
        rep["status"] = "UNOBSERVED"
        rep["detail"] = (f"{n_never} leg(s) declare an artifact and produced no contract row in "
                         f"{window_h} h -- their clocks are not firing")
    else:
        rep["status"] = "CONTRACT_KEPT"
        rep["detail"] = (f"{len(rep['ok'])} leg(s) wrote, {len(rep['declared_no_ops'])} declared a "
                         f"named no-op, {len(rep['undeclared'])} declare no artifact at all")
    return rep


def publish(rep: dict[str, Any]) -> Path:
    """Write the artifact. The contract's own artifact obeys the contract: it is always written."""
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARTIFACT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    tmp.replace(ARTIFACT)
    return ARTIFACT


#: How stale the published artifact may get before a leg boundary rebuilds it.
PUBLISH_EVERY_S = 300


def maybe_publish(*, every_s: int = PUBLISH_EVERY_S) -> bool:
    """Rebuild `WRITE_OR_EXPLAIN.json` if it is older than `every_s`. Throttled, and total.

    THE CONTRACT PUBLISHES ITSELF, and that is deliberate. Its fence is registered in the law
    gate -- which, measured 2026-09-23, HAS NO WINDOWS CLOCK and was silent for 270 hours (that
    was failure 1). An artifact whose only writer is a battery that never runs on the box would
    be this work repeating the very defect it was built to end, so the cycle that fills the
    ledger also keeps the summary of it current, whatever the battery does.

    Rebuilding is a read of the ledger tail and one small JSON write, at most once every five
    minutes per process, so it costs a leg nothing measurable.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False                                # the suite never rewrites desk state (R0748)
    try:
        try:
            age = datetime.now(UTC).timestamp() - ARTIFACT.stat().st_mtime
            if age < every_s:
                return False
        except OSError:
            pass                                    # never published here yet: publish now
        publish(build_report())
        return True
    except Exception:
        return False                                # telemetry never fails a leg


def before_leg(leg: str) -> dict[str, dict[str, Any]]:
    """The one call a cycle runner makes BEFORE a leg. Total; an unreadable registry stats none."""
    try:
        return snapshot(declared_artifacts(leg))
    except Exception:
        return {}


def read_ledger(*, ledger: Path | None = None, limit: int = 400_000) -> list[dict[str, Any]]:
    """Every contract row on disk, oldest first. A malformed line is skipped, never fatal."""
    path = ledger or LEDGER
    rows: list[dict[str, Any]] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    rows.append(obj)
    except OSError:
        return []
    return rows[-limit:]


def is_defect(verdict: object) -> bool:
    return str(verdict) in DEFECTS
