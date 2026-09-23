"""THAILAND: the currency that trades gold, a tourism current account, and a royal calendar.

THE ONE MECHANISM THAT MAKES THIS PACK WORTH MORE THAN THE REST OF ITS REGION, AND IT IS FULLY
EXECUTABLE ON BOTH LEGS. Thai households hold gold the way other households hold a deposit
account. There are thousands of gold shops, they quote a domestic price in baht per baht-weight
(15.244 grammes of 96.5% gold) many times a day, and the Gold Traders Association publishes those
quotes and the COUNT of daily revisions. When the world price rallies, Thai households SELL into
it -- they are structurally price-elastic suppliers, not buyers -- the shops accumulate metal,
export it, and the dollar proceeds are converted into baht. A gold rally therefore APPRECIATES the
baht through the physical trade balance, and the non-monetary gold line in the customs data is
where it shows up.

That is a causal chain with both ends quotable on this broker: XAUUSD and USDTHB. Nothing else in
this department has that property. India's gold mechanism runs through an unquotable MCX premium;
Vietnam's runs through an unquotable SJC bar; Thailand's runs through two symbols the desk already
trades. TH-C is built on it and the controls are what make it a test rather than a correlation.

THE SECOND MECHANISM: A CURRENT ACCOUNT MADE OF TOURISTS. Tourism receipts were close to a tenth
of GDP before the pandemic, the arrival season peaks from November to February and troughs in May
and June and again in September and October, and the Ministry of Tourism and Sports publishes
WEEKLY arrivals by nationality, free. A services current account that seasonal, published that
often, is a genuinely unusual macro dataset. The collapse in Chinese arrivals through 2025 is the
live structural break in it.

THE THIRD: A ROYAL AND BUDDHIST CALENDAR WITH A SUBSTITUTION LAW. Thailand closes for Songkran in
mid-April -- three statutory days plus substitutions, with the market effectively shut for the
better part of a week -- and for a set of royal birthdays and Buddhist lunar observances that no
weekday rule generates. Songkran 2026 falls on Monday 13 April, so the closure is 13-15 April with
no substitution, which is the cleanest version of it in years.

THE STRUCTURAL CONSTRAINT: BAHT THAT CANNOT LEAVE. The Bank of Thailand caps non-resident baht
account balances and restricts non-resident baht lending. The baht is therefore RESTRICTED but not
prohibited -- unlike the ringgit, which cannot be traded offshore at all -- which is why USDTHB is
on this broker's registry and USDMYR is not, and why an offshore THB non-deliverable forward
settles against the 03:00 UTC regional fixing while an onshore market runs 02:00-11:00 UTC.

WHAT IS EXECUTABLE AND WHAT IS NOT. USDTHB, XAUUSD, XAGUSD, the energy complex and the softs
Thailand exports are all quotable. The SET index, SET50 futures, TFEX's baht-gold contracts, Thai
rice, natural rubber, THOR and the 10-year government bond are not; each is named in
`TRANSMISSION_TARGETS` with the symbols its mechanism reaches. TFEX's gold contract is the
interesting absence: it is literally XAUUSD multiplied by USDTHB in a listed wrapper, which means
the desk can REPLICATE it from two instruments it holds and does not need the contract itself.

THE TRAP. The gold-and-baht correlation is easy to find and easy to mis-attribute: gold and the
baht both respond to the dollar, so a raw correlation is mostly USDX. TH-C's first control is the
dollar factor, its second is a gold-poor comparison currency, and its third is the direction of
the physical trade -- because the mechanism predicts the link is ASYMMETRIC and conditional on
households being net sellers, not a constant beta.

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
CODE = "TH"
NAME = "Thailand"
REGION_COMMAND = "southeast_asia"
CURRENCY = "THB"
FISCAL_YEAR_END = "09-30"  # the Thai fiscal year runs 1 October to 30 September
NATIVE_LANGUAGES: tuple[str, ...] = ("th", "en", "zh")

EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDTHB",                      # the domestic quote; Forex Exotics
    "XAUUSD", "XAGUSD",            # the household gold channel: BOTH legs quotable, uniquely
    "XTIUSD", "XBRUSD",            # a net energy importer of about a million barrels a day
    "SUGAR", "SUGARRAW",           # a top-two sugar exporter whose policy moves the world price
    "CORN", "WHEAT",               # feed imports and the domestic cassava-maize substitution
    "COFROB",                      # a robusta producer, small next to Vietnam but in the complex
    "USDCNH",                      # China is the largest tourist source and export destination
    "USDSGD", "USDIDR",            # the regional complex and the ASEAN factor
    "USDJPY",                      # Japanese FDI, the auto cluster, and Japanese visitors
    "USDKRW",                      # the shared electronics export cycle
    "USDX",                        # the dollar factor every gold-and-baht claim must remove
    "HK50", "JPN225", "US500",     # the risk and electronics-demand channels
    "UST10Y",                      # what foreign holders of Thai bonds trade the spread to
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "domestic gold price in baht per baht-weight",
     "venue": "Gold Traders Association, quoted by the gold shops",
     "why": "the price Thai households actually transact at, revised many times a day; the "
            "REVISION COUNT is itself a published volatility observable",
     "proxies": ("XAUUSD", "USDTHB")},
    {"name": "TFEX gold futures (10 baht-weight and 50 baht-weight)",
     "venue": "Thailand Futures Exchange",
     "why": "a listed contract that is arithmetically XAUUSD multiplied by USDTHB; the desk can "
            "REPLICATE it from two symbols it already holds and does not need the contract",
     "proxies": ("XAUUSD", "USDTHB")},
    {"name": "SET index and SET50 index futures", "venue": "SET and TFEX",
     "why": "foreign net flow in the SET is published daily and free; the index has been a net "
            "foreign-selling market for years, which is itself the fact worth studying",
     "proxies": ("HK50", "USDTHB")},
    {"name": "Thai white and parboiled rice FOB", "venue": "Thai Rice Exporters Association",
     "why": "Thailand is a top-three rice exporter and the FOB quote is published weekly; no "
            "rice contract exists in this universe and rice is not in the vegetable-oil or grain "
            "complexes the broker does quote",
     "proxies": ("WHEAT", "CORN", "USDTHB")},
    {"name": "natural rubber (RSS3 and STR20)", "venue": "Thai rubber markets, SGX TSR20",
     "why": "Thailand is the largest natural rubber exporter; the price is a terms-of-trade input "
            "and a farm-income variable in the south",
     "proxies": ("USDTHB", "USDIDR")},
    {"name": "THOR and the Thai baht interest rate complex",
     "venue": "Bank of Thailand",
     "why": "THBFIX was retired and THOR replaced it; the onshore curve is where a policy "
            "surprise is actually priced",
     "proxies": ("USDTHB", "UST10Y")},
    {"name": "10-year Thai government bond", "venue": "Thai BMA / onshore OTC",
     "why": "the BoT restricted its own short-dated bond issuance to limit speculative inflows, "
            "which shaped the whole foreign holder base",
     "proxies": ("UST10Y", "USDTHB")},
    {"name": "non-resident baht accounts (NRBA and NRBS)",
     "venue": "Bank of Thailand regulation",
     "why": "the balance cap is the structural constraint that makes the baht restricted rather "
            "than free, and it is the reason an offshore NDF exists at all",
     "proxies": ("USDTHB", "USDSGD")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank of Thailand",
    "short": "BoT",
    "committee": "Monetary Policy Committee",
    "policy_instrument": "the one-day bilateral repurchase rate",
    "mandate": "flexible inflation targeting with a headline CPI target band agreed annually with "
               "the Ministry of Finance; the band has been set at 1-3%",
    "decision_rule": "SIX meetings a year, reduced from eight, on dates published a year ahead. "
                     "The decision is announced at 14:00 ICT, which is 07:00 UTC -- the same hour "
                     "as Bank Negara Malaysia and Bank Indonesia, so three Southeast Asian "
                     "central banks can print into one window",
    "announce_local": "14:00 ICT", "announce_utc": "07:00",
    "presser_utc": "07:30",
    "minutes_lag_days": 14,
    "fx_regime": "a managed float with heavy smoothing, plus a structural constraint: the BoT "
                 "caps non-resident baht account balances and restricts non-resident baht "
                 "lending, which limits offshore speculative positioning without prohibiting the "
                 "offshore market outright as Malaysia does",
    "off_cycle": "the MPC has met off-cycle in crises; the BoT's more usual off-calendar action "
                 "is a regulatory change to non-resident baht limits, which arrives without "
                 "notice and is a genuine event class of its own",
    "other_clocks": (
        {"what": "daily average interbank USD/THB exchange rate",
         "when_local": "after the onshore close", "when_utc": "11:00", "reference_lag_days": 0},
        {"what": "THOR publication for the previous business day",
         "when_local": "about 09:00 ICT", "when_utc": "02:00", "reference_lag_days": 1},
        {"what": "weekly international reserves and the forward position",
         "when_local": "Friday", "when_utc": "11:00", "reference_lag_days": 7},
        {"what": "monthly balance of payments and economic conditions report",
         "when_local": "end of month, 14:30 ICT", "when_utc": "07:30", "reference_lag_days": 30},
    ),
    "dates": {
        2024: ("2024-02-07", "2024-04-10", "2024-06-12", "2024-08-21", "2024-10-16",
               "2024-12-18"),
        2025: ("2025-02-26", "2025-04-30", "2025-06-25", "2025-08-13", "2025-10-08",
               "2025-12-17"),
        2026: (),
    },
    "dates_status": "2024 and 2025 follow the BoT's published six-meeting calendars. 2026 is "
                    "UNMEASURED here (L1.28a) and must be read from bot.or.th before any event "
                    "study; the BoT publishes the following year's dates in the fourth quarter",
    "governor_note": "the governorship changed on 1 October 2025. Governor transitions are era "
                     "boundaries in every managed-float currency in this department and Thailand "
                     "is no exception",
}

# --------------------------------------------------------------------------- fixings, settlement
#: ICT is UTC+7 all year with no daylight saving.
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Bank of Thailand daily average interbank exchange rate",
     "administrator": "Bank of Thailand",
     "window_local": "onshore interbank USD/THB transactions through the session",
     "window_utc": "01:00-10:30", "publish_local": "after the onshore close",
     "publish_utc": "11:00",
     "basis": "a weighted average of actual onshore interbank deals",
     "uses": "the official daily rate for accounting, customs and statistical purposes",
     "note": "published AFTER the session it describes, so it is never tradable on its own day "
             "and a cell that uses it same-day has a look-ahead"},
    {"name": "ABS/SFEMC THB spot fixing",
     "administrator": "ABS Benchmarks Administration Co, Singapore",
     "window_local": "concluding about 11:00 SGT, which is 10:00 ICT",
     "window_utc": "02:30-03:00", "publish_local": "about 11:00 SGT", "publish_utc": "03:00",
     "basis": "the regional Asian currency fixing panel",
     "uses": "settlement of offshore THB non-deliverable forwards",
     "note": "the same 03:00 UTC instant at which eight other Asian currencies settle; an "
             "apparent THB fixing effect must be checked against the whole set before it is "
             "called Thai"},
    {"name": "THOR -- Thai Overnight Repurchase Rate",
     "administrator": "Bank of Thailand",
     "window_local": "the previous business day's overnight private repo transactions",
     "window_utc": "previous session", "publish_local": "about 09:00 ICT the next business day",
     "publish_utc": "02:00",
     "basis": "a volume-weighted average of overnight private repurchase transactions",
     "uses": "the successor reference rate after THBFIX was retired; the floating leg of the "
             "onshore swap curve",
     "note": "the THBFIX-to-THOR transition is a break in any Thai rates series that spans it, "
             "and the two are not the same object -- THBFIX embedded an FX swap and THOR does not"},
    {"name": "Gold Traders Association domestic gold price",
     "administrator": "Gold Traders Association of Thailand",
     "window_local": "revised intraday, many times on an active day",
     "window_utc": "intraday", "publish_local": "continuous during shop hours",
     "publish_utc": "02:00-11:00",
     "basis": "the shops' bid and offer for 96.5% gold in baht per baht-weight (15.244 g), plus "
              "a separate 99.99% bar quote",
     "uses": "the price at which Thai households actually transact",
     "note": "TREATED AS A FIXING HERE ON PURPOSE. The association publishes the REVISION COUNT, "
             "which is a free, published, intraday volatility observable of a kind almost no "
             "other retail market provides"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"market": "USD/THB onshore interbank spot", "cycle": "T+2",
     "session_local": "08:00-17:30 ICT", "session_utc": "01:00-10:30",
     "note": "the baht is RESTRICTED, not prohibited: non-resident baht account balances are "
             "capped and non-resident baht lending is limited, which is why an offshore NDF "
             "exists and why USDTHB is quotable here while USDMYR is not"},
    {"market": "SET equities", "cycle": "T+2 since March 2018",
     "session_local": "pre-open randomised 09:55-10:00, morning 10:00-12:30, pre-open "
                      "14:25-14:30, afternoon 14:30-16:30, call market and off-hours to 17:00",
     "session_utc": "03:00-05:30 and 07:30-09:30",
     "note": "the RANDOMISED pre-open is unusual: the auction can begin at any second inside a "
             "five-minute window, which is designed to stop the open itself being gamed and "
             "means an open-price statistic has a built-in timing jitter"},
    {"market": "TFEX derivatives", "cycle": "cash settled",
     "session_local": "morning and afternoon sessions plus a night session to 03:00 ICT",
     "session_utc": "02:45-09:55 and 11:00-20:00",
     "note": "the NIGHT SESSION is the point: TFEX gold futures trade while COMEX is open, which "
             "is how the Thai gold complex stays connected to the world price overnight"},
    {"market": "Thai government bonds", "cycle": "T+2",
     "session_local": "09:00-16:00 ICT", "session_utc": "02:00-09:00",
     "note": "the BoT deliberately restricted its own short-dated bond issuance to limit "
             "speculative inflows, which shaped the foreign holder base toward longer duration"},
    {"market": "gold shops", "cycle": "immediate physical",
     "session_local": "about 09:00-18:00 ICT, six or seven days a week",
     "session_utc": "02:00-11:00",
     "note": "a retail physical market open on Saturdays, which means Thai household gold demand "
             "keeps transacting when every financial market in the country is shut"},
)

# --------------------------------------------------------------------------- exchanges
EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Stock Exchange of Thailand", "code": "SET",
     "hours_local": "10:00-12:30 and 14:30-16:30 ICT, with randomised pre-open auctions",
     "hours_utc": "03:00-05:30 and 07:30-09:30",
     "expiry_rule": "n/a for cash",
     "settlement": "T+2",
     "rebalance": "SET50 and SET100 reviewed semi-annually, effective in January and July"},
    {"name": "Thailand Futures Exchange -- SET50 index futures", "code": "TFEX-S50",
     "hours_local": "09:45-12:30, 14:15-16:55 and a night session 18:50-03:00 ICT",
     "hours_utc": "02:45-05:30, 07:15-09:55 and 11:50-20:00",
     "expiry_rule": "the LAST BUSINESS DAY of the contract month, which differs from the third "
                    "Friday used elsewhere in the region",
     "settlement": "cash, against an averaged closing value of the SET50 index computed from the "
                   "final minutes of the last trading day",
     "rebalance": "with the SET50"},
    {"name": "Thailand Futures Exchange -- gold futures", "code": "TFEX-GF",
     "hours_local": "day and night sessions, the night session running while COMEX is open",
     "hours_utc": "02:45-09:55 and 11:50-20:00",
     "expiry_rule": "even-numbered contract months, expiring on the last business day",
     "settlement": "cash, against a settlement price derived from the London PM gold price and "
                   "the USD/THB rate",
     "rebalance": "n/a",
     "note": "arithmetically XAUUSD multiplied by USDTHB. The desk holds both legs, so this "
             "contract is REPLICABLE rather than missing -- the only absent instrument in this "
             "department of which that is true"},
)

# --------------------------------------------------------------------------- the holiday rule
_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "New Year's Day",
        "2024-02-26": "Makha Bucha Day (in lieu of Saturday 24 February)",
        "2024-04-08": "Chakri Memorial Day (in lieu of Saturday 6 April)",
        "2024-04-12": "Songkran Festival (additional day)",
        "2024-04-15": "Songkran Festival",
        "2024-04-16": "Songkran Festival (in lieu)",
        "2024-05-01": "National Labour Day",
        "2024-05-06": "Coronation Day (in lieu of Saturday 4 May)",
        "2024-05-22": "Visakha Bucha Day",
        "2024-06-03": "HM Queen Suthida's Birthday",
        "2024-07-22": "Asarnha Bucha Day (in lieu)",
        "2024-07-29": "HM King Vajiralongkorn's Birthday (in lieu of Sunday 28 July)",
        "2024-08-12": "HM Queen Mother Sirikit's Birthday",
        "2024-10-14": "HM King Bhumibol Memorial Day (in lieu of Sunday 13 October)",
        "2024-10-23": "Chulalongkorn Day",
        "2024-12-05": "HM King Bhumibol's Birthday and National Day",
        "2024-12-10": "Constitution Day",
        "2024-12-31": "New Year's Eve",
    },
    2025: {
        "2025-01-01": "New Year's Day",
        "2025-02-12": "Makha Bucha Day",
        "2025-04-07": "Chakri Memorial Day (in lieu of Sunday 6 April)",
        "2025-04-14": "Songkran Festival",
        "2025-04-15": "Songkran Festival",
        "2025-05-01": "National Labour Day",
        "2025-05-05": "Coronation Day (in lieu of Sunday 4 May)",
        "2025-05-12": "Visakha Bucha Day",
        "2025-06-03": "HM Queen Suthida's Birthday",
        "2025-07-10": "Asarnha Bucha Day",
        "2025-07-11": "Khao Phansa Day",
        "2025-07-28": "HM King Vajiralongkorn's Birthday",
        "2025-08-12": "HM Queen Mother Sirikit's Birthday",
        "2025-10-13": "HM King Bhumibol Memorial Day",
        "2025-10-23": "Chulalongkorn Day",
        "2025-12-05": "HM King Bhumibol's Birthday and National Day",
        "2025-12-10": "Constitution Day",
        "2025-12-31": "New Year's Eve",
    },
    2026: {
        "2026-01-01": "New Year's Day",
        "2026-03-03": "Makha Bucha Day",
        "2026-04-06": "Chakri Memorial Day",
        "2026-04-13": "Songkran Festival",
        "2026-04-14": "Songkran Festival",
        "2026-04-15": "Songkran Festival",
        "2026-05-01": "National Labour Day",
        "2026-05-04": "Coronation Day",
        "2026-06-01": "Visakha Bucha Day (in lieu of Sunday 31 May)",
        "2026-06-03": "HM Queen Suthida's Birthday",
        "2026-07-28": "HM King Vajiralongkorn's Birthday",
        "2026-07-29": "Asarnha Bucha Day",
        "2026-07-30": "Khao Phansa Day",
        "2026-08-12": "HM Queen Mother Sirikit's Birthday",
        "2026-10-13": "HM King Bhumibol Memorial Day",
        "2026-10-23": "Chulalongkorn Day",
        "2026-12-07": "HM King Bhumibol's Birthday (in lieu of Saturday 5 December)",
        "2026-12-10": "Constitution Day",
        "2026-12-31": "New Year's Eve",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": "Three layers. FIXED ROYAL AND NATIONAL DATES: 1 January, 6 April (Chakri), 13-15 "
            "April (Songkran), 1 May, 4 May (Coronation), 3 June (HM Queen Suthida), 28 July "
            "(HM the King), 12 August (HM Queen Mother), 13 October (HM King Bhumibol Memorial), "
            "23 October (Chulalongkorn), 5 December (HM King Bhumibol's Birthday and National "
            "Day), 10 December (Constitution Day) and 31 December. BUDDHIST LUNAR OBSERVANCES: "
            "Makha Bucha (the full moon of the third lunar month), Visakha Bucha (the full moon "
            "of the sixth), Asarnha Bucha and Khao Phansa (the full moon of the eighth and the "
            "day after) -- none computable from a Gregorian rule and all tabulated. THE "
            "SUBSTITUTION LAW: a holiday falling on a Saturday or a Sunday is substituted on the "
            "following working day, and Thailand substitutes BOTH weekend days, unlike Singapore "
            "which substitutes only Sunday. Songkran additionally attracts extra government "
            "holidays in some years, which extend the closure beyond the statutory three days. "
            "The cabinet may also declare an ad hoc special holiday to create a long weekend, "
            "usually with a few weeks' notice, and the exchange observes it.",
    "table": _HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED", 2025: "CONFIRMED",
               2026: "PROVISIONAL -- the fixed royal and national dates and the substitution law "
                     "are certain and Songkran 2026 falls on Monday 13 April so the closure is "
                     "13-15 April with no substitution; the Buddhist lunar dates are carried at "
                     "their expected values and any ad hoc cabinet special holiday is by "
                     "definition unknowable in advance"},
    "songkran_note": "Songkran is the single largest closure in the Thai year and it moves "
                     "domestic activity, not just the market: the gold shops stay open, tourism "
                     "peaks domestically, and the offshore NDF keeps trading throughout",
    "regional_note": "Thailand does NOT close for Chinese New Year, which makes it one of the few "
                     "Asian markets open while seven of its neighbours are shut -- a useful "
                     "control condition for any regional liquidity study",
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "SET daily trading by investor type",
     "root": "https://www.set.or.th/en/market/statistics/investor-type",
     "fields": ("foreign investors", "local institutions", "proprietary trading", "local "
                "individuals -- buy, sell and net for each"),
     "frequency": "daily", "publish_utc": "10:00", "lag_days": 0, "licence": "free, public",
     "why": "a four-way daily split published free. The SET has been a net foreign-SELLING "
            "market for years, which is itself the structural fact worth studying rather than a "
            "signal to fade"},
    {"name": "Thai BMA foreign holdings of Thai bonds",
     "root": "https://www.thaibma.or.th/EN/Market/Statistic.aspx",
     "fields": ("non-resident holdings of government bonds", "by tenor bucket"),
     "frequency": "daily and weekly", "publish_utc": "10:00", "lag_days": 1,
     "licence": "free, public",
     "why": "the BoT's restriction of short-dated issuance pushed foreign holders out along the "
            "curve, so the TENOR SPLIT carries the policy's effect and the total does not"},
    {"name": "Bank of Thailand weekly international reserves and forward position",
     "root": "https://www.bot.or.th/en/statistics/",
     "fields": ("gross international reserves", "net forward position"),
     "frequency": "weekly", "publish_utc": "11:00", "lag_days": 7, "licence": "free, public",
     "why": "WEEKLY reserves with the forward book alongside is faster than most of this region, "
            "and the forward line is where the intervention that is not in spot shows up"},
    {"name": "Ministry of Tourism and Sports weekly arrivals",
     "root": "https://www.mots.go.th/news-link.php",
     "fields": ("arrivals by nationality", "cumulative year to date", "receipts estimate"),
     "frequency": "weekly", "publish_utc": "07:00", "lag_days": 5, "licence": "free, public",
     "why": "a WEEKLY, free, official read on a services current account worth close to a tenth "
            "of GDP; the Chinese arrivals line is the live structural break in it"},
    {"name": "Gold Traders Association price and revision count",
     "root": "https://www.goldtraders.or.th/",
     "fields": ("domestic buy and sell price per baht-weight", "the count of daily revisions",
                "the 96.5% and 99.99% quotes"),
     "frequency": "intraday", "publish_utc": "02:00-11:00", "lag_days": 0,
     "licence": "free, public",
     "why": "the price Thai households transact at, and a published intraday revision count that "
            "functions as a free realised-volatility proxy for retail gold activity"},
    {"name": "CFTC Commitments of Traders",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("non-commercial net in gold, crude, sugar, the dollar index",),
     "frequency": "weekly", "publish_utc": "20:30", "lag_days": 3, "licence": "free, public",
     "why": "the external leg of the gold edge. THB is not in the COT, and the gold positioning "
            "line is the speculative counterpart to Thailand's physical flow"},
)

# --------------------------------------------------------------------------- terminology
#: Thai script first. Thai is written without spaces between words and the domestic gold and
#: policy commentary exists in Thai only; a Latin-transliteration search finds essentially nothing.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "TH-A": ("ธนาคารแห่งประเทศไทย", "อัตราดอกเบี้ยนโยบาย", "คณะกรรมการนโยบายการเงิน",
             "นโยบายการเงิน", "เงินเฟ้อ", "กนง.", "policy rate"),
    "TH-B": ("เงินบาท", "อัตราแลกเปลี่ยน", "ค่าเงินบาท", "แทรกแซง", "ทุนสำรองระหว่างประเทศ",
             "บัญชีเงินบาทของผู้มีถิ่นที่อยู่นอกประเทศ", "baht intervention"),
    "TH-C": ("ทองคำ", "ราคาทองคำ", "ร้านทอง", "สมาคมค้าทองคำ", "บาททองคำ", "ทองรูปพรรณ",
             "ขายทอง", "ส่งออกทองคำ", "gold shop"),
    "TH-D": ("ทองคำล่วงหน้า", "สัญญาซื้อขายล่วงหน้า", "TFEX", "ส่วนต่างราคาทอง",
             "gold futures basis"),
    "TH-E": ("นักท่องเที่ยว", "การท่องเที่ยว", "ฤดูกาลท่องเที่ยว", "นักท่องเที่ยวจีน",
             "รายได้จากการท่องเที่ยว", "tourist arrivals"),
    "TH-F": ("ส่งออก", "นำเข้า", "ดุลการค้า", "อิเล็กทรอนิกส์", "ฮาร์ดดิสก์", "ยานยนต์",
             "electronics exports"),
    "TH-G": ("ข้าว", "ยางพารา", "น้ำตาล", "มันสำปะหลัง", "ทุเรียน", "ราคาข้าวส่งออก",
             "agricultural exports"),
    "TH-H": ("ตลาดหลักทรัพย์", "นักลงทุนต่างชาติ", "ซื้อสุทธิ", "ขายสุทธิ", "SET50",
             "วันหมดอายุ", "foreign net selling"),
    "TH-I": ("ตลาดพันธบัตร", "ผลตอบแทนพันธบัตร", "ถือครองโดยต่างชาติ", "bond yield"),
    "TH-J": ("วันหยุด", "สงกรานต์", "วันหยุดยาว", "สภาพคล่อง", "ปิดทำการ", "Songkran"),
    "TH-K": ("มาตรการกระตุ้นเศรษฐกิจ", "งบประมาณ", "เงินโอน", "คนละครึ่ง",
             "fiscal stimulus"),
    "TH-L": ("กองทุนรวมที่ลงทุนในต่างประเทศ", "เงินทุนไหลออก", "การลงทุนต่างประเทศ",
             "outbound fund flows"),
    "TH-M": ("อัตราอ้างอิง", "อัตราแลกเปลี่ยนเฉลี่ยระหว่างธนาคาร", "ตลาดต่างประเทศ",
             "ส่วนต่างในประเทศนอกประเทศ", "เวลาประกาศ", "onshore offshore basis"),
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

    `machine_use_allowed=True` means the terms of the page FORBID automated extraction. Such a
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
    _src("TH-S1", "the Bank of Thailand and the ministries", layer="official",
         roots=("https://www.bot.or.th/en/news-and-media/news.html",
                "https://www.bot.or.th/en/statistics/", "https://www.nesdc.go.th/",
                "https://tradereport.moc.go.th/", "https://www.mots.go.th/news-link.php"),
         languages=("th", "en"), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("มติ กนง อัตราดอกเบี้ยนโยบาย",
                  "ทุนสำรองระหว่างประเทศ รายสัปดาห์",
                  "นักท่องเที่ยวรายสัปดาห์",
                  "BOT MPC statement", "weekly international reserves forward position"),
         notes="the MPC statement at 07:00 UTC, WEEKLY reserves with the forward position "
               "alongside, and the ministry of tourism's WEEKLY arrivals -- three unusually fast "
               "official series for this region"),
    _src("TH-S2", "SET, TFEX, the bond association and the gold traders' association",
         layer="institutional",
         roots=("https://www.set.or.th/en/market/statistics/investor-type",
                "https://www.tfex.co.th/en/products/", "https://www.thaibma.or.th/EN/",
                "https://www.goldtraders.or.th/", "https://www.imf.org/en/Countries/THA"),
         languages=("th", "en"), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("สมาคมค้าทองคำ ราคา",
                  "นักลงทุนต่างชาติ ซื้อสุทธิ",
                  "TFEX gold futures specification", "SET50 futures final settlement"),
         notes="the Gold Traders Association is an INSTITUTIONAL source of a retail price: it "
               "publishes the shop quote and the revision count, which is the observable TH-C is "
               "built on and which no exchange anywhere else provides"),
    _src("TH-S3", "Thai and multilateral academic work", layer="academic",
         roots=("https://www.pier.or.th/en/", "https://www.econ.chula.ac.th/en/research/",
                "https://www.imf.org/en/Publications/WP", "https://www.adb.org/publications"),
         languages=("th", "en"), licence="free, public", access_label="PUBLIC",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("งานวิจัย ค่าเงินบาท ทองคำ",
                  "gold trade baht exchange rate Thailand study",
                  "household debt monetary transmission Thailand"),
         notes="PIER is the Bank of Thailand's own research institute and has published on the "
               "gold-and-baht relationship and on the household debt constraint that blunts "
               "monetary transmission -- both of which this pack asserts and neither of which it "
               "should assert without a prior"),
    _src("TH-S4", "the gold dealers and the practitioner community", layer="practitioner",
         roots=("https://www.ylgbullion.co.th/", "https://www.huasengheng.com/",
                "https://www.mtsgoldfutures.co.th/", "https://www.settrade.com/"),
         languages=("th",), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("บทวิเคราะห์ทองคำ วันนี้",
                  "ขายทองออก",
                  "ส่วนต่างราคาทอง",
                  "gold futures basis Thailand"),
         notes="the two largest dealers publish daily commentary in Thai describing which "
               "direction the public is trading -- 'khai thong' (selling gold) versus buying -- "
               "which is the SIGN variable TH-C conditions on and which the customs data only "
               "confirms a month later"),
    _src("TH-S5", "Thai retail communities", layer="retail_ecology",
         roots=("https://pantip.com/forum/sinthorn", "https://www.facebook.com/groups/",
                "https://www.reddit.com/r/Thailand/"),
         languages=("th",), licence="public web; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("ต่อแถวซื้อทอง",
                  "ขายทองเก็บได้กำไร",
                  "ติดดอยหุ้น", "margin call หุ้นไทย"),
         notes="Pantip's Sinthorn board is one of the few places household gold-selling behaviour "
               "is described in the FIRST PERSON -- queue reports at the shops, 'khai thong kep "
               "dai kamrai' (did selling gold make a profit) -- which is direct evidence for the "
               "TH-C mechanism even though every individual post is unreliable"),
    _src("TH-S6", "Thai trading and investment apps", layer="app_ecosystem",
         roots=("https://www.settrade.com/th/home", "https://www.finnomena.com/",
                "https://dime.co.th/", "https://www.liberator.co.th/"),
         languages=("th",), licence="public web; platform terms vary",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("สตรีมมิ่ง พอร์ต",
                  "ค่าธรรมเนียมหุ้น",
                  "กองทุนรวม FIF"),
         notes="Settrade's Streaming platform is the rail almost all Thai retail equity and TFEX "
               "order flow runs through, and the FIF fund platforms are the retail end of the "
               "outbound flow TH-L is about. ACCESS_UNCLEAR: product pages public, data terms not "
               "uniformly stated"),
    _src("TH-S7", "Thai financial press", layer="media",
         roots=("https://www.bangkokbiznews.com/finance", "https://www.prachachat.net/finance",
                "https://www.thansettakij.com/", "https://www.set.or.th/en/news"),
         languages=("th",), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("เงินบาทแข็งค่า",
                  "นักท่องเที่ยวจีนลดลง",
                  "ส่งออกทองคำ"),
         notes="the domestic reading of a BoT decision, a gold record or a tourism collapse "
               "appears here in Thai first; the gold-export story in particular is a Thai "
               "business-press subject and almost never an English wire one"),
    _src("TH-S8", "the Royal Gazette and the historical archives", layer="archive",
         roots=("https://ratchakitcha.soc.go.th/", "https://www.bot.or.th/en/statistics/",
                "https://web.archive.org/web/*/bot.or.th*"),
         languages=("th",), licence="free, public", access_label="PUBLIC_ARCHIVE",
         credibility="AUTHORITATIVE", predictive_state="NOT_PREDICTIVE",
         queries=("ราชกิจจานุเบกษา วันหยุด",
                  "ประกาศธนาคารแห่งประเทศไทย",
                  "cabinet resolution special holiday"),
         notes="THE ONLY WAY TO DATE A THAI CLOSURE CORRECTLY. Ad hoc cabinet special holidays "
               "and the substitution rules are published in the Royal Gazette and appear in no "
               "annual calendar issued beforehand. NOT_PREDICTIVE: an archive dates"),
    _src("TH-S9", "the physical economy: gold counters, crops, power and ports",
         layer="physical_economy",
         roots=("https://www.goldtraders.or.th/", "http://www.thairiceexporters.or.th/",
                "http://www.sugarzone.in.th/", "https://www.tmd.go.th/",
                "https://www.egat.co.th/home/en/statistics/"),
         languages=("th", "en"), licence="free, public", access_label="PUBLIC",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("ราคาข้าวส่งออก รายสัปดาห์",
                  "ปริมาณอ้อยเข้าหีบ",
                  "พยากรณ์อากาศ ภาคอีสาน"),
         notes="THE PHYSICAL LAYER IS THIS PACK'S CENTRE OF GRAVITY. The gold counters publish "
               "the price households transact at; the rice exporters publish a weekly FOB quote; "
               "the cane board publishes crush progress. All free, all in Thai, and all upstream "
               "of instruments the desk can actually trade"),
    _src("TH-S10", "the source graph: registries and mirrors", layer="source_graph",
         roots=("https://data.go.th/", "https://data.worldbank.org/country/thailand",
                "https://comtradeplus.un.org/", "https://www.imf.org/en/Countries/THA"),
         languages=("th", "en"), licence="open data", access_label="OPEN_DATA",
         credibility="RELIABLE", predictive_state="NOT_PREDICTIVE",
         queries=("Comtrade Thailand non-monetary gold", "data.go.th catalogue",
                  "World Bank Thailand tourism receipts"),
         notes="THE META LAYER, and Thailand is the case where it earns its keep: the "
               "non-monetary gold line is reported by Thai customs AND mirrored by the importing "
               "countries' customs, so a discrepancy between the two is direct evidence about "
               "the physical flow TH-C depends on"),
    _src("TH-S11", "licensed bullion and commodity assessments", layer="institutional",
         roots=("https://www.lbma.org.uk/prices-and-data",
                "https://www.spglobal.com/commodityinsights/en/our-methodology/"),
         languages=("en",), licence="methodology free; assessments licensed",
         access_label="LICENSED", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         machine_use_allowed=True,
         notes="REGISTERED AND NOT SCRAPED. The TFEX gold contract settles against a licensed "
               "London price whose terms forbid automated extraction. This costs the pack "
               "nothing, because TH-D replicates the contract from XAUUSD and USDTHB, which the "
               "desk holds -- the row exists so that substitution is a recorded decision"),
    _src("TH-S12", "rumour channels and unverified chatter", layer="retail_ecology",
         roots=("https://www.facebook.com/groups/", "https://t.me/s/",
                "https://www.youtube.com/results?search_query="),
         languages=("th",), licence="public social; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("ทองขึ้นแน่นอน",
                  "หุ้นเด็ด พรุ่งนี้",
                  "ข่าวลือ ธปท. ลดดอกเบี้ย"),
         notes="FRINGE AND KEPT. Thai gold-price prediction channels and rate-cut rumours are "
               "mostly wrong, and gold rumour in particular CAUSES queue behaviour at the shops, "
               "which means the rumour is part of the mechanism rather than merely noise about "
               "it. Low weight, FRINGE label attached, never promoted, never deleted"),
)

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("Gold Traders Association domestic gold price and revision count",
            source="Gold Traders Association of Thailand", coverage="2010-",
            frequency="intraday", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2010-01-01", pit_feasible=True,
            assets=("XAUUSD", "USDTHB"), mechanism_families=("physical_demand", "retail_flow"),
            how_to_fetch="the association's site publishes each revision with a timestamp; the "
                         "COUNT of revisions in a day is a free realised-volatility proxy for "
                         "retail gold activity and is the part most users throw away"),
    dataset("Thai non-monetary gold exports and imports",
            source="Thai Customs / Ministry of Commerce", coverage="2000-", frequency="monthly",
            publication_lag_days=25, revisions="routine", licence="free, public",
            history_from="2000-01-01", pit_feasible=True, assets=("XAUUSD", "USDTHB"),
            mechanism_families=("physical_flow", "current_account"),
            how_to_fetch="the customs commodity tables; the non-monetary gold line is the "
                         "DIRECT evidence for the household-selling mechanism and it swings the "
                         "monthly trade balance on its own in a strong gold month"),
    dataset("Ministry of Tourism weekly arrivals by nationality",
            source="Ministry of Tourism and Sports", coverage="2010-", frequency="weekly",
            publication_lag_days=5, revisions="monthly true-up", licence="free, public",
            history_from="2010-01-01", pit_feasible=True, assets=("USDTHB", "USDCNH"),
            mechanism_families=("services_flow", "seasonality"),
            how_to_fetch="the ministry's news-link releases; the Chinese line is the live "
                         "structural break and must be modelled separately from the rest"),
    dataset("Bank of Thailand weekly reserves and net forward position",
            source="Bank of Thailand", coverage="1997-", frequency="weekly",
            publication_lag_days=7, revisions="rare", licence="free, public",
            history_from="1997-01-01", pit_feasible=True, assets=("USDTHB", "USDX"),
            mechanism_families=("intervention", "reserve_adequacy"),
            how_to_fetch="the BoT statistics portal; the FORWARD line is where the intervention "
                         "that does not appear in spot reserves is recorded"),
    dataset("SET daily trading by investor type", source="Stock Exchange of Thailand",
            coverage="2000-", frequency="daily", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2000-01-01", pit_feasible=True,
            assets=("HK50", "USDTHB"), mechanism_families=("flows", "risk_appetite"),
            how_to_fetch="the investor-type statistics page; published at the close, so it is "
                         "knowable for the next session only"),
    dataset("Thai monthly merchandise trade", source="Ministry of Commerce", coverage="1995-",
            frequency="monthly", publication_lag_days=22, revisions="routine",
            licence="free, public", history_from="1995-01-01", pit_feasible=True,
            assets=("USDTHB", "XAUUSD", "US500"),
            mechanism_families=("trade_cycle", "terms_of_trade"),
            how_to_fetch="the trade report portal; the gold line must be stripped out before the "
                         "underlying trade balance can be read, because it is large enough to "
                         "dominate the headline in a strong gold month"),
    dataset("Thai CPI", source="Ministry of Commerce", coverage="2000-", frequency="monthly",
            publication_lag_days=5, revisions="rare", licence="free, public",
            history_from="2000-01-01", pit_feasible=True, assets=("USDTHB", "UST10Y"),
            mechanism_families=("inflation", "policy_reaction"),
            how_to_fetch="published in the first week of the month -- a five-day lag, among the "
                         "fastest in the region; Thailand spent much of 2024-25 in outright "
                         "DEFLATION, which is a regime a reaction function fitted elsewhere has "
                         "never seen"),
    dataset("Bank of Thailand MPC statements and minutes", source="Bank of Thailand",
            coverage="2000-", frequency="six a year", publication_lag_days=0,
            revisions="none; minutes 14 days later", licence="free, public",
            history_from="2000-01-01", pit_feasible=True, assets=("USDTHB", "UST10Y"),
            mechanism_families=("policy_event", "tone"),
            how_to_fetch="the news releases at 07:00 UTC; note the reduction from eight meetings "
                         "a year to six, which changes the event count per year"),
    dataset("Thai rice export FOB quotes", source="Thai Rice Exporters Association",
            coverage="2000-", frequency="weekly", publication_lag_days=0, revisions="none",
            licence="free, public", history_from="2000-01-01", pit_feasible=True,
            assets=("WHEAT", "CORN", "USDTHB"),
            mechanism_families=("agricultural_exports", "food_prices"),
            how_to_fetch="the association publishes white and parboiled quotes weekly; there is "
                         "no rice contract in this universe, so the quote is a transmission input "
                         "and never a target"),
    dataset("Thai sugar production and export data",
            source="Office of the Cane and Sugar Board", coverage="2000-",
            frequency="weekly in crush season, monthly otherwise", publication_lag_days=7,
            revisions="routine", licence="free, public", history_from="2000-01-01",
            pit_feasible=True, assets=("SUGAR", "SUGARRAW"),
            mechanism_families=("supply", "commodity_policy"),
            how_to_fetch="the board's crush-season reports; Thailand is a top-two exporter and "
                         "its crush progress is the second-largest supply signal in the world "
                         "sugar balance after Brazil's"),
    dataset("THOR daily", source="Bank of Thailand", coverage="2020-", frequency="daily",
            publication_lag_days=1, revisions="none", licence="free, public",
            history_from="2020-04-01", pit_feasible=True, assets=("USDTHB",),
            mechanism_families=("funding", "fx_swap_basis"),
            how_to_fetch="published about 09:00 ICT for the previous business day; the "
                         "THBFIX-to-THOR transition means a longer history is two different "
                         "objects spliced together and must not be treated as one series"),
    dataset("Thai BMA foreign bond holdings", source="Thai Bond Market Association",
            coverage="2005-", frequency="daily and weekly", publication_lag_days=1,
            revisions="rare", licence="free, public", history_from="2005-01-01",
            pit_feasible=True, assets=("UST10Y", "USDTHB"),
            mechanism_families=("flows", "positioning"),
            how_to_fetch="the statistics pages; take the TENOR SPLIT, because the BoT's "
                         "restriction of short-dated issuance is visible there and invisible in "
                         "the total"),
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor(
        "Thai gold shops and the Gold Traders Association",
        holds="physical inventory of 96.5% gold ornament and 99.99% bar, quoted in baht per "
              "baht-weight and revised many times a day",
        forced_to=("post a two-way price continuously, so they absorb whichever side the public "
                   "brings them",
                   "export accumulated metal when households are net sellers, because domestic "
                   "inventory financing is expensive",
                   "import when households are net buyers"),
        when="shop hours, roughly 02:00-11:00 UTC, six or seven days a week -- including "
             "Saturdays, when every financial market in Thailand is shut",
        information=("their own inventory and two-way flow, which is the physical order book",
                     "the world price and USDTHB in real time",
                     "the association's published quote revisions"),
        constraints=("inventory financing cost",
                     "import and export logistics and the refiner relationships",
                     "the 96.5% purity convention, which is Thai and not international, so "
                     "exported metal must be re-refined"),
        instruments=("XAUUSD", "USDTHB"),
        counterparties=("Thai households", "international bullion banks and refiners",
                        "TFEX participants hedging the same exposure"),
        observables=("the association's published price and REVISION COUNT",
                     "monthly non-monetary gold exports in the customs data",
                     "the domestic price against XAUUSD times USDTHB"),
        impact="the transmission point of the whole pack: household selling becomes a physical "
               "export becomes a dollar inflow becomes baht appreciation, and every step is "
               "observable in a free public series",
        persistence="structural and centuries old; the SIZE grew with household wealth and the "
                    "mechanism was strong enough that the central bank has commented on it "
                    "publicly",
        falsifier="a year in which large net household gold selling produces no rise in "
                  "non-monetary gold exports would break the chain at its first link"),
    actor(
        "Thai households as gold savers",
        holds="a very large aggregate stock of gold ornament and bar held as savings rather than "
              "as jewellery consumption",
        forced_to=("sell into rallies, because the holding is a savings buffer and a high price "
                   "is when it is worth realising",
                   "buy back in weakness, which makes them stabilising and not trend-following"),
        when="continuously, with visible surges on days the domestic price sets a record",
        information=("the shop window price, which is the only price most of them see",
                     "domestic media coverage of gold records, which itself drives queues"),
        constraints=("the 96.5% convention and the ornament premium",
                     "no capital gains tax on the transaction",
                     "physical proximity to a shop, which is universal in Thai towns"),
        instruments=("XAUUSD", "USDTHB"),
        counterparties=("the gold shops",),
        observables=("shop queue reporting in the Thai press",
                     "the revision count as an activity proxy",
                     "the direction of the non-monetary gold trade line"),
        impact="makes Thai physical gold supply POSITIVELY price-elastic, which is the opposite "
               "of the Indian festival-demand pattern and is why the two countries' gold "
               "mechanisms have opposite signs into the currency",
        persistence="deeply structural; the behaviour survived the pandemic and the 2024-25 "
                    "record-price period",
        falsifier="a sustained gold rally during which Thai households are net BUYERS, which "
                  "would invert the mechanism and require the sign of TH-C to be reversed"),
    actor(
        "Bank of Thailand's foreign exchange desk",
        holds="gross reserves above USD 200bn plus a substantial net forward position",
        forced_to=("smooth a currency whose current account swings with tourism and with the "
                   "gold trade",
                   "publish weekly reserves AND the forward book, so its footprint is more "
                   "visible than most of its peers'",
                   "manage a currency that appreciates on gold rallies for physical reasons "
                   "unrelated to Thai fundamentals"),
        when="the 01:00-10:30 UTC onshore session",
        information=("onshore interbank flow", "the customs gold line before publication",
                     "non-resident baht account balances it caps"),
        constraints=("a 1-3% headline inflation target band agreed with the finance ministry",
                     "the non-resident baht account caps, which are its structural tool",
                     "US Treasury currency report scrutiny, which Thailand has attracted"),
        instruments=("USDTHB", "XAUUSD", "USDCNH"),
        counterparties=("domestic and foreign banks onshore", "offshore NDF market makers"),
        observables=("weekly reserves and the forward position",
                     "changes to non-resident baht limits, which arrive without notice",
                     "realised USDTHB volatility"),
        impact="dampens the baht's response to the gold and tourism flows, which means the "
               "OBSERVED elasticity is a joint measurement of the flow and of the BoT's "
               "willingness to absorb it -- and that willingness changes with the governor",
        persistence="structural; the intensity is governor-dependent and the governorship changed "
                    "on 1 October 2025",
        falsifier="a quarter of large gold-driven inflows with no reserve accumulation and full "
                  "pass-through into the currency would say the desk has stepped back"),
    actor(
        "The Bank of Thailand Monetary Policy Committee",
        holds="the one-day bilateral repurchase rate",
        forced_to=("target headline inflation in a band agreed annually with the finance "
                   "ministry, which makes the target itself a negotiated variable",
                   "set policy through a long stretch of outright DEFLATION in 2024-25, a regime "
                   "most reaction functions have never had to fit",
                   "print at 07:00 UTC alongside two regional peers"),
        when="six times a year at 14:00 ICT",
        information=("domestic credit and household debt data", "the tourism recovery path"),
        constraints=("a household debt burden among the highest in emerging Asia, which limits "
                     "how much a rate cut can stimulate",
                     "political pressure from a government that has publicly wanted lower rates"),
        instruments=("USDTHB", "UST10Y"),
        counterparties=("domestic banks", "foreign bond holders", "the finance ministry"),
        observables=("the policy rate", "the statement and the minutes fourteen days later",
                     "dissent counts, which have been unusually visible"),
        impact="a policy rate that has been the subject of open disagreement between the central "
               "bank and the government, so the STATEMENT carries institutional information "
               "beyond the rate and a text feature set has something to find",
        persistence="structural; the target band is renegotiated annually",
        falsifier="a year in which the dissent count carries no information about the subsequent "
                  "rate path"),
    actor(
        "Inbound tourists and the tourism industry",
        holds="a services export worth close to a tenth of GDP in a normal year",
        forced_to=("arrive on a seasonal pattern set by northern-hemisphere winter and by school "
                   "holidays",
                   "convert foreign currency into baht on arrival"),
        when="the high season from November to February, a secondary peak in July and August, "
             "and troughs in May, June, September and October",
        information=("published weekly arrival data", "airline capacity"),
        constraints=("visa policy, which Thailand has repeatedly liberalised",
                     "airline seat capacity, the binding constraint in the recovery",
                     "safety perception, which collapsed Chinese arrivals through 2025"),
        instruments=("USDTHB", "USDCNH"),
        counterparties=("hotels and the domestic services economy", "the banking system"),
        observables=("weekly arrivals by nationality", "tourism receipts",
                     "the services balance in the monthly balance of payments"),
        impact="a large, strongly seasonal, weekly-published current account inflow -- which "
               "makes the baht one of the few currencies whose current account has a genuine "
               "high-frequency observable rather than a quarterly one",
        persistence="structural, with a live composition break: the Chinese share fell hard "
                    "through 2025 and was not fully replaced",
        falsifier="a high season with arrivals at trend and no measurable seasonal in the "
                  "services balance or in USDTHB"),
    actor(
        "Thai electronics and hard-disk-drive exporters",
        holds="an export book concentrated in data storage, integrated circuits and electrical "
              "components",
        forced_to=("ship on the customer's schedule", "convert dollar receipts"),
        when="monthly, visible in the trade data on about the 22nd",
        information=("customer order books", "the global data-centre capital spending cycle"),
        constraints=("competition from Vietnamese and Malaysian assembly",
                     "the 2011 flood, which permanently moved some capacity abroad"),
        instruments=("US500", "USDTHB", "USDKRW"),
        counterparties=("US and Chinese buyers", "Japanese parent companies"),
        observables=("the electronics line in the monthly trade data",
                     "the manufacturing production index", "global storage demand"),
        impact="ties Thailand's export cycle to data-centre and storage capital spending, which "
               "is a different part of the technology cycle from Korea's memory exposure and "
               "therefore not redundant with it",
        persistence="structural; the share of exports has been stable for a decade",
        falsifier="a quarter of falling Thai electronics exports with rising global storage "
                  "shipments"),
    actor(
        "Japanese automotive assemblers in Thailand",
        holds="the assembly capacity that made Thailand the region's vehicle manufacturing hub",
        forced_to=("repatriate profits to Japanese parents",
                   "respond to a domestic pickup-truck credit cycle that turned sharply negative",
                   "compete with Chinese electric vehicle entrants selling below their cost base"),
        when="continuous production; repatriation follows the Japanese fiscal year ending in March",
        information=("domestic auto loan approval rates, which collapsed after 2023",
                     "Chinese EV pricing"),
        constraints=("a domestic household debt problem that killed pickup financing",
                     "Chinese competition with state-supported pricing",
                     "Japanese parent-company capital allocation"),
        instruments=("USDTHB", "USDJPY", "JPN225"),
        counterparties=("Thai households buying on credit", "export markets in the region",
                        "Japanese parents"),
        observables=("monthly vehicle production and domestic sales",
                     "auto loan rejection rates", "vehicle export volumes"),
        impact="a large manufacturing sector in structural decline for reasons that are partly "
               "domestic credit and partly Chinese competition, which drags the whole "
               "manufacturing production index and is a genuine reason Thai growth has "
               "underperformed its neighbours",
        persistence="the DECLINE is structural and recent, beginning around 2023; a model fitted "
                    "on the 2010s expects an auto cycle that no longer exists",
        falsifier="a recovery in Thai vehicle production with no recovery in domestic auto credit "
                  "and no retreat by Chinese entrants"),
    actor(
        "Thai rice, rubber, sugar and cassava exporters",
        holds="the export book of a top-three rice exporter, the largest rubber exporter and a "
              "top-two sugar exporter",
        forced_to=("sell at harvest", "compete with Indian and Vietnamese rice policy decisions "
                   "they do not control",
                   "respond to Chinese demand for durian and cassava, which is concentrated and "
                   "politically exposed"),
        when="the rice harvest from November; the sugar crush from December to April; rubber "
             "tapping suppressed in the February-April wintering season",
        information=("weekly FOB quotes published by their own associations",
                     "Indian export policy notifications"),
        constraints=("Indian rice export bans and their relaxations, which reset the world price "
                     "without any Thai action",
                     "weather, above all in the northeast",
                     "government price-support schemes"),
        instruments=("SUGAR", "SUGARRAW", "WHEAT", "CORN", "USDTHB"),
        counterparties=("African and Asian rice importers", "Chinese buyers",
                        "Indian competitors"),
        observables=("weekly FOB rice quotes", "crush progress reports",
                     "monthly agricultural export values"),
        impact="Thailand is the RESIDUAL supplier in rice: when India restricts, Thai prices rise "
               "because Thailand is who buyers turn to, which makes the Thai FOB quote a clean "
               "read on the effect of Indian policy",
        persistence="structural; the residual-supplier role has been stable for two decades",
        falsifier="an Indian rice export restriction with no rise in the Thai FOB quote within "
                  "two weeks"),
    actor(
        "Foreign investors in the Stock Exchange of Thailand",
        holds="a shrinking share of a market they have sold persistently for years",
        forced_to=("rebalance against EM benchmark weights as Thailand's weight falls",
                   "convert on repatriation"),
        when="daily, published at the close",
        information=("the daily four-way investor split", "index provider consultations"),
        constraints=("index weights", "the foreign-ownership limits on individual companies",
                     "a domestic market whose earnings growth has disappointed for a decade"),
        instruments=("HK50", "USDTHB"),
        counterparties=("domestic institutions and retail, who have absorbed the selling",),
        observables=("daily foreign net", "the SET's index weight in regional benchmarks",
                     "the NVDR mechanism's share of turnover"),
        impact="years of persistent net selling means the flow is a STRUCTURAL drift rather than "
               "a cyclical signal, and a cell that treats a negative print as bearish news is "
               "trading the trend's mean",
        persistence="the selling has been persistent enough to be structural rather than "
                    "episodic, which is itself the finding",
        falsifier="a year of sustained net foreign BUYING, which would end the structural "
                  "interpretation and require the domain to be refitted"),
    actor(
        "Thai outbound mutual funds (FIF) and the structural baht seller",
        holds="foreign investment fund allocations sold to Thai savers seeking yield abroad",
        forced_to=("buy foreign assets with baht on a subscription schedule",
                   "hedge or not hedge, which the BoT watches"),
        when="continuous, with surges when domestic yields are unusually low",
        information=("their own subscription book", "domestic versus foreign yield differentials"),
        constraints=("BoT limits on outbound investment, which have been liberalised repeatedly",
                     "investor appetite, which follows past returns"),
        instruments=("USDTHB", "US500"),
        counterparties=("Thai retail savers", "global asset managers"),
        observables=("FIF assets under management", "the portfolio investment line in the balance "
                     "of payments"),
        impact="a structural BAHT SELLER that partially offsets the tourism and gold inflows, "
               "which is why the baht is weaker than its current account alone suggests and why "
               "a current-account-only model over-predicts appreciation",
        persistence="structural and growing with liberalisation",
        falsifier="a period of low domestic yields with no growth in FIF assets"),
    actor(
        "TFEX gold futures participants",
        holds="a listed contract that is arithmetically XAUUSD multiplied by USDTHB",
        forced_to=("arbitrage against the physical shop price and against the world price",
                   "trade the night session, which runs while COMEX is open"),
        when="the day and night sessions, the latter 11:50-20:00 UTC",
        information=("the shop price", "the world price", "USDTHB"),
        constraints=("position limits", "the contract's baht-weight denomination"),
        instruments=("XAUUSD", "USDTHB"),
        counterparties=("gold shops hedging inventory", "retail speculators",
                        "the physical trade"),
        observables=("TFEX gold open interest and volume",
                     "the futures-to-shop-price basis",
                     "the night session's connection to COMEX"),
        impact="makes the Thai gold complex continuously connected to the world price even "
               "overnight, which is why the physical channel can respond within a day rather "
               "than within a month",
        persistence="stable since the contract's launch",
        falsifier="a period in which the TFEX basis to the replicated XAUUSD-times-USDTHB value "
                  "drifts persistently without an arbitrage response"),
    actor(
        "The Thai fiscal authority and its transfer programmes",
        holds="the budget, a fiscal year ending 30 September, and a recent history of large "
              "direct household transfers",
        forced_to=("stimulate a domestic demand economy constrained by household debt",
                   "fund transfers within a public debt ceiling"),
        when="budget in the autumn; transfer programmes announced and disbursed episodically",
        information=("household debt data", "the political calendar"),
        constraints=("a public debt ceiling", "a household debt burden that blunts the "
                     "transmission of any stimulus into durable spending"),
        instruments=("USDTHB", "UST10Y"),
        counterparties=("households", "the bond market", "the central bank, publicly"),
        observables=("the budget and its execution rate",
                     "transfer programme announcements and disbursement",
                     "retail sales and the private consumption index"),
        impact="a fiscal year ending 30 SEPTEMBER, which is unique in this department and gives "
               "Thailand a year-end effect three months out of step with everyone else -- a free "
               "control for any regional fiscal-calendar study",
        persistence="the fiscal year is statutory; the transfer programmes are political",
        falsifier="a transfer programme with no measurable move in private consumption over the "
                  "following two quarters"),
    actor(
        "Offshore THB non-deliverable forward market makers",
        holds="the offshore baht risk book, settled at the 03:00 UTC regional fixing",
        forced_to=("settle at a fixing five to eight hours before the onshore close",
                   "price a currency whose onshore balances they cannot hold freely"),
        when="03:00 UTC daily and at month end",
        information=("offshore positioning", "onshore liquidity conditions"),
        constraints=("the non-resident baht account caps, which are the reason the market is "
                     "non-deliverable",
                     "the ABS fixing methodology"),
        instruments=("USDTHB", "USDSGD", "USDIDR"),
        counterparties=("EM real money", "onshore banks", "regional macro funds"),
        observables=("the ABS fixing", "the NDF curve",
                     "the onshore-offshore basis at the two times of day"),
        impact="gives Thailand the same two-clock structure as Indonesia -- an offshore fix at "
               "03:00 UTC and an onshore rate at 11:00 UTC -- and the gap is a continuous read "
               "on how binding the non-resident baht caps are",
        persistence="structural while the caps stand",
        falsifier="a period in which the offshore and onshore rates converge to within "
                  "transaction costs while the caps remain in force"),
    actor(
        "Chinese tourists and Chinese buyers of Thai agricultural exports",
        holds="the single largest source of both tourist arrivals and durian and cassava demand",
        forced_to=("travel on Chinese holiday calendars, above all the Lunar New Year and the "
                   "October Golden Week",
                   "buy durian in a harvest window of a few weeks"),
        when="Lunar New Year and October Golden Week for travel; April to June for durian",
        information=("Chinese outbound travel policy", "safety perception, which collapsed in "
                     "2025 after high-profile incidents"),
        constraints=("Chinese group-travel policy and airline capacity",
                     "a perishable durian harvest window with no storage option"),
        instruments=("USDTHB", "USDCNH"),
        counterparties=("Thai hotels and retailers", "Thai fruit exporters"),
        observables=("weekly arrivals by nationality",
                     "durian export values in the monthly trade data",
                     "Chinese outbound travel statistics"),
        impact="concentrates a large share of Thailand's two biggest foreign-currency earners "
               "into one counterparty country with its own moving calendar, which is a "
               "concentration risk and a seasonal at the same time",
        persistence="the concentration is structural; the 2025 arrivals collapse is a live break "
                    "that may or may not reverse",
        falsifier="a Chinese Lunar New Year with no measurable spike in Thai arrivals or in "
                  "USDTHB flow"),
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("TH-A", "BoT policy decisions in a three-central-bank hour",
           objects=("six MPC decisions a year at 07:00 UTC",
                    "the minutes fourteen days later and their dissent count",
                    "the annually renegotiated inflation target band",
                    "the October 2025 governor transition"),
           conditions=("whether Bank Negara or Bank Indonesia prints in the same hour",
                       "whether headline inflation is below zero, as it was for much of 2024-25",
                       "the public disagreement between the bank and the government"),
           instruments=("USDTHB", "UST10Y", "HK50"),
           controls=("days when the BoT alone prints at 07:00 UTC versus days when two or three "
                     "regional banks do",
                     "the same statistic at 07:00 UTC on non-decision days",
                     "the deflation period against the rest of the sample, since a reaction "
                     "function has never had to fit a negative headline before"),
           notes="the dissent count is unusually informative here because the committee's "
                 "disagreements have been public and have preceded rate moves"),
    domain("TH-B", "Baht intervention under the non-resident baht account caps",
           objects=("the BoT's weekly reserves and its net forward position",
                    "the non-resident baht account and securities account balance caps",
                    "changes to those caps, which arrive without notice",
                    "realised USDTHB volatility against the regional median"),
           conditions=("whether the caps have recently been tightened or relaxed",
                       "whether the inflow is gold-driven, tourism-driven or portfolio-driven",
                       "whether a US Treasury currency report review is pending"),
           instruments=("USDTHB", "USDX", "USDCNH"),
           controls=("USDIDR and USDSGD over the same period, neither of which is subject to a "
                     "non-resident balance cap of this kind, so the difference isolates the "
                     "constraint rather than the intervention",
                     "the net FORWARD position against the spot reserve change, since "
                     "intervention that does not appear in spot appears here",
                     "periods with no cap change, where the mechanism is dormant by construction"),
           notes="the caps are a QUANTITY restriction on offshore baht balances rather than a "
                 "price defence, which is why Thailand sits between Malaysia's outright "
                 "prohibition and Singapore's free convertibility and is the middle term in any "
                 "regional comparison of capital-account openness"),
    domain("TH-C", "The household gold channel: both legs executable",
           objects=("the domestic shop price and its revision count",
                    "monthly non-monetary gold exports in the customs data",
                    "XAUUSD against USDTHB",
                    "the direction of the physical trade, which conditions everything"),
           conditions=("whether households are net sellers or net buyers, which the customs line "
                       "reveals with a lag",
                       "whether the domestic price is at a record, which drives queue behaviour",
                       "the dollar's own direction, which moves both legs independently"),
           instruments=("XAUUSD", "USDTHB", "XAGUSD"),
           controls=("USDX residualised out FIRST, because gold and the baht both respond to the "
                     "dollar and the raw correlation is mostly that",
                     "a gold-poor comparison currency in the region -- USDIDR or USDCNH -- which "
                     "shares the dollar factor and has no household gold trade of this size",
                     "the ASYMMETRY test: the mechanism predicts the link is conditional on "
                     "households being net sellers, so a CONSTANT beta in both directions "
                     "falsifies the mechanism even if the correlation is strong",
                     "XAGUSD, where the domestic Thai market is far smaller, so the effect must "
                     "be weaker"),
           notes="THE PACK'S CENTRAL DOMAIN and the only country mechanism in this department "
                 "with both legs quotable. The asymmetry control is what separates it from a "
                 "dollar correlation that anyone can find"),
    domain("TH-D", "The replicable TFEX gold basis",
           objects=("TFEX gold futures against XAUUSD multiplied by USDTHB",
                    "the futures-to-shop-price basis",
                    "the night session's connection to COMEX"),
           conditions=("session: day, night or closed",
                       "whether the physical trade is in export or import mode"),
           instruments=("XAUUSD", "USDTHB"),
           controls=("the replicated value from the two executable legs, which is the arithmetic "
                     "identity the basis is measured against",
                     "the same basis on days the shops are open and the exchange is not, which "
                     "isolates the physical market from the listed one"),
           notes="the only absent instrument in this department that can be REPLICATED exactly "
                 "from symbols the desk already holds, which makes its basis a measurement rather "
                 "than a proxy"),
    domain("TH-E", "Tourism seasonality and the weekly services account",
           objects=("weekly arrivals by nationality",
                    "the November-February high season and the May-June and September-October "
                    "troughs",
                    "the services balance in the monthly balance of payments",
                    "the 2025 collapse in Chinese arrivals"),
           conditions=("the composition of arrivals, above all the Chinese share",
                       "airline seat capacity, the binding constraint in the recovery",
                       "visa policy changes"),
           instruments=("USDTHB", "USDCNH"),
           controls=("the pre-pandemic seasonal as an out-of-sample test, since the composition "
                     "has changed and a seasonal fitted before 2020 should FAIL",
                     "a capacity control: arrivals cannot exceed seats, so a seat-constrained "
                     "period is not a demand signal",
                     "other regional destinations on the same dates, which share the northern "
                     "winter and not the Chinese composition"),
           notes="the weekly publication is what makes this domain unusual: almost no country "
                 "publishes a current account component weekly and free"),
    domain("TH-F", "The manufacturing export cycle and the automotive decline",
           objects=("the electronics and hard-disk line in the monthly trade data",
                    "vehicle production and domestic sales",
                    "auto loan rejection rates",
                    "the manufacturing production index"),
           conditions=("the global data-centre and storage capital spending cycle",
                       "the domestic household debt burden, which killed pickup financing",
                       "Chinese electric vehicle competition"),
           instruments=("US500", "USDTHB", "JPN225", "USDKRW"),
           controls=("Korean memory exports, a different part of the same technology cycle, so "
                     "an effect present in both is a technology effect and not a Thai one",
                     "regional vehicle production, which isolates the Thai credit problem from "
                     "the global auto cycle",
                     "the pre-2023 period, before the auto credit collapse"),
           notes="the automotive decline is recent and structural; a model fitted on the 2010s "
                 "expects an auto cycle that no longer exists and will keep predicting a recovery"),
    domain("TH-G", "Agricultural exports and Thailand as the residual rice supplier",
           objects=("weekly Thai rice FOB quotes",
                    "the sugar crush from December to April",
                    "rubber wintering from February to April",
                    "durian exports to China in the April-June window"),
           conditions=("Indian rice export policy, which resets the world price without any Thai "
                       "action",
                       "Brazilian sugar supply, the larger exporter",
                       "Chinese demand concentration in durian and cassava"),
           instruments=("SUGAR", "SUGARRAW", "WHEAT", "CORN", "USDTHB"),
           controls=("Vietnamese rice quotes on the same dates, the other residual supplier, "
                     "which must move together if the mechanism is Indian policy and separately "
                     "if it is Thai supply",
                     "Brazilian crush progress for sugar",
                     "the pre-2023 period, before the Indian rice export ban"),
           notes="Thailand's value here is as the RESIDUAL supplier: the Thai FOB quote is the "
                 "cleanest available read on the effect of an Indian export restriction, which "
                 "ties this domain directly to IN-L"),
    domain("TH-H", "SET foreign flow as a structural drift",
           objects=("the daily four-way investor split",
                    "years of persistent net foreign selling",
                    "Thailand's falling weight in regional benchmarks",
                    "the NVDR mechanism's share of turnover"),
           conditions=("whether the print is above or below the multi-year mean, which is "
                       "NEGATIVE",
                       "index review dates"),
           instruments=("HK50", "USDTHB"),
           controls=("Indonesian and Philippine foreign equity flow, which share the regional "
                     "factor without the structural drift",
                     "a de-meaned version of the series, since the raw level is dominated by a "
                     "trend and a cell fitted on the raw level is trading the trend's mean"),
           notes="the finding here is that the drift IS structural; the trap is treating each "
                 "negative print as news when the unconditional expectation is negative"),
    domain("TH-I", "The bond market shaped by restricted short-dated issuance",
           objects=("foreign holdings by tenor bucket",
                    "the BoT's restriction of its own short-dated bond issuance",
                    "the 10-year spread to UST10Y"),
           conditions=("the global EM local-rates cycle",
                       "whether the flow is in short or long tenors, which the policy separates"),
           instruments=("UST10Y", "USDTHB"),
           controls=("the TOTAL foreign holding, which hides the policy's effect, against the "
                     "tenor split, which reveals it -- the control here is the aggregation itself",
                     "Malaysian and Indonesian foreign bond flow, neither of which faced the same "
                     "issuance restriction"),
           notes="a policy designed to make short-dated speculative positioning impossible should "
                 "show up as a tenor composition effect and not as a level effect; that is the "
                 "testable prediction"),
    domain("TH-J", "Songkran and a calendar no weekday rule generates",
           objects=("the 13-15 April Songkran closure and its substitutions",
                    "the royal birthdays and Buddhist lunar observances",
                    "ad hoc cabinet special holidays announced weeks ahead",
                    "the fact that Thailand does NOT close for Chinese New Year"),
           conditions=("whether the closure is extended by substitution or by a cabinet holiday",
                       "whether the region is simultaneously shut, which Songkran is not"),
           instruments=("USDTHB", "XAUUSD", "USDSGD"),
           controls=("Chinese New Year, when Thailand is OPEN and seven neighbours are shut -- "
                     "the reverse condition, and the cleanest regional liquidity control in this "
                     "department",
                     "the offshore NDF across the Songkran closure, which keeps trading",
                     "volume as well as price, since a liquidity claim needs both"),
           notes="Thailand being open for Chinese New Year is a genuinely useful asymmetry: it "
                 "gives a within-region control for 'the neighbours are shut' that no other "
                 "country here provides"),
    domain("TH-K", "Fiscal transfers and a year ending 30 September",
           objects=("the fiscal year ending 30 September, unique in this department",
                    "direct household transfer programmes and their disbursement",
                    "budget execution rates",
                    "the household debt constraint on transmission"),
           conditions=("the public debt ceiling",
                       "the political cycle",
                       "household debt, which blunts the multiplier"),
           instruments=("USDTHB", "UST10Y"),
           controls=("the CALENDAR year end, which is not Thailand's fiscal year end, so a "
                     "fiscal-calendar effect must appear in September and not in December",
                     "India's 31 March and Indonesia's 31 December year ends as regional controls"),
           notes="the 30 September boundary is three months out of step with the region, which "
                 "makes Thailand the natural control for any regional fiscal-calendar claim"),
    domain("TH-L", "Outbound fund flows as the structural offset",
           objects=("foreign investment fund assets under management",
                    "the portfolio investment line in the balance of payments",
                    "the gap between the current account surplus and the currency's behaviour"),
           conditions=("the domestic-versus-foreign yield differential",
                       "BoT liberalisation of outbound limits",
                       "past returns, which drive retail appetite with a lag"),
           instruments=("USDTHB", "US500"),
           controls=("the current account alone as the null model, which OVER-predicts "
                     "appreciation -- the residual it leaves is what this domain is about",
                     "Korean and Taiwanese outbound retail flows, the same behaviour in "
                     "neighbouring markets"),
           notes="this domain exists to explain a persistent residual: Thailand runs a current "
                 "account surplus and a currency that does not appreciate as much as it implies, "
                 "and the offset is domestic savers buying abroad"),
    domain("TH-M", "Two clocks: the 03:00 UTC offshore fix and the 11:00 UTC onshore rate",
           objects=("the ABS/SFEMC THB fixing at 03:00 UTC",
                    "the BoT daily average rate published at 11:00 UTC",
                    "the non-resident baht account caps that create the split",
                    "the onshore-offshore basis"),
           conditions=("month end", "whether the caps have recently been changed",
                       "days when the onshore market is shut and the offshore one is not"),
           instruments=("USDTHB", "USDSGD", "USDIDR"),
           controls=("USDSGD in the same windows, deliverable and with no NDF to settle",
                     "the other eight currencies settling at the same 03:00 UTC instant",
                     "the adjacent half hours around each clock"),
           notes="the BoT rate is published AFTER the session it describes, so any cell using it "
                 "same-day carries a look-ahead; that is stated here because it is the single "
                 "easiest mistake to make in this pack"),
)

# --------------------------------------------------------------------------- miners (specs)
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("th_gold_channel", domain_ids=("TH-C",), kind="cross_asset",
          entry="research.countries.th.miners:gold_channel", cadence_s=3600.0, steerable=False,
          notes="SPEC, NOT YET WIRED. Residualises USDX out FIRST, then tests the ASYMMETRY "
                "conditional on the sign of the non-monetary gold trade line; a constant beta in "
                "both directions is reported as a falsification and not as a weaker result"),
    miner("th_gold_revision_count", domain_ids=("TH-C",), kind="microstructure",
          entry="research.countries.th.miners:gold_revision_count", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Uses the association's published revision count as a free "
                "retail-activity volatility proxy, which is the part of that dataset everyone "
                "else discards"),
    miner("th_tfex_basis", domain_ids=("TH-D",), kind="basis",
          entry="research.countries.th.miners:tfex_basis", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Replicates the contract exactly from XAUUSD and USDTHB and "
                "measures the listed price against the identity, not against a proxy"),
    miner("th_tourism_seasonal", domain_ids=("TH-E",), kind="macro",
          entry="research.countries.th.miners:tourism_seasonal", cadence_s=604800.0,
          notes="SPEC, NOT YET WIRED. Models the Chinese arrivals line separately and treats the "
                "pre-2020 seasonal as an out-of-sample test that is EXPECTED to fail"),
    miner("th_mpc_hour", domain_ids=("TH-A",), kind="event",
          entry="research.countries.th.miners:mpc_hour", cadence_s=86400.0, steerable=False,
          notes="SPEC, NOT YET WIRED. Separates Thai decisions from Malaysian and Indonesian ones "
                "printing in the same 07:00 UTC hour before any Thai claim is made"),
    miner("th_rice_residual_supplier", domain_ids=("TH-G",), kind="cross_country",
          entry="research.countries.th.miners:rice_residual_supplier", cadence_s=604800.0,
          notes="SPEC, NOT YET WIRED. Joins Indian DGFT notifications to the Thai weekly FOB "
                "quote, which is the cleanest available measure of Indian policy's world effect"),
    miner("th_foreign_flow_drift", domain_ids=("TH-H",), kind="flow",
          entry="research.countries.th.miners:foreign_flow_drift", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. De-means the series before anything else, because the "
                "unconditional expectation of Thai foreign equity flow is negative"),
    miner("th_songkran_liquidity", domain_ids=("TH-J",), kind="calendar",
          entry="research.countries.th.miners:songkran_liquidity", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Uses Chinese New Year -- when Thailand is OPEN and the "
                "region is shut -- as the reverse control"),
    miner("th_two_clocks", domain_ids=("TH-M",), kind="microstructure",
          entry="research.countries.th.miners:two_clocks", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Refuses any same-day use of the BoT average rate, which is "
                "published after the session it describes"),
)

# --------------------------------------------------------------------------- transmission seeds
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("TH-E01", source="XAUUSD rally with Thai households in net-selling mode",
         mechanism="Thai households sell physical gold into strength, the shops export it, and "
                   "the dollar proceeds are converted into baht -- so a gold rally APPRECIATES "
                   "the baht through the physical trade balance",
         targets=("USDTHB",), sign="-", horizon="5 to 40 sessions",
         lag="0 on price; 25 days on the customs line that confirms the physical flow",
         control="USDX residualised out first; a gold-poor regional currency (USDIDR or USDCNH) "
                 "as the same-dollar-factor comparison; and the ASYMMETRY test conditional on "
                 "the sign of the non-monetary gold trade",
         notes="FALSIFIER: a constant beta in both directions, which the mechanism forbids -- it "
               "predicts the link operates when households are net SELLERS and weakens when they "
               "are not. THE PACK'S CENTRAL EDGE, and the only one in this department with both "
               "legs quotable"),
    edge("TH-E02", source="Thai non-monetary gold export volume",
         mechanism="physical metal leaving Thailand is metal arriving in the world market, and "
                   "the volume is large enough in a strong month to move the monthly trade balance",
         targets=("XAUUSD", "USDTHB"), sign="-", horizon="1 to 2 months", lag="25 days",
         control="Indian gold IMPORT data over the same period, which runs the opposite way and "
                 "should partially offset -- the two countries' household gold mechanisms have "
                 "opposite signs and that is the sharpest available cross-check",
         notes="FALSIFIER: Thai gold exports and Indian gold imports both surging with no net "
               "effect, which would say the physical channel nets out globally and cannot move "
               "the world price"),
    edge("TH-E03", source="Thai tourist arrivals against their seasonal norm",
         mechanism="tourism receipts are a services current account inflow worth close to a tenth "
                   "of GDP, published weekly, and converted into baht on arrival",
         targets=("USDTHB", "USDCNH"), sign="-", horizon="1 to 3 months", lag="5 days",
         control="the pre-2020 seasonal as an out-of-sample test that is EXPECTED to fail given "
                 "the composition change, plus an airline seat-capacity control",
         notes="FALSIFIER: a high season at trend arrivals with no seasonal in the services "
               "balance or in USDTHB. The Chinese line must be modelled separately"),
    edge("TH-E04", source="BoT policy decision surprise at 07:00 UTC",
         mechanism="a rate surprise moves the carry and the local curve; the committee's public "
                   "disagreement with the government adds institutional information to the text",
         targets=("USDTHB", "UST10Y"), sign="-", horizon="0 to 3 sessions", lag="0",
         control="days when the BoT alone prints at 07:00 UTC versus days when Bank Negara or "
                 "Bank Indonesia print too, and 07:00 UTC on non-decision days",
         notes="FALSIFIER: an identical response whether the BoT prints alone or alongside its "
               "regional peers, which would mean the regional factor is doing the work"),
    edge("TH-E05", source="an Indian rice export restriction",
         mechanism="Thailand is the residual supplier, so buyers turn to the Thai FOB quote when "
                   "India restricts and Thai agricultural export earnings rise",
         targets=("USDTHB", "WHEAT"), sign="-", horizon="1 to 3 months",
         lag="0 at the Indian notification; weekly on the Thai FOB quote",
         control="Vietnamese rice quotes on the same dates -- the other residual supplier, which "
                 "must move together if the cause is Indian policy and separately if it is Thai "
                 "supply",
         notes="FALSIFIER: an Indian restriction with no rise in the Thai FOB quote within two "
               "weeks. This edge ties directly to the Indian pack's IN-L"),
    edge("TH-E06", source="Thai sugar crush progress, December to April",
         mechanism="a top-two exporter's crush is the second-largest supply signal in the world "
                   "sugar balance after Brazil's",
         targets=("SUGAR", "SUGARRAW"), sign="-", horizon="1 to 3 months", lag="7 days",
         control="Brazilian crush progress on the same dates, the larger exporter, which must be "
                 "controlled for before any Thai claim",
         notes="FALSIFIER: no incremental content once Brazilian supply is in the model, which is "
               "the likely outcome and is worth measuring once"),
    edge("TH-E07", source="Thai electronics and hard-disk export growth",
         mechanism="Thailand's storage and component cluster ties its export cycle to global "
                   "data-centre capital spending, a different part of the technology cycle from "
                   "Korea's memory exposure",
         targets=("US500", "USDKRW"), sign="+", horizon="1 to 2 quarters", lag="22 days",
         control="Korean memory exports on the same dates; an effect present in both is a "
                 "technology effect and not a Thai one",
         notes="FALSIFIER: no incremental content once Korean exports are in the model"),
    edge("TH-E08", source="Thai vehicle production and domestic auto credit",
         mechanism="a manufacturing sector in structural decline for domestic credit reasons "
                   "drags the production index and Japanese parent-company earnings",
         targets=("USDJPY", "JPN225", "USDTHB"), sign="+", horizon="1 to 3 quarters",
         lag="30 days",
         control="regional vehicle production, which isolates the Thai household debt problem "
                 "from the global auto cycle, and the pre-2023 period before the credit collapse",
         notes="FALSIFIER: a recovery in Thai vehicle production with no recovery in domestic "
               "auto credit and no retreat by Chinese entrants"),
    edge("TH-E09", source="the Songkran closure, 13-15 April",
         mechanism="the largest closure in the Thai year removes onshore price discovery for the "
                   "better part of a week while the offshore NDF and the gold shops keep trading",
         targets=("USDTHB", "XAUUSD"), sign="0",
         horizon="the closure window and the two sessions after",
         lag="0 -- the dates are statutory and known years ahead",
         control="Chinese New Year, when Thailand is OPEN and seven neighbours are shut -- the "
                 "reverse condition and the cleanest regional liquidity control available",
         notes="FALSIFIER: no fall in onshore volume across the closure. Must be measured in "
               "VOLUME as well as price. Songkran 2026 is 13-15 April with no substitution"),
    edge("TH-E10", source="Thai foreign equity net flow on the SET",
         mechanism="a structural multi-year selling drift rather than a cyclical signal; the "
                   "unconditional expectation is negative and the deviation is the information",
         targets=("HK50", "USDTHB"), sign="+", horizon="1 to 5 sessions", lag="0 at the close",
         control="the series DE-MEANED first, and Indonesian and Philippine foreign equity flow "
                 "as the regional factor without the Thai drift",
         notes="FALSIFIER: the raw level outperforming the de-meaned version, which would mean "
               "the cell is trading the trend's mean rather than the flow"),
    edge("TH-E11", source="Thai outbound fund (FIF) subscription growth",
         mechanism="domestic savers buying foreign assets are a structural BAHT SELLER that "
                   "offsets the tourism and gold inflows",
         targets=("USDTHB", "US500"), sign="+", horizon="1 to 3 quarters", lag="30 days",
         control="the current account alone as the null model, which OVER-predicts appreciation; "
                 "the residual it leaves is what this edge claims to explain",
         notes="FALSIFIER: no relationship between FIF growth and the current-account residual "
               "across a decade"),
    edge("TH-E12", source="the 03:00 UTC offshore THB fixing",
         mechanism="offshore NDF settlement concentrates hedging demand into a window eight hours "
                   "before the onshore rate is published",
         targets=("USDTHB", "USDIDR", "USDSGD"), sign="+", horizon="intraday", lag="0",
         control="USDSGD in the same window, deliverable with no NDF to settle, and the other "
                 "eight currencies settling at the same instant",
         notes="FALSIFIER: an effect present in USDSGD, which would prove it is a session "
               "boundary and not a fixing"),
    edge("TH-E13", source="Thai crude and refined product import volume",
         mechanism="a net energy importer of about a million barrels a day carries a structural "
                   "dollar bid that scales with the oil price",
         targets=("XBRUSD", "XTIUSD", "USDTHB"), sign="+", horizon="1 to 2 months", lag="22 days",
         control="Malaysia, the region's net energy EXPORTER, which must show the opposite sign; "
                 "agreement between the two means nothing has been identified",
         notes="FALSIFIER: the same sign in Thailand and Malaysia, which would identify a dollar "
               "or risk factor rather than an energy balance"),
    edge("TH-E14", source="the Thai fiscal year end on 30 September",
         mechanism="budget execution and transfer disbursement cluster into a year end three "
                   "months out of step with the rest of the region",
         targets=("USDTHB", "UST10Y"), sign="0", horizon="the four weeks around 30 September",
         lag="0 -- statutory",
         control="31 December, which is NOT Thailand's fiscal year end, plus India's 31 March and "
                 "Indonesia's 31 December as regional controls",
         notes="FALSIFIER: a September effect that also appears in December, which would make it "
               "a quarter-end artefact. Unsigned: the direction depends on execution, not on the "
               "date"),
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("TH-R1", start="2010-01-01", end="2019-12-31",
        label="the surplus baht, pre-pandemic",
        what_changed="a very large current account surplus driven by tourism and manufacturing "
                     "made the baht one of Asia's strongest currencies; the BoT tightened "
                     "non-resident baht account limits in 2019 to slow the appreciation",
        invalidates="a tourism seasonal fitted here has a composition that no longer exists, and "
                    "the appreciation pressure of this era has not returned",
        notes="THBFIX was still the reference rate throughout"),
    era("TH-R2", start="2020-01-01", end="2022-09-30",
        label="the tourism collapse",
        what_changed="arrivals fell to near zero, the services account went from a huge surplus "
                     "to nothing, and the current account flipped into deficit",
        invalidates="a current-account model fitted across this era averages a normal economy "
                    "with a closed one; the tourism seasonal is absent by construction",
        notes="THBFIX began its transition to THOR during this period"),
    era("TH-R3", start="2022-10-01", end="2024-12-31",
        label="the recovery, the deflation and the auto credit collapse",
        what_changed="tourism recovered but with a changed composition, headline inflation fell "
                     "below zero for an extended stretch, and domestic auto credit collapsed and "
                     "took vehicle production with it",
        invalidates="a reaction function fitted on positive inflation has never seen the "
                     "deflation stretch; a manufacturing model fitted before 2023 expects an auto "
                     "cycle that ended",
        notes="the BoT reduced its MPC meetings to six a year in this window's vicinity, changing "
              "the event count"),
    era("TH-R4", start="2025-01-01", end="2025-09-30",
        label="the Chinese arrivals break and the gold record",
        what_changed="Chinese arrivals fell sharply on safety perception and were not fully "
                     "replaced, while the world gold price set records and Thai household selling "
                     "and gold exports surged with it",
        invalidates="the tourism and the gold channels moved in OPPOSITE directions in this "
                    "period, so a single-factor current-account model fits it badly and a cell "
                    "must condition on which channel it is claiming",
        notes="the clearest recent period for observing the gold channel on its own"),
    era("TH-R5", start="2025-10-01", end=None,
        label="the new governor",
        what_changed="the governorship changed on 1 October 2025, and governor transitions are "
                     "era boundaries in every managed-float currency in this department",
        invalidates="the intervention intensity that the observed gold-and-baht elasticity is a "
                    "joint measurement of may have changed; TH-C must be re-fitted inside this "
                    "era before a live candidate rests on it",
        notes="the current regime and what a live candidate is actually trading"),
)


# --------------------------------------------------------------------------- assembly
MISSION = (
    "mine Thailand to exhaustion on the one country mechanism in this department "
    "whose BOTH legs are quotable here: Thai households sell physical gold into "
    "rallies, the shops export it, and the baht appreciates -- XAUUSD and USDTHB, "
    "with the customs gold line as the physical confirmation -- plus a weekly-"
    "published tourism current account and a royal calendar no weekday rule generates")
NOTES = (
    "USDTHB, XAUUSD and XAGUSD are all executable, which is what makes TH-C a test "
    "rather than an observation. The SET, SET50 futures, TFEX's gold contract, Thai "
    "rice, rubber, THOR and the 10-year bond are absent and are named in this module's "
    "TRANSMISSION_TARGETS; the TFEX gold contract is the only absent instrument in this "
    "whole department that the desk can REPLICATE exactly from symbols it already "
    "holds. The BoT daily average rate is published AFTER the session it describes, so "
    "a same-day use of it is a look-ahead.")


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
    """Thailand's pack: `CountryPack` when the framework has landed, else the same fields as a
    dict. `transmission_targets` rides alongside the twenty-one frozen fields."""
    return build_pack(**fields())
