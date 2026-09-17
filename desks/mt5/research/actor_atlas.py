#!/usr/bin/env python3
"""THE ACTOR / CONSTRAINT ATLAS -- who is FORCED to transact, why, and where it shows.

WHY THIS EXISTS (ledger M11). The desk's candidate supply is dominated by indicator mining: take
a series, take a transformation, take a horizon, test the cross product. That population has a
known pathology -- it is drawn from the space of things that could be true of ANY series, so
every survivor is a multiple-testing artefact until proven otherwise, and the trial budget it
spends raises the bar for everything else on the docket. The alternative is not a better
indicator. It is a different QUESTION: name a participant who must transact regardless of price,
name the rule that forces them, name the public series or calendar that shows the forcing, and
only then ask what it does to a Fusion-executable instrument.

**CANDIDATES FROM WHO MUST TRANSACT BEAT CANDIDATES FROM INDICATOR MINING.** Not because they
win more often -- that is the gauntlet's verdict, not this module's -- but because they arrive
with a mechanism attached, which is the thing `economic_prior` asks for and the thing a chart
pattern can never supply. A forced-flow claim survives a regime change for a reason that can be
stated in advance; a momentum variant survives until it does not.

THE FOUR-PART CHAIN, and a row without all four is not an atlas row:

    ACTOR -> CONSTRAINT -> OBSERVABLE -> MARKET IMPACT

`actor` is a participant, never a strategy. `constraint` is the rule, mandate or contract that
removes their discretion. `observable` is the PUBLIC or point-in-time series/calendar that shows
the constraint binding -- and the atlas records, per row, whether this box can actually reach it,
because an observable nobody here can measure produces a hypothesis nobody here can test (L1.49:
a gate that never ran is a claim the desk cannot cash). `market_impact` is direction, instruments,
horizon and session.

WHERE THE INSTRUMENTS COME FROM. Never a hand-kept list: every row declares SELECTORS (an asset
class, a currency leg, a venue bundle) and they are resolved against MetaTrader's own registry
(`data/universe/universe.json`) and filtered through `universe_policy.may_hypothesise`. Under the
two-lane order (2026-09-06) single-name equities are traded on news and earnings and are NEVER
hunted for statistical hypotheses, so an equity can never leave this module as a discovery --
not because a list excludes it, but because the lane fence drops it. A selector that resolves to
nothing is recorded as an empty row, which is a measurement about the broker's book.

WHAT ENRICHES THE SEED, because a declared table that never learns is a document:

  * `data/forced_flow_calendar.json` -- the DATED windows. A row naming calendar kinds gets its
    event count and next window attached, and every calendar actor the seed does NOT name is
    reported, so the gap between "what forces flow" and "what the atlas knows" is visible.
  * `data/axis_registry.jsonl` -- the desk's own judged cells, tagged by `economic_actor`. That
    is how the atlas says which actors have been TESTED and how those cells fared, and which
    have never been touched at all.
  * the registry's `claims` table -- every claim naming an actor, read through
    `lead_schema` (`structured.actor` when a seat declared one, the row's own words otherwise).

WHAT IT PRODUCES. One DISCOVERY per row that has BOTH a measurable observable and at least one
MT5 instrument, recorded in the canonical registry as `source_type="actor_atlas"`,
`origin="MOAT"`, state UNPROCESSED, for the discovery compiler to expand. Deduped by the
registry's own content hash, so a row recorded on ten passes is one discovery with one lineage.
Nothing here scores, ranks or gates: the atlas says where to look.

    python actor_atlas.py
    python actor_atlas.py --dry-run     # build and print; write nothing, record nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as reg  # noqa: E402
from libs.research import lead_schema as ls  # noqa: E402

UNIVERSE = _DESK / "data" / "universe" / "universe.json"
CALENDAR = _DESK / "data" / "forced_flow_calendar.json"
AXIS_CELLS = _DESK / "data" / "axis_registry.jsonl"
DATABASE = _DESK / "data" / "actor_atlas.json"
REPORT = _DESK / "reports" / "ACTOR_ATLAS.json"

UNMEASURED = "UNMEASURED"
SOURCE_ID = "actor_atlas"
#: The six fields every atlas row must carry. A row missing any of them is not an atlas row: it
#: is a hunch with an actor's name on it, and the validator says so rather than publishing it.
ROW_FIELDS: tuple[str, ...] = ("actor", "constraint", "observable", "market_impact",
                               "mt5_instruments", "source")
DIRECTIONS: tuple[str, ...] = ("buy", "sell", "two_sided", "volatility", UNMEASURED)
MAX_AXIS_LINES = 400_000
MAX_CLAIMS = 4000
RULE = "candidates from who must transact beat candidates from indicator mining"


# --------------------------------------------------------------------------- the universe fence
def _registry_rows() -> dict[str, dict[str, Any]]:
    """MetaTrader's own registry. Read at CALL TIME, never cached at import, so a test can point
    `UNIVERSE` at a fixture and the fence still answers from it."""
    try:
        data = json.loads(Path(UNIVERSE).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k).upper(): v for k, v in data.items() if isinstance(v, dict)}


def _may_hypothesise() -> Any:
    """`universe_policy.may_hypothesise`, or a stand-in that admits nothing it cannot check.

    THE STAND-IN IS NOT A LOOPHOLE AND IT IS NOT PERMISSIVE EITHER. If the policy module cannot
    be imported, the fence falls back to the registry's own `asset_class`, refusing every class
    the hypothesis lane does not name -- so an unreachable import can never be the reason an
    equity reaches the docket.
    """
    try:
        from research.universe_policy import may_hypothesise
    except ImportError:  # pragma: no cover - import-context dependent
        try:
            from universe_policy import may_hypothesise  # type: ignore[no-redef]
        except ImportError:
            return _fallback_may_hypothesise
    return may_hypothesise


_HYPOTHESIS_CLASSES = frozenset({
    "forex", "forex majors", "forex crosses", "forex exotics", "fx", "commodity", "commodities",
    "soft commodity", "soft commodities", "metal", "metals", "precious metals", "energy",
    "indices", "index", "bond", "bonds", "crypto", "cryptocurrency",
})


def _fallback_may_hypothesise(symbol: str) -> bool:
    row = _registry_rows().get(str(symbol).strip().upper())
    if not isinstance(row, dict):
        return False
    klass = " ".join(str(row.get("asset_class") or "").lower().replace("_", " ").split())
    return klass in _HYPOTHESIS_CLASSES


def resolve(selectors: Sequence[str]) -> list[str]:
    """Selector tokens -> MT5 symbols, through the registry and the hypothesis-lane fence.

    Tokens: `class:<asset class>`, `fx:<CCY>` (any pair carrying that leg), `prefix:<XAU>`,
    `symbol:<EXACT>`. Everything is intersected with the broker's book and passed through
    `may_hypothesise`, so a symbol Fusion does not list, or one whose edge is sought in the event
    lane, is dropped here rather than published as a tradeable instrument.
    """
    rows = _registry_rows()
    policy = _may_hypothesise()
    picked: list[str] = []
    for raw in selectors:
        token = str(raw or "").strip()
        head, _, tail = token.partition(":")
        head, tail = head.lower(), tail.strip().upper()
        if head == "class":
            want = " ".join(tail.lower().replace("_", " ").split())
            picked.extend(k for k, v in rows.items() if " ".join(
                str(v.get("asset_class") or "").lower().replace("_", " ").split()) == want)
        elif head == "fx":
            picked.extend(k for k, v in rows.items()
                          if str(v.get("asset_class") or "").lower().startswith("forex")
                          and tail in k)
        elif head == "prefix":
            picked.extend(k for k in rows if k.startswith(tail))
        elif head == "symbol":
            picked.extend(k for k in rows if k == tail)
    out: list[str] = []
    for sym in sorted(dict.fromkeys(picked)):
        if policy(sym):
            out.append(sym)
    return out


# --------------------------------------------------------------------------- the seed table
@dataclass(frozen=True)
class Seed:
    """One declared actor/constraint pair, before the registry and the desk enrich it."""

    row_id: str
    actor: str
    constraint: str
    observable: str
    observable_kind: str
    direction: str
    selectors: tuple[str, ...]
    horizon: str
    session: str
    source: str
    confidence: float
    suggested_family: str
    axis_actor: str = ""
    calendar_kinds: tuple[str, ...] = ()
    actor_terms: tuple[str, ...] = ()
    desk_path: str = ""
    notes: str = ""


def _s(row_id: str, actor: str, constraint: str, observable: str, observable_kind: str,
       direction: str, selectors: tuple[str, ...], horizon: str, session: str, source: str,
       confidence: float, suggested_family: str, **kw: Any) -> Seed:
    return Seed(row_id=row_id, actor=actor, constraint=constraint, observable=observable,
                observable_kind=observable_kind, direction=direction, selectors=selectors,
                horizon=horizon, session=session, source=source, confidence=confidence,
                suggested_family=suggested_family, **kw)


#: THE SEED. Public, licensed or desk-owned references only; no crypto-exchange-native ground
#: anywhere (2026-08-18 mandate). Fusion's crypto CFDs are instruments here, never a hunted
#: universe of their own, and no row names a single-name equity: the selectors cannot express one.
SEED: tuple[Seed, ...] = (
    _s("dealer_month_end_balance_sheet",
       "bank dealers and their balance-sheet desks",
       "leverage-ratio and end-of-period reporting force dealers to shrink repo and FX-swap books"
       " over the month-end and quarter-end print, whatever the level",
       "month-end / quarter-end calendar; cross-currency basis and FX-swap implied yields",
       "calendar", "two_sided", ("class:Forex", "class:Forex Exotics"), "intraday", "london",
       "BIS Quarterly Review on window-dressing in repo and FX swaps (public)", 0.7,
       "forced_flow", axis_actor="forced_participant_on_a_dated_calendar",
       calendar_kinds=("month_end", "quarter_end"), actor_terms=("dealer", "balance sheet",
                                                                 "repo", "fx swap"),
       desk_path="data/forced_flow_calendar.json"),
    _s("wmr_fix_benchmark_customer",
       "index and pension funds benchmarked to the WMR 4pm London fix, and the banks that sold "
       "them the guaranteed rate",
       "a fund valued at the fix must transact AT the fix or carry tracking error its mandate "
       "forbids; the bank that guaranteed the rate must hedge into the same minutes",
       "WMR 4pm London fixing window (15:00-16:30 London), month-end especially",
       "calendar", "two_sided", ("class:Forex",), "intraday", "london",
       "WM/Refinitiv fix methodology; FSB FX Benchmarks report (public)", 0.75,
       "fx_fixing_reversal", axis_actor="benchmark_tracking_customer",
       calendar_kinds=("fixing", "month_end"),
       actor_terms=("fix", "fixing", "wmr", "benchmark"),
       desk_path="data/forced_flow_calendar.json"),
    _s("tokyo_ttm_gotobi_exporter",
       "Japanese corporates settling import and export invoices at the TTM rate their bank "
       "publishes each morning",
       "the TTM is struck once, at 09:55 Tokyo, and every invoice booked against it must be "
       "covered by then; the 5th/10th 'gotobi' days concentrate the flow",
       "Tokyo 09:55 TTM fixing window; gotobi day-of-month pattern",
       "calendar", "buy", ("fx:JPY",), "intraday", "asia",
       "MUFG/SMBC published TTM methodology (public)", 0.65, "fx_fixing_reversal",
       axis_actor="benchmark_tracking_customer", calendar_kinds=("fixing",),
       actor_terms=("ttm", "gotobi", "tokyo fix"),
       desk_path="data/forced_flow_calendar.json"),
    _s("index_tracker_rebalance",
       "passive funds and index trackers",
       "a tracker's mandate is to hold the index as reconstituted on the effective date; it must "
       "trade the add and the delete at that close whatever the price",
       "index review and effective-date calendar (FTSE Russell, S&P, MSCI, STOXX)",
       "calendar", "two_sided", ("class:Indices",), "intraday", "ny",
       "FTSE Russell / S&P DJI / MSCI published index review calendars (public)", 0.75,
       "forced_flow", axis_actor="forced_participant_on_a_dated_calendar",
       calendar_kinds=("index_rebalance", "quarter_end"),
       actor_terms=("index fund", "tracker", "rebalance", "reconstitution"),
       desk_path="data/forced_flow_calendar.json"),
    _s("index_inclusion_event",
       "passive funds facing an inclusion or deletion event",
       "inclusion is announced before it is effective, so the demand is known and dated and the "
       "tracker still cannot pre-trade away from its benchmark",
       "index inclusion announcements and their effective dates",
       "calendar", "two_sided", ("class:Indices",), "multi_day", "ny",
       "index provider announcement notices (public)", 0.55, "forced_flow",
       axis_actor="forced_participant_on_a_dated_calendar",
       calendar_kinds=("index_rebalance",),
       actor_terms=("inclusion", "deletion", "index addition"),
       desk_path="data/forced_flow_calendar.json"),
    _s("producer_hedging_programme",
       "commodity producers and refiners running a board-mandated hedging programme",
       "the programme hedges a fixed share of forward production on a calendar cycle; the "
       "treasurer executes the tranche when the policy says, not when the price is good",
       "CFTC Commitments of Traders producer/merchant/processor/user net position, weekly",
       "series", "sell", ("class:Energy", "class:Commodities"), "multi_day", "ny",
       "CFTC Commitments of Traders (public, weekly, point-in-time)", 0.6, "cot_positioning",
       axis_actor="forced_participant_on_a_dated_calendar",
       actor_terms=("producer", "refiner", "hedging programme", "hedger"),
       desk_path="data/intelligence/cot"),
    _s("airline_fuel_hedging",
       "airlines and freight operators hedging jet fuel and diesel",
       "fuel hedge ratios are set by policy and rolled on quarterly cycles disclosed to "
       "shareholders; the roll happens on the cycle, not on the level",
       "CFTC COT commercial net position in crude and products; quarterly reporting calendar",
       "series", "buy", ("symbol:XTIUSD", "symbol:XBRUSD"), "multi_day", "ny",
       "CFTC Commitments of Traders; IATA fuel hedging surveys (public)", 0.45,
       "cot_positioning", axis_actor="forced_participant_on_a_dated_calendar",
       actor_terms=("airline", "jet fuel", "fuel hedge"), desk_path="data/intelligence/cot"),
    _s("pension_quarter_end_rebalance",
       "pension funds and balanced mandates",
       "a policy portfolio must be rebalanced back to weights at quarter-end; a quarter in which "
       "equities outran bonds forces a mechanical sale of equities and purchase of bonds",
       "quarter-end calendar crossed with the quarter's equity-minus-bond return",
       "calendar", "two_sided", ("class:Indices", "class:Bonds"), "multi_day", "ny",
       "OECD/Willis Towers Watson pension asset surveys; published rebalancing policies", 0.6,
       "forced_flow", axis_actor="calendar_constrained_allocator",
       calendar_kinds=("quarter_end", "month_end"),
       actor_terms=("pension", "rebalanc", "policy portfolio"),
       desk_path="data/forced_flow_calendar.json"),
    _s("cta_vol_target_flow",
       "CTAs and managed-futures programmes running a volatility target",
       "position size is the inverse of realised volatility by construction, so a vol spike "
       "forces deleveraging across every trend position at once regardless of conviction",
       "realised volatility of the desk's own bars; CFTC COT managed-money net position",
       "series", "two_sided", ("class:Forex", "class:Commodities", "class:Indices",
                               "class:Energy"), "multi_day", "all",
       "CFTC Commitments of Traders managed money; SocGen CTA index methodology (public)", 0.6,
       "vol_transition", axis_actor="crowded_speculator",
       actor_terms=("cta", "managed money", "vol target", "trend follower"),
       desk_path="data/intelligence/cot"),
    _s("dealer_gamma_expiry_pin",
       "options dealers hedging an inventory of short-dated strikes",
       "a dealer short gamma must buy strength and sell weakness to stay flat; near a large "
       "strike into expiry the hedge is mechanical and its size is set by the open interest",
       "listed option expiry calendar (third Friday; 10:00 NY cut for FX)",
       "calendar", "two_sided", ("class:Indices", "prefix:XAU", "class:Forex"), "intraday", "ny",
       "CME/CBOE published expiry calendars; BIS on FX option expiries (public)", 0.6,
       "liquidity_gamma_reversal", axis_actor="option_dealer",
       calendar_kinds=("option_expiry",),
       actor_terms=("gamma", "dealer", "expiry", "strike", "pin"),
       desk_path="data/forced_flow_calendar.json"),
    _s("central_bank_reserve_rebalance",
       "central bank reserve managers",
       "a reserve portfolio has currency weights set by committee and is rebalanced to them on a "
       "quarterly review, independently of the exchange rate at the time",
       "IMF COFER quarterly reserve composition; central bank decision calendar",
       "series", "two_sided", ("class:Forex", "class:Forex Exotics"), "multi_day", "all",
       "IMF COFER (public, quarterly); central bank published calendars", 0.45, "forced_flow",
       axis_actor="calendar_constrained_allocator", calendar_kinds=("central_bank",),
       actor_terms=("reserve manager", "cofer", "reserve rebalanc"),
       desk_path="data/forced_flow_calendar.json"),
    _s("central_bank_intervention_threshold",
       "central banks with a stated or revealed intervention threshold",
       "a bank defending a level must transact at that level and not at a better one; the "
       "threshold is the constraint and the market knows roughly where it is",
       "spot distance to the revealed threshold; official intervention statements and the "
       "published daily fix where one exists",
       "series", "two_sided", ("symbol:USDJPY", "symbol:USDCNH", "symbol:EURCHF",
                               "symbol:USDTRY"), "multi_day", "asia",
       "MoF Japan intervention disclosures; PBoC daily fix; SNB statements (public)", 0.5,
       "regime_transition", axis_actor="scheduled_repricer",
       actor_terms=("intervention", "mof", "pboc", "snb", "fix deviation"),
       desk_path="data/intelligence/central_bank"),
    _s("corporate_repatriation_season",
       "corporate treasuries repatriating foreign earnings",
       "the fiscal-year and dividend calendar fixes WHEN foreign cash must come home; the "
       "treasurer converts on the schedule the board set, not on the rate",
       "Japanese fiscal year-end (March) and dividend payment calendar; month-end flow",
       "calendar", "buy", ("fx:JPY", "fx:EUR"), "multi_day", "asia",
       "MoF Japan balance-of-payments releases; published dividend calendars (public)", 0.5,
       "forced_flow", axis_actor="calendar_constrained_allocator",
       calendar_kinds=("month_end", "quarter_end"),
       actor_terms=("repatriation", "treasury", "dividend", "fiscal year"),
       desk_path="data/forced_flow_calendar.json"),
    _s("futures_roll_cycle",
       "any participant holding a futures-referenced exposure into first notice or delivery",
       "a holder who cannot take delivery MUST roll before first notice; the date is contractual "
       "and the flow is one-directional across the whole open interest",
       "exchange delivery and roll calendar; the Goldman roll window (5th-9th business day)",
       "calendar", "two_sided", ("class:Energy", "class:Commodities", "class:Soft Commodity"),
       "multi_day", "ny",
       "CME/ICE contract specifications and delivery calendars (public)", 0.7, "forced_flow",
       axis_actor="forced_participant_on_a_dated_calendar", calendar_kinds=("futures_roll",),
       actor_terms=("roll", "first notice", "delivery", "contango", "backwardation"),
       desk_path="data/forced_flow_calendar.json"),
    _s("eia_inventory_repricer",
       "refiners, physical traders and inventory-financing desks",
       "the weekly inventory print is the only scheduled moment the physical balance is revealed;"
       " storage and hedge books are marked and adjusted against it on the hour it lands",
       "EIA Weekly Petroleum Status Report (Wed 14:30 UTC) and Natural Gas Storage (Thu)",
       "calendar", "two_sided", ("class:Energy",), "intraday", "ny",
       "US EIA weekly reports (public, scheduled, point-in-time)", 0.7, "macro_conditional",
       axis_actor="scheduled_repricer", calendar_kinds=("inventory",),
       actor_terms=("inventory", "eia", "crude stocks", "storage"),
       desk_path="data/forced_flow_calendar.json"),
    _s("usda_wasde_repricer",
       "grain merchants, crushers and agricultural hedgers",
       "WASDE resets the official supply-demand balance on a published date; every hedge struck "
       "against the old balance is repriced at that minute",
       "USDA WASDE release calendar (16:00 UTC on the release day)",
       "calendar", "two_sided", ("class:Soft Commodity",), "intraday", "ny",
       "USDA WASDE publication schedule (public)", 0.65, "macro_conditional",
       axis_actor="scheduled_repricer", calendar_kinds=("usda",),
       actor_terms=("wasde", "usda", "crop report", "grain"),
       desk_path="data/forced_flow_calendar.json"),
    _s("sovereign_wealth_oil_recycling",
       "oil-exporting sovereign wealth funds",
       "a fund whose inflow is the state's oil revenue must invest what arrives, on the schedule "
       "the fiscal rule sets; a revenue collapse forces the mirror-image withdrawal",
       "oil price level crossed with published fund inflow/outflow reports",
       "series", "two_sided", ("fx:NOK", "symbol:XBRUSD"), "multi_day", "london",
       "Norges Bank Investment Management quarterly reports (public)", 0.4, "cross_asset_residual",
       axis_actor="calendar_constrained_allocator",
       actor_terms=("sovereign wealth", "nbim", "oil fund"),
       desk_path="data/intelligence/world"),
    _s("etf_creation_redemption_metal",
       "authorised participants creating and redeeming metal ETF shares",
       "a creation must be delivered in metal the same day; the AP buys the physical leg into a "
       "deadline it does not control",
       "published daily ETF holdings in tonnes (gold and silver trusts)",
       "series", "two_sided", ("prefix:XAU", "prefix:XAG"), "multi_day", "ny",
       "SPDR Gold Shares / iShares Silver Trust daily holdings files (public)", 0.55,
       "cross_asset_residual", axis_actor="inventory_laden_dealer",
       actor_terms=("etf", "creation", "redemption", "tonnes", "authorised participant"),
       desk_path="data/intelligence/world"),
    _s("retail_broker_triple_swap",
       "retail brokers and their clients carrying positions over the value-date roll",
       "spot settles T+2, so the Wednesday roll carries three days of financing; a negative-carry"
       " holder pays it mechanically and the broker debits it whatever the market does",
       "the broker's own published swap table (swap_long / swap_short per symbol)",
       "series", "two_sided", ("class:Forex Exotics", "class:Forex"), "intraday", "ny",
       "Fusion Markets swap table, mirrored in desks/mt5/data/universe/universe.json", 0.6,
       "carry", axis_actor="negative_carry_holder",
       actor_terms=("swap", "rollover", "triple swap", "carry"),
       desk_path="data/universe/universe.json"),
    _s("auction_settlement_dealer",
       "primary dealers taking down a government bond auction",
       "a dealer must bid the auction to keep the franchise and must hedge the take-down in the "
       "hours around it; the size and the date are published weeks ahead",
       "Treasury and DMO auction calendars; the bond auction window",
       "calendar", "two_sided", ("class:Bonds", "symbol:USDX"), "intraday", "ny",
       "US Treasury and UK DMO published auction calendars (public)", 0.55, "forced_flow",
       axis_actor="forced_participant_on_a_dated_calendar", calendar_kinds=("bond_auction",),
       actor_terms=("auction", "primary dealer", "take-down", "gilt"),
       desk_path="data/forced_flow_calendar.json"),
    _s("leveraged_etf_close_rebalance",
       "leveraged and inverse ETF issuers",
       "a 2x fund must end each day at 2x its stated exposure, so it must trade the SAME "
       "direction as the day's move into the close, every day, by prospectus",
       "intraday return to the close on the index the fund tracks",
       "series", "two_sided", ("class:Indices",), "intraday", "ny",
       "leveraged ETF prospectuses; SEC filings on daily rebalancing (public)", 0.5,
       "hedging_demand_close", axis_actor="close_rebalancing_issuer",
       actor_terms=("leveraged etf", "close rebalanc", "issuer"),
       desk_path="data/universe/universe.json"),
    _s("margin_forced_liquidation",
       "leveraged holders whose margin is called",
       "a liquidation engine closes an account, not a view: it sells into whatever bid exists "
       "and stops when the position is gone rather than when the price is right",
       "the desk's own realised-volatility jumps and spread widening on its tape",
       "series", "two_sided", ("class:Crypto", "class:Indices"), "intraday", "all",
       "desk tape (desks/mt5/data/tape); broker margin terms (public)", 0.5,
       "volatility_shock", axis_actor="margin_called_trader",
       actor_terms=("liquidation", "margin call", "forced sell", "cascade"),
       desk_path="data/tape"),
    _s("fx_option_ny_cut_expiry",
       "FX option dealers running expiries at the 10:00 New York cut",
       "an expiry is settled against the spot rate at a named minute; a dealer hedging a large "
       "strike must defend or abandon it by that minute and not later",
       "listed and OTC FX expiry calendar at the 10:00 NY cut",
       "calendar", "two_sided", ("class:Forex",), "intraday", "ny",
       "CME FX option expiry calendar; BIS Triennial Survey on the NY cut (public)", 0.5,
       "liquidity_gamma_reversal", axis_actor="option_dealer",
       calendar_kinds=("option_expiry",),
       actor_terms=("ny cut", "expiry", "strike", "option"),
       desk_path="data/forced_flow_calendar.json"),
    _s("holiday_inventory_carry",
       "market makers carrying inventory into a thin holiday session",
       "a desk that must quote through a holiday holds inventory it cannot lay off, so it widens "
       "and skews rather than warehousing risk it is not paid for",
       "exchange holiday calendar; the desk's own measured spread state",
       "calendar", "volatility", ("class:Forex", "class:Indices"), "intraday", "all",
       "exchange published holiday calendars (public)", 0.45, "spread_state",
       axis_actor="liquidity_provider", calendar_kinds=("holiday_liquidity",),
       actor_terms=("holiday", "thin liquidity", "inventory"),
       desk_path="data/forced_flow_calendar.json"),
    _s("gold_london_fix_auction",
       "bullion banks and refiners clearing physical gold at the LBMA price auction",
       "the auction clears the day's physical book at 10:30 and 15:00 London; a participant with "
       "metal to deliver must be in the auction, not around it",
       "LBMA Gold Price auction windows (10:30 / 15:00 London)",
       "calendar", "two_sided", ("prefix:XAU", "prefix:XAG"), "intraday", "london",
       "LBMA published auction methodology and times (public)", 0.6, "fx_fixing_reversal",
       axis_actor="benchmark_tracking_customer", calendar_kinds=("fixing",),
       actor_terms=("lbma", "gold fix", "auction", "bullion"),
       desk_path="data/forced_flow_calendar.json"),
)


def validate(seed: Sequence[Seed] = SEED) -> list[str]:
    """Everything wrong with the seed table, in plain words. Empty means nothing is."""
    problems: list[str] = []
    seen: set[str] = set()
    for row in seed:
        if row.row_id in seen:
            problems.append(f"{row.row_id}: duplicate row_id")
        seen.add(row.row_id)
        for fname, value in (("actor", row.actor), ("constraint", row.constraint),
                             ("observable", row.observable), ("source", row.source),
                             ("suggested_family", row.suggested_family)):
            if not str(value or "").strip():
                problems.append(f"{row.row_id}: {fname} is empty")
        if row.direction not in DIRECTIONS:
            problems.append(f"{row.row_id}: direction {row.direction!r} is not one of {DIRECTIONS}")
        if not row.selectors:
            problems.append(f"{row.row_id}: no instrument selectors")
        if not 0.0 <= float(row.confidence) <= 1.0:
            problems.append(f"{row.row_id}: confidence {row.confidence} is outside [0, 1]")
        if not row.horizon.strip() or not row.session.strip():
            problems.append(f"{row.row_id}: market impact needs a horizon and a session")
    return problems


def seed_row(seed: Seed) -> dict[str, Any]:
    """One seed, resolved against the registry into the published atlas shape."""
    instruments = resolve(seed.selectors)
    return {
        "row_id": seed.row_id,
        "actor": seed.actor,
        "constraint": seed.constraint,
        "observable": seed.observable,
        "observable_kind": seed.observable_kind,
        "market_impact": {"direction": seed.direction, "instruments": instruments,
                          "horizon": seed.horizon, "session": seed.session},
        "mt5_instruments": instruments,
        "source": seed.source,
        "confidence": float(seed.confidence),
        "suggested_family": seed.suggested_family,
        "axis_actor": seed.axis_actor,
        "calendar_kinds": list(seed.calendar_kinds),
        "desk_path": seed.desk_path,
        "notes": seed.notes,
    }


# --------------------------------------------------------------------------- enrichment
def _read_json(path: Path, note: dict[str, str]) -> Any:
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except FileNotFoundError:
        note[str(path)] = "absent"
    except (OSError, ValueError) as exc:
        note[str(path)] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return None


def calendar_enrichment(note: dict[str, str]) -> dict[str, Any]:
    """The dated windows, by calendar kind and by the forced actor the calendar itself names."""
    doc = _read_json(CALENDAR, note)
    events = doc.get("events") if isinstance(doc, dict) else None
    rows = [e for e in (events or []) if isinstance(e, dict)]
    by_kind: dict[str, int] = {}
    next_window: dict[str, str] = {}
    actors: dict[str, int] = {}
    now = datetime.now(tz=UTC).isoformat()
    for e in rows:
        kind = str(e.get("kind") or UNMEASURED)
        by_kind[kind] = by_kind.get(kind, 0) + 1
        start = str(e.get("window_start_utc") or "")
        if start > now and (kind not in next_window or start < next_window[kind]):
            next_window[kind] = start
        actor = str(e.get("forced_actor") or "").strip()
        if actor:
            actors[actor] = actors.get(actor, 0) + 1
    return {"n_events": len(rows), "by_kind": by_kind, "next_window": next_window,
            "calendar_actors": actors}


def tested_actors(note: dict[str, str]) -> dict[str, dict[str, int]]:
    """Which economic actors the desk has TESTED, and how those cells fared.

    Read off `axis_registry`'s own cells, whose `economic_actor` tag comes from
    `MECHANISM_ACTOR`. LIVE/FORWARD/CERTIFIED count as survived, MEASURED_FAIL as failed, and
    UNMEASURED as neither -- a cell nobody judged is not a failure, it is a cell nobody judged.
    """
    out: dict[str, dict[str, int]] = {}
    path = Path(AXIS_CELLS)
    if not path.exists():
        note[str(path)] = "absent"
        return out
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= MAX_AXIS_LINES:
                    note[str(path)] = f"truncated at {MAX_AXIS_LINES} lines"
                    break
                raw = line.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                actor = str(row.get("economic_actor") or UNMEASURED)
                state = str(row.get("state") or "UNMEASURED").upper()
                bucket = out.setdefault(actor, {"cells": 0, "survived": 0, "failed": 0,
                                                "unmeasured": 0})
                bucket["cells"] += 1
                if state in ("LIVE", "FORWARD", "CERTIFIED"):
                    bucket["survived"] += 1
                elif state == "MEASURED_FAIL":
                    bucket["failed"] += 1
                else:
                    bucket["unmeasured"] += 1
    except OSError as exc:
        note[str(path)] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return out


def claims_naming_actor(conn: Any, seed: Sequence[Seed] = SEED) -> dict[str, list[str]]:
    """Registry claims that name an atlas actor, by row_id.

    TWO READS, and the declared one wins. A claim whose row carried a `structured.actor` (the
    lead schema's own fourteen-field block) is matched on that; otherwise the claim's own words
    are matched against the row's declared `actor_terms`. Both are recorded, because a seat that
    bothered to fill in the actor field has told the desk something a substring search cannot.
    """
    out: dict[str, list[str]] = {}
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT claim_id, source_id, text, instruments_json, provenance_json FROM claims "
            "ORDER BY created_at DESC LIMIT ?", (MAX_CLAIMS,))]
    except Exception:  # a registry without the table is a measurement
        return out
    for r in rows:
        text = str(r.get("text") or "")
        instruments: list[str] = []
        with suppress(ValueError, TypeError):
            instruments = list(json.loads(r.get("instruments_json") or "[]"))
        # The claim's PROVENANCE is folded into the intake row before the lead schema reads it,
        # so a seat that bothered to stamp `actor` on what it donated is heard. Without this the
        # declared branch could never fire and the atlas would be a substring search wearing a
        # schema's name.
        provenance: dict[str, Any] = {}
        with suppress(ValueError, TypeError):
            loaded = json.loads(r.get("provenance_json") or "{}")
            provenance = loaded if isinstance(loaded, dict) else {}
        lead = ls.from_intelligence_row({**provenance, "claim": text,
                                         "source": str(r.get("source_id") or ""),
                                         "symbols": instruments})
        declared = str(((lead.structured or {}).get("actor") if lead else "") or "").lower()
        low = text.lower()
        for s in seed:
            hit = any(term in low for term in s.actor_terms)
            if declared and (declared in s.actor.lower() or any(t in declared
                                                                for t in s.actor_terms)):
                hit = True
            if hit:
                out.setdefault(s.row_id, []).append(str(r.get("claim_id") or ""))
    return out


def observable_is_measurable(row: Mapping[str, Any], calendar: Mapping[str, Any]) -> bool:
    """Can THIS BOX see the observable? A calendar row needs its kind present in the built
    calendar; a series row needs the artifact its `desk_path` names to exist. Anything else is
    UNMEASURED, which keeps the row in the atlas and out of the discovery queue."""
    kinds = [str(k) for k in (row.get("calendar_kinds") or [])]
    if kinds:
        by_kind = calendar.get("by_kind") or {}
        if any(int(by_kind.get(k, 0)) > 0 for k in kinds):
            return True
    path = str(row.get("desk_path") or "")
    return bool(path) and (_DESK / path).exists()


# --------------------------------------------------------------------------- build and publish
def build(conn: Any = None, seed: Sequence[Seed] = SEED) -> dict[str, Any]:
    """The atlas database payload, without touching disk."""
    note: dict[str, str] = {}
    problems = validate(seed)
    calendar = calendar_enrichment(note)
    tested = tested_actors(note)
    claims = claims_naming_actor(conn, seed) if conn is not None else {}
    rows: list[dict[str, Any]] = []
    for s in seed:
        row = seed_row(s)
        kinds = row["calendar_kinds"]
        row["calendar_events"] = sum(int((calendar["by_kind"]).get(k, 0)) for k in kinds)
        row["next_window"] = next((calendar["next_window"][k] for k in kinds
                                   if k in calendar["next_window"]), UNMEASURED)
        row["observable_measurable"] = observable_is_measurable(row, calendar)
        row["tested"] = tested.get(s.axis_actor, {"cells": 0, "survived": 0, "failed": 0,
                                                  "unmeasured": 0}) if s.axis_actor else {}
        row["claims"] = claims.get(s.row_id, [])[:50]
        row["n_claims"] = len(claims.get(s.row_id, []))
        row["discoverable"] = bool(row["observable_measurable"] and row["mt5_instruments"])
        rows.append(row)
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_rows": len(rows),
        "n_actors": len({r["actor"] for r in rows}),
        "rows": rows,
        "calendar": {k: v for k, v in calendar.items() if k != "calendar_actors"},
        "calendar_actors_unmapped": sorted(
            a for a in (calendar.get("calendar_actors") or {})
            if not any(_overlaps(a, r["actor"]) for r in rows)),
        "tested_actors": tested,
        "problems": problems,
        "unmeasured": note,
        "rule": RULE,
    }


def _overlaps(a: str, b: str) -> bool:
    """Two actor descriptions naming the same participant, by shared significant words."""
    ta = {w for w in str(a).lower().split() if len(w) > 4}
    tb = {w for w in str(b).lower().split() if len(w) > 4}
    return bool(ta & tb)


def record_discoveries(doc: Mapping[str, Any], conn: Any) -> tuple[int, int]:
    """One UNPROCESSED discovery per discoverable row. Returns (recorded, already_present).

    Deduped by the REGISTRY's own content hash, so this is idempotent across passes: the exact
    rule carries the row_id and the observable, which is what makes two rows sharing a mechanism
    two discoveries rather than one.
    """
    created = present = 0
    for row in doc.get("rows") or []:
        if not row.get("discoverable"):
            continue
        impact = row.get("market_impact") or {}
        _, made = reg.record_discovery(
            source_id=SOURCE_ID, source_type="actor_atlas", origin="MOAT",
            generator="actor_atlas", mechanism=str(row.get("suggested_family") or "forced_flow"),
            actor=str(row.get("actor") or ""),
            constraint=str(row.get("constraint") or ""),
            information=str(row.get("observable_kind") or ""),
            economic_rationale=str(row.get("observable") or ""),
            assets=list(row.get("mt5_instruments") or []),
            horizons=[str(impact.get("horizon") or UNMEASURED)],
            sessions=[str(impact.get("session") or UNMEASURED)],
            exact_rule=f"{row.get('row_id')}::{row.get('observable')}",
            required_data=[str(row.get("desk_path") or UNMEASURED)],
            confidence=float(row.get("confidence") or 0.0),
            falsifier=("the observable does not separate the constrained window from matched "
                       "control windows after costs"),
            payload={"actor": row.get("actor"), "constraint": row.get("constraint"),
                     "observable": row.get("observable"),
                     "instruments": row.get("mt5_instruments"),
                     "horizon": impact.get("horizon"), "session": impact.get("session"),
                     "suggested_family": row.get("suggested_family"),
                     "direction": impact.get("direction"), "source": row.get("source")},
            conn=conn)
        created += int(made)
        present += int(not made)
    return created, present


def report_of(doc: Mapping[str, Any], discoveries_recorded: int) -> dict[str, Any]:
    rows = list(doc.get("rows") or [])
    tested = dict(doc.get("tested_actors") or {})
    named = {str(r.get("axis_actor") or "") for r in rows} - {""}
    return {
        "at": doc.get("generated_at"),
        "n_actors": doc.get("n_actors"),
        "n_rows": doc.get("n_rows"),
        "tested_actors": {a: tested[a] for a in sorted(named & set(tested))},
        "untested_actors": sorted(a for a in named if int(
            (tested.get(a) or {}).get("cells", 0)) == 0),
        "observables_missing": sorted(str(r.get("row_id")) for r in rows
                                      if not r.get("observable_measurable")),
        "instruments_missing": sorted(str(r.get("row_id")) for r in rows
                                      if not r.get("mt5_instruments")),
        "discoveries_recorded": int(discoveries_recorded),
        "calendar_actors_unmapped": list(doc.get("calendar_actors_unmapped") or [])[:40],
        "claims_matched": sum(int(r.get("n_claims") or 0) for r in rows),
        "problems": list(doc.get("problems") or []),
        "unmeasured": dict(doc.get("unmeasured") or {}),
        "rule": RULE,
    }


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=1, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError, PermissionError):
            os.unlink(name)


def run(*, dry_run: bool = False, conn: Any = None,
        seed: Sequence[Seed] = SEED) -> dict[str, Any]:
    """One pass: build the atlas, record what is discoverable, publish both artifacts."""
    close_after = conn is None
    c = conn if conn is not None else reg.connect()
    try:
        doc = build(c, seed)
        recorded = 0
        if not dry_run:
            recorded, _present = record_discoveries(doc, c)
        report = report_of(doc, recorded)
        report["dry_run"] = bool(dry_run)
        if not dry_run:
            _atomic_json(DATABASE, doc)
            _atomic_json(REPORT, report)
        return report
    finally:
        if close_after:
            c.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="build and print; write no artifact and record no discovery")
    a = ap.parse_args(argv)
    report = run(dry_run=a.dry_run)
    print(json.dumps(report, indent=1, default=str))
    if a.dry_run:
        print("  (dry run: nothing written, no discovery recorded)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
