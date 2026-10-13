"""SINGAPORE: the only major central bank whose policy instrument is an exchange rate band.

THE ONE THING THAT MAKES SINGAPORE DIFFERENT FROM EVERY OTHER COUNTRY IN THIS DEPARTMENT. MAS has
no policy rate. It has never had one and says it never will: with a trade-to-GDP ratio above 300%
the exchange rate, not the interest rate, is what transmits to domestic prices. So policy is a
BAND on the trade-weighted Singapore dollar -- the S$NEER -- described by three parameters:

  * the SLOPE, the annualised rate at which the band's midpoint crawls upward;
  * the WIDTH, a symmetric corridor around that midpoint;
  * the CENTRE, which MAS occasionally RE-CENTRES to the prevailing level, a step change that is
    not a slope change and must never be modelled as one.

MAS PUBLISHES NONE OF THE THREE. It publishes a weekly S$NEER index level and a qualitative
sentence ("slightly", "modestly", "no change to the width"), and the market infers the rest. The
research consequence is exact and unusual: THE POLICY STATE IS A LATENT VARIABLE, and the first
job of any Singapore cell is to estimate it. That is SG-A and SG-C, and it is why this pack
carries a `BAND_STATE` table of every announced move since 2020 rather than a rate history.

WHY THAT IS TRADABLE ON THIS BROKER, WHICH IS THE PART THAT MATTERS HERE. The S$NEER is not
quoted anywhere and cannot be. But it is a trade-weighted basket, and this broker quotes SEVEN
SGD pairs -- USDSGD, EURSGD, GBPSGD, AUDSGD, NZDSGD, CHFSGD and SGDJPY -- plus USDCNH, USDKRW,
USDIDR, USDTHB, USDINR and USDHKD, which between them cover most of the trade weights the basket
is built from. A SYNTHETIC S$NEER is therefore constructible from instruments the desk can
actually trade, and a band-edge hypothesis becomes a basket trade rather than an untradable
observation. No other country in this department has its central bank's target reconstructible
out of executable symbols.

THE SECOND MECHANISM: SINGAPORE IS A PRICING VENUE FOR THINGS THAT HAPPEN ELSEWHERE. The
11:00 SGT ABS/SFEMC fixings settle the non-deliverable forwards of half of Asia -- IDR, MYR, PHP,
THB, INR, KRW, TWD, VND, CNY -- so 03:00 UTC is a REGIONAL fixing event and not a Singapore one,
and it is the single clock that ties this pack to the Indonesian, Malaysian, Thai, Philippine,
Vietnamese and Indian packs. The 16:30 SGT Platts Market-on-Close window (08:30 UTC) sets the
Asian oil benchmarks that price Dubai, the Brent-Dubai exchange for swaps, gasoil and jet. SGX is
the clearing venue for the world's iron-ore derivatives and the world's largest bunkering port
sits in the same harbour. Singapore's own economy is small; its CALENDAR is regional.

WHAT IS EXECUTABLE AND WHAT IS NOT. Everything in the currency layer is executable, which makes
Singapore the richest FX pack in this department. Nothing in the venue layer is: the Straits Times
Index, SGX's FTSE China A50 and Nikkei 225 contracts, SGX iron ore, SGX rubber, SORA, MAS bills
and SGS are all ABSENT and are named in `TRANSMISSION_TARGETS` with the symbols their mechanisms
reach -- JPN225 for the Nikkei SQ, CHINAH and HK50 for the A50, AUS200 and XCUUSD for iron ore.

THE TRAP THIS PACK EXISTS TO STOP. Singapore looks like a clean, liquid, English-language,
well-documented market, and it is, which makes it the easiest place in Asia to fit a spurious
seasonal. Every domain below therefore carries a control that asks the same question of a
currency MAS does not manage. A statistic that appears in USDSGD and in USDHKD equally is a dollar
statistic wearing a Singapore hat; a statistic that appears in the SGD NEER basket and not in any
single pair is the one worth having.

CUSTOM_MINERS ARE SPECIFICATIONS, NOT WIRING. Every entry names the module it will live in and
the inputs it must read. None is on a clock yet; unwired is a defect (III.16), and naming it is
how the defect stays visible instead of being reported as "built".
"""
from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[3]
for _p in (str(_DESK), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.countries import (  # noqa: E402
    actor,
    build_pack,
    dataset,
    domain,
    edge,
    era,
    miner,
    source_class,
)

# --------------------------------------------------------------------------- identity
CODE = "SG"
NAME = "Singapore"
REGION_COMMAND = "southeast_asia"
CURRENCY = "SGD"
FISCAL_YEAR_END = "03-31"  # government FY runs 1 April to 31 March; the Budget is read in February
NATIVE_LANGUAGES: tuple[str, ...] = ("en", "zh", "ms", "ta")

#: Singapore is the richest FX pack in this department: seven SGD pairs plus the regional
#: currencies that make up most of the trade weights. That is what makes a synthetic S$NEER
#: constructible out of instruments the desk can trade.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDSGD", "EURSGD", "GBPSGD", "AUDSGD", "NZDSGD", "CHFSGD", "SGDJPY",  # the SGD complex
    "USDCNH", "USDKRW", "USDJPY", "USDHKD", "USDIDR", "USDTHB", "USDINR",  # basket constituents
    "EURUSD", "AUDUSD", "USDX",           # the factors a NEER claim must be residualised on
    "JPN225", "HK50", "CHINAH",           # what SGX's index contracts are about
    "XTIUSD", "XBRUSD", "XNGUSD",         # the Asian oil pricing hub's underlying
    "XAUUSD", "XCUUSD", "AUS200",         # bullion vaulting, iron-ore clearing, the miner proxy
)

#: What Singapore's mechanisms are ABOUT that this broker does not quote.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "S$NEER trade-weighted index", "venue": "MAS (weekly index level only)",
     "why": "the policy instrument itself. MAS publishes a weekly index level and NONE of the "
            "three band parameters, so the policy state is latent and must be estimated",
     "proxies": ("USDSGD", "EURSGD", "SGDJPY", "AUDSGD", "GBPSGD", "CHFSGD", "NZDSGD",
                 "USDCNH", "USDKRW", "USDIDR", "USDTHB")},
    {"name": "Straits Times Index", "venue": "SGX",
     "why": "a 30-name, bank-heavy index whose own moves are mostly a domestic rate story; its "
            "value here is as a confirmation channel, not as a target",
     "proxies": ("HK50", "AUS200")},
    {"name": "SGX FTSE China A50 index futures", "venue": "SGX",
     "why": "the offshore China equity hedge, with a T-session and a T+1 session that spans the "
            "European and US hours when the onshore market is shut",
     "proxies": ("CHINAH", "HK50", "USDCNH")},
    {"name": "SGX Nikkei 225 index futures", "venue": "SGX",
     "why": "settles to the Osaka Special Quotation on the second Friday of March, June, "
            "September and December, so the SQ is a Singapore-cleared event too",
     "proxies": ("JPN225", "USDJPY")},
    {"name": "SGX iron ore 62% Fe futures and swaps", "venue": "SGX",
     "why": "SGX clears the overwhelming majority of the world's iron-ore derivatives; monthly "
            "settlement is an index average, so the whole month is the event, not the last day",
     "proxies": ("AUS200", "XCUUSD", "USDCNH", "AUDUSD")},
    {"name": "SGX TSR20 rubber futures", "venue": "SGX / SICOM",
     "why": "the world benchmark for natural rubber, which is a Thai, Indonesian and Malaysian "
            "export price and therefore a terms-of-trade input for three packs in this region",
     "proxies": ("USDTHB", "USDIDR")},
    {"name": "Singapore marine fuel 0.5% and MOPS product cracks", "venue": "Platts MOC 16:30 SGT",
     "why": "the world's largest bunkering port prices here; the 08:30 UTC window sets Asian "
            "product cracks that feed refinery margins from Korea to India",
     "proxies": ("XTIUSD", "XBRUSD")},
    {"name": "SORA, MAS bills and Singapore Government Securities", "venue": "MAS / SGS",
     "why": "SGD rates are an OUTPUT of the FX band, not an input to it -- the cleanest natural "
            "example of the impossible trinity that exists, and the reason an SGD rate cell must "
            "be conditioned on the band state",
     "proxies": ("USDSGD", "USDX")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Monetary Authority of Singapore",
    "short": "MAS",
    "committee": "no separate committee; the Monetary Policy Statement is issued by MAS itself",
    "policy_instrument": "the trade-weighted Singapore dollar nominal effective exchange rate "
                         "(S$NEER) managed within an undisclosed policy band",
    "band_parameters": ("slope: the annualised rate of appreciation of the band's midpoint",
                        "width: a symmetric corridor around the midpoint",
                        "centre: the midpoint's level, which MAS occasionally RE-CENTRES to the "
                        "prevailing level as a step change"),
    "disclosure": "MAS publishes a weekly S$NEER INDEX LEVEL and a qualitative description of "
                  "each move ('slightly', 'modestly', 'no change to the width'). It publishes "
                  "NONE of the three parameters. The market convention is a width of about "
                  "+/-2%, which is an inference and not a disclosure, and any cell that treats "
                  "it as known must say so",
    "mandate": "medium-term price stability as the basis for sustainable growth; MAS also "
               "supervises the financial sector and manages the official foreign reserves",
    "decision_rule": "QUARTERLY Monetary Policy Statements since 2024 -- January, April, July "
                     "and October -- replacing the semi-annual April/October cycle that ran for "
                     "decades. Released at 08:00 SGT, which is 00:00 UTC: the earliest scheduled "
                     "central bank event in the global day and the reason a Singapore event cell "
                     "must be careful about which UTC date it attributes the move to",
    "announce_local": "08:00 SGT", "announce_utc": "00:00",
    "presser_utc": "01:00",
    "off_cycle": "MAS has moved OFF-CYCLE three times in recent memory (March 2020, January 2022 "
                 "and July 2022). An off-cycle statement arrives with no notice and is the "
                 "largest single-day SGD event class there is",
    "other_clocks": (
        {"what": "official foreign reserves and the forward book",
         "when_local": "7th business day, 17:00 SGT", "when_utc": "09:00",
         "reference_lag_days": 30},
        {"what": "SORA publication for the previous business day",
         "when_local": "09:00 SGT", "when_utc": "01:00", "reference_lag_days": 1},
        {"what": "weekly S$NEER index level", "when_local": "Friday", "when_utc": "09:00",
         "reference_lag_days": 7},
        {"what": "MAS bill and SGS auctions", "when_local": "varies", "when_utc": "04:00",
         "reference_lag_days": 0},
    ),
    "dates": {
        2024: ("2024-01-29", "2024-04-12", "2024-07-26", "2024-10-14"),
        2025: ("2025-01-24", "2025-04-14", "2025-07-30"),
        2026: (),
    },
    "dates_status": "2024 is the first full quarterly year and is complete. The 2025 fourth "
                    "statement and the whole 2026 calendar are UNMEASURED in this pack (L1.28a) "
                    "and must be read from the MAS media-release calendar before any event study "
                    "-- an invented date is worse than a missing one, because a missing one is "
                    "visible",
}

