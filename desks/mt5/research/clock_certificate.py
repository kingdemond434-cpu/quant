#!/usr/bin/env python3
"""CLOCK IMPLIES CERTIFICATE -- a forward clock without one is a BREACH, and it is TESTED, not cut.

THE PRINCIPAL'S LAW (2026-09-23): "all forward clocks must be certified -- any forward clock
running without a certificate is a breach, and they all must be tested and then put on clocks."

THE LAW RAISES TESTING; IT DOES NOT REDUCE EVIDENCE, and the difference is the whole design. The
obvious reading -- find the uncertified clocks and switch them off -- would shrink the forward
book to the size of the canon overnight and reintroduce exactly the scarcity the principal
abolished the same week ("no quota or scarcity ever on forward evidence slots"). A forward clock
gathers evidence and deploys no capital; killing one before its cell has been judged destroys
the evidence that would have settled it and buys nothing. So a breach pushes its CELL TO THE
FRONT OF THE JUDGE'S QUEUE and the clock keeps running while it waits:

    BACKED              a current certificate backs this clock -- the law is satisfied
    BREACHED            no certificate backs it: a breach, named with its cell, queued FIRST
    AWAITING_JUDGEMENT  a breached clock whose cell is queued and the judge has not reached it;
                        it KEEPS its clock and its age is published, because removing
                        evidence-gathering before the test is the scarcity that was abolished
    RETIRED             the judge REJECTED the cell (its terminal gate is the reason) or the row
                        was already terminal -- this is the only way a clock is taken away

THE CANON IS READ AND NEVER WRITTEN. `reports/UNIVERSAL_SURVIVORS.json` and
`shadow_admission.authorized_runs` belong to the certificate lane; this module opens them and
nothing else. AND IT REFUSES TO JUDGE A BREACH WHILE THE CANON IS MOVING: measured 2026-09-23,
two reads a minute apart returned n=28 and n=0 while that lane was mid-repair. Retiring 489
clocks against a canon that momentarily reads zero would be the largest evidence loss this desk
has ever taken, so an empty or unreadable canon makes backing UNMEASURED (L1.28a) -- a verdict,
never a breach and never a pass.

THE JOIN, and its grain stated honestly. A clock's key is the engine's (`sleeve_key`); the
judge's ledger rows are keyed by the gauntlet's own cell grammar. The one join that speaks both
languages is the ENGINE'S ROSTER, which is built from the canon by the engine's own key function
-- so `key in roster` IS "a certificate backs this clock", with no re-derivation to drift. The
verdict lookup is coarser and is labelled as such: it matches (symbol, family, timeframe) against
`data/hypotheses/gate_verdict_ledger.jsonl`, streamed a line at a time because the sibling
`universal_gates_external.json` is 88 MB and no organ should land that in RAM on an 8 GB box.
A REJECT is claimed only on a verdict that actually ran: `terminal_gate` UNKNOWN or a
`NOT_RUN_*_DEFERRED` status is a cell the judge never reached, which is AWAITING, not a failure.

Artifacts: the `certificate` block of `desks/mt5/reports/CLOCK_LIVENESS.json` (breached,
awaiting, backed, retired every pass) and the breach-age ledger
`desks/mt5/data/clock_breach_ledger.json`, which is what makes "older than one judging cycle"
a measured age rather than a guess.
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: THE CANON HAS TWO SOURCES AND THE SECOND IS THE ONE THAT HOLDS. `shadow_admission.
#: CANON_SOURCES` reads the gauntlet's latest sweep first and falls back to the last SEALED
#: canon, and the roster this module joins against is built through exactly that order -- so
#: reading only the first file would have declared 150 clocks in breach whenever a sweep left
#: `reports/UNIVERSAL_SURVIVORS.json` momentarily empty. MEASURED 2026-09-23: the sweep file
#: read n=0 while the sealed canon read n=28 and `authorized_runs` returned 148 runs.
CANON = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SEALED_CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
VERDICTS = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
BREACH_LEDGER = DESK / "data" / "clock_breach_ledger.json"
BREACH_DOCKET = DESK / "reports" / "CLOCK_CERTIFICATE_BREACH.json"
TASK_QUEUE = DESK / "data" / "task_queue.jsonl"

BACKED, BREACHED, AWAITING, RETIRED, UNMEASURED = (
    "BACKED", "BREACHED", "AWAITING_JUDGEMENT", "RETIRED", "UNMEASURED")
BACKING_STATES = (BACKED, BREACHED, AWAITING, RETIRED, UNMEASURED)

#: One judging cycle. The ten-gate sweep is hourly (`MT5-Gauntlet`, leg `external_gauntlet`), so
#: a breach that has outlived one of them was queued FIRST and still not reached -- which is a
#: fact about the judge's throughput, and the fence says so rather than letting it age quietly.
JUDGING_CYCLE_S = 3600.0

#: The breach queue is submitted at a priority above every other `recertify` task, because
#: `TaskQueue.claim` sorts by `-priority`: a clock running uncertified is the desk's only
#: currently-breached law, so it is judged before work that breaks nothing.
BREACH_PRIORITY = 1000.0

#: A verdict whose downstream status starts with one of these never ran: the judge stamped the
#: cell and the budget died before the gates. It is AWAITING, not a rejection.
NOT_REACHED = ("NOT_RUN_BUILD_BUDGET", "NOT_RUN_MEMORY_BUDGET", "DEFERRED", "NOT_RUN_QUEUED")

#: THE ONLY REJECTS THAT MAY TAKE A CLOCK AWAY ON THIS JOIN, and the restraint is not timidity --
#: it is the ban on guessing. The verdict ledger is keyed by the gauntlet's own cell hash and a
#: clock is keyed by the engine's `sleeve_key`; the two cannot be joined below (symbol, family,
#: chart) without importing the sealed judge. So a reject at a gate whose answer DEPENDS ON THE
#: PARAMETERS -- deflated_sharpe, pbo, walk_forward, the rest -- may belong to a sibling
#: parameterization, and acting on it would retire a clock whose own cell was never judged.
#: `economic_prior` and `symbol_eligibility` are different: they rule on whether the FAMILY
#: encodes an economic cause at all and whether the SYMBOL is tradeable, and no choice of
#: parameters changes either answer. Everything else waits for the judge to reach the exact
#: cell -- which is what queueing it first is for.
PARAM_INDEPENDENT_REJECTS = ("economic_prior", "symbol_eligibility", "universe_policy",
                             "asset_class_lane", "untradeable_symbol")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def now_utc() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------------- the canon
def canon_state(path: Path | None = None) -> tuple[int | None, str]:
    """(certificates in the canon, why). None is UNMEASURED and is NOT zero.

    The certificate lane owns this file and is repairing it; an absent, unreadable or EMPTY canon
    means the desk cannot currently say what is certified, which is the one state in which no
    breach may be declared.
    """
    for src in ([path] if path is not None else [CANON, SEALED_CANON]):
        doc = _read_json(src)
        if not isinstance(doc, dict):
            continue
        survivors = doc.get("survivors")
        if isinstance(survivors, dict) and survivors:
            return len(survivors), (f"{len(survivors)} certificate(s) in {src.name} "
                                    f"(read through shadow_admission.CANON_SOURCES order)")
        n = doc.get("n")
        if isinstance(n, int) and n > 0:
            return n, f"{src.name} declares n={n} with no readable survivor map"
    return None, ("every canon source is absent or EMPTY (the sweep file and the sealed canon "
                  "both read n=0): the certificate lane is mid-repair, so backing is UNMEASURED "
                  "and no clock may be declared in breach against it")


# -------------------------------------------------------------------------------- the verdicts
def _tf_of(cell: str) -> str:
    head = str(cell).split(".", 1)[0]
    return head.split("@", 1)[1].upper() if "@" in head else "H1"


def verdict_index(cells: Iterable[tuple[str, str, str]],
                  path: Path | None = None) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Newest RAN verdict per (symbol, family, timeframe), for the wanted cells only.

    STREAMED, ONE LINE AT A TIME. The sibling `universal_gates_external.json` is 88 MB and eight
    modules once landed a 57 MB queue in RAM apiece on this box; a census must never be the
    thing that pushes the judge out of memory.
    """
    want = {(str(s).upper(), str(f), str(t).upper()) for s, f, t in cells}
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    p = path or VERDICTS
    if not want or not p.exists():
        return out
    try:
        with p.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.startswith("{"):
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                key = (str(row.get("sym") or "").upper(), str(row.get("family") or ""),
                       _tf_of(row.get("cell") or ""))
                if key not in want:
                    continue
                prev = out.get(key)
                if prev is None or str(row.get("at") or "") >= str(prev.get("at") or ""):
                    out[key] = row
    except OSError:
        return out
    return out


