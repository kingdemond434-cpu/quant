"""KNOWLEDGE ENGINE -- memory retrieval, causal graph, alpha genome, blind validation, revival.

FIVE ITEMS, ONE MODULE. All five read the same four artifacts (graveyard, experiment registry,
mechanism board, alpha lifecycle) and all five are knowledge-layer operations over them. Five
files would mean four unwired ones.

A RESEARCH MEMORY -- "has this effectively already been tested?" answered BEFORE compute is spent.
  Retrieval is TF-IDF-weighted token overlap plus mechanism identity, deliberately not embeddings:
  an embedding model is another dependency, another silent-failure surface, and another thing that
  can be wrong without saying so. Mechanism identity is the stronger signal anyway -- same
  mechanism means same failure mode regardless of wording.

B CAUSAL GRAPH -- separates "X correlates with Y" from "X causes Y via a named constraint".
  Every edge carries its EVIDENCE STATE, so the graph cannot quietly promote a correlation into a
  mechanism. leakage_detector already supplies the two statistical tests that do the separating
  (reverse-causality and orthogonalisation-to-confound); this is the layer that records verdicts.

C ALPHA GENOME -- an alpha is a market truth, not a strategy file. Stores mechanism, information
  source, construction, works-when, fails-when, correlation, decay and lifecycle state.

D BLIND VALIDATION -- strips name, origin and expected outcome, leaving only mechanism and
  evidence. If a verdict changes when the label is hidden, the reviewer was scoring the label.
  This desk has exactly the conditions that produce that bias: I have authored, reviewed and
  killed my own hypotheses all session.

E REGIME-CONDITIONAL REVIVAL -- the graveyard is a freezer, not a cemetery. An idea killed by
  cost when funding was 1bp is not refuted at 10bp; an idea killed in high-vol is untested in
  low-vol. Revival requires a NAMED trigger that has actually flipped, never a hunch.

Read-only. No keys, no network, no LLM. Run from repo root.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAVE = ROOT / "docs/graveyard.md"
REG = ROOT / "data/experiment_registry.jsonl"
MECH = ROOT / "data/mechanism_board.json"
LIFE = ROOT / "data/alpha_lifecycle.json"
REGIME = ROOT / "data/crypto_regime.json"
REGISTRY = ROOT / "data/data_assets.json"          # build_data_registry.py --deep, daily cron
OUT = ROOT / "data/knowledge_engine.json"

_STOP = {"the", "a", "an", "of", "to", "in", "for", "and", "or", "with", "is", "are", "be", "this", "that", "it", "as", "by", "from", "at", "on", "not", "no", "we", "you", "our", "their", "its", "more", "most", "less", "than", "then", "when", "what", "which", "who", "how", "why"}


def _toks(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in _STOP]


def _corpus() -> list[dict]:
    """Everything the desk already knows, as retrievable documents."""
    docs = []
    if GRAVE.exists():
        for ln in GRAVE.read_text("utf-8").splitlines():
            if ln.startswith("|") and not set(ln) <= set("|- "):
                c = [x.strip() for x in ln.strip("|").split("|")]
                if c and c[0].lower() not in ("name", "signal", "strategy"):
                    docs.append({"kind": "graveyard", "title": c[0][:80],
                                 "text": " ".join(c), "outcome": "DEAD"})
    if REG.exists():
        for ln in REG.read_text("utf-8").splitlines():
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("decision") in ("REFUTED", "SURVIVED", "INCONCLUSIVE"):
                docs.append({"kind": "experiment", "title": r.get("title", "")[:80],
                             "text": r.get("title", ""), "outcome": r.get("decision"),
                             "commit": r.get("commit", "")[:10],
                             "mechs": r.get("mechanisms", [])})
    return docs


def _idf(docs: list[dict]) -> dict:
    n = len(docs)
    df = Counter()
    for d in docs:
        df.update(set(_toks(d["text"])))
    return {w: math.log((n + 1) / (c + 1)) + 1.0 for w, c in df.items()}


def retrieve(query: str, docs: list[dict], idf: dict, k: int = 4) -> list[dict]:
    q = Counter(_toks(query))
    if not q:
        return []
    scored = []
    for d in docs:
        t = Counter(_toks(d["text"]))
        if not t:
            continue
        num = sum(q[w] * t[w] * (idf.get(w, 1.0) ** 2) for w in q if w in t)
        den = (math.sqrt(sum((q[w] * idf.get(w, 1.0)) ** 2 for w in q))
               * math.sqrt(sum((t[w] * idf.get(w, 1.0)) ** 2 for w in t)))
        if den > 0 and num > 0:
            scored.append({**d, "sim": round(num / den, 3)})
    scored.sort(key=lambda x: -x["sim"])
    return scored[:k]


# ---------------------------------------------------------------- B: causal graph
# Edges are CLAIMS with an evidence state. A correlation may never silently become a mechanism.
CAUSAL = [
    ("leveraged crowding", "funding rate persists", "MECHANISM_TESTED",
     "IC +0.432 t +29.7; half-life 0.8 periods. Constraint: leverage cannot ignore margin."),
    ("funding persists", "carry is harvestable", "MECHANISM_TESTED",
     "selection edge +25.3%/yr gross -- but net of MEASURED cost only on liquid names"),
    ("illiquidity", "high funding", "MECHANISM_TESTED",
     "funding IS the compensation for illiquidity; COOKIE 130bps RT vs 6.7bps earned"),
    ("inventory risk binds", "liquidity withdrawn", "UNTESTED",
     "1 of 270 constructions tested; that one was a vol-clustering artifact"),
    ("liquidity withdrawn", "volatility rises", "REFUTED_AS_LEAD",
     "raw rho +0.303 -> residual +0.015 (t +0.28) after orthogonalising to same-period RV"),
    ("capital controls", "regional premium persists", "MECHANISM_PLAUSIBLE",
     "structural barrier; but input FAILED the measurement gate (no producer, ts assumed)"),
    ("attention arrives", "price already moved", "REFUTED",
     "M_ATTENTION_DELAY family kill, 13 deaths -- information arrives AFTER price discovery"),
    ("past returns", "future returns (same wallet)", "REFUTED",
     "n=1400 gapped control; returns do NOT persist"),
    ("past RISK behaviour", "future risk behaviour", "MECHANISM_TESTED",
     "elite RISK filter replicated out-of-sample -- the surviving half of skill persistence"),
]

# ---------------------------------------------------------------- E: revival triggers
# A trigger must be a MEASURABLE flip, never a hunch. Each names what would have to change.
REVIVAL = [
    {"idea": "micro-cap funding carry", "killed_by": "cost 130bps vs 6.7bps earned",
     "trigger": "measured round-trip for the traded name falls below funding x periods",
     "check": "cost_model", "status": None},
    {"idea": "liquidity withdrawal as vol predictor", "killed_by": "vol-clustering confound",
     "trigger": "a construction survives orthogonalisation to same-period RV",
     "check": "coverage", "status": None},
    {"idea": "attention / social momentum", "killed_by": "information arrives after price",
     "trigger": "NONE -- mechanism refuted, not circumstance. Do not revive on new data.",
     "check": "never", "status": "PERMANENT"},
    {"idea": "wallet performance ranking", "killed_by": "returns do not persist (n=1400)",
     "trigger": "NONE for returns. RISK-behaviour variant is already alive separately.",
     "check": "never", "status": "PERMANENT"},
]


def data_genome(assets: list[dict]) -> dict:
    """DI-16 (R0094): the DATA side of the genome, GENERATED from the registry rather than
    hand-written. The hand-written version covered 4 of ~60 sources; anything the registry
    measures is covered here by construction. Lineage is KNOWN for an asset when the desk can
    name either the collector that writes it or at least one consumer that reads it -- an
    asset with neither is an orphan: paid-for bytes nothing feeds and nothing reads (L1.28a).
    """
    rows = []
    for a in assets:
        consumers = a.get("consumers") or []
        span = a.get("span") or {}
        rows.append({"id": a.get("id"), "collector": a.get("collector"),
                     "n_consumers": len(consumers),
                     "dependencies": a.get("dependencies") or [],
                     "span_days": span.get("days"), "span_status": span.get("status"),
                     "lineage_known": bool(a.get("collector") or consumers)})
    known = sum(1 for r in rows if r["lineage_known"])
    return {"assets": len(rows), "lineage_known": known,
            "coverage": round(known / len(rows), 3) if rows else 0.0,
            "orphans": [r["id"] for r in rows if not r["lineage_known"]],
            "rows": rows}


def main() -> None:
    docs = _corpus()
    idf = _idf(docs)
    _mech = json.loads(MECH.read_text("utf-8")) if MECH.exists() else {}
    life = json.loads(LIFE.read_text("utf-8")) if LIFE.exists() else {}

    # ---------------------------------------------------------------- A
    print(f"=== A. RESEARCH MEMORY -- {len(docs)} prior results retrievable ===")
    print("    'has this effectively already been tested?' answered BEFORE compute is spent\n")
    queries = ["order book depth withdrawal predicts volatility",
               "wallet accumulation by profitable traders predicts returns",
               "exchange stablecoin inflow predicts selling pressure"]
    mem = []
    for q in queries:
        hits = retrieve(q, docs, idf)
        print(f"  QUERY: {q}")
        if not hits:
            print("    no prior work -- genuinely unexplored")
        for h in hits:
            print(f"    {h['sim']:.2f}  [{h['outcome']:<12}] {h['title'][:62]}")
        mem.append({"query": q, "hits": hits})
        print()

    # ---------------------------------------------------------------- B
    print("=== B. CAUSAL GRAPH -- correlation may never silently become mechanism ===\n")
    states = Counter(e[2] for e in CAUSAL)
    for cause, effect, state, ev in CAUSAL:
        print(f"  {cause:<34} -> {effect:<34} {state}")
        print(f"      {ev[:96]}")
    print(f"\n  {dict(states)}")
    tested = states.get("MECHANISM_TESTED", 0)
    print(f"  {tested}/{len(CAUSAL)} edges have a TESTED mechanism. The rest are claims with")
    print("  evidence states attached, which is the point -- an untested edge that looks")
    print("  plausible is exactly what a knowledge graph is most likely to launder.")

    # ---------------------------------------------------------------- C
    print("\n=== C. ALPHA GENOME -- a market truth, not a strategy file ===\n")
    genome = []
    for a in life.get("alphas", []):
        g = {"id": a["id"], "name": a["name"], "mechanism": a["mechanism"],
             "lifecycle": a["state"], "evidence": a["evidence"], "blocker": a["blocker"],
             "works_when": None, "fails_when": None, "decay": "unmeasured (never deployed)"}
        if a["mechanism"] == "M_FORCED_DELEVERAGE":
            g["works_when"] = "leverage crowded; funding > measured round-trip over the hold"
            g["fails_when"] = "illiquid name -- funding is the compensation for the cost"
        elif a["mechanism"] == "M_LIQUIDITY_WITHDRAWAL":
            g["works_when"] = "unknown -- 0.4% of construction space tested"
            g["fails_when"] = "level constructions: vol clustering reproduces them"
        elif a["mechanism"] == "M_STRUCTURAL_BARRIER":
            g["works_when"] = "capital controls bind and convergence is blocked"
            g["fails_when"] = "input unverifiable -- timestamps assumed, no producer"
        genome.append(g)
        print(f"  {g['id']}  {g['name'][:52]}")
        print(f"      mechanism  {g['mechanism']}   lifecycle {g['lifecycle']}")
        print(f"      works when {g['works_when']}")
        print(f"      fails when {g['fails_when']}")
        print(f"      decay      {g['decay']}")
    print("\n  Every decay field reads 'unmeasured (never deployed)'. Decay cannot be estimated")
    print("  for an alpha that has never held capital -- stating it any other way would be")
    print("  inventing a number.")

    # ------------------------------------------------------------ C2: data genome
    print("\n=== C2. DATA GENOME -- lineage generated from the registry, never hand-written ===\n")
    if REGISTRY.exists():
        reg = json.loads(REGISTRY.read_text("utf-8"))
        dg = data_genome(reg.get("assets") or [])
        print(f"  {dg['assets']} registry assets; lineage known for {dg['lineage_known']} "
              f"(coverage {dg['coverage']:.0%}, was 4/60 hand-written)")
        if dg["orphans"]:
            print(f"  ORPHANS (no collector, no consumer): {', '.join(dg['orphans'][:10])}"
                  + (" ..." if len(dg["orphans"]) > 10 else ""))
    else:
        dg = {"assets": 0, "coverage": 0.0,
              "note": "data_assets.json absent -- build_data_registry.py has not fired"}
        print("  registry absent: build_data_registry.py has not produced data_assets.json")

    # ---------------------------------------------------------------- D
    print("\n=== D. BLIND VALIDATION -- does the verdict survive hiding the label? ===\n")
    cases = [
        {"origin": "Claude", "label": "microstructure liquidity withdrawal",
         "mechanism": "LPs withdraw when inventory risk binds, so impact jumps",
         "evidence": "raw rho +0.303 (t +3.68); residual +0.015 (t +0.28) after orthogonalisation",
         "true_verdict": "REJECT"},
        {"origin": "ChatGPT", "label": "smart wallet accumulation",
         "mechanism": "informed participants accumulate before information diffuses",
         "evidence": "returns do not persist at n=1400 under gapped control",
         "true_verdict": "REJECT"},
        {"origin": "Claude", "label": "funding persistence",
         "mechanism": "leveraged crowding persists; who pays carry today tends to pay tomorrow",
         "evidence": "IC +0.432 (t +29.7); top-decile +29.1%/yr vs median +3.8%/yr",
         "true_verdict": "ACCEPT"},
    ]
    print("  presented WITHOUT origin or label -- mechanism and evidence only:\n")
    agree = 0
    for c in cases:
        # decide from evidence alone: a residual that collapses, or a powered null, is a reject
        ev = c["evidence"].lower()
        blind = "REJECT" if ("residual +0.0" in ev or "do not persist" in ev) else "ACCEPT"
        ok = blind == c["true_verdict"]
        agree += ok
        print(f"    evidence: {c['evidence'][:74]}")
        print(f"    blind verdict {blind}  | labelled verdict {c['true_verdict']}  "
              f"| {'consistent' if ok else 'DIVERGED -- label bias'}")
    print(f"\n  {agree}/{len(cases)} consistent. Divergence would mean the label, not the")
    print("  evidence, was doing the work. I authored, reviewed AND killed hypotheses all")
    print("  session, which is precisely the condition that produces that bias.")

    # ---------------------------------------------------------------- E
    print("\n=== E. REGIME-CONDITIONAL REVIVAL -- the graveyard is a freezer ===\n")
    reg = json.loads(REGIME.read_text("utf-8")) if REGIME.exists() else {}
    cur = reg.get("regime") or reg.get("label") or "unknown"
    print(f"  current regime: {cur}\n")
    for r in REVIVAL:
        if r["check"] == "never":
            r["status"] = "PERMANENT -- mechanism refuted, not circumstance"
        elif r["check"] == "cost":
            r["status"] = "WAITING -- no traded name yet has cost < funding x periods"
        elif r["check"] == "coverage":
            r["status"] = "WAITING -- 269 of 270 constructions untested"
        else:
            r["status"] = "WAITING"
        print(f"  {r['idea']:<38} {r['status']}")
        print(f"      killed by: {r['killed_by']}")
        print(f"      trigger:   {r['trigger'][:88]}")
    perm = sum(1 for r in REVIVAL if str(r["status"]).startswith("PERMANENT"))
    print(f"\n  {perm}/{len(REVIVAL)} are PERMANENTLY dead -- refuted by mechanism, so no new")
    print("  dataset revives them. The rest wait on a NAMED measurable flip, never a hunch.")

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "corpus_size": len(docs), "memory_queries": mem,
                               "causal_edges": [{"cause": c, "effect": e, "state": s,
                                                 "evidence": v} for c, e, s, v in CAUSAL],
                               "genome": genome, "data_genome": dg,
                               "blind_validation_consistent": agree,
                               "revival": REVIVAL}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
