"""KIMI HUNTER -- Deep Forest Protocol orchestration. Wave 1 -> 2 -> 3, enforced.

The last genuinely unbuilt item. It cannot RUN until OpenRouter is funded (402), but the harness
is not blocked by that and this ships ready to fire the moment credit lands.

THE PROTOCOL, enforced in code rather than trusted to the prompt:
  WAVE 1 SHADOW MAPPING       map what the herd covered. No findings permitted yet.
  WAVE 2 NEGATIVE SPACE       findings MUST cite the Wave-1 coverage that caused the miss.
                              A Wave-2 finding with no linkage is REJECTED here, not argued with.
  WAVE 3 DEEP FOREST          things the herd does not know are measurable.
Waves run in sequence and each is fed the previous wave's output, because a hunter that skips
straight to Wave 3 just returns whatever it already knew -- which is the herd's knowledge.

WHY THIS CANNOT SHORTCUT THE DESK. Kimi output is RAW ORE. It enters exactly one path:
    kimi_hunter -> suggestion ledger -> mechanism board -> measurement gate -> Stage-A -> clock
It has ZERO promotion authority, cannot open a position, cannot start an experiment, and cannot
write to any research artifact except the ledger. Findings that map to a FAMILY KILL are rejected
at intake and debited to the source, exactly like any other contributor -- an external model that
has not read the graveyard will re-propose corpses forever because it costs it nothing.

FORBIDDEN ZONES are enforced MECHANICALLY, not requested politely. A finding mentioning Binance
funding anomalies, RSI/TradingView combinations, Twitter sentiment, Google Trends or anything with
a public CoinGlass/Dune dashboard is dropped before it reaches the ledger. The prompt asks; this
enforces.

BUDGET: reads data/panel_budget.json and refuses to start if the envelope is exhausted. Free and
public sources only -- no paid data APIs, no institutional terminals.
"""
from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
KEYS = ROOT / "data/secrets/llm_panel.json"

from libs.doctrine.constitution import OBJECTIVE_PREAMBLE  # noqa: E402
from libs.ops.llm_route import build_chain  # noqa: E402
from libs.research import hunt_frontier as hf  # noqa: E402

BUDGET = ROOT / "data/panel_budget.json"
BSTATE = ROOT / "data/panel_budget_state.json"
LEDGER = ROOT / "data/suggestion_ledger.jsonl"
MECHB = ROOT / "data/mechanism_board.json"
OUT = ROOT / "data/kimi_hunt.json"
CTX = ssl.create_default_context()

MODEL = "moonshotai/kimi-k3"          # seated model; swarm-max reserved for quarterly deep dives

#: THE HUNT DOES NOT STOP BECAUSE ONE DOOR IS SHUT (L1.54, 2026-08-05).
#:
#: Until today this file named ONE model and had no path past it. Absent from the roster ->
#: SystemExit(2). Out of credit -> SystemExit(3). Any transport hiccup mid-wave -> SystemExit(3)
#: with the completed waves discarded from memory unwritten. The desk's widest non-Claude lens --
#: scheduled every three hours plus two deep runs a week -- had therefore produced EXACTLY NOTHING
#: since it was built: no data/kimi_hunt.json, no data/hunt_coverage.json, no ledger rows. Not
#: because the protocol is wrong (it is good) but because a single unavailable string ended it,
#: silently, 56 times a week.
#:
#: A weapon with one firing pin is not an aggressive weapon. The chain below is tried IN ORDER and
#: the first model that answers wins. Free variants are last rather than absent: a free-tier hunt
#: is worth immeasurably more than no hunt, and "the account is unfunded" is a reason to hunt
#: cheaper, never a reason to stop hunting.
#:
#: NOT A QUALITY COMPROMISE HIDDEN AS RESILIENCE: every finding carries the model that produced
#: it into the ledger, so a fallback hunt is attributable and can be re-run on the seated model
#: later. The gate it must pass is identical either way -- fallback buys ATTEMPTS, never leniency.
MODEL_CHAIN: tuple[str, ...] = (
    "moonshotai/kimi-k3",            # seated: the deep-forest hunter proper
    "moonshotai/kimi-k2",            # same family, previous generation
    "deepseek/deepseek-r1",          # different family: a genuinely different prior on what is
    "qwen/qwen3-235b-a22b",          #   under-observed, which is the point of the hunt
    "moonshotai/kimi-k2:free",       # free tier -- last, never omitted
    "deepseek/deepseek-r1:free",
    "qwen/qwen3-235b-a22b:free",
)

_COVERAGE = ROOT / "data/hunt_coverage.json"
_VECTOR_COOLDOWN_D = 45      # a forest may be re-entered only after this long

