"""THE MICROSTRUCTURE AND OPTIONS-FLOW FACTORY -- one leg: collect point-in-time, build cells,
hand them to the one judge, and say per family exactly why the rest are not built.

THE PRINCIPAL, 2026-10-11: "the constraint is ... data access, history, timestamp accuracy, feed
resolution, compute and judging throughput". So this is not a taxonomy. Every family in the
grammar below carries a MEASURED data status, its history depth, the publication lag that makes
it point-in-time, the MT5 instruments it maps to, how many cells it generated this pass, and
whether those cells reach the existing judge. A family the desk cannot feed says which source,
which terms clause or which venue fact blocks it.

WHAT IS BUILT AND JUDGED NOW -- first-party data, which is always allowed:

  THE TICK TAPE. `recorders/tick_recorder.py` / `mt5desk/tape.py` record Fusion's quote stream
  under data/tape/ticks/<SYM>/. Each pass folds every completed five-minute bucket into
  data/lake/series/tf_<SYMBOL>.parquet: the tick rule on the mid (signed quote flow), unit-depth
  order-flow imbalance sign(dBid)+sign(dAsk) (Cont-Kukanov-Stoikov with no sizes, because Fusion
  publishes none -- `data/tape/depth_probe.json`), the plain mid-sign count the older family uses,
  mean and peak relative spread, and quote rate. Buckets are written once, complete, and never
  rewritten: the series is a vintage. `mt5desk/family_tick_flow.py` reads it by `source` and
  `feature`, so the sealed gauntlet rebuilds the cells through its ordinary `fn(h1, **params)`.

  OWN EXECUTION. data/fill_corpus.jsonl (fill_recorder) -- slippage and reject states per
  symbol and session, measured and published. No family conditions on them yet and the corpus is
  tens of rows, so its cell count is 0 with that reason, never a silent zero.

WHAT IS COUNTED, NOT RE-MINTED: COT positioning (CFTC, public domain, collected by
mt5desk/fetch_cot.py and judged through the existing cot families and run_cot_macro_sweep),
bar-spread states (microstructure_miner -> spread_state), options-implied state (PR #234's
options_implied, itself HELD on FRED/CBOE terms). No second lane: each names its owner organ.

TERMS FAIL CLOSED, PER SOURCE (principal ruling, 2026-10-13 16:10Z). No source is banned as a
category; every source is judged on its own terms. Allowed: official APIs and free tiers within
their published limits (NEEDS_KEY when the desk holds no key), public pages the desk is permitted
to fetch, and public posts read for ideas. Off: METHOD only -- bypassing logins, paywalls,
CAPTCHAs, rate limits or region locks, stolen data, and MNPI. Idea provenance never blocks a cell.
Each source carries an `access` state from ACCESS_STATES (API_PERMITTED / NEEDS_KEY / PUBLIC_PAGE
/ IDEAS_ONLY / METHOD_BLOCKED / UNREAD) and a `verdict`: PERMITTED or FIRST_PARTY when this desk
may ingest it now, else HELD with the reason by name. `SOURCES` carries the verbatim clause read
from each source's OWN page on the date given; UNREAD is never a permission. This organ fetches
nothing at all; collection runs in the owner organs.

THE UNKNOWN-UNKNOWN MICROSTRUCTURE MINER runs in the same pass. It classifies anything the
grammar does not yet name -- a tape symbol the registry does not list, a tick field or tick flag
never seen, an asset class, an order type or broker retcode outside the known sets, a dated-
contract expiry convention in a symbol name -- appends it to the grammar's open axes and writes
the candidate cells it implies. A new tape symbol enters cell generation on the same pass.

TRIALS. This organ charges none: its donations carry `tests_run: 0`. Counting cells is a
measurement. The judge charges what it judges, as it always has.

    python desks/mt5/research/flow_factory.py --once [--dry-run] [--out PATH] [--budget-s N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_tick_flow as tfam  # noqa: E402

SEAT = "flow_factory"
DATA = DESK / "data"
TAPE = DATA / "tape" / "ticks"
SERIES_DIR = tfam.SERIES_DIR
STATE_DIR = DATA / "lake" / "flow_factory"
DONATED = STATE_DIR / "donated.json"
GRAMMAR_STATE = STATE_DIR / "grammar_discovered.json"
REPORT = DESK / "reports" / "FLOW_FACTORY.json"
FILL_CORPUS = DATA / "fill_corpus.jsonl"
ORDER_INTENTS = DATA / "order_intents.jsonl"
COT_DIR = DATA / "cot"
UNIVERSE_JSON = DATA / "universe" / "universe.json"
DEPTH_PROBE = DATA / "tape" / "depth_probe.json"

BUCKET_MS = tfam.BUCKET_MIN * 60_000
#: Completed buckets a symbol needs before cells are minted on it (about ten trading days).
MIN_BUCKETS = 2_000
#: Fills per state before an own-execution state is a measurement rather than an anecdote.
MIN_FILLS_PER_STATE = 30

# ----------------------------------------------------------------------------- the grammar
#: THE CELL GRAMMAR. Every axis is OPEN: the values here are what the desk can name today, and
#: the unknown-unknown miner appends what it finds (persisted in GRAMMAR_STATE). A cell is one
#: value per axis it uses; an axis a family does not use is "*".
GRAMMAR: dict[str, list[str]] = {
    "venue": ["fusion_mt5", "cftc", "finra", "sec", "occ", "cboe", "cme", "nyse_nasdaq_auction",
              "lbma_fix"],
    "feed_type": ["L1_quotes", "L2_depth", "L3_orders", "trade_prints", "off_exchange_trf",
                  "own_fills", "own_rejects", "positioning_report", "options_tape",
                  "vol_surface", "oi_volume_bulletin", "auction_imbalance", "fixing"],
    "instrument": [],                    # filled from the tape and the registry each pass
    "event": ["none", "macro_release", "earnings", "expiry", "roll", "auction", "fixing",
              "session_open", "session_close", "cot_release"],
    "aggressor": ["tick_rule_mid", "quote_ofi_unit_depth", "mid_sign", "true_side_flag"],
    "size": ["unit", "block", "sweep"],
    "liquidity_state": ["spread_wide", "spread_calm", "quote_burst", "quote_drought",
                        "refill", "resilience"],
    "strike_moneyness_tenor": ["atm", "otm_put", "otm_call", "0dte", "weekly", "monthly",
                               "leaps"],
    "structure": ["single", "vertical", "straddle", "risk_reversal", "calendar"],
    "iv_state": ["iv_high", "iv_low", "iv_spike", "iv_crush", "term_inverted", "skew_steep"],
    "greeks": ["gamma", "vanna", "charm", "vega"],
    "oi_state": ["oi_build", "oi_unwind", "oi_flat"],
    "dealer_state": ["long_gamma", "short_gamma", "gamma_flip", "pin_pressure"],
    "positioning": ["spec_net_extreme", "comm_net_extreme", "oi_change", "borrow_tight"],
    "cross_asset": ["SPX_ES->US500", "NDX_NQ->NAS100", "DJI_YM->US30", "GC_GLD->XAUUSD",
                    "SI_SLV->XAGUSD", "CL_USO->XTIUSD", "BZ->XBRUSD", "CME_FX->MT5_FX",
                    "crypto_ref_options->BTCUSD_SOLUSD"],
    "regime": ["*"],
    "mt5_target": [],                    # filled from the registry each pass
    "horizon": ["M5", "M15", "M30", "H1", "H4"],
}
DERIVATIONS: tuple[str, ...] = (
    "level", "change", "acceleration", "imbalance", "surprise", "residual", "divergence",
    "sequence", "hazard", "change_point", "cross_impact", "elasticity", "liquidity_recovery",
    "dealer_hedge_pressure", "surface_dislocation", "expiry_state", "auction_state")

# ----------------------------------------------------------------------------- the sources
PERMITTED = "PERMITTED"
HELD = "HELD"
FIRST_PARTY = "FIRST_PARTY"
#: The per-source access vocabulary (principal ruling 2026-10-13 16:10Z). Only API_PERMITTED and
#: PUBLIC_PAGE (and first-party data) may be ingested; IDEAS_ONLY may be read, never ingested.
ACCESS_STATES: tuple[str, ...] = ("API_PERMITTED", "NEEDS_KEY", "PUBLIC_PAGE", "IDEAS_ONLY",
                                  "METHOD_BLOCKED", "UNREAD")
INGESTIBLE = frozenset({"API_PERMITTED", "PUBLIC_PAGE"})
#: Terms, verbatim from each source's OWN page as read with WebFetch on `checked_at`. A source
#: whose page could not be read, or carries no clause permitting automated internal research use,
#: is HELD and never fetched. Fail closed: nothing here is inferred.
SOURCES: dict[str, dict[str, Any]] = {
    "mt5_tick_tape": {
        "publisher": "Fusion Markets via this desk's own MT5 terminal", "verdict": FIRST_PARTY,
        "access": "API_PERMITTED",
        "terms_url": "", "terms_quote": "first-party: the desk's own recorded quote stream",
        "checked_at": "2026-10-13", "collector": "recorders/tick_recorder.py, mt5desk/tape.py",
        "pit": "bucket [start, start+5m) on the broker clock (MT5 time_msc, the bars' clock); "
               "available at bucket end; written only once complete; never rewritten",
        "publication_lag": "0 (bucket end)"},
    "own_fills": {
        "publisher": "this desk's gateway and fill_recorder", "verdict": FIRST_PARTY,
        "access": "API_PERMITTED",
        "terms_url": "", "terms_quote": "first-party: the desk's own orders and deals",
        "checked_at": "2026-10-13", "collector": "research/fill_recorder.py",
        "pit": "a row is knowable at its own decided_at / filled_at; appended hourly",
        "publication_lag": "<= 1h (fill_recorder cadence)"},
    "cftc_cot": {
        "publisher": "U.S. Commodity Futures Trading Commission", "verdict": PERMITTED,
        "access": "PUBLIC_PAGE",
        "terms_url": "https://www.cftc.gov/webpolicy/index.htm",
        "terms_quote": ("Government information at the CFTC website is in the public domain. "
                        "Public domain information may be freely distributed and copied, but it "
                        "is requested that in any subsequent use the CFTC be given appropriate "
                        "acknowledgement."),
        "checked_at": "2026-10-13", "collector": "mt5desk/fetch_cot.py",
        "pit": "positions as of Tuesday, released Friday 15:30 ET; usable from Friday 21:00 UTC",
        "publication_lag": "3 days 21 hours after the as-of Tuesday"},
    "finra_short_sale_otc": {
        "publisher": "FINRA", "verdict": HELD,
        "terms_url": "https://www.finra.org/terms-of-use",
        "terms_quote": ("the content and material provided through the FINRA Website shall be "
                        "used ONLY for your own non-commercial personal or professional use. "
                        "[...] use any data mining, scraping or harvesting tools (including "
                        "robots) [...] develop or create a database of data using the FINRA "
                        "Website"),
        "checked_at": "2026-10-13", "collector": None,
        "pit": "daily short-sale volume files, same-day evening ET (not collected)",
        "publication_lag": "~0-1 day (not collected)",
        "access": "NEEDS_KEY",
        "api_url": "https://developer.finra.org/docs",
        "api_quote": ("An API Credential is required to make API requests on the FINRA API "
                      "platform. [...] Synchronous requests: 1200 requests per minute per IP "
                      "address."),
        "why_held": ("the website terms prohibit robots and building a database from the site, "
                     "so the site is not a route; the official FINRA API is, and it needs an "
                     "OAuth API credential the desk does not hold (NEEDS_KEY)")},
    "sec_fails_to_deliver": {
        "publisher": "U.S. Securities and Exchange Commission", "verdict": PERMITTED,
        "access": "PUBLIC_PAGE",
        "terms_url": "https://www.sec.gov/about/webmaster-frequently-asked-questions",
        "terms_quote": ("We allow scripted access to sec.gov content [...] Please declare your "
                        "user agent in request headers [...] Note that our current maximum "
                        "access rate is 10 requests per second."),
        "conditions": "declared User-Agent naming the desk and a contact; at most 10 requests/s",
        "checked_at": "2026-10-13", "collector": None,
        "pit": "twice-monthly files, roughly two weeks after the settlement dates they cover",
        "publication_lag": "~14 days (not collected)"},
    "occ_daily_stats": {
        "publisher": "The Options Clearing Corporation", "verdict": HELD,
        "terms_url": "https://www.theocc.com/terms-of-use",
        "terms_quote": "(not readable: the terms page returned a fetch error on 2026-10-13)",
        "checked_at": "2026-10-13", "collector": None,
        "pit": "daily volume/OI statistics, D+1 (not collected)",
        "publication_lag": "1 day (not collected)",
        "access": "UNREAD",
        "why_held": "no terms clause could be read, so none permits the use"},
    "cboe_market_stats": {
        "publisher": "Cboe Global Markets", "verdict": HELD,
        "terms_url": "https://www.cboe.com/use-of-content",
        "terms_quote": ("In order to use any Cboe Content, you must receive approval in advance "
                        "from Cboe. [...] You are not approved to use Cboe Content until a "
                        "license agreement has been signed by both you and Cboe."),
        "checked_at": "2026-10-13", "collector": None,
        "pit": "daily options statistics, D+1 (not collected)",
        "publication_lag": "1 day (not collected)",
        "access": "IDEAS_ONLY",
        "why_held": ("use requires a signed licence the desk does not hold; the public pages "
                     "may be read for ideas, never ingested")},
    "cme_volume_oi_bulletin": {
        "publisher": "CME Group", "verdict": HELD,
        "terms_url": "https://www.cmegroup.com/terms-of-use.html",
        "terms_quote": "(not readable: the terms page returned a fetch error on 2026-10-13)",
        "checked_at": "2026-10-13", "collector": None,
        "pit": "daily volume and open interest bulletin, D+1 morning CT (not collected)",
        "publication_lag": "1 day (not collected)",
        "access": "UNREAD",
        "why_held": "no terms clause could be read, so none permits the use"},
    "crypto_reference_options": {
        "publisher": "crypto-exchange option venues", "verdict": HELD,
        "access": "UNREAD",
        "terms_url": "",
        "terms_quote": ("(not read: no venue's own market-data API terms are on file; an "
                        "official public market-data API is allowable in principle under the "
                        "2026-10-13 ruling)"),
        "checked_at": "2026-10-13", "collector": None, "pit": "n/a", "publication_lag": "n/a",
        "why_held": ("mt5_purity fence; principal ruling pending on the fence "
                     "(scripts/check_mt5_purity.py fails CI on crypto-exchange hostnames). Not a "
                     "category ban: Fusion's BTCUSD/SOLUSD CFDs are traded, and the reference "
                     "options would inform them only")},
    "auction_imbalance_feeds": {
        "publisher": "listing-exchange auction imbalance feeds", "verdict": HELD,
        "terms_url": "", "terms_quote": "(no terms page read: vendor feeds, no public route)",
        "checked_at": "2026-10-13", "collector": None,
        "pit": "intraday imbalance messages (not collected)", "publication_lag": "n/a",
        "access": "UNREAD",
        "why_held": "no public source with a permitting clause"},
    "benchmark_fixings": {
        "publisher": "benchmark administrators (gold/silver fix, WM/R)", "verdict": HELD,
        "terms_url": "", "terms_quote": "(no terms page read: licensed benchmarks)",
        "checked_at": "2026-10-13", "collector": None, "pit": "n/a", "publication_lag": "n/a",
        "access": "UNREAD",
        "why_held": "licensed benchmark data; no permitting clause on file"},
    "external_futures_tape": {
        "publisher": "CME/COMEX/NYMEX futures prints", "verdict": HELD,
        "terms_url": "https://www.cmegroup.com/terms-of-use.html",
        "terms_quote": "(not readable: the terms page returned a fetch error on 2026-10-13)",
        "checked_at": "2026-10-13", "collector": None, "pit": "n/a", "publication_lag": "n/a",
        "why_held": ("no CME clause could be read; the existing futures_lead_lag leg reads a "
                     "Yahoo route whose own terms are not on file here (per source, not a "
                     "category ban), so it is not counted as collection here")},
}

# ----------------------------------------------------------------------------- the families
#: One row per family. `sources` decide the status; `judge_families` are the registered
#: families its cells compile to; `owner` names the organ that mints them when it is not this one.
FAMILIES: tuple[dict[str, Any], ...] = (
    {"key": "orderflow_ticks", "title": "Order flow from ticks (tick rule, unit-depth OFI)",
     "sources": ["mt5_tick_tape"], "judge_families": ["tick_flow"], "owner": SEAT,
     "axes": ["venue", "feed_type", "instrument", "aggressor", "horizon"],
     "derivations": ["level", "imbalance", "surprise"], "mt5_mapping": "the symbol itself"},
    {"key": "liquidity_state_ticks", "title": "Spread and quote-rate liquidity states",
     "sources": ["mt5_tick_tape"], "judge_families": ["tick_flow"], "owner": SEAT,
     "axes": ["venue", "feed_type", "instrument", "liquidity_state", "horizon"],
     "derivations": ["level", "surprise", "liquidity_recovery"],
     "mt5_mapping": "the symbol itself"},
    {"key": "orderflow_minus_price_response", "priority_residual": True,
     "title": "OrderFlow - PriceResponse", "sources": ["mt5_tick_tape"],
     "judge_families": ["flow_residual"], "owner": SEAT,
     "axes": ["venue", "instrument", "aggressor", "horizon"],
     "derivations": ["residual", "elasticity", "divergence"], "mt5_mapping": "the symbol itself"},
    {"key": "own_execution_state", "title": "Own fills, rejects and slippage states",
     "sources": ["own_fills"], "judge_families": [], "owner": SEAT,
     "axes": ["venue", "feed_type", "instrument", "liquidity_state", "event"],
     "derivations": ["level", "surprise", "hazard"], "mt5_mapping": "the symbol traded"},
    {"key": "cot_positioning", "title": "COT positioning (net, change, commercials)",
     "sources": ["cftc_cot"], "owner": "research/run_cot_macro_sweep.py + cot families",
     "judge_families": ["cot_positioning", "cot_net_fade"],
     "axes": ["venue", "positioning", "instrument", "horizon"],
     "derivations": ["level", "change", "surprise"],
     "mt5_mapping": "fetch_cot contract -> AUDUSD/USDCAD/USDCHF/GBPUSD/USDJPY/NZDUSD/"
                    "XAUUSD/XAGUSD/US500/NAS100"},
    {"key": "oi_change_minus_volume", "priority_residual": True, "title": "OIChange - Volume",
     "sources": ["cftc_cot", "cme_volume_oi_bulletin"], "judge_families": [], "owner": SEAT,
     "axes": ["venue", "oi_state", "instrument"], "derivations": ["residual", "change"],
     "mt5_mapping": "futures contract -> its MT5 CFD"},
    {"key": "options_tape", "title": "Options tape: strikes, expiries, 0DTE, LEAPS, structures",
     "sources": ["occ_daily_stats", "cboe_market_stats"], "judge_families": [], "owner": SEAT,
     "axes": ["venue", "strike_moneyness_tenor", "structure", "oi_state"],
     "derivations": ["level", "change", "expiry_state"],
     "mt5_mapping": "SPX/NDX/DJI -> US500/NAS100/US30; GLD -> XAUUSD; USO -> XTIUSD"},
    {"key": "vol_surface", "title": "IV level, skew, term, VRP, vol-of-vol",
     "sources": ["cboe_market_stats"], "owner": "research/options_implied.py (PR #234, HELD)",
     "judge_families": ["implied_vol_state", "implied_vol_conditioned"],
     "axes": ["iv_state", "strike_moneyness_tenor", "mt5_target"],
     "derivations": ["level", "change", "surface_dislocation"],
     "mt5_mapping": "VIX->US500, VXN->NAS100, VXD->US30, GVZ->XAUUSD, OVX->XTIUSD"},
    {"key": "iv_change_minus_realized_vol_change", "priority_residual": True,
     "title": "IVSurfaceChange - RealizedVolChange", "sources": ["cboe_market_stats"],
     "judge_families": [], "owner": SEAT, "axes": ["iv_state", "mt5_target", "horizon"],
     "derivations": ["residual", "divergence"], "mt5_mapping": "as vol_surface"},
    {"key": "options_flow_minus_underlying_response", "priority_residual": True,
     "title": "OptionsFlow - UnderlyingResponse",
     "sources": ["occ_daily_stats", "cboe_market_stats"], "judge_families": [], "owner": SEAT,
     "axes": ["structure", "strike_moneyness_tenor", "mt5_target"],
     "derivations": ["residual", "cross_impact"], "mt5_mapping": "as options_tape"},
    {"key": "dealer_hedge_pressure_minus_realized_move", "priority_residual": True,
     "title": "DealerHedgePressure - RealizedMove (GEX, vanna, charm, flip, pin)",
     "sources": ["occ_daily_stats", "cboe_market_stats"], "judge_families": [], "owner": SEAT,
     "axes": ["greeks", "dealer_state", "mt5_target"],
     "derivations": ["dealer_hedge_pressure", "residual", "expiry_state"],
     "mt5_mapping": "index and ETF option chains -> US500/NAS100/US30/XAUUSD"},
    {"key": "gamma_state_x_ofi", "priority_residual": True, "title": "GammaState x OFI",
     "sources": ["occ_daily_stats", "cboe_market_stats", "mt5_tick_tape"],
     "judge_families": [], "owner": SEAT, "axes": ["dealer_state", "aggressor", "mt5_target"],
     "derivations": ["dealer_hedge_pressure", "imbalance"],
     "mt5_mapping": "US500/NAS100/US30 tape conditioned on the index's gamma state"},
    {"key": "auction_imbalance_x_overnight", "priority_residual": True,
     "title": "AuctionImbalance x Overnight (MOC, opening/closing auctions)",
     "sources": ["auction_imbalance_feeds"], "judge_families": [], "owner": SEAT,
     "axes": ["event", "venue", "mt5_target"], "derivations": ["auction_state", "surprise"],
     "mt5_mapping": "NYSE/Nasdaq closing auctions -> US500/NAS100/US30 overnight"},
    {"key": "fixings", "title": "Benchmark fixings (gold/silver fix, WM/R 4pm)",
     "sources": ["benchmark_fixings"], "judge_families": [], "owner": SEAT,
     "axes": ["event", "mt5_target"], "derivations": ["auction_state", "sequence"],
     "mt5_mapping": "XAUUSD/XAGUSD/MT5 FX"},
    {"key": "off_exchange_short_volume", "title": "Off-exchange (TRF) and short-sale volume",
     "sources": ["finra_short_sale_otc"], "judge_families": [], "owner": SEAT,
     "axes": ["venue", "feed_type", "instrument"], "derivations": ["level", "surprise"],
     "mt5_mapping": "SPY/QQQ/DIA/GLD/USO -> US500/NAS100/US30/XAUUSD/XTIUSD"},
    {"key": "fails_and_borrow", "title": "Fails-to-deliver and borrow",
     "sources": ["sec_fails_to_deliver"], "judge_families": [], "owner": SEAT,
     "axes": ["positioning", "instrument"], "derivations": ["level", "change"],
     "mt5_mapping": "ETF fails -> index/metal CFDs; single names are event-lane only"},
    {"key": "futures_flow_minus_cfd_response", "priority_residual": True,
     "title": "FuturesFlow - CFDResponse", "sources": ["external_futures_tape"],
     "judge_families": [], "owner": SEAT, "axes": ["cross_asset", "mt5_target", "horizon"],
     "derivations": ["residual", "cross_impact"],
     "mt5_mapping": "ES/NQ/YM/GC/SI/CL/BZ/6E.. -> US500/NAS100/US30/XAUUSD/XAGUSD/XTIUSD/"
                    "XBRUSD/MT5 FX"},
    {"key": "cross_venue_lead_minus_mt5_reaction", "priority_residual": True,
     "title": "CrossVenueLead - MT5Reaction", "sources": ["external_futures_tape"],
     "judge_families": [], "owner": SEAT, "axes": ["cross_asset", "mt5_target", "horizon"],
     "derivations": ["cross_impact", "sequence"],
     "mt5_mapping": "external venue lead -> the MT5 CFD"},
    {"key": "crypto_reference_options", "title": "Crypto reference options -> Fusion crypto CFDs",
     "sources": ["crypto_reference_options"], "judge_families": [], "owner": SEAT,
     "axes": ["cross_asset", "iv_state", "mt5_target"], "derivations": ["level"],
     "mt5_mapping": "BTCUSD/SOLUSD CFDs"},
    {"key": "depth_queue_l2_l3", "title": "L2/L3 depth, queue, adds/cancels, microprice from sizes",
     "sources": ["mt5_tick_tape"], "venue_blocked": True, "judge_families": [], "owner": SEAT,
     "axes": ["feed_type", "liquidity_state", "size"],
     "derivations": ["imbalance", "liquidity_recovery"], "mt5_mapping": "the symbol itself"},
)

#: The tick-tape cell grid. Fixed and declared so the grid is the same every hour and its width
#: is what the judge's own multiplicity charge sees.
TICK_GRID: tuple[tuple[str, str, str], ...] = tuple(
    [("tick_flow", f, m) for f in ("tick_rule", "quote_ofi") for m in ("follow", "fade")]
    + [("tick_flow", f, m) for f in ("spread_bp", "quote_rate")
       for m in ("move_follow", "move_fade")]
    + [("flow_residual", f, m) for f in ("tick_rule", "quote_ofi")
       for m in ("unabsorbed", "exhaustion")])
CHARTS: tuple[str, ...] = ("M15", "H1")
GRID_FAMILY: dict[str, str] = {"tick_flow": "orderflow_ticks",
                               "flow_residual": "orderflow_minus_price_response"}

PAYER: dict[str, str] = {
    "follow": "one-sided aggressive quote flow is a participant working an order; the rest of "
              "it is still to come",
    "fade": "a burst of one-sided quote revisions is a liquidity provider skewing to shed "
            "inventory, and the skew reverts",
    "move_follow": "a move made while the venue is unusually wide or busy carries information "
                   "the provider is charging for",
    "move_fade": "a move made into a thin or frantic book was priced by absence and retraces "
                 "when depth returns",
    "unabsorbed": "flow that price has not yet paid for: the response is owed",
    "exhaustion": "a price move no flow paid for: nobody stands behind it",
}


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    try:
        os.replace(tmp, path)
    except PermissionError:
        # os.replace onto a read-only destination is legal on POSIX and WinError 5 on the box.
        path.chmod(0o644)
        os.replace(tmp, path)


def _jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


# ----------------------------------------------------------------------------- the tape
def tape_index(tape: Path) -> dict[str, dict[str, Path]]:
    """{SYMBOL: {YYYY-MM-DD: path}} through moat_series' reader (both writers' namings)."""
    import moat_series as ms
    old = ms.TICKS
    ms.TICKS = tape
    try:
        return ms.tape_index()
    finally:
        ms.TICKS = old


def day_buckets(path: Path) -> tuple[pd.DataFrame | None, int]:
    """(five-minute buckets of one tape day, last tick ms), or (None, 0)."""
    import moat_series as ms
    t = ms._read_day(path)
    if t is None:
        return None, 0
    return buckets_from_ticks(t["ms"], t["mid"], t["spread"]), int(t["ms"][-1])


def buckets_from_ticks(ms: np.ndarray, mid: np.ndarray, spread: np.ndarray) -> pd.DataFrame:
    """The features of every bucket in a sorted tick run. Pure arithmetic, vectorised."""
    bid, ask = mid - spread / 2.0, mid + spread / 2.0

    def sgn(x: np.ndarray) -> np.ndarray:
        # bid/ask are rebuilt from mid and spread, so an unchanged quote can differ by float
        # noise; a change below a billionth of the price is no change.
        d = np.diff(x, prepend=x[0])
        return np.where(np.abs(d) <= 1e-9 * np.abs(x), 0.0, np.sign(d))

    dmid = sgn(mid)
    # The tick test on the mid: an unchanged mid inherits the last non-zero sign.
    s = pd.Series(np.where(dmid == 0, np.nan, dmid)).ffill().fillna(0.0).to_numpy()
    ofi = sgn(bid) + sgn(ask)
    with np.errstate(divide="ignore", invalid="ignore"):
        sbp = np.where(mid > 0, spread / mid * 1e4, np.nan)
    b = (ms // BUCKET_MS) * BUCKET_MS
    f = pd.DataFrame({"b": b, "tick_rule": s, "quote_ofi": ofi, "mid_sign": dmid,
                      "spread_bp": sbp, "spread_max_bp": sbp, "quote_rate": 1.0})
    g = f.groupby("b", sort=True).agg({"tick_rule": "sum", "quote_ofi": "sum", "mid_sign": "sum",
                                       "spread_bp": "mean", "spread_max_bp": "max",
                                       "quote_rate": "sum"})
    g.index = pd.to_datetime(g.index, unit="ms", utc=True)
    g.index.name = "bucket"
    return g


def build_series(sym: str, days: dict[str, Path], existing: pd.DataFrame | None,
                 deadline: float) -> tuple[pd.DataFrame | None, dict[str, Any]]:
    """Existing vintage + every NEW completed bucket. Old buckets are never rewritten."""
    have_last = None
    if existing is not None and len(existing):
        have_last = pd.Timestamp(existing.index.max())
    frames: list[pd.DataFrame] = []
    last_ms = 0
    read = 0
    for day in sorted(days):
        if have_last is not None and day < have_last.strftime("%Y-%m-%d"):
            continue
        if time.monotonic() > deadline:
            break
        g, lm = day_buckets(days[day])
        read += 1
        if g is None:
            continue
        last_ms = max(last_ms, lm)
        frames.append(g)
    info: dict[str, Any] = {"days_on_tape": len(days), "days_read": read}
    if not frames:
        return existing, {**info, "new_buckets": 0}
    new = pd.concat(frames)
    new = new[~new.index.duplicated(keep="first")]
    # THE OPEN BUCKET IS NOT A BUCKET: anything at or after the last tick's own bucket may still
    # be filling, so it waits for the next pass. Completeness is what makes this a vintage.
    open_start = pd.Timestamp((last_ms // BUCKET_MS) * BUCKET_MS, unit="ms", tz="UTC")
    new = new[new.index < open_start]
    if have_last is not None:
        new = new[new.index > have_last]
    new = new.copy()
    new["available"] = new.index + pd.Timedelta(milliseconds=BUCKET_MS)
    new["ingested_utc"] = now_iso()
    out = new if existing is None or not len(existing) else pd.concat([existing, new])
    out = out.sort_index()
    return out, {**info, "new_buckets": len(new)}


def read_existing(sym: str, series_dir: Path) -> pd.DataFrame | None:
    p = series_dir / f"tf_{sym}.parquet"
    if not p.exists():
        return None
    try:
        f = pd.read_parquet(p)
    except Exception:
        return None
    if "bucket" in f.columns:
        f["bucket"] = pd.to_datetime(f["bucket"], utc=True)
        f = f.set_index("bucket")
    return f.sort_index()


def write_series(sym: str, f: pd.DataFrame, series_dir: Path) -> Path:
    import io
    buf = io.BytesIO()
    f.reset_index().to_parquet(buf, index=False)
    p = series_dir / f"tf_{sym}.parquet"
    _atomic_bytes(p, buf.getvalue())
    return p


# ----------------------------------------------------------------------------- own execution
def own_execution(fills: list[dict[str, Any]], intents: list[dict[str, Any]]) -> dict[str, Any]:
    """Slippage and reject STATES from the desk's own corpus. Measured; never a zero by absence."""
    if not fills and not intents:
        return {"status": "UNMEASURED", "why": "no fill corpus and no order intents on this host"}
    filled = [r for r in fills if isinstance(r.get("slip_frac"), (int, float))]
    states: dict[str, dict[str, Any]] = {}
    for r in filled:
        k = f"{r.get('symbol')}|{r.get('session') or 'unknown'}"
        states.setdefault(k, {"n": 0, "slips": []})
        states[k]["n"] += 1
        states[k]["slips"].append(float(r["slip_frac"]))
    table = {k: {"n": v["n"], "median_slip_bp": round(float(np.median(v["slips"])) * 1e4, 3),
                 "measured": v["n"] >= MIN_FILLS_PER_STATE} for k, v in sorted(states.items())}
    rejects: dict[str, int] = {}
    for r in fills:
        if r.get("rejected"):
            why = str(r.get("reject_reason") or r.get("retcode") or "unknown")
            rejects[why] = rejects.get(why, 0) + 1
    stamps = sorted(str(r.get("decided_at") or "") for r in fills if r.get("decided_at"))
    return {"status": "COLLECTING", "rows": len(fills), "intents": len(intents),
            "with_slippage": len(filled), "rejects_by_reason": rejects,
            "first": stamps[0] if stamps else None, "last": stamps[-1] if stamps else None,
            "slippage_states": table,
            "states_measured": sum(1 for v in table.values() if v["measured"]),
            "min_fills_per_state": MIN_FILLS_PER_STATE}


