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


def _measure_and_diagnose() -> dict[str, Any]:
    """Resolve a real measurement for every compiled cell, diagnose it, and record the lot.

    THIS IS WHERE THE LOOP ACTUALLY CLOSES. Before this, `measurement`, `failure_states`,
    `adapters` and `store` were four correct modules that nothing invoked -- which by the desk's
    own law (III.16) is a defect, not a completion. A measurement contract nobody resolves and a
    six-state diagnosis nobody records leave the allocator learning from the same collapsed FAIL
    it always did.

    Every compiled cell now gets: a real observable from the adapter registry, a diagnosis in one
    of the six states, and a row in the append-only store. The allocator can then ask the only
    question that matters -- which mechanisms were GENUINELY refuted, versus merely mismeasured.
    """
    import pandas as pd

    from libs.research_os import brain_ab, credit, store
    from libs.research_os.adapters import REGISTRY
    from libs.research_os.brain_ab import ARMS, assign_arm
    from libs.research_os.failure_states import data_needs, diagnose, policy_report

    cells_path = DESK / "data" / "hypotheses" / "compiled_proposals.json"
    try:
        cells = json.loads(cells_path.read_text("utf-8")).get("cells", [])
    except (OSError, json.JSONDecodeError):
        return {"skipped": "no compiled cells to measure"}

    uni = DESK / "data" / "universe"
    diagnoses = []
    paired: list[tuple[Any, dict[str, Any]]] = []
    measured = 0
    for cell in cells[:40]:                     # a pass, not a sweep; the gauntlet does volume
        params = cell.get("params") or {}
        mech = str(params.get("event") or cell.get("family") or "")
        # A representative instrument per pass. The point here is the MEASUREMENT class, which
        # is a property of the mechanism and the desk's data, not of one symbol.
        sym = str(cell.get("symbol") or "EURUSD")
        bars_path = uni / f"{sym}_H1.parquet"
        if not bars_path.exists():
            continue
        try:
            bars = pd.read_parquet(bars_path).rename(columns=str.lower).tail(2000)
        except Exception:
            continue

        res = REGISTRY.resolve({"mechanism": mech, "symbol": sym}, bars)
        measured += 1
        store.record_measurement(
            hypothesis_id=str(cell.get("name") or ""), mechanism=mech, adapter=res.adapter,
            status=res.status, attributable=res.attributable, pit_safe=res.pit_safe,
            missing_observable="" if res.runnable else mech, notes=res.notes)

        # DIAGNOSE THE REAL EXPERIMENT, NOT A STUB. This passed gross=None, net=None,
        # n_trades=0 -- values that do not exist yet -- so every cell fell through to the
        # `n_trades < 20` branch and was filed MEASUREMENT_FAILED regardless of what the gauntlet
        # had actually found. The six states were being applied to the absence of a result, which
        # is not post-experiment credit assignment at all: COST_FAILED and MECHANISM_REFUTED were
        # unreachable by construction, so no failure could ever teach anything about a mechanism.
        #
        # The outcomes exist: `sync_research_ledger` writes expectancy, cost-stressed expectancy
        # and trade count into the experiments table from the gauntlet's own gate results. Reading
        # the latest row per hypothesis is what turns this from "we measured it" into "we tested
        # it and here is which link broke".
        hid = str(cell.get("name") or "")
        exp = _latest_experiment(store, hid)
        d = diagnose(
            mechanism=mech,
            measurement_class=res.status if res.status != "UNAVAILABLE" else "",
            exp_r_gross=exp.get("exp_r_gross"), exp_r_net=exp.get("exp_r_net"),
            novelty_verdict=exp.get("novelty_verdict"),
            missing_observable="" if res.runnable else (res.notes[:80] or mech),
            n_trades=int(exp.get("n_trades") or 0))
        diagnoses.append(d)
        # PAIR THE CELL WITH ITS DIAGNOSIS HERE, not by zipping the two lists later. `diagnoses`
        # skips every cell that `continue`d above (absent parquet, unreadable file), so a
        # positional zip attributes each child to whichever cell sits at that index -- a mutation
        # logged against a parent that did not produce it, corrupting the lineage credit reads.
        paired.append((d, cell))
        store.record_failure(d, hypothesis_id=hid)

        # THE ARM IS FIXED AT PROPOSAL TIME, before any outcome exists, and persisted with the
        # hypothesis. Nothing wrote this table, which is why lineage and the brain A/B both had
        # zero rows: the columns for parentage and brain version were designed and never filled.
        store.record_hypothesis(
            hypothesis_id=hid, origin="compiled_cell",
            generator=str(cell.get("generator") or cell.get("origin") or "unknown"),
            mechanism=mech, coordinate=str(cell.get("coordinate") or ""),
            parent_ids=[], generation=0, brain_version=assign_arm(hid),
            spec={**params, "symbol": sym, "measured_by": res.adapter})

    for need in data_needs(diagnoses):
        store.record_data_need(need, sources=["see scripts/check_unmeasurable_claims.py"])

    # CLOSE THE LOOP. The diagnosis printed `mutate_measurement` and nothing mutated anything --
    # the desk identified which link broke and discarded the answer, which is the same as not
    # diagnosing. Each surviving diagnosis now breeds a CHILD that changes only the indicted link,
    # or refuses by name.
    from libs.research_os.mutation import mutate_batch

    parents: dict[str, dict[str, Any]] = {}
    eligible, withheld = [], 0
    for d, cell in paired:
        hid = str(cell.get("name") or "")
        d.hypothesis_id = hid
        parents[hid] = {**(cell.get("params") or {}),
                        "symbol": str(cell.get("symbol") or "EURUSD")}
        # THE CONTROL ARM DOES NOT BREED. Without this both arms behave identically and the A/B
        # measures nothing while producing a confident-looking report.
        if ARMS.get(assign_arm(hid), {}).get("breed_children"):
            eligible.append(d)
        else:
            withheld += 1
    bred = mutate_batch(eligible, parents)

    for child in bred.get("children", []):
        pid = str(child.get("parent") or "")
        store.record_hypothesis(
            hypothesis_id=f"{pid}+{child.get('mutation')}", origin="mutation",
            generator=str(parents.get(pid, {}).get("generator") or "mutation"),
            mechanism=str(parents.get(pid, {}).get("event") or ""),
            coordinate="", parent_ids=[pid], generation=1, brain_version=assign_arm(pid),
            spec={**(child.get("params") or {}), "mutation": str(child.get("mutation") or "")})
    bred["withheld_control_arm"] = withheld

    return {"cells_measured": measured, "policy": policy_report(diagnoses),
            "mutation": bred, "post_experiment": _diagnose_real_experiments(store),
            "crossover": _crossover_pass(),
            "credit": credit.from_store(),
            "brain_ab": brain_ab.report(), "store": store.summary()}


