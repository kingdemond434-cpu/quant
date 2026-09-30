"""THE INSTITUTIONAL FOOTPRINT ONTOLOGY -- the frozen top-level map every country pack fills in.

THE PRINCIPAL, 2026-09-30 (17:47-18:14Z, five messages, one ruling): reconstruct the public
institutional footprint -- positioning, options, swaps, funds, hedge-fund leverage, dealer and
bank balance sheets, repo and collateral, money-market plumbing, securities lending, settlement,
beneficial ownership, corporate forced flow, cross-border capital, official reserves, central-bank
operations, physical inventory, participant-type flow, index mechanics, public chains, execution
routing and systematic mechanical flow -- in EVERY economically relevant jurisdiction, and merge
it into the country packs and region commands rather than build a second subsystem. After this
layer the taxonomy is FROZEN: growth comes from new jurisdictions and new sources that fit these
classes, not from new classes.

WHAT LIVES HERE AND WHAT DOES NOT. This module is the ontology and nothing else: the classes, the
jurisdiction template, the coverage statuses, the latent actors and the latent states with the
evidence each one reads. The SOURCES are rows in
`desks/mt5/data/source_rosters/institutional_footprint.yaml` (one canonical id per dataset,
`institutional.<jurisdiction>.<publisher>.<dataset>`), which the unified mining registry reads in
place. The ENGINE that turns rows into states and cells is
`desks/mt5/research/institutional_footprint.py`. Each country pack exposes its own slice through
`countries._institutional.footprint(code)`.

THE HONEST CEILING, stated once so no reader mistakes a state for a book. Prime-broker books,
individual dealer inventories, bilateral OTC books, internal market-maker flow and paid tick data
are not public. Every latent state here is therefore a PROBABILITY WITH AN INTERVAL, built from
aggregates, and dealer positioning is carried as competing SCENARIOS scored against observed
price behaviour -- never as a signed number the public data cannot support.
"""
from __future__ import annotations

from typing import Any

# --------------------------------------------------------------------------- the frozen classes
#: The top-level source classes. FROZEN (principal 2026-09-30 18:08Z): a new public dataset is
#: filed under one of these; a dataset that fits none is flagged by the future-source watcher as
#: `UNCLASSIFIED` for a human to rule on, never silently given a new class.
SOURCE_CLASSES: tuple[dict[str, str], ...] = (
    {"id": "futures_positioning", "reveals": "trader-category and participant positions in "
     "listed futures: who is long, who is short, how concentrated"},
    {"id": "options_positioning", "reveals": "put/call volume and OI, strike and expiry "
     "concentration, the raw material of the dealer-gamma scenarios"},
    {"id": "otc_swaps", "reveals": "swap-dealer and SDR activity by product, tenor and currency"},
    {"id": "fund_flows", "reveals": "mutual-fund, ETF and MMF net flows and creations"},
    {"id": "fund_holdings", "reveals": "13F, N-PORT and national equivalents: who owns what"},
    {"id": "hedge_fund_leverage", "reveals": "Form PF and OFR aggregates: gross/net leverage, "
     "repo dependence, counterparties, liquidity"},
    {"id": "dealer_bank_balance_sheet", "reveals": "primary-dealer positions, financing and "
     "fails; H.8, bank derivatives books, BIS dealer aggregates"},
    {"id": "repo_collateral", "reveals": "cleared, tri-party and bilateral repo rates, volumes, "
     "haircuts and collateral mix; SOMA securities lending"},
    {"id": "money_market_plumbing", "reveals": "MMF holdings and repo exposure, RRP take-up, "
     "unsecured funding (ECB MMSR, SONIA, TONA)"},
    {"id": "securities_lending_short", "reveals": "short interest, short-sale volume, "
     "aggregate short positions, borrow demand"},
    {"id": "settlement_fails", "reveals": "fails-to-deliver, primary-dealer fails, CCP margin "
     "and clearing-house stress"},
    {"id": "beneficial_ownership", "reveals": "13D/13G and national large-holder filings"},
    {"id": "corporate_flow", "reveals": "insider trades, Form 144, buybacks, issuance, "
     "lockups, tenders, converts: forced corporate supply and demand"},
    {"id": "cross_border_capital", "reveals": "TIC, balance of payments, portfolio flows, "
     "cross-border bank claims, custody for foreign official accounts"},
    {"id": "official_reserves", "reveals": "COFER, central-bank reserves and gold purchases, "
     "sovereign-fund holdings, auction allotments by investor class"},
    {"id": "central_bank_operations", "reveals": "repo/RRP operations, SOMA and balance "
     "sheets, FX intervention"},
    {"id": "physical_inventory", "reveals": "warehouse stocks, warrants, delivery notices, "
     "vault holdings, customs, production and port stocks"},
    {"id": "participant_type_flow", "reveals": "exchange trading by investor type (foreign, "
     "institution, individual, dealer, trust)"},
    {"id": "index_mechanical", "reveals": "index adds/deletes, reconstitution, rebalances, "
     "ETF creations: deterministic passive flow"},
    {"id": "public_chain", "reveals": "public-chain large-holder transfers, as a SENSOR only "
     "(no crypto venue is ever hunted)"},
    {"id": "execution_routing", "reveals": "Rule 605/606 routing and execution quality: the "
     "liquidity-provider ecology"},
    {"id": "systematic_mechanical", "reveals": "CTA, vol-control, risk-parity, pension "
     "rebalance, roll, expiry and fixing models from public methodology"},
    {"id": "enforcement_archaeology", "reveals": "documented spoofing, layering, marking the "
     "close and squeezes: detector phenotypes and negative knowledge"},
    {"id": "fx_settlement_fixing", "reveals": "CLS aggregate FX activity, benchmark fixing "
     "windows (WM/R 4pm, Tokyo, ECB), month and quarter end"},
    {"id": "pension_insurance", "reveals": "Form 5500, public pension allocations, insurer "
     "aggregates: long-duration allocator demand"},
    {"id": "adviser_topology", "reveals": "Form ADV and Private Fund Statistics: the actor map "
     "and leverage ecology, not trades"},
    {"id": "mortgage_convexity", "reveals": "MBS duration and refinancing proxies, NY Fed "
     "agency-MBS operations"},
    {"id": "observed_price_footprint", "reveals": "the desk's own MT5 bars: whether price "
     "confirms or refuses what the flows imply"},
)
CLASS_IDS: tuple[str, ...] = tuple(c["id"] for c in SOURCE_CLASSES)

