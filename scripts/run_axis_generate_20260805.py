#!/usr/bin/env python3
"""Scoped GENERATE run, batch 2, for the 9 stale Bronze axes (clock-saturation duty, 2026-08-05).

The 2026-07-23 batch (scripts/run_axis_generate.py) authored one hypothesis per axis; all of
this file's nine axes were then Stage-A screened on 2026-07-26 (reports/axis_screens/*.json,
175 trials, ZERO survivors) and the gen_done_* clocks were never refreshed, so on 2026-08-05
every one of them reads >7d stale to max_audit.check_clock_saturation. This run pays the duty
again the only honest way: ONE genuinely NEW mechanism per axis -- different mechanism or
construction from batch 1 AND from the 07-26 screen set, never a parameter variant -- scored
through the EV gate with honest priors and routed by the GATE'S OWN verdict. The HONESTY GUARD
governs: most SHOULD fail (base rates); a manufactured survivor is NEGATIVE discovery.

Novelty is checked mechanically before registration: every candidate is scored by
libs.alpha_factory.hypothesis_novelty against batch-1 HYPS, the research agenda queue + dnr,
the research-memory rows of these nine axes and the graveyard table. The gate is advisory
(its recall was measured at 0% on 2026-07-30), so novelty is argued on MECHANISM in each card
and the score is recorded as corroboration, exactly the OLMAR-kill precedent.

Batch-1's two hard-won idempotence rules carry over verbatim: a pre-registration is an ACT and
re-running must not repeat it (agenda dedupe), and a run that registered nothing must not stamp
"done at now" onto any record (NO-CANDIDATES leaves doc, memory and cadence state alone).

Run once: .venv/bin/python scripts/run_axis_generate_20260805.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path("/home/quant/quant-platform")
if not ROOT.exists():
    ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.run_axis_generate import COVERED as BATCH1_COVERED  # noqa: E402
from scripts.run_axis_generate import HYPS as BATCH1_HYPS  # noqa: E402

from libs.alpha_factory.hypothesis_novelty import PriorIdea, hypothesis_novelty  # noqa: E402
from libs.ops.lawful import guard  # noqa: E402
from libs.research.alpha_economics import Idea, ev_score  # noqa: E402

NOW = datetime.now(tz=UTC).isoformat()
AXES = ("cme", "crossasset", "energy", "equity", "etf_flows", "fed", "metal", "mining",
        "wikipedia")
AGENDA = ROOT / "research_agenda.json"
CADENCE = ROOT / "data/cadence_state.json"
DOC = ROOT / "docs/research/axis_generation_20260805.md"
MEMORY_DB = ROOT / "data/sor_research.sqlite"

# ---------------------------------------------------------------------------------------------
# The nine pre-registrations: (axis, name, mechanism (incl. WHO is forced and why they cannot
# stop), construction + concrete falsifier, target/horizon cell, revisit condition, honest Idea).
# Priors respected: difficulty runs price > return sign > macro > volatility, so the two axes
# whose mechanisms honestly allow it (cme, crossasset) target a SPREAD/CARRY quantity rather
# than a return sign; no cross-sectional construction is authored at all because every xsec form
# on these axes was tested and killed 2026-07-26 (POWminusNONMINED, ETHminusBTC, BTCminusALT,
# rel_attention) and a fresh one would need BTC-beta neutralisation it cannot honestly claim to
# add mechanism for. No textbook daily-bar indicator variants. est_sharpe/breadth/orthogonality/
# effort are true priors, not reverse-engineered; the gate decides.
# ---------------------------------------------------------------------------------------------
HYPS: list[tuple[str, str, str, str, str, str, Idea]] = [
    ("cme", "cme_roll_window_spread_pressure",
     "CME monthly expiry FORCES every holder of the dying front contract to roll inside a "
     "compressed calendar window: futures-tracking funds must roll by prospectus on published "
     "dates (holding to cash settlement breaks the exposure mandate) and cash-and-carry shorts "
     "must roll to stay hedged against spot/ETF inventory. Neither can stop -- expiry is "
     "contractual. The forced cohort is net long front, so its roll (sell front / buy next) "
     "should predictably steepen the next-over-front calendar spread through the roll window "
     "and decay after. Batch-1 tested a LEVEL dislocation between the CME anchor and perps; "
     "07-26 tested spread/basis LEVELS and CHANGES as predictors of BTC returns. This targets "
     "the SPREAD PATH around a forced calendar event -- a carry cell, not a return-sign cell.",
     "Construction: event-time panel around each BTC+ETH front expiry (bronze cme per-contract "
     "1d OHLCV + definition expiries): mean change of annualized next-minus-front spread over "
     "days [-5,0] vs the [-10,-6] baseline. Falsify: >=24 historical expiry events plus 3 "
     "forward events (90 fwd days); NW-t of the pre-registered widening <=0 kills, and a mean "
     "move below 2x the round-trip cost of trading the CME calendar spread kills it as "
     "uneconomic even if significant.",
     "target=CME next-minus-front calendar-spread change (carry, direction-agnostic); "
     "horizon=5d event window",
     "REVISIT only if CME crypto OI composition shifts to a structurally forced-long regime "
     "(e.g. futures-ETF AUM regrowth) -- that raises the forced cohort's size, the mechanism's "
     "one free parameter.",
     Idea(name="cme_roll_window_spread_pressure", est_sharpe=0.3, breadth=2, capacity_usd=2e6,
          orthogonality=0.5, effort_h=6.0,
          tags=["funding_family", "crowded_known", "narrow_breadth"])),

    ("crossasset", "bill_yield_carry_hurdle_passthrough",
     "Perp funding equilibrium = risk-free rate + crypto leverage premium. The marginal SUPPLIER "
     "of perp shorts (the basis arbitrageur) prices capital off the front-end rate -- financing "
     "desks charge SOFR-plus by contract -- while the demand side (retail leverage longs) does "
     "not read SOFR at all. When the 3m bill yield moves, the arb's participation hurdle "
     "reprices immediately but arb AUM reallocates on mandate/monthly cycles, so aggregate "
     "funding should follow the bill yield with a multi-week lag. The forced side is the arb: "
     "it cannot supply shorts below its contractual cost of capital. 07-26 tested rates as "
     "predictors of BTC RETURNS; this predicts the FUNDING LEVEL itself -- the desk's one "
     "validated crop -- a carry cell, not a return-sign cell.",
     "Construction: 3m bill yield 60d change (bronze crossasset ust_curve) -> 20d-forward "
     "change in cross-venue median annualized perp funding, sign positive. Falsify: 40 fwd days "
     "joined to the 8y panel; NW-t of the beta <=0 kills; |corr| > 0.6 with the DXY-driver "
     "construction of the already-rejected dollar_strength_funding_dislocation kills it as a "
     "re-labelling.",
     "target=20d change in median perp funding level (carry, direction-agnostic); horizon=20d",
     "REVISIT if a passive read of the desk's own funding archive shows a stable funding-to-"
     "bill-yield beta (no research-hours needed to watch it) -- that moves est_sharpe on "
     "evidence.",
     Idea(name="bill_yield_carry_hurdle_passthrough", est_sharpe=0.3, breadth=8,
          capacity_usd=2e6, orthogonality=0.5, effort_h=6.0,
          tags=["funding_family", "crowded_known"])),

    ("energy", "miner_curtailment_supply_relief",
     "Post-2022 large US miners hold interruptible-power/demand-response contracts: a gas/power "
     "spike triggers CONTRACTUAL curtailment (they are paid to shut off, and the tariff strike "
     "compels it). Curtailment cuts coin production AND replaces coin-sale opex revenue with "
     "grid credits, so the old channel (energy spike -> forced miner selling -> BTC down, the "
     "batch-1 miner_margin_squeeze story, EV-rejected) should INVERT to mild supply RELIEF in "
     "spike weeks. The forced flow is the legacy always-on miner still selling through the "
     "spike to pay fiat opex; the edge claim is that the market prices the OLD regime's supply "
     "pressure while the NEW regime structurally removes it on exactly those days. 07-26 tested "
     "continuous XNG/XTI ret/mom vs returns; this is event-conditional with an era split and a "
     "testable physical precondition.",
     "Construction: XNG 20d z > 2 event weeks post-2023-01 -> BTC forward 5d return vs "
     "unconditional; era-split control 2019-2021 must show the OLD (negative) sign. Falsify: "
     ">=12 spike events incl. 90 fwd days; one-sided t of conditional-minus-unconditional 5d "
     "mean <=0 kills; VOID (not killed, unfishable) if the 14d hashrate response to spikes is "
     "indistinguishable from zero -- the precondition, checked first on bronze mining data.",
     "target=BTC absolute timing return, event-conditional; horizon=5d",
     "REVISIT only if the precondition test finds hashrate DOES respond but the price cell was "
     "underpowered (<12 events) -- then re-ledger at 20 events, never re-fish the same window.",
     Idea(name="miner_curtailment_supply_relief", est_sharpe=0.2, breadth=1, capacity_usd=2e6,
          orthogonality=0.7, effort_h=5.0, tags=["crowded_known", "narrow_breadth"])),

    ("equity", "credit_stress_degross_transmission",
     "LQD-minus-IEF excess return isolates the corporate CREDIT premium from duration. Credit "
     "deterioration tightens financing for levered intermediaries -- prime brokers and margin "
     "desks reprice haircuts off credit indices by policy -- and financed crypto inventory is "
     "the highest-beta position on those books, cut FIRST when haircuts widen. The forced side "
     "is the margin-constrained fund: degrossing under a haircut change is contractual, not "
     "chosen. 07-26 tested the equity axis's beta (QQQ), rotation (XLY/XLP) and duration (TLT) "
     "channels; the FINANCING channel via credit ETFs on the same bronze axis was never "
     "constructed. Batch-1's crypto_equity_leadlag (COIN/MSTR session lead) shares no data or "
     "mechanism with this.",
     "Construction: 5d LQD-minus-IEF excess return (both on bronze equity) -> BTC absolute 5d "
     "forward, sign positive (credit easing -> risk bid). Falsify: 40 fwd days; NW-t of the IC "
     "<=0 kills; residual IC after orthogonalizing to the same-window QQQ shock below half the "
     "raw IC kills it as equity beta re-labelled (the channel 07-26 already killed).",
     "target=BTC absolute timing return; horizon=5d",
     "REVISIT only on a credit-regime break (IG OAS > 200bps era) where the haircut channel "
     "carries observable variance -- the 2023-2026 sample is credit-calm and biases power down.",
     Idea(name="credit_stress_degross_transmission", est_sharpe=0.25, breadth=10,
          capacity_usd=5e6, orthogonality=0.55, effort_h=5.0, tags=["crowded_known"])),

    ("etf_flows", "etf_flow_price_divergence_absorption",
     "Spot-ETF net creations are NON-DISCRETIONARY realized demand: APs must create when the "
     "fund trades rich (arbitrage obligation) and advisor model-portfolio allocations execute "
     "on mandate schedules -- neither can stop. When strong net creations coincide with flat/"
     "down BTC over the same window, a finite discretionary seller is absorbing a mechanical "
     "bid; the mechanical flow persists after the seller exhausts, so the DIVERGENCE state "
     "(flow-price interaction) should predict, where the flow LEVEL alone does not. Batch-1's "
     "etf_flow_pressure was the level/momentum form (EV-rejected, later re-opened); the "
     "divergence construction conditions on the interaction and is the genuinely different "
     "cell. The 07-26 screen could not run at all (22 flow-days < the 51-row floor) -- this "
     "pre-registration is dated NOW so the evidence that accrues is forward.",
     "Construction: divergence state = 5d net-flow z > +1 while 5d BTC return z < 0 (and the "
     "symmetric redemption state) -> BTC absolute 5d forward. NOT SCREENABLE until the farside "
     "history clears 51 rows (22 on disk, ~1/day accruing -> screen executes ~2026-09). "
     "Falsify at screen: 40 fwd days; conditional NW-t <=0 kills; UNDERPOWERED if <8 divergence "
     "events in sample -> re-ledger at 120 rows, never widen the state definition to make "
     "events.",
     "target=BTC absolute timing return, divergence-conditional; horizon=5d",
     "Screen fires the day flow history reaches 51 rows; the pre-registered construction and "
     "thresholds above are frozen now and may not be tuned at screen time.",
     Idea(name="etf_flow_price_divergence_absorption", est_sharpe=0.35, breadth=15,
          capacity_usd=5e6, orthogonality=0.75, effort_h=6.0, tags=["new_orthogonal_data"])),

    ("fed", "tga_announced_path_anticipation",
     "The Treasury PUBLISHES its target end-of-quarter TGA balance in the quarterly refunding "
     "statement: the future reserve drain/injection is ANNOUNCED before it is realized, and "
     "bill issuance then follows mechanically -- Treasury must hit its stated cash balance "
     "(debt-management policy) and primary dealers must absorb the auctions (their PD "
     "obligation). Neither can stop. Every one of the 11 constructions killed on 07-26 measured "
     "REALIZED net-liquidity flow; this is the last standalone form left on the axis: the "
     "announced-but-not-yet-realized gap (anticipation), which realized-flow constructions "
     "cannot contain. Batch-1 pre-committed that when net_liquidity_impulse failed, the axis "
     "would be ledgered exhausted absent a new mechanism class -- this is that class's final "
     "member, scored honestly against a transmission channel measured dead 11 times.",
     "Construction: announced quarter-end TGA target minus current TGA level (bronze fed "
     "TGA_daily + refunding statements, which require new collection) -> BTC absolute 20d. "
     "Falsify: 40 fwd days; NW-t <=0 kills -- and on kill the fed axis is EXHAUSTED per the "
     "batch-1 pre-commitment: no further standalone macro-liquidity forms, re-entry only on a "
     "named new mechanism class (L1.16a).",
     "target=BTC absolute timing return; horizon=20d",
     "None within the macro-liquidity family -- the family's exhaustion is the pre-committed "
     "outcome of this reject. A genuinely new fed-axis mechanism class re-opens the axis.",
     Idea(name="tga_announced_path_anticipation", est_sharpe=0.15, breadth=10, capacity_usd=5e6,
          orthogonality=0.55, effort_h=8.0, tags=["crowded_known"])),

    ("metal", "flight_to_safety_rotation_lag",
     "On flight-to-safety EVENT days (gold 1d z >= +2 while equities fall), mandate-driven "
     "rebalancers -- target-vol and risk-parity programs -- mechanically buy hedges and cut "
     "risk, and their execution is spread over days BY DESIGN (impact schedules, vol-lookback "
     "windows). The mandate is the product: they cannot stop. If BTC carries any share of the "
     "hedge bid, the lagged tail of that rebalancing spills into it over the following days; "
     "if BTC is pure risk, the same lag shows continued de-risking. The event-conditional 5d "
     "response adjudicates the debasement-hedge claim on FORCED-flow evidence. 07-26 tested "
     "only continuous forms (XAU ret/mom, XAU/XAG ratio); batch-1's digital_gold_rotation was "
     "a continuous relative-momentum dominance tilt. Nothing event-conditional has ever been "
     "run on this axis.",
     "Construction: FTS event = XAU 1d z >= +2 AND same-day QQQ return < 0 (bronze metal + "
     "equity) -> BTC absolute forward 5d, pre-registered sign POSITIVE (hedge-rotation claim). "
     "Falsify: >=20 historical events (8y) plus forward events in 90 fwd days; one-sided t of "
     "conditional-minus-unconditional 5d mean <=0 kills the hedge claim; UNDERPOWERED if <12 "
     "events -> ledger, do not loosen the event threshold to manufacture events.",
     "target=BTC absolute timing return, event-conditional; horizon=5d",
     "REVISIT only if the event count reaches 30+ with the sign consistently positive but "
     "underpowered -- more history is the only honest power increase.",
     Idea(name="flight_to_safety_rotation_lag", est_sharpe=0.2, breadth=1, capacity_usd=5e6,
          orthogonality=0.7, effort_h=4.0, tags=["crowded_known", "narrow_breadth"])),

    ("mining", "hashrate_capex_overshoot_fade",
     "Hashrate arriving today embodies ASIC capex committed 6-9 months ago (fabrication, "
     "delivery, racking are physical lags). ACCELERATING hashrate growth is therefore the "
     "delivery wave of capital committed near the PRIOR price peak -- and the miners must "
     "energize it regardless of today's price: hosting is take-or-pay, the rigs are already "
     "paid for, debt is serviced in fiat. Their coin-selling scales with the energized fleet "
     "exactly as network margin compresses -- a late-cycle supply and sentiment marker. FADE "
     "it. Every 07-26 mining construction was a LEVEL or FIRST-DIFFERENCE form (30/60 ribbon "
     "cross, 14d difficulty change, hashprice z); batch-1's hashrate_capitulation reads "
     "DECLINE as a bottom. This reads growth ACCELERATION (second derivative, 90d window) as a "
     "top -- opposite tail, different transform, different horizon.",
     "Construction: z of d(90d log hashrate growth) (bronze mining hash-rate.csv), top decile "
     "-> BTC 20d forward, pre-registered sign NEGATIVE. Falsify: 40 fwd days plus 8y history; "
     "NW-t of the acceleration-to-forward relation >=0 kills (it must be negative); "
     "|corr(acceleration z, 90d price momentum)| > 0.6 kills it as inverse price momentum "
     "re-labelled (price_only in disguise).",
     "target=BTC absolute timing return (fade); horizon=20d",
     "REVISIT only on a structural break in the capex lag (e.g. hosting capacity glut making "
     "energization discretionary) -- that severs the forced-energization premise.",
     Idea(name="hashrate_capex_overshoot_fade", est_sharpe=0.25, breadth=1, capacity_usd=5e6,
          orthogonality=0.6, effort_h=5.0, tags=["crowded_known", "narrow_breadth"])),

    ("wikipedia", "attention_breadth_regime_fade",
     "Cross-ARTICLE attention BREADTH -- how many of the 7 tracked coin articles spike "
     "simultaneously -- measures how WIDE the retail wave is, not how tall one name's spike is. "
     "Attention is FED to the late cohort by ranking/social algorithms that amplify what "
     "already moved, so the cohort's late arrival is mechanical, not chosen: they cannot stop "
     "arriving late, and their buying is earlier holders' exit liquidity. Broad simultaneous "
     "attention should therefore mark distribution at MULTI-WEEK horizon. The graveyard's own "
     "multilingual-attention kill closes daily timing but explicitly leaves 'weekly "
     "conditioning at best' open -- this is that cell. 07-26 tested single-article levels and "
     "pairwise relatives at 1d/5d; batch-1's attention_surge_fade was a per-name xsec fade. "
     "Breadth-across-articles at 20d has never been constructed.",
     "Construction: count of the 7 bronze wikipedia articles with 7d pageview z > 1.5, 20d-"
     "smoothed -> BTC absolute 20d forward, pre-registered sign NEGATIVE (fade broad-attention "
     "regimes). Falsify: 60 fwd days plus full history; NW-t of the negative relation >=0 "
     "kills; de-contamination residual vs trailing 20d return below half the raw IC kills it "
     "as a past-return echo -- and EITHER kill EXHAUSTS the wikipedia attention family at "
     "every horizon (daily was killed 07-26/graveyard; this is the last open cell).",
     "target=BTC absolute timing return (fade); horizon=20d",
     "None within the attention family if killed -- family exhaustion is this card's "
     "pre-committed downside. New articles/languages are parameter variants, not re-openers.",
     Idea(name="attention_breadth_regime_fade", est_sharpe=0.2, breadth=3, capacity_usd=5e6,
          orthogonality=0.8, effort_h=4.0, tags=["crowded_known"])),
]

#: axes already accruing evidence elsewhere would be routed here after artifact verification --
#: NONE this run: the crossasset shadow clock (data/crossasset_shadow_state.json, slot 6/12)
#: accrues the cross-asset REGIME construction, not this batch's funding-passthrough mechanism,
#: so crossasset gets a real generation rather than COVERED bookkeeping.
COVERED: dict[str, str] = {}


def route(results: list[dict[str, Any]], already: set[str]) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Pure routing: split gate-scored results into (queued, rejected, skipped).

    The GATE's own verdict decides -- this function adds no threshold of its own (batch-1's
    NEAR_MISS band predates the 2026-07-31 recalibration to 0.002 and re-adding one below the
    gate's bar would be loosening). ``already`` implements the batch-1 idempotence rule: a
    pre-registration is an act, and re-running must not repeat it.
    """
    queued, rejected, skipped = [], [], []
    for r in results:
        if r["name"] in already:
            skipped.append(r)
        elif str(r["verdict"]).startswith("QUEUE"):
            queued.append(r)
        else:
            rejected.append(r)
    return queued, rejected, skipped


