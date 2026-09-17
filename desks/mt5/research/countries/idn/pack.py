"""INDONESIA: triple intervention, a legislated export-proceeds rule, and the world's nickel.

THE THREE THINGS THAT MAKE INDONESIA ITS OWN MARKET AND NOT A GENERIC HIGH-BETA EM.

  1. A CENTRAL BANK THAT INTERVENES IN THREE MARKETS SIMULTANEOUSLY AND SAYS SO. Bank Indonesia
     calls it "triple intervention": spot, the domestic non-deliverable forward (DNDF, an
     onshore instrument BI created in 2018 precisely so that hedging demand would stop leaking
     offshore), and outright purchases of government bonds in the secondary market. Since
     September 2023 a fourth leg exists -- SRBI, a rupiah security BI issues itself at yields
     designed to attract foreign money. The research consequence is that an intervention here is
     not one observable but four, they are published on different clocks, and a cell that reads
     only spot is reading a quarter of the position.

  2. AN EXPORT-PROCEEDS RETENTION RULE WITH A DATE. Government Regulation 36/2023 required 30% of
     natural-resource export proceeds above USD 250,000 to be parked onshore for three months
     from August 2023. Regulation 8/2025 raised that to ONE HUNDRED PERCENT for twelve months
     with effect from 1 March 2025. That is a legislated, dated, structural change to the supply
     of dollars in the onshore market, and it is the single cleanest natural experiment in this
     whole department: the same economy, the same commodities, the same central bank, and a step
     change in how much of the export dollar has to come home.

  3. A COMMODITY EXPORT BOOK THAT SETS WORLD PRICES IN TWO MARKETS. Indonesia is the largest
     thermal coal exporter on earth, the largest palm oil producer, and supplies something close
     to half of the world's mined nickel. Its policy instruments are supply instruments: the ore
     export ban in force since 2020, the RKAB production quota system, the palm export levy and
     domestic market obligation, the biodiesel blending mandate that steps up by decree. When
     Jakarta changes a rule, the world price moves -- and the rule change is a published
     ministerial decree, not a market event.

WHAT IS EXECUTABLE AND WHAT IS NOT. USDIDR is quotable here. The two instruments Indonesia
actually sets the price of -- palm oil and thermal coal -- are NOT, and neither is the JCI, the
10-year INDOGB, the DNDF, SRBI or the JISDOR fix itself. They are named in
`TRANSMISSION_TARGETS` with the symbols their mechanisms reach: SOYBEAN for the vegetable-oil
substitution complex, XNGUSD and the crude pair for the coal-to-gas switching channel, XNIUSD for
nickel, XALUSD for the bauxite ban's aluminium leg, XCUUSD for Grasberg.

THE SUBSTITUTION CHANNEL IS THE HONEST PART AND IT IS STATED AS A WEAKNESS, NOT HIDDEN. The
broker quotes SOYBEAN, the bean, and palm oil competes with soybean OIL -- a different point in
the crush. The edge from an Indonesian palm decree to SOYBEAN therefore runs through two links,
each of which can break, and IDN-G carries the control that tests whether the second link is
carrying any signal at all. Naming that here is cheaper than discovering it after a hundred cells
have been compiled on it.

THE CALENDAR IS THE OTHER HALF OF THIS PACK. Indonesia closes its market for longer than any
other country in Asia: the Idul Fitri break plus the government's `cuti bersama` collective leave
routinely shuts the exchange for six to nine consecutive sessions, and the dates come from a joint
ministerial decree issued the preceding year rather than from a calendar rule. Currency in
circulation surges by a fifth in the weeks before it. And Indonesian corporates pay dividends to
foreign parents in the second quarter, which is a recurring, dated, seasonal dollar demand that
shows in USDIDR every year and in no textbook.

CUSTOM_MINERS ARE SPECIFICATIONS, NOT WIRING. Each names the module it will live in and the
inputs it must read. None is on a clock yet; unwired is a defect (III.16) and naming it is how the
defect stays visible rather than being reported as "built".
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
CODE = "ID"
NAME = "Indonesia"
REGION_COMMAND = "southeast_asia"
CURRENCY = "IDR"
FISCAL_YEAR_END = "12-31"  # the APBN state budget runs on the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("id", "jv", "en")

EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDIDR",                      # the one domestic quote; Forex Exotics
    "XNIUSD",                      # about half the world's mined nickel is Indonesian
    "XALUSD",                      # the bauxite export ban's aluminium leg
    "XCUUSD",                      # Grasberg, and the concentrate export rules
    "XTIUSD", "XBRUSD", "XNGUSD",  # a net crude importer and a huge LNG and coal exporter
    "SOYBEAN", "CORN",             # the vegetable-oil substitution complex and feed
    "COFROB", "SUGAR",             # the world's third robusta producer; a large sugar importer
    "USDCNH", "USDSGD", "USDTHB", "USDINR",  # the regional complex and the two largest buyers
    "USDX",                        # the dollar factor every IDR claim must be residualised on
    "UST10Y",                      # what foreign SBN money trades the spread to
    "HK50", "CHINAH", "AUS200", "US500",     # the EM risk channel and the coal-exporter proxy
    "XAUUSD",                      # a large domestic retail gold market and a reserve asset
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "crude palm oil (FCPO and the Indonesian export reference price)",
     "venue": "Bursa Malaysia Derivatives; Indonesian reference price set by decree",
     "why": "Indonesia is the largest producer and its export levy, domestic market obligation "
            "and biodiesel mandate are the world supply instruments; none of it is quotable here",
     "proxies": ("SOYBEAN", "USDIDR", "XTIUSD")},
    {"name": "Indonesian thermal coal and the HBA reference price",
     "venue": "ESDM ministerial decree; ICE Newcastle and API benchmarks",
     "why": "the world's largest thermal coal exporter sets a reference price by decree, now "
            "twice monthly; it is the largest single line in the export book",
     "proxies": ("XNGUSD", "XBRUSD", "AUS200", "USDIDR")},
    {"name": "IDX Composite (JCI) and LQ45", "venue": "Indonesia Stock Exchange",
     "why": "foreign net flow in the JCI is published daily and is a genuine positioning series; "
            "the index itself cannot be traded here",
     "proxies": ("HK50", "CHINAH", "USDIDR")},
    {"name": "10-year Indonesian government bond (INDOGB)", "venue": "secondary OTC / IDX",
     "why": "the foreign ownership share of SBN is the single most-watched EM Asia positioning "
            "number and BI buys this market as one leg of its intervention",
     "proxies": ("UST10Y", "USDIDR")},
    {"name": "Domestic Non-Deliverable Forward (DNDF)", "venue": "onshore interbank, BI auctions",
     "why": "BI created it in 2018 to pull hedging demand back onshore; the DNDF-to-offshore-NDF "
            "gap is the cleanest available read on how hard BI is defending the rupiah",
     "proxies": ("USDIDR", "USDCNH")},
    {"name": "SRBI, SVBI and SUVBI", "venue": "Bank Indonesia auctions",
     "why": "BI's own securities, introduced from September 2023, whose foreign holding share is "
            "published and is the newest hot-money channel into Indonesia",
     "proxies": ("USDIDR", "UST10Y")},
    {"name": "JISDOR spot reference rate", "venue": "Bank Indonesia",
     "why": "the transaction-based onshore fix published at 08:00 UTC; it settles domestic "
            "contracts and anchors the DNDF",
     "proxies": ("USDIDR",)},
    {"name": "refined tin", "venue": "LME and the Indonesia Commodity and Derivatives Exchange",
     "why": "Indonesia is a top-two refined tin exporter and its export-licensing delays in 2024 "
            "moved the world price; no tin contract exists in this universe",
     "proxies": ("XNIUSD", "XALUSD", "XCUUSD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank Indonesia",
    "short": "BI",
    "committee": "Rapat Dewan Gubernur (Board of Governors meeting), abbreviated RDG",
    "policy_instrument": "the BI-Rate, renamed from the BI 7-Day Reverse Repo Rate in 2024",
    "secondary_instruments": ("spot intervention",
                              "DNDF, the onshore non-deliverable forward BI auctions",
                              "outright secondary-market purchases of government securities",
                              "SRBI, SVBI and SUVBI issuance to attract and sterilise inflows",
                              "macroprudential liquidity incentives that direct bank credit"),
    "mandate": "rupiah stability -- BOTH against goods (inflation, targeted at 2.5% +/-1%) and "
               "against other currencies. The second half of that mandate is explicit in the "
               "central bank act and is why BI intervenes openly where other inflation targeters "
               "deny doing so",
    "decision_rule": "MONTHLY. A two-day RDG whose decision is announced on the second day at "
                     "about 14:00-14:30 WIB, generally in the third week of the month. Twelve "
                     "decisions a year is the highest frequency of any central bank in this "
                     "department and it makes BI the most event-dense currency here",
    "announce_local": "about 14:00-14:30 WIB", "announce_utc": "07:00",
    "presser_utc": "07:20",
    "off_cycle": "BI has acted between meetings through intervention rather than through rate "
                 "changes; an unscheduled rate move is rare, an unscheduled intervention "
                 "announcement is not",
    "other_clocks": (
        {"what": "JISDOR spot reference rate", "when_local": "about 15:00 WIB",
         "when_utc": "08:00", "reference_lag_days": 0},
        {"what": "weekly non-resident flow release (SBN, equities, SRBI)",
         "when_local": "Thursday or Friday", "when_utc": "10:00", "reference_lag_days": 3},
        {"what": "monthly foreign reserves", "when_local": "the 7th", "when_utc": "07:00",
         "reference_lag_days": 7},
        {"what": "SRBI auctions", "when_local": "Wednesday and Friday", "when_utc": "03:00",
         "reference_lag_days": 0},
        {"what": "government SBN and sukuk auctions", "when_local": "Tuesday, alternating",
         "when_utc": "03:00", "reference_lag_days": 0},
    ),
    "dates": {
        2024: ("2024-01-17", "2024-02-21", "2024-03-20", "2024-04-24", "2024-05-22",
               "2024-06-20", "2024-07-17", "2024-08-21", "2024-09-18", "2024-10-16",
               "2024-11-20", "2024-12-18"),
        2025: ("2025-01-15", "2025-02-19", "2025-03-19", "2025-04-23", "2025-05-21",
               "2025-06-18", "2025-07-16", "2025-08-20", "2025-09-17", "2025-10-22",
               "2025-11-19", "2025-12-17"),
        2026: (),
    },
    "dates_status": "RECONSTRUCTED from BI's published annual RDG schedule pattern (a mid-month "
                    "two-day meeting announcing on the second day) and NOT individually verified "
                    "against bi.go.id. Any event study must re-read the official schedule first: "
                    "a date that is a day out turns an event window into a placebo. 2026 is "
                    "UNMEASURED here rather than absent (L1.28a)",
}

#: The export-proceeds retention regime, as a dated state. This is the natural experiment the
#: pack is built around: the same economy and the same central bank, with a legislated step change
#: in how much of the export dollar must come home.
DHE_REGIME: tuple[dict[str, str], ...] = (
    {"from": "2019-01-01", "rule": "no binding onshore retention; proceeds had to enter the "
                                   "domestic banking system but could be converted out freely",
     "share": "0%", "tenor": "n/a",
     "note": "the baseline era; the export dollar was free to leave immediately"},
    {"from": "2023-08-01", "rule": "Government Regulation 36/2023: natural-resource export "
                                   "proceeds above USD 250,000 must be held onshore",
     "share": "30%", "tenor": "3 months",
     "note": "the first binding retention; incentives were attached through a special deposit "
             "instrument with a tax-favoured rate"},
    {"from": "2025-03-01", "rule": "Government Regulation 8/2025: the retention share is raised "
                                   "to the whole of natural-resource export proceeds",
     "share": "100%", "tenor": "12 months",
     "note": "THE EVENT. A step change in onshore dollar supply with a legislated date, applying "
             "to coal, palm oil, nickel, copper and the rest of the resource book"},
)

# --------------------------------------------------------------------------- fixings, settlement
#: WIB (Western Indonesia Time, Jakarta) is UTC+7 all year with no daylight saving.
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "JISDOR (Jakarta Interbank Spot Dollar Rate)",
     "administrator": "Bank Indonesia",
     "window_local": "USD/IDR interbank spot transactions from 08:00 to 14:45 WIB",
     "window_utc": "01:00-07:45", "publish_local": "about 15:00 WIB", "publish_utc": "08:00",
     "basis": "transaction-weighted average of actual interbank deals in the window; the "
              "methodology was revised in 2021 to use the whole window rather than a morning cut",
     "uses": "settlement of DNDF and of domestic contracts; the anchor the offshore NDF is "
             "priced against",
     "note": "a TRANSACTION-based fix, not a poll, which means it can be moved by trading in it "
             "and BI is one of the participants in the window"},
    {"name": "ABS/SFEMC IDR spot fixing",
     "administrator": "ABS Benchmarks Administration Co, Singapore",
     "window_local": "concluding about 11:00 SGT, which is 10:00 WIB",
     "window_utc": "02:30-03:00", "publish_local": "about 11:00 SGT", "publish_utc": "03:00",
     "basis": "the regional Asian currency fixing panel",
     "uses": "settlement of OFFSHORE IDR non-deliverable forwards",
     "note": "Indonesia therefore has TWO fixings five hours apart, an onshore one at 08:00 UTC "
             "and an offshore one at 03:00 UTC, and the gap between them is a measurable "
             "onshore-offshore basis that no single-fix cell can see"},
    {"name": "BI mid rate (kurs tengah) for accounting and customs",
     "administrator": "Bank Indonesia", "window_local": "daily", "window_utc": "08:00",
     "publish_local": "daily with the JISDOR", "publish_utc": "08:00",
     "basis": "the average of BI's buying and selling rates",
     "uses": "customs valuation, tax and corporate accounting translation",
     "note": "corporate translation demand keys to the month-end value of this rate, which is "
             "one reason Indonesian month-end flow is larger than the economy's size implies"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"market": "USD/IDR onshore interbank spot", "cycle": "T+2",
     "session_local": "08:00-16:00 WIB", "session_utc": "01:00-09:00",
     "note": "the rupiah is not freely deliverable offshore; BI restricts non-resident rupiah "
             "lending, which is why an offshore NDF market exists at all"},
    {"market": "DNDF", "cycle": "cash settled in rupiah against JISDOR",
     "session_local": "onshore hours, with BI auctions announced ad hoc",
     "session_utc": "01:00-09:00",
     "note": "an ONSHORE non-deliverable forward is an unusual instrument: it exists so that "
             "hedging demand which would otherwise price offshore prices onshore instead, under "
             "BI's eye"},
    {"market": "IDX equities", "cycle": "T+2 since 2018",
     "session_local": "09:00-11:30 and 13:30-15:00 WIB, plus a pre-closing auction and a "
                      "post-trading session",
     "session_utc": "02:00-04:30 and 06:30-08:00",
     "note": "the lunch break is real and is 90 minutes; an intraday statistic that ignores it "
             "is averaging across a closure"},
    {"market": "government securities (SBN)", "cycle": "T+2",
     "session_local": "09:00-16:00 WIB", "session_utc": "02:00-09:00",
     "note": "auctions on Tuesdays, alternating conventional and sukuk; the Ministry of Finance "
             "publishes DAILY foreign ownership with a one-to-two day lag, which is the best "
             "free bond-positioning series in Asia"},
    {"market": "IDX derivatives and single-stock futures", "cycle": "cash",
     "session_local": "as the cash market", "session_utc": "02:00-08:00",
     "note": "thin. Indonesian equity risk is hedged offshore or not at all, which is why the "
             "cash foreign-flow series carries so much information here"},
)

# --------------------------------------------------------------------------- exchanges
EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Indonesia Stock Exchange", "code": "IDX",
     "hours_local": "pre-opening 08:45-08:59 WIB, session I 09:00-11:30, session II "
                    "13:30-15:00, pre-closing 15:00-15:15, post-trading 15:15-15:30",
     "hours_utc": "02:00-04:30 and 06:30-08:00",
     "expiry_rule": "index futures expire on the last trading day of the contract month; the "
                    "listed derivatives market is small and illiquid",
     "settlement": "T+2 cash",
     "rebalance": "LQ45 and IDX30 reviewed twice a year, effective in February and August; "
                  "free-float weights revised quarterly",
     "auto_rejection": "IDX applies a symmetric daily price limit (auto-rejection) that varies "
                       "by price band and was tightened and loosened repeatedly in 2020-2021; "
                       "any intraday return distribution from that period is TRUNCATED by rule "
                       "and not by the market"},
    {"name": "Indonesia Commodity and Derivatives Exchange", "code": "ICDX",
     "hours_local": "09:30-16:30 WIB and an evening session",
     "hours_utc": "02:30-09:30",
     "expiry_rule": "monthly for physical tin and gold contracts",
     "settlement": "physical for tin",
     "rebalance": "n/a",
     "auto_rejection": "n/a -- but the tin export licensing regime it clears is itself the "
                       "supply constraint that moves the LME price"},
)

# --------------------------------------------------------------------------- the holiday rule
#: Indonesia closes for longer than any other market in Asia, and the reason is `cuti bersama`:
#: collective leave granted by a joint decree of three ministries, issued the preceding year and
#: sometimes amended. A calendar rule cannot produce these dates; only the decree can.
_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "Tahun Baru Masehi (New Year)",
        "2024-02-08": "Isra Mikraj",
        "2024-02-09": "Cuti bersama (Isra Mikraj)",
        "2024-02-14": "Pemilu (general election day)",
        "2024-03-11": "Hari Suci Nyepi",
        "2024-03-12": "Cuti bersama (Nyepi)",
        "2024-03-29": "Wafat Isa Almasih (Good Friday)",
        "2024-04-08": "Cuti bersama Idul Fitri",
        "2024-04-09": "Cuti bersama Idul Fitri",
        "2024-04-10": "Hari Raya Idul Fitri 1445H",
        "2024-04-11": "Hari Raya Idul Fitri 1445H",
        "2024-04-12": "Cuti bersama Idul Fitri",
        "2024-04-15": "Cuti bersama Idul Fitri",
        "2024-05-01": "Hari Buruh (Labour Day)",
        "2024-05-09": "Kenaikan Isa Almasih (Ascension)",
        "2024-05-10": "Cuti bersama (Ascension)",
        "2024-05-23": "Hari Raya Waisak",
        "2024-05-24": "Cuti bersama (Waisak)",
        "2024-06-17": "Hari Raya Idul Adha",
        "2024-06-18": "Cuti bersama (Idul Adha)",
        "2024-09-16": "Maulid Nabi Muhammad",
        "2024-12-25": "Hari Raya Natal (Christmas)",
        "2024-12-26": "Cuti bersama (Natal)",
    },
    2025: {
        "2025-01-01": "Tahun Baru Masehi (New Year)",
        "2025-01-27": "Isra Mikraj",
        "2025-01-28": "Cuti bersama (Tahun Baru Imlek)",
        "2025-01-29": "Tahun Baru Imlek (Chinese New Year)",
        "2025-03-28": "Cuti bersama (Nyepi)",
        "2025-03-29": "Hari Suci Nyepi",
        "2025-03-31": "Hari Raya Idul Fitri 1446H",
        "2025-04-01": "Hari Raya Idul Fitri 1446H",
        "2025-04-02": "Cuti bersama Idul Fitri",
        "2025-04-03": "Cuti bersama Idul Fitri",
        "2025-04-04": "Cuti bersama Idul Fitri",
        "2025-04-07": "Cuti bersama Idul Fitri",
        "2025-04-18": "Wafat Isa Almasih (Good Friday)",
        "2025-05-01": "Hari Buruh (Labour Day)",
        "2025-05-12": "Hari Raya Waisak",
        "2025-05-13": "Cuti bersama (Waisak)",
        "2025-05-29": "Kenaikan Isa Almasih (Ascension)",
        "2025-05-30": "Cuti bersama (Ascension)",
        "2025-06-06": "Hari Raya Idul Adha",
        "2025-06-27": "Tahun Baru Islam 1447H",
        "2025-09-05": "Maulid Nabi Muhammad",
        "2025-12-25": "Hari Raya Natal (Christmas)",
        "2025-12-26": "Cuti bersama (Natal)",
    },
    2026: {
        "2026-01-01": "Tahun Baru Masehi (New Year)",
        "2026-01-16": "Isra Mikraj",
        "2026-02-17": "Tahun Baru Imlek (Chinese New Year)",
        "2026-03-19": "Hari Suci Nyepi",
        "2026-03-20": "Hari Raya Idul Fitri 1447H",
        "2026-03-23": "Cuti bersama Idul Fitri",
        "2026-03-24": "Cuti bersama Idul Fitri",
        "2026-03-25": "Cuti bersama Idul Fitri",
        "2026-04-03": "Wafat Isa Almasih (Good Friday)",
        "2026-05-01": "Hari Buruh (Labour Day)",
        "2026-05-14": "Kenaikan Isa Almasih (Ascension)",
        "2026-05-27": "Hari Raya Idul Adha",
        "2026-06-01": "Hari Raya Waisak",
        "2026-06-16": "Tahun Baru Islam 1448H",
        "2026-08-17": "Hari Kemerdekaan (Independence Day)",
        "2026-08-26": "Maulid Nabi Muhammad",
        "2026-12-25": "Hari Raya Natal (Christmas)",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": "Two layers. The STATUTORY layer is the national holiday list: fixed Gregorian dates "
            "(1 January, 1 May, 17 August, 25 December), the Christian moveable feasts, and the "
            "Islamic, Balinese Hindu, Buddhist and Chinese lunar and lunisolar dates. The SECOND "
            "layer is `cuti bersama` -- collective leave granted by a joint decree of the "
            "ministries of religion, manpower and administrative reform, issued in the preceding "
            "year and occasionally amended. Cuti bersama is why the Idul Fitri break routinely "
            "shuts the exchange for six to nine consecutive sessions, and NO CALENDAR RULE CAN "
            "PRODUCE IT: the decree is the only authority. Islamic dates are set by the ministry "
            "of religion from local moon-sighting and can move by a day against a computed "
            "Islamic calendar. Independence Day (17 August) and the fixed dates produce no "
            "closure when they fall at a weekend, because Indonesia does not substitute.",
    "table": _HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED for the statutory dates and the announced cuti bersama",
               2025: "CONFIRMED for the statutory dates and the announced cuti bersama",
               2026: "PROVISIONAL -- fixed dates are certain; the Islamic dates are carried at "
                     "their expected values (Idul Fitri 1447H on 20 March 2026) and the cuti "
                     "bersama block around it is an ESTIMATE until the joint decree is read"},
    "longest_closure": "the Idul Fitri block. In 2025 the exchange was shut from 28 March to "
                       "7 April inclusive of weekends -- a gap across which no Indonesian "
                       "session statistic exists and across which every offshore NDF kept trading",
    "regional_note": "Chinese New Year (17 February 2026) closes Indonesia on the same day as "
                     "Singapore, Malaysia, Vietnam, China, Hong Kong, Taiwan and Korea",
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "DJPPR daily foreign ownership of government securities",
     "root": "https://www.djppr.kemenkeu.go.id/portal/id/data-statistik.html",
     "fields": ("foreign holdings of SBN by nominal", "share of outstanding",
                "holdings by holder type: banks, insurance, pension, BI, non-resident"),
     "frequency": "daily", "publish_utc": "10:00", "lag_days": 2, "licence": "free, public",
     "why": "a DAILY, free, official foreign-ownership series for a whole government bond market. "
            "Nothing else in Asia publishes this; it is the reason IDN-E is worth mining"},
    {"name": "Bank Indonesia weekly non-resident transaction release",
     "root": "https://www.bi.go.id/en/publikasi/ruang-media/news-release/",
     "fields": ("non-resident net purchase of SBN", "of equities", "of SRBI"),
     "frequency": "weekly", "publish_utc": "10:00", "lag_days": 3, "licence": "free, public",
     "why": "the SRBI line is the newest hot-money channel and did not exist before September "
            "2023, so any pre-2023 flow model is missing the instrument that now dominates"},
    {"name": "IDX daily foreign net buy and sell",
     "root": "https://www.idx.co.id/en/market-data/trading-summary/",
     "fields": ("foreign buy value", "foreign sell value", "net by board"),
     "frequency": "daily", "publish_utc": "09:00", "lag_days": 0, "licence": "free, public",
     "why": "with no meaningful domestic derivatives market, the cash foreign flow IS the "
            "positioning signal in Indonesian equity risk"},
    {"name": "Bank Indonesia monthly foreign reserves",
     "root": "https://www.bi.go.id/en/statistik/ekonomi-keuangan/",
     "fields": ("official reserve assets", "months of import cover"),
     "frequency": "monthly", "publish_utc": "07:00", "lag_days": 7, "licence": "free, public",
     "why": "the intervention observable. BI states an import-cover threshold publicly, which "
            "makes the reaction function partly announced rather than wholly inferred"},
    {"name": "SRBI auction results and foreign holding share",
     "root": "https://www.bi.go.id/en/statistik/", "fields": ("awarded amount", "weighted "
                                                              "average yield", "foreign share"),
     "frequency": "twice weekly", "publish_utc": "08:00", "lag_days": 0, "licence": "free, public",
     "why": "the yield BI pays to attract inflows is a published price for its own defence of "
            "the rupiah, which is as close to a stated intervention cost as any EM gets"},
    {"name": "CFTC Commitments of Traders",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("non-commercial net in the dollar index, crude, copper, soybeans",),
     "frequency": "weekly", "publish_utc": "20:30", "lag_days": 3, "licence": "free, public",
     "why": "IDR is not in the COT; these are the external legs of the transmission edges and the "
            "factors a commodity claim must be residualised against"},
)

# --------------------------------------------------------------------------- terminology
#: Bahasa Indonesia. A lexical search over English finds none of the domestic press, the ministry
#: decrees or the retail communities, and the decrees are where the supply policy actually lives.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "IDN-A": ("suku bunga acuan", "BI-Rate", "Rapat Dewan Gubernur", "kebijakan moneter",
              "Bank Indonesia", "inflasi", "stabilitas rupiah", "policy rate"),
    "IDN-B": ("intervensi", "triple intervention", "kurs", "nilai tukar", "rupiah melemah",
              "rupiah menguat", "cadangan devisa", "JISDOR"),
    "IDN-C": ("DNDF", "lindung nilai", "forward", "pasar valas", "hedging", "NDF offshore"),
    "IDN-D": ("devisa hasil ekspor", "DHE SDA", "penempatan devisa", "Peraturan Pemerintah",
              "retensi", "export proceeds retention"),
    "IDN-E": ("aliran modal asing", "investor asing", "surat berharga negara", "SBN",
              "kepemilikan asing", "SRBI", "lelang", "net beli asing"),
    "IDN-F": ("batu bara", "harga batubara acuan", "HBA", "ekspor batu bara", "royalti",
              "coal reference price"),
    "IDN-G": ("minyak sawit", "CPO", "pungutan ekspor", "bea keluar", "domestic market obligation",
              "DMO", "biodiesel", "B40", "mandatori"),
    "IDN-H": ("nikel", "bijih nikel", "RKAB", "smelter", "larangan ekspor", "hilirisasi",
              "kuota produksi"),
    "IDN-I": ("Lebaran", "Idul Fitri", "mudik", "THR", "tunjangan hari raya", "uang kartal",
              "cuti bersama", "libur bursa"),
    "IDN-J": ("dividen", "repatriasi", "musim dividen", "laba", "dividend season"),
    "IDN-K": ("neraca perdagangan", "ekspor", "impor", "surplus", "defisit transaksi berjalan",
              "harga komoditas"),
    "IDN-L": ("sesi perdagangan", "jam bursa", "auto rejection", "likuiditas", "spread",
              "sesi pertama", "sesi kedua"),
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

    `machine_use_allowed=False` means the terms of the page FORBID automated extraction. Such a
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
    _src("IDN-S1", "Bank Indonesia, the ministries and the statistics agency", layer="official",
         roots=("https://www.bi.go.id/id/publikasi/ruang-media/news-release/",
                "https://www.bi.go.id/id/statistik/",
                "https://www.djppr.kemenkeu.go.id/portal/id/data-statistik.html",
                "https://www.bps.go.id/", "https://www.ojk.go.id/id/kanal/pasar-modal/"),
         languages=("id", "en"), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("hasil rapat dewan gubernur", "suku bunga acuan BI-Rate terbaru",
                  "kepemilikan asing SBN harian", "cadangan devisa bulanan",
                  "transaksi nonresiden mingguan"),
         notes="the RDG statement at 07:00 UTC, JISDOR, the weekly non-resident flow release and "
               "DJPPR's DAILY foreign ownership file -- the last of which exists in Indonesian "
               "only and is the most valuable free series in this pack"),
    _src("IDN-S2", "the exchanges, the depository and the multilaterals", layer="institutional",
         roots=("https://www.idx.co.id/id/data-pasar/ringkasan-perdagangan/",
                "https://www.ksei.co.id/", "https://www.icdx.co.id/",
                "https://www.adb.org/countries/indonesia/main",
                "https://www.imf.org/en/Countries/IDN"),
         languages=("id", "en"), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("auto rejection batas atas bawah", "net beli asing harian IDX",
                  "kalender libur bursa", "IMF Article IV Indonesia reserves adequacy"),
         notes="the IDX trading summary carries the daily foreign flow AND the auto-rejection "
               "limits in force, which is the censoring parameter IDN-L is about"),
    _src("IDN-S3", "Indonesian and multilateral academic work", layer="academic",
         roots=("https://www.lpem.org/", "https://www.csis.or.id/publications/",
                "https://www.imf.org/en/Publications/WP", "https://www.adb.org/publications"),
         languages=("id", "en"), licence="free, public", access_label="PUBLIC",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("efektivitas intervensi valas Bank Indonesia",
                  "devisa hasil ekspor dampak rupiah", "triple intervention effectiveness"),
         notes="LPEM UI and CSIS are where the export-retention rule's effect is argued in "
               "Indonesian; the IMF staff reports are where the intervention's effectiveness is "
               "estimated. IDN-D's natural experiment needs a prior and this is where it comes "
               "from"),
    _src("IDN-S4", "the commodity trade's own practitioners", layer="practitioner",
         roots=("https://gapki.id/", "https://www.apbi-icma.org/",
                "https://www.bareksa.com/berita/", "https://www.idx.co.id/id/produk/"),
         languages=("id",), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("harga CPO hari ini", "pungutan ekspor sawit terbaru",
                  "produksi batu bara kuota RKAB", "mandatori B40 alokasi"),
         notes="GAPKI (the palm producers' association) and APBI (the coal miners') publish "
               "production and policy commentary in Indonesian days before an English wire picks "
               "it up; they are advocacy bodies, which is why the predictive state is a narrative "
               "feature rather than untested data"),
    _src("IDN-S5", "retail investor communities", layer="retail_ecology",
         roots=("https://stockbit.com/", "https://www.kaskus.co.id/forum/10/investasi/",
                "https://www.reddit.com/r/finansial/"),
         languages=("id",), licence="public web; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("saham gorengan", "bandar saham", "ARA ARB hari ini", "nyangkut saham",
                  "pom-pom saham"),
         notes="Stockbit is where the post-2020 Indonesian retail cohort actually talks, in a "
               "vocabulary ('saham gorengan' for a pumped stock, 'ARA/ARB' for the auto-rejection "
               "limits) that is untranslatable and that names the censoring mechanism IDN-L "
               "studies. UNRELIABLE as fact, informative as behaviour"),
    _src("IDN-S6", "retail brokerage and investment apps", layer="app_ecosystem",
         roots=("https://ajaib.co.id/", "https://bibit.id/", "https://stockbit.com/",
                "https://www.indopremier.com/ipotgo/", "https://www.bareksa.com/"),
         languages=("id",), licence="public web; API and platform terms vary",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("aplikasi saham pemula", "biaya transaksi broker", "reksa dana pasar uang",
                  "fitur auto invest"),
         notes="the 2020-2023 Indonesian retail boom happened ON these apps and the single-stock "
               "account count published by KSEI tracks their growth directly. ACCESS_UNCLEAR: "
               "product pages are public and the API terms are not uniformly stated"),
    _src("IDN-S7", "Indonesian financial press", layer="media",
         roots=("https://insight.kontan.co.id/", "https://www.cnbcindonesia.com/market",
                "https://katadata.co.id/finansial", "https://bisnis.com/",
                "https://www.tempo.co/ekonomi"),
         languages=("id",), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("rupiah melemah hari ini", "harga batubara acuan HBA",
                  "intervensi Bank Indonesia", "musim dividen emiten"),
         notes="Kontan and Bisnis carry the ministerial decree before the wires and carry the "
               "trade's reaction to it; the dividend-season coverage in April to June is where "
               "IDN-J's mechanism is described in the first person by the companies paying"),
    _src("IDN-S8", "the legal gazette and the decree archive", layer="archive",
         roots=("https://jdih.setneg.go.id/", "https://peraturan.bpk.go.id/",
                "https://web.archive.org/web/*/bi.go.id*"),
         languages=("id",), licence="free, public", access_label="PUBLIC_ARCHIVE",
         credibility="AUTHORITATIVE", predictive_state="NOT_PREDICTIVE",
         queries=("Peraturan Pemerintah 36 tahun 2023 devisa",
                  "Peraturan Pemerintah 8 tahun 2025 DHE", "permendag larangan ekspor CPO"),
         notes="THE ONLY WAY TO DATE IDN-D CORRECTLY. The two export-retention regulations have "
               "signature dates and effective dates that differ by weeks, and the whole natural "
               "experiment turns on using the EFFECTIVE date. NOT_PREDICTIVE by construction"),
    _src("IDN-S9", "the physical economy: mines, mills, ports, power and weather",
         layer="physical_economy",
         roots=("https://www.minerba.esdm.go.id/", "https://www.esdm.go.id/id/harga-acuan",
                "https://www.bmkg.go.id/", "https://www.pln.co.id/statistics",
                "https://www.pelindo.co.id/"),
         languages=("id",), licence="free, public", access_label="PUBLIC",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("harga batubara acuan bulan ini", "RKAB disetujui nikel",
                  "prakiraan cuaca pelayaran", "konsumsi listrik industri"),
         notes="the coal reference price and the nickel production quotas are published on "
               "ministry portals as DECREES, not as data feeds, which means the physical-economy "
               "layer here is a document feed and the series has to be built rather than "
               "downloaded"),
    _src("IDN-S10", "the source graph: registries and multilateral mirrors",
         layer="source_graph",
         roots=("https://data.go.id/", "https://data.worldbank.org/country/indonesia",
                "https://comtradeplus.un.org/", "https://www.imf.org/en/Countries/IDN"),
         languages=("id", "en"), licence="open data", access_label="OPEN_DATA",
         credibility="RELIABLE", predictive_state="NOT_PREDICTIVE",
         queries=("Comtrade Indonesia nickel exports", "katalog data BPS",
                  "World Bank Indonesia commodity exports"),
         notes="THE META LAYER, and it earns its place here because Indonesian nickel and coal "
               "export volumes as reported by BPS and as MIRRORED by importing countries' customs "
               "have differed materially -- a discrepancy that is itself evidence about "
               "under-reporting and is invisible if only one source is read"),
    _src("IDN-S11", "licensed commodity assessments and vendor data", layer="institutional",
         roots=("https://www.spglobal.com/commodityinsights/en/our-methodology/"
                "methodology-specifications", "https://www.argusmedia.com/en/methodology"),
         languages=("en",), licence="methodology free; assessments licensed",
         access_label="LICENSED", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         machine_use_allowed=False,
         notes="REGISTERED AND NOT SCRAPED. Assessed Indonesian coal and palm prices would be the "
               "ideal inputs to IDN-F and IDN-G; the terms forbid automated extraction. The free "
               "substitute is the HBA decree itself, which is published and is what the pack uses"),
    _src("IDN-S12", "rumour channels and pump groups", layer="retail_ecology",
         roots=("https://t.me/s/", "https://www.facebook.com/groups/",
                "https://www.youtube.com/results?search_query="),
         languages=("id",), licence="public social; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("bocoran saham besok", "rumor rupiah dijaga", "info bandar",
                  "saham auto ARA besok"),
         notes="FRINGE AND KEPT. Indonesian pump groups and rupiah rumours are frequently false "
               "and occasionally anticipate a genuine decree, because decrees here arrive with "
               "little notice and leak. Low weight, FRINGE label attached, never promoted to a "
               "fact, never deleted"),
)

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("JISDOR daily reference rate", source="Bank Indonesia", coverage="2013-",
            frequency="daily", publication_lag_days=0, revisions="none", licence="free, public",
            history_from="2013-05-20", pit_feasible=True, assets=("USDIDR",),
            mechanism_families=("fixing", "intervention"),
            how_to_fetch="bi.go.id statistics, published about 15:00 WIB. The 2021 methodology "
                         "revision widened the transaction window and is a break in the series, "
                         "not a refinement of it"),
    dataset("DJPPR daily foreign ownership of SBN", source="Ministry of Finance / DJPPR",
            coverage="2010-", frequency="daily", publication_lag_days=2,
            revisions="occasional restatement of the holder split", licence="free, public",
            history_from="2010-01-01", pit_feasible=True, assets=("USDIDR", "UST10Y"),
            mechanism_families=("flows", "positioning"),
            how_to_fetch="the data-statistik page; take the non-resident line and the BI line "
                         "separately: BI's own holdings are an INTERVENTION, not a flow"),
    dataset("Bank Indonesia weekly non-resident flows", source="Bank Indonesia",
            coverage="2015-", frequency="weekly", publication_lag_days=3, revisions="none",
            licence="free, public", history_from="2015-01-01", pit_feasible=True,
            assets=("USDIDR", "HK50"), mechanism_families=("flows", "risk_appetite"),
            how_to_fetch="the weekly news release; the SRBI line begins only in September 2023"),
    dataset("Bank Indonesia monthly foreign reserves", source="Bank Indonesia",
            coverage="1998-", frequency="monthly", publication_lag_days=7, revisions="rare",
            licence="free, public", history_from="1998-01-01", pit_feasible=True,
            assets=("USDIDR", "USDX"), mechanism_families=("intervention", "reserve_adequacy"),
            how_to_fetch="published on about the 7th at 14:00 WIB with a stated months-of-import "
                         "cover, which BI itself frames as its adequacy threshold"),
    dataset("HBA thermal coal reference price",
            source="Ministry of Energy and Mineral Resources (ESDM)", coverage="2009-",
            frequency="monthly to 2024, twice monthly from 2025", publication_lag_days=1,
            revisions="none", licence="free, public", history_from="2009-01-01",
            pit_feasible=True, assets=("XNGUSD", "AUS200", "USDIDR"),
            mechanism_families=("commodity_policy", "export_earnings"),
            how_to_fetch="the ESDM decree; the FREQUENCY CHANGE in 2025 doubles the observation "
                         "count and is a break in any event-study sample that spans it"),
    dataset("Indonesian monthly merchandise trade", source="Badan Pusat Statistik",
            coverage="1990-", frequency="monthly", publication_lag_days=15,
            revisions="routine prior-month revision", licence="free, public",
            history_from="1990-01-01", pit_feasible=True,
            assets=("USDIDR", "XNIUSD", "XNGUSD"),
            mechanism_families=("terms_of_trade", "export_earnings"),
            how_to_fetch="BPS release on about the 15th at 11:00 WIB (04:00 UTC), inside the "
                         "Indonesian session, which is unusual for a market-moving print"),
    dataset("Indonesian CPI", source="Badan Pusat Statistik", coverage="1968-",
            frequency="monthly", publication_lag_days=1, revisions="rare", licence="free, public",
            history_from="2000-01-01", pit_feasible=True, assets=("USDIDR", "UST10Y"),
            mechanism_families=("inflation", "policy_reaction"),
            how_to_fetch="the first working day of the month at 11:00 WIB -- a one-day lag, "
                         "which is among the fastest CPI prints anywhere"),
    dataset("palm oil export levy and domestic market obligation decrees",
            source="Ministry of Finance and Ministry of Trade", coverage="2015-",
            frequency="episodic, with a monthly reference price", publication_lag_days=0,
            revisions="none", licence="free, public", history_from="2015-01-01",
            pit_feasible=True, assets=("SOYBEAN", "USDIDR"),
            mechanism_families=("commodity_policy", "substitution"),
            how_to_fetch="the ministerial decree archives; the April-May 2022 export BAN is the "
                         "largest single observation in the series and is dated to the day"),
    dataset("RKAB nickel production quotas and ore export policy",
            source="Ministry of Energy and Mineral Resources", coverage="2020-",
            frequency="annual with in-year amendments", publication_lag_days=0,
            revisions="amended in year", licence="free, public", history_from="2020-01-01",
            pit_feasible=True, assets=("XNIUSD", "XALUSD"),
            mechanism_families=("supply_policy", "commodity_policy"),
            how_to_fetch="the minerba portal; the quota is approved per company and the AGGREGATE "
                         "is what matters, which means the series has to be built rather than "
                         "downloaded"),
    dataset("IDX daily foreign net flow", source="Indonesia Stock Exchange", coverage="2005-",
            frequency="daily", publication_lag_days=0, revisions="none", licence="free, public",
            history_from="2005-01-01", pit_feasible=True, assets=("HK50", "USDIDR"),
            mechanism_families=("flows", "risk_appetite"),
            how_to_fetch="the trading summary; published at the close, so it is knowable for the "
                         "next session only"),
    dataset("currency in circulation (uang kartal)", source="Bank Indonesia",
            coverage="1990-", frequency="monthly", publication_lag_days=21,
            revisions="rare", licence="free, public", history_from="1990-01-01",
            pit_feasible=True, assets=("USDIDR",),
            mechanism_families=("seasonality", "liquidity"),
            how_to_fetch="the monetary statistics tables; the pre-Lebaran surge is the largest "
                         "recurring seasonal in Indonesian monetary data and moves by weeks each "
                         "year with the Islamic calendar"),
    dataset("SRBI auction results", source="Bank Indonesia", coverage="2023-",
            frequency="twice weekly", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2023-09-15", pit_feasible=True,
            assets=("USDIDR", "UST10Y"), mechanism_families=("sterilisation", "carry"),
            how_to_fetch="the auction result releases; a series with only a two-year history, "
                         "which is too short for a regime claim and is stated as such"),
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor(
        "Bank Indonesia's triple intervention desk",
        holds="foreign reserves above USD 150bn, a DNDF book and a portfolio of government bonds "
              "bought in the secondary market",
        forced_to=("defend the rupiah in three markets at once when a depreciation episode "
                   "begins, because leaving any one of them unsupported reopens the channel",
                   "sterilise the rupiah consequence through SRBI issuance",
                   "do it under a mandate that names external stability explicitly, so unlike "
                   "most inflation targeters it cannot deny the objective"),
        when="continuously through the 01:00-09:00 UTC onshore session, with the JISDOR window "
             "01:00-07:45 UTC as the concentration point",
        information=("onshore interbank flow it settles",
                     "DNDF auction demand", "daily SBN ownership before it is published"),
        constraints=("reserve adequacy expressed as months of import cover, which BI itself "
                     "names publicly",
                     "the fiscal cost of SRBI yields, which are paid out of its own balance sheet",
                     "an inflation target of 2.5% +/-1%"),
        instruments=("USDIDR", "USDCNH", "UST10Y"),
        counterparties=("onshore banks", "offshore NDF market makers",
                        "foreign holders of SBN and SRBI"),
        observables=("monthly reserves", "weekly non-resident flow", "the DNDF-to-NDF gap",
                     "SRBI awarded yields", "BI's own SBN holdings in the DJPPR file"),
        impact="four simultaneous legs mean the rupiah's path is smoother than its fundamentals "
               "and its TAILS are fatter, because when the defence is abandoned all four legs "
               "stop at once; a volatility cell fitted on the quiet periods is fitted on the "
               "defence and not on the currency",
        persistence="structural; the INSTRUMENTS have changed twice in a decade (DNDF in 2018, "
                    "SRBI in 2023) and each addition is an era boundary",
        falsifier="a depreciation episode of more than 5% in a quarter with reserves unchanged "
                  "and no DNDF auction would say the desk has stopped operating"),
    actor(
        "Foreign holders of Indonesian government securities",
        holds="a share of SBN outstanding that fell from about 39% in 2019 to the mid teens, "
              "which is itself the most important structural change in this market",
        forced_to=("mark to a daily published ownership file, so their position is visible to "
                   "everyone including the central bank",
                   "hedge the currency leg or accept it",
                   "rebalance against EM local-currency benchmarks"),
        when="continuous, published daily with a one-to-two day lag",
        information=("the auction calendar", "BI's own purchases", "the global EM cycle"),
        constraints=("index weights", "the currency's carry net of hedging cost",
                     "a withholding tax regime that has been cut to attract them"),
        instruments=("UST10Y", "USDIDR"),
        counterparties=("domestic banks and insurers", "Bank Indonesia",
                        "the Ministry of Finance at auction"),
        observables=("the DJPPR daily file", "the 10-year spread to UST10Y",
                     "auction bid-to-cover"),
        impact="the fall in the foreign share from 39% to the mid teens means the SAME foreign "
               "outflow now moves the bond market far less and the currency far more, because "
               "the domestic bid absorbs the bond and not the dollar",
        persistence="the DECLINE is structural and is the result of deliberate policy to "
                    "domesticate the holder base",
        falsifier="a quarter of foreign SBN outflow above USD 2bn with no measurable USDIDR move "
                  "and an unchanged 10-year spread"),
    actor(
        "Thermal coal exporters",
        holds="the export book of the world's largest thermal coal exporter, above 400 million "
              "tonnes a year",
        forced_to=("sell into a reference price set by ministerial decree rather than negotiated "
                   "freely",
                   "meet a domestic market obligation before exporting",
                   "repatriate and retain export proceeds onshore under the DHE rule"),
        when="shipments are continuous; the HBA decree lands monthly and, from 2025, twice monthly",
        information=("their own contract book", "Chinese and Indian import demand",
                     "the HBA formula's input assessments"),
        constraints=("the domestic market obligation and its penalty regime",
                     "royalty rates tied to the HBA",
                     "the DHE retention rule, which since March 2025 keeps the whole of the "
                     "proceeds onshore for a year"),
        instruments=("XNGUSD", "XBRUSD", "AUS200", "USDIDR"),
        counterparties=("Chinese and Indian utilities", "Japanese and Korean buyers",
                        "the domestic power utility"),
        observables=("the HBA decree", "monthly export volume in the BPS trade data",
                     "Newcastle and API benchmark prices"),
        impact="the largest single line in Indonesia's export book, so the coal price IS the "
               "terms of trade; and because the retention rule now holds the proceeds onshore, "
               "the same coal price now translates into onshore dollar supply rather than into "
               "an offshore deposit",
        persistence="structural, with a slow decline as importing countries decarbonise; the "
                    "DHE rule change in March 2025 is a step, not a trend",
        falsifier="a quarter of rising coal export value with falling onshore dollar liquidity "
                  "after March 2025 would falsify the retention mechanism"),
    actor(
        "Palm oil producers, refiners and the biodiesel mandate",
        holds="roughly 60% of world palm oil production, plus the refining capacity behind it",
        forced_to=("supply the domestic market at a mandated price before exporting",
                   "blend a mandated share of palm-based biodiesel into domestic diesel, stepped "
                   "up by decree from B30 to B35 and then to B40",
                   "pay an export levy whose rate moves with a reference price"),
        when="continuous, with the reference price and levy set monthly and mandate steps set "
             "annually",
        information=("their own stocks", "the Malaysian MPOB print on the 10th",
                     "Indian and Chinese import demand"),
        constraints=("the domestic market obligation, the export levy and the biodiesel mandate, "
                     "any of which can be changed at short notice",
                     "the April-May 2022 outright export ban, which is the precedent everyone in "
                     "this market now prices"),
        instruments=("SOYBEAN", "XTIUSD", "USDIDR"),
        counterparties=("Indian and Chinese importers", "the domestic biodiesel programme",
                        "Malaysian refiners competing for the same buyers"),
        observables=("the levy and reference price decrees", "the biodiesel allocation quota",
                     "Malaysian MPOB stocks as the visible half of the world balance"),
        impact="a mandate step diverts several million tonnes from export to domestic diesel in a "
               "single decree, which is a world supply shock with an Indonesian signature; the "
               "biodiesel channel also ties palm to the CRUDE price through the blending economics",
        persistence="structural and increasing: each mandate step is permanent in practice",
        falsifier="a biodiesel mandate step with no move in the palm-soy oil spread and no change "
                  "in Indonesian export volume over the following two quarters"),
    actor(
        "Nickel miners and the Chinese-owned smelter parks",
        holds="close to half of world mined nickel supply, concentrated in Sulawesi, with the "
              "processing overwhelmingly Chinese-owned",
        forced_to=("mine to an RKAB quota approved by the ministry, which has been the binding "
                   "constraint since 2024",
                   "process onshore because ore export has been banned since January 2020",
                   "sell into a market they themselves have oversupplied"),
        when="continuous, with quota approvals annual and amendable in year",
        information=("their own quota", "LME and Shanghai nickel prices",
                     "stainless steel and battery demand"),
        constraints=("the RKAB quota system",
                     "the ore export ban",
                     "the DHE retention rule on proceeds",
                     "an environmental and permitting regime that has tightened"),
        instruments=("XNIUSD", "XALUSD", "USDIDR"),
        counterparties=("Chinese stainless and battery producers",
                        "Western automakers seeking non-Chinese supply chains",
                        "the LME, whose nickel contract was broken by a 2022 squeeze partly "
                        "rooted in Indonesian supply"),
        observables=("aggregate RKAB approvals", "monthly nickel product export volume",
                     "the ore reference price", "LME and Shanghai inventories"),
        impact="Indonesia is the price setter in nickel, so a QUOTA decision in Jakarta is a "
               "world supply decision; it is also the reason the LME nickel price has behaved so "
               "badly as a hedging instrument since 2022",
        persistence="structural, and the downstream policy is a stated national strategy rather "
                    "than a cyclical choice",
        falsifier="a material change in aggregate RKAB approvals with no move in XNIUSD over the "
                  "following quarter"),
    actor(
        "Pertamina and the fuel import bill",
        holds="the import book for the refined product Indonesia cannot refine for itself, "
              "against a domestic price that is politically set",
        forced_to=("buy dollars continuously to pay for cargoes",
                   "sell at a subsidised domestic price and be compensated fiscally, which "
                   "converts an oil price shock into a FISCAL shock"),
        when="continuous, with month-end invoice settlement clustering",
        information=("its own cargo schedule", "the Singapore MOPS assessments it prices off"),
        constraints=("state ownership and the political impossibility of passing through a price "
                     "rise quickly",
                     "the energy subsidy line in the state budget"),
        instruments=("USDIDR", "XBRUSD", "XTIUSD"),
        counterparties=("Singapore traders", "Middle Eastern suppliers", "the state budget"),
        observables=("monthly oil and gas import value", "the subsidy line in the budget",
                     "domestic pump prices, which move rarely and visibly"),
        impact="a structural dollar bid that makes Indonesia a net energy IMPORTER on the crude "
               "and product side even while it is a huge coal and LNG exporter -- which is why a "
               "simple commodity-currency model fits Indonesia badly and must be built on the NET "
               "energy balance",
        persistence="structural; refining capacity has not kept up with demand for two decades",
        falsifier="a sustained crude rally with an IMPROVING Indonesian trade balance, which "
                  "would say the coal and LNG legs now dominate the crude leg"),
    actor(
        "Indonesian corporates paying dividends to foreign parents",
        holds="the profits of the foreign-owned share of Indonesian industry",
        forced_to=("pay dividends on an annual general meeting schedule concentrated in the "
                   "second quarter",
                   "convert rupiah into dollars to remit them"),
        when="April to July, peaking in May and June",
        information=("their own earnings", "board schedules published in advance"),
        constraints=("company law requiring an AGM within six months of the year end",
                     "withholding tax on dividends",
                     "the DHE rule, which applies to export proceeds and not to dividends"),
        instruments=("USDIDR",),
        counterparties=("foreign parent companies", "domestic banks executing the conversion"),
        observables=("the primary income deficit in the quarterly balance of payments",
                     "AGM calendars", "announced dividend amounts"),
        impact="a recurring, dated, second-quarter dollar demand that shows in USDIDR every year "
               "and in no textbook; it is one of the few genuinely seasonal EM FX flows with a "
               "legal cause rather than a behavioural one",
        persistence="structural and permanent while foreign ownership of Indonesian industry is "
                    "large; the TIMING is fixed by company law",
        falsifier="a second quarter with no widening of the primary income deficit and no "
                  "measurable USDIDR seasonal, across three consecutive years"),
    actor(
        "Indonesian households in the Ramadan and Lebaran cycle",
        holds="the cash economy, and a legally mandated annual bonus",
        forced_to=("receive the THR (tunjangan hari raya) religious holiday allowance, which the "
                   "law requires employers to pay before Idul Fitri",
                   "spend it in a compressed two-week window",
                   "travel home in the mudik exodus, which shuts commercial activity"),
        when="the fortnight before Idul Fitri, which moves eleven days earlier each Gregorian year",
        information=("the announced Idul Fitri date", "the cuti bersama decree"),
        constraints=("the statutory THR deadline",
                     "the exchange's own multi-day closure"),
        instruments=("USDIDR",),
        counterparties=("employers", "the banking system, which must supply the cash",
                        "Bank Indonesia, which pre-positions currency"),
        observables=("currency in circulation, which surges by a fifth",
                     "BI's announced cash preparation",
                     "retail sales and the CPI food component"),
        impact="the largest recurring liquidity event in the Indonesian calendar, and because the "
               "Islamic calendar drifts eleven days a year against the Gregorian one, it is a "
               "seasonal that a month-of-year dummy CANNOT capture -- which is why most published "
               "Indonesian seasonality work misses it",
        persistence="permanent, with the date drifting through the Gregorian year on a 33-year "
                    "cycle",
        falsifier="a Lebaran with no surge in currency in circulation relative to the trailing "
                  "three-month average"),
    actor(
        "Domestic banks and the onshore-offshore basis",
        holds="the onshore rupiah funding book and the domestic side of every DNDF",
        forced_to=("fund rupiah assets domestically because offshore rupiah lending is restricted",
                   "quote into BI's DNDF auctions",
                   "square the book into the 09:00 UTC close"),
        when="the onshore session, with the largest imbalance at month end",
        information=("their own client flow", "BI's auction intentions"),
        constraints=("BI's limits on non-resident rupiah transactions, which are what create the "
                     "offshore NDF market in the first place",
                     "reserve requirements, which BI varies as a macroprudential tool"),
        instruments=("USDIDR", "USDSGD"),
        counterparties=("offshore NDF market makers in Singapore", "exporters and importers",
                        "Bank Indonesia"),
        observables=("the DNDF-to-offshore-NDF gap", "onshore forward points",
                     "the 03:00 UTC offshore fixing against the 08:00 UTC onshore one"),
        impact="the basis between two fixings five hours apart is a continuous read on how "
               "binding the capital controls are, which is a structural variable that most EM "
               "currencies do not offer",
        persistence="structural while the restrictions stand",
        falsifier="a period in which the two fixings converge to within transaction costs while "
                  "the restrictions remain in force"),
    actor(
        "The Ministry of Finance debt management office",
        holds="the SBN issuance programme, and a cash buffer built from front-loaded global "
              "issuance",
        forced_to=("issue to fund the budget deficit on a published auction calendar",
                   "front-load global bond issuance in January, when the market is open and "
                   "before the domestic calendar gets complicated"),
        when="conventional and sukuk auctions on alternating Tuesdays at about 03:00 UTC",
        information=("its own cash position", "the tax calendar", "BI's appetite to buy"),
        constraints=("a statutory 3% of GDP deficit ceiling",
                     "the burden-sharing arrangements with BI that were used during the pandemic "
                     "and then wound down"),
        instruments=("UST10Y", "USDIDR"),
        counterparties=("domestic banks and insurers", "foreign investors", "Bank Indonesia"),
        observables=("the auction calendar and bid-to-cover", "the January global issuance",
                     "the realised deficit against target"),
        impact="the January global issue is a large, dated, single-day dollar INFLOW, which is "
               "the mirror image of the Q2 dividend outflow and makes the Indonesian year "
               "structurally front-loaded",
        persistence="structural; the front-loading strategy has been consistent for a decade",
        falsifier="a January with no global issuance and no measurable USDIDR effect"),
    actor(
        "Badan Pusat Statistik as an information actor",
        holds="the release calendar for CPI, trade and GDP",
        forced_to=("publish CPI on the first working day of the month",
                   "publish trade on about the 15th",
                   "publish both at 11:00 WIB, which is inside the trading session"),
        when="CPI at 04:00 UTC on the first working day; trade at 04:00 UTC on about the 15th",
        information=("the underlying survey data before release",),
        constraints=("statistical law and a published release calendar",),
        instruments=("USDIDR", "UST10Y"),
        counterparties=("the whole market",),
        observables=("the release calendar itself", "the prints"),
        impact="Indonesia's CPI lands with a ONE-DAY lag, among the fastest in the world, and "
               "lands INSIDE the session rather than before it -- which means the price reaction "
               "is observable in the same bars as the print and does not require an overnight gap "
               "study",
        persistence="structural; the calendar has been stable for years",
        falsifier="a CPI release that moves neither USDIDR nor the local curve within the session, "
                  "repeatedly"),
    actor(
        "Offshore NDF market makers in Singapore",
        holds="the offshore rupiah risk book, settled against the 03:00 UTC ABS fixing",
        forced_to=("settle at the offshore fixing five hours before the onshore one",
                   "hedge fixing exposure into the 02:30-03:00 UTC window",
                   "price a currency they cannot deliver"),
        when="03:00 UTC daily and at month end",
        information=("offshore client positioning", "onshore liquidity conditions"),
        constraints=("BI's restrictions on non-resident rupiah, which is why the market is "
                     "non-deliverable at all",
                     "the ABS fixing methodology"),
        instruments=("USDIDR", "USDSGD", "USDTHB"),
        counterparties=("EM real money", "onshore banks", "hedge funds expressing a regional view"),
        observables=("the ABS fixing", "the NDF curve", "the gap to the DNDF"),
        impact="the offshore market is where a rupiah view is expressed when the onshore market "
               "is shut -- which, given Indonesia's holiday calendar, is for six to nine "
               "consecutive sessions once a year",
        persistence="structural; DNDF has reduced the offshore market's share without closing it",
        falsifier="a Lebaran closure across which the offshore NDF does not move at all"),
    actor(
        "Retail investors on the Indonesia Stock Exchange",
        holds="a retail account base that multiplied after 2020 and now dominates daily turnover "
              "by count",
        forced_to=("trade inside a symmetric auto-rejection price band",
                   "settle T+2 with pre-funding at most brokers"),
        when="the two cash sessions, 02:00-04:30 and 06:30-08:00 UTC",
        information=("Stockbit and the retail commentary ecosystem", "IDX announcements"),
        constraints=("the auto-rejection limits, which truncate the daily return distribution by "
                     "RULE",
                     "short-selling restrictions"),
        instruments=("HK50",),
        counterparties=("foreign institutions", "domestic mutual funds"),
        observables=("daily retail versus foreign turnover split", "new account openings",
                     "the number of stocks hitting the auto-rejection limit"),
        impact="the auto-rejection band means an Indonesian daily return series is CENSORED, so a "
               "tail statistic computed on it is a statistic about the rule; the count of limit "
               "hits is the uncensored observable and is the one to use",
        persistence="the cohort is persistent; the LIMITS changed repeatedly in 2020-2021 and "
                    "each change is a break in the censoring",
        falsifier="a period in which the realised tail of the daily return distribution exceeds "
                  "the auto-rejection band, which would mean the band is not binding"),
    actor(
        "The Financial Services Authority as a macroprudential actor",
        holds="the supervisory levers over banks, insurers and the capital market",
        forced_to=("act on financial stability without a rate lever, which belongs to BI",
                   "coordinate with BI through the financial system stability committee"),
        when="episodic, with announcements at short notice",
        information=("bank-level supervisory data", "capital market surveillance"),
        constraints=("a division of responsibility with BI that is statutory",
                     "political pressure to support credit growth"),
        instruments=("USDIDR", "HK50"),
        counterparties=("banks", "listed companies", "investors"),
        observables=("supervisory rule changes", "credit growth data",
                     "trading halts and short-selling rule changes"),
        impact="a second policy source with its own calendar, which matters because an Indonesian "
               "policy event study that reads only BI misses half the announcements that move "
               "the market",
        persistence="structural since the authority was created in 2011",
        falsifier="a year in which no supervisory announcement produces a measurable market "
                  "reaction"),
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("IDN-A", "The monthly BI decision and the twelve-event year",
           objects=("twelve RDG decisions a year announced at about 07:00 UTC",
                    "the BI-Rate path", "the governor's press conference at 07:20 UTC",
                    "the accompanying macroprudential and liquidity-incentive announcements"),
           conditions=("the DHE regime in force", "whether the rupiah is under defence",
                       "whether CPI is inside the 2.5% +/-1% target band",
                       "the Fed's own meeting calendar, which BI reacts to explicitly"),
           instruments=("USDIDR", "UST10Y", "HK50"),
           controls=("the same statistic on the eleven NON-decision mid-month Wednesdays of the "
                     "year, separating the event from the mid-month date",
                     "the same statistic on USDTHB and USDCNH on the same dates",
                     "decisions that FOLLOW an FOMC within a week versus those that do not, "
                     "since BI has repeatedly moved in the Fed's wake"),
           notes="twelve events a year makes Indonesia the most event-dense currency in this "
                 "department, which is a statistical advantage and a multiple-testing cost at the "
                 "same time -- the trial count is shared and IDN spends more of it than its "
                 "neighbours"),
    domain("IDN-B", "Two fixings five hours apart",
           objects=("the 01:00-07:45 UTC JISDOR transaction window and its 08:00 UTC publication",
                    "the 02:30-03:00 UTC offshore ABS window and its 03:00 UTC publication",
                    "the gap between the two"),
           conditions=("month end", "whether BI is visibly intervening",
                       "days when the onshore market is shut and the offshore one is not"),
           instruments=("USDIDR", "USDSGD"),
           controls=("the same window statistic on USDSGD, a deliverable currency with no NDF and "
                     "therefore no fixing exposure to hedge",
                     "the adjacent half hours around each fix",
                     "the other eight currencies that settle at the same 03:00 UTC instant -- an "
                     "effect in all nine is a regional settlement effect, not an Indonesian one"),
           notes="having two official fixings at different times is rare and is a free "
                 "identification: a mechanism attached to the ONSHORE fix cannot also explain an "
                 "effect at the offshore one"),
    domain("IDN-C", "The DNDF and the onshore-offshore basis as an intervention thermometer",
           objects=("BI's DNDF auctions and their awarded rates",
                    "the DNDF-to-offshore-NDF gap", "onshore forward points"),
           conditions=("the intensity of a depreciation episode",
                       "whether BI has announced an auction",
                       "the level of reserves against the stated import-cover threshold"),
           instruments=("USDIDR", "USDCNH"),
           controls=("the same basis in CNH, where an onshore-offshore split exists with the same "
                     "shape under a different central bank",
                     "periods with no auctions, where the basis should be driven by funding alone",
                     "a USD funding factor, residualised out first"),
           notes="the basis is available DAILY where the reserve print waits seven days; that is "
                 "the entire reason to bear the estimation difficulty"),
    domain("IDN-D", "The export-proceeds retention regime as a natural experiment",
           objects=("the 30% three-month rule from August 2023",
                    "the 100% twelve-month rule from 1 March 2025",
                    "onshore dollar deposits and the special deposit instrument",
                    "the gap between export earnings and onshore dollar supply"),
           conditions=("which regime is in force",
                       "the commodity price level, which scales the flow being retained",
                       "whether the exporter is in the covered natural-resource sector"),
           instruments=("USDIDR", "XNGUSD", "XNIUSD"),
           controls=("the same statistic for a non-resource export currency in the region, which "
                     "shares the commodity cycle and not the rule",
                     "the pre-August-2023 baseline, where no retention applied",
                     "a placebo on the three months BEFORE each rule's effective date, to test "
                     "for anticipation"),
           notes="THE CLEANEST NATURAL EXPERIMENT IN THIS DEPARTMENT: the same economy, the same "
                 "central bank, the same commodities, and a legislated step change in how much "
                 "of the export dollar must come home. If the retention mechanism is real it must "
                 "show here and nowhere else"),
    domain("IDN-E", "Foreign flows in bonds, equities and SRBI",
           objects=("the DJPPR daily foreign ownership file",
                    "BI's weekly non-resident release", "IDX daily foreign net flow",
                    "the SRBI foreign holding share"),
           conditions=("whether the flow is in SBN, equities or SRBI, which behave differently",
                       "the global EM cycle",
                       "whether BI itself is buying, which appears in the same file"),
           instruments=("USDIDR", "UST10Y", "HK50"),
           controls=("the same regression on Thai and Indian foreign bond flow, which share the "
                     "EM factor and not the Indonesian instruments",
                     "separating BI's own holdings from non-resident holdings, since one is "
                     "intervention and the other is a flow",
                     "a lead-lag reversal test"),
           notes="the fall in the foreign SBN share from about 39% to the mid teens means a "
                 "coefficient fitted before 2020 is far too large for today; this is the domain "
                 "most likely to be quietly wrong from a long sample"),
    domain("IDN-F", "The coal export cycle and the reference price decree",
           objects=("the HBA reference price decree, monthly to 2024 and twice monthly from 2025",
                    "monthly coal export volume and value",
                    "the domestic market obligation and its penalties",
                    "Newcastle and API benchmark prices"),
           conditions=("the decree frequency era",
                       "Chinese and Indian import demand",
                       "the DHE regime, which determines whether the earnings come home"),
           instruments=("XNGUSD", "XBRUSD", "AUS200", "USDIDR"),
           controls=("Australian coal export data over the same period, the competing supplier",
                     "the gas price, since coal-to-gas switching is the substitution channel and "
                     "an effect that appears in coal and not in gas has not been identified",
                     "the frequency change in 2025, which doubles the event count"),
           notes="no coal instrument exists in this universe, so every claim here terminates in "
                 "XNGUSD, AUS200 or USDIDR and the transmission is the hypothesis, not a "
                 "convenience"),
    domain("IDN-G", "Palm oil policy and the vegetable-oil substitution channel",
           objects=("the export levy and reference price decrees",
                    "the domestic market obligation",
                    "the biodiesel blending mandate and its steps",
                    "the April-May 2022 export ban as the precedent"),
           conditions=("the mandate level in force",
                       "the palm-soy oil spread", "Indian import duty changes on vegetable oils",
                       "the crude price, which sets the biodiesel blending economics"),
           instruments=("SOYBEAN", "XTIUSD", "USDIDR"),
           controls=("US soybean supply-and-demand events on the same dates, which move SOYBEAN "
                     "without any Indonesian cause -- the control that decides whether this "
                     "domain has any signal at all",
                     "Malaysian MPOB releases, which move palm without an Indonesian decree",
                     "a two-link decomposition: the decree must move PALM, and palm must move "
                     "SOYBEAN; if the second link is absent the domain is dead and should be said "
                     "to be dead"),
           notes="STATED AS A WEAKNESS: the broker quotes the BEAN and palm competes with soybean "
                 "OIL. The edge runs through two links and IDN-G's controls exist to find out "
                 "whether the second one carries anything"),
    domain("IDN-H", "Nickel supply policy",
           objects=("RKAB production quota approvals and amendments",
                    "the ore export ban in force since January 2020",
                    "the smelter build-out and its Chinese ownership",
                    "LME and Shanghai inventories"),
           conditions=("whether the quota is binding",
                       "battery versus stainless demand mix",
                       "LME contract functioning, which was damaged by the 2022 squeeze"),
           instruments=("XNIUSD", "XALUSD", "XCUUSD"),
           controls=("copper and aluminium on the same dates, which share the industrial-metal "
                     "factor and not the Indonesian policy",
                     "the pre-2020 period, before the ore ban, where the mechanism cannot operate",
                     "Philippine ore export volume, the substitute supply that fills the gap"),
           notes="Indonesia is the price setter, so this is one of the few domains in this "
                 "department where a single country's ADMINISTRATIVE decision is a world supply "
                 "shock with a published date"),
    domain("IDN-I", "Ramadan, Lebaran and the cash cycle",
           objects=("the THR statutory bonus and its payment deadline",
                    "currency in circulation, which surges by about a fifth",
                    "the mudik exodus",
                    "the six-to-nine session exchange closure"),
           conditions=("the Gregorian date of Idul Fitri, which moves eleven days earlier a year",
                       "the length of the cuti bersama block in the decree",
                       "whether the closure spans a month end"),
           instruments=("USDIDR", "HK50"),
           controls=("the SAME Gregorian weeks in years when Lebaran fell elsewhere -- the "
                     "control that separates the festival from the month, and the reason a "
                     "month-of-year dummy cannot capture this seasonal",
                     "Malaysian and Singaporean Hari Raya dates, which are the same festival in "
                     "different markets",
                     "the offshore NDF across the closure, which keeps trading when the onshore "
                     "market does not"),
           notes="the eleven-day annual drift is what makes this seasonal invisible to most "
                 "published work and available to anyone who indexes on the Islamic calendar "
                 "instead of the Gregorian one"),
    domain("IDN-J", "Dividend repatriation and the second-quarter dollar demand",
           objects=("AGM schedules concentrated in the second quarter",
                    "announced dividend amounts",
                    "the primary income deficit in the balance of payments"),
           conditions=("the previous year's corporate earnings, which set the amount",
                       "the withholding tax regime",
                       "whether the rupiah is already under pressure, which amplifies the effect"),
           instruments=("USDIDR",),
           controls=("the same calendar quarter in Thailand and the Philippines, which have "
                     "different AGM conventions",
                     "a year with collapsed corporate earnings, where the flow should shrink",
                     "the first quarter as a within-year placebo"),
           notes="a seasonal with a LEGAL cause -- company law requires an AGM within six months "
                 "of the year end -- which is a far stronger prior than a behavioural seasonal"),
    domain("IDN-K", "Terms of trade and the trade print on the 15th",
           objects=("monthly merchandise trade at 04:00 UTC on about the 15th",
                    "the coal, palm, nickel and oil lines within it",
                    "the current account, published quarterly"),
           conditions=("the commodity price level in the reference month",
                       "the DHE regime, which determines whether a surplus becomes onshore "
                       "dollar supply"),
           instruments=("USDIDR", "XNGUSD", "XNIUSD"),
           controls=("the same statistic for Malaysia and Australia, commodity exporters without "
                     "the retention rule",
                     "a price-versus-volume decomposition, since a surplus driven by falling "
                     "imports is not the same event as one driven by rising exports"),
           notes="the print lands INSIDE the session at 04:00 UTC, so the reaction is in the same "
                 "bars and no overnight gap study is needed -- unusual and convenient"),
    domain("IDN-L", "Session microstructure and the censored return distribution",
           objects=("the two cash sessions and the 90-minute lunch break",
                    "the auto-rejection price band",
                    "the 01:00-09:00 UTC FX session",
                    "the count of stocks hitting the limit"),
           conditions=("the auto-rejection band in force, which changed repeatedly in 2020-2021",
                       "whether the offshore NDF is the only market open"),
           instruments=("USDIDR", "HK50"),
           controls=("the same tail statistic on USDIDR, which has no auto-rejection band, "
                     "against the equity index which does",
                     "the periods before and after each band change",
                     "the lunch break as a within-day placebo"),
           notes="an Indonesian daily equity return series is CENSORED BY RULE. A tail or "
                 "volatility statistic computed on it is a statistic about the rule, and the "
                 "count of limit hits is the uncensored observable that should be used instead"),
)

# --------------------------------------------------------------------------- miners (specs)
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("idn_rdg_event_study", domain_ids=("IDN-A",), kind="event",
          entry="research.countries.idn.miners:rdg_event_study", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Re-reads the official RDG schedule from bi.go.id before "
                "every run, because the dates in CENTRAL_BANK are RECONSTRUCTED and a date a day "
                "out turns the event window into a placebo"),
    miner("idn_two_fixings", domain_ids=("IDN-B", "IDN-C"), kind="microstructure",
          entry="research.countries.idn.miners:two_fixings", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Measures the 03:00 UTC and 08:00 UTC windows together and "
                "reports the gap as the primary output, not either window alone"),
    miner("idn_dhe_experiment", domain_ids=("IDN-D",), kind="regime",
          entry="research.countries.idn.miners:dhe_experiment", cadence_s=604800.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. The retention-rule natural experiment, with the "
                "anticipation placebo on the three months before each effective date"),
    miner("idn_foreign_flow", domain_ids=("IDN-E",), kind="flow",
          entry="research.countries.idn.miners:foreign_flow", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Separates BI's own SBN holdings from non-resident holdings "
                "before anything else, because one is intervention and the other is a flow"),
    miner("idn_commodity_decree", domain_ids=("IDN-F", "IDN-G", "IDN-H"), kind="event",
          entry="research.countries.idn.miners:commodity_decree", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Watches the ESDM and trade ministry decree feeds in "
                "Indonesian; the decree lands days before any English wire carries it"),
    miner("idn_lebaran_cycle", domain_ids=("IDN-I",), kind="calendar",
          entry="research.countries.idn.miners:lebaran_cycle", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Indexes on the ISLAMIC calendar, not the Gregorian one, "
                "which is the whole point: an eleven-day annual drift is invisible to a "
                "month-of-year dummy"),
    miner("idn_dividend_season", domain_ids=("IDN-J",), kind="flow",
          entry="research.countries.idn.miners:dividend_season", cadence_s=604800.0,
          notes="SPEC, NOT YET WIRED. Joins announced dividends to the primary income deficit and "
                "tests the second-quarter USDIDR seasonal against a first-quarter placebo"),
    miner("idn_trade_print", domain_ids=("IDN-K",), kind="macro",
          entry="research.countries.idn.miners:trade_print", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Decomposes the surplus into price and volume before any "
                "terms-of-trade claim is made"),
    miner("idn_censoring_check", domain_ids=("IDN-L",), kind="data_quality",
          entry="research.countries.idn.miners:censoring_check", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Refuses any Indonesian equity tail statistic computed on a "
                "sample whose auto-rejection band changed inside it"),
)

# --------------------------------------------------------------------------- transmission seeds
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("IDN-E01", source="Bank Indonesia BI-Rate decision surprise",
         mechanism="a hawkish surprise raises the carry and signals a more aggressive defence, so "
                   "USDIDR falls and the local curve reprices",
         targets=("USDIDR", "UST10Y"), sign="-", horizon="0 to 3 sessions",
         lag="0 -- announced at about 07:00 UTC",
         control="USDTHB and USDCNH on the same dates, and the eleven non-decision mid-month "
                 "Wednesdays of the year",
         notes="FALSIFIER: no difference between hawkish-surprise and dovish-surprise days. "
               "RE-READ THE OFFICIAL RDG DATES FIRST: this pack's dates are reconstructed"),
    edge("IDN-E02", source="the export-proceeds retention step of 1 March 2025",
         mechanism="a legislated jump from 30% for three months to 100% for twelve months changes "
                   "the onshore supply of dollars for a given level of export earnings",
         targets=("USDIDR",), sign="-", horizon="1 to 6 months",
         lag="0 -- the effective date is in the regulation",
         control="a commodity-exporting regional currency with no retention rule, and the three "
                 "months before the effective date as an anticipation placebo",
         notes="FALSIFIER: no change in the relationship between the trade surplus and USDIDR "
               "across the effective date. THE CENTRAL EDGE OF THIS PACK"),
    edge("IDN-E03", source="Indonesian RKAB nickel quota decisions",
         mechanism="Indonesia supplies close to half of world mined nickel, so an administrative "
                   "quota decision is a world supply decision with a published date",
         targets=("XNIUSD",), sign="-", horizon="1 to 3 months",
         lag="0 at the decree, then monthly on export volume",
         control="copper and aluminium on the same dates, which share the industrial-metal factor "
                 "and not the Indonesian policy",
         notes="FALSIFIER: a material change in aggregate approvals with no XNIUSD response over "
               "the following quarter"),
    edge("IDN-E04", source="Indonesian bauxite and alumina export restrictions",
         mechanism="the bauxite ore export ban from June 2023 removed feedstock from the Chinese "
                   "alumina chain, which is the aluminium cost curve's first link",
         targets=("XALUSD",), sign="+", horizon="1 to 6 months", lag="0 at the decree",
         control="Guinean bauxite supply events on the same dates, the substitute source",
         notes="FALSIFIER: no measurable alumina or aluminium response once Guinean supply is "
               "controlled for"),
    edge("IDN-E05", source="an Indonesian biodiesel blending mandate step",
         mechanism="a mandate step diverts several million tonnes of palm from export to domestic "
                   "diesel, which tightens the world vegetable-oil balance and ties palm to crude",
         targets=("SOYBEAN", "XTIUSD"), sign="+", horizon="1 to 2 quarters",
         lag="0 at the decree, with effect at the stated start date",
         control="US soybean supply-and-demand reports on the same dates, and a two-link check "
                 "that the decree moved PALM before asking whether palm moved SOYBEAN",
         notes="FALSIFIER: the decree moves palm and palm does not move SOYBEAN, which kills the "
               "second link and with it this edge. Stated as the likely outcome"),
    edge("IDN-E06", source="the HBA thermal coal reference price decree",
         mechanism="the world's largest thermal coal exporter setting a reference price by decree "
                   "is a supply-side signal for the whole seaborne market",
         targets=("XNGUSD", "AUS200"), sign="+", horizon="1 to 2 months",
         lag="1 day after the decree",
         control="Australian coal export data and the gas price, since coal-to-gas switching is "
                 "the substitution channel that makes XNGUSD the right proxy",
         notes="FALSIFIER: no XNGUSD response to an HBA move once Newcastle prices are "
               "controlled for. Note the 2025 move to twice-monthly decrees"),
    edge("IDN-E07", source="foreign net flow in Indonesian government securities",
         mechanism="a daily, free, official ownership file for a whole bond market; outflow must "
                   "be converted and is a mechanical dollar bid",
         targets=("USDIDR", "UST10Y"), sign="+", horizon="1 to 10 sessions",
         lag="2 days on the DJPPR file",
         control="Thai and Indian foreign bond flow, which share the EM factor, and a lead-lag "
                 "reversal test",
         notes="FALSIFIER: no incremental content once regional EM flow is in the model. The "
               "foreign share fell from about 39% to the mid teens, so a pre-2020 coefficient is "
               "far too large"),
    edge("IDN-E08", source="the Lebaran currency-in-circulation surge",
         mechanism="a statutory bonus paid into a two-week window drives a fifth-sized jump in "
                   "cash demand and a multi-session market closure",
         targets=("USDIDR",), sign="+", horizon="the four weeks around Idul Fitri",
         lag="0 -- the date is announced in advance by the ministry of religion",
         control="the SAME Gregorian weeks in years when Lebaran fell elsewhere, which is the "
                 "control the eleven-day annual drift makes free",
         notes="FALSIFIER: no surge in currency in circulation relative to the trailing three "
               "months, or a USDIDR effect that tracks the Gregorian month rather than the "
               "Islamic date"),
    edge("IDN-E09", source="Indonesian second-quarter dividend repatriation",
         mechanism="company law requires an AGM within six months of the year end, so dividend "
                   "conversion to foreign parents clusters in April to July",
         targets=("USDIDR",), sign="+", horizon="the second quarter",
         lag="0 -- AGM calendars are published in advance",
         control="the first quarter as a within-year placebo, and Thailand and the Philippines, "
                 "which have different AGM conventions",
         notes="FALSIFIER: three consecutive years with no widening of the primary income deficit "
               "and no USDIDR seasonal"),
    edge("IDN-E10", source="the Indonesian trade balance print on the 15th",
         mechanism="a commodity exporter's surplus is its terms of trade, and under the retention "
                   "rule it is also onshore dollar supply",
         targets=("USDIDR", "XNIUSD"), sign="-", horizon="0 to 5 sessions", lag="15 days",
         control="Malaysian and Australian trade data, commodity exporters without the retention "
                 "rule, and a price-versus-volume decomposition",
         notes="FALSIFIER: no USDIDR response to a surplus surprise, or a response of the same "
               "size before and after the March 2025 retention step"),
    edge("IDN-E11", source="the DNDF-to-offshore-NDF gap",
         mechanism="the gap between an onshore instrument BI controls and an offshore one it does "
                   "not is a direct read on how hard the rupiah is being defended",
         targets=("USDIDR", "USDCNH"), sign="+", horizon="1 to 10 sessions",
         lag="0 -- both are observable daily",
         control="the CNH onshore-offshore basis, the same shape under a different central bank, "
                 "and a USD funding factor residualised out first",
         notes="FALSIFIER: gap moves that do not predict the subsequent monthly reserve print's "
               "flow component"),
    edge("IDN-E12", source="Indonesian CPI on the first working day",
         mechanism="a one-day publication lag and a release inside the session make this the "
                   "fastest inflation print in the region and a direct input to the next RDG",
         targets=("USDIDR", "UST10Y"), sign="-", horizon="same session", lag="1 day",
         control="Thai and Philippine CPI on their own dates, which share the mechanism and not "
                 "the speed",
         notes="FALSIFIER: no within-session reaction to a CPI surprise, repeatedly -- which "
               "would say the print is fully anticipated and the domain is dead"),
    edge("IDN-E13", source="Indonesian foreign equity net selling on IDX",
         mechanism="with no meaningful domestic hedging market, cash foreign flow is the whole "
                   "positioning signal in Indonesian equity risk",
         targets=("HK50", "USDIDR"), sign="+", horizon="1 to 5 sessions", lag="0 at the close",
         control="Thai and Philippine foreign equity flow, which share the regional factor",
         notes="FALSIFIER: no incremental content once regional equity flow is in the model"),
    edge("IDN-E14", source="the 03:00 UTC offshore IDR fixing",
         mechanism="offshore NDF settlement concentrates hedging demand into a window five hours "
                   "before the onshore fix",
         targets=("USDIDR", "USDTHB", "USDINR"), sign="+", horizon="intraday", lag="0",
         control="USDSGD in the same window, which is deliverable and has no NDF to settle, and "
                 "the adjacent half hours",
         notes="FALSIFIER: an effect present in USDSGD, which would prove it is a session "
               "boundary and not a fixing"),
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("IDN-R1", start="2013-05-20", end="2018-10-31",
        label="post-taper-tantrum, JISDOR era, no onshore forward",
        what_changed="JISDOR was introduced in May 2013 in the middle of the taper tantrum; "
                     "hedging demand priced offshore because no onshore non-deliverable "
                     "instrument existed",
        invalidates="any onshore-offshore basis statistic from this era is measuring a market "
                    "with only one side of the instrument that now defines it",
        notes="the foreign SBN share was rising through this whole period toward its 2019 peak"),
    era("IDN-R2", start="2018-11-01", end="2020-01-31",
        label="DNDF introduced",
        what_changed="BI launched the domestic non-deliverable forward specifically to pull "
                     "hedging demand onshore, adding the second leg of what became triple "
                     "intervention",
        invalidates="the basis becomes a DIFFERENT object once an onshore instrument exists, so a "
                    "basis series spanning November 2018 is two series",
        notes="the nickel ore export ban was announced in this window for January 2020 effect"),
    era("IDN-R3", start="2020-02-01", end="2023-07-31",
        label="pandemic, burden sharing and the foreign-share collapse",
        what_changed="BI bought government bonds directly under burden-sharing arrangements, the "
                     "foreign SBN share fell hard, the nickel ore ban took effect, IDX "
                     "auto-rejection limits were changed repeatedly, and palm oil exports were "
                     "banned outright for a month in 2022",
        invalidates="four separate structural changes inside one era; a cell spanning it must say "
                    "which of them it is about, and an equity tail statistic from it is censored "
                    "by a band that moved",
        notes="the April-May 2022 palm export ban is the largest single commodity-policy "
              "observation in this pack"),
    era("IDN-R4", start="2023-08-01", end="2025-02-28",
        label="30% retention and the SRBI launch",
        what_changed="the first binding export-proceeds retention rule in August 2023, then SRBI "
                     "from September 2023 as a fourth intervention leg and a new foreign inflow "
                     "channel",
        invalidates="a flow model without SRBI is missing the instrument that came to dominate "
                    "non-resident positioning, and it did not exist before September 2023",
        notes="the BI-Rate was renamed from the BI 7-Day Reverse Repo Rate during this era"),
    era("IDN-R5", start="2025-03-01", end=None,
        label="100% retention for twelve months",
        what_changed="Government Regulation 8/2025 required the whole of natural-resource export "
                     "proceeds to be held onshore for twelve months, and the HBA reference price "
                     "moved to twice-monthly publication in the same year",
        invalidates="the relationship between the trade surplus and onshore dollar supply is "
                    "different by law from this date; anything fitted on IDN-R4 and evaluated "
                    "here is measuring the rule change",
        notes="the current regime and the one a live candidate is actually trading"),
)


# --------------------------------------------------------------------------- assembly
MISSION = (
    "mine Indonesia to exhaustion on three mechanisms no other country here has: a "
    "central bank that intervenes in four markets at once and publishes each leg on "
    "a different clock, a legislated export-proceeds retention rule that stepped "
    "from 30% to 100% on a known date, and an administrative supply policy in coal, "
    "palm and nickel that sets world prices by ministerial decree")
NOTES = (
    "USDIDR is the only domestic quote. The two commodities Indonesia actually sets the "
    "price of -- palm oil and thermal coal -- are ABSENT from the broker universe, as "
    "are the JCI, INDOGB, the DNDF, SRBI and JISDOR; all are named in this module's "
    "TRANSMISSION_TARGETS. DHE_REGIME carries the retention rule as a dated state and "
    "is the natural experiment IDN-D is built on.")


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
        "transmission_targets": TRANSMISSION_TARGETS, "dhe_regime": DHE_REGIME,
        "mission": MISSION, "notes": NOTES,
    }


def pack() -> Any:
    """Indonesia's pack: `CountryPack` when the framework has landed, else the same fields as a
    dict. `transmission_targets` and `dhe_regime` ride alongside the twenty-one frozen fields."""
    return build_pack(**fields())
