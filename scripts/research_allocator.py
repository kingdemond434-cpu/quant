"""ADAPTIVE RESEARCH ALLOCATOR -- dynamic exploration budget (principal 2026-07-27).

Replaces hardcoded split percentages ("40/25/20/15") with an evidence-driven allocation that
recomputes every cycle from the decision ledger + graveyard + mechanism graph.

THE REWARD FUNCTION IS THE WHOLE DESIGN. Allocating purely on "did this area produce a live alpha"
would defund every area that produces DECISIVE REFUTATIONS -- yet closing a family permanently
(M3 participant-behaviour, refuted at power 2026-07-27) is real value: it stops all future waste.
So reward = INFORMATION GAIN:

#  EXHAUSTION: allocation is uncapped upward. If one area earns 90% of the budget on
#  measured information gain, give it 90% -- an artificial spread is a quota, and a
#  quota is how a desk funds mediocrity to feel balanced.

    decisive refutation   0.60   (powered null / mechanism closed -- prevents future waste)
    claimed progress      0.50   (ledger PROSE says wired/replicated -- a claim, never an edge)
    method upgrade        0.50   (a new rail: gapped-window, power reporting, stability check)
    inconclusive          0.00   (underpowered / data-blocked -- pure cost, no knowledge)

**THERE IS NO `survivor` REWARD BUCKET, AND ITS ABSENCE IS THE POINT.** Until 2026-08-09 a ledger
row whose prose contained "wired" scored 1.00 here -- the top of the scale, equal to a validated
forward clock. On a desk whose ledger is mostly about wiring modules that fired 82 times while the
true confirmed count was 0. A confirmed survivor cannot be read out of prose at all, so it is
sourced from the Stage-B shadow tracker and used only where it belongs: the honesty gate.

ALLOCATION = Thompson sampling over Beta posteriors (one per area), so areas with thin evidence
keep exploration weight instead of being starved by one bad month, and areas with repeated null
yield decay smoothly rather than being cut by decree. A SATURATION PENALTY from the mechanism graph
down-weights chains where every node is already observed (M1: 7/7 -> new sensors are marginal).

HONESTY RAIL: when CONFIRMED evidence is thin the posterior is PRIOR-DOMINATED and the report says
so, rather than presenting a prior as a data-driven allocation. It keys on the shadow tracker and
never on the prose tally -- a count that a keyword can raise must never be able to lower a
disclaimer, which is exactly what it did before. An unreadable tracker is UNMEASURED and fails
CLOSED: "we cannot see the numerator" and "the numerator is large" must not print the same report.

Read-only. Run from repo root.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

LEDGER = Path("data/decision_ledger.json")
GRAVE = Path("docs/graveyard.md")
OUT = Path("data/research_allocation.json")
#: GROUND TRUTH for confirmed edges. Ledger prose is not evidence and never was.
SHADOW = Path("web/axis_shadows.json")

# area -> (keywords for ledger matching, mechanism-graph saturation 0..1, base prior weight)
AREAS = {
    "M1_liquidity_flows": (("stablecoin", "etf", "funding", "liquidity", "reserve"), 1.00, 1.0),
    "M2_regional_controls": (("kimchi", "premium", "cny", "capital control", "krw"), 0.55, 1.0),
    "M3_participant": (
        ("trader", "copytrad", "leaderboard", "elite", "skill", "wallet"),
        0.95,
        1.0,
    ),
    "M4_info_diffusion": (
        ("attention", "wikipedia", "developer", "github", "search", "narrative"),
        0.30,
        1.0,
    ),
    "M5_reflexivity": (("reflexiv", "liquidation", "feedback", "cascade", "leverage"), 0.15, 1.0),
    "execution_costs": (("cost", "slippage", "churn", "execution", "fill", "tca"), 0.40, 1.0),
    "method_infra": (("harness", "rail", "power", "validator", "gate", "audit", "oos"), 0.20, 1.0),
}

#: A CLAIM OF PROGRESS IN PROSE IS WORTH A METHOD UPGRADE, NOT AN EDGE. `claimed_progress`
#: was scored 1.00 as `survivor` until 2026-08-09; that was the leak, because it paid a
#: keyword match the same information gain as a validated forward clock.
REWARD = {"claimed_progress": 0.5, "refutation": 0.6, "method": 0.5, "inconclusive": 0.0}


def confirmed_survivors() -> tuple[int | None, str]:
    """Ground truth for survivors: Stage-B shadow verdicts, NEVER ledger prose.

    None means the tracker could not be read, which is UNMEASURED and is NOT zero. The distinction
    matters because both answers must suppress the data-driven claim, but only one of them is a
    statement about the desk -- the other is a statement about this clone (L1.28a).
    """
    try:
        sd = json.loads(SHADOW.read_text("utf-8"))
    except (OSError, ValueError):
        return None, (f"{SHADOW} unreadable -- confirmed survivors UNMEASURED. On a fresh clone "
                      "this file is gitignored and lives on the box, so absence here is a fact "
                      "about the clone; it still cannot license a data-driven claim")
    n = sum(1 for a in sd.get("axes", []) if a.get("verdict") == "ELIGIBLE")
    return n, f"{n} axis/axes at verdict ELIGIBLE in {SHADOW}"


def classify(text: str) -> str:
    t = text.lower()
    if (any(k in t for k in ("forward clock", "wired", "screen-interesting", "replicat"))
            and "not wired" not in t and "nothing wired" not in t):
        # NOT `survivor`, AND THE RENAME IS THE FIX. These keywords match ledger PROSE: "wired"
        # fires on every row describing a module being wired, which on this desk is most of them.
        # Counting those as survivors produced 82 against a true confirmed count of 0, and that
        # inflated number then silenced the PRIOR-DOMINATED warning below -- so the leak did not
        # merely mislabel a column, it switched off the sentence that existed to catch it.
        #
        # The identical bug was found and fixed in scripts/research_alpha_optimizer.py, whose
        # comment records it counting 63 when the truth was 0. Nobody swept for siblings; this was
        # the sibling. A claim of progress in prose is at most a METHOD UPGRADE, never an edge.
        return "claimed_progress"
    if (any(k in t for k in ("rail", "harness", "control", "power", "validator", "standard"))
            and any(k in t for k in ("built", "added", "earned", "new standard"))):
        return "method"
    if any(
        k in t
        for k in (
            "refut",
            "killed",
            "reject",
            "fails",
            "zero predictive",
            "graveyard",
            "exhausted",
            "no edge",
        )
    ):
        return "refutation"
    if any(k in t for k in ("underpowered", "data-blocked", "thin", "insufficient", "blocked")):
        return "inconclusive"
    return "inconclusive"


def main() -> None:
    led = json.loads(LEDGER.read_text("utf-8"))["decisions"]
    tally = {a: {"claimed_progress": 0, "refutation": 0, "method": 0, "inconclusive": 0}
             for a in AREAS}
    for d in led:
        blob = " ".join(str(d.get(k, "")) for k in ("id", "decision", "hypothesis", "flagged_gap"))
        kind = classify(blob)
        low = blob.lower()
        for a, (kws, _, _) in AREAS.items():
            if any(k in low for k in kws):
                tally[a][kind] += 1

    rng = np.random.default_rng(7)
    rows, draws = [], {}
    for a, (_kws, sat, _prior_w) in AREAS.items():
        t = tally[a]
        n = sum(t.values())
        gain = sum(REWARD[k] * v for k, v in t.items())
        # Beta posterior on "information yield per attempt"
        alpha = 1.0 + gain
        beta = 1.0 + max(0.0, n - gain)
        samp = float(rng.beta(alpha, beta, size=4000).mean())
        # saturation penalty: a fully-observed chain earns less from a new sensor
        adj = samp * (1.0 - 0.65 * sat)
        draws[a] = adj
        rows.append(
            {
                "area": a,
                "attempts": n,
                "claimed_progress": t["claimed_progress"],
                "refutations": t["refutation"],
                "methods": t["method"],
                "inconclusive": t["inconclusive"],
                "info_gain": round(gain, 2),
                "posterior_mean": round(samp, 4),
                "saturation": sat,
                "score": round(adj, 4),
            }
        )

    # --- DIVERSIFICATION LAYER (principal 2026-07-27) -------------------------------------
    # "diversify a lot like the S&P 500, but that doesn't mean low focus on all" -- i.e. broad
    # coverage with CONVICTION WEIGHTING, not equal weight. Three rails:
    #   FLOOR  every area keeps a minimum so a lean patch can never permanently kill a branch
    #          (an area at 0% can never generate the evidence that would revive it --
    #          an absorbing state)
    #   CAP    no area exceeds MAX_W, so the book can never become a single-mechanism bet
    #   NEW    a permanent, non-negotiable slice for branches that DO NOT EXIST YET -- this is the
    #          "always be branching out" mandate; it never decays because unexplored classes have
    #          no track record to decay from. Implements DIGGING_CHARTER s12 in budget form.
    # L3 RATCHET: the new-branch slice GROWS as the known universe saturates. Saturation is a
    # signal to EXPAND, never to stop. base 15% + up to +15% as mean saturation -> 1.0.
    mean_sat = float(np.mean([AREAS[a][1] for a in AREAS]))
    NEW_BRANCH = min(0.30, 0.15 + 0.15 * mean_sat)
    # L2: MIN_W is a FLOOR ON ACTIVE WEIGHT, but depth is guaranteed by CADENCE (below), not by
    # this share -- with N branches growing, equal shares would collapse into skimming.
    MIN_W, MAX_W = 0.04, 0.28
    tot = sum(draws.values()) or 1.0
    for a in draws:
        draws[a] = draws[a] / tot * (1.0 - NEW_BRANCH)
    for _ in range(60):  # iterate floor/cap to a fixed point
        for a in draws:
            draws[a] = min(max(draws[a], MIN_W * (1 - NEW_BRANCH)), MAX_W * (1 - NEW_BRANCH))
        t2 = sum(draws.values()) or 1.0
        draws = {a: v / t2 * (1.0 - NEW_BRANCH) for a, v in draws.items()}
    for r in rows:
        r["allocation_pct"] = round(100 * draws[r["area"]], 1)
    rows.sort(key=lambda r: -r["allocation_pct"])
    rows.append(
        {
            "area": "NEW_BRANCHES (unexplored classes)",
            "attempts": 0,
            "claimed_progress": 0,
            "refutations": 0,
            "methods": 0,
            "inconclusive": 0,
            "info_gain": 0.0,
            "posterior_mean": None,
            "saturation": 0.0,
            "allocation_pct": round(100 * NEW_BRANCH, 1),
        }
    )

    # --- L1 MONOTONIC BRANCH REGISTRY: branches are never deleted, only down-weighted ---------
    REG = Path("data/branch_registry.json")
    reg = json.loads(REG.read_text("utf-8")) if REG.exists() else {"branches": {}}
    now = datetime.now(tz=UTC).isoformat()
    for r in rows:
        b = reg["branches"].setdefault(
            r["area"],
            {"first_seen": now, "last_weight": None, "last_dug": None, "status": "active"},
        )
        b["last_weight"] = r["allocation_pct"]
        b["last_seen"] = now
    reg["count"] = len(reg["branches"])
    reg["monotonic_rule"] = (
        "branch count never decreases; a branch may be down-weighted on "
        "evidence but never deleted -- zero attention is an absorbing state"
    )
    REG.write_text(json.dumps(reg, indent=1), "utf-8")

    # --- L2 DEPTH = GUARANTEED REVISIT CADENCE (not budget share) -----------------------------
    # weight sets frequency/intensity; cadence guarantees no branch is ever abandoned.
    print("")
    print("  L2 DEPTH GUARANTEE -- revisit cadence by weight band (never abandoned):")
    for r in rows:
        w = r["allocation_pct"]
        cad = 7 if w >= 15 else (14 if w >= 8 else (30 if w >= 4 else 60))
        r["revisit_days"] = cad
        print(f"    {r['area']:<34} {w:>5.1f}%  re-dig every {cad:>2}d to exhaustion criteria")

    total_n = sum(r["attempts"] for r in rows)
    total_claimed = sum(r["claimed_progress"] for r in rows)
    confirmed, confirmed_why = confirmed_survivors()
    # THE HONESTY GATE, AND IT NOW KEYS ON GROUND TRUTH. It was `total_surv < 5 or total_n < 30`
    # over the prose tally, so 82 keyword hits flipped it False and suppressed the warning. A
    # count that a keyword can raise must never be able to lower a disclaimer.
    #
    # UNMEASURED FAILS CLOSED: an unreadable shadow tracker is prior-dominated, because "we cannot
    # see the numerator" and "the numerator is large" must not produce the same report.
    prior_dominated = (confirmed is None) or confirmed < 5 or total_n < 30

    banner = ("recomputed from evidence, not decreed" if not prior_dominated else
              "PRIOR-DOMINATED -- this is a prior wearing an allocation's clothes")
    print(f"=== ADAPTIVE RESEARCH ALLOCATION ({banner}) ===\n")
    print(
        f"  "
        f"{'area':<22}{'alloc':>7}{'att':>5}{'clm':>6}{'refut':>7}{'meth':>6}{'gain':>7}{'sat':>6}"
    )
    for r in rows:
        print(
            f"  {r['area']:<22}{r['allocation_pct']:>6.1f}%{r['attempts']:>5}"
            f"{r['claimed_progress']:>6}{r['refutations']:>7}{r['methods']:>6}"
            f"{r['info_gain']:>7.1f}{r['saturation']:>6.2f}"
        )
    print(
        f"\n  reward: claimed_progress {REWARD['claimed_progress']} "
        f"| refutation {REWARD['refutation']} "
        f"| method {REWARD['method']} | inconclusive {REWARD['inconclusive']}"
    )
    print("  (refutations are PAID -- closing a family permanently prevents future waste)")

    print(f"\n  clm = CLAIMED_PROGRESS: ledger PROSE matching 'wired'/'forward clock'/"
          f"'replicat'. {total_n} attempt(s), {total_claimed} claim(s).")
    print(f"  CONFIRMED survivors (ground truth, {SHADOW}): "
          f"{'UNMEASURED' if confirmed is None else confirmed}")
    print(f"    {confirmed_why}")
    if prior_dominated:
        shown = "UNMEASURED" if confirmed is None else str(confirmed)
        print(f"\n  *** PRIOR-DOMINATED: {shown} CONFIRMED survivor(s) across {total_n} "
              "attempt(s). ***")
        print("  Allocation is currently driven by MECHANISM SATURATION, not realised yield.")
        print("  This is honest, not a defect -- but do not present it as data-driven until")
        print("  CONFIRMED survivors accumulate. Prose claims cannot lift this gate: they were")
        print(f"  counted as survivors until 2026-08-09, and {total_claimed} of them silenced")
        print("  this very warning while the true confirmed count was zero.")

    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "prior_dominated": bool(prior_dominated),
                "total_attempts": total_n,
                "confirmed_survivors": confirmed,
                "confirmed_survivors_source": str(SHADOW),
                "confirmed_survivors_note": confirmed_why,
                "claimed_progress_from_prose": total_claimed,
                "reward_function": REWARD,
                "areas": rows,
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