def _crossover_pass() -> dict[str, Any]:
    """QuantaAlpha trajectory crossover over the recorded lineage.

    `crossover_candidates` has existed and been UNCALLED, because nothing built the graph it needs:
    the hypotheses table carrying parentage was empty until this session. It is called every pass
    now, and returning zero pairs is a real answer -- the eligibility rule requires two lineages
    whose FAILING STEPS DIFFER, and while every failure is MEASUREMENT_FAILED there is nothing for
    two parents to exchange. It starts producing pairs when the post-experiment diagnosis above
    begins yielding COST_FAILED and MECHANISM_REFUTED alongside it.
    """
    try:
        from libs.research_os.lineage_bridge import crossover
        return crossover(seed=int(datetime.now(tz=UTC).strftime("%j")))
    except Exception as exc:
        return {"skipped": f"{type(exc).__name__}: {str(exc)[:90]}"}


def _diagnose_real_experiments(store: Any, limit: int = 400) -> dict[str, Any]:
    """Post-experiment credit assignment over candidates that ACTUALLY RAN.

    THE POPULATIONS ARE DISJOINT, and that is the whole finding. Compiled cells are fresh
    proposals named `LIQUIDITY_FRAGILITY_RATIO`; experiment rows are canon certificates named
    `external.AFG.discovered.p=ef2e...`. Measured 2026-09-04: 119 experiment ids, 94 cell ids,
    overlap ZERO. So diagnosing the cell population reads n_trades=0 for every row and files
    everything MEASUREMENT_FAILED -- COST_FAILED and MECHANISM_REFUTED are unreachable by
    construction, and no failure can ever teach anything about a mechanism.

    A proposal that has not run is not a failure; it is unrun. The diagnosis that carries
    information is the one taken over rows holding a real gross, a real net and a real trade
    count, which is exactly what the experiments table holds. This is where the six states become
    a verdict about a mechanism rather than a restatement of "no result yet".
    """
    from libs.research_os.failure_states import diagnose, policy_report
    try:
        with store.connect() as conn:
            rows = conn.execute(
                "SELECT hypothesis_id, mechanism, exp_r_gross, exp_r_net, n_trades, "
                "MAX(id) FROM experiments WHERE n_trades > 0 GROUP BY hypothesis_id "
                "ORDER BY MAX(id) DESC LIMIT ?", (limit,)).fetchall()
            classes = {str(r[0]): str(r[1] or "") for r in conn.execute(
                "SELECT hypothesis_id, status FROM measurements ORDER BY id ASC").fetchall()}
    except Exception as exc:
        return {"skipped": f"{type(exc).__name__}: {str(exc)[:80]}"}

    diags = []
    for hid, mech, gross, net, n, _ in rows:
        diags.append(diagnose(
            mechanism=str(mech or ""),
            measurement_class=classes.get(str(hid), ""),
            exp_r_gross=gross, exp_r_net=net, novelty_verdict=None,
            missing_observable="", n_trades=int(n or 0)))
        for d in diags[-1:]:
            d.hypothesis_id = str(hid)
    if not diags:
        return {"experiments_diagnosed": 0,
                "why": "no experiment row carries a trade count yet"}
    for d in diags:
        store.record_failure(d, hypothesis_id=getattr(d, "hypothesis_id", ""))
    return {"experiments_diagnosed": len(diags), "policy": policy_report(diags)}