#: What every jurisdiction owes the atlas (principal 2026-09-30 18:02Z: "regulator + exchange +
#: clearing house + central bank + treasury + custodial/settlement + fund filings + short/position
#: data + derivatives reports + physical market data"). A role with no source in a jurisdiction is
#: a coverage cell like any other and must carry one of the statuses below.
JURISDICTION_ROLES: tuple[str, ...] = (
    "regulator", "exchange", "clearing_house", "central_bank", "treasury",
    "custodian_settlement", "fund_filings", "short_position", "derivatives_reports",
    "physical_market")

#: The role a source class discharges, beside the publisher's own role: a CFTC report is both the
#: regulator's and a derivatives report. A row serves `row["role"]` AND `CLASS_ROLE[class]`.
CLASS_ROLE: dict[str, str] = {
    "futures_positioning": "derivatives_reports", "options_positioning": "derivatives_reports",
    "otc_swaps": "derivatives_reports", "securities_lending_short": "short_position",
    "physical_inventory": "physical_market", "fund_holdings": "fund_filings",
    "fund_flows": "fund_filings", "beneficial_ownership": "fund_filings",
    "settlement_fails": "clearing_house", "repo_collateral": "custodian_settlement",
    "central_bank_operations": "central_bank", "official_reserves": "central_bank",
    "cross_border_capital": "treasury"}


def roles_of(row: dict[str, Any]) -> set[str]:
    out = {str(row.get("role") or "")}
    out.add(CLASS_ROLE.get(str(row.get("source_class") or ""), ""))
    return {r for r in out if r in JURISDICTION_ROLES}


