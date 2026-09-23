"""The Asian production-chain and transmission graph, MEASURED and then converted into cells.

USE THE GRAPH TO GENERATE HYPOTHESES. NEVER TREAT THE GRAPH ITSELF AS EVIDENCE. That sentence is
the whole discipline of this file and it is easy to lose: a chain like

    SHFE copper inventory -> Chinese industrial demand -> copper -> AUD sensitivity -> AUDUSD

reads as an explanation, and an explanation is exactly what an overfit finds convincing. So every
declared edge here is a CLAIM with a falsifier attached, it is measured against the bars on disk
before anything is proposed, and an edge that does not measure is written down as REFUTED rather
than quietly dropped. A graph whose failures are invisible is a graph that only ever confirms.

WHAT IS GENUINELY NEW HERE AGAINST `cross_asset_graph`, which already sweeps the book's pairs:

    THE PAIRS ARE ECONOMIC, NOT COMBINATORIAL. `cross_asset_graph` tries every ordered pair of
    twelve book symbols and pays the multiplicity charge for all of them. A declared chain is one
    hypothesis with a stated mechanism, so `lead_lag.edge` admits it at the CAUSAL_ROLE bar
    (t >= 3.0) rather than the STATISTICAL bar (t >= 4.0) -- the prior is doing work it is
    entitled to do, and the trial count it spends is a dozen rather than a hundred and thirty.

    THE SESSION IS CONDITIONED. Chinese and Japanese information is released into Asian hours. An
    edge measured over all 24 hours pools the session the information ARRIVES in with the two
    sessions that merely inherit it, which is how a real Asia-hours transmission gets averaged
    into nothing. Each edge is measured twice -- pooled and Asia-only -- and the pair is the
    finding: an edge that exists only in Asian hours is a transmission, and an edge that exists
    in both is more likely a shared factor.

    IT TARGETS THE EMPTY CLUSTER. `EFFECTIVE_BREADTH` measures 11 of 15 declared clusters as empty
    in both the traded and certified books, and `cross_asset_lead_lag` is the first of them. 65
    live sleeves behaving as ~5.6 independent bets is not fixed by a 66th sleeve in an occupied
    cluster; it is fixed here or somewhere like here.

A CHAIN WHOSE ENDPOINT THIS ACCOUNT DOES NOT QUOTE IS NAMED, NOT SKIPPED. Copper is the clearest
industrial-demand instrument in every one of these chains and Fusion does not quote it, so those
chains route through their declared currency proxy and the substitution is recorded on the row.
Pretending the proxy IS copper is how a transmission gets credited to the wrong mechanism.

    python desks/mt5/research/asia_transmission.py
    python desks/mt5/research/asia_transmission.py --propose    # also donate the cells
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

OUT = BASE / "reports" / "ASIA_TRANSMISSION.json"

#: Asian trading hours in UTC. Tokyo opens 00:00 UTC and Shanghai's afternoon session ends around
#: 07:00; London's pre-open begins to dominate by 08:00. The window is deliberately generous at
#: the front and tight at the back: an edge that only appears once London is awake is not an Asian
#: transmission whatever its t-statistic says.
ASIA_HOURS = tuple(range(0, 8))

#: Entry thresholds and holds swept per surviving edge, matching `cross_asset_graph` so the two
#: proposers charge the same multiplicity for the same shape of search.
ENTRY_Z = (1.5, 2.0)
HOLDS = (4, 8)

#: THE DECLARED CHAINS. Each is an economic claim with a falsifier, not a correlation someone
#: noticed. `proxy_for` records where the true instrument is unquoted here and a currency stands
#: in for it -- the substitution is part of the finding, never hidden inside it.
CHAINS: tuple[dict[str, Any], ...] = (
    {"name": "china_industrial_to_aud",
     "hops": ["SHFE copper/ore inventory", "Chinese industrial demand", "base metals",
              "Australian export revenue", "AUD"],
     "driver": "AUS200", "target": "AUDUSD", "expected": "same",
     "rationale": ("Chinese industrial demand is Australian export revenue with a lag. The "
                   "Australian index carries the resource complex's earnings, so it prices the "
                   "same demand state the currency does and its Asian-hours session is where "
                   "Chinese information lands first."),
     "falsifier": ("no Asia-hours lead from the Australian index into AUDUSD at any lag up to "
                   "the graph's maximum, or a lead that reverses sign out of sample"),
     "proxy_for": "copper and iron ore, neither quoted on this account"},

    {"name": "china_growth_to_nzd",
     "hops": ["Chinese credit impulse", "Asian industrial demand", "commodity exporters", "NZD"],
     "driver": "AUDUSD", "target": "NZDUSD", "expected": "same",
     "rationale": ("NZD is the second-order expression of the same Chinese demand state AUD "
                   "prices first: the Australian read is larger, earlier and more liquid, so if "
                   "the channel exists at all NZD should lag it in Asian hours."),
     "falsifier": "no measurable lag; the two move contemporaneously, which is a shared factor "
                  "rather than a transmission"},

    {"name": "sge_premium_to_gold",
     "hops": ["Shanghai gold benchmark", "Chinese physical demand", "loco-London premium",
              "XAUUSD"],
     "driver": "XAGUSD", "target": "XAUUSD", "expected": "same",
     "rationale": ("Until the SGE benchmark itself is collected, the Asian-hours silver/gold "
                   "relationship is the only public read this desk holds on the precious complex "
                   "during the session Chinese physical demand clears in. Silver has the thinner "
                   "float, so a physical bid shows there first."),
     "falsifier": "no Asia-hours lead from silver into gold, or a lead present equally in London "
                  "hours -- which would make it a precious-complex factor and not a Chinese one",
     "proxy_for": "the SGE Shanghai premium, source sge_benchmark, not yet collected"},

    {"name": "jpy_rates_to_gold",
     "hops": ["BOJ liquidity stance", "JGB yields", "JPY repricing", "gold in JPY", "XAUUSD"],
     "driver": "USDJPY", "target": "XAUUSD", "expected": "opposite",
     "rationale": ("Japanese rates are one of the two real-rate terms gold prices off, and the "
                   "Japanese session is where they move. A weaker yen raises the domestic gold "
                   "price and suppresses the Japanese physical bid, which reaches the dollar "
                   "price with a lag."),
     "falsifier": "no Asia-hours relationship, or a same-sign one, which would contradict the "
                  "stated real-rate mechanism rather than merely fail to support it"},

    {"name": "cnh_stress_to_gold",
     "hops": ["PBOC fixing / liquidity", "CNH funding stress", "Asian risk state", "XAUUSD"],
     "driver": "USDCNH", "target": "XAUUSD", "expected": "same",
     "rationale": ("offshore RMB weakness is the public expression of Chinese capital pressure, "
                   "and Chinese households and the central bank are both structural gold buyers "
                   "into exactly that state."),
     "falsifier": "no Asia-hours lead, or an edge that vanishes once the dollar's own move is "
                  "removed -- in which case this is the dollar factor wearing a Chinese label"},

    {"name": "china_energy_to_cad",
     "hops": ["INE crude / Chinese refinery runs", "Asian crude demand", "global crude", "CAD"],
     "driver": "XTIUSD", "target": "USDCAD", "expected": "opposite",
     "rationale": ("Chinese refinery demand clears in the Asian session and CAD is the currency "
                   "expression of the crude complex; the Asian-hours crude move should reach the "
                   "Canadian dollar before the North American session prices it."),
     "falsifier": "no Asia-hours lead into USDCAD, or an edge no larger than the pooled one"},

    {"name": "china_energy_to_nok",
     "hops": ["Asian crude demand", "Brent complex", "NOK"],
     "driver": "XTIUSD", "target": "USDNOK", "expected": "opposite",
     "rationale": ("the same crude channel into the other petro-currency, kept as a separate "
                   "chain so that a result appearing in only one of the two is visible as the "
                   "warning it is."),
     "falsifier": "an edge into NOK with none into CAD, which would mean the mechanism is not "
                  "crude at all but something Norwegian"},

    {"name": "hk_liquidity_to_cnh",
     "hops": ["HKMA aggregate balance", "HIBOR", "offshore funding", "CNH"],
     "driver": "HK50", "target": "USDCNH", "expected": "opposite",
     "rationale": ("Hong Kong is the offshore transmission point: mainland tightening reaches "
                   "the offshore RMB through HK funding, and the HK index is the risk expression "
                   "of that state during Asian hours."),
     "falsifier": "no Asia-hours lead from HK risk into CNH",
     "proxy_for": "the HKMA aggregate balance, source hkma_open_api, not yet collected"},

    {"name": "asia_risk_to_jpy_cross",
     "hops": ["Asian session risk state", "carry demand", "JPY crosses"],
     "driver": "AUS200", "target": "AUDJPY", "expected": "same",
     "rationale": ("AUDJPY is the canonical carry expression of Asian risk appetite, and the "
                   "Australian index is the risk state that sets it, in the same session."),
     "falsifier": "no lead, which would mean the carry pair is already efficient inside the "
                  "session that sets it"},

    {"name": "gold_silver_ratio_state",
     "hops": ["Chinese industrial silver demand", "gold/silver ratio", "XAGUSD"],
     "driver": "XAUUSD", "target": "XAGUSD", "expected": "same",
     "rationale": ("the reverse direction of the precious chain, declared separately because a "
                   "transmission that measures in BOTH directions is a shared factor and not a "
                   "lead -- and that is a result worth being able to read."),
     "falsifier": "an edge of similar strength to the silver->gold chain, which refutes both as "
                  "transmissions"},
)


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default if default is not None else {}


def _asia_only(df):
    """The same frame restricted to Asian hours. Empty rather than wrong when the index is naive.

    A naive index is read as UTC, which is what every other organ on this desk assumes of the
    universe parquets; stating it once here is better than two organs assuming it differently.
    """
    try:
        import pandas as pd
        idx = pd.DatetimeIndex(df.index)
        hours = idx.tz_convert("UTC").hour if idx.tz is not None else idx.hour
        return df[[h in ASIA_HOURS for h in hours]]
    except Exception:
        return df.iloc[0:0]


def measure(budget_s: float = 600.0) -> dict[str, Any]:
    import time

    from libs.research import lead_lag
    from research import proposer_common as pc

    started = time.monotonic()
    meta = pc.universe_meta()
    have = {p.stem.removesuffix("_H1") for p in pc.UNI.glob("*_H1.parquet")}
    bars: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []

    for ch in CHAINS:
        d, t = str(ch["driver"]), str(ch["target"])
        rec: dict[str, Any] = {k: ch[k] for k in
                               ("name", "hops", "driver", "target", "expected", "rationale",
                                "falsifier")}
        if "proxy_for" in ch:
            rec["proxy_for"] = ch["proxy_for"]
        missing = [s for s in (d, t) if s not in have]
        if missing:
            rec.update({"verdict": "UNQUOTED",
                        "why": f"{', '.join(missing)} has no H1 chart on this account, so the "
                               f"chain has no instrument to land on here"})
            rows.append(rec)
            continue
        for s in (d, t):
            if s not in bars:
                bars[s] = pc.bars(s)
        if bars[d] is None or bars[t] is None:
            rec.update({"verdict": "UNMEASURED", "why": "bars would not load"})
            rows.append(rec)
            continue

        # THE DECLARED MECHANISM BUYS THE LOWER BAR, and only the declared ones. `plausible_role`
        # is what moves `lead_lag.edge` from t>=4.0 to t>=3.0; a pair nobody wrote a rationale for
        # does not get it.
        pooled = lead_lag.edge(bars[d], bars[t], plausible_role=ch["name"])
        asia = lead_lag.edge(_asia_only(bars[d]), _asia_only(bars[t]),
                             plausible_role=ch["name"])
        rec["pooled"] = pooled
        rec["asia_hours"] = asia

        sign_ok = str(asia.get("direction") or "") == str(ch["expected"])
        if asia.get("verdict") == "EDGE" and sign_ok:
            rec["verdict"] = "TRANSMISSION" if pooled.get("verdict") != "EDGE" else "SHARED_FACTOR"
            rec["why"] = ("present in Asian hours and absent when pooled: the session the "
                          "information arrives in is the session it works in"
                          if rec["verdict"] == "TRANSMISSION" else
                          "present in BOTH Asian and pooled hours, which is more consistent with "
                          "a shared factor than with a session transmission -- proposed, but "
                          "with that written on it")
        elif asia.get("verdict") == "EDGE" and not sign_ok:
            rec.update({"verdict": "REFUTED",
                        "why": (f"an Asia-hours edge exists but runs {asia.get('direction')} "
                                f"where the mechanism requires {ch['expected']}. A relationship "
                                f"with the wrong sign contradicts the claim rather than failing "
                                f"to support it.")})
        elif asia.get("verdict") == "UNMEASURED":
            rec.update({"verdict": "UNMEASURED",
                        "why": f"only {asia.get('n')} aligned Asia-hours observations"})
        else:
            rec.update({"verdict": "NO_EDGE",
                        "why": ("measured and not found: the falsifier fired. Recorded so the "
                                "graph cannot quietly keep only its successes.")})
        rows.append(rec)
        if time.monotonic() - started > budget_s:
            break

    return {"rows": rows, "bars": bars, "meta": meta}


def propose(measured: dict[str, Any], budget_s: float = 600.0) -> list[dict[str, Any]]:
    """Surviving chains -> `family_lead_lag` cells at the MEASURED lag. Never at a declared one."""
    import time

    from mt5desk.family_lead_lag import family_lead_lag

    from research import proposer_common as pc

    started = time.monotonic()
    bars, meta = measured["bars"], measured["meta"]
    out: list[dict[str, Any]] = []
    for rec in measured["rows"]:
        if rec.get("verdict") not in ("TRANSMISSION", "SHARED_FACTOR"):
            continue
        if time.monotonic() - started > budget_s:
            break
        d, t = str(rec["driver"]), str(rec["target"])
        e = rec["asia_hours"]
        tgt = bars.get(t)
        drv = bars.get(d)
        if tgt is None or drv is None:
            continue
        cost = pc.cost_frac(t, meta, tgt["close"])
        if cost is None:
            continue
        unf = pc.artifact_hours(tgt)
        for z in ENTRY_Z:
            for h in HOLDS:
                params = {"driver_symbol": d, "lag": int(e.get("lag") or 1),
                          "direction": e.get("direction"), "entry_z": z, "norm": 240,
                          "hold_bars": h}
                sig = family_lead_lag(tgt, driver=drv, **params)
                sc = pc.screen(tgt, sig, cost, unf)
                if sc is None:
                    continue
                out.append({"cell": f"{t}.lead_lag.{d}.asia", "symbol": t, "params": params,
                            "chain": rec["name"], "edge_t": e.get("t"),
                            "verdict": rec["verdict"], **sc})
    return pc.deflate(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--propose", action="store_true", help="donate the surviving cells")
    ap.add_argument("--budget", type=float, default=600.0)
    args = ap.parse_args(argv)

    from research import proposer_common as pc

    measured = measure(budget_s=args.budget)
    rows = measured["rows"]
    proposals: list[dict[str, Any]] = []
    donated: str | None = None
    if args.propose:
        proposals = pc.best_per_cell(propose(measured, budget_s=args.budget))
        cands = [pc.candidate("asia_transmission", p["symbol"], "lead_lag", p["params"],
                              next((c["rationale"] for c in CHAINS if c["name"] == p["chain"]),
                                   "declared Asian transmission chain"))
                 for p in proposals]
        if cands:
            path = pc.donate("asia_transmission", cands, tests_run=len(CHAINS) * len(ENTRY_Z)
                             * len(HOLDS))
            donated = str(path) if path else None

    census = Counter(str(r.get("verdict")) for r in rows)
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("the graph GENERATES hypotheses and is never itself evidence. Every declared "
                 "chain carries a falsifier, is measured before anything is proposed, and a "
                 "chain that fails is written down as NO_EDGE or REFUTED rather than dropped."),
        "asia_hours_utc": list(ASIA_HOURS),
        "n_chains": len(CHAINS),
        "census": dict(census),
        "targets_empty_cluster": "cross_asset_lead_lag, one of the 11 clusters EFFECTIVE_BREADTH "
                                 "measures as empty in both the traded and certified books",
        "n_proposals": len(proposals),
        "donated_to": donated,
        "chains": rows,
        "proposals": proposals,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")

    print(f"asia transmission: {len(CHAINS)} declared chain(s) -> {dict(census)}")
    for r in rows:
        a = r.get("asia_hours") or {}
        p = r.get("pooled") or {}
        print(f"  {str(r['name'])[:30]:30} {r['verdict']!s:14} "
              f"asia t={a.get('t', 0)!s:>6} lag={a.get('lag', 0)!s:>3} "
              f"pooled t={p.get('t', 0)!s:>6}  {r['driver']!s}->{r['target']!s}")
    if proposals:
        print(f"  {len(proposals)} cell(s) proposed -> {donated}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
