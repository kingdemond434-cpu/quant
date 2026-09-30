"""AI PEER REVIEW PANELS (Tier S layer 20): independent, typed reviewers that raise falsification
challenges which must be answered by evidence, not argued away.

Typed reviewers, each given a DIFFERENT slice of the candidate's record (a reviewer that sees
everything converges with the others; independence is the point):

    statistician      the selection-aware significance gates only (DSR, PBO, SPA, trials)
    econometrician    sample length, fold count, walk-forward stability
    microstructure    cost fields and the cost-stress gate
    execution         fills, tradeability, matched-fill count
    portfolio         dependence on the book (uniqueness from the topology organ)
    causal            the economic prior and the mechanism record (is there a falsifier?)
    reproducibility   the independent-replication verdict
    adversarial       the Red Queen's attacks on this exact candidate
    ecologist         the closure and agent-based stress worlds this candidate was replayed in

Each returns typed CHALLENGES. A challenge names the condition that would resolve it
(`resolves_when`) as a predicate over the evidence the desk will publish later -- a replication
verdict appearing, forward n crossing a threshold, the cost gate re-run at a higher multiplier.
`resolve()` re-evaluates every open challenge against the latest evidence each hour, so a challenge
is answered EXPERIMENTALLY by the desk's own experiment organs, never by the reviewer changing its
mind. Consensus is not enough: one unresolved HIGH challenge keeps the candidate CHALLENGED.

The panel never promotes and never demotes (firewall role `reviewer`); it publishes.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

Evidence = Mapping[str, Any]


@dataclass(frozen=True)
class Challenge:
    candidate: str
    reviewer: str
    kind: str
    claim: str
    severity: str  # HIGH / MEDIUM / LOW
    resolves_when: str  # name of a predicate in RESOLVERS

    @property
    def cid(self) -> str:
        return f"{self.candidate}|{self.reviewer}|{self.kind}"


def _g(ev: Evidence, *path: str) -> Any:
    cur: Any = ev
    for p in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(p)
    return cur


def _f(x: Any) -> float | None:
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def _matched_fills_10(ev: Evidence) -> bool | None:
    """Ten matched live fills, then: the live mean R captures more than half the forward clock's
    expectancy -- or, with no positive forward expectancy to compare against, is itself positive.

    Until 2026-09-30 this read `execution.capture`, which no evidence builder wrote: every
    candidate reaching ten fills was resolved AGAINST on a missing field (None -> 0.0 > 0.5)."""
    if (_f(_g(ev, "execution", "matched_fills")) or 0) < 10:
        return None
    cap = _f(_g(ev, "execution", "capture"))
    if cap is not None:
        return cap > 0.5
    live = _f(_g(ev, "execution", "live_mean_r"))
    return None if live is None else live > 0


#: the closure worlds that GAP the tape (the market or the instrument reopens elsewhere): a
#: position held through one meets a price nobody could trade at in between. `session_closed`
#: removes a session instead, which starves a signal rather than gapping a held position.
CLOSURE_GAP_WORLDS: tuple[str, ...] = ("market_closure_gap", "instrument_halt")
CLOSURE_WORLDS: tuple[str, ...] = ("market_closure_gap", "session_closed", "instrument_halt")
#: every agent-based ecology (libs/tiers/agent_worlds.NAMES)
AGENT_WORLDS: tuple[str, ...] = ("abm_momentum_herd", "abm_value_anchor",
                                 "abm_liquidity_withdrawal")
#: the named failure modes those worlds earn (synthetic_regimes.FLAG_RULES)
CLOSURE_FLAGS: tuple[str, ...] = ("dies_on_market_closure", "needs_the_closed_session",
                                  "halt_fragile")
AGENT_FLAGS: dict[str, str] = {"dies_in_herding_market": "abm_momentum_herd",
                               "dies_in_value_market": "abm_value_anchor",
                               "dies_when_liquidity_withdraws": "abm_liquidity_withdrawal"}


def _measured_exp(ev: Evidence, family: str, world: str) -> float | None:
    """The candidate's own expectancy (R) in one named world, or None when it was not measured."""
    row = _g(ev, "worlds", family, world)
    if not isinstance(row, Mapping) or row.get("status") != "MEASURED":
        return None
    return _f(row.get("expectancy"))


def _closure_gap_losses(ev: Evidence) -> list[str] | None:
    """The gap worlds in which the candidate's OWN positive edge became a loss: positive
    expectancy on the untouched tape, negative on its replay through the gap. None while the
    baseline or every gap world is unmeasured -- absence is never a clean verdict. A candidate
    with no edge of its own returns [] here: the gap did not cause that loss."""
    base = _f(_g(ev, "worlds", "baseline_expectancy"))
    exps = {w: _measured_exp(ev, "closure", w) for w in CLOSURE_GAP_WORLDS}
    if base is None or all(v is None for v in exps.values()):
        return None
    if base <= 0:
        return []
    return [w for w, v in exps.items() if v is not None and v < 0]


