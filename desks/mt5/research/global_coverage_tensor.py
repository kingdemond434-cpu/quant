"""THE GLOBAL COVERAGE TENSOR: every region's sources, mechanisms and markets as ONE explicit
frontier, counted only where a proven path reached a measured outcome (principal, 2026-09-30).

    python desks/mt5/research/global_coverage_tensor.py --once --budget-s 540
    python desks/mt5/research/global_coverage_tensor.py --once --dry-run

WHAT IT EXTENDS, AND WHY IT IS NOT A SECOND TENSOR ENGINE. `libs/research/coverage.py` is the
algebra (sparse store, monotone ladder, EVIG, ratchet) and `coverage_tensor.py` the world/forest
organ. This leg adds the principal's fourteen axes as a third tensor of the SAME algebra
(`coverage.GLOBAL`), stored on the SAME world ladder: the principal's status ladder
(UNEXPLORED -> SOURCED -> INGESTED -> COMPILED -> JUDGED -> CERTIFIED -> FORWARD -> LIVE, with the
terminals FAILED / DUPLICATE / NO_EDGE / NOT_TRADEABLE / BLOCKED_WITH_SUBSTITUTE /
LOW_EV_RETIRED) is a VIEW derived through `coverage.principal_view`, never a parallel store.

CELLS BY MECHANISTIC COMPATIBILITY, NEVER THE LITERAL PRODUCT. Each mechanism declares the source
classes that can carry its evidence, the transmissions through which that evidence reaches an
MT5 instrument class, the horizons and broker-clock sessions it lives in, the regimes it is
conditional on, the dated events and positioning / cross-asset states it needs, and how it is
executed; the participant is `axis_registry.MECHANISM_ACTOR`'s own payer. Every region receives
the SAME template in its own language -- no civilisation is deep while another is an RSS feed.
The literal product is published beside the generated count as `nominal`, so the distinct count
has something to be distinct from; evidence that lands outside the template is ADDED to the
space (the frontier is open-ended), never dropped.

COVERAGE COUNTS ONLY ON A PROVEN PATH:

    source -> acquisition -> PIT store -> extraction -> mechanism -> cell -> docket
           -> gauntlet/conditioner -> measured outcome

A registered source moves its cells to SOURCED and a fetched one to INGESTED -- NOMINAL coverage.
A cell is PROVEN only when every link above is measured for it: the source is registered, it was
acquired, what it serves carries point-in-time stamps, a family mapped to a mechanism, the cell
reached the docket and the gauntlet returned a verdict that IS an outcome (an `observations`
refusal is work not done, L1.28a). Both shares are published; the gap between them is the work.

THE SOURCE REGISTRY IS READ, NEVER OWNED. PR #133 (`libs/mining`, branch
claude/mt5-global-mining-v1) owns the unified registry and its ACTIVE/COLD rule -- ACTIVE only
when one of the source's cells reached EVALUATED within 30 days. When `libs.mining` and
`data/mining/mining.db` are on this tree they are read (read-only sqlite); when absent this organ
falls back to the registries LIVE already holds (the canonical registry's `sources` table,
`deep_forest_sources.json`, the intelligence seats, the hypothesis graph and the gate ledger) and
names every link it could not measure.

PER SOURCE: fetched -> extracted -> compiled -> judged -> survived -> forward -> live, marginal
information gain per compute hour, incremental k_eff (`libs/research/breadth_credit`), ACTIVE /
COLD, and an auto-retire flag raised after ADEQUATE sampling with ZERO novel information.
Retirement means REDIRECT BUDGET: no source is deleted, no scout is stopped (LAWS 5f).

MISSIONS. The emptiest high-EVIG cells become research missions through the path the desk
already consumes -- `coverage_gap` discoveries in the canonical registry and rows under
`data/intelligence/global_coverage/`, which `miner_candidate_compiler` reads and routes to the
deepening worker's `coverage_gap` specialist. Each names the cell and the ONE move that fills it.

BACKPRESSURE. When the desk creates cells faster than it judges them, this organ's OWN mission
emission and its source-onboarding share are throttled by judged/created -- reordered toward the
highest EVIG, deferred rather than deleted, never cut to zero. No miner, acquirer or source is
slowed by anything here (GROWTH_GOVERNANCE: generate differently, never less).

Artifacts: reports/GLOBAL_COVERAGE_TENSOR.json, reports/SOURCE_ROI.json,
data/intelligence/global_coverage/missions_<date>.json. State: data/global_coverage/state.json.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(BASE), str(BASE / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import coverage as CV  # noqa: E402

UNMEASURED = CV.UNMEASURED
ANY = CV.ANY

#: Module globals, not frozen constants: the tests point the whole organ at a tmp desk.
DATA = BASE / "data"
REPORTS = BASE / "reports"
OUT = REPORTS / "GLOBAL_COVERAGE_TENSOR.json"
ROI_OUT = REPORTS / "SOURCE_ROI.json"
STATE = DATA / "global_coverage" / "state.json"
MISSIONS_DIR = DATA / "intelligence" / "global_coverage"
GRAPH = DATA / "hypothesis_graph.jsonl"
GATE_LEDGER = DATA / "hypotheses" / "gate_verdict_ledger.jsonl"
UNIVERSE_JSON = DATA / "universe" / "universe.json"
UNIVERSE_DIR = DATA / "universe"
DEEP_FOREST = DATA / "deep_forest_sources.json"
INTEL_ROOTS: tuple[Path, ...] = (DATA / "intelligence", REPO / "data" / "intelligence")
SURVIVORS = REPORTS / "UNIVERSAL_SURVIVORS.json"
SLEEVES = DATA / "sleeves.json"
FORWARD = DATA / "forward_reconcile.json"
BACKPRESSURE = REPORTS / "GAUNTLET_BACKPRESSURE.json"
BREADTH = REPORTS / "EFFECTIVE_BREADTH.json"
MINING_DB = DATA / "mining" / "mining.db"
MINING_METRICS = REPORTS / "mining" / "MINING_METRICS.json"

BUDGET_S = 540.0
#: How far back the FIRST pass reads the append-only logs; later passes read only the bytes
#: appended since the durable cursor, so the lifetime record accumulates in the state file.
BACKFILL_DAYS = 30.0
ACTIVE_WINDOW_DAYS = 30.0
MAX_ROWS_PER_LOG = 600_000
MAX_GENERATE = 250_000
MAX_MISSIONS = 40
#: THE FLOOR UNDER EVERY THROTTLE. Emission is reordered and deferred, never zero.
MISSION_FLOOR = 10
#: The share of missions that onboard NEW ground when judging keeps up; scaled by judged/created
#: when it does not. The remainder converts ground the desk already holds.
ONBOARDING_SHARE = 0.5
#: ADEQUATE SAMPLING before a source may be flagged for budget redirection: this many measured
#: outcomes AND this many days on the record. Below either, silence is not evidence (L1.28a).
RETIRE_MIN_JUDGED = 200
RETIRE_MIN_DAYS = 14.0
#: A source that fetched this much and compiled nothing is STRANDED ingestion -- a defect to fix,
#: not a source to retire.
STRANDED_MIN_FETCHED = 1_000
MAX_SOURCES_PER_CELL = 4
PROJECTION: tuple[str, ...] = ("region", "source_class", "mechanism", "instrument")
SOURCE_TYPE = "global_coverage_tensor"
GAP_KIND = "coverage_gap"
PIT_KEYS: tuple[str, ...] = ("available_time", "knowable_at", "as_of", "pit_time", "pit_status",
                             "available_at", "available_for_decision_at", "acquisition_time",
                             "fetched_at", "acquired_at", "retrieved_at")
#: Gauntlet gates whose refusal is NOT an outcome: work not done (L1.28a).
UNMEASURED_GATES = frozenset({"observations", "UNKNOWN", ""})
BANNED_FAMILIES = frozenset({"discovered"})

RULE = ("coverage counts only on a proven path source -> acquisition -> PIT store -> extraction "
        "-> mechanism -> cell -> docket -> gauntlet -> measured outcome; registered or fetched "
        "alone is nominal coverage and is published beside it, never instead of it")


# ================================================================================ the vocabulary
#: region -> (country codes, the region's native languages). Every region gets the same depth
#: template: the generator walks every one of them in each of its languages.
REGIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "global": (("global", "institutional", "any", "eu_wide", "world"), ("en",)),
    "north_america": (("us", "ca"), ("en",)),
    "latam": (("br", "mx", "ar", "cl", "co", "pe"), ("es", "pt")),
    "uk": (("gb", "uk"), ("en",)),
    "europe": (("de", "fr", "es", "it", "nl", "se", "no", "dk", "fi", "pl", "cz", "hu", "ch",
                "at", "be", "ie", "pt", "gr", "eu"), ("de", "fr")),
    "cis": (("ru", "ua", "kz", "by"), ("ru",)),
    "middle_east_africa": (("tr", "sa", "ae", "il", "eg", "ma", "za", "ng", "ke", "qa"),
                           ("ar", "tr")),
    "south_asia": (("in", "pk", "bd", "lk"), ("hi", "en")),
    "southeast_asia": (("id", "th", "vn", "sg", "my", "ph"), ("id", "vi")),
    "china": (("cn", "hk", "tw", "mo"), ("zh",)),
    "japan": (("jp",), ("ja",)),
    "korea": (("kr",), ("ko",)),
    "oceania": (("au", "nz"), ("en",)),
}
_COUNTRY_REGION: dict[str, str] = {c: r for r, (cs, _l) in REGIONS.items() for c in cs}

#: BROKER-CLOCK SESSIONS. The broker clock is New York + 7h (DST-invariant against New York), so
#: these hours hold all year: the 17:00 New York rollover is broker 00:00, the London open broker
#: 10:00, the WMR 4pm London fix broker 18:00, the Tokyo 9:55 fix broker ~03:00-04:00.
SESSION_BROKER_HOURS: dict[str, tuple[int, int]] = {
    "all": (0, 24), "asia": (0, 10), "tokyo_fix": (2, 4), "london": (10, 15),
    "overlap": (15, 19), "london_fix": (18, 19), "ny": (15, 23), "close": (22, 24)}
HORIZONS: tuple[str, ...] = ("5m", "15m", "1h", "4h", "1d", "5d", "20d", "event_0_5m",
                             "event_5_30m", "event_30m_4h", "event_1_5d")
REGIMES: tuple[str, ...] = ("unconditional", "vol_high", "vol_low", "risk_on", "risk_off",
                            "liquidity_thin", "macro_tightening", "macro_easing")
EVENT_TYPES: tuple[str, ...] = ("none", "macro_release", "central_bank", "auction_supply",
                                "fixing", "index_rebalance", "roll_expiry", "month_quarter_end",
                                "earnings_corporate", "geopolitical", "weather", "holiday",
                                "session_open", "inventory_report", "positioning_report")
POSITIONING_STATES: tuple[str, ...] = ("any", "crowded_long", "crowded_short", "neutral",
                                       "forced_deleveraging", "dealer_short_gamma",
                                       "dealer_long_gamma")
CROSS_ASSET_STATES: tuple[str, ...] = ("any", "usd_led", "rates_led", "equity_led",
                                       "commodity_led", "risk_off_flight", "divergence",
                                       "coupled")
EXECUTION_STATES: tuple[str, ...] = ("market", "limit", "stop", "bracket", "session_window",
                                     "fix_order", "moc")
INSTRUMENTS: tuple[str, ...] = ("fx_major", "fx_cross", "fx_exotic", "metals", "energy",
                                "indices", "softs", "bonds", "crypto_cfd")
TRANSMISSIONS: dict[str, tuple[str, ...]] = {
    "direct_price": INSTRUMENTS,
    "rates_to_fx": ("fx_major", "fx_cross", "fx_exotic"),
    "rates_to_bonds": ("bonds",),
    "usd_to_metals": ("metals",),
    "risk_to_indices": ("indices",),
    "risk_to_fx": ("fx_major", "fx_cross"),
    "commodity_to_fx": ("fx_major", "fx_exotic"),
    "supply_to_energy": ("energy",),
    "supply_to_metals": ("metals",),
    "weather_to_softs": ("softs",),
    "flows_to_fx": ("fx_major", "fx_cross", "fx_exotic"),
    "equity_to_indices": ("indices",),
    "vol_to_risk": ("indices", "metals", "fx_major"),
    "sentiment_to_crypto": ("crypto_cfd",),
}

#: THE COMPATIBILITY TEMPLATE, one row per mechanism in `axis_registry.MECHANISM_ACTOR`. Every
#: list is what the mechanism's economics ADMITS -- a gamma-hedging cell needs an options/vol or
#: positioning source and a dealer gamma state; a fixing flow lives at the fixes. The generator
#: takes the product WITHIN a row, never across rows. A mechanism the registry adds later that
#: has no row here gets `_DEFAULT_PROFILE` and is named in the artifact until it is profiled.
_P = dict[str, tuple[str, ...]]
MECHANISM_PROFILES: dict[str, _P] = {
    "session_handover": {
        "sources": ("market_native", "retail_social", "strategy_code_archaeology", "academic"),
        "transmissions": ("direct_price", "risk_to_fx"), "horizons": ("1h", "4h"),
        "sessions": ("asia", "london", "ny"), "regimes": ("unconditional", "vol_high"),
        "events": ("session_open",), "positioning": ("any",), "cross_asset": ("coupled",),
        "execution": ("session_window",)},
    "session_information_handoff": {
        "sources": ("market_native", "news_events", "academic", "strategy_code_archaeology"),
        "transmissions": ("direct_price", "equity_to_indices"), "horizons": ("1h", "4h"),
        "sessions": ("london", "ny", "asia"), "regimes": ("unconditional", "risk_off"),
        "events": ("session_open",), "positioning": ("any",), "cross_asset": ("equity_led",),
        "execution": ("market",)},
    "fx_fixing_flow": {
        "sources": ("market_native", "positioning_flows", "academic", "historical_archives"),
        "transmissions": ("flows_to_fx", "usd_to_metals"), "horizons": ("5m", "15m", "1h"),
        "sessions": ("london_fix", "tokyo_fix"), "regimes": ("unconditional", "liquidity_thin"),
        "events": ("fixing", "month_quarter_end"), "positioning": ("neutral",),
        "cross_asset": ("usd_led",), "execution": ("fix_order",)},
    "macro_release": {
        "sources": ("government_macro", "rates_monetary", "prediction_disagreement",
                    "news_events", "historical_archives"),
        "transmissions": ("rates_to_fx", "rates_to_bonds", "usd_to_metals", "risk_to_indices"),
        "horizons": ("event_0_5m", "event_5_30m", "event_30m_4h"), "sessions": ("ny", "london"),
        "regimes": ("unconditional", "vol_high"), "events": ("macro_release", "central_bank"),
        "positioning": ("any",), "cross_asset": ("rates_led",), "execution": ("bracket",)},
    "forced_flow": {
        "sources": ("positioning_flows", "market_native", "corporate", "sovereign_fiscal"),
        "transmissions": ("equity_to_indices", "flows_to_fx", "rates_to_bonds"),
        "horizons": ("1h", "1d"), "sessions": ("close", "london_fix"),
        "regimes": ("unconditional", "liquidity_thin"),
        "events": ("index_rebalance", "month_quarter_end", "roll_expiry", "auction_supply"),
        "positioning": ("forced_deleveraging",), "cross_asset": ("any",), "execution": ("moc",)},
    "carry_rollover": {
        "sources": ("rates_monetary", "fx_reserves", "market_native", "credit"),
        "transmissions": ("rates_to_fx", "direct_price"), "horizons": ("5d", "20d"),
        "sessions": ("all",), "regimes": ("vol_low", "risk_on"), "events": ("none",),
        "positioning": ("crowded_long",), "cross_asset": ("rates_led",),
        "execution": ("market",)},
    "positioning_crowding": {
        "sources": ("positioning_flows", "retail_social", "options_vol", "attention_search"),
        "transmissions": ("flows_to_fx", "usd_to_metals", "risk_to_indices",
                          "sentiment_to_crypto"),
        "horizons": ("1d", "5d"), "sessions": ("all",), "regimes": ("unconditional", "risk_off"),
        "events": ("positioning_report",), "positioning": ("crowded_long", "crowded_short"),
        "cross_asset": ("any",), "execution": ("limit",)},
    "calendar_seasonality": {
        "sources": ("historical_archives", "market_native", "country_specific_oddities",
                    "academic"),
        "transmissions": ("direct_price",), "horizons": ("1d", "5d"),
        "sessions": ("all", "tokyo_fix"), "regimes": ("unconditional",),
        "events": ("holiday", "month_quarter_end"), "positioning": ("any",),
        "cross_asset": ("any",), "execution": ("session_window",)},
    "relative_value_dislocation": {
        "sources": ("market_native", "academic", "strategy_code_archaeology", "credit"),
        "transmissions": ("direct_price", "commodity_to_fx"), "horizons": ("4h", "1d", "5d"),
        "sessions": ("all",), "regimes": ("unconditional", "vol_high"), "events": ("none",),
        "positioning": ("any",), "cross_asset": ("divergence",), "execution": ("limit",)},
    "cross_market_lead": {
        "sources": ("market_native", "commodity_physical", "transport_logistics",
                    "energy_infra", "alternative_public_proxies", "government_macro"),
        "transmissions": ("commodity_to_fx", "supply_to_energy", "supply_to_metals",
                          "equity_to_indices", "rates_to_fx"),
        "horizons": ("1h", "1d"), "sessions": ("asia", "london", "ny"),
        "regimes": ("unconditional", "risk_off"), "events": ("inventory_report", "none"),
        "positioning": ("any",), "cross_asset": ("commodity_led",), "execution": ("market",)},
    "trend_persistence": {
        "sources": ("market_native", "strategy_code_archaeology", "academic", "retail_social"),
        "transmissions": ("direct_price",), "horizons": ("1d", "5d", "20d"),
        "sessions": ("all",), "regimes": ("unconditional", "vol_low"), "events": ("none",),
        "positioning": ("any",), "cross_asset": ("any",), "execution": ("stop",)},
    "range_reversion": {
        "sources": ("market_native", "strategy_code_archaeology", "retail_social"),
        "transmissions": ("direct_price",), "horizons": ("15m", "1h", "4h"),
        "sessions": ("asia", "london"), "regimes": ("vol_low", "unconditional"),
        "events": ("none",), "positioning": ("any",), "cross_asset": ("coupled",),
        "execution": ("limit",)},
    "volatility_shock": {
        "sources": ("options_vol", "news_events", "geopolitical_policy", "market_native"),
        "transmissions": ("vol_to_risk", "risk_to_fx"), "horizons": ("1h", "1d"),
        "sessions": ("all",), "regimes": ("vol_high", "risk_off"),
        "events": ("geopolitical", "macro_release"), "positioning": ("any",),
        "cross_asset": ("risk_off_flight",), "execution": ("market",)},
    "regime_transition": {
        "sources": ("government_macro", "rates_monetary", "credit", "geopolitical_policy",
                    "prediction_disagreement"),
        "transmissions": ("rates_to_fx", "risk_to_indices", "usd_to_metals"),
        "horizons": ("5d", "20d"), "sessions": ("all",),
        "regimes": ("macro_tightening", "macro_easing"), "events": ("central_bank",),
        "positioning": ("any",), "cross_asset": ("rates_led",), "execution": ("market",)},
    "breakout_liquidity": {
        "sources": ("market_native", "strategy_code_archaeology", "retail_social"),
        "transmissions": ("direct_price",), "horizons": ("15m", "1h"),
        "sessions": ("london", "ny"), "regimes": ("unconditional", "liquidity_thin"),
        "events": ("session_open",), "positioning": ("any",), "cross_asset": ("any",),
        "execution": ("stop",)},
    "execution_microstructure": {
        "sources": ("market_native", "strategy_code_archaeology"),
        "transmissions": ("direct_price",), "horizons": ("5m", "15m"),
        "sessions": ("london", "ny", "overlap"), "regimes": ("unconditional",),
        "events": ("none",), "positioning": ("any",), "cross_asset": ("any",),
        "execution": ("limit",)},
    "gamma_hedging_state": {
        "sources": ("options_vol", "positioning_flows", "market_native"),
        "transmissions": ("vol_to_risk", "equity_to_indices", "usd_to_metals"),
        "horizons": ("1h", "1d"), "sessions": ("ny", "close"),
        "regimes": ("unconditional", "vol_low"), "events": ("roll_expiry",),
        "positioning": ("dealer_short_gamma", "dealer_long_gamma"),
        "cross_asset": ("equity_led",), "execution": ("moc",)},
    "hedging_demand_close_flow": {
        "sources": ("corporate", "market_native", "positioning_flows", "payments_consumer"),
        "transmissions": ("flows_to_fx", "equity_to_indices"), "horizons": ("1h", "4h"),
        "sessions": ("close", "london_fix"), "regimes": ("unconditional",),
        "events": ("month_quarter_end", "earnings_corporate"), "positioning": ("any",),
        "cross_asset": ("any",), "execution": ("fix_order",)},
    "inventory_shock": {
        "sources": ("commodity_physical", "energy_infra", "transport_logistics",
                    "weather_climate"),
        "transmissions": ("supply_to_energy", "supply_to_metals", "weather_to_softs",
                          "commodity_to_fx"),
        "horizons": ("event_30m_4h", "1d", "5d"), "sessions": ("ny", "london"),
        "regimes": ("unconditional", "vol_high"), "events": ("inventory_report", "weather"),
        "positioning": ("any",), "cross_asset": ("commodity_led",), "execution": ("bracket",)},
    "forced_liquidation": {
        "sources": ("positioning_flows", "credit", "retail_social", "options_vol"),
        "transmissions": ("sentiment_to_crypto", "risk_to_indices", "usd_to_metals",
                          "flows_to_fx"),
        "horizons": ("1h", "1d"), "sessions": ("all",), "regimes": ("risk_off", "vol_high"),
        "events": ("none",), "positioning": ("forced_deleveraging",),
        "cross_asset": ("risk_off_flight",), "execution": ("market",)},
}
_DEFAULT_PROFILE: _P = {
    "sources": ("market_native", "strategy_code_archaeology", "academic"),
    "transmissions": ("direct_price",), "horizons": ("1h", "1d"), "sessions": ("all",),
    "regimes": ("unconditional",), "events": ("none",), "positioning": ("any",),
    "cross_asset": ("any",), "execution": ("market",)}

#: SOURCE -> SOURCE CLASS, by the words a source's id, kind and name carry. First match wins, so
#: the specific classes sit above the general ones. A source none of them names is UNCLASSIFIED
#: and says so: guessing a class would make coverage a description of this table.
_CLASS_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("options_vol", ("option", "gamma", "vix", "cboe", "implied_vol", "volatility")),
    ("positioning_flows", ("cot", "positioning", "fund_flow", "benchmark_flows", "flows",
                           "crowding", "fund_disclosure", "13f")),
    ("rates_monetary", ("central_bank", "bis_speech", "fomc", "ecb", "boj", "rates_credit",
                        "monetary", "rates")),
    ("sovereign_fiscal", ("treasury", "auction", "fiscal", "sovereign", "debt_management")),
    ("fx_reserves", ("reserve", "cofer", "tic_")),
    ("credit", ("credit", "cds", "high_yield", "bond_spread")),
    ("transport_logistics", ("shipping", "freight", "port", "baltic", "ais", "logistic",
                             "supply_chain")),
    ("energy_infra", ("eia", "pipeline", "power", "electric", "lng", "refiner", "energy")),
    ("commodity_physical", ("inventory", "lme", "comex", "usda", "physical_commodity",
                            "futures_term_structure", "commodity", "metal")),
    ("weather_climate", ("weather", "climate", "noaa", "enso", "geospatial")),
    ("payments_consumer", ("payment", "consumer", "card_spend", "retail_sales")),
    ("corporate", ("earnings", "sec_edgar", "filing", "corporate", "accounting",
                   "activist", "regulatory_filing", "patent", "job_posting")),
    ("prediction_disagreement", ("predict", "polymarket", "kalshi", "consensus", "survey",
                                 "disagreement", "forecast")),
    ("geopolitical_policy", ("geopolit", "sanction", "policy", "election", "enforcement",
                             "court", "public_messaging")),
    ("attention_search", ("trend", "search", "wiki", "attention", "digital_activity",
                          "youtube", "video")),
    ("historical_archives", ("archive", "history", "vintage", "alfred", "dead_web",
                             "genealogy", "incident_postmortem")),
    ("country_specific_oddities", ("gotobi", "holiday", "local_market", "competition",
                                   "oddit", "exchange_rulebook", "seasonality")),
    ("government_macro", ("fred", "macro", "calendar", "forexfactory", "cpi", "statistic",
                          "government", "event_response")),
    ("academic", ("arxiv", "ssrn", "academic", "paper", "nber", "journal", "research",
                  "longform_research")),
    ("strategy_code_archaeology", ("github", "gitee", "mql5", "codebase", "script", "code",
                                   "quantconnect", "joinquant", "ricequant", "bigquant",
                                   "collective2", "darwinex", "duplitrade", "zulu", "copy",
                                   "track_record", "playbook", "strategy", "leaderboard",
                                   "notebook", "platform_native", "repo", "external",
                                   "practitioner", "blog", "column", "interview", "qa",
                                   "vendor_product", "failure", "negative_knowledge")),
    ("retail_social", ("reddit", "forum", "twitter", "stocktwits", "fear_greed", "aaii",
                       "peacearmy", "xueqiu", "zhihu", "tradingview", "followme", "telegram",
                       "social", "community", "share4you", "myfxbook", "sentiment")),
    ("news_events", ("news", "gdelt", "headline", "wire", "event_graph", "longform_media",
                     "media")),
    ("alternative_public_proxies", ("alt_", "satellite", "night", "app_", "web_traffic",
                                    "proxy", "dataset", "anomal", "synthetic", "distant")),
    ("market_native", ("bars", "broker", "microstructure", "plumbing", "tape", "trend_core",
                       "axis_registry", "discovery_compiler", "search_paradigm", "moat_factory",
                       "factor_residual", "net_edge", "survivor", "alpha_evolution",
                       "standing_questions", "world_lab", "market", "swap", "exchange",
                       "cross_sectional", "correlation", "regime", "research_process")),
)


# ================================================================================ small helpers
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def _tok(value: Any) -> str:
    text = " ".join(str(value or "").strip().lower().replace("-", " ").replace("_", " ").split())
    return text.replace(" ", "_")


def _read_json(path: Path, limit_bytes: int = 256 * 1024 * 1024) -> Any:
    try:
        if Path(path).stat().st_size > limit_bytes:
            return None
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _write_atomic(path: Path, payload: Any) -> None:
    """Atomic where the filesystem allows; `os.replace` onto a read-only file raises on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str, ensure_ascii=False),
                   encoding="utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        with contextlib.suppress(OSError):
            path.chmod(0o644)
        os.replace(tmp, path)


