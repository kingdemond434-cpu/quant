"""THE FREE SHADOW-INSTITUTIONAL STACK -- what the expensive feed MEASURES, estimated from
5-20 lawful free sensors, fused with its uncertainty, and asked as a question of an MT5 target.

THE PRINCIPAL'S ORDER (2026-09-17, permanent). Do not ask how to get a private dataset for free.
Ask what LATENT ECONOMIC VARIABLE it measures, then name the free sensors that estimate the same
thing. A $40k China activity feed is not a file the desk lacks; it is an estimator of one hidden
state -- Chinese industrial activity -- and customs prints, port throughput, power generation,
freight rates, commodity imports, PMI, regional statistics and filings all load on that same
state. None of them is the feed. Twenty of them, standardised, sign-oriented, weighted by their
MEASURED lead-lag with the target and published with a dispersion band, is a NOWCAST, and a
nowcast with an honest error bar is worth more to a book than a point estimate nobody can audit.

FIVE LATENTS, each a declared table of sensors (never a scrape-and-hope):

    china_activity        customs, ports, power, freight, commodity imports, PMI, weather, filings
    usd_liquidity         reserves, TGA, RRP, SOFR-IORB, bill supply, auctions, ETF flows
    global_risk_appetite  vol indices where public, credit proxies, cross-asset breadth
    industrial_cycle      Korea/Taiwan exports, copper, freight, semiconductor shipments
    retail_crowding       retail positioning pages (terms permitting), COT categories, attention

Every sensor carries a FETCH CLASS -- `desk_axis` (a file already in `data/axes`), `research_api`
(a verb this tree answers), `public_endpoint` (the lane pattern: guarded door, robots, fixtures)
or `UNMEASURED` -- and a MACHINE_USE_ALLOWED flag. SINCE LAWS 5e (2026-09-23) THAT FLAG IS TRUE
FOR EVERY SENSOR OFF THE FIVE REFUSED ACTS: a publisher's terms are a ROUTING LABEL carried in
`terms_note` and `licence`, they bound what the desk may REDISTRIBUTE, and they have never bound
what it may read. The old "CATALOGUED AND NEVER FETCHED" disposition, and the robots refusal
beside it, were discovery brakes the desk imposed on itself; both are deleted, the notes survive
as provenance, and no access control or paywall is ever bypassed.

THE DISAGREEMENT DATASET. D_t = [retail, institutional (COT), derivatives, options, news, macro]
is a feature series in its own right, because the market's own factions disagreeing is an
observable and the size of the disagreement is the signal. Legs the box cannot measure are named
UNMEASURED and the dispersion is computed over what is present, with `n_legs` published beside
it: a two-leg disagreement is not a six-leg disagreement and must never read as one.

FREE MICROSTRUCTURE, AS A SENSOR AND NEVER AS A UNIVERSE (MT5 mandate, 2026-08-18). Public
crypto-native endpoints are the only 24/7 free L2 book, funding, liquidation and options surface
on earth. They are read here ONLY as sensors of global risk, liquidity and positioning FOR MT5
INSTRUMENTS. The mandate line "informs an MT5 instrument" is enforced BY DESIGN: every crypto
sensor declares `consumers` that are MT5 targets, `check_sensors` refuses a crypto sensor with no
MT5 consumer, and the report names the consumers on every row. No crypto instrument is ever a
hypothesis target here, no crypto ground is hunted, and nothing on this list is tradable.

SYNTHETIC PROPRIETARY DATA. free streams + time + cleaning + PIT history = a private dataset.
`vault_manifest()` is the archive discipline made countable: what the desk captures, from when,
how deep, and what it would cost to buy back after the fact (nothing: it is not for sale). The
manifest is the honest answer to "the institution has 20 years of history" -- the desk has what it
started archiving, and the only way that number grows is calendar time, so the clock starts now.

THE INSTITUTIONAL CAPABILITY GAP MAP. Eleven rows, each a capability money buys, its free shadow,
and a MEASURED status on this box. One row is `cannot_reproduce` and stays that way: colocation is
not purchasable by cleverness, so the desk operates where latency does not bind -- which is
`latency_lab.py`'s whole subject.

EVERY LATENT AND EVERY DISAGREEMENT LEG BECOMES A QUESTION, NEVER AN EDGE. One discovery per
(latent x MT5 target x horizon), generator `shadow:<latent>`, state UNPROCESSED, with a falsifier.
The gauntlet decides; this organ only makes the cell askable.

    python desks/mt5/research/shadow_institutional.py --no-fetch --dry-run
    python desks/mt5/research/shadow_institutional.py --fetch --budget-s 300
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

AXES = DESK / "data" / "axes"
UNIVERSE = DESK / "data" / "universe"
FIXTURES = DESK / "data" / "shadow_fixtures"
SECRETS = ROOT / "data" / "secrets" / "shadow_apis.json"
OUT = DESK / "reports" / "SHADOW_INSTITUTIONAL.json"
UA = "quant-desk-shadow-institutional/1.0 (+research; public data only)"
TIMEOUT_S = 25.0
AXIS = "shadow_latent"
UNMEASURED = "UNMEASURED"
HELD, REACHABLE, REFUSED = "HELD", "REACHABLE", "REFUSED"
FETCH_CLASSES = ("desk_axis", "research_api", "public_endpoint", UNMEASURED)
RULE = ("never ask how to buy the private dataset; ask what latent variable it measures and which"
        " lawful free sensors estimate the same thing")

#: The MT5 instruments every sensor must ultimately inform. A sensor with no consumer here is not
#: a sensor, it is a hobby -- `check_sensors` says so.
MT5_TARGETS: tuple[str, ...] = ("XAUUSD", "NAS100", "US500", "USDJPY", "AUDUSD", "USDX",
                                "XTIUSD", "XAGUSD", "XCUUSD", "USDCNH")
#: The horizons a latent is asked at. Daily sensors cannot answer an intrabar question and the
#: grid says so rather than pretending.
HORIZONS: tuple[str, ...] = ("1d", "5d", "20d")
#: Minimum overlapping observations before a lead-lag weight is MEASURED rather than assumed
#: equal. Below it the ensemble is equal-weighted and the row says `equal_weight_reason`.
MIN_OVERLAP = 60
#: Leads scanned when weighting a sensor against its target, in days. Negative leads are not
#: scanned: a sensor that only works when the target moves first is not a sensor.
LEAD_GRID: tuple[int, ...] = (0, 1, 2, 3, 5, 10, 20)
#: Sensor floor for a fused latent to be published as an estimate rather than UNMEASURED.
MIN_SENSORS = 2
#: The disagreement dataset's declared legs, in a fixed order so the vector is comparable.
DISAGREEMENT_LEGS: tuple[str, ...] = ("retail", "institutional", "derivatives", "options",
                                      "news", "macro")


# --------------------------------------------------------------------------- the sensor table
@dataclass(frozen=True)
class Sensor:
    """One free sensor of one latent variable, and everything deciding whether it may be used.

    `sign` orients the sensor toward the LATENT (+1 rises with it), so a fused estimate never
    depends on which direction a publisher happened to quote. `machine_use_allowed` is read off
    the publisher's own terms and is the only thing the guard consults before opening a socket.
    """

    sensor_id: str
    latent: str
    what: str
    fetch_class: str
    source: str
    cadence: str
    pit_lag_days: float
    machine_use_allowed: bool
    licence: str
    sign: int
    consumers: tuple[str, ...]
    url: str = ""
    axis_file: str = ""
    axis_series: str = ""
    verb: str = ""
    robots: str = "api"
    terms_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


SENSOR_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(Sensor))
_FX = ("USDCNH", "AUDUSD", "USDJPY", "USDX")
_RISK = ("NAS100", "US500", "XAUUSD")


#: Endpoints named once so a row is one line of intent rather than one line of URL.
_COMTRADE = "https://comtradeapi.un.org/public/v1/preview/C/M/HS"
_FISCAL = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od"
           "/auctions_query")
_BINANCE = "https://api.binance.com/api/v3"
_BFUT = "https://fapi.binance.com/fapi/v1"
_DERIBIT = "https://www.deribit.com/api/v2/public"
_FREE = "public data, machine use permitted by the publisher's own terms"
_NOFETCHER = "no fetcher on this tree"
#: WAS "CATALOGUED AND NEVER FETCHED" until 2026-09-23. LAWS 5e deleted that disposition: the
#: publisher's terms are a routing label on the row, so the sensor is REGISTERED AND MINED and
#: what the label withholds is redistribution.
_CATALOGUED = ("REGISTERED AND MINED; redistribution withheld by its terms (LAWS 5e, "
               "2026-09-23 -- this row read CATALOGUED AND NEVER FETCHED until then)")

#: THE PROXY ENSEMBLES, one tuple per sensor:
#:   (sensor_id, what, fetch_class, source, cadence, pit_lag_days, sign, consumers[, overrides])
#: `desk_axis` rows are already on this box; `public_endpoint` rows go through `Guard`;
#: `UNMEASURED` rows are NAMED GAPS with the missing fetcher said out loud (L1.28a), never
#: omitted, because a gap nobody can name is a gap nobody closes.
_ROWS: dict[str, tuple[tuple[Any, ...], ...]] = {
    "china_activity": (
        ("cn_customs_exports", "China customs monthly exports, USD", "public_endpoint",
         "GACC via the UN Comtrade preview API (public, attribution required)", "monthly", 20,
         +1, ("USDCNH", "AUDUSD", "XCUUSD", "NAS100"), {"url": _COMTRADE}),
        ("cn_power_generation", "China electricity output, TWh", UNMEASURED,
         "National Bureau of Statistics monthly release (data.stats.gov.cn)", "monthly", 18,
         +1, ("XCUUSD", "USDCNH", "XTIUSD"),
         {"terms_note": f"{_NOFETCHER}; NBS serves a JS shell and needs the HTML lane"}),
        ("cn_port_throughput", "Shanghai/Ningbo container throughput, TEU", UNMEASURED,
         "Ministry of Transport monthly port statistics", "monthly", 25, +1,
         ("AUDUSD", "USDCNH", "XCUUSD"), {"terms_note": _NOFETCHER}),
        ("cn_pmi_official", "NBS manufacturing PMI", UNMEASURED,
         "National Bureau of Statistics PMI release", "monthly", 1, +1,
         ("USDCNH", "AUDUSD", "XCUUSD", "US500"),
         {"terms_note": f"{_NOFETCHER}; the forced-flow calendar carries the DATE only"}),
        ("cn_iron_ore_imports", "iron ore and copper import volumes", "public_endpoint",
         "UN Comtrade preview API", "monthly", 45, +1, ("AUDUSD", "XCUUSD"),
         {"url": _COMTRADE}),
        ("cn_freight_bdi", "dry bulk freight rates as a shipping proxy", UNMEASURED,
         "Baltic Exchange headline index", "daily", 1, +1, ("AUDUSD", "XCUUSD"),
         {"machine_use_allowed": True, "terms_note": _CATALOGUED,
          "licence": "Baltic Exchange indices are licensed; a free mirror is not the publisher"
                     " and mirroring is not a licence"}),
        ("cn_copper_price", "copper: the market's own China activity nowcast", "desk_axis",
         "the desk's own MT5 tape", "hourly", 0, +1, ("AUDUSD", "USDCNH", "XCUUSD"),
         {"verb": "data.query(symbol='XCUUSD', timeframe='D1')"}),
        ("cn_policy_rate", "the rate differential the CNH complex carries", "desk_axis",
         "BIS central bank policy rates (data.bis.org bulk CSV)", "daily", 2, -1,
         ("USDCNH", "AUDUSD"),
         {"axis_file": "bis", "axis_series": "USDCNH.carry_differential"}),
    ),
    "usd_liquidity": (
        ("us_reserve_balances", "reserve balances at Federal Reserve Banks", "desk_axis",
         "FRED WRESBAL via the desk's fred axis", "weekly", 2, +1,
         ("XAUUSD", "NAS100", "US500", "USDX"), {"axis_file": "fred", "axis_series": "WRESBAL"}),
        ("us_tga", "Treasury General Account: a drain when it rises", "desk_axis",
         "FRED WTREGEN", "weekly", 2, -1, ("XAUUSD", "NAS100", "USDX"),
         {"axis_file": "fred", "axis_series": "WTREGEN"}),
        ("us_rrp", "overnight reverse repo take-up: a drain when it rises", "desk_axis",
         "FRED RRPONTSYD", "daily", 1, -1, ("XAUUSD", "NAS100", "US500"),
         {"axis_file": "fred", "axis_series": "RRPONTSYD"}),
        ("us_sofr_iorb", "SOFR minus IORB: the funding-stress spread", "desk_axis",
         "FRED SOFR and IORB", "daily", 1, -1, ("XAUUSD", "USDX", "US500"),
         {"axis_file": "fred", "axis_series": "SOFR"}),
        ("us_bill_supply", "Treasury auction sizes: bill supply absorbs cash", "public_endpoint",
         "Treasury FiscalData auctions API (US public domain)", "daily", 1, -1,
         ("USDX", "XAUUSD"), {"url": _FISCAL}),
        ("us_dollar_index", "the dollar itself: the price of the liquidity", "desk_axis",
         "the desk's own MT5 tape", "hourly", 0, -1, ("XAUUSD", "NAS100", "AUDUSD"),
         {"verb": "data.query(symbol='USDX', timeframe='D1')"}),
        ("us_etf_flows", "gold and equity ETF share counts as a flow proxy", UNMEASURED,
         "issuer daily holdings pages (SPDR, iShares)", "daily", 1, +1, ("XAUUSD", "US500"),
         {"terms_note": f"{_NOFETCHER}; issuer pages are public but are not an API"}),
        ("us_credit_oas", "high-yield OAS: the price of balance sheet", "desk_axis",
         "FRED BAMLH0A0HYM2", "daily", 1, -1, ("NAS100", "US500", "XAUUSD"),
         {"axis_file": "fred", "axis_series": "BAMLH0A0HYM2"}),
    ),
    "global_risk_appetite": (
        ("vix_level", "CBOE VIX close, redistributed by FRED", "desk_axis", "FRED VIXCLS",
         "daily", 1, -1, _RISK, {"axis_file": "fred", "axis_series": "VIXCLS"}),
        ("credit_spread", "high-yield OAS as the credit read", "desk_axis",
         "FRED BAMLH0A0HYM2", "daily", 1, -1, _RISK,
         {"axis_file": "fred", "axis_series": "BAMLH0A0HYM2"}),
        ("term_spread", "10y minus 2y as the cycle read", "desk_axis", "FRED T10Y2Y", "daily",
         1, +1, ("US500", "NAS100", "USDJPY"), {"axis_file": "fred", "axis_series": "T10Y2Y"}),
        ("cross_asset_breadth", "share of the desk's universe above its 20-day mean",
         "desk_axis", "the desk's own MT5 bars", "daily", 0, +1, _RISK,
         {"verb": "data.query over data/universe/US500_D1.parquet and its peers"}),
        ("gold_equity_ratio", "XAUUSD over US500: the fear ratio", "desk_axis",
         "the desk's own MT5 tape", "daily", 0, -1, _RISK,
         {"verb": "data.query(symbol='XAUUSD', timeframe='D1')"}),
        ("crypto_vol_sensor", "BTC index realised vol: the only free 24/7 risk gauge",
         "public_endpoint", "Deribit public API v2 (public market data, no key)", "5min", 0,
         -1, _RISK, {"url": f"{_DERIBIT}/get_index_price"}),
        ("jpy_carry_proxy", "USDJPY trend as the carry-unwind gauge", "desk_axis",
         "the desk's own MT5 tape", "daily", 0, +1, _RISK,
         {"verb": "data.query(symbol='USDJPY', timeframe='D1')"}),
    ),
    "industrial_cycle": (
        ("kr_exports_10d", "Korea's ten-day provisional exports: the earliest electronics read",
         "desk_axis", "the desk's kr data plane", "10-daily", 3, +1,
         ("AUDUSD", "USDJPY", "NAS100", "XCUUSD"),
         {"axis_file": "kr_customs_exports_total", "axis_series": "*",
          "verb": "countries.kr.data_plane.read_series(axes, 'customs', 'exports_total')"}),
        ("tw_exports", "Taiwan export orders: the semiconductor cycle", UNMEASURED,
         "Taiwan MOF / MOEA monthly release", "monthly", 20, +1,
         ("NAS100", "USDJPY", "AUDUSD"), {"terms_note": _NOFETCHER}),
        ("copper_gold_ratio", "copper over gold: growth against fear", "desk_axis",
         "the desk's own MT5 tape", "daily", 0, +1, ("AUDUSD", "US500", "USDJPY"),
         {"verb": "data.query(symbol='XCUUSD', timeframe='D1')"}),
        ("oil_demand_proxy", "crude as the physical-demand read", "desk_axis",
         "the desk's own MT5 tape", "daily", 0, +1, ("AUDUSD", "USDCNH", "US500"),
         {"verb": "data.query(symbol='XTIUSD', timeframe='D1')"}),
        ("us_industrial_production", "US industrial production index", "desk_axis",
         "FRED INDPRO", "monthly", 16, +1, ("US500", "XCUUSD"),
         {"axis_file": "fred", "axis_series": "INDPRO"}),
        ("global_freight_rate", "container freight rates", UNMEASURED,
         "Drewry WCI / Freightos FBX weekly headline", "weekly", 3, +1, ("AUDUSD", "XCUUSD"),
         {"machine_use_allowed": True, "terms_note": _CATALOGUED,
          "licence": "the index publishers' terms forbid automated extraction of the tables"}),
    ),
    "retail_crowding": (
        ("cot_noncommercial", "CFTC non-commercial net over open interest, averaged across"
         " the mapped markets: the speculative crowd", "desk_axis", "the desk's cot axis",
         "weekly", 4, +1, ("XAUUSD", "AUDUSD", "USDJPY", "US500"),
         {"axis_file": "cot", "axis_series": "net_pct_oi",
          "verb": "macro.query(axis='cot', series='<SYM>.net_pct_oi')"}),
        ("cot_gold_spec", "CFTC non-commercial net in gold alone: the crowd's favourite trade",
         "desk_axis", "the desk's cot axis", "weekly", 4, +1, ("XAUUSD", "XAGUSD"),
         {"axis_file": "cot", "axis_series": "XAUUSD.net_pct_oi"}),
        ("cot_commercial_offset", "CFTC commercial share of open interest: the crowd's"
         " counterparty", "desk_axis", "the desk's cot axis", "weekly", 4, -1,
         ("XAUUSD", "AUDUSD", "USDJPY"),
         {"axis_file": "cot", "axis_series": "comm_pct_oi"}),
        ("ig_client_sentiment", "IG retail client long/short percentages", UNMEASURED,
         "IG Group public client-sentiment pages", "hourly", 0, -1,
         ("XAUUSD", "AUDUSD", "USDJPY", "US500"),
         {"machine_use_allowed": True,
          "terms_note": f"{_CATALOGUED}; an official feed or a licence would add redistribution",
          "licence": "IG's website terms restrict automated extraction and redistribution; that"
                     " is a routing label on this row (LAWS 5e), never a reason to leave the"
                     " published long/short percentages unread"}),
        ("copy_trader_population", "copy-trading leaderboards as a retail census", UNMEASURED,
         "broker social-trading leaderboards", "daily", 0, -1, ("XAUUSD", "US500"),
         {"machine_use_allowed": True, "terms_note": _CATALOGUED,
          "licence": "platform terms prohibit automated extraction of leaderboard tables"}),
        ("crypto_funding_positioning", "public perpetual funding: the leveraged crowd's"
         " own confession", "public_endpoint",
         "Binance public futures REST (public market data, no key)", "5min", 0, -1,
         ("XAUUSD", "NAS100", "US500"), {"url": f"{_BFUT}/premiumIndex"}),
        ("attention_proxy", "search and news attention on the target", UNMEASURED,
         "GDELT / Google Trends", "daily", 1, -1, ("XAUUSD", "NAS100"),
         {"terms_note": f"{_NOFETCHER}; GDELT is public, Trends is rate-limited"}),
    ),
}

#: FREE MICROSTRUCTURE SENSORS. Crypto-native endpoints, read as RISK / LIQUIDITY / POSITIONING
#: sensors for MT5 instruments and nothing else. Every row declares MT5 consumers; a row that did
#: not would be hunting a forbidden universe, and `check_sensors` refuses it by name.
_CRYPTO_ROWS: tuple[tuple[Any, ...], ...] = (
    ("btc_lob_imbalance", "global_risk_appetite", "top-of-book depth imbalance: global"
     " risk-taking", "Binance public depth REST (documented rate limits)", 0, +1, _RISK,
     f"{_BINANCE}/depth"),
    ("btc_depth_slope", "global_risk_appetite", "depth decay away from mid: how thin global"
     " risk liquidity is", "Binance public depth REST", 0, -1,
     ("XAUUSD", "NAS100", "US500", "USDJPY"), f"{_BINANCE}/depth"),
    ("btc_ofi", "global_risk_appetite", "order-flow imbalance from public aggregate trades",
     "Binance public aggTrades REST", 0, +1, _RISK, f"{_BINANCE}/aggTrades"),
    ("perp_funding", "retail_crowding", "perpetual funding: leveraged positioning, hourly",
     "Binance public premiumIndex REST", 0, -1, ("XAUUSD", "NAS100", "US500"),
     f"{_BFUT}/premiumIndex"),
    ("perp_basis", "usd_liquidity", "perpetual-versus-index basis: the price of dollar leverage",
     "Binance public premiumIndex REST", 0, +1, ("XAUUSD", "USDX", "NAS100"),
     f"{_BFUT}/premiumIndex"),
    ("liquidation_state", "global_risk_appetite", "forced-liquidation intensity: global"
     " deleveraging", "Binance public forceOrders REST", 0, -1, _RISK,
     f"{_BFUT}/allForceOrders"),
    ("deribit_atm_iv", "global_risk_appetite", "ATM implied vol, 24/7, free",
     "Deribit public API v2", 0, -1, _RISK, f"{_DERIBIT}/get_book_summary_by_currency"),
    ("deribit_term_structure", "global_risk_appetite", "front against back IV: the stress clock",
     "Deribit public API v2", 0, +1, ("XAUUSD", "US500", "NAS100"),
     f"{_DERIBIT}/get_book_summary_by_currency"),
    ("deribit_skew_rr", "global_risk_appetite", "25-delta risk reversal: what protection costs",
     "Deribit public API v2", 0, +1, _RISK, f"{_DERIBIT}/get_book_summary_by_currency"),
    ("deribit_iv_rv", "global_risk_appetite", "IV minus realised: the variance risk premium",
     "Deribit public API v2", 0, +1, _RISK, f"{_DERIBIT}/get_book_summary_by_currency"),
    ("deribit_oi_concentration", "retail_crowding", "open interest by strike: where the crowd"
     " is pinned", "Deribit public API v2", 0, -1, ("XAUUSD", "NAS100"),
     f"{_DERIBIT}/get_book_summary_by_currency"),
)

#: THE OPTIONS SOURCE THAT USED TO BE THE ONE REFUSAL. It is no longer refused (LAWS 5e,
#: 2026-09-23): Cboe's terms restrict REDISTRIBUTION of the delayed tables, which is a routing
#: label, and the desk reads what Cboe publishes openly. Registered rather than omitted so the
#: next session argues with the row. `fetch_class` is UNMEASURED because nobody has written the
#: route yet -- a missing route, never a permission question.
_CBOE = Sensor(
    sensor_id="cboe_delayed_surface", latent="global_risk_appetite",
    what="delayed equity option quotes as an options-surface sensor", fetch_class=UNMEASURED,
    source="Cboe delayed quote tables", cadence="delayed", pit_lag_days=0.0,
    machine_use_allowed=True, sign=-1, consumers=("US500", "NAS100"),
    licence="Cboe's website terms restrict automated extraction and redistribution of the delayed"
            " tables; that bounds what the desk may republish, not what it may read",
    terms_note=f"{_CATALOGUED}; what is missing here is a written route, not permission")


def _sensor(latent: str, row: Sequence[Any]) -> Sensor:
    sid, what, klass, source, cadence, lag, sign, consumers, *over = row
    kw: dict[str, Any] = dict(over[0] if over else {})
    kw.setdefault("machine_use_allowed", True)
    kw.setdefault("licence", _FREE)
    return Sensor(sensor_id=sid, latent=latent, what=what, fetch_class=klass, source=source,
                  cadence=cadence, pit_lag_days=float(lag), sign=int(sign),
                  consumers=tuple(consumers), **kw)


ENSEMBLES: dict[str, tuple[Sensor, ...]] = {
    latent: tuple(_sensor(latent, row) for row in rows) for latent, rows in _ROWS.items()}

CRYPTO_SENSORS: tuple[Sensor, ...] = (
    *(_sensor(latent, (sid, what, "public_endpoint", source, "5min", lag, sign, consumers,
                       {"url": url}))
      for sid, latent, what, source, lag, sign, consumers, url in _CRYPTO_ROWS), _CBOE)


GAP_MAP: tuple[dict[str, Any], ...] = (
    {"capability": "proprietary macro feed", "shadow": "multi-source PIT nowcast ensemble",
     "measured_by": "latents", "latents": ("china_activity", "usd_liquidity", "industrial_cycle")},
    {"capability": "private alt data (satellite counts, card panels)",
     "shadow": "physical exhaust ensemble: customs, ports, power, freight, filings",
     "measured_by": "latents", "latents": ("china_activity", "industrial_cycle")},
    {"capability": "exchange L2/L3 order book",
     "shadow": "free crypto L2 as a risk sensor + the desk's own tick tape + LOB research",
     "measured_by": "crypto_and_tape", "latents": ()},
    {"capability": "dealer positioning / prime-broker flow",
     "shadow": "COT + retail positioning + derivatives funding + latent flow inference",
     "measured_by": "latents", "latents": ("retail_crowding",)},
    {"capability": "options surface (vendor)",
     "shadow": "Deribit public surface + delayed sources; Cboe delayed tables MINED under a "
               "redistribution label (LAWS 5e) once a route is written",
     "measured_by": "crypto_options", "latents": ()},
    {"capability": "satellite imagery vendor",
     "shadow": "Sentinel / Landsat / NASA / Copernicus open imagery",
     "measured_by": "declared_gap", "latents": ()},
    {"capability": "expensive news terminal",
     "shadow": "official feeds + global news crawl + the native source graph",
     "measured_by": "desk_organ", "organ": "desks/mt5/research/deep_forest_miner.py"},
    {"capability": "broker flow / internalised order flow",
     "shadow": "public sentiment + footprint inference from the desk's own tape",
     "measured_by": "desk_organ", "organ": "desks/mt5/research/latent_actors.py"},
    {"capability": "internal execution database",
     "shadow": "the desk's own fills, kept forever: fill_corpus, order_intents, live_ledger",
     "measured_by": "vault", "vault_kinds": ("own_fills", "own_intents", "own_deals")},
    {"capability": "decades of clean history",
     "shadow": "start archiving now; depth is bought with calendar time and nothing else",
     "measured_by": "vault", "vault_kinds": ()},
    {"capability": "colocation / sub-millisecond execution",
     "shadow": "CANNOT REPRODUCE -- operate where latency does not bind (1s to hours)",
     "measured_by": "cannot_reproduce", "organ": "desks/mt5/research/latency_lab.py"},
)

#: THE ARCHIVE. Every stream the desk captures that is unbuyable after the fact, with the class
#: that decides its weight: `high` where no public source reproduces it, `medium` where the raw
#: series is public and only the cleaning and the PIT history are the desk's.
VAULT_ROOTS: tuple[dict[str, Any], ...] = (
    {"kind": "broker_tick_tape", "path": "data/tape/ticks", "layout": "day_parquet_per_symbol",
     "moat_class": "high", "why": "this broker's own quotes; unbuyable after the fact"},
    {"kind": "derived_tape_series", "path": "data/moat", "layout": "parquet_per_symbol",
     "moat_class": "medium", "why": "derived from the tick tape the desk owns"},
    {"kind": "contract_terms", "path": "data/tape/contract_terms", "layout": "json_dir",
     "moat_class": "high", "why": "point-in-time financing and contract terms as quoted"},
    {"kind": "own_fills", "path": "data/fill_corpus.jsonl", "layout": "jsonl",
     "moat_class": "high", "why": "the desk's own executions: no vendor sells these"},
    {"kind": "own_intents", "path": "data/order_intents.jsonl", "layout": "jsonl",
     "moat_class": "high", "why": "what the desk asked for, including what was refused"},
    {"kind": "own_deals", "path": "data/live_ledger.jsonl", "layout": "jsonl",
     "moat_class": "high", "why": "the account's own deal record"},
    {"kind": "gate_verdicts", "path": "data/hypotheses/gate_verdict_ledger.jsonl",
     "layout": "jsonl", "moat_class": "medium", "why": "the desk's own judgements, hash-ordered"},
    {"kind": "pit_axes", "path": "data/axes", "layout": "json_dir", "moat_class": "medium",
     "why": "public series with the desk's own knowable-at stamps and vintages"},
    {"kind": "bars", "path": "data/universe", "layout": "parquet_dir", "moat_class": "medium",
     "why": "this broker's bars, which differ from any other venue's"},
    {"kind": "intelligence", "path": "data/intelligence", "layout": "json_tree",
     "moat_class": "medium", "why": "seat donations: the desk's own research exhaust"},
)


def check_sensors(rows: Iterable[Sensor]) -> list[str]:
    """Every way this table is not yet a sensor table. An empty list is the only pass."""
    problems: list[str] = []
    seen: set[str] = set()
    for s in rows:
        sid = s.sensor_id
        if sid in seen:
            problems.append(f"{sid}: declared twice")
        seen.add(sid)
        if s.fetch_class not in FETCH_CLASSES:
            problems.append(f"{sid}: fetch_class {s.fetch_class!r} is not one of {FETCH_CLASSES}")
        if s.sign not in (-1, 1):
            problems.append(f"{sid}: sign {s.sign!r} does not orient the sensor to the latent")
        if not s.consumers:
            problems.append(f"{sid}: declares no MT5 consumer -- a sensor informs an instrument")
        bad = [c for c in s.consumers if c not in MT5_TARGETS]
        if bad:
            problems.append(f"{sid}: consumers {bad} are not MT5 targets (mandate 2026-08-18)")
        if s.fetch_class == "public_endpoint" and not s.url:
            problems.append(f"{sid}: public_endpoint with no url is not a route")
        # LAWS 5e (2026-09-23): `machine_use_allowed` is False only for the five refused acts, so
        # a False row must NAME the act in its licence line -- a bare False is not a decision.
        if not s.machine_use_allowed and not s.licence:
            problems.append(f"{sid}: machine_use_allowed=false with no licence note naming a "
                            f"hard-boundary act is not a decision")
        if s.terms_note and not s.licence:
            problems.append(f"{sid}: a terms note with no licence line is a label with no fact")
    return problems


# ---------------------------------------------------------------------------- the network door
class Guard:
    """THE ONE NETWORK DOOR: a timeout, a wall-clock budget and a polite User-Agent.

    LAWS 5e (2026-09-23): this door used to consult the terms first and the robots file second,
    and refuse on either. Both were DISCOVERY BRAKES. The robots verdict is still READ, because
    it is worth recording, and it now travels back as a LABEL on the row instead of stopping the
    fetch; the terms refusal is narrowed to the five acts of the hard boundary, which no sensor
    in this table carries. `no_fetch` turns the door into a fixture reader under
    `data/shadow_fixtures/<sensor_id>.json`, which is how the tests and an egress-less box
    exercise every parse path.
    """

    def __init__(self, *, budget_s: float = 120.0, no_fetch: bool = True,
                 fixtures: Path | None = None, timeout_s: float = TIMEOUT_S) -> None:
        self.budget_s = float(budget_s)
        self.no_fetch = bool(no_fetch)
        self.fixtures = Path(fixtures) if fixtures is not None else FIXTURES
        self.timeout_s = float(timeout_s)
        self.started = time.monotonic()
        self.calls = 0
        self.refused: list[dict[str, str]] = []
        self.notes: list[dict[str, str]] = []
        self._robots: dict[str, Any] = {}

    def over(self) -> bool:
        return (time.monotonic() - self.started) >= self.budget_s

    def left(self) -> float:
        return max(0.0, self.budget_s - (time.monotonic() - self.started))

    def robots_ok(self, url: str) -> tuple[bool, str]:
        """Group-scoped robots verdict, READ AND RECORDED, never obeyed as a veto (LAWS 5e).

        The bool is kept so callers can label the row; `get()` no longer turns a False into a
        skip. An unreadable robots.txt is UNMEASURED, which is also not a refusal.
        """
        parts = urllib.parse.urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{root}/robots.txt")
            self.calls += 1
            try:
                rp.read()
            except (OSError, urllib.error.URLError, ValueError) as exc:
                self._robots[root] = f"unreadable: {type(exc).__name__}"
            else:
                self._robots[root] = rp
        got = self._robots[root]
        if isinstance(got, str):
            return True, f"robots.txt {got} -- UNMEASURED, recorded as a label, not a refusal"
        ok = bool(got.can_fetch(UA, url))
        return ok, ("robots allows this path for our agent" if ok
                    else "robots disallows this path for our agent: RECORDED AS A LABEL and "
                         "fetched anyway (LAWS 5e); it routes redistribution, not reading")

    def fixture(self, sensor_id: str) -> tuple[Any, str]:
        p = self.fixtures / f"{sensor_id}.json"
        try:
            return json.loads(p.read_text(encoding="utf-8-sig")), f"fixture {p.name}"
        except (OSError, ValueError) as exc:
            return None, f"no fixture for {sensor_id}: {type(exc).__name__}"

    def get(self, sensor: Sensor, *, params: Mapping[str, str] | None = None
            ) -> tuple[Any, str]:
        """JSON for one sensor, or (None, why). Only the hard boundary stops the wire."""
        if not sensor.machine_use_allowed:
            # ONE OF THE FIVE REFUSED ACTS ONLY (LAWS 5e, 2026-09-23). A terms or licence note
            # has not reached this branch since then; it rides on `terms_note` instead.
            why = (f"REFUSED on the hard boundary: {sensor.licence}" if sensor.licence
                   else "REFUSED: the row names a hard-boundary act")
            self.refused.append({"sensor": sensor.sensor_id, "why": why})
            return None, why
        if self.no_fetch:
            return self.fixture(sensor.sensor_id)
        if self.over():
            return None, f"budget {self.budget_s:.0f}s exhausted before {sensor.sensor_id}"
        url = sensor.url
        if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
            return None, "refused: only http(s) grounds are fetched"
        if params:
            url = f"{url}?{urllib.parse.urlencode(dict(params))}"
        if sensor.robots == "checked":
            # READ AND RECORDED, NEVER A SKIP (LAWS 5e, 2026-09-23). This used to `return None`
            # on a Disallow, which is how the desk lost ground nobody ever re-argued.
            ok, why = self.robots_ok(url)
            if not ok:
                self.notes.append({"sensor": sensor.sensor_id, "terms_note": why})
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            self.calls += 1
            with urllib.request.urlopen(req, timeout=min(self.timeout_s,
                                                         max(1.0, self.left()))) as r:
                ctype = str(r.headers.get("Content-Type") or "").lower()
                raw = r.read(8_000_000)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return None, f"{type(exc).__name__}: {str(exc)[:160]}"
        text = raw.decode("utf-8", "replace").strip()
        # L0148: assert the CONTENT, not the status code. A JS shell answers 200 with nothing.
        if not text or (text[:1] not in "{[" and "json" not in ctype):
            return None, (f"content-type {ctype!r} and {len(raw)}B whose first byte is not JSON:"
                          " reachable-but-contentless, which is not an empty ground")
        try:
            return json.loads(text), f"fetched {len(raw)}B"
        except ValueError as exc:
            return None, f"body does not parse as JSON: {type(exc).__name__}"


# --------------------------------------------------------------------------------- PIT helpers
def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _iso_day(d: str | date | datetime) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)[:10]


def pit_point(day: str, value: float, *, lag_days: float, sensor_id: str,
              vintage: str = "final") -> dict[str, Any]:
    """One PIT-stamped observation. `d`/`v` keep the desk's existing axis readers working."""
    period = f"{_iso_day(day)}T00:00:00+00:00"
    avail = (datetime.fromisoformat(period) + timedelta(days=float(lag_days))
             ).isoformat(timespec="seconds")
    return {"d": _iso_day(day), "v": float(value), "value": float(value),
            "period_time": period, "publication_time": avail, "available_time": avail,
            "knowable_at": avail[:10], "vintage": vintage, "revision_n": 0,
            "source_id": sensor_id,
            "vintage_id": _vintage_id(sensor_id, f"{day}|{value}")}