def stamp(cad: dict[str, Any], axes: tuple[str, ...] | list[str], now: str) -> dict[str, Any]:
    """Pure: return a copy of cadence state with gen_done_<axis> set, all other keys kept."""
    out = dict(cad)
    for ax in axes:
        out[f"gen_done_{ax}"] = now
    return out


def _graveyard_priors() -> list[PriorIdea]:
    """Graveyard table rows as novelty priors (row text is the statement; crude but content-rich).
    """
    out: list[PriorIdea] = []
    gy = ROOT / "docs/graveyard.md"
    if not gy.exists():
        return out
    for line in gy.read_text("utf-8", errors="ignore").splitlines():
        if line.startswith("| ") and "---" not in line and line.count("|") >= 4:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0] and cells[0].lower() not in ("hypothesis",
                                                              "hypothesis (external prior)"):
                out.append(PriorIdea(id=f"graveyard:{cells[0][:60]}", statement=line[:800],
                                     lesson=cells[-1][:200] if len(cells) > 3 else None))
    return out


def _memory_priors() -> list[PriorIdea]:
    """research_memory rows touching the nine axes, as novelty priors."""
    out: list[PriorIdea] = []
    if not MEMORY_DB.exists():
        return out
    con = sqlite3.connect(MEMORY_DB)
    con.row_factory = sqlite3.Row
    try:
        rows = list(con.execute(
            "SELECT id, statement, lessons, metrics_json FROM research_memory"))
    finally:
        con.close()
    for r in rows:
        try:
            axis = str(json.loads(r["metrics_json"] or "{}").get("axis", ""))
        except (ValueError, TypeError):
            axis = ""
        if axis in AXES or any(f"{ax} " in str(r["statement"])[:60].lower() for ax in AXES):
            out.append(PriorIdea(id=f"rm:{r['id']}", statement=str(r["statement"])[:800],
                                 lesson=(str(r["lessons"])[:200] if r["lessons"] else None)))
    return out