def _share(num: float, den: float) -> float | None:
    return None if den <= 0 else round(float(num) / float(den), 6)


def _at(value: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


class Absent:
    """Every input this pass could not read, by name. UNMEASURED is never zero (L1.28a)."""

    def __init__(self) -> None:
        self.rows: dict[str, str] = {}

    def note(self, name: str, why: str) -> None:
        self.rows.setdefault(name, why)

    def to_json(self) -> dict[str, str]:
        return dict(sorted(self.rows.items()))


# ============================================================================ the vocabularies
def mechanism_actor() -> dict[str, str]:
    """mechanism -> the payer, from `axis_registry` (the desk's one declared table)."""
    try:
        from research import axis_registry as AX
        return {str(k): str(v) for k, v in AX.MECHANISM_ACTOR.items() if str(k) != "UNKNOWN"}
    except Exception:                                                        # noqa: BLE001
        return {m: "UNMEASURED" for m in MECHANISM_PROFILES}


def family_mechanism() -> dict[str, str]:
    try:
        from research import axis_registry as AX
        return {str(f): str(m) for f, (m, _i, _s) in AX.FAMILY_TABLE.items()}
    except Exception:                                                        # noqa: BLE001
        return {}


def profile(mech: str) -> _P:
    return MECHANISM_PROFILES.get(mech, _DEFAULT_PROFILE)


def vocabulary(actors: Mapping[str, str], extra_languages: Iterable[str] = ()) -> dict[str, list[str]]:
    langs = sorted({lang for _c, ls in REGIONS.values() for lang in ls} | set(extra_languages))
    trans = sorted(TRANSMISSIONS)
    return {
        "region": sorted(REGIONS), "language": langs, "source_class": list(CV.SOURCE_CLASSES),
        "mechanism": sorted(actors), "asset_transmission": trans,
        "instrument": list(INSTRUMENTS), "horizon": list(HORIZONS),
        "session": list(SESSION_BROKER_HOURS), "regime": list(REGIMES),
        "participant": sorted(set(actors.values())), "event_type": list(EVENT_TYPES),
        "positioning_state": list(POSITIONING_STATES),
        "cross_asset_state": list(CROSS_ASSET_STATES), "execution_state": list(EXECUTION_STATES)}


def instrument_class(symbol: str, asset_class: str) -> str | None:
    """The MT5 instrument class of a HYPOTHESIS-lane symbol; None for the event lane."""
    ac = _tok(asset_class)
    sym = str(symbol or "").upper()
    if ac == "forex":
        g10 = {"USD", "EUR", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD"}
        a, b = sym[:3], sym[3:6]
        if a in g10 and b in g10:
            return "fx_major" if "USD" in (a, b) else "fx_cross"
        return "fx_exotic"
    return {"forex_exotics": "fx_exotic", "commodities": "metals", "energy": "energy",
            "soft_commodity": "softs", "indices": "indices", "bonds": "bonds",
            "crypto": "crypto_cfd"}.get(ac)


def universe(absent: Absent) -> dict[str, str]:
    """symbol -> instrument class, hypothesis lane only (single names are the event lane)."""
    doc = _read_json(UNIVERSE_JSON)
    if not isinstance(doc, dict):
        absent.note("universe.json", f"{UNIVERSE_JSON} unreadable: the instrument axis cannot map "
                                     "a symbol, so no observation lands in the tensor")
        return {}
    try:
        from research import universe_policy as UP
        lane = UP.lane
    except Exception:                                                        # noqa: BLE001
        absent.note("research.universe_policy", "lane routing unavailable: no symbol is admitted")
        return {}
    out: dict[str, str] = {}
    for sym, row in doc.items():
        if not isinstance(row, Mapping):
            continue
        try:
            if lane(str(sym)) != "hypothesis":
                continue
        except Exception:                                                    # noqa: BLE001
            continue
        klass = instrument_class(str(sym), str(row.get("asset_class") or ""))
        if klass:
            out[str(sym).upper()] = klass
    return out


def region_of(value: Any) -> str:
    tok = _tok(value)
    if tok in REGIONS:
        return tok
    return _COUNTRY_REGION.get(tok.split("_")[0] if tok else "", "global")


def language_of(value: Any, region: str) -> str:
    tok = _tok(value).split("_")[0]
    if tok == "zh":
        return "zh"
    return tok or REGIONS.get(region, ((), ("en",)))[1][0]


def classify_source(*words: Any) -> str:
    """One of the 24 source classes, or UNCLASSIFIED (named, never guessed)."""
    blob = " " + " ".join(_tok(w) for w in words if w) + " "
    for klass, keys in _CLASS_WORDS:
        for k in keys:
            if k in blob:
                return klass
    return "UNCLASSIFIED"


# ================================================================================ the generator
def cell_key(values: Mapping[str, str]) -> str:
    return "|".join(str(values.get(a) or ANY) for a in CV.GLOBAL_AXES)


def generate(actors: Mapping[str, str], *, cap: int = MAX_GENERATE) -> tuple[dict[str, tuple[str, ...]], dict[str, Any]]:
    """Every mechanistically compatible cell, keyed. Never the literal product: the product is
    taken WITHIN a mechanism's profile, and every region in every one of its languages."""
    cells: dict[str, tuple[str, ...]] = {}
    truncated = False
    unprofiled: list[str] = []
    for mech in sorted(actors):
        prof = profile(mech)
        if mech not in MECHANISM_PROFILES:
            unprofiled.append(mech)
        part = actors[mech]
        for sc in prof["sources"]:
            for region, (_cs, langs) in REGIONS.items():
                for lang in langs:
                    for tr in prof["transmissions"]:
                        for inst in TRANSMISSIONS.get(tr, ()):
                            for hz in prof["horizons"]:
                                for sess in prof["sessions"]:
                                    for reg in prof["regimes"]:
                                        for ev in prof["events"]:
                                            for pos in prof["positioning"]:
                                                if len(cells) >= cap:
                                                    truncated = True
                                                    break
                                                coords = (region, lang, sc, mech, tr, inst, hz,
                                                          sess, reg, part, ev, pos,
                                                          prof["cross_asset"][0],
                                                          prof["execution"][0])
                                                cells["|".join(coords)] = coords
    return cells, {"generated": len(cells), "truncated": truncated, "cap": cap,
                   "unprofiled_mechanisms": unprofiled}


def observed_coords(mech: str, instrument: str, *, region: str, language: str, source_class: str,
                    horizon: str | None, session: str | None, actors: Mapping[str, str]
                    ) -> tuple[str, ...]:
    """The tensor coordinate an OBSERVATION lands on: the mechanism's template fills the axes the
    evidence does not carry (transmission, regime, event, positioning, cross-asset, execution),
    so evidence and generator agree on every axis the evidence cannot speak to."""
    prof = profile(mech)
    tr = next((t for t in prof["transmissions"] if instrument in TRANSMISSIONS.get(t, ())),
              "direct_price")
    hz = horizon if horizon in HORIZONS else prof["horizons"][0]
    if hz not in prof["horizons"]:
        hz = prof["horizons"][0] if horizon is None else hz
    sess = session if session in SESSION_BROKER_HOURS else prof["sessions"][0]
    return (region, language, source_class, mech, tr, instrument, hz, sess, prof["regimes"][0],
            actors.get(mech, "UNMEASURED"), prof["events"][0], prof["positioning"][0],
            prof["cross_asset"][0], prof["execution"][0])


_HZ_OF_AXIS = {"intrabar": "15m", "sub_4h": "1h", "sub_1d": "4h", "multi_day": "5d"}


def axes_of_row(symbol: Any, family: Any, params: Any) -> dict[str, str]:
    try:
        from research import axis_registry as AX
        return dict(AX.axis_cell(symbol, family, params if isinstance(params, dict) else None))
    except Exception:                                                        # noqa: BLE001
        return {}


# ================================================================================== the sources
class Sources:
    """The unified view of every source this tree can name, keyed by a stable id.

    Precedence: #133's roster (when importable) -> the canonical registry's `sources` table ->
    `deep_forest_sources.json` -> the intelligence seats -> the graph's own source labels. The
    first definition of an id wins; later ones only add evidence of acquisition.
    """

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    def add(self, sid: str, *, origin: str, region: str = "global", language: str = "",
            source_class: str = "", registered: bool = True, **extra: Any) -> dict[str, Any]:
        row = self.rows.get(sid)
        if row is None:
            reg = region_of(region)
            row = {"id": sid, "origin": origin, "region": reg,
                   "language": language_of(language, reg),
                   "source_class": source_class or "UNCLASSIFIED", "registered": registered,
                   "acquired": False, "acquired_basis": UNMEASURED, "pit": None,
                   "pit_basis": UNMEASURED, "fetched": None, "status_133": None}
            self.rows[sid] = row
        for k, v in extra.items():
            if v is not None and row.get(k) in (None, UNMEASURED, False, 0, ""):
                row[k] = v
        return row


def seat_of_graph_source(src: Any) -> str:
    """`miner:asia:Q3` -> `seat:asia`; `fund_playbook:AQR:A` -> `seat:fund_playbook`."""
    parts = str(src or "").split(":")
    if parts and parts[0] == "miner" and len(parts) > 1:
        return f"seat:{parts[1]}"
    return f"seat:{parts[0] or 'unknown'}"


def _intel_seats() -> dict[str, dict[str, Any]]:
    """seat -> {files, bytes, newest, pit}: acquisition evidence by the seat's own directory."""
    out: dict[str, dict[str, Any]] = {}
    for root in INTEL_ROOTS:
        if not root.exists():
            continue
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            files = [p for p in d.rglob("*") if p.is_file() and p.suffix in (".json", ".jsonl")]
            if not files:
                continue
            row = out.setdefault(d.name, {"files": 0, "bytes": 0, "pit": False, "sampled": 0})
            row["files"] += len(files)
            row["bytes"] += sum(p.stat().st_size for p in files)
            newest = sorted(files, key=lambda p: p.stat().st_mtime)[-3:]
            for p in newest:
                row["sampled"] += 1
                if _file_has_pit(p):
                    row["pit"] = True
                    break
    return out


def _file_has_pit(path: Path, max_bytes: int = 4 * 1024 * 1024) -> bool:
    """Does a seat file carry a point-in-time stamp on its rows? Read at most `max_bytes`."""
    try:
        with path.open("rb") as fh:
            head = fh.read(max_bytes)
    except OSError:
        return False
    text = head.decode("utf-8", "replace")
    return any(f'"{k}"' in text for k in PIT_KEYS)


def load_sources(absent: Absent, conn: Any, graph_seats: Iterable[str]) -> Sources:
    src = Sources()
    # 1. PR #133's unified roster, when this tree carries it.
    try:
        from libs.mining import acquirer as ACQ
        roster = ACQ.load_roster(root=REPO)
    except Exception as exc:                                                 # noqa: BLE001
        roster = []
        absent.note("libs.mining (PR #133)",
                    f"the unified source registry is not on this tree ({type(exc).__name__}); "
                    "its ACTIVE/COLD rule is re-derived here from the gate ledger and the graph")
    for s in roster:
        src.add(str(s.id), origin="libs/mining/sources.yaml (#133)", region=s.region,
                language=s.language,
                source_class=classify_source(s.id, s.kind, s.name, s.fetcher, *list(s.uses)))
    # 2. The canonical registry's `sources` table.
    try:
        rows = conn.execute("SELECT source_id, kind, language, country, status, last_crawled "
                            "FROM sources LIMIT 50000").fetchall() if conn is not None else []
    except Exception as exc:                                                 # noqa: BLE001
        rows = []
        absent.note("registry.sources", f"unreadable: {type(exc).__name__}")
    for r in rows:
        d = dict(r)
        row = src.add(f"registry:{d.get('source_id')}", origin="registry.sources",
                      region=d.get("country") or "global", language=d.get("language") or "",
                      source_class=classify_source(d.get("source_id"), d.get("kind")))
        if d.get("last_crawled"):
            row["acquired"], row["acquired_basis"] = True, "registry.sources.last_crawled"
    # 3. The deep forest grounds.
    doc = _read_json(DEEP_FOREST)
    grounds = doc.get("grounds") if isinstance(doc, dict) else None
    if not isinstance(grounds, list):
        absent.note("deep_forest_sources.json", f"{DEEP_FOREST} unreadable")
        grounds = []
    for g in grounds:
        if not isinstance(g, Mapping):
            continue
        url = str(g.get("url") or "")
        slug = re.sub(r"[^a-z0-9]+", "_", url.lower().split("//")[-1])[:60] or \
            hashlib.sha1(str(g.get("name")).encode()).hexdigest()[:10]
        src.add(f"forest:{g.get('region') or 'global'}:{slug}", origin="deep_forest_sources.json",
                region=str(g.get("region") or "global"), language=str(g.get("language") or ""),
                source_class=classify_source(g.get("kind"), g.get("name"), url))
    # 4. The intelligence seats: a directory with rows is acquisition, rows with stamps are PIT.
    seats = _intel_seats()
    for name, info in seats.items():
        row = src.add(f"seat:{name}", origin="data/intelligence/<seat>",
                      source_class=classify_source(name))
        row["acquired"], row["acquired_basis"] = True, f"{info['files']} file(s) under the seat"
        row["fetched"] = int(info["files"])
        row["pit"] = bool(info["pit"])
        row["pit_basis"] = ("a sampled seat file carries a PIT key" if info["pit"] else
                            f"none of {info['sampled']} sampled file(s) carries a PIT key")
    # 5. The graph's own labels: an internal generator reads the broker bar estate, which is its
    #    acquisition and its PIT store (every bar is stamped by the venue).
    bars = UNIVERSE_DIR.exists() and any(UNIVERSE_DIR.glob("*.parquet"))
    for sid in graph_seats:
        name = sid.split(":", 1)[-1]
        klass = classify_source(name)
        row = src.add(sid, origin="hypothesis_graph.jsonl source label", source_class=klass,
                      registered=name in seats or klass == "market_native")
        if klass == "market_native" and bars and not row["acquired"]:
            row["acquired"], row["acquired_basis"] = True, "broker bar estate (data/universe)"
            row["pit"], row["pit_basis"] = True, "venue-stamped bars"
    return src


# ============================================================================== delta log reads
def _head_hash(path: Path, n: int = 4096) -> str:
    """The hash of the file's first `n` bytes. The cursor stores how many bytes it hashed, so a
    small file that only GREW keeps its head and a rewritten one does not."""
    try:
        with path.open("rb") as fh:
            return hashlib.sha256(fh.read(max(0, n))).hexdigest()[:16]
    except OSError:
        return ""


def read_log(path: Path, cursor: dict[str, Any], *, now: datetime, deadline: float,
             absent: Absent, name: str) -> list[dict[str, Any]]:
    """Rows APPENDED since the durable cursor; on a first pass (or a rewritten file) the newest
    BACKFILL_DAYS, read backwards. The cursor advances only over what was actually decoded, so a
    pass cut by its budget resumes where it stopped."""
    try:
        size = path.stat().st_size
    except OSError:
        absent.note(name, f"{path} is not on this tree: its rows are UNMEASURED, not zero")
        return []
    cur = cursor.get(name) if isinstance(cursor.get(name), dict) else None
    head_n = min(4096, size)
    rows: list[dict[str, Any]] = []
    if (cur and 0 < int(cur.get("offset") or 0) <= size
            and cur.get("head") == _head_hash(path, int(cur.get("head_n") or 4096))):
        offset = int(cur["offset"])
        with path.open("rb") as fh:
            fh.seek(offset)
            for raw in fh:
                if not raw.endswith(b"\n"):
                    break                     # a line still being written: next pass reads it
                offset += len(raw)
                with contextlib.suppress(ValueError):
                    obj = json.loads(raw.decode("utf-8", "replace"))
                    if isinstance(obj, dict):
                        rows.append(obj)
                if len(rows) >= MAX_ROWS_PER_LOG or time.monotonic() > deadline:
                    absent.note(f"{name}_delta", f"delta read stopped at {len(rows)} rows "
                                                 "(cap or budget); the cursor resumes there")
                    break
        cursor[name] = {"head": _head_hash(path, head_n), "head_n": head_n, "offset": offset,
                        "size": size, "mode": "delta"}
        return rows
    try:
        import gauntlet_backpressure as GB
    except Exception:                                                        # noqa: BLE001
        from research import gauntlet_backpressure as GB
    note: dict[str, str] = {}
    old_cap = GB.MAX_LINES
    try:
        GB.MAX_LINES = MAX_ROWS_PER_LOG
        rows = GB._read_jsonl(path, note, since=now - timedelta(days=BACKFILL_DAYS),
                              deadline=deadline)
    finally:
        GB.MAX_LINES = old_cap
    if note.get(path.name, "READ") != "READ":
        absent.note(f"{name}_backfill", note[path.name])
    cursor[name] = {"head": _head_hash(path, head_n), "head_n": head_n, "offset": size,
                    "size": size, "mode": "backfill",
                    "backfill_days": BACKFILL_DAYS}
    return rows


# ==================================================================================== the state
def load_state() -> dict[str, Any]:
    doc = _read_json(STATE)
    if not isinstance(doc, dict) or doc.get("schema") != "global_coverage_state/1":
        return {"schema": "global_coverage_state/1", "first_at": None, "cursor": {}, "cells": {},
                "sources": {}, "pair_sources": {}}
    for k, v in (("cursor", {}), ("cells", {}), ("sources", {}), ("pair_sources", {})):
        doc.setdefault(k, v)
    return doc


def _later(a: Any, b: Any) -> str | None:
    """The later of two ISO stamps (a log is not perfectly date-ordered)."""
    ta, tb = _at(a), _at(b)
    if ta is None:
        return str(b) if tb is not None else None
    if tb is None or ta >= tb:
        return str(a)
    return str(b)


def _src_counts(state: dict[str, Any], sid: str) -> dict[str, Any]:
    return state["sources"].setdefault(sid, {
        "compiled": 0.0, "judged": 0.0, "measured": 0.0, "survived": 0.0, "duplicates": 0.0,
        "first_at": None, "last_measured_at": None, "measured_at": []})


class Store:
    """The persisted cells, raised through the SAME monotone ladder as every tensor."""

    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.tensor = CV.Tensor(CV.GLOBAL)
        self.meta: dict[str, dict[str, Any]] = {}
        for key, row in (state.get("cells") or {}).items():
            coords = tuple(str(key).split("|"))
            if len(coords) != len(CV.GLOBAL_AXES) or not isinstance(row, list) or not row:
                continue
            with contextlib.suppress(ValueError):
                self.tensor.put(CV.Cell(CV.GLOBAL, coords, str(row[0]), {}, ""))
                self.meta[str(key)] = {"terminal": row[1] if len(row) > 1 else None,
                                       "proven": bool(row[2]) if len(row) > 2 else False,
                                       "sources": list(row[3]) if len(row) > 3 else []}

    def observe(self, coords: tuple[str, ...], state: str, *, source: str, why: str,
                terminal: str | None = None, proven: bool = False, at: str = "",
                attribute: bool = True) -> None:
        cell = self.tensor.observe(coords, state, {"source": source, "why": why}, at=at or None)
        key = "|".join(coords)
        m = self.meta.setdefault(key, {"terminal": None, "proven": False, "sources": []})
        if terminal and (m["terminal"] is None or cell.state in ("FAILED", "DECAYED")):
            m["terminal"] = terminal
        if cell.state in ("CERTIFIED", "FORWARD", "LIVE"):
            m["terminal"] = None if m["terminal"] != "DUPLICATE" else m["terminal"]
        m["proven"] = bool(m["proven"] or proven)
        # ONLY EVIDENCE ATTRIBUTES A CELL TO A SOURCE. A registration marks the ground nominally;
        # crediting it with the survivor another source's cell produced would pay the registrant
        # for the miner's work, and the ROI below would reward registering over finding.
        if attribute and source not in m["sources"] and len(m["sources"]) < MAX_SOURCES_PER_CELL:
            m["sources"].append(source)

    def dump(self) -> dict[str, list[Any]]:
        """Only EVIDENCE-derived cells persist (CANDIDATES and above). Nominal SOURCED/INGESTED
        marks are re-derived from the registries every pass, so persisting them would only grow
        a tracked file by the size of the design."""
        out: dict[str, list[Any]] = {}
        bar = self.tensor.ladder.rank("CANDIDATES")
        for c in self.tensor.cells():
            if self.tensor.ladder.rank(c.state) < bar:
                continue
            m = self.meta.get(c.key, {})
            out[c.key] = [c.state, m.get("terminal"), int(bool(m.get("proven"))),
                          list(m.get("sources") or [])]
        return out


def outcome_terminal(passed: Any, gate: Any) -> tuple[str, str | None, bool]:
    """(world state, principal terminal, is a measured outcome) for one verdict row."""
    g = str(gate or "")
    if passed is True:
        return "CERTIFIED", None, True
    if passed is None or g in UNMEASURED_GATES:
        return "TESTING", None, False
    try:
        import gauntlet_backpressure as GB
        cls = GB.gate_class(g)
    except Exception:                                                        # noqa: BLE001
        cls = None
    return "FAILED", CV.terminal_of_gate_class(cls) or "FAILED", True


# ============================================================================ the observations
def observe_evidence(store: Store, src: Sources, state: dict[str, Any], *, graph_rows: list[dict[str, Any]],
                     ledger_rows: list[dict[str, Any]], sym_class: Mapping[str, str],
                     actors: Mapping[str, str], fam_mech: Mapping[str, str], absent: Absent,
                     at: str) -> dict[str, Any]:
    """Graph births -> COMPILED; ledger verdicts joined at (symbol, family) -> measured outcomes."""
    counts: Counter[str] = Counter()
    pair_sources: dict[str, list[str]] = state["pair_sources"]
    now_iso = at
    ledger_present = GATE_LEDGER.exists()
    for r in graph_rows:
        sid = seat_of_graph_source(r.get("source"))
        fam = str(r.get("family") or "")
        sym = str(r.get("symbol") or "").upper()
        srow = src.rows.get(sid) or src.add(sid, origin="hypothesis_graph.jsonl source label",
                                            source_class=classify_source(sid.split(":", 1)[-1]),
                                            registered=False)
        c = _src_counts(state, sid)
        c["first_at"] = c["first_at"] or str(r.get("at") or now_iso)
        if fam in BANNED_FAMILIES:
            counts["banned_family_rows"] += 1
            continue
        mech = fam_mech.get(fam, "UNKNOWN")
        inst = sym_class.get(sym)
        if inst is None:
            counts["event_lane_or_unclassified_symbol"] += 1
            continue
        if mech == "UNKNOWN" or mech not in actors:
            counts["family_without_mechanism"] += 1
            continue
        if srow["source_class"] == "UNCLASSIFIED":
            counts["unclassified_source"] += 1
            continue
        ax = axes_of_row(sym, fam, r.get("params"))
        coords = observed_coords(mech, inst, region=srow["region"], language=srow["language"],
                                 source_class=srow["source_class"],
                                 horizon=_HZ_OF_AXIS.get(str(ax.get("horizon"))),
                                 session=str(ax.get("session") or "") or None, actors=actors)
        fate = str(r.get("fate") or "BORN").upper()
        c["compiled"] += 1
        key = f"{sym}|{fam}"
        lst = pair_sources.setdefault(key, [])
        if sid not in lst and len(lst) < 8:
            lst.append(sid)
        store.observe(coords, "CANDIDATES", source=sid, why=f"graph {r.get('id')} born",
                      at=now_iso)
        counts["graph_births"] += 1
        if fate in ("FAILED", "CERTIFIED"):
            st = "CERTIFIED" if fate == "CERTIFIED" else "FAILED"
            proven = bool(srow["registered"] and srow["acquired"] and srow["pit"])
            store.observe(coords, st, source=sid, why=f"graph fate {fate}",
                          terminal=None if st == "CERTIFIED" else "FAILED", proven=proven,
                          at=now_iso)
            counts["graph_fates"] += 1
            if ledger_present:
                continue        # the same verdict is counted once, from the gate ledger below
            c["judged"] += 1
            c["measured"] += 1
            c["survived"] += 1 if st == "CERTIFIED" else 0
            c["last_measured_at"] = _later(c.get("last_measured_at"), r.get("at") or now_iso)
    for v in ledger_rows:
        sym = str(v.get("sym") or v.get("symbol") or "").upper()
        fam = str(v.get("family") or "")
        sids = pair_sources.get(f"{sym}|{fam}") or []
        if not sids:
            counts["verdicts_without_a_known_source"] += 1
            continue
        st, term, measured = outcome_terminal(v.get("passed"), v.get("terminal_gate"))
        mech = fam_mech.get(fam, "UNKNOWN")
        inst = sym_class.get(sym)
        w = 1.0 / len(sids)
        for sid in sids:
            srow = src.rows.get(sid)
            c = _src_counts(state, sid)
            c["judged"] += w
            if not measured or srow is None or inst is None or mech not in actors:
                continue
            c["measured"] += w
            c["survived"] += w if st == "CERTIFIED" else 0.0
            if term == "DUPLICATE":
                c["duplicates"] += w
            c["last_measured_at"] = _later(c.get("last_measured_at"), v.get("at") or now_iso)
            ax = axes_of_row(sym, fam, None)
            coords = observed_coords(mech, inst, region=srow["region"],
                                     language=srow["language"],
                                     source_class=srow["source_class"],
                                     horizon=_HZ_OF_AXIS.get(str(ax.get("horizon"))),
                                     session=None, actors=actors)
            proven = bool(srow["registered"] and srow["acquired"] and srow["pit"])
            store.observe(coords, "CANDIDATES", source=sid, why="docketed", at=now_iso)
            store.observe(coords, st, source=sid, terminal=term, proven=proven,
                          why=f"verdict {v.get('terminal_gate')} joined at (symbol, family)",
                          at=now_iso)
            counts["verdicts_joined"] += 1
    counts["pair_index_size"] = len(pair_sources)
    return dict(sorted(counts.items()))


def observe_133(store: Store, src: Sources, state: dict[str, Any], *, sym_class: Mapping[str, str],
                actors: Mapping[str, str], fam_mech: Mapping[str, str], absent: Absent,
                at: str, now: datetime) -> dict[str, Any]:
    """PR #133's cells, read-only: the strictest proven path this desk records."""
    if not MINING_DB.exists():
        absent.note("mining.db (PR #133)", f"{MINING_DB} is not on this tree: the #133 funnel and "
                                           "its ACTIVE/COLD receipts are UNMEASURED here")
        return {"status": UNMEASURED}
    out: Counter[str] = Counter()
    try:
        conn = sqlite3.connect(f"file:{MINING_DB.as_posix()}?mode=ro", uri=True, timeout=30)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        absent.note("mining.db (PR #133)", f"unopenable: {exc}")
        return {"status": UNMEASURED}
    try:
        recs = {str(r["source_id"]): int(r["n"]) for r in conn.execute(
            "SELECT source_id, COUNT(*) AS n FROM records GROUP BY source_id")}
        since = _iso(now - timedelta(days=ACTIVE_WINDOW_DAYS))
        receipts = {str(r["s"]): int(r["n"]) for r in conn.execute(
            "SELECT c.source_id AS s, COUNT(DISTINCT e.cell_id) AS n FROM cell_events e JOIN "
            "cells c ON c.cell_id=e.cell_id WHERE e.to_status='EVALUATED' AND e.at >= ? "
            "GROUP BY c.source_id", (since,))}
        rows = conn.execute("SELECT source_id, status, gauntlet_cell, doc FROM cells "
                            "LIMIT ?", (MAX_ROWS_PER_LOG,)).fetchall()
    except sqlite3.Error as exc:
        absent.note("mining.db (PR #133)", f"unreadable: {exc}")
        conn.close()
        return {"status": UNMEASURED}
    conn.close()
    for sid, n in recs.items():
        row = src.add(sid, origin="libs/mining (#133)",
                      source_class=classify_source(sid))
        row["fetched"] = n
        row["acquired"], row["acquired_basis"] = n > 0, "#133 PIT store records"
        row["pit"], row["pit_basis"] = n > 0, "#133 records carry available_for_decision_at"
        row["status_133"] = "ACTIVE" if receipts.get(sid, 0) >= 1 else "COLD"
    for r in rows:
        sid = str(r["source_id"])
        status = str(r["status"])
        try:
            doc = json.loads(str(r["doc"]))
        except ValueError:
            continue
        spec = doc.get("spec") or {}
        fam = str(spec.get("family") or "")
        mech = fam_mech.get(fam, "UNKNOWN")
        syms = [str(s).upper() for s in (doc.get("required_instruments") or
                                         [spec.get("symbol")]) if s]
        srow = src.rows.get(sid) or src.add(sid, origin="libs/mining (#133)",
                                            source_class=classify_source(sid))
        c = _src_counts(state, sid)
        c["extracted_133"] = int(c.get("extracted_133") or 0) + 1
        if fam in BANNED_FAMILIES or mech not in actors:
            out["no_mechanism"] += 1
            continue
        verdict = doc.get("verdict") or {}
        for sym in syms[:4]:
            inst = sym_class.get(sym)
            if inst is None or srow["source_class"] == "UNCLASSIFIED":
                continue
            coords = observed_coords(mech, inst, region=srow["region"],
                                     language=srow["language"],
                                     source_class=srow["source_class"], horizon=None,
                                     session=None, actors=actors)
            if status.startswith("BLOCKED_"):
                term = "BLOCKED_WITH_SUBSTITUTE" if "SUBSTITUTE" in status or \
                    doc.get("substitute") else ("DUPLICATE" if doc.get("duplicate_of")
                                                else "NOT_TRADEABLE")
                store.observe(coords, "CANDIDATES", source=sid, why=f"#133 {status}", at=at)
                store.observe(coords, "FAILED", source=sid, terminal=term,
                              why=f"#133 {status} {doc.get('rejection_reason') or ''}"[:200],
                              at=at)
                out["blocked"] += 1
            elif status == "RESEARCH_ONLY":
                store.observe(coords, "INGESTED", source=sid, why="#133 RESEARCH_ONLY", at=at)
            elif status in ("TESTABLE", "QUEUED", "EVALUATING"):
                store.observe(coords, "CANDIDATES" if status == "TESTABLE" else "TESTING",
                              source=sid, why=f"#133 {status}", at=at)
            elif status == "EVALUATED":
                st, term, measured = outcome_terminal(verdict.get("passed"),
                                                      verdict.get("terminal_gate"))
                proven = bool(measured and doc.get("available_for_decision_at")
                              and doc.get("mechanism_family") and doc.get("gauntlet_cell"))
                store.observe(coords, "CANDIDATES", source=sid, why="#133 docketed", at=at)
                store.observe(coords, st, source=sid, terminal=term, proven=proven,
                              why=f"#133 EVALUATED {verdict.get('terminal_gate')}", at=at)
                out["evaluated"] += 1
    return {"status": "MEASURED", "cells": len(rows), **dict(out)}


def observe_registered(store: Store, src: Sources, gen_index: Mapping[tuple[str, str], list[str]],
                       gen: Mapping[str, tuple[str, ...]], at: str) -> dict[str, int]:
    """A registered source raises its (region, class) cells to SOURCED; an acquired one to
    INGESTED. NOMINAL coverage: nothing here is a measured outcome, and nothing here attributes a
    cell to a source. Grouped per (region, class), so 500 grounds cost one pass over the ground."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for sid, row in src.rows.items():
        if not row["registered"] or row["source_class"] == "UNCLASSIFIED":
            continue
        g = groups.setdefault((row["region"], row["source_class"]),
                              {"acquired": False, "n": 0, "first": sid})
        g["n"] += 1
        g["acquired"] = bool(g["acquired"] or row["acquired"])
    n_s = n_i = 0
    for (region, klass), g in groups.items():
        keys = gen_index.get((region, klass), [])
        state = "INGESTED" if g["acquired"] else "SOURCE_HUNT"
        for k in keys:
            store.observe(gen[k], state, source=str(g["first"]), attribute=False, at=at,
                          why=f"{g['n']} registered {klass} source(s) in {region} ({state})")
        n_s += len(keys)
        n_i += len(keys) if g["acquired"] else 0
    return {"groups": len(groups), "sourced_cell_marks": n_s, "ingested_cell_marks": n_i}


def observe_book(store: Store, sym_class: Mapping[str, str], actors: Mapping[str, str],
                 fam_mech: Mapping[str, str], absent: Absent, at: str) -> dict[str, Any]:
    """Certified / forward / live cells, attributed to `market_native` only where the family is
    price-only -- its source IS the bar estate. Anything else stays unattributed and named."""
    out: Counter[str] = Counter()
    try:
        from research import axis_registry as AX
        info = {str(f): str(i) for f, (_m, i, _s) in AX.FAMILY_TABLE.items()}
    except Exception:                                                        # noqa: BLE001
        info = {}

    def hit(sym: str, fam: str, state: str, why: str, session: Any = None) -> None:
        mech = fam_mech.get(fam, "UNKNOWN")
        inst = sym_class.get(sym.upper())
        if inst is None or mech not in actors:
            out["unmapped"] += 1
            return
        if info.get(fam) != "price_only":
            out["unattributed_source"] += 1
            return
        coords = observed_coords(mech, inst, region="global", language="en",
                                 source_class="market_native", horizon=None,
                                 session=_tok(session) or None, actors=actors)
        store.observe(coords, "CANDIDATES", source="seat:broker_bars", why=why, at=at)
        store.observe(coords, state, source="seat:broker_bars", why=why, proven=True, at=at)
        out[state] += 1

    surv = _read_json(SURVIVORS)
    if isinstance(surv, Mapping) and isinstance(surv.get("survivors"), Mapping):
        for v in surv["survivors"].values():
            if isinstance(v, Mapping):
                spec = v.get("shadow_spec") if isinstance(v.get("shadow_spec"), Mapping) else {}
                hit(str(v.get("sym") or spec.get("symbol") or ""), str(spec.get("family") or ""),
                    "CERTIFIED", "ten-gate certificate (UNIVERSAL_SURVIVORS.json)",
                    spec.get("selector"))
    else:
        absent.note("universal_survivors", f"{SURVIVORS} unreadable: CERTIFIED is UNMEASURED")
    sl = _read_json(SLEEVES)
    rows = (sl.get("sleeves") if isinstance(sl, Mapping) else sl) or []
    for s in rows if isinstance(rows, list) else []:
        if isinstance(s, Mapping) and str(s.get("status") or "").upper() in ("LIVE", "STANDBY"):
            hit(str(s.get("symbol") or ""), str(s.get("family") or ""), "LIVE",
                f"sleeve {s.get('name')} {s.get('status')}", s.get("session"))
    if not rows:
        absent.note("sleeves", f"{SLEEVES} unreadable: LIVE is UNMEASURED")
    return dict(out)


# ============================================================================= the measurements
def principal_histogram(store: Store, keys: Iterable[str]) -> dict[str, Any]:
    stages: Counter[str] = Counter()
    terms: Counter[str] = Counter()
    for k in keys:
        cell = store.tensor._cells.get(tuple(k.split("|")))
        st = cell.state if cell is not None else "UNOBSERVED"
        m = store.meta.get(k, {})
        view = CV.principal_view(st, m.get("terminal") if st in ("FAILED", "DECAYED") else None)
        stages[str(view["stage"])] += 1
        if view["terminal"]:
            terms[str(view["terminal"])] += 1
    return {"stages": {s: int(stages.get(s, 0)) for s in CV.PRINCIPAL_LADDER},
            "terminals": {t: int(terms.get(t, 0)) for t in CV.PRINCIPAL_TERMINALS}}


def coverage_shares(store: Store, distinct: Sequence[str]) -> dict[str, Any]:
    n = len(distinct)
    nominal = proven = measured = 0
    for k in distinct:
        cell = store.tensor._cells.get(tuple(k.split("|")))
        if cell is None or cell.state == "UNOBSERVED":
            continue
        nominal += 1
        stage = CV.PRINCIPAL_OF_WORLD[cell.state]
        if stage in CV.MEASURED_OUTCOME_STAGES:
            measured += 1
            if store.meta.get(k, {}).get("proven"):
                proven += 1
    return {"n_distinct": n, "nominal_covered": nominal, "measured_outcome": measured,
            "proven_path_covered": proven, "nominal_covered_share": _share(nominal, n),
            "measured_outcome_share": _share(measured, n),
            "proven_path_covered_share": _share(proven, n),
            "definitions": {
                "nominal": "the cell holds ANY evidence -- a registered or fetched source, a "
                           "compiled candidate -- i.e. principal stage SOURCED or above",
                "proven_path": "the cell reached a measured outcome (JUDGED or above) through "
                               "a source whose registration, acquisition and PIT stamps are "
                               "all measured"}}


def effective_dimensions(keys: Sequence[str], *, cap: int = 20_000) -> dict[str, Any]:
    """The participation ratio of the one-hot axis incidence of `keys`: how many INDEPENDENT
    directions the cells span. A thousand cells differing only in instrument are ~one."""
    if len(keys) < 2:
        return {"value": UNMEASURED, "n": len(keys), "why": "fewer than two cells to compare"}
    try:
        import numpy as np
    except Exception:                                                        # noqa: BLE001
        return {"value": UNMEASURED, "n": len(keys), "why": "numpy unavailable"}
    # A HASH-ORDERED sample, so a cap never keeps one region or one mechanism by accident of
    # generation order.
    sample = sorted(keys, key=lambda k: hashlib.sha1(k.encode()).hexdigest())[:cap]
    cols: dict[tuple[int, str], int] = {}
    rows = [k.split("|") for k in sample]
    for r in rows:
        for i, v in enumerate(r):
            cols.setdefault((i, v), len(cols))
    x = np.zeros((len(rows), len(cols)), dtype=np.float32)
    for n, r in enumerate(rows):
        for i, v in enumerate(r):
            x[n, cols[(i, v)]] = 1.0
    x -= x.mean(axis=0, keepdims=True)
    try:
        s = np.linalg.svd(x, compute_uv=False)
    except Exception as exc:                                                 # noqa: BLE001
        return {"value": UNMEASURED, "n": len(rows), "why": f"svd failed: {exc}"}
    lam = (s.astype(float) ** 2)
    tot = float(lam.sum())
    if tot <= 0:
        return {"value": 1.0, "n": len(rows), "why": "every cell identical on every axis"}
    pr = tot * tot / float((lam * lam).sum())
    return {"value": round(pr, 4), "n": len(rows), "n_columns": len(cols),
            "sampled": len(keys) > cap,
            "method": "participation ratio (sum lambda)^2 / sum lambda^2 of the centred one-hot "
                      "axis-incidence covariance"}


def log_rates(graph_rows: Sequence[Mapping[str, Any]], ledger_rows: Sequence[Mapping[str, Any]],
              now: datetime) -> dict[str, Any]:
    """Created and judged per day over the SPAN of the rows this pass read -- the fallback when no
    organ publishes a window. Births are graph rows with fate BORN; verdicts are ledger rows (or,
    with no ledger, graph fate rows). Its age is published: a span ending days ago still prices a
    compute hour, but it may not throttle anything (see `throttle`)."""
    births = [t for r in graph_rows if str(r.get("fate") or "BORN").upper() == "BORN"
              and (t := _at(r.get("at"))) is not None]
    src = ledger_rows if ledger_rows else [r for r in graph_rows
                                           if str(r.get("fate") or "").upper()
                                           in ("FAILED", "CERTIFIED")]
    verdicts = [t for r in src if (t := _at(r.get("at"))) is not None]
    stamps = births + verdicts
    if len(stamps) < 2:
        return {"status": UNMEASURED, "why": "fewer than two dated rows in this pass"}
    lo, hi = min(stamps), max(stamps)
    days = max((hi - lo).total_seconds() / 86_400.0, 1.0 / 24.0)
    if days < 1.0:
        return {"status": UNMEASURED, "why": f"the rows span {days * 24:.1f}h, under a day"}
    return {"status": "MEASURED", "created_per_day": round(len(births) / days, 3),
            "judged_per_day": round(len(verdicts) / days, 3),
            "judged_per_hour": round(len(verdicts) / days / 24.0, 4),
            "ratio": _share(len(verdicts), len(births)) if births else None,
            "basis": ("gate ledger" if ledger_rows else "graph fate rows")
                     + f" over the {days:.1f}-day span of rows read this pass",
            "span_end": _iso(hi), "age_h": round((now - hi).total_seconds() / 3600.0, 2)}


def judging_vs_creation(state: dict[str, Any], absent: Absent,
                        fallback: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """created/day and judged/day, from the backpressure organ first (its 24h window)."""
    doc = _read_json(BACKPRESSURE)
    if isinstance(doc, Mapping):
        w = ((doc.get("windows") or {}).get("24h") or {})
        born = (w.get("intake") or {}).get("born_cells")
        judged = (w.get("testing") or {}).get("cells_judged")
        if isinstance(born, (int, float)) and isinstance(judged, (int, float)) and born > 0:
            return {"status": "MEASURED", "created_per_day": float(born),
                    "judged_per_day": float(judged),
                    "judged_per_hour": round(float(judged) / 24.0, 4),
                    "ratio": round(float(judged) / float(born), 6),
                    "basis": "GAUNTLET_BACKPRESSURE.json windows.24h", "at": doc.get("at")}
    doc = _read_json(MINING_METRICS)
    if isinstance(doc, Mapping):
        c, j = doc.get("cells_created_24h"), doc.get("cells_evaluated_24h")
        if isinstance(c, (int, float)) and isinstance(j, (int, float)) and c > 0:
            return {"status": "MEASURED", "created_per_day": float(c), "judged_per_day": float(j),
                    "judged_per_hour": round(float(j) / 24.0, 4),
                    "ratio": round(float(j) / float(c), 6),
                    "basis": "mining/MINING_METRICS.json (#133)"}
    absent.note("judging_vs_creation", f"neither {BACKPRESSURE.name} nor {MINING_METRICS.name} "
                                       "carries a 24h window: the log span is read instead")
    if fallback is not None and fallback.get("status") == "MEASURED":
        return dict(fallback)
    return {"status": UNMEASURED, "ratio": None, "judged_per_hour": None}


#: A reading older than this prices compute hours but never throttles: yesterday's backlog is not
#: a reason to hold back today's missions.
THROTTLE_MAX_AGE_H = 48.0


def throttle(jvc: Mapping[str, Any]) -> dict[str, Any]:
    ratio = jvc.get("ratio")
    age = jvc.get("age_h")
    stale = isinstance(age, (int, float)) and age > THROTTLE_MAX_AGE_H
    if jvc.get("status") != "MEASURED" or ratio is None or ratio >= 1.0 or stale:
        factor = 1.0
        why = ("the reading is stale ({age}h): it may not throttle".format(age=age) if stale
               else "judging keeps up with creation" if jvc.get("status") == "MEASURED"
               else "UNMEASURED: no throttle engages on an absent reading")
    else:
        factor = max(0.0, float(ratio))
        why = (f"judged/day {jvc.get('judged_per_day')} < created/day "
               f"{jvc.get('created_per_day')}: this organ's own emission is scaled by "
               f"{factor:.3f}, onboarding first, never below the {MISSION_FLOOR}-mission floor")
    n = max(MISSION_FLOOR, int(math.ceil(MAX_MISSIONS * factor)))
    # Onboarding is what the throttle cuts first, and even it keeps one slot: new ground is the
    # exploration floor of this organ, and a floor at zero is not a floor.
    onboard = max(1, int(math.floor(n * ONBOARDING_SHARE * factor)))
    if factor >= 1.0:
        onboard = int(round(n * ONBOARDING_SHARE))
    return {"engaged": factor < 1.0, "factor": round(factor, 6), "missions": n,
            "onboarding_missions_max": onboard, "floor": MISSION_FLOOR, "why": why,
            "scope": "this organ's own mission emission and onboarding share only; no miner, "
                     "acquirer or source is slowed by it"}


# =============================================================================== the source ROI
def source_roi(src: Sources, state: dict[str, Any], store: Store, *, now: datetime,
               judge_per_hour: float | None, book: Mapping[str, Any],
               live_mechs: set[str]) -> dict[str, Any]:
    """Per source: the funnel, info gain per compute hour, incremental k_eff, ACTIVE/COLD, and the
    auto-retire flag. A source is never deleted: a retire flag REDIRECTS BUDGET."""
    measured_by: dict[str, list[str]] = defaultdict(list)
    survivors_by: dict[str, list[str]] = defaultdict(list)
    forward_by: Counter[str] = Counter()
    live_by: Counter[str] = Counter()
    for c in store.tensor.cells():
        stage = CV.PRINCIPAL_OF_WORLD[c.state]
        m = store.meta.get(c.key, {})
        for sid in m.get("sources") or []:
            if stage in CV.MEASURED_OUTCOME_STAGES:
                measured_by[sid].append(c.key)
            if c.state in ("CERTIFIED", "FORWARD", "LIVE"):
                survivors_by[sid].append(c.value("mechanism"))
            if c.state == "FORWARD":
                forward_by[sid] += 1
            if c.state == "LIVE":
                live_by[sid] += 1
    owners: Counter[str] = Counter()
    for sid, keys in measured_by.items():
        for k in set(keys):
            owners[k] += 1
    try:
        from libs.research import breadth_credit as BC
    except Exception:                                                        # noqa: BLE001
        BC = None                                                            # type: ignore[assignment]
    out: dict[str, Any] = {}
    active_cut = now - timedelta(days=ACTIVE_WINDOW_DAYS)
    for sid, row in sorted(src.rows.items()):
        c = state["sources"].get(sid) or {}
        judged = float(c.get("judged") or 0.0)
        measured = float(c.get("measured") or 0.0)
        survived = float(c.get("survived") or 0.0)
        compiled = float(c.get("compiled") or 0.0) + float(c.get("extracted_133") or 0)
        novel = sum(1 for k in set(measured_by.get(sid, [])) if owners[k] == 1)
        hours: float | None = None
        if judge_per_hour and judge_per_hour > 0:
            hours = judged / judge_per_hour
        gain: Any
        if hours is None:
            gain = UNMEASURED
        elif hours <= 0:
            gain = UNMEASURED if judged == 0 else 0.0
        else:
            gain = round(novel / hours, 6)
        # incremental k_eff: each survivor added to the book at the correlation its mechanism
        # implies -- the book's own rho where the mechanism is already live, the cross rho where not
        dk: Any = UNMEASURED
        if book.get("status") == "MEASURED" and BC is not None:
            if judged <= 0:
                dk = UNMEASURED
            else:
                n, k, acc = float(book["n_nominal"]), float(book["k_eff"]), 0.0
                for mech in survivors_by.get(sid, []):
                    rho = float(book["rho_book"] if mech in live_mechs else book["rho_cross"])
                    try:
                        step = BC.marginal_k_eff(n, k, rho)
                    except ValueError:
                        break
                    acc += step
                    n, k = n + 1.0, k + step
                dk = round(acc, 6)
        last = _at(c.get("last_measured_at"))
        status = row.get("status_133") or ("ACTIVE" if last is not None and last >= active_cut
                                           else "COLD")
        first = _at(c.get("first_at"))
        days = (now - first).total_seconds() / 86_400 if first else 0.0
        adequate = measured >= RETIRE_MIN_JUDGED and days >= RETIRE_MIN_DAYS
        retire = bool(adequate and novel == 0 and survived == 0)
        fetched = row.get("fetched")
        stranded = bool(isinstance(fetched, (int, float)) and fetched >= STRANDED_MIN_FETCHED
                        and compiled == 0)
        out[sid] = {
            "source_class": row["source_class"], "region": row["region"],
            "language": row["language"], "origin": row["origin"],
            "funnel": {"fetched": fetched if fetched is not None else UNMEASURED,
                       "extracted": round(compiled, 3), "compiled": round(compiled, 3),
                       "judged": round(judged, 3), "survived": round(survived, 3),
                       "forward": int(forward_by.get(sid, 0)), "live": int(live_by.get(sid, 0))},
            "proven_links": {"registered": bool(row["registered"]),
                             "acquired": bool(row["acquired"]),
                             "acquired_basis": row["acquired_basis"],
                             "pit": row["pit"] if row["pit"] is not None else UNMEASURED,
                             "pit_basis": row["pit_basis"],
                             "extracted": compiled > 0, "measured_outcome": measured > 0},
            "novel_measured_cells": novel,
            "compute_hours": round(hours, 4) if hours is not None else UNMEASURED,
            "info_gain_per_compute_hour": gain,
            "incremental_keff": dk,
            "status": status,
            "status_basis": ("#133 receipts (>=1 cell EVALUATED in 30 days)" if row.get("status_133")
                             else "re-derived: a measured outcome in the last 30 days"),
            "auto_retire": {"flag": retire, "action": "REDIRECT_BUDGET" if retire else None,
                            "adequately_sampled": adequate, "measured": round(measured, 3),
                            "days_on_record": round(days, 2),
                            "why": ("adequately sampled and zero novel information: redirect its "
                                    "budget; the source is kept and its scout never stops"
                                    if retire else "not flagged")},
            "stranded_ingestion": stranded,
        }
    return out


# ================================================================================== the missions
MOVE: dict[str, str] = {
    "UNEXPLORED": "onboard ground: register a {sc} source for {region} in {lang} with a durable "
                  "cursor (libs/mining/sources.yaml or deep_forest_sources.json) aimed at "
                  "{mech} evidence that transmits into {inst}",
    "SOURCED": "fetch it: run the acquirer on the registered {sc} source(s) for {region} so the "
               "records land in a PIT store with available_for_decision_at",
    "INGESTED": "extract and compile: turn the ingested {sc} records for {region} into a {mech} "
                "cell on {inst} ({example}) and donate it to the docket",
    "COMPILED": "judge it: the {mech} x {inst} cell from {sc}/{region} sits unjudged; route it up "
                "judge_coverage's order so the gauntlet returns a measured outcome",
}


def missions(store: Store, gen: Mapping[str, tuple[str, ...]], distinct: Sequence[str], *,
             thr: Mapping[str, Any], sym_by_class: Mapping[str, list[str]],
             family_of_mech: Mapping[str, list[str]], live_by_inst: Mapping[str, int],
             deadline: float) -> dict[str, Any]:
    """The emptiest high-EVIG projected cells, each with the ONE move that fills it."""
    tensor = store.tensor
    marg = tensor.marginals(PROJECTION)
    measured_proj: set[tuple[str, ...]] = set()
    idx = [CV.GLOBAL_AXES.index(a) for a in PROJECTION]
    for c in tensor.cells():
        if CV.PRINCIPAL_OF_WORLD[c.state] in CV.MEASURED_OUTCOME_STAGES:
            measured_proj.add(tuple(c.coordinates[i] for i in idx))
    exemplar: dict[tuple[str, ...], tuple[str, ...]] = {}
    for coords in gen.values():
        exemplar.setdefault(tuple(coords[i] for i in idx), coords)

    def cap(values: Mapping[str, str]) -> float:
        return 1.0 / (1.0 + float(live_by_inst.get(values.get("instrument", ""), 0)))

    scorer = tensor.evig_scorer(PROJECTION, capacity_of=cap, max_neighbours=200)
    holes: list[dict[str, Any]] = []
    # EVERY PROJECTED CELL OF THE DESIGN IS A CANDIDATE HOLE, stored or not: a coordinate absent
    # from the store is at the floor, and that is exactly the emptiest ground.
    truncated = False
    for key in sorted(exemplar):
        if key in measured_proj:
            continue
        if time.monotonic() > deadline:
            truncated = True
            break
        row = marg.get(key)
        values = dict(zip(PROJECTION, key, strict=True))
        s, br = scorer(values)
        best = str(row["best"]) if row is not None else tensor.ladder.floor
        stage = CV.PRINCIPAL_OF_WORLD[best]
        holes.append({"values": values, "stage": stage, "evig": round(float(s), 6),
                      "breakdown": {k: br.get(k) for k in ("prior_p_edge", "reachability",
                                                           "novelty", "capacity", "cost")},
                      "n_cells": int(row["n"]) if row is not None else 0,
                      "exemplar": exemplar[key]})
    # ONE MOVE, ONE MISSION. Onboarding and fetching are moves on a (region, source class) --
    # registering a Korean credit source fills every mechanism x instrument cell it feeds -- so
    # the holes are grouped by the move that fills them and ranked by the EVIG they fill in
    # total. Compiling and judging are moves on one mechanism x instrument, and stay one each.
    groups: dict[tuple[str, ...], dict[str, Any]] = {}
    for h in holes:
        v = h["values"]
        gk: tuple[str, ...] = ((h["stage"], v["region"], v["source_class"])
                               if h["stage"] in ("UNEXPLORED", "SOURCED") else
                               (h["stage"], v["region"], v["source_class"], v["mechanism"],
                                v["instrument"]))
        g = groups.get(gk)
        if g is None:
            groups[gk] = {**h, "evig_best": h["evig"], "evig": h["evig"], "fills": [h["values"]]}
        else:
            g["evig"] = round(g["evig"] + h["evig"], 6)
            g["fills"].append(h["values"])
            if h["evig"] > g["evig_best"]:
                g.update({"values": h["values"], "evig_best": h["evig"],
                          "breakdown": h["breakdown"], "exemplar": h["exemplar"]})
    ranked = sorted(groups.values(), key=lambda g: (-g["evig"], tuple(g["values"].values())))
    n_total = int(thr["missions"])
    n_onboard = int(thr["onboarding_missions_max"])
    onboard = [g for g in ranked if g["stage"] == "UNEXPLORED"]
    convert = [g for g in ranked if g["stage"] != "UNEXPLORED"]
    cap = max(1, int(math.ceil(n_total * DIVERSITY_SHARE)))
    used: Counter[tuple[str, str]] = Counter()
    taken: list[dict[str, Any]] = []
    chosen = _diverse(onboard, n_onboard, cap=cap, used=used, taken=taken)
    chosen += _diverse(convert, max(0, n_total - len(chosen)), cap=cap, used=used, taken=taken)
    if len(chosen) < n_total:                        # nothing left to convert: fill with ground
        chosen += _diverse(onboard, n_total - len(chosen), cap=cap, used=used, taken=taken)
    chosen.sort(key=lambda g: -g["evig"])
    emitted: list[dict[str, Any]] = []
    for h in chosen:
        v = h["values"]
        ex = dict(zip(CV.GLOBAL_AXES, h["exemplar"], strict=True))
        syms = sym_by_class.get(v["instrument"], [])[:3]
        fams = [f for f in family_of_mech.get(v["mechanism"], []) if f not in BANNED_FAMILIES]
        example = f"{fams[0]} on {syms[0]}" if fams and syms else f"a {v['mechanism']} family"
        grouped = h["stage"] in ("UNEXPLORED", "SOURCED")
        mechs = sorted({f["mechanism"] for f in h["fills"]})
        move = MOVE.get(h["stage"], MOVE["COMPILED"]).format(
            sc=v["source_class"], region=v["region"], lang=ex["language"],
            mech=(", ".join(mechs[:4]) + (" ..." if len(mechs) > 4 else "")) if grouped
            else v["mechanism"], inst="MT5 instruments" if grouped else v["instrument"],
            example=example)
        cell = ("|".join(f"{a}={v[a]}" for a in ("region", "source_class")) if grouped
                else "|".join(f"{a}={v[a]}" for a in PROJECTION))
        emitted.append({"cell": cell, "values": v, "exemplar_cell": ex, "stage": h["stage"],
                        "next_move": move, "evig": h["evig"], "evig_best_cell": h["evig_best"],
                        "cells_filled": len(h["fills"]), "mechanisms": mechs,
                        "evig_breakdown": h["breakdown"],
                        "family": fams[0] if fams and not grouped else None,
                        "symbols": syms if not grouped else [],
                        "kind": "onboarding" if h["stage"] == "UNEXPLORED" else "conversion"})
    deferred = len(groups) - len(emitted)
    return {"n_holes": len(holes), "n_moves": len(groups), "emitted": emitted,
            "deferred": max(0, deferred), "ranking_truncated_by_budget": truncated,
            "deferred_why": ("deferred, never deleted: re-ranked every pass and emitted the "
                             "moment the throttle or the ranking admits them")}


#: BREADTH IN THE MISSION SET ITSELF. EVIG ties across whole faces of the tensor (every academic
#: calendar cell of one region scores alike), so a plain top-k hands the machine forty copies of
#: one move. No region, mechanism or source class takes more than this share of one pass.
DIVERSITY_SHARE = 0.15


def _diverse(holes: Sequence[dict[str, Any]], k: int, *, cap: int,
             used: Counter[tuple[str, str]], taken: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedy top-k by EVIG under per-axis caps SHARED across the whole pass (`used`, `taken`);
    relaxes the caps only if it runs short, so it never returns fewer than it could."""
    out: list[dict[str, Any]] = []
    if k <= 0:
        return out
    for h in holes:
        if any(h is t for t in taken):
            continue
        v = h["values"]
        keys = [("region", v["region"]), ("mechanism", v["mechanism"]),
                ("source_class", v["source_class"])]
        if any(used[x] >= cap for x in keys):
            continue
        out.append(h)
        taken.append(h)
        for x in keys:
            used[x] += 1
        if len(out) >= k:
            return out
    for h in holes:                                     # short: relax, never return fewer
        if len(out) >= k:
            break
        if not any(h is t for t in taken):
            out.append(h)
            taken.append(h)
    return out


def donate(emitted: Sequence[Mapping[str, Any]], *, at: str, day: str, dry_run: bool,
           conn: Any) -> dict[str, Any]:
    """The missions reach the machine two ways the desk already consumes."""
    rows = []
    for m in emitted:
        v = m["values"]
        rows.append({
            "kind": GAP_KIND, "source": SOURCE_TYPE, "available_time": at,
            "title": f"coverage gap: {v['mechanism']} x {v['instrument']} from "
                     f"{v['source_class']} ({v['region']}) is {m['stage']}",
            "description": m["next_move"], "cell": m["cell"], "state": m["stage"],
            "next_move": m["next_move"], "evig": m["evig"], "family": m.get("family"),
            "symbols": list(m.get("symbols") or []), "mission_kind": m["kind"],
            "consumer": "miner_candidate_compiler -> deepening_worker (coverage_gap specialist)"})
    out: dict[str, Any] = {"intelligence_rows": 0, "discoveries_recorded": 0,
                           "discoveries_seen": 0, "dry_run": dry_run}
    if dry_run:
        return out
    path = MISSIONS_DIR / f"missions_{day}.json"
    _write_atomic(path, {"generated_at": at, "source": SOURCE_TYPE, "rows": rows})
    out["intelligence_rows"] = len(rows)
    out["path"] = str(path)
    if conn is None:
        out["registry"] = "UNMEASURED: canonical registry unreachable"
        return out
    try:
        from libs.moat import registry as R
    except Exception as exc:                                                 # noqa: BLE001
        out["registry"] = f"UNMEASURED: {type(exc).__name__}"
        return out
    for m, row in zip(emitted, rows, strict=True):
        try:
            _, created = R.record_discovery(
                source_id=f"{SOURCE_TYPE}:global", source_type=SOURCE_TYPE,
                mechanism=str(m["values"]["mechanism"]), origin="DESK", generator=SOURCE_TYPE,
                conn=conn, information=str(m["values"]["source_class"]),
                economic_rationale=str(m["next_move"])[:800],
                assets=list(m.get("symbols") or []),
                sessions=[str(m["exemplar_cell"]["session"])],
                regimes=[str(m["exemplar_cell"]["regime"])],
                horizons=[str(m["exemplar_cell"]["horizon"])],
                exact_rule_if_known=f"global:{m['cell']} -> {m['stage']}",
                novelty=float(m["evig_breakdown"].get("novelty") or 1.0),
                confidence=float(m["evig_breakdown"].get("prior_p_edge") or CV.PRIOR),
                falsifier="the cell is tested and the mechanism does not separate forward returns",
                payload={**row, "law": "LAWS 5f: an explicit frontier row, not a blind spot"})
        except Exception:                                                    # noqa: BLE001
            continue
        out["discoveries_recorded" if created else "discoveries_seen"] += 1
    return out


# ======================================================================================= the run
def build(*, budget_s: float = BUDGET_S, dry_run: bool = False, now: datetime | None = None,
          conn: Any = None) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(float(budget_s), 5.0)
    now = now or _now()
    at = _iso(now)
    absent = Absent()
    own = conn is None
    if conn is None:
        try:
            from libs.moat import registry as R
            conn = R.connect()
        except Exception as exc:                                             # noqa: BLE001
            conn = None
            absent.note("registry", f"canonical registry unreachable: {type(exc).__name__}")
    try:
        state = load_state()
        state["first_at"] = state.get("first_at") or at
        actors = mechanism_actor()
        fam_mech = family_mechanism()
        sym_class = universe(absent)
        gen, gen_meta = generate(actors)
        gen_index: dict[tuple[str, str], list[str]] = defaultdict(list)
        for k, coords in gen.items():
            gen_index[(coords[0], coords[2])].append(k)
        cursor = state["cursor"]
        read_share = t0 + 0.45 * (deadline - t0)
        graph_rows = read_log(GRAPH, cursor, now=now, deadline=read_share, absent=absent,
                              name="hypothesis_graph")
        ledger_rows = read_log(GATE_LEDGER, cursor, now=now,
                               deadline=t0 + 0.6 * (deadline - t0), absent=absent,
                               name="gate_verdict_ledger")
        graph_seats = {seat_of_graph_source(r.get("source")) for r in graph_rows}
        graph_seats |= set(state["sources"])
        src = load_sources(absent, conn, sorted(s for s in graph_seats if s.startswith("seat:")))
        store = Store(state)
        obs_reg = observe_registered(store, src, gen_index, gen, at)
        obs_ev = observe_evidence(store, src, state, graph_rows=graph_rows,
                                  ledger_rows=ledger_rows, sym_class=sym_class, actors=actors,
                                  fam_mech=fam_mech, absent=absent, at=at)
        obs_133 = observe_133(store, src, state, sym_class=sym_class, actors=actors,
                              fam_mech=fam_mech, absent=absent, at=at, now=now)
        obs_book = observe_book(store, sym_class, actors, fam_mech, absent, at)

        observed = {c.key for c in store.tensor.cells() if c.state != "UNOBSERVED"}
        distinct = sorted(set(gen) | observed)
        vocab = vocabulary(actors, (c.value("language") for c in store.tensor.cells()))
        nominal = CV.nominal_cells(vocab)
        shares = coverage_shares(store, distinct)
        measured_keys = [k for k in distinct
                         if (cell := store.tensor._cells.get(tuple(k.split("|")))) is not None
                         and CV.PRINCIPAL_OF_WORLD[cell.state] in CV.MEASURED_OUTCOME_STAGES]
        eff_measured = effective_dimensions(measured_keys)
        eff_design = effective_dimensions(list(gen))

        jvc = judging_vs_creation(state, absent, log_rates(graph_rows, ledger_rows, now))
        thr = throttle(jvc)
        sym_by_class: dict[str, list[str]] = defaultdict(list)
        for s, klass in sorted(sym_class.items()):
            sym_by_class[klass].append(s)
        family_of_mech: dict[str, list[str]] = defaultdict(list)
        for f, m in sorted(fam_mech.items()):
            family_of_mech[m].append(f)
        live_mechs: set[str] = set()
        live_by_inst: Counter[str] = Counter()
        for c in store.tensor.cells():
            if c.state == "LIVE":
                live_mechs.add(c.value("mechanism"))
                live_by_inst[c.value("instrument")] += 1
        mis = missions(store, gen, distinct, thr=thr, sym_by_class=sym_by_class,
                       family_of_mech=family_of_mech, live_by_inst=live_by_inst,
                       deadline=t0 + 0.9 * (deadline - t0))
        handed = donate(mis["emitted"], at=at, day=now.strftime("%Y%m%d"), dry_run=dry_run,
                        conn=conn)
        try:
            from libs.research import breadth_credit as BC
            book = BC.book_state(_read_json(BREADTH) or {})
        except Exception as exc:                                             # noqa: BLE001
            book = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
        if book.get("status") != "MEASURED":
            absent.note("effective_breadth", f"{BREADTH.name}: {book.get('why')} -- incremental "
                                             "k_eff per source is UNMEASURED")
        roi = source_roi(src, state, store, now=now, judge_per_hour=jvc.get("judged_per_hour"),
                         book=book, live_mechs=live_mechs)
        by_class: dict[str, dict[str, Any]] = {}
        for sid, r in roi.items():
            b = by_class.setdefault(r["source_class"], {"sources": 0, "active": 0, "judged": 0.0,
                                                        "survived": 0.0, "retire_flags": 0})
            b["sources"] += 1
            b["active"] += int(r["status"] == "ACTIVE")
            b["judged"] += float(r["funnel"]["judged"])
            b["survived"] += float(r["funnel"]["survived"])
            b["retire_flags"] += int(r["auto_retire"]["flag"])
        by_region: dict[str, dict[str, Any]] = {}
        for k in distinct:
            reg = k.split("|", 1)[0]
            cell = store.tensor._cells.get(tuple(k.split("|")))
            b = by_region.setdefault(reg, {"distinct": 0, "nominal": 0, "proven": 0})
            b["distinct"] += 1
            if cell is not None and cell.state != "UNOBSERVED":
                b["nominal"] += 1
                if CV.PRINCIPAL_OF_WORLD[cell.state] in CV.MEASURED_OUTCOME_STAGES and \
                        store.meta.get(k, {}).get("proven"):
                    b["proven"] += 1
        for b in by_region.values():
            b["proven_share"] = _share(b["proven"], b["distinct"])
        classes_without_source = sorted(set(CV.SOURCE_CLASSES) - {
            r["source_class"] for r in src.rows.values() if r["registered"]})
        doc = {
            "at": at, "schema": "global_coverage_tensor/1",
            "elapsed_s": round(time.monotonic() - t0, 2), "budget_s": float(budget_s),
            "dry_run": bool(dry_run), "rule": RULE,
            # THE FIVE KEYS THE CRO CYCLE READS (PR #154). Pinned by a test.
            "nominal": nominal,
            "distinct": len(distinct),
            "effective_independent": eff_measured.get("value"),
            "proven_path_covered_share": shares["proven_path_covered_share"],
            "top_missions": [{"cell": m["cell"], "stage": m["stage"], "next_move": m["next_move"],
                              "evig": m["evig"], "cells_filled": m["cells_filled"]}
                             for m in mis["emitted"][:10]],
            "three_numbers": {
                "nominal_cells": nominal, "nominal_log10": round(math.log10(max(nominal, 1)), 3),
                "mechanistically_distinct_cells": len(distinct),
                "effective_independent_dimensions": eff_measured,
                "effective_independent_dimensions_of_the_design": eff_design,
                "why": "nominal is the literal product of the fourteen vocabularies; distinct is "
                       "the compatibility-generated set plus every observed cell; effective "
                       "counts the independent directions the MEASURED cells actually span"},
            "coverage": shares,
            "principal_ladder": principal_histogram(store, distinct),
            "ladder_mapping": {"principal_of_world": dict(CV.PRINCIPAL_OF_WORLD),
                               "terminals": list(CV.PRINCIPAL_TERMINALS),
                               "terminal_of_failure_class": dict(CV.TERMINAL_OF_FAILURE_CLASS),
                               "why": "one ladder: the principal's stages are a view of the "
                                      "world ladder the tensors already share"},
            "axes": list(CV.GLOBAL_AXES),
            "vocabulary_sizes": {a: len(v) for a, v in vocab.items()},
            "source_classes": list(CV.SOURCE_CLASSES),
            "source_classes_without_a_registered_source": classes_without_source,
            "generator": gen_meta,
            "observations": {"registered": obs_reg, "evidence": obs_ev, "mining_133": obs_133,
                             "book": obs_book},
            "by_region": dict(sorted(by_region.items())),
            "by_source_class": dict(sorted(by_class.items())),
            "judging_vs_creation": jvc, "throttle": thr,
            "missions": {"n_holes": mis["n_holes"], "n_moves": mis["n_moves"],
                         "emitted": len(mis["emitted"]),
                         "deferred": mis["deferred"], "deferred_why": mis["deferred_why"],
                         "handed_to_the_machine": handed, "rows": mis["emitted"]},
            "sources": {"n": len(src.rows),
                        "active": sum(1 for r in roi.values() if r["status"] == "ACTIVE"),
                        "cold": sum(1 for r in roi.values() if r["status"] == "COLD"),
                        "retire_flags": sum(1 for r in roi.values() if r["auto_retire"]["flag"]),
                        "stranded": sorted(s for s, r in roi.items() if r["stranded_ingestion"]),
                        "roi_artifact": str(ROI_OUT.name)},
            "state": {"first_at": state["first_at"], "cursor": state["cursor"],
                      "persisted_cells": 0},
            "unmeasured": absent.to_json(),
        }
        roi_doc = {
            "at": at, "schema": "source_roi/1",
            "info_gain_per_compute_hour": {s: r["info_gain_per_compute_hour"]
                                           for s, r in roi.items()},
            "incremental_keff": {s: r["incremental_keff"] for s, r in roi.items()},
            "funnel": {s: r["funnel"] for s, r in roi.items()},
            "sources": roi,
            "compute_basis": {"judged_per_hour": jvc.get("judged_per_hour"),
                              "basis": jvc.get("basis", UNMEASURED),
                              "why": "compute hours = judged cells / cells judged per judge-hour"},
            "book": {k: book.get(k) for k in ("status", "n_nominal", "k_eff", "rho_book",
                                              "rho_cross", "why")},
            "retire_rule": (f"flag only after >= {RETIRE_MIN_JUDGED} measured outcomes and >= "
                            f"{RETIRE_MIN_DAYS:.0f} days with zero novel cells and zero "
                            "survivors; the flag REDIRECTS BUDGET and never deletes a source"),
            "unmeasured": absent.to_json(),
        }
        if not dry_run:
            state["cells"] = store.dump()
            doc["state"]["persisted_cells"] = len(state["cells"])
            _write_atomic(OUT, doc)
            _write_atomic(ROI_OUT, roi_doc)
            _write_atomic(STATE, state)
        doc["_roi"] = roi_doc
        return doc
    finally:
        if own and conn is not None:
            with contextlib.suppress(Exception):
                conn.close()


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the global coverage tensor, source ROI and "
                                             "missing-cell missions")
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled shape)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    a = ap.parse_args(list(argv) if argv is not None else None)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run)
    cov = doc["coverage"]
    print(f"global coverage tensor: nominal {doc['nominal']:.3e}  distinct {doc['distinct']}  "
          f"effective {doc['effective_independent']}", flush=True)
    print(f"  covered: nominal {cov['nominal_covered_share']}  measured "
          f"{cov['measured_outcome_share']}  proven-path {cov['proven_path_covered_share']}")
    print(f"  missions {doc['missions']['emitted']} emitted, {doc['missions']['deferred']} "
          f"deferred; throttle {doc['throttle']['factor']}; sources {doc['sources']['n']}")
    for m in doc["top_missions"][:10]:
        print(f"  EVIG {m['evig']:.5f} {m['stage']:10s} {m['cell'][:100]}")
    if a.dry_run:
        print("  --dry-run: nothing written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