def verdict_state(row: Mapping[str, Any] | None) -> tuple[str, str]:
    """(state, reason). REJECTED only on a verdict that actually ran its gates."""
    if row is None:
        return AWAITING, "the judge holds no verdict for this cell yet"
    status = str(row.get("downstream_status") or "")
    gate = str(row.get("terminal_gate") or "")
    if any(status.upper().startswith(x) or x in status.upper() for x in NOT_REACHED):
        return AWAITING, (f"the judge stamped this cell and never ran its gates "
                          f"({status}): queued, not judged")
    if not gate or gate.upper() == "UNKNOWN":
        return AWAITING, ("the verdict names no terminal gate, so the ten gates did not "
                          "reach a conclusion on this cell")
    if row.get("passed") is True:
        return BACKED, f"the judge passed this cell at {row.get('at')}"
    if gate.lower() in PARAM_INDEPENDENT_REJECTS:
        return RETIRED, (f"the ten-gate judge REJECTED this cell at gate `{gate}` "
                         f"({status or 'no downstream status'}) on {row.get('at')} -- a gate "
                         f"whose answer no choice of parameters can change, so the rejection "
                         f"is this clock's")
    return AWAITING, (f"a sibling cell of this family and symbol was rejected at gate `{gate}`, "
                      f"which is parameter-dependent: that verdict is not this clock's and the "
                      f"clock keeps accruing until the judge reaches its exact cell")