# --------------------------------------------------------------------------- coverage statuses
#: Exactly one status per (jurisdiction x source class) cell. `UNSEARCHED` is not one of the
#: principal's seven: it is the honest reading of a cell nobody has looked at yet, and it is RED.
COVERAGE_STATUSES: tuple[str, ...] = (
    "ACTIVE",                     # ingested, and a consumer has read it
    "DISCOVERED_NOT_INGESTED",    # exists and is public; no fetch or no consumer yet
    "BLOCKED_SUBSTITUTE",         # blocked (terms, auth, robots) and a public substitute named
    "PAID_PUBLIC_PROXY",          # the real dataset is paid; a free proxy stands in
    "NOT_PUBLISHED",              # searched; the jurisdiction does not publish it
    "TESTED_NO_INFORMATION",      # ingested and judged; no incremental information
    "NOT_RELEVANT",               # no MT5 transmission from this jurisdiction for this class
)
UNSEARCHED = "UNSEARCHED"
#: Statuses that close a cell. Everything else is open work for the source frontier.
CLOSED_STATUSES: frozenset[str] = frozenset({
    "ACTIVE", "BLOCKED_SUBSTITUTE", "PAID_PUBLIC_PROXY", "NOT_PUBLISHED",
    "TESTED_NO_INFORMATION", "NOT_RELEVANT"})

# --------------------------------------------------------------------------- jurisdictions
#: The jurisdictions the atlas is enforced over, each bound to the country pack (or region pack)
#: it merges into. Order is the principal's replication order (18:02Z): US, UK, EU, Japan,
#: China/HK, Korea, Australia, Canada, Brazil, India, then the rest.
JURISDICTIONS: tuple[dict[str, Any], ...] = (
    {"code": "us", "pack": "us", "region": "north_america", "currencies": ("USD",)},
    {"code": "uk", "pack": "uk", "region": "europe", "currencies": ("GBP",)},
    {"code": "ea", "pack": "ea", "region": "europe", "currencies": ("EUR",)},
    {"code": "jp", "pack": "jp", "region": "east_asia", "currencies": ("JPY",)},
    {"code": "cn", "pack": "cn", "region": "east_asia", "currencies": ("CNH", "CNY")},
    {"code": "hk", "pack": "hk", "region": "east_asia", "currencies": ("HKD",)},
    {"code": "kr", "pack": "kr", "region": "east_asia", "currencies": ("KRW",)},
    {"code": "tw", "pack": "tw", "region": "east_asia", "currencies": ("TWD",)},
    {"code": "au", "pack": "au", "region": "oceania", "currencies": ("AUD",)},
    {"code": "nz", "pack": "nz", "region": "oceania", "currencies": ("NZD",)},
    {"code": "ca", "pack": "ca", "region": "north_america", "currencies": ("CAD",)},
    {"code": "br", "pack": "br", "region": "latam", "currencies": ("BRL",)},
    {"code": "mx", "pack": "mx", "region": "latam", "currencies": ("MXN",)},
    {"code": "ind", "pack": "ind", "region": "south_asia", "currencies": ("INR",)},
    {"code": "sg", "pack": "sg", "region": "southeast_asia", "currencies": ("SGD",)},
    {"code": "my", "pack": "my", "region": "southeast_asia", "currencies": ("MYR",)},
    {"code": "ch", "pack": "ch", "region": "europe", "currencies": ("CHF",)},
    {"code": "se", "pack": "se", "region": "europe", "currencies": ("SEK",)},
    {"code": "no", "pack": "no", "region": "europe", "currencies": ("NOK",)},
    {"code": "za", "pack": "za", "region": "africa", "currencies": ("ZAR",)},
    {"code": "sa", "pack": "sa", "region": "mena", "currencies": ("SAR",)},
    {"code": "ae", "pack": "ae", "region": "mena", "currencies": ("AED",)},
    {"code": "tr", "pack": "tr", "region": "europe", "currencies": ("TRY",)},
    {"code": "pl", "pack": "pl", "region": "europe", "currencies": ("PLN",)},
    {"code": "global", "pack": "institutional", "region": "institutional", "currencies": ()},
)
JURISDICTION_CODES: tuple[str, ...] = tuple(j["code"] for j in JURISDICTIONS)
PACK_OF: dict[str, str] = {j["code"]: j["pack"] for j in JURISDICTIONS}
JURISDICTION_OF_PACK: dict[str, str] = {j["pack"]: j["code"] for j in JURISDICTIONS}


def coverage_jurisdictions() -> tuple[str, ...]:
    """The listed jurisdictions first, then EVERY other country or region pack on disk: the
    atlas is enforced over every department, and a pack with no atlas row yet is a column of
    UNSEARCHED cells -- the frontier, published, never omitted."""
    from pathlib import Path
    here = Path(__file__).resolve().parents[1]
    extra = sorted(p.parent.name for p in here.glob("*/pack.py")
                   if p.parent.name not in JURISDICTION_OF_PACK)
    return JURISDICTION_CODES + tuple(extra)

