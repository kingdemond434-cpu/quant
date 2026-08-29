"""Two loops at different speeds: one steers research in hours, one decides truth in weeks.

WHY THIS EXISTS (principal, 2026-08-29)

    "Loop speed. They close hypothesis->feedback in hours. We take 14 days minimum because
     forward evidence is wall-clock. That's a 100x+ iteration-rate difference, and iteration rate
     is how a research system learns."
    "The loop iterates on the RESEARCH; ours iterates on the CANDIDATE."

Both true, and the second is the one that costs more. RD-Agent's feedback changes WHAT IT
RESEARCHES NEXT; this desk re-ran the same gauntlet on more variants of ground already mined --
7.3 candidates per unit of ground, 84% of them carrying no declared mechanism. Their bandit had
somewhere to send the budget. Until the census existed, nothing here even measured where the
budget went.

THE FIX IS NOT TO SPEED UP THE TRUTH ENGINE. Wall-clock forward evidence is slow because it is
honest: a held-out historical split still shares the selection era, and every framework inspected
today calls that "OOS". Speeding it up would trade the desk's one genuine advantage for their one
genuine advantage, which is a bad swap in the direction that compounds -- alpha-search ran a fast
loop around a validator with a 1000x cost error and a backtest that returned random numbers, and
the speed simply manufactured wrong answers faster.

SO: TWO LOOPS, WITH A FIREWALL BETWEEN THEM.

    FAST (this file, hourly)     signal: gauntlet outcome on HISTORY. Steers where the next
                                 trials go -- region, mechanism, branch. Has NO promotion
                                 authority whatsoever and cannot move a candidate toward live.
    SLOW (forward shadow, 14d)   signal: wall-clock forward evidence. Decides truth. Unchanged.

The fast loop is allowed to be wrong, because being wrong only costs a misdirected trial. The
slow loop is not, because being wrong costs capital. Keeping the authority boundary explicit is
what lets the desk have their iteration rate without inheriting their failure mode.

WHAT IT WIRES. search_controller (which action, which branch), lineage_dag (fertility and credit
assignment), agents (the falsifier gate), tri_alignment (hypothesis vs implementation), and
edge_queue (the preregistered mechanisms). Before this file, all five had zero production callers
-- built, tested, and idle, which LAWS III.16 calls a defect rather than a completion.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "data" / "research_loop.json"

#: Trials the fast loop allocates per pass. A recommendation, not a spend -- the sweep reads it.
LOOP_BUDGET = 1000

#: Fixed so consecutive passes are comparable as a time series rather than a fresh opinion.
SEED = 20260829


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _branches_from_funnel() -> list[Any]:
    """Turn the measured funnel into search branches, split EXPLORE / REFINE.

    A family with certificates is REFINE ground; one without is EXPLORE ground. The two
    populations then get separate budgets and never bid against each other -- exploitation wins
    every fair contest, and 20 of 41 certificates in one family is what that collapse looks like.
    """
    from libs.research.funnel_census import build
    from libs.research.search_controller import Branch

    recs = build(ROOT)
    out: list[Branch] = []
    for fam, r in sorted(recs.items()):
        if fam == "__UNATTRIBUTED__" or not r.denominator_known():
            continue
        cand = r.counts.get("candidates", 0)
        cert = r.counts.get("certified", 0)
        # SATURATION IS ATTEMPTS, NOT SUCCESS. `discovered` took 84% of the docket for 0.07%
        # yield; that ground is exhausted regardless of how many certificates it produced.
        saturation = min(1.0, cand / 3000.0)
        out.append(Branch(key=fam, attempts=cand, successes=cert,
                          population="REFINE" if cert > 0 else "EXPLORE",
                          saturation=saturation))
    return out


#: Data this desk genuinely does not have, and the mechanism each one blocks. An EXPLICIT LIST,
#: not a substring test: a first version matched "H1 bars" against "H1 or finer bars with correct
#: session boundaries" -- which the desk HAS -- and reported a data gap worth 0.60 that did not
#: exist. Inferring absence from string overlap manufactures gaps out of phrasing.
_MISSING_DATA: dict[str, str] = {
    "options_implied_volatility": ("gamma environment is measured by a realised-vol PROXY in "
                                   "hedging_demand_close and liquidity_gamma_reversal"),
    "exact_fix_timestamps_per_venue": ("fx_fixing_reversal uses a fixed broker hour rather than "
                                       "the venue's actual fixing window"),
    "cot_tff_positioning_current": ("positioning_extreme conditioning is stale between weekly "
                                    "releases"),
}


def _data_gap_value() -> tuple[float, str]:
    """What a MISSING dataset would be worth, on the same scale as a branch reward.

    ACQUIRE is the action a discovery-maximising search never chooses for itself, and the one
    this desk most needs. Two preregistered mechanisms are measured through a PROXY today, so
    their observed yield understates the mechanism by construction -- and no number of further
    trials against the proxy fixes that.
    """
    have_dir = DESK / "data"
    still_missing = {}
    for key, why in _MISSING_DATA.items():
        # Presence is a FILE question, not a phrasing question.
        if not list(have_dir.rglob(f"*{key.split('_')[0]}*")):
            still_missing[key] = why
    if not still_missing:
        return 0.0, "every preregistered mechanism has real data, not a proxy"
    value = min(0.6, 0.2 * len(still_missing))
    first = next(iter(still_missing.items()))
    return value, (f"{len(still_missing)} dataset(s) absent; e.g. {first[0]} -- {first[1]}. "
                   f"Trials in those regions measure a proxy, and more of them will not fix it.")


def _check_role_discipline() -> list[dict[str, Any]]:
    """Every preregistered mechanism must satisfy the four-role contracts.

    `edge_queue` specs and `agents` contracts were written separately, and nothing checked that a
    spec would actually survive the discipline the roles impose. That gap matters: the roles are
    the standard for what may consume a trial, and a preregistration exempt from them is a
    privileged candidate -- the same defect as a family behind its own door.

    So each spec is reconstructed as a Mechanism and a Hypothesis. `Mechanism.__post_init__`
    refuses unless all seven questions are answered AND an observation is cited;
    `Hypothesis.__post_init__` refuses without falsifiers and without naming the boring
    alternative. A spec that cannot be expressed as both is not ready to be tested.
    """
    from libs.research.agents import Hypothesis, Mechanism, Observation, RoleViolation
    from libs.research.edge_queue import QUEUE

    out: list[dict[str, Any]] = []
    for spec in QUEUE:
        try:
            obs = Observation(text=f"Published finding: {spec.source}", source=spec.source,
                              instruments=spec.universe)
            mech = Mechanism(
                name=spec.coordinate.event,
                who_is_forced=spec.payer,
                why_forced=spec.claim,
                when=spec.coordinate.context,
                what_constraint=spec.constraint,
                who_is_compensated="the counterparty absorbing the constrained flow",
                why_not_arbitraged=("the flow is compelled rather than chosen, so competing it "
                                    "away would require removing the constraint itself"),
                observable_footprint=", ".join(spec.observables[:4]),
                evidence=(obs,))
            Hypothesis(
                hypothesis_id=spec.id, claim=spec.claim, mechanism=mech,
                semantic_coordinate=spec.coordinate.key(), prediction=spec.prediction,
                falsifiers=spec.falsifiers,
                alternative_explanation=spec.alternative_explanation,
                distinguishing_test=spec.distinguishing_test,
                point_in_time_contract="; ".join(spec.data_requirements))
            out.append({"id": spec.id, "verdict": "PASS",
                        "why": f"satisfies all four role contracts; {len(spec.falsifiers)} "
                               f"falsifier(s) declared"})
        except RoleViolation as exc:
            out.append({"id": spec.id, "verdict": "REJECT", "why": str(exc)[:180]})
    return out


def _check_edge_queue_alignment() -> list[dict[str, Any]]:
    """Every preregistered mechanism must be implemented by code that implements IT.

    This is the tri-alignment gate on the four families this desk actually added today. It costs
    milliseconds and it is the only defence against a gamma story passing ten gates on the
    strength of an RSI.
    """
    from libs.research import tri_alignment as ta
    from libs.research.edge_queue import QUEUE

    src_path = DESK / "mt5desk" / "families_edge_queue.py"
    try:
        src = src_path.read_text("utf-8")
    except OSError:
        return [{"id": "ALL", "verdict": "REJECT",
                 "why": f"{src_path} unreadable; an implementation nobody can read is unaligned"}]

    fn_for = {
        "H-2026-0001-HEDGING_DEMAND_CLOSE_FLOW": "family_hedging_demand_close",
        "H-2026-0002-FX_FIXING_REVERSAL": "family_fx_fixing_reversal",
        "H-2026-0003-GOLD_SESSION_HANDOFF": "family_session_handoff",
        "H-2026-0004-LIQUIDITY_GAMMA_REVERSAL": "family_liquidity_gamma_reversal",
    }
    out = []
    for spec in QUEUE:
        fn = fn_for.get(spec.id)
        if not fn or f"def {fn}" not in src:
            out.append({"id": spec.id, "verdict": "REJECT",
                        "why": "preregistered but not implemented; a spec is not a candidate"})
            continue
        start = src.index(f"def {fn}")
        nxt = src.find("\ndef ", start + 1)
        body = src[start:nxt if nxt > 0 else len(src)]
        a = ta.check(hypothesis=spec.claim, mechanism=spec.coordinate.event, code=body,
                     horizon=spec.coordinate.output,
                     coordinate_context=spec.coordinate.claim())
        out.append({"id": spec.id, "function": fn, "verdict": a.verdict,
                    "why": a.reasons[0][:180]})
    return out


def main() -> int:
    from libs.research.search_controller import choose_action, split_budget

    now = datetime.now(tz=UTC)
    print(f"RESEARCH LOOP (fast) {now.isoformat(timespec='seconds')}")
    print("  steers research only -- NO promotion authority; truth stays with the 14-day "
          "forward shadow")

    # ---- 0. ROLE DISCIPLINE on the preregistered mechanisms ---------------------------------
    roles = _check_role_discipline()
    role_bad = [r for r in roles if r["verdict"] != "PASS"]
    print(f"\n  ROLE DISCIPLINE over {len(roles)} preregistered mechanism(s)")
    for r in roles:
        print(f"    {'ok  ' if r['verdict'] == 'PASS' else 'FAIL'} {r['id'][:40]:42s} "
              f"{r['why'][:70]}")

    # ---- 1. TRI-ALIGNMENT on the preregistered mechanisms -----------------------------------
    align = _check_edge_queue_alignment()
    bad = [a for a in align if a["verdict"] != "PASS"]
    print(f"\n  TRI-ALIGNMENT over {len(align)} preregistered mechanism(s)")
    for a in align:
        mark = "ok  " if a["verdict"] == "PASS" else "FAIL"
        print(f"    {mark} {a['id'][:40]:42s} {a.get('function', '')}")
        if a["verdict"] != "PASS":
            print(f"         {a['why'][:120]}")

    # ---- 2. WHERE THE NEXT TRIALS GO --------------------------------------------------------
    branches = _branches_from_funnel()
    gap_value, gap_why = _data_gap_value()
    action, why = choose_action(branches, seed=SEED, data_gap_value=gap_value)
    alloc = split_budget(branches, LOOP_BUDGET, seed=SEED)

    print(f"\n  BRANCHES {len(branches)}  "
          f"(EXPLORE {sum(1 for b in branches if b.population == 'EXPLORE')}, "
          f"REFINE {sum(1 for b in branches if b.population == 'REFINE')})")
    print(f"  ACTION: {action}")
    print(f"    {why[:150]}")
    if gap_value > 0:
        print(f"  DATA GAP value {gap_value:.2f}: {gap_why[:130]}")

    top = sorted(alloc.items(), key=lambda kv: -kv[1])[:8]
    print(f"\n  NEXT {LOOP_BUDGET} TRIALS")
    for k, v in top:
        b = next((x for x in branches if x.key == k), None)
        pop = b.population if b else "?"
        print(f"    {k:26s} {v:5d}  [{pop}]  attempts={b.attempts if b else 0} "
              f"certs={b.successes if b else 0}")
    zeroed = [k for k, v in alloc.items() if v == 0]
    if zeroed:
        print(f"    WARNING: {len(zeroed)} branch(es) allocated zero despite the exploration "
              f"floor -- that is a bug, not a decision: {zeroed[:5]}")

    payload = {
        "ran_at": now.isoformat(timespec="seconds"),
        "authority": "STEERING ONLY -- this loop cannot promote, size or arm anything",
        "role_discipline": roles,
        "tri_alignment": align,
        "action": action, "action_why": why,
        "data_gap_value": gap_value, "data_gap_why": gap_why,
        "allocation": alloc,
        "branches": [{"key": b.key, "population": b.population, "attempts": b.attempts,
                      "successes": b.successes, "saturation": round(b.saturation, 3),
                      "reward": round(b.reward(), 5)} for b in branches],
    }
    OUT.write_text(json.dumps(payload, indent=1, default=str), "utf-8")
    print(f"\n  -> {OUT}")
    # A misaligned preregistered mechanism is a real defect: it means the desk is about to spend
    # gauntlet compute testing something other than the claim it wrote down.
    return 1 if (bad or role_bad) else 0


if __name__ == "__main__":
    raise SystemExit(main())