# ------------------------------------------------------------------------------ breach ledger
def load_ledger(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or BREACH_LEDGER)
    return doc if isinstance(doc, dict) else {}


def save_ledger(doc: Mapping[str, Any], path: Path | None = None) -> None:
    p = path or BREACH_LEDGER
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass


# -------------------------------------------------------------------------- the judge's queue
def push_to_front(cells: Sequence[Mapping[str, Any]], *, apply: bool = True,
                  queue_path: Path | None = None) -> dict[str, Any]:
    """Queue every breached cell for judgement AT THE FRONT. This is the whole remedy.

    `TaskQueue.claim` sorts by `-priority`, and the hourly leg `recertify_canon` already claims
    `recertify` tasks -- so a breached cell submitted here is the next thing the judge's lane
    picks up, ahead of work that breaches no law. Dedupe is per cell against LIVE work only, so
    a cell waiting in the queue is not re-queued every hour and one that was judged and breached
    again is.
    """
    out: dict[str, Any] = {"submitted": 0, "already_queued": 0, "cells": [], "applied": apply}
    if not cells:
        out["why"] = "no breached cell to queue"
        return out
    try:
        from libs.ops.task_queue import TaskQueue
    except Exception as exc:
        out["why"] = f"task_queue unimportable ({type(exc).__name__}: {exc}); queueing UNMEASURED"
        return out
    if not apply:
        out["why"] = "dry run: the cells that would be queued are listed, nothing was submitted"
        out["cells"] = [str(c.get("cell")) for c in cells][:100]
        return out
    try:
        q = TaskQueue(queue_path or TASK_QUEUE)
    except Exception as exc:
        out["why"] = f"queue unopenable ({type(exc).__name__}: {exc})"
        return out
    for c in cells:
        cell = str(c.get("cell") or "")
        if not cell:
            continue
        try:
            task = q.submit(
                "recertify",
                payload={"cell": cell, "sym": c.get("symbol"), "family": c.get("family"),
                         "timeframe": c.get("timeframe"), "clock": c.get("key"),
                         "why": ("a forward clock is running on this cell with no certificate: "
                                 "CLOCK IMPLIES CERTIFICATE (principal 2026-09-23). Judge it "
                                 "first; the clock keeps accruing until you do.")},
                priority=BREACH_PRIORITY, dedupe_key=f"clock_breach:{cell}",
                source_event="clock_certificate.breach")
        except Exception as exc:
            out.setdefault("errors", []).append(f"{cell}: {type(exc).__name__}: {exc}")
            continue
        if task is None:
            out["already_queued"] += 1
        else:
            out["submitted"] += 1
            if len(out["cells"]) < 100:
                out["cells"].append(cell)
    out["why"] = (f"{out['submitted']} breached cell(s) submitted at priority "
                  f"{BREACH_PRIORITY:.0f} (the front of the judge's queue), "
                  f"{out['already_queued']} already waiting there")
    return out


