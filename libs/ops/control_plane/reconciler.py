"""THE RECONCILER -- the only organ allowed to say a component is HEALTHY.

    DESIRED STATE - OBSERVED STATE = RECONCILIATION WORK

Everything else in this package is a noun. This is the verb. Each pass:

    1. reads DESIRED state from the component registry (`desks/mt5/ops/components.py`),
    2. OBSERVES reality per component -- is it scheduled, is its process/lock there, has its
       watermark moved inside its SLA, are its outputs inside valid leases, did the consumers
       acknowledge them,
    3. assigns a state from the one model
       DECLARED -> STARTING -> HEALTHY -> DEGRADED -> STALE -> STALLED -> BROKEN -> REPAIRING
       -> HEALTHY, or -> QUARANTINED -> RETIRED,
    4. PLANS the repair work, and under --apply runs each actuator and proves its postcondition,
    5. publishes the twelve invariants and the one bit: DESK_CLOSED_AND_HEALTHY.

A COMPONENT CANNOT CERTIFY ITSELF. HEALTHY is assigned here, from observation, and nowhere else.
That is the whole reason this file exists rather than a `self_check()` on each organ: every
self-check this desk ever wrote reported the thing its author was thinking about, and the outages
came from the thing they were not.

FAIL-CLOSED. A required repair that times out makes the pass red and the process exit non-zero. A
parent never returns success while a required child failed. `complete: true` is impossible with
any required observation missing -- UNMEASURED is a verdict, never a pass (L1.28a).

THE OBJECTIVES, published per component rather than asserted:
    P(failure exists and the desk does not know) -> 0
    detection time + repair time <= the component's own SLA (spec.detection_sla_s + repair_sla_s)
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.control_plane import actuators as act
from libs.ops.control_plane import edges as edg
from libs.ops.control_plane import fingerprints as fp
from libs.ops.control_plane import lease
from libs.ops.control_plane import watermarks as wm
from libs.ops.control_plane.specs import UNMEASURED, ComponentSpec, Registry

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
REPORT = DESK / "reports" / "CONTROL_PLANE.json"
QUARANTINE = DESK / "data" / "control_plane_quarantine.json"

#: The twelve invariants, in the order the report prints them. The first one that is not True is
#: the desk's first broken invariant, and it is named under the top-level bit.
INVARIANTS: tuple[str, ...] = (
    "component_coverage", "schedule_coverage", "runtime_coverage", "progress_coverage",
    "freshness", "wiring", "candidate_conservation", "forward", "release", "controller",
    "resource_loop", "closed_loop_proof",
)


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def epoch_id(at: datetime | str | None = None, salt: str = "") -> str:
    """The immutable id of one controller cycle.

    IMMUTABLE MEANS DERIVED FROM THE CYCLE, NOT FROM THE CLOCK AT READ TIME. Two organs certifying
    the same cycle must compute the same id from the same `at`, and a later pass must compute a
    different one -- which is what makes "a stale WIRING_CEO.json can never make a later pass
    green" enforceable instead of aspirational.
    """
    stamp = at.astimezone(UTC).isoformat(timespec="seconds") if isinstance(at, datetime) \
        else str(at or now_utc().isoformat(timespec="seconds"))
    digest = hashlib.sha256(f"{stamp}|{salt}".encode()).hexdigest()[:10]
    return f"E{stamp.replace('-', '').replace(':', '').replace('+0000', 'Z')[:15]}-{digest}"


def epoch_compatible(envelope: Mapping[str, Any] | None, epoch: str | None,
                     epoch_started_at: str | None = None) -> tuple[bool | None, str]:
    """May this artifact certify THIS epoch?

    Two ways to qualify, and only two: the envelope names the epoch, or it was created after the
    epoch began (an explicitly compatible watermark). Anything else is an older pass's report,
    and an older pass's report cannot make a later one green -- which is exactly how a green
    WIRING_CEO.json from the top of the hour certified a pass that had failed at :45.
    """
    if not envelope:
        return None, "no envelope: the artifact claims no epoch and no producer run"
    if not epoch:
        return None, "no epoch declared for this pass"
    if str(envelope.get("epoch_id")) == str(epoch):
        return True, f"stamped with epoch {epoch}"
    created = str(envelope.get("created_at") or "")
    if epoch_started_at and created:
        try:
            c = datetime.fromisoformat(created)
            s = datetime.fromisoformat(epoch_started_at)
        except ValueError:
            return False, f"unparseable timestamps ({created!r} vs {epoch_started_at!r})"
        if c.tzinfo is None:
            c = c.replace(tzinfo=UTC)
        if s.tzinfo is None:
            s = s.replace(tzinfo=UTC)
        if c >= s:
            return True, f"created {created} inside the epoch that began {epoch_started_at}"
        return False, (f"created {created}, BEFORE this epoch began at {epoch_started_at}: an "
                       f"earlier pass's report cannot certify a later one")
    return False, f"stamped with epoch {envelope.get('epoch_id')!r}, not {epoch}"


# ------------------------------------------------------------------------------- observation
@dataclass
class Observation:
    component_id: str
    state: str
    why: str
    details: dict[str, Any]
    criticality: str = "optional"

    def to_dict(self) -> dict[str, Any]:
        return {"component_id": self.component_id, "state": self.state,
                "criticality": self.criticality, "why": self.why, **self.details}


def _quarantined(root: Path | None = None) -> dict[str, str]:
    p = (root or ROOT) / "desks" / "mt5" / "data" / "control_plane_quarantine.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    rows = doc.get("quarantined") if isinstance(doc, dict) else None
    if isinstance(rows, dict):
        return {str(k): str(v) for k, v in rows.items()}
    return {}


def _lock_state(spec: ComponentSpec, locks: Path | None = None) -> dict[str, Any]:
    """Resident liveness, with the desk's own lock semantics.

    AN UNREADABLE LOCK IS A HELD LOCK. The residents hold a Windows byte-range lock on byte 0 of
    their own lock file, so reading it raises PermissionError WHILE THE PROCESS IS ALIVE. Reading
    that as death reported twenty-two healthy residents DEAD and "restarted" every fifteen
    minutes (measured 2026-09-17) -- the strongest evidence of life this desk has, read as the
    opposite.
    """
    stem = spec.component_id.split(":", 1)[1] if ":" in spec.component_id else spec.component_id
    base = locks or (DESK / "data" / "locks")
    p = base / f"{stem}.lock"
    if not p.exists():
        return {"lock": "FREE", "pid": None, "alive": False}
    try:
        first = p.read_text(encoding="utf-8", errors="replace").split()
    except OSError:
        return {"lock": "HELD", "pid": None, "alive": True}
    if first and first[0].isdigit():
        pid = int(first[0])
        return {"lock": "PID", "pid": pid, "alive": act.pid_alive(pid)}
    return {"lock": "STALE", "pid": None, "alive": False}


def observe(spec: ComponentSpec, *, now: datetime | None = None, root: Path | None = None,
            locks: Path | None = None, watermark_root: Path | None = None,
            quarantine: Mapping[str, str] | None = None,
            lineage: Path | None = None) -> Observation:
    """One component's state, from observation only. The ONLY place HEALTHY is assigned."""
    t = now or now_utc()
    base = root or ROOT
    q = dict(quarantine or {})
    details: dict[str, Any] = {"schedule": spec.schedule, "cadence_s": spec.cadence_s,
                               "max_silence_s": spec.max_silence_s,
                               "detection_sla_s": spec.detection_sla_s,
                               "repair_sla_s": spec.repair_sla_s, "sla_s": spec.sla_s}

    if spec.component_id in q:
        return Observation(spec.component_id, "QUARANTINED", q[spec.component_id], details,
                           spec.criticality)
    if not spec.scheduled:
        return Observation(
            spec.component_id, "DECLARED",
            f"{spec.component_id} exists and nothing in this repository schedules it",
            details, spec.criticality)

    if spec.kind == "resident":
        lk = _lock_state(spec, locks)
        details.update(lk)
        if not lk["alive"]:
            return Observation(spec.component_id, "BROKEN",
                               f"{spec.component_id} holds no live singleton lock "
                               f"({lk['lock']})", details, spec.criticality)

    prog = wm.advancing(spec.component_id, spec.max_silence_s, t, watermark_root)
    details["progress"] = prog
    if prog["state"] == "STALLED":
        return Observation(spec.component_id, "STALLED", prog["why"], details, spec.criticality)

    outs = [base / o for o in spec.outputs if o and not str(o).endswith("/")]
    fresh = lease.staleness(outs, t, base) if outs else {}
    details["outputs"] = fresh
    stale = [k for k, v in fresh.items() if v["verdict"] == "STALE"]
    if stale:
        return Observation(spec.component_id, "STALE",
                           f"{spec.component_id} owns {len(stale)} expired artifact(s): "
                           f"{stale[:3]}", details, spec.criticality)

    my_edges = edg.edges_for(producer=spec.component_id)
    if my_edges:
        rows = [edg.observe(e, t, lineage) for e in my_edges]
        details["edges"] = rows
        unobserved = [r for r in rows if not r["observed"]]
        if unobserved:
            return Observation(spec.component_id, "DEGRADED", unobserved[0]["why"], details,
                               spec.criticality)

    if prog["state"] == "UNMEASURED":
        return Observation(spec.component_id, "DEGRADED", prog["why"], details, spec.criticality)
    return Observation(spec.component_id, "HEALTHY", "", details, spec.criticality)