#: Classes that are, by construction, not a per-jurisdiction publication: the global layer
#: carries them and a country cell for them reads NOT_RELEVANT unless a row says otherwise.
GLOBAL_ONLY_CLASSES: frozenset[str] = frozenset({
    "public_chain", "systematic_mechanical", "observed_price_footprint"})

# --------------------------------------------------------------------------- latent actors
#: The actor atlas (principal 17:47Z). Each source row names the actors it informs; a state is
#: always a statement about ONE of these, never about "the market".
ACTORS: tuple[str, ...] = (
    "dealers_intermediaries", "leveraged_funds_ctas", "asset_managers", "commercial_hedgers",
    "passive_etf", "retail_offexchange", "corporate_insiders", "foreign_official",
    "option_market_makers", "pensions_insurers", "banks", "money_funds",
    "physical_consumers_producers", "public_chain_holders")

# --------------------------------------------------------------------------- latent states
#: Each state: the actor it describes, the MT5 assets it transmits to, and its EVIDENCE -- one
#: row per input with the feature it reads (a column the engine computes from a lake frame), the
#: sign of its effect on the log-odds, and a weight. Weights are PRIORS, stated, not fitted: the
#: gauntlet is where information is measured, and a state that carries no information will fail
#: there under the trials it is charged. `min_inputs` is how many inputs must be measured before
#: the state is emitted at all; below it the state reads UNMEASURED.
LATENT_STATES: tuple[dict[str, Any], ...] = (
    {"id": "leveraged_fund_crowding", "actor": "leveraged_funds_ctas",
     "assets": ("XAUUSD", "XAGUSD", "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "US500",
                "NAS100"),
     "evidence": (("cot.lev_net_pct", +1, 1.0), ("cot.lev_net_z", +1, 0.6),
                  ("cot.oi_chg_z", +1, 0.4), ("cot.conc_top4_pct", +1, 0.3)),
     "min_inputs": 2},
    {"id": "marginal_buyer_exhaustion", "actor": "leveraged_funds_ctas",
     "assets": ("XAUUSD", "XAGUSD", "EURUSD", "USDJPY", "US500", "NAS100"),
     "evidence": (("cot.lev_net_pct", +1, 0.8), ("price.div_vs_positioning", +1, 1.0),
                  ("cot.oi_chg_z", -1, 0.5)),
     "min_inputs": 2},
    {"id": "commercial_hedging_pressure", "actor": "commercial_hedgers",
     "assets": ("XAUUSD", "XAGUSD", "XTIUSD", "XBRUSD", "XNGUSD"),
     "evidence": (("cot.swap_net_pct", -1, 1.0), ("cot.swap_net_z", -1, 0.5)),
     "min_inputs": 1},
    {"id": "dealer_balance_sheet_pressure", "actor": "dealers_intermediaries",
     "assets": ("US500", "NAS100", "XAUUSD", "USDJPY", "EURUSD", "USDX"),
     "evidence": (("nyfed.pd_net_positions_z", +1, 1.0), ("nyfed.pd_fails_z", +1, 0.8),
                  ("ofr.repo_rate_spread_z", +1, 0.6), ("cot.dealer_net_pct", -1, 0.3)),
     "min_inputs": 1},
    {"id": "repo_funding_stress", "actor": "banks",
     "assets": ("US500", "NAS100", "XAUUSD", "USDJPY", "USDX"),
     "evidence": (("ofr.repo_rate_spread_z", +1, 1.0), ("nyfed.rrp_chg_z", -1, 0.4),
                  ("ofr.repo_volume_chg_z", -1, 0.3)),
     "min_inputs": 1},
    {"id": "collateral_scarcity", "actor": "dealers_intermediaries",
     "assets": ("USDX", "XAUUSD", "US500"),
     "evidence": (("nyfed.seclending_demand_z", +1, 1.0), ("nyfed.pd_fails_z", +1, 0.6)),
     "min_inputs": 1},
    {"id": "hedge_fund_leverage_pressure", "actor": "leveraged_funds_ctas",
     "assets": ("US500", "NAS100", "XAUUSD", "USDJPY"),
     "evidence": (("ofr.hf_leverage_z", +1, 1.0), ("ofr.hf_repo_borrowing_z", +1, 0.8)),
     "min_inputs": 1},
    {"id": "short_crowding", "actor": "leveraged_funds_ctas",
     "assets": ("US500", "NAS100", "US30"),
     "evidence": (("finra.short_volume_ratio_z", +1, 1.0), ("sec.ftd_z", +1, 0.5)),
     "min_inputs": 1},
    {"id": "foreign_official_demand", "actor": "foreign_official",
     "assets": ("USDX", "XAUUSD", "USDJPY", "USDCNH"),
     "evidence": (("fed.custody_chg_z", +1, 1.0), ("treasury.tic_official_z", +1, 0.6),
                  ("treasury.auction_indirect_z", +1, 0.6)),
     "min_inputs": 1},
    {"id": "passive_forced_flow", "actor": "passive_etf",
     "assets": ("US500", "NAS100", "XAUUSD"),
     "evidence": (("calendar.index_event", +1, 1.0), ("calendar.month_end", +1, 0.4),
                  ("ici.etf_issuance_z", +1, 0.6)),
     "min_inputs": 1},
    {"id": "fund_redemption_pressure", "actor": "asset_managers",
     "assets": ("US500", "NAS100", "XAUUSD"),
     "evidence": (("ici.mf_flow_z", -1, 1.0), ("cot.am_net_chg_z", -1, 0.5)),
     "min_inputs": 1},
    {"id": "physical_tightness", "actor": "physical_consumers_producers",
     "assets": ("XAUUSD", "XAGUSD", "XCUUSD", "XTIUSD"),
     "evidence": (("physical.stock_chg_z", -1, 1.0), ("physical.registered_ratio_z", -1, 0.6)),
     "min_inputs": 1},
    {"id": "forced_deleveraging", "actor": "leveraged_funds_ctas",
     "assets": ("US500", "NAS100", "XAUUSD", "USDJPY", "AUDJPY"),
     "evidence": (("cot.lev_net_pct", +1, 0.5), ("ofr.repo_rate_spread_z", +1, 0.6),
                  ("price.drawdown_z", +1, 0.8), ("cot.oi_chg_z", -1, 0.6)),
     "min_inputs": 2},
)
STATE_IDS: tuple[str, ...] = tuple(s["id"] for s in LATENT_STATES)