# --------------------------------------------------------------------------------- the census
def cell_of(clock: Mapping[str, Any]) -> str:
    """The cell this clock's evidence belongs to, in the gauntlet's own prefix grammar."""
    sym, tf = str(clock.get("symbol") or ""), str(clock.get("timeframe") or "H1")
    fam = family_of(clock)
    head = sym if tf.upper() == "H1" else f"{sym}@{tf.upper()}"
    return f"{head}.{fam}"


def family_of(clock: Mapping[str, Any]) -> str:
    """The family from the clock's key: `SYM.family.selector...`, or the breakout default."""
    key = str(clock.get("key") or "")
    parts = key.split("#", 1)[0].split("@", 1)[0].split(".")
    return parts[1] if len(parts) >= 3 else "session_range_breakout"


def audit(clocks: Sequence[Mapping[str, Any]], *, roster: set[str] | None,
          now: datetime | None = None, apply: bool = True,
          canon_path: Path | None = None, verdict_path: Path | None = None,
          ledger_path: Path | None = None,
          queue_path: Path | None = None) -> dict[str, Any]:
    """The whole law in one pass: trace, queue, keep, retire -- and publish the four counts."""
    now = now or now_utc()
    n_canon, canon_why = canon_state(canon_path)
    rows: list[dict[str, Any]] = []
    unmeasurable = n_canon is None or roster is None
    for c in clocks:
        row = {"lane": c.get("lane"), "key": c.get("key"), "symbol": c.get("symbol"),
               "family": family_of(c), "timeframe": c.get("timeframe"),
               "cell": cell_of(c), "clock_verdict": c.get("verdict"),
               "status": c.get("status")}
        if str(c.get("verdict")) == "RETIRED" or str(c.get("status") or "").upper().startswith(
                ("RETIRED", "VOID", "REFUSED", "QUARANT", "KILLED", "DEAD")):
            row |= {"backing": RETIRED,
                    "why": "the clock is already terminal: it runs on nothing and breaches nothing"}
        elif unmeasurable:
            row |= {"backing": UNMEASURED,
                    "why": (canon_why if n_canon is None else
                            "the engine roster is unreadable on this host, so backing is "
                            "UNMEASURED")}
        elif str(c.get("key")) in (roster or set()):
            row |= {"backing": BACKED,
                    "why": (f"a current certificate backs this clock: its key is on "
                            f"`shadow_forward`'s roster, which is built from the canon "
                            f"({canon_why})")}
        else:
            row |= {"backing": BREACHED,
                    "why": ("no certificate backs this clock: CLOCK IMPLIES CERTIFICATE "
                            "(principal 2026-09-23) -- its cell is queued for judgement FIRST "
                            "and the clock keeps accruing until the judge rules")}
        rows.append(row)

    breached = [r for r in rows if r["backing"] == BREACHED]
    index = verdict_index(((str(r["symbol"]), str(r["family"]), str(r["timeframe"]))
                           for r in breached), verdict_path)
    ledger = load_ledger(ledger_path)
    seen = dict(ledger.get("first_seen") or {})
    retire: list[dict[str, Any]] = []
    for r in breached:
        state, why = verdict_state(index.get((str(r["symbol"]).upper(), str(r["family"]),
                                              str(r["timeframe"]).upper())))
        first = seen.setdefault(str(r["cell"]), now.isoformat())
        try:
            age = (now - datetime.fromisoformat(str(first))).total_seconds()
        except ValueError:
            age = 0.0
        r |= {"judge": state, "judge_why": why, "breach_first_seen": first,
              "breach_age_s": round(max(0.0, age), 1),
              "over_one_judging_cycle": age > JUDGING_CYCLE_S}
        if state == RETIRED:
            r["backing"] = RETIRED
            r["why"] = why                      # the verdict IS the reason the clock is taken
            retire.append(r)
        elif state == BACKED:
            # The judge passed it and the canon has not caught up; the clock stays and says so.
            r["backing"] = AWAITING
            r["why"] = (f"{why} -- the clock keeps accruing until the certificate lane writes it "
                        f"into the canon")
        else:
            r["backing"] = AWAITING
            r["why"] = (f"{why}; queued FIRST for judgement and the clock keeps accruing, "
                        f"because removing evidence before the test is the scarcity the "
                        f"principal abolished")

    queue = push_to_front([r for r in rows if r["backing"] in (BREACHED, AWAITING)],
                          apply=apply, queue_path=queue_path)
    still = {r["cell"] for r in rows if r["backing"] in (BREACHED, AWAITING)}
    if apply:
        save_ledger({"first_seen": {k: v for k, v in seen.items() if k in still},
                     "at": now.isoformat(), "n_breached": len(still),
                     "rule": ("a cell leaves this ledger only when its clock is backed or "
                              "retired; the age it carries is what the fence measures")},
                    ledger_path)
    counts = {s: sum(1 for r in rows if r["backing"] == s) for s in BACKING_STATES}
    overdue = [r for r in rows if r.get("over_one_judging_cycle")
               and r["backing"] in (BREACHED, AWAITING)]
    return {
        "law": ("CLOCK IMPLIES CERTIFICATE (principal 2026-09-23): a forward clock without a "
                "certificate is a breach; it is TESTED FIRST, never cut, and only the judge's "
                "rejection takes a clock away"),
        "canon": {"n": n_canon, "why": canon_why, "source": str(CANON.name), "written_by": "NEVER"},
        "counts": counts,
        "breached": counts[BREACHED] + counts[AWAITING],
        "awaiting": counts[AWAITING], "backed": counts[BACKED], "retired": counts[RETIRED],
        "overdue_beyond_one_judging_cycle": len(overdue),
        "judging_cycle_s": JUDGING_CYCLE_S,
        "queue": queue,
        "retire": [{k: r.get(k) for k in ("lane", "key", "cell", "why")} for r in retire],
        "rows": [{k: r.get(k) for k in
                  ("lane", "key", "cell", "symbol", "family", "timeframe", "backing", "judge",
                   "breach_age_s", "over_one_judging_cycle", "why")} for r in rows],
    }