#: Which states are a defect the reconciler must plan work for.
BROKEN_STATES: frozenset[str] = frozenset({"BROKEN", "STALLED", "STALE"})


# ------------------------------------------------------------------------------------ plan
def plan(observations: Sequence[Observation],
         registry: Registry) -> list[dict[str, Any]]:
    """The reconciliation work: one row per component that is not where desired state says.

    DEGRADED IS NOT REPAIRED BY RESTARTING. A component whose watermark is UNMEASURED or whose
    consumer never acked is not sick -- it is UNWIRED, and the repair is a code or registry
    change, not a process kick. Planning a restart for it would be the old behaviour: a fixer
    firing forever at something a restart cannot fix.
    """
    rows: list[dict[str, Any]] = []
    for o in observations:
        if o.state not in BROKEN_STATES:
            continue
        spec = registry.get(o.component_id)
        if spec is None:
            continue
        rows.append({
            "component_id": o.component_id, "state": o.state, "why": o.why,
            "actuator": spec.restart_action,
            "criticality": o.criticality,
            "detection_sla_s": spec.detection_sla_s, "repair_sla_s": spec.repair_sla_s,
        })
    rows.sort(key=lambda r: (r["criticality"] != "required", r["component_id"]))
    return rows


def _actuator_for(spec: ComponentSpec) -> act.Actuator | None:
    """Turn a spec's declared `restart_action` into a real actuator. None when the action is not
    one this plane knows how to perform -- named in the record rather than silently skipped."""
    action = str(spec.restart_action or "")
    if action.startswith("restart:task:"):
        task = action.split("restart:task:", 1)[1]
        stem = (spec.component_id.split(":", 1)[1] if spec.kind == "resident"
                else spec.component_id)
        return act.restart_resident(spec.component_id, task, stem)
    if action.startswith("restart:resident:"):
        stem = action.split("restart:resident:", 1)[1]
        from desks.mt5.ops import components as comp  # pragma: no cover - box-side only
        task = comp.residents().get(stem, (UNMEASURED,))[0]
        return act.restart_resident(spec.component_id, task, stem)
    return None


