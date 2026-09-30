"""THE SELF-MODEL AND ARCHITECTURE EVOLUTION (Tier S layers 14/29/30/33 and the closing rule).

The desk's final job is to never need another blueprint: it must find its own largest deficiency,
propose alternatives, benchmark them under sealed evaluation, and upgrade itself when the evidence
supports it -- without ever rewriting its own constitution.

SELF-MODEL. `inventory()` reads what the Tier S organs publish and states, per capability, what
the desk KNOWS about itself: data it lacks (acquisition ranking), regimes/cells poorly covered
(MAP-Elites empty niches), alpha clusters over-represented (topology steering), weak research
disciplines (researcher-market posteriors), validation weakness (immune score, blind spots the Red
Queen found), unexplained live deviations (prediction overconfidence), layers whose contract is
REJECTED or UNMEASURED, and the epistemic census (how much of what it publishes is decidable).

DEFICIENCY RANKING. Each deficiency gets an EXPECTED IMPROVEMENT: gap x weight of the gain it
blocks x P(a fix works) / cost. The top of that list is the next thing the desk works on, and it is
written to the CEO docket as a task -- the planning question is "what modification to myself has
the largest expected improvement in future research productivity?".

ARCHITECTURE EVOLUTION. A challenger for a component is registered with the twin, run in shadow,
and scored on the SEALED ARCHITECTURE SUITE: the meta-benchmark (immune score and power), the
order-protocol model check, the chaos campaign, replay consistency, and the layer contracts. A
release that regresses any sealed score is BLOCKED from self-promotion; a research-side challenger
that improves without regressing is ADOPTED; a money-path challenger becomes a PROPOSAL. The
constitution is outside the loop: amendments stay proposals until the principal ratifies
(`libs/tiers/truth_kernel.constitution_status`).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

#: how much a blocked gain matters when ranking deficiencies (the principal's order of value)
GAIN_WEIGHT: dict[str, float] = {
    "ALPHA_DISCOVERY": 1.0, "FDR_REDUCTION": 0.9, "FALSIFICATION": 0.9, "CALIBRATION": 0.8,
    "EXECUTION_CAPTURE": 0.8, "INFO_PER_COMPUTE": 0.7, "PRODUCTIVITY": 0.7,
    "OPERATIONAL_RISK": 0.6,
}

#: sealed-suite metrics and the direction that is better; a release may not move any the wrong way
SEALED_METRICS: dict[str, str] = {
    "immune_score": "up", "power": "up", "protocol_proven": "up", "protocol_verified": "up",
    "chaos_breaches": "down",
    "replay_share": "up", "firewall_violations": "down", "journal_ok": "up",
}


def _get(d: Mapping[str, Any] | None, *path: str) -> Any:
    cur: Any = d
    for p in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(p)
    return cur


def inventory(reports: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Deficiencies from the Tier S reports. Each: area, gap in [0,1], gain, p_fix, cost, why."""
    out: list[dict[str, Any]] = []

    def add(area: str, gap: float | None, gain: str, why: str, p_fix: float = 0.5,
            cost: float = 1.0) -> None:
        if gap is None:
            gap, why = 0.5, why + " (UNMEASURED: counted at half weight, never as zero)"
        out.append({"area": area, "gap": round(max(0.0, min(1.0, float(gap))), 4),
                    "gain": gain, "p_fix": p_fix, "cost": cost, "why": why})

    imm = _get(reports.get("immune"), "score", "immune_score")
    add("validation.immune", None if imm is None else 1.0 - float(imm), "FALSIFICATION",
        f"planted traps let through: {_get(reports.get('immune'), 'score', 'traps_let_through')}",
        p_fix=0.6)
    powr = _get(reports.get("immune"), "score", "power")
    add("validation.power", None if powr is None else 1.0 - float(powr), "ALPHA_DISCOVERY",
        "genuine planted signals rejected by the validator", p_fix=0.5)
    # THE PRODUCTION CERTIFIER'S OWN POWER on the sealed suite's genuine controls -- the lost-
    # discovery side of the real gates, which a perfect immune score can hide (power_alarm)
    ppow = _get(reports.get("immune"), "production", "power")
    add("validation.production_power", None if ppow is None else 1.0 - float(ppow),
        "ALPHA_DISCOVERY", "genuine positive controls the PRODUCTION certifier rejects "
        f"({_get(reports.get('immune'), 'power_alarm') or 'no alarm'})", p_fix=0.5)
    conf = _get(reports.get("formal"), "conformance", "evidenced_share")
    add("ops.protocol_conformance", None if conf is None else 1.0 - float(conf),
        "OPERATIONAL_RISK", "gateway send sites that break the model-checked order protocol: "
        f"{_get(reports.get('formal'), 'conformance', 'obligations')}", p_fix=0.6)
    # THE CLAIM, NOT THE MODEL (S31's consumer, `formal.claim` over FORMAL.json): a PROVEN model
    # whose knobs the gateway lacks is not a verified protocol, and the gap is the share of
    # invariants the implementation does not back. VIOLATED is a full gap; UNMEASURED half.
    fc = reports.get("formal_claim")
    if fc is not None:
        fclaim = _get(fc, "claim")
        vs = _get(fc, "verified_share")
        gap = (1.0 if fclaim == "VIOLATED" else None if fclaim in (None, "UNMEASURED")
               or vs is None else 1.0 - float(vs))
        add("ops.protocol_verified", gap, "OPERATIONAL_RISK",
            f"order protocol claim {fclaim}: {'; '.join(_get(fc, 'reasons') or [])[:300]}",
            p_fix=0.6)
    rq = _get(reports.get("red_queen"), "attack_success")
    add("validation.red_queen", rq, "FALSIFICATION",
        f"evolved attacks fool the defender; blind spots "
        f"{_get(reports.get('red_queen'), 'blind_spots')}", p_fix=0.5)
    over = _get(reports.get("online_fdr"), "over_budget_share")
    add("inference.lifetime_budget", over, "FDR_REDUCTION",
        "certificates issued at a level the lifetime online-FDR budget cannot afford", p_fix=0.7)
    comb = _get(reports.get("topology"), "rank", "combined")
    n = _get(reports.get("topology"), "rank", "n_sleeves")
    add("breadth.independence", None if not comb or not n else 1.0 - float(comb) / float(n),
        "ALPHA_DISCOVERY", f"effective independent rank {comb} of {n} sleeves", p_fix=0.4)
    cov = _get(reports.get("qd"), "coverage", "share")
    add("breadth.niches", None if cov is None else 1.0 - float(cov), "ALPHA_DISCOVERY",
        "MAP-Elites niches empty", p_fix=0.5, cost=0.5)
    oc = _get(reports.get("predictions"), "score", "overconfidence")
    add("calibration.forecasts", None if oc is None else min(1.0, abs(float(oc) - 1.0)),
        "CALIBRATION", f"standardised forecast error sd {oc}", p_fix=0.6)
    acc = _get(reports.get("predictions"), "coverage", "accounted_share")
    add("calibration.accounting", None if acc is None else 1.0 - float(acc), "CALIBRATION",
        "trades with no forecast registered before them", p_fix=0.8, cost=0.5)
    rs = _get(reports.get("replay"), "reconstructible_share")
    add("ops.replay", None if rs is None else 1.0 - float(rs), "OPERATIONAL_RISK",
        "desk components the durable logs cannot rebuild", p_fix=0.7)
    tk = _get(reports.get("truth_kernel"), "coverage", "share")
    add("provenance.fills", None if tk is None else 1.0 - float(tk), "OPERATIONAL_RISK",
        "fills whose ancestry the truth kernel cannot reconstruct", p_fix=0.7)
    fw = _get(reports.get("firewall"), "audit", "n_violations")
    add("governance.firewall", None if fw is None else min(1.0, float(fw) / 10.0),
        "FDR_REDUCTION", "organs that cross an epistemic role boundary", p_fix=0.8, cost=0.5)
    dec = _get(reports.get("epistemic"), "decidable_share")
    add("epistemics.decidable", None if dec is None else 1.0 - float(dec), "CALIBRATION",
        "published quantities not decidable from their evidence", p_fix=0.4)
    for layer, v in (_get(reports.get("contracts"), "layers") or {}).items():
        verdict = _get(v, "verdict")
        if verdict in ("REJECTED", "UNMEASURED"):
            add(f"layer.{layer}", 1.0 if verdict == "REJECTED" else None,
                str(_get(v, "gain") or "PRODUCTIVITY"),
                f"contract {verdict}: {_get(v, 'why')}", p_fix=0.3)
    return out