def publish_docket(doc: Mapping[str, Any], path: Path | None = None) -> Path:
    """The breach docket `judging_throughput` reads, so the judge's own sizing honours the law."""
    p = path or BREACH_DOCKET
    slim = {k: doc.get(k) for k in
            ("law", "canon", "counts", "breached", "awaiting", "backed", "retired",
             "overdue_beyond_one_judging_cycle", "judging_cycle_s", "queue")}
    slim["at"] = now_utc().isoformat()
    slim["cells"] = sorted({str(r.get("cell")) for r in (doc.get("rows") or [])
                            if r.get("backing") in (BREACHED, AWAITING)})[:2000]
    slim["families"] = sorted({str(r.get("family")) for r in (doc.get("rows") or [])
                               if r.get("backing") in (BREACHED, AWAITING)})
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(slim, indent=1, default=str), encoding="utf-8")
    except OSError:
        pass
    return p


def retire_rejected(rows: Sequence[Mapping[str, Any]], lane_by_name: Mapping[str, Any]) -> int:
    """Take the clock away from a cell the judge REJECTED, with the verdict as its reason.

    EVIDENCE IS NEVER DESTROYED: `n`, `cum_r`, `max_dd_r` and every ledger stay exactly as they
    are. What changes is the row's status, so nothing downstream can read a rejected cell's
    forward series as live evidence again.
    """
    stamp = now_utc().isoformat()
    changed = 0
    by_lane: dict[str, list[Mapping[str, Any]]] = {}
    for r in rows:
        by_lane.setdefault(str(r.get("lane")), []).append(r)
    for lane_name, items in by_lane.items():
        ln = lane_by_name.get(lane_name)
        if ln is None or not ln.path.exists():
            continue
        doc = _read_json(ln.path)
        if not isinstance(doc, dict):
            continue
        target = doc.get(ln.nested) if getattr(ln, "nested", None) else doc
        if not isinstance(target, dict):
            continue
        n = 0
        for r in items:
            row = target.get(str(r.get("key")))
            if not isinstance(row, dict):
                continue
            if str(row.get("status") or "").upper().startswith(("RETIRED", "VOID")):
                continue
            row["status"] = "RETIRED_GATE_FAIL"
            row["status_why"] = str(r.get("why") or "the ten-gate judge rejected this cell")
            row["status_at"] = stamp
            row["retired_by"] = "research/clock_certificate.py (CLOCK IMPLIES CERTIFICATE)"
            n += 1
        if n:
            tmp = ln.path.with_suffix(".clockcert.tmp")
            tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
            os.replace(tmp, ln.path)
            changed += n
    return changed