def apply_plan(rows: Sequence[Mapping[str, Any]], registry: Registry, *, budget_s: float,
               runner: Any = None, sleeper: Any = None, clock: Any = None,
               locks: Path | None = None,
               watermark_root: Path | None = None) -> list[dict[str, Any]]:
    """Run each planned repair and PROVE it. Returns one record per attempt.

    A repair whose postcondition does not hold is recorded FAILED or UNPROVEN whatever the return
    code said -- the whole point of `actuators.run_actuator`.
    """
    tick = clock or time.monotonic
    t0 = tick()
    out: list[dict[str, Any]] = []
    for row in rows:
        spec = registry.get(str(row.get("component_id")))
        if spec is None:
            continue
        if tick() - t0 >= budget_s:
            out.append({"component_id": spec.component_id, "result": "SKIPPED",
                        "repaired": False, "why": "reconciliation budget exhausted"})
            continue
        a = _actuator_for(spec)
        if a is None:
            out.append({"component_id": spec.component_id, "result": "SKIPPED",
                        "repaired": False,
                        "why": (f"{spec.component_id} declares restart_action "
                                f"{spec.restart_action!r}, which this plane cannot perform")})
            continue
        ctx: dict[str, Any] = {"component_id": spec.component_id}
        if locks is not None:
            ctx["locks"] = locks
        if watermark_root is not None:
            ctx["watermark_root"] = watermark_root
        rec = act.run_actuator(a, ctx, apply=True, runner=runner, sleeper=sleeper, clock=clock)
        rec["component_id"] = spec.component_id
        rec["criticality"] = spec.criticality
        if not rec.get("repaired"):
            fp.record(f"{spec.component_id} repair {rec.get('result')}: {rec.get('why')}",
                      spec.component_id)
        out.append(rec)
    return out