#: Dealer gamma is NOT a latent state with one number. OI does not say which side the dealer
#: holds, so the engine scores three scenarios against observed intraday behaviour and publishes
#: the posterior over them (principal 17:47Z: "long-dealer / short-dealer / neutral scenario and
#: ask which best explains observed behaviour").
DEALER_GAMMA_SCENARIOS: tuple[str, ...] = ("dealer_long_gamma", "dealer_neutral",
                                           "dealer_short_gamma")

#: The controlled feature family every raw series explodes into (17:47Z). The engine computes the
#: first eight on every frame; the interaction rows are what the conditioner cells cross with
#: session and regime axes downstream, so they are not re-materialised here.
FEATURE_FAMILY: tuple[str, ...] = (
    "level", "change", "acceleration", "rolling_percentile", "z_score", "historical_extreme",
    "divergence_vs_price", "change_x_return",
    "cross_sectional_rank", "divergence_vs_volatility", "flow_x_liquidity", "flow_x_session",
    "flow_x_regime", "flow_x_event", "crowding_x_reversal", "crowding_x_continuation",
    "position_x_funding", "position_x_options", "position_x_macro_surprise")

# --------------------------------------------------------------------------- triangulation
#: Every commodity is read three ways at once (18:12Z): financial positioning, physical market,
#: commercial actors. Values are canonical source ids from the roster; the coverage engine checks
#: that each view has at least one ACTIVE or DISCOVERED row and names the gap when not.
COMMODITY_TRIANGULATION: dict[str, dict[str, tuple[str, ...]]] = {
    "gold": {
        "financial": ("institutional.us.cftc.cot_disaggregated",
                      "institutional.cn.shfe.daily_ranking",
                      "institutional.jp.jpx.investor_type_derivatives",
                      "institutional.ind.mcx.participant_oi"),
        "physical": ("institutional.us.cme.comex_warehouse_stocks",
                     "institutional.global.lbma.vault_holdings",
                     "institutional.global.lbma.clearing_statistics",
                     "institutional.cn.sge.delivery_volume", "institutional.cn.shfe.warrants"),
        "commercial": ("institutional.global.wgc.central_bank_purchases",
                       "institutional.global.wgc.etf_flows",
                       "institutional.global.imf.ifs_reserves_gold"),
    },
    "silver": {
        "financial": ("institutional.us.cftc.cot_disaggregated",),
        "physical": ("institutional.us.cme.comex_warehouse_stocks",
                     "institutional.global.lbma.vault_holdings", "institutional.cn.shfe.warrants"),
        "commercial": ("institutional.global.silver_institute.balance",),
    },
    "crude": {
        "financial": ("institutional.us.cftc.cot_disaggregated",
                      "institutional.global.ice.cot_brent",
                      "institutional.cn.ine.daily_ranking"),
        "physical": ("institutional.us.eia.weekly_petroleum_status",
                     "institutional.global.jodi.oil",
                     "institutional.cn.ine.warrants"),
        "commercial": ("institutional.global.opec.momr",),
    },
    "copper": {
        "financial": ("institutional.us.cftc.cot_disaggregated", "institutional.global.lme.cot",
                      "institutional.cn.shfe.daily_ranking"),
        "physical": ("institutional.global.lme.warehouse_stocks", "institutional.cn.shfe.warrants",
                     "institutional.us.cme.comex_warehouse_stocks"),
        "commercial": ("institutional.global.icsg.balance",),
    },
    "iron_ore": {
        "financial": ("institutional.sg.sgx.iron_ore_oi", "institutional.cn.dce.daily_ranking"),
        "physical": ("institutional.cn.dce.warrants", "institutional.cn.customs.imports"),
        "commercial": ("institutional.au.dfat.resources_exports",),
    },
    "palm_oil": {
        "financial": ("institutional.my.bursa.fcpo_oi",),
        "physical": ("institutional.my.mpob.stocks_production_exports",),
        "commercial": ("institutional.my.mpob.stocks_production_exports",),
    },
}