def ratchet(breached_after: int, path: Path | None = None) -> dict[str, Any]:
    """The breach count may only FALL. A law's violation count is not a dial."""
    p = (path or BREACH_LEDGER).with_name("clock_breach_ratchet.json")
    cur = _read_json(p)
    low = cur.get("lowest_breached") if isinstance(cur, dict) else None
    floor = breached_after if not isinstance(low, int) else min(int(low), breached_after)
    doc = {"lowest_breached": floor, "last_breached": breached_after,
           "at": now_utc().isoformat(),
           "rule": ("the enforced ceiling is the lowest breach count ever measured on this box; "
                    "it may fall and never rise -- and it falls by JUDGING cells, never by "
                    "switching clocks off")}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass
    return doc


def read_ratchet(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json((path or BREACH_LEDGER).with_name("clock_breach_ratchet.json"))
    return doc if isinstance(doc, dict) else {}


def oldest_breach_age_s(doc: Mapping[str, Any]) -> float | None:
    ages = [float(r.get("breach_age_s") or 0.0) for r in (doc.get("rows") or [])
            if r.get("backing") in (BREACHED, AWAITING) and r.get("breach_age_s") is not None]
    return max(ages) if ages else None


def since(stamp: Any) -> timedelta | None:
    try:
        return now_utc() - datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