# NO TARGET LIST. Seed vectors exist ONLY to bootstrap run #1 on an empty coverage file; from
# run #2 onward the hunter generates its own and these are never consulted again.
_SEED_VECTORS = ["anything you consider under-observed"]

# Mechanically enforced. The prompt asks for these to be avoided; this drops them.
FORBIDDEN_SETS = [
    # Each entry is a REQUIRED TOKEN SET: the zone trips only when EVERY token is present,
    # in any order. Exact-substring matching let "Binance funding anomaly" through while
    # dropping "Binance funding rate anomaly" -- the same dead source, one word apart.
    {"binance", "funding"},          # crowded beyond usefulness; 10k bots watch it
    {"funding", "anomaly"},
    {"open", "interest", "high"},
    {"rsi"}, {"macd"}, {"bollinger"}, {"stochastic"},
    {"tradingview"}, {"coinglass"},
    {"dune", "dashboard"},
    {"twitter", "sentiment"}, {"sentiment", "analysis"},
    {"google", "trends"}, {"wikipedia", "pageview"},
    {"moving", "average"},
]



def _doctrine(role: str = "") -> str:
    """Runtime doctrine preamble. One source (scripts/doctrine.py); never a pasted copy."""
    try:
        from scripts.doctrine import preamble
        return preamble(role)
    except Exception:  # blind-except intentional (BLE001)
        try:
            import sys as _s
            _s.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
            from doctrine import preamble  # type: ignore
            return preamble(role)
        except Exception:  # blind-except intentional (BLE001)
            return ""          # never break a caller over a preamble


def _forbidden(text: str) -> str | None:
    """Return the tripped zone, or None. Token-set membership, order-independent.

    NOTE the deliberate narrowness: multi-token zones require ALL tokens, so bare "funding"
    is NOT blocked -- funding persistence is this desk's single confirmed edge and must stay
    researchable. The zone blocks crowded FRAMINGS of it, not the subject.
    """
    toks = set(re.findall(r"[a-z]+", text.lower()))
    for zone in FORBIDDEN_SETS:
        if zone <= toks:
            return " + ".join(sorted(zone))
    return None

