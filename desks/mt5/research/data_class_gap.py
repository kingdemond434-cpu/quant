"""THE TIER-1 DATA-CLASS GAP LIST -- which classes of data a tier-1 systematic shop reads for the
MT5 universe, what this desk already ingests for each, how fresh it is, and the lawful free sources
worldwide it does not read yet. Report-only; regenerated every hour.

    python desks/mt5/research/data_class_gap.py --once
    python desks/mt5/research/data_class_gap.py --once --md <path>.md   # plus the human copy

WHY THIS EXISTS (hourly pass item 14, 2026-10-29: "DATASET HUNT at max with a tier-1 data-class gap
list"). `tier1_gap.py` counts datasets in orders of magnitude and `world_dataset_hunter.py`
walks the public statistical world, but neither says WHICH KIND of information is missing. A desk
with 30,000 DBnomics series and no implied-vol surface, no fund flows and no auction results is
wide in one class and blind in three. Tier-1 shops (RenTech, Two Sigma, Citadel, DE Shaw, Man/AHL,
Millennium pods) are organised by data CLASS -- positioning, flows, curves, vol, weather, physical,
text -- and so is this list. A gap note written once by hand goes stale the day after; this one is
DERIVED from the repo's producers, registries and the box's artifacts every pass, so it moves when a
producer lands.

WHAT EACH ROW MEASURES (nothing here is typed in except the class definitions and the candidate
sources, which are facts about the world):

    producers     the declared modules for the class that EXIST in this tree, each with its clock
                  (an hourly_cycle leg found by its own `_producer(...)` call, or a schedule file
                  that names it), else UNWIRED -- an unwired producer is a defect (III.16),
                  not cover
    hosts_in_code every non-test file carrying a URL on one of the class's data URLs, split into
                  FETCHERS and CATALOGUES (country packs, rosters, ontologies name a host without
                  reading it; a mention is never ingestion)
    freshness     each producer's artifact (resolved from the runtime attestation the box commits)
                  and its age from the artifact's own timestamp on THIS host; absent -> UNMEASURED
    catalogues    rows of the desk's own dataset catalogues that name the class: the world hunter's
                  catalog (box), data_registry.json and the free-stack roster
    candidates    the best lawful free public sources worldwide for the class, every region and
                  language, each with its terms status read from the ONE register
                  (libs/data/terms_fence.SOURCE_POLICY): a host with no row, or a row without a
                  quoted clause, is TERMS_UNMEASURED -- never OK -- and is mined for ideas only
    gap_score     weight x (1 - coverage) x (1 + ln(1 + open lawful candidates)); coverage is a
                  measured ladder (NONE 0, CATALOGUED 0.2, PRODUCER 0.45, WIRED 0.7,
                  WIRED_FRESH 1.0; stale wired 0.55). A class nobody can measure scores as WIRED
                  with its freshness UNMEASURED: absence never reads as cover, and never as zero

OWNERSHIP IS DATA, NOT A FILTER. A class another thread owns (futures curves and COT: the Futures
thread; the Asian physical gold rows: the asia-gold worker; power grids: the unlanded entsoe/smard
branches) is still listed and scored -- its `owner` says who closes it, so no session builds it
twice.

MT5 MANDATE. Every candidate informs an MT5 instrument. No crypto-exchange host appears here: crypto
is read only as MT5 CFDs (check_mt5_purity). Single-name filings stay event-lane inputs.

Clock: `hourly_cycle:data_class_gap` (department `data`, layer `information`).
Artifact: desks/mt5/reports/DATA_CLASS_GAP.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "DATA_CLASS_GAP.json"
HOURLY = DESK / "research" / "hourly_cycle.py"
RUNTIME_STATE = ROOT / "docs" / "research" / "runtime_state.json"
WORLD_CATALOG = DESK / "data" / "world_datasets" / "catalog.json"
REGISTRY = DESK / "data" / "data_registry.json"
FREE_STACK = DESK / "data" / "free_stack_sources.json"
UNMEASURED = "UNMEASURED"
TERMS_UNMEASURED = "TERMS_UNMEASURED"

#: Where code that reads the world lives. Tests never count as a producer.
SCAN_DIRS = ("desks/mt5/research", "desks/mt5/macro", "desks/mt5/mt5desk",
             "desks/mt5/side_channels", "desks/mt5/recorders", "desks/mt5/scripts", "libs",
             "scripts", "ops")
#: Files that NAME hosts without fetching them (rosters, country packs, ontologies, fences, probes).
_CATALOGUE_RX = re.compile(
    r"(?:^|/)(?:countries/|macro_region/|equivalence_ontology|world_crawler|terms_fence|"
    r"data_axis_miner|deep_forest|check_|probe_|scout_roster|source_registry|knowledge_graph|"
    r"research_gap_map|fund_playbook|paid_data|_declared_data_plane|_data_plane_miner|"
    r"_retired/|data_class_gap|terms_basis_census)")
#: Adjacent string literals ("https://host/a/" "b/c", across lines or with `+`) are one URL.
_JOIN = re.compile(r"([\"'])\s*\n\s*\+?\s*[rfbRFB]{0,2}\1|([\"'])\s*\+\s*[rfbRFB]{0,2}\2")
#: Schedule files: a module named in one of these runs on that clock.
CLOCK_FILES = ("ops/*.sh", "ops/*.service", "ops/*.timer", "desks/mt5/scripts/*.ps1",
               "desks/mt5/recorders/*.ps1", "desks/mt5/side_channels/run_all_miners.py",
               "desks/mt5/research/daily_cycle.py")
#: Box keys the common brief names (presence only is ever read; a key is never printed).
BOX_KEYS = ("COMTRADE_API_KEY", "USAJOBS_API_KEY", "ADZUNA_APP_KEY", "EIA_API_KEY",
            "FIRMS_MAP_KEY", "NASS_API_KEY", "EARTHDATA_TOKEN", "BLS_API_KEY", "ESTAT_APP_ID")

COVERAGE = {"NONE": 0.0, "CATALOGUED": 0.2, "PRODUCER": 0.45, "WIRED": 0.7, "WIRED_STALE": 0.55,
            "WIRED_FRESH": 1.0}
FRESH_DEFAULT_H = 48.0
#: In-artifact timestamp keys, first hit wins.
TS_KEYS = ("generated_at", "at", "as_of", "updated_at", "measured_at", "built_at", "written_at",
           "ts", "created_at")


def _c(cid: str, name: str, url: str, region: str, lang: str, access: str = "keyless",
       note: str = "") -> dict[str, str]:
    """One candidate source: id, what it is, a representative URL on its data host, where, which
    language it publishes in, how it is reached (keyless | key:<ENV> | registration | paid)."""
    return {"id": cid, "name": name, "url": url, "region": region, "language": lang,
            "access": access, "note": note}


#: THE TIER-1 DATA CLASSES. `weight` is the class's weight for the MT5 universe (3 = every tier-1
#: macro/FX shop reads it daily; 1 = a niche input), `mt5` the instruments it informs, `producers`
#: the modules in this tree that ingest it (verified on disk every pass), `extra_hosts` hosts beside
#: the candidates' whose appearance in code evidences the class, `catalogue_terms` a regex for the
#: desk's catalogue rows. PUBLIC knowledge about how the firms work, order-of-magnitude only.
CLASSES: tuple[dict[str, Any], ...] = (
    {"id": "tick_quote_depth", "name": "Tick, quote and depth (L1/L2, spreads, tick volume)",
     "weight": 3, "mt5": ["every MT5 symbol"],
     "tier1": "HRT/Jump/XTX/Citadel: venue ticks and books are the base layer for cost and timing",
     "producers": ["recorders/tick_recorder.py", "recorders/tape_features.py",
                   "recorders/vol_archive.py"],
     "extra_urls": [], "catalogue_terms": r"\btick|quote|spread|depth|tape\b",
     "max_age_h": 6,
     "candidates": [
         _c("dukascopy_ticks", "Dukascopy historical tick bid/ask (FX, metals, CFDs)",
            "https://datafeed.dukascopy.com/datafeed/", "CH/global", "en"),
         _c("truefx_ticks", "TrueFX interbank FX tick history", "https://www.truefx.com/",
            "global", "en", "registration"),
         _c("histdata_ticks", "HistData.com FX tick and M1 archives", "https://www.histdata.com/",
            "global", "en")]},
    {"id": "futures_curves", "name": "Futures curves and term structure (contango, roll yield)",
     "weight": 2, "mt5": ["XTIUSD", "XBRUSD", "XNGUSD", "XAUUSD", "softs", "indices"],
     "tier1": "AHL/Winton/every CTA: curve carry and roll are core trend and carry inputs",
     "owner": "Futures thread", "producers": ["research/fetch_futures_curves.py",
                                              "research/futures_lead_lag.py"],
     "extra_urls": ["www.cmegroup.com", "www.ice.com"],
     "catalogue_terms": r"futures?\b|term structure|curve", "max_age_h": 30,
     "candidates": [
         _c("cme_settlements", "CME Group daily settlements", "https://www.cmegroup.com/",
            "US", "en", note="Futures thread"),
         _c("shfe_daily", "SHFE daily quotes", "https://www.shfe.com.cn/", "CN", "zh",
            note="Futures thread; held route cnx_shfe")]},
    {"id": "options_implied_vol", "name": "Options, implied-vol surfaces, risk reversals, skew",
     "weight": 3, "mt5": ["EURUSD", "USDJPY", "XAUUSD", "US500", "NAS100", "GER40"],
     "tier1": "every macro/FX desk reads 25d risk reversals and ATM vol term structure daily",
     "producers": ["research/options_state.py", "research/options_implied.py",
                   "research/institutional_atlas.py"],
     "extra_urls": ["www.cboe.com", "cdn.cboe.com"],
     "catalogue_terms": r"option|implied vol|risk reversal|skew|\bvix\b", "max_age_h": 30,
     # THE ONLY WIRED PRODUCER IS A PROXY (realized vol from the desk's own bars, 2026-10-29):
     # no implied source is live input, so the class can read PRODUCER at most until one is.
     "coverage_cap": ("PRODUCER", "proxy only: realized-vol PROXY family wired; no implied-vol "
                                  "source is live input (every one IDEAS_ONLY or held)"),
     "candidates": [
         _c("cboe_vix_history", "Cboe VIX/VVIX/SKEW index history", "https://cdn.cboe.com/",
            "US", "en", note="held row cboe_delayed_index_values"),
         _c("eurex_settlement", "Eurex daily settlement prices (index options)",
            "https://www.eurex.com/", "DE", "en/de"),
         _c("cme_option_bulletin", "CME daily bulletin option OI by strike",
            "https://www.cmegroup.com/", "US", "en", note="Futures thread"),
         _c("jpx_options", "JPX Nikkei 225 option statistics", "https://www.jpx.co.jp/",
            "JP", "ja", note="JPX terms bar automated collection (held rows)"),
         _c("minneapolis_fed_mpd", "Minneapolis Fed market-based probabilities (option-implied "
            "distributions: grains, gold, crude, EUR, JPY, S&P 500)",
            "https://www.minneapolisfed.org/banking/current-and-historical-market-based-"
            "probabilities", "US", "en",
            note="IDEAS_ONLY row; parser options_implied.mpd_frame; PROXY family built")]},
    {"id": "positioning", "name": "Positioning (COT, TFF, exchange open interest, broker books)",
     "weight": 2, "mt5": ["FX majors", "XAUUSD", "XAGUSD", "XTIUSD", "indices"],
     "tier1": "CTA and macro desks read speculative positioning weekly as a crowding state",
     "owner": "Futures thread",
     "producers": ["side_channels/fetch_cot.py", "side_channels/cot_miner.py"],
     "extra_urls": ["publicreporting.cftc.gov", "www.cftc.gov"],
     "catalogue_terms": r"\bcot\b|\btff\b|commitments of traders|open interest|positioning",
     "max_age_h": 200,
     "candidates": [
         _c("cftc_tff", "CFTC Traders in Financial Futures (Socrata)",
            "https://publicreporting.cftc.gov/resource/", "US", "en", note="Futures thread"),
         _c("myfxbook_outlook", "Myfxbook community outlook (retail FX positioning)",
            "https://www.myfxbook.com/", "global", "en", "key:MYFXBOOK")]},
    {"id": "fund_flows", "name": "Fund flows (MMF, ETF, cross-border portfolio flows)",
     "weight": 3, "mt5": ["USDJPY", "EURUSD", "US500", "XAUUSD", "AUDUSD"],
     "tier1": "Two Sigma/Millennium read weekly flow data (EPFR-class) as a demand state",
     # the fund-flow doors (MoF weekly, TIC, ECB IVF, Fed Z.1) live in the world dataset hunter
     "producers": ["research/world_dataset_hunter.py"], "extra_urls": [],
     "catalogue_terms": r"fund flow|portfolio flow|\bmmf\b|money market fund|\btic\b|"
                        r"international transactions in securities",
     "max_age_h": 200,
     "candidates": [
         _c("jp_mof_weekly_securities", "Japan MoF weekly international transactions in "
            "securities (foreign buying of JGBs/stocks, Japanese buying abroad)",
            "https://www.mof.go.jp/policy/international_policy/reference/"
            "itn_transactions_in_securities/", "JP", "ja/en"),
         _c("us_tic", "US Treasury TIC monthly cross-border securities flows",
            "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/",
            "US", "en"),
         _c("ici_mmf_weekly", "ICI weekly money market fund assets", "https://www.ici.org/",
            "US", "en"),
         _c("fed_z1", "Federal Reserve Z.1 Financial Accounts (sector flows)",
            "https://www.federalreserve.gov/releases/z1/data/", "US", "en"),
         _c("ecb_ivf", "ECB investment fund statistics",
            "https://data-api.ecb.europa.eu/service/data/IVF/",
            "EA", "en"),
         _c("kr_fss_foreign_flows", "Korea FSS foreign investor net equity purchases",
            "https://www.fss.or.kr/", "KR", "ko")]},
    {"id": "cb_balance_sheets", "name": "Central bank balance sheets and liquidity",
     "weight": 3, "mt5": ["USD crosses", "EURUSD", "USDJPY", "XAUUSD", "US500"],
     "tier1": "macro shops nowcast net liquidity (Fed assets - TGA - RRP) weekly",
     "producers": ["research/alt_proxies.py", "research/shadow_institutional.py"],
     "extra_urls": ["www.federalreserve.gov"],
     "catalogue_terms": r"balance sheet|h\.?4\.?1|total assets|reserves|liquidity",
     "max_age_h": 30,
     "candidates": [
         _c("fed_h41", "Federal Reserve H.4.1 factors affecting reserve balances",
            "https://www.federalreserve.gov/releases/h41/", "US", "en"),
         _c("ecb_wfs", "ECB weekly financial statement / consolidated balance sheet",
            "https://data-api.ecb.europa.eu/", "EA", "en"),
         _c("snb_balance", "SNB balance sheet and sight deposits (weekly)",
            "https://data.snb.ch/", "CH", "de/en/fr"),
         _c("boj_accounts", "BoJ accounts (every 10 days)", "https://www.boj.or.jp/",
            "JP", "ja/en", note="macro_feed:BOJ terms are non-commercial"),
         _c("pboc_balance", "PBOC monetary authority balance sheet", "http://www.pbc.gov.cn/",
            "CN", "zh")]},
    {"id": "cb_operations_money_markets",
     "name": "Central bank operations and money-market rates (repo, RRP, SOFR/ESTR/TONA)",
     "weight": 3, "mt5": ["USD crosses", "EURUSD", "USDJPY", "USDHKD", "USDCNH"],
     "tier1": "funding stress and operation take-up are a daily state at every rates/FX desk",
     "producers": ["research/alt_proxies.py"],
     "extra_urls": ["api.hkma.gov.hk"],
     "catalogue_terms": r"repo|reverse repo|\bsofr\b|\bestr\b|\btona\b|\bhibor\b|interbank",
     "max_age_h": 30,
     "candidates": [
         _c("nyfed_rates", "NY Fed reference rates (SOFR, EFFR, OBFR volumes and percentiles)",
            "https://markets.newyorkfed.org/api/rates/all/latest.json", "US", "en"),
         _c("nyfed_soma", "NY Fed SOMA holdings", "https://markets.newyorkfed.org/api/soma/",
            "US", "en"),
         _c("ecb_estr", "ECB euro short-term rate", "https://data-api.ecb.europa.eu/", "EA",
            "en"),
         _c("hkma_interbank", "HKMA interbank liquidity and HIBOR",
            "https://api.hkma.gov.hk/public/", "HK", "en/zh"),
         _c("chinamoney_shibor", "China Foreign Exchange Trade System SHIBOR / repo fixings",
            "https://www.chinamoney.com.cn/", "CN", "zh")]},
    {"id": "sovereign_auctions", "name": "Sovereign issuance and auction results",
     "weight": 2, "mt5": ["USD crosses", "UST10Y", "GBPUSD", "EURUSD", "USDJPY", "XAUUSD"],
     "tier1": "rates desks trade auction tails and foreign take-up; bill supply drains reserves",
     "producers": ["research/world_dataset_hunter.py", "research/shadow_institutional.py"],
     "extra_urls": [], "catalogue_terms": r"auction|bid.to.cover|issuance|gilt|\bjgb\b",
     "max_age_h": 48,
     "candidates": [
         _c("us_fiscaldata_auctions", "US Treasury auction results (FiscalData auctions_query)",
            "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/"
            "auctions_query", "US", "en"),
         _c("uk_dmo_auctions", "UK DMO gilt auction results", "https://www.dmo.gov.uk/",
            "GB", "en"),
         _c("de_finanzagentur", "Germany Finanzagentur Bund auction results",
            "https://www.deutsche-finanzagentur.de/", "DE", "de/en"),
         _c("jp_mof_jgb_auctions", "Japan MoF JGB auction results", "https://www.mof.go.jp/",
            "JP", "ja/en"),
         _c("fr_aft", "Agence France Tresor OAT auction results", "https://www.aft.gouv.fr/",
            "FR", "fr/en"),
         _c("it_mef", "Italy MEF BTP auction results", "https://www.dt.mef.gov.it/", "IT",
            "it/en")]},
    {"id": "rates_yield_curves", "name": "Government yield curves (daily, par and zero)",
     "weight": 3, "mt5": ["every FX pair", "UST10Y", "indices", "XAUUSD"],
     "tier1": "rate differentials and curve slope are the first macro state every FX model reads",
     "producers": ["scripts/collect_fred_macro.py", "research/world_dataset_hunter.py",
                   "research/carry_state.py"],
     "extra_urls": ["fred.stlouisfed.org"],
     "catalogue_terms": r"yield curve|government bond|treasury yield|par yield|term structure "
                        r"of interest",
     "max_age_h": 48,
     "candidates": [
         _c("ust_par_curve", "US Treasury daily par yield curve (XML/CSV)",
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/",
            "US", "en"),
         _c("ecb_yield_curves", "ECB euro area AAA yield curves (daily)",
            "https://data-api.ecb.europa.eu/", "EA", "en"),
         _c("bundesbank_term_structure", "Bundesbank daily term structure",
            "https://www.bundesbank.de/", "DE", "de/en"),
         _c("jp_mof_jgb_yields", "Japan MoF JGB interest rates (daily CSV)",
            "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/", "JP",
            "ja/en"),
         _c("boc_yields", "Bank of Canada Valet API bond yields",
            "https://www.bankofcanada.ca/valet/", "CA", "en/fr"),
         _c("rba_f2", "RBA F2 capital market yields", "https://www.rba.gov.au/", "AU", "en")]},
    {"id": "macro_nowcasts_vintages", "name": "Macro nowcasts and real-time vintages",
     "weight": 3, "mt5": ["USD crosses", "EURUSD", "US500", "GER40", "XAUUSD"],
     "tier1": "surprise vs the nowcast, on the vintage known at the time, is the macro edge",
     "producers": ["research/fetch_alfred.py", "research/macro_state_engine.py",
                   "research/world_dataset_hunter.py"],
     "extra_urls": ["alfred.stlouisfed.org"],
     "catalogue_terms": r"nowcast|gdpnow|vintage|real.time data|survey of professional",
     "max_age_h": 48,
     "candidates": [
         _c("atlanta_gdpnow", "Atlanta Fed GDPNow", "https://www.atlantafed.org/cqer/research/"
            "gdpnow", "US", "en"),
         _c("nyfed_nowcast", "NY Fed Staff Nowcast (download behind the nowcast page)",
            "https://www.newyorkfed.org/medialibrary/Research/Interactives/Data/NowCast/",
            "US", "en"),
         _c("philly_rtdsm", "Philadelphia Fed Real-Time Data Set for Macroeconomists",
            "https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/",
            "US", "en"),
         _c("cleveland_inflation_nowcast", "Cleveland Fed inflation nowcasting",
            "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting", "US",
            "en"),
         _c("ecb_spf", "ECB Survey of Professional Forecasters",
            "https://data-api.ecb.europa.eu/", "EA", "en"),
         _c("oecd_mei_vintages", "OECD Main Economic Indicators revisions database",
            "https://data-explorer.oecd.org/", "OECD", "en/fr")]},
    {"id": "macro_statistics", "name": "Official macro statistics (national offices, IMF/OECD/BIS)",
     "weight": 2, "mt5": ["every FX pair", "indices"],
     "tier1": "the full statistical world, PIT-stamped, is table stakes",
     "producers": ["research/world_dataset_hunter.py", "scripts/collect_fred_macro.py"],
     "extra_urls": ["api.db.nomics.world", "data.bis.org"],
     "catalogue_terms": r"\bcpi\b|\bgdp\b|unemployment|industrial production|\bpmi\b|retail sales",
     "max_age_h": 48,
     "candidates": [
         _c("dbnomics", "DBnomics (IMF, OECD, BIS, ECB, Eurostat, ~80 providers)",
            "https://api.db.nomics.world/v22", "global", "multi"),
         _c("jp_estat", "Japan e-Stat API", "https://api.e-stat.go.jp/", "JP", "ja",
            "key:ESTAT_APP_ID"),
         _c("us_bls", "US BLS public data API v2", "https://api.bls.gov/publicAPI/v2/", "US",
            "en", "key:BLS_API_KEY"),
         _c("ons_api", "UK ONS beta API", "https://api.beta.ons.gov.uk/v1", "GB", "en"),
         _c("abs_api", "Australian Bureau of Statistics data API", "https://api.data.abs.gov.au/",
            "AU", "en"),
         _c("statcan_wds", "Statistics Canada web data service",
            "https://www150.statcan.gc.ca/t1/wds/rest/", "CA", "en/fr"),
         _c("ibge_sidra", "IBGE SIDRA API (Brazil)", "https://apisidra.ibge.gov.br/", "BR",
            "pt"),
         _c("inegi_bie", "INEGI BIE API (Mexico)", "https://www.inegi.org.mx/", "MX", "es")]},
    {"id": "shipping_ais_ports", "name": "Shipping, AIS and port calls",
     "weight": 2, "mt5": ["AUDUSD", "USDCNH", "XTIUSD", "XBRUSD", "XCUUSD"],
     "tier1": "satellite/AIS vessel counts are a standard physical-flow input at quant macro shops",
     "producers": ["research/alt_proxies.py"],
     "extra_urls": ["services9.arcgis.com"],
     "catalogue_terms": r"\bais\b|port call|vessel|shipping|freight|container|chokepoint",
     "max_age_h": 48,
     "candidates": [
         _c("imf_portwatch", "IMF PortWatch daily port calls and chokepoint transits",
            "https://portwatch.imf.org/", "global", "en"),
         _c("noaa_marinecadastre_ais", "NOAA/BOEM MarineCadastre US AIS archive",
            "https://marinecadastre.gov/ais/", "US", "en"),
         _c("unctad_port_calls", "UNCTADstat port calls and liner connectivity",
            "https://unctadstat.unctad.org/", "global", "en"),
         _c("kr_mof_containers", "Korea MOF container throughput (data.go.kr)",
            "https://apis.data.go.kr/", "KR", "ko"),
         _c("global_fishing_watch", "Global Fishing Watch vessel presence API",
            "https://gateway.api.globalfishingwatch.org/", "global", "en", "registration")]},
    {"id": "satellite_fires_nightlights", "name": "Satellite: fires, night lights, NO2, vegetation",
     "weight": 2, "mt5": ["USDCNH", "AUDUSD", "XCUUSD", "softs", "USDBRL"],
     "tier1": "Orbital Insight/SpaceKnow-class activity panels; free stand-ins are NASA/ESA",
     "producers": ["research/alt_proxies.py"],
     "extra_urls": ["firms.modaps.eosdis.nasa.gov"],
     "catalogue_terms": r"satellite|firms|night.?light|viirs|sentinel|no2|ndvi",
     "max_age_h": 48,
     "candidates": [
         _c("nasa_firms", "NASA FIRMS active fires (area CSV API)",
            "https://firms.modaps.eosdis.nasa.gov/api/", "global", "en", "key:FIRMS_MAP_KEY"),
         _c("nasa_black_marble", "NASA Black Marble VNP46 night lights (LAADS)",
            "https://ladsweb.modaps.eosdis.nasa.gov/", "global", "en", "key:EARTHDATA_TOKEN"),
         _c("copernicus_s5p_no2", "Copernicus Sentinel-5P NO2 (Data Space)",
            "https://dataspace.copernicus.eu/", "EU/global", "en", "registration"),
         _c("modis_ndvi_glam", "NASA GLAM / MODIS crop NDVI", "https://glam1.gsfc.nasa.gov/",
            "global", "en")]},
    {"id": "weather_climate", "name": "Weather, climate indices and degree days",
     "weight": 3, "mt5": ["XNGUSD", "COFFEE", "COCOA", "SUGAR", "WHEAT", "CORN", "SOYBEAN",
                           "AUDUSD"],
     "tier1": "every energy and ags desk trades heating/cooling degree days and ENSO",
     "producers": ["side_channels/weather_miner.py", "research/world_dataset_hunter.py"],
     "extra_urls": ["api.open-meteo.com", "www.nhc.noaa.gov"],
     "catalogue_terms": r"weather|climate|enso|el ni|degree day|precipitation|temperature|"
                        r"drought|oscillation",
     "max_age_h": 48,
     "candidates": [
         _c("noaa_cpc_indices", "NOAA CPC ENSO (ONI), NAO, AO, PNA index tables",
            "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", "US/global", "en"),
         _c("noaa_cpc_degree_days", "NOAA CPC population-weighted daily degree days (CONUS)",
            "https://ftp.cpc.ncep.noaa.gov/htdocs/degree_days/weighted/daily_data/",
            "US", "en"),
         _c("ecmwf_open_data", "ECMWF open data (IFS/AIFS forecasts, CC BY 4.0)",
            "https://data.ecmwf.int/forecasts/", "EU/global", "en"),
         _c("dwd_open_data", "DWD open data (Germany station and forecast data)",
            "https://opendata.dwd.de/", "DE", "de"),
         _c("bom_climate_drivers", "Australian BoM climate driver (ENSO/IOD) updates",
            "http://www.bom.gov.au/climate/enso/", "AU", "en"),
         _c("inmet_brazil", "INMET Brazil station data (coffee/sugar belts)",
            "https://portal.inmet.gov.br/", "BR", "pt"),
         _c("us_drought_monitor", "US Drought Monitor weekly statistics",
            "https://usdmdataservices.unl.edu/api/", "US", "en"),
         _c("open_meteo", "Open-Meteo forecast and archive API", "https://api.open-meteo.com/",
            "global", "en", note="its free tier is for non-commercial use")]},
    {"id": "power_gas_grid", "name": "Power and gas grid data (load, generation, flows, prices)",
     "weight": 2, "mt5": ["XNGUSD", "EURUSD", "GER40", "XTIUSD"],
     "tier1": "European power/gas fundamentals drive TTF/NG and the EUR terms of trade",
     "owner": "unlanded branches claude/entsoe-power, claude/smard-power",
     "producers": ["research/entsoe_power.py", "research/smard_power.py"],
     "extra_urls": ["transparency.entsog.eu", "agsi.gie.eu"],
     "catalogue_terms": r"electricity|power|grid|gas flow|gas storage|load|generation",
     "max_age_h": 48,
     "candidates": [
         _c("entsoe_transparency", "ENTSO-E transparency platform (load, generation, prices)",
            "https://web-api.tp.entsoe.eu/api", "EU", "en", "registration"),
         _c("smard", "SMARD Bundesnetzagentur market data (CC BY 4.0)",
            "https://www.smard.de/app/chart_data/", "DE", "de/en"),
         _c("energy_charts", "Fraunhofer ISE Energy-Charts API",
            "https://api.energy-charts.info/", "DE/EU", "de/en"),
         _c("entsog_flows", "ENTSOG transparency gas flows", "https://transparency.entsog.eu/api/",
            "EU", "en"),
         _c("gie_agsi", "GIE AGSI+ EU gas storage", "https://agsi.gie.eu/api", "EU", "en",
            "registration"),
         _c("elexon_bmrs", "Elexon BMRS / Insights (GB power)", "https://data.elexon.co.uk/",
            "GB", "en")]},
    {"id": "energy_inventories", "name": "Energy inventories, production and refinery runs",
     "weight": 3, "mt5": ["XTIUSD", "XBRUSD", "XNGUSD", "USDCAD", "USDNOK"],
     "tier1": "weekly inventory surprise is the most-traded fundamental print in energy",
     "producers": ["research/world_dataset_hunter.py"],
     "extra_urls": ["ir.eia.gov"],
     "catalogue_terms": r"inventor|crude stock|storage|refiner|rig count|oil stocks",
     "max_age_h": 200,
     "candidates": [
         _c("eia_weekly", "EIA weekly petroleum status and natural gas storage (API v2)",
            "https://api.eia.gov/v2/seriesid/", "US", "en", "key:EIA_API_KEY"),
         _c("jodi_oil", "JODI-Oil world database (monthly, 100+ countries)",
            "https://www.jodidata.org/", "global", "en"),
         _c("baker_hughes_rigs", "Baker Hughes rig count", "https://rigcount.bakerhughes.com/",
            "global", "en"),
         _c("jp_meti_petroleum", "METI petroleum statistics (Japan)", "https://www.meti.go.jp/",
            "JP", "ja"),
         _c("cer_canada", "Canada Energy Regulator commodity statistics",
            "https://www.cer-rec.gc.ca/", "CA", "en/fr")]},
    {"id": "physical_metals", "name": "Physical metals: premiums, vault and ETF stocks",
     "weight": 2, "mt5": ["XAUUSD", "XAGUSD", "XPTUSD", "XCUUSD"],
     "tier1": "physical premiums and vault flows mark real demand beside paper positioning",
     "owner": "asia-gold worker (Asian physical gold rows); Futures thread (exchange stocks)",
     "producers": ["research/fetch_sge_premium.py"],
     "extra_urls": ["www.sge.com.cn", "en.sge.com.cn"],
     "catalogue_terms": r"vault|premium|etf holdings|bullion|\bgld\b|lbma",
     "max_age_h": 48,
     "candidates": [
         _c("lbma_vault_holdings", "LBMA London vault holdings (monthly)",
            "https://www.lbma.org.uk/prices-and-data/london-vault-data", "GB", "en"),
         _c("spdr_gld_holdings", "SPDR Gold Shares daily holdings archive",
            "https://www.spdrgoldshares.com/", "US", "en"),
         _c("swiss_gold_exports", "Swiss FOCBS gold trade by partner (opendata)",
            "https://www.bazg.admin.ch/", "CH", "de/fr/en"),
         _c("ishares_slv_holdings", "iShares Silver Trust holdings", "https://www.ishares.com/",
            "US", "en")]},
    {"id": "trade_hs_customs", "name": "Trade by HS code and customs",
     "weight": 2, "mt5": ["AUDUSD", "USDCNH", "USDKRW", "USDJPY", "XCUUSD", "XAUUSD"],
     "tier1": "bilateral HS-level flows are a terms-of-trade nowcast for commodity currencies",
     "producers": ["research/shadow_institutional.py", "research/alt_proxies.py"],
     "extra_urls": [], "catalogue_terms": r"\bhs\b|customs|export|import|comtrade|trade",
     "max_age_h": 800,
     "candidates": [
         _c("un_comtrade", "UN Comtrade API (monthly HS flows)",
            "https://comtradeapi.un.org/public/v1/", "global", "en", "key:COMTRADE_API_KEY"),
         _c("us_census_trade", "US Census international trade API",
            "https://api.census.gov/data/timeseries/intltrade/", "US", "en"),
         _c("eurostat_comext", "Eurostat Comext (EU trade by HS)",
            "https://ec.europa.eu/eurostat/api/comext/", "EU", "en/fr/de"),
         _c("jp_customs", "Japan Customs trade statistics", "https://www.customs.go.jp/",
            "JP", "ja/en"),
         _c("cn_gacc", "China GACC customs statistics", "http://www.customs.gov.cn/", "CN",
            "zh"),
         _c("br_comexstat", "Brazil Comex Stat API", "https://api-comexstat.mdic.gov.br/", "BR",
            "pt")]},
    {"id": "retail_web_attention",
     "name": "Retail and web attention (pageviews, search, app ranks)",
     "weight": 2, "mt5": ["XAUUSD", "BTCUSD", "USDTRY", "USDJPY", "US500"],
     "tier1": "attention spikes front-run retail flow; used as a crowding state",
     "producers": ["research/alt_proxies.py", "research/attention_substitutes.py",
                   "research/free_stack_hunter.py"],
     "extra_urls": ["wikimedia.org"],
     "catalogue_terms": r"pageview|wikipedia|search interest|trends|app rank|attention",
     "max_age_h": 48,
     "candidates": [
         _c("wikimedia_pageviews", "Wikimedia pageviews REST API (every language edition)",
            "https://wikimedia.org/api/rest_v1/metrics/pageviews/", "global", "multi"),
         _c("gdelt_doc", "GDELT DOC 2.0 timeline volume", "https://api.gdeltproject.org/api/v2/",
            "global", "multi"),
         _c("naver_datalab", "Naver DataLab search trends API", "https://openapi.naver.com/",
            "KR", "ko", "registration"),
         _c("apple_app_rss", "Apple marketing tools app-rank RSS",
            "https://rss.applemarketingtools.com/", "global", "multi")]},
    {"id": "news_event_calendars",
     "name": "News and event calendars (releases, meetings, auctions)",
     "weight": 3, "mt5": ["every MT5 symbol"],
     "tier1": "event time is the most valuable timestamp a desk owns; every shop keeps a calendar",
     "producers": ["research/news_event_stream.py", "research/event_surprise.py",
                   "research/forced_flow_calendar.py"],
     "extra_urls": ["www.bls.gov", "www.bea.gov"],
     "catalogue_terms": r"calendar|schedule|release date|meeting|event",
     "max_age_h": 30,
     "candidates": [
         _c("fed_fomc_calendar", "Federal Reserve FOMC calendar and statements",
            "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm", "US", "en"),
         _c("bls_schedule", "BLS release schedule", "https://www.bls.gov/schedule/", "US", "en"),
         _c("ecb_calendar", "ECB monetary policy meeting calendar",
            "https://www.ecb.europa.eu/press/calendars/", "EA", "en"),
         _c("gdelt_events", "GDELT 2.0 event export (15-minute files)",
            "http://data.gdeltproject.org/gdeltv2/", "global", "multi"),
         _c("us_treasury_auction_calendar", "TreasuryDirect upcoming auctions",
            "https://www.treasurydirect.gov/auctions/upcoming/", "US", "en")]},
    {"id": "text_sentiment_multilang", "name": "Text sentiment by language (central banks, press)",
     "weight": 2, "mt5": ["USDJPY", "EURUSD", "USDCNH", "USDKRW", "indices"],
     "tier1": "native-language NLP on policy text and press, scored for surprise vs prior text",
     "producers": ["side_channels/bis_speech_tone.py", "side_channels/language_change_miner.py",
                   "side_channels/central_bank_miner.py", "research/cb_tone_screen.py"],
     "extra_urls": ["www.bis.org"],
     "catalogue_terms": r"speech|statement|tone|sentiment|minutes|press conference",
     "max_age_h": 48,
     "candidates": [
         _c("bis_cb_speeches", "BIS central bankers' speeches", "https://www.bis.org/cbspeeches/",
            "global", "en/multi"),
         _c("gdelt_gkg", "GDELT GKG tone by source language", "http://data.gdeltproject.org/"
            "gdeltv2/", "global", "multi"),
         _c("pboc_releases", "PBOC Chinese-language releases", "http://www.pbc.gov.cn/", "CN",
            "zh"),
         _c("bok_releases", "Bank of Korea press releases", "https://www.bok.or.kr/", "KR",
            "ko"),
         _c("banxico_minutes", "Banxico minutes and statements", "https://www.banxico.org.mx/",
            "MX", "es")]},
    {"id": "regulatory_filings", "name": "Regulatory filings and disclosures",
     "weight": 1, "mt5": ["share CFDs (event lane)", "US500", "NAS100"],
     "tier1": "insider and short-position filings as event and breadth inputs",
     "producers": ["research/form4_lane.py"],
     "extra_urls": ["data.sec.gov", "efts.sec.gov"],
     "catalogue_terms": r"filing|edgar|form 4|13f|short position|disclosure",
     "max_age_h": 48,
     "candidates": [
         _c("sec_edgar", "SEC EDGAR submissions and full-text search",
            "https://data.sec.gov/submissions/",
            "US", "en"),
         _c("uk_fca_short_positions", "FCA disclosed net short positions (daily)",
            "https://www.fca.org.uk/markets/short-selling/notification-disclosure-net-short-"
            "positions", "GB", "en"),
         _c("esma_registers", "ESMA registers (FIRDS, short-selling)",
            "https://registers.esma.europa.eu/", "EU", "en"),
         _c("hkex_di", "HKEX disclosure of interests", "https://di.hkex.com.hk/", "HK",
            "en/zh")]},
    {"id": "payments_mobility", "name": "Payments, card spend and mobility",
     "weight": 2, "mt5": ["US500", "USDJPY", "USDKRW", "USDCNH", "USDBRL"],
     "tier1": "card-panel and mobility nowcasts of consumption (Second Measure-class)",
     "producers": ["research/alt_proxies.py"],
     "extra_urls": ["www.tsa.gov"],
     "catalogue_terms": r"card|payment|spend|mobility|throughput|footfall|subway",
     "max_age_h": 48,
     "candidates": [
         _c("tsa_throughput", "TSA checkpoint throughput", "https://www.tsa.gov/travel/"
            "passenger-volumes", "US", "en"),
         _c("opportunity_insights", "Opportunity Insights economic tracker",
            "https://github.com/OpportunityInsights/EconomicTracker", "US", "en"),
         _c("ons_realtime", "ONS real-time indicators (card spend, footfall)",
            "https://www.ons.gov.uk/economy/economicoutputandproductivity/output/datasets/"
            "economicactivityandsocialchangeintheukrealtimeindicators", "GB", "en"),
         _c("bcb_pix", "BCB PIX statistics (Brazil)", "https://dadosabertos.bcb.gov.br/",
            "BR", "pt"),
         _c("npci_upi", "NPCI UPI monthly statistics", "https://www.npci.org.in/", "IN", "en")]},
    {"id": "agri_supply", "name": "Agricultural supply (crop progress, WASDE, export sales)",
     "weight": 2, "mt5": ["WHEAT", "CORN", "SOYBEAN", "SUGAR", "COFFEE", "COCOA", "COTTON"],
     "tier1": "every ags desk trades crop progress and WASDE surprises",
     "producers": ["research/world_dataset_hunter.py"],
     "extra_urls": ["apps.fas.usda.gov", "www.nass.usda.gov"],
     "catalogue_terms": r"crop|wasde|harvest|export sales|usda|conab",
     "max_age_h": 200,
     "candidates": [
         _c("usda_nass_quickstats", "USDA NASS Quick Stats API (crop progress)",
            "https://quickstats.nass.usda.gov/api/", "US", "en", "key:NASS_API_KEY"),
         _c("usda_fas_esr", "USDA FAS export sales reporting API",
            "https://apps.fas.usda.gov/OpenData/", "US", "en"),
         _c("usda_wasde", "USDA WASDE monthly (as-reported report data files)",
            "https://www.usda.gov/sites/default/files/documents/oce-wasde-report-data-",
            "US", "en"),
         _c("conab_brazil", "CONAB crop survey (Brazil)", "https://www.conab.gov.br/", "BR",
            "pt"),
         _c("ico_coffee", "International Coffee Organization statistics",
            "https://www.ico.org/", "global", "en")]},
    {"id": "crypto_cfd_reference", "name": "Crypto reference data for MT5 crypto CFDs only",
     "weight": 1, "mt5": ["BTCUSD", "ETHUSD"],
     "tier1": "on-chain and fund-flow state as an input to the CFD, never a hunted venue",
     "producers": [], "extra_urls": [],
     "catalogue_terms": r"bitcoin|on.chain|hash rate|stablecoin",
     "max_age_h": 48,
     "candidates": [
         _c("sec_etf_flows", "SEC EDGAR spot-ETF share counts (N-CEN/424B filings)",
            "https://data.sec.gov/", "US", "en")]},
)


# ------------------------------------------------------------------------------- reading ----
def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


_URL = re.compile(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})(/[^\s\"'<>)\]}]*)?")


def norm_url(host: str, path: str = "") -> str:
    """host (lower, `www.` dropped) + path (no query, no trailing slash): the prefix form."""
    h = host.lower()
    h = h[4:] if h.startswith("www.") else h
    return h + (path or "").split("?")[0].split("#")[0].rstrip("/")


def code_hosts(root: Path = ROOT, dirs: Iterable[str] = SCAN_DIRS) -> dict[str, set[str]]:
    """normalised URL (host + path) -> the non-test files whose text carries it."""
    idx: dict[str, set[str]] = defaultdict(set)
    for d in dirs:
        base = root / d
        if not base.exists():
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = [x for x in dn if x not in ("tests", "__pycache__", ".pt", "fixtures")]
            for f in fn:
                if not f.endswith(".py"):
                    continue
                p = Path(dp) / f
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                rel = p.relative_to(root).as_posix()
                for h, path in set(_URL.findall(_JOIN.sub("", text))):
                    idx[norm_url(h, path)].add(rel)
    return idx


def is_catalogue(rel: str) -> bool:
    return bool(_CATALOGUE_RX.search(rel))


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _prefix(url: str) -> tuple[str, bool]:
    """(normalised prefix, whether it names a PATH). A bare host proves nothing about which of
    the publisher's datasets a file reads, so it is matched only as HOST_ONLY evidence."""
    try:
        u = urlparse(url if "://" in url else "https://" + url)
    except ValueError:
        return "", False
    pref = norm_url(u.hostname or "", u.path)
    return pref, bool((u.path or "").strip("/"))


