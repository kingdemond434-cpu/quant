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

THE BOARD EXISTS EVEN WHEN ITS INPUTS DO NOT (2026-09-08). Measured on this tree:
data/mechanism_board.json had never been produced, because data/research_erv.json and
data/research_autopsy.json do not exist here and nothing wrote the board without them --
while five readers (run_alpha_frontier, research_cio, kimi_hunter, knowledge_engine,
module_justification) opened it and silently got nothing. The board is now written on every
run: the ECONOMIC taxonomy (`libs.research.mechanism_census.TAXONOMY`, 32 payer-named classes)
is its `mechanisms` list in every mode, the graveyard tally gives verdicts where the graveyard
exists, and `basis` names which inputs were present and which were absent, so a reader can
tell a board built from evidence from one built from the taxonomy alone.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.mechanism_census import TAXONOMY  # noqa: E402

GRAVE = ROOT / "docs/graveyard.md"
ERV = ROOT / "data/research_erv.json"
AUTOPSY = ROOT / "data/research_autopsy.json"
OUT = ROOT / "data/mechanism_board.json"

#: `basis.mode` values. FULL means the ERV ranking (and the autopsy, when present) fed the
#: board; TAXONOMY_FALLBACK means neither research_erv.json nor research_autopsy.json existed
#: and the board carries the taxonomy plus whatever the graveyard alone could say.
FULL, TAXONOMY_FALLBACK = "FULL", "TAXONOMY_FALLBACK"
# a mechanism with many deaths and no survivor is a FAMILY KILL
LIVE = {"M_STRUCTURAL_BARRIER", "M_FORCED_DELEVERAGE"}  # kimchi/cny, funding persistence
OPEN = {"M_LIQUIDITY_WITHDRAWAL"}  # moat, untested
FAMILY_KILL_DEATHS = 5

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


def graveyard_rows(path: Path) -> list[dict[str, Any]]:
    """Every graveyard table row mapped to its economic mechanism(s); [] when the file is absent."""
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return rows
    for ln in lines:
        if not ln.startswith("|") or set(ln) <= set("|- "):
            continue
        c = [x.strip() for x in ln.strip("|").split("|")]
        if len(c) < 3 or c[0].lower() in ("name", "signal", "strategy"):
            continue
        rows.append({"name": c[0][:80], "blob": " ".join(c), "mechs": mech_of(" ".join(c))})
    return rows


def verdicts_of(tally: dict[str, int]) -> dict[str, str]:
    """Every mechanism the board names gets a verdict; zero recorded deaths is UNTESTED, never
    silence, so a reader that keys on the verdict table sees the whole vocabulary."""
    verdicts: dict[str, str] = {}
    for m in (*MECHANISMS, *(k for k in tally if k not in MECHANISMS)):
        n = tally.get(m, 0)
        if m == "M_UNMAPPED":
            v = "UNMAPPED"
        elif m in LIVE:
            v = "ALIVE"
        elif m in OPEN or n == 0:
            v = "UNTESTED"
        elif n >= FAMILY_KILL_DEATHS:
            v = "FAMILY KILL"
        else:
            v = "WEAK"
        verdicts[m] = v
    return verdicts


def taxonomy_mechanisms() -> list[dict[str, Any]]:
    """The economic taxonomy as the board's ontology: 32 payer-named classes, each with the
    reason the payer cannot stop paying, its plausibility and orthogonality priors, and what
    testing it would take. Read by run_alpha_frontier as `mechanisms`."""
    out = []
    for c in TAXONOMY:
        d = c.to_dict()
        d["signatures"] = list(c.signatures)[:12]
        d["priority"] = c.priority
        out.append(d)
    return out