def _agenda_priors(agenda: dict[str, Any]) -> list[PriorIdea]:
    out: list[PriorIdea] = []
    for q in agenda.get("queue_ranked_by_expected_research_roi", []):
        if isinstance(q, dict):
            out.append(PriorIdea(id=f"queue:{q.get('id')}",
                                 statement=f"{q.get('mechanism', '')} {q.get('construction', '')}"
                                           [:800] or str(q.get("id"))))
    out.extend(PriorIdea(id=f"dnr:{str(e).split(' ', 1)[0]}", statement=str(e)[:800])
               for e in agenda.get("do_not_repeat", []))
    return out


def _batch1_priors() -> list[PriorIdea]:
    out = [PriorIdea(id=f"batch1:{name}", statement=f"{mech} {constr}"[:800])
           for _ax, name, mech, constr, _idea in BATCH1_HYPS]
    out.extend(PriorIdea(id=f"batch1-covered:{ax}", statement=txt[:800])
               for ax, txt in BATCH1_COVERED.items())
    return out


def _log_memory(axis: str, name: str, r: dict[str, Any], cell: str, queued: bool,
                revisit: str) -> None:
    """One research_memory row per authored hypothesis, via the desk CLI (its ledger, its pen)."""
    if queued:
        args = ["--result", "pending",
                "--statement",
                f"PRE-REGISTERED {NOW[:10]} (axis generate batch 2): {name} [{cell}] ev "
                f"{r['ev']} p_survive {r['p_survive']} QUEUE. One DSR-counted trial; "
                f"construction+falsifier frozen in docs/research/axis_generation_20260805.md. "
                f"{revisit[:180]}",
                "--lessons", "Gate decided with honest inputs; the pre-registration date is "
                             "load-bearing under the two-stage law."]
    else:
        args = ["--result", "rejected", "--failure-stage", "screen",
                "--failure-cause", "economics",
                "--statement",
                f"EV-REJECT pre-research {NOW[:10]} (axis generate batch 2): {name} [{cell}] "
                f"ev {r['ev']} p_survive {r['p_survive']} tags {'+'.join(r['tags'])}. Screen-"
                f"level kill, axis stays ingested; full card in "
                f"docs/research/axis_generation_20260805.md.",
                "--lessons", f"REVISIT: {revisit[:400]}"]
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/research_memory.py"), "log",
         "--category", "hypothesis", "--axis", axis, *args],
        cwd=ROOT, check=True, capture_output=True, text=True, timeout=60)


