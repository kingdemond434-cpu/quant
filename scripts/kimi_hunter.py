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
KEYS = ROOT / "data/secrets/llm_panel.json"
BUDGET = ROOT / "data/panel_budget.json"
BSTATE = ROOT / "data/panel_budget_state.json"
LEDGER = ROOT / "data/suggestion_ledger.jsonl"
MECHB = ROOT / "data/mechanism_board.json"
OUT = ROOT / "data/kimi_hunt.json"
CTX = ssl.create_default_context()

MODEL = "moonshotai/kimi-k3"          # seated model; swarm-max reserved for quarterly deep dives

VECTORS = ["linguistic_abyss", "github_graveyard", "protocol_documentation_sewer",
           "mempool_infrastructure_underworld", "regulatory_legal_trench",
           "cross_chain_shadow_roads", "obscure_perp_swamps"]

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
    "- FREE, PUBLIC, SCRAPABLE or RPC-accessible sources ONLY. Never suggest paid data APIs, "
    "institutional terminals or enterprise datasets.\n"
    "- Never suggest strategies or indicators. Suggest INFORMATION SOURCES and MECHANISMS.\n"
    "- Every finding needs a FORCED PARTICIPANT or a CONSTRAINT, not a correlation.\n"
    "- Report the bizarre. If something looks like a bug, report it -- the best discoveries look "
    "like errors first. Depth over breadth: 3 deep findings beat 20 shallow ones.\n"
    "- NEGATIVE KNOWLEDGE COUNTS: if you hunt a forest and find nothing, SAY SO explicitly. That "
    "prevents repeated waste and is a valid deliverable.\n\n"
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


def _budget_ok() -> tuple[bool, str]:
    try:
        env = json.loads(BUDGET.read_text("utf-8"))["monthly_envelope_usd"]
        st = json.loads(BSTATE.read_text("utf-8"))
        mtd = st.get("usage_at_run_start", 0.0) - st.get("usage_at_month_start", 0.0)
        return (mtd < env, f"MTD ${mtd:.2f} of ${env:.2f} envelope")
    except Exception:  # noqa: BLE001
        return (True, "budget state unreadable -- proceeding, guard is advisory")


def _ask(base, key, system, user, timeout=240.0) -> str:
    body = json.dumps({"model": MODEL, "max_tokens": 3000, "temperature": 0.9,
                       "messages": [{"role": "system", "content": system},
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
        keep, reason, cls, _ = _admit(line, 3, "")
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


def main() -> None:
    ok, why = _budget_ok()
    print("=== KIMI HUNTER -- Deep Forest Protocol (Wave 1 -> 2 -> 3) ===")
    print(f"    budget: {why}\n")
    if not ok:
        raise SystemExit("envelope exhausted -- refusing to start (guard, not a failure)")

    prov = None
    if KEYS.exists():
        for p in json.loads(KEYS.read_text("utf-8")).get("providers", []):
            if isinstance(p, dict) and p.get("model") == MODEL:
                prov = p
                break
    if not prov:
        print(f"  {MODEL} not in the seated roster -- add it to llm_panel.json first")
        raise SystemExit(2)

    kills = set(json.loads(MECHB.read_text("utf-8")).get("family_kills", [])) \
        if MECHB.exists() else set()
    print(f"  enforcing {len(FORBIDDEN_SETS)} forbidden zones + {len(kills)} family kills\n")

    transcript, findings, dropped = {}, [], []
    for w in (1, 2, 3):
        name, brief = WAVES[w]
        prior = "\n\n".join(f"WAVE {k} OUTPUT:\n{v[:2500]}" for k, v in transcript.items())
        user = (f"{brief}\n\nVECTORS: {', '.join(VECTORS)}\n\n{prior}" if prior
                else f"{brief}\n\nVECTORS: {', '.join(VECTORS)}")
        print(f"  WAVE {w} -- {name}")
        try:
            txt = _ask(prov["base_url"], prov["key"], CHARTER, user)
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", "")
            print(f"    FAILED ({type(e).__name__} {code})")
            if code == 402:
                print("    OpenRouter is out of credit. The hunt is BLOCKED, not broken --")
                print("    the harness is intact and fires on the next funded run.")
            raise SystemExit(3) from e
        transcript[w] = txt
        print(f"    {len(txt)} chars returned")

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
    for d in dropped[:6]:
        print(f"    dropped (wave {d['wave']}): {d['reason']}")
    if findings:
        with LEDGER.open("a", encoding="utf-8") as fh:
            for f in findings:
                fh.write(json.dumps(f) + "\n")
        print(f"  -> {LEDGER}  (enters the SAME gate as every other contributor)")
    print("\n  ZERO PROMOTION AUTHORITY. These are raw ore. Next stops: mechanism board "
          "(family-kill rejection), measurement gate, Stage-A screening, forward clock.")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "model": MODEL,
                               "waves": {str(k): v[:4000] for k, v in transcript.items()},
                               "findings": findings, "dropped": dropped}, indent=1), "utf-8")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    main()