#: The announced band moves. This is Singapore's equivalent of a policy rate history, and it is
#: the reason a slope change and a RE-CENTRING must never be pooled: a re-centring is a step in
#: the level of the target, a slope change is a change in its drift, and a cell that treats them
#: as the same event is averaging a jump with a trend.
BAND_STATE: tuple[dict[str, str], ...] = (
    {"date": "2020-03-30", "action": "EASE", "slope": "reduced to zero",
     "centre": "re-centred DOWN to the prevailing level", "width": "unchanged",
     "note": "the pandemic easing: a simultaneous slope cut and downward re-centring, the only "
             "one of its kind in the sample"},
    {"date": "2021-10-14", "action": "TIGHTEN", "slope": "raised slightly from zero",
     "centre": "unchanged", "width": "unchanged",
     "note": "the start of the tightening cycle"},
    {"date": "2022-01-25", "action": "TIGHTEN (OFF-CYCLE)", "slope": "raised slightly",
     "centre": "unchanged", "width": "unchanged",
     "note": "an unscheduled statement; the SGD gapped on a day with no scheduled event"},
    {"date": "2022-04-14", "action": "TIGHTEN", "slope": "raised",
     "centre": "re-centred UP to the prevailing level", "width": "unchanged",
     "note": "the first upward re-centring of the cycle"},
    {"date": "2022-07-14", "action": "TIGHTEN (OFF-CYCLE)", "slope": "unchanged",
     "centre": "re-centred UP to the prevailing level", "width": "unchanged",
     "note": "a pure re-centring with no slope change: the cleanest available observation of "
             "what a step in the target alone does to the basket"},
    {"date": "2022-10-14", "action": "TIGHTEN", "slope": "unchanged",
     "centre": "re-centred UP to the prevailing level", "width": "unchanged",
     "note": "the last tightening of the cycle"},
    {"date": "2023-04-14", "action": "HOLD", "slope": "unchanged", "centre": "unchanged",
     "width": "unchanged", "note": "the pause begins and runs for seven statements"},
    {"date": "2025-01-24", "action": "EASE", "slope": "reduced slightly", "centre": "unchanged",
     "width": "unchanged",
     "note": "the first easing since March 2020, and the first policy change under the quarterly "
             "cadence"},
    {"date": "2025-04-14", "action": "EASE", "slope": "reduced slightly", "centre": "unchanged",
     "width": "unchanged", "note": "a second consecutive slope reduction"},
)

# --------------------------------------------------------------------------- fixings, settlement
#: SGT is UTC+8 all year with no daylight saving, so every stamp below is constant. The 03:00 UTC
#: row is the one that matters most: it is not a Singapore fixing, it is ASIA's, and it is the
#: clock this pack shares with the Indonesian, Malaysian, Thai, Philippine, Vietnamese and Indian
#: packs.
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "ABS/SFEMC Asian currency spot fixings",
     "administrator": "ABS Benchmarks Administration Co, under SFEMC conventions",
     "window_local": "a polling and transaction window concluding around 11:00 SGT",
     "window_utc": "02:30-03:00", "publish_local": "about 11:00-11:30 SGT",
     "publish_utc": "03:00",
     "basis": "contributed and transaction-based spot rates for the region's restricted "
              "currencies",
     "uses": "settlement of non-deliverable forwards in IDR, MYR, PHP, THB, INR, KRW, TWD, VND "
             "and CNY",
     "note": "THE REGIONAL CLOCK. An NDF settlement effect in six other packs lands at this one "
             "UTC stamp, and a cell that finds an 03:00 UTC effect in a single currency must "
             "check it is not simply the whole region settling at once"},
    {"name": "SORA -- Singapore Overnight Rate Average",
     "administrator": "MAS", "window_local": "the previous business day's unsecured overnight "
                                             "interbank SGD transactions",
     "window_utc": "previous session", "publish_local": "09:00 SGT the following business day",
     "publish_utc": "01:00",
     "basis": "volume-weighted average of eligible unsecured overnight interbank borrowings",
     "uses": "the successor to SOR, which was retired in mid-2023; compounded SORA is the "
             "reference for SGD loans and swaps",
     "note": "SGD rates are an OUTPUT of the band, not a lever: a SORA move is information about "
             "capital flows and about the band's position, never about a policy decision"},
    {"name": "SGD spot in the WM/Refinitiv 16:00 London benchmark window",
     "administrator": "WM/Refinitiv", "window_local": "00:00-00:05 SGT the following day",
     "window_utc": "15:57:30-16:02:30", "publish_local": "about 00:05 SGT",
     "publish_utc": "16:02",
     "basis": "the standard five-minute benchmark window",
     "uses": "index and passive-mandate rebalancing in SGD",
     "note": "this window sits in the middle of Singapore's night, so a benchmark-driven SGD flow "
             "and a Singapore-session SGD flow can never be confused for one another -- a free "
             "identification the other packs in this region do not get"},
    {"name": "Platts Singapore Market-on-Close assessment window",
     "administrator": "S&P Global Commodity Insights",
     "window_local": "the half hour to 16:30 SGT", "window_utc": "08:00-08:30",
     "publish_local": "16:30 SGT", "publish_utc": "08:30",
     "basis": "bids, offers and trades in the closing window for Dubai, Brent-Dubai EFS, gasoil, "
              "jet and marine fuel",
     "uses": "the physical benchmarks that price the whole Asian barrel",
     "note": "the only commodity fixing in Asia large enough to be worth its own domain, and it "
             "falls INSIDE the European morning, which is what makes it visible in XBRUSD"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"market": "SGD interbank spot", "cycle": "T+2",
     "session_local": "the Asian session runs from about 07:00 SGT; SGD liquidity peaks "
                      "09:00-17:00 SGT",
     "session_utc": "01:00-09:00",
     "note": "SGD is fully convertible and freely deliverable, unlike almost every other "
             "currency in this department, which is why so much of Asia's restricted-currency "
             "risk is BOOKED here even though it is not deliverable here"},
    {"market": "SGX securities", "cycle": "T+2 since December 2018",
     "session_local": "09:00-17:00 SGT continuous, with no mid-day break since 2011",
     "session_utc": "01:00-09:00",
     "note": "the removal of the lunch break in 2011 is a break in every intraday SGX series "
             "that spans it"},
    {"market": "SGX derivatives", "cycle": "cash settled for index products",
     "session_local": "T session 09:00-16:30 SGT and T+1 session 17:00-05:15 SGT",
     "session_utc": "01:00-08:30 and 09:00-21:15",
     "note": "the T+1 session is the point of SGX: the China A50 and the Nikkei trade through "
             "the European and US hours when their home markets are shut, which makes SGX the "
             "venue where Asian equity risk gets repriced overnight"},
    {"market": "SGX iron ore", "cycle": "cash settled against a monthly index average",
     "session_local": "T and T+1 sessions", "session_utc": "01:00-21:15",
     "note": "because settlement is a MONTH AVERAGE, the whole month is the event and there is "
             "no expiry-day effect to find; a cell that looks for one is looking for something "
             "the contract design excludes"},
    {"market": "Singapore Government Securities and MAS bills", "cycle": "T+1",
     "session_local": "09:00-17:00 SGT", "session_utc": "01:00-09:00",
     "note": "issued for liquidity management rather than to fund a deficit, which is why the "
             "supply calendar carries no fiscal information"},
)

# --------------------------------------------------------------------------- exchanges
EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Singapore Exchange securities market", "code": "SGX-ST",
     "hours_local": "09:00-17:00 SGT, pre-open 08:30-09:00, closing auction 17:00-17:06",
     "hours_utc": "01:00-09:00",
     "expiry_rule": "n/a for cash",
     "settlement": "T+2",
     "rebalance": "FTSE Straits Times Index semi-annual review in March and September, effective "
                  "after the third Friday"},
    {"name": "SGX derivatives -- FTSE China A50 index futures", "code": "SGX-CN",
     "hours_local": "T 09:00-16:30 SGT, T+1 17:00-05:15 SGT",
     "hours_utc": "01:00-08:30 and 09:00-21:15",
     "expiry_rule": "the SECOND LAST business day of the contract month, which is unusual and is "
                    "NOT the third Friday most index contracts use",
     "settlement": "cash against the official FTSE China A50 closing index",
     "rebalance": "FTSE quarterly review in March, June, September and December"},
    {"name": "SGX derivatives -- Nikkei 225 index futures", "code": "SGX-NK",
     "hours_local": "T and T+1 sessions", "hours_utc": "01:00-08:30 and 09:00-21:15",
     "expiry_rule": "settles to the Osaka Special Quotation: the second Friday of March, June, "
                    "September and December, computed from the opening prices of the 225 "
                    "constituents",
     "settlement": "cash at the SQ",
     "rebalance": "Nikkei annual review in autumn plus ad hoc replacements"},
    {"name": "SGX commodities -- iron ore, rubber, freight", "code": "SGX-CO",
     "hours_local": "T and T+1 sessions", "hours_utc": "01:00-21:15",
     "expiry_rule": "monthly, cash settled against the AVERAGE of the underlying index over the "
                    "contract month, so there is no single settlement instant",
     "settlement": "cash against a monthly index average",
     "rebalance": "n/a"},
)

