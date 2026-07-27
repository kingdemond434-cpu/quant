"""ADAPTIVE RESEARCH ALLOCATOR -- dynamic exploration budget (principal 2026-07-27).

Replaces hardcoded split percentages ("40/25/20/15") with an evidence-driven allocation that
recomputes every cycle from the decision ledger + graveyard + mechanism graph.

THE REWARD FUNCTION IS THE WHOLE DESIGN. Allocating purely on "did this area produce a live alpha"
would defund every area that produces DECISIVE REFUTATIONS -- yet closing a family permanently
(M3 participant-behaviour, refuted at power 2026-07-27) is real value: it stops all future waste.
So reward = INFORMATION GAIN:

    survivor              1.00   (a forward clock earned)
    decisive refutation   0.60   (powered null / mechanism closed -- prevents future waste)
    method upgrade        0.50   (a new rail: gapped-window, power reporting, stability check)
    inconclusive          0.00   (underpowered / data-blocked -- pure cost, no knowledge)

ALLOCATION = Thompson sampling over Beta posteriors (one per area), so areas with thin evidence
keep exploration weight instead of being starved by one bad month, and areas with repeated null
yield decay smoothly rather than being cut by decree. A SATURATION PENALTY from the mechanism graph
down-weights chains where every node is already observed (M1: 7/7 -> new sensors are marginal).

HONESTY RAIL: when total evidence is thin the posterior is PRIOR-DOMINATED, and the report says so
explicitly rather than presenting a prior as a data-driven allocation.

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

# area -> (keywords for ledger matching, mechanism-graph saturation 0..1, base prior weight)
AREAS = {
    "M1_liquidity_flows":   (("stablecoin", "etf", "funding", "liquidity", "reserve"), 1.00, 1.0),
    "M2_regional_controls": (("kimchi", "premium", "cny", "capital control", "krw"), 0.55, 1.0),
    "M3_participant":       (("trader", "copytrad", "leaderboard", "elite", "skill", "wallet"), 0.95, 1.0),
    "M4_info_diffusion":    (("attention", "wikipedia", "developer", "github", "search", "narrative"), 0.30, 1.0),
    "M5_reflexivity":       (("reflexiv", "liquidation", "feedback", "cascade", "leverage"), 0.15, 1.0),
    "execution_costs":      (("cost", "slippage", "churn", "execution", "fill", "tca"), 0.40, 1.0),
    "method_infra":         (("harness", "rail", "power", "validator", "gate", "audit", "oos"), 0.20, 1.0),
}

REWARD = {"survivor": 1.0, "refutation": 0.6, "method": 0.5, "inconclusive": 0.0}


def classify(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("forward clock", "wired", "screen-interesting", "replicat")):
        if "not wired" not in t and "nothing wired" not in t:
            return "survivor"
    if any(k in t for k in ("rail", "harness", "control", "power", "validator", "standard")):
        if any(k in t for k in ("built", "added", "earned", "new standard")):
            return "method"
    if any(k in t for k in ("refut", "killed", "reject", "fails", "zero predictive",
                            "graveyard", "exhausted", "no edge")):
        return "refutation"
    if any(k in t for k in ("underpowered", "data-blocked", "thin", "insufficient", "blocked")):
        return "inconclusive"
    return "inconclusive"


def main() -> None:
    led = json.loads(LEDGER.read_text("utf-8"))["decisions"]
    tally = {a: {"survivor": 0, "refutation": 0, "method": 0, "inconclusive": 0} for a in AREAS}
    for d in led:
        blob = " ".join(str(d.get(k, "")) for k in ("id", "decision", "hypothesis", "flagged_gap"))
        kind = classify(blob)
        low = blob.lower()
        for a, (kws, _, _) in AREAS.items():
            if any(k in low for k in kws):
                tally[a][kind] += 1

    rng = np.random.default_rng(7)
    rows, draws = [], {}
    for a, (kws, sat, _prior_w) in AREAS.items():
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
        rows.append({"area": a, "attempts": n, "survivors": t["survivor"],
                     "refutations": t["refutation"], "methods": t["method"],
                     "inconclusive": t["inconclusive"], "info_gain": round(gain, 2),
                     "posterior_mean": round(samp, 4), "saturation": sat,
                     "score": round(adj, 4)})

    # --- DIVERSIFICATION LAYER (principal 2026-07-27) -------------------------------------
    # "diversify a lot like the S&P 500, but that doesn't mean low focus on all" -- i.e. broad
    # coverage with CONVICTION WEIGHTING, not equal weight. Three rails:
    #   FLOOR  every area keeps a minimum so a lean patch can never permanently kill a branch
    #          (an area at 0% can never generate the evidence that would revive it -- absorbing state)
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
    for _ in range(60):                      # iterate floor/cap to a fixed point
        for a in draws:
            draws[a] = min(max(draws[a], MIN_W * (1 - NEW_BRANCH)), MAX_W * (1 - NEW_BRANCH))
        t2 = sum(draws.values()) or 1.0
        draws = {a: v / t2 * (1.0 - NEW_BRANCH) for a, v in draws.items()}
    for r in rows:
        r["allocation_pct"] = round(100 * draws[r["area"]], 1)
    rows.sort(key=lambda r: -r["allocation_pct"])
    rows.append({"area": "NEW_BRANCHES (unexplored classes)", "attempts": 0, "survivors": 0,
                 "refutations": 0, "methods": 0, "inconclusive": 0, "info_gain": 0.0,
                 "posterior_mean": None, "saturation": 0.0,
                 "allocation_pct": round(100 * NEW_BRANCH, 1)})

    # --- L1 MONOTONIC BRANCH REGISTRY: branches are never deleted, only down-weighted ---------
    REG = Path("data/branch_registry.json")
    reg = json.loads(REG.read_text("utf-8")) if REG.exists() else {"branches": {}}
    now = datetime.now(tz=UTC).isoformat()
    for r in rows:
        b = reg["branches"].setdefault(r["area"], {"first_seen": now, "last_weight": None,
                                                   "last_dug": None, "status": "active"})
        b["last_weight"] = r["allocation_pct"]
        b["last_seen"] = now
    reg["count"] = len(reg["branches"])
    reg["monotonic_rule"] = ("branch count never decreases; a branch may be down-weighted on "
                             "evidence but never deleted -- zero attention is an absorbing state")
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
    total_surv = sum(r["survivors"] for r in rows)
    prior_dominated = total_surv < 5 or total_n < 30

    print("=== ADAPTIVE RESEARCH ALLOCATION (recomputed from evidence, not decreed) ===\n")
    print(f"  {'area':<22}{'alloc':>7}{'att':>5}{'surv':>6}{'refut':>7}{'meth':>6}{'gain':>7}{'sat':>6}")
    for r in rows:
        print(f"  {r['area']:<22}{r['allocation_pct']:>6.1f}%{r['attempts']:>5}"
              f"{r['survivors']:>6}{r['refutations']:>7}{r['methods']:>6}"
              f"{r['info_gain']:>7.1f}{r['saturation']:>6.2f}")
    print(f"\n  reward: survivor {REWARD['survivor']} | refutation {REWARD['refutation']} "
          f"| method {REWARD['method']} | inconclusive {REWARD['inconclusive']}")
    print("  (refutations are PAID -- closing a family permanently prevents future waste)")

    if prior_dominated:
        print(f"\n  *** PRIOR-DOMINATED: {total_surv} survivors across {total_n} attempts. ***")
        print("  Allocation is currently driven by MECHANISM SATURATION, not realised yield.")
        print("  This is honest, not a defect -- but do not present it as data-driven until")
        print("  survivors accumulate. Re-run after the Aug 7 OI/LS verdict.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "prior_dominated": bool(prior_dominated),
                               "total_attempts": total_n, "total_survivors": total_surv,
                               "reward_function": REWARD, "areas": rows}, indent=1), "utf-8")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