def _closure_gap_survives(ev: Evidence) -> bool | None:
    lost = _closure_gap_losses(ev)
    return None if lost is None else not lost


def _agent_worlds_survive(ev: Evidence) -> bool | None:
    """False when the candidate LOSES in every agent ecology (all three measured, all three
    negative): no market made of traders keeps it alive. True as soon as one measured ecology
    is non-negative; None while any is unmeasured and none has survived."""
    exps = [_measured_exp(ev, "agents", w) for w in AGENT_WORLDS]
    if any(v is not None and v >= 0 for v in exps):
        return True
    if any(v is None for v in exps):
        return None
    return False


def _closure_agent_measured(ev: Evidence) -> bool | None:
    """True once any closure or agent world has replayed the candidate; open (None) until then."""
    fams = (("closure", CLOSURE_WORLDS), ("agents", AGENT_WORLDS))
    return True if any(_measured_exp(ev, fam, w) is not None
                       for fam, ws in fams for w in ws) else None


#: predicate name -> function(evidence) -> True when the challenge is answered in the candidate's
#: favour, False when answered against it, None while still open
RESOLVERS: dict[str, Callable[[Evidence], bool | None]] = {
    "replication_agrees": lambda ev: (None if _g(ev, "replication", "verdict") is None
                                      else _g(ev, "replication", "verdict") == "AGREE"),
    "forward_n_40": lambda ev: (None if (_f(_g(ev, "forward", "n")) or 0) < 40
                                else (_f(_g(ev, "forward", "mean_r")) or 0.0) > 0),
    "stress_x5_positive": lambda ev: (None if _f(_g(ev, "stress", "exp_x5")) is None
                                      else (_f(_g(ev, "stress", "exp_x5")) or 0.0) > 0),
    "matched_fills_10": lambda ev: _matched_fills_10(ev),
    "uniqueness_03": lambda ev: (None if _f(_g(ev, "topology", "uniqueness")) is None
                                 else (_f(_g(ev, "topology", "uniqueness")) or 0.0) >= 0.3),
    "falsifier_declared": lambda ev: (None if _g(ev, "mechanism") is None
                                      else bool(_g(ev, "mechanism", "falsifier"))),
    "red_queen_survives": lambda ev: (None if _g(ev, "red_queen", "attacks") is None
                                      else not bool(_g(ev, "red_queen", "killed"))),
    "online_fdr_admits": lambda ev: (None if _g(ev, "online_fdr") is None
                                     else not bool(_g(ev, "online_fdr", "over_budget"))),
    # the candidate's own replays through the closure and agent-based worlds (organ_worlds)
    "closure_gap_survives": _closure_gap_survives,
    "agent_worlds_survive": _agent_worlds_survive,
    "closure_agent_measured": _closure_agent_measured,
}


def statistician(cid: str, ev: Evidence) -> list[Challenge]:
    out = []
    dsr = _f(_g(ev, "gates", "deflated_sharpe", "dsr"))
    n_tr = _f(_g(ev, "gates", "deflated_sharpe", "n_trials"))
    pbo = _f(_g(ev, "gates", "pbo", "pbo"))
    if dsr is not None and dsr < 0.99:
        out.append(Challenge(cid, "statistician", "DSR_MARGIN", f"DSR {dsr:.3f} is within 0.04 of "
                             "the bar", "MEDIUM", "forward_n_40"))
    if n_tr is not None and n_tr < 50:
        out.append(Challenge(cid, "statistician", "TRIAL_CHARGE", f"charged only {n_tr:.0f} "
                             "trials; the lifetime online-FDR level must still admit it", "HIGH",
                             "online_fdr_admits"))
    if pbo is not None and pbo > 0.2:
        out.append(Challenge(cid, "statistician", "PBO", f"PBO {pbo:.2f}", "HIGH",
                             "forward_n_40"))
    return out


def econometrician(cid: str, ev: Evidence) -> list[Challenge]:
    out = []
    days = _f(_g(ev, "days"))
    folds = _f(_g(ev, "gates", "cpcv", "folds"))
    stab = _f(_g(ev, "gates", "walk_forward", "stability"))
    if days is not None and days < 750:
        out.append(Challenge(cid, "econometrician", "SHORT_SAMPLE", f"{days:.0f} days", "MEDIUM",
                             "forward_n_40"))
    if folds is not None and folds < 10:
        out.append(Challenge(cid, "econometrician", "FEW_FOLDS", f"{folds:.0f} CPCV folds", "LOW",
                             "forward_n_40"))
    if stab is not None and stab < 0.75:
        out.append(Challenge(cid, "econometrician", "UNSTABLE", f"walk-forward stability "
                             f"{stab:.2f}", "HIGH", "forward_n_40"))
    return out