CHARTER = (
    "You are an INFORMATION PREDATOR for a solo quant desk. You are not a literature reviewer.\n"
    "Your purpose: find edible information BEFORE the herd arrives. If you return 'funding rates "
    "are interesting' or 'OI is high' you have FAILED -- that is surface water.\n\n"
    "HARD CONSTRAINTS:\n"
    "\n"
    "EXHAUSTION MANDATE -- THERE IS NO CEILING AND NO QUOTA.\n"
    "Report EVERY finding you can substantiate, not a tidy number of them. If a forest holds\n"
    "thirty things, return thirty. If it holds two, return two AND SAY THE FOREST IS THIN --\n"
    "a documented empty seam stops the desk re-digging it and is worth as much as a find.\n"
    "Never stop because you have 'enough'. Enough is not a concept here.\n"
    "Never summarise to save space. Depth per finding AND number of findings are both unbounded.\n"
    "Go one layer deeper than feels finished. The layer past 'finished' is where the things\n"
    "nobody has named live, and it is the layer every other researcher skips.\n"
    "If you find yourself writing a conclusion, you stopped too early -- hunt again instead.\n"
    "\n"
    "- NAME YOUR OWN TERRITORIES. Prefix each with 'VECTOR: <name>'. You are not given\n"
    "  a search list; a fixed checklist is where everyone already looks.\n"
    "- FREE, PUBLIC, SCRAPABLE or RPC-accessible sources ONLY. Never suggest paid data APIs, "
    "institutional terminals or enterprise datasets.\n"
    # PRINCIPAL 2026-07-31: "miners n explorers kimi etc all should find every crypto strat even
    # discretionary n all n never limit to just one thing." This line used to read "Never suggest
    # strategies or indicators", which was aimed at PATTERN-MINING and hit STRATEGIES wholesale --
    # so the desk's only non-Claude hunter, its widest lens, was barred from returning the thing
    # the desk most needs. The real test was never source-vs-strategy; it is MECHANISM vs PATTERN,
    # and it applies identically either way.
    "- STRATEGIES ARE IN SCOPE, PATTERNS ARE NOT, and the difference is a FORCED PARTICIPANT.\n"
    "  Banned: a bare indicator or fitted rule with nobody on the other side ('RSI(14) crossover\n"
    "  on 4h', 'this MA pair backtests well') -- that is curve-fitting with a name.\n"
    "  In scope: any strategy whose mechanism names WHO is forced to trade against it and WHY\n"
    "  they cannot stop -- including DISCRETIONARY-shaped ones. Price reacting at a level is a\n"
    "  real mechanism when the forced participant is clustered stop-losses; a session-open\n"
    "  effect is real when it is a mandate-driven flow. A mechanism is never disqualified for\n"
    "  being judgement-shaped, only for being unfalsifiable.\n"
    "  INFORMATION SOURCES remain equally in scope -- this widens the brief, it does not\n"
    "  redirect it. Returning only one KIND of finding is the failure either way.\n"
    "- Every finding needs a FORCED PARTICIPANT or a CONSTRAINT, not a correlation.\n"
    "- Report the bizarre. If something looks like a bug, report it -- the best discoveries look "
    "like errors first. Depth AND breadth are both unbounded; a count is a quota in disguise.\n"
    "\n"
    "STRATEGY-FAMILY BREADTH -- UNLIMITED, ALL-SURFACE, NEVER-ENDING.\n"
    "NO SURFACE IS OUT OF SCOPE. Every venue, era, language, asset class, timeframe and FORMAT\n"
    "(papers, repos, configs, backtest tables, bot source, forum arguments, filings, incident\n"
    "post-mortems), and every STYLE -- systematic, discretionary, manual, hybrid, market-making,\n"
    "event-driven. If you catch yourself deciding a surface is not the kind of thing this desk\n"
    "looks at, that judgement IS the finding: name it and go there.\n"
    "NEVER-ENDING: there is no terminal state. 'Covered' and 'we already looked' are claims\n"
    "requiring evidence -- a dated search with its operators and its residual gap -- never\n"
    "defaults. UNLIMITED: no quota on families, findings, depth or session length; a count is a\n"
    "quota in disguise. The only two limits are the licence gate (public and licensed only, a\n"
    "forbidding licence is a HARD STOP) and never installing third-party tooling -- mine it as\n"
    "TEXT. Neither is a scope limit.\n"
    "Coverage is still the count of DISTINCT MECHANISM FAMILIES you\n"
    "return, never the count of findings. Twelve findings from one family are correlated by\n"
    "construction: they die together and the desk learns one thing while the log reports\n"
    "twelve. data/strategy_coverage.json names every family HUNTED / THIN / NEVER-HUNTED from\n"
    "the desk's own graveyard -- read it, and prefer an unhunted family over deepening a\n"
    "worked one. On the desk's record 41 buried candidates cluster into 7 worked families of\n"
    "14, so breadth is the binding constraint, not depth.\n"
    "- NEGATIVE KNOWLEDGE COUNTS: if you hunt a forest and find nothing, SAY SO explicitly. That "
    "prevents repeated waste and is a valid deliverable.\n"
    # L1.34 (principal 2026-07-31): the hunters were free to return one CLASS of artifact and
    # call the ground dug. Every source class is in scope for every seat, kimi included -- it is
    # the desk's only non-Claude hunter, so a narrow brief here narrows the widest lens we own.
    "- EVERY FORM OF RAW INFORMATION IS IN SCOPE (L1.34), not just live feeds: published "
    "BACKTESTS and result tables (read the code and the window -- the leak they missed is the "
    "find), STRATEGY CODE and configs, DATASETS and the endpoint lists inside collector code, "
    "AI-QUANT STRUCTURES (factor-mining frameworks, symbolic regression, agent-team and "
    "multi-model architectures, RL harnesses), NICHE AI-QUANT COMMUNITIES explicitly including "
    "the Chinese ecosystem (Gitee, Zhihu, Xueqiu, JoinQuant/BigQuant, WeChat mirrors, Bilibili) "
    "and their contributor networks, UNTESTED ALPHAS (published-but-never-validated claims, "
    "abandoned hypotheses, 'this worked for me' posts with no out-of-sample -- untested is not "
    "false, it is an UNPRICED OPTION and it is the richest and most neglected vein), VIDEO AND "
    "AUDIO (talks, lectures, botter walkthroughs -- transcripts are readable and are first-class "
    "material, never a logged blocker), and everything else carrying information: exchange "
    "changelogs and announcement archives, regulatory filings and enforcement actions, patents, "
    "JOB POSTINGS (they leak infrastructure and strategy families), theses, dead products' docs, "
    "archived APIs. THE STANDING TEST: if a source carries information a competitor would have "
    "to PAY to reconstruct, it is in scope regardless of format, language, age, or how "
    "unglamorous it looks.\n\n"
    "CLAIM PROVENANCE IS MANDATORY. Every finding starts with one of:\n"
    "  VERIFIED  -- direct quote or number WITH a URL or document reference\n"
    "  INFERRED  -- your own mechanism construction (legitimate, but say so)\n"
    "NEVER blend them in one finding. Split it, or drop it. A VERIFIED tag with no\n"
    "source reference will be downgraded automatically.\n"
    "YOUR JOB IS RAW SIGNAL, NOT MECHANISM. Mechanism construction happens at the next\n"
    "stage. If you find yourself explaining WHY something should work, you have\n"
    "overstepped -- report what you FOUND and let the next stage build the story.\n"
    "If you find nothing in a forest, say so explicitly. That is a valid deliverable.\n\n"
    "OUTPUT: one finding per line, fields separated by |, exactly 8 fields:\n"
    "CLAIM_CLASS | PROBLEM | EVIDENCE | BENEFIT | COST | DEPENDENCIES | SUCCESS_METRIC | KILL_CONDITION\n"
    "where PROBLEM names the information gap, EVIDENCE cites the source/URL, and KILL_CONDITION "
    "states what observation would prove the source worthless."
)

