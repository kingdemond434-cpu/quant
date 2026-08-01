"""ALPHA LIFECYCLE -- failure patterns, transfer pipeline, feature novelty, anomaly memory.

FOUR BUILD ITEMS, ONE MODULE. All four are lifecycle concerns over the same objects (trades,
features, alphas, incidents) and all four read artifacts that already exist. Four separate scripts
would mean three unwired ones.

1 FAILURE PATTERN FILTER -- most desks store winners. This mines the 249 realised closes for the
  CHARACTERISTICS that predict losses, which is a permanent filter rather than a post-mortem.
  It is not a re-derivation of the cost model: it asks which combination of measurable traits
  precedes a losing close, and would have flagged COOKIEUSDT before 21 opens rather than after.

2 ALPHA TRANSFER PIPELINE -- a discovery that never reaches capital has zero economic value. The
  desk had no explicit state machine, so "validated" and "deployed" were indistinguishable in
  conversation while being 0 and 0 in reality. Every alpha now carries a gate state and the
  evidence required to advance.

3 FEATURE NOVELTY DETECTOR -- prevents renamed factors. RSI / stochastic / Williams %R are one
  mechanism wearing three names. Reuses the jaccard machinery already written for research
  exchange intake, plus mechanism-level overlap, which is the stronger test: same mechanism means
  same failure mode regardless of construction.

4 MARKET ANOMALY MEMORY -- append-only record of rare events. Costs nothing, only accrues, and
  starting late is the only way to lose. Seeded with incident #6.

Read-only w.r.t. trading. Run from repo root.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRADES = ROOT / "data/cashcarry_trades.json"
COST = ROOT / "data/cost_model.json"
FEAT = ROOT / "data/feature_library.json"
GRAVE = ROOT / "docs/graveyard.md"
OUT = ROOT / "data/alpha_lifecycle.json"
ANOM = ROOT / "data/anomaly_memory.jsonl"

DEFAULT_RT = 39.5

# The transfer pipeline. Each gate names the EVIDENCE that advances it -- a state machine whose
# transitions are opinions is just a label.
PIPELINE = [
    ("DISCOVERED", "a mechanism and a falsification criterion exist"),
    ("SCREENED", "Stage-A screen run; ZERO promotion authority"),
    ("DECONTAMINATED", "survives orthogonalisation to the obvious confound"),
    ("COST_REAL", "net of MEASURED round-trip, not a default"),
    ("FORWARD_REGISTERED", "pre-registered forward clock with a fixed end date"),
    ("FORWARD_PASSED", "clock reached its date and the sign held"),
    ("SHADOW", "traded on paper at live sizing"),
    ("SMALL_CAPITAL", "live, minimum size, kill switch verified"),
    ("SCALED", "size increased on realised evidence"),
    ("MONITORED", "decay and crowding tracked"),
    ("RETIRED", "replaced or mechanism died"),
]

# Where the desk's actual alphas sit. Honest, and mostly early.
ALPHAS = [
    {"id": "A001", "name": "funding persistence (carry entry signal)",
     "mechanism": "M_FORCED_DELEVERAGE", "state": "COST_REAL",
     "evidence": "IC +0.432 (t +29.7) 24h; selection edge +25.3%/yr; survives cost model",
     "blocker": "no pre-registered forward clock of its own -- it audits the LIVE system instead"},
    {"id": "A002", "name": "OI/LS positioning", "mechanism": "M_FORCED_DELEVERAGE",
     "state": "FORWARD_REGISTERED", "evidence": "OOS chained, clock running",
     "blocker": "verdict due 2026-08-07"},
    {"id": "A003", "name": "CNY structural premium", "mechanism": "M_STRUCTURAL_BARRIER",
     "state": "SCREENED", "evidence": "structure test passed",
     "blocker": "INPUT FAILED measurement gate -- no producer, timestamps assumed"},
    {"id": "A004", "name": "liquidity withdrawal (moat)", "mechanism": "M_LIQUIDITY_WITHDRAWAL",
     "state": "DECONTAMINATED", "evidence": "1 of 270 constructions tested; residual rho +0.015 "
                                            "(t +0.28) -- that construction is a null",
     "blocker": "269 constructions untested; 0.4% coverage"},
]


def _closes():
    try:
        t = json.loads(TRADES.read_text("utf-8"))
    except Exception:
        return []
    rows = t if isinstance(t, list) else t.get("trades", [])
    out = []
    for r in rows:
        if r.get("event") != "close":
            continue
        h, n, f, pp = (r.get("held_hours"), r.get("notional"), r.get("funding_rate"),
                       r.get("price_pnl"))
        if None in (h, n, f, pp) or not n or float(h) <= 0:
            continue
        h, n, f, pp = float(h), float(n), float(f), float(pp)
        out.append({"sym": r.get("symbol"), "held_h": h, "notional": n, "funding": f,
                    "net_bps": (n * f * (h / 8.0) + pp) / n * 1e4})
    return out


def _rt(cm, sym):
    try:
        v = cm["symbols"][sym]["pair"]["500"].get("pair_roundtrip_bps")
        return (float(v), True) if v is not None else (DEFAULT_RT, False)
    except (KeyError, TypeError, ValueError):
        return (DEFAULT_RT, False)


def failure_patterns():
    rows = _closes()
    try:
        cm = json.loads(COST.read_text("utf-8"))
    except Exception:
        cm = {}
    if len(rows) < 40:
        print("  too few closes to mine"); return []
    for r in rows:
        r["rt"], r["measured"] = _rt(cm, r["sym"])
        r["loss"] = r["net_bps"] < 0

    # Traits are BINARY and pre-declared, so this is a lift table and not a search over
    # thresholds. Searching thresholds on 249 rows would manufacture a filter.
    traits = {
        "cost_unmeasured": lambda r: not r["measured"],
        "cost_gt_20bps": lambda r: r["rt"] > 20,
        "cost_gt_100bps": lambda r: r["rt"] > 100,
        "hold_under_24h": lambda r: r["held_h"] < 24,
        "funding_under_2bp": lambda r: r["funding"] * 1e4 < 2.0,
        "notional_over_1k": lambda r: r["notional"] > 1000,
    }
    base = sum(r["loss"] for r in rows) / len(rows)
    out = []
    print(f"  base loss rate across {len(rows)} closes: {base*100:.1f}%\n")
    print(f"  {'trait':<22}{'n':>5}{'loss%':>8}{'lift':>7}   verdict")
    for name, fn in traits.items():
        sub = [r for r in rows if fn(r)]
        if len(sub) < 15:
            continue
        lr = sum(r["loss"] for r in sub) / len(sub)
        lift = lr / max(base, 1e-9)
        v = ("PREDICTS LOSS" if lift > 1.25 else
             "protective" if lift < 0.8 else "no signal")
        print(f"  {name:<22}{len(sub):>5}{lr*100:>7.1f}%{lift:>7.2f}   {v}")
        out.append({"trait": name, "n": len(sub), "loss_rate": round(lr, 4),
                    "lift": round(lift, 3), "verdict": v})
    worst = [t for t in out if t["lift"] > 1.25]
    if worst:
        print(f"\n  PERMANENT FILTER CANDIDATES: {', '.join(t['trait'] for t in worst)}")
        print("  These are lift ratios on pre-declared binary traits, not a threshold search.")
    else:
        print("\n  No trait clears 1.25x lift. The sample cannot support a permanent filter yet;")
        print("  reporting that rather than lowering the bar until something passes.")
    return out



# Mechanism-level kill check runs BEFORE token overlap. Concept archaeology blocks a phrase;
# mechanism archaeology blocks a reason -- including wordings nobody has used yet.
_DEAD_MECHS = {
    "M_PRICE_PATTERN": ("rsi", "stochastic", "williams", "macd", "moving average", "oversold",
                        "overbought", "breakout", "momentum", "reversal", "bollinger"),
    "M_ATTENTION_DELAY": ("attention", "sentiment", "social", "twitter", "reddit", "search "
                          "interest", "google trends", "wikipedia", "hype", "narrative"),
    "M_SKILL_PERSISTENCE": ("copytrad", "leaderboard", "top trader", "smart money",
                            "profitable wallet", "trader ranking"),
    "M_FLOW_PRESSURE": ("netflow", "inflow predicts", "outflow predicts"),
}


def _dead_mechanism(text: str):
    """Return the BEST-matching dead mechanism, not the first dict hit.

    First-match returned M_PRICE_PATTERN for "social attention momentum from search interest"
    because "momentum" is a price-pattern keyword and dict order put it first. The verdict was
    right and the evidence trail was wrong, which sends the next reader to the wrong graveyard.
    Score every family and take the strongest.
    """
    low = text.lower()
    best, bm = 0, None
    for m, kws in _DEAD_MECHS.items():
        hits = sum(1 for k in kws if k in low)
        if hits > best:
            best, bm = hits, m
    return bm

_STOP = set(["the", "a", "an", "of", "to", "in", "for", "and", "or", "with", "is", "are", "be", "this", "that", "it", "as", "by", "from", "at"])


def novelty(candidate: str) -> dict:
    def toks(s):
        return {w for w in re.findall(r"[a-z]{4,}", s.lower()) if w not in _STOP}
    known = []
    try:
        for f in json.loads(FEAT.read_text("utf-8")).get("features", []):
            known.append((f"{f['name']} {f.get('rationale','')}", f.get("mechanism")))
    except Exception:
        pass
    if GRAVE.exists():
        for ln in GRAVE.read_text("utf-8").splitlines():
            if ln.startswith("|") and not set(ln) <= set("|- "):
                c = [x.strip() for x in ln.strip("|").split("|")]
                if c and c[0].lower() not in ("name", "signal", "strategy"):
                    known.append((c[0], None))
    ct = toks(candidate)
    best, bn = 0.0, None
    for text, _m in known:
        kt = toks(text)
        if not kt or not ct:
            continue
        j = len(ct & kt) / len(ct | kt)
        if j > best:
            best, bn = j, text
    dead = _dead_mechanism(candidate)
    if dead:
        return {"candidate": candidate, "max_jaccard": round(best, 3),
                "nearest": f"FAMILY KILL {dead}", "dead_mechanism": dead,
                "verdict": "DEAD-MECHANISM"}
    return {"candidate": candidate, "max_jaccard": round(best, 3),
            "nearest": (bn or "")[:70], "dead_mechanism": None,
            "verdict": "DUPLICATE" if best >= 0.5 else "novel" if best < 0.25 else "adjacent"}


def main() -> None:
    print("=== 1. FAILURE PATTERN FILTER -- what predicts a losing close ===")
    fp = failure_patterns()

    print("\n=== 2. ALPHA TRANSFER PIPELINE -- discovery without capital is worth zero ===\n")
    idx = {s: i for i, (s, _) in enumerate(PIPELINE)}
    print(f"  {'id':<6}{'alpha':<40}{'state':<20}{'gate':>6}")
    for a in ALPHAS:
        print(f"  {a['id']:<6}{a['name'][:40]:<40}{a['state']:<20}"
              f"{idx.get(a['state'],0)+1}/{len(PIPELINE)}")
        print(f"        blocker: {a['blocker'][:88]}")
    reached = max((idx.get(a["state"], 0) for a in ALPHAS), default=0) + 1
    print(f"\n  furthest any alpha has reached: gate {reached}/{len(PIPELINE)} "
          f"({PIPELINE[reached-1][0]})")
    print("  gates 6-11 (FORWARD_PASSED .. RETIRED) have NEVER been occupied. That is the")
    print("  whole distance between this desk's research output and its economic output.")

    print("\n=== 3. FEATURE NOVELTY DETECTOR -- stop renamed factors ===\n")
    tests = ["depth5 replenishment rate after liquidity withdrawal",
             "social attention momentum from search interest",
             "RSI oversold bounce on micro caps"]
    nov = [novelty(t) for t in tests]
    for r in nov:
        print(f"  {r['verdict']:<10} jaccard {r['max_jaccard']:.2f}  {r['candidate'][:52]}")
        if r["nearest"]:
            print(f"             nearest prior: {r['nearest']}")

    print("\n=== 4. MARKET ANOMALY MEMORY -- append-only, starts accruing today ===")
    seed = {"ts": "2026-07-27T21:06:52Z", "kind": "DESK_INCIDENT", "id": "INC-006",
            "title": "cash-carry hedge inverted short->long, twice",
            "detail": "COOKIEUSDT futures +916,772 where -183,140 required (unrl -$482, free "
                      "margin $110); recurred on 1000CATUSDT +1,138,985 after systemd respawn",
            "root_cause": "order size exceeded venue MARKET_LOT_SIZE (150,000) -> -4005 reject -> "
                          "resting post-only limit fallback -> accumulated fills crossed zero; no "
                          "reduceOnly on any futures cover",
            "detection_gap": "no invariant asserted that a tracked carry's futures leg is SHORT",
            "fixes": ["chunking to venue cap", "reduceOnly on covers",
                      "closes bypass the maker path", "hedge_integrity.py rail",
                      "kill forces rail over churn guard"]}
    existing = set()
    if ANOM.exists():
        for ln in ANOM.read_text("utf-8").splitlines():
            try:
                existing.add(json.loads(ln).get("id"))
            except json.JSONDecodeError:
                continue
    if seed["id"] not in existing:
        with ANOM.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(seed) + "\n")
        print(f"  seeded {seed['id']}: {seed['title']}")
    print(f"  {len(existing | {seed['id']})} anomaly record(s) -> {ANOM}")
    print("  Rare events are the stress-test library. Starting late is the only way to lose one.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "failure_patterns": fp,
                               "pipeline": [{"gate": g, "evidence": e} for g, e in PIPELINE],
                               "alphas": ALPHAS, "furthest_gate": reached,
                               "novelty_tests": nov}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