def url_files(url: str, idx: dict[str, set[str]]) -> tuple[set[str], set[str]]:
    """(files carrying a URL under this exact data path, files naming only its host)."""
    pref, has_path = _prefix(url)
    host = pref.split("/", 1)[0]
    exact: set[str] = set()
    host_only: set[str] = set()
    if not host:
        return exact, host_only
    for k, files in idx.items():
        kh = k.split("/", 1)[0]
        if not (kh == host or kh.endswith("." + host)):
            continue
        if has_path and (k == pref or k.startswith(pref + "/") or k.startswith(pref)):
            exact |= files
        else:
            host_only |= files
    return exact, host_only - exact


def hourly_legs(path: Path = HOURLY) -> dict[str, str]:
    """module path (relative to desks/mt5) -> hourly leg name, from the cycle's own calls."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return {mod: leg for leg, mod in
            re.findall(r'_producer\(\s*"([A-Za-z0-9_]+)",\s*"([^"]+\.py)"', text)}


def clock_texts(root: Path = ROOT) -> dict[str, str]:
    out: dict[str, str] = {}
    for pat in CLOCK_FILES:
        for p in root.glob(pat):
            try:
                out[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8",
                                                                  errors="ignore")
            except OSError:
                continue
    return out


def runtime_rows(path: Path = RUNTIME_STATE) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """organ name -> attestation row, and the attestation's host stamp."""
    doc = _read_json(path)
    if not isinstance(doc, dict):
        return {}, {"state": UNMEASURED, "why": f"{path.name} unreadable or absent"}
    rows = {str(r.get("organ")): r for r in doc.get("organs") or [] if isinstance(r, dict)}
    raw_host = doc.get("host")
    host: dict[str, Any] = raw_host if isinstance(raw_host, dict) else {}
    return rows, {"generated_at": doc.get("generated_at"), "hostname": host.get("hostname"),
                  "role": host.get("role")}


