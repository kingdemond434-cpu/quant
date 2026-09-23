"""THE 24/7 MAXIMISER -- name the one binding constraint this hour, and move compute at it.

    python desks/mt5/research/bottleneck_attack.py --once --budget-s 300

THE PRINCIPAL'S ORDER (2026-09-23): "do something which 24/7 makes these happen permanently and
always maximised." A desk that improves everything improves nothing at a rate anyone can see. The
throughput of a pipeline is the throughput of its narrowest stage, so the only compute that buys
anything is compute spent on the stage that is actually binding -- and the desk has never NAMED
that stage hourly from measurement. It has four standing bottlenecks and it has been paying all
four the same attention:

    CONVERSION DEBT      discoveries the registry holds that no cell has ever been cut from.
                         Owner department: discovery.
    JUDGING THROUGHPUT   cells born per hour against cells judged per hour, and the queue that
                         difference builds. Owner: validate.
    ENROLMENT LATENCY    hours from a certificate minting to a forward clock accruing on it.
                         Evidence that never starts is evidence that never arrives. Owner: forward.
    PLUMBING DEFECTS     the pipes themselves (`plumbing_watchdog`). Owner: meta.

PLUMBING DOMINATES BY CONSTRUCTION, and that is not a preference. While an adoption clock is dead
or the commit limit is exhausted, every other stage's measurement is of a machine that is not
running -- improving conversion on a box that adopts no code buys nothing at all. So a plumbing
defect past its escalation window scores 1.0 and takes the binding slot outright.

HOW IT MOVES COMPUTE: through machinery that already exists, never a new allocator.

    research_auction    `build(bottleneck=...)` blends this organ's `compute_shift` with
                        `bottleneck_law`'s (the MAXIMUM per department, never the minimum), and
                        the auction's factors reach `research_budget.budget_s`, which is what
                        actually sets a leg's seconds next cycle.
    the registry        one upsert row per pass under `kind="proposal"`, so the proposal is in the
                        canonical store the controller and the auction already read.
    compute_policy      READ, never written. `compute_economics` is its only writer, and a second
                        writer to one file is the exact defect the plumbing watchdog hunts.

NEVER A CUT (growth governance, Rule 2 and the standing "never reduce aggressiveness"). Every
shift this organ emits is >= 1.0: it can fund the binding stage harder, and it has no instrument
for starving anything. A bottleneck attacker that took compute away from a department would be a
veto wearing a throughput costume.

PEER ARTIFACTS ARE CONSUMED, NEVER WRITTEN. `conversion_maximiser.py`, `judging_throughput.py`
and the forward enrolment organ belong to other builders; this reads their reports and falls back
to the primitives underneath them (`GAUNTLET_BACKPRESSURE.json`, `RESEARCH_LATENCY.json`,
`registry.conversion_debt`) when a report has not landed. An absent peer is UNMEASURED with its
reason named, never a zero -- a bottleneck nobody measured cannot be declared absent, and
measuring it is itself a move (L1.28a).

    desks/mt5/reports/BOTTLENECK_ATTACK.json   the binding constraint, what it moved, and the
                                               trend of all four over the last day, so "is it
                                               getting better" is answerable every morning.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.ops import events  # noqa: E402
from libs.ops.control_plane import lease  # noqa: E402
from libs.ops.control_plane import watermarks as wm  # noqa: E402

REPORTS = DESK / "reports"
OUT = REPORTS / "BOTTLENECK_ATTACK.json"
HISTORY = DESK / "data" / "bottleneck_attack_history.jsonl"
COMPONENT = "leg:bottleneck_attack"

UNMEASURED = "UNMEASURED"

#: The four standing bottlenecks and the department that owns each. The owner is where compute
#: goes when that bottleneck binds, and it is a DEPARTMENT because that is the unit the auction
#: and `research_budget` already price -- inventing a new unit here would mean inventing a new
#: allocator to spend it, which is the thing this organ exists not to do.
OWNER: dict[str, str] = {
    "conversion_debt": "discovery",
    "judging_throughput": "validate",
    "enrolment_latency": "forward",
    "plumbing_defects": "meta",
}

#: The most a single pass may raise one department's factor. It matches `research_auction`'s own
#: CEIL (= `research_budget.CEIL`), so the shift this organ proposes is expressible in the
#: machinery that consumes it rather than being clipped somewhere downstream without a record.
MAX_SHIFT = 2.0

#: Saturating references, in the unit each bottleneck is measured in. They set the SCALE at which
#: a bottleneck is "half as bad as it can get", not a threshold: severity is x/(x+ref), which is
#: monotone, bounded, and has no cliff for a value to sit just under.
REF_ENROLMENT_H = 24.0          # a day from certificate to accruing clock
REF_DEFECTS = 10.0              # ten open plumbing defects


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v))
    except (TypeError, ValueError):
        return None


def _saturate(x: float, ref: float) -> float:
    """x/(x+ref) in [0,1): monotone, bounded, no cliff. A severity with a hard cap invites every
    value to pile up at the cap, and then the binding constraint is decided by a tie-break."""
    x = max(0.0, float(x))
    return x / (x + max(1e-9, float(ref)))


def _row(name: str, *, severity: float | None, value: Any, unit: str, basis: str,
         source: str, detail: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"bottleneck": name, "owner": OWNER[name],
            "severity": None if severity is None else round(float(severity), 4),
            "status": UNMEASURED if severity is None else "MEASURED",
            "value": value, "unit": unit, "basis": basis, "source": source,
            **(dict(detail) if detail else {})}


# ------------------------------------------------------------------------ 1. conversion debt
def measure_conversion_debt(root: Path | None = None,
                            conn: Any = None) -> dict[str, Any]:
    """Discoveries the registry holds that no cell has ever been cut from.

    `conversion_maximiser.py` owns the rich per-class version and is another builder's file; its
    report is read first and the registry primitive underneath it is the fallback, so this organ
    measures something real on the pass before that organ's first artifact lands.
    """
    base = root or ROOT
    doc = _read(base / "desks" / "mt5" / "reports" / "CONVERSION_MAXIMISER.json")
    after = doc.get("debt_after") or doc.get("debt_before") or {}
    total = _num((after or {}).get("total_debt"))
    if total is not None:
        comps = (after or {}).get("components") or {}
        done = _num(doc.get("new_cells")) or 0.0
        return _row("conversion_debt", severity=_saturate(total, max(1.0, total + done + 50.0)),
                    value=int(total), unit="rows owed",
                    basis=("debt rows over debt plus the cells this hour actually cut, floored "
                           "so an idle hour with no debt is not severity 1.0"),
                    source="reports/CONVERSION_MAXIMISER.json",
                    detail={"components": comps,
                            "largest_blocker": doc.get("blocker_owner")
                            or (doc.get("largest_blocker") or {}),
                            "new_cells_last_pass": int(done)})
    try:
        from libs.moat import registry as reg
        debt = reg.conversion_debt(conn)
    except Exception as exc:  # the registry may be locked, absent or mid-migration
        return _row("conversion_debt", severity=None, value=UNMEASURED, unit="rows owed",
                    basis=f"registry unreadable: {type(exc).__name__}: {exc}",
                    source="libs/moat/registry.conversion_debt")
    missing = _num(debt.get("unexplained_missing"))
    possible = _num(debt.get("possible")) or 0.0
    if missing is None:
        return _row("conversion_debt", severity=None, value=UNMEASURED, unit="rows owed",
                    basis="the registry's conversion_debt names no unexplained_missing",
                    source="libs/moat/registry.conversion_debt", detail={"registry": debt})
    return _row("conversion_debt", severity=_saturate(missing, max(1.0, possible * 0.05)),
                value=int(missing), unit="cells owed and unexplained",
                basis=("cells possible minus generated minus blocked-with-a-reason, against 5% "
                       "of the possible grid as the scale"),
                source="libs/moat/registry.conversion_debt",
                detail={"possible": int(possible), "registry": debt})


# --------------------------------------------------------------- 2. judging queue and throughput
def measure_judging(root: Path | None = None) -> dict[str, Any]:
    """Cells born against cells judged, and the queue the difference builds.

    `judging_throughput.py` is another builder's organ; `GAUNTLET_BACKPRESSURE.json` is the
    primitive it is built over and already on disk, so the fallback measures the same quantity
    from the same place rather than inventing a second count of the same thing.
    """
    base = root or ROOT
    for rel, key in (("reports/JUDGING_THROUGHPUT.json", "throughput"),
                     ("reports/GAUNTLET_BACKPRESSURE.json", "backpressure")):
        doc = _read(base / "desks" / "mt5" / rel)
        if not doc:
            continue
        win = ((doc.get("windows") or {}).get("24h")) or {}
        testing = win.get("testing") or doc.get("testing") or {}
        backlog = win.get("backlog") or doc.get("backlog") or {}
        per_hour = _num(testing.get("per_hour")) or _num(doc.get("gates_per_hour"))
        depth = (_num(backlog.get("born_minus_judged"))
                 or _num(doc.get("queue_depth"))
                 or _num(backlog.get("registry_grid_cells")))
        if per_hour is None and depth is None:
            continue
        # Hours of queue at the measured rate: the unit a human can act on. A queue of 10,000 at
        # 100/h is 100 hours, and 100 hours of queue is a stage that is binding whatever its
        # absolute numbers look like.
        hours_of_queue = (depth / per_hour) if (depth is not None and per_hour
                                                and per_hour > 0) else None
        sev = (_saturate(hours_of_queue, REF_ENROLMENT_H) if hours_of_queue is not None
               else (None if depth is None else _saturate(depth, 5000.0)))
        return _row("judging_throughput", severity=sev,
                    value=None if hours_of_queue is None else round(hours_of_queue, 2),
                    unit="hours of queue at the measured judging rate",
                    basis=("the judge is AHEAD of the births by "
                           f"{abs(hours_of_queue):.1f}h of its own capacity, so this stage is "
                           "not binding and its severity is 0"
                           if (hours_of_queue is not None and hours_of_queue < 0)
                           else "queue depth over judged-cells-per-hour, saturated against a "
                                "one-day reference" if hours_of_queue is not None
                           else "queue depth alone; the judging rate is UNMEASURED"),
                    source=f"{rel} ({key})",
                    detail={"gates_per_hour": per_hour, "queue_depth": depth,
                            "pass_rate": testing.get("pass_rate")})
    return _row("judging_throughput", severity=None, value=UNMEASURED, unit="hours of queue",
                basis=("neither reports/JUDGING_THROUGHPUT.json nor "
                       "reports/GAUNTLET_BACKPRESSURE.json is readable: the judging stage is "
                       "UNMEASURED, which is a verdict and not a zero"),
                source="absent")


# ------------------------------------------------------------- 3. forward enrolment latency
def measure_enrolment(root: Path | None = None) -> dict[str, Any]:
    """Hours from a certificate minting to a forward clock accruing on it.

    The forward enrolment organ is another builder's; `RESEARCH_LATENCY.json` already publishes
    the same transition as the stage `certified->forward`, and `FORWARD_SLOT_RANKER.json` counts
    what is waiting for a slot. Both are read; the stage's median is the headline.
    """
    base = root or ROOT
    desk = base / "desks" / "mt5"
    ranker = _read(desk / "reports" / "FORWARD_SLOT_RANKER.json")
    waiting = _num(ranker.get("n_waiting"))
    for rel in ("reports/FORWARD_ENROLMENT.json", "reports/RESEARCH_LATENCY.json"):
        doc = _read(desk / rel)
        if not doc:
            continue
        median = _num(doc.get("enrolment_median_h"))
        stage: Mapping[str, Any] = {}
        if median is None:
            for s in doc.get("stages") or []:
                if isinstance(s, Mapping) and str(s.get("stage")) == "certified->forward":
                    stage, median = s, _num(s.get("median_h"))
                    break
        if median is None:
            continue
        return _row("enrolment_latency", severity=_saturate(median, REF_ENROLMENT_H),
                    value=round(median, 2), unit="hours, certificate -> accruing clock",
                    basis="median of the certified->forward transition against a one-day scale",
                    source=rel,
                    detail={"p90_h": stage.get("p90_h"), "n": stage.get("n"),
                            "waiting_for_a_slot": waiting})
    if waiting is not None and waiting > 0:
        # THE STAGE IS UNTIMED AND STILL VISIBLY BACKED UP. A median nobody computed is not the
        # same fact as a queue nobody is draining, and the queue is the one that is measured.
        return _row("enrolment_latency", severity=_saturate(waiting, 20.0),
                    value=int(waiting), unit="certificates waiting for a forward slot",
                    basis=("the certified->forward median is UNMEASURED, but the slot ranker "
                           "counts what is waiting, and a queue is an observation"),
                    source="reports/FORWARD_SLOT_RANKER.json")
    return _row("enrolment_latency", severity=None, value=UNMEASURED,
                unit="hours, certificate -> accruing clock",
                basis=("no enrolment report and no certified->forward stage: the latency of the "
                       "step between evidence and forward evidence is UNMEASURED"),
                source="absent")


# ------------------------------------------------------------------- 4. plumbing defects
def measure_plumbing(root: Path | None = None) -> dict[str, Any]:
    """The pipes. A defect past its escalation window is severity 1.0 and binds outright.

    Not a preference: while the box adopts no code, or the commit limit is exhausted, or the
    gauntlet's clock is gone, the other three measurements describe a machine that is not running.
    Compute spent anywhere else in that state buys nothing, and the desk has the receipts -- four
    days of shipped fixes that never reached the gateway, and a week of departments that left no
    artifact because every process died of STATUS_COMMITMENT_LIMIT.
    """
    base = root or ROOT
    doc = _read(base / "desks" / "mt5" / "reports" / "PLUMBING_WATCHDOG.json")
    if not doc:
        return _row("plumbing_defects", severity=None, value=UNMEASURED, unit="open defects",
                    basis=("reports/PLUMBING_WATCHDOG.json is absent: whether the desk's pipes "
                           "are open is UNMEASURED, and an unread watchdog is the silence it "
                           "exists to end"),
                    source="absent")
    n = int(_num(doc.get("n_defects")) or 0)
    overdue = int(_num(doc.get("n_past_escalation_window")) or 0)
    sev = 1.0 if overdue else _saturate(n, REF_DEFECTS)
    return _row("plumbing_defects", severity=sev, value=n, unit="open defects",
                basis=("1.0 whenever any defect is past its own escalation window -- a stopped "
                       "pipe makes every other measurement a measurement of a stopped machine"
                       if overdue else "open defects against a scale of ten"),
                source="reports/PLUMBING_WATCHDOG.json",
                detail={"past_escalation_window": overdue,
                        "escalated": int(_num(doc.get("n_escalated")) or 0),
                        "watchdog_at": doc.get("at")})


# ------------------------------------------------------------------------- the binding one
def binding(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """THE ONE constraint this hour. Highest severity wins; ties go to the earlier stage in the
    pipeline, because relieving a downstream stage while an upstream one starves it moves
    nothing. An all-UNMEASURED desk has a binding constraint too, and it is the measuring."""
    measured = [r for r in rows if r.get("severity") is not None]
    order = list(OWNER)
    if not measured:
        unmeasured = [str(r.get("bottleneck")) for r in rows]
        return {"bottleneck": UNMEASURED, "owner": "meta", "severity": None,
                "why": ("every bottleneck is UNMEASURED " + f"({', '.join(unmeasured)}): the "
                        "binding constraint is the desk's own measurement, and the move is to "
                        "make these four organs produce")}
    best = max(measured, key=lambda r: (float(r["severity"]), -order.index(str(r["bottleneck"]))))
    return {"bottleneck": str(best["bottleneck"]), "owner": str(best["owner"]),
            "severity": best["severity"], "value": best.get("value"), "unit": best.get("unit"),
            "why": (f"{best['bottleneck']} scores {best['severity']} "
                    f"({best.get('value')} {best.get('unit')}) -- {best.get('basis')}"),
            "unmeasured": [str(r["bottleneck"]) for r in rows if r.get("severity") is None]}


def compute_shift(bind: Mapping[str, Any]) -> dict[str, float]:
    """The department factors this organ proposes. NEVER BELOW 1.0.

    The binding department is funded in proportion to how badly it binds, to the same CEIL the
    auction and `research_budget` already clip at. Everything else is left exactly where it is:
    this organ has no instrument for taking compute away, on purpose (growth governance Rule 2,
    and the standing order that the desk never reduces its aggressiveness).
    """
    out = dict.fromkeys(set(OWNER.values()), 1.0)
    sev = bind.get("severity")
    if sev is None:
        return out
    owner = str(bind.get("owner") or "meta")
    out[owner] = round(min(MAX_SHIFT, 1.0 + float(sev)), 3)
    return out


# --------------------------------------------------------------------------------- the trend
def append_history(rows: Sequence[Mapping[str, Any]], bind: Mapping[str, Any], at: datetime,
                   path: Path | None = None) -> bool:
    p = path or HISTORY
    row = {"at": at.isoformat(timespec="seconds"), "binding": bind.get("bottleneck"),
           "severity": {str(r["bottleneck"]): r.get("severity") for r in rows},
           "value": {str(r["bottleneck"]): r.get("value") for r in rows}}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str, separators=(",", ":")) + "\n")
    except OSError:
        return False
    return True


def trend(rows: Sequence[Mapping[str, Any]], now: datetime,
          path: Path | None = None, hours: float = 24.0) -> dict[str, Any]:
    """Each bottleneck's severity now against its severity a day ago, so "is it getting better"
    is answerable without reading a log. A bottleneck with no history says so; the first pass of
    a new organ has no trend and inventing one would be the only dishonest number here."""
    p = path or HISTORY
    cutoff = now - timedelta(hours=hours)
    past: list[dict[str, Any]] = []
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-2000:]:
            line = line.strip()
            if not line:
                continue
            with contextlib.suppress(ValueError):
                past.append(json.loads(line))
    except OSError:
        past = []
    def _at(r: Mapping[str, Any]) -> datetime | None:
        try:
            t = datetime.fromisoformat(str(r.get("at") or ""))
        except ValueError:
            return None
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    window = [r for r in past if (_at(r) or now) >= cutoff]
    oldest = window[0] if window else None
    out: dict[str, Any] = {"window_h": hours, "samples": len(window)}
    for r in rows:
        name = str(r["bottleneck"])
        then = ((oldest or {}).get("severity") or {}).get(name) if oldest else None
        nowv = r.get("severity")
        if then is None or nowv is None:
            out[name] = {"then": then, "now": nowv, "direction": UNMEASURED,
                         "why": ("no sample inside the window" if oldest is None
                                 else "one of the two readings is UNMEASURED")}
            continue
        delta = round(float(nowv) - float(then), 4)
        out[name] = {"then": then, "now": nowv, "delta": delta,
                     "direction": ("improving" if delta < -0.01 else
                                   "worsening" if delta > 0.01 else "flat")}
    return out


# ------------------------------------------------------------------- moving the compute
def publish_proposal(bind: Mapping[str, Any], shift: Mapping[str, float],
                     epoch: str) -> dict[str, Any]:
    """One upsert into the canonical registry, under the desk's existing proposal vocabulary.

    `memory_key` makes it an UPSERT, so the proposal is refreshed hourly rather than growing a row
    per pass: the desk wants the current binding constraint, not a diary of every hour that ever
    had one.
    """
    try:
        from libs.moat import registry as reg
        rid = reg.remember(
            "bottleneck_attack",
            (f"binding constraint {bind.get('bottleneck')} (severity {bind.get('severity')}): "
             f"{bind.get('why')}"),
            kind="proposal", memory_key="bottleneck_attack:binding",
            metrics={"severity": bind.get("severity"), "owner": bind.get("owner"),
                     "epoch": epoch, **{f"shift.{k}": v for k, v in shift.items()}})
    except Exception as exc:  # a proposal that cannot be stored may never take the organ down
        return {"written": False, "why": f"{type(exc).__name__}: {exc}"}
    return {"written": True, "memory_id": str(rid), "memory_key": "bottleneck_attack:binding"}


def run(*, budget_s: float = 300.0, root: Path | None = None, now: datetime | None = None,
        write: bool = True, history: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    t = now or _now()
    t0 = time.monotonic()
    rows = [measure_conversion_debt(base), measure_judging(base),
            measure_enrolment(base), measure_plumbing(base)]
    bind = binding(rows)
    shift = compute_shift(bind)
    tr = trend(rows, t, history)
    epoch = t.strftime("%Y-%m-%dT%H")
    moved = publish_proposal(bind, shift, epoch) if write else {"written": False,
                                                                "why": "--no-write"}
    doc: dict[str, Any] = {
        "at": t.isoformat(timespec="seconds"),
        "epoch": epoch,
        "binding": bind,
        "bottlenecks": rows,
        "compute_shift": shift,
        "moved": {
            "registry_proposal": moved,
            "consumers": [
                "desks/mt5/research/research_auction.py build() -- blends this compute_shift "
                "with BOTTLENECK_LAW's (the maximum per department, never the minimum)",
                "desks/mt5/research/research_budget.py budget_s() -- the auction's factor is "
                "what actually sets a leg's seconds next cycle",
            ],
            "read_only": ["desks/mt5/data/compute_policy.json (compute_economics is its only "
                          "writer; a second writer to one file is the defect the plumbing "
                          "watchdog hunts)"],
        },
        "trend_24h": tr,
        "n_unmeasured": sum(1 for r in rows if r.get("severity") is None),
        "elapsed_s": round(time.monotonic() - t0, 2),
        "budget_s": budget_s,
        "rule": ("the throughput of a pipeline is the throughput of its narrowest stage; "
                 "plumbing past its escalation window scores 1.0 and binds outright, because "
                 "every other measurement is then a measurement of a stopped machine; every "
                 "shift is >= 1.0 and nothing is ever starved"),
    }
    if write:
        append_history(rows, bind, t, history)
        try:
            env = lease.write_report(OUT, doc, COMPONENT, inputs=(), ttl="hourly", root=base)
            doc = {**doc, "envelope": {"artifact_id": env.get("artifact_id"),
                                       "producer_run_id": env.get("producer_run_id")}}
            wm.progress(COMPONENT, "attack_passes",
                        int((wm.read(COMPONENT) or {}).get("value") or 0) + 1,
                        run_id=str(env.get("producer_run_id")))
        except (OSError, ValueError, RuntimeError):
            OUT.parent.mkdir(parents=True, exist_ok=True)
            tmp = OUT.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
            os.replace(tmp, OUT)
        events.emit("BOTTLENECK_BOUND", bottleneck=str(bind.get("bottleneck")),
                    owner=str(bind.get("owner")), severity=bind.get("severity"),
                    shift=shift.get(str(bind.get("owner") or "meta")))
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode there is)")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, write=not a.no_write)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        b = doc["binding"]
        print(f"bottleneck attack {doc['at']}: BINDING={b.get('bottleneck')} "
              f"(owner {b.get('owner')}, severity {b.get('severity')}) in {doc['elapsed_s']}s")
        print(f"  why: {str(b.get('why'))[:220]}")
        for r in doc["bottlenecks"]:
            tr = doc["trend_24h"].get(str(r["bottleneck"]), {})
            print(f"  {r['bottleneck']!s:<20} sev={r['severity']!s:<8} "
                  f"{r['value']!s:<12} {r['unit'][:36]:<36} {tr.get('direction', '')}")
            print(f"      {str(r['basis'])[:150]}")
        print(f"  compute_shift: {doc['compute_shift']}")
        print(f"  proposal: {doc['moved']['registry_proposal']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
