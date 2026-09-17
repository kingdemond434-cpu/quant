"""VIETNAM: a printed central rate, the world's robusta, and a gold bar the state re-priced.

WHAT MAKES VIETNAM ITS OWN MARKET. Four mechanisms, none of which any other country in this
department has in the same combination:

  1. A CRAWLING PEG WITH A PUBLISHED ANCHOR. Since January 2016 the State Bank of Vietnam has
     published a CENTRAL RATE (ty gia trung tam) every morning, derived from the previous day's
     interbank average, a basket of eight reference currencies, and the SBV's own view of the
     macro balance. Commercial banks may quote within a band around it -- widened to plus or
     minus 5% on 17 October 2022 -- and the SBV additionally sells dollars to banks at a FIXED
     intervention price, which acts as a hard ceiling. So the policy state here is not latent the
     way Singapore's band is: the anchor is printed daily at about 01:00 UTC. What is not printed
     is the basket weights, and the intervention price is announced only when it changes.

  2. THE WORLD'S ROBUSTA. Vietnam produces something close to two fifths of world robusta coffee,
     harvested October to January in the Central Highlands. The distinctive part is BEHAVIOURAL
     and well documented by the trade: Vietnamese farmers HOLD beans when prices rise, storing
     them at the farm and selling into weakness, which makes short-run supply elasticity
     PERVERSE. The FOB differential to the London robusta price is publicly quoted and is the
     direct observable of that behaviour. COFROB is on this broker's registry, so this mechanism
     is executable on the commodity leg even though the currency leg is not.

  3. A GOLD BAR THE STATE RE-PRICED. Decree 24 of 2012 gave the SBV a monopoly over the SJC gold
     bar brand, and the domestic SJC price drifted to a premium over world gold that reached the
     high teens in percentage terms by mid-2024. On 3 June 2024 the SBV began selling gold
     directly through four state banks and SJC itself, and the premium compressed sharply. In
     2025 the monopoly was formally ended and licensed producers were admitted. That is a dated,
     administrative, domestic-premium intervention with a public price series on both sides.

  4. A MARKET WITH CEILINGS AND FLOORS. HOSE applies a plus or minus 7% daily band against the
     previous reference price, HNX 10% and UPCoM 15%. The daily return distribution is therefore
     CENSORED BY RULE, and the informative variable is the COUNT of securities at the ceiling
     (tran) or the floor (san), not the distribution's tails. Add a T+2 cycle, ATO and ATC call
     auctions, a foreign ownership room of 49% for most companies and 30% for banks, and the
     non-prefunding reform of 2024 that unlocked the FTSE Russell reclassification.

WHAT IS EXECUTABLE AND WHAT IS NOT. USDVND is NOT on this broker's registry -- the dong is not
convertible and its offshore market is a thin non-deliverable forward settled against the 03:00
UTC regional fixing. Neither the VN-Index, the VN30 future, the SJC bar price, the central rate
nor Vietnamese government bonds is quotable. All are named in `TRANSMISSION_TARGETS`. What IS
quotable is the commodity and demand complex Vietnam sits inside: COFROB for robusta, COTTON for
the textile input, CORN and SOYBEAN for the livestock feed import, US500 and NAS100 for the
electronics demand that Vietnamese assembly serves, XAUUSD for the gold channel, and USDCNH,
USDTHB, USDSGD and USDIDR for whatever a dong move reaches.

THE BILATERAL LINKS THIS PACK OWNS. Vietnam is the Philippines' rice supplier and the Philippines
is Vietnam's largest rice customer, so PH-E and VN-H are two ends of one trade. Vietnam and
Thailand are the two residual rice suppliers when India restricts, which ties VN-H to TH-G and
IN-L. And Vietnamese assembly competes directly with Malaysian and Philippine assembly for the
same electronics orders.

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
CODE = "VN"
NAME = "Vietnam"
REGION_COMMAND = "southeast_asia"
CURRENCY = "VND"
FISCAL_YEAR_END = "12-31"  # the state budget runs on the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("vi", "en")

#: NO VIETNAMESE INSTRUMENT IS IN THIS LIST. The dong is not convertible and USDVND is not on the
#: broker registry, so this is the set of symbols Vietnam's mechanisms REACH.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "COFROB", "COFARA",                      # about two fifths of world robusta production
    "COTTON",                                # a top-three cotton importer, for the textile book
    "CORN", "SOYBEAN", "WHEAT",              # a very large livestock feed importer
    "SUGAR",                                 # a protected domestic sector with import quotas
    "XAUUSD", "XAGUSD",                      # the SJC premium and household gold demand
    "XTIUSD", "XBRUSD", "XNGUSD",            # a net energy importer with limited refining
    "USDCNH",                                # the input side of the assembly model; the dong
                                             # tracks the yuan more closely than anything else
    "USDTHB", "USDSGD", "USDIDR",            # the regional complex a dong move can reach
    "USDX",                                  # the dollar factor every claim here must remove
    "US500", "NAS100",                       # where the electronics assembly demand comes from
    "HK50", "CHINAH",                        # the EM Asia risk factor and the China link
    "UST10Y",                                # the external rate anchor for the whole complex
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/VND spot and the SBV central rate", "venue": "onshore interbank; offshore NDF",
     "why": "the dong is not convertible. The SBV publishes a daily CENTRAL RATE and a plus or "
            "minus 5% band, and sells dollars at a fixed intervention price that acts as a hard "
            "ceiling; none of it is quotable here",
     "proxies": ("USDCNH", "USDTHB", "USDSGD")},
    {"name": "VN-Index and VN30", "venue": "Ho Chi Minh Stock Exchange (HOSE)",
     "why": "the domestic equity market, censored by a plus or minus 7% daily band, with a "
            "foreign ownership room and a T+2 cycle",
     "proxies": ("HK50", "CHINAH", "US500")},
    {"name": "VN30 index futures", "venue": "Hanoi Stock Exchange (HNX)",
     "why": "the only liquid Vietnamese derivative; it expires on the THIRD THURSDAY and settles "
            "against the average VN30 over the last 30 minutes including the ATC auction, which "
            "is a rule no other venue in this department uses",
     "proxies": ("HK50", "CHINAH")},
    {"name": "SJC gold bar domestic price", "venue": "SJC and licensed dealers",
     "why": "the domestic price of a state-branded bar, which traded at a high-teens percentage "
            "premium to world gold before the SBV began direct sales on 3 June 2024",
     "proxies": ("XAUUSD", "XAGUSD")},
    {"name": "Vietnamese government bonds", "venue": "HNX bond market",
     "why": "a shallow market dominated by domestic banks; the curve is an output of the credit "
            "quota system rather than an independent price",
     "proxies": ("UST10Y",)},
    {"name": "Vietnamese robusta FOB differential",
     "venue": "Dak Lak and Ho Chi Minh City physical trade",
     "why": "the publicly quoted spread of Vietnamese physical robusta to the London price IS "
            "the observable of farmer holding behaviour, and it is the mechanism's direct read",
     "proxies": ("COFROB",)},
    {"name": "Vietnamese rice export quotes", "venue": "Vietnam Food Association",
     "why": "Vietnam is a top-three rice exporter and the Philippines' largest supplier; the "
            "quote is the direct bilateral link between this pack and PH-E",
     "proxies": ("WHEAT", "CORN")},
    {"name": "credit growth quotas (room tin dung)", "venue": "State Bank of Vietnam",
     "why": "the SBV allocates annual credit growth ceilings to individual banks, which is a "
            "quantity instrument with no price and no analogue in this department",
     "proxies": ("HK50", "USDCNH")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "State Bank of Vietnam",
    "short": "SBV",
    "committee": "no independent committee; the SBV is a ministry-level agency of the government "
                 "and policy is set administratively rather than by a published vote",
    "policy_instrument": "the DAILY CENTRAL RATE (ty gia trung tam) with a trading band, plus "
                         "the refinancing and discount rates, open-market bill operations, and "
                         "annual credit growth quotas allocated to individual banks",
    "band": "plus or minus 5% around the central rate since 17 October 2022, widened from plus or "
            "minus 3%; the band edge is a hard limit on commercial bank quotes",
    "central_rate_rule": "published each morning, derived from a weighted average of the previous "
                         "day's interbank rate, a basket of EIGHT reference currencies (the US "
                         "dollar, euro, yuan, yen, Singapore dollar, won, Taiwan dollar and baht) "
                         "and the authorities' macro-balance objectives. THE BASKET WEIGHTS ARE "
                         "NOT PUBLISHED, so the rate is printed and the rule behind it is not",
    "intervention_price": "the SBV sells dollars to commercial banks at an announced fixed price, "
                          "which functions as a hard ceiling on the onshore rate and is changed "
                          "only by announcement -- a far more visible defence than any of its "
                          "neighbours run",
    "mandate": "currency value stability, banking system safety and support for growth; the SBV "
               "is not independent and its objectives are set with the government",
    "decision_rule": "NO SCHEDULED MEETING CALENDAR. Rate changes are announced by decision "
                     "(quyet dinh) when the government decides, with immediate or near-immediate "
                     "effect. The recurring daily clock is the central rate at about 01:00 UTC; "
                     "the recurring annual clock is the credit quota allocation, set early in the "
                     "year and revised in-year",
    "announce_local": "central rate about 08:00 ICT; policy decisions at no fixed hour",
    "announce_utc": "01:00",
    "presser_utc": "none scheduled",
    "off_cycle": "EVERYTHING here is off-cycle by the standards of the rest of this department. "
                 "A rate decision, a band widening, an intervention-price change and a credit "
                 "quota revision all arrive without a published calendar, which means a Vietnam "
                 "event study cannot be built from a date list and must be built from a "
                 "DOCUMENT FEED",
    "other_clocks": (
        {"what": "daily central rate publication", "when_local": "about 08:00 ICT",
         "when_utc": "01:00", "reference_lag_days": 0},
        {"what": "General Statistics Office monthly socio-economic report",
         "when_local": "the 6th and again near month end", "when_utc": "03:00",
         "reference_lag_days": 6},
        {"what": "General Department of Customs preliminary half-month trade data",
         "when_local": "around the 10th-12th and the 25th-27th", "when_utc": "03:00",
         "reference_lag_days": 10},
        {"what": "credit growth quota allocation", "when_local": "early in the year",
         "when_utc": "03:00", "reference_lag_days": 0},
    ),
    "dates": {2024: (), 2025: (), 2026: ()},
    "dates_status": "DELIBERATELY EMPTY, and this is a finding rather than a gap. The SBV "
                    "publishes no policy meeting calendar: decisions arrive as government "
                    "documents when the government decides. Any Vietnam event study must be "
                    "driven by a decision-document feed from sbv.gov.vn rather than by a date "
                    "list, and a pack that invented a schedule here would be inventing the one "
                    "thing this central bank does not have (L1.28a)",
}

# --------------------------------------------------------------------------- fixings, settlement
#: ICT is UTC+7 all year with no daylight saving.
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "SBV central rate (ty gia trung tam)",
     "administrator": "State Bank of Vietnam",
     "window_local": "computed overnight from the previous day's interbank average and the "
                     "reference basket",
     "window_utc": "previous session",
     "publish_local": "about 08:00 ICT each working day", "publish_utc": "01:00",
     "basis": "a weighted average of the previous day's interbank rate, a basket of eight "
              "reference currencies, and the authorities' macro-balance objectives",
     "uses": "the anchor of the plus or minus 5% band within which every commercial bank must "
             "quote",
     "note": "THE MOST INFORMATIVE DAILY PRINT IN THIS DEPARTMENT: a crawling peg whose anchor is "
             "published every morning. The basket WEIGHTS are not published, so the rate is "
             "observable and the reaction function is not -- which is the research problem"},
    {"name": "SBV intervention selling price",
     "administrator": "State Bank of Vietnam",
     "window_local": "in force until changed by announcement", "window_utc": "continuous",
     "publish_local": "on announcement", "publish_utc": "varies",
     "basis": "an announced fixed price at which the SBV sells dollars to commercial banks",
     "uses": "a hard ceiling on the onshore rate whenever the market reaches it",
     "note": "when the onshore rate sits at this price for days at a time, the currency is PINNED "
             "and its realised volatility is an artefact of the ceiling; a volatility statistic "
             "computed across a pinned period is measuring the SBV and not the market"},
    {"name": "commercial bank quoted band edges",
     "administrator": "the commercial banks, within the SBV's band",
     "window_local": "the onshore session", "window_utc": "01:00-09:00",
     "publish_local": "continuously on bank rate boards", "publish_utc": "01:00-09:00",
     "basis": "each bank's own buy and sell quote, constrained to the plus or minus 5% band",
     "uses": "the rate a Vietnamese corporate or household actually transacts at",
     "note": "banks CLUSTER at the band's upper edge in depreciation episodes, so the distance "
             "of the quoted rate from the ceiling is a continuous, free measure of pressure -- "
             "the closest thing Vietnam has to a market-implied stress index"},
    {"name": "ABS/SFEMC VND spot fixing",
     "administrator": "ABS Benchmarks Administration Co, Singapore",
     "window_local": "concluding about 11:00 SGT, which is 10:00 ICT",
     "window_utc": "02:30-03:00", "publish_local": "about 11:00 SGT", "publish_utc": "03:00",
     "basis": "the regional Asian currency fixing panel",
     "uses": "settlement of the thin offshore VND non-deliverable forward",
     "note": "the VND leg of the 03:00 UTC regional instant is the smallest of the nine; a "
             "VND-specific fixing effect is the least likely in the set and that expectation "
             "should be stated before the measurement, not after it"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"market": "USD/VND onshore interbank spot", "cycle": "T+2",
     "session_local": "08:00-16:00 ICT", "session_utc": "01:00-09:00",
     "note": "the dong is NOT convertible. Onshore foreign currency lending and deposit rates are "
             "administratively capped, and the offshore forward market is thin and "
             "non-deliverable"},
    {"market": "HOSE equities", "cycle": "T+2, with the 2024 non-prefunding reform removing the "
                                         "requirement for foreign investors to fully pre-fund",
     "session_local": "ATO 09:00-09:15, continuous 09:15-11:30, break 11:30-13:00, continuous "
                      "13:00-14:30, ATC 14:30-14:45, put-through to 15:00 ICT",
     "session_utc": "02:00-04:30 and 06:00-08:00",
     "note": "the non-prefunding reform is what unlocked the FTSE Russell reclassification, and "
             "it is a structural break in foreign participation dated to late 2024"},
    {"market": "HNX and UPCoM equities", "cycle": "T+2",
     "session_local": "as HOSE, with a continuous close rather than an ATC on UPCoM",
     "session_utc": "02:00-08:00",
     "note": "the daily price band is 10% on HNX and 15% on UPCoM against 7% on HOSE, so the "
             "SAME stock's return distribution is censored differently depending on where it is "
             "listed -- a natural experiment in censoring that few markets provide"},
    {"market": "VN30 index futures", "cycle": "cash settled in dong",
     "session_local": "08:45-14:45 ICT, opening before the cash market and closing with it",
     "session_utc": "01:45-07:45",
     "note": "the future opens fifteen minutes BEFORE the cash ATO, so the pre-open future is the "
             "only Vietnamese price discovery before the auction"},
    {"market": "SJC gold bars", "cycle": "immediate physical",
     "session_local": "dealer hours, roughly 01:00-11:00 UTC",
     "session_utc": "01:00-11:00",
     "note": "a state-branded bar whose premium to world gold was an administrative variable "
             "until 2025; buy-sell spreads at the dealers widen dramatically in stress and are "
             "themselves an observable"},
)

# --------------------------------------------------------------------------- exchanges
EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Ho Chi Minh Stock Exchange", "code": "HOSE",
     "hours_local": "ATO 09:00-09:15, continuous 09:15-11:30 and 13:00-14:30, ATC 14:30-14:45, "
                    "put-through to 15:00 ICT",
     "hours_utc": "02:00-04:30 and 06:00-08:00",
     "expiry_rule": "n/a for cash",
     "settlement": "T+2, with non-prefunding available to foreign institutional investors since "
                   "late 2024",
     "rebalance": "VN30 reviewed semi-annually, effective in the first Monday of February and "
                  "August windows",
     "price_band": "plus or minus 7% against the previous reference price. The daily return "
                   "distribution is CENSORED BY RULE and the informative variable is the COUNT "
                   "of securities at the ceiling (tran) or the floor (san), never the tails"},
    {"name": "Hanoi Stock Exchange", "code": "HNX",
     "hours_local": "as HOSE", "hours_utc": "02:00-08:00",
     "expiry_rule": "n/a for cash",
     "settlement": "T+2",
     "rebalance": "HNX30 semi-annual",
     "price_band": "plus or minus 10%, wider than HOSE, which makes cross-listing comparisons a "
                   "free test of how much the band binds"},
    {"name": "HNX derivatives -- VN30 index futures", "code": "HNX-VN30F",
     "hours_local": "08:45-14:45 ICT", "hours_utc": "01:45-07:45",
     "expiry_rule": "the THIRD THURSDAY of the contract month",
     "settlement": "cash, against the AVERAGE of the VN30 index over the last 30 minutes of the "
                   "final trading day, including the ATC auction -- a settlement rule no other "
                   "venue in this department uses",
     "rebalance": "with the VN30",
     "price_band": "the future's band is wider than the cash market's, which is why the basis can "
                   "move when the cash index cannot"},
    {"name": "UPCoM", "code": "UPCOM",
     "hours_local": "as HOSE", "hours_utc": "02:00-08:00",
     "expiry_rule": "n/a",
     "settlement": "T+2",
     "rebalance": "n/a",
     "price_band": "plus or minus 15%, the widest of the three boards"},
)

# --------------------------------------------------------------------------- the holiday rule
#: The Tet block is the longest market closure in Asia after Indonesia's Lebaran, and like
#: Lebaran it is set by government decision rather than by a computable rule: the statutory
#: entitlement is five days and the government routinely extends the block to bridge weekends.
_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "Tet Duong Lich (Gregorian New Year)",
        "2024-02-08": "Tet Nguyen Dan (Lunar New Year block)",
        "2024-02-09": "Tet Nguyen Dan (New Year's Eve)",
        "2024-02-12": "Tet Nguyen Dan (day 3)",
        "2024-02-13": "Tet Nguyen Dan (day 4)",
        "2024-02-14": "Tet Nguyen Dan (day 5)",
        "2024-04-18": "Gio To Hung Vuong (Hung Kings Commemoration)",
        "2024-04-29": "Reunification Day observed",
        "2024-04-30": "Ngay Giai Phong (Reunification Day)",
        "2024-05-01": "Ngay Quoc te Lao dong (International Labour Day)",
        "2024-09-02": "Quoc Khanh (National Day)",
        "2024-09-03": "Quoc Khanh (additional day)",
    },
    2025: {
        "2025-01-01": "Tet Duong Lich (Gregorian New Year)",
        "2025-01-27": "Tet Nguyen Dan (New Year's Eve)",
        "2025-01-28": "Tet Nguyen Dan (New Year's Eve)",
        "2025-01-29": "Tet Nguyen Dan (day 1)",
        "2025-01-30": "Tet Nguyen Dan (day 2)",
        "2025-01-31": "Tet Nguyen Dan (day 3)",
        "2025-04-07": "Gio To Hung Vuong (Hung Kings Commemoration)",
        "2025-04-30": "Ngay Giai Phong (Reunification Day)",
        "2025-05-01": "Ngay Quoc te Lao dong (International Labour Day)",
        "2025-09-02": "Quoc Khanh (National Day)",
    },
    2026: {
        "2026-01-01": "Tet Duong Lich (Gregorian New Year)",
        "2026-02-16": "Tet Nguyen Dan (New Year's Eve)",
        "2026-02-17": "Tet Nguyen Dan (day 1, Binh Ngo, Year of the Horse)",
        "2026-02-18": "Tet Nguyen Dan (day 2)",
        "2026-02-19": "Tet Nguyen Dan (day 3)",
        "2026-02-20": "Tet Nguyen Dan (day 4)",
        "2026-04-26": "Gio To Hung Vuong (Hung Kings Commemoration)",
        "2026-04-30": "Ngay Giai Phong (Reunification Day)",
        "2026-05-01": "Ngay Quoc te Lao dong (International Labour Day)",
        "2026-09-02": "Quoc Khanh (National Day)",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": "The Labour Code grants a small number of statutory public holidays: 1 January, the "
            "Tet Nguyen Dan block, Gio To Hung Vuong (the 10th day of the 3rd lunar month), 30 "
            "April (Reunification Day), 1 May and 2 September (National Day, with an adjacent "
            "day added since 2021). TET IS THE PART NO RULE GENERATES. The statutory entitlement "
            "is five days around the lunar new year, but the government issues an annual "
            "notification (thong bao) that fixes the exact block and routinely EXTENDS it to "
            "bridge weekends, so the closure has run from five to nine consecutive days in "
            "recent years and the length is a decision, not a calculation. When a statutory "
            "holiday falls at a weekend the following working day is taken in lieu. Gio To Hung "
            "Vuong is lunisolar and moves by weeks in the Gregorian calendar.",
    "table": _HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED for the statutory dates and the announced Tet block",
               2025: "CONFIRMED for the statutory dates and the announced Tet block",
               2026: "PROVISIONAL -- Tet Binh Ngo begins on 17 February 2026 and the fixed "
                     "statutory dates are certain; the exact length of the Tet block and the "
                     "Hung Kings date are ESTIMATES until the government notification is read"},
    "than_tai": {2024: "2024-02-19", 2025: "2025-02-07", 2026: "2026-02-26",
                 "what": "Ngay via Than Tai, the God of Wealth day on the 10th day of the first "
                         "lunar month. It is NOT a public holiday and the market is open, but it "
                         "is the single largest day of retail gold buying in Vietnam and dealers "
                         "queue around the block. A gold-demand cell that ignores it is missing "
                         "the one Vietnamese date that reliably moves physical demand",
                 "status": "2026 is PROVISIONAL, derived from the Tet date"},
    "regional_note": "Tet falls on the same day as Chinese New Year -- 17 February 2026 -- so "
                     "Vietnam, China, Hong Kong, Taiwan, Korea, Singapore and Malaysia are all "
                     "shut together, and the Vietnamese block is the longest of them",
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "HOSE daily foreign trading (khoi ngoai)",
     "root": "https://www.hsx.vn/Modules/Statistic/", "fields": ("foreign buy volume and value",
                                                                 "foreign sell volume and value",
                                                                 "net by security"),
     "frequency": "daily", "publish_utc": "08:30", "lag_days": 0, "licence": "free, public",
     "why": "the foreign bloc is followed obsessively by Vietnamese retail and is the single most "
            "quoted number in the domestic market commentary; it is free and published at the "
            "close"},
    {"name": "foreign ownership room utilisation",
     "root": "https://www.hsx.vn/Modules/Listed/", "fields": ("foreign ownership percentage",
                                                              "remaining room by security"),
     "frequency": "daily", "publish_utc": "08:30", "lag_days": 0, "licence": "free, public",
     "why": "a security at its 49% room (or 30% for a bank) CANNOT absorb further foreign buying, "
            "so room utilisation is a hard constraint on the flow and explains why index "
            "inclusion money can be blocked at the security level"},
    {"name": "ceiling and floor counts (so ma tran, so ma san)",
     "root": "https://www.hsx.vn/Modules/Statistic/", "fields": ("securities at the ceiling",
                                                                 "securities at the floor"),
     "frequency": "daily", "publish_utc": "08:30", "lag_days": 0, "licence": "free, public",
     "why": "the UNCENSORED observable in a market whose return distribution is truncated by "
            "rule; a tail statistic computed on returns is a statistic about the band, and this "
            "count is what should be used instead"},
    {"name": "General Department of Customs half-month trade data",
     "root": "https://www.customs.gov.vn/", "fields": ("exports and imports by commodity",
                                                        "coffee volume", "textile exports",
                                                        "destination breakdown"),
     "frequency": "twice monthly", "publish_utc": "03:00", "lag_days": 10,
     "licence": "free, public",
     "why": "TWICE-MONTHLY customs data is unusually fast for this region and the coffee volume "
            "line is the direct read on whether farmers are releasing beans"},
    {"name": "SBV central rate and commercial bank quote boards",
     "root": "https://www.sbv.gov.vn/", "fields": ("central rate", "band edges",
                                                    "bank buy and sell quotes"),
     "frequency": "daily", "publish_utc": "01:00", "lag_days": 0, "licence": "free, public",
     "why": "the distance of the quoted rate from the band's upper edge is a free, continuous "
            "measure of depreciation pressure -- the closest thing Vietnam has to a market-"
            "implied stress index"},
    {"name": "CFTC Commitments of Traders",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("non-commercial net in coffee, cotton, gold, the dollar index",),
     "frequency": "weekly", "publish_utc": "20:30", "lag_days": 3, "licence": "free, public",
     "why": "VND is not in the COT. The COFFEE leg is the speculative counterpart to Vietnamese "
            "farmer holding behaviour and the two together are the whole robusta position"},
)

# --------------------------------------------------------------------------- terminology
#: Vietnamese WITH DIACRITICS. Vietnamese is written in a Latin alphabet with tone and vowel
#: marks, and an unaccented search is a different word: "ty gia" without marks does not match
#: "ty gia" with them in most search engines, and the domestic press writes with them. The
#: unaccented forms are included ALONGSIDE, not instead, because forum and chat text is often
#: typed without marks.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "VN-A": ("tỷ giá trung tâm", "biên độ", "Ngân hàng Nhà nước", "tỷ giá", "neo tỷ giá",
             "ty gia trung tam", "central rate", "trading band"),
    "VN-B": ("giá bán can thiệp", "bán ngoại tệ", "dự trữ ngoại hối", "áp trần tỷ giá",
             "can thiệp", "intervention selling price"),
    "VN-C": ("room tín dụng", "hạn mức tăng trưởng tín dụng", "lãi suất điều hành",
             "thanh khoản", "tín phiếu", "credit growth quota"),
    "VN-D": ("xuất khẩu", "điện tử", "linh kiện", "Samsung", "gia công", "FDI",
             "đầu tư trực tiếp nước ngoài", "electronics exports"),
    "VN-N": ("thuế quan", "thuế đối ứng", "trung chuyển", "hàng rào thương mại",
             "tariff", "transshipment"),
    "VN-F": ("cà phê", "cà phê Robusta", "Đắk Lắk", "giá cà phê", "nông dân găm hàng",
             "trừ lùi", "cộng thưởng", "niên vụ", "farmer holding", "FOB differential"),
    "VN-G": ("dệt may", "bông", "sợi", "da giày", "đơn hàng", "textile orders"),
    "VN-H": ("gạo", "xuất khẩu gạo", "giá gạo", "Philippines", "hợp đồng tập trung",
             "rice export quote"),
    "VN-I": ("giá vàng", "vàng miếng SJC", "chênh lệch giá vàng", "vàng nhẫn",
             "ngày vía Thần Tài", "đấu thầu vàng", "SJC premium"),
    "VN-J": ("trần", "sàn", "biên độ dao động", "khối ngoại", "room ngoại", "thanh khoản",
             "ATO", "ATC", "ceiling", "floor"),
    "VN-K": ("phái sinh", "hợp đồng tương lai", "VN30F", "đáo hạn", "ngày đáo hạn",
             "cơ sở", "basis", "expiry"),
    "VN-L": ("Tết Nguyên Đán", "nghỉ Tết", "thưởng Tết", "lì xì", "sau Tết",
             "Tet bonus", "post-Tet liquidity"),
    "VN-M": ("nâng hạng", "thị trường mới nổi", "FTSE Russell", "MSCI", "prefunding",
             "không ký quỹ trước", "market reclassification"),
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
    English query against a Vietnamese forum returns nothing, and returning nothing is
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


#: Layers with no source in this pack, each with the reason. Empty here: all ten are populated.
ABSENT_SOURCE_LAYERS: dict[str, str] = {}

SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    _src("VN-S1", "State Bank of Vietnam and government decision documents", layer="official",
         roots=("https://www.sbv.gov.vn/webcenter/portal/vi/menu/trangchu/tk/hdtt",
                "https://www.sbv.gov.vn/webcenter/portal/vi/menu/fm/vbqppl",
                "https://vanban.chinhphu.vn/", "https://www.gso.gov.vn/",
                "https://www.customs.gov.vn/"),
         languages=("vi", "en"), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("tỷ giá trung tâm hôm nay", "quyết định lãi suất Ngân hàng Nhà nước",
                  "thông tư ngân hàng nhà nước", "số liệu xuất nhập khẩu kỳ 1",
                  "báo cáo tình hình kinh tế xã hội"),
         notes="THE DECISION FEED IS THE CALENDAR. The SBV publishes no meeting schedule, so the "
               "legal-document portal is what a Vietnam event study must be driven from; "
               "vanban.chinhphu.vn carries the government decrees that change the gold regime and "
               "the tariff position"),
    _src("VN-S2", "exchanges, the securities commission and the index providers",
         layer="institutional",
         roots=("https://www.hsx.vn/Modules/Statistic/", "https://www.hnx.vn/",
                "https://www.ssc.gov.vn/", "https://www.vsd.vn/",
                "https://www.ftserussell.com/research/equity-country-classification"),
         languages=("vi", "en"), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("khối ngoại mua ròng", "room ngoại còn lại", "quy chế giao dịch",
                  "hợp đồng tương lai VN30F đáo hạn", "nâng hạng thị trường"),
         notes="HOSE publishes the foreign flow, the room utilisation and the ceiling and floor "
               "counts free and daily; FTSE Russell's classification reviews are the dated "
               "external events that VN-M is about"),
    _src("VN-S3", "Vietnamese and multilateral academic work", layer="academic",
         roots=("https://www.fulbright.edu.vn/en/research/", "https://www.adb.org/publications",
                "https://www.imf.org/en/Publications/CR", "https://www.nber.org/papers"),
         languages=("vi", "en"), licence="free, public", access_label="PUBLIC",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("chính sách tỷ giá Việt Nam nghiên cứu", "truyền dẫn tỷ giá",
                  "exchange rate pass-through Vietnam", "crawling peg Vietnam"),
         notes="Fulbright School and the IMF Article IV staff reports are where the central rate's "
               "basket and the pass-through elasticity are actually estimated, because the SBV "
               "publishes neither"),
    _src("VN-S4", "the physical coffee and rice trade's own practitioners", layer="practitioner",
         roots=("https://giacaphe.com/", "https://vicofa.org.vn/",
                "https://www.vietfood.org.vn/", "https://tintaynguyen.com/"),
         languages=("vi",), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="UNTESTED",
         queries=("giá cà phê hôm nay Đắk Lắk", "trừ lùi cà phê", "nông dân găm hàng cà phê",
                  "giá gạo xuất khẩu hôm nay", "hợp đồng tập trung gạo"),
         notes="giacaphe.com publishes the daily Central Highlands farmgate price and the FOB "
               "differential talk that IS the observable of farmer holding behaviour. This is the "
               "single most valuable non-official source in the pack and it exists only in "
               "Vietnamese"),
    _src("VN-S5", "retail investor forums and chat", layer="retail_ecology",
         roots=("https://f319.com/", "https://f247.com/", "https://www.reddit.com/r/VietNam/",
                "https://vozforums.com/"),
         languages=("vi",), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("đội lái", "bơm thổi", "hàng nóng", "khối ngoại xả", "call margin",
                  "cháy tài khoản", "kèo thơm"),
         notes="F319 is the oldest Vietnamese stock forum and is full of pump talk, rumour and "
               "outright manipulation attempts. KEPT DELIBERATELY as a low-weight evidence "
               "object: 'doi lai' (the steering team) and margin-call chatter are a genuine "
               "sentiment and crowding feature even when every individual claim is false. Never "
               "used as a fact source, never dropped"),
    _src("VN-S6", "broker apps, their public APIs and the margin ecosystem",
         layer="app_ecosystem",
         roots=("https://www.vndirect.com.vn/", "https://fireant.vn/", "https://vietstock.vn/",
                "https://api.vietstock.vn/", "https://www.ssi.com.vn/khach-hang-ca-nhan"),
         languages=("vi",), licence="public web; API terms vary by provider",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("dư nợ margin", "tỷ lệ ký quỹ", "sức mua", "bảng giá trực tuyến",
                  "app chứng khoán"),
         notes="Vietnamese retail trades through a small number of broker apps that publish "
               "market-wide MARGIN BALANCES quarterly -- an unusual disclosure and a real "
               "crowding observable. ACCESS_UNCLEAR is deliberate: the data pages are public and "
               "the API terms are not uniformly stated, so each root must be checked before any "
               "automated collection"),
    _src("VN-S7", "Vietnamese financial press", layer="media",
         roots=("https://cafef.vn/", "https://vneconomy.vn/", "https://vnexpress.net/kinh-doanh",
                "https://tinnhanhchungkhoan.vn/", "https://thanhnien.vn/kinh-te.htm"),
         languages=("vi",), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("giá vàng SJC hôm nay", "tỷ giá USD ngân hàng", "chứng khoán hôm nay",
                  "lãi suất huy động", "thưởng Tết"),
         notes="CafeF is the highest-traffic Vietnamese financial site and carries the domestic "
               "reading of a gold or currency move hours before any English wire. The SJC price "
               "and the bank quote boards are published here continuously"),
    _src("VN-S8", "gazette, legal and web archives", layer="archive",
         roots=("https://congbao.chinhphu.vn/", "https://thuvienphapluat.vn/",
                "https://web.archive.org/web/*/sbv.gov.vn*"),
         languages=("vi",), licence="gazette free; the legal library has terms",
         access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
         predictive_state="NOT_PREDICTIVE",
         queries=("Nghị định 24/2012 vàng", "Nghị định 232/2025", "công báo chính phủ",
                  "quyết định biên độ tỷ giá"),
         notes="THE ONLY WAY TO DATE A REGIME CHANGE CORRECTLY. Decree 24 of 2012 created the SJC "
               "monopoly and the 2025 decree ended it; the gazette carries the signature dates "
               "and the effective dates, which differ and which a news article routinely "
               "conflates. NOT_PREDICTIVE by construction -- an archive establishes WHEN, never "
               "what happens next"),
    _src("VN-S9", "the physical economy: farmgate, ports, power and gold counters",
         layer="physical_economy",
         roots=("https://giacaphe.com/gia-ca-phe-noi-dia/", "https://sjc.com.vn/giavang",
                "https://www.vinacomin.vn/", "https://www.evn.com.vn/",
                "http://www.vpa.org.vn/"),
         languages=("vi",), licence="free, public",
         access_label="PUBLIC", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("giá cà phê nhân xô", "giá vàng SJC mua vào bán ra", "sản lượng điện",
                  "cảng Cát Lái", "container xuất khẩu"),
         notes="the SJC counter publishes its own buy and sell prices continuously, and the "
               "BUY-SELL SPREAD widens dramatically in stress -- a free dealer-stress observable. "
               "Farmgate coffee prices at the Central Highlands collection points are the "
               "upstream end of COFROB"),
    _src("VN-S10", "the source graph: who cites whom, and the dataset registries",
         layer="source_graph",
         roots=("https://data.worldbank.org/country/vietnam",
                "https://www.imf.org/en/Countries/VNM",
                "https://comtradeplus.un.org/", "https://ourworldindata.org/"),
         languages=("en",), licence="free, public / open data",
         access_label="OPEN_DATA", credibility="RELIABLE", predictive_state="NOT_PREDICTIVE",
         queries=("Vietnam trade data mirror", "UN Comtrade Vietnam coffee",
                  "Vietnam statistics dataset registry"),
         notes="THE META LAYER, and it earns its place here for one specific reason: Vietnamese "
               "customs data is MIRRORED by UN Comtrade and by the multilateral databases with "
               "different lags and occasionally different revisions, so the source graph is how "
               "the desk discovers that two 'official' numbers for the same month disagree -- "
               "which has happened with coffee export volumes"),
    _src("VN-S11", "licensed price assessors for the physical coffee and rice trade",
         layer="physical_economy",
         roots=("https://www.spglobal.com/commodityinsights/en/our-methodology/",
                "https://www.reuters.com/markets/commodities/"),
         languages=("en",), licence="methodology free; the assessments themselves are licensed",
         access_label="LICENSED", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         machine_use_allowed=False,
         notes="REGISTERED AND NOT SCRAPED. The assessed differentials would be the ideal input "
               "to VN-F and the terms forbid automated extraction, so this row exists to record "
               "that the material is known, is relevant, and is deliberately unread. The free "
               "substitute is giacaphe.com's published farmgate and differential talk, which is "
               "noisier and is what VN-F actually uses"),
    _src("VN-S12", "rumour channels and unverified market chatter", layer="retail_ecology",
         roots=("https://t.me/s/", "https://www.facebook.com/groups/",
                "https://www.youtube.com/results?search_query="),
         languages=("vi",), licence="public social; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("tin đồn nâng hạng", "room tín dụng nới", "sắp có sóng", "đội lái thao túng",
                  "phím hàng"),
         notes="FRINGE AND KEPT. Vietnamese market rumour -- an imminent credit-quota loosening, "
               "an index upgrade, a steering team in a particular stock -- is frequently false "
               "and occasionally the first signal of a real administrative decision, because "
               "decisions here arrive without a calendar. Held as a low-weight evidence object "
               "with the FRINGE label attached, never promoted to a fact, never deleted"),
)

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("SBV daily central rate and band", source="State Bank of Vietnam",
            coverage="2016-", frequency="daily", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2016-01-04", pit_feasible=True,
            assets=("USDCNH", "USDTHB"), mechanism_families=("policy_anchor", "crawling_peg"),
            how_to_fetch="sbv.gov.vn publishes the rate each working morning at about 08:00 ICT; "
                         "the series begins on 4 January 2016 and nothing before that date is "
                         "the same object, because the regime was a step-devaluation peg"),
    dataset("commercial bank USD/VND quote boards", source="the commercial banks",
            coverage="2010-", frequency="intraday", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2010-01-01", pit_feasible=True,
            assets=("USDCNH",), mechanism_families=("band_position", "stress"),
            how_to_fetch="the large banks publish buy and sell boards continuously and CafeF "
                         "aggregates them; the DISTANCE from the band's upper edge is the "
                         "variable, not the level"),
    dataset("Vietnamese robusta farmgate price and FOB differential",
            source="giacaphe.com and the Central Highlands trade", coverage="2008-",
            frequency="daily", publication_lag_days=0, revisions="none",
            licence="public web; attribute", history_from="2008-01-01", pit_feasible=True,
            assets=("COFROB",), mechanism_families=("farmer_behaviour", "physical_supply"),
            how_to_fetch="the daily Dak Lak and Lam Dong farmgate quote plus the published "
                         "differential to London; a NEGATIVE differential that narrows is the "
                         "signature of farmers releasing beans"),
    dataset("General Department of Customs half-month trade data",
            source="General Department of Vietnam Customs", coverage="2010-",
            frequency="twice monthly", publication_lag_days=10,
            revisions="the second-half figure supersedes the preliminary",
            licence="free, public", history_from="2010-01-01", pit_feasible=True,
            assets=("COFROB", "COTTON", "NAS100"),
            mechanism_families=("export_cycle", "physical_flow"),
            how_to_fetch="customs.gov.vn preliminary releases around the 10th-12th and the "
                         "25th-27th; twice-monthly is unusually fast for this region"),
    dataset("SJC gold bar buy and sell price", source="Saigon Jewelry Company",
            coverage="2010-", frequency="intraday", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2010-01-01", pit_feasible=True,
            assets=("XAUUSD",), mechanism_families=("local_premium", "intervention"),
            how_to_fetch="sjc.com.vn publishes buy and sell continuously; the PREMIUM to world "
                         "gold converted at the bank rate is the series, and the BUY-SELL SPREAD "
                         "is a separate and independently informative dealer-stress observable"),
    dataset("HOSE daily foreign flow and room utilisation",
            source="Ho Chi Minh Stock Exchange", coverage="2008-", frequency="daily",
            publication_lag_days=0, revisions="none", licence="free, public",
            history_from="2008-01-01", pit_feasible=True, assets=("HK50", "CHINAH"),
            mechanism_families=("flows", "hard_constraint"),
            how_to_fetch="the HOSE statistics module; take the ROOM alongside the flow, because "
                         "a security at its limit cannot absorb buying and the flow series alone "
                         "does not say which ones are blocked"),
    dataset("HOSE ceiling and floor counts", source="Ho Chi Minh Stock Exchange",
            coverage="2008-", frequency="daily", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2008-01-01", pit_feasible=True,
            assets=("HK50",), mechanism_families=("censoring", "breadth"),
            how_to_fetch="the daily statistics; THE UNCENSORED OBSERVABLE in a market whose "
                         "return distribution is truncated by a plus or minus 7% band"),
    dataset("General Statistics Office monthly socio-economic report",
            source="General Statistics Office", coverage="2000-", frequency="monthly",
            publication_lag_days=6, revisions="routine", licence="free, public",
            history_from="2000-01-01", pit_feasible=True, assets=("NAS100", "USDCNH"),
            mechanism_families=("activity", "inflation", "fdi"),
            how_to_fetch="gso.gov.vn publishes on about the 6th; the report carries CPI, "
                         "industrial production, registered and DISBURSED foreign direct "
                         "investment, and the two FDI numbers behave very differently"),
    dataset("Vietnamese rice export quotes", source="Vietnam Food Association",
            coverage="2008-", frequency="weekly", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2008-01-01", pit_feasible=True,
            assets=("WHEAT", "CORN"), mechanism_families=("agricultural_exports",),
            how_to_fetch="the association's weekly quote; this is the number the Philippine "
                         "import programme trades against and is the direct bilateral link to "
                         "the PH pack"),
    dataset("credit growth quota allocations and revisions",
            source="State Bank of Vietnam", coverage="2012-",
            frequency="annual with in-year revisions", publication_lag_days=0,
            revisions="revised in year, sometimes more than once", licence="free, public",
            history_from="2012-01-01", pit_feasible=True, assets=("HK50", "USDCNH"),
            mechanism_families=("quantity_policy", "liquidity"),
            how_to_fetch="announced by SBV document; a QUANTITY instrument with no price, which "
                         "means a rates-based model of Vietnamese monetary policy is modelling "
                         "the wrong lever"),
    dataset("VN30 futures open interest and basis", source="Hanoi Stock Exchange",
            coverage="2017-", frequency="daily", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2017-08-10", pit_feasible=True,
            assets=("HK50", "CHINAH"), mechanism_families=("expiry", "hedging_demand"),
            how_to_fetch="hnx.vn derivatives statistics; the contract expires on the THIRD "
                         "THURSDAY and settles on the last-30-minute average including the ATC"),
    dataset("broker margin balances", source="listed securities companies' quarterly reports",
            coverage="2015-", frequency="quarterly", publication_lag_days=30,
            revisions="none", licence="free, public", history_from="2015-01-01",
            pit_feasible=True, assets=("HK50",), mechanism_families=("crowding", "leverage"),
            how_to_fetch="aggregated from the brokers' own quarterly disclosures; an unusual "
                         "market-wide leverage observable that most markets do not publish at all"),
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor(
        "The State Bank of Vietnam's exchange rate desk",
        holds="foreign reserves, the daily central rate, and an announced fixed price at which it "
              "will sell dollars to commercial banks",
        forced_to=("publish a central rate every working morning, whatever the pressure",
                   "sell dollars at the announced intervention price whenever the market reaches "
                   "it, which converts the ceiling into a real commitment rather than a signal",
                   "manage a currency whose depreciation feeds directly into an import-dependent "
                   "cost base"),
        when="the central rate at about 01:00 UTC; intervention through the 01:00-09:00 UTC "
             "onshore session",
        information=("interbank flow it settles", "the reference basket it will not publish",
                     "state-owned bank positioning"),
        constraints=("reserves, which are modest relative to the import bill",
                     "an explicit objective of currency stability in the central bank law",
                     "the US Treasury currency report, which named Vietnam a manipulator in 2020 "
                     "and then removed the designation -- a constraint with a date"),
        instruments=("USDCNH", "USDTHB", "XAUUSD"),
        counterparties=("state-owned and joint-stock commercial banks",
                        "exporters and importers", "the thin offshore NDF market"),
        observables=("the published central rate", "the announced intervention price",
                     "the distance of bank quotes from the band's upper edge",
                     "reserve estimates, published with a long lag"),
        impact="pins the currency for long stretches at the intervention price and then allows "
               "step adjustments, so the dong's realised volatility is an artefact of the ceiling "
               "and a volatility statistic computed across a pinned period is measuring the SBV",
        persistence="the crawling-peg framework has been in place since January 2016 and the "
                    "band was widened once, in October 2022",
        falsifier="a depreciation episode in which bank quotes exceed the announced intervention "
                  "price without the SBV selling, which would mean the ceiling is a signal rather "
                  "than a commitment"),
    actor(
        "The SBV's credit-quota allocation function",
        holds="the authority to set each commercial bank's annual credit growth ceiling",
        forced_to=("allocate a system-wide credit growth target among individual banks",
                   "revise the allocation in-year when growth undershoots or a bank hits its "
                   "ceiling",
                   "use a QUANTITY instrument because the price instrument is constrained by the "
                   "exchange rate objective"),
        when="the initial allocation early in the year, with revisions announced at no fixed date",
        information=("bank-level supervisory data", "the government's growth target"),
        constraints=("the growth target set by the National Assembly",
                     "banking system asset quality, above all in property lending",
                     "the impossible trinity: with a managed rate and an open-ish capital "
                     "account, the domestic rate is not free"),
        instruments=("HK50", "CHINAH", "USDCNH"),
        counterparties=("commercial banks", "property developers", "the bond market"),
        observables=("the announced allocations and revisions",
                     "system credit growth published monthly",
                     "broker margin balances, which move with the credit cycle"),
        impact="a quantity lever with no price, which means a model of Vietnamese monetary policy "
               "built on interest rates is modelling the wrong instrument -- and a quota "
               "LOOSENING is one of the most reliable domestic equity catalysts there is",
        persistence="structural; the SBV has said repeatedly it intends to move away from quotas "
                    "and has not",
        falsifier="a year in which credit growth diverges materially from the allocated quota "
                  "without an announced revision"),
    actor(
        "Robusta coffee farmers in the Central Highlands",
        holds="roughly two fifths of world robusta production, stored on-farm after the "
              "October-to-January harvest",
        forced_to=("harvest on a biological calendar",
                   "sell eventually, because storage has a limit and debts fall due",
                   "NOT sell into a rally, which is the documented behaviour: farmers hold beans "
                   "when the price rises and release them into weakness"),
        when="harvest October to January, with release decisions made continuously through the "
             "year and concentrated before Tet, when cash is needed",
        information=("the London robusta price, which they follow closely",
                     "the local collection-point quote published daily",
                     "the FOB differential, which tells them how tight the physical market is"),
        constraints=("on-farm storage capacity and quality degradation",
                     "credit from collectors, which forces some early selling",
                     "drought, which cut output materially in the 2023-24 and 2024-25 seasons"),
        instruments=("COFROB", "COFARA"),
        counterparties=("local collectors and Vietnamese exporters",
                        "international trade houses", "Indonesian robusta as the substitute"),
        observables=("the daily Dak Lak farmgate price",
                     "the FOB differential to London, which is publicly quoted",
                     "twice-monthly customs export volumes",
                     "European and US certified stocks"),
        impact="makes short-run robusta supply elasticity PERVERSE: a price rally reduces "
               "near-term availability rather than increasing it, which is the mechanism behind "
               "robusta's tendency to trend harder than arabica in a deficit",
        persistence="structural and behavioural, documented by the trade for two decades; the "
                    "DROUGHT shock of 2023-25 is a level event on top of it",
        falsifier="a season in which rising prices coincide with accelerating farmer selling, "
                  "visible as a widening negative FOB differential and rising customs volumes"),
    actor(
        "Vietnamese coffee exporters and the FOB differential",
        holds="the physical book between the farmgate and the London price",
        forced_to=("buy from farmers who will not sell into strength",
                   "deliver against contracts struck earlier, which has repeatedly forced "
                   "defaults and renegotiations in tight seasons",
                   "quote a differential that reveals how tight the physical market is"),
        when="continuous, with the heaviest shipment from December to March",
        information=("their own book and the farmers' holding behaviour",
                     "London prices and certified stocks"),
        constraints=("contract obligations struck before the price moved",
                     "credit lines, which tighten exactly when they are most needed",
                     "port and container availability"),
        instruments=("COFROB",),
        counterparties=("international trade houses", "European roasters", "farmers"),
        observables=("the published FOB differential",
                     "customs export volumes twice a month",
                     "reports of contract defaults, which cluster in tight seasons"),
        impact="the differential is the market's own measure of physical tightness and it moves "
               "BEFORE the flat price in a squeeze, which makes it the leading half of the "
               "robusta mechanism",
        persistence="structural",
        falsifier="a season in which the differential and the London flat price move together "
                  "with no lead, which would remove the differential's information"),
    actor(
        "Electronics assemblers and their foreign parents",
        holds="the assembly capacity that made Vietnam a top-tier exporter of phones, "
              "electronics and components within fifteen years",
        forced_to=("import components, overwhelmingly from China and Korea, then export finished "
                   "goods overwhelmingly to the United States",
                   "ship on the parent's schedule",
                   "respond to tariff decisions made in Washington that they do not control"),
        when="continuous; visible in twice-monthly customs data",
        information=("parent order books", "the US tariff position",
                     "component prices from China and Korea"),
        constraints=("a very high import content, so the value added is a fraction of the gross "
                     "export number",
                     "US rules on transshipment, which carry a punitive rate",
                     "power supply, which has been a binding constraint in northern Vietnam"),
        instruments=("NAS100", "US500", "USDCNH"),
        counterparties=("US retailers and technology firms", "Chinese component suppliers",
                        "Korean parents"),
        observables=("twice-monthly customs export volumes by commodity",
                     "registered and disbursed foreign direct investment",
                     "the US bilateral trade deficit with Vietnam, which is politically salient"),
        impact="ties Vietnam simultaneously to US demand on the output side and to China on the "
               "input side, which is why the dong tracks the yuan more closely than it tracks "
               "anything else and why a US tariff is a CHINA event for Vietnam too",
        persistence="structural and still growing; the tariff risk is the live threat",
        falsifier="a quarter of rising Vietnamese electronics exports with falling US imports of "
                  "the same categories, which would mean the destination assumption is wrong"),
    actor(
        "Textile, garment and footwear exporters",
        holds="an export book second only to electronics, built on imported cotton and yarn",
        forced_to=("import cotton, which makes Vietnam a top-three world cotton importer",
                   "hold order books that are visible six months ahead and therefore forecastable",
                   "compete on labour cost with Bangladesh and India"),
        when="continuous, with order placement concentrated ahead of northern-hemisphere seasons",
        information=("their own order books", "brand buying calendars", "cotton prices"),
        constraints=("cotton and yarn input costs",
                     "labour cost inflation, which is eroding the advantage",
                     "rules-of-origin requirements in trade agreements"),
        instruments=("COTTON", "US500"),
        counterparties=("US and European brands", "cotton exporters in the US, Brazil and "
                        "Australia"),
        observables=("cotton import volumes in customs data",
                     "garment export values", "reported order-book coverage in the trade press"),
        impact="makes Vietnam a genuine marginal BUYER in the world cotton market, which is the "
               "one commodity where Vietnamese demand rather than supply is the mechanism -- the "
               "opposite direction from coffee and rice",
        persistence="structural, with a slow erosion as labour costs rise",
        falsifier="a period of rising Vietnamese garment exports with falling cotton imports and "
                  "no change in the imported-yarn share"),
    actor(
        "Rice exporters and the Vietnam Food Association",
        holds="a top-three world rice export position, with the Philippines as the largest "
              "single customer",
        forced_to=("sell the winter-spring and summer-autumn harvests",
                   "respond to Philippine import decisions they do not control",
                   "compete with Thailand and India for the same buyers"),
        when="the winter-spring harvest from February to April is the largest; export commitments "
             "run through the year",
        information=("the weekly published export quote",
                     "Philippine import clearances and policy announcements",
                     "Indian export policy, which resets the world price"),
        constraints=("Mekong Delta salinity and upstream dam operation",
                     "Philippine demand concentration, which is a single-customer risk",
                     "government-to-government contract arrangements"),
        instruments=("WHEAT", "CORN"),
        counterparties=("Philippine importers, the largest customer",
                        "African and Indonesian buyers", "Thai and Indian competitors"),
        observables=("the weekly export quote",
                     "customs volumes twice a month",
                     "Philippine import clearance data, which is the demand side of the same "
                     "trade"),
        impact="the Vietnamese quote and the Philippine import programme are two ends of ONE "
               "trade, which makes VN-H and PH-E a matched pair and the cleanest bilateral link "
               "in this department",
        persistence="structural; the Philippine concentration has increased rather than "
                    "diversified",
        falsifier="a Philippine import suspension with no fall in the Vietnamese export quote "
                  "within a month"),
    actor(
        "SJC, the licensed gold dealers and Vietnamese gold savers",
        holds="the domestic gold market: a state-branded bar, ring gold, and household savings "
              "held in metal",
        forced_to=("quote a domestic price that has been detached from world gold by regulation",
                   "buy from the SBV when it chooses to sell, which is the only legal import "
                   "channel",
                   "widen buy-sell spreads dramatically when supply is short"),
        when="dealer hours, 01:00-11:00 UTC; demand concentrated on Ngay via Than Tai, the God of "
             "Wealth day ten days after Tet",
        information=("world gold and the bank rate", "SBV auction and direct-sale announcements"),
        constraints=("Decree 24 of 2012, which gave the SBV the SJC brand monopoly",
                     "the 2025 decree that ended the monopoly and admitted licensed producers",
                     "import licensing, which is the binding supply constraint"),
        instruments=("XAUUSD", "XAGUSD"),
        counterparties=("Vietnamese households", "the SBV as the sole legal importer",
                        "the smuggling channel, which the premium created"),
        observables=("the SJC buy and sell price and the premium to world gold",
                     "the buy-sell SPREAD, which is a dealer-stress observable in its own right",
                     "SBV auction and direct-sale announcements"),
        impact="a domestic premium that reached the high teens in percentage terms and was "
               "compressed by direct state selling from 3 June 2024 -- an administrative "
               "intervention in a commodity price with a public series on both sides, which "
               "almost nothing else in this department offers",
        persistence="the household demand is structural; the PREMIUM is a policy variable and its "
                    "regime changed twice between 2024 and 2025",
        falsifier="a period of large SBV gold sales with no compression in the SJC premium"),
    actor(
        "Retail investors on HOSE and the margin cycle",
        holds="the overwhelming majority of Vietnamese daily turnover, traded through a handful "
              "of broker apps and financed with margin",
        forced_to=("trade inside a plus or minus 7% daily band",
                   "meet margin calls, which cascade because the band means a position cannot be "
                   "exited at the floor",
                   "settle T+2"),
        when="the two cash sessions, 02:00-04:30 and 06:00-08:00 UTC",
        information=("broker apps and their price boards", "F319 and the chat ecosystem",
                     "the foreign bloc's daily net, which they watch obsessively"),
        constraints=("the price band, which TRUNCATES the return distribution by rule",
                     "margin limits set by the securities commission",
                     "the absence of short selling"),
        instruments=("HK50", "CHINAH"),
        counterparties=("foreign institutions", "domestic funds", "the brokers financing them"),
        observables=("the count of securities at the ceiling or the floor",
                     "quarterly market-wide margin balances",
                     "turnover concentration"),
        impact="the band plus margin produces a specific failure mode: at the floor there is no "
               "bid, a margin call cannot be met by selling, and the cascade runs over several "
               "days rather than one -- so Vietnamese drawdowns have a characteristic multi-day "
               "shape that a one-day tail statistic cannot see",
        persistence="structural while the band and the margin regime stand",
        falsifier="a market-wide decline of more than 15% completed in a single session, which "
                  "the band makes arithmetically impossible and whose occurrence would mean the "
                  "band had been suspended"),
    actor(
        "Foreign institutional investors under the room and the prefunding reform",
        holds="a constrained position: 49% of most companies and 30% of banks, and until late "
              "2024 a requirement to pre-fund purchases in full",
        forced_to=("pre-fund, until the non-prefunding mechanism arrived in late 2024",
                   "stop buying a security that has reached its room",
                   "rebalance against frontier and, prospectively, emerging benchmarks"),
        when="daily, published at the close",
        information=("room utilisation published daily",
                     "index provider consultations and classification reviews"),
        constraints=("the ownership room, which is a HARD constraint at the security level",
                     "the prefunding requirement, now relaxed",
                     "the absence of a deliverable currency to hedge in"),
        instruments=("HK50", "CHINAH"),
        counterparties=("domestic retail, who are the other side of almost every trade",),
        observables=("daily foreign net", "room utilisation by security",
                     "FTSE Russell and MSCI classification announcements"),
        impact="index inclusion money can be BLOCKED at the security level by the room even when "
               "the country is upgraded, which is why a Vietnamese reclassification trade is a "
               "security-by-security question and not an index-level one",
        persistence="the room is statutory and changes slowly; the prefunding reform is a dated "
                    "structural break in late 2024",
        falsifier="a classification upgrade followed by foreign inflows into securities that "
                  "were already at their room, which is impossible and whose appearance would "
                  "mean the room data is wrong"),
    actor(
        "The government as a tariff counterparty to the United States",
        holds="a very large bilateral trade surplus with the United States and the political "
              "exposure that comes with it",
        forced_to=("negotiate under the threat of a punitive reciprocal tariff",
                   "police transshipment, which carries a higher rate than Vietnamese-origin "
                   "goods",
                   "avoid a currency-manipulation designation, which constrains the exchange "
                   "rate desk"),
        when="tariff announcements and negotiations arrive without a calendar, as everything "
             "here does",
        information=("its own negotiating position", "the US political calendar"),
        constraints=("dependence on the US market for roughly a third of exports",
                     "dependence on China for inputs, which is what creates the transshipment "
                     "question in the first place"),
        instruments=("NAS100", "US500", "USDCNH"),
        counterparties=("the US administration", "Chinese input suppliers",
                        "the assemblers caught between them"),
        observables=("tariff announcements and the agreed rates",
                     "the bilateral trade balance, published monthly by both sides",
                     "rules-of-origin enforcement actions"),
        impact="a tariff decision in Washington is simultaneously a Vietnamese growth shock, a "
               "Chinese supply-chain shock and a dong event, and it arrives with no notice -- "
               "which makes it the single largest unscheduled risk in this pack",
        persistence="live and unresolved; the 2025 negotiations set a rate and did not settle "
                    "the transshipment question",
        falsifier="a tariff change of more than ten percentage points with no measurable effect "
                  "on Vietnamese export volumes over two quarters"),
    actor(
        "Vietnamese households at Tet and on Than Tai day",
        holds="the cash economy, the Tet bonus, and a large aggregate stock of household gold",
        forced_to=("receive a Tet bonus (thuong Tet), which is a near-universal convention rather "
                   "than a statute",
                   "spend and gift it in the fortnight around Tet",
                   "buy gold on Ngay via Than Tai, the God of Wealth day on the tenth day of the "
                   "first lunar month, which is a custom strong enough to produce queues"),
        when="the fortnight before Tet for cash demand; Than Tai day ten days after Tet for gold",
        information=("the announced Tet holiday block", "the SJC price"),
        constraints=("the custom itself, which is not price-sensitive on the day",
                     "gold supply, which is licensed and has been short"),
        instruments=("XAUUSD",),
        counterparties=("employers", "gold dealers", "the banking system"),
        observables=("currency in circulation around Tet",
                     "SJC volumes and the buy-sell spread on Than Tai day",
                     "reported queue lengths in the domestic press"),
        impact="a single DATED day of concentrated, price-insensitive physical gold demand -- "
               "2026-02-26 -- which is the one Vietnamese date that reliably moves domestic "
               "physical demand and is invisible in any Gregorian seasonal",
        persistence="a deeply rooted custom; the SIZE grew with household wealth",
        falsifier="a Than Tai day with no widening of the SJC buy-sell spread and no reported "
                  "queueing"),
    actor(
        "Commercial banks quoting within the band",
        holds="the onshore dollar book and the customer flow of the whole economy",
        forced_to=("quote inside the plus or minus 5% band",
                   "buy dollars from the SBV at the intervention price when the market is short",
                   "cluster at the band's upper edge in depreciation episodes, because that is "
                   "where the constraint binds"),
        when="the onshore session, 01:00-09:00 UTC",
        information=("their own customer flow", "SBV guidance, which is often informal"),
        constraints=("the band", "the intervention price",
                     "administrative caps on foreign currency deposit rates, which are set at or "
                     "near zero"),
        instruments=("USDCNH",),
        counterparties=("exporters and importers", "the SBV", "households holding dollars"),
        observables=("the quote boards", "the distance from the band's upper edge",
                     "the gap between the free-market (gold shop) dollar rate and the bank rate"),
        impact="the PARALLEL rate at the gold shops versus the bank rate is a second, informal "
               "observable of pressure that exists because the official rate is administered; "
               "the gap between them is a stress measure with no official counterpart",
        persistence="structural while the band and the caps stand",
        falsifier="a depreciation episode in which the parallel and bank rates converge"),
    actor(
        "Foreign direct investors and the factory build-out",
        holds="the registered and disbursed foreign investment that built the export sector",
        forced_to=("disburse committed capital on a construction schedule",
                   "convert foreign currency into dong for land, labour and construction",
                   "decide between Vietnam, India, Mexico and Indonesia for the next plant"),
        when="registration and disbursement published monthly by the statistics office",
        information=("their own expansion plans", "the tariff position",
                     "power supply reliability, which has caused visible outages"),
        constraints=("power supply in the northern industrial provinces",
                     "land availability and industrial park capacity",
                     "the tariff and transshipment rules"),
        instruments=("USDCNH", "NAS100"),
        counterparties=("provincial authorities", "construction contractors", "the SBV"),
        observables=("registered versus DISBURSED FDI, which behave very differently: "
                     "registration is an intention and disbursement is a flow",
                     "industrial park occupancy", "power consumption data"),
        impact="a steady dollar INFLOW that partially offsets the trade and income outflows, and "
               "the disbursement series is the one that actually moves the balance of payments "
               "while the registration series is the one the press reports",
        persistence="structural and the core of the growth model; the tariff question is the "
                    "live threat to it",
        falsifier="a year of rising registered FDI with falling disbursement and no change in the "
                  "balance of payments financial account"),
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("VN-A", "The published central rate and the band as a state",
           objects=("the daily central rate at 01:00 UTC",
                    "the plus or minus 5% band since 17 October 2022",
                    "the announced intervention selling price",
                    "the distance of commercial bank quotes from the upper edge"),
           conditions=("whether the market is at, near or away from the intervention price",
                       "the yuan's own direction, since the reference basket includes it",
                       "the band era: plus or minus 3% before October 2022 and 5% after"),
           instruments=("USDCNH", "USDTHB", "USDSGD"),
           controls=("USDCNH, which is also managed against a basket by a central bank that "
                     "publishes a daily fix -- the closest available analogue and the one that "
                     "must be residualised out before any Vietnam-specific claim",
                     "periods when the rate is PINNED at the intervention price, where realised "
                     "volatility is an artefact and must be excluded rather than averaged in",
                     "the pre-2016 step-devaluation regime, where the mechanism did not exist"),
           notes="the anchor is printed and the basket weights are not, so this domain is about "
                 "RECOVERING the reaction function from an observable target -- the mirror image "
                 "of Singapore, where the rule is described and the target is not published"),
    domain("VN-B", "The intervention price as a hard ceiling",
           objects=("the announced fixed selling price",
                    "periods in which bank quotes sit at it for days",
                    "the gap between the parallel gold-shop dollar rate and the bank rate"),
           conditions=("reserve adequacy", "the size of the trade surplus",
                       "whether a US currency-report review is pending"),
           instruments=("USDCNH", "XAUUSD"),
           controls=("the parallel rate as an independent stress measure that the ceiling does "
                     "not bind -- if pressure is real it must show there when the official rate "
                     "cannot move",
                     "a censored-data treatment: a pinned rate is a CENSORED observation and "
                     "treating it as a realised price is the standard error in this market"),
           notes="the parallel-rate control is the important one: an administered price cannot "
                 "reveal pressure, and the gold-shop dollar rate is the only free price for the "
                 "same good"),
    domain("VN-C", "Credit quotas as a quantity instrument",
           objects=("the annual allocation and its in-year revisions",
                    "system credit growth", "broker margin balances",
                    "the absence of any published meeting calendar"),
           conditions=("whether a quota loosening has been announced or merely rumoured",
                       "the property sector's condition, which drives the asset-quality "
                       "constraint",
                       "the government's growth target"),
           instruments=("HK50", "CHINAH", "USDCNH"),
           controls=("interest rate changes over the same period, which should carry LESS "
                     "information than quota changes if the quantity instrument is the real one "
                     "-- a direct test of which lever matters",
                     "Chinese credit-quantity measures, the nearest analogue"),
           notes="a rates-based model of Vietnamese monetary policy is modelling the wrong lever, "
                 "and this domain's job is to demonstrate that rather than assert it"),
    domain("VN-D", "The electronics assembly export cycle",
           objects=("twice-monthly customs export volumes by commodity",
                    "registered against DISBURSED foreign direct investment",
                    "the Chinese component import side of the same goods",
                    "power supply in the northern industrial provinces"),
           conditions=("the phase of the US technology capital spending cycle",
                       "whether the constraint is demand or is power and land",
                       "the share of value added, which is a fraction of the gross export figure"),
           instruments=("NAS100", "US500", "USDCNH"),
           controls=("Korean 20-day exports and Taiwanese export orders on the same dates, which "
                     "carry the same cycle and must absorb the signal if Vietnam has none of its "
                     "own",
                     "the import side: an assembly model's exports and imports move together, so "
                     "a rise in exports with flat component imports is a measurement error",
                     "disbursed against registered FDI, since registration is an intention and "
                     "only disbursement is a flow"),
           notes="the twice-monthly customs release is the fastest read on this cycle anywhere in "
                 "the region, which is the ONLY reason to test a channel that Korea and Taiwan "
                 "otherwise dominate"),
    domain("VN-F", "Robusta: farmer holding and the FOB differential",
           objects=("the daily Central Highlands farmgate price",
                    "the published FOB differential to London",
                    "twice-monthly customs export volumes",
                    "certified stocks in Europe"),
           conditions=("the point in the October-to-January harvest and the release cycle",
                       "whether cash is needed before Tet, which forces selling",
                       "drought, which cut output in consecutive seasons"),
           instruments=("COFROB", "COFARA"),
           controls=("arabica on the same dates, where the producer behaviour is Brazilian and "
                     "completely different -- if the effect appears in both it is a coffee "
                     "factor and not a Vietnamese one",
                     "Indonesian robusta, the substitute supply",
                     "a price-versus-volume decomposition: the holding claim predicts volumes "
                     "FALL as prices rise, and a positive supply response falsifies it"),
           notes="the FALSIFIABLE core of this pack's commodity half: the claim is a PERVERSE "
                 "short-run supply elasticity, which is a strong claim and is directly measurable "
                 "in free data"),
    domain("VN-G", "Cotton demand: the one market where Vietnam is the buyer",
           objects=("cotton and yarn import volumes",
                    "garment and footwear export values",
                    "order-book coverage reported in the trade press"),
           conditions=("brand buying calendars ahead of northern-hemisphere seasons",
                       "the tariff position, which changes the order flow's destination",
                       "competition from Bangladesh and India"),
           instruments=("COTTON", "US500"),
           controls=("Bangladeshi and Indian cotton imports on the same dates, the competing "
                     "buyers, which share the world demand factor without the Vietnamese order "
                     "book",
                     "US retail inventory data, the ultimate demand"),
           notes="the direction is REVERSED from every other commodity domain in this pack: here "
                 "Vietnam is the marginal buyer, not the marginal seller, which makes the sign of "
                 "the edge opposite and is worth stating explicitly"),
    domain("VN-H", "Rice exports and the Philippine bilateral",
           objects=("the weekly export quote",
                    "twice-monthly customs volumes",
                    "Philippine import clearances and policy announcements",
                    "the winter-spring harvest from February to April"),
           conditions=("Philippine policy, which is the demand side of the same trade",
                       "Indian export restrictions, which reset the world price",
                       "Mekong Delta salinity and upstream dam operation"),
           instruments=("WHEAT", "CORN"),
           controls=("Thai quotes on the same dates, the other residual supplier, which must "
                     "move together if the cause is Indian policy and separately if it is "
                     "Vietnamese supply",
                     "wheat and corn as the non-rice grain control, since a rice-specific shock "
                     "should not move them"),
           notes="VN-H and PH-E are two ends of ONE trade and must be tested jointly; a "
                 "Vietnamese supply claim that ignores the Philippine demand decision is "
                 "measuring half of a bilateral"),
    domain("VN-I", "The SJC premium and state gold intervention",
           objects=("the SJC buy and sell price and its premium to world gold",
                    "the buy-sell spread as a dealer-stress observable",
                    "the 3 June 2024 start of direct state selling",
                    "the 2025 decree ending the monopoly",
                    "Ngay via Than Tai, the God of Wealth day"),
           conditions=("which regime is in force: monopoly, direct selling, or liberalised",
                       "whether import licensing is open",
                       "the calendar proximity to Tet and Than Tai day"),
           instruments=("XAUUSD", "XAGUSD"),
           controls=("the Indian and Thai domestic premiums on the same dates, two other large "
                     "household gold markets with no state monopoly -- the difference is the "
                     "administrative component",
                     "ring gold (vang nhan), which was NOT covered by the SJC monopoly and "
                     "therefore traded at a different premium: a within-country control that "
                     "isolates the monopoly's effect from general Vietnamese demand"),
           notes="the ring-gold control is the sharp one and it is unique to Vietnam: the same "
                 "metal, the same households, the same day, and only one of the two forms is "
                 "monopolised"),
    domain("VN-J", "A censored market: ceilings, floors and the margin cascade",
           objects=("the plus or minus 7% HOSE band and the 10% and 15% bands elsewhere",
                    "the daily count of securities at the ceiling or the floor",
                    "quarterly market-wide margin balances",
                    "the multi-day shape of Vietnamese drawdowns"),
           conditions=("the board a security is listed on, which sets its band",
                       "the level of margin balances relative to market capitalisation",
                       "whether the market is in a cascade"),
           instruments=("HK50", "CHINAH"),
           controls=("the SAME statistic computed on HNX and UPCoM, where the bands are 10% and "
                     "15% -- a within-country natural experiment in censoring that almost no "
                     "market provides",
                     "the ceiling and floor COUNTS against the return tails, which must diverge "
                     "if the band binds"),
           notes="a tail or volatility statistic on Vietnamese daily returns is a statistic about "
                 "the BAND. The count is the uncensored observable and the three-board band "
                 "difference is the control that proves it"),
    domain("VN-K", "VN30 futures expiry on the third Thursday",
           objects=("expiry on the THIRD THURSDAY of the contract month",
                    "settlement at the average VN30 over the last 30 minutes including the ATC",
                    "the futures opening fifteen minutes before the cash ATO",
                    "the basis, which can move when the cash index cannot because the future's "
                    "band is wider"),
           conditions=("open interest against its trailing median",
                       "whether the cash index is near its band",
                       "the level of margin balances"),
           instruments=("HK50", "CHINAH"),
           controls=("the third FRIDAY of the same months, the rule every other venue uses, so a "
                     "third-Friday effect here would mean the effect is not about this contract",
                     "Malaysia's 15th and last-business-day rules and NSE's Tuesday, three more "
                     "distinct expiry calendars in this department",
                     "non-expiry Thursdays"),
           notes="four different expiry rules across this department -- Vietnam's third Thursday, "
                 "Malaysia's 15th and last business day, Singapore's second-last business day, "
                 "India's Tuesday -- which between them make a regional expiry study identifiable "
                 "rather than confounded"),
    domain("VN-L", "Tet: the longest closure and the Than Tai gold day",
           objects=("the Tet block, five to nine consecutive days set by government notification",
                    "the pre-Tet cash and bonus surge",
                    "Ngay via Than Tai on the tenth day of the first lunar month",
                    "the post-Tet liquidity normalisation"),
           conditions=("the length of the announced block, which is a decision and not a rule",
                       "whether the block spans a month end",
                       "that Tet coincides with Chinese New Year, so the whole region is shut"),
           instruments=("XAUUSD", "HK50", "USDCNH"),
           controls=("Chinese New Year in markets that do NOT take a nine-day block, which "
                     "separates the Vietnamese closure length from the shared lunar date",
                     "Than Tai day itself, which is NOT a holiday and on which the market is "
                     "open -- a within-festival control that isolates the gold demand from the "
                     "closure",
                     "the offshore NDF across the block"),
           notes="Than Tai is the useful date precisely because it is a trading day: the closure "
                 "and the physical demand can be separated, which is impossible for most festival "
                 "seasonals"),
    domain("VN-M", "Index reclassification and the room constraint",
           objects=("the FTSE Russell classification reviews",
                    "the late-2024 non-prefunding reform that unlocked them",
                    "foreign ownership room utilisation by security",
                    "MSCI's separate and slower process"),
           conditions=("whether a security is at its room, which blocks inclusion money at the "
                       "security level",
                       "the review calendar, which is published years ahead",
                       "whether the reform in question is implemented or merely announced"),
           instruments=("HK50", "CHINAH"),
           controls=("the 2020-21 Chinese and the Indian FAR-route inclusions, where the "
                     "mechanism is identical and the country is not",
                     "an announcement-versus-implementation split, since an efficient market "
                     "prices the announcement",
                     "securities already at their room, which CANNOT receive the flow -- the "
                     "cleanest placebo an index study ever gets"),
           notes="the room makes a Vietnamese reclassification trade a security-by-security "
                 "question rather than an index-level one, which is why an index-level cell here "
                 "will disappoint even when the upgrade is real"),
    domain("VN-N", "Tariffs, transshipment and the assembly model",
           objects=("US reciprocal tariff announcements and the negotiated rates",
                    "the punitive transshipment rate",
                    "the bilateral trade balance, published by both sides",
                    "registered versus disbursed foreign direct investment"),
           conditions=("whether the announcement is a threat, a rate, or an enforcement action",
                       "the Chinese input share of the goods in question",
                       "the US political calendar"),
           instruments=("NAS100", "US500", "USDCNH"),
           controls=("Mexican and Indian exposure to the same announcements, the competing "
                     "relocation destinations, which share the tariff shock without the "
                     "transshipment question",
                     "Chinese exports of the same categories, since a transshipment rule is a "
                     "CHINA event expressed through Vietnam"),
           notes="the largest unscheduled risk in this pack, and it arrives with no calendar -- "
                 "which is the same structural fact as the SBV's missing meeting schedule and is "
                 "why this country needs a document feed rather than a date list"),
)

# --------------------------------------------------------------------------- miners (specs)
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("vn_central_rate_reaction", domain_ids=("VN-A",), kind="state_estimation",
          entry="research.countries.vn.miners:central_rate_reaction", cadence_s=3600.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Recovers the reference basket's implied weights from the "
                "published central rate and residualises USDCNH out before any Vietnam-specific "
                "claim; excludes PINNED periods rather than averaging them in"),
    miner("vn_parallel_rate_stress", domain_ids=("VN-B",), kind="microstructure",
          entry="research.countries.vn.miners:parallel_rate_stress", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Uses the gold-shop dollar rate as the free price for the "
                "same good when the official rate is pinned, and treats a pinned observation as "
                "CENSORED rather than realised"),
    miner("vn_credit_quota_events", domain_ids=("VN-C",), kind="event",
          entry="research.countries.vn.miners:credit_quota_events", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Driven by the sbv.gov.vn DOCUMENT FEED rather than a date "
                "list, because this central bank publishes no meeting calendar"),
    miner("vn_robusta_holding", domain_ids=("VN-F",), kind="commodity",
          entry="research.countries.vn.miners:robusta_holding", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Tests the PERVERSE elasticity claim directly: volumes must "
                "fall as prices rise, and a positive supply response falsifies the domain"),
    miner("vn_sjc_premium", domain_ids=("VN-I",), kind="basis",
          entry="research.countries.vn.miners:sjc_premium", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Runs the RING GOLD control, which isolates the monopoly's "
                "administrative premium from general Vietnamese household demand"),
    miner("vn_band_censoring", domain_ids=("VN-J",), kind="data_quality",
          entry="research.countries.vn.miners:band_censoring", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Refuses any Vietnamese return-tail statistic and substitutes "
                "the ceiling and floor counts; uses the three-board band difference as the "
                "control"),
    miner("vn_expiry_thursday", domain_ids=("VN-K",), kind="calendar",
          entry="research.countries.vn.miners:expiry_thursday", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Supplies the third-Thursday leg of the department's "
                "four-rule regional expiry identification"),
    miner("vn_tet_than_tai", domain_ids=("VN-L",), kind="calendar",
          entry="research.countries.vn.miners:tet_than_tai", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Separates the closure from the physical gold demand using "
                "Than Tai day, which is a TRADING day ten days after Tet"),
    miner("vn_room_aware_index", domain_ids=("VN-M",), kind="flow",
          entry="research.countries.vn.miners:room_aware_index", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Joins room utilisation to index review dates so that a "
                "reclassification claim is made security by security, and uses at-room "
                "securities as the placebo"),
    miner("vn_tariff_document_feed", domain_ids=("VN-N",), kind="event",
          entry="research.countries.vn.miners:tariff_document_feed", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. A document feed rather than a calendar, for the same reason "
                "vn_credit_quota_events is: nothing here is scheduled"),
)

# --------------------------------------------------------------------------- transmission seeds
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("VN-E01", source="Vietnamese robusta farmer holding, read through the FOB differential",
         mechanism="farmers hold beans when prices rise, so short-run supply elasticity is "
                   "PERVERSE and a rally tightens rather than loosens near-term availability",
         targets=("COFROB",), sign="+", horizon="1 to 3 months",
         lag="0 on the daily differential; 10 days on the twice-monthly customs volume",
         control="arabica on the same dates, where producer behaviour is Brazilian and entirely "
                 "different; plus a price-versus-volume decomposition, since the claim predicts "
                 "volumes FALL as prices rise",
         notes="FALSIFIER: a season in which rising prices coincide with accelerating farmer "
               "selling -- a widening negative differential and rising customs volumes. THE "
               "PACK'S SHARPEST COMMODITY EDGE, and directly measurable in free data"),
    edge("VN-E02", source="Vietnamese coffee export volumes, twice monthly",
         mechanism="about two fifths of world robusta leaves through a customs series published "
                   "every fortnight, which is faster than any other major origin publishes",
         targets=("COFROB", "COFARA"), sign="-", horizon="0 to 6 weeks", lag="10 days",
         control="Brazilian and Indonesian robusta shipments on the same dates, and European "
                 "certified stocks, which absorb the flow",
         notes="FALSIFIER: no COFROB response to a large deviation in the fortnightly volume "
               "against its seasonal norm"),
    edge("VN-E03", source="Vietnamese cotton and yarn import volumes",
         mechanism="a top-three world cotton IMPORTER whose demand is driven by a garment order "
                   "book visible months ahead -- the one commodity where Vietnam is the marginal "
                   "buyer rather than the marginal seller",
         targets=("COTTON",), sign="+", horizon="1 to 3 months", lag="10 days",
         control="Bangladeshi and Indian cotton imports on the same dates, the competing buyers "
                 "sharing the world demand factor without the Vietnamese order book",
         notes="FALSIFIER: no incremental content once Bangladeshi and Indian imports are in the "
               "model. NOTE the sign is reversed from every other commodity edge in this pack"),
    edge("VN-E04", source="a Philippine rice import suspension or tariff change",
         mechanism="the Philippines is Vietnam's largest rice customer, so a Philippine demand "
                   "decision is a Vietnamese supply-glut or squeeze event",
         targets=("WHEAT", "CORN"), sign="-", horizon="1 to 3 months",
         lag="0 at the Philippine order; weekly on the Vietnamese export quote",
         control="Thai quotes on the same dates, the other residual supplier; and wheat and corn "
                 "as the non-rice grain control",
         notes="FALSIFIER: a Philippine import suspension with no fall in the Vietnamese quote "
               "within a month. VN-H and PH-E are two ends of one trade and must be tested "
               "jointly"),
    edge("VN-E05", source="SBV direct gold selling and the SJC premium",
         mechanism="a state monopoly selling gold directly into a domestic market compresses an "
                   "administrative premium, and the licensed import channel is the only legal "
                   "source of new metal",
         targets=("XAUUSD",), sign="+", horizon="1 to 6 months",
         lag="0 at the announcement; intraday on the SJC price",
         control="RING GOLD (vang nhan), which was not covered by the monopoly and therefore "
                 "traded at a different premium -- a within-country control that isolates the "
                 "monopoly from general Vietnamese demand; plus the Indian and Thai premiums",
         notes="FALSIFIER: large SBV gold sales with no compression in the SJC premium. The ring "
               "gold control is unique to Vietnam and is the reason this edge is testable at all"),
    edge("VN-E06", source="Ngay via Than Tai, the God of Wealth day",
         mechanism="a single dated day of concentrated, price-insensitive household gold buying "
                   "strong enough to produce queues, ten days after Tet",
         targets=("XAUUSD",), sign="+", horizon="the week around the day", lag="0",
         control="the day itself is a TRADING day, so the closure and the demand separate "
                 "cleanly; plus the same Gregorian week in years when Tet fell elsewhere",
         notes="FALSIFIER: a Than Tai day with no widening of the SJC buy-sell spread and no "
               "reported queueing. 2026-02-26 is the date and it is derived from the Tet date"),
    edge("VN-E07", source="the SBV central rate and its distance from the band edge",
         mechanism="a crawling peg with a printed anchor: the central rate's drift is policy and "
                   "the distance of bank quotes from the upper edge is depreciation pressure",
         targets=("USDCNH", "USDTHB"), sign="+", horizon="5 to 20 sessions", lag="0",
         control="USDCNH residualised out first, since it is also basket-managed with a daily "
                 "published fix and is the closest analogue; and pinned periods EXCLUDED as "
                 "censored observations",
         notes="FALSIFIER: no residual information in the central rate's drift once the yuan is "
               "controlled for, which would mean Vietnam is simply tracking China"),
    edge("VN-E08", source="a credit growth quota loosening",
         mechanism="a quantity instrument with no price: a quota revision releases lending "
                   "capacity directly and is among the most reliable domestic equity catalysts "
                   "there is",
         targets=("HK50", "CHINAH"), sign="+", horizon="1 to 2 quarters",
         lag="0 at the document; monthly on system credit growth",
         control="interest rate changes over the same period, which must carry LESS information "
                 "if the quantity instrument is the real lever -- a direct test of which matters",
         notes="FALSIFIER: rate changes carrying more information than quota changes, which would "
               "invert this pack's reading of Vietnamese monetary policy"),
    edge("VN-E09", source="a US tariff or transshipment decision affecting Vietnam",
         mechanism="a third of exports go to the United States and the inputs come from China, so "
                   "a transshipment rule is a Chinese supply-chain event expressed through "
                   "Vietnamese assembly",
         targets=("NAS100", "US500", "USDCNH"), sign="-", horizon="1 to 3 quarters",
         lag="0 at the announcement; 10 days on customs volumes",
         control="Mexican and Indian exposure to the same announcements, the competing relocation "
                 "destinations; and Chinese exports of the same categories",
         notes="FALSIFIER: a tariff change above ten percentage points with no effect on "
               "Vietnamese export volumes over two quarters. The largest unscheduled risk here"),
    edge("VN-E10", source="Vietnamese electronics export volumes, twice monthly",
         mechanism="assembly for US technology demand, published faster than any comparable "
                   "origin, which makes it an early read on the same cycle Korea and Taiwan "
                   "report later",
         targets=("NAS100", "US500"), sign="+", horizon="1 to 2 quarters", lag="10 days",
         control="Korean 20-day exports and Taiwanese export orders on the same dates, which must "
                 "absorb the signal if Vietnam carries none of its own",
         notes="FALSIFIER: no incremental content once Korea and Taiwan are in the model -- the "
               "likely outcome, and the twice-monthly speed is the only reason to test it"),
    edge("VN-E11", source="HOSE ceiling and floor counts",
         mechanism="the uncensored breadth observable in a market whose return distribution is "
                   "truncated by rule; a floor-count spike is a margin cascade in progress",
         targets=("HK50", "CHINAH"), sign="-", horizon="1 to 5 sessions", lag="0 at the close",
         control="the same statistic on HNX and UPCoM, where the bands are 10% and 15% -- a "
                 "within-country natural experiment in censoring",
         notes="FALSIFIER: the return tails carrying more information than the counts, which "
               "would mean the band does not bind and the whole censoring argument is wrong"),
    edge("VN-E12", source="a FTSE Russell or MSCI classification review for Vietnam",
         mechanism="index inclusion money arrives at securities that have room to take it and "
                   "is BLOCKED at those that do not, so the flow is a security-level question",
         targets=("HK50", "CHINAH"), sign="+", horizon="the review and the implementation window",
         lag="0 -- review dates are published years ahead",
         control="securities already at their foreign ownership room, which CANNOT receive the "
                 "flow -- the cleanest placebo an index study ever gets; plus the Chinese and "
                 "Indian inclusions as the mechanism analogue",
         notes="FALSIFIER: inflows into securities already at their room, which is impossible and "
               "whose apparent occurrence would mean the room data is wrong"),
    edge("VN-E13", source="the VN30 futures third-Thursday expiry",
         mechanism="settlement on the last-30-minute average including the ATC concentrates "
                   "hedging into one auction under a band that can prevent the cash index moving",
         targets=("HK50", "CHINAH"), sign="0", horizon="the expiry session", lag="0",
         control="the third FRIDAY of the same months, the rule every other venue uses; plus "
                 "non-expiry Thursdays and the other three expiry calendars in this department",
         notes="FALSIFIER: an effect appearing on the third Friday too, which would make it a "
               "monthly artefact. Unsigned: the claim is about variance and basis, not direction"),
    edge("VN-E14", source="the Tet closure block and the pre-Tet cash surge",
         mechanism="the longest closure in Asia after Lebaran, set by government notification "
                   "rather than by rule, coinciding with Chinese New Year so the whole region "
                   "shuts together",
         targets=("USDCNH", "HK50", "XAUUSD"), sign="0",
         horizon="the block and the two sessions after",
         lag="0 -- the block is announced months ahead",
         control="Chinese New Year in markets that do NOT take a nine-day block, which separates "
                 "the Vietnamese closure LENGTH from the shared lunar date",
         notes="FALSIFIER: no difference between Vietnam's longer block and its neighbours' "
               "shorter ones. Tet Binh Ngo begins 2026-02-17. Unsigned: a liquidity claim, "
               "measured in volume as well as price"),
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("VN-R1", start="2011-01-01", end="2015-12-31",
        label="the step-devaluation peg",
        what_changed="the SBV held a fixed rate and devalued in occasional steps, with no "
                     "published central rate and no daily anchor",
        invalidates="the currency's variance is concentrated in a handful of devaluation days, so "
                    "a volatility or mean-reversion statistic from this era describes a different "
                    "object entirely from the post-2016 crawl",
        notes="Decree 24 of 2012 created the SJC gold monopoly during this era"),
    era("VN-R2", start="2016-01-04", end="2022-10-16",
        label="the central rate with a plus or minus 3% band",
        what_changed="a daily published central rate and a 3% band replaced the step peg; the US "
                     "Treasury named Vietnam a currency manipulator in 2020 and then removed the "
                     "designation",
        invalidates="a band-position statistic from this era uses a band half the current width, "
                    "so the distance-to-edge variable is not comparable across October 2022",
        notes="the VN30 futures contract launched in August 2017, so there is no Vietnamese "
              "derivatives history before then"),
    era("VN-R3", start="2022-10-17", end="2024-06-02",
        label="the wider band, the bond-market crisis and the peak gold premium",
        what_changed="the band was widened to plus or minus 5%, the corporate bond and property "
                     "sector seized, and the SJC gold premium reached its highest levels on "
                     "record with the monopoly still in force",
        invalidates="a domestic credit or equity model fitted here is fitted on a bond-market "
                    "crisis; the gold premium reached levels that the subsequent regime makes "
                    "unrepeatable",
        notes="the intervention selling price became a visible hard ceiling during 2024's "
              "depreciation episode"),
    era("VN-R4", start="2024-06-03", end="2025-08-31",
        label="direct state gold selling and the prefunding reform",
        what_changed="the SBV began selling gold directly through four state banks and SJC from "
                     "3 June 2024, compressing the premium; the non-prefunding mechanism for "
                     "foreign investors arrived in late 2024 and unlocked the FTSE Russell "
                     "reclassification path",
        invalidates="the SJC premium series has an administrative STEP at 3 June 2024, and "
                    "foreign participation in the equity market has a structural break in late "
                    "2024 -- neither is a market event and both will be mis-read as one",
        notes="two separate structural breaks, in two different markets, inside fifteen months"),
    era("VN-R5", start="2025-09-01", end=None,
        label="the liberalised gold regime and the tariff settlement",
        what_changed="the 2025 decree ended the SJC monopoly and admitted licensed producers, "
                     "while the US tariff negotiations settled a rate and left the transshipment "
                     "question open",
        invalidates="the gold premium's ADMINISTRATIVE component is being removed, so VN-I must "
                    "be re-fitted inside this era and the pre-2025 premium is a control rather "
                    "than training data",
        notes="the current regime and what a live candidate is actually trading"),
)

# --------------------------------------------------------------------------- assembly
MISSION = (
    "mine Vietnam to exhaustion as a TRANSMISSION-ONLY country with an unusually informative "
    "domestic record: a crawling peg whose anchor is printed every morning and whose basket is "
    "not, a robusta market where farmer holding makes short-run supply elasticity perverse, a "
    "gold bar whose premium was an administrative variable until 2025, and an equity market "
    "censored by a price band whose uncensored observable is the ceiling and floor count")
NOTES = (
    "NO VIETNAMESE INSTRUMENT IS EXECUTABLE. USDVND, the VN-Index, the VN30 future, the SJC bar, "
    "the central rate and Vietnamese government bonds are all named in this module's "
    "TRANSMISSION_TARGETS. COFROB and COTTON carry the commodity half of the pack directly. This "
    "central bank publishes NO meeting calendar -- CENTRAL_BANK['dates'] is deliberately empty -- "
    "so every Vietnam event study must be driven by the sbv.gov.vn and vanban.chinhphu.vn "
    "document feed rather than by a date list.")


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
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES, "datasets": DATASETS,
        "actors": ACTORS, "domains": DOMAINS, "custom_miners": CUSTOM_MINERS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS,
        "absent_source_layers": ABSENT_SOURCE_LAYERS,
        "mission": MISSION, "notes": NOTES,
    }


def pack() -> Any:
    """Vietnam's pack: `CountryPack` when the framework has landed, else the same fields as a
    dict."""
    return build_pack(**fields())