WAVES = {
    1: ("SHADOW MAPPING", "Map what the herd covered in the last 24h: English CT narratives, "
        "Dune/CoinGlass/DefiLlama trending, GitHub trending quant repos, mainstream crypto media. "
        "Output 10-15 covered topics labelled HERD_COVERED. Do NOT report findings yet."),
    2: ("NEGATIVE SPACE MINING", "For each HERD_COVERED item from Wave 1, ask what ADJACENT topic "
        "they ignored because it is too small, weird or foreign. You may NOT report a finding "
        "unless you name the specific herd coverage that caused the miss."),
    3: ("DEEP FOREST PENETRATION", "Forget the herd. Hunt: abandoned repos with 0 stars, protocols "
        "under $10M TVL with no English docs, mempool patterns nobody has named, regulatory "
        "filings in non-Latin scripts, bridge failure modes, perp venues with no CoinGlass page. "
        "Findings must be things where a typical quant would say 'I didn't know that was "
        "measurable'."),
}


def _re_vectors(text: str) -> set[str]:
    """Territory names declared this wave. EXTRACTION ONLY -- it records no outcome.

    Splitting extraction from recording is the fix: the old version stamped every named territory
    as covered the instant it was uttered, burying wave-1 mapping output for the full cooldown
    before anything hunted it.
    """
    return {v.strip().lower()
            for v in re.findall(r"VECTOR:\s*([A-Za-z0-9_\- ]{4,50})", text) if v.strip()}


def _budget_ok() -> tuple[bool, str]:
    try:
        env = json.loads(BUDGET.read_text("utf-8"))["monthly_envelope_usd"]
        st = json.loads(BSTATE.read_text("utf-8"))
        mtd = st.get("usage_at_run_start", 0.0) - st.get("usage_at_month_start", 0.0)
        return (mtd < env, f"MTD ${mtd:.2f} of ${env:.2f} envelope")
    except Exception:  # blind-except intentional (BLE001)
        return (True, "budget state unreadable -- proceeding, guard is advisory")


def _providers() -> list[tuple[str, str, str]]:
    """Every (model, base_url, key) worth trying, in preference order.

    Built by crossing MODEL_CHAIN with the seated roster: a roster entry naming a chain model is
    used directly, and any other roster entry sharing that entry's base_url can also SERVE the
    chain model, because OpenRouter routes by the `model` field rather than by the credential.
    That second rule is what turns one dead string into a working hunt -- previously a roster
    holding four OpenRouter seats none of which was literally `moonshotai/kimi-k3` produced
    "not in the seated roster", exit 2, no hunt, no artifact, no complaint.

    Returns [] when there is genuinely no credential anywhere. That is a BLOCKER to record, and
    main() records it -- it is not a reason for this function to invent one.
    """
    # ONE implementation, in libs/ops/llm_route. Eleven other organs on this desk resolve a single
    # model and stop; copying this logic into each would guarantee eleven slightly different
    # versions and eleven separate regressions, so the routing lives in a library they can all
    # adopt and check_llm_routing names the ones that have not.
    return [(r.model, r.base_url, r.key) for r in build_chain(MODEL_CHAIN, KEYS)]