def microstructure(cid: str, ev: Evidence) -> list[Challenge]:
    x3 = _f(_g(ev, "gates", "stress_costs", "exp_x3"))
    ev0 = _f(_g(ev, "gates", "expected_value", "ev"))
    if x3 is not None and ev0 and ev0 > 0 and x3 / ev0 < 0.6:
        return [Challenge(cid, "microstructure", "COST_FRAGILE", f"x3 cost keeps {x3 / ev0:.0%} "
                          "of EV", "HIGH", "stress_x5_positive")]
    return []


def execution(cid: str, ev: Evidence) -> list[Challenge]:
    mf = _f(_g(ev, "execution", "matched_fills"))
    if mf is None or mf < 10:
        return [Challenge(cid, "execution", "NO_FILL_EVIDENCE", f"{mf or 0:.0f} matched fills",
                          "MEDIUM", "matched_fills_10")]
    return []


def portfolio(cid: str, ev: Evidence) -> list[Challenge]:
    u = _f(_g(ev, "topology", "uniqueness"))
    if u is not None and u < 0.3:
        return [Challenge(cid, "portfolio", "CLONE", f"uniqueness {u:.2f} vs the book", "MEDIUM",
                          "uniqueness_03")]
    return []


def causal(cid: str, ev: Evidence) -> list[Challenge]:
    mech = _g(ev, "mechanism")
    if not isinstance(mech, Mapping) or not mech.get("falsifier"):
        return [Challenge(cid, "causal", "NO_FALSIFIER", "no machine-readable falsifier for the "
                          "mechanism", "HIGH", "falsifier_declared")]
    return []


def reproducibility(cid: str, ev: Evidence) -> list[Challenge]:
    v = _g(ev, "replication", "verdict")
    if v != "AGREE":
        return [Challenge(cid, "reproducibility", "NOT_REPLICATED", f"replication {v or 'absent'}",
                          "HIGH", "replication_agrees")]
    return []


def adversarial(cid: str, ev: Evidence) -> list[Challenge]:
    if _g(ev, "red_queen", "killed"):
        return [Challenge(cid, "adversarial", "ATTACK_SUCCEEDED",
                          str(_g(ev, "red_queen", "killed_by") or "an evolved attack"), "HIGH",
                          "red_queen_survives")]
    return []


def epistemologist(cid: str, ev: Evidence) -> list[Challenge]:
    """The uncertainty engine's answer, raised in the panel (layer 37): a forward edge whose
    interval still straddles zero has not been decided by its evidence -- 'not enough evidence'
    is a finding the panel must carry, never a silent pass."""
    if _g(ev, "epistemic", "decision") == "INSUFFICIENT_EVIDENCE":
        return [Challenge(cid, "epistemologist", "UNDECIDED",
                          f"forward edge undecided on {_g(ev, 'epistemic', 'n') or 0} trades "
                          f"(label {_g(ev, 'epistemic', 'label') or '?'})", "MEDIUM",
                          "forward_n_40")]
    return []


def conflict(cid: str, ev: Evidence) -> list[Challenge]:
    """The firewall's shared-reward flag (layer 32), raised in the panel: an evaluator that is
    paid from the same reward artifact as the candidate it judged is not independent of it. A
    SELF flag (the evaluator's own host bore the candidate) is HIGH; a SHARED one MEDIUM. Both
    are answered only by an independent replication, never by the flagged evaluator."""
    out: list[Challenge] = []
    flags = _g(ev, "firewall", "shared_reward") or []
    for sev, kind, level in (("SELF", "SELF_JUDGED", "HIGH"), ("SHARED", "SHARED_REWARD",
                                                                "MEDIUM")):
        hit = sorted({str(f.get("evaluator")) for f in flags
                      if isinstance(f, Mapping) and f.get("severity") == sev})
        if hit:
            out.append(Challenge(cid, "conflict", kind, f"judged by {', '.join(hit)}, paid from "
                                 "the same reward artifact as this candidate's producer", level,
                                 "replication_agrees"))
    return out


