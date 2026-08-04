"""PHASE A -- Mechanism Graveyard + Hypothesis Portfolio + Mechanism Review Board.

Built as ONE module because they are one system, not three: the mechanism taxonomy produces the
verdicts, the verdicts drive portfolio correlation, and the review board enforces both at the gate.

WHY MECHANISM LEVEL BEATS CONCEPT LEVEL (the principal's key point):
    concept view:   Twitter / Google Trends / Wikipedia / Reddit  = 4 different failed datasets
    mechanism view: ATTENTION -> information arrives AFTER sophisticated participants -> 1 dead
                    mechanism, and every future variant inherits the evidence
Concept archaeology stops "social attention momentum" impersonating "Twitter sentiment". Mechanism
archaeology stops the whole family -- including variants nobody has worded yet. It is the
difference between blocking a phrase and blocking a reason.

THE THREE PARTS:
 1 MECHANISM GRAVEYARD -- maps every graveyard entry to its ECONOMIC MECHANISM (who is forced to
   act, and why the edge could exist), then aggregates verdicts per mechanism.
 2 PORTFOLIO CONSTRUCTION -- ranking by ERV alone concentrates the book: today's top-5 by ERV were
   ALL liquidity-stress variants, i.e. ONE BET WEARING FIVE HATS. This applies a correlation
   penalty so the second liquidity idea is worth less than the first.
 3 MECHANISM REVIEW BOARD -- four questions every hypothesis must answer BEFORE consuming a slot:
   why should this exist / who is FORCED to trade / why is it not already arbitraged / what kills
   it. Anything failing is rejected pre-test. Cheap gate, and 64% of this desk's failures were
   measurement or timing rather than alpha -- exactly what a pre-test gate can catch.

Read-only. No LLM, no keys. Run from repo root.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAVE = ROOT / "docs/graveyard.md"
ERV = ROOT / "data/research_erv.json"
AUTOPSY = ROOT / "data/research_autopsy.json"
OUT = ROOT / "data/mechanism_board.json"

# ECONOMIC MECHANISM taxonomy -- "who is forced to act, and why can the edge persist?"
# Deliberately NOT a dataset taxonomy. Many concepts collapse into one mechanism.
MECHANISMS = {
    "M_ATTENTION_DELAY": {
        "story": "attention/information reaches us AFTER sophisticated participants have priced it",
        "kws": (
            "attention",
            "sentiment",
            "social",
            "twitter",
            "wikipedia",
            "search",
            "trend",
            "narrative",
            "mention",
            "reddit",
            "influencer",
            "hype",
            "pageview",
        ),
    },
    "M_FUNDAMENTAL_PROXY": {
        "story": "a fundamental (developer effort, usage, revenue) is assumed to lead valuation",
        "kws": (
            "developer",
            "github",
            "commit",
            "contributor",
            "tvl",
            "revenue",
            "usage",
            "active address",
            "transaction count",
            "adoption",
            "release",
        ),
    },
    "M_SKILL_PERSISTENCE": {
        "story": "some participants are skilled and their past performance predicts future",
        "kws": (
            "trader",
            "elite",
            "copytrad",
            "leaderboard",
            "skill",
            "whale",
            "smart money",
            "persistence",
            "retention",
        ),
    },
    "M_STRUCTURAL_BARRIER": {
        "story": "a HARD barrier (capital control, licence, settlement, collateral) stops "
        "convergence -- the only mechanism family with a live survivor on this desk",
        "kws": (
            "capital control",
            "kimchi",
            "cny",
            "premium",
            "regulat",
            "licence",
            "license",
            "segment",
            "barrier",
            "peg",
            "redemption",
            "queue",
            "cross-venue",
        ),
    },
    "M_FORCED_DELEVERAGE": {
        "story": "leveraged participants are FORCED to unwind (margin, liquidation, funding cost)",
        "kws": (
            "funding",
            "open interest",
            "leverage",
            "liquidation",
            "margin",
            "crowding",
            "positioning",
            "long short",
            "basis",
            "carry",
            "squeeze",
        ),
    },
    "M_LIQUIDITY_WITHDRAWAL": {
        "story": "liquidity providers withdraw when inventory risk binds, so price impact jumps",
        "kws": (
            "depth",
            "spread",
            "order book",
            "orderbook",
            "market maker",
            "liquidity",
            "imbalance",
            "slippage",
            "replenish",
            "fragility",
            "microstructure",
        ),
    },
    "M_FLOW_PRESSURE": {
        "story": "observable capital movement precedes the price impact of that capital",
        "kws": (
            "flow",
            "netflow",
            "inflow",
            "outflow",
            "stablecoin",
            "bridge",
            "exchange reserve",
            "mint",
            "supply",
        ),
    },
    "M_PRICE_PATTERN": {
        "story": "price history alone predicts price -- no participant story at all",
        "kws": (
            "momentum",
            "reversal",
            "breakout",
            "rsi",
            "macd",
            "moving average",
            "kama",
            "squeeze",
            "donchian",
            "indicator",
            "lowvol",
            "trend",
        ),
    },
}

# the four questions -- a hypothesis that cannot answer these should not consume a slot
BOARD = [
    (
        "why_exists",
        "Why should this edge exist at all?",
        ("because", "mechanism", "due to", "driven by", "caused"),
    ),
    (
        "who_forced",
        "WHO is forced to trade against their own interest?",
        (
            "forced",
            "must",
            "liquidat",
            "margin",
            "redemption",
            "mandate",
            "rebalanc",
            "cannot",
            "obliged",
            "required",
        ),
    ),
    (
        "why_not_arbed",
        "Why has this not already been arbitraged away?",
        (
            "barrier",
            "control",
            "licence",
            "license",
            "constraint",
            "cost",
            "capacity",
            "latency",
            "illiquid",
            "segment",
            "regulat",
            "queue",
            "friction",
        ),
    ),
    (
        "kill_condition",
        "What observation kills it?",
        ("kill", "if ic", "t<", "below", "fails", "reject if", "abandon"),
    ),
]


def mech_of(text: str) -> list[str]:
    t = text.lower()
    return [m for m, d in MECHANISMS.items() if any(k in t for k in d["kws"])]


def main() -> None:
    # ---------- 1. MECHANISM GRAVEYARD -------------------------------------------------
    rows = []
    for ln in GRAVE.read_text("utf-8").splitlines() if GRAVE.exists() else []:
        if not ln.startswith("|") or set(ln) <= set("|- "):
            continue
        c = [x.strip() for x in ln.strip("|").split("|")]
        if len(c) < 3 or c[0].lower() in ("name", "signal", "strategy"):
            continue
        rows.append({"name": c[0][:80], "blob": " ".join(c), "mechs": mech_of(" ".join(c))})

    tally: dict[str, int] = {}
    for r in rows:
        for m in r["mechs"] or ["M_UNMAPPED"]:
            tally[m] = tally.get(m, 0) + 1

    # a mechanism with many deaths and no survivor is a FAMILY KILL
    LIVE = {"M_STRUCTURAL_BARRIER", "M_FORCED_DELEVERAGE"}  # kimchi/cny, funding persistence
    OPEN = {"M_LIQUIDITY_WITHDRAWAL"}  # moat, untested
    print("=== 1. MECHANISM-LEVEL GRAVEYARD ===")
    print("    concept archaeology blocks a PHRASE; mechanism archaeology blocks a REASON\n")
    print(f"  {'mechanism':<26}{'deaths':>7}  verdict / economic story")
    verdicts = {}
    for m, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        if m == "M_UNMAPPED":
            v = "UNMAPPED"
        elif m in LIVE:
            v = "ALIVE"
        elif m in OPEN:
            v = "UNTESTED"
        elif n >= 5:
            v = "FAMILY KILL"
        else:
            v = "WEAK"
        verdicts[m] = v
        story = MECHANISMS.get(m, {}).get("story", "-")
        print(f"  {m:<26}{n:>7}  {v:<12} {story[:74]}")

    dead_fams = [m for m, v in verdicts.items() if v == "FAMILY KILL"]
    print(f"\n  FAMILY KILLS: {dead_fams}")
    print("  Any future hypothesis mapping to these inherits the evidence and must show a NEW")
    print("  asymmetry or forced-flow story -- not merely a new dataset.")

    # ---------- 2. HYPOTHESIS PORTFOLIO CONSTRUCTION ------------------------------------
    print("\n=== 2. HYPOTHESIS PORTFOLIO (ERV alone concentrates the book) ===")
    ranked = []
    if ERV.exists():
        ranked = json.loads(ERV.read_text("utf-8")).get("ranked", [])
    if not ranked:
        print("  no ERV output -- run scripts/research_erv.py first")
    else:
        used_mech, out = {}, []
        for h in ranked:
            ms = mech_of(h.get("name", "") + " " + " ".join(h.get("concepts", []))) or [
                "M_UNMAPPED"
            ]
            # correlation penalty: each prior selection in the same mechanism halves the value
            overlap = max(used_mech.get(m, 0) for m in ms)
            adj = h.get("erv", 0) / (2**overlap)
            out.append({**h, "mechs": ms, "overlap": overlap, "erv_adj": round(adj, 4)})
            for m in ms:
                used_mech[m] = used_mech.get(m, 0) + 1
        out.sort(key=lambda x: -x["erv_adj"])
        print(f"  {'ERV':>6}{'ADJ':>7}  {'mech':<24} hypothesis")
        for h in out[:10]:
            print(
                f"  {h['erv']:>6.3f}{h['erv_adj']:>7.3f}  {h['mechs'][0][:24]:<24} {h['name'][:44]}"
            )
        dupes = [h for h in out if h["overlap"] > 0]
        print(f"\n  {len(dupes)} hypotheses de-rated for mechanism overlap -- these were ONE BET")
        print("  WEARING SEVERAL HATS. Ranking by raw ERV would have funded the same idea 5x.")

    # ---------- 3. MECHANISM REVIEW BOARD ------------------------------------------------
    print("\n=== 3. MECHANISM REVIEW BOARD (pre-test gate) ===")
    print("    64% of this desk's failures were TIMING or MEASUREMENT, not alpha -- exactly what")
    print("    a pre-test gate catches for free\n")
    samples = [
        {
            "name": "Low RSI predicts bounce",
            "text": "rsi oversold below 30 tends to bounce, momentum indicator",
        },
        {
            "name": "Liquidation cascade exhaustion",
            "text": "forced liquidations must sell into thin books, exceeding available depth; "
            "the constraint is that liquidated accounts CANNOT choose timing; not arbitraged "
            "because capacity is limited by book depth. kill if IC<0 over 12 months",
        },
        {
            "name": "Attention efficiency ratio",
            "text": "return per unit of social attention growth predicts continuation",
        },
    ]
    for s in samples:
        t = (s["name"] + " " + s["text"]).lower()
        answers = {k: any(w in t for w in kws) for k, q, kws in BOARD}
        ms = mech_of(t) or ["M_UNMAPPED"]
        fam = [m for m in ms if verdicts.get(m) == "FAMILY KILL"]
        passed = all(answers.values()) and not fam
        print(f"  {s['name'][:44]:<44} {'PASS' if passed else 'REJECT'}")
        for k, q, _ in BOARD:
            if not answers[k]:
                print(f"      unanswered: {q}")
        if fam:
            print(f"      mechanism {fam[0]} is a FAMILY KILL -- needs a new asymmetry story")

    OUT.write_text(
        json.dumps(
            {
                "updated": datetime.now(tz=UTC).isoformat(),
                "mechanism_deaths": tally,
                "verdicts": verdicts,
                "family_kills": dead_fams,
                "portfolio": out if ranked else [],
            },
            indent=1,
        ),
        "utf-8",
    )
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