# ------------------------------------------------------------------------------ invariants
def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _inv(ok: bool | None, measured: Any, why: str) -> dict[str, Any]:
    return {"ok": ok, "measured": measured, "why": why}


def invariants(observations: Sequence[Observation], registry: Registry, *,
               root: Path | None = None, census: Mapping[str, Any] | None = None,
               epoch: str | None = None, lineage: Path | None = None,
               now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """The twelve, measured. `None` is UNMEASURED and never a pass."""
    base = root or ROOT
    desk = base / "desks" / "mt5"
    t = now or now_utc()
    by_id = {o.component_id: o for o in observations}
    required = list(registry.required())

    cov = dict(census or {})
    unclaimed = cov.get("executables_unclaimed")
    coverage = cov.get("coverage")
    inv_component = _inv(
        None if coverage is None else bool(coverage >= 1.0),
        {"executables": cov.get("executables"), "unregistered": len(unclaimed or []),
         "components": len(registry)},
        "" if coverage == 1.0 else
        f"{len(unclaimed or [])} executable(s) carry no ComponentSpec: {list(unclaimed or [])[:5]}"
        if unclaimed else "component census UNMEASURED")

    desired = [s for s in registry.all() if s.cadence_s is not None]
    unsched = [s.component_id for s in desired if not s.scheduled]
    inv_schedule = _inv(not unsched if desired else None,
                        {"desired": len(desired), "scheduled": len(desired) - len(unsched)},
                        "" if not unsched else
                        f"{len(unsched)} component(s) declare a cadence and no schedule: "
                        f"{unsched[:5]}")

    res = [s for s in registry.by_kind("resident") if s.criticality == "required"]
    dead = [s.component_id for s in res
            if by_id.get(s.component_id) and by_id[s.component_id].state == "BROKEN"]
    inv_runtime = _inv(not dead if res else None,
                       {"required_residents": len(res), "alive": len(res) - len(dead)},
                       "" if not dead else f"{len(dead)} required resident(s) hold no live lock: "
                                           f"{dead[:5]}")

    prog_rows = [(s, by_id.get(s.component_id)) for s in required]
    not_advancing = [s.component_id for s, o in prog_rows
                     if o is None or (o.details.get("progress") or {}).get("state")
                     != "ADVANCING"]
    inv_progress = _inv(not not_advancing if required else None,
                        {"required": len(required),
                         "advancing": len(required) - len(not_advancing)},
                        "" if not not_advancing else
                        f"{len(not_advancing)} required component(s) have no advancing watermark: "
                        f"{not_advancing[:5]}")

    stale_arts: list[str] = []
    unleased: list[str] = []
    missing_arts: list[str] = []
    for s in required:
        o = by_id.get(s.component_id)
        if o is None:
            continue
        for k, v in (o.details.get("outputs") or {}).items():
            if v.get("verdict") == "STALE":
                stale_arts.append(k)
            elif v.get("verdict") == "UNLEASED":
                unleased.append(k)
            elif v.get("verdict") == "MISSING":
                missing_arts.append(k)
    inv_fresh = _inv(not stale_arts if required else None,
                     {"expired_required_artifacts": len(stale_arts),
                      "unleased": len(unleased), "missing": len(missing_arts)},
                     "" if not stale_arts else
                     f"{len(stale_arts)} required artifact(s) outside their lease: "
                     f"{stale_arts[:5]}")

    loop = edg.closed_loop(edg.REQUIRED_EDGES, t, lineage)
    unconsumed = [r["edge"] for r in loop["edges"]
                  if r["state"] in ("UNACKED", "ACK_WEAK")]
    unproduced = [r["edge"] for r in loop["edges"] if r["state"] == "UNPRODUCED"]
    #: AN OUTPUT NOBODY PRODUCED IS NOT A CONSUMED OUTPUT, and it is not a clean one either. When
    #: every required edge is UNPRODUCED the consumption question has no subject, so the verdict
    #: is UNMEASURED -- reporting `0 unconsumed` there would be the denominator trick the laws
    #: forbid: perfect wiring because nothing was ever wired.
    inv_wiring = _inv(None if len(unproduced) == len(loop["edges"]) else not unconsumed,
                      {"unconsumed_required_outputs": len(unconsumed),
                       "unproduced_required_outputs": len(unproduced)},
                      (f"no required edge has a produced artifact yet: {len(unproduced)} "
                       f"producer(s) stamp no envelope, so consumption is UNMEASURED"
                       if len(unproduced) == len(loop["edges"]) else
                       "" if not unconsumed else
                       f"{len(unconsumed)} required output(s) nothing acknowledges: "
                       f"{unconsumed[:5]}"))

    cc = _read_json(desk / "reports" / "CANDIDATE_CONSERVATION.json")
    n_lost = (cc or {}).get("n_lost") if isinstance(cc, dict) else None
    inv_cand = _inv(None if n_lost is None else bool(int(n_lost) == 0),
                    {"n_lost": n_lost, "n_verdicts": (cc or {}).get("n_verdicts")
                     if isinstance(cc, dict) else None},
                    "CANDIDATE_CONSERVATION.json absent or unreadable: discovered vs accounted is "
                    "UNMEASURED" if n_lost is None else
                    ("" if int(n_lost) == 0 else f"{n_lost} discovered candidate(s) unaccounted"))

    wc = _read_json(desk / "reports" / "WIRING_CEO.json")
    cert = (wc or {}).get("certificates_without_clocks") if isinstance(wc, dict) else None
    n_cert = cert.get("n") if isinstance(cert, dict) else cert
    cert_env = lease.read_envelope(desk / "reports" / "WIRING_CEO.json")
    compat, compat_why = epoch_compatible(cert_env, epoch,
                                          None if epoch is None else cov.get("epoch_started_at"))
    inv_forward = _inv(
        None if n_cert is None or compat is False else bool(int(n_cert) == 0),
        {"certificates_without_clocks": n_cert, "epoch_compatible": compat},
        (f"the certificate census cannot certify this pass: {compat_why}" if compat is False else
         "WIRING_CEO.json absent or unreadable: certified-but-unclocked is UNMEASURED"
         if n_cert is None else
         ("" if int(n_cert) == 0 else f"{n_cert} certificate(s) hold no forward clock")))

    rel = _read_json(desk / "data" / "release_identity.json")
    rel_ok = rel.get("ok") if isinstance(rel, dict) else None
    inv_release = _inv(None if rel_ok is None else bool(rel_ok),
                       {"running_sha": (rel or {}).get("running_sha") if rel else None,
                        "release_sha": (rel or {}).get("release_sha") if rel else None,
                        "tested_sha": (rel or {}).get("tested_sha") if rel else None},
                       "release_identity.json absent: running = sealed = tested is UNMEASURED"
                       if rel_ok is None else
                       ("" if rel_ok else str((rel or {}).get("reason") or "")[:300]))

    mc = _read_json(desk / "reports" / "META_CONTROLLER.json")
    ep = (mc or {}).get("epoch") if isinstance(mc, dict) else None
    complete = ep.get("complete") if isinstance(ep, dict) else (mc or {}).get("epoch_complete") \
        if isinstance(mc, dict) else None
    inv_controller = _inv(None if complete is None else bool(complete),
                          {"epoch_id": (mc or {}).get("epoch_id") if isinstance(mc, dict)
                           else None,
                           "missing_kinds": ep.get("missing") if isinstance(ep, dict) else None},
                          "META_CONTROLLER.json absent or its epoch UNMEASURED"
                          if complete is None else
                          ("" if complete else
                           f"epoch incomplete: {ep.get('why') if isinstance(ep, dict) else ''}"))

    alloc_paths = ("desks/mt5/data/research_allocation.json",
                   "desks/mt5/data/forest_allocation.json")
    written = {p: (base / p).exists() for p in alloc_paths}
    acked = {p: len(lease.acks_for(p)) for p in alloc_paths}
    unobserved = [p for p in alloc_paths if not written[p] or acked[p] == 0]
    inv_resource = _inv(not unobserved,
                        {"written": written, "acknowledgements": acked},
                        "" if not unobserved else
                        f"{len(unobserved)} resource decision(s) written but unobserved "
                        f"downstream: {unobserved}")

    inv_closed = _inv(loop["closed"],
                      {"required_edges": loop["required"], "observed": loop["observed"],
                       "open": loop["open"][:6]},
                      "" if loop["closed"] else
                      f"{len(loop['open'])} mandatory edge(s) not observed inside valid leases")

    return {
        "component_coverage": inv_component,
        "schedule_coverage": inv_schedule,
        "runtime_coverage": inv_runtime,
        "progress_coverage": inv_progress,
        "freshness": inv_fresh,
        "wiring": inv_wiring,
        "candidate_conservation": inv_cand,
        "forward": inv_forward,
        "release": inv_release,
        "controller": inv_controller,
        "resource_loop": inv_resource,
        "closed_loop_proof": inv_closed,
    }


def first_broken(inv: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    for name in INVARIANTS:
        row = inv.get(name)
        if row is None:
            return {"invariant": name, "ok": None, "why": "not measured by this pass"}
        if row.get("ok") is not True:
            return {"invariant": name, "ok": row.get("ok"), "why": row.get("why"),
                    "measured": row.get("measured")}
    return None


# ----------------------------------------------------------------------------- the pass
def reconcile(*, registry: Registry | None = None, root: Path | None = None,
              apply: bool = False, budget_s: float = 600.0, epoch: str | None = None,
              now: datetime | None = None, locks: Path | None = None,
              watermark_root: Path | None = None, lineage: Path | None = None,
              runner: Any = None, sleeper: Any = None, clock: Any = None,
              census: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """One full reconciliation pass. Returns the document written to CONTROL_PLANE.json."""
    t = now or now_utc()
    base = root or ROOT
    reg = registry
    cen = dict(census or {})
    if reg is None:
        reg, cen = _desk_registry(base)
    ep = epoch or epoch_id(t)
    q = _quarantined(base)
    # THE REAPER RUNS FIRST, BEFORE ANY OTHER REPAIR (2026-09-22, measured). 72 orphaned pool
    # workers held 147 GB of a 251 GB commit limit while 67 GB of physical memory was free; every
    # process started after that died with STATUS_COMMITMENT_LIMIT and left no artifact. So an
    # apply pass that reaped LAST, or reaped somewhere in the middle of the plan, would spend its
    # budget watching every other actuator fail for a reason none of them could name. Freeing the
    # commit limit is the precondition of every repair, which is why it is not one of them.
    pre_pass: list[dict[str, Any]] = []
    if apply:
        reaper = act.desk_actuators().get("reap_orphans")
        if reaper is not None:
            rec = act.run_actuator(reaper, {"component_id": "component:control_plane"},
                                   apply=True, runner=runner, sleeper=sleeper, clock=clock)
            pre_pass.append({"actuator": "reap_orphans", "result": rec.get("result"),
                             "repaired": rec.get("repaired"), "why": rec.get("why")})
    obs = [observe(s, now=t, root=base, locks=locks, watermark_root=watermark_root,
                   quarantine=q, lineage=lineage) for s in reg.all()]
    work = plan(obs, reg)
    repairs: list[dict[str, Any]] = []
    if apply and work:
        repairs = apply_plan(work, reg, budget_s=budget_s, runner=runner, sleeper=sleeper,
                             clock=clock, locks=locks, watermark_root=watermark_root)
    inv = invariants(obs, reg, root=base, census=cen, epoch=ep, lineage=lineage, now=t)
    broken = first_broken(inv)
    failed_required = [r for r in repairs
                       if r.get("criticality") == "required" and not r.get("repaired")]
    by_state: dict[str, int] = {}
    for o in obs:
        by_state[o.state] = by_state.get(o.state, 0) + 1
    doc: dict[str, Any] = {
        "at": t.isoformat(timespec="seconds"),
        "epoch_id": ep,
        "mode": "apply" if apply else "observe",
        "DESK_CLOSED_AND_HEALTHY": broken is None and not failed_required,
        "first_broken_invariant": broken,
        "invariants": inv,
        "components": len(reg),
        "states": by_state,
        "unhealthy": [o.to_dict() for o in obs if o.state not in ("HEALTHY", "DECLARED")][:200],
        "plan": work[:200],
        "pre_pass": pre_pass,
        "repairs": repairs,
        "failed_required_repairs": [r.get("component_id") for r in failed_required],
        "registry_census": cen,
        "fingerprints": fp.summary(),
        "slas": _sla_table(reg),
        "state_model": ("DECLARED -> STARTING -> HEALTHY -> DEGRADED -> STALE -> STALLED -> "
                        "BROKEN -> REPAIRING -> HEALTHY, or -> QUARANTINED -> RETIRED; only the "
                        "reconciler assigns HEALTHY"),
        "rule": ("WIRED = scheduled AND executed AND progressed AND produced owned output AND "
                 "consumer acknowledged it; CLOSED LOOP = every required edge observed inside "
                 "valid freshness leases"),
    }
    return doc


def _sla_table(reg: Registry) -> dict[str, Any]:
    """detection + repair, published per component -- the objective, not an assertion."""
    rows = [{"component_id": s.component_id, "criticality": s.criticality,
             "detection_sla_s": s.detection_sla_s, "repair_sla_s": s.repair_sla_s,
             "sla_s": s.sla_s}
            for s in reg.required()]
    known = [r["sla_s"] for r in rows if r["sla_s"] is not None]
    return {"required": len(rows), "with_sla": len(known),
            "max_sla_s": max(known) if known else None,
            "unmeasured": [r["component_id"] for r in rows if r["sla_s"] is None][:20],
            "rows": rows[:200]}


def _desk_registry(root: Path) -> tuple[Registry, dict[str, Any]]:
    """The desk's registry, imported by path so this module works from the repo root and the box.

    A failure here is FATAL to the pass and says so: a reconciler that cannot read desired state
    has nothing to reconcile against, and returning an empty registry would publish a green
    report about a desk it never looked at.
    """
    import importlib.util
    path = root / "desks" / "mt5" / "ops" / "components.py"
    spec_ = importlib.util.spec_from_file_location("_cp_components", path)
    if spec_ is None or spec_.loader is None:
        raise RuntimeError(f"cannot load the component registry from {path}")
    mod = importlib.util.module_from_spec(spec_)
    sys.modules.setdefault("_cp_components", mod)
    spec_.loader.exec_module(mod)
    return mod.registry(root), mod.census(root)


def write(doc: Mapping[str, Any], path: Path | None = None,
          root: Path | None = None) -> dict[str, Any]:
    """Publish the report WITH its own lease, so the control plane is held to its own law."""
    target = path or REPORT
    reg, _ = _desk_registry(root or ROOT)
    spec_ = reg.get("component:control_plane")
    return lease.write_report(target, dict(doc), spec_ or "component:control_plane",
                              inputs=(), ttl="fifteen_minute",
                              epoch_id=str(doc.get("epoch_id") or UNMEASURED), root=root or ROOT)