#: research-queue statuses that are WAITING for the gate (anything else has been judged/closed)
GATE_WAITING: frozenset[str] = frozenset({"QUEUED_CANONICAL_GAUNTLET", "PENDING", "QUEUED"})
#: a backlog that takes this many hours to drain at the measured verdict rate is a full gap
BACKLOG_FULL_GAP_H = 168.0
#: allocator bindings that hold the book BELOW what it solved for (the free optimum)
BELOW_OPTIMUM_BINDINGS: frozenset[str] = frozenset({"cap", "ceiling", "ruin_guard",
                                                     "measurement_edge", "survival"})


def operational_inventory(*, queue_status: Mapping[str, int] | None,
                          oldest_waiting_h: float | None,
                          verdicts_per_h: float | None,
                          compute: Sequence[Mapping[str, Any]] | None,
                          allocation: Mapping[str, Any] | None) -> tuple[list[dict[str, Any]],
                                                                         dict[str, Any]]:
    """The three self-facts the organ reports never carried, as deficiency rows (same shape as
    `inventory`) plus the measurements behind them. Each is UNMEASURED (half weight) when its
    artifact is absent -- never a zero.

      gate backlog      cells waiting for the gauntlet / cells it has cleared per hour = hours
                        to drain; gap = drain hours / BACKLOG_FULL_GAP_H (capped at 1)
      compute timeouts  the share of recorded leg runs that ended in a timeout or were
                        interrupted -- each is compute spent with no verdict
      allocator binding the constraint that bound the allocator's book and the growth it left
                        on the table: (free optimum - deployed) / free optimum when the binding
                        is one that holds the book below its own solve; the fact, never a
                        recommendation to loosen anything (sizing is outside this organ)."""
    rows: list[dict[str, Any]] = []
    facts: dict[str, Any] = {}

    def add(area: str, gap: float | None, gain: str, why: str, p_fix: float = 0.5,
            cost: float = 1.0) -> None:
        if gap is None:
            gap, why = 0.5, why + " (UNMEASURED: counted at half weight, never as zero)"
        rows.append({"area": area, "gap": round(max(0.0, min(1.0, float(gap))), 4),
                     "gain": gain, "p_fix": p_fix, "cost": cost, "why": why})

    # gate backlog
    if queue_status is None:
        facts["gate_backlog"] = {"status": "UNMEASURED", "why": "no research queue"}
        add("throughput.gate_backlog", None, "PRODUCTIVITY", "cells waiting for the gauntlet")
    else:
        waiting = sum(int(v) for k, v in queue_status.items() if k in GATE_WAITING)
        drain_h = (waiting / verdicts_per_h) if verdicts_per_h and verdicts_per_h > 0 else None
        facts["gate_backlog"] = {"status": "MEASURED", "waiting": waiting,
                                 "by_status": dict(queue_status),
                                 "verdicts_per_h": verdicts_per_h, "drain_h": drain_h,
                                 "oldest_waiting_h": oldest_waiting_h}
        if waiting == 0:
            gap: float | None = 0.0
        elif drain_h is None:
            gap = 1.0 if verdicts_per_h == 0 else None       # a gate that clears nothing
        else:
            gap = drain_h / BACKLOG_FULL_GAP_H
        add("throughput.gate_backlog", gap, "PRODUCTIVITY",
            f"{waiting} cells wait for the gauntlet at {verdicts_per_h} verdicts/h "
            f"(drain {'unknown' if drain_h is None else f'{drain_h:.0f}h'}, oldest "
            f"{'unknown' if oldest_waiting_h is None else f'{oldest_waiting_h:.0f}h'})",
            p_fix=0.6)
    # compute timeouts
    if not compute:
        facts["compute_timeouts"] = {"status": "UNMEASURED", "why": "no compute ledger rows"}
        add("compute.timeouts", None, "INFO_PER_COMPUTE", "leg runs that time out")
    else:
        def bad(o: str) -> bool:
            low = o.lower()
            return "timeout" in low or "timed out" in low or low == "interrupted"
        outs = [str(r.get("outcome") or "") for r in compute]
        by_run: dict[str, int] = {}
        wasted = 0.0
        for r, o in zip(compute, outs, strict=True):
            if bad(o):
                by_run[str(r.get("run") or "?")] = by_run.get(str(r.get("run") or "?"), 0) + 1
                wasted += float(r.get("wall_s") or 0.0)
        n_bad = sum(by_run.values())
        facts["compute_timeouts"] = {"status": "MEASURED", "runs": len(outs),
                                     "timeouts": n_bad, "wasted_wall_s": round(wasted, 1),
                                     "by_run": dict(sorted(by_run.items(),
                                                           key=lambda kv: -kv[1])[:15])}
        add("compute.timeouts", n_bad / len(outs), "INFO_PER_COMPUTE",
            f"{n_bad} of {len(outs)} recorded leg runs timed out or were interrupted "
            f"({wasted:.0f}s of wall time with no verdict); worst "
            f"{', '.join(list(facts['compute_timeouts']['by_run'])[:3]) or 'none'}", p_fix=0.7)
    # allocator binding constraints
    heat = (allocation or {}).get("heat") if isinstance(allocation, Mapping) else None
    if not isinstance(heat, Mapping):
        facts["allocator_binding"] = {"status": "UNMEASURED", "why": "no allocator artifact"}
        add("allocator.binding", None, "ALPHA_DISCOVERY", "the allocator's binding constraint")
    else:
        binding = str(heat.get("binding") or "")
        held = bool(heat.get("held"))
        free = heat.get("free_optimum")
        total = heat.get("total")
        facts["allocator_binding"] = {
            "status": "MEASURED", "binding": binding or None, "held_book": held,
            "free_optimum": free, "deployed": total, "resolved": heat.get("resolved"),
            "shortfall": heat.get("shortfall"),
            "operative_ceiling": (heat.get("envelope") or {}).get("operative_ceiling")
            if isinstance(heat.get("envelope"), Mapping) else None}
        try:
            fo, tt = float(free), float(total)  # type: ignore[arg-type]
            left = max(0.0, fo - tt) / fo if fo > 0 else 0.0
        except (TypeError, ValueError):
            left = None
        gap_a = (left if left is not None and (binding in BELOW_OPTIMUM_BINDINGS or held)
                 else (0.0 if left is not None else None))
        facts["allocator_binding"]["growth_left_share"] = None if left is None else round(
            left, 4)
        add("allocator.binding", gap_a, "ALPHA_DISCOVERY",
            f"the book is bound by '{binding or 'nothing'}'{' (held book)' if held else ''}: "
            f"deployed {total} of a free optimum {free} -- more independent positive-Elog "
            "sleeves inside the same heat is what moves this", p_fix=0.3)
    return rows, facts