# --------------------------------------------------------------------------- the holiday rule
_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "New Year's Day",
        "2024-02-10": "Chinese New Year day 1",
        "2024-02-12": "Chinese New Year day 2 (in lieu of Sunday 11 February)",
        "2024-03-29": "Good Friday",
        "2024-04-10": "Hari Raya Puasa",
        "2024-05-01": "Labour Day",
        "2024-05-22": "Vesak Day",
        "2024-06-17": "Hari Raya Haji",
        "2024-08-09": "National Day",
        "2024-10-31": "Deepavali",
        "2024-12-25": "Christmas Day",
    },
    2025: {
        "2025-01-01": "New Year's Day",
        "2025-01-29": "Chinese New Year day 1",
        "2025-01-30": "Chinese New Year day 2",
        "2025-03-31": "Hari Raya Puasa",
        "2025-04-18": "Good Friday",
        "2025-05-01": "Labour Day",
        "2025-05-12": "Vesak Day",
        "2025-06-07": "Hari Raya Haji",
        "2025-08-09": "National Day",
        "2025-10-20": "Deepavali",
        "2025-12-25": "Christmas Day",
    },
    2026: {
        "2026-01-01": "New Year's Day",
        "2026-02-17": "Chinese New Year day 1",
        "2026-02-18": "Chinese New Year day 2",
        "2026-03-20": "Hari Raya Puasa",
        "2026-04-03": "Good Friday",
        "2026-05-01": "Labour Day",
        "2026-05-27": "Hari Raya Haji",
        "2026-06-01": "Vesak Day (in lieu of Sunday 31 May)",
        "2026-08-10": "National Day (in lieu of Sunday 9 August)",
        "2026-11-09": "Deepavali (in lieu of Sunday 8 November)",
        "2026-12-25": "Christmas Day",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": "Eleven gazetted public holidays under the Holidays Act. Five are fixed Gregorian "
            "dates (1 January, 1 May, 9 August, 25 December, and Labour Day's own fixed date); "
            "Good Friday follows the Western computus; Chinese New Year is the first two days of "
            "the Chinese lunisolar year; Vesak is the Vesakha full moon; Hari Raya Puasa and "
            "Hari Raya Haji follow the Islamic lunar calendar and are gazetted from local "
            "moon-sighting, so a computed Islamic date can differ from the gazetted one by a "
            "day; Deepavali follows the Hindu lunisolar calendar. THE SUBSTITUTION LAW IS THE "
            "PART THAT MATTERS FOR A SESSION MASK: when a gazetted holiday falls on a SUNDAY the "
            "following Monday is a holiday, and when it falls on a SATURDAY it is not "
            "substituted for most workers -- so a Saturday holiday produces no market closure at "
            "all and must not be counted as one.",
    "table": _HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED", 2025: "CONFIRMED",
               2026: "PROVISIONAL -- fixed dates and the substitution law are certain; Hari Raya "
                     "Puasa is carried at 20 March 2026 and may be gazetted a day later, and "
                     "Vesak's 2026 date should be checked against the gazette before use"},
    "special_sessions": "a general election polling day is gazetted as a public holiday at short "
                        "notice (3 May 2025 was one); it is a genuine closure and it is not in "
                        "any published annual calendar",
    "regional_note": "Chinese New Year closes Singapore, Malaysia, Hong Kong, China, Taiwan, "
                     "Korea and Vietnam within the same 48 hours, and 17 February 2026 is that "
                     "date for all of them. An Asian FX liquidity statistic measured across it "
                     "is measuring the whole region being shut",
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "MAS weekly S$NEER index level",
     "root": "https://www.mas.gov.sg/statistics/exchange-rates",
     "fields": ("S$NEER index level",),
     "frequency": "weekly", "publish_utc": "09:00", "lag_days": 7, "licence": "free, public",
     "why": "the only official read on where the basket sits. It does NOT give the band, so the "
            "position within the band is still an inference -- which is the whole research "
            "problem and is stated here rather than hidden"},
    {"name": "MAS official foreign reserves and net forward position",
     "root": "https://www.mas.gov.sg/statistics/reserve-statistics",
     "fields": ("official foreign reserves", "net forward position", "SDR and IMF positions"),
     "frequency": "monthly", "publish_utc": "09:00", "lag_days": 30, "licence": "free, public",
     "why": "an intervention observable, and one of the very few in this region that includes "
            "the FORWARD book rather than spot alone"},
    {"name": "SGX monthly market statistics report",
     "root": "https://www.sgx.com/research-education/market-statistics",
     "fields": ("derivatives volume and open interest by contract", "securities turnover",
                "iron ore and rubber volumes"),
     "frequency": "monthly", "publish_utc": "04:00", "lag_days": 5, "licence": "free, public",
     "why": "open interest in the A50 and Nikkei contracts is the cleanest public measure of "
            "offshore hedging demand for Chinese and Japanese equity risk"},
    {"name": "CFTC Commitments of Traders",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("non-commercial net in USD index, JPY, AUD, gold, crude",),
     "frequency": "weekly", "publish_utc": "20:30", "lag_days": 3, "licence": "free, public",
     "why": "SGD is not in the COT. The dollar index and yen legs are the external factor every "
            "SGD basket claim must be residualised against"},
    {"name": "MAS monetary policy statements and the accompanying macroeconomic review",
     "root": "https://www.mas.gov.sg/news/monetary-policy-statements",
     "fields": ("the policy sentence", "slope, width and centre language",
                "the core inflation forecast range"),
     "frequency": "quarterly", "publish_utc": "00:00", "lag_days": 0, "licence": "free, public",
     "why": "the statement's LANGUAGE is the policy variable, because the parameters are not "
            "published; a text feature set is the only way to read the band state at the event"},
    {"name": "Singapore Department of Statistics trade and NODX",
     "root": "https://www.singstat.gov.sg/find-data/search-by-theme/trade-and-investment",
     "fields": ("non-oil domestic exports by market and product", "electronics NODX"),
     "frequency": "monthly", "publish_utc": "00:30", "lag_days": 17, "licence": "free, public",
     "why": "NODX at 08:00 SGT on about the 17th is one of the earliest reads on the Asian trade "
            "cycle each month and is published before Korea's full-month figure"},
)

# --------------------------------------------------------------------------- terminology
#: Singapore's four official languages, and all four appear in market commentary: Chinese for the
#: retail and mainland-facing press, Malay for the regional press, English for everything
#: institutional. A miner searching only in English misses Lianhe Zaobao entirely.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "SG-A": ("新加坡金融管理局", "货币政策声明", "名义有效汇率", "政策区间", "斜率", "重新定中",
             "收紧", "宽松", "dasar monetari", "kadar tukaran", "policy band", "re-centring"),
    "SG-B": ("核心通胀", "整体通胀", "通胀预期", "inflasi teras", "core inflation",
             "MAS Core CPI"),
    "SG-C": ("新元", "汇率", "篮子货币", "区间上限", "区间下限", "dolar Singapura",
             "band top", "band floor", "synthetic NEER"),
    "SG-D": ("亚洲货币", "区域货币", "无本金交割远期", "定盘价", "mata wang serantau",
             "NDF fixing", "ABS benchmark"),
    "SG-E": ("新元利率", "隔夜利率", "流动性", "kecairan", "SORA", "swap basis"),
    "SG-F": ("新交所", "期货", "到期", "未平仓合约", "A50", "日经", "niaga hadapan",
             "SGX expiry", "open interest"),
    "SG-G": ("铁矿石", "橡胶", "运费", "bijih besi", "getah", "iron ore", "TSR20"),
    "SG-H": ("石油", "船用燃料", "加油", "炼油利润", "minyak", "bunker", "MOPS", "crack spread"),
    "SG-I": ("非石油国内出口", "电子产品", "贸易", "eksport", "elektronik", "NODX"),
    "SG-J": ("外汇储备", "干预", "远期头寸", "rizab", "reserves", "forward book"),
    "SG-K": ("农历新年", "假期", "流动性不足", "Tahun Baru Cina", "Hari Raya Puasa",
             "cuti umum", "holiday liquidity"),
    "SG-L": ("财富管理", "家族办公室", "资金流入", "pengurusan kekayaan", "family office",
             "wealth inflow"),
}

# --------------------------------------------------------------------------- the source layers
#: THE TEN SOURCE LAYERS (principal's per-country depth rule, 2026-09-17). A country is never
#: "covered" by five obvious sources. Every layer below is either POPULATED or named in
#: `ABSENT_SOURCE_LAYERS` with a reason; blank is not an option, because a blank layer is
#: indistinguishable from a layer nobody looked at.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology",
    "app_ecosystem", "media", "archive", "physical_economy", "source_graph")