def tracked_files(root: Path = ROOT) -> set[str] | None:
    """Git-tracked paths under the desk reports/data (a tracked copy's mtime is checkout time)."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "desks/mt5/reports",
                              "desks/mt5/data", "docs/research"], capture_output=True,
                             text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return set(out.stdout.splitlines()) if out.returncode == 0 else None


def artifact_age(rel: str, now: datetime, *, root: Path = ROOT,
                 tracked: set[str] | None = None) -> dict[str, Any]:
    """Age of one artifact on THIS host, from its own timestamp; UNMEASURED when it cannot say."""
    p = root / rel
    if not rel or not p.exists():
        return {"artifact": rel or None, "present": False, "age_h": UNMEASURED,
                "basis": "absent on this host"}
    when = None
    basis = ""
    if p.suffix == ".json" and p.stat().st_size < 64 * 1024 * 1024:
        doc = _read_json(p)
        if isinstance(doc, dict):
            for k in TS_KEYS:
                when = _parse_ts(doc.get(k))
                if when:
                    basis = f"in-file {k}"
                    break
    if when is None:
        if tracked is not None and rel in tracked:
            return {"artifact": rel, "present": True, "age_h": UNMEASURED,
                    "basis": "tracked copy with no in-file timestamp: its mtime is checkout time"}
        when = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
        basis = "file mtime (untracked, written on this host)"
    return {"artifact": rel, "present": True,
            "age_h": round(max(0.0, (now - when).total_seconds()) / 3600.0, 1), "basis": basis}


def catalogue_rows() -> dict[str, list[str]]:
    """Names in the desk's own dataset catalogues, by catalogue (absent -> not listed)."""
    out: dict[str, list[str]] = {}
    cat = _read_json(WORLD_CATALOG)
    if isinstance(cat, dict) and isinstance(cat.get("datasets"), dict):
        out["world_datasets/catalog.json"] = [
            f"{k} {v.get('name') or ''}" for k, v in cat["datasets"].items()
            if isinstance(v, dict)]
    reg = _read_json(REGISTRY)
    if isinstance(reg, dict) and isinstance(reg.get("datasets"), dict):
        out["data_registry.json"] = [f"{k} {(v or {}).get('source') or ''} "
                                     f"{(v or {}).get('notes') or ''}"
                                     for k, v in reg["datasets"].items()]
    fs = _read_json(FREE_STACK)
    if isinstance(fs, dict) and isinstance(fs.get("sources"), list):
        out["free_stack_sources.json"] = [f"{r.get('id')} {r.get('name') or ''}"
                                          for r in fs["sources"] if isinstance(r, dict)]
    return out