def rank(deficiencies: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for d in deficiencies:
        ei = float(d["gap"]) * GAIN_WEIGHT.get(str(d["gain"]), 0.5) * float(d["p_fix"]) / max(
            1e-6, float(d["cost"]))
        rows.append({**d, "expected_improvement": round(ei, 5)})
    rows.sort(key=lambda r: (-float(r["expected_improvement"]), str(r["area"])))
    return rows


def sealed_scorecard(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, float | None]:
    def f(x: Any) -> float | None:
        try:
            return None if x is None else float(x)
        except (TypeError, ValueError):
            return None
    return {
        "immune_score": f(_get(reports.get("immune"), "score", "immune_score")),
        "power": f(_get(reports.get("immune"), "score", "power")),
        "protocol_proven": f(1.0 if _get(reports.get("formal"), "desk_all_proven") else 0.0)
        if reports.get("formal") else None,
        # VERIFIED is the implementation-backed claim (S31), never the model check alone
        "protocol_verified": f(_get(reports.get("formal_claim"), "verified_share"))
        if reports.get("formal_claim") else None,
        "chaos_breaches": f(sum((_get(reports.get("chaos"), "campaign", "breaches") or {})
                                .values())) if reports.get("chaos") else None,
        "replay_share": f(_get(reports.get("replay"), "reconstructible_share")),
        "firewall_violations": f(_get(reports.get("firewall"), "audit", "n_violations")),
        "journal_ok": f(1.0 if _get(reports.get("truth_kernel"), "verify", "ok") else 0.0)
        if reports.get("truth_kernel") else None,
    }


def regression(prev: Mapping[str, float | None], cur: Mapping[str, float | None],
               tol: float = 1e-9) -> dict[str, Any]:
    regressed = []
    for k, better in SEALED_METRICS.items():
        a, b = prev.get(k), cur.get(k)
        if a is None or b is None:
            continue
        if (better == "up" and b < a - tol) or (better == "down" and b > a + tol):
            regressed.append({"metric": k, "before": a, "after": b})
    return {"regressed": regressed, "blocked": bool(regressed)}


def adoption(challenger: Mapping[str, Any], verdict: str, money_path: bool,
             blocked: bool) -> str:
    if blocked:
        return "BLOCKED_BY_SEALED_REGRESSION"
    if verdict in ("PROMOTE", "PROPOSE"):
        return "PROPOSAL_FOR_PRINCIPAL" if money_path else "ADOPTED"
    if verdict == "REJECT":
        return "REJECTED"
    return "SHADOW"
