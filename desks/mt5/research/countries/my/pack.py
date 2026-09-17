"""MALAYSIA: a currency this broker cannot quote, and why that is a finding and not a gap.

WHY USDMYR IS ABSENT AND WHY THAT IS THE FIRST FACT OF THIS PACK. Bank Negara has prohibited
offshore ringgit trading since the 1998 capital controls and has never lifted the prohibition. It
does not recognise the offshore non-deliverable forward market, it has repeatedly warned banks
against facilitating it, and the ringgit is quoted, funded and settled ONSHORE or not at all. The
consequence for a retail CFD broker is mechanical: USDIDR, USDTHB, USDSGD and USDINR are on this
registry and USDMYR is not, because the first four have deliverable or offshore markets a
liquidity provider can access and the fifth does not. The absence is not an oversight in the
broker's list. It is Malaysian monetary policy, visible in a JSON file.

SO THIS IS A TRANSMISSION-ONLY PACK, AND IT IS WRITTEN AS ONE. `executable_instruments` contains
no Malaysian instrument at all: it is the set of symbols Malaysia's mechanisms actually reach --
the vegetable-oil complex through SOYBEAN, energy through XBRUSD, XTIUSD and XNGUSD, the regional
FX complex through USDSGD, USDIDR, USDTHB and USDCNH, and the commodity-exporter equity beta
through AUS200. USDMYR, FCPO palm oil, the KLCI, MGS, tin and rubber are all in
`TRANSMISSION_TARGETS`, named, with the symbols each one's mechanism reaches.

THE FOUR MECHANISMS WORTH MINING ANYWAY.

  1. PALM OIL, AND THE ONLY HARD MONTHLY SUPPLY-DEMAND PRINT IN THE VEGETABLE-OIL COMPLEX. The
     Malaysian Palm Oil Board publishes stocks, production and exports on the 10th of each month
     at 12:00 MYT -- 04:00 UTC. Indonesia produces more but publishes less and later, so MPOB's
     print is the world's visible half of a market where the larger half is opaque. Between MPOB
     prints, three private cargo surveyors publish export estimates on the 10th, 15th, 20th, 25th
     and month end, which turns an opaque month into five dated observations. Nothing else in
     this department has that structure.

  2. A STATE-DIRECTED REPATRIATION LEVER WITH A DATED CAMPAIGN. In early 2024, with the ringgit
     at its weakest since 1998, the government and Bank Negara coordinated the government-linked
     investment companies -- the pension fund, the sovereign fund, the unit trust manager, the
     civil-service fund -- to repatriate and convert foreign investment income, and pressed
     exporters to convert proceeds. The ringgit went from about 4.80 in February 2024 to about
     4.12 by September and finished 2024 the best-performing currency in Asia. That is a policy
     flow with a date, a named set of actors, and a measurable outcome -- and it is the reason
     MY-C exists as a domain rather than as a footnote.

  3. PETRONAS. The national oil company is a Brent-linked exporter, the largest single source of
     federal revenue through its dividend, and the operator of one of the world's larger LNG
     complexes. Malaysia is a net energy EXPORTER on gas and a marginal one on oil, which is the
     opposite of Thailand, the Philippines and India and makes it the natural control in any
     regional oil-and-currency study.

  4. A THIRD OF THE GOVERNMENT BOND MARKET HELD OFFSHORE. Malaysia carries one of the highest
     foreign ownership shares of local-currency government debt in emerging Asia. With no
     offshore currency market to hedge in, that foreign holder's currency risk is either unhedged
     or hedged onshore, which is a structural asymmetry no other country in this department has.

THE TRAP THIS PACK IS BUILT TO AVOID. Because there is no MYR symbol, every Malaysian claim must
terminate in a non-Malaysian instrument, and the temptation is to treat USDSGD or USDIDR as "the
ringgit proxy" and stop thinking. They are not. They are currencies with their own central banks,
their own commodity exposures and their own calendars, and MY-L exists specifically to measure how
much of a Malaysian move survives into each of them -- with the honest expectation that most of it
does not.

CUSTOM_MINERS ARE SPECIFICATIONS, NOT WIRING. Each names the module it will live in. None is on a
clock yet; unwired is a defect (III.16) and naming it keeps the defect visible.
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
CODE = "MY"
NAME = "Malaysia"
REGION_COMMAND = "southeast_asia"
CURRENCY = "MYR"
FISCAL_YEAR_END = "12-31"  # the federal budget runs on the calendar year, tabled in October
NATIVE_LANGUAGES: tuple[str, ...] = ("ms", "en", "zh", "ta")

#: NOT ONE MALAYSIAN INSTRUMENT IS IN THIS LIST, and that is the pack's first finding rather than
#: an omission. USDMYR is absent from the broker registry because Bank Negara prohibits offshore
#: ringgit trading. Everything here is a symbol Malaysia's mechanisms REACH.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "SOYBEAN", "CORN",                       # the vegetable-oil and feed complex palm competes in
    "XBRUSD", "XTIUSD", "XNGUSD",            # Petronas, LNG, and the biodiesel blending economics
    "USDSGD", "USDIDR", "USDTHB", "USDCNH",  # the regional FX complex a ringgit move reaches
    "USDINR",                                # India is the largest single palm oil buyer
    "AUS200",                                # the commodity-exporter equity beta
    "HK50", "CHINAH",                        # China is the other large palm buyer and the EM factor
    "USDX",                                  # the dollar factor every claim here is residualised on
    "UST10Y",                                # what the foreign MGS holder trades the spread to
    "XAUUSD",                                # a reserve asset and a domestic retail market
    "XCUUSD", "XALUSD",                      # the base-metal complex tin trades alongside
    "US500",                                 # the semiconductor demand channel for Penang
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/MYR spot and forward", "venue": "onshore interbank only",
     "why": "THE DEFINING ABSENCE. Bank Negara prohibits offshore ringgit trading and does not "
            "recognise the NDF market, so no offshore liquidity provider can make a price and no "
            "retail CFD registry carries the pair. The absence IS the policy",
     "proxies": ("USDSGD", "USDIDR", "USDTHB", "USDCNH")},
    {"name": "crude palm oil futures (FCPO)", "venue": "Bursa Malaysia Derivatives",
     "why": "the world benchmark for palm oil, and the price the MPOB print moves. Malaysia's "
            "second-place production makes it the visible half of a market whose larger half "
            "publishes less",
     "proxies": ("SOYBEAN", "XTIUSD", "USDIDR")},
    {"name": "FBM KLCI and the FKLI index future", "venue": "Bursa Malaysia",
     "why": "a bank-and-plantation-heavy index; FKLI expires on the last business day of the "
            "month, which is a different rule from every other index in this region",
     "proxies": ("HK50", "AUS200")},
    {"name": "Malaysian Government Securities (MGS), 10-year", "venue": "onshore OTC",
     "why": "one of the highest foreign ownership shares in emerging Asia, held by investors who "
            "have no offshore currency market in which to hedge it",
     "proxies": ("UST10Y", "USDSGD")},
    {"name": "refined tin", "venue": "London Metal Exchange and the KL Tin Market",
     "why": "Malaysia smelts a meaningful share of world refined tin and the KL market is one of "
            "the two physical price points; no tin contract exists in this universe",
     "proxies": ("XCUUSD", "XALUSD")},
    {"name": "natural rubber (SMR20)", "venue": "Malaysian Rubber Board, SGX TSR20",
     "why": "a Malaysian, Thai and Indonesian export price and a terms-of-trade input for three "
            "packs in this region",
     "proxies": ("USDTHB", "USDIDR")},
    {"name": "Malaysian LNG contract prices", "venue": "bilateral, JKM-linked",
     "why": "Petronas is a top-five LNG exporter and its contracts are Asian-benchmark linked, "
            "not Henry Hub linked -- so XNGUSD is an IMPERFECT proxy and is named as one",
     "proxies": ("XNGUSD", "XBRUSD")},
    {"name": "KLIBOR and MYOR", "venue": "Bank Negara Malaysia",
     "why": "the onshore rate complex; with no offshore market there is no MYR cross-currency "
            "basis to read, which removes an observable every other pack in this region has",
     "proxies": ("USDSGD", "UST10Y")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank Negara Malaysia",
    "short": "BNM",
    "committee": "Monetary Policy Committee",
    "policy_instrument": "the Overnight Policy Rate (OPR)",
    "mandate": "price stability while giving due regard to developments in the economy; BNM is "
               "explicitly NOT an inflation targeter and has no numerical target, which is "
               "unusual in this region and means the reaction function has to be estimated rather "
               "than read off a mandate",
    "non_internationalisation": "the ringgit may not be traded offshore. BNM does not recognise "
                                "the NDF market, prohibits non-resident ringgit lending beyond "
                                "narrow limits, and has repeatedly instructed banks not to "
                                "facilitate offshore ringgit business. This has been in force "
                                "since the 1998 capital controls and is the single most "
                                "consequential fact in this pack",
    "decision_rule": "SIX meetings a year, roughly every two months, on dates published a year "
                     "ahead. The statement is released at 15:00 MYT, which is 07:00 UTC -- the "
                     "same hour as Bank Indonesia and the Bank of Thailand, so three Southeast "
                     "Asian central banks can print into the same window and a regional event "
                     "study must separate them",
    "announce_local": "15:00 MYT", "announce_utc": "07:00",
    "presser_utc": "none; BNM does not hold a routine press conference after the statement",
    "off_cycle": "BNM has not moved off-cycle in the recent record; its crisis tool has been "
                 "the statutory reserve requirement and liquidity operations rather than an "
                 "unscheduled rate move",
    "other_clocks": (
        {"what": "USD/MYR reference rate (the BNM Rate)", "when_local": "15:30 MYT",
         "when_utc": "07:30", "reference_lag_days": 0},
        {"what": "international reserves", "when_local": "the 7th and the 22nd, 15:00 MYT",
         "when_utc": "07:00", "reference_lag_days": 7},
        {"what": "monthly monetary and financial statistics",
         "when_local": "end of month, 15:00 MYT", "when_utc": "07:00", "reference_lag_days": 30},
        {"what": "KLIBOR and MYOR publication", "when_local": "11:00 MYT", "when_utc": "03:00",
         "reference_lag_days": 0},
    ),
    "dates": {
        2024: ("2024-01-24", "2024-03-07", "2024-05-09", "2024-07-11", "2024-09-05",
               "2024-11-06"),
        2025: ("2025-01-22", "2025-03-06", "2025-05-08", "2025-07-09", "2025-09-04",
               "2025-11-06"),
        2026: (),
    },
    "dates_status": "2024 and 2025 follow BNM's published six-meeting schedule. 2026 is "
                    "UNMEASURED here (L1.28a): BNM publishes the following year's calendar in "
                    "the fourth quarter and it must be read before any event study",
    "policy_note": "the OPR was cut by 25 basis points in July 2025, the first reduction since "
                   "the pandemic easing, after a long hold that makes the pre-2025 sample a "
                   "period in which the policy variable simply did not move",
}

# --------------------------------------------------------------------------- fixings, settlement
#: MYT is UTC+8 all year with no daylight saving.
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Kuala Lumpur USD/MYR Reference Rate (the BNM Rate)",
     "administrator": "Bank Negara Malaysia",
     "window_local": "interbank USD/MYR transactions through the onshore session to 15:00 MYT",
     "window_utc": "01:00-07:00", "publish_local": "15:30 MYT", "publish_utc": "07:30",
     "basis": "a weighted average of actual onshore interbank transactions",
     "uses": "the settlement reference for onshore contracts and the anchor for corporate "
             "translation",
     "note": "this is an ONSHORE-ONLY fix for an onshore-only currency. There is no offshore "
             "counterpart to compare it against, which removes the onshore-offshore basis that "
             "every other restricted currency in this region provides as an observable"},
    {"name": "KLIBOR", "administrator": "Bank Negara Malaysia",
     "window_local": "a contributor panel quoted in the morning",
     "window_utc": "02:00-03:00", "publish_local": "11:00 MYT", "publish_utc": "03:00",
     "basis": "a panel-contributed interbank offered rate, with 3-month KLIBOR the reference "
              "tenor for most floating-rate lending",
     "uses": "the floating leg of the domestic swap curve",
     "note": "Malaysia has published MYOR, a transaction-based overnight rate, as an alternative "
             "reference; KLIBOR has been retained rather than retired, so the market carries two "
             "references at once"},
    {"name": "MPOB monthly palm oil supply and demand",
     "administrator": "Malaysian Palm Oil Board",
     "window_local": "the preceding calendar month", "window_utc": "the preceding month",
     "publish_local": "the 10th of each month at 12:00 MYT", "publish_utc": "04:00",
     "basis": "a statutory census of closing stocks, crude palm oil production, exports and "
              "imports",
     "uses": "the world's hard monthly read on the visible half of the palm oil balance",
     "note": "TREATED AS A FIXING HERE ON PURPOSE. It is a scheduled, statutory, market-moving "
             "number with a stamped release time, which is exactly what a fixing is for research "
             "purposes, and it is the single most tradable Malaysian clock"},
    {"name": "cargo surveyor export estimates",
     "administrator": "Intertek, AmSpec and SGS (private)",
     "window_local": "the 1st to the 10th, 15th, 20th, 25th and month end",
     "window_utc": "month-to-date", "publish_local": "on those dates, morning MYT",
     "publish_utc": "02:00-04:00",
     "basis": "surveyed cargo loadings expressed as a month-to-date total and a year-on-year "
              "change",
     "uses": "the intramonth bridge between MPOB prints",
     "note": "three independent surveyors publishing the same quantity on the same dates gives a "
             "free cross-check; when they disagree materially, the disagreement is itself the "
             "signal"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"market": "USD/MYR onshore interbank spot", "cycle": "T+2",
     "session_local": "09:00-17:00 MYT", "session_utc": "01:00-09:00",
     "note": "ONSHORE ONLY. Outside these hours the ringgit does not trade anywhere, so a "
             "Malaysian shock that lands during the European or US session cannot be expressed in "
             "the currency until the next Asian open -- which is why it leaks into USDSGD and "
             "USDIDR instead, and why MY-L is a domain"},
    {"market": "Bursa Malaysia securities", "cycle": "T+2",
     "session_local": "09:00-12:30 and 14:30-17:00 MYT, with a theoretical opening price phase "
                      "from 08:30",
     "session_utc": "01:00-04:30 and 06:30-09:00",
     "note": "a two-hour lunch break, the longest in the region, which a naive intraday grid "
             "averages straight across"},
    {"market": "Bursa Malaysia Derivatives -- FCPO", "cycle": "physical delivery",
     "session_local": "10:30-12:30 and 14:30-18:00 MYT",
     "session_utc": "02:30-04:30 and 06:30-10:00",
     "note": "the benchmark contract is the THIRD forward month, not the front month, which is "
             "unusual and means a naive front-month continuous series is not the price the "
             "market quotes"},
    {"market": "Bursa Malaysia Derivatives -- FKLI", "cycle": "cash",
     "session_local": "08:45-12:45 and 14:30-17:15 MYT",
     "session_utc": "00:45-04:45 and 06:30-09:15",
     "note": "the index future trades outside the cash session at both ends, which gives a "
             "pre-open and post-close read the cash market does not have"},
    {"market": "Malaysian Government Securities", "cycle": "T+2",
     "session_local": "09:00-17:00 MYT", "session_utc": "01:00-09:00",
     "note": "foreign holders are a third of the market and have no offshore currency market in "
             "which to hedge; they hedge onshore or not at all"},
)

# --------------------------------------------------------------------------- exchanges
EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Bursa Malaysia securities market", "code": "BURSA",
     "hours_local": "09:00-12:30 and 14:30-17:00 MYT",
     "hours_utc": "01:00-04:30 and 06:30-09:00",
     "expiry_rule": "n/a for cash",
     "settlement": "T+2",
     "rebalance": "FBM KLCI semi-annual review in June and December, effective after the third "
                  "Friday"},
    {"name": "Bursa Malaysia Derivatives -- crude palm oil (FCPO)", "code": "BMD-FCPO",
     "hours_local": "10:30-12:30 and 14:30-18:00 MYT",
     "hours_utc": "02:30-04:30 and 06:30-10:00",
     "expiry_rule": "the 15th of the contract month, or the preceding business day when the 15th "
                    "is a holiday",
     "settlement": "physical delivery against port tank certificates",
     "rebalance": "n/a",
     "note": "the BENCHMARK is the third forward month; the front month is illiquid into "
             "delivery. The monthly export duty is set from the preceding month's average price "
             "of this contract's underlying, which makes the price itself a policy input"},
    {"name": "Bursa Malaysia Derivatives -- FKLI index futures", "code": "BMD-FKLI",
     "hours_local": "08:45-12:45 and 14:30-17:15 MYT",
     "hours_utc": "00:45-04:45 and 06:30-09:15",
     "expiry_rule": "the LAST BUSINESS DAY of the contract month, which differs from the third "
                    "Friday used by most index contracts in this region and from SGX's "
                    "second-last business day",
     "settlement": "cash, against the average of the underlying index taken at intervals in the "
                   "last half hour",
     "rebalance": "with the KLCI"},
)

# --------------------------------------------------------------------------- the holiday rule
_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "Tahun Baru (New Year's Day)",
        "2024-02-01": "Hari Wilayah Persekutuan (Federal Territory Day)",
        "2024-02-12": "Tahun Baru Cina (in lieu of Saturday 10 February)",
        "2024-02-13": "Tahun Baru Cina (in lieu of Sunday 11 February)",
        "2024-03-28": "Nuzul Al-Quran",
        "2024-04-10": "Hari Raya Aidilfitri",
        "2024-04-11": "Hari Raya Aidilfitri",
        "2024-05-01": "Hari Pekerja (Labour Day)",
        "2024-05-22": "Hari Wesak",
        "2024-06-03": "Hari Keputeraan Yang di-Pertuan Agong",
        "2024-06-17": "Hari Raya Haji",
        "2024-07-08": "Awal Muharram (in lieu of Sunday 7 July)",
        "2024-09-16": "Hari Malaysia and Maulidur Rasul",
        "2024-10-31": "Deepavali",
        "2024-12-25": "Hari Krismas (Christmas Day)",
    },
    2025: {
        "2025-01-01": "Tahun Baru (New Year's Day)",
        "2025-01-29": "Tahun Baru Cina",
        "2025-01-30": "Tahun Baru Cina",
        "2025-02-11": "Thaipusam",
        "2025-03-18": "Nuzul Al-Quran",
        "2025-03-31": "Hari Raya Aidilfitri",
        "2025-04-01": "Hari Raya Aidilfitri",
        "2025-05-01": "Hari Pekerja (Labour Day)",
        "2025-05-12": "Hari Wesak",
        "2025-06-02": "Hari Keputeraan Yang di-Pertuan Agong",
        "2025-06-27": "Awal Muharram",
        "2025-09-01": "Hari Kebangsaan (in lieu of Sunday 31 August)",
        "2025-09-05": "Maulidur Rasul",
        "2025-09-16": "Hari Malaysia",
        "2025-10-20": "Deepavali",
        "2025-12-25": "Hari Krismas (Christmas Day)",
    },
    2026: {
        "2026-01-01": "Tahun Baru (New Year's Day)",
        "2026-02-02": "Hari Wilayah Persekutuan (in lieu of Sunday 1 February)",
        "2026-02-17": "Tahun Baru Cina",
        "2026-02-18": "Tahun Baru Cina",
        "2026-03-07": "Nuzul Al-Quran",
        "2026-03-20": "Hari Raya Aidilfitri",
        "2026-03-21": "Hari Raya Aidilfitri",
        "2026-03-23": "Hari Raya Aidilfitri (in lieu of Saturday 21 March)",
        "2026-05-01": "Hari Pekerja (Labour Day)",
        "2026-05-27": "Hari Raya Haji",
        "2026-06-01": "Hari Wesak (in lieu of Sunday 31 May)",
        "2026-06-16": "Awal Muharram",
        "2026-08-26": "Maulidur Rasul",
        "2026-08-31": "Hari Kebangsaan (National Day)",
        "2026-09-16": "Hari Malaysia",
        "2026-11-09": "Deepavali (in lieu of Sunday 8 November)",
        "2026-12-25": "Hari Krismas (Christmas Day)",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": "Bursa Malaysia observes the FEDERAL public holidays plus the Federal Territory "
            "holidays of Kuala Lumpur, where the exchange sits. Fixed Gregorian dates are 1 "
            "January, 1 May, 31 August (Hari Kebangsaan), 16 September (Hari Malaysia) and 25 "
            "December. The Yang di-Pertuan Agong's birthday is a moveable official date set by "
            "proclamation and has recently fallen on the first Monday of June. Hari Raya "
            "Aidilfitri (two days), Hari Raya Haji, Awal Muharram, Maulidur Rasul and Nuzul "
            "Al-Quran follow the Islamic calendar and are gazetted from local moon-sighting, so "
            "a computed date can be a day out. Chinese New Year is two days; Wesak is the "
            "Vesakha full moon; Deepavali and Thaipusam follow the Hindu calendar. THE "
            "SUBSTITUTION LAW IS THE OPERATIVE PART: a gazetted holiday falling on a SUNDAY is "
            "substituted on the following working day, and Malaysia -- unlike Singapore -- also "
            "substitutes several SATURDAY holidays, which is why the two neighbours' closure "
            "calendars diverge in a way a shared-festival assumption gets wrong. State holidays "
            "(rulers' birthdays, Thaipusam in some states) close state offices and NOT the "
            "exchange, except where they coincide with a Federal Territory holiday.",
    "table": _HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED for the federal and Federal Territory dates",
               2025: "CONFIRMED for the federal and Federal Territory dates",
               2026: "PROVISIONAL -- fixed dates and the substitution law are certain; Islamic "
                     "dates are carried at their expected values (Aidilfitri 1447H on 20-21 "
                     "March 2026) and the gazette is the authority"},
    "regional_note": "Hari Raya Aidilfitri closes Malaysia, Indonesia, Singapore and Brunei "
                     "within the same two days, and Chinese New Year closes Malaysia, Singapore, "
                     "China, Hong Kong, Taiwan, Korea and Vietnam. A Malaysian holiday statistic "
                     "measured without the regional overlap is measuring the whole of Asia being "
                     "shut",
    "palm_note": "when the 10th of the month falls inside a holiday block the MPOB print moves, "
                 "which is the one calendar interaction in this pack that changes a tradable "
                 "clock rather than only the closure",
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "Bursa Malaysia daily participation by investor type",
     "root": "https://www.bursamalaysia.com/market_information/equities_prices",
     "fields": ("local institution", "local retail", "foreign institution", "foreign retail",
                "net buy and sell by category"),
     "frequency": "daily", "publish_utc": "10:00", "lag_days": 0, "licence": "free, public",
     "why": "a four-way participation split published daily and free; the foreign institution "
            "line is the positioning series a Malaysian flow claim rests on"},
    {"name": "BNM foreign holdings of Malaysian Government Securities",
     "root": "https://www.bnm.gov.my/monthly-highlights-statistics",
     "fields": ("non-resident holdings of MGS and GII", "share of outstanding"),
     "frequency": "monthly", "publish_utc": "07:00", "lag_days": 30, "licence": "free, public",
     "why": "one of the highest foreign ownership shares in emerging Asia, held by investors with "
            "no offshore currency market to hedge in -- a structural asymmetry worth measuring"},
    {"name": "BNM international reserves, twice monthly",
     "root": "https://www.bnm.gov.my/international-reserves",
     "fields": ("total reserves", "months of retained imports", "short-term external debt cover"),
     "frequency": "twice monthly", "publish_utc": "07:00", "lag_days": 7,
     "licence": "free, public",
     "why": "TWICE monthly is faster than most of this region and gives two intervention "
            "observations a month instead of one"},
    {"name": "MPOB monthly stocks, production and exports",
     "root": "https://bepi.mpob.gov.my/",
     "fields": ("closing stocks", "crude palm oil production", "exports", "imports",
                "stock-to-usage ratio"),
     "frequency": "monthly", "publish_utc": "04:00", "lag_days": 10, "licence": "free, public",
     "why": "the hard monthly supply-demand print for the visible half of the world palm market, "
            "and the single most tradable Malaysian clock"},
    {"name": "cargo surveyor intramonth export estimates",
     "root": "https://www.intertek.com/agriculture/ (and AmSpec and SGS wire releases)",
     "fields": ("month-to-date export volume", "year-on-year change by destination"),
     "frequency": "five times a month", "publish_utc": "02:00", "lag_days": 0,
     "licence": "published to the wires; the underlying service is commercial",
     "why": "turns an opaque month into five dated observations, and three independent surveyors "
            "publishing the same quantity gives a free cross-check"},
    {"name": "CFTC Commitments of Traders",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("non-commercial net in soybeans, soybean oil, crude, the dollar index",),
     "frequency": "weekly", "publish_utc": "20:30", "lag_days": 3, "licence": "free, public",
     "why": "MYR is not in the COT and neither is palm oil. The soybean-oil leg is the closest "
            "positioning read on the vegetable-oil complex this desk can get"},
)

# --------------------------------------------------------------------------- terminology
#: Bahasa Malaysia first. BNM, the ministries and the domestic press publish in Malay, and the
#: Chinese-language business press carries the plantation and commodity trade's own commentary.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "MY-A": ("Bank Negara Malaysia", "Kadar Dasar Semalaman", "dasar monetari",
             "Jawatankuasa Dasar Monetari", "kadar faedah", "inflasi", "pertumbuhan ekonomi",
             "国家银行", "隔夜政策利率", "货币政策会议"),
    "MY-B": ("ringgit", "kadar pertukaran", "nilai ringgit", "ringgit melemah", "ringgit menguat",
             "kadar rujukan", "非国际化", "令吉"),
    "MY-C": ("penghantaran pulang", "penukaran hasil eksport", "Kumpulan Wang Simpanan Pekerja",
             "pelaburan luar negara", "syarikat berkaitan kerajaan", "repatriation", "汇回资金",
             "公积金海外资产"),
    "MY-D": ("minyak sawit mentah", "stok minyak sawit", "pengeluaran", "eksport sawit",
             "Lembaga Minyak Sawit Malaysia", "棕榈油", "库存"),
    "MY-E": ("duti eksport", "cukai eksport sawit", "harga rujukan", "anggaran eksport",
             "penyiasat kargo", "出口税", "船运调查机构"),
    "MY-F": ("biodiesel", "mandatori B20", "minyak kacang soya", "minyak sayuran",
             "penggantian", "substitution", "生物柴油", "豆油价差"),
    "MY-G": ("Petronas", "minyak dan gas", "gas asli cecair", "dividen Petronas", "hasil petroleum",
             "eksport tenaga", "国油", "液化天然气出口"),
    "MY-H": ("sekuriti kerajaan Malaysia", "pegangan asing", "bon", "hasil bon",
             "pelabur asing", "外资持有"),
    "MY-I": ("Bursa Malaysia", "niaga hadapan", "tarikh luput", "kontrak", "FKLI", "FCPO",
             "指数期货"),
    "MY-J": ("cuti umum", "Hari Raya Aidilfitri", "Tahun Baru Cina", "Deepavali",
             "cuti bursa", "kecairan", "开斋节", "屠妖节", "休市"),
    "MY-K": ("subsidi", "subsidi diesel", "rasionalisasi subsidi", "harga runcit", "inflasi",
             "RON95"),
    "MY-L": ("penularan", "korelasi serantau", "mata wang serantau", "proksi",
             "regional transmission"),
}

# --------------------------------------------------------------------------- the source layers
#: THE TEN SOURCE LAYERS (principal's per-country depth rule, 2026-09-17). A country is never
#: "covered" by five obvious sources. Every layer below is either POPULATED or named in
#: `ABSENT_SOURCE_LAYERS` with a reason; blank is not an option, because a blank layer is
#: indistinguishable from a layer nobody looked at.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology",
    "app_ecosystem", "media", "archive", "physical_economy", "source_graph")

#: The three INDEPENDENT labels every source carries. They are independent on purpose: an
#: AUTHORITATIVE source can be NOT_PREDICTIVE, and a FRINGE one can be PREDICTIVE. Collapsing
#: them into a single "quality" score is how a desk quietly stops looking at the material that
#: disagrees with it.
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

    `machine_use_allowed=False` means the terms of the page FORBID automated extraction. Such a
    source is REGISTERED and never scraped: it stays visible so that a later session knows the
    material exists and knows why the desk has not read it, which is the opposite of omitting it.

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
    _src("MY-S1", "Bank Negara Malaysia and the government", layer="official",
         roots=("https://www.bnm.gov.my/monetary-policy-statements",
                "https://www.bnm.gov.my/monthly-highlights-statistics",
                "https://www.bnm.gov.my/international-reserves",
                "https://www.dosm.gov.my/", "https://www.mof.gov.my/portal/en/news/press-release"),
         languages=("ms", "en"), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("kenyataan dasar monetari", "kadar dasar semalaman terkini",
                  "rizab antarabangsa dua kali sebulan", "belanjawan dividen Petronas",
                  "statistik perdagangan bulanan"),
         notes="the MPC statement at 07:00 UTC with NO press conference, so the written text is "
               "the whole event; twice-monthly reserves; and the annual report where BNM explains "
               "the non-internationalisation policy in its own words"),
    _src("MY-S2", "Bursa, the regulator, the palm board and the multilaterals",
         layer="institutional",
         roots=("https://www.bursamalaysia.com/market_information/",
                "https://www.sc.com.my/", "https://bepi.mpob.gov.my/",
                "https://www.mpoc.org.my/", "https://www.imf.org/en/Countries/MYS"),
         languages=("ms", "en"), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("spesifikasi kontrak FCPO tamat tempoh", "penyertaan pelabur harian Bursa",
                  "stok minyak sawit akhir bulan", "MPOB monthly stocks production exports"),
         notes="MPOB's statutory census on the 10th at 04:00 UTC is the most tradable Malaysian "
               "clock there is, and BEPI carries the free historical series that makes a "
               "long-sample palm study possible at all"),
    _src("MY-S3", "Malaysian and multilateral academic work", layer="academic",
         roots=("https://www.krinstitute.org/Publications.aspx",
                "https://www.imf.org/en/Publications/WP",
                "https://www.bnm.gov.my/publications/working-papers",
                "https://www.adb.org/publications"),
         languages=("ms", "en"), licence="free, public", access_label="PUBLIC",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("kesan penukaran hasil eksport ringgit",
                  "ringgit non-internationalisation policy research",
                  "palm oil price transmission Malaysia study"),
         notes="Khazanah Research Institute and BNM's own working papers are where the 2024 "
               "repatriation campaign and the conversion rules are analysed rather than reported, "
               "which is what MY-C needs a prior from"),
    _src("MY-S4", "the plantation and commodity trade's own practitioners", layer="practitioner",
         roots=("https://www.theedgemalaysia.com/categories/plantation",
                "https://klse.i3investor.com/web/blog",
                "https://www.mpoa.org.my/", "https://www.palmoilanalytics.com/"),
         languages=("ms", "en", "zh"), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("anggaran eksport sawit ITS AmSpec", "harga FCPO bulan ketiga",
                  "nisbah stok penggunaan sawit", "棕榈油 库存 预估"),
         notes="the cargo-surveyor estimates on the 10th, 15th, 20th, 25th and month end reach "
               "the market through this layer before they reach any official series, and the "
               "three surveyors' DISAGREEMENT is discussed here and nowhere else"),
    _src("MY-S5", "retail investor forums", layer="retail_ecology",
         roots=("https://klse.i3investor.com/", "https://forum.lowyat.net/topic/",
                "https://www.reddit.com/r/MalaysianPF/"),
         languages=("ms", "en", "zh"), licence="public web; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("saham goreng", "syndicate saham", "kaunter ladang", "ringgit kukuh bila",
                  "種植 股 讨论"),
         notes="i3investor is where the Malaysian retail cohort discusses the plantation counters "
               "and the palm cycle, in three languages. UNRELIABLE as fact and useful as a read "
               "on when the palm story has reached the retail crowd, which is late by "
               "construction"),
    _src("MY-S6", "retail trading apps and the brokerage plumbing", layer="app_ecosystem",
         roots=("https://www.rakutentrade.my/", "https://www.malacca.com.my/",
                "https://www.bursamalaysia.com/trade/our_products_services/bursa_anywhere",
                "https://www.moomoo.com/my"),
         languages=("ms", "en"), licence="public web; platform terms vary",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("caj brokerage saham Malaysia", "Bursa Anywhere e-dividend",
                  "platform dagangan derivatif FKLI"),
         notes="Rakuten Trade's flat-fee entry changed Malaysian retail participation measurably "
               "after 2017; Bursa Anywhere is the exchange's own retail rail. ACCESS_UNCLEAR: the "
               "product pages are public and the data terms are not uniformly stated"),
    _src("MY-S7", "Malaysian media in three languages", layer="media",
         roots=("https://theedgemalaysia.com/", "https://www.thestar.com.my/business",
                "https://www.bernama.com/en/business/", "https://www.bharian.com.my/bisnes",
                "https://www.enanyang.my/"),
         languages=("ms", "en", "zh"), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("ringgit menguat penukaran eksport", "subsidi diesel dimansuhkan",
                  "令吉 汇率", "harga minyak sawit hari ini", "马来西亚 棕油 出口税 最新"),
         notes="the domestic political economy of subsidy, palm and the ringgit is argued in "
               "Malay first and in Chinese for the plantation trade; an English-only crawler sees "
               "a translation days later and misses the physical basis talk entirely"),
    _src("MY-S8", "the federal gazette and the archives", layer="archive",
         roots=("https://lom.agc.gov.my/federal-gazette.php",
                "https://www.arkib.gov.my/", "https://web.archive.org/web/*/bnm.gov.my*"),
         languages=("ms", "en"), licence="free, public", access_label="PUBLIC_ARCHIVE",
         credibility="AUTHORITATIVE", predictive_state="NOT_PREDICTIVE",
         queries=("warta kerajaan cukai eksport sawit", "perintah kastam duti eksport",
                  "gazette public holidays Malaysia"),
         notes="the export duty schedule and the gazetted holiday list are legal instruments, and "
               "the gazette is where the substitution rules that make MY-J's calendar diverge "
               "from Singapore's are actually written. NOT_PREDICTIVE: an archive dates"),
    _src("MY-S9", "the physical economy: mills, ports, power and weather",
         layer="physical_economy",
         roots=("https://bepi.mpob.gov.my/index.php/en/sectoral-status",
                "https://www.met.gov.my/", "https://www.tnb.com.my/",
                "https://www.northport.com.my/", "https://www.lgm.gov.my/"),
         languages=("ms", "en"), licence="free, public", access_label="OPEN_DATA",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("hasil buah tandan segar sebulan", "ramalan hujan semenanjung",
                  "muatan kapal Port Klang", "harga getah SMR20"),
         notes="MPOB publishes MILL-LEVEL yield and extraction rates, which is the biological "
               "upstream of the palm production seasonal MY-E and MY-F depend on, and the rubber "
               "board publishes the SMR20 price this pack can only reach through a proxy"),
    _src("MY-S10", "the source graph: registries and mirrors",
         layer="source_graph",
         roots=("https://data.gov.my/", "https://data.worldbank.org/country/malaysia",
                "https://comtradeplus.un.org/", "https://stats.bis.org/"),
         languages=("ms", "en"), licence="open data", access_label="OPEN_DATA",
         credibility="RELIABLE", predictive_state="NOT_PREDICTIVE",
         queries=("Comtrade Malaysia palm oil exports", "katalog data.gov.my",
                  "BIS effective exchange rate ringgit"),
         notes="THE META LAYER, and it matters here for one reason above all: the ringgit has no "
               "offshore market, so BIS's published effective exchange rate is one of the very "
               "few INDEPENDENT reconstructions of the currency's path and is the natural "
               "cross-check on the onshore reference rate"),
    _src("MY-S11", "licensed cargo surveyor services and price assessors",
         layer="institutional",
         roots=("https://www.intertek.com/agriculture/", "https://www.amspecgroup.com/",
                "https://www.spglobal.com/commodityinsights/en/our-methodology/"),
         languages=("en",), licence="headline estimates carried by the wires; the service is "
                                   "commercial",
         access_label="LICENSED", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         machine_use_allowed=False,
         notes="REGISTERED AND NOT SCRAPED. The surveyors' full cargo detail is a commercial "
               "product whose terms forbid automated extraction; the HEADLINE month-to-date "
               "figure is carried by the wires and is what MY-E actually uses. The row exists so "
               "a later session knows the richer data is real and deliberately unread"),
    _src("MY-S12", "rumour channels and unverified chatter", layer="retail_ecology",
         roots=("https://t.me/s/", "https://www.facebook.com/groups/",
                "https://www.youtube.com/results?search_query="),
         languages=("ms", "en", "zh"), licence="public social; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("ringgit akan jatuh", "khabar angin subsidi", "saham panas esok",
                  "EPF akan bawa balik duit"),
         notes="FRINGE AND KEPT. Malaysian rumour about subsidy removal timing and about EPF "
               "repatriation is frequently wrong and occasionally precedes the announcement, "
               "because these are coordinated political decisions that leak. Low weight, FRINGE "
               "label attached, never promoted to a fact, never deleted"),
)

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("MPOB monthly palm oil stocks, production and exports",
            source="Malaysian Palm Oil Board", coverage="1980-", frequency="monthly",
            publication_lag_days=10, revisions="prior month occasionally restated",
            licence="free, public", history_from="1980-01-01", pit_feasible=True,
            assets=("SOYBEAN", "XTIUSD"),
            mechanism_families=("supply_demand", "commodity_print"),
            how_to_fetch="BEPI's statistics portal; the release is on the 10th at 12:00 MYT "
                         "(04:00 UTC) and moves when the 10th falls in a holiday block"),
    dataset("cargo surveyor palm oil export estimates",
            source="Intertek, AmSpec and SGS", coverage="2005-", frequency="five times a month",
            publication_lag_days=0, revisions="each estimate supersedes the last",
            licence="published to the wires; the service itself is commercial",
            history_from="2010-01-01", pit_feasible=True, assets=("SOYBEAN",),
            mechanism_families=("intramonth_flow", "nowcast"),
            how_to_fetch="wire releases on the 10th, 15th, 20th, 25th and month end; three "
                         "independent estimates of the same quantity give a free cross-check and "
                         "their DISAGREEMENT is itself informative"),
    dataset("BNM USD/MYR reference rate", source="Bank Negara Malaysia", coverage="2005-",
            frequency="daily", publication_lag_days=0, revisions="none", licence="free, public",
            history_from="2005-07-21", pit_feasible=True, assets=("USDSGD", "USDIDR"),
            mechanism_families=("fixing", "policy_state"),
            how_to_fetch="the BNM exchange rate page at 15:30 MYT. NOT DIRECTLY TRADABLE here: "
                         "it is an input to a transmission study, never a symbol"),
    dataset("BNM international reserves", source="Bank Negara Malaysia", coverage="1990-",
            frequency="twice monthly", publication_lag_days=7, revisions="rare",
            licence="free, public", history_from="1990-01-01", pit_feasible=True,
            assets=("USDSGD", "USDX"), mechanism_families=("intervention", "reserve_adequacy"),
            how_to_fetch="published on the 7th and the 22nd at 15:00 MYT, which gives two "
                         "intervention observations a month rather than one"),
    dataset("foreign holdings of Malaysian Government Securities",
            source="Bank Negara Malaysia", coverage="2004-", frequency="monthly",
            publication_lag_days=30, revisions="rare", licence="free, public",
            history_from="2004-01-01", pit_feasible=True, assets=("UST10Y", "USDSGD"),
            mechanism_families=("flows", "positioning"),
            how_to_fetch="the monthly highlights and statistics release; the share has been among "
                         "the highest in emerging Asia for two decades"),
    dataset("Bursa Malaysia daily participation by investor type",
            source="Bursa Malaysia", coverage="2010-", frequency="daily",
            publication_lag_days=0, revisions="none", licence="free, public",
            history_from="2010-01-01", pit_feasible=True, assets=("HK50", "AUS200"),
            mechanism_families=("flows", "risk_appetite"),
            how_to_fetch="the market information pages; a four-way split published free and "
                         "daily, which most markets do not offer"),
    dataset("Malaysian monthly trade statistics",
            source="Department of Statistics Malaysia", coverage="1990-", frequency="monthly",
            publication_lag_days=30, revisions="routine", licence="free, public",
            history_from="1990-01-01", pit_feasible=True,
            assets=("SOYBEAN", "XNGUSD", "US500"),
            mechanism_families=("trade_cycle", "electronics_cycle"),
            how_to_fetch="the DOSM release; the electrical and electronics line carries the "
                         "Penang semiconductor cluster and tracks the global chip cycle"),
    dataset("Malaysian CPI", source="Department of Statistics Malaysia", coverage="2000-",
            frequency="monthly", publication_lag_days=21, revisions="rare",
            licence="free, public", history_from="2000-01-01", pit_feasible=True,
            assets=("USDSGD",), mechanism_families=("inflation", "subsidy_passthrough"),
            how_to_fetch="the DOSM release; the June 2024 diesel subsidy removal and the RON95 "
                         "targeted-subsidy programme are administrative STEPS in this series and "
                         "not inflation in the usual sense"),
    dataset("palm oil export duty schedule and the monthly reference price",
            source="Ministry of Finance / Malaysian Palm Oil Board", coverage="2013-",
            frequency="monthly", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2013-01-01", pit_feasible=True,
            assets=("SOYBEAN",), mechanism_families=("commodity_policy", "export_economics"),
            how_to_fetch="the duty rate for each month is set from the PRECEDING month's average "
                         "reference price, which makes the duty a MECHANICAL function of a known "
                         "number and therefore forecastable a month ahead"),
    dataset("BNM monetary policy statements", source="Bank Negara Malaysia", coverage="2004-",
            frequency="six a year", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2004-01-01", pit_feasible=True,
            assets=("USDSGD", "UST10Y"), mechanism_families=("policy_event", "tone"),
            how_to_fetch="the statement archive; BNM holds no routine press conference, so the "
                         "written statement is the entire event and a text feature set is the "
                         "only tone signal available"),
    dataset("Petronas quarterly results and the federal dividend",
            source="Petronas and the Ministry of Finance", coverage="2010-",
            frequency="quarterly, with the dividend annual", publication_lag_days=45,
            revisions="none", licence="free, public", history_from="2010-01-01",
            pit_feasible=True, assets=("XBRUSD", "XNGUSD"),
            mechanism_families=("fiscal", "energy_receipts"),
            how_to_fetch="Petronas publishes results despite being unlisted; the dividend to the "
                         "federal government is a budget line and is the fiscal transmission of "
                         "an oil price move"),
    dataset("Malaysian LNG export volumes",
            source="Department of Statistics Malaysia and Petronas", coverage="2000-",
            frequency="monthly", publication_lag_days=30, revisions="routine",
            licence="free, public", history_from="2000-01-01", pit_feasible=True,
            assets=("XNGUSD", "XBRUSD"), mechanism_families=("energy_exports", "terms_of_trade"),
            how_to_fetch="the trade statistics gas line; NOTE that Malaysian LNG prices off "
                         "Asian and oil-linked benchmarks and not off Henry Hub, so XNGUSD is an "
                         "IMPERFECT proxy and any edge must carry that caveat"),
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor(
        "Bank Negara Malaysia's non-internationalisation policy",
        holds="the legal and supervisory authority to keep ringgit trading onshore",
        forced_to=("enforce the prohibition on offshore ringgit business continuously, because a "
                   "single tolerated channel reopens the whole market",
                   "provide an onshore hedging market deep enough that the prohibition is "
                   "bearable for foreign bond holders",
                   "accept that the currency cannot trade for sixteen hours a day"),
        when="continuously since the 1998 capital controls",
        information=("bank-level supervisory data on ringgit positions",
                     "offshore pricing it does not recognise but can observe"),
        constraints=("the tension between the prohibition and foreign investors' need to hedge",
                     "IMF and index-provider views on market accessibility",
                     "the risk that enforcement drives foreign money out of MGS entirely"),
        instruments=("USDSGD", "USDIDR", "USDTHB"),
        counterparties=("global banks", "foreign holders of MGS",
                        "offshore desks that would make an NDF market if permitted"),
        observables=("the absence of USDMYR from every offshore venue including this broker's "
                     "registry",
                     "BNM circulars to banks", "the onshore forward curve with no offshore "
                     "counterpart"),
        impact="removes the ringgit from the tradable universe entirely and forces every "
               "Malaysian claim into a non-Malaysian instrument; it also removes the "
               "onshore-offshore basis that every other restricted currency in this region "
               "provides as a free intervention observable",
        persistence="in force for more than a quarter of a century and re-affirmed repeatedly; "
                    "a relaxation would be a first-order event for this whole pack",
        falsifier="the appearance of a quotable USDMYR on any offshore retail venue, or a BNM "
                  "statement recognising the NDF market, would end the transmission-only "
                  "constraint and require this pack to be rewritten"),
    actor(
        "Bank Negara Malaysia's Monetary Policy Committee",
        holds="the Overnight Policy Rate and the statutory reserve requirement",
        forced_to=("set policy without a numerical inflation target, so the reaction function is "
                   "estimated rather than announced",
                   "print at 07:00 UTC, the same hour as Bank Indonesia and the Bank of Thailand"),
        when="six times a year at 15:00 MYT",
        information=("domestic credit and deposit data it supervises",
                     "the subsidy rationalisation schedule, which is a known future CPI shock"),
        constraints=("no inflation target",
                     "a growth mandate held jointly with the finance ministry",
                     "an exchange rate it will not defend explicitly but plainly cares about"),
        instruments=("UST10Y", "USDSGD"),
        counterparties=("domestic banks", "foreign MGS holders"),
        observables=("the OPR", "the written statement, with no press conference to interpret it",
                     "KLIBOR and MYOR"),
        impact="a rate path that moved almost not at all between 2023 and mid-2025, which means "
               "the policy variable carries very little variance in the recent sample and a "
               "rate-surprise cell fitted on it is fitted on almost nothing",
        persistence="structural; the absence of a target is a long-standing institutional choice",
        falsifier="the adoption of a numerical inflation target would change the reaction "
                  "function and invalidate any estimated version of it"),
    actor(
        "The Employees Provident Fund",
        holds="above a trillion ringgit of members' retirement savings, with roughly a third "
              "invested overseas",
        forced_to=("repatriate and convert foreign investment income when directed to support the "
                   "currency, as in the 2024 campaign",
                   "meet an annual dividend expectation that is politically salient",
                   "deploy monthly contributions regardless of market level"),
        when="monthly contributions; repatriation episodes are policy-driven and dated",
        information=("its own portfolio", "government coordination requests"),
        constraints=("a statutory overseas allocation ceiling",
                     "the dividend it must declare each year",
                     "member withdrawal schemes that have been opened episodically"),
        instruments=("USDSGD", "US500", "UST10Y"),
        counterparties=("global asset managers", "the domestic bond and equity markets",
                        "Bank Negara"),
        observables=("the annual report's overseas allocation share",
                     "the declared dividend", "quarterly investment income"),
        impact="the largest single repatriation lever the Malaysian state has, and the one that "
               "did most of the work in the 2024 ringgit recovery; its ACTIONS are a policy "
               "variable rather than a market one, which is what makes them datable",
        persistence="structural as an institution; the repatriation CAMPAIGNS are episodic and "
                    "each is a dated event",
        falsifier="a ringgit depreciation episode of comparable size to 2024 with no coordinated "
                  "repatriation would say the lever has been retired"),
    actor(
        "Khazanah, Permodalan Nasional and the other government-linked investment companies",
        holds="sovereign and quasi-sovereign portfolios with material foreign assets",
        forced_to=("participate in coordinated conversion campaigns when the state asks",
                   "fund domestic commitments in ringgit"),
        when="episodic; the 2024 campaign is the documented instance",
        information=("their own allocations", "government coordination"),
        constraints=("investment mandates", "returns expectations from their own stakeholders"),
        instruments=("USDSGD", "US500"),
        counterparties=("global markets", "the domestic economy"),
        observables=("annual reports", "the currency's behaviour during a campaign",
                     "official statements naming the participants"),
        impact="converts a currency defence from an FX-reserve operation into a PORTFOLIO "
               "operation, which does not show in reserves and therefore is invisible to the "
               "standard intervention observable",
        persistence="episodic and policy-driven",
        falsifier="a campaign announced with no measurable currency effect over the following two "
                  "quarters"),
    actor(
        "Petronas",
        holds="the national oil and gas book: crude, condensate, and one of the world's larger "
              "LNG export complexes",
        forced_to=("sell into Brent-linked and Asian-benchmark-linked contracts",
                   "pay an annual dividend to the federal government that is a budget line",
                   "fund domestic subsidy obligations indirectly through that dividend"),
        when="continuous export; the dividend is set annually with the budget",
        information=("its own production and contract book", "Asian LNG demand"),
        constraints=("state ownership and the fiscal expectation attached to it",
                     "reserve depletion and the capital expenditure needed to offset it"),
        instruments=("XBRUSD", "XNGUSD"),
        counterparties=("Japanese, Korean and Chinese LNG buyers", "the federal government"),
        observables=("Petronas quarterly results", "the dividend line in the October budget",
                     "monthly LNG export volumes in the trade data"),
        impact="makes Malaysia a net energy EXPORTER on gas -- the opposite sign to Thailand, the "
               "Philippines and India -- which makes it the natural CONTROL in any regional "
               "oil-and-currency study rather than another data point",
        persistence="structural, with a slow decline as domestic fields mature",
        falsifier="a sustained crude rally with a deteriorating Malaysian trade balance would say "
                  "the net exporter status has flipped"),
    actor(
        "Plantation companies and palm oil refiners",
        holds="the estates, mills and refineries behind roughly a quarter of world palm oil "
              "production",
        forced_to=("harvest on a biological cycle with a pronounced seasonal peak from August to "
                   "October and a trough in the first quarter",
                   "pay an export duty whose rate is set mechanically from the preceding month's "
                   "reference price",
                   "compete for the same Indian and Chinese buyers as Indonesian refiners"),
        when="continuous production with a strong within-year seasonal; the duty is monthly",
        information=("their own yields", "the MPOB census they contribute to",
                     "the Indonesian levy, which determines their competitiveness"),
        constraints=("labour shortages, which bound production materially after 2020",
                     "the export duty schedule",
                     "replanting cycles that determine yield years ahead"),
        instruments=("SOYBEAN", "XTIUSD"),
        counterparties=("Indian and Chinese importers", "Indonesian competitors",
                        "the domestic biodiesel programme"),
        observables=("MPOB production", "the stock-to-usage ratio", "the export duty rate",
                     "the palm-to-soybean-oil spread"),
        impact="the biological production seasonal is one of the strongest and most physically "
               "grounded seasonals in any commodity, and unlike most agricultural seasonals it "
               "is a YIELD cycle rather than a harvest date, so it is smooth and predictable",
        persistence="structural and biological; the LABOUR constraint after 2020 is a level shift "
                    "that a pre-2020 seasonal model will over-predict through",
        falsifier="a production year whose monthly profile is flat against the historical "
                  "seasonal with no labour or weather explanation"),
    actor(
        "The Malaysian Palm Oil Board as an information actor",
        holds="the statutory monthly census of the palm oil balance",
        forced_to=("publish on the 10th of each month at 12:00 MYT",
                   "collect from every mill and refinery under statute"),
        when="04:00 UTC on the 10th, moving when the 10th falls in a holiday block",
        information=("the census before publication",),
        constraints=("statutory collection obligations", "a published release calendar"),
        instruments=("SOYBEAN",),
        counterparties=("the whole vegetable-oil complex",),
        observables=("the release itself", "the pre-release survey consensus published by wires"),
        impact="the only hard monthly supply-demand print in the vegetable-oil complex, and the "
               "one that makes palm a MEASURABLE market rather than an opaque one; the surprise "
               "against the wire survey is the tradable object, not the level",
        persistence="statutory and stable for decades",
        falsifier="a release whose surprise against the wire consensus produces no move in the "
                  "palm complex, repeatedly"),
    actor(
        "Cargo surveyors as intramonth information producers",
        holds="the loading records of the ports palm oil leaves through",
        forced_to=("publish on the 10th, 15th, 20th, 25th and month end because the market pays "
                   "for the service and the wires carry the headline",
                   "compete on accuracy with two rivals measuring the same thing"),
        when="five times a month, morning MYT",
        information=("port loading data ahead of the market",),
        constraints=("coverage gaps at smaller ports",
                     "commercial confidentiality on individual cargoes"),
        instruments=("SOYBEAN",),
        counterparties=("traders", "the wires", "each other"),
        observables=("the three published estimates and their disagreement",),
        impact="turns an opaque month into five dated observations, which converts the palm market "
               "from monthly to roughly weekly for research purposes -- and the DISAGREEMENT "
               "between three independent estimates of the same quantity is a free measure of "
               "the information's own reliability",
        persistence="commercial and stable",
        falsifier="a month in which the three surveyors agree closely and the MPOB print differs "
                  "materially from all of them"),
    actor(
        "Indian and Chinese palm oil importers",
        holds="the demand side of the world palm market, concentrated in two buyers",
        forced_to=("buy ahead of Indian festival demand and Chinese New Year",
                   "switch between palm and soft oils on price and on import duty"),
        when="Indian buying concentrates before Diwali; Chinese buying before the Lunar New Year",
        information=("their own stocks", "domestic duty schedules",
                     "the palm-to-soft-oil spread"),
        constraints=("Indian import duty on crude and refined vegetable oils, which has been "
                     "changed repeatedly",
                     "Chinese state reserve policy"),
        instruments=("SOYBEAN", "USDINR", "USDCNH"),
        counterparties=("Malaysian and Indonesian refiners",),
        observables=("Indian monthly vegetable oil import data",
                     "Chinese customs data", "the destination breakdown in surveyor estimates"),
        impact="demand is festival-dated on the Indian side and lunar-dated on the Chinese side, "
               "so palm demand carries TWO moving calendars, which is why a Gregorian seasonal "
               "fits the demand side badly even though it fits the supply side well",
        persistence="structural; India and China have been the two largest buyers for decades",
        falsifier="a Diwali or Lunar New Year season with no measurable pre-buying in the "
                  "destination breakdown"),
    actor(
        "Foreign holders of Malaysian Government Securities",
        holds="roughly a third of the MGS market, unhedgeable offshore",
        forced_to=("hold the currency risk onshore or unhedged, because no offshore ringgit "
                   "market exists",
                   "rebalance against EM local-currency benchmarks"),
        when="continuous, published monthly with a thirty-day lag",
        information=("BNM's monthly statistics", "the auction calendar"),
        constraints=("index weights",
                     "the non-internationalisation policy, which makes the hedge expensive or "
                     "impossible"),
        instruments=("UST10Y", "USDSGD"),
        counterparties=("domestic banks and the EPF", "Bank Negara"),
        observables=("the monthly foreign holding share", "the MGS-UST spread",
                     "auction bid-to-cover"),
        impact="a large foreign holder base carrying unhedged currency risk is structurally "
               "fragile: an outflow is simultaneously a bond sale and a currency sale with no "
               "hedge to unwind, which is why Malaysian outflow episodes are sharper than the "
               "size of the flow suggests",
        persistence="structural; the share has been high for two decades",
        falsifier="an outflow episode in which the bond market moves and the currency does not"),
    actor(
        "Malaysian exporters under the conversion regime",
        holds="dollar export proceeds from palm, energy, electronics and rubber",
        forced_to=("convert a share of export proceeds into ringgit under BNM's rules, with the "
                   "share and the incentives changed episodically",
                   "hold the rest in onshore foreign-currency accounts"),
        when="continuous, with month-end invoice clustering",
        information=("their own receivables", "the conversion rules in force"),
        constraints=("the conversion requirement itself",
                     "the interest differential between onshore dollar and ringgit deposits"),
        instruments=("USDSGD", "SOYBEAN", "XNGUSD"),
        counterparties=("onshore banks", "Bank Negara"),
        observables=("onshore foreign-currency deposit balances",
                     "the export-conversion incentives announced by BNM"),
        impact="the Malaysian analogue of Indonesia's retention rule, but softer and more often "
               "adjusted -- which makes it a worse natural experiment and a better example of a "
               "continuously varying policy parameter",
        persistence="structural in principle, episodic in the details",
        falsifier="a change in the conversion regime with no measurable change in onshore "
                  "foreign-currency deposit balances"),
    actor(
        "The Penang semiconductor assembly and test cluster",
        holds="a back-end semiconductor packaging and test capacity that is globally significant",
        forced_to=("ship on the customer's schedule",
                   "invest against a global chip cycle it does not control"),
        when="continuous, visible monthly in the electrical and electronics trade line",
        information=("customer order books", "the global semiconductor cycle"),
        constraints=("export controls on advanced equipment",
                     "competition from Vietnam and from reshoring incentives elsewhere"),
        instruments=("US500", "USDSGD", "USDKRW"),
        counterparties=("US, Taiwanese and Chinese chipmakers",),
        observables=("the monthly electrical and electronics export line",
                     "the Malaysian manufacturing PMI", "global chip billings"),
        impact="ties Malaysia's export cycle to US technology capital spending, which is the one "
               "Malaysian channel that reaches a US index rather than a commodity",
        persistence="structural and growing as supply chains diversify out of China",
        falsifier="a quarter of falling Malaysian electronics exports with rising global chip "
                  "billings"),
    actor(
        "The federal subsidy rationalisation programme",
        holds="the administered prices of diesel and petrol and the fiscal cost of subsidising "
              "them",
        forced_to=("remove or target subsidies to control the deficit, which is a deliberate "
                   "CPI shock",
                   "time each step to survive politically"),
        when="announcements at short notice; diesel was floated in June 2024 and the petrol "
             "programme followed",
        information=("the fiscal cost of the subsidy at prevailing crude prices",
                     "the political calendar"),
        constraints=("public reaction", "the deficit target in the October budget"),
        instruments=("XBRUSD", "USDSGD"),
        counterparties=("households", "the bond market, which rewards deficit reduction"),
        observables=("the announcement itself", "administered pump prices",
                     "the CPI transport component"),
        impact="an ADMINISTRATIVE step in the CPI series that is not inflation in the usual sense; "
               "a cell that treats it as a demand-driven price move is mis-reading the mechanism, "
               "and a policy reaction fitted through it is fitted on a fiscal decision",
        persistence="a multi-year programme with episodic steps",
        falsifier="a subsidy removal with no step in the CPI transport component"),
    actor(
        "Bursa Malaysia derivatives participants",
        holds="the FCPO and FKLI open interest",
        forced_to=("roll FCPO before the 15th of the contract month",
                   "close FKLI on the last business day",
                   "trade the THIRD forward month in FCPO because the front month is illiquid "
                   "into delivery"),
        when="the FCPO expiry on the 15th and the FKLI expiry on the last business day",
        information=("the MPOB calendar", "physical basis at the ports"),
        constraints=("physical delivery obligations in FCPO",
                     "position limits"),
        instruments=("SOYBEAN", "HK50"),
        counterparties=("refiners hedging", "speculators", "Chinese and Indian buyers"),
        observables=("open interest by contract month", "the third-month basis",
                     "expiry-day volume"),
        impact="two expiry rules that differ from every other venue in this region -- the 15th "
               "and the last business day -- which makes Malaysia a useful CONTROL for any "
               "regional expiry study: an effect that is really about the third Friday cannot "
               "appear here",
        persistence="stable contract design",
        falsifier="a third-Friday effect appearing in FCPO or FKLI, which would show the effect "
                  "is not about contract expiry at all"),
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("MY-A", "BNM policy decisions in a three-central-bank hour",
           objects=("six OPR decisions a year at 07:00 UTC",
                    "the written statement, with no press conference",
                    "the July 2025 cut after a long hold",
                    "the statutory reserve requirement as an alternative lever"),
           conditions=("whether Bank Indonesia or the Bank of Thailand prints in the same hour",
                       "the subsidy rationalisation schedule, a known future CPI shock",
                       "the absence of a numerical inflation target"),
           instruments=("UST10Y", "USDSGD", "USDIDR"),
           controls=("the same statistic on days when BNM alone prints at 07:00 UTC versus days "
                     "when two or three of the regional central banks do",
                     "the same statistic at 07:00 UTC on non-decision days",
                     "Thai and Indonesian decisions as the regional factor"),
           notes="three Southeast Asian central banks share the 07:00 UTC hour. A regional event "
                 "study that does not separate them is attributing one bank's move to another"),
    domain("MY-B", "The non-internationalised ringgit as a structural constraint",
           objects=("the absence of USDMYR from every offshore venue",
                    "the onshore-only 07:30 UTC reference rate",
                    "the sixteen hours a day in which the currency does not trade",
                    "BNM circulars enforcing the prohibition"),
           conditions=("whether the Malaysian session is open",
                       "whether a shock lands inside or outside the onshore hours"),
           instruments=("USDSGD", "USDIDR", "USDTHB", "USDCNH"),
           controls=("USDIDR and USDTHB, which are restricted but have offshore NDF markets, so "
                     "the difference between them and Malaysia isolates the effect of the "
                     "prohibition rather than of restriction in general",
                     "the same statistic on days when a Malaysian shock lands during Asian hours "
                     "versus during the US session"),
           notes="THE FOUNDING DOMAIN. Everything else here is downstream of the fact that the "
                 "currency cannot be traded, which is a policy choice and not a data gap"),
    domain("MY-C", "The state repatriation lever as a dated policy flow",
           objects=("the 2024 coordinated repatriation and conversion campaign",
                    "GLIC overseas allocation shares",
                    "the export-conversion rules and their incentives",
                    "onshore foreign-currency deposit balances"),
           conditions=("whether a campaign is in progress",
                       "the ringgit's level against its own multi-year range, which is what "
                       "triggers a campaign"),
           instruments=("USDSGD", "US500", "UST10Y"),
           controls=("the same period in Indonesia and Thailand, which faced the same dollar and "
                     "no campaign",
                     "the years before 2024, when the lever was not used",
                     "reserves, which should NOT move if the mechanism is portfolio repatriation "
                     "rather than intervention -- the sharpest control in this domain"),
           notes="a currency defence that does not appear in reserves is invisible to the "
                 "standard intervention observable, which is exactly why this needs its own "
                 "domain and its own control"),
    domain("MY-D", "The MPOB print on the 10th at 04:00 UTC",
           objects=("closing stocks, production, exports and the stock-to-usage ratio",
                    "the wire survey consensus published beforehand",
                    "the surprise against that consensus"),
           conditions=("the seasonal phase: the August-October production peak or the "
                       "first-quarter trough",
                       "whether the 10th falls inside a holiday block, which moves the release",
                       "the level of Indonesian stocks, the invisible half of the balance"),
           instruments=("SOYBEAN", "XTIUSD"),
           controls=("the same statistic on the 10th of months with no MPOB release",
                     "US soybean WASDE release dates, which move the same complex without any "
                     "Malaysian cause",
                     "the pre-release consensus: the LEVEL is anticipated and only the SURPRISE "
                     "can carry information"),
           notes="the single most tradable Malaysian clock, and the reason is that it is the only "
                 "hard monthly supply-demand print in the whole vegetable-oil complex"),
    domain("MY-E", "Intramonth cargo surveyor estimates and the mechanical export duty",
           objects=("estimates on the 10th, 15th, 20th, 25th and month end",
                    "the disagreement between three independent surveyors",
                    "the export duty, set from the preceding month's average reference price"),
           conditions=("the destination mix, India versus China versus the rest",
                       "whether the surveyors agree or diverge"),
           instruments=("SOYBEAN", "USDINR", "USDCNH"),
           controls=("the duty's mechanical formula as a forecastability check: if the duty is a "
                     "known function of a known number, its announcement cannot be news, and an "
                     "announcement effect would falsify the formula",
                     "the same dates in months with no surveyor release"),
           notes="the duty is MECHANICALLY determined a month ahead, which makes it a rare case "
                 "of a policy variable that is perfectly forecastable -- and therefore a test of "
                 "whether the market actually prices what it can compute"),
    domain("MY-F", "Palm, soy and the vegetable-oil substitution complex",
           objects=("the palm-to-soybean-oil spread",
                    "the biodiesel blending economics against crude",
                    "Indian vegetable oil import duty changes",
                    "Indonesian levy and mandate decisions"),
           conditions=("the crude price, which sets biodiesel demand for both oils",
                       "the Indian duty in force",
                       "relative stock levels in each oil"),
           instruments=("SOYBEAN", "XTIUSD", "CORN"),
           controls=("CORN as a placebo: it shares the agricultural and biofuel factor and is not "
                     "a vegetable oil, so an effect that appears in CORN too is a biofuel effect "
                     "and not a substitution one",
                     "US soybean crop events, which move SOYBEAN with no palm cause",
                     "a two-link decomposition: the Malaysian event must move palm, and palm must "
                     "move SOYBEAN"),
           notes="STATED AS A WEAKNESS: this broker quotes the BEAN, and palm competes with "
                 "soybean OIL. Every edge from Malaysia to SOYBEAN runs through two links and "
                 "this domain's controls exist to find out whether the second one carries "
                 "anything at all"),
    domain("MY-G", "Petronas, LNG and the net-energy-exporter sign",
           objects=("Petronas quarterly results and the federal dividend",
                    "monthly LNG and crude export volumes",
                    "the October budget's petroleum revenue assumption"),
           conditions=("the Brent level and the Asian LNG benchmark",
                       "the subsidy cost, which moves in the opposite direction to the revenue"),
           instruments=("XBRUSD", "XNGUSD", "USDSGD"),
           controls=("Thailand, the Philippines and India, which are net energy IMPORTERS, so the "
                     "sign of the oil-to-currency relationship must be OPPOSITE; a study in "
                     "which Malaysia and Thailand show the same sign has not identified anything",
                     "the subsidy cost as the offsetting fiscal leg"),
           notes="Malaysia is the natural CONTROL in any regional oil-and-currency study rather "
                 "than another data point, because it is the only net energy exporter in this "
                 "department's Southeast Asian set"),
    domain("MY-H", "Foreign MGS ownership and unhedgeable duration",
           objects=("the monthly foreign holding share",
                    "the MGS-to-UST spread",
                    "auction bid-to-cover",
                    "the absence of an offshore hedge"),
           conditions=("the global EM local-rates cycle",
                       "whether the foreign holder can hedge onshore at reasonable cost"),
           instruments=("UST10Y", "USDSGD"),
           controls=("Indonesian and Thai foreign bond flow, which share the EM factor and CAN be "
                     "hedged offshore -- the difference isolates the hedging constraint",
                     "domestic holder behaviour, which has no currency risk at all"),
           notes="an outflow here is simultaneously a bond sale and an unhedged currency sale, "
                 "which is why Malaysian outflow episodes are sharper than the size of the flow "
                 "predicts; that sharpness is the testable claim"),
    domain("MY-I", "Bursa expiry rules as a regional control",
           objects=("FCPO expiry on the 15th of the contract month",
                    "FKLI expiry on the last business day",
                    "the FCPO third-forward-month benchmark convention",
                    "the two-hour lunch break"),
           conditions=("which contract", "open interest against its trailing median",
                       "whether the expiry date falls in a holiday block"),
           instruments=("SOYBEAN", "HK50"),
           controls=("the THIRD FRIDAY of the same months, which is not an expiry on either "
                     "Malaysian contract -- so a third-Friday effect appearing here falsifies any "
                     "regional expiry claim built on that date",
                     "SGX's second-last business day and NSE's Tuesday, two more distinct rules"),
           notes="Malaysia's value in a regional expiry study is precisely that its rules are "
                 "different: it is the placebo the other venues cannot provide"),
    domain("MY-J", "Holiday liquidity and the overlapping festival calendar",
           objects=("Hari Raya Aidilfitri, which closes four markets in two days",
                    "Chinese New Year, which closes seven",
                    "the Saturday and Sunday substitution rules",
                    "the interaction with the MPOB release date"),
           conditions=("how many regional markets are shut simultaneously",
                       "whether the closure moves a scheduled print"),
           instruments=("SOYBEAN", "USDSGD", "USDIDR"),
           controls=("days when Malaysia alone is shut, the isolating condition",
                     "Singapore's non-substitution of Saturday holidays, which makes the two "
                     "neighbours' calendars diverge and provides a within-festival control",
                     "volume as well as price, since a liquidity claim must show in both"),
           notes="the MPOB interaction is the one that matters: a holiday block that moves the "
                 "10th moves a tradable clock, not just a closure"),
    domain("MY-K", "Subsidy rationalisation as an administrative CPI step",
           objects=("the June 2024 diesel float",
                    "the targeted petrol programme that followed",
                    "administered pump prices",
                    "the CPI transport component"),
           conditions=("the crude price at the time of each step",
                       "the deficit target in the October budget",
                       "the political calendar"),
           instruments=("XBRUSD", "USDSGD", "UST10Y"),
           controls=("the CPI excluding administered prices, which isolates demand-driven "
                     "inflation from the fiscal step",
                     "Indonesian fuel price adjustments, the same mechanism under a different "
                     "government"),
           notes="an administrative step is not inflation in the usual sense, and a policy "
                 "reaction function fitted through one is fitted on a fiscal decision"),
    domain("MY-L", "How much of a Malaysian move survives into a tradable symbol",
           objects=("the correlation of the onshore reference rate with USDSGD, USDIDR, USDTHB "
                    "and USDCNH",
                    "the sixteen-hour window in which only the proxies trade",
                    "the leakage of a Malaysian shock into the neighbours"),
           conditions=("whether the Malaysian session is open",
                       "whether the shock is commodity-driven, which the neighbours share, or "
                       "policy-driven, which they do not",
                       "the regional risk regime"),
           instruments=("USDSGD", "USDIDR", "USDTHB", "USDCNH"),
           controls=("the dollar factor, residualised out first, because most of the raw "
                     "correlation between any two Asian currencies is the dollar",
                     "a commodity-versus-policy split on the source of the Malaysian shock",
                     "USDHKD as a null proxy: a pegged currency should carry NONE of the "
                     "Malaysian signal, and if it does the whole measurement is a dollar artefact"),
           notes="THE HONEST DOMAIN. The expectation is that most of a Malaysian move does NOT "
                 "survive into any single proxy, and this domain exists to measure how much does "
                 "rather than to assume a proxy works"),
)

# --------------------------------------------------------------------------- miners (specs)
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("my_mpob_surprise", domain_ids=("MY-D",), kind="event",
          entry="research.countries.my.miners:mpob_surprise", cadence_s=86400.0, steerable=False,
          notes="SPEC, NOT YET WIRED. Measures the SURPRISE against the wire consensus, never the "
                "level, and handles the release date moving when the 10th falls in a holiday "
                "block"),
    miner("my_surveyor_bridge", domain_ids=("MY-E",), kind="nowcast",
          entry="research.countries.my.miners:surveyor_bridge", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Uses the DISAGREEMENT between three independent surveyors "
                "as a reliability weight rather than averaging them blindly"),
    miner("my_duty_forecastability", domain_ids=("MY-E",), kind="event",
          entry="research.countries.my.miners:duty_forecastability", cadence_s=604800.0,
          notes="SPEC, NOT YET WIRED. Tests whether a duty that is a known function of a known "
                "number produces any announcement effect at all -- a direct test of whether the "
                "market prices what it can compute"),
    miner("my_substitution_two_link", domain_ids=("MY-F",), kind="cross_asset",
          entry="research.countries.my.miners:substitution_two_link", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Decomposes every palm-to-SOYBEAN claim into two links and "
                "reports the second link's strength separately, with CORN as the biofuel placebo"),
    miner("my_repatriation_campaign", domain_ids=("MY-C",), kind="flow",
          entry="research.countries.my.miners:repatriation_campaign", cadence_s=604800.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Checks reserves as the control: a portfolio repatriation "
                "must NOT show as intervention, and if it does the mechanism is mis-identified"),
    miner("my_net_exporter_sign", domain_ids=("MY-G",), kind="cross_country",
          entry="research.countries.my.miners:net_exporter_sign", cadence_s=604800.0,
          notes="SPEC, NOT YET WIRED. Runs the oil-to-currency relationship for Malaysia against "
                "the region's net importers and fails the study when the signs agree"),
    miner("my_proxy_survival", domain_ids=("MY-L", "MY-B"), kind="transmission",
          entry="research.countries.my.miners:proxy_survival", cadence_s=3600.0, steerable=False,
          notes="SPEC, NOT YET WIRED. Measures how much of an onshore ringgit move survives into "
                "each proxy AFTER the dollar factor is removed, with USDHKD as the null"),
    miner("my_expiry_placebo", domain_ids=("MY-I",), kind="calendar",
          entry="research.countries.my.miners:expiry_placebo", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Supplies the third-Friday placebo that no other venue in "
                "this region can provide"),
    miner("my_holiday_clock_shift", domain_ids=("MY-J",), kind="calendar",
          entry="research.countries.my.miners:holiday_clock_shift", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Detects when a holiday block moves the MPOB release date, "
                "which changes a tradable clock rather than only a closure"),
)

# --------------------------------------------------------------------------- transmission seeds
#: EVERY edge here terminates in a non-Malaysian symbol, because no Malaysian symbol exists on
#: this broker. That is the pack's defining constraint made explicit.
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("MY-E01", source="MPOB closing-stock surprise against the wire consensus",
         mechanism="the only hard monthly supply-demand print in the vegetable-oil complex; a "
                   "stock surprise reprices palm, and palm and soy oil are substitutes",
         targets=("SOYBEAN",), sign="-", horizon="0 to 5 sessions",
         lag="10 days -- the print covers the preceding month and lands on the 10th at 04:00 UTC",
         control="US soybean WASDE dates, which move SOYBEAN with no Malaysian cause, and the "
                 "10th of months with no MPOB release",
         notes="FALSIFIER: no SOYBEAN response to a large MPOB surprise across a full year. The "
               "two-link caveat applies: the broker quotes the BEAN, not the oil"),
    edge("MY-E02", source="an Indonesian or Malaysian biodiesel mandate step",
         mechanism="a mandate step diverts palm from export to domestic diesel and ties the "
                   "vegetable-oil complex to the crude price through blending economics",
         targets=("SOYBEAN", "XTIUSD"), sign="+", horizon="1 to 2 quarters",
         lag="0 at the decree, with effect at the stated start date",
         control="CORN, which shares the biofuel factor and is not a vegetable oil, so an effect "
                 "appearing in CORN too is a biofuel effect and not a substitution one",
         notes="FALSIFIER: the same response in CORN as in SOYBEAN, which would identify the "
               "biofuel channel and kill the substitution claim"),
    edge("MY-E03", source="the Malaysian palm export duty rate",
         mechanism="the duty is set MECHANICALLY from the preceding month's average reference "
                   "price, so it is perfectly forecastable and its announcement should be a "
                   "non-event",
         targets=("SOYBEAN",), sign="0", horizon="0 to 2 sessions",
         lag="0 -- announced at month end for the following month",
         control="the duty's own formula, computed from the prior month's published prices",
         notes="FALSIFIER: a measurable announcement effect, which would show the market does not "
               "price what it can compute. Unsigned on purpose: the hypothesis is a NULL"),
    edge("MY-E04", source="Malaysian LNG and crude export receipts",
         mechanism="Malaysia is a net energy EXPORTER on gas, so an energy rally improves its "
                   "terms of trade and its fiscal position -- the OPPOSITE sign to its neighbours",
         targets=("XNGUSD", "XBRUSD", "USDSGD"), sign="+", horizon="1 to 2 quarters",
         lag="30 days on the trade data",
         control="Thailand, the Philippines and India, which are net energy importers and must "
                 "show the OPPOSITE sign; agreement between them and Malaysia means nothing has "
                 "been identified",
         notes="FALSIFIER: the same sign in Malaysia and in the region's net importers. NOTE that "
               "Malaysian LNG prices off Asian benchmarks, not Henry Hub, so XNGUSD is imperfect"),
    edge("MY-E05", source="the 2024-style coordinated repatriation campaign",
         mechanism="state-directed portfolio repatriation converts foreign assets into the "
                   "domestic currency without touching reserves, which is a currency defence "
                   "invisible to the standard intervention observable",
         targets=("USDSGD", "US500"), sign="-", horizon="1 to 3 quarters",
         lag="0 at the announcement; the flow is measurable only in annual reports",
         control="reserves, which must NOT move if the mechanism is portfolio repatriation, and "
                 "Indonesia and Thailand over the same period facing the same dollar",
         notes="FALSIFIER: a campaign with a measurable reserve change, which would mean it was "
               "ordinary intervention wearing a portfolio label"),
    edge("MY-E06", source="foreign net selling of Malaysian Government Securities",
         mechanism="a third of the market is foreign-held and CANNOT be hedged offshore, so an "
                   "outflow is a simultaneous bond and unhedged currency sale",
         targets=("UST10Y", "USDSGD"), sign="+", horizon="1 to 3 months", lag="30 days",
         control="Indonesian and Thai foreign bond flow, which share the EM factor and CAN be "
                 "hedged offshore -- the difference isolates the hedging constraint",
         notes="FALSIFIER: Malaysian outflow episodes no sharper than Indonesian or Thai ones of "
               "the same size, which would say the hedging constraint does not bite"),
    edge("MY-E07", source="the BNM OPR decision at 07:00 UTC",
         mechanism="one of three Southeast Asian central banks printing in the same hour; the "
                   "Malaysian decision reaches the regional complex through the rate differential",
         targets=("USDSGD", "USDIDR", "UST10Y"), sign="-", horizon="0 to 3 sessions", lag="0",
         control="days when BNM alone prints at 07:00 UTC against days when two or three print, "
                 "and 07:00 UTC on non-decision days",
         notes="FALSIFIER: an identical response whether BNM prints alone or alongside Bank "
               "Indonesia, which would mean the regional factor is doing the work"),
    edge("MY-E08", source="Malaysian electrical and electronics exports",
         mechanism="the Penang back-end semiconductor cluster ties Malaysia's export cycle to US "
                   "technology capital spending",
         targets=("US500", "USDSGD"), sign="+", horizon="1 to 2 quarters", lag="30 days",
         control="Singapore NODX electronics and Korean chip exports, which carry the same cycle "
                 "and must absorb the signal if Malaysia carries none of its own",
         notes="FALSIFIER: no incremental content once Singapore and Korea are in the model, "
               "which is the likely outcome and is worth measuring once"),
    edge("MY-E09", source="an onshore ringgit move during Malaysian hours",
         mechanism="with no offshore ringgit market, a Malaysian shock can only be expressed in "
                   "the neighbours, so it should LEAK into USDSGD and USDIDR",
         targets=("USDSGD", "USDIDR", "USDTHB"), sign="+", horizon="0 to 3 sessions",
         lag="0 -- the reference rate is published at 07:30 UTC",
         control="USDHKD as a null proxy, which is pegged and should carry NONE of the signal; "
                 "and the dollar factor residualised out first",
         notes="FALSIFIER: signal appearing in USDHKD too, which would prove the whole measurement "
               "is a dollar artefact. EXPECTATION: most of a Malaysian move does not survive"),
    edge("MY-E10", source="Indian vegetable oil import duty changes",
         mechanism="India is the largest single palm buyer and its duty is changed repeatedly; a "
                   "duty cut pulls physical demand forward into the Malaysian and Indonesian book",
         targets=("SOYBEAN", "USDINR"), sign="+", horizon="1 to 3 months",
         lag="0 at the notification",
         control="Chinese import data over the same period, the other large buyer, and the "
                 "destination breakdown in surveyor estimates",
         notes="FALSIFIER: an Indian duty change with no shift in the destination breakdown of "
               "Malaysian exports over the following two months"),
    edge("MY-E11", source="the palm oil production seasonal",
         mechanism="a biological yield cycle peaking August to October and troughing in the first "
                   "quarter -- smooth, physically grounded and unusually predictable for an "
                   "agricultural seasonal",
         targets=("SOYBEAN",), sign="0", horizon="within-year", lag="10 days on MPOB",
         control="the post-2020 labour constraint, a LEVEL shift that a pre-2020 seasonal model "
                 "will over-predict through; and US soybean seasonality, a harvest-date cycle "
                 "rather than a yield cycle",
         notes="FALSIFIER: a production year whose monthly profile is flat against the historical "
               "seasonal with no labour or weather explanation. Unsigned: the claim is shape"),
    edge("MY-E12", source="Malaysian subsidy rationalisation steps",
         mechanism="an administered price float converts a crude price move into a domestic CPI "
                   "step and a fiscal saving at the same time",
         targets=("XBRUSD", "UST10Y"), sign="0", horizon="1 to 2 quarters",
         lag="0 at the announcement, then 21 days on the CPI print",
         control="CPI excluding administered prices, and Indonesian fuel price adjustments as the "
                 "same mechanism under a different government",
         notes="FALSIFIER: a subsidy removal with no step in the CPI transport component. "
               "Unsigned: the fiscal and inflation legs point in opposite directions"),
    edge("MY-E13", source="cargo surveyor intramonth export estimates",
         mechanism="five dated observations a month turn an opaque market into a roughly weekly "
                   "one, and the estimate is published before the MPOB print it anticipates",
         targets=("SOYBEAN",), sign="+", horizon="0 to 3 sessions", lag="0",
         control="the surveyors' DISAGREEMENT as a reliability weight, and the same dates in "
                 "months with no release",
         notes="FALSIFIER: no response to a surveyor estimate that later proves accurate against "
               "the MPOB print, which would mean the intramonth channel carries nothing"),
    edge("MY-E14", source="Malaysian and Indonesian Hari Raya closure overlap",
         mechanism="four markets close within two days, so regional liquidity falls and the "
                   "palm complex loses its physical price discovery for a week",
         targets=("SOYBEAN", "USDIDR", "USDSGD"), sign="0",
         horizon="the closure window and the two sessions after",
         lag="0 -- the dates are gazetted a year ahead",
         control="days when Malaysia alone is shut, and Singapore's non-substitution of Saturday "
                 "holidays, which makes the neighbours' calendars diverge within the same festival",
         notes="FALSIFIER: no fall in volume across the closure. Must be measured in VOLUME as "
               "well as price or it is not a liquidity claim"),
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("MY-R1", start="1998-09-01", end="2005-07-20",
        label="the pegged ringgit under capital controls",
        what_changed="a hard peg at 3.80 to the dollar plus the non-internationalisation rules "
                     "that survive to this day",
        invalidates="the currency has no variance at all in this era, so nothing FX can be "
                    "estimated on it; the non-internationalisation policy, however, dates from "
                    "here and is the pack's founding constraint",
        notes="the prohibition on offshore ringgit trading is the part of 1998 that never ended"),
    era("MY-R2", start="2005-07-21", end="2014-12-31",
        label="managed float, commodity boom",
        what_changed="the peg was replaced by a managed float against a basket; the palm and "
                     "energy boom ran through the whole period",
        invalidates="a terms-of-trade coefficient fitted here is fitted on a one-way commodity "
                    "market and will not generalise",
        notes="foreign MGS ownership rose steadily through this era toward its peak"),
    era("MY-R3", start="2015-01-01", end="2020-02-29",
        label="the oil shock, 1MDB and the 2016 NDF crackdown",
        what_changed="the 2014-15 oil collapse hit a net energy exporter's fiscal position "
                     "directly; in November 2016 BNM moved forcefully against the offshore NDF "
                     "market after an offshore-driven depreciation episode",
        invalidates="the November 2016 crackdown is the sharpest break in the ringgit's "
                    "microstructure in two decades, and any onshore-offshore statistic spanning "
                    "it is two different markets",
        notes="this is the era in which the modern enforcement of non-internationalisation was "
              "set"),
    era("MY-R4", start="2020-03-01", end="2023-12-31",
        label="pandemic, EPF withdrawals and the weak-ringgit period",
        what_changed="special EPF withdrawal schemes drew down domestic savings, the labour "
                     "shortage bound palm production, and the ringgit weakened steadily toward "
                     "its 1998 lows",
        invalidates="a palm production seasonal fitted before 2020 over-predicts through the "
                    "labour constraint; a savings-flow model fitted here is fitted on emergency "
                    "withdrawals",
        notes="the OPR sat still for most of this era, so the policy variable has almost no "
              "variance in it"),
    era("MY-R5", start="2024-01-01", end="2025-06-30",
        label="the repatriation campaign and the ringgit recovery",
        what_changed="a coordinated GLIC and exporter conversion campaign took the ringgit from "
                     "about 4.80 to about 4.12 across 2024; diesel subsidies were floated in "
                     "June 2024",
        invalidates="a currency model with no policy-flow term cannot explain 2024 at all, and "
                    "one fitted on 2024 will expect a campaign that is not running",
        notes="the cleanest observation of the state repatriation lever that exists"),
    era("MY-R6", start="2025-07-01", end=None,
        label="the easing cycle begins",
        what_changed="the OPR was cut in July 2025, the first reduction since the pandemic, "
                     "while the targeted petrol subsidy programme rolled out",
        invalidates="the current regime; the policy variable has variance again for the first "
                    "time in years, which changes what a rate-surprise cell can even be fitted on",
        notes="what a live candidate is actually trading"),
)


# --------------------------------------------------------------------------- assembly
MISSION = (
    "mine Malaysia to exhaustion as a TRANSMISSION-ONLY country: the ringgit cannot "
    "be quoted here because Bank Negara prohibits offshore ringgit trading, so every "
    "claim must terminate in a non-Malaysian symbol -- the vegetable-oil complex "
    "through SOYBEAN, energy through XBRUSD and XNGUSD, the regional FX complex "
    "through USDSGD, USDIDR and USDTHB -- and MY-L exists to measure how much of a "
    "Malaysian move actually survives that trip rather than assuming a proxy works")
NOTES = (
    "NO MALAYSIAN INSTRUMENT IS EXECUTABLE. USDMYR, FCPO palm oil, the KLCI and FKLI, "
    "MGS, tin, rubber and KLIBOR are all named in this module's TRANSMISSION_TARGETS. "
    "The MPOB print on the 10th at 04:00 UTC is the most tradable Malaysian clock and "
    "reaches the desk only through SOYBEAN, across two links, which MY-F measures "
    "rather than assumes.")


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
        "transmission_targets": TRANSMISSION_TARGETS,
        "absent_source_layers": ABSENT_SOURCE_LAYERS,
        "mission": MISSION, "notes": NOTES,
    }


def pack() -> Any:
    """Malaysia's pack: `CountryPack` when the framework has landed, else the same fields as a
    dict. `transmission_targets` rides alongside the twenty-one frozen fields and carries USDMYR
    itself, because the absence of the country's own currency is this pack's first finding."""
    return build_pack(**fields())
