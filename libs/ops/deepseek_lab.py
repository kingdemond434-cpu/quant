"""DEEPSEEK THIRD-BRAIN LABORATORY -- the queue-driven 24/7 layer over `deepseek_cycle`.

WHAT THE HOURLY CYCLE WAS. One role per hour, one call, round-robin over 35 seed roles: a role came
round every day and a half whether or not it had ever produced anything, a provider error lost the
hour's work for good (the role pointer had already moved on), and a finding the model called an
EXACT_CANDIDATE reached the compiler WITHOUT `params` -- so `compile_row`'s EXACT_RECIPE door, which
admits only `family` + `params` + `symbols`, could never open for a DeepSeek row. Every DeepSeek
"exact" strategy was re-read from prose or parked in the deepening queue.

WHAT THIS ADDS (third-brain addendum sections 6-13, 21, 23-27, 32, 38), and only this:

  * A PERSISTENT JOB QUEUE (`data/deepseek_lab/queue.json`). Jobs carry stable ids, so a restart
    resumes them and an event seen twice enqueues once. A provider failure keeps the job PENDING
    with a backoff; nothing is dropped for being deferred.
  * LABS A-Q PLUS CONVERSION as data, each with a cadence (hourly / daily / weekly) and the packet
    sections it may see. Event jobs fire when a packet section's content hash changes.
  * JOB SCORING inside the lab: measured downstream yield per lab (compiled exact candidates and
    gauntlet passes per call), urgency, age and model tier cost, with a cold-exploration floor and
    a probation prior. This only orders DeepSeek's own jobs; the desk's department budget stays
    `research_auction.py`'s.
  * OUTPUT CONTRACT ds-2: exact rules, falsifier, data inputs, registered family + params (the
    `formula` family takes an `alpha_grammar` expression, which is how a new mechanism becomes an
    exact executable). Vague rules, unknown series, unregistered families and invalid expressions
    are named and downgraded, never repaired by invention. Banal indicator variants are rejected
    as discoveries.
  * FREEZE + NOVELTY + GENEALOGY: every exact candidate is hashed FROZEN_PRE_EVALUATION; exact
    duplicates are collapsed, parameter neighbours share one trial family, descendants keep their
    parents.
  * TYPED ROUTING into the SAME stores: exact candidates -> `data/intelligence/deepseek`
    (compiler EXACT_RECIPE -> docket -> gauntlet); hypotheses -> the same door (deepening queue);
    data and source requests -> the hunt frontier (NAMED_ONLY = priority ground for the hunters)
    and an open-request ledger that re-checks arrival; capability challengers -> the existing walk.
  * COVERAGE DEBT: each exact candidate's same-asset-class translations are registered as owed
    coordinates and drained by cursor; a cap means "not this pass", never "never".
  * FEEDBACK: compiler receipts and gate-ledger verdicts are joined back by hypothesis id and
    credited to lab, model and prompt version; the scores above read that ledger.
  * A SEAT REGISTRY of EVERY `:free` model of every family, refreshed from OpenRouter's public
    model list (paid ids are never registered). Each model is a named seat with its own yield:
    the first job of a cycle takes the least-called seat (coverage), the rest go to the best
    measured seats, and a failed seat falls through to the next with the attempt on the record.
    The job is credited to the seat that ANSWERED -- never a silent substitution. A loopback
    open-weight seat (any family) takes over when the cloud is out.

AUTHORITY. Research generation only. Nothing here promotes, sizes, certifies, arms or merges; the
fences in `deepseek_cycle` apply to every object, and model text is data, never instruction.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from libs.ops import deepseek_cycle as ds
from libs.ops.llm_lab_core import (
    _ROOT,
    ATTRIBUTION,
    BASE_VALUE,
    COLD_LABS,
    LABS,
    MARKS,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    TIER_COST,
    _iso,
    _load,
    _now_dt,
    _parse,
    _save,
    context,
    due_jobs,
    ensure_cadence,
    fail_job,
    lab_prompt,
    load_queue,
    parse_objects,
    rearm_parked,
    save_queue,
    scan_events,
    validate,
)
from libs.ops.llm_lab_routing import (
    _requests,
    drain_debt,
    recheck_requests,
    record_call,
    refresh_attribution,
    route,
)
from libs.ops.llm_lab_seats import (
    make_chat,
    model_family,
    refresh_models,
)

# ---------------------------------------------------------------------------- job scoring


def lab_rate(attrib: dict[str, Any], lab: str) -> tuple[float, str]:
    """Measured downstream usefulness per call, with a probation prior.

    useful = exact candidates the compiler admitted + gauntlet passes x 5 + accepted requests x
    0.25. A lab with fewer than three calls is on PROBATION at rate 1.0: a new lab earns its first
    work, then keeps it only by producing."""
    row = (attrib.get("by_lab") or {}).get(lab) or {}
    calls = int(row.get("calls") or 0)
    if calls < 3:
        return 1.0, "PROBATION"
    useful = (float(row.get("compiled") or 0) + 5.0 * float(row.get("passed") or 0)
              + 0.25 * float(row.get("requests") or 0))
    return (1.0 + useful) / (1.0 + calls), "MEASURED"


def score(job: dict[str, Any], attrib: dict[str, Any], *, now: datetime | None = None
          ) -> dict[str, Any]:
    """Priority = value x measured yield x urgency x age / tier cost (section 26, inside the lab).
    The terms are named on the job so the ordering can be audited."""
    t = now or _now_dt()
    lab = job["lab"]
    rate, basis = lab_rate(attrib, lab)
    trig = str(job.get("trigger") or "")
    urgency = 1.5 if trig.startswith("event:") else 1.2 if trig.startswith("resume:") else 1.0
    urgency *= 0.8 ** int(job.get("attempts") or 0)
    created = _parse(job.get("created_utc")) or t
    age = 1.0 + min(3.0, max(0.0, (t - created).total_seconds() / 86400.0))
    cost = TIER_COST.get(LABS[lab]["tier"], 1.0)
    p = BASE_VALUE * rate * urgency * age / cost
    return {"priority": round(p, 4), "rate": round(rate, 4), "basis": basis,
            "urgency": round(urgency, 3), "age": round(age, 3), "cost": cost}


def select(jobs: list[dict[str, Any]], attrib: dict[str, Any], k: int, *,
           now: datetime | None = None) -> list[dict[str, Any]]:
    """Top-k by priority, one job per lab per cycle, and a COLD FLOOR: when any cold-exploration
    job is due, at least one slot goes to it whatever the scores say (section 18)."""
    if k <= 0 or not jobs:
        return []
    for j in jobs:
        j["score"] = score(j, attrib, now=now)
    ranked = sorted(jobs, key=lambda j: (-j["score"]["priority"], j["created_utc"], j["job_id"]))
    picked: list[dict[str, Any]] = []
    labs: set[str] = set()
    cold = next((j for j in ranked if j["lab"] in COLD_LABS), None)
    if cold is not None:
        picked.append(cold)
        labs.add(cold["lab"])
    for j in ranked:
        if len(picked) >= k:
            break
        if j in picked or j["lab"] in labs:
            continue
        picked.append(j)
        labs.add(j["lab"])
    return picked[:k]


# --------------------------------------------------------------------------- the cycle


def run_job(root: Path, job: dict[str, Any], packet: dict[str, Any], ctx: dict[str, Any],
            chat: Callable[..., dict[str, Any]], *, policy_hash: str) -> dict[str, Any]:
    lab = job["lab"]
    cold = ds.cold_context({"sections": packet.get("sections") or {},
                            "packet_hash": packet.get("packet_hash")})
    system, user = lab_prompt(lab, job, cold, ctx["contract"])
    tier = LABS[lab]["tier"]
    reply = chat(user, system, tier)
    if not reply.get("text"):
        fail_job(job, reply.get("error") or "empty reply")
        return {"job_id": job["job_id"], "lab": lab, "status": "CALL_FAILED",
                "why": reply.get("error"), "attempts": reply.get("attempts")}
    rid = f"lab{lab}_{job['job_id']}_{job.get('attempts', 0)}"
    sealed = ds.seal(rid, role=f"lab_{lab}", phase_a_output=reply["text"],
                     policy_hash=policy_hash, cold_context_hash=cold["cold_context_hash"],
                     provider=reply["provider"], model=reply["model"],
                     prompt_version=PROMPT_VERSION, root=root)
    objs, schema = parse_objects(reply["text"])
    prov = {"model": reply["model"], "provider": reply["provider"],
            "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION,
            "job_id": job["job_id"], "seal": sealed.get("path"),
            "packet_hash": packet.get("packet_hash")}
    recs = [validate(o, ctx) for o in objs]
    routed = route(root, recs, lab=lab, prov=prov, ctx=ctx, memory=ctx["memory"])
    job["status"], job["done_utc"] = "DONE", _iso(_now_dt())
    job["outcome"] = {"schema": schema, "objects": len(objs), **routed["counts"]}
    record_call(root, {"at": _iso(_now_dt()), "lab": lab, "job_id": job["job_id"],
                       "model": reply["model"], "provider": reply["provider"],
                       "prompt_version": PROMPT_VERSION, "schema": schema,
                       "objects": len(objs), "counts": routed["counts"],
                       "family": model_family(str(reply["model"])),
                       "seat_plan": (reply.get("pick") or {}).get("seats"),
                       "failed_seats": [a.get("model") for a in reply.get("attempts") or []]})
    return {"job_id": job["job_id"], "lab": lab, "status": "OK", "model": reply["model"],
            "provider": reply["provider"], "seal": sealed.get("verdict"), "schema": schema,
            "objects": len(objs), **routed}


def calls_per_cycle(env: dict[str, str]) -> int:
    """Calls this cycle: the env knob, never more than a twentieth of today's remaining free
    requests (the OpenRouter free allowance is account-wide and other organs share it)."""
    try:
        k = int(env.get("DEEPSEEK_CALLS_PER_CYCLE", "4"))
    except ValueError:
        k = 4
    try:
        from libs.ops.llm_seat import free_budget_left, free_tier_only
        if free_tier_only():
            k = min(k, max(1, free_budget_left() // 20))
    except Exception:
        pass
    return max(0, k)


def cycle(root: Path | None = None, *, packet: dict[str, Any], policy_hash: str,
          env: dict[str, str] | None = None, chat: Callable[..., dict[str, Any]] | None = None,
          k: int | None = None, fetch: Callable[[str], Any] | None = None,
          now: datetime | None = None) -> dict[str, Any]:
    """One pass: events + cadence -> queue -> score -> run k jobs -> drain debt -> feedback ->
    metrics. Never raises past a job: one bad job costs that job, not the cycle."""
    base = root or _ROOT
    e = dict(os.environ if env is None else env)
    t = now or _now_dt()
    q = load_queue(base)
    marks = _load(base / MARKS, {})
    if not isinstance(marks, dict):
        marks = {}
    rearmed = rearm_parked(q)
    made_events = scan_events(q, packet, marks, now=t)
    made_cadence = ensure_cadence(q, now=t)
    ctx = context(base)
    arrived = recheck_requests(base, ctx["series"], q)
    save_queue(base, q)
    _save(base / MARKS, marks)
    reg = refresh_models(base, fetch=fetch, now=t)
    attrib = _load(base / ATTRIBUTION, {})
    chat_fn = chat or make_chat(e, reg, attrib if isinstance(attrib, dict) else {})
    kk = calls_per_cycle(e) if k is None else k
    picked = select(due_jobs(q, now=t), attrib if isinstance(attrib, dict) else {}, kk, now=t)
    runs = []
    for job in picked:
        try:
            runs.append(run_job(base, job, packet, ctx, chat_fn, policy_hash=policy_hash))
        except Exception as exc:          # one bad job never takes the cycle down
            fail_job(job, f"{type(exc).__name__}: {exc}")
            runs.append({"job_id": job["job_id"], "lab": job["lab"], "status": "JOB_ERROR",
                         "why": f"{type(exc).__name__}: {str(exc)[:300]}"})
        save_queue(base, q)               # persisted after EVERY job: a kill loses one at most
    try:
        drain_limit = int(e.get("DEEPSEEK_DEBT_DRAIN", "25"))
    except ValueError:
        drain_limit = 25
    debt = drain_debt(base, drain_limit)
    fb = refresh_attribution(base, now=t)
    metrics = publish_metrics(base, q, fb, debt, reg, runs, now=t)
    return {"rearmed": rearmed, "events_enqueued": len(made_events),
            "cadence_enqueued": len(made_cadence), "requests_arrived": arrived,
            "calls_budget": kk, "runs": runs, "debt": debt, "metrics": metrics,
            "models": {"status": reg.get("status"),
                       "free_seats": len(reg.get("models") or []),
                       "families": reg.get("families") or []}}


def publish_metrics(root: Path, q: dict[str, Any], fb: dict[str, Any], debt: dict[str, Any],
                    reg: dict[str, Any], runs: list[dict[str, Any]], *,
                    now: datetime | None = None) -> dict[str, Any]:
    """Section 38. Every number is MEASURED from the lab's own files or says UNMEASURED."""
    t = now or _now_dt()
    jobs = list(q["jobs"].values())
    pending = [j for j in jobs if j.get("status") == "PENDING"]
    oldest = min((_parse(j.get("created_utc")) or t for j in pending), default=None)
    calls = fb.get("calls") or []
    day = [c for c in calls if (_parse(c.get("at")) or t) > t - timedelta(days=1)]
    ok = [c for c in day if c.get("schema") == "OK"]
    objs = sum(int(c.get("objects") or 0) for c in day)

    def tot(f: str) -> int:
        return sum(int((c.get("counts") or {}).get(f, 0)) for c in day)

    reqs = _requests(root)
    last_ok = max((c.get("at") for c in calls), default=None)
    m = {
        "updated_utc": _iso(t),
        "liveness": {"last_successful_call_utc": last_ok or "UNMEASURED: no call has succeeded",
                     "this_cycle_runs": len(runs),
                     "this_cycle_ok": sum(1 for r in runs if r.get("status") == "OK"),
                     "models_registry": reg.get("status", "UNMEASURED")},
        "queue": {"pending": len(pending),
                  "done": sum(1 for j in jobs if j.get("status") == "DONE"),
                  "parked": sum(1 for j in jobs if j.get("status") == "PARKED"),
                  "pending_by_lab": {lab: sum(1 for j in pending if j["lab"] == lab)
                                     for lab in LABS},
                  "oldest_pending_utc": _iso(oldest) if oldest else None},
        "production_24h": {"calls": len(day), "objects": objs, "exact": tot("exact"),
                           "deepening": tot("deepening"), "data_requests": tot("data_request"),
                           "validation_attacks": tot("validation_attack"),
                           "duplicates": tot("duplicate"), "invalid": tot("invalid")},
        "quality_24h": ({"valid_schema_rate": round(len(ok) / len(day), 3),
                         "exact_rate": round(tot("exact") / objs, 3) if objs else None,
                         "duplicate_rate": round(tot("duplicate") / objs, 3) if objs else None}
                        if day else "UNMEASURED: no call in 24h"),
        "pipeline": {"compiler": fb.get("compiler"), "gauntlet": {
            k: v for k, v in (fb.get("gauntlet") or {}).items() if k != "verdicts"}},
        "debt": {"coverage_owed": debt.get("owed"), "drained_this_cycle": debt.get("donated"),
                 "drain_cycles_at_this_rate": debt.get("drain_cycles_at_this_rate"),
                 "open_requests": len(reqs["open"]),
                 "open_by_type": {tt: sum(1 for r in reqs["open"].values()
                                          if r.get("object_type") == tt)
                                  for tt in ("DATA_REQUEST", "SOURCE_ACQUISITION_REQUEST",
                                             "REPRESENTATION_REQUEST", "VALIDATION_ATTACK")}},
        "economics": {"inference_cost_usd": 0.0 if os.environ.get("QUANT_FREE_TIER", "1") != "0"
                      else "UNMEASURED: paid route enabled",
                      "free_requests_used_24h": len(day)},
        "by_lab": fb.get("by_lab"), "by_model": fb.get("by_model"),
        "by_family": fb.get("by_family"),
        "authority": "RESEARCH GENERATION ONLY -- cannot promote, size, certify, arm or merge",
    }
    return m