def main() -> None:
    guard()

    agenda = json.loads(AGENDA.read_text("utf-8"))
    priors = (_batch1_priors() + _agenda_priors(agenda) + _memory_priors()
              + _graveyard_priors())
    print(f"novelty priors assembled: {len(priors)} "
          "(batch-1 HYPS + agenda queue/dnr + research_memory axis rows + graveyard table)")

    results, novelty, redundant = [], {}, []
    for axis, name, mech, constr, cell, revisit, idea in HYPS:
        nv = hypothesis_novelty(f"{mech} {constr}", priors=priors)
        novelty[name] = nv
        if nv.is_redundant:
            # DUPLICATE of a prior tested idea -- the novelty gate is advisory, but a >=0.7
            # similarity to something already tried means this card must NOT be registered as
            # new work; say it loudly and leave the axis's clock honestly unstamped.
            redundant.append((axis, name, nv))
            print(f"  {axis:12s} {name:40s} DUPLICATE of {nv.nearest_id} "
                  f"(sim {nv.nearest_similarity:.2f}) -- NOT registered")
            continue
        r = ev_score(idea)
        r["axis"] = axis
        results.append((axis, name, mech, constr, cell, revisit, r))
        print(f"  {axis:12s} {name:40s} ev={r['ev']:<7} p={r['p_survive']:<7} "
              f"novelty={nv.novelty_score:.2f} {r['verdict']}")

    dnr = agenda.setdefault("do_not_repeat", [])
    queue = agenda.setdefault("queue_ranked_by_expected_research_roi", [])
    already = {str(q.get("id")) for q in queue if isinstance(q, dict)}
    already |= {str(e).split(" ", 1)[0] for e in dnr}
    scored = [dict(r, _axis=axis, _mech=mech, _constr=constr, _cell=cell, _revisit=revisit,
                   name=name)
              for axis, name, mech, constr, cell, revisit, r in results]
    queued, rejected, skipped = route(scored, already)

    if not queued and not rejected:
        # Batch-1's rule, kept verbatim in spirit: a run that registered nothing did not
        # generate, and must not stamp today onto any record of a run that did.
        print(f"NO-CANDIDATES: nothing new to pre-register ({len(skipped)} already registered, "
              f"{len(redundant)} DUPLICATE) -- doc, cadence state and research memory LEFT "
              "ALONE.")
        return

    if skipped:
        print(f"already pre-registered, skipped: {[s['name'] for s in skipped]}")

    for r in queued:
        queue.append({"id": r["name"], "axis": r["_axis"], "mechanism": r["_mech"],
                      "construction": r["_constr"], "cell": r["_cell"], "ev": r["ev"],
                      "p_survive": r["p_survive"], "rank": "standard",
                      "novelty": round(novelty[r["name"]].novelty_score, 3),
                      "preregistered": NOW,
                      "decision": "QUEUED by 2026-08-05 axis generate batch 2 (gate verdict at "
                                  "the recalibrated 0.002 bar); screen build -> Stage-A -> slot "
                                  "by EV order"})
    for r in rejected:
        entry = (f"{r['name']} (REJECTED {NOW[:10]} by EV gate: ev {r['ev']}, "
                 f"{'+'.join(r['tags'])}; axis={r['_axis']}; cell={r['_cell']}. "
                 f"{r['_mech'][:120]}... REVISIT: {r['_revisit'][:220]})")
        if not any(str(x).startswith(r["name"]) for x in dnr):
            dnr.append(entry)
    AGENDA.write_text(json.dumps(agenda, indent=1, ensure_ascii=False), "utf-8")

    # cadence_state is SHARED (other organs read-modify-write it too): re-read at the last
    # moment, update only our keys, replace atomically so a concurrent writer never sees a
    # torn file and no other key is dropped.
    stamped_axes = [r["_axis"] for r in queued + rejected + skipped]
    cad = stamp(json.loads(CADENCE.read_text("utf-8")), stamped_axes, NOW)
    tmp = CADENCE.with_suffix(f".json.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(cad, indent=2), "utf-8")
    os.replace(tmp, CADENCE)

    doc_rows = [f"| {r['_axis']} | {r['name']} | {r['ev']} | {r['p_survive']} | "
                f"{round(novelty[r['name']].novelty_score, 3)} | {r['verdict']} |"
                for r in queued + rejected]
    doc = (f"# AXIS PRE-REGISTRATIONS, BATCH 2 -- generate run {NOW[:16]}Z "
           "(clock-saturation duty)\n\n"
           "Nine stale axes (gen_done 2026-07-22, screened-and-killed 2026-07-26, clocks never "
           "refreshed). One genuinely NEW mechanism per axis -- checked against batch-1 HYPS "
           "(scripts/run_axis_generate.py), docs/research/AXIS_PREREGISTRATIONS.md, the "
           "2026-07-26 screen artifacts (reports/axis_screens/*.json), the research agenda "
           "queue/do_not_repeat, research_memory rows for these axes and docs/graveyard.md; "
           "novelty scored mechanically by libs.alpha_factory.hypothesis_novelty (advisory -- "
           "0% measured recall -- so each card also argues novelty on mechanism). EV-gated with "
           "honest inputs at the recalibrated 0.002 bar; the GATE routes, and most SHOULD "
           "fail. **Each card below is ONE pre-registered, DSR-counted trial** (one cell: one "
           "target, one horizon, falsifier frozen at registration).\n\n"
           "Priors respected: direction-agnostic carry/spread targets where the mechanism "
           "honestly allows (cme, crossasset); NO cross-sectional constructions (every xsec "
           "form on these axes died 2026-07-26 and none of these mechanisms adds the BTC-beta-"
           "neutralised breadth an xsec re-entry would demand); no daily-bar indicator "
           "variants.\n\n"
           "| axis | hypothesis | ev | p_survive | novelty | verdict |\n"
           "|---|---|---|---|---|---|\n" + "\n".join(doc_rows) + "\n\n## Full cards\n")
    for r in queued + rejected:
        nv = novelty[r["name"]]
        doc += (f"\n### {r['name']} ({r['_axis']})\n"
                f"- **Mechanism (incl. who is forced to trade against it):** {r['_mech']}\n"
                f"- **Construction / falsifier:** {r['_constr']}\n"
                f"- **Cell (one DSR-counted trial):** {r['_cell']}\n"
                f"- **EV (honest inputs):** {r['ev']} (p_survive {r['p_survive']}, tags "
                f"{r['tags']}) -> **{r['verdict']}**\n"
                f"- **Novelty:** {nv.novelty_score:.3f} (nearest prior: {nv.nearest_id} at "
                f"sim {nv.nearest_similarity:.3f})\n"
                f"- **Route:** "
                f"{'research queue' if str(r['verdict']).startswith('QUEUE') else 'do_not_repeat'}"
                f"; revisit: {r['_revisit']}\n")
    doc += ("\n## Cadence\n"
            f"gen_done_<axis> stamped {NOW} for: {', '.join(sorted(set(stamped_axes)))}. "
            "Recurrence detector: max_audit's check_clock_saturation, which reads the ACCRUAL "
            "stores (data/forward_slots.json for a live clock, the `axis=` trail in "
            "research_agenda.json for a ledgered one) -- never gen_done_<axis>, which is a "
            "one-way presence latch this script deliberately refuses to re-stamp. Generation "
            "stays a judgement call, never cadence-automated (see batch-1's dedupe comment).\n")
    DOC.write_text(doc, "utf-8")

    for r in queued + rejected:
        _log_memory(r["_axis"], r["name"], r, r["_cell"],
                    str(r["verdict"]).startswith("QUEUE"), r["_revisit"])

    print(f"\nqueued: {len(queued)} {[r['name'] for r in queued]}")
    print(f"rejected->dnr: {len(rejected)} | skipped: {len(skipped)} | "
          f"redundant: {len(redundant)}")
    print(f"gen_done stamped for {sorted(set(stamped_axes))}")
    print(f"doc: {DOC.relative_to(ROOT)}; research_memory rows: {len(queued) + len(rejected)}")


if __name__ == "__main__":
    main()