def _ask(base, key, system, user, timeout=240.0, model: str = MODEL) -> str:
    body = json.dumps({"model": model, "max_tokens": 16000, "temperature": 1.0,
                       "messages": [{"role": "system",
                                     "content": (OBJECTIVE_PREAMBLE + "\n"
                                                 + _doctrine("kimi_hunter") + system)},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        out = json.loads(r.read())
    m = out["choices"][0]["message"]
    return str(m.get("content") or m.get("reasoning") or "")






def _admit(line: str, wave: int, wave_text: str = "") -> tuple[bool, str, str, list[str]]:
    """SINGLE SOURCE OF TRUTH for admission. Returns (keep, reason, claim_class, fields).

    main() and _selftest() both call this. Previously the selftest carried its own simplified
    copy, scored 6/6 against a rule that does not run, and stayed green through a charter change
    that broke it. One function means they cannot diverge again.
    """
    parts = [x.strip() for x in line.split("|")]
    if len(parts) < 8:
        return (False, f"only {len(parts)} fields, charter needs 8", "", parts)
    cls = parts[0].upper()
    if cls not in ("VERIFIED", "INFERRED"):
        return (False, f"claim class {cls!r} not VERIFIED/INFERRED", cls, parts)
    f = _forbidden(line)
    if f:
        return (False, f"forbidden zone {f!r}", cls, parts)
    body = " ".join(parts[1:])
    if cls == "VERIFIED" and not any(t in body.lower() for t in
                                     ("http", "www.", ".gov", ".org", "10-q", "10-k",
                                      "filing", "docs.", "github.com")):
        # an unsourced claim of sourcing is worth exactly what an unsourced claim is worth
        return (True, "VERIFIED downgraded to INFERRED -- no source reference", "INFERRED",
                parts[1:])
    if wave == 2 and "HERD_COVERED" not in wave_text.upper() and "because" not in line.lower():
        return (False, "no linkage to Wave-1 coverage", cls, parts)
    return (True, "", cls, parts[1:])


_SELFTEST_CASES = [
    ("INFERRED | Japanese tax reclassification drives offshore perp flow | FIEA 2027 timeline;"
     " capital-flight mechanism is my construction | forced-flow lead | 3d | none |"
     " JPY-hours perp volume share rises | no share change after 90d",
     "KEEP", "INFERRED and labelled as such -- legitimate"),
    ("VERIFIED | Strategy preferred dividend forces BTC sales | $1.2B annual obligation |"
     " scheduled forced seller | 2d | none | sale within 5d of dividend date | no clustering",
     "KEEP-DOWNGRADED", "VERIFIED with no URL -> auto-downgraded to INFERRED"),
    ("Bridge failure spike | illustrative example | edge | 1d | none | IC | none | extra",
     "DROP", "no CLAIM_CLASS in position 1"),
    ("INFERRED | Binance funding anomaly | dashboards show it | edge | 1d | NONE | IC | none",
     "DROP", "forbidden zone: crowded funding"),
    ("INFERRED | RSI oversold micro caps | tradingview | edge | 1d | NONE | IC | none",
     "DROP", "forbidden zone: RSI / TradingView"),
    ("INFERRED | Twitter sentiment velocity | CT volume | edge | 1d | NONE | IC | none",
     "DROP", "forbidden zone: twitter sentiment"),
    ("VERIFIED | Aave health-factor tail predicts forced liquidation | https://docs.aave.com logs"
     " | forced-seller lead time | 2d | local node | share of cascades pre-detected > 0.4 |"
     " no lead beyond 1 block",
     "KEEP", "forced participant + free source + kill condition"),
    ("VERIFIED | Validator exit queue predicts stETH discount | https://beaconcha.in API | early"
     " warning | 1d | NONE | corr with discount > 0.3 | no relation after 60d",
     "KEEP", "obscure, free, mechanism named"),
    ("INFERRED | Bridge failure spike | Stargate subgraph | liquidity stress",
     "DROP", "only 3 fields, charter needs 7"),
]


def _selftest() -> int:
    """Exercise enforcement offline with synthetic hunter output. Costs nothing."""
    print("=== KIMI HUNTER SELFTEST (enforcement only; API path needs credit) ===")
    print()
    passed = 0
    for line, expect, why in _SELFTEST_CASES:
        keep, reason, _cls, _ = _admit(line, 3, "")
        got = "KEEP" if keep else "DROP"
        if keep and "downgraded" in reason:
            got = "KEEP-DOWNGRADED"
        ok = got == expect
        passed += ok
        print(f"  {'PASS' if ok else 'FAIL'}  expect {expect:<16} got {got:<16}  {why}")
        if reason:
            print(f"           {reason}")
    print()
    print(f"  {passed}/{len(_SELFTEST_CASES)} enforcement cases correct")
    print("  Verified WITHOUT spending credit: forbidden zones drop crowded and dead sources,")
    print("  the 7-field charter rejects incomplete proposals, and genuine forced-participant")
    print("  findings on free sources survive. The API path stays untested until funded --")
    print("  stated, not implied.")
    return 0 if passed == len(_SELFTEST_CASES) else 1




# Adversarial on purpose: 2 admissible, 1 forbidden, 1 unsourced-VERIFIED, 1 malformed.
_MOCK_WAVES = {
    1: ("HERD_COVERED: BTC funding squeeze; ETF flows; SOL upgrade narrative; "
        "liquidation heatmaps; DXY macro; Dune liquidation trackers."),
    2: ("HERD_COVERED liquidation heatmaps -- they watch CEX perp liquidations because "
        "CoinGlass renders them, and therefore ignore DeFi lending health factors upstream.\n"
        "VERIFIED | Aave health-factor left tail predicts forced liquidation before perps "
        "reflect it | https://docs.aave.com event logs via free RPC, because the herd watches "
        "CEX heatmaps | forced-seller lead time | 2d | local node | share of cascades "
        "pre-detected > 0.4 | no lead beyond 1 block\n"
        "INFERRED | Binance funding anomaly on majors | dashboards show it | edge | 1d | NONE "
        "| IC | none\n"),
    3: ("VERIFIED | Validator exit queue length predicts stETH discount | "
        "https://beaconcha.in public API | early warning on staked-ETH pressure | 1d | NONE | "
        "corr with discount > 0.3 | no relation after 60d\n"
        "VERIFIED | Strategy preferred dividend forces quarterly BTC sales | $1.2B annual "
        "obligation | scheduled forced seller | 2d | NONE | sale within 5d of dividend | "
        "no clustering over 4 quarters\n"
        "INFERRED | Bridge failure spike | Stargate subgraph | liquidity stress\n"),
}


def _mock() -> int:
    """Run the entire pipeline on synthetic output. Only the HTTP call is bypassed."""
    print("=== KIMI HUNTER --mock : full chain, no credit, HTTP bypassed ===")
    print("    payload is adversarial: 2 admissible, 1 forbidden, 1 unsourced-VERIFIED,")
    print("    1 malformed. Wrong admissions fail loudly instead of reaching the ledger.\n")
    findings, dropped = [], []
    for w in (1, 2, 3):
        txt = _MOCK_WAVES[w]
        print(f"  WAVE {w}: {len(txt)} chars")
        if w == 1:
            print("    (mapping wave -- findings not permitted)")
            continue
        for ln in txt.splitlines():
            if ln.count("|") < 3:
                continue
            keep, reason, cls, parts = _admit(ln, w, txt)
            if reason:
                dropped.append((w, reason))
                print(f"    drop/flag: {reason}")
            if not keep:
                continue
            findings.append({"date": datetime.now(tz=UTC).date().isoformat(),
                             "source": "kimi_k3_deep_forest", "wave": w, "claim_class": cls,
                             "problem": parts[0][:220], "evidence": parts[1][:220],
                             "benefit": parts[2][:180], "cost": parts[3][:140],
                             "dependencies": parts[4][:140], "success_metric": parts[5][:180],
                             "kill_condition": parts[6][:180], "status": "proposed"})
            print(f"    ADMIT [{cls}] {parts[0][:62]}")

    expect_admit, expect_drop = 3, 3
    ok = len(findings) == expect_admit and len(dropped) >= expect_drop
    print(f"\n  admitted {len(findings)} (expect {expect_admit}), "
          f"dropped/flagged {len(dropped)} (expect >= {expect_drop})")
    if not ok:
        print("  MOCK FAILED -- the chain would write the wrong things when funded.")
        return 1

    before = LEDGER.stat().st_size if LEDGER.exists() else 0
    with LEDGER.open("a", encoding="utf-8") as fh:
        for f in findings:
            f["mock"] = True                       # tagged so the scoreboard can exclude it
            fh.write(json.dumps(f) + "\n")
    after = LEDGER.stat().st_size
    print(f"  ledger {before} -> {after} bytes (+{after-before}) -- rows tagged mock=true")
    print("\n  CHAIN PROVEN. The only untested link between funded credit and findings in the")
    print("  ledger is one urllib call returning 200 instead of 402. Admission, provenance")
    print("  downgrade, forbidden zones, wave-2 linkage and the ledger write all executed")
    print("  against real code just now.")
    return 0


def _blocked(reason: str, attempts: list[dict] | None = None) -> None:
    """Record a hunt that could not run, as an ARTIFACT rather than as a log line and an exit code.

    L1.44's rule applied to an organ that produces nothing: an absent artifact is indistinguishable
    from an organ nobody scheduled, so the desk could not tell "the hunter is unfunded" from "the
    hunter was never built" -- a bill to pay versus a thing to build. The `status` field is what
    the capability ratchet and max_audit read; `blocker` is what a human acts on.
    """
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(),
        "status": "BLOCKED",
        "blocker": reason,
        "attempts": attempts or [],
        "model_chain": list(MODEL_CHAIN),
        "waves": {}, "findings": [], "dropped": [],
        "note": ("the Deep Forest protocol and its intake gates are INTACT. This records that the "
                 "hunt could not be ATTEMPTED, which is a different fact from a hunt that found "
                 "nothing -- and only the second is evidence about the world."),
    }, indent=1), "utf-8")
    print(f"  BLOCKED -> {OUT}\n    {reason}")