# ----------------------------------------------------------------------------- COT (counted)
def cot_depth(cot_dir: Path) -> dict[str, Any]:
    files = sorted(cot_dir.glob("*.parquet")) if cot_dir.is_dir() else []
    if not files:
        return {"status": "UNMEASURED", "why": f"no COT parquet under {cot_dir.name}/ here"}
    first, last, rows = None, None, 0
    for f in files:
        try:
            d = pd.read_parquet(f, columns=["report_date"])
        except Exception:
            continue
        dt = pd.to_datetime(d["report_date"], utc=True, errors="coerce").dropna()
        if dt.empty:
            continue
        rows += len(dt)
        first = min(first, dt.min()) if first is not None else dt.min()
        last = max(last, dt.max()) if last is not None else dt.max()
    if first is None:
        return {"status": "UNMEASURED", "why": "COT files unreadable here"}
    return {"status": "COLLECTING", "contracts": len(files), "rows": rows,
            "first": str(first.date()), "last": str(last.date()),
            "history_years": round((last - first).days / 365.25, 1)}


# ----------------------------------------------------------------------------- the miner
KNOWN_TICK_FIELDS = frozenset({"ts", "time", "time_msc", "bid", "ask", "last", "volume",
                               "volume_real", "flags", "recv_utc", "recv_mono", "symbol"})