def portfolio_of(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """ERV ranking with the mechanism-overlap penalty: each prior selection in the same
    mechanism halves the value, so the second liquidity idea is worth less than the first."""
    used_mech: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for h in ranked:
        ms = mech_of(h.get("name", "") + " " + " ".join(h.get("concepts", []))) or ["M_UNMAPPED"]
        overlap = max(used_mech.get(m, 0) for m in ms)
        adj = h.get("erv", 0) / (2**overlap)
        out.append({**h, "mechs": ms, "overlap": overlap, "erv_adj": round(adj, 4)})
        for m in ms:
            used_mech[m] = used_mech.get(m, 0) + 1
    out.sort(key=lambda x: -x["erv_adj"])
    return out


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def build(grave: Path = GRAVE, erv: Path = ERV, autopsy: Path = AUTOPSY) -> dict[str, Any]:
    """The board document. Never refuses: absent inputs are named in `basis`, not fatal."""
    rows = graveyard_rows(grave)
    tally: dict[str, int] = {}
    for r in rows:
        for m in r["mechs"] or ["M_UNMAPPED"]:
            tally[m] = tally.get(m, 0) + 1
    verdicts = verdicts_of(tally)
    dead_fams = [m for m, v in verdicts.items() if v == "FAMILY KILL"]
    erv_doc = _read_json(erv)
    ranked = list((erv_doc or {}).get("ranked") or []) if isinstance(erv_doc, dict) else []
    autopsy_present = autopsy.exists()
    mode = FULL if (erv.exists() or autopsy_present) else TAXONOMY_FALLBACK
    basis = {
        "mode": mode,
        "graveyard": (f"{grave.name}: {len(rows)} row(s) mapped" if rows
                      else f"{grave.name}: absent or no table rows"),
        "erv": (f"{erv.name}: {len(ranked)} ranked hypothesis(es)" if erv.exists()
                else f"{erv.name}: absent"),
        "autopsy": f"{autopsy.name}: {'present' if autopsy_present else 'absent'}",
        "taxonomy": f"libs.research.mechanism_census.TAXONOMY: {len(TAXONOMY)} classes",
        "note": ("TAXONOMY_FALLBACK: the ERV ranking and the autopsy were absent, so the "
                 "portfolio is empty and the verdicts rest on the graveyard tally alone; the "
                 "mechanisms list is the economic taxonomy in every mode"
                 if mode == TAXONOMY_FALLBACK else
                 "FULL: ERV ranking present; portfolio carries the mechanism-overlap penalty"),
    }
    return {"updated": datetime.now(tz=UTC).isoformat(), "basis": basis,
            "mechanism_deaths": tally, "verdicts": verdicts, "family_kills": dead_fams,
            "portfolio": portfolio_of(ranked) if ranked else [],
            "mechanisms": taxonomy_mechanisms(), "n_mechanisms": len(TAXONOMY)}


def main() -> None:
    doc = build()
    tally, verdicts, dead_fams, out = (doc["mechanism_deaths"], doc["verdicts"],
                                       doc["family_kills"], doc["portfolio"])
    # ---------- 1. MECHANISM GRAVEYARD -------------------------------------------------
    print("=== 1. MECHANISM-LEVEL GRAVEYARD ===")
    print("    concept archaeology blocks a PHRASE; mechanism archaeology blocks a REASON\n")
    print(f"  {'mechanism':<26}{'deaths':>7}  verdict / economic story")
    for m, v in sorted(verdicts.items(), key=lambda kv: -tally.get(kv[0], 0)):
        story = MECHANISMS.get(m, {}).get("story", "-")
        print(f"  {m:<26}{tally.get(m, 0):>7}  {v:<12} {story[:74]}")

    print(f"\n  FAMILY KILLS: {dead_fams}")
    print("  Any future hypothesis mapping to these inherits the evidence and must show a NEW")
    print("  asymmetry or forced-flow story -- not merely a new dataset.")

    # ---------- 2. HYPOTHESIS PORTFOLIO CONSTRUCTION ------------------------------------
    print("\n=== 2. HYPOTHESIS PORTFOLIO (ERV alone concentrates the book) ===")
    if not out:
        print(f"  no ERV output ({doc['basis']['erv']}) -- run scripts/research_erv.py first; "
              f"board written in {doc['basis']['mode']} mode from {doc['basis']['taxonomy']}")
    else:
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

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")
    print(f"\n  -> {OUT}  (basis: {doc['basis']['mode']})")


if __name__ == "__main__":
    main()
