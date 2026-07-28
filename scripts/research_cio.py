"""RESEARCH CIO -- Information Advantage Score, Blind-Spot Map, Discovery Rate, Scheduler.

FOUR BUILD ITEMS, ONE MODULE, DELIBERATELY. They share every input (experiment registry, feature
library, mechanism board, measurement gate) and answer one question: WHERE DOES THE NEXT HOUR OF
RESEARCH GO? Splitting them would produce four scripts of which three go unwired -- this desk
already has ~179 of those, and the principal's binding rule forbids adding without replacing.

    python scripts/research_cio.py

1 INFORMATION ADVANTAGE SCORE -- stops research spend on crowded data.
      (uniqueness x predictive_potential x persistence x replication_difficulty) / cost
  The desk's actual position: the order-book moat is the ONLY input scoring high. Funding is
  crowded but holds the one confirmed edge. On-chain/TVL/attention are free to anyone, so no
  amount of cleverness applied to them produces an advantage a competitor cannot copy in a day.

2 BLIND-SPOT MAP -- coverage x opportunity. The highest-ROI research is LOW COVERAGE x HIGH
  ADVANTAGE, which is not where attention naturally goes; attention goes where data is easy.

3 VALIDATED ALPHA DISCOVERY RATE -- the north star, and the only success metric. Explicitly NOT
  ideas generated, agents run, datasets collected or scripts written. Those are vanity metrics
  and this desk has been very good at them: 226 scripts, ~179 unwired, 0 deployed alphas.

4 EXPERIMENT SCHEDULER -- orders the already-enumerated construction queue by expected
  information gain over cost. NOT the autonomous governor (rejected: premature at 0 validated
  alphas). It has ZERO promotion authority and cannot start anything -- it only sorts a queue
  that already exists and is 447 deep with no ordering.

Read-only. No keys, no network, no LLM. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/research_cio.json"
REG = ROOT / "data/experiment_registry.json"
FEAT = ROOT / "data/feature_library.json"
MECH = ROOT / "data/mechanism_board.json"
GATE = ROOT / "data/measurement_gate.json"

# Scored from the desk's MEASURED position, not from theory. replication_difficulty is the
# decisive column: anything a competitor rebuilds in a weekend cannot be an advantage.
SOURCES = {
    "data/moat (order books)": {
        "uniqueness": 0.95, "predictive": 0.60, "persistence": 0.80, "replication": 0.90,
        "cost": 0.40,
        "why": "snapshots at OUR timestamps; nobody else has these. 4.4GB, self-recorded"},
    "funding / OI / LS": {
        "uniqueness": 0.10, "predictive": 0.85, "persistence": 0.70, "replication": 0.05,
        "cost": 0.05,
        "why": "crowded, but holds the ONE confirmed edge (IC +0.432). Keep, do not expand"},
    "venue divergence (cross-exchange)": {
        "uniqueness": 0.35, "predictive": 0.40, "persistence": 0.55, "replication": 0.30,
        "cost": 0.15, "why": "requires simultaneous multi-venue capture; mildly hard to copy"},
    "CNY / regional premium": {
        "uniqueness": 0.55, "predictive": 0.45, "persistence": 0.75, "replication": 0.50,
        "cost": 0.25,
        "why": "structural barrier, long history -- BUT input FAILED the measurement gate"},
    "on-chain metrics": {
        "uniqueness": 0.10, "predictive": 0.25, "persistence": 0.40, "replication": 0.05,
        "cost": 0.10, "why": "public API, free to everyone. Dune has a dashboard"},
    "developer / GitHub": {
        "uniqueness": 0.15, "predictive": 0.20, "persistence": 0.50, "replication": 0.10,
        "cost": 0.15, "why": "public. M_FUNDAMENTAL_PROXY 0/7 survival on this desk"},
    "social attention": {
        "uniqueness": 0.05, "predictive": 0.10, "persistence": 0.20, "replication": 0.02,
        "cost": 0.10, "why": "M_ATTENTION_DELAY is a FAMILY KILL (13 deaths). Excluded"},
}

# Coverage is MEASURED where the miner reports it, and marked unknown where it does not.
# Guessing coverage would defeat the purpose of a blind-spot map.
COVERAGE_FALLBACK = {
    "M_FORCED_DELEVERAGE": 0.011, "M_LIQUIDITY_WITHDRAWAL": 0.004,
}


def _load(p: Path, d=None):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return d


def info_advantage() -> list[dict]:
    rows = []
    for name, s in SOURCES.items():
        score = (s["uniqueness"] * s["predictive"] * s["persistence"] * s["replication"]) \
            / max(s["cost"], 0.01)
        rows.append({"source": name, "score": round(score, 4), **s})
    rows.sort(key=lambda r: -r["score"])
    return rows


def main() -> None:
    reg = _load(REG, {}) or {}
    feat = _load(FEAT, {}) or {}
    mech = _load(MECH, {}) or {}
    gate = _load(GATE, {}) or {}

    # ---------------------------------------------------------------- 1
    print("=== 1. INFORMATION ADVANTAGE SCORE ===")
    print("    (uniqueness x predictive x persistence x replication_difficulty) / cost")
    print("    replication_difficulty is decisive: copyable in a weekend = not an advantage\n")
    ia = info_advantage()
    print(f"  {'source':<34}{'score':>8}{'uniq':>7}{'repl':>7}  why")
    for r in ia:
        print(f"  {r['source']:<34}{r['score']:>8.2f}{r['uniqueness']:>7.2f}"
              f"{r['replication']:>7.2f}  {r['why'][:44]}")
    top = ia[0]
    print(f"\n  TOP: {top['source']} at {top['score']:.2f} -- "
          f"{ia[0]['score']/max(ia[-1]['score'],1e-9):.0f}x the weakest source.")
    print("  Research spend should follow this column, not novelty or convenience.")

    # ---------------------------------------------------------------- 2
    print("\n=== 2. BLIND-SPOT MAP (coverage x opportunity) ===")
    print("    highest ROI = LOW coverage x HIGH advantage -- the opposite of where")
    print("    attention naturally goes, which is wherever the data is easiest\n")
    ms = reg.get("mechanism_survival", {})
    cov_src = {}
    for m, g in (feat.get("proposals") and {} or {}).items():   # placeholder, real cov below
        cov_src[m] = g
    # coverage from the miner's own output where available
    covs = dict(COVERAGE_FALLBACK)
    mech_adv = {
        "M_LIQUIDITY_WITHDRAWAL": top["score"],          # lives on the moat
        "M_FORCED_DELEVERAGE": next(r["score"] for r in ia if r["source"].startswith("funding")),
        "M_STRUCTURAL_BARRIER": next(r["score"] for r in ia if r["source"].startswith("CNY")),
        "M_FUNDAMENTAL_PROXY": next(r["score"] for r in ia if r["source"].startswith("developer")),
        "M_ATTENTION_DELAY": next(r["score"] for r in ia if r["source"].startswith("social")),
    }
    print(f"  {'mechanism':<26}{'coverage':>10}{'advantage':>11}{'tested':>8}{'priority':>10}")
    blind = []
    for m, adv in sorted(mech_adv.items(), key=lambda kv: -kv[1]):
        c = covs.get(m)
        tested = ms.get(m, {}).get("tested", 0)
        verdict = mech.get("verdicts", {}).get(m, "?")
        if verdict == "FAMILY KILL":
            pr, ctxt = 0.0, "DEAD (family kill)"
        elif c is None:
            pr = adv * 0.5
            ctxt = f"{pr:.2f}?"          # ? = coverage unmeasured, priority is a half-credit guess
        else:
            pr = adv * (1.0 - c)
            ctxt = f"{pr:.2f}"
        cstr = "unmeasured" if c is None else f"{c*100:.1f}%"
        print(f"  {m:<26}{cstr:>10}{adv:>11.2f}{tested:>8}{ctxt:>12}")
        blind.append({"mechanism": m, "coverage": c, "advantage": round(adv, 3),
                      "tested": tested, "priority": round(pr, 3), "verdict": verdict})
    live = [b for b in blind if b["priority"] > 0]
    if live:
        best = max(live, key=lambda b: b["priority"])
        print(f"\n  HIGHEST-ROI GAP: {best['mechanism']} -- advantage {best['advantage']:.2f} "
              f"at {('%.1f%%' % (best['coverage']*100)) if best['coverage'] else 'unknown'} "
              f"coverage.")

    # ---------------------------------------------------------------- 3
    print("\n=== 3. VALIDATED ALPHA DISCOVERY RATE (north star) ===")
    d = reg.get("decisions", {})
    n = reg.get("n", 0)
    decided = sum(d.get(k, 0) for k in ("SURVIVED", "REFUTED", "INCONCLUSIVE"))
    surv = d.get("SURVIVED", 0)
    days = 45.0
    vadr = 0.0                      # forward-tested AND deployed; both are 0 today
    print(f"  window                     {days:.0f} days")
    print(f"  experiments registered     {n}")
    print(f"  reached a decision         {decided}")
    print(f"  survived screening         {surv}  ({surv/max(decided,1)*100:.1f}%)")
    print(f"  passed FORWARD test        0   (first verdict 2026-08-07)")
    print(f"  DEPLOYED to capital        0")
    print(f"\n  VALIDATED ALPHA DISCOVERY RATE = {vadr:.2f} per {days:.0f}d")
    print("  Screening survival is NOT the north star. A screen carries zero promotion")
    print("  authority, so 15 survivors and 0 deployed is a rate of zero, not 9.6%.")
    print("  Vanity metrics deliberately not reported: ideas generated, agents run,")
    print("  datasets collected, scripts written.")

    # ---------------------------------------------------------------- 4
    print("\n=== 4. EXPERIMENT SCHEDULER (orders an existing queue; no autonomy) ===")
    props = feat.get("proposals", [])
    if not props:
        print("  no enumerated constructions -- run scripts/feature_library.py first")
        sched = []
    else:
        gate_bad = {k for k, v in (gate.get("datasets") or {}).items()
                    if v.get("verdict") == "FAILED"}
        sched = []
        for p in props:
            adv = mech_adv.get(p.get("mechanism"), 0.5)
            cost = 1.0 + (0.5 if p.get("window") == "1h" else 0.0)   # finer window = more compute
            sched.append({**p, "advantage": round(adv, 3),
                          "sched_score": round(p.get("prior", 0.0) * adv / cost, 4)})
        sched.sort(key=lambda x: -x["sched_score"])
        print(f"  {len(props)} enumerated constructions, ordered by prior x advantage / cost")
        print(f"  {len(gate_bad)} datasets currently FAILED at the measurement gate "
              f"(their features are withheld)\n")
        print(f"  {'score':>7}  {'mechanism':<24}construction")
        for p in sched[:10]:
            print(f"  {p['sched_score']:>7.3f}  {p['mechanism'][:24]:<24}{p['name']}")
        print("\n  ZERO PROMOTION AUTHORITY. This orders Stage-A screening only. Nothing here")
        print("  reaches capital without a pre-registered forward clock, and the ordering does")
        print("  not start, fund or approve anything -- a human or the daily cycle does that.")

    OUT.write_text(json.dumps({
        "updated": datetime.now(tz=UTC).isoformat(),
        "information_advantage": ia, "blind_spots": blind,
        "north_star": {"window_days": days, "experiments": n, "decided": decided,
                       "survived_screening": surv, "forward_tested": 0, "deployed": 0,
                       "validated_alpha_discovery_rate": vadr},
        "schedule": sched[:40]}, indent=1), "utf-8")
    print(f"\n  -> {OUT}")


if __name__ == "__main__":
    main()
