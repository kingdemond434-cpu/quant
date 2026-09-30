"""Every publicly described hedge-fund mechanism, as a deterministic hypothesis card with a grade.

WHAT THIS IS. A corpus of the mechanisms Bridgewater, AQR, Man AHL, Cubist, Citadel and
Renaissance have described in public -- statements, papers, interviews, testimony -- plus the
lower-grade social claims about them, each written down as something this desk can TEST: a
family the desk has, parameters, the instruments it applies to, the economic argument, and an
evidence grade. Cards whose family exists are donated to the miner contract as EXACT_RECIPE rows
and face the ten gates. Cards whose family does not exist yet go to the deepening queue with the
source text, so the research brains work them rather than forget them.

WHAT THE GRADE MEANS, and what it does NOT. A is the firm's own words; B is reputable reporting
or book-derived; C is social media, ex-employee hearsay, or inference. The grade is carried on the
card and on the candidate. It changes NOTHING about how the gauntlet treats the cell -- a C-grade
rumour that certifies is certified, an A-grade statement that fails is failed. The grade exists
so a later reader knows what kind of prior produced the hypothesis, which is the difference
between a research record and a pile of guesses.

NOT A SECOND DOOR. Cards are miner rows. `miner_candidate_compiler` admits or routes them by the
same rules as every other source, and `hypothesis_graph` records each with the fund and the
claim as its parent, so the lineage from a public statement to a certificate (or a grave) is
explicit.

WHAT IS DELIBERATELY NOT HERE. Anything requiring data the desk has no route to -- fundamental
equity data, rates curves for countries whose bonds Fusion does not offer, order-book depth --
is a card with `blocked_on` filled in, routed to the prospector rather than pretended.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

SOURCE = "fund_playbook"
OUT = BASE / "data" / "intelligence" / SOURCE
REPORT = BASE / "reports" / "FUND_PLAYBOOK.json"
MEDALLION_REPORT = BASE / "reports" / "MEDALLION_PUBLIC_CORPUS.json"
MEDALLION_COVERAGE = BASE / "reports" / "MEDALLION_COVERAGE.json"
PUBLIC_METHOD_COVERAGE = BASE / "reports" / "PUBLIC_QUANT_METHOD_COVERAGE.json"

A, B, C = "A", "B", "C"

SENATE_2014_STATEMENT = (
    "https://www.hsgac.senate.gov/wp-content/uploads/imo/media/doc/"
    "STMT%20-%20Renaissance%20%28July%2022%202014%292.pdf"
)
SENATE_2014_REPORT = (
    "https://www.hsgac.senate.gov/wp-content/uploads/imo/media/doc/"
    "REPORT-Abuse%20of%20Structured%20Financial%20Products%20%28Basket%20Options%29%20"
    "%287-22-14%2C%20updated%209-30-14%29.pdf"
)
SIMONS_2008_TESTIMONY = (
    "https://www.govinfo.gov/content/pkg/CHRG-110hhrg56582/pdf/CHRG-110hhrg56582.pdf"
)

# These are explicit specialisations of organs the desk already owns.  They make the six final
# Medallion frontier laws inspectable without creating a second crawler, graph, ensemble, or
# scheduler.  A missing owner is a wiring defect and is tested below.
MEDALLION_FRONTIER_LAWS = {
    "autonomous_data_edge_discovery": "desks/mt5/research/data_prospector.py",
    "surprise_relative_to_expectations": "desks/mt5/research/event_surprise.py",
    "dynamic_directed_cross_asset_graph": "desks/mt5/research/cross_asset_graph.py",
    "whole_book_residual_search": "desks/mt5/research/factor_residual_engine.py",
    "source_representation_execution_search": "desks/mt5/research/coverage_tensor.py",
    "missing_dimension_meta_research": "desks/mt5/research/unknown_unknowns.py",
}

# Publicly reported METHOD classes map to canonical owners.  This is deliberately a wiring map,
# not a claim that the desk owns Renaissance's private implementation or signals.
MEDALLION_METHOD_OWNERS = {
    "many_weak_signals_one_frozen_model": (
        "desks/mt5/research/weak_signal_compiler.py",
        "desks/mt5/mt5desk/family_ensemble.py",
    ),
    "latent_regimes_and_online_state_probabilities": (
        "libs/regime/hmm.py",
        "desks/mt5/research/regime_router.py",
    ),
    "factor_neutral_residual_reversion": (
        "desks/mt5/research/factor_residual_engine.py",
        "desks/mt5/research/cross_asset_graph.py",
    ),
    "forced_flow_and_calendar_effects": (
        "desks/mt5/research/actor_atlas.py",
        "desks/mt5/research/actor_pressure.py",
    ),
    "nonlinear_representation_search": (
        "desks/mt5/research/representation_discovery.py",
    ),
    "rare_state_smoothing_and_maximum_entropy": (
        "desks/mt5/research/weak_signal_compiler.py",
        "desks/mt5/research/representation_discovery.py",
    ),
    "point_in_time_clean_history": (
        "libs/data/quality.py",
        "libs/data/pit_certificate.py",
        "desks/mt5/research/pit_audit.py",
    ),
    "cost_impact_and_capacity_gating": (
        "desks/mt5/research/cost_truth.py",
        "desks/mt5/research/capacity.py",
        "libs/execution/digital_twin.py",
    ),
    "portfolio_kelly_on_combined_forecasts": (
        "libs/portfolio/kelly_surface.py",
        "libs/portfolio/posterior_growth.py",
    ),
    "independent_bets_and_breadth_conditioned_heat": (
        "desks/mt5/research/independence_intake.py",
        "libs/portfolio/posterior_growth.py",
    ),
    "joint_intraday_cost_aware_sizing": (
        "libs/portfolio/optimize.py",
        "desks/mt5/research/cost_truth.py",
    ),
    "cross_source_data_quality": (
        "libs/data/quality.py",
        "desks/mt5/research/fetch_dukascopy.py",
        "desks/mt5/research/pit_audit.py",
    ),
    "session_handoffs_and_ten_segment_week": (
        "desks/mt5/research/actor_pressure.py",
        "desks/mt5/research/axis_proposer.py",
    ),
    "opening_gap_fade_and_stress_reversal": (
        "desks/mt5/research/institutional_cards.py",
        "desks/mt5/research/tail_alpha_search.py",
    ),
    "cluster_residuals_with_correlation_regime_guard": (
        "desks/mt5/research/factor_residual_engine.py",
        "desks/mt5/research/cross_asset_graph.py",
    ),
    "m5_intraday_research_lane": (
        "desks/mt5/research/chart_allocator.py",
        "desks/mt5/research/counterfactual_timeframes.py",
    ),
    "weekday_weekend_effects_with_stability_falsifiers": (
        "desks/mt5/research/axis_proposer.py",
        "desks/mt5/research/falsifier_run.py",
    ),
    "report_only_crowding_monitor": (
        "desks/mt5/research/crowding_miner.py",
        "libs/research/crowding_hazard.py",
    ),
    "graduated_nonintuitive_signal_admission": (
        "desks/mt5/research/fast_admission.py",
        "libs/research/marginal_admission.py",
    ),
}

PUBLIC_METHOD_OWNERS = {
    "Renaissance|weak_signal_combination_regimes_flows_costs": (
        "desks/mt5/research/weak_signal_compiler.py", "libs/regime/hmm.py",
        "desks/mt5/research/actor_pressure.py", "desks/mt5/research/cost_truth.py"),
    "Bridgewater|macro_surprise_quadrants_risk_balance": (
        "desks/mt5/research/macro_state_engine.py", "libs/portfolio/risk_parity.py"),
    "DE_Shaw|relative_value_residuals_cost_optimal_execution": (
        "desks/mt5/research/factor_residual_engine.py",
        "desks/mt5/research/cost_truth.py"),
    "Two_Sigma|feature_store_pit_walk_forward_research_platform": (
        "libs/data/feature_store.py", "libs/data/pit_certificate.py",
        "desks/mt5/research/representation_discovery.py"),
    "AQR|value_momentum_carry_defensive": (
        "desks/mt5/research/institutional_cards.py",
        "desks/mt5/research/curve_strategy_screen.py"),
    "Man_AHL_Winton|multi_speed_trend_vol_target": (
        "desks/mt5/research/trend_core.py", "libs/risk/vol_target.py"),
    "Citadel_Millennium|marginal_growth_allocation_risk_budgets": (
        "libs/research/marginal_admission.py", "libs/portfolio/posterior_growth.py"),
    "public_data|dukascopy_and_venue_tick_truth": (
        "desks/mt5/research/fetch_dukascopy.py",
        "desks/mt5/research/dukascopy_backfill.py",
        "desks/mt5/research/cost_truth.py"),
    "volatility_risk_premium|vol_curve_as_state": (
        "desks/mt5/research/curve_strategy_screen.py",
        "desks/mt5/research/tail_alpha_search.py"),
    "event_news_surprise|actual_minus_consensus_and_reaction": (
        "desks/mt5/research/event_surprise.py",
        "desks/mt5/research/event_response_atlas.py",
        "desks/mt5/research/news_event_stream.py"),
    "term_structure_roll|curves_and_swap_proxies": (
        "desks/mt5/research/fetch_futures_curves.py",
        "desks/mt5/research/curve_strategy_screen.py"),
    "seasonality|calendar_and_physical_cycles": (
        "desks/mt5/research/actor_pressure.py", "desks/mt5/research/axis_proposer.py"),
    "tail_hedging_convexity|portfolio_crash_protection": (
        "desks/mt5/research/tail_alpha_search.py", "libs/discovery/tail_risk.py"),
    "capacity_decay|measure_then_retire": (
        "desks/mt5/research/capacity.py", "desks/mt5/research/decay_monitor.py"),
    "peer_review_and_full_test_trail": (
        "desks/mt5/research/blind_reviewer.py", "libs/research/hypothesis_graph.py",
        "libs/research/review_rubric.py"),
}


def _m(claim_id: str, grade: str, claim: str, *, state: str, currentness: str,
       source: str, source_id: str, disposition: str, falsifier: str, **kwargs: object) -> dict:
    """One Medallion public-evidence claim, never a prestige shortcut."""
    return {"claim_id": claim_id, "fund": "Renaissance", "grade": grade, "claim": claim,
            "claim_state": state, "currentness": currentness, "source_url": source,
            "canonical_source_id": source_id, "disposition": disposition,
            "falsifier": falsifier, **kwargs}


MEDALLION_CARDS: list[dict] = [
    _m("rt_many_weak_predictions", A,
       "predictions profitable only slightly more often than not; recommendation breadth and "
       "aggregation reduce outcome variance", state="DIRECT_CONFIRMED_METHOD",
       currentness="HISTORICAL_ONLY", source=SENATE_2014_STATEMENT,
       source_id="HSGAC-2014-RENTEC-STATEMENT", disposition="IMPLEMENTED",
       falsifier="weak_signal_compiler fails to beat its best member on untouched OOS data",
       family="ensemble", symbols=[], params={},
       note="owned by weak_signal_compiler + family_ensemble; no duplicate cell donation"),
    _m("rt_balanced_relative_book", A,
       "balanced long/short country books and relative recent-winner/loser effects",
       state="DIRECT_CONFIRMED_HISTORICAL_STRATEGY", currentness="HISTORICAL_ONLY",
       source=SIMONS_2008_TESTIMONY, source_id="US-HOUSE-2008-SIMONS",
       disposition="GENERATING",
       falsifier="index residual ranks have no positive net OOS expectancy after full costs",
       family="cross_asset_residual", symbols=["NAS100", "US30", "GER40", "UK100", "JPN225"],
       params={"factor_symbols": ["US500"], "lookback": 120, "beta_win": 120,
               "entry_z": 2.0, "ttl_bars": 48, "side_mode": "revert"},
       why="MT5 ANALOGUE: remove the global index factor, then test reversion in the residual; "
           "single-name statistical mining remains excluded by mandate"),
    _m("rt_liquid_global_systematic", A,
       "computer-generated systematic trading across liquid global stocks, bonds, currencies "
       "and commodities", state="DIRECT_CONFIRMED_METHOD", currentness="HISTORICAL_ONLY",
       source=SIMONS_2008_TESTIMONY, source_id="US-HOUSE-2008-SIMONS",
       disposition="GENERATING", falsifier="multi-asset trend descendants add no independent "
       "OOS value beyond the current book", family="multi_speed_trend",
       symbols=["EURUSD", "USDJPY", "XAUUSD", "XAGUSD", "XBRUSD", "US500", "UST10Y"],
       params={"speeds": [5, 10, 21, 63, 126, 252], "hold_days": 5,
               "min_agreement": 0.6},
       why="persistent hedging and slow institutional repositioning can create trends across "
           "otherwise unrelated liquid markets"),
    _m("rt_public_information_inputs", A,
       "models consumed public news, analyst, energy, crop, weather, filing, accounting, quote "
       "and trade information", state="DIRECT_CONFIRMED_INPUT", currentness="HISTORICAL_ONLY",
       source=SENATE_2014_STATEMENT, source_id="HSGAC-2014-RENTEC-STATEMENT",
       disposition="GENERATING", falsifier="PIT public-information descendants add no OOS "
       "information after novelty residualisation", family="event_reaction",
       symbols=["XAUUSD", "XBRUSD", "XTIUSD", "CORN", "WHEAT", "SUGAR"],
       params={"input_source": "public_information_surprise"},
       blocked_on="PIT actual/expectation ledgers for each report family",
       why="the tradeable object is information arrival relative to the market's prior, not the "
           "raw level or the source's prestige"),
    _m("rt_quotes_and_trades", A,
       "quotes and trades from markets around the world were model inputs",
       state="DIRECT_CONFIRMED_INPUT", currentness="HISTORICAL_ONLY",
       source=SENATE_2014_STATEMENT, source_id="HSGAC-2014-RENTEC-STATEMENT",
       disposition="GENERATING", falsifier="Fusion tick imbalance has no net OOS edge after "
       "spread, commission and latency", family="orderflow_imbalance",
       symbols=["XAUUSD", "EURUSD", "USDJPY", "US500", "XBRUSD"],
       params={"input_source": "fusion_tick_tape"},
       why="aggressive quote/trade imbalance measures short-lived informed or forced flow; the "
           "Fusion tape is a broker proxy, not a centralized book"),
    _m("rt_high_turnover", A,
       "very high recommendation and trade turnover was critical to the historical strategy",
       state="DIRECT_CONFIRMED_HISTORICAL_STRATEGY", currentness="HISTORICAL_ONLY",
       source=SENATE_2014_REPORT, source_id="HSGAC-2014-BASKET-OPTIONS-REPORT",
       disposition="RESEARCH_ONLY", falsifier="effective independent bets do not increase after "
       "costs when holding horizons shorten", family=None, symbols=[], params={},
       note="turnover is an outcome to measure, never a target or permission to overtrade"),
    _m("rt_short_lived_temporal", B,
       "short-lived temporal anomalies were repeatedly re-estimated intraday",
       state="STRONG_SECONDARY_REPORT", currentness="HISTORICAL_ONLY", source="",
       source_id="ZUCKERMAN-2019-RECONSTRUCTION", disposition="GENERATING",
       falsifier="clock-shift and day-label placebos match or beat the measured effect",
       family="clock_transition", symbols=["XAUUSD", "EURUSD", "US500", "XBRUSD"],
       params={"label": "session_transition", "stamp_hour": None, "mode": "fade", "side": 1,
               "lead_bars": 1, "hold_bars": 2},
       blocked_on="stamp hour must be resolved by plumbing_miner for each venue clock",
       why="scheduled inventory transfer and liquidity changes can produce repeatable transition "
           "effects; the clock relabel is the required null"),
    _m("rt_cross_market_information", B,
       "a broad multi-market system can use one liquid market's state to predict another",
       state="INFERENCE", currentness="UNKNOWN", source=SENATE_2014_STATEMENT,
       source_id="HSGAC-2014-RENTEC-STATEMENT", disposition="GENERATING",
       falsifier="driver-target directionality vanishes under lag reversal and block bootstrap",
       family="lead_lag", symbols=["XAUUSD", "USDJPY", "AUDUSD", "XBRUSD", "US500"],
       params={"driver_symbol": "USDX", "lag_bars": 1, "threshold_z": 1.5,
               "ttl_bars": 4, "side_mode": "continue"},
       why="information reprices the most liquid driver first and transmits to exposed markets; "
           "the directed edge must survive common-factor controls"),
    _m("rt_turbulence_conditioning", B,
       "predictor strength changed with turbulence and market state",
       state="FORMER_EMPLOYEE_PUBLIC_STATEMENT", currentness="UNKNOWN", source="",
       source_id="PUBLIC-INTERVIEW-TURBULENCE", disposition="GENERATING",
       falsifier="state-conditioned rules fail to beat the unconditional preregistered control",
       family="vol_transition", symbols=["XAUUSD", "EURUSD", "US500", "XBRUSD", "UST10Y"],
       params={"window": 63, "fast_window": 10, "high_q": 0.8, "low_q": 0.2,
               "ttl_bars": 12},
       why="volatility transitions change risk-bearing capacity and forced-flow intensity; the "
           "regime is frozen before OOS evaluation"),
    _m("rt_external_managers_as_instruments", A,
       "outside manager return streams were historically modeled as instruments and beta hedged",
       state="DIRECT_CONFIRMED_HISTORICAL_STRATEGY", currentness="HISTORICAL_ONLY", source="",
       source_id="SIMONS-PUBLIC-MANAGER-PORTFOLIO", disposition="BLOCKED_ON_DATA",
       falsifier="PIT public strategy streams have no stable conditional predictability after "
       "fees and selection-bias controls", family=None, symbols=[], params={},
       blocked_on="survivorship-safe PIT public manager/strategy return streams",
       why="model the behavior and regimes of public strategies, never copy a manager's claim"),
]

#: Each card: who, what they said (paraphrased), the grade, and how this desk states it.
#: `family`/`params`/`symbols` make it executable; `blocked_on` names the missing input instead.
CARDS: list[dict] = [
    *MEDALLION_CARDS,
    # ---------------------------------------------------------------- Bridgewater
    {"fund": "Bridgewater", "grade": A, "claim": "trade growth/inflation SURPRISES relative to "
     "what is discounted, not levels", "family": "event_reaction",
     "symbols": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US500"],
     "params": {"input_source": "ff_calendar_vintage"},
     "blocked_on": "calendar ACTUAL prints (surprise = actual - forecast is uncomputable)",
     "why": "the desk's calendar carries forecast and previous but no actual"},
    {"fund": "Bridgewater", "grade": A, "claim": "cross-country divergence in policy and "
     "conditions creates relative-value FX/rates trades",
     "family": "cross_asset_residual", "symbols": ["EURGBP", "EURJPY", "GBPJPY", "AUDNZD",
     "EURCHF", "AUDCAD", "NZDCAD", "EURAUD", "GBPAUD"],
     "params": {"factor_symbols": ["USDX"], "lookback": 240, "beta_win": 240, "entry_z": 2.0,
                "ttl_bars": 72, "side_mode": "revert"},
     "why": "strip the dollar; the residual of a cross is the two countries' relative state"},
    {"fund": "Bridgewater", "grade": A, "claim": "real-yield / gold relationship; asset-yield "
     "vs cash-rate equilibrium gap", "family": "cross_asset_residual",
     "symbols": ["XAUUSD", "XAGUSD"],
     "params": {"factor_symbols": ["USDX", "UST10Y"], "lookback": 240, "beta_win": 240,
                "entry_z": 2.0, "ttl_bars": 72, "side_mode": "revert"},
     "why": "gold as a zero-coupon real asset priced off the real rate it forgoes"},
    {"fund": "Bridgewater", "grade": A, "claim": "risk-balance exposures so no one macro factor "
     "dominates", "family": None, "symbols": [], "params": {},
     "note": "this is the allocator's factor_k_eff bound (PR #10), already enforced"},
    {"fund": "Bridgewater", "grade": B, "claim": "policy -> liquidity/credit -> spending -> "
     "inflation/growth -> rates -> FX transmission chain", "family": "macro_conditional",
     "symbols": ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD"],
     "params": {"input_source": "fred:macro", "transform": "trailing_pct_rank",
                "publication_lag_d": 45},
     "why": "condition FX direction on the macro impulse's percentile rank, lagged for publication"},
    {"fund": "Bridgewater", "grade": B, "claim": "real-exchange-rate disequilibrium mean-reverts "
     "over long horizons", "family": None, "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
     "blocked_on": "CPI series per country (FRED/ECB/ONS) to build real exchange rates",
     "why": "PPP deviation as a slow-reverting state"},
    # ---------------------------------------------------------------- AQR
    {"fund": "AQR", "grade": A, "claim": "time-series momentum across asset classes "
     "(Moskowitz-Ooi-Pedersen)", "family": "multi_speed_trend",
     "symbols": ["XAUUSD", "EURUSD", "USDJPY", "GBPUSD", "US500", "NAS100", "XBRUSD", "AUDUSD"],
     "params": {"speeds": [10, 21, 63, 126, 252], "hold_days": 5, "min_agreement": 0.6},
     "why": "sign of trailing return, vol-scaled, ensemble of speeds"},
    {"fund": "AQR", "grade": A, "claim": "carry across asset classes", "family": "carry",
     "symbols": ["AUDJPY", "NZDJPY", "USDTRY", "USDZAR", "USDMXN", "EURTRY", "GBPJPY"],
     "params": {"input_symbol": None},
     "why": "broker swap differential is a directly measured carry premium"},
    {"fund": "AQR", "grade": A, "claim": "naive factor timing deteriorates after lags and costs",
     "family": None, "symbols": [], "params": {},
     "note": "a NEGATIVE card: multi_speed_trend does not time itself, by design"},
    {"fund": "AQR", "grade": A, "claim": "betting-against-beta / defensive: low-beta assets "
     "outperform per unit of risk", "family": None, "symbols": [], "params": {},
     "note": "single-name statistical mining is excluded; retain as a public factor prior for "
             "the event-only equity lane and cross-asset style-premia research"},
    # ---------------------------------------------------------------- Man AHL
    {"fund": "Man AHL", "grade": A, "claim": "multi-speed trend; fastest speeds carry the crisis "
     "alpha", "family": "multi_speed_trend",
     "symbols": ["US500", "NAS100", "GER40", "JPN225", "XAUUSD", "USDJPY"],
     "params": {"speeds": [5, 10, 21, 63], "hold_days": 3, "min_agreement": 0.5,
                "crisis_only": True},
     "why": "enter only at the turn where the fast speed disagrees with the slow: crisis alpha"},
    {"fund": "Man AHL", "grade": A, "claim": "breadth: trade hundreds of markets", "family": None,
     "symbols": [], "params": {}, "note": "the 251-instrument universe and economic_drivers map"},
    # ---------------------------------------------------------------- Cubist / Citadel
    {"fund": "Cubist", "grade": A, "claim": "mid-frequency anomalies from price-volume + "
     "order-book + alternative data, feature-combined", "family": "orderflow_imbalance",
     "symbols": ["XAUUSD", "EURUSD", "USDJPY"], "params": {"input_source": "fusion_tick_tape"},
     "why": "tick-derived flow imbalance as the price-volume anomaly the desk can measure"},
    {"fund": "Citadel", "grade": A, "claim": "observe -> precise hypothesis -> test -> scale "
     "only on evidence", "family": None, "symbols": [], "params": {},
     "note": "the ten-gate gauntlet and the promoter's forward evidence are this process"},
    # ---------------------------------------------------------------- Social / unverified
    {"fund": "social", "grade": C, "claim": "Medallion uses hidden Markov models / regime "
     "switching as the core", "family": "regime_transition",
     "symbols": ["XAUUSD", "EURUSD", "USDJPY"],
     "params": {"window": 750, "refit_days": 250, "horizon_days": 1, "entry_p_leave": 0.25,
                "min_age": 5, "side_mode": "exhaustion"},
     "why": "if the claim has any content, it is that regime ENDINGS are tradeable"},
    {"fund": "social", "grade": C, "claim": "leverage ~12.5x, sometimes 20x", "family": None,
     "symbols": [], "params": {}, "note": "not a hypothesis; never a sizing target"},
]


def executable(card: dict) -> bool:
    return bool(card.get("family")) and not card.get("blocked_on") and bool(card.get("symbols"))


def rows() -> tuple[list[dict], list[dict], list[dict]]:
    """(donatable rows, deepening rows, informational cards)."""
    try:
        from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
        known = set(ORTHOGONAL_FAMILIES) | {"session_range_breakout", "discovered"}
    except Exception:                                            # noqa: BLE001
        known = set()
    donate, deepen, info = [], [], []
    for c in CARDS:
        base = {"source": SOURCE, "kind": "fund_claim", "fund": c["fund"],
                "evidence_grade": c["grade"], "title": f"{c['fund']} [{c['grade']}]: {c['claim'][:90]}",
                "text": c["claim"], "url": c.get("source_url") or "",
                "claim_id": c.get("claim_id"),
                "canonical_source_id": c.get("canonical_source_id"),
                "claim_state": c.get("claim_state"), "currentness": c.get("currentness"),
                "disposition": c.get("disposition"), "falsifier": c.get("falsifier"),
                "mechanism": c.get("why") or c.get("note") or "",
                "found_at": datetime.now(tz=UTC).isoformat()}
        # A public claim that merely describes an owned desk capability (for example the
        # weak-signal ensemble) is evidence/coverage, not a zero-symbol candidate.
        if not c.get("family") or not c.get("symbols"):
            info.append({**base, "note": c.get("note"), "blocked_on": c.get("blocked_on")})
            continue
        if c.get("blocked_on"):
            deepen.append({**base, "family": c["family"], "symbols": c["symbols"],
                           "params": c.get("params") or {}, "blocked_on": c["blocked_on"]})
            continue
        if c["family"] not in known:
            deepen.append({**base, "family": c["family"], "symbols": c["symbols"],
                           "params": c.get("params") or {},
                           "blocked_on": f"family {c['family']} not registered here"})
            continue
        for sym in c["symbols"]:
            params = dict(c.get("params") or {})
            if c["family"] == "carry":
                params["input_symbol"] = sym
            if c["family"] == "clock_transition" and params.get("stamp_hour") is None:
                # The plumbing miner owns the offset; a card cannot know the stamp hour. It is
                # routed to deepening with the label so the miner's own sweep covers it.
                deepen.append({**base, "family": c["family"], "symbols": [sym], "params": params,
                               "blocked_on": "stamp hour resolved by plumbing_miner, not by a card"})
                break
            donate.append({**base, "symbol": sym, "symbols": [sym], "family": c["family"],
                           "params": params})
    return donate, deepen, info


def run() -> dict:
    donate, deepen, info = rows()
    try:
        from libs.data.pit import stamp as _pit_stamp
        donate = [_pit_stamp(r, SOURCE) for r in donate]
        deepen = [_pit_stamp(r, SOURCE) for r in deepen]
    except Exception:                                            # noqa: BLE001
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M")
    path = OUT / f"discoveries_{stamp}.json"
    path.write_text(json.dumps({"source": SOURCE, "generated_at": datetime.now(tz=UTC).isoformat(),
                                "discoveries": donate + deepen}, indent=1, default=str), "utf-8")
    try:
        from libs.research.hypothesis_graph import BORN, Graph, Node
        g = Graph()
        for r in donate:
            g.append(Node(symbol=r["symbol"], family=r["family"], params=r["params"],
                          source=f"{SOURCE}:{r['fund']}:{r['evidence_grade']}",
                          parent=f"{r['fund']}|{r['text'][:60]}", fate=BORN,
                          why=r["mechanism"][:200]))
    except Exception:                                            # noqa: BLE001
        pass
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "cards": len(CARDS),
           "donated_rows": len(donate), "deepening_rows": len(deepen), "informational": len(info),
           "by_grade": {g: sum(1 for c in CARDS if c["grade"] == g) for g in (A, B, C)},
           "by_fund": {f: sum(1 for c in CARDS if c["fund"] == f) for f in
                       sorted({c["fund"] for c in CARDS})},
           "blocked": [{"fund": r["fund"], "claim": r["text"][:80], "on": r["blocked_on"]}
                       for r in deepen], "donated_to": str(path)}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    medallion = {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "scope": "publicly defensible Renaissance/Medallion evidence; never proprietary claims",
        "claims": MEDALLION_CARDS,
        "frontier_laws": MEDALLION_FRONTIER_LAWS,
        "method_owners": MEDALLION_METHOD_OWNERS,
        "promotion_authority": False,
        "canonical_route": "fund_playbook -> miner_candidate_compiler -> canonical gauntlet",
    }
    MEDALLION_REPORT.write_text(json.dumps(medallion, indent=1, default=str), "utf-8")
    med_ids = {c["claim_id"] for c in MEDALLION_CARDS}
    generated = [r for r in donate if r.get("claim_id") in med_ids]
    blocked = [r for r in deepen if r.get("claim_id") in med_ids]
    coverage = {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "claims": len(MEDALLION_CARDS),
        "by_disposition": {d: sum(c["disposition"] == d for c in MEDALLION_CARDS)
                           for d in sorted({c["disposition"] for c in MEDALLION_CARDS})},
        "executable_descendants": len(generated),
        "blocked_descendants": len(blocked),
        "informational_or_owned": sum(not c.get("family") for c in MEDALLION_CARDS),
        "frontier_laws": MEDALLION_FRONTIER_LAWS,
        "method_owners": MEDALLION_METHOD_OWNERS,
        "unowned_frontier_laws": [name for name, rel in MEDALLION_FRONTIER_LAWS.items()
                                  if not (ROOT / rel).exists()],
        "unowned_methods": [name for name, rels in MEDALLION_METHOD_OWNERS.items()
                            if any(not (ROOT / rel).exists() for rel in rels)],
        "terminal_state": "CURRENT_PUBLIC_FRONTIER_EXHAUSTED_NEVER_DONE_FOREVER",
        "rule": "source pedigree changes the prior and provenance, never a gate or capital authority",
    }
    MEDALLION_COVERAGE.write_text(json.dumps(coverage, indent=1, default=str), "utf-8")
    public_methods = {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "scope": "public method classes only; no claim to any firm's private implementation",
        "owners": PUBLIC_METHOD_OWNERS,
        "unowned": [name for name, rels in PUBLIC_METHOD_OWNERS.items()
                    if any(not (ROOT / rel).exists() for rel in rels)],
        "candidate_generator": "desks/mt5/research/institutional_cards.py",
        "canonical_route": "public evidence -> named mechanism -> canonical gauntlet -> forward",
        "single_name_equities": "EVENT_LANE_ONLY",
        "market_making_at_retail_latency": "NON_TRANSFERABLE",
        "terminal_state": "CURRENT_PUBLIC_FRONTIER_EXHAUSTED_NEVER_DONE_FOREVER",
    }
    PUBLIC_METHOD_COVERAGE.write_text(
        json.dumps(public_methods, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"FUND PLAYBOOK  {d['cards']} cards -> {d['donated_rows']} executable rows, "
          f"{d['deepening_rows']} to deepening, {d['informational']} informational")
    print(f"  grades {d['by_grade']}  funds {d['by_fund']}")
    for b in d["blocked"]:
        print(f"  BLOCKED {b['fund']:12s} {b['claim'][:60]:60s} on: {b['on']}")
    print(f"donated: {d['donated_to']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