#: MT5 tick flag bits: BID 2, ASK 4, LAST 8, VOLUME 16, BUY 32, SELL 64.
TICK_FLAG_NAMES = {2: "BID", 4: "ASK", 8: "LAST", 16: "VOLUME", 32: "BUY", 64: "SELL"}
KNOWN_FLAG_BITS = frozenset({2, 4})
KNOWN_ASSET_CLASSES = frozenset({"Equities", "Forex Exotics", "Forex", "Indices", "Crypto",
                                 "Commodities", "Soft Commodity", "Bonds", "Energy"})
KNOWN_ORDER_TYPES = frozenset({"market", "pending_stop", "pending_limit", "buy", "sell",
                               "buy_stop", "sell_stop", "buy_limit", "sell_limit"})
#: MT5 trade-server return codes the desk already names.
KNOWN_RETCODES = frozenset({10004, 10006, 10008, 10009, 10010, 10013, 10014, 10015, 10016,
                            10018, 10019, 10021, 10027})
MONTHS = "JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC"
EXPIRY_RE = re.compile(rf"(?:[._\-])((?:[FGHJKMNQUVXZ]\d{{1,2}})|(?:(?:{MONTHS})\d{{2}}))$",
                       re.IGNORECASE)


def mine_unknowns(*, tape: dict[str, dict[str, Path]], registry: dict[str, Any],
                  fills: list[dict[str, Any]], intents: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify what the grammar does not yet name, and the candidate cells each implies."""
    finds: list[dict[str, Any]] = []
    reg_syms = {k for k, v in registry.items() if isinstance(v, dict)}

    def find(kind: str, value: str, axis: str, cells: list[str], why: str) -> None:
        finds.append({"kind": kind, "value": value, "axis": axis, "candidate_cells": cells,
                      "why": why})

    for sym in sorted(set(tape) - reg_syms):
        find("new_product", sym, "instrument", [f"tick_flow|{sym}|*", f"flow_residual|{sym}|*"],
             "recorded on the tape but absent from the universe registry: UNCLASSIFIED, so the "
             "two-lane policy hunts nothing on it until it is classified")
    fields: dict[str, set[str]] = {}
    flag_bits: set[int] = set()
    try:
        import pyarrow.parquet as pq
    except Exception:                                             # pragma: no cover - install
        pq = None
    for sym, days in sorted(tape.items()):
        if not days or pq is None:
            continue
        latest = days[max(days)]
        try:
            names = set(pq.read_schema(latest).names)
        except Exception:
            continue
        for n in names - KNOWN_TICK_FIELDS:
            fields.setdefault(n, set()).add(sym)
        if "flags" in names:
            try:
                fl = pd.read_parquet(latest, columns=["flags"])["flags"]
                vals = np.unique(pd.to_numeric(fl, errors="coerce").dropna().astype("int64"))
                for v in vals:
                    for bit in TICK_FLAG_NAMES:
                        if int(v) & bit:
                            flag_bits.add(bit)
            except Exception:
                pass
    for n, syms in sorted(fields.items()):
        find("new_feed_field", n, "feed_type", [f"tick_flow|*|{n}"],
             f"tick field never named by the grammar, on {len(syms)} symbol(s)")
    for bit in sorted(flag_bits - KNOWN_FLAG_BITS):
        name = TICK_FLAG_NAMES[bit]
        cells = (["tick_flow|*|true_side_flag"] if name in ("BUY", "SELL")
                 else [f"tick_flow|*|{name.lower()}_prints"])
        find("new_tick_flag", name, "aggressor" if name in ("BUY", "SELL") else "feed_type",
             cells, "the venue sets this tick flag: "
             + ("TRUE aggressor side is published, replacing the tick-rule proxy"
                if name in ("BUY", "SELL") else "trade prints or volume ride the quote stream"))
    classes = {str(v.get("asset_class")) for v in registry.values()
               if isinstance(v, dict) and v.get("asset_class")}
    for c in sorted(classes - KNOWN_ASSET_CLASSES):
        find("new_asset_class", c, "instrument", [f"*|class:{c}|*"],
             "an asset class the factory has never seen; its symbols are hunted by nothing "
             "until the two-lane policy classifies it")
    for sym in sorted(reg_syms | set(tape)):
        m = EXPIRY_RE.search(sym)
        if m:
            find("expiry_convention", f"{sym}:{m.group(1).upper()}", "event",
                 [f"tick_flow|{sym}|expiry_state", f"*|{sym}|roll"],
                 "a dated-contract suffix in the symbol name: expiry and roll become events")
    otypes = {str(r.get("order_type")) for r in fills if r.get("order_type")}
    otypes |= {str(r.get("side")) for r in intents if r.get("side")}
    for o in sorted(otypes - KNOWN_ORDER_TYPES):
        find("new_order_type", o, "feed_type", [f"own_execution|*|{o}"],
             "an order type the desk sent that the grammar does not name")
    codes: set[int] = set()
    for r in [*fills, *intents]:
        rc = r.get("retcode")
        if isinstance(rc, int) or (isinstance(rc, str) and rc.isdigit()):
            codes.add(int(rc))
    for c in sorted(codes - KNOWN_RETCODES):
        find("new_retcode", str(c), "event", [f"own_execution|*|retcode:{c}"],
             "a broker return code the desk has not classified")
    by_kind: dict[str, int] = {}
    for f in finds:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
    return {"finds": finds, "by_kind": by_kind, "n": len(finds),
            "candidate_cells": sum(len(f["candidate_cells"]) for f in finds)}


def extend_grammar(miner: dict[str, Any], state: Path | None, *, write: bool
                   ) -> dict[str, list[str]]:
    """The open axes after this pass: declared values + every value ever discovered."""
    seen = _read(state, {}) if state else {}
    seen = seen if isinstance(seen, dict) else {}
    for f in miner.get("finds", []):
        vals = seen.setdefault(f["axis"], [])
        if f["value"] not in vals:
            vals.append(f["value"])
    if write and state is not None:
        _atomic_bytes(state, json.dumps(seen, indent=1, sort_keys=True).encode())
    return {ax: list(dict.fromkeys([*vals, *seen.get(ax, [])])) for ax, vals in GRAMMAR.items()}


# ----------------------------------------------------------------------------- the cells
def _may_hypothesise(sym: str, family: str) -> bool:
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        return True                 # the donation door re-applies it; absence is not refusal
    try:
        return bool(may_hypothesise(sym, family))
    except Exception:
        return True


def build_cells(series: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]],
                                                            dict[str, str]]:
    """The declared grid on every symbol whose vintage holds MIN_BUCKETS completed buckets.

    `series` is {symbol: {"buckets", "first", "last"}} -- a summary, never the frame."""
    from proposer_common import candidate
    out: list[dict[str, Any]] = []
    skipped: dict[str, str] = {}
    for sym in sorted(series):
        n = int(series[sym].get("buckets") or 0)
        if n < MIN_BUCKETS:
            skipped[sym] = (f"{n} completed buckets < {MIN_BUCKETS}: history too short to "
                            "judge")
            continue
        for (fam, feature, mode), chart in product(TICK_GRID, CHARTS):
            if not _may_hypothesise(sym, fam):
                skipped[sym] = "two-lane mandate: not a hypothesis-lane instrument"
                break
            params = {"source": f"tf_{sym}", "feature": feature, "mode": mode,
                      "timeframe": chart}
            c = candidate(SEAT, sym, fam, params,
                          f"{fam} {feature}/{mode} on {sym}: {PAYER[mode]}",
                          f"{fam} {feature} {mode} -> {sym} {chart}",
                          {"series": f"tf_{sym}", "buckets": n,
                           "first_bucket": series[sym]["first"],
                           "last_bucket": series[sym]["last"],
                           "flow_note": ("unit-depth proxy: Fusion publishes no depth or "
                                         "trade side")})
            c["chart"] = chart
            c["alpha_cluster"] = "session_liquidity"
            c["flow_family"] = GRID_FAMILY[fam] if feature in tfam.SIGNED or \
                fam == "flow_residual" else "liquidity_state_ticks"
            c["required_data"] = [f"desks/mt5/data/lake/series/tf_{sym}.parquet"]
            c["falsifier"] = (f"{feature} in mode {mode} has no relation to {sym} forward "
                              f"returns at {chart} out of sample, net of this broker's round "
                              "trip")
            out.append(c)
    return out, skipped


def judge_reach(families: list[str]) -> dict[str, Any]:
    """Whether each named family resolves in the registry the sealed gauntlet builds from."""
    if not families:
        return {"reaches_judge": False, "why": "no registered family compiles these cells"}
    try:
        from mt5desk.families import get_family_func
    except Exception as exc:
        return {"reaches_judge": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    missing = [f for f in families if get_family_func(f) is None]
    return {"reaches_judge": not missing, "families": families, "unresolved": missing,
            "path": ("proposer_common.donate -> data/intelligence/flow_factory/ -> "
                     "miner_candidate_compiler (EXACT_RECIPE) -> docket -> external_gauntlet")}


# ----------------------------------------------------------------------------- the pass
def run(*, dry_run: bool = False, tape_dir: Path | None = None, series_dir: Path | None = None,
        out: Path | None = None, budget_s: float = 900.0) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + budget_s
    tape_dir = tape_dir or TAPE
    series_dir = series_dir or SERIES_DIR
    tape = tape_index(tape_dir) if tape_dir.is_dir() else {}
    registry = _read(UNIVERSE_JSON, {}) or {}
    fills, intents = _jsonl(FILL_CORPUS), _jsonl(ORDER_INTENTS)

    # 1. COLLECT: fold completed buckets into each symbol's vintage series, stalest first. Only
    # a summary is kept per symbol, so the pass holds one series in memory at a time.
    def _age(sym: str) -> float:
        p = series_dir / f"tf_{sym}.parquet"
        return p.stat().st_mtime if p.exists() else 0.0

    series: dict[str, dict[str, Any]] = {}
    collect: dict[str, Any] = {}
    unreached: list[str] = []
    for sym in sorted(tape, key=lambda s: (_age(s), s)):
        existing = read_existing(sym, series_dir)
        if time.monotonic() > deadline:
            unreached.append(sym)
            f, info = existing, {"days_on_tape": len(tape[sym]), "days_read": 0,
                                 "new_buckets": 0, "why": "budget spent; next pass"}
        else:
            f, info = build_series(sym, tape[sym], existing, deadline)
            if f is not None and len(f) and not dry_run and info.get("new_buckets"):
                write_series(sym, f, series_dir)
        if f is not None and len(f):
            series[sym] = {"buckets": len(f), "first": str(f.index.min()),
                           "last": str(f.index.max())}
            info.update(series[sym])
        collect[sym] = info
        del f, existing

    # 2. MINE the unknown unknowns and extend the open grammar.
    miner = mine_unknowns(tape=tape, registry=registry, fills=fills, intents=intents)
    grammar = extend_grammar(miner, None if dry_run else GRAMMAR_STATE, write=not dry_run)
    grammar["instrument"] = sorted(set(grammar["instrument"]) | set(tape))
    grammar["mt5_target"] = sorted(set(grammar["mt5_target"]) | {k for k, v in registry.items()
                                                                  if isinstance(v, dict)})

    # 3. CELLS from the tape, donated once each to the one judge. No trial is charged here.
    cells, skipped = build_cells(series)
    from proposer_common import identity
    done = set(_read(DONATED, {}).get("identities") or [])
    fresh = [c for c in cells if identity(c["symbol"], c["family"], c["params"]) not in done]
    counts: dict[str, Any] = {}
    contract = None
    if not dry_run and fresh:
        from proposer_common import donate, donation_counts
        contract = donate(source=SEAT, candidates=fresh, tests_run=0)
        counts = donation_counts()
        if contract is not None:
            done |= {identity(c["symbol"], c["family"], c["params"]) for c in fresh}
            _atomic_bytes(DONATED, json.dumps({"at": now_iso(), "n": len(done),
                                               "identities": sorted(done)}).encode())

    # 4. THE REPORT, per family.
    own = own_execution(fills, intents)
    cot = cot_depth(COT_DIR)
    probe = _read(DEPTH_PROBE, {}) or {}
    probe_syms = probe.get("symbols") if isinstance(probe.get("symbols"), dict) else {}
    no_depth = sum(1 for v in probe_syms.values()
                   if isinstance(v, dict) and v.get("verdict") == "NO_DEPTH")
    tape_status: dict[str, Any]
    if tape:
        depth_days = [len(d) for d in tape.values()]
        tape_status = {"status": "COLLECTING", "symbols": len(tape),
                       "days_min": min(depth_days), "days_max": max(depth_days),
                       "series_symbols": len(series),
                       "buckets_total": int(sum(v["buckets"] for v in series.values())),
                       "unreached_this_pass": unreached}
    else:
        tape_status = {"status": "UNMEASURED",
                       "why": (f"no tick tape under {tape_dir} on this host: the recorder writes "
                               "it on the trading box, where this leg measures it")}
    by_ff: dict[str, int] = {}
    for c in cells:
        by_ff[c["flow_family"]] = by_ff.get(c["flow_family"], 0) + 1
    fams: list[dict[str, Any]] = []
    for spec in FAMILIES:
        srcs = [SOURCES[s] for s in spec["sources"]]
        held = [(s, SOURCES[s]) for s in spec["sources"] if SOURCES[s]["verdict"] == HELD]
        row: dict[str, Any] = {k: spec[k] for k in ("key", "title", "owner", "axes",
                                                     "derivations", "mt5_mapping")}
        row["priority_residual"] = bool(spec.get("priority_residual"))
        row["sources"] = spec["sources"]
        row["pit"] = {s: SOURCES[s]["pit"] for s in spec["sources"]}
        row["publication_lag"] = {s: SOURCES[s]["publication_lag"] for s in spec["sources"]}
        if spec.get("venue_blocked"):
            row["status"] = HELD
            row["why"] = (f"venue publishes no depth of market: data/tape/depth_probe.json "
                          f"reads NO_DEPTH on {no_depth} of {len(probe_syms)} probed symbols "
                          "(UNMEASURED if the probe is absent); a book synthesised from bid/ask "
                          "would model the synthesis")
            row["history"] = None
        elif held:
            # NEEDS_KEY when every blocked source is only waiting on a credential
            row["status"] = ("NEEDS_KEY" if all(v.get("access") == "NEEDS_KEY" for _, v in held)
                             else HELD)
            row["why"] = "; ".join(f"{s} [{v.get('access', 'UNREAD')}]: "
                                   f"{v.get('why_held', 'no permitting clause')}"
                                   for s, v in held)
            row["history"] = None
        elif spec["sources"] == ["mt5_tick_tape"]:
            row["status"] = tape_status["status"]
            row["history"] = tape_status
        elif spec["sources"] == ["own_fills"]:
            row["status"] = own["status"]
            row["history"] = {k: own.get(k) for k in ("rows", "first", "last", "with_slippage",
                                                       "states_measured", "why") if k in own}
        elif spec["sources"] == ["cftc_cot"]:
            row["status"] = cot["status"]
            row["history"] = cot
        else:
            row["status"] = "UNMEASURED"
            row["history"] = None
            uncollected = [s for s in spec["sources"] if not SOURCES[s].get("collector")]
            if uncollected:
                row["why"] = (f"permitted, no collector built yet: {', '.join(uncollected)} "
                              "(UNWIRED, not blocked)")
        row["access"] = {s: SOURCES[s].get("access", "UNREAD") for s in spec["sources"]}
        row["terms"] = [{"source": s, "verdict": v["verdict"], "access": v.get("access"),
                         "terms_url": v["terms_url"],
                         "quote": v["terms_quote"], "checked_at": v["checked_at"]}
                        for s, v in zip(spec["sources"], srcs, strict=True)]
        if spec["owner"] == SEAT:
            row["cells_generated"] = by_ff.get(spec["key"], 0)
        else:
            row["cells_generated"] = 0
            row["cells_note"] = f"minted by its owner organ ({spec['owner']}), not re-minted here"
        if spec["key"] == "own_execution_state":
            row["cells_note"] = (f"0: no registered family conditions on own slippage, and "
                                 f"{own.get('states_measured', 0)} state(s) reach "
                                 f"{MIN_FILLS_PER_STATE} fills")
        row["judge"] = judge_reach(list(spec["judge_families"]))
        fams.append(row)
    status_counts: dict[str, int] = {}
    for r in fams:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    doc = {
        "at": now_iso(), "writer": "research/flow_factory.py", "seat": SEAT,
        "status": "DRY_RUN" if dry_run else "RAN",
        "rule": ("first-party tape and fills are collected point-in-time and turned into judged "
                 "cells; every external source is judged per source (2026-10-13 ruling): "
                 "ingested only when its access state is API_PERMITTED or PUBLIC_PAGE with a "
                 "verbatim clause, else HELD/NEEDS_KEY by name; nothing here promotes, sizes or "
                 "conditions capital"),
        "grammar": {"axes": grammar, "derivations": list(DERIVATIONS),
                    "open": "every axis is open; the miner appends discovered values"},
        "families": fams, "status_counts": status_counts,
        "sources": SOURCES, "tape": tape_status, "collect": collect,
        "own_execution": own, "cot": cot,
        "unknown_unknown_miner": miner,
        "grid": {"total": len(cells), "per_symbol": len(TICK_GRID) * len(CHARTS),
                 "by_flow_family": by_ff, "skipped": skipped,
                 "min_buckets": MIN_BUCKETS},
        "donated": {"fresh": len(fresh), "contract": str(contract) if contract else None,
                    "minted": counts.get("donated", 0),
                    "refused_wrong_lane": counts.get("refused_wrong_lane", 0),
                    "refused_unstamped": counts.get("refused_unstamped", 0),
                    "trials_charged": 0,
                    "rule": ("each identity donated once with tests_run 0: counting is a "
                             "measurement; the judge charges what it judges")},
        "live_yield": "UNMEASURED until the trading box runs this leg on its tape",
        "promotion_authority": False,
        "seconds": round(time.monotonic() - t0, 2),
    }
    target = out or (None if dry_run else REPORT)
    if target is not None:
        _atomic_bytes(target, json.dumps(doc, indent=1, default=str).encode())
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly cycle is the clock)")
    ap.add_argument("--dry-run", action="store_true",
                    help="write no series, no grammar state and no donation")
    ap.add_argument("--out", type=Path, default=None, help="write the report here instead")
    ap.add_argument("--tape-dir", type=Path, default=None)
    ap.add_argument("--series-dir", type=Path, default=None)
    ap.add_argument("--budget-s", type=float, default=900.0)
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run, tape_dir=a.tape_dir, series_dir=a.series_dir, out=a.out,
              budget_s=a.budget_s)
    print(f"flow_factory: {doc['status']} -- tape {doc['tape']['status']}, grid "
          f"{doc['grid']['total']}, fresh {doc['donated']['fresh']}, minted "
          f"{doc['donated']['minted']}, unknowns {doc['unknown_unknown_miner']['n']}")
    for r in doc["families"]:
        print(f"  {r['key']:<44} {r['status']:<11} cells={r['cells_generated']:<5} "
              f"judge={r['judge'].get('reaches_judge')}")
    print(f"YIELD cells={doc['grid']['total']} minted={doc['donated']['minted']} "
          f"statuses={doc['status_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