# ------------------------------------------------------------------------------- terms ----
def terms_of(url: str) -> dict[str, Any]:
    """The ONE register's answer for a candidate URL. No row, an unread row, or an unreadable
    register is TERMS_UNMEASURED; only a row quoting a clause with a permitting status is OK."""
    try:
        from libs.data import terms_fence as tf
    except Exception as exc:                                   # pragma: no cover - import guard
        return {"policy_row": None, "status": UNMEASURED, "terms_state": UNMEASURED,
                "live_basis": TERMS_UNMEASURED, "why": f"register unreadable: {exc}"}
    key = tf.source_of_url(url)
    if not key:
        return {"policy_row": None, "status": "UNLISTED", "terms_state": tf.UNREAD,
                "live_basis": TERMS_UNMEASURED,
                "why": "no SOURCE_POLICY row: ideas only until its own terms are quoted"}
    st = tf.live_input_status(key)
    ts = tf.terms_state(key)
    row = tf.SOURCE_POLICY.get(key) or {}
    if st in (tf.IDEAS_ONLY, tf.METHOD_BLOCKED) or row.get("held_route"):
        basis = "REFUSED"
    elif ts != "READ":
        basis = TERMS_UNMEASURED
    elif st == tf.NEEDS_KEY:
        basis = "NEEDS_KEY"
    elif st in (tf.API_PERMITTED, tf.PUBLIC_PAGE):
        basis = "OK"
    else:
        basis = TERMS_UNMEASURED
    return {"policy_row": key, "status": st, "terms_state": ts, "live_basis": basis,
            "terms_url": (row.get("terms") or {}).get("url")}


