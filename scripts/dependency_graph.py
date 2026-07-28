"""DEPENDENCY GRAPH + IMPACT ANALYSIS -- which alphas are poisoned RIGHT NOW?

TIER 0: FORWARD TEST INTEGRITY. This exists because of a live finding nothing acted on.
data_vitals scored oi_ls_history.jsonl at DQS 0.000 (latency 0.00, completeness 0.00 -- genuinely
stale, not a threshold artifact). That file feeds A002 (OI/LS positioning), which is the ONLY
alpha with a running forward clock, reading out 2026-08-07. If the collector has been dead, the
verdict is already compromised -- and the desk would have accepted it on the date, because nothing
connects "this collector died" to "this clock is invalid".

That is the 14-day silent-websocket failure repeating in a new place: the failure is not that a
feed dies, it is that NOTHING DOWNSTREAM KNOWS.

    source -> feature -> alpha -> forward clock -> capital

Impact propagates FORWARD along that chain from any degraded node. Severity is taken from the
worst upstream state, never averaged -- averaging is how one dead input hides behind four healthy
ones, the same defect that made DQS mark 14/14 collectors dead yesterday.

STATES
    CLEAN       every upstream input passes both the measurement gate and DQS
    DEGRADED    an upstream input is stale or failed the gate; results are suspect
    POISONED    an upstream input is DEAD and the node depends on it for a LIVE decision
                (forward clock or deployed capital). This must block promotion.

Read-only. No keys, no network. Run from repo root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VITALS = ROOT / "data/data_vitals.json"
GATE = ROOT / "data/measurement_gate.json"
LIFE = ROOT / "data/alpha_lifecycle.json"
OUT = ROOT / "data/dependency_graph.json"
PAGE = ROOT / "docs/PRINCIPAL_ACTION.md"

# The graph. Declared explicitly because inferring it from imports would miss the ones that
# matter -- a collector and its consumer often share no code path at all, only a filename.
EDGES = {
    # STATIC ARCHIVE, not a live collector. Ends 2023-12-03 by design (600 days from
    # 2021-06-01, written once by dl_metrics_history.py for OOS backtesting). v1 of this graph
    # scored it POISONED because DQS applies live-feed latency rules to it -- the same category
    # error as judging an event log by time-series rules. A static archive cannot be stale.
    "oi_ls_history.jsonl": {
        "features": ["oi_ls_ratio", "taker_ratio"],
        "alphas": [],
        "static": True,
        "live_decision": False,
        "note": "historical backfill for OOS backtest; ends 2023-12-03 BY DESIGN"},
    "axis_shadow_state.json (live clocks)": {
        "features": ["kimchi_premium", "stablecoin_supply_momentum", "cny_premium"],
        "alphas": ["A002"],
        "live_decision": True,
        "note": "THE running forward clocks: kimchi day 6/40 due 2026-09-01, "
                "stablecoin day 5/40 due 2026-09-02, cny not started"},
    "cny_otc_premium_history.jsonl": {
        "features": ["cny_otc_premium"],
        "alphas": ["A003"],
        "live_decision": False,
        "note": "M_STRUCTURAL_BARRIER long-sample backbone"},
    "venue_divergence_shadow.jsonl": {
        "features": ["venue_nav_divergence"],
        "alphas": [],
        "live_decision": False,
        "note": "shadow monitor; no alpha depends on it yet"},
    "coinmetrics_flows.jsonl": {
        "features": ["stablecoin_flow"],
        "alphas": [],
        "live_decision": False, "note": "screened, no survivor"},
    "onchain_metrics.jsonl": {
        "features": ["active_addresses", "tx_count", "throughput_usd"],
        "alphas": [],
        "live_decision": False, "note": "M_FUNDAMENTAL_PROXY 0/7 survival"},
    "data/moat": {
        "features": ["spread_bps", "depth5", "depth10", "imbalance", "concentration", "slope"],
        "alphas": ["A004"],
        "live_decision": False,
        "note": "self-recorded; not covered by the .jsonl collectors scan"},
    "binance funding (live API)": {
        "features": ["funding_rate_persistence"],
        "alphas": ["A001"],
        "live_decision": True,          # the LIVE carry entry gate reads this every cycle
        "note": "feeds the live cash-carry entry gate"},
}


def _load(p, d=None):
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return d


def main() -> None:
    vit = {c["source"]: c for c in (_load(VITALS, {}) or {}).get("collectors", [])}
    gate = (_load(GATE, {}) or {}).get("datasets", {})
    alphas = {a["id"]: a for a in (_load(LIFE, {}) or {}).get("alphas", [])}

    print("=== DEPENDENCY GRAPH -- source -> feature -> alpha -> clock -> capital ===")
    print("    severity is taken from the WORST upstream input, never averaged:")
    print("    averaging is how one dead input hides behind four healthy ones\n")

    rows, poisoned, degraded = [], [], []
    print(f"  {'source':<34}{'DQS':>7}{'gate':>9}{'alphas':>8}  state")
    for src, e in EDGES.items():
        if e.get("static"):
            print(f"  {src:<34}{'static':>7}{'-':>9}{len(e['alphas']):>8}  STATIC (cannot be stale)")
            rows.append({"source": src, "dqs": None, "gate": None, "state": "STATIC",
                         "features": e["features"], "alphas": e["alphas"],
                         "live_decision": False, "note": e["note"]})
            continue
        v = vit.get(src)
        g = gate.get(src, {}).get("verdict")
        dqs = v["dqs"] if v else None
        dead = (dqs is not None and dqs < 0.5)
        gate_bad = (g == "FAILED")

        if (dead or gate_bad) and e["live_decision"]:
            state = "POISONED"
        elif dead or gate_bad:
            state = "DEGRADED"
        elif dqs is None and g is None:
            state = "UNMONITORED"
        else:
            state = "CLEAN"

        dstr = "n/a" if dqs is None else f"{dqs:.3f}"
        gstr = g or "-"
        print(f"  {src:<34}{dstr:>7}{gstr:>9}{len(e['alphas']):>8}  {state}")
        row = {"source": src, "dqs": dqs, "gate": g, "state": state,
               "features": e["features"], "alphas": e["alphas"],
               "live_decision": e["live_decision"], "note": e["note"]}
        rows.append(row)
        if state == "POISONED":
            poisoned.append(row)
        elif state == "DEGRADED":
            degraded.append(row)

    print(f"\n  {len(poisoned)} POISONED, {len(degraded)} DEGRADED, "
          f"{sum(1 for r in rows if r['state']=='CLEAN')} CLEAN, "
          f"{sum(1 for r in rows if r['state']=='UNMONITORED')} UNMONITORED")

    if poisoned:
        print("\n  === POISONED: a LIVE decision depends on a degraded input ===")
        for r in poisoned:
            print(f"\n  {r['source']}  (DQS {r['dqs'] if r['dqs'] is not None else 'n/a'}, "
                  f"gate {r['gate'] or '-'})")
            print(f"     -> features: {', '.join(r['features'])}")
            for aid in r["alphas"]:
                a = alphas.get(aid, {})
                print(f"     -> {aid} {a.get('name','?')}  [state {a.get('state','?')}]")
                print(f"        {r['note']}")
            print("     ACTION: the dependent result is NOT admissible until the input is")
            print("     repaired AND the affected window is re-derived. A forward clock that")
            print("     ran on a dead feed did not test the hypothesis -- it tested the feed.")

    unmon = [r for r in rows if r["state"] == "UNMONITORED"]
    if unmon:
        print(f"\n  UNMONITORED ({len(unmon)}): no DQS and no gate verdict covers these, so the")
        print("  graph cannot state whether anything downstream is safe. Absence of an alarm is")
        print("  not evidence of health -- that assumption is what let a websocket die for 14 days.")
        for r in unmon:
            print(f"    {r['source']:<34} feeds {r['alphas'] or 'no alpha'}  ({r['note']})")

    if poisoned:
        try:
            with PAGE.open("a", encoding="utf-8") as fh:
                fh.write(f"\n## {datetime.now(tz=UTC).isoformat()} POISONED DEPENDENCY\n")
                for r in poisoned:
                    fh.write(f"- {r['source']} (DQS {r['dqs']}) feeds {r['alphas']} "
                             f"-- {r['note']}\n")
            print(f"\n  -> paged {PAGE}")
        except OSError:
            pass

    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(), "nodes": rows,
                               "n_poisoned": len(poisoned), "n_degraded": len(degraded)},
                              indent=1), "utf-8")
    print(f"  -> {OUT}")
    raise SystemExit(1 if poisoned else 0)


if __name__ == "__main__":
    main()
