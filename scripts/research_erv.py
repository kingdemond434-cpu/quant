"""EXPECTED RESEARCH VALUE -- score hypotheses BEFORE testing, so conversion rises instead of \
supply.

THE INSIGHT THIS IMPLEMENTS (principal, 2026-07-27): the desk does not have an idea shortage. It
has a CONVERSION problem. ~28 hypotheses tested today, ONE survived. Adding generators raises
supply against a fixed confirmation budget; what actually helps is testing the RIGHT ones first.

    ERV = P(edge) x information_gain x moat_advantage x future_unlocks / experiment_cost

FOUR SCORERS, each grounded in something this desk MEASURED rather than assumed:

1. ARCHAEOLOGY (the biggest fix). The hypothesis_generator dedups on TOKENS, which is too weak:
   "Twitter sentiment predicts returns" and "social attention predicts momentum" share almost no
   tokens and are the SAME dead idea. This maps text to CONCEPT FAMILIES (attention, developer,
   whale, funding, premium, flow, spread, microstructure...) and matches at concept level against
   the graveyard. A hypothesis whose concept family is dead scores ~0 regardless of wording.

2. MOAT ADVANTAGE. Public data (GitHub/TVL/Twitter/Wikipedia/Trends) carries a PROCESSING
   advantage anyone can replicate. data/moat -- 4.4GB of recorded order books, 30 symbols x
   spot/fut -- is an INFORMATION advantage nobody else has. Weighted accordingly: today proved
   public-data hypotheses die at ~27/28.

3. MECHANISM DEPTH. Every survivor on this desk has been a SPREAD with a HARD constraint (kimchi:
   capital controls; carry: funding structure). Every FORECAST died. So forced-flow and
   hard-barrier mechanisms score above correlational ones -- this is a measured prior, not taste.

4. EXPERIMENT COST. Cheap falsifiable tests outrank expensive ones at equal promise, because the
   binding constraint is confirmation budget, not compute.

Read-only. No LLM, no keys. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GRAVE = ROOT / "docs/graveyard.md"
QUEUE = ROOT / "data/hypothesis_queue.jsonl"
OUT = ROOT / "data/research_erv.json"

# concept families -- the archaeologist's vocabulary. Matching happens HERE, not on raw tokens.
CONCEPTS = {
    "attention": ("attention", "sentiment", "social", "twitter", "wikipedia", "search",
                  "narrative", "mention", "trend", "hype", "buzz", "interest", "pageview"),
    "developer": ("developer", "github", "commit", "contributor", "repo", "code", "maintainer",
                  "release", "dev activity", "talent"),
    "trader_skill": ("trader", "copytrad", "leaderboard", "elite", "skill", "whale", "smart money",
                     "persistence", "follower"),
    "premium_regional": ("premium", "kimchi", "regional", "korea", "china", "arbitrage venue",
                         "cross-venue", "peg", "depeg"),
    "funding_position": ("funding", "open interest", "positioning", "crowding", "long short",
                         "liquidation", "basis", "carry", "perp"),
    "onchain_flow": ("on-chain", "onchain", "wallet", "exchange flow", "netflow", "stablecoin",
                     "tvl", "bridge", "address", "supply"),
    "microstructure": ("order book", "orderbook", "depth", "spread", "liquidity", "imbalance",
                       "market maker", "slippage", "replenish", "fragility", "microstructure"),
    "reflexivity": ("reflexiv", "feedback", "cascade", "leverage cycle", "credit cycle"),
}

# concept -> (verdict, why) from THIS desk's measured history
HISTORY = {
    "attention": (
        "DEAD", "level AND acceleration tested across 15 horizons, 5 languages; all dead"),
    "developer": (
        "MOSTLY DEAD", "commit velocity CS-IC ~0 at 1/3/6mo; retention n=10 underpowered"),
    "trader_skill": ("DEAD", "5 mechanisms, ~50k traders, gapped persistence rho -0.064"),
    "premium_regional": ("PARTLY ALIVE", "kimchi/cny live; JP/BR/TR/pegs/LSD all died on WIDTH"),
    "funding_position": ("ALIVE", "funding persistence IC +0.432; ls_contrarian on clock to Aug 7"),
    "onchain_flow": ("MOSTLY DEAD", "usage metrics dead; stablecoin supply weak-but-live"),
    "microstructure": ("UNTESTED", "4.4GB recorded moat, needs book reconstruction -- OPEN"),
    "reflexivity": ("INCONCLUSIVE", "M5 underpowered, OI history capped at 500 bars"),
}

MOAT_TERMS = ("order book", "orderbook", "depth", "book imbalance", "replenish", "moat",
              "recorded", "l2", "microstructure", "slippage", "market maker inventory")
PUBLIC_TERMS = ("github", "twitter", "wikipedia", "google trends", "tvl", "defillama",
                "social", "reddit", "search volume")
HARD_MECH = ("capital control", "licence", "license", "regulat", "settlement", "collateral",
             "margin call", "forced", "liquidation", "redemption", "queue", "mandate",
             "cannot", "barrier", "segmentat")


def concepts_of(text: str) -> set[str]:
    t = text.lower()
    return {c for c, kws in CONCEPTS.items() if any(k in t for k in kws)}


def score(h: dict[str, Any]) -> dict[str, Any]:
    blob = " ".join(str(h.get(k, "")) for k in ("name", "mechanism", "data", "test"))
    t = blob.lower()
    cs = concepts_of(blob)

    # 1. archaeology -- concept-level, not token-level
    verdicts = [HISTORY.get(c, ("UNKNOWN", ""))[0] for c in cs]
    if "DEAD" in verdicts:
        arch, arch_why = 0.05, (
            f"concept already DEAD here: {[c for c in cs if HISTORY.get(c,('',''))[0]=='DEAD']}")
    elif "MOSTLY DEAD" in verdicts:
        arch, arch_why = 0.3, "concept mostly refuted; needs a materially new construction"
    elif "INCONCLUSIVE" in verdicts or "PARTLY ALIVE" in verdicts:
        arch, arch_why = 0.8, "concept partially explored, room remains"
    elif "UNTESTED" in verdicts:
        arch, arch_why = 1.0, "concept UNTESTED on this desk"
    else:
        arch, arch_why = 0.9, "no concept match -- genuinely novel or unclassified"

    # 2. moat advantage
    if any(m in t for m in MOAT_TERMS):
        moat, moat_why = 1.0, "uses the recorded order-book moat (information advantage)"
    elif any(p in t for p in PUBLIC_TERMS):
        moat, moat_why = 0.35, "public data -- processing advantage only, replicable by anyone"
    else:
        moat, moat_why = 0.6, "mixed/unclear data provenance"

    # 3. mechanism depth -- spreads and forced flows beat forecasts (measured prior)
    mech = 1.0 if any(m in t for m in HARD_MECH) else (0.6 if "spread" in t else 0.35)
    mech_why = ("hard constraint / forced flow named" if mech == 1.0
                else "spread construction" if mech == 0.6
                else "correlational -- forecasts died here")

    # 4. cost -- cheap falsifiable tests first
    cost = 1.0
    if any(k in t for k in ("reconstruct", "clustering", "neural", "graph", "panel of")):
        cost = 0.5
    if not h.get("kill"):
        cost *= 0.7                              # no kill condition = not properly falsifiable

    erv = arch * moat * mech * cost
    return {"erv": round(erv, 4), "archaeology": arch, "moat": moat, "mechanism": mech,
            "cost": cost, "concepts": sorted(cs),
            "why": f"{arch_why}; {moat_why}; {mech_why}"}


def main() -> None:
    rows = []
    if QUEUE.exists():
        for ln in QUEUE.read_text("utf-8").splitlines():
            if ln.strip():
                try:
                    rows.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    print("=== EXPECTED RESEARCH VALUE -- prioritise BEFORE testing ===")
    print("    the desk has an idea SURPLUS and a conversion deficit; this ranks the queue\n")
    print("  concept-family status on this desk (measured, not assumed):")
    for c, (v, why) in HISTORY.items():
        print(f"    {c:<18} {v:<14} {why}")

    if not rows:
        print("\n  hypothesis queue is EMPTY (hypothesis_generator has never run -- 402).")
        print("  Demonstrating the scorer on the principal's own recent slate instead:\n")
        rows = [
            {"name": "Attention efficiency ratio", "mechanism": "return per unit social attention",
             "data": "google trends + wikipedia", "test": "cross-sectional IC", "kill": "IC<0.03"},
            {"name": "Developer retention momentum",
             "mechanism": "contributors staying predicts growth",
             "data": "github contributors", "test": "rank vs fwd relative return", "kill": "t<2"},
            {"name": "Market maker inventory stress",
             "mechanism": "MMs FORCED to withdraw depth when inventory risk binds",
             "data": "recorded order book depth (moat)", "test": "depth withdrawal vs fwd RV",
             "kill": "no vol expansion"},
            {"name": "Liquidity fragility score",
             "mechanism": "depth collapse under stress cannot be replenished -- forced flow",
             "data": "recorded order book (moat)", "test": "depth decay vs realised vol",
             "kill": "ratio<1.2"},
            {"name": "Bridge flow predicts rotation", "mechanism": "capital migrates before repricing",
             "data": "defillama bridges", "test": "flow vs fwd relative return", "kill": "t<2"},
        ]

    scored = sorted(((h, score(h)) for h in rows), key=lambda x: -x[1]["erv"])
    print(f"  {'ERV':>6}  {'arch':>5} {'moat':>5} {'mech':>5} {'cost':>5}  hypothesis")
    for h, s in scored[:20]:
        print(f"  {s['erv']:>6.3f}  {s['archaeology']:>5.2f} {s['moat']:>5.2f} "
              f"{s['mechanism']:>5.2f} {s['cost']:>5.2f}  {h['name'][:52]}")
        print(f"          {s['why'][:110]}")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "n": len(scored),
                               "ranked": [{"name": h["name"], **s} for h, s in scored]},
                              indent=1), "utf-8")
    print(f"\n  -> {OUT}")
    print("  A hypothesis scoring <0.15 should NOT consume a confirmation slot regardless of how")
    print("  interesting it sounds. Concept-level archaeology means rewording a dead idea does not")
    print("  resurrect it -- which token-level dedup could not prevent.")


if __name__ == "__main__":
    main()