# ------------------------------------------------------------------------------- one row ----
def _key_present(access: str) -> bool | None:
    if not access.startswith("key:"):
        return None
    return bool(os.environ.get(access.split(":", 1)[1]))


def measure_class(spec: dict[str, Any], *, idx: dict[str, set[str]], legs: dict[str, str],
                  clocks: dict[str, str], runtime: dict[str, dict[str, Any]],
                  catalogues: dict[str, list[str]], now: datetime,
                  tracked: set[str] | None, root: Path = ROOT) -> dict[str, Any]:
    unmeasured: list[str] = []
    producers = []
    for mod in spec.get("producers") or []:
        path = next((b / mod for b in (root / "desks" / "mt5", root) if (b / mod).exists()),
                    root / "desks" / "mt5" / mod)
        exists = path.exists()
        leg = legs.get(mod)
        clock = f"hourly_cycle:{leg}" if leg else None
        if exists and not clock:
            base = Path(mod).name
            hit = next((f for f, t in clocks.items() if base in t), None)
            clock = f"named in {hit}" if hit else None
        shown = path.relative_to(root).as_posix() if path.is_relative_to(root) else mod
        row: dict[str, Any] = {"module": shown,
                               "exists": exists, "clock": clock or ("UNWIRED" if exists
                                                                     else "ABSENT")}
        if exists:
            att = runtime.get(f"leg:{leg}") if leg else None
            att = att or runtime.get(f"executable:desks/mt5/{mod}")
            art = str((att or {}).get("artifact") or "")
            if art:
                row["attested"] = {"state": (att or {}).get("state"), "artifact": art}
                fr = artifact_age(art, now, root=root, tracked=tracked)
                row["freshness"] = fr
                if fr["age_h"] == UNMEASURED:
                    unmeasured.append(f"{spec['id']}: {art} freshness ({fr['basis']})")
            else:
                row["freshness"] = {"age_h": UNMEASURED,
                                    "basis": "no artifact declared for it in runtime_state.json"}
                unmeasured.append(f"{spec['id']}: {mod} has no declared artifact")
        producers.append(row)

    urls = [c["url"] for c in spec["candidates"]] + list(spec.get("extra_urls") or [])
    fetchers: set[str] = set()
    catalogued: set[str] = set()
    for u in urls:
        exact, host_only = url_files(u, idx)
        for f in exact:
            (catalogued if is_catalogue(f) else fetchers).add(f)
        catalogued |= host_only
    rx = re.compile(spec["catalogue_terms"], re.I)
    cat_hits: dict[str, Any] = {name: sum(1 for r in rows if rx.search(r))
                                for name, rows in catalogues.items()}
    for name in ("world_datasets/catalog.json",):
        if name not in catalogues:
            cat_hits[name] = UNMEASURED
            unmeasured.append(f"{spec['id']}: {name} absent on this host (box store)")

    cands = []
    open_lawful = 0
    for c in spec["candidates"]:
        h = _host(c["url"])
        exact, host_only = url_files(c["url"], idx)
        fetch_files = sorted(f for f in exact if not is_catalogue(f))
        named = sorted(host_only | {f for f in exact if is_catalogue(f)})
        terms = terms_of(c["url"])
        ingested = bool(fetch_files)
        row = {**{k: v for k, v in c.items() if v}, "host": h, "ingested": ingested,
               "fetched_by": fetch_files[:6], "host_named_by": named[:6],
               "evidence": ("DATA_PATH_IN_FETCHER" if ingested else
                            "HOST_NAMED_ONLY" if named else "ABSENT"),
               "terms": terms}
        kp = _key_present(c["access"])
        if kp is not None:
            row["key_present_here"] = kp
        lawful_free = c["access"] != "paid" and terms["live_basis"] != "REFUSED"
        if not ingested and lawful_free:
            open_lawful += 1
        if terms["live_basis"] == TERMS_UNMEASURED:
            unmeasured.append(f"{spec['id']}: {c['id']} terms ({h})")
        cands.append(row)

    live = [p for p in producers if p["exists"] and p["clock"] not in ("UNWIRED", "ABSENT")]
    if live:
        ages = [p.get("freshness", {}).get("age_h") for p in live]
        known = [a for a in ages if isinstance(a, (int, float))]
        limit = float(spec.get("max_age_h") or FRESH_DEFAULT_H)
        if known and min(known) <= limit:
            level = "WIRED_FRESH"
        elif known:
            level = "WIRED_STALE"
        else:
            level = "WIRED"
    elif any(p["exists"] for p in producers) or fetchers:
        level = "PRODUCER"
    elif catalogued or any(isinstance(v, int) and v for v in cat_hits.values()):
        level = "CATALOGUED"
    else:
        level = "NONE"
    cap = spec.get("coverage_cap")
    capped = None
    if cap and COVERAGE[level] > COVERAGE[cap[0]]:
        capped = {"from": level, "to": cap[0], "why": cap[1]}
        level = cap[0]
    cov = COVERAGE[level]
    score = round(float(spec["weight"]) * (1.0 - cov) * (1.0 + math.log1p(open_lawful)), 3)
    return {
        "id": spec["id"], "name": spec["name"], "weight": spec["weight"], "mt5": spec["mt5"],
        "tier1_use": spec["tier1"], "owner": spec.get("owner") or "unowned",
        "coverage": level, "coverage_value": cov, "coverage_capped": capped,
        "freshness_limit_h": spec.get("max_age_h") or FRESH_DEFAULT_H,
        "producers": producers,
        "hosts_in_code": {"fetchers": sorted(fetchers)[:12], "catalogues": sorted(catalogued)[:12],
                          "n_fetchers": len(fetchers), "n_catalogues": len(catalogued)},
        "catalogue_rows": cat_hits,
        "candidates": cands, "open_lawful_candidates": open_lawful,
        "gap_score": score, "unmeasured": unmeasured,
    }