# --------------------------------------------------------------------------- mechanical models
#: Deterministic flow models from PUBLIC methodology and observable state (18:08Z item 14). Each
#: is an estimate of an unobserved book, labelled as such; none claims to know a private position.
MECHANICAL_FLOW_MODELS: tuple[dict[str, str], ...] = (
    {"id": "cta_trend_positioning", "method": "sum of sign(return over 20/60/120/250d) scaled "
     "by inverse realised vol, per asset; the implied position change is the forced flow"},
    {"id": "vol_control_exposure", "method": "target vol / realised vol (21d), capped at the "
     "published leverage limit; exposure change on a vol shock is the forced sale"},
    {"id": "risk_parity_deleveraging", "method": "inverse-vol weights across equity, bonds, "
     "gold; a joint vol rise implies gross de-risking"},
    {"id": "pension_month_end_rebalance", "method": "equity vs bond month-to-date relative "
     "return against a 60/40 policy mix; the gap is the rebalance direction"},
    {"id": "commodity_index_roll", "method": "BCOM/GSCI published roll windows (5th-9th "
     "business day): calendar-deterministic front-to-next roll pressure"},
    {"id": "futures_roll", "method": "quarterly index and FX futures roll weeks"},
    {"id": "option_expiry", "method": "monthly and quarterly expiry; pin density from OI"},
    {"id": "benchmark_fixing", "method": "WM/R 16:00 London, Tokyo 09:55, ECB 14:15 CET; "
     "month-end and quarter-end fix concentration"},
    {"id": "passive_index_rebalance", "method": "published S&P/FTSE/MSCI/Nasdaq rebalance and "
     "reconstitution dates"},
)


def as_dict() -> dict[str, Any]:
    """The whole ontology as plain data, for the coverage report and the tests."""
    return {"source_classes": SOURCE_CLASSES, "jurisdiction_roles": JURISDICTION_ROLES,
            "coverage_statuses": COVERAGE_STATUSES, "unsearched": UNSEARCHED,
            "jurisdictions": JURISDICTIONS, "actors": ACTORS, "latent_states": LATENT_STATES,
            "dealer_gamma_scenarios": DEALER_GAMMA_SCENARIOS, "feature_family": FEATURE_FAMILY,
            "commodity_triangulation": COMMODITY_TRIANGULATION,
            "mechanical_flow_models": MECHANICAL_FLOW_MODELS}