#: The three INDEPENDENT labels every source carries. Independent on purpose: an AUTHORITATIVE
#: source can be NOT_PREDICTIVE and a FRINGE one can be PREDICTIVE. Collapsing them into a single
#: "quality" score is how a desk quietly stops looking at the material that disagrees with it.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")
CREDIBILITY_LABELS: tuple[str, ...] = (
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")
PREDICTIVE_STATES: tuple[str, ...] = (
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE")


def _src(sid: str, label: str, *, layer: str, roots: Sequence[str], languages: Sequence[str],
         licence: str, access_label: str, credibility: str, predictive_state: str,
         queries: Sequence[str] = (), machine_use_allowed: bool = True,
         notes: str = "") -> dict[str, Any]:
    """One source class: the framework's row, plus its layer, its three labels and its queries.

    `research.countries.source_class` owns the base shape and this adds the depth-rule fields on
    top rather than replacing it, so a consumer that only knows the base shape still reads these
    rows correctly.

    `machine_use_allowed=True` means the terms of the page FORBID automated extraction. Such a
    source is REGISTERED and never scraped: it stays visible so a later session knows the material
    exists and knows why the desk has not read it, which is the opposite of omitting it.

    `queries` are the NATIVE-SCRIPT search strings for this layer, including slang. A translated
    English query against a native-language board returns nothing, and returning nothing is
    indistinguishable from the question never having been asked.
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"{sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"{sid}: access_label {access_label!r} unknown")
    if credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"{sid}: credibility {credibility!r} unknown")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"{sid}: predictive_state {predictive_state!r} unknown")
    row = source_class(sid, label, roots=roots, languages=languages, licence=licence, notes=notes)
    row.update({"layer": layer, "access_label": access_label, "credibility": credibility,
                "predictive_state": predictive_state,
                "machine_use_allowed": bool(machine_use_allowed), "queries": tuple(queries)})
    return row


#: Layers with no source in this pack, each with the reason. Empty: all ten are populated.
ABSENT_SOURCE_LAYERS: dict[str, str] = {}

SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    _src("SG-S1", "MAS and the official statistical system", layer="official",
         roots=("https://www.mas.gov.sg/news/monetary-policy-statements",
                "https://www.mas.gov.sg/publications/macroeconomic-review",
                "https://www.mas.gov.sg/statistics", "https://www.singstat.gov.sg/",
                "https://www.mti.gov.sg/", "https://www.mof.gov.sg/singaporebudget"),
         languages=("en",), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("monetary policy statement slope", "S$NEER index weekly",
                  "货币政策声明", "NODX advance estimate"),
         notes="the statement at 00:00 UTC, the Macroeconomic Review where MAS comes closest to "
               "describing the band without publishing it, and the weekly S$NEER level"),
    _src("SG-S2", "SGX, the benchmark administrator and the multilaterals",
         layer="institutional",
         roots=("https://www.sgx.com/derivatives/products",
                "https://www.sgx.com/research-education/market-statistics",
                "https://abs.org.sg/benchmarks-fx", "https://www.bis.org/publ/",
                "https://www.imf.org/en/Countries/SGP"),
         languages=("en",), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("SGX A50 contract specifications expiry", "ABS benchmarks Asian FX fixing",
                  "iron ore futures settlement index average", "IMF Article IV Singapore band"),
         notes="the contract specifications carry the expiry rules SG-G depends on, and the IMF "
               "staff reports routinely carry an ESTIMATE of the band parameters MAS itself will "
               "not publish"),
    _src("SG-S3", "academic work on band regimes", layer="academic",
         roots=("https://www.mas.gov.sg/publications/staff-papers",
                "https://fass.nus.edu.sg/ecs/research/",
                "https://economics.smu.edu.sg/research", "https://www.nber.org/papers"),
         languages=("en",), licence="free, public", access_label="PUBLIC",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("S$NEER band estimation slope width", "exchange rate policy Singapore BBC band",
                  "monetary policy without an interest rate"),
         notes="the band's parameters are estimated in the literature and not published by MAS, "
               "so the academic layer here is not background reading -- it is the only place a "
               "PRIOR for SG-C's latent state comes from"),
    _src("SG-S4", "bank research and the professional community", layer="practitioner",
         roots=("https://www.dbs.com/insights/", "https://www.ocbc.com/group/research",
                "https://www.uobgroup.com/web-resources/uobgroup/pdf/research/",
                "https://www.cfasingapore.org/"),
         languages=("en", "zh"), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("SGD NEER estimate bank research", "新元汇率展望",
                  "MAS policy preview slope", "SORA outlook"),
         notes="the three local banks publish their own S$NEER ESTIMATES publicly, which is the "
               "single most useful practitioner output in this department: it is an independent "
               "reconstruction of the same latent state SG-C is trying to build"),
    _src("SG-S5", "retail investor forums and personal finance communities",
         layer="retail_ecology",
         roots=("https://forums.hardwarezone.com.sg/forums/money-mind.170/",
                "https://www.reddit.com/r/singaporefi/",
                "https://www.reddit.com/r/singaporeraw/", "https://blog.seedly.sg/"),
         languages=("en", "zh"), licence="public web; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("T-bill cut off yield rumour", "SSB allotment", "定期存款 "
                  "利率", "SGD fixed deposit rate chase", "CPF OA transfer"),
         notes="Singapore retail chases T-bill and fixed-deposit yield in a way that is visible "
               "in auction cut-offs, so this layer is a genuine leading indicator of domestic "
               "deposit competition -- UNRELIABLE individually and informative in aggregate"),
    _src("SG-S6", "trading and wealth apps and their public documentation",
         layer="app_ecosystem",
         roots=("https://www.tigerbrokers.com.sg/", "https://www.moomoo.com/sg",
                "https://www.syfe.com/", "https://endowus.com/",
                "https://www.interactivebrokers.com.sg/"),
         languages=("en", "zh"), licence="public web; API and platform terms vary",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("SGX access fees retail app", "新加坡 券商 "
                  "开户", "robo advisor SGD allocation", "cash management account yield"),
         notes="ACCESS_UNCLEAR is deliberate: these platforms publish rate cards and product "
               "pages openly and their API terms are not uniformly stated, so each root must be "
               "checked before any automated collection rather than assumed"),
    _src("SG-S7", "Singapore media in four languages", layer="media",
         roots=("https://www.businesstimes.com.sg/", "https://www.channelnewsasia.com/business",
                "https://www.straitstimes.com/business",
                "https://www.zaobao.com.sg/realtime/finance",
                "https://www.beritaharian.sg/"),
         languages=("en", "zh", "ms"), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("金管局 收紧", "新元 汇率 走势",
                  "dasar monetari MAS", "kadar tukaran dolar Singapura",
                  "eksport bukan minyak", "belanjawan Singapura",
                  "pelabur asing pasaran saham", "MAS tightens policy band"),
         notes="Lianhe Zaobao is read across the region and carries policy commentary that never "
               "appears in the English press; Berita Harian is the Malay-language channel into "
               "the Malaysian and Indonesian story where several SG edges terminate"),
    _src("SG-S8", "the national archive, Hansard and the web archive", layer="archive",
         roots=("https://eresources.nlb.gov.sg/newspapers/",
                "https://sprs.parl.gov.sg/search/home",
                "https://www.mas.gov.sg/news?content_type=Monetary%20Policy%20Statements",
                "https://web.archive.org/web/*/mas.gov.sg*"),
         languages=("en", "zh", "ms"), licence="free, public", access_label="PUBLIC_ARCHIVE",
         credibility="AUTHORITATIVE", predictive_state="NOT_PREDICTIVE",
         queries=("MAS statement archive 2001 slope", "parliamentary question exchange rate policy",
                  "NewspaperSG monetary policy band"),
         notes="the full MPS archive back to the 1980s is what makes an era table possible at "
               "all, and parliamentary answers are where MAS has been pressed to describe the "
               "band in more detail than it does voluntarily. NOT_PREDICTIVE: an archive dates"),
    _src("SG-S9", "the physical economy: port, bunkers, power and cargo",
         layer="physical_economy",
         roots=("https://www.mpa.gov.sg/port-marine-ops/port-statistics",
                "https://www.changiairport.com/corporate/our-expertise/air-hub/traffic-statistics",
                "https://www.ema.gov.sg/resources/statistics",
                "https://www.psa.com.sg/"),
         languages=("en",), licence="free, public", access_label="OPEN_DATA",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("bunker sales volume monthly MPA", "container throughput TEU Singapore",
                  "electricity demand half hourly", "vessel arrival tonnage"),
         notes="the world's largest bunkering port and one of its largest container ports publish "
               "their PHYSICAL volumes monthly and free. This is a global-trade observable "
               "produced by a port authority rather than by a bank, and it is the upstream end "
               "of SG-H"),
    _src("SG-S10", "the source graph: registries and the multilateral mirrors",
         layer="source_graph",
         roots=("https://data.gov.sg/", "https://data.worldbank.org/country/singapore",
                "https://comtradeplus.un.org/", "https://stats.bis.org/"),
         languages=("en",), licence="open data", access_label="OPEN_DATA",
         credibility="RELIABLE", predictive_state="NOT_PREDICTIVE",
         queries=("data.gov.sg dataset catalogue", "BIS effective exchange rate Singapore",
                  "Comtrade Singapore re-exports"),
         notes="THE META LAYER, and Singapore is the case where it matters most: BIS publishes "
               "its OWN trade-weighted effective exchange rate for the Singapore dollar, computed "
               "from different weights than MAS uses, so the source graph is how the desk "
               "discovers that two authoritative NEERs for the same currency disagree"),
    _src("SG-S11", "licensed commodity assessments", layer="institutional",
         roots=("https://www.spglobal.com/commodityinsights/en/our-methodology/"
                "methodology-specifications", "https://www.argusmedia.com/en/methodology"),
         languages=("en",), licence="methodology free; the assessments are licensed",
         access_label="LICENSED", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         machine_use_allowed=True,
         notes="REGISTERED AND NOT SCRAPED. The 08:30 UTC MOC assessments are what SG-H is "
               "actually about and the terms forbid automated extraction. The METHODOLOGY is "
               "free and is what the pack uses: the window's timing and rules, against which "
               "XBRUSD's own behaviour inside 08:00-08:30 UTC can be measured"),
    _src("SG-S12", "finfluencer and chat-channel chatter", layer="retail_ecology",
         roots=("https://t.me/s/", "https://www.youtube.com/results?search_query=",
                "https://www.tiktok.com/search"),
         languages=("en", "zh"), licence="public social; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("MAS will devalue SGD", "新元 崩盘", "SGD peg break",
                  "guaranteed SGD yield"),
         notes="FRINGE AND KEPT. Recurrent claims that MAS is about to abandon or break the band "
               "are almost always wrong and occasionally cluster right before a re-centring, "
               "because the same pressure drives both. Held as a low-weight sentiment object "
               "with the FRINGE label attached, never promoted to a fact, never deleted"),
)

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("MAS weekly S$NEER index", source="Monetary Authority of Singapore",
            coverage="2021-", frequency="weekly", publication_lag_days=7, revisions="none",
            licence="free, public", history_from="2021-01-01", pit_feasible=True,
            assets=("USDSGD", "EURSGD", "SGDJPY"),
            mechanism_families=("policy_state", "band_position"),
            how_to_fetch="the MAS exchange-rate statistics page; note that the series begins only "
                         "in the 2020s, so a long-history band study must reconstruct the index "
                         "from trade weights and cannot use this"),
    dataset("MAS monetary policy statements", source="Monetary Authority of Singapore",
            coverage="2000-", frequency="quarterly since 2024, semi-annual before",
            publication_lag_days=0, revisions="none", licence="free, public",
            history_from="2000-01-01", pit_feasible=True,
            assets=("USDSGD", "SGDJPY", "EURSGD"),
            mechanism_families=("policy_event", "tone"),
            how_to_fetch="the media-release archive at 08:00 SGT (00:00 UTC); the CADENCE CHANGE "
                         "in 2024 doubles the event count and halves the average surprise, which "
                         "is a break in any event-study sample that spans it"),
    dataset("MAS official foreign reserves and net forward position",
            source="Monetary Authority of Singapore", coverage="1991-", frequency="monthly",
            publication_lag_days=30, revisions="rare", licence="free, public",
            history_from="1991-01-01", pit_feasible=True, assets=("USDSGD", "USDX"),
            mechanism_families=("intervention", "reserve_adequacy"),
            how_to_fetch="the reserve statistics page on the 7th business day; the forward "
                         "position is published alongside, which is unusual in this region"),
    dataset("SORA daily", source="Monetary Authority of Singapore", coverage="2005-",
            frequency="daily", publication_lag_days=1, revisions="none", licence="free, public",
            history_from="2005-07-01", pit_feasible=True, assets=("USDSGD",),
            mechanism_families=("funding", "fx_swap_basis"),
            how_to_fetch="published 09:00 SGT for the PREVIOUS business day, so it is knowable "
                         "one session late and never intraday"),
    dataset("Singapore non-oil domestic exports (NODX)",
            source="Enterprise Singapore / SingStat", coverage="1976-", frequency="monthly",
            publication_lag_days=17, revisions="routine prior-month revision",
            licence="free, public", history_from="1990-01-01", pit_feasible=True,
            assets=("USDSGD", "USDKRW", "JPN225"),
            mechanism_families=("trade_cycle", "electronics_cycle"),
            how_to_fetch="08:00 SGT on about the 17th; one of the earliest monthly reads on the "
                         "Asian trade cycle"),
    dataset("MAS Core CPI and headline CPI", source="MAS / SingStat", coverage="1990-",
            frequency="monthly", publication_lag_days=23, revisions="rare",
            licence="free, public", history_from="1990-01-01", pit_feasible=True,
            assets=("USDSGD",), mechanism_families=("inflation", "policy_reaction"),
            how_to_fetch="MAS Core CPI excludes accommodation and private transport, which is "
                         "what MAS actually targets; a cell built on HEADLINE CPI is not modelling "
                         "the reaction function"),
    dataset("SGX derivatives volume and open interest",
            source="Singapore Exchange", coverage="2010-", frequency="monthly",
            publication_lag_days=5, revisions="none", licence="free, public",
            history_from="2010-01-01", pit_feasible=True, assets=("CHINAH", "JPN225", "HK50"),
            mechanism_families=("hedging_demand", "expiry"),
            how_to_fetch="the monthly market statistics report; daily volume is available on the "
                         "contract pages but without the same history"),
    dataset("Singapore GDP advance estimate",
            source="Ministry of Trade and Industry", coverage="1975-", frequency="quarterly",
            publication_lag_days=14, revisions="substantially revised at the full release",
            licence="free, public", history_from="1990-01-01", pit_feasible=True,
            assets=("USDSGD",), mechanism_families=("growth", "policy_reaction"),
            how_to_fetch="published within about two weeks of the quarter end, days before the "
                         "January, April, July and October MPS -- so the advance estimate is a "
                         "PRE-EVENT for the policy statement and is the tradable half"),
    dataset("Singapore bunker sales volume", source="Maritime and Port Authority",
            coverage="2005-", frequency="monthly", publication_lag_days=20,
            revisions="none", licence="free, public", history_from="2005-01-01",
            pit_feasible=True, assets=("XTIUSD", "XBRUSD"),
            mechanism_families=("physical_demand", "shipping_cycle"),
            how_to_fetch="the MPA port statistics page; the world's largest bunkering port "
                         "publishing its physical volume is a genuine free demand observable"),
    dataset("ABS/SFEMC Asian currency fixings", source="ABS Benchmarks Administration Co",
            coverage="2005-", frequency="daily", publication_lag_days=0, revisions="none",
            licence="free to view, redistribution restricted", history_from="2005-01-01",
            pit_feasible=True, assets=("USDIDR", "USDTHB", "USDINR"),
            mechanism_families=("fixing", "ndf_settlement"),
            how_to_fetch="the ABS benchmarks page at about 11:00 SGT; this is the row that ties "
                         "this pack to six others"),
    dataset("MAS Macroeconomic Review", source="Monetary Authority of Singapore",
            coverage="2002-", frequency="semi-annual", publication_lag_days=0,
            revisions="none", licence="free, public", history_from="2002-01-01",
            pit_feasible=True, assets=("USDSGD",), mechanism_families=("policy_tone",),
            how_to_fetch="published alongside the April and October statements; the special "
                         "features are where MAS explains its own framework and are the best "
                         "public description of how the band is operated"),
    dataset("IMF Article IV consultation for Singapore", source="International Monetary Fund",
            coverage="1990-", frequency="annual", publication_lag_days=60,
            revisions="none", licence="free, public", history_from="1990-01-01",
            pit_feasible=True, assets=("USDSGD",), mechanism_families=("policy_state",),
            how_to_fetch="imf.org publication search; the staff report routinely carries an "
                         "estimate of the band's parameters, which MAS itself does not publish"),
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor(
        "MAS Monetary and Domestic Markets Management Department",
        holds="the official foreign reserves and the operational mandate to keep the S$NEER "
              "inside an undisclosed band",
        forced_to=("buy dollars when the basket presses the band's strong side",
                   "sell dollars when it presses the weak side",
                   "do so without publishing the band, so the intervention is inferable only "
                   "from the reserve print and from price action at the inferred edge"),
        when="continuously through the 01:00-09:00 UTC Singapore session, with the statement "
             "itself at 00:00 UTC",
        information=("its own band parameters", "interbank flow it sees as the reserve manager",
                     "the core inflation forecast that sets the slope"),
        constraints=("a medium-term price stability mandate expressed through the exchange rate",
                     "the impossible trinity: with an open capital account and a managed "
                     "exchange rate, SGD interest rates are an OUTPUT and MAS has no lever over "
                     "them",
                     "reserve adequacy and the political cost of visible losses"),
        instruments=("USDSGD", "EURSGD", "SGDJPY", "AUDSGD"),
        counterparties=("the global bank FX community", "regional corporates invoicing in SGD",
                        "reserve managers rebalancing into SGD"),
        observables=("the weekly S$NEER index level", "monthly reserves and the forward book",
                     "the qualitative language of each statement",
                     "price behaviour at the market's ESTIMATE of the band edge"),
        impact="truncates the SGD's distribution at both ends of a corridor whose position is "
               "unknown, which produces mean reversion toward an unobserved centre -- the most "
               "commonly mis-fitted feature of this currency, because a cell that mean-reverts "
               "to a rolling average is reverting to the wrong thing",
        persistence="the framework has been in place since 1981 and has survived four crises; "
                    "the SLOPE and CENTRE move several times a decade and each move is an era",
        falsifier="a quarter in which the estimated S$NEER breaches the inferred band edge by "
                  "more than the estimation error and MAS neither intervenes nor re-centres "
                  "would say the band estimate, not the framework, is wrong"),
    actor(
        "MAS money market and liquidity operations",
        holds="the SGD money market's reserve balances, managed through MAS bills, SGS and FX "
              "swaps",
        forced_to=("sterilise the domestic liquidity consequence of every FX intervention",
                   "keep SORA anchored near where the covered parity implied by the band puts it"),
        when="daily, with auctions concentrated in the 01:00-06:00 UTC morning",
        information=("banking system liquidity", "its own intervention that day"),
        constraints=("no policy rate to set, so every rate outcome must be delivered through "
                     "quantity operations",
                     "the covered interest parity relationship with USD rates"),
        instruments=("USDSGD", "USDX"),
        counterparties=("primary dealers", "the local bank treasuries"),
        observables=("SORA against the parity-implied rate", "MAS bill auction sizes and cut-offs",
                     "the FX swap basis"),
        impact="the FX swap basis becomes a direct read on how hard the band is being defended, "
               "because sterilisation volume and intervention volume are the same number seen "
               "twice",
        persistence="structural and mechanical, following from the framework",
        falsifier="a period in which SORA diverges persistently from the covered-parity implied "
                  "rate with no change in the FX swap basis"),
    actor(
        "GIC and Temasek",
        holds="sovereign portfolios that are overwhelmingly foreign-currency denominated",
        forced_to=("rebalance across asset classes on internal schedules",
                   "fund domestic commitments in SGD from foreign assets"),
        when="episodic and undisclosed; Temasek's review is published in July and GIC's in July "
             "as well",
        information=("their own asset allocation", "the government's funding needs"),
        constraints=("the Net Investment Returns Contribution framework, which caps how much of "
                     "expected long-term returns the Budget may spend",
                     "no obligation to disclose positions"),
        instruments=("USDSGD", "US500", "HK50"),
        counterparties=("global asset managers", "MAS, which manages a separate reserve pool"),
        observables=("the annual reviews in July",
                     "the Net Investment Returns Contribution line in the February Budget"),
        impact="a very large, slow, undisclosed SGD demand that shows up as a level effect rather "
               "than a flow effect; it is a reason the SGD is structurally strong and is NOT a "
               "tradable timing signal, which is exactly why it is listed with that caveat",
        persistence="structural and permanent",
        falsifier="a year in which the NIRC line falls with no change in either portfolio's "
                  "reported returns"),
    actor(
        "The Central Provident Fund and the domestic savings sink",
        holds="compulsory retirement savings of essentially the entire resident workforce, "
              "invested in non-tradable Special Singapore Government Securities",
        forced_to=("absorb contributions every month regardless of market conditions",
                   "pay a statutory minimum interest rate"),
        when="monthly on payroll dates",
        information=("contribution rates set by statute",),
        constraints=("investment restricted to government securities issued to it directly",
                     "statutory minimum rates that do not float with the market"),
        instruments=("USDSGD",),
        counterparties=("the Government of Singapore, which on-lends to GIC",),
        observables=("CPF monthly statistics", "SSGS outstanding in the government accounts"),
        impact="removes a large fraction of domestic savings from the tradable market, which is "
               "why Singapore runs a huge current account surplus with a small, illiquid domestic "
               "bond market -- and therefore why SGD rates are set offshore",
        persistence="statutory and permanent",
        falsifier="a sustained fall in CPF net contributions with no demographic explanation"),
    actor(
        "Singapore bank treasuries",
        holds="the SGD funding book for the region, and the largest share of SGD interbank "
              "liquidity",
        forced_to=("fund SGD assets with SGD liabilities or with FX swaps",
                   "square the book into the 09:00 UTC close"),
        when="the Singapore session, with a concentration into the 08:00-09:00 UTC close",
        information=("their own client flow", "the regional corporate order book"),
        constraints=("liquidity coverage and net stable funding requirements",
                     "MAS supervisory limits"),
        instruments=("USDSGD", "SGDJPY", "USDCNH"),
        counterparties=("regional corporates", "global banks", "MAS"),
        observables=("the FX swap basis", "SORA", "quarterly bank statistics"),
        impact="the transmission point between MAS's quantity operations and the price a "
               "foreigner sees in USDSGD",
        persistence="structural",
        falsifier="a quarter in which the SGD swap basis moves with no corresponding change in "
                  "domestic liquidity or in USD funding conditions"),
    actor(
        "The Asian non-deliverable forward market-making community",
        holds="the offshore risk book for IDR, MYR, PHP, THB, INR, KRW, TWD, VND and CNY, booked "
              "predominantly in Singapore even though none of those currencies is deliverable "
              "here",
        forced_to=("settle against the ABS/SFEMC fixings at 03:00 UTC",
                   "hedge the fixing exposure into the fixing window"),
        when="03:00 UTC daily, with the largest exposure on month-end and on option expiry dates",
        information=("their own fixing exposure", "onshore liquidity conditions in each currency"),
        constraints=("onshore central bank restrictions on offshore participation",
                     "the fixings' own methodology"),
        instruments=("USDIDR", "USDTHB", "USDINR", "USDKRW", "USDCNH"),
        counterparties=("real-money EM investors", "onshore banks", "the regional central banks"),
        observables=("the ABS fixings themselves", "onshore-offshore basis in each currency",
                     "NDF-implied yields"),
        impact="makes 03:00 UTC a REGIONAL event: several restricted currencies settle at the "
               "same instant, which means an apparent single-currency fixing effect must be "
               "checked against the whole set before it is called a country effect",
        persistence="structural; the set of currencies changes slowly as convertibility changes",
        falsifier="a fixing-window effect present in one currency and in none of the other eight "
                  "would be a genuine country effect, and its absence in all nine would retire "
                  "the domain"),
    actor(
        "SGX FTSE China A50 arbitrageurs",
        holds="the basis between offshore A50 futures and the onshore CSI 300 or A-share basket",
        forced_to=("carry the basis through the T+1 session, when the onshore market is shut",
                   "unwind into the second-last business day settlement"),
        when="the T+1 session, 09:00-21:15 UTC, and the monthly settlement",
        information=("Stock Connect quota usage", "onshore closing prices",
                     "CNH funding cost"),
        constraints=("Stock Connect daily quotas and its own trading-day calendar, which differs "
                     "from both exchanges'",
                     "onshore short-selling restrictions"),
        instruments=("CHINAH", "HK50", "USDCNH"),
        counterparties=("global macro funds hedging China exposure",
                        "onshore and Hong Kong market makers"),
        observables=("A50 open interest", "the futures basis", "Stock Connect net flow"),
        impact="the A50's T+1 session is where Chinese equity risk is repriced overnight, which "
               "is the mechanism behind the HK50 and CHINAH gap at the next Asian open",
        persistence="structural while the onshore market stays closed to direct foreign shorting",
        falsifier="an overnight A50 move that does not survive into the next HK50 open, "
                  "repeatedly"),
    actor(
        "Singapore-domiciled commodity trading houses",
        holds="physical oil, refined product, palm oil, grains and metals in transit through the "
              "Straits, financed in dollars",
        forced_to=("mark to the Platts Singapore assessments",
                   "hedge the paper leg into the 08:00-08:30 UTC MOC window"),
        when="the MOC window at 08:00-08:30 UTC, daily",
        information=("physical cargo positions", "freight rates", "regional refinery runs"),
        constraints=("trade finance limits from the regional banks",
                     "the assessment methodology itself, which rewards showing a bid or offer "
                     "in the window"),
        instruments=("XTIUSD", "XBRUSD", "XNGUSD"),
        counterparties=("Asian refiners", "Middle Eastern producers", "Chinese and Indian buyers"),
        observables=("Dubai and Brent-Dubai EFS assessments", "regional product cracks",
                     "Singapore onshore product stocks published weekly"),
        impact="concentrates Asian physical oil price discovery into one half hour that falls "
               "inside the European morning, which is when it becomes visible in XBRUSD",
        persistence="structural; the MOC methodology has been in place for decades",
        falsifier="no measurable difference in XBRUSD behaviour inside the 08:00-08:30 UTC window "
                  "against the adjacent half hours, measured across a year"),
    actor(
        "The Singapore bunker market",
        holds="the physical marine fuel demand of the world's largest bunkering port, above "
              "50 million tonnes a year",
        forced_to=("buy product continuously because ships must refuel",
                   "comply with the IMO sulphur cap, which forced a fuel-grade switch in 2020"),
        when="continuous, with volumes published monthly",
        information=("vessel arrival schedules", "regional refinery output"),
        constraints=("MPA licensing and mass-flow-metering rules",
                     "IMO environmental regulation"),
        instruments=("XTIUSD", "XBRUSD"),
        counterparties=("shipowners", "refiners", "traders"),
        observables=("MPA monthly bunker sales volume", "the marine fuel 0.5% assessment",
                     "vessel arrival counts"),
        impact="a genuinely free, monthly, physical demand series that correlates with global "
               "trade volume and is published by a port authority rather than by a bank",
        persistence="structural; the 2020 IMO sulphur cap is a break in the GRADE mix and not in "
                    "the total",
        falsifier="a year in which bunker volume rises while global container throughput falls"),
    actor(
        "Family offices and the wealth-management inflow",
        holds="assets under management that roughly doubled in the five years to 2024 as regional "
              "wealth relocated",
        forced_to=("convert some part of an inflow into SGD for local spending and property",
                   "comply with the tax-incentive conditions attached to the 13O and 13U schemes"),
        when="episodic, with a visible surge in 2020-2023",
        information=("regulatory scheme conditions", "regional political risk"),
        constraints=("MAS's tightening of the family-office incentive criteria",
                     "additional buyer's stamp duty on residential property, raised sharply in "
                     "April 2023"),
        instruments=("USDSGD",),
        counterparties=("private banks", "the domestic property market"),
        observables=("MAS AUM survey", "family office counts",
                     "residential property price index"),
        impact="a structural SGD bid that is not in the trade data and not in the portfolio flow "
               "data, which is one reason the SGD has been persistently stronger than a "
               "trade-weighted model implies",
        persistence="policy-dependent: the 2023 stamp-duty change and the 2023-24 tightening of "
                    "incentive criteria both slowed it, and both are datable",
        falsifier="a year of falling AUM with an unchanged incentive regime"),
    actor(
        "Regional corporates invoicing and funding in SGD",
        holds="SGD-denominated receivables, payables and bond issuance from across Southeast Asia",
        forced_to=("hedge SGD exposure through the deliverable forward market",
                   "roll SGD funding at issue maturity"),
        when="issuance clusters in January and after each MPS; hedging rolls at quarter end",
        information=("the SGD curve", "their own regional cash flows"),
        constraints=("SGD bond market depth, which is small relative to the currency's use",
                     "credit ratings"),
        instruments=("USDSGD", "SGDJPY"),
        counterparties=("Singapore bank treasuries", "regional investors"),
        observables=("SGD bond issuance volume", "the deliverable forward curve"),
        impact="gives the SGD a regional funding role disproportionate to Singapore's size, which "
               "is the mechanism behind SGD's usefulness as a proxy for the ASEAN complex",
        persistence="structural and growing",
        falsifier="a year in which SGD-denominated regional issuance falls while the currency's "
                  "correlation with the ASEAN complex is unchanged"),
    actor(
        "The Singapore electronics and precision engineering export sector",
        holds="a semiconductor and equipment export book plugged directly into the global chip "
              "cycle",
        forced_to=("ship on the customer's schedule", "convert dollar receipts"),
        when="monthly, with NODX published at 00:30 UTC on about the 17th",
        information=("customer order books", "the global semiconductor cycle"),
        constraints=("export controls on advanced equipment",
                     "a very high import content, so gross exports overstate the domestic value "
                     "added and the FX effect"),
        instruments=("USDSGD", "USDKRW", "JPN225"),
        counterparties=("Chinese, US and Korean buyers", "equipment makers"),
        observables=("NODX electronics", "the Singapore PMI and the electronics PMI",
                     "regional chip billings"),
        impact="NODX on the 17th is one of the earliest monthly reads on the Asian trade cycle, "
               "which makes it a leading indicator for the Korean and Taiwanese prints",
        persistence="cyclical with the semiconductor cycle; the SHARE of the economy has fallen "
                    "over two decades, so a coefficient fitted on the 2000s is too large",
        falsifier="a quarter of falling NODX electronics with rising Korean chip exports"),
    actor(
        "MAS as a macroprudential and property regulator",
        holds="the levers over the domestic property market that substitute for an interest rate",
        forced_to=("act on housing affordability without a policy rate",
                   "coordinate with the Ministry of National Development on supply"),
        when="announcements arrive without notice, usually late in the evening local time",
        information=("the private residential property price index",
                     "transaction volumes and loan-to-value data"),
        constraints=("no interest rate lever",
                     "political sensitivity of housing costs"),
        instruments=("USDSGD",),
        counterparties=("domestic and foreign buyers", "the banks"),
        observables=("additional buyer's stamp duty rates", "total debt servicing ratio limits",
                     "the quarterly property price index"),
        impact="the macroprudential lever exists BECAUSE the rate lever does not, which is a "
               "consequence of the band framework and is a genuinely Singaporean causal chain: "
               "domestic overheating is met with a tax, not a rate",
        persistence="structural while the framework stands; individual measures are dated",
        falsifier="a domestic overheating episode met with an SGD rate response rather than a "
                  "macroprudential one"),
    actor(
        "Foreign reserve managers and the SGD's official-sector bid",
        holds="SGD allocations in official reserve portfolios, small in absolute terms and large "
              "relative to the SGS market",
        forced_to=("buy SGS to hold SGD, because the tradable SGD money market is thin",
                   "rebalance on benchmark schedules"),
        when="quarterly benchmark rebalancing",
        information=("IMF COFER allocations", "index composition"),
        constraints=("SGS market depth, which is deliberately limited because Singapore does not "
                     "borrow to fund a deficit",),
        instruments=("USDSGD",),
        counterparties=("primary dealers", "MAS"),
        observables=("foreign holdings of SGS", "IMF COFER 'other currencies' line"),
        impact="a small bid meeting a deliberately small supply, which amplifies the price impact "
               "per dollar of official demand far beyond what Singapore's economic size suggests",
        persistence="structural and slowly growing",
        falsifier="a rise in foreign SGS holdings with no move in the SGS-swap spread"),
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("SG-A", "The monetary policy statement as an event at 00:00 UTC",
           objects=("the quarterly statement since 2024 and the semi-annual one before",
                    "the three off-cycle statements of 2020 and 2022",
                    "the qualitative policy sentence",
                    "the accompanying Macroeconomic Review in April and October",
                    "the GDP advance estimate released days before it"),
           conditions=("scheduled or off-cycle",
                       "whether the move is a slope change, a re-centring, or both",
                       "the cadence era: semi-annual before 2024, quarterly after",
                       "the core inflation forecast range in force"),
           instruments=("USDSGD", "SGDJPY", "EURSGD", "AUDSGD"),
           controls=("the same statistic on USDHKD on the same dates, a currency with a hard peg "
                     "and no band to adjust",
                     "the same statistic at 00:00 UTC on non-statement days, since 00:00 UTC is "
                     "itself a liquidity boundary",
                     "the same statistic on the GDP advance-estimate day, which precedes the "
                     "statement and carries much of the information",
                     "a semi-annual versus quarterly split: more events should mean smaller "
                     "average surprises, and a constant surprise size falsifies the cadence claim"),
           notes="00:00 UTC is the earliest scheduled central bank event in the global day. A "
                 "careless event study attributes the move to the previous calendar date"),
    domain("SG-B", "MAS Core CPI and the reaction function",
           objects=("MAS Core CPI, which excludes accommodation and private transport",
                    "headline CPI", "the published core forecast range",
                    "imported versus domestic inflation decomposition"),
           conditions=("whether core is inside or outside the forecast range",
                       "the direction of the S$NEER over the preceding quarter",
                       "the GST rate, which stepped up in January 2023 and January 2024"),
           instruments=("USDSGD",),
           controls=("headline CPI as a placebo: if the effect is in headline and not in core, "
                     "the market is not reading the reaction function",
                     "the same statistic on Hong Kong CPI, a similarly open economy with no "
                     "exchange-rate policy lever",
                     "a GST-step control, since two January prints carry a mechanical jump"),
           notes="a cell built on headline CPI is not modelling what MAS targets, and the two "
                 "series diverge most exactly when policy is about to move"),
    domain("SG-C", "The band as a latent state: synthetic NEER construction and edge behaviour",
           objects=("a trade-weighted basket built from executable SGD crosses and regional pairs",
                    "the weekly official index level as a calibration anchor",
                    "the inferred slope, width and centre",
                    "price behaviour at the estimated edge"),
           conditions=("the band era from BAND_STATE",
                       "the estimation error of the synthetic index against the weekly official "
                       "level",
                       "whether the basket is in the upper, middle or lower third of the "
                       "estimated band"),
           instruments=("USDSGD", "EURSGD", "GBPSGD", "AUDSGD", "NZDSGD", "CHFSGD", "SGDJPY"),
           controls=("the same construction with RANDOM weights, which must NOT track the "
                     "official weekly index -- the single most important control in this pack, "
                     "because a basket of correlated FX pairs tracks almost anything",
                     "the same edge statistic on a synthetic basket of currencies no central "
                     "bank manages",
                     "an out-of-sample period after each re-centring, where the fitted centre is "
                     "known to be wrong"),
           notes="THE FAILURE MODE IS SPECIFIC: mean reversion toward a rolling average of the "
                 "basket is not mean reversion toward the band centre, and the two agree except "
                 "exactly when a re-centring has happened, which is when the money is made or "
                 "lost"),
    domain("SG-D", "The SGD as a regional basket proxy",
           objects=("SGD against the ASEAN complex",
                    "the correlation of USDSGD with USDIDR, USDTHB, USDMYR and USDPHP",
                    "the SGD's role as the deliverable expression of a non-deliverable view"),
           conditions=("regional risk episodes",
                       "whether the regional currencies are under their own central banks' "
                       "intervention",
                       "whether SGD is at an estimated band edge, which caps its ability to "
                       "express a regional move"),
           instruments=("USDSGD", "USDIDR", "USDTHB", "USDCNH", "USDINR"),
           controls=("the same correlation with USDHKD, which is pegged and cannot express a "
                     "regional view",
                     "the dollar factor, residualised out first",
                     "a period test: the proxy relationship should WEAKEN when SGD is at a band "
                     "edge, and a constant beta across band positions falsifies the mechanism"),
           notes="this is the domain that makes Singapore worth trading for reasons other than "
                 "Singapore: an unhedgeable Indonesian or Malaysian view can be expressed in a "
                 "deliverable currency, at a cost that is measurable"),
    domain("SG-E", "SGD funding, SORA and the FX swap basis",
           objects=("SORA against the covered-parity implied rate",
                    "the FX swap basis", "MAS bill auction sizes",
                    "quarter-end and year-end funding squeezes"),
           conditions=("whether MAS is intervening, inferred from the reserve print",
                       "USD funding conditions globally",
                       "quarter end and year end"),
           instruments=("USDSGD", "USDX"),
           controls=("the same basis statistic in HKD, where the peg forces a different and "
                     "known relationship",
                     "the same statistic at non-quarter-end month ends",
                     "a global USD funding control, since a basis move can be entirely American"),
           notes="the basis is the intervention observable that does NOT wait thirty days for the "
                 "reserve print, which is the only reason it is worth the estimation difficulty"),
    domain("SG-F", "The 03:00 UTC regional fixing and NDF settlement",
           objects=("the ABS/SFEMC fixings for nine Asian currencies",
                    "the fixing window itself", "month-end fixing exposure",
                    "the onshore-offshore basis in each currency"),
           conditions=("month end", "option expiry dates",
                       "whether the onshore market of the currency in question is open"),
           instruments=("USDIDR", "USDTHB", "USDINR", "USDKRW", "USDCNH", "USDSGD"),
           controls=("the SAME window in SGD itself, which is deliverable and has no NDF, so an "
                     "effect present in SGD is not a fixing effect",
                     "the adjacent half hours",
                     "a cross-currency check: an effect in one of the nine and not the others is "
                     "a country effect; an effect in all nine is a regional settlement effect"),
           notes="this is the clock that ties the Indonesian, Thai, Indian, Malaysian, Philippine "
                 "and Vietnamese packs together; an apparent single-country fixing edge that has "
                 "not been checked against the other eight is not yet a finding"),
    domain("SG-G", "SGX derivative expiries",
           objects=("FTSE China A50 settlement on the second-last business day",
                    "Nikkei 225 settlement at the Osaka SQ on the second Friday of the quarter",
                    "the T+1 session's overnight repricing",
                    "monthly iron-ore settlement against an index average"),
           conditions=("which contract", "the level of open interest against its trailing median",
                       "whether the underlying's home market is open or closed"),
           instruments=("CHINAH", "HK50", "JPN225"),
           controls=("the same statistic on the third Friday, which is NOT the A50's expiry, "
                     "separating the contract's own rule from a generic monthly effect",
                     "the same statistic on the Japanese market's own SQ, where the effect should "
                     "be larger if it is an SQ effect and not an SGX effect",
                     "iron ore as a negative control: its monthly-average settlement means it "
                     "CANNOT have an expiry-day effect, so finding one falsifies the method"),
           notes="the iron-ore control is unusually clean: a contract design that excludes the "
                 "effect by construction is the best placebo a calendar study can have"),
    domain("SG-H", "The Platts Singapore MOC window and Asian oil pricing",
           objects=("the 08:00-08:30 UTC assessment window",
                    "Dubai and the Brent-Dubai exchange for swaps",
                    "regional product cracks: gasoil, jet, marine fuel 0.5%",
                    "weekly Singapore onshore product stocks"),
           conditions=("the Brent-Dubai spread's sign, which flips with the sour-sweet balance",
                       "regional refinery maintenance season",
                       "whether the window falls before or after a European data release"),
           instruments=("XBRUSD", "XTIUSD", "XNGUSD"),
           controls=("the adjacent half hours at 07:30-08:00 and 08:30-09:00 UTC",
                     "the same statistic on the London ICE close, a different and larger window",
                     "days when the Singapore market is closed but the paper market is not"),
           notes="the only Asian commodity fixing large enough to be visible in a global "
                 "benchmark, and it falls inside the European morning, which is what makes it "
                 "measurable in XBRUSD rather than merely in a licensed assessment"),
    domain("SG-I", "NODX and the Asian trade cycle",
           objects=("non-oil domestic exports on about the 17th at 00:30 UTC",
                    "the electronics sub-component",
                    "the market breakdown, above all China and the US"),
           conditions=("the semiconductor cycle's phase",
                       "tariff regime changes affecting transshipment",
                       "Chinese New Year timing, which distorts January and February"),
           instruments=("USDSGD", "USDKRW", "JPN225"),
           controls=("Korean 20-day exports, published earlier and covering a similar basket",
                     "Taiwanese export orders",
                     "a Chinese New Year timing control, since the distortion is a calendar "
                     "artefact and not a cycle turn"),
           notes="NODX is early but noisy and heavily revised; its value is as a CONFIRMATION of "
                 "the Korean print rather than as a signal on its own"),
    domain("SG-J", "Reserves, the forward book and inferred intervention",
           objects=("monthly official foreign reserves",
                    "the net forward position published alongside",
                    "the gap between reserve change and valuation effects"),
           conditions=("the direction of the basket in the month",
                       "whether a re-centring occurred",
                       "global reserve currency valuation moves"),
           instruments=("USDSGD", "USDX"),
           controls=("a valuation-only counterfactual: reserves revalued at unchanged holdings, "
                     "which isolates the FLOW from the price effect",
                     "the same statistic for Hong Kong's Aggregate Balance, where intervention is "
                     "mechanical and fully observable",
                     "months with no basket movement, where intervention should be absent"),
           notes="the thirty-day lag is what makes this domain hard; the FX swap basis in SG-E is "
                 "the same information available sooner and with more noise, and the two should "
                 "be tested against each other rather than used separately"),
    domain("SG-K", "Holiday and Chinese New Year liquidity in the Asian complex",
           objects=("Chinese New Year, which closes seven markets within 48 hours",
                    "the Singapore substitution law and its Saturday exception",
                    "an unannounced polling-day closure",
                    "the two-day gap between Asian closures and the deliverable SGD market"),
           conditions=("how many regional markets are shut simultaneously",
                       "whether Singapore itself is open while its neighbours are not"),
           instruments=("USDSGD", "USDCNH", "USDIDR", "USDTHB"),
           controls=("Western holidays of comparable breadth, such as the Christmas week",
                     "days when Singapore is shut and the region is open, the reverse condition",
                     "a volume control, since a liquidity effect must show in volume and not only "
                     "in price"),
           notes="the Saturday exception is the trap: a gazetted holiday on a Saturday produces "
                 "NO market closure and a naive calendar that counts it produces a phantom "
                 "holiday effect"),
    domain("SG-L", "Wealth inflow, property macroprudential policy and the structural SGD bid",
           objects=("assets under management growth",
                    "the 13O and 13U family-office incentive schemes and their tightening",
                    "additional buyer's stamp duty changes",
                    "the residential property price index"),
           conditions=("the incentive regime in force",
                       "regional political risk episodes that drive relocation"),
           instruments=("USDSGD",),
           controls=("Hong Kong's AUM over the same period, the competing hub, which should move "
                     "in the OPPOSITE direction if the mechanism is relocation rather than "
                     "regional growth",
                     "a trade-weighted fair-value residual, since the claim is that SGD is "
                     "stronger than trade alone implies"),
           notes="a slow, level-shifting mechanism with no tradable timing signal of its own; it "
                 "belongs here because it explains a PERSISTENT residual that a trade-based model "
                 "will otherwise keep trying to mean-revert"),
)

# --------------------------------------------------------------------------- miners (specs)
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("sg_synthetic_neer", domain_ids=("SG-C", "SG-D"), kind="state_estimation",
          entry="research.countries.sg.miners:synthetic_neer", cadence_s=3600.0, steerable=False,
          notes="SPEC, NOT YET WIRED. Builds the basket from the seven SGD crosses plus the "
                "regional pairs, calibrates against the weekly official index, and reports the "
                "RANDOM-WEIGHT control alongside every fit or the fit is not published"),
    miner("sg_mps_event_study", domain_ids=("SG-A",), kind="event",
          entry="research.countries.sg.miners:mps_event_study", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Splits scheduled from off-cycle and slope changes from "
                "re-centrings; refuses to pool them"),
    miner("sg_band_edge", domain_ids=("SG-C",), kind="microstructure",
          entry="research.countries.sg.miners:band_edge", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Tests behaviour conditional on the estimated position "
                "within the band, and reports the estimation error with every verdict"),
    miner("sg_regional_fixing", domain_ids=("SG-F",), kind="microstructure",
          entry="research.countries.sg.miners:regional_fixing", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Runs the 03:00 UTC window across all nine currencies at "
                "once, so a single-country claim cannot be made without the regional check"),
    miner("sg_sgx_expiry", domain_ids=("SG-G",), kind="calendar",
          entry="research.countries.sg.miners:sgx_expiry", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Includes the iron-ore placebo, whose monthly-average "
                "settlement means an expiry-day effect there falsifies the method"),
    miner("sg_moc_window", domain_ids=("SG-H",), kind="microstructure",
          entry="research.countries.sg.miners:moc_window", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Measures XBRUSD and XTIUSD inside 08:00-08:30 UTC against "
                "the two adjacent half hours"),
    miner("sg_nodx_nowcast", domain_ids=("SG-I",), kind="macro",
          entry="research.countries.sg.miners:nodx_nowcast", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Joins NODX to the Korean 20-day print and reports the "
                "Chinese New Year timing control"),
    miner("sg_reserve_intervention", domain_ids=("SG-E", "SG-J"), kind="flow",
          entry="research.countries.sg.miners:reserve_intervention", cadence_s=604800.0,
          notes="SPEC, NOT YET WIRED. Builds the valuation-only counterfactual before it reports "
                "any inferred intervention flow"),
    miner("sg_holiday_liquidity", domain_ids=("SG-K",), kind="calendar",
          entry="research.countries.sg.miners:holiday_liquidity", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Applies the Saturday exception correctly, which is the "
                "whole point of it"),
)

# --------------------------------------------------------------------------- transmission seeds
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("SG-E01", source="MAS monetary policy statement slope change",
         mechanism="a slope change alters the drift of the whole basket, so every SGD cross "
                   "reprices together in a way a single-pair view cannot see",
         targets=("USDSGD", "EURSGD", "SGDJPY", "AUDSGD"), sign="-",
         horizon="0 to 10 sessions",
         lag="0 -- the statement is public at 00:00 UTC",
         control="USDHKD on the same dates, a hard peg with no band to adjust",
         notes="FALSIFIER: a slope change that moves USDSGD and no other SGD cross, which would "
               "say the market is trading the pair and not the basket"),
    edge("SG-E02", source="MAS re-centring of the band",
         mechanism="a re-centring is a STEP in the level of the target and is a different animal "
                   "from a slope change; the basket should jump and then resume its prior drift",
         targets=("USDSGD", "EURSGD", "SGDJPY"), sign="-", horizon="0 to 3 sessions", lag="0",
         control="the same statistic at slope-only changes, where no step should appear",
         notes="FALSIFIER: an indistinguishable response to a re-centring and to a slope change, "
               "which would mean the distinction this pack is built on does not trade"),
    edge("SG-E03", source="the estimated S$NEER position within its band",
         mechanism="MAS resists the edges, so basket returns should be asymmetric conditional on "
                   "position -- weaker mean reversion in the middle, stronger at the edge",
         targets=("USDSGD", "AUDSGD", "GBPSGD"), sign="-", horizon="5 to 20 sessions",
         lag="7 days on the official weekly index used for calibration",
         control="the same statistic computed on a random-weight basket, which must show nothing",
         notes="FALSIFIER: identical mean reversion at the estimated edge and in the estimated "
               "middle. Requires the estimation error to be reported with every verdict"),
    edge("SG-E04", source="SGD funding stress in the FX swap basis",
         mechanism="sterilisation of intervention moves the basis, so a basis move is an earlier "
                   "read on intervention than the thirty-day reserve print",
         targets=("USDSGD", "USDX"), sign="+", horizon="1 to 10 sessions",
         lag="1 session on SORA",
         control="the HKD basis, where the peg forces a known and different relationship",
         notes="FALSIFIER: basis moves that do not predict the subsequent reserve print's flow "
               "component, across a full year of months"),
    edge("SG-E05", source="the 03:00 UTC ABS/SFEMC fixing window",
         mechanism="nine restricted currencies settle their NDFs at one instant, so hedging "
                   "demand concentrates into the window across the whole region at once",
         targets=("USDIDR", "USDTHB", "USDINR", "USDKRW"), sign="+",
         horizon="intraday, the window and the hour after it",
         lag="0 -- the fixing is the event",
         control="USDSGD in the same window, which is deliverable and has no NDF to settle",
         notes="FALSIFIER: an effect present in USDSGD, which would prove it is a session "
               "boundary and not a fixing"),
    edge("SG-E06", source="SGX FTSE China A50 T+1 session move",
         mechanism="Chinese equity risk is repriced overnight on SGX while the onshore market is "
                   "shut, so the T+1 close carries information into the next Asian open",
         targets=("CHINAH", "HK50", "USDCNH"), sign="+", horizon="the next session's open",
         lag="0 -- observable in real time",
         control="nights when the onshore market is open for an extended session, where the "
                 "mechanism is weakened by construction",
         notes="FALSIFIER: an overnight A50 move that does not survive into the next HK50 open"),
    edge("SG-E07", source="SGX Nikkei 225 Special Quotation",
         mechanism="the SQ is computed from constituent OPENING prices on the second Friday of "
                   "the quarter, which concentrates hedging into one auction",
         targets=("JPN225", "USDJPY"), sign="0", horizon="the SQ session",
         lag="0", control="the third Friday of the same months, which is not the SQ",
         notes="FALSIFIER: an SQ effect on the third Friday too, which would make it a monthly "
               "artefact. Sign is deliberately unsigned: the claim is about VARIANCE, not "
               "direction"),
    edge("SG-E08", source="Singapore bunker sales volume",
         mechanism="the world's largest bunkering port publishes its physical demand monthly, "
                   "which is a free read on global shipping activity and on middle-distillate "
                   "demand",
         targets=("XBRUSD", "XTIUSD"), sign="+", horizon="1 to 2 months",
         lag="20 days",
         control="global container throughput, which shares the trade cycle without the fuel "
                 "grade mix",
         notes="FALSIFIER: a year of rising bunker volume with falling container throughput and "
               "no product-crack response"),
    edge("SG-E09", source="the 08:00-08:30 UTC Platts MOC window",
         mechanism="Asian physical oil price discovery concentrates into one half hour that falls "
                   "inside the European morning",
         targets=("XBRUSD", "XTIUSD"), sign="0", horizon="intraday", lag="0",
         control="the adjacent half hours at 07:30-08:00 and 08:30-09:00 UTC",
         notes="FALSIFIER: no difference in realised variance between the window and its "
               "neighbours across a year. Unsigned: the claim is concentration of variance"),
    edge("SG-E10", source="Singapore NODX electronics",
         mechanism="an early monthly read on the Asian trade cycle, published before the full "
                   "Korean and Taiwanese figures",
         targets=("USDKRW", "JPN225"), sign="-", horizon="0 to 5 sessions",
         lag="17 days",
         control="Korean 20-day exports, published earlier, which must absorb the signal if NODX "
                 "carries no independent content",
         notes="FALSIFIER: no incremental content once the Korean 20-day print is in the model"),
    edge("SG-E11", source="a Chinese New Year multi-market closure",
         mechanism="seven Asian markets shut inside 48 hours, so regional FX liquidity collapses "
                   "and spreads widen mechanically",
         targets=("USDCNH", "USDIDR", "USDTHB", "USDSGD"), sign="0",
         horizon="the closure window and the two sessions after",
         lag="0 -- the dates are known years ahead",
         control="Western holiday weeks of comparable breadth, and days when Singapore alone is "
                 "shut",
         notes="FALSIFIER: no widening of spreads or fall in volume across the closure. Must be "
               "measured in VOLUME as well as price or it is not a liquidity claim"),
    edge("SG-E12", source="the S$NEER basket against the ASEAN complex",
         mechanism="SGD is the deliverable expression of a regional view, so it carries the ASEAN "
                   "beta that the restricted currencies cannot fully price",
         targets=("USDIDR", "USDTHB", "USDINR"), sign="+", horizon="5 to 20 sessions",
         lag="0",
         control="USDHKD, which is pegged and cannot express a regional view at all",
         notes="FALSIFIER: an unchanged proxy beta when SGD is pinned at an estimated band edge, "
               "where the mechanism says it must weaken"),
    edge("SG-E13", source="MAS Core CPI surprise against its own published forecast range",
         mechanism="MAS targets core, not headline, so only a core surprise carries policy "
                   "information",
         targets=("USDSGD", "SGDJPY"), sign="-", horizon="0 to 3 sessions", lag="23 days",
         control="headline CPI surprises of the same size, which must move the market less if the "
                 "market is reading the reaction function",
         notes="FALSIFIER: identical responses to core and headline surprises. Exclude the two "
               "January prints carrying a GST step"),
    edge("SG-E14", source="SGX iron ore open interest and volume",
         mechanism="SGX clears most of the world's iron-ore derivatives, so its open interest is "
                   "a free read on Chinese steel-mill hedging",
         targets=("AUS200", "USDCNH", "XCUUSD"), sign="+", horizon="1 to 3 months",
         lag="5 days on the monthly statistics",
         control="Chinese steel PMI and port stocks, which carry the same demand without the "
                 "hedging channel",
         notes="FALSIFIER: no incremental content once onshore steel data is in the model -- the "
               "likely outcome, and worth measuring once"),
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("SG-R1", start="2010-01-01", end="2020-03-29",
        label="semi-annual statements, pre-pandemic band operation",
        what_changed="two statements a year in April and October, a modest appreciating slope "
                     "through most of the decade, and a zero-slope episode in 2015-2016",
        invalidates="the event count is half the current one, so an event-study sample pooled "
                    "with the quarterly era has twice the events per year in its second half and "
                    "a smaller average surprise in it",
        notes="the SGX lunch break was removed in 2011, which is a separate intraday break"),
    era("SG-R2", start="2020-03-30", end="2021-10-13",
        label="pandemic easing at zero slope",
        what_changed="slope cut to zero and the centre re-centred down in a single move, then "
                     "eighteen months of no change",
        invalidates="a band-position statistic fitted here is fitted on a FLAT band, where the "
                    "mean-reversion target does not drift and the estimation problem is easier "
                    "than it ever is again",
        notes="the only simultaneous slope-and-centre easing in the sample"),
    era("SG-R3", start="2021-10-14", end="2022-10-14",
        label="the tightening cycle, including two off-cycle moves",
        what_changed="five tightenings in twelve months, two of them unscheduled, including a "
                     "pure re-centring in July 2022 with no slope change",
        invalidates="event-day volatility here is not comparable to any other era, and the "
                    "off-cycle moves mean a scheduled-dates-only event study misses two of the "
                    "five largest days",
        notes="July 2022 is the cleanest observation of a pure re-centring that exists"),
    era("SG-R4", start="2022-10-15", end="2023-12-31",
        label="the plateau",
        what_changed="no policy change across four consecutive statements while inflation fell "
                     "back and the GST rate stepped up in January 2023",
        invalidates="a tone-based feature set fitted here learns that nothing ever happens",
        notes="the last era under the semi-annual cadence"),
    era("SG-R5", start="2024-01-01", end="2024-12-31",
        label="the quarterly cadence begins",
        what_changed="MAS moved to four statements a year in January, April, July and October; "
                     "no policy parameter moved during the year",
        invalidates="the CADENCE change alone doubles the event count without doubling the "
                    "information, so an event-frequency statistic pooled across 2023 and 2024 is "
                    "measuring the calendar",
        notes="the second GST step landed in January 2024"),
    era("SG-R6", start="2025-01-01", end=None,
        label="quarterly cadence with easing",
        what_changed="two consecutive slope reductions in January and April 2025, the first "
                     "easing since March 2020, under the new quarterly calendar",
        invalidates="the current regime; a band-position cell must be fitted inside it because "
                    "the drift of the target changed twice at its start",
        notes="what a live candidate is actually trading"),
)


# --------------------------------------------------------------------------- assembly
MISSION = (
    "mine Singapore to exhaustion on the one mechanism no other country in this "
    "department has: a central bank whose instrument is an exchange rate band whose "
    "three parameters are never published, reconstructible out of seven executable "
    "SGD crosses -- plus the regional clocks Singapore hosts, the 03:00 UTC Asian "
    "fixing and the 08:30 UTC oil assessment")
NOTES = (
    "the SGD complex is fully executable and the VENUE layer is not: the Straits Times "
    "Index, SGX's A50 and Nikkei contracts, SGX iron ore and rubber, SORA, MAS bills "
    "and SGS are all absent from the broker universe and are named in this module's "
    "TRANSMISSION_TARGETS. BAND_STATE carries every announced band move since 2020 and "
    "is this country's equivalent of a policy rate history.")


def fields() -> dict[str, Any]:
    """The LOSSLESS form of this pack: the twenty-one mandate fields plus the extras this pack
    adds, as a plain mapping in `research.countries` row shape.

    This exists because two sibling frameworks landed with DIFFERENT row schemas.
    `research.countries` builds edges as {id, source, mechanism, targets, sign, horizon, lag,
    control, evidence} and `libs.research.country_lab.CountryPack` coerces whatever it is given
    into its own `TransmissionSeed` / `HolidayRule` / `Era` shapes, which do not carry those
    names. `pack()` returns the coerced object because that is what the framework's consumers
    expect; `fields()` returns the data as written, which is what a validator and a miner in this
    package should read. When the two schemas converge, this function becomes a formality.
    """
    return {
        "code": CODE, "name": NAME, "region_command": REGION_COMMAND, "currency": CURRENCY,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS, "settlement_conventions": SETTLEMENT_CONVENTIONS,
        "exchanges": EXCHANGES, "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES, "datasets": DATASETS,
        "actors": ACTORS, "domains": DOMAINS, "custom_miners": CUSTOM_MINERS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "band_state": BAND_STATE,
        "mission": MISSION, "notes": NOTES,
    }


def pack() -> Any:
    """Singapore's pack: `CountryPack` when the framework has landed, else the same fields as a
    dict. `transmission_targets` and `band_state` ride alongside the twenty-one frozen fields;
    `build_pack` keeps them in the dict form and drops them from the dataclass when it does not
    declare them, which is the right trade -- an absent instrument must be NAMED somewhere."""
    return build_pack(**fields())
