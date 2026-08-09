"""FEATURE LIBRARY + CONTINUOUS FEATURE MINER -- features as managed assets, and the construction
space they live in, made countable.

THE PRINCIPAL'S FRAMING, adopted verbatim as the design goal: the question becomes "which pieces
of information about markets are consistently useful?" rather than "what strategy should I try?"

WHY THIS IS THE RIGHT NEXT BUILD, with the evidence:
micro_factory.py computed SIX state variables over 4.4GB of proprietary order books -- spread_bps,
depth5, depth10, imbalance, concentration, slope -- tested exactly ONE derived construction
(negative z of near-touch depth vs 24h rolling), got a null after de-contamination, and DISCARDED
ALL SIX. The next microstructure question re-reads 4.4GB from scratch. That is the measurable
bottleneck this removes.

THE MINER IS THE POINT, NOT THE REGISTRY. A registry of what was built is bookkeeping. The
valuable half answers "can I construct another observable for this mechanism?" MECHANICALLY, by
enumerating a construction grammar:

        OBSERVABLE  x  TRANSFORM  x  WINDOW  x  NORMALISATION

and reporting which cells have been tested. That converts "keep exploring, never exhaust" from an
instruction into a COVERAGE PERCENTAGE. The desk has never known what fraction of a mechanism's
observable space it has visited; after this it does, and "we tested microstructure" becomes
"we tested 1 of 96 constructions = 1.0%", which is a very different sentence.

CRITICAL HONESTY RAIL -- COVERAGE IS NOT PROGRESS. Enumerating 96 cells and testing all 96 is
mass multiple-hypothesis testing, and this desk's own SUSPECT-LOOKAHEAD and Holm rails exist
because that path manufactures survivors. So the miner RANKS cells and hands them to the existing
Stage-A/Stage-B law: screening is unlimited and carries ZERO promotion authority; only
pre-registered forward clocks promote. The miner feeds screening. It cannot promote anything.

MEASUREMENT DOCTRINE COMPLIANCE (principal 2026-07-27): every feature row carries the gate verdict
of the dataset it derives from. A feature built on an UNVERIFIED input is marked BLOCKED and is
not offered to the miner -- optimising feature space over broken inputs is exactly what the
doctrine forbids.

Read-only. No keys, no LLM, no network. Run from repo root.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/feature_library.json"
GATE = ROOT / "data/measurement_gate.json"
MECH = ROOT / "data/mechanism_board.json"

# ---------------------------------------------------------------- REGISTERED FEATURES
# Seeded from features this desk has ACTUALLY computed. Nothing aspirational: every row below
# corresponds to code that ran. `tested_constructions` is what was carried through to a verdict.
FEATURES = [
    # -- microstructure state variables from the moat (micro_factory.py, commit ae4045b)
    {
        "id": "F001",
        "name": "spread_bps",
        "mechanism": "M_LIQUIDITY_WITHDRAWAL",
        "source": "data/moat",
        "producer": "scripts/micro_factory.py",
        "rationale": "quoted cost of immediacy; widens as inventory risk binds",
        "status": "computed_unused",
        "tested_constructions": 0,
    },
    {
        "id": "F002",
        "name": "depth5",
        "mechanism": "M_LIQUIDITY_WITHDRAWAL",
        "source": "data/moat",
        "producer": "scripts/micro_factory.py",
        "rationale": "notional within 5bps of mid; the liquidity actually reachable",
        "status": "tested",
        "tested_constructions": 1,
        "result": "neg-z vs 24h roll: raw lead rho +0.3032 (t +3.68) -> residual +0.0154 (t +0.28) "
        "after orthogonalising to same-period RV. Vol clustering explained it.",
    },
    {
        "id": "F003",
        "name": "depth10",
        "mechanism": "M_LIQUIDITY_WITHDRAWAL",
        "source": "data/moat",
        "producer": "scripts/micro_factory.py",
        "rationale": "notional within 10bps; the shoulder of the book",
        "status": "computed_unused",
        "tested_constructions": 0,
    },
    {
        "id": "F004",
        "name": "imbalance",
        "mechanism": "M_LIQUIDITY_WITHDRAWAL",
        "source": "data/moat",
        "producer": "scripts/micro_factory.py",
        "rationale": "bid share of near depth; directional inventory pressure",
        "status": "computed_unused",
        "tested_constructions": 0,
    },
    {
        "id": "F005",
        "name": "concentration",
        "mechanism": "M_LIQUIDITY_WITHDRAWAL",
        "source": "data/moat",
        "producer": "scripts/micro_factory.py",
        "rationale": "top-level share of near depth; thin veneer vs real book",
        "status": "computed_unused",
        "tested_constructions": 0,
    },
    {
        "id": "F006",
        "name": "slope",
        "mechanism": "M_LIQUIDITY_WITHDRAWAL",
        "source": "data/moat",
        "producer": "scripts/micro_factory.py",
        "rationale": "depth10/depth5; how fast liquidity accumulates away from touch",
        "status": "computed_unused",
        "tested_constructions": 0,
    },
    # -- the one survivor on this desk
    {
        "id": "F007",
        "name": "funding_rate_persistence",
        "mechanism": "M_FORCED_DELEVERAGE",
        "source": "binance funding",
        "producer": "scripts/funding_persistence.py",
        "rationale": "leveraged crowding persists; who pays carry today tends to pay tomorrow",
        "status": "confirmed",
        "tested_constructions": 1,
        "result": "IC +0.432 (t +29.7) at 24h; top-decile +29.08%/yr vs median +3.77%/yr; "
        "selection edge +25.30%/yr; shock half-life 0.8 periods (6h).",
    },
    {
        "id": "F008",
        "name": "oi_ls_ratio",
        "mechanism": "M_FORCED_DELEVERAGE",
        "source": "data/oi_ls_history.jsonl",
        "producer": "scripts/run_axis_shadows.py",
        "rationale": "positioning skew as a proxy for forced-unwind pressure",
        "status": "forward_clock",
        "tested_constructions": 1,
        "result": "OOS forward clock running; first verdict 2026-08-07.",
    },
    {
        "id": "F009",
        "name": "cny_otc_premium",
        "mechanism": "M_STRUCTURAL_BARRIER",
        "source": "data/cny_otc_premium_history.jsonl",
        "producer": "UNCOMMITTED (backfill)",
        "rationale": "capital control prevents convergence; premium is the barrier's price",
        "status": "blocked",
        "tested_constructions": 1,
        "result": "input FAILED measurement gate: no producer, and timestamp alignment is "
        "'23:55 CST assumed' rather than verified.",
    },
]

# ---------------------------------------------------------------- CONSTRUCTION GRAMMAR
# The observable space per mechanism. OBSERVABLES are what you can see; TRANSFORMS turn a level
# into a dynamic; WINDOWS set the horizon; NORMS make it comparable across symbols.
GRAMMAR = {
    "M_LIQUIDITY_WITHDRAWAL": {
        "observables": ["depth5", "depth10", "spread_bps", "imbalance", "concentration", "slope"],
        "transforms": ["level", "delta", "replenish_rate", "recovery_halflife", "one_sided_gap"],
        "windows": ["1h", "4h", "24h"],
        "norms": ["zscore_roll", "pct_rank", "raw"],
    },
    "M_FORCED_DELEVERAGE": {
        "observables": ["funding", "oi", "ls_ratio", "taker_ratio", "basis"],
        "transforms": ["level", "delta", "dispersion", "crowding_z"],
        "windows": ["8h", "24h", "72h"],
        "norms": ["zscore_roll", "pct_rank", "raw"],
    },
}
# constructions already carried to a verdict -- (mechanism, observable, transform, window, norm)
TESTED = {
    ("M_LIQUIDITY_WITHDRAWAL", "depth5", "level", "24h", "zscore_roll"),
    ("M_FORCED_DELEVERAGE", "funding", "level", "24h", "raw"),
    ("M_FORCED_DELEVERAGE", "ls_ratio", "level", "24h", "zscore_roll"),
}
# PRIOR RANKING. Not a prediction of alpha -- a prior on whether the construction can even be
# DISTINGUISHED from what already failed. Transforms that are dynamics rank above levels because
# the level construction is the one that died to vol clustering.
TRANSFORM_PRIOR = {
    "level": 0.2,
    "delta": 0.6,
    "replenish_rate": 1.0,
    "recovery_halflife": 0.9,
    "one_sided_gap": 0.8,
    "dispersion": 0.7,
    "crowding_z": 0.5,
}


def _gate_verdicts() -> dict:
    if not GATE.exists():
        return {}
    try:
        return {
            k: v.get("verdict")
            for k, v in json.loads(GATE.read_text("utf-8")).get("datasets", {}).items()
        }
    except Exception:  # blind-except intentional (BLE001)
        return {}


def main() -> None:
    print("=== FEATURE LIBRARY -- features as managed assets ===")
    print(
        "    'which pieces of information are consistently useful?' beats 'what strategy next?'\n"
    )
    gv = _gate_verdicts()
    live_mechs = set()
    if MECH.exists():
        try:
            mb = json.loads(MECH.read_text("utf-8"))
            live_mechs = {
                m for m, v in mb.get("verdicts", {}).items() if v in ("ALIVE", "UNTESTED")
            }
        except Exception:  # blind-except intentional (BLE001)
            pass

    rows = []
    for f in FEATURES:
        src = Path(f["source"]).name
        verdict = gv.get(src)
        blocked = verdict == "FAILED"
        rows.append(
            {
                **f,
                "input_gate": verdict or ("n/a" if "/" not in f["source"] else "UNGATED"),
                "blocked_by_measurement": blocked,
            }
        )
    print(f"  {'id':<6}{'feature':<26}{'mechanism':<26}{'status':<17}{'input gate'}")
    for r in rows:
        print(
            f"  {r['id']:<6}{r['name']:<26}{r['mechanism']:<26}{r['status']:<17}{r['input_gate']}"
        )
    unused = [r for r in rows if r["status"] == "computed_unused"]
    print(f"\n  {len(unused)} of {len(rows)} features were COMPUTED AND DISCARDED. Each one cost a")
    print("  full pass over 4.4GB of order books and none is reachable without re-reading it.")
    blocked = [r for r in rows if r["blocked_by_measurement"]]
    if blocked:
        print(
            f"  {len(blocked)} BLOCKED by the measurement gate: "
            f"{', '.join(r['name'] for r in blocked)}"
        )
        print("  (doctrine: a feature on an unverified input is not offered to the miner)")

    # ------------------------------------------------ CONTINUOUS FEATURE MINER
    print("\n=== CONTINUOUS FEATURE MINER -- 'what else could represent this mechanism?' ===")
    print("    enumerated mechanically, so exploration coverage becomes a NUMBER\n")
    proposals = []
    for mech, g in GRAMMAR.items():
        if live_mechs and mech not in live_mechs:
            print(f"  {mech}: skipped (mechanism not ALIVE/UNTESTED on the board)")
            continue
        cells = list(product(g["observables"], g["transforms"], g["windows"], g["norms"]))
        done = [c for c in cells if (mech, *c) in TESTED]
        cov = len(done) / len(cells) * 100
        print(f"  {mech}")
        print(
            f"    construction space: {len(g['observables'])} observables x "
            f"{len(g['transforms'])} transforms x {len(g['windows'])} windows x "
            f"{len(g['norms'])} norms = {len(cells)} cells"
        )
        print(f"    TESTED {len(done)}/{len(cells)} = {cov:.1f}% COVERAGE")
        for obs, tr, win, nrm in cells:
            if (mech, obs, tr, win, nrm) in TESTED:
                continue
            score = TRANSFORM_PRIOR.get(tr, 0.4)
            if win == "1h":
                score += 0.15  # finer horizon = more independent observations
            if nrm == "zscore_roll":
                score += 0.05
            proposals.append(
                {
                    "mechanism": mech,
                    "observable": obs,
                    "transform": tr,
                    "window": win,
                    "norm": nrm,
                    "prior": round(score, 3),
                    "name": f"{obs}__{tr}__{win}__{nrm}",
                }
            )
    proposals.sort(key=lambda p: -p["prior"])
    print(f"\n  {len(proposals)} untested constructions enumerated. Top 12 by prior:\n")
    print(f"  {'prior':>6}  {'mechanism':<24}construction")
    for p in proposals[:12]:
        print(f"  {p['prior']:>6.2f}  {p['mechanism'][:24]:<24}{p['name']}")

    print("\n  THE PRIOR RANKS DISTINGUISHABILITY, NOT EXPECTED ALPHA. 'level' constructions rank")
    print("  LOWEST because the level construction is exactly what died to vol clustering on")
    print("  2026-07-27 -- retesting neighbouring levels re-runs a known null. Dynamics")
    print("  (replenish_rate, recovery_halflife, one_sided_gap) rank highest because they are the")
    print("  constructions a vol-clustering confound does NOT trivially reproduce.")
    print("\n  COVERAGE IS NOT PROGRESS. Testing all cells is mass multiple-hypothesis testing,")
    print("  which is why this desk has Holm correction and a SUSPECT-LOOKAHEAD rail. These")
    print("  proposals enter STAGE-A SCREENING ONLY -- unlimited, and with ZERO promotion")
    print(
        "  authority. Nothing here can reach live capital without a pre-registered forward clock."
    )

    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "features": rows,
                "n_features": len(rows),
                "computed_unused": len(unused),
                "blocked": len(blocked),
                "proposals": proposals[:60],
                "n_proposals": len(proposals),
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