def build(now: datetime | None = None, *, root: Path = ROOT,
          classes: Iterable[dict[str, Any]] = CLASSES) -> dict[str, Any]:
    now = now or _now()
    idx = code_hosts(root)
    legs = hourly_legs(HOURLY)
    clocks = clock_texts(root)
    runtime, att_host = runtime_rows(RUNTIME_STATE)
    catalogues = catalogue_rows()
    tracked = tracked_files(root)
    rows = [measure_class(c, idx=idx, legs=legs, clocks=clocks, runtime=runtime,
                          catalogues=catalogues, now=now, tracked=tracked, root=root)
            for c in classes]
    rows.sort(key=lambda r: (-r["gap_score"], -r["weight"], r["id"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    by_cov: dict[str, int] = defaultdict(int)
    for r in rows:
        by_cov[r["coverage"]] += 1
    opens = []
    for r in rows:
        for c in r["candidates"]:
            if not c["ingested"] and c["terms"]["live_basis"] in ("OK", "NEEDS_KEY"):
                opens.append({"class": r["id"], "rank": r["rank"], "id": c["id"],
                              "url": c["url"], "live_basis": c["terms"]["live_basis"],
                              "policy_row": c["terms"]["policy_row"]})
    unmeasured = [u for r in rows for u in r["unmeasured"]]
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "organ": "desks/mt5/research/data_class_gap.py",
        "leg": "hourly_cycle:data_class_gap",
        "rule": ("report-only; coverage is measured from producers, clocks, artifacts and "
                 "catalogues on this host; absence is UNMEASURED, never 0; terms come from "
                 "libs/data/terms_fence.SOURCE_POLICY only and a source with no quoted clause "
                 "is TERMS_UNMEASURED, never OK"),
        "scoring": {"formula": "weight * (1 - coverage) * (1 + ln(1 + open_lawful_candidates))",
                    "coverage_ladder": COVERAGE},
        "attestation": att_host,
        "keys_present_here": {k: bool(os.environ.get(k)) for k in BOX_KEYS},
        "summary": {"classes": len(rows), "by_coverage": dict(by_cov),
                    "classes_wired": sum(1 for r in rows if r["coverage"].startswith("WIRED")),
                    "classes_fresh": by_cov.get("WIRED_FRESH", 0),
                    "candidates": sum(len(r["candidates"]) for r in rows),
                    "candidates_ingested": sum(1 for r in rows for c in r["candidates"]
                                               if c["ingested"]),
                    "candidates_terms_ok": sum(1 for r in rows for c in r["candidates"]
                                               if c["terms"]["live_basis"] == "OK"),
                    "candidates_terms_unmeasured": sum(
                        1 for r in rows for c in r["candidates"]
                        if c["terms"]["live_basis"] == TERMS_UNMEASURED),
                    "unmeasured_items": len(unmeasured)},
        "top_open_with_terms_basis": opens[:25],
        "classes": rows,
        "unmeasured": unmeasured,
    }


def render_md(doc: dict[str, Any], top: int = 15) -> str:
    s = doc["summary"]
    out = [f"# Tier-1 data-class gap list ({doc['generated_at'][:10]})", "",
           f"Generated by `{doc['organ']}` (leg `{doc['leg']}`) at {doc['generated_at']}. "
           f"Machine copy: `desks/mt5/reports/DATA_CLASS_GAP.json`, regenerated hourly.", "",
           f"Rule: {doc['rule']}.", "",
           f"Score: `{doc['scoring']['formula']}`; coverage ladder "
           + ", ".join(f"{k} {v}" for k, v in doc["scoring"]["coverage_ladder"].items()) + ".", "",
           f"{s['classes']} classes; coverage {dict(s['by_coverage'])}; {s['candidates']} "
           f"candidate sources, {s['candidates_ingested']} ingested, {s['candidates_terms_ok']} "
           f"with a quoted terms basis, {s['candidates_terms_unmeasured']} TERMS_UNMEASURED; "
           f"{s['unmeasured_items']} UNMEASURED items.", "",
           f"## Top {top}", "",
           "| rank | class | weight | coverage | score | owner | producers (clock) | open lawful "
           "candidates (terms) |", "|---|---|---|---|---|---|---|---|"]
    for r in doc["classes"][:top]:
        prods = "; ".join(f"{p['module']} ({p['clock']})" for p in r["producers"]
                          if p["exists"]) or "none"
        opens = "; ".join(f"{c['id']} ({c['terms']['live_basis']})" for c in r["candidates"]
                          if not c["ingested"]) or "none"
        out.append(f"| {r['rank']} | {r['name']} | {r['weight']} | {r['coverage']} | "
                   f"{r['gap_score']} | {r['owner']} | {prods} | {opens} |")
    out += ["", "## Every class", ""]
    for r in doc["classes"]:
        out.append(f"### {r['rank']}. {r['name']} (`{r['id']}`)")
        out.append(f"- Tier-1 use: {r['tier1_use']}. MT5: {', '.join(r['mt5'])}. "
                   f"Owner: {r['owner']}.")
        out.append(f"- Coverage {r['coverage']}, score {r['gap_score']}; fetchers in code "
                   f"{r['hosts_in_code']['n_fetchers']}, catalogue mentions "
                   f"{r['hosts_in_code']['n_catalogues']}; catalogue rows {r['catalogue_rows']}.")
        for p in r["producers"]:
            fr = p.get("freshness") or {}
            art = fr.get("artifact") or (p.get("attested") or {}).get("artifact")
            out.append(f"- Producer `{p['module']}`: {p['clock']}"
                       + (f"; artifact {art} age {fr.get('age_h')} h ({fr.get('basis')})"
                          if p["exists"] else ""))
        for c in r["candidates"]:
            t = c["terms"]
            out.append(f"- {'INGESTED' if c['ingested'] else 'open'}: {c['name']} "
                       f"[{c['region']}, {c['language']}, {c['access']}] {c['url']} -- terms "
                       f"{t['live_basis']} (row {t['policy_row'] or 'none'}, {t['terms_state']})")
        out.append("")
    out += ["## UNMEASURED", ""] + [f"- {u}" for u in doc["unmeasured"]] + [""]
    return "\n".join(out)


def write(doc: dict[str, Any], path: Path = REPORT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--out", default=str(REPORT))
    ap.add_argument("--md", default="", help="also write the human copy to this path")
    ap.add_argument("--json", action="store_true", help="print the document")
    a = ap.parse_args(argv)
    doc = build()
    write(doc, Path(a.out))
    if a.md:
        md = Path(a.md)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(render_md(doc), encoding="utf-8")
    if a.json:
        print(json.dumps(doc, indent=1, ensure_ascii=False))
    else:
        s = doc["summary"]
        top = ", ".join(f"{r['id']}={r['gap_score']}" for r in doc["classes"][:5])
        print(f"data_class_gap: {s['classes']} classes {dict(s['by_coverage'])}; top {top}; "
              f"{s['unmeasured_items']} UNMEASURED -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