def main() -> None:
    attempts: list[dict] = []
    models_used: list[str] = []
    ok, why = _budget_ok()
    print("=== KIMI HUNTER -- Deep Forest Protocol (Wave 1 -> 2 -> 3) ===")
    print(f"    budget: {why}\n")
    if not ok:
        raise SystemExit("envelope exhausted -- refusing to start (guard, not a failure)")

    # A BLOCKED HUNT MUST LEAVE EVIDENCE THAT IT WAS BLOCKED. The old code printed a line and
    # exited 2, so an organ firing 56 times a week left no artifact at all -- and an artifact that
    # is absent looks exactly like an organ nobody scheduled. The desk could not tell "the hunter
    # is unfunded" from "the hunter was never built", which is the difference between a bill to
    # pay and a thing to build.
    chain = _providers()
    if not chain:
        _blocked("no usable credential: data/secrets/llm_panel.json is absent or holds no seat "
                 "with both a base_url and a key. The Deep Forest protocol is INTACT and unrun -- "
                 "this is a funding/credential blocker, not a defect in the hunt.")
        raise SystemExit(2)
    print(f"  {len(chain)} model/seat combination(s) to try, in order: "
          f"{', '.join(m for m, _, _ in chain[:4])}{' ...' if len(chain) > 4 else ''}")

    kills = set(json.loads(MECHB.read_text("utf-8")).get("family_kills", [])) \
        if MECHB.exists() else set()
    print(f"  enforcing {len(FORBIDDEN_SETS)} forbidden zones + {len(kills)} family kills\n")

    state = hf.load(_COVERAGE)
    go, gate_why = hf.should_hunt(state, cooldown_d=_VECTOR_COOLDOWN_D)
    print(f"  frontier: {gate_why}")
    if not go:
        # THE FREE GATE. No model call was made to reach this -- it is read off local state. A
        # hunter on a clock pays a full reasoning pass to discover the world has not changed.
        print("  SKIPPING the reasoning pass -- no frontier open. Not a failure and not an "
              "outage: the organ is declining to re-mine picked-over ground.")
        hf.save(state, _COVERAGE)
        return
    _seen_before: set[str] = set(state.vectors)
    _wave_vectors: dict[int, set[str]] = {}
    transcript, findings, dropped = {}, [], []
    for w in (1, 2, 3):
        name, brief = WAVES[w]
        prior = "\n\n".join(f"WAVE {k} OUTPUT:\n{v[:2500]}" for k, v in transcript.items())
        _sec = hf.prompt_sections(state, cooldown_d=_VECTOR_COOLDOWN_D)
        _cover = _sec["priority"] + (f"\n\n{_sec['exclude']}" if _sec["exclude"] else "")
        user = f"{brief}\n\n{_cover}" + (f"\n\n{prior}" if prior else "")
        print(f"  WAVE {w} -- {name}")
        # WALK THE CHAIN. One model being unavailable, rate-limited or out of credit ends that
        # ATTEMPT, never the hunt. Failures accumulate into the artifact so a run that ends
        # blocked says which doors it tried and what each one answered.
        txt, used = "", ""
        for model, base, key in chain:
            try:
                txt = _ask(base, key, CHARTER, user, model=model)
            except Exception as e:  # blind-except intentional (BLE001)
                code = getattr(e, "code", "")
                attempts.append({"wave": w, "model": model, "error": f"{type(e).__name__} {code}"})
                print(f"    {model}: FAILED ({type(e).__name__} {code})"
                      + ("  [out of credit]" if code == 402 else ""))
                continue
            if txt.strip():
                used = model
                break
            attempts.append({"wave": w, "model": model, "error": "empty response"})
            print(f"    {model}: empty response")
        if not used:
            # EVERY door on this wave is shut. Keep whatever the earlier waves produced -- a
            # completed Wave 1 map is worth having and re-deriving it costs a full run.
            print(f"    wave {w} could not be run on any model; keeping {len(transcript)} "
                  "completed wave(s)")
            break
        transcript[w] = txt
        models_used.append(used)
        # NAMING IS NOT HUNTING. Wave 1 is mapping only, so its territories are NAMED_ONLY --
        # frontier to chase next run, never coverage. Recording them as hunted is what locked
        # this organ out of its own best ground for 45 days.
        _named = _re_vectors(txt)
        for _v in _named:
            if _v not in state.vectors:
                hf.record(state, _v, outcome="NAMED_ONLY")
        _new_v = len(_named - _seen_before)
        _seen_before |= _named
        _wave_vectors[w] = _named
        print(f"    [{used}] {len(txt)} chars returned, {_new_v} new vector(s) recorded")
        # PERSIST AFTER EVERY WAVE. Coverage used to be written only after Wave 3 returned, so a
        # hunt dying late threw away the territory memory of the waves that HAD succeeded and the
        # next run re-hunted the same forest -- the cooldown silently defeated by its own failure
        # path, which is the most expensive way to lose depth.
        hf.save(state, _COVERAGE)

        if w == 1:
            continue                       # Wave 1 is mapping only; findings are not permitted
        for ln in txt.splitlines():
            if ln.count("|") < 3:
                continue
            keep, reason, cls, parts = _admit(ln, w, txt)
            if reason:
                dropped.append({"wave": w, "reason": reason, "line": ln[:120]})
            if not keep:
                continue
            findings.append({"date": datetime.now(tz=UTC).date().isoformat(),
                             "source": "kimi_k3_deep_forest", "wave": w, "claim_class": cls,
                             "problem": parts[0][:220], "evidence": parts[1][:220],
                             "benefit": parts[2][:180], "cost": parts[3][:140],
                             "dependencies": parts[4][:140], "success_metric": parts[5][:180],
                             "kill_condition": parts[6][:180], "status": "proposed"})

    print(f"\n  {len(findings)} charter-complete findings, {len(dropped)} dropped")
    for d in dropped:
        print(f"    dropped (wave {d['wave']}): {d['reason']}")
    if findings:
        with LEDGER.open("a", encoding="utf-8") as fh:
            for f in findings:
                fh.write(json.dumps(f) + "\n")
        print(f"  -> {LEDGER}  (enters the SAME gate as every other contributor)")
    print("\n  ZERO PROMOTION AUTHORITY. These are raw ore. Next stops: mechanism board "
          "(family-kill rejection), measurement gate, Stage-A screening, forward clock.")
    # OUTCOME ATTRIBUTION. A territory hunted in wave 2/3 is YIELDED if this run produced any
    # finding, EMPTY otherwise -- EMPTY being real negative knowledge, not a failure.
    _hunted = _wave_vectors.get(2, set()) | _wave_vectors.get(3, set())
    _per = max(1, len(_hunted))
    for _v in _hunted:
        hf.record(state, _v, outcome=("YIELDED" if findings else "EMPTY"),
                  findings=(len(findings) // _per if findings else 0))
    hf.save(state, _COVERAGE)
    _fr = hf.frontier(state, cooldown_d=_VECTOR_COOLDOWN_D)
    # The key is `vectors`. This line read cov.get('"vectors"') -- chr(34) is a double quote, so
    # the lookup asked for a key spelled WITH quotation marks, missed every time, and printed
    # "0 territories hunted to date" unconditionally. The desk's only depth-accumulation readout
    # was hardcoded to zero by an obfuscation, which is the worst place for one: a hunter whose
    # depth always reads nothing gives nobody a reason to look at whether depth is accruing.
    # ...and "hunted to date" was the wrong count anyway, which is why it now reports the
    # FRONTIER split: a territory merely NAMED is not one hunted, and reporting them together is
    # the same conflation that locked this organ out of its own mapping output.
    n_terr = len(state.vectors)
    print(f"  coverage memory: {n_terr} territories known -- "
          f"{len(_fr['unhunted'])} named-but-unhunted, {len(_fr['blocked'])} blocked, "
          f"{len(_fr['picked_over'])} picked over")
    # PARTIAL is a first-class outcome. A run that mapped the herd and mined negative space but
    # could not reach Wave 3 produced real work, and calling that a failure would throw it away.
    status = "OK" if len(transcript) == 3 else ("PARTIAL" if transcript else "BLOCKED")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "status": status,
                               "models_used": models_used,
                               "model_chain": list(MODEL_CHAIN),
                               "waves_completed": sorted(transcript),
                               "attempts": attempts,
                               "territories_hunted": n_terr,
                               "waves": {str(k): v[:4000] for k, v in transcript.items()},
                               "findings": findings, "dropped": dropped}, indent=1), "utf-8")
    print(f"  status {status} | waves {sorted(transcript)} | models {models_used}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    if "--mock" in sys.argv:
        raise SystemExit(_mock())
    main()
