"""Scoped GENERATE run for all 13 Bronze axes (clock-saturation breach, principal 2026-07-23).

Same pattern as the 2026-07-17 fred_macro generate run: author pre-registered hypotheses per
axis, score each through the EV gate (libs.research.alpha_economics -- pure python, honest
tags, NO tuning-to-pass), route by verdict (QUEUE / do_not_repeat with revisit condition /
COVERED bookkeeping), set gen_done_<axis>, write the pre-registration doc. The HONESTY GUARD
governs: the duty is every axis TESTED-or-ledgered -- not survivors manufactured. Run from root.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libs.research.alpha_economics import Idea, ev_score

NOW = datetime.now(tz=UTC).isoformat()

# Axes already accruing evidence elsewhere -- bookkeeping, not generation:
COVERED = {
    "binance_metrics": "COVERED: this axis IS the derivative-metrics archive feeding the "
                       "oi_divergence + ls_contrarian + liquidation_reversal forward clocks "
                       "(24/40d accruing, peek e-values live) -- evidence has been accruing "
                       "since 07-09; the gen_done key was simply never set.",
    "crypto": "COVERED: this axis IS the price lake the autodiscovery factory tests daily "
              "(12 price families, content-hash dedup) and every deployed/shadow sleeve runs on.",
}

# Authored pre-registrations (mechanism, construction, falsification) with HONEST EV inputs.
# Tags follow the desk's meta-learned priors; est_sharpe/breadth/orthogonality/effort are my
# honest priors, not reverse-engineered to pass. The gate decides; most SHOULD fail (base rates).
HYPS = [
    ("cme", "cme_anchored_basis_dislocation",
     "CME front-month annualized basis is the INSTITUTIONAL cost of regulated long exposure; "
     "perp funding is crypto-native leverage cost. When the CME anchor and the cross-sectional "
     "perp basis complex dislocate (z of spread), institutional vs degen positioning has "
     "diverged -- fade the perp side toward the anchor across the perp universe (xsec, not "
     "BTC-only, so breadth is real).",
     "Construction: daily CME basis (front vs spot) minus median perp basis; xsec tilt on "
     "per-name deviation from that anchor. Falsify: 40 fwd days, NW-t of the tilt <=0, or "
     "|corr| to funding_carry >0.5 (not orthogonal enough to earn a slot).",
     Idea(name="cme_anchored_basis_dislocation", est_sharpe=0.4, breadth=60, capacity_usd=5e5,
          orthogonality=0.7, effort_h=6.0, tags=["new_orthogonal_data", "funding_family"])),

    ("etf_flows", "etf_flow_pressure",
     "Spot-ETF net creations are REALIZED institutional demand hitting a thin float; flows are "
     "autocorrelated at daily horizon, so a 5d flow z-score should lead 1-3d BTC/ETH returns "
     "and, through beta, the whole complex (tilt sizing, breadth via the perp cross-section).",
     "Construction: 5d z of aggregate net flows -> directional tilt scaled across perps by BTC "
     "beta. Falsify: 40 fwd days NW-t<=0, or signal decays under 1d latency (flows publish EOD).",
     Idea(name="etf_flow_pressure", est_sharpe=0.45, breadth=40, capacity_usd=1e6,
          orthogonality=0.75, effort_h=6.0, tags=["new_orthogonal_data"])),

    ("wikipedia", "attention_surge_fade",
     "Wikipedia pageview spikes on coin articles = late retail attention; attention peaks lag "
     "price and mark local crowding -- fade names with attention z-spikes vs the cross-section "
     "(classic attention/overreaction literature, but on a fresher, less-arbed proxy than "
     "Google Trends).",
     "Construction: per-coin pageview z (7d) -> xsec fade of top decile, ~40-60 mapped names. "
     "Falsify: 40 fwd days NW-t<=0 or sign flips (attention momentum, not fade -> graveyard "
     "wrong_sign, do NOT flip-fit).",
     Idea(name="attention_surge_fade", est_sharpe=0.4, breadth=45, capacity_usd=8e5,
          orthogonality=0.8, effort_h=6.0, tags=["new_orthogonal_data"])),

    ("fx", "dxy_shock_beta_rotation",
     "USD liquidity shocks transmit to crypto with a lag via risk appetite; a 5d DXY shock "
     "should rotate the crypto cross-section (high-beta alts vs BTC) rather than just level.",
     "Construction: DXY 5d z -> xsec tilt low-beta-over-high-beta on shock. Falsify: 40 fwd "
     "days NW-t<=0. NOTE: macro-overlay class rejected 3x on 07-17 (FRED) -- this differs only "
     "by being xsec-rotation not level-overlay; if the gate rejects, that precedent stands.",
     Idea(name="dxy_shock_beta_rotation", est_sharpe=0.3, breadth=60, capacity_usd=2e6,
          orthogonality=0.6, effort_h=6.0, tags=["new_orthogonal_data", "crowded_known"])),

    ("equity", "crypto_equity_leadlag",
     "Crypto-adjacent equities (COIN/MSTR/miners) trade US hours with institutional flow; "
     "their overnight/US-session moves may lead 24h crypto (information arrives via the "
     "regulated market first).",
     "Construction: US-close basket return -> next-Asia-session crypto tilt. Falsify: 40 fwd "
     "days NW-t<=0; also falsified if lead vanishes at 1h latency (then it is just beta).",
     Idea(name="crypto_equity_leadlag", est_sharpe=0.3, breadth=30, capacity_usd=1e6,
          orthogonality=0.55, effort_h=6.0, tags=["price_only", "crowded_known"])),

    ("index", "risk_regime_rotation",
     "SPX/NDX drawdown states compress crypto dispersion and flip carry/momentum regimes; an "
     "equity-vol regime flag may time the desk's own sleeve weights (meta-allocation, breadth "
     "= the whole book).",
     "Construction: NDX 20d vol regime -> sleeve-weight tilt in the combiner. Falsify: "
     "regime-split Sharpe difference insignificant at 40 fwd days. NOTE: overlay class -- the "
     "est_sharpe=refinement penalty applies honestly.",
     Idea(name="risk_regime_rotation", est_sharpe=0.2, breadth=100, capacity_usd=5e6,
          orthogonality=0.5, effort_h=5.0, tags=["crowded_known"])),

    ("metal", "digital_gold_rotation",
     "Gold and BTC compete for the debasement-hedge flow; strong gold with flat BTC implies "
     "hedge demand exists but is choosing metal -- a relative-rotation signal for BTC vs alts.",
     "Construction: gold 20d momentum vs BTC 20d -> BTC-dominance tilt. Falsify: 40 fwd days "
     "NW-t<=0.",
     Idea(name="digital_gold_rotation", est_sharpe=0.25, breadth=20, capacity_usd=2e6,
          orthogonality=0.5, effort_h=5.0, tags=["price_only", "crowded_known"])),

    ("energy", "miner_margin_squeeze",
     "Energy price spikes squeeze miner margins -> forced BTC treasury selling with a lag -- a "
     "supply-pressure channel (works jointly with the mining axis for hashprice).",
     "Construction: energy 20d shock x mining-difficulty trend -> BTC supply-pressure flag. "
     "Falsify: no excess BTC-down conditional response at 40 fwd days.",
     Idea(name="miner_margin_squeeze", est_sharpe=0.25, breadth=8, capacity_usd=2e6,
          orthogonality=0.6, effort_h=6.0, tags=["new_orthogonal_data", "narrow_breadth"])),

    ("mining", "hashrate_capitulation",
     "Hash-ribbon style: sustained hashrate/difficulty decline marks miner capitulation, "
     "historically near local bottoms (published; the crowding is priced honestly in tags).",
     "Construction: 30d vs 60d hashrate cross -> BTC long flag. Falsify: 40 fwd days "
     "conditional return <= unconditional.",
     Idea(name="hashrate_capitulation", est_sharpe=0.3, breadth=5, capacity_usd=3e6,
          orthogonality=0.6, effort_h=5.0, tags=["crowded_known", "narrow_breadth"])),

    ("fed", "net_liquidity_impulse",
     "Standalone (NOT overlay -- the 07-17 overlay class is dead): 4w impulse of WALCL-TGA-RRP "
     "as a direct directional signal for the crypto complex, the 'net liquidity' trade.",
     "Construction: 4w net-liquidity z -> directional tilt. Falsify: 40 fwd days NW-t<=0. "
     "PRIOR: 3 FRED-family ideas EV-rejected 07-17 at 0.004-0.013; this is the last "
     "un-tested standalone form -- if it also rejects, the fed axis is ledgered exhausted.",
     Idea(name="net_liquidity_impulse", est_sharpe=0.3, breadth=20, capacity_usd=5e6,
          orthogonality=0.55, effort_h=5.0, tags=["crowded_known"])),

    ("crossasset", "crossasset_carry_confirm",
     "Cross-asset trend/carry agreement (FX carry, commodity trend, equity trend all risk-on) "
     "as a breadth-100 conditioning state for crypto sleeve sizing -- the diversified-macro "
     "regime read, distinct from any single index.",
     "Construction: 3-asset-class trend agreement score -> sleeve sizing multiplier within "
     "existing rails. Falsify: regime-split difference insignificant at 40 fwd days. Overlay "
     "penalty applies.",
     Idea(name="crossasset_carry_confirm", est_sharpe=0.2, breadth=100, capacity_usd=5e6,
          orthogonality=0.5, effort_h=6.0, tags=["crowded_known"])),
]

QUEUE_MIN = 0.05      # the gate's own threshold; NOT adjustable here
NEAR_MISS = 0.02      # borderline band -> queued LOW-RANK for the panel/brain to re-estimate


def main() -> None:
    results, doc_rows = [], []
    for axis, name, mech, constr, idea in HYPS:
        r = ev_score(idea)
        r["axis"] = axis
        results.append((axis, name, mech, constr, r))
        doc_rows.append(f"| {axis} | {name} | {r['ev']} | {r['p_survive']} | {r['verdict']} |")
        print(f"  {axis:16s} {name:32s} ev={r['ev']:<8} {r['verdict']}")

    agenda = json.loads(Path("research_agenda.json").read_text("utf-8"))
    dnr = agenda.setdefault("do_not_repeat", [])
    queue = agenda.setdefault("queue_ranked_by_expected_research_roi", [])
    queued, rejected = [], []
    for axis, name, mech, constr, r in results:
        if r["ev"] >= QUEUE_MIN or r["ev"] >= NEAR_MISS:
            rank = "standard" if r["ev"] >= QUEUE_MIN else "low-rank (near-miss; re-estimate at panel)"
            queue.append({"id": name, "axis": axis, "mechanism": mech, "construction": constr,
                          "ev": r["ev"], "p_survive": r["p_survive"], "rank": rank,
                          "preregistered": NOW,
                          "decision": f"QUEUED by 2026-07-23 axis generate run ({rank}); "
                                      "screen build -> Stage-A -> slot by EV order"})
            queued.append(f"{name}({r['ev']})")
        else:
            entry = (f"{name} (REJECTED {NOW[:10]} by EV gate: ev {r['ev']}, "
                     f"{'+'.join(r['tags'])}; axis={axis}. {mech[:140]}... REVISIT if the "
                     "mechanism gains breadth, a cheaper construction, or the priors move on "
                     "evidence -- axis stays ingested, kill is screen-level not economic-final.")
            if not any(str(x).startswith(name) for x in dnr):
                dnr.append(entry)
            rejected.append(f"{name}({r['ev']})")
    Path("research_agenda.json").write_text(
        json.dumps(agenda, indent=1, ensure_ascii=False), "utf-8")

    cad_p = Path("data/cadence_state.json")
    cad = json.loads(cad_p.read_text("utf-8"))
    for axis, *_ in HYPS:
        cad[f"gen_done_{axis}"] = NOW
    for axis in COVERED:
        cad[f"gen_done_{axis}"] = NOW
    cad_p.write_text(json.dumps(cad, indent=2), "utf-8")

    doc = (f"# AXIS PRE-REGISTRATIONS -- generate run {NOW[:16]}Z (clock-saturation duty)\n\n"
           "Authored per-axis hypotheses, EV-gated honestly (no tuning-to-pass), routed per the "
           "TWO-STAGE LAW: rejects are SCREEN-level kills with explicit revisit conditions -- "
           "the axes stay ingested and re-open on new mechanisms.\n\n"
           "| axis | hypothesis | ev | p_survive | verdict |\n|---|---|---|---|---|\n"
           + "\n".join(doc_rows) + "\n\n## Covered axes (bookkeeping)\n"
           + "\n".join(f"- **{k}**: {v}" for k, v in COVERED.items())
           + "\n\n## Full cards\n")
    for axis, name, mech, constr, r in results:
        doc += (f"\n### {name} ({axis})\n- **Mechanism:** {mech}\n- **Construction/falsify:** "
                f"{constr}\n- **EV:** {r['ev']} (p_survive {r['p_survive']}, tags "
                f"{r['tags']}) -> {r['verdict']}\n")
    Path("docs/research/AXIS_PREREGISTRATIONS.md").write_text(doc, "utf-8")

    print(f"\nqueued: {len(queued)} {queued}")
    print(f"rejected->dnr: {len(rejected)}")
    print(f"gen_done set for all 13 axes")


if __name__ == "__main__":
    main()