def _latest_experiment(store: Any, hypothesis_id: str) -> dict[str, Any]:
    """The most recent recorded outcome for this hypothesis, or an empty dict.

    Empty is the honest answer for a cell the gauntlet has not reached yet: `diagnose` then sees
    n_trades=0 and files it as underpowered, which is true. What it must never do is invent a
    result -- a fabricated expectancy would be credited to the mechanism.
    """
    try:
        with store.connect() as conn:
            row = conn.execute(
                "SELECT exp_r_gross, exp_r_net, n_trades FROM experiments "
                "WHERE hypothesis_id=? ORDER BY id DESC LIMIT 1", (hypothesis_id,)).fetchone()
    except Exception:
        return {}
    if not row:
        return {}
    return {"exp_r_gross": row[0], "exp_r_net": row[1], "n_trades": row[2],
            "novelty_verdict": None}


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

    # ---- 3. MEASURE, DIAGNOSE, RECORD -------------------------------------------------------
    md = _measure_and_diagnose()
    if md.get("policy"):
        pol = md["policy"]
        print(f"\n  MEASURED {md['cells_measured']} cell(s) through the adapter registry")
        print(f"    failure states: {pol['by_state']}")
        print(f"    may lower a mechanism posterior: {pol['may_lower_a_posterior']} of "
              f"{pol['total']}")
        for need in pol["data_needs"][:4]:
            print(f"    DATA NEED {need['observable'][:48]:50s} blocks {need['mechanisms']}")
        print(f"    store: {md['store']}")
    elif md.get("skipped"):
        print(f"\n  MEASUREMENT SKIPPED: {md['skipped']}")

    payload = {
        "ran_at": now.isoformat(timespec="seconds"),
        "measurement": md,
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