def _vintage_id(source_id: str, payload: str) -> str:
    try:
        from libs.data import pit_stamp
        got = pit_stamp.vintage_id_for(source_id, now_iso(), payload)
        if got:
            return str(got)
    except Exception:  # pragma: no cover -- a tree where libs has not landed
        pass
    import hashlib
    return hashlib.sha1(f"{source_id}|{payload}".encode()).hexdigest()[:16]


def _write_atomic(path: Path, payload: Any) -> None:
    """Atomic where the filesystem allows it; `os.replace` onto a read-only file is WinError 5."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=1, default=str, ensure_ascii=False)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    for attempt in range(2):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt or not path.exists():
                break
            try:
                os.chmod(path, 0o666)
            except OSError:
                break
        except OSError:
            break
    path.write_text(body, encoding="utf-8")
    tmp.unlink(missing_ok=True)


def read_axis_points(axes: Path, name: str, series: str = "*") -> list[tuple[str, float]]:
    """(day, value) from ANY of the three axis shapes this tree actually writes.

    `series[sid].points` (fred, ecb, the shadow latents), a bare `points` list (the kr lane), or
    a flat `rows` list keyed by `knowable_at` (cot, bis). For `rows`, `series` names the VALUE
    FIELD, optionally prefixed by a symbol filter -- `net_pct_oi` averages the field across every
    symbol on the day (the crowd's aggregate position), `XAUUSD.net_pct_oi` reads one market.
    A day appearing twice is averaged rather than kept twice: two markets are one reading of the
    crowd, and duplicate days would silently weight a Tuesday by how many contracts the CFTC
    happens to list.
    """
    try:
        doc = json.loads((Path(axes) / f"{name}.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    if not isinstance(doc, Mapping):
        return []
    blocks: list[Any] = []
    got = doc.get("series")
    if isinstance(got, Mapping):
        blocks = [v.get("points") for k, v in got.items()
                  if isinstance(v, Mapping) and (series in ("*", k))]
    if not blocks and isinstance(doc.get("points"), list):
        blocks = [doc["points"]]
    tally: dict[str, list[float]] = {}
    for pts in blocks:
        for p in pts or []:
            if not isinstance(p, Mapping):
                continue
            day = str(p.get("knowable_at") or p.get("d") or "")[:10]
            try:
                val = float(p.get("v") if p.get("v") is not None else p.get("value"))
            except (TypeError, ValueError):
                continue
            if day:
                tally.setdefault(day, []).append(val)
    if not tally and isinstance(doc.get("rows"), list):
        sym, _, field = series.rpartition(".")
        for r in doc["rows"]:
            if not isinstance(r, Mapping) or (sym and str(r.get("symbol")) != sym):
                continue
            day = str(r.get("knowable_at") or "")[:10]
            try:
                val = float(r.get(field))
            except (TypeError, ValueError):
                continue
            if day and len(day) == 10:
                tally.setdefault(day, []).append(val)
    return sorted((d, float(sum(v) / len(v))) for d, v in tally.items() if v)


def read_bars(symbol: str, timeframe: str = "D1", universe: Path | None = None
              ) -> list[tuple[str, float]]:
    """(day, close) from the desk's own bars. An absent file is UNMEASURED, never a flat series."""
    try:
        import pandas as pd
    except ImportError:  # pragma: no cover -- pandas is installed on both boxes
        return []
    path = Path(universe or UNIVERSE) / f"{symbol}_{timeframe}.parquet"
    if not path.exists():
        return []
    try:
        frame = pd.read_parquet(path, columns=["close"]).tail(4000)
    except (OSError, ValueError, KeyError):
        return []
    days = [str(v)[:10] for v in frame.index]
    vals = [float(v) for v in frame["close"].to_numpy()]
    return [(d, v) for d, v in zip(days, vals, strict=False) if math.isfinite(v)]


# ------------------------------------------------------------------------------- the fusion
def _z(values: np.ndarray) -> np.ndarray:
    sd = float(np.nanstd(values))
    if not math.isfinite(sd) or sd <= 0:
        return np.zeros_like(values)
    return (values - float(np.nanmean(values))) / sd


def _align(a: Sequence[tuple[str, float]], b: Sequence[tuple[str, float]]
           ) -> tuple[np.ndarray, np.ndarray]:
    bmap = dict(b)
    days = [d for d, _ in a if d in bmap]
    return (np.array([dict(a)[d] for d in days], dtype=float),
            np.array([bmap[d] for d in days], dtype=float))


def lead_lag_weight(sensor: Sequence[tuple[str, float]], target: Sequence[tuple[str, float]]
                    ) -> tuple[float, int, int]:
    """(|corr| at the best non-negative lead, that lead, overlap n). (0, 0, n) when unmeasurable.

    The sensor LEADS: the correlation is against the target's forward change, so a sensor that
    only moves after the target scores nothing. Absolute correlation because the sign is already
    declared in the table and re-deriving it here would let noise flip a mechanism.
    """
    xs, ys = _align(list(sensor), list(target))
    n = int(xs.size)
    if n < MIN_OVERLAP:
        return 0.0, 0, n
    dy = np.diff(ys, prepend=ys[0])
    best, best_lead = 0.0, 0
    for lead in LEAD_GRID:
        if n - lead < MIN_OVERLAP:
            break
        a, b = xs[:n - lead] if lead else xs, dy[lead:] if lead else dy
        if a.size < MIN_OVERLAP or float(np.nanstd(a)) <= 0 or float(np.nanstd(b)) <= 0:
            continue
        c = float(np.corrcoef(_z(a), _z(b))[0, 1])
        if math.isfinite(c) and abs(c) > abs(best):
            best, best_lead = c, lead
    return abs(best), best_lead, n


@dataclass
class LatentEstimate:
    """One fused latent: the estimate, its uncertainty, and exactly which sensors made it."""

    latent: str
    n_sensors_declared: int
    n_sensors_used: int
    weights: dict[str, float] = field(default_factory=dict)
    leads: dict[str, int] = field(default_factory=dict)
    points: list[dict[str, Any]] = field(default_factory=list)
    unmeasured: list[dict[str, str]] = field(default_factory=list)
    equal_weight_reason: str = ""
    status: str = UNMEASURED

    def row(self) -> dict[str, Any]:
        last = self.points[-1] if self.points else {}
        return {"latent": self.latent, "status": self.status,
                "n_sensors_declared": self.n_sensors_declared,
                "n_sensors_used": self.n_sensors_used, "weights": dict(self.weights),
                "leads_days": dict(self.leads), "n_points": len(self.points),
                "first": self.points[0]["d"] if self.points else None,
                "last": last.get("d"), "latest_estimate": last.get("v"),
                "latest_sd": last.get("sd"), "latest_n_present": last.get("n_present"),
                "equal_weight_reason": self.equal_weight_reason,
                "unmeasured": list(self.unmeasured)}


def fuse(latent: str, readings: Mapping[str, Sequence[tuple[str, float]]],
         signs: Mapping[str, int], *, target: Sequence[tuple[str, float]] | None = None,
         lag_days: float = 1.0, declared: int | None = None,
         unmeasured: Sequence[Mapping[str, str]] = ()) -> LatentEstimate:
    """Standardise, orient by the declared sign, weight by measured lead-lag, publish with a band.

    THE UNCERTAINTY IS THE DISPERSION OF THE SENSORS, not a bootstrap of one of them. When six
    free proxies of Chinese activity agree, the nowcast is worth trading; when they scatter, the
    band says so and the allocator can size on it. A day with one sensor present carries an
    UNMEASURED band rather than a zero one -- one sensor cannot disagree with itself.
    """
    est = LatentEstimate(latent=latent,
                         n_sensors_declared=int(declared if declared is not None else
                                                len(readings)),
                         n_sensors_used=0, unmeasured=[dict(u) for u in unmeasured])
    usable = {k: list(v) for k, v in readings.items() if len(v) >= 2}
    for k in sorted(set(readings) - set(usable)):
        est.unmeasured.append({"sensor": k, "why": f"{len(readings[k])} point(s): too short"})
    if len(usable) < MIN_SENSORS:
        est.status = UNMEASURED
        est.n_sensors_used = len(usable)
        est.equal_weight_reason = (f"{len(usable)} usable sensor(s) < {MIN_SENSORS}: the latent is"
                                   " UNMEASURED, not zero -- one sensor cannot disagree with"
                                   " itself, so it has no band and is not an ensemble")
        return est
    weights: dict[str, float] = {}
    for sid, pts in usable.items():
        if target:
            w, lead, n = lead_lag_weight(pts, target)
            est.leads[sid] = int(lead)
            if w > 0:
                weights[sid] = float(w)
                continue
            est.equal_weight_reason = est.equal_weight_reason or (
                f"{sid}: {n} overlapping day(s) with the target, below the {MIN_OVERLAP} a"
                " lead-lag weight needs -- equal weights, declared")
        weights[sid] = weights.get(sid, 0.0)
    if sum(weights.values()) <= 0:
        weights = dict.fromkeys(usable, 1.0)
        est.equal_weight_reason = est.equal_weight_reason or (
            "no sensor reached the overlap floor against the target: equal weights, declared")
    total = sum(weights.values()) or 1.0
    est.weights = {k: round(v / total, 6) for k, v in sorted(weights.items())}
    est.n_sensors_used = len(usable)

    zs: dict[str, dict[str, float]] = {}
    for sid, pts in usable.items():
        days = [d for d, _ in pts]
        vals = _z(np.array([v for _, v in pts], dtype=float)) * float(signs.get(sid, 1))
        zs[sid] = dict(zip(days, (float(v) for v in vals), strict=False))
    all_days = sorted({d for m in zs.values() for d in m})
    points: list[dict[str, Any]] = []
    for day in all_days:
        vals = [(est.weights[sid], zs[sid][day]) for sid in zs if day in zs[sid]]
        if not vals:
            continue
        wsum = sum(w for w, _ in vals) or 1.0
        mean = sum(w * v for w, v in vals) / wsum
        n_present = len(vals)
        sd = (float(np.std([v for _, v in vals], ddof=1)) if n_present > 1 else None)
        p = pit_point(day, mean, lag_days=lag_days, sensor_id=f"shadow:{latent}")
        p["sd"] = sd
        p["n_present"] = n_present
        p["sensors"] = sorted(sid for sid in zs if day in zs[sid])
        points.append(p)
    est.points = points
    est.status = "MEASURED" if points else UNMEASURED
    return est


def store_latent(axes: Path, est: LatentEstimate, *, dry_run: bool = False) -> dict[str, Any]:
    """Write the fused latent as an axis series with PIT stamps. Append-only by (day, vintage)."""
    path = Path(axes) / f"shadow_{est.latent}.json"
    try:
        prev = json.loads(path.read_text(encoding="utf-8-sig"))
        old = list(prev.get("points") or []) if isinstance(prev, Mapping) else []
    except (OSError, ValueError):
        old = []
    seen = {(str(p.get("period_time")), str(p.get("vintage_id"))) for p in old
            if isinstance(p, Mapping)}
    added = [p for p in est.points if (p["period_time"], p["vintage_id"]) not in seen]
    points = sorted([*old, *added], key=lambda p: (str(p.get("period_time")),
                                                   str(p.get("available_time"))))
    doc = {"axis": AXIS, "id": f"shadow_{est.latent}", "latent": est.latent, "at": now_iso(),
           "n": len(points), "added": len(added), "status": est.status,
           "n_sensors_declared": est.n_sensors_declared, "n_sensors_used": est.n_sensors_used,
           "weights": est.weights, "leads_days": est.leads,
           "equal_weight_reason": est.equal_weight_reason,
           "vintage_note": "APPEND-ONLY: a revised sensor makes a new observation, never an edit",
           "shape": "points[] -- d, v, sd, n_present, period_time, available_time, vintage_id",
           "unmeasured": est.unmeasured,
           "series": {est.latent: {"what": f"fused latent {est.latent}", "n": len(points),
                                   "points": points}},
           "points": points}
    if not dry_run:
        _write_atomic(path, doc)
    return doc


# --------------------------------------------------------------------- the disagreement dataset
def disagreement(legs: Mapping[str, Sequence[tuple[str, float]]], *, lag_days: float = 1.0
                 ) -> dict[str, Any]:
    """D_t over [retail, institutional, derivatives, options, news, macro], legs standardised.

    The VALUE is the cross-leg dispersion; the VECTOR is kept beside it, because "retail long
    while COT is short" is a different state from "options bid while news is quiet" and a scalar
    cannot tell them apart. A leg the box cannot measure is named, and `n_legs` rides on every
    point so a two-leg reading can never be compared with a six-leg one by accident.
    """
    present = {k: list(v) for k, v in legs.items() if k in DISAGREEMENT_LEGS and len(v) >= 2}
    missing = [{"leg": k, "why": UNMEASURED} for k in DISAGREEMENT_LEGS if k not in present]
    zs: dict[str, dict[str, float]] = {}
    for leg, pts in present.items():
        days = [d for d, _ in pts]
        vals = _z(np.array([v for _, v in pts], dtype=float))
        zs[leg] = dict(zip(days, (float(v) for v in vals), strict=False))
    all_days = sorted({d for m in zs.values() for d in m})
    points: list[dict[str, Any]] = []
    for day in all_days:
        row = {leg: zs[leg][day] for leg in zs if day in zs[leg]}
        if len(row) < 2:
            continue
        vals = np.array(list(row.values()), dtype=float)
        p = pit_point(day, float(np.std(vals, ddof=1)), lag_days=lag_days,
                      sensor_id="shadow:disagreement")
        p["legs"] = {k: round(v, 6) for k, v in sorted(row.items())}
        p["n_legs"] = len(row)
        p["max_gap"] = float(vals.max() - vals.min())
        points.append(p)
    return {"axis": AXIS, "id": "shadow_disagreement", "at": now_iso(),
            "legs_declared": list(DISAGREEMENT_LEGS), "legs_present": sorted(present),
            "legs_unmeasured": missing, "n": len(points),
            "status": "MEASURED" if points else UNMEASURED,
            "shape": "points[] -- v is the cross-leg sd; legs{} is the vector; n_legs rides along",
            "vintage_note": "APPEND-ONLY; a leg arriving later changes future points, never past",
            "series": {"disagreement": {"what": "cross-faction disagreement", "n": len(points),
                                        "points": points}},
            "points": points}


# ------------------------------------------------------------------------------ the vault
def _jsonl_span(path: Path, keys: Sequence[str]) -> tuple[str | None, str | None, int]:
    """(first day, last day, rows) from a JSONL without loading it whole."""
    first: str | None = None
    last: str | None = None
    rows = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rows += 1
                try:
                    doc = json.loads(line)
                except ValueError:
                    continue
                stamp = next((str(doc.get(k)) for k in keys if doc.get(k)), "")[:10]
                if not stamp:
                    continue
                first = stamp if first is None or stamp < first else first
                last = stamp if last is None or stamp > last else last
    except OSError:
        return None, None, 0
    return first, last, rows


_DAY_KEYS = ("date", "day", "time", "decided_at", "at", "created_at", "knowable_at")
#: Parquet files sampled when measuring a bar store's CONTENT depth.
PARQUET_SAMPLE = 12


def _parquet_span(files: Sequence[Path], *, sample: int = PARQUET_SAMPLE
                  ) -> tuple[str | None, str | None]:
    """(first day, last day) from the bar INDEX of a sample of files, or (None, None)."""
    try:
        import pandas as pd
    except ImportError:  # pragma: no cover -- pandas is installed on both boxes
        return None, None
    picks = list(files)[:sample] if len(files) <= sample else [
        files[i] for i in np.linspace(0, len(files) - 1, sample).astype(int)]
    days: list[str] = []
    for path in picks:
        try:
            idx = pd.read_parquet(path, columns=[]).index
        except Exception:
            continue
        if len(idx):
            days.extend((str(idx.min())[:10], str(idx.max())[:10]))
    days = [d for d in days if len(d) == 10 and d[:4].isdigit()]
    return (min(days), max(days)) if days else (None, None)


def vault_manifest(desk: Path | None = None) -> dict[str, Any]:
    """FREE STREAMS + TIME + CLEANING + PIT HISTORY = A PRIVATE DATASET, counted.

    Depth is measured from the artifacts, never declared: a stream the box does not hold is
    UNMEASURED with its path, which is the honest answer to "how many years do you have".
    """
    base = Path(desk or DESK)
    rows: list[dict[str, Any]] = []
    for spec in VAULT_ROOTS:
        path = base / str(spec["path"])
        row: dict[str, Any] = {**spec, "abs_path": str(path), "status": UNMEASURED,
                               "first": None, "last": None, "depth_days": None, "n": 0}
        if not path.exists():
            row["why"] = f"{spec['path']} is not on this box"
            rows.append(row)
            continue
        if spec["layout"] == "jsonl":
            first, last, n = _jsonl_span(path, _DAY_KEYS)
            row.update({"first": first, "last": last, "n": n})
        elif spec["layout"] == "day_parquet_per_symbol":
            days: set[str] = set()
            syms = 0
            for sub in sorted(path.iterdir()):
                if not sub.is_dir():
                    continue
                syms += 1
                days |= {p.stem for p in sub.glob("*.parquet") if len(p.stem) == 10}
            row.update({"first": min(days) if days else None, "last": max(days) if days else None,
                        "n": len(days), "n_symbols": syms})
        elif spec["layout"] == "parquet_dir":
            # THE CONTENT'S DEPTH, NOT THE FILE'S. A parquet of six years of bars copied onto the
            # box yesterday has an mtime of yesterday; reading the index is the only honest answer
            # to "how much history does the desk hold", and it is the whole point of this row.
            files = sorted(path.glob("*.parquet"))
            first, last = _parquet_span(files, sample=PARQUET_SAMPLE)
            row.update({"first": first, "last": last, "n": len(files),
                        "stamp_basis": f"the bar index of up to {PARQUET_SAMPLE} sampled file(s)"})
        else:
            files = [p for p in path.rglob("*") if p.is_file()]
            stamps = sorted(datetime.fromtimestamp(p.stat().st_mtime, tz=UTC).date().isoformat()
                            for p in files[:5000])
            row.update({"first": stamps[0] if stamps else None,
                        "last": stamps[-1] if stamps else None, "n": len(files),
                        "stamp_basis": "file mtime -- a copy resets it, so this is a FLOOR"})
        if row["first"] and row["last"]:
            row["depth_days"] = (date.fromisoformat(row["last"])
                                 - date.fromisoformat(row["first"])).days + 1
            row["status"] = "ARCHIVING"
        else:
            row["why"] = row.get("why") or "present but no dated artifact could be read"
        rows.append(row)
    archiving = [r for r in rows if r["status"] == "ARCHIVING"]
    return {"at": now_iso(), "rule": "capture before it disappears; keep revisions; stamp"
                                     " availability; the only way depth grows is calendar time",
            "n_streams": len(rows), "n_archiving": len(archiving),
            "deepest_days": max((int(r["depth_days"] or 0) for r in archiving), default=0),
            "streams": rows}


# ----------------------------------------------------------------------------- the gap map
def gap_map(latents: Mapping[str, LatentEstimate], vault: Mapping[str, Any],
            sensors: Sequence[Sensor]) -> list[dict[str, Any]]:
    """Eleven capabilities money buys, their free shadows, and a MEASURED status per row."""
    by_kind = {str(r.get("kind")): r for r in (vault.get("streams") or [])}
    crypto_ok = [s for s in sensors if s.fetch_class == "public_endpoint"
                 and s.machine_use_allowed]
    out: list[dict[str, Any]] = []
    for row in GAP_MAP:
        how = str(row["measured_by"])
        rec: dict[str, Any] = {"capability": row["capability"], "shadow": row["shadow"],
                               "measured_by": how, "status": UNMEASURED, "detail": {}}
        if how == "latents":
            names = [n for n in row.get("latents", ()) if n in latents]
            used = {n: latents[n].n_sensors_used for n in names}
            short = sorted(n for n in names if used.get(n, 0) < MIN_SENSORS)
            rec["detail"] = {"latents": used,
                             "declared": {n: latents[n].n_sensors_declared for n in names},
                             "below_sensor_floor": short, "sensor_floor": MIN_SENSORS}
            # THE VOCABULARY, AND WHAT EACH WORD COSTS TO SAY.
            #   SHADOWED  every latent this capability names is actually estimated on THIS box
            #             from at least `MIN_SENSORS` fused sensors -- a proxy stands in for the
            #             feed, today, and the axis file exists to prove it.
            #   PARTIAL   some do and some do not, and `below_sensor_floor` NAMES the ones that
            #             do not. A capability two thirds shadowed is not shadowed, and
            #             collapsing it upward would let the map advertise cover the desk lacks.
            #   UNMEASURED nothing here reaches the floor. Never "no shadow exists" -- only that
            #             none was measured on this box (L1.28a).
            rec["status"] = (UNMEASURED if not names or len(short) == len(names) else
                             "SHADOWED" if not short else "PARTIAL")
            if short:
                rec["missing"] = (f"{', '.join(short)}: fewer than {MIN_SENSORS} sensor(s) fused"
                                  " on this box, so no proxy stands in for that half of the"
                                  " capability")
        elif how == "crypto_and_tape":
            tape = by_kind.get("broker_tick_tape", {})
            rec["detail"] = {"free_l2_sensors_declared": len([s for s in crypto_ok
                                                              if "lob" in s.sensor_id
                                                              or "depth" in s.sensor_id]),
                             "own_tick_tape_days": tape.get("depth_days"),
                             "own_tick_tape_status": tape.get("status")}
            rec["status"] = ("SHADOWED" if tape.get("status") == "ARCHIVING" else "PARTIAL")
        elif how == "crypto_options":
            n = len([s for s in crypto_ok if s.sensor_id.startswith("deribit_")])
            # Hard-boundary refusals only since LAWS 5e; a terms note is in `terms_labelled`.
            refused = [s.sensor_id for s in sensors if not s.machine_use_allowed]
            rec["detail"] = {"deribit_sensors_declared": n, "deribit_sensors": n,
                             "refused_for_terms": refused,
                             "terms_labelled": [s.sensor_id for s in sensors if s.terms_note]}
            rec["status"] = "SHADOWED" if n else UNMEASURED
        elif how == "vault":
            kinds = [k for k in row.get("vault_kinds", ()) if k in by_kind]
            rec["detail"] = {k: {"status": by_kind[k]["status"],
                                 "depth_days": by_kind[k]["depth_days"]} for k in kinds}
            deepest = int(vault.get("deepest_days") or 0)
            rec["detail"]["deepest_stream_days"] = deepest
            rec["status"] = "ARCHIVING" if deepest > 0 else UNMEASURED
        elif how == "desk_organ":
            organ = ROOT / str(row.get("organ") or "")
            rec["detail"] = {"organ": row.get("organ"), "on_this_tree": organ.exists()}
            rec["status"] = "SHADOWED" if organ.exists() else UNMEASURED
        elif how == "declared_gap":
            rec["detail"] = {"sources": ["Sentinel-2/Copernicus", "Landsat", "NASA Worldview"],
                             "fetcher_on_this_tree": False}
            rec["status"] = "DECLARED_ONLY"
        elif how == "cannot_reproduce":
            rec["detail"] = {"organ": row.get("organ"),
                             "doctrine": "operate where latency does not bind: 1s to hours"}
            rec["status"] = "CANNOT_REPRODUCE"
        if rec["status"] in (UNMEASURED, "PARTIAL", "DECLARED_ONLY") and "missing" not in rec:
            rec["missing"] = (f"{rec['capability']}: nothing on this box measures this row's"
                              f" shadow yet ({how})")
        out.append(rec)
    return out


# -------------------------------------------------------------------------------- discoveries
def record_discoveries(latents: Mapping[str, LatentEstimate], *, conn: Any = None,
                       dry_run: bool = True, targets: Sequence[str] = MT5_TARGETS,
                       horizons: Sequence[str] = HORIZONS) -> dict[str, Any]:
    """One DiscoveryObject per (latent x MT5 target x horizon). A question, never an edge.

    The dedupe key `record_discovery` uses is (source, mechanism, assets, rule), so the target
    rides in `assets` and the horizon in the rule: the same cell recorded twice returns the same
    id and the counter reads `seen` rather than `recorded`.
    """
    out = {"recorded": 0, "seen": 0, "by_latent": {}, "cells": []}
    for latent, est in sorted(latents.items()):
        consumers = sorted({c for s in ENSEMBLES.get(latent, ()) for c in s.consumers
                            if c in targets})
        n = 0
        for target in consumers:
            for horizon in horizons:
                cell = {"latent": latent, "target": target, "horizon": horizon,
                        "status": est.status, "n_sensors_used": est.n_sensors_used}
                out["cells"].append(cell)
                n += 1
                out["seen"] += 1
                if dry_run:
                    continue
                try:
                    from libs.moat import registry as R
                    _did, created = R.record_discovery(
                        conn=conn, source_id=f"shadow:{latent}", source_type="latent_ensemble",
                        mechanism=(f"the latent {latent}, estimated from {est.n_sensors_used} of "
                                   f"{est.n_sensors_declared} declared free sensors, conditions "
                                   f"{target}")[:400],
                        origin="EXTERNAL", generator=f"shadow:{latent}",
                        assets=[target], horizons=[horizon],
                        information="shadow_institutional_ensemble",
                        exact_rule_if_known=(f"condition {target} on the standardised {latent} "
                                             f"estimate and its dispersion band over {horizon}"),
                        required_data=[f"data/axes/shadow_{latent}.json"],
                        pit_requirements=["every sensor carries available_time; the fused point "
                                          "is stamped at the slowest sensor's lag"],
                        economic_rationale=("the expensive feed measures this latent; these free "
                                            "sensors estimate the same hidden state"),
                        novelty=0.5, confidence=min(0.6, 0.1 * est.n_sensors_used),
                        falsifier=(f"the {latent} estimate has no relation to {target} at "
                                   f"{horizon} out of sample, or the dispersion band does not "
                                   f"separate reliable days from unreliable ones"),
                        payload={"latent": latent, "target": target, "horizon": horizon,
                                 "weights": est.weights, "leads_days": est.leads,
                                 "status": est.status, "rule": RULE})
                    out["recorded"] += int(created)
                except Exception:  # pragma: no cover -- an unopenable registry is not fatal
                    pass
        out["by_latent"][latent] = n
    return out


# ----------------------------------------------------------------------------- the whole pass
def _gather(latent: str, sensors: Sequence[Sensor], *, axes: Path, universe: Path,
            guard: Guard) -> tuple[dict[str, list[tuple[str, float]]], list[dict[str, str]],
                                   list[dict[str, Any]]]:
    """Readings per sensor, the UNMEASURED ones by name, and the status row for every sensor."""
    readings: dict[str, list[tuple[str, float]]] = {}
    missing: list[dict[str, str]] = []
    status: list[dict[str, Any]] = []
    for s in sensors:
        pts: list[tuple[str, float]] = []
        why = ""
        if not s.machine_use_allowed:
            # HARD BOUNDARY ONLY (LAWS 5e, 2026-09-23): no sensor in this table reaches here for
            # terms any more, and a row that does must name the refused act in its licence line.
            why = f"REFUSED on the hard boundary: {s.licence}"
            guard.refused.append({"sensor": s.sensor_id, "why": why})
        elif s.fetch_class == "desk_axis" and s.axis_file:
            pts = read_axis_points(axes, s.axis_file, s.axis_series or "*")
            why = "" if pts else (f"data/axes/{s.axis_file}.json holds no readable point for"
                                  f" series {s.axis_series or '*'!r} -- UNMEASURED, not barren")
        elif s.fetch_class == "desk_axis":
            sym = next((t for t in MT5_TARGETS if t in (s.verb or "")), "")
            pts = read_bars(sym, "D1", universe) if sym else []
            why = "" if pts else f"no bars for {sym or 'the declared symbol'} on this box"
        elif s.fetch_class == "public_endpoint":
            payload, why = guard.get(s)
            pts = parse_points(payload) if payload is not None else []
            if payload is not None and not pts:
                why = "payload carried no (day, value) pair this parser recognises"
        else:
            why = s.terms_note or "no fetcher on this tree"
        if pts:
            readings[s.sensor_id] = pts
        else:
            missing.append({"sensor": s.sensor_id, "why": why or UNMEASURED})
        state = (REFUSED if not s.machine_use_allowed else
                 HELD if pts else
                 REACHABLE if s.fetch_class == "public_endpoint" else UNMEASURED)
        status.append({"sensor": s.sensor_id, "latent": s.latent, "state": state,
                       "fetch_class": s.fetch_class, "machine_use_allowed": s.machine_use_allowed,
                       "terms_note": s.terms_note, "licence": s.licence,
                       "consumers": list(s.consumers), "n": len(pts),
                       "first": pts[0][0] if pts else None, "last": pts[-1][0] if pts else None,
                       "why": why or None})
    return readings, missing, status


def parse_points(payload: Any) -> list[tuple[str, float]]:
    """(day, value) out of a public payload. Three shapes cover every endpoint declared here."""
    rows: list[Any]
    if isinstance(payload, Mapping):
        rows = next((v for k, v in payload.items()
                     if isinstance(v, list) and k in ("data", "result", "points", "rows",
                                                      "series")), [])
        if not rows and "d" in payload and "v" in payload:
            rows = [payload]
    elif isinstance(payload, list):
        rows = payload
    else:
        return []
    out: list[tuple[str, float]] = []
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        day = ""
        for k in ("d", "date", "day", "period", "record_date", "auction_date", "time"):
            if r.get(k):
                day = str(r[k])[:10]
                break
        val = None
        for k in ("v", "value", "close", "index_price", "last_price", "mark", "amount"):
            if r.get(k) not in (None, "", "-"):
                try:
                    val = float(str(r[k]).replace(",", ""))
                except (TypeError, ValueError):
                    val = None
                break
        if day and val is not None and math.isfinite(val):
            out.append((day, val))
    return sorted(out)


def run(*, budget_s: float = 300.0, no_fetch: bool = True, dry_run: bool = True,
        desk: Path | None = None, axes: Path | None = None, universe: Path | None = None,
        fixtures: Path | None = None, conn: Any = None, report_path: Path | None = None,
        risk_target: str = "US500") -> dict[str, Any]:
    """Every ensemble, the disagreement dataset, the vault, the gap map, and the questions."""
    base = Path(desk or DESK)
    ax = Path(axes) if axes is not None else base / "data" / "axes"
    uni = Path(universe) if universe is not None else base / "data" / "universe"
    guard = Guard(budget_s=budget_s, no_fetch=no_fetch,
                  fixtures=fixtures if fixtures is not None else base / "data/shadow_fixtures")
    all_sensors = [s for rows in ENSEMBLES.values() for s in rows] + list(CRYPTO_SENSORS)
    problems = check_sensors(all_sensors)
    target = read_bars(risk_target, "D1", uni)
    latents: dict[str, LatentEstimate] = {}
    sensor_status: list[dict[str, Any]] = []
    for latent, rows in ENSEMBLES.items():
        extra = tuple(s for s in CRYPTO_SENSORS if s.latent == latent)
        readings, missing, status = _gather(latent, (*rows, *extra), axes=ax, universe=uni,
                                            guard=guard)
        sensor_status.extend(status)
        signs = {s.sensor_id: s.sign for s in (*rows, *extra)}
        lag = max((s.pit_lag_days for s in (*rows, *extra)
                   if s.sensor_id in readings), default=1.0)
        est = fuse(latent, readings, signs, target=target or None, lag_days=lag,
                   declared=len(rows) + len(extra), unmeasured=missing)
        latents[latent] = est
        store_latent(ax, est, dry_run=dry_run)

    legs: dict[str, list[tuple[str, float]]] = {}
    if "retail_crowding" in latents and latents["retail_crowding"].points:
        legs["retail"] = [(p["d"], float(p["v"])) for p in latents["retail_crowding"].points]
    cot = read_axis_points(ax, "cot")
    if cot:
        legs["institutional"] = cot
    for leg, sid in (("derivatives", "perp_funding"), ("options", "deribit_atm_iv")):
        payload, _why = guard.get(next(s for s in CRYPTO_SENSORS if s.sensor_id == sid))
        pts = parse_points(payload) if payload is not None else []
        if pts:
            legs[leg] = pts
    macro = read_axis_points(ax, "fred")
    if macro:
        legs["macro"] = macro
    dis = disagreement(legs)
    if not dry_run:
        _write_atomic(ax / "shadow_disagreement.json", dis)

    vault = vault_manifest(base)
    doc = {
        "at": now_iso(), "rule": RULE, "mode": "no-fetch" if no_fetch else "fetch",
        "dry_run": bool(dry_run), "risk_target": risk_target,
        "mandate": ("crypto-native endpoints are RISK/LIQUIDITY/POSITIONING SENSORS for MT5"
                    " instruments only; no crypto ground is hunted and every sensor names its"
                    " MT5 consumers (2026-08-18)"),
        "sensor_problems": problems,
        "ensembles": [latents[k].row() for k in ENSEMBLES],
        "sensors": sensor_status,
        "sensor_counts": {state: sum(1 for r in sensor_status if r["state"] == state)
                          for state in (HELD, REACHABLE, REFUSED, UNMEASURED)},
        "crypto_sensors": [{"sensor": s.sensor_id, "latent": s.latent,
                            "machine_use_allowed": s.machine_use_allowed,
                            "licence": s.licence, "consumers": list(s.consumers),
                            "terms_note": s.terms_note} for s in CRYPTO_SENSORS],
        # EMPTY BY CONSTRUCTION since LAWS 5e (2026-09-23): only a hard-boundary act lands here.
        # The key is kept so an old reader finds an explicit empty list.
        "refused_for_terms": guard.refused,
        "terms_labels": guard.notes,
        "access_rule": ("every sensor off the five refused acts is MINED; licence, terms and "
                        "robots notes are routing labels that withhold redistribution"),
        "disagreement": {k: v for k, v in dis.items() if k not in ("points", "series")},
        "vault_manifest": vault,
        "gap_map": gap_map(latents, vault, all_sensors),
        "network_calls": guard.calls,
    }
    doc["discoveries"] = record_discoveries(latents, conn=conn, dry_run=dry_run)
    if not dry_run:
        _write_atomic(Path(report_path) if report_path is not None else OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the free shadow-institutional stack")
    ap.add_argument("--fetch", action="store_true",
                    help="go to the network (robots is read and labelled, never obeyed as a veto)")
    ap.add_argument("--no-fetch", dest="no_fetch", action="store_true",
                    help="read fixtures instead of the wire (the default)")
    ap.add_argument("--dry-run", action="store_true", help="measure and write nothing")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--risk-target", default="US500")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, no_fetch=not a.fetch, dry_run=a.dry_run,
              risk_target=a.risk_target)
    for row in doc["ensembles"]:
        print(f"{row['latent']:<22} {row['status']:<10} "
              f"{row['n_sensors_used']}/{row['n_sensors_declared']} sensors  "
              f"n={row['n_points']:<5} last={row['last']}")
    counts = doc["sensor_counts"]
    print(f"  sensors  held={counts[HELD]} reachable={counts[REACHABLE]} "
          f"refused={counts[REFUSED]} unmeasured={counts[UNMEASURED]}")
    print(f"  vault    {doc['vault_manifest']['n_archiving']}/"
          f"{doc['vault_manifest']['n_streams']} streams archiving, deepest "
          f"{doc['vault_manifest']['deepest_days']}d")
    states = sorted({str(r["status"]) for r in doc["gap_map"]})
    print(f"  gap map  {len(doc['gap_map'])} row(s): {', '.join(states)}")
    print(f"  cells    {doc['discoveries']['seen']} question(s), "
          f"{doc['discoveries']['recorded']} newly recorded")
    if doc["sensor_problems"]:
        for p in doc["sensor_problems"][:10]:
            print(f"  SENSOR TABLE: {p}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