def ecologist(cid: str, ev: Evidence) -> list[Challenge]:
    """The closure and agent-based worlds (Tier S layer 16), read per candidate. Only a failure
    is a finding, and the severity follows who caused it:

      HIGH    CLOSURE_GAP_LOSS        the candidate's own positive edge turns negative when the
                                      market or the instrument shuts and reopens gapped: its
                                      positions were caught by the gap
      HIGH    LOSES_IN_EVERY_ECOLOGY  negative expectancy in all three agent ecologies
      MEDIUM  CLOSURE_FRAGILE         a closure flag without either (a starved session, or no
                                      edge of its own to break); answered by forward evidence
      MEDIUM  ECOLOGY_DEPENDENT       it dies in two of the three ecologies (LOW for one)
      LOW     WORLDS_UNMEASURED       no closure or agent world has replayed it yet

    Both HIGH challenges resolve on the candidate's OWN replays (`closure_gap_survives`,
    `agent_worlds_survive`), which is what makes them candidate-specific at the door."""
    out: list[Challenge] = []
    flags = {str(f) for f in (_g(ev, "worlds", "flags") or [])}
    lost = _closure_gap_losses(ev)
    if lost:
        base = _f(_g(ev, "worlds", "baseline_expectancy")) or 0.0
        exps = ", ".join(f"{w} {_measured_exp(ev, 'closure', w) or 0.0:+.3f}R" for w in lost)
        out.append(Challenge(cid, "ecologist", "CLOSURE_GAP_LOSS",
                             f"its own edge ({base:+.3f}R on the untouched tape) loses when the "
                             f"venue gaps: {exps}", "HIGH", "closure_gap_survives"))
    elif flags & set(CLOSURE_FLAGS):
        out.append(Challenge(cid, "ecologist", "CLOSURE_FRAGILE",
                             f"closure flags {sorted(flags & set(CLOSURE_FLAGS))}", "MEDIUM",
                             "forward_n_40"))
    if _agent_worlds_survive(ev) is False:
        exps_a = {w: _measured_exp(ev, "agents", w) or 0.0 for w in AGENT_WORLDS}
        out.append(Challenge(cid, "ecologist", "LOSES_IN_EVERY_ECOLOGY",
                             "negative in all three agent ecologies: "
                             + ", ".join(f"{w} {v:+.3f}R" for w, v in exps_a.items()),
                             "HIGH", "agent_worlds_survive"))
    else:
        dies = sorted(w for f, w in AGENT_FLAGS.items() if f in flags)
        if dies:
            out.append(Challenge(cid, "ecologist", "ECOLOGY_DEPENDENT",
                                 f"dies in {', '.join(dies)}",
                                 "MEDIUM" if len(dies) >= 2 else "LOW", "forward_n_40"))
    if _g(ev, "worlds") is not None and _closure_agent_measured(ev) is None:
        out.append(Challenge(cid, "ecologist", "WORLDS_UNMEASURED",
                             "no closure or agent-based world has replayed this candidate",
                             "LOW", "closure_agent_measured"))
    return out


#: reviewer -> (function, the evidence keys it is allowed to see)
PANEL: dict[str, tuple[Callable[[str, Evidence], list[Challenge]], tuple[str, ...]]] = {
    "statistician": (statistician, ("gates", "online_fdr")),
    "econometrician": (econometrician, ("gates", "days")),
    "microstructure": (microstructure, ("gates", "stress")),
    "execution": (execution, ("execution",)),
    "portfolio": (portfolio, ("topology",)),
    "causal": (causal, ("mechanism",)),
    "reproducibility": (reproducibility, ("replication",)),
    "adversarial": (adversarial, ("red_queen",)),
    "epistemologist": (epistemologist, ("epistemic",)),
    "conflict": (conflict, ("firewall",)),
    "ecologist": (ecologist, ("worlds",)),
}


def review(cid: str, ev: Evidence) -> list[Challenge]:
    out: list[Challenge] = []
    for _name, (fn, keys) in PANEL.items():
        view = {k: ev[k] for k in keys if k in ev}
        out.extend(fn(cid, view))
    return out


def resolve(ch: Challenge, ev: Evidence) -> str:
    fn = RESOLVERS.get(ch.resolves_when)
    if fn is None:
        return "OPEN"
    r = fn(ev)
    return "OPEN" if r is None else ("PASSED" if r else "FAILED")


def panel_report(candidates: Mapping[str, Evidence]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    counts = {"OPEN": 0, "PASSED": 0, "FAILED": 0}
    verdicts = {"CLEAR": 0, "CHALLENGED": 0, "FAILED": 0}
    for cid, ev in candidates.items():
        chs = review(cid, ev)
        states = []
        for ch in chs:
            s = resolve(ch, ev)
            counts[s] += 1
            states.append({**asdict(ch), "state": s})
        if any(s["state"] == "FAILED" and s["severity"] == "HIGH" for s in states):
            v = "FAILED"
        elif any(s["state"] == "OPEN" and s["severity"] == "HIGH" for s in states):
            v = "CHALLENGED"
        else:
            v = "CLEAR"
        verdicts[v] += 1
        rows.append({"candidate": cid, "verdict": v, "challenges": states})
    total = sum(counts.values())
    return {"n_candidates": len(candidates), "verdicts": verdicts, "challenges": counts,
            "resolved_share": ((counts["PASSED"] + counts["FAILED"]) / total) if total else None,
            "rows": rows}
