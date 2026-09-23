"""THE PHILIPPINES: a current account made of people, rice bought from abroad, and ore that stops
when it rains.

WHAT THE PHILIPPINES IS AS A MARKET MECHANISM. Strip out the commodities and what is left is an
economy whose two largest foreign-currency earners are LABOUR EXPORTS, converted into pesos on
calendars that human institutions set and markets do not:

  1. OVERSEAS FILIPINO WORKER REMITTANCES, above USD 34bn a year and close to a tenth of GDP, the
     fourth-largest inbound remittance flow on earth. It has the sharpest December peak of any
     large remittance corridor, because Christmas in the Philippines is a two-month economic
     season and because the STATUTORY thirteenth-month pay must be paid by 24 December. There is
     a secondary bump in May and June for school enrolment. The BSP publishes the monthly cash
     remittance series with roughly a forty-five-day lag, which is the point-in-time problem: the
     December print -- the largest of the year -- does not exist until the middle of February.

  2. BUSINESS-PROCESS OUTSOURCING, around USD 38bn of annual revenue and over a million and a
     half workers. Those workers are paid in pesos on the Philippine SEMI-MONTHLY payroll
     convention: the 15th and the end of the month. The dollar revenue is therefore converted
     twice a month on dates nobody chooses and nobody can move. That is as concrete a
     microstructural flow calendar as exists anywhere in this department, and it is the reason
     PH-D is a domain and not a curiosity.

  3. RICE. The Philippines is the world's LARGEST rice importer, buying four to five million
     tonnes a year, overwhelmingly from Vietnam. That is simultaneously a dollar demand, a food
     inflation channel, and a direct, dated link to the Vietnamese pack. The tariff regime has
     been moved twice in eighteen months -- cut from 35% to 15% in mid-2024, then imports
     suspended in 2025 to protect farmgate prices -- and each move is an administrative shock to
     both the import bill and the CPI.

  4. NICKEL ORE THAT STOPS WHEN IT RAINS. The Philippines is the second-largest exporter of mined
     nickel and the largest supplier of direct-shipping ore to China. The mines are in Surigao
     and Zambales, they are open-pit and monsoon-exposed, and Surigao shuts for the northeast
     monsoon from roughly October to March every single year. So Philippine nickel supply has a
     HARD, WEATHER-DRIVEN, ANNUAL seasonal that is not a behavioural pattern and not a
     price response -- it is the rain. When Indonesia restricts supply by quota, the Philippines
     is the swing barrel, and its swing is seasonal.

WHAT IS EXECUTABLE AND WHAT IS NOT. USDPHP is NOT on this broker's registry. Neither is the PSEi,
the peso reference rate, the RTB retail bond programme, nor any Philippine rice or nickel
contract. Every one of them is named in `TRANSMISSION_TARGETS` with the symbols its mechanism
reaches: XNIUSD for the ore seasonal, XCUUSD and XAUUSD for the mining complex, WHEAT and CORN for
the food-import channel, US500 and NAS100 for the BPO revenue's ultimate source, and USDSGD,
USDTHB, USDIDR and USDCNH for whatever peso move survives into the regional complex.

THE HONEST PART. The remittance and BPO mechanisms are large, well documented and genuinely
seasonal, and NONE of them can be traded directly here. What can be traded is what they reach: a
nickel seasonal, a rice-and-grain channel, and the regional FX complex. PH-L measures how much of
a Philippine move survives into each proxy, with the expectation that most of it does not -- the
same discipline MY-L applies to Malaysia, for the same reason.

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
CODE = "PH"
NAME = "Philippines"
REGION_COMMAND = "southeast_asia"
CURRENCY = "PHP"
FISCAL_YEAR_END = "12-31"  # the national budget runs on the calendar year
NATIVE_LANGUAGES: tuple[str, ...] = ("fil", "en", "ceb")

#: NO PHILIPPINE INSTRUMENT IS IN THIS LIST. USDPHP is absent from the broker registry, so this
#: is the set of symbols Philippine mechanisms REACH.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "XNIUSD",                                # the swing supplier of direct-shipping nickel ore
    "XCUUSD", "XAUUSD",                      # the copper-gold porphyry mining complex
    "WHEAT", "CORN", "SUGAR",                # the food-import channel and domestic sugar policy
    "XTIUSD", "XBRUSD",                      # a net oil importer with no refining to speak of
    "USDSGD", "USDTHB", "USDIDR", "USDCNH",  # the regional complex a peso move can reach
    "USDJPY",                                # Japanese ODA, FDI and a large remittance corridor
    "USDX",                                  # the dollar factor every claim here must remove
    "US500", "NAS100",                       # where BPO revenue ultimately comes from
    "HK50",                                  # the EM Asia risk factor
    "UST10Y",                                # what foreign holders of Philippine debt price to
)

TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USD/PHP spot and forward", "venue": "onshore interbank; offshore NDF",
     "why": "not on the broker registry. The peso is deliverable onshore and has a thin offshore "
            "NDF settled against the 03:00 UTC regional fixing; neither is quotable here",
     "proxies": ("USDSGD", "USDTHB", "USDIDR", "USDCNH")},
    {"name": "PSEi and the Philippine Stock Exchange", "venue": "PSE",
     "why": "foreign net flow is published daily and free; the index has been a net "
            "foreign-selling market for years and has no liquid derivative",
     "proxies": ("HK50", "US500")},
    {"name": "BAP PHP reference rate", "venue": "Bankers Association of the Philippines",
     "why": "the onshore transaction-weighted reference for the peso session; the settlement "
            "anchor for domestic contracts",
     "proxies": ("USDSGD", "USDIDR")},
    {"name": "Retail Treasury Bonds and the domestic government curve",
     "venue": "Bureau of the Treasury",
     "why": "RTB offerings are periodic, large and marketed directly to households, which drains "
            "peso liquidity on announced dates in a way no other country here does",
     "proxies": ("UST10Y",)},
    {"name": "Philippine nickel direct-shipping ore", "venue": "physical, sold to China",
     "why": "the world's largest DSO supplier, with a hard monsoon-driven seasonal; no ore "
            "contract exists anywhere, let alone in this universe",
     "proxies": ("XNIUSD",)},
    {"name": "Philippine rice import tenders and the NFA farmgate programme",
     "venue": "government and private importers",
     "why": "the world's largest rice importer, buying mostly from Vietnam; the tariff has moved "
            "twice in eighteen months and each move is a dated administrative shock",
     "proxies": ("WHEAT", "CORN")},
    {"name": "BSP overnight reverse repurchase facility and the domestic curve",
     "venue": "Bangko Sentral ng Pilipinas",
     "why": "the policy rate and the liquidity operations around it; the reserve requirement has "
            "been cut repeatedly and is a genuine second instrument",
     "proxies": ("UST10Y", "USDSGD")},
    {"name": "BSP monthly cash remittance series", "venue": "Bangko Sentral ng Pilipinas",
     "why": "the single most important Philippine macro series and the one with the worst "
            "publication lag: the December peak is not published until mid-February",
     "proxies": ("USDSGD", "USDJPY")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bangko Sentral ng Pilipinas",
    "short": "BSP",
    "committee": "the Monetary Board",
    "policy_instrument": "the overnight reverse repurchase (RRP) rate",
    "secondary_instruments": ("the reserve requirement ratio, cut repeatedly and by large steps, "
                              "which is a genuine second instrument rather than a technicality",
                              "BSP securities auctions and the term deposit facility",
                              "foreign exchange smoothing, which the BSP frames as tempering "
                              "volatility rather than defending a level"),
    "mandate": "price stability conducive to balanced and sustainable growth, with an inflation "
               "target band agreed with the government and set at 2-4%",
    "decision_rule": "a schedule of policy meetings published a year ahead, six to eight per "
                     "year in the recent calendars. The decision is announced at about 15:00 PHT, "
                     "which is 07:00 UTC -- the same hour as Bank Negara, Bank Indonesia and the "
                     "Bank of Thailand, so up to four Southeast Asian central banks can print "
                     "into one window",
    "announce_local": "about 15:00 PHT", "announce_utc": "07:00",
    "presser_utc": "07:30",
    "fx_regime": "a float with smoothing. The BSP does not defend a level and says so, but the "
                 "market has repeatedly treated round numbers as psychological lines and the BSP "
                 "has repeatedly been visible near them",
    "off_cycle": "the Monetary Board can act between scheduled meetings and has done so in "
                 "crises; the more usual off-calendar action is a reserve requirement cut, "
                 "announced with effect several weeks ahead",
    "other_clocks": (
        {"what": "monthly cash remittances", "when_local": "about the 15th, 16:00 PHT",
         "when_utc": "08:00", "reference_lag_days": 45},
        {"what": "gross international reserves", "when_local": "the 7th business day",
         "when_utc": "08:00", "reference_lag_days": 7},
        {"what": "balance of payments position", "when_local": "about the 19th",
         "when_utc": "08:00", "reference_lag_days": 20},
        {"what": "BAP PHP reference rate", "when_local": "after the onshore session",
         "when_utc": "08:00", "reference_lag_days": 0},
    ),
    "dates": {
        2024: (),
        2025: ("2025-02-13", "2025-04-03", "2025-06-19", "2025-08-28", "2025-10-09",
               "2025-12-11"),
        2026: (),
    },
    "dates_status": "ONLY 2025 is carried, and it is RECONSTRUCTED from the BSP's published "
                    "schedule pattern rather than individually verified. 2024 and 2026 are "
                    "UNMEASURED here (L1.28a): the BSP has changed the number of meetings a year "
                    "within this sample, so a pattern cannot be extrapolated and an invented date "
                    "is worse than a missing one. Read bsp.gov.ph before any event study",
}

# --------------------------------------------------------------------------- fixings, settlement
#: PHT is UTC+8 all year with no daylight saving.
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "BAP PHP reference rate",
     "administrator": "Bankers Association of the Philippines",
     "window_local": "the onshore USD/PHP spot session, 09:00-16:00 PHT",
     "window_utc": "01:00-08:00", "publish_local": "after the session closes",
     "publish_utc": "08:00",
     "basis": "a transaction-weighted average of onshore interbank spot dealings",
     "uses": "the settlement reference for domestic contracts and for corporate translation",
     "note": "published AFTER the session it describes, so a same-day use of it is a look-ahead; "
             "the Thai and Philippine rates share this trap and it is the easiest mistake to "
             "make in both packs"},
    {"name": "ABS/SFEMC PHP spot fixing",
     "administrator": "ABS Benchmarks Administration Co, Singapore",
     "window_local": "concluding about 11:00 SGT, which is 11:00 PHT",
     "window_utc": "02:30-03:00", "publish_local": "about 11:00 SGT", "publish_utc": "03:00",
     "basis": "the regional Asian currency fixing panel",
     "uses": "settlement of offshore PHP non-deliverable forwards",
     "note": "the same 03:00 UTC instant as eight other Asian currencies; the Philippine NDF is "
             "thin relative to the Indonesian or Korean one, so a PHP-specific fixing effect is "
             "less likely here than elsewhere in the set"},
    {"name": "the semi-monthly payroll conversion dates",
     "administrator": "none -- this is a labour-law convention, not a benchmark",
     "window_local": "the 15th and the last working day of each month",
     "window_utc": "01:00-08:00 on those dates",
     "publish_local": "n/a", "publish_utc": "n/a",
     "basis": "Philippine wages are paid semi-monthly by near-universal convention, so dollar "
              "revenue at the BPO operators is converted into pesos twice a month on dates that "
              "nobody chooses",
     "uses": "not a settlement reference; a FLOW CLOCK",
     "note": "TREATED AS A FIXING HERE ON PURPOSE. A recurring, institutionally fixed, "
             "twice-monthly conversion of several billion dollars a year is exactly the kind of "
             "dated forced flow the region mandate's actor chain is designed to find, and it has "
             "no benchmark attached because nobody publishes it"},
    {"name": "the thirteenth-month pay deadline",
     "administrator": "Philippine labour law",
     "window_local": "on or before 24 December each year",
     "window_utc": "the December payroll cycle", "publish_local": "n/a", "publish_utc": "n/a",
     "basis": "employers are statutorily required to pay a thirteenth month's salary by 24 "
              "December, which is the domestic counterpart of the remittance peak",
     "uses": "a FLOW CLOCK, not a benchmark",
     "note": "the two December flows -- inbound remittances and the domestic statutory bonus -- "
             "peak in the same fortnight and reinforce each other, which is why the Philippine "
             "December seasonal is sharper than any other in this department"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"market": "USD/PHP onshore interbank spot", "cycle": "T+1 for the onshore peso leg",
     "session_local": "09:00-16:00 PHT", "session_utc": "01:00-08:00",
     "note": "the peso is deliverable onshore and largely convertible; the offshore NDF exists "
             "for offshore booking convenience rather than because the currency is prohibited, "
             "which is the opposite of the Malaysian case"},
    {"market": "Philippine Stock Exchange equities", "cycle": "T+2",
     "session_local": "pre-open 09:00-09:30, morning 09:30-12:00, recess 12:00-13:30, afternoon "
                      "13:30-15:20, run-off to 15:30 PHT",
     "session_utc": "01:30-04:00 and 05:30-07:30",
     "note": "the RUN-OFF period after 15:20 trades only at the closing price, which means the "
             "close is a fixed-price window and not an auction -- a different animal from the "
             "closing auctions elsewhere in this region"},
    {"market": "Philippine government securities", "cycle": "T+2",
     "session_local": "09:00-16:00 PHT", "session_utc": "01:00-08:00",
     "note": "Retail Treasury Bond offerings are marketed directly to households over a "
             "multi-week offer period, which drains peso bank deposits on announced dates -- a "
             "liquidity event with a published calendar"},
    {"market": "offshore PHP non-deliverable forward",
     "cycle": "cash settled against the 03:00 UTC ABS fixing",
     "session_local": "offshore hours", "session_utc": "continuous",
     "note": "thin relative to the Indonesian, Korean and Taiwanese NDFs, because the onshore "
             "market is accessible enough that offshore demand is small"},
)

# --------------------------------------------------------------------------- exchanges
EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Philippine Stock Exchange", "code": "PSE",
     "hours_local": "09:30-12:00 and 13:30-15:20 PHT, with a run-off to 15:30",
     "hours_utc": "01:30-04:00 and 05:30-07:30",
     "expiry_rule": "there is no liquid listed index derivative; the exchange has attempted "
                    "index futures more than once and liquidity has not persisted, so the "
                    "Philippines has NO expiry-day mechanism to study -- which makes it a useful "
                    "negative control for any regional expiry claim",
     "settlement": "T+2",
     "rebalance": "PSEi reviewed semi-annually with changes effective in February and August"},
    {"name": "Philippine Dealing and Exchange Corp", "code": "PDEx",
     "hours_local": "09:00-16:00 PHT", "hours_utc": "01:00-08:00",
     "expiry_rule": "n/a -- a fixed income trading platform",
     "settlement": "T+2",
     "rebalance": "n/a",
     "note": "where the domestic government bond curve is actually priced, and where an RTB "
             "offering's effect on peso liquidity becomes visible"},
)

# --------------------------------------------------------------------------- the holiday rule
_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-01-01": "New Year's Day",
        "2024-02-10": "Chinese New Year (special non-working day)",
        "2024-03-28": "Maundy Thursday",
        "2024-03-29": "Good Friday",
        "2024-04-09": "Araw ng Kagitingan (Day of Valour)",
        "2024-04-10": "Eid'l Fitr",
        "2024-05-01": "Labour Day",
        "2024-06-12": "Independence Day",
        "2024-06-17": "Eid'l Adha",
        "2024-08-21": "Ninoy Aquino Day",
        "2024-08-26": "National Heroes Day (last Monday of August)",
        "2024-11-01": "All Saints' Day",
        "2024-12-24": "Christmas Eve (special non-working day)",
        "2024-12-25": "Christmas Day",
        "2024-12-30": "Rizal Day",
        "2024-12-31": "Last day of the year (special non-working day)",
    },
    2025: {
        "2025-01-01": "New Year's Day",
        "2025-01-29": "Chinese New Year (special non-working day)",
        "2025-04-01": "Eid'l Fitr",
        "2025-04-09": "Araw ng Kagitingan (Day of Valour)",
        "2025-04-17": "Maundy Thursday",
        "2025-04-18": "Good Friday",
        "2025-05-01": "Labour Day",
        "2025-05-12": "National and local elections (special non-working day)",
        "2025-06-12": "Independence Day",
        "2025-08-21": "Ninoy Aquino Day",
        "2025-08-25": "National Heroes Day (last Monday of August)",
        "2025-12-08": "Feast of the Immaculate Conception",
        "2025-12-25": "Christmas Day",
        "2025-12-30": "Rizal Day",
        "2025-12-31": "Last day of the year (special non-working day)",
    },
    2026: {
        "2026-01-01": "New Year's Day",
        "2026-02-17": "Chinese New Year (special non-working day)",
        "2026-03-20": "Eid'l Fitr",
        "2026-04-02": "Maundy Thursday",
        "2026-04-03": "Good Friday",
        "2026-04-09": "Araw ng Kagitingan (Day of Valour)",
        "2026-05-01": "Labour Day",
        "2026-05-27": "Eid'l Adha",
        "2026-06-12": "Independence Day",
        "2026-08-21": "Ninoy Aquino Day",
        "2026-08-31": "National Heroes Day (last Monday of August)",
        "2026-11-30": "Bonifacio Day",
        "2026-12-08": "Feast of the Immaculate Conception",
        "2026-12-25": "Christmas Day",
        "2026-12-30": "Rizal Day",
        "2026-12-31": "Last day of the year (special non-working day)",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": "Two statutory classes with different legal effects. REGULAR HOLIDAYS carry double "
            "pay and are mostly fixed Gregorian dates -- 1 January, 9 April (Araw ng Kagitingan), "
            "1 May, 12 June (Independence Day), the last Monday of August (National Heroes Day), "
            "30 November (Bonifacio Day), 25 December and 30 December (Rizal Day) -- plus Maundy "
            "Thursday and Good Friday from the Western computus, and Eid'l Fitr and Eid'l Adha "
            "proclaimed from local moon-sighting. SPECIAL NON-WORKING DAYS carry a different pay "
            "rule and include Chinese New Year, 8 December, 24 and 31 December, All Saints' Day, "
            "and any day the President proclaims. THE PROCLAMATION POWER IS THE OPERATIVE PART: "
            "the President issues the following year's list by proclamation, routinely MOVES a "
            "holiday to a Monday to create a long weekend ('holiday economics'), and adds ad hoc "
            "days at a few weeks' notice -- including election days. No weekday rule generates "
            "this calendar, and the exchange follows the proclamation.",
    "table": _HOLIDAYS,
    "years": (2024, 2025, 2026),
    "status": {2024: "CONFIRMED for the regular holidays and the main special days",
               2025: "CONFIRMED for the regular holidays and the main special days",
               2026: "PROVISIONAL -- fixed dates and the last-Monday-of-August rule are certain; "
                     "the Islamic dates are carried at their expected values (Eid'l Fitr on 20 "
                     "March 2026) and any presidential proclamation of an additional day is by "
                     "definition unknowable in advance"},
    "holiday_economics": "the practice of moving a holiday to the nearest Monday means a "
                         "Philippine holiday's WEEKDAY is a policy choice, so a day-of-week "
                         "statistic computed across this calendar is contaminated by a "
                         "deliberate Monday bias that no other country here has",
    "christmas_note": "the Philippine Christmas season runs from September and the market "
                      "calendar thins from mid-December; combined with the 24 and 31 December "
                      "special days the last fortnight of the year is effectively a half-market",
}

# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "PSE daily foreign buying and selling",
     "root": "https://www.pse.com.ph/market-information/",
     "fields": ("foreign buying value", "foreign selling value", "net foreign flow"),
     "frequency": "daily", "publish_utc": "08:00", "lag_days": 0, "licence": "free, public",
     "why": "with no liquid listed derivative, cash foreign flow is the entire positioning "
            "signal in Philippine equity risk"},
    {"name": "BSP monthly cash remittances",
     "root": "https://www.bsp.gov.ph/SitePages/Statistics/External.aspx",
     "fields": ("cash remittances by source country", "personal remittances",
                "year-on-year growth"),
     "frequency": "monthly", "publish_utc": "08:00", "lag_days": 45, "licence": "free, public",
     "why": "the most important Philippine macro series and the one with the worst lag: the "
            "December peak, the largest print of the year, is not published until mid-February"},
    {"name": "BSP gross international reserves",
     "root": "https://www.bsp.gov.ph/SitePages/Statistics/External.aspx",
     "fields": ("gross international reserves", "months of import cover",
                "short-term external debt cover"),
     "frequency": "monthly", "publish_utc": "08:00", "lag_days": 7, "licence": "free, public",
     "why": "the intervention observable; the BSP frames its participation as tempering "
            "volatility, so the reserve change is the only quantitative record of it"},
    {"name": "Bureau of the Treasury auction results and the RTB calendar",
     "root": "https://www.treasury.gov.ph/",
     "fields": ("auction volume and cut-off", "RTB offer period and size"),
     "frequency": "weekly auctions; RTB offerings periodic", "publish_utc": "04:00",
     "lag_days": 0, "licence": "free, public",
     "why": "an RTB offering drains household bank deposits on announced dates, which is a peso "
            "liquidity event with a published calendar and no analogue elsewhere in this region"},
    {"name": "Philippine Statistics Authority trade and CPI",
     "root": "https://psa.gov.ph/statistics",
     "fields": ("merchandise exports and imports by commodity", "CPI and the rice sub-index",
                "electronics exports"),
     "frequency": "monthly", "publish_utc": "01:00", "lag_days": 40,
     "licence": "free, public",
     "why": "the RICE sub-index of CPI is the politically decisive number in the Philippines and "
            "is what triggers a tariff or import-suspension decision"},
    {"name": "CFTC Commitments of Traders",
     "root": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
     "fields": ("non-commercial net in copper, gold, wheat, corn, the dollar index",),
     "frequency": "weekly", "publish_utc": "20:30", "lag_days": 3, "licence": "free, public",
     "why": "PHP is not in the COT. These are the external legs of the mining and food-import "
            "transmission edges"},
)

# --------------------------------------------------------------------------- terminology
#: Filipino (Tagalog) with English, which is the actual register of Philippine financial
#: discussion: the institutions publish in English and the household economy is discussed in
#: Filipino, so a miner needs both and a Filipino-only or English-only search misses half.
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "PH-A": ("Bangko Sentral ng Pilipinas", "patakarang salapi", "interes", "implasyon",
             "Monetary Board", "policy rate", "reserve requirement"),
    "PH-B": ("piso", "halaga ng piso", "palitan", "humina ang piso", "lumakas ang piso",
             "reserba", "peso depreciation"),
    "PH-C": ("padala", "remitansya", "OFW", "Overseas Filipino Worker", "balikbayan",
             "pamilya", "Pasko", "ika-labintatlong buwang sahod", "13th month pay"),
    "PH-D": ("BPO", "call center", "sahod", "sweldo", "kinsenas", "katapusan",
             "semi-monthly payroll", "outsourcing revenue"),
    "PH-E": ("bigas", "palay", "presyo ng bigas", "taripa", "angkat na bigas", "NFA",
             "rice tariff", "import suspension"),
    "PH-F": ("mina", "minahan", "nikel", "tanso", "ginto", "tag-ulan", "habagat", "amihan",
             "nickel ore", "monsoon shutdown"),
    "PH-G": ("langis", "presyo ng langis", "angkat", "oil imports"),
    "PH-H": ("pamilihan ng sapi", "PSE", "dayuhang mamumuhunan", "netong pagbebenta",
             "foreign net selling"),
    "PH-I": ("bono", "RTB", "Kabang Yaman", "utang ng gobyerno", "retail treasury bond"),
    "PH-J": ("pista opisyal", "walang pasok", "Mahal na Araw", "Pasko", "Bagong Taon",
             "holiday economics", "proclamation"),
    "PH-K": ("badyet", "gastusin ng gobyerno", "imprastraktura", "Build Better More",
             "infrastructure spending"),
    "PH-L": ("paghahatid", "ugnayan", "rehiyonal", "proxy", "regional transmission"),
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
    _src("PH-S1", "the central bank, the treasury and the statistics authority", layer="official",
         roots=("https://www.bsp.gov.ph/SitePages/MediaAndResearch/MediaDisp.aspx",
                "https://www.bsp.gov.ph/SitePages/Statistics/External.aspx",
                "https://psa.gov.ph/statistics", "https://www.treasury.gov.ph/",
                "https://www.da.gov.ph/"),
         languages=("en", "fil"), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("BSP monetary policy decision statement", "cash remittances monthly BSP",
                  "presyo ng bigas CPI", "rice import clearance weekly",
                  "gross international reserves Philippines"),
         notes="the policy statement at 07:00 UTC, the remittance series with its forty-five-day "
               "lag, and the agriculture department's rice import and farmgate data -- the three "
               "series this pack is built on"),
    _src("PH-S2", "the exchange, the dealing platform, the bankers' association and the ADB",
         layer="institutional",
         roots=("https://www.pse.com.ph/market-information/",
                "https://www.pds.com.ph/", "https://www.sec.gov.ph/",
                "https://www.adb.org/countries/philippines/main",
                "https://www.imf.org/en/Countries/PHL"),
         languages=("en",), licence="free, public", access_label="PUBLIC",
         credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         queries=("PSE daily foreign buying selling", "BAP reference rate methodology",
                  "PSEi index review effective", "ADB Philippines remittance study"),
         notes="the ADB is headquartered in Manila and publishes more on Philippine remittance "
               "and labour flows than any other institution, which makes the institutional layer "
               "unusually strong here even though the market layer is thin"),
    _src("PH-S3", "Philippine academic and policy research", layer="academic",
         roots=("https://www.pids.gov.ph/publications", "https://econ.upd.edu.ph/dp/",
                "https://www.adb.org/publications", "https://www.imf.org/en/Publications/WP"),
         languages=("en",), licence="free, public", access_label="PUBLIC",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("remittance seasonality Philippines study",
                  "rice tariffication law impact PIDS", "BPO sector labour displacement"),
         notes="PIDS and the UP School of Economics are where the rice tariffication law's effects "
               "and the remittance seasonal are actually quantified; PH-C and PH-E both need a "
               "prior and this is the only layer that supplies one"),
    _src("PH-S4", "the economist survey and the practitioner community", layer="practitioner",
         roots=("https://www.bworldonline.com/economy/",
                "https://www.colfinancial.com/ape/Final2/home/",
                "https://www.firstmetrosec.com.ph/", "https://www.investagrams.com/"),
         languages=("en", "fil"), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("BusinessWorld poll BSP rate decision", "analyst forecast peso 59",
                  "PSEi technical outlook", "RTB offering rate guidance"),
         notes="THE BUSINESSWORLD ECONOMIST POLL IS LOAD-BEARING. With no liquid rates derivative "
               "there is no market-implied path, so the published poll is the ONLY consensus a "
               "BSP surprise can be measured against -- a weaker instrument than a price and "
               "named as such in PH-A"),
    _src("PH-S5", "retail investor and personal finance communities", layer="retail_ecology",
         roots=("https://www.reddit.com/r/phinvest/", "https://www.reddit.com/r/Philippines/",
                "https://www.facebook.com/groups/", "https://www.investagrams.com/Forum"),
         languages=("en", "fil"), licence="public web; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("ipon challenge", "13th month pay investment", "padala rate ngayon",
                  "pasok sa PSEi", "sideways pa rin ang market"),
         notes="r/phinvest is where the thirteenth-month-pay deployment decision is discussed "
               "every December in the first person, which is direct behavioural evidence for the "
               "domestic half of PH-C's seasonal. UNRELIABLE as fact, informative as behaviour"),
    _src("PH-S6", "brokerage, remittance and e-wallet apps", layer="app_ecosystem",
         roots=("https://www.colfinancial.com/", "https://www.gcash.com/",
                "https://www.mayabank.ph/", "https://www.investagrams.com/",
                "https://www.remitly.com/ph/en"),
         languages=("en", "fil"), licence="public web; platform terms vary",
         access_label="ACCESS_UNCLEAR", credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("GCash padala fee", "remittance app exchange rate comparison",
                  "COL Financial minimum investment", "digital wallet remittance volume"),
         notes="THE APP LAYER IS THE REMITTANCE RAIL. A growing share of OFW remittance arrives "
               "through digital wallets rather than through bank counters, which changes both the "
               "conversion TIMING and the BSP's measurement of it -- a live measurement problem "
               "for PH-C that this layer is the only way to see"),
    _src("PH-S7", "Philippine media in English and Filipino", layer="media",
         roots=("https://www.bworldonline.com/", "https://business.inquirer.net/",
                "https://www.philstar.com/business", "https://www.rappler.com/business/",
                "https://www.abante.com.ph/"),
         languages=("en", "fil"), licence="public web; quote verbatim and attribute",
         access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("presyo ng bigas tumaas", "suspension ng pag-angkat ng bigas",
                  "peso hits new low", "typhoon damage agriculture"),
         notes="the rice price is the most politically charged number in the country and is "
               "covered in Filipino in the tabloids long before a policy change is announced in "
               "English -- which is the leading edge of PH-E"),
    _src("PH-S8", "the Official Gazette and the proclamation archive", layer="archive",
         roots=("https://www.officialgazette.gov.ph/", "https://elibrary.judiciary.gov.ph/",
                "https://web.archive.org/web/*/bsp.gov.ph*"),
         languages=("en", "fil"), licence="free, public", access_label="PUBLIC_ARCHIVE",
         credibility="AUTHORITATIVE", predictive_state="NOT_PREDICTIVE",
         queries=("proclamation declaring holidays 2026", "executive order rice tariff",
                  "administrative order import suspension"),
         notes="THE PROCLAMATION ARCHIVE IS NOT OPTIONAL HERE. Philippine holidays are set and "
               "MOVED by presidential proclamation, so the statutory date and the observed date "
               "differ and only the gazette records both -- the control PH-J requires. "
               "NOT_PREDICTIVE: an archive dates"),
    _src("PH-S9", "the physical economy: typhoons, mines, ports and power",
         layer="physical_economy",
         roots=("https://www.pagasa.dost.gov.ph/", "https://mgb.gov.ph/",
                "https://www.ppa.com.ph/", "https://www.doe.gov.ph/",
                "https://www.philrice.gov.ph/"),
         languages=("en", "fil"), licence="free, public", access_label="OPEN_DATA",
         credibility="RELIABLE", predictive_state="UNTESTED",
         queries=("PAGASA tropical cyclone bulletin", "nickel ore shipment Surigao monsoon",
                  "palay farmgate price weekly", "port cargo throughput Philippines"),
         notes="PAGASA's cyclone bulletins are the upstream of PH-K, which is a JOINT food and "
               "metals shock: the same weather system damages the rice crop and stops the ore "
               "barges. MGB's production data carries the monsoon seasonal that PH-F trades"),
    _src("PH-S10", "the source graph: registries and mirrors", layer="source_graph",
         roots=("https://data.gov.ph/", "https://data.worldbank.org/country/philippines",
                "https://comtradeplus.un.org/",
                "https://www.worldbank.org/en/topic/migrationremittancesdiasporaissues"),
         languages=("en",), licence="open data", access_label="OPEN_DATA",
         credibility="RELIABLE", predictive_state="NOT_PREDICTIVE",
         queries=("World Bank bilateral remittance matrix Philippines",
                  "Comtrade Philippines nickel ore China", "data.gov.ph catalogue"),
         notes="THE META LAYER, and it matters twice here: the World Bank's bilateral remittance "
               "matrix is the only source for CORRIDOR composition, and Chinese customs import "
               "data mirrors Philippine nickel ore exports with a different lag -- so the two "
               "together date the monsoon suppression better than either alone"),
    _src("PH-S11", "licensed price assessments and vendor data", layer="institutional",
         roots=("https://www.spglobal.com/commodityinsights/en/our-methodology/",
                "https://www.fastmarkets.com/methodology/"),
         languages=("en",), licence="methodology free; assessments licensed",
         access_label="LICENSED", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
         machine_use_allowed=True,
         notes="REGISTERED AND NOT SCRAPED. Assessed nickel ore CIF China prices would be the "
               "ideal input to PH-F and the terms forbid automated extraction. The free "
               "substitutes are MGB production, Philippine customs volume and Chinese port ore "
               "inventories, which is what PH-F actually uses and which lag by more"),
    _src("PH-S12", "unverified chatter and tip pages", layer="retail_ecology",
         roots=("https://www.facebook.com/groups/", "https://t.me/s/",
                "https://www.youtube.com/results?search_query="),
         languages=("en", "fil"), licence="public social; platform terms apply",
         access_label="PUBLIC_SOCIAL", credibility="FRINGE",
         predictive_state="NARRATIVE_FEATURE",
         queries=("sure ball stock pick", "peso babagsak", "bigas mag-i-shortage",
                  "insider tip PSE"),
         notes="FRINGE AND KEPT. Philippine rice-shortage rumour in particular is a genuine "
               "mechanism rather than noise: it drives household hoarding, which moves the retail "
               "price, which triggers the policy response PH-E is about. Low weight, FRINGE label "
               "attached, never promoted to a fact, never deleted"),
)

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("BSP monthly cash remittances", source="Bangko Sentral ng Pilipinas",
            coverage="1989-", frequency="monthly", publication_lag_days=45,
            revisions="routine prior-month revision", licence="free, public",
            history_from="1989-01-01", pit_feasible=True, assets=("USDSGD", "USDJPY"),
            mechanism_families=("remittance_flow", "seasonality"),
            how_to_fetch="the external statistics pages; THE LAG IS THE POINT -- December, the "
                         "largest print of the year, does not exist until mid-February, so a cell "
                         "that trades the December flow must trade the FORECAST and never the "
                         "print"),
    dataset("Philippine CPI and the rice sub-index",
            source="Philippine Statistics Authority", coverage="1994-", frequency="monthly",
            publication_lag_days=5, revisions="rare", licence="free, public",
            history_from="1994-01-01", pit_feasible=True, assets=("WHEAT", "CORN", "UST10Y"),
            mechanism_families=("inflation", "food_prices", "policy_reaction"),
            how_to_fetch="the PSA price indices page in the first week of the month; the RICE "
                         "line is the politically decisive series and is what triggers a tariff "
                         "or import-suspension decision"),
    dataset("Philippine merchandise trade with the electronics and mineral lines",
            source="Philippine Statistics Authority", coverage="1991-", frequency="monthly",
            publication_lag_days=40, revisions="routine", licence="free, public",
            history_from="1991-01-01", pit_feasible=True,
            assets=("XNIUSD", "XCUUSD", "NAS100"),
            mechanism_families=("trade_cycle", "commodity_exports"),
            how_to_fetch="the PSA trade releases; the forty-day lag makes this one of the slowest "
                         "trade prints in the region and it is rarely tradable on its own"),
    dataset("Mines and Geosciences Bureau nickel and copper production",
            source="Mines and Geosciences Bureau", coverage="2005-", frequency="quarterly",
            publication_lag_days=60, revisions="routine", licence="free, public",
            history_from="2005-01-01", pit_feasible=True, assets=("XNIUSD", "XCUUSD"),
            mechanism_families=("supply", "weather_seasonality"),
            how_to_fetch="the MGB statistics pages; the SEASONAL is the value here, and it can be "
                         "read from the quarterly pattern even though the level lags badly"),
    dataset("BSP gross international reserves", source="Bangko Sentral ng Pilipinas",
            coverage="1990-", frequency="monthly", publication_lag_days=7, revisions="rare",
            licence="free, public", history_from="1990-01-01", pit_feasible=True,
            assets=("USDSGD", "USDX"), mechanism_families=("intervention", "reserve_adequacy"),
            how_to_fetch="published on the 7th business day; the only quantitative record of "
                         "BSP participation in the currency market"),
    dataset("Bureau of the Treasury auction results and RTB offerings",
            source="Bureau of the Treasury", coverage="2010-",
            frequency="weekly auctions; RTB periodic", publication_lag_days=0,
            revisions="none", licence="free, public", history_from="2010-01-01",
            pit_feasible=True, assets=("UST10Y",),
            mechanism_families=("fiscal", "liquidity_drain"),
            how_to_fetch="the treasury site; an RTB offer period is a dated multi-week drain on "
                         "household bank deposits and is announced in advance"),
    dataset("PSE daily foreign flow", source="Philippine Stock Exchange", coverage="2005-",
            frequency="daily", publication_lag_days=0, revisions="none", licence="free, public",
            history_from="2005-01-01", pit_feasible=True, assets=("HK50", "US500"),
            mechanism_families=("flows", "risk_appetite"),
            how_to_fetch="the market information pages; published at the close, so it is knowable "
                         "for the next session only"),
    dataset("Philippine rice import volumes and tariff notifications",
            source="Bureau of Plant Industry and the Department of Agriculture",
            coverage="2019-", frequency="weekly import clearances; tariff changes episodic",
            publication_lag_days=7, revisions="routine", licence="free, public",
            history_from="2019-03-01", pit_feasible=True, assets=("WHEAT", "CORN"),
            mechanism_families=("food_imports", "commodity_policy"),
            how_to_fetch="the plant industry bureau publishes sanitary and phytosanitary import "
                         "clearances weekly; the series begins with the 2019 Rice Tariffication "
                         "Law and is short by construction"),
    dataset("World Bank bilateral remittance estimates", source="World Bank",
            coverage="1990-", frequency="annual", publication_lag_days=180,
            revisions="routine", licence="free, public", history_from="1990-01-01",
            pit_feasible=True, assets=("USDSGD", "USDJPY"),
            mechanism_families=("remittance_corridor",),
            how_to_fetch="the migration and remittances data portal; useful for CORRIDOR "
                         "composition -- which source countries -- and useless for timing"),
    dataset("BSP policy statements and the pre-decision economist survey",
            source="BSP and BusinessWorld", coverage="2002-", frequency="six to eight a year",
            publication_lag_days=0, revisions="none", licence="free, public",
            history_from="2002-01-01", pit_feasible=True, assets=("UST10Y", "USDSGD"),
            mechanism_families=("policy_event", "surprise"),
            how_to_fetch="the BSP statement at 07:00 UTC and the BusinessWorld survey published "
                         "days before it -- the survey is the closest thing to a consensus in a "
                         "market with no liquid rates derivative, so it is what a SURPRISE must "
                         "be measured against"),
    dataset("Philippine balance of payments position",
            source="Bangko Sentral ng Pilipinas", coverage="2005-", frequency="monthly",
            publication_lag_days=20, revisions="routine", licence="free, public",
            history_from="2005-01-01", pit_feasible=True, assets=("USDSGD", "USDX"),
            mechanism_families=("external_balance",),
            how_to_fetch="published about the 19th; the overall BOP position is the headline and "
                         "the current account detail arrives quarterly"),
    dataset("Philippine electronics and semiconductor exports",
            source="Philippine Statistics Authority and SEIPI", coverage="2000-",
            frequency="monthly", publication_lag_days=40, revisions="routine",
            licence="free, public", history_from="2000-01-01", pit_feasible=True,
            assets=("NAS100", "US500"), mechanism_families=("electronics_cycle",),
            how_to_fetch="the PSA trade release plus the industry association's commentary; "
                         "electronics are more than half of Philippine merchandise exports, which "
                         "is a higher share than most people expect of a services economy"),
)

# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor(
        "Overseas Filipino workers and their families",
        holds="the largest single source of Philippine foreign currency: above USD 34bn a year "
              "of cash remittances, close to a tenth of GDP",
        forced_to=("remit for family maintenance regardless of the exchange rate, because the "
                   "flow funds consumption and not investment",
                   "remit MORE before Christmas, which in the Philippines is a two-month "
                   "economic season",
                   "remit again in May and June for school enrolment"),
        when="a December peak that is the sharpest of any large remittance corridor, a secondary "
             "May-June bump, and a steady base through the year",
        information=("the peso rate, which they watch and which does accelerate discretionary "
                     "remittance",
                     "family cash needs, which do not respond to the rate at all"),
        constraints=("host-country employment conditions, above all in the Gulf",
                     "remittance transfer costs",
                     "deployment bans and host-country policy, which are political"),
        instruments=("USDSGD", "USDJPY"),
        counterparties=("Philippine banks and remittance operators", "recipient households",
                        "the BSP as the ultimate absorber"),
        observables=("the BSP monthly cash remittance series, with a forty-five-day lag",
                     "remittance operator volumes",
                     "the source-country breakdown"),
        impact="a large, stable, partly price-opportunistic inflow with a pronounced December "
               "seasonal, which is one reason peso depreciation episodes are truncated in the "
               "fourth quarter and resume in January",
        persistence="structural for decades; the CORRIDOR composition shifts slowly as "
                    "deployment patterns change, with the Gulf's share falling and North "
                    "America's and Japan's rising",
        falsifier="a December with remittance growth at or below the annual average, or a "
                  "depreciation episode in November-December with no acceleration in the flow"),
    actor(
        "Business-process outsourcing operators",
        holds="around USD 38bn a year of dollar revenue against a peso cost base of more than a "
              "million and a half salaries",
        forced_to=("convert dollars into pesos on the semi-monthly payroll convention -- the "
                   "15th and the end of the month -- because that is when wages are paid",
                   "hedge or not hedge a revenue stream contracted in dollars"),
        when="twice a month, on the 15th and the last working day, inside the 01:00-08:00 UTC "
             "onshore window",
        information=("their own contracted revenue", "client demand, which is US corporate "
                     "operating spending"),
        constraints=("client contracts denominated in dollars with fixed rates",
                     "a peso cost base that rises with domestic inflation",
                     "competition from India and from artificial intelligence displacing "
                     "voice work"),
        instruments=("USDSGD", "US500", "NAS100"),
        counterparties=("US and European corporate clients", "Philippine banks",
                        "their own employees"),
        observables=("the industry association's annual revenue and headcount figures",
                     "the services export line in the balance of payments",
                     "intraday peso flow patterns on the 15th and month end"),
        impact="a recurring, institutionally dated, twice-monthly conversion of several billion "
               "dollars a year -- the most concrete forced-flow calendar in this department, and "
               "one that nobody publishes because it is a labour convention rather than a market "
               "one",
        persistence="structural, with a live threat: automation of voice work is the single "
                    "largest risk to the Philippine external account and it is not cyclical",
        falsifier="no measurable difference in onshore peso flow or intraday behaviour between "
                  "the 15th and end of month and other days, measured across a full year"),
    actor(
        "The Bangko Sentral ng Pilipinas",
        holds="gross international reserves above USD 100bn and the overnight reverse repurchase "
              "rate",
        forced_to=("target inflation in a 2-4% band agreed with the government",
                   "temper peso volatility without defending a level, while the market treats "
                   "round numbers as lines",
                   "print at 07:00 UTC alongside up to three regional peers"),
        when="six to eight scheduled meetings a year at about 15:00 PHT, plus reserve-requirement "
             "changes announced with effect weeks ahead",
        information=("bank-level supervisory data", "the remittance series before publication",
                     "onshore interbank flow"),
        constraints=("the inflation target band",
                     "reserve adequacy in months of import cover",
                     "a rice-driven CPI it cannot influence with a rate"),
        instruments=("UST10Y", "USDSGD"),
        counterparties=("domestic banks", "the Treasury", "foreign investors"),
        observables=("the policy rate and the statement",
                     "the reserve requirement, cut repeatedly and by large steps",
                     "monthly reserves"),
        impact="a central bank whose largest inflation problem -- rice -- is immune to its "
               "instrument, which is why Philippine monetary policy has repeatedly been "
               "accompanied by trade policy and why a rate-only reaction function fits it badly",
        persistence="structural; the reserve requirement's role as a second instrument is "
                    "unusual and has been used aggressively",
        falsifier="a period in which the policy rate responds to a rice-driven CPI spike in the "
                  "same way it responds to a demand-driven one"),
    actor(
        "Philippine rice importers and the agriculture department",
        holds="the import programme of the world's LARGEST rice importer, four to five million "
              "tonnes a year",
        forced_to=("import because domestic production has not kept pace with population for "
                   "decades",
                   "buy mostly from Vietnam, which makes the Philippines Vietnam's largest rice "
                   "customer and creates a direct bilateral link",
                   "respond to a farmgate price collapse with an import suspension, and to a "
                   "retail price spike with a tariff cut -- opposite actions for the same "
                   "commodity"),
        when="continuous imports with a pre-harvest lull; policy changes arrive by administrative "
             "order with weeks of notice",
        information=("domestic retail and farmgate prices, published weekly",
                     "the Vietnamese export quote",
                     "the political calendar, because rice is the most politically sensitive "
                     "price in the country"),
        constraints=("the 2019 Rice Tariffication Law, which replaced quotas with a tariff",
                     "the tariff rate, cut from 35% to 15% in mid-2024",
                     "a 2025 import suspension imposed to defend farmgate prices",
                     "typhoon damage to the domestic crop"),
        instruments=("WHEAT", "CORN", "USDSGD"),
        counterparties=("Vietnamese and Thai exporters", "Filipino farmers", "consumers"),
        observables=("weekly import clearances", "the CPI rice sub-index",
                     "farmgate and retail price series", "the administrative orders themselves"),
        impact="the largest importer in the world market, which means a Philippine policy change "
               "is a demand shock to Vietnamese and Thai exporters and a direct link between "
               "this pack and both of theirs",
        persistence="structural; self-sufficiency has been a stated goal for fifty years and has "
                    "not been achieved",
        falsifier="a Philippine import suspension with no fall in the Vietnamese export quote "
                  "within a month"),
    actor(
        "Nickel ore miners in Surigao and Zambales",
        holds="the world's largest supply of direct-shipping nickel ore to China",
        forced_to=("STOP MINING when the northeast monsoon arrives, roughly October to March in "
                   "Surigao, because the pits and the barge loading are weather-exposed",
                   "ship to China, which is essentially the only buyer of ore rather than "
                   "processed nickel",
                   "compete with Indonesian ore that is banned from export, which is why "
                   "Philippine ore exists as a market at all"),
        when="a hard annual cycle: production and shipment concentrated from April to September, "
             "suppressed from October to March",
        information=("weather forecasts", "Chinese nickel pig iron margins",
                     "Indonesian quota decisions, which determine how much the world needs them"),
        constraints=("the monsoon, which is not negotiable",
                     "an on-and-off domestic debate about banning raw ore exports to force "
                     "downstream processing, mirroring Indonesia's policy",
                     "environmental permitting, which has been tightened and loosened with "
                     "administrations"),
        instruments=("XNIUSD",),
        counterparties=("Chinese nickel pig iron producers", "Indonesian competitors"),
        observables=("quarterly MGB production data",
                     "monthly ore export volumes in the trade data",
                     "Chinese port ore inventories",
                     "the rainfall record in Surigao"),
        impact="a WEATHER-DRIVEN annual supply seasonal in a market where the dominant producer "
               "manages supply by administrative quota -- so the Philippine seasonal is the one "
               "genuinely exogenous supply variation in the nickel balance",
        persistence="permanent, because it is the monsoon; the AMPLITUDE depends on how binding "
                    "Indonesian quotas are in a given year",
        falsifier="a year in which Philippine ore exports show no October-March suppression, or "
                  "a suppression that produces no response in the nickel price when Indonesian "
                  "supply is simultaneously constrained"),
    actor(
        "Copper and gold miners",
        holds="porphyry copper-gold deposits, several of them large and several of them stalled",
        forced_to=("sell concentrate abroad because domestic smelting capacity is limited",
                   "operate under a fiscal regime that was rewritten in 2024 after years of "
                   "uncertainty"),
        when="continuous, reported quarterly",
        information=("their own grades and reserves", "the copper and gold price"),
        constraints=("a mining fiscal regime that took years to settle",
                     "an open-pit mining ban that was imposed and then lifted",
                     "indigenous consent requirements and local permitting"),
        instruments=("XCUUSD", "XAUUSD"),
        counterparties=("Japanese and Chinese smelters", "gold refiners"),
        observables=("MGB quarterly production", "mineral export values",
                     "the fiscal regime legislation"),
        impact="a second mining channel whose POLICY history is the interesting part: the open-pit "
               "ban and its reversal are dated administrative supply shocks in a market where "
               "most supply news is geological",
        persistence="structural; the policy oscillation is the source of the variance",
        falsifier="a change in the mining fiscal or permitting regime with no measurable change "
                  "in announced project timelines over the following year"),
    actor(
        "Filipino households under the thirteenth-month pay statute",
        holds="a legally mandated extra month's salary payable by 24 December",
        forced_to=("receive it by the statutory deadline",
                   "spend it inside a Christmas season that begins in September"),
        when="the December payroll cycle, concentrated in the fortnight to 24 December",
        information=("the statutory deadline, which is universal knowledge",),
        constraints=("the statute itself, with penalties for late payment",),
        instruments=("USDSGD",),
        counterparties=("employers", "retailers", "the banking system"),
        observables=("December retail sales", "currency in circulation",
                     "the December CPI, which is seasonally distinct"),
        impact="the domestic counterpart of the remittance peak: two large flows land in the same "
               "fortnight and reinforce each other, which is why the Philippine December seasonal "
               "is sharper than any other in this department",
        persistence="statutory and permanent",
        falsifier="a December with no measurable spike in currency in circulation or retail "
                  "sales relative to the trailing three months"),
    actor(
        "Philippine oil importers",
        holds="the import book of an economy with almost no domestic crude and limited refining",
        forced_to=("buy refined product rather than crude, because refining capacity is small",
                   "pass prices through weekly, which the Philippines does more transparently "
                   "than most of its neighbours"),
        when="continuous, with weekly domestic price adjustments",
        information=("the Singapore MOPS assessments the domestic price formula uses",),
        constraints=("a deregulated downstream market with weekly pass-through",
                     "no meaningful subsidy buffer, unlike Indonesia and Malaysia"),
        instruments=("XBRUSD", "XTIUSD", "USDSGD"),
        counterparties=("Singapore traders and regional refiners", "domestic motorists"),
        observables=("weekly pump price adjustments",
                     "the oil line in the monthly trade data",
                     "the transport component of CPI"),
        impact="weekly pass-through means the Philippine CPI transmits an oil shock FASTER than "
               "any of its subsidised neighbours, which makes it the cleanest regional test of "
               "how quickly an oil move reaches consumer prices",
        persistence="structural since downstream deregulation",
        falsifier="an oil price move of more than 10% with no corresponding move in Philippine "
                  "pump prices within three weeks"),
    actor(
        "Foreign portfolio investors in the Philippine Stock Exchange",
        holds="a shrinking share of a market they have sold for years, with no liquid derivative "
              "to hedge in",
        forced_to=("rebalance as the Philippine weight in regional benchmarks falls",
                   "express a view in cash only, because the exchange has no liquid index future"),
        when="daily, published at the close",
        information=("index provider consultations", "the daily foreign flow report"),
        constraints=("foreign ownership limits written into the constitution for several sectors",
                     "index weights", "the absence of a hedging instrument"),
        instruments=("HK50", "US500"),
        counterparties=("domestic institutions and retail",),
        observables=("daily net foreign flow", "the PSEi's regional index weight",
                     "average daily turnover, which has fallen for years"),
        impact="without a derivative, foreign investors must trade the cash market to change "
               "exposure, so the flow series carries the WHOLE of their position change -- a "
               "cleaner signal than in markets where futures absorb most of it",
        persistence="the selling drift has been persistent enough to be structural",
        falsifier="a sustained period of net foreign buying with no change in index weights or "
                  "in earnings expectations"),
    actor(
        "The Bureau of the Treasury and the retail bond programme",
        holds="the domestic borrowing programme, including Retail Treasury Bonds sold directly "
              "to households",
        forced_to=("fund the deficit on a published auction calendar",
                   "market RTB offerings over multi-week periods, which pulls money out of bank "
                   "deposits"),
        when="weekly auctions; RTB offerings periodic and announced in advance",
        information=("its own cash position", "the tax calendar"),
        constraints=("the deficit target",
                     "a domestic investor base concentrated in banks and, increasingly, "
                     "households"),
        instruments=("UST10Y",),
        counterparties=("domestic banks", "retail investors", "foreign holders"),
        observables=("auction results and cut-offs", "RTB offer sizes and take-up",
                     "bank deposit growth during an offer period"),
        impact="an RTB offering is a dated, announced, multi-week drain on household bank "
               "deposits -- a liquidity event with a published calendar that has no analogue "
               "elsewhere in this department",
        persistence="a recurring programme rather than a one-off",
        falsifier="an RTB offer period with no measurable slowdown in bank deposit growth"),
    actor(
        "The Philippine electronics and semiconductor assembly sector",
        holds="more than half of Philippine merchandise exports, concentrated in assembly and "
              "test rather than fabrication",
        forced_to=("ship on the customer's schedule",
                   "compete with Vietnamese and Malaysian assembly on cost"),
        when="monthly, visible in trade data with a forty-day lag",
        information=("customer order books", "the global semiconductor cycle"),
        constraints=("a high import content, so gross exports overstate domestic value added",
                     "competition from lower-cost assembly locations",
                     "power costs, which are among the highest in the region"),
        instruments=("NAS100", "US500", "USDSGD"),
        counterparties=("US, Japanese and Taiwanese chipmakers",),
        observables=("the electronics export line", "industry association commentary",
                     "global chip billings"),
        impact="a larger share of merchandise exports than most people expect of a services "
               "economy, which means the Philippines carries a real technology-cycle beta "
               "alongside its remittance and BPO beta",
        persistence="structural but eroding as assembly migrates to lower-cost locations",
        falsifier="a quarter of falling Philippine electronics exports with rising Malaysian and "
                  "Vietnamese assembly exports and rising global chip billings"),
    actor(
        "The presidential proclamation power over the holiday calendar",
        holds="the legal authority to set, move and add national holidays by proclamation",
        forced_to=("issue the following year's holiday list by proclamation",
                   "move holidays to Mondays under the 'holiday economics' policy to create long "
                   "weekends",
                   "add ad hoc days at a few weeks' notice, including election days"),
        when="the annual proclamation, plus ad hoc additions through the year",
        information=("the political calendar", "tourism policy"),
        constraints=("statutory regular holidays that cannot be removed, only moved",
                     "labour law's different pay rules for regular holidays and special "
                     "non-working days"),
        instruments=("HK50", "USDSGD"),
        counterparties=("the exchange, which follows the proclamation", "employers", "workers"),
        observables=("the proclamation itself", "PSE holiday announcements"),
        impact="a Philippine holiday's WEEKDAY is a policy choice rather than a calendar fact, so "
               "any day-of-week statistic computed across this calendar carries a deliberate "
               "Monday bias that no other country in this department has",
        persistence="the proclamation power is statutory; the Monday-moving practice has been "
                    "applied inconsistently across administrations",
        falsifier="a year in which no holiday is moved from its statutory date"),
    actor(
        "The domestic banking system and the peso liquidity cycle",
        holds="the deposit base that funds government borrowing and absorbs remittances",
        forced_to=("meet a reserve requirement that the BSP has cut repeatedly and by large steps",
                   "fund an RTB offering's outflow",
                   "intermediate the remittance inflow into pesos"),
        when="continuous, with month-end and RTB-period concentrations",
        information=("their own deposit flows", "BSP supervisory guidance"),
        constraints=("the reserve requirement", "single-borrower limits",
                     "capital adequacy rules"),
        instruments=("UST10Y", "USDSGD"),
        counterparties=("depositors", "the Treasury", "the BSP"),
        observables=("deposit growth", "the reserve requirement ratio",
                     "domestic liquidity measures published monthly"),
        impact="the reserve requirement has been used as a genuine policy instrument here, not a "
               "technicality, so a Philippine liquidity model that reads only the policy rate is "
               "missing the lever that has moved most",
        persistence="structural; the reserve requirement's prominence is unusual and deliberate",
        falsifier="a large reserve requirement cut with no measurable change in domestic "
                  "liquidity or lending growth"),
    actor(
        "Typhoons and the agricultural supply shock",
        holds="an average of about twenty tropical cyclones entering Philippine waters each year, "
              "several of them landfalling in the rice belt",
        forced_to=("arrive in the June-to-November season",
                   "damage the crop in the months before harvest"),
        when="the typhoon season, concentrated July to October, overlapping the main rice harvest",
        information=("none -- this actor is the weather and has no intent",),
        constraints=("physical", "climate variability including El Nino and La Nina states"),
        instruments=("WHEAT", "CORN", "XNIUSD"),
        counterparties=("farmers", "rice importers, whose demand rises after damage",
                        "the mining sector, whose operations also stop"),
        observables=("PAGASA cyclone tracks and warnings",
                     "agriculture department damage assessments",
                     "the subsequent import clearance volume"),
        impact="the supply shock that turns a normal import programme into an emergency one, and "
               "the same weather system that suppresses nickel ore shipment -- so a Philippine "
               "typhoon is simultaneously a food-import and a metals-supply event",
        persistence="permanent and climatological, with a trend in intensity",
        falsifier="a major landfalling typhoon in the rice belt with no subsequent increase in "
                  "import clearances or in the CPI rice sub-index"),
)

# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("PH-A", "BSP policy decisions in a four-central-bank hour",
           objects=("six to eight scheduled decisions a year at 07:00 UTC",
                    "the reserve requirement as a second and heavily used instrument",
                    "the BusinessWorld pre-decision economist survey",
                    "the 2-4% inflation target band"),
           conditions=("how many of Malaysia, Indonesia and Thailand print in the same hour",
                       "whether the CPI shock is rice-driven, which the rate cannot address",
                       "whether a reserve requirement change is announced alongside"),
           instruments=("UST10Y", "USDSGD", "HK50"),
           controls=("days when the BSP alone prints at 07:00 UTC versus days when two or more "
                     "regional banks do",
                     "the same statistic at 07:00 UTC on non-decision days",
                     "rice-driven versus demand-driven CPI episodes, since the mechanism says "
                     "the reaction must differ and a constant response falsifies it"),
           notes="the economist survey is the only available consensus because there is no liquid "
                 "rates derivative, so a SURPRISE here is measured against a published poll "
                 "rather than against a market price -- a weaker instrument, and it must be "
                 "said so"),
    domain("PH-B", "Peso smoothing and the psychological-level regime",
           objects=("BSP participation, framed publicly as tempering volatility",
                    "monthly gross international reserves and months of import cover",
                    "the round numbers the market has repeatedly treated as lines",
                    "the thin offshore NDF and its basis to the onshore rate"),
           conditions=("the distance of the rate from the nearest round number",
                       "whether reserves are falling against the stated adequacy threshold",
                       "whether the pressure is remittance-seasonal or oil-import driven"),
           instruments=("USDSGD", "USDIDR", "USDX"),
           controls=("USDIDR and USDTHB over the same period, two managed currencies whose "
                     "central banks state their objectives differently, so a common move is a "
                     "dollar move and not a Philippine one",
                     "a round-number placebo at levels the market has never treated as a line, "
                     "which must show no clustering if the psychological claim is real",
                     "valuation-adjusted reserves, since a reserve fall driven by revaluation is "
                     "not intervention"),
           notes="the BSP denies defending a level and the market prices one anyway; the "
                 "round-number placebo is the only way to tell an actual reaction function from "
                 "a self-fulfilling convention, and it is cheap to run"),
    domain("PH-C", "Remittance seasonality and a forty-five-day publication lag",
           objects=("the December remittance peak",
                    "the May-June enrolment bump",
                    "the source-country corridor composition",
                    "the BSP monthly series and its lag"),
           conditions=("whether the peso is weak, which accelerates discretionary remittance",
                       "Gulf employment conditions",
                       "the month, since this is a seasonal domain by construction"),
           instruments=("USDSGD", "USDJPY"),
           controls=("the Indian remittance corridor, the other large one, which shares the "
                     "mechanism and has a different seasonal shape",
                     "a lag-aware backtest: the December print does not exist until mid-February, "
                     "so a cell must trade the FORECAST and the difference between the two is "
                     "the whole test",
                     "tourism receipts as a services placebo with no level opportunism"),
           notes="THE PIT TRAP OF THIS PACK. The most important series has the worst lag, and a "
                 "seasonal cell built on the reference month rather than the publication date "
                 "trades a number that did not exist"),
    domain("PH-D", "The semi-monthly BPO payroll conversion",
           objects=("the 15th and the last working day of each month",
                    "dollar revenue converted into peso wages",
                    "the services export line in the balance of payments",
                    "intraday onshore flow on those dates"),
           conditions=("whether the date falls on a weekend or a holiday and shifts",
                       "month end, which coincides with the second conversion and with corporate "
                       "translation demand"),
           instruments=("USDSGD", "US500"),
           controls=("the 14th and 16th as within-month placebos",
                     "months in which the 15th fell at a weekend and the payroll shifted, a "
                     "natural experiment the calendar provides free",
                     "Indian IT exporters, the competing industry, which pays MONTHLY and "
                     "therefore should show no semi-monthly pattern"),
           notes="the Indian control is the sharp one: the same industry, the same dollar "
                 "revenue, a different payroll convention. If a semi-monthly effect appears in "
                 "both, it is not a payroll effect"),
    domain("PH-E", "Rice imports, the tariff and the world's largest buyer",
           objects=("weekly import clearances",
                    "the 2019 tariffication law, the 2024 tariff cut and the 2025 suspension",
                    "the CPI rice sub-index",
                    "farmgate versus retail prices, which the policy oscillates between"),
           conditions=("whether the policy is defending consumers or farmers, which are opposite "
                       "actions",
                       "typhoon damage to the domestic crop",
                       "the Vietnamese export quote"),
           instruments=("WHEAT", "CORN", "USDSGD"),
           controls=("the Vietnamese and Thai export quotes, which must move if the Philippines "
                     "is genuinely the marginal buyer",
                     "Indonesian rice policy over the same period, the other large Asian importer",
                     "wheat and corn as the non-rice grain control, since a rice-specific shock "
                     "should NOT move them and a common move identifies a general food factor"),
           notes="no rice instrument exists in this universe, so every claim terminates in WHEAT "
                 "or CORN and the substitution is the hypothesis rather than a convenience -- "
                 "the same honesty MY-F applies to palm and soy"),
    domain("PH-F", "The monsoon-driven nickel ore seasonal",
           objects=("the October-to-March suppression of Surigao shipments",
                    "quarterly MGB production", "monthly ore export volumes",
                    "Chinese port ore inventories"),
           conditions=("how binding Indonesian RKAB quotas are that year, which sets how much "
                       "the world needs Philippine ore",
                       "the strength of the northeast monsoon",
                       "whether a domestic ore export ban is being debated"),
           instruments=("XNIUSD", "XCUUSD"),
           controls=("copper, which shares the industrial metal factor and has NO Philippine "
                     "weather seasonal",
                     "Indonesian supply, which must be controlled for because it dominates the "
                     "balance",
                     "the same calendar months in years when Indonesian quotas were loose, where "
                     "the Philippine swing should matter less"),
           notes="the one genuinely EXOGENOUS supply variation in the nickel balance: the "
                 "dominant producer manages supply by administrative quota and the swing "
                 "supplier is governed by the rain"),
    domain("PH-G", "Oil imports with weekly pass-through",
           objects=("weekly domestic pump price adjustments",
                    "the oil line in the trade data",
                    "the transport component of CPI"),
           conditions=("the Singapore MOPS assessment the formula uses",
                       "the absence of a subsidy buffer, unlike Indonesia and Malaysia"),
           instruments=("XBRUSD", "XTIUSD", "USDSGD"),
           controls=("Indonesian and Malaysian pump prices over the same period, both subsidised "
                     "and administratively set, which should show a SLOWER and smaller "
                     "pass-through",
                     "the lag structure itself: weekly here against monthly or discretionary "
                     "there"),
           notes="the Philippines is the cleanest regional test of how fast an oil move reaches "
                 "consumer prices, precisely because nothing buffers it"),
    domain("PH-H", "PSE foreign flow without a hedging instrument",
           objects=("daily net foreign flow",
                    "the absence of a liquid index derivative",
                    "the PSEi's falling regional index weight",
                    "average daily turnover, which has declined for years"),
           conditions=("index review dates",
                       "whether the flow is above or below its negative multi-year mean"),
           instruments=("HK50", "US500"),
           controls=("Thai and Indonesian foreign equity flow, which share the regional factor "
                     "and DO have hedging instruments -- the difference isolates the effect of "
                     "having no future to trade",
                     "the series de-meaned, since the unconditional expectation is negative"),
           notes="with no derivative, the cash flow carries the WHOLE position change rather than "
                 "the residual after futures, which should make it a cleaner signal than its "
                 "regional peers -- that is the testable claim"),
    domain("PH-I", "Retail Treasury Bonds as a dated liquidity drain",
           objects=("RTB offer periods and their sizes",
                    "bank deposit growth during an offer",
                    "the weekly auction calendar"),
           conditions=("the size of the offering relative to the deposit base",
                       "whether the offer spans a month end",
                       "the level of domestic rates, which drives household take-up"),
           instruments=("UST10Y",),
           controls=("comparable weeks with no RTB offering",
                     "regional government bond auctions, which are institutional and do not "
                     "touch household deposits -- the mechanism here is RETAIL and that is the "
                     "distinguishing feature"),
           notes="a multi-week, announced, household-facing liquidity drain with a published "
                 "calendar has no analogue elsewhere in this department"),
    domain("PH-J", "A holiday calendar set by proclamation",
           objects=("regular holidays and special non-working days, which have different pay "
                    "rules",
                    "the 'holiday economics' practice of moving holidays to Mondays",
                    "ad hoc proclamations including election days",
                    "the thinning of the market through the last fortnight of December"),
           conditions=("whether a holiday has been moved from its statutory date",
                       "whether the region is simultaneously shut, as at Chinese New Year"),
           instruments=("HK50", "USDSGD"),
           controls=("the STATUTORY date against the OBSERVED date for every moved holiday, "
                     "which is the control the proclamation power makes necessary",
                     "regional markets on the same dates, since the Philippines observes Chinese "
                     "New Year as a special day and most of its statutory calendar is unique"),
           notes="because the weekday of a Philippine holiday is a policy choice, a day-of-week "
                 "statistic across this calendar carries a deliberate Monday bias; the statutory "
                 "versus observed control is not optional here"),
    domain("PH-K", "Typhoons as a joint food and metals supply shock",
           objects=("cyclone tracks and landfalls in the rice belt",
                    "agriculture damage assessments",
                    "the simultaneous suppression of mining and barge loading",
                    "the subsequent import clearance volume"),
           conditions=("El Nino or La Nina state",
                       "whether landfall is in the rice belt or in the mining provinces",
                       "the point in the harvest cycle"),
           instruments=("WHEAT", "CORN", "XNIUSD"),
           controls=("Vietnamese typhoon landfalls on the same weather systems, which affect a "
                     "rice EXPORTER rather than an importer and should move the price the same "
                     "way through a different channel",
                     "cyclones that stay offshore, the natural placebo the weather provides",
                     "the mining-province versus rice-belt split, since the two channels should "
                     "separate cleanly"),
           notes="the same weather system moves a food import and a metal export, which is a "
                 "genuinely joint shock and is why this is one domain rather than two"),
    domain("PH-L", "How much of a Philippine move survives into a tradable symbol",
           objects=("the correlation of the onshore peso with USDSGD, USDTHB, USDIDR and USDCNH",
                    "the peso's own drivers, which are remittance and BPO flows the neighbours "
                    "do not share",
                    "the thin offshore NDF"),
           conditions=("whether the Philippine shock is commodity-driven, which the neighbours "
                       "share, or labour-flow-driven, which they do not",
                       "the regional risk regime"),
           instruments=("USDSGD", "USDTHB", "USDIDR", "USDCNH"),
           controls=("the dollar factor residualised out first",
                     "USDHKD as a null proxy: a pegged currency should carry NONE of the "
                     "Philippine signal, and if it does the measurement is a dollar artefact",
                     "a driver split: a remittance-driven peso move is UNIQUELY Philippine and "
                     "should survive into the proxies LESS well than a commodity-driven one, "
                     "which is a sharp and testable prediction"),
           notes="THE HONEST DOMAIN, and the driver split is what makes it more than a correlation "
                 "exercise: the mechanism predicts WHICH kinds of Philippine shocks transmit and "
                 "which do not"),
)

# --------------------------------------------------------------------------- miners (specs)
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("ph_remittance_lag_honest", domain_ids=("PH-C",), kind="macro",
          entry="research.countries.ph.miners:remittance_lag_honest", cadence_s=604800.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Stamps every remittance observation on its PUBLICATION date "
                "and refuses any cell that references the reference month, because the December "
                "peak does not exist until mid-February"),
    miner("ph_payroll_clock", domain_ids=("PH-D",), kind="calendar",
          entry="research.countries.ph.miners:payroll_clock", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Runs the 14th and 16th placebos and the Indian monthly-"
                "payroll control before reporting any semi-monthly effect"),
    miner("ph_rice_policy_shock", domain_ids=("PH-E",), kind="event",
          entry="research.countries.ph.miners:rice_policy_shock", cadence_s=3600.0,
          notes="SPEC, NOT YET WIRED. Joins Philippine administrative orders to the Vietnamese "
                "export quote, which is the direct bilateral link to the VN pack"),
    miner("ph_nickel_monsoon", domain_ids=("PH-F",), kind="seasonality",
          entry="research.countries.ph.miners:nickel_monsoon", cadence_s=604800.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Conditions the Philippine ore seasonal on how binding "
                "Indonesian RKAB quotas are, because the swing supplier only matters when the "
                "dominant one is constrained"),
    miner("ph_oil_passthrough", domain_ids=("PH-G",), kind="macro",
          entry="research.countries.ph.miners:oil_passthrough", cadence_s=604800.0,
          notes="SPEC, NOT YET WIRED. Compares weekly Philippine pass-through against subsidised "
                "Indonesian and Malaysian pass-through as the regional control"),
    miner("ph_rtb_liquidity", domain_ids=("PH-I",), kind="flow",
          entry="research.countries.ph.miners:rtb_liquidity", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Measures deposit growth during an RTB offer period against "
                "comparable weeks with no offering"),
    miner("ph_proclamation_calendar", domain_ids=("PH-J",), kind="calendar",
          entry="research.countries.ph.miners:proclamation_calendar", cadence_s=86400.0,
          steerable=False,
          notes="SPEC, NOT YET WIRED. Keeps the STATUTORY and the OBSERVED date for every moved "
                "holiday, without which a Philippine day-of-week statistic is contaminated"),
    miner("ph_typhoon_joint_shock", domain_ids=("PH-K",), kind="event",
          entry="research.countries.ph.miners:typhoon_joint_shock", cadence_s=86400.0,
          notes="SPEC, NOT YET WIRED. Splits landfalls by province into the rice-belt and "
                "mining-province channels and uses offshore cyclones as the placebo"),
    miner("ph_proxy_survival", domain_ids=("PH-L",), kind="transmission",
          entry="research.countries.ph.miners:proxy_survival", cadence_s=3600.0, steerable=False,
          notes="SPEC, NOT YET WIRED. Splits Philippine shocks into commodity-driven and "
                "labour-flow-driven before measuring survival into each proxy, with USDHKD as "
                "the null"),
)

# --------------------------------------------------------------------------- transmission seeds
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("PH-E01", source="the Philippine northeast monsoon suppressing Surigao ore shipments",
         mechanism="the world's largest supplier of direct-shipping nickel ore stops for the "
                   "rain from roughly October to March, which is the only genuinely exogenous "
                   "supply variation in a market whose dominant producer manages supply by quota",
         targets=("XNIUSD",), sign="+", horizon="1 to 4 months",
         lag="30 days on the export data; the weather itself is observable in real time",
         control="copper, which shares the industrial-metal factor and has no Philippine weather "
                 "seasonal; and Indonesian quota tightness, which determines whether the swing "
                 "supplier matters at all that year",
         notes="FALSIFIER: a year with no October-March suppression in Philippine ore exports, or "
               "a suppression that produces no nickel response while Indonesian supply is also "
               "constrained. THE PACK'S SHARPEST EDGE"),
    edge("PH-E02", source="a Philippine rice import suspension or tariff change",
         mechanism="the world's largest rice importer changing its demand by administrative order "
                   "is a demand shock to Vietnamese and Thai exporters",
         targets=("WHEAT", "CORN"), sign="-", horizon="1 to 3 months",
         lag="0 at the administrative order; weekly on import clearances",
         control="the Vietnamese and Thai export quotes, which must move if the Philippines is "
                 "genuinely the marginal buyer; and wheat and corn as the non-rice grain control",
         notes="FALSIFIER: a Philippine import suspension with no fall in the Vietnamese export "
               "quote within a month. No rice contract exists here, so the grain leg is the "
               "hypothesis and not a convenience"),
    edge("PH-E03", source="a landfalling typhoon in the Philippine rice belt",
         mechanism="crop damage converts a normal import programme into an emergency one, and the "
                   "same weather system suppresses ore shipment from the mining provinces",
         targets=("WHEAT", "CORN", "XNIUSD"), sign="+", horizon="1 to 3 months",
         lag="7 days on damage assessments; 30 days on import clearances",
         control="cyclones that stay offshore as the natural placebo, and a rice-belt versus "
                 "mining-province landfall split, since the two channels must separate",
         notes="FALSIFIER: a major rice-belt landfall with no subsequent rise in import "
               "clearances or in the CPI rice sub-index"),
    edge("PH-E04", source="the December remittance and thirteenth-month-pay fortnight",
         mechanism="the sharpest December seasonal of any large remittance corridor, reinforced "
                   "by a statutory domestic bonus payable by 24 December",
         targets=("USDSGD", "USDJPY"), sign="-", horizon="the fourth quarter",
         lag="45 days on the published series; the STATUTORY dates are known years ahead",
         control="the Indian remittance corridor, which shares the mechanism with a different "
                 "seasonal shape; and a lag-aware backtest that trades the forecast rather than "
                 "the print",
         notes="FALSIFIER: a December with remittance growth at or below the annual average. "
               "A cell that references the reference month rather than the publication date is "
               "trading a number that did not exist and is refused"),
    edge("PH-E05", source="the semi-monthly BPO payroll conversion on the 15th and month end",
         mechanism="several billion dollars a year of outsourcing revenue converted into peso "
                   "wages twice a month on dates set by labour convention and not by markets",
         targets=("USDSGD",), sign="-", horizon="intraday to 2 sessions",
         lag="0 -- the dates are a convention, known indefinitely in advance",
         control="the 14th and 16th as within-month placebos; months when the 15th fell at a "
                 "weekend and the payroll shifted; and Indian IT exporters, the competing "
                 "industry, which pays MONTHLY",
         notes="FALSIFIER: a semi-monthly effect appearing in the Indian corridor too, which "
               "would mean it is not a payroll effect. The most concrete forced-flow calendar in "
               "this department"),
    edge("PH-E06", source="the BSP policy decision at 07:00 UTC",
         mechanism="up to four Southeast Asian central banks print in the same hour; the "
                   "Philippine decision reaches the regional complex through the rate "
                   "differential and through the reserve requirement",
         targets=("UST10Y", "USDSGD", "USDIDR"), sign="-", horizon="0 to 3 sessions", lag="0",
         control="days when the BSP alone prints at 07:00 UTC versus days when two or more "
                 "regional banks do; and rice-driven versus demand-driven CPI episodes",
         notes="FALSIFIER: an identical response whether the BSP prints alone or alongside its "
               "peers. The surprise must be measured against the BusinessWorld economist survey, "
               "which is a weaker instrument than a market price and is named as such"),
    edge("PH-E07", source="Philippine copper and gold mining policy changes",
         mechanism="an open-pit ban, its reversal and a rewritten fiscal regime are dated "
                   "administrative supply shocks in a market where most supply news is geological",
         targets=("XCUUSD", "XAUUSD"), sign="+", horizon="1 to 4 quarters",
         lag="0 at the legislation; 60 days on production data",
         control="Peruvian and Chilean policy events over the same period, larger producers whose "
                 "administrative shocks must dominate if the channel is policy rather than "
                 "Philippine",
         notes="FALSIFIER: no measurable change in announced project timelines after a fiscal or "
               "permitting change, which would mean the policy is not binding"),
    edge("PH-E08", source="Philippine weekly fuel price pass-through",
         mechanism="a deregulated downstream market with weekly adjustments and no subsidy buffer "
                   "transmits an oil move to consumer prices faster than any of its neighbours",
         targets=("XBRUSD", "XTIUSD"), sign="+", horizon="1 to 3 weeks", lag="7 days",
         control="Indonesian and Malaysian pump prices, both administratively set and subsidised, "
                 "which must show a slower and smaller pass-through",
         notes="FALSIFIER: an oil move above 10% with no Philippine pump price response within "
               "three weeks, or a pass-through no faster than the subsidised neighbours"),
    edge("PH-E09", source="Philippine electronics and semiconductor assembly exports",
         mechanism="more than half of merchandise exports are electronics, which gives a services "
                   "economy a real technology-cycle beta",
         targets=("NAS100", "US500"), sign="+", horizon="1 to 2 quarters", lag="40 days",
         control="Malaysian and Vietnamese assembly exports on the same dates, which carry the "
                 "same cycle and must absorb the signal if the Philippines carries none of its own",
         notes="FALSIFIER: no incremental content once Malaysia and Vietnam are in the model, "
               "which is the likely outcome given the forty-day publication lag"),
    edge("PH-E10", source="a Retail Treasury Bond offer period",
         mechanism="a multi-week, announced, household-facing offering drains bank deposits on a "
                   "published calendar",
         targets=("UST10Y",), sign="+", horizon="the offer period and the month after",
         lag="0 -- announced in advance",
         control="comparable weeks with no offering, and regional institutional bond auctions, "
                 "which do not touch household deposits",
         notes="FALSIFIER: an RTB offer period with no measurable slowdown in deposit growth"),
    edge("PH-E11", source="PSE net foreign flow",
         mechanism="with no liquid index derivative, cash flow carries the WHOLE foreign position "
                   "change rather than the residual after futures",
         targets=("HK50", "US500"), sign="+", horizon="1 to 5 sessions", lag="0 at the close",
         control="Thai and Indonesian foreign equity flow, which share the regional factor and DO "
                 "have hedging instruments; and the series de-meaned, since the unconditional "
                 "expectation is negative",
         notes="FALSIFIER: Philippine flow carrying no more information than Thai or Indonesian "
               "flow of the same size, which would falsify the no-derivative claim"),
    edge("PH-E12", source="a labour-flow-driven versus commodity-driven Philippine shock",
         mechanism="a remittance or BPO shock is UNIQUELY Philippine and should transmit into the "
                   "regional proxies far less well than a commodity or risk shock, which the "
                   "neighbours share",
         targets=("USDSGD", "USDTHB", "USDIDR"), sign="0", horizon="1 to 10 sessions", lag="0",
         control="USDHKD as the null proxy, which is pegged and must carry NONE of the signal; "
                 "and the dollar factor residualised out first",
         notes="FALSIFIER: equal transmission of labour-flow and commodity shocks, which would "
               "mean the proxies are carrying a common factor and nothing Philippine. Unsigned: "
               "the claim is about DIFFERENTIAL transmission, not direction"),
    edge("PH-E13", source="the Philippine CPI rice sub-index",
         mechanism="the politically decisive price in the country, and the trigger for the tariff "
                   "and import-suspension decisions that move the world rice market",
         targets=("WHEAT", "CORN", "UST10Y"), sign="+", horizon="1 to 3 months", lag="5 days",
         control="the non-rice CPI, which isolates the food channel from general inflation; and "
                 "Indonesian and Vietnamese rice CPI over the same period",
         notes="FALSIFIER: a rice CPI spike with no policy response within a quarter, which would "
               "break the chain from price to policy to world market"),
    edge("PH-E14", source="Philippine holiday proclamations that move a statutory date",
         mechanism="the weekday of a Philippine holiday is a policy choice, so the observed "
                   "closure calendar diverges from the statutory one in a way no other country "
                   "here does",
         targets=("HK50", "USDSGD"), sign="0", horizon="the closure and the session after",
         lag="0 -- proclaimed weeks to a year ahead",
         control="the STATUTORY date against the OBSERVED date for every moved holiday, which is "
                 "the control the proclamation power makes necessary",
         notes="FALSIFIER: identical behaviour on statutory and observed dates, which would mean "
               "the proclamation has no market effect and the contamination concern is moot. "
               "Unsigned: this is a calendar-integrity check, not a directional claim"),
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("PH-R1", start="2010-01-01", end="2019-02-28",
        label="the rice quota era",
        what_changed="rice imports were controlled by a National Food Authority quota rather "
                     "than a tariff, so the Philippines' demand on the world market was an "
                     "administrative decision with no price mechanism at all",
        invalidates="a price-responsive import model fitted here is fitted on a quota; the "
                    "elasticity of Philippine demand to the world price is essentially zero in "
                    "this era and non-zero afterwards",
        notes="the pre-tariffication baseline for PH-E"),
    era("PH-R2", start="2019-03-01", end="2022-12-31",
        label="rice tariffication and the pandemic",
        what_changed="the Rice Tariffication Law replaced the quota with a 35% tariff and "
                     "liberalised private imports; the pandemic then collapsed both remittances "
                     "and BPO office work simultaneously before both recovered",
        invalidates="two regime changes inside one era -- a trade liberalisation and a pandemic "
                    "-- so a cell spanning it must say which it is about",
        notes="remittances proved far more resilient through the pandemic than forecasts assumed, "
              "which is itself evidence about the flow's price and income elasticity"),
    era("PH-R3", start="2023-01-01", end="2024-06-30",
        label="the inflation spike and aggressive tightening",
        what_changed="a rice and food driven inflation spike took CPI well above the target band "
                     "and the BSP tightened hard into a shock its instrument could not address",
        invalidates="a reaction-function estimate from this era is estimating a central bank "
                    "responding to a supply shock with a demand instrument, which is not the "
                    "same object as normal policy",
        notes="the clearest available evidence for PH-A's rice-versus-demand control"),
    era("PH-R4", start="2024-07-01", end="2025-08-31",
        label="the tariff cut and the easing cycle",
        what_changed="the rice tariff was cut from 35% to 15% in mid-2024 to break the food "
                     "inflation, the BSP began easing, and the reserve requirement was cut by "
                     "large steps",
        invalidates="the food CPI series has an administrative STEP in it from the tariff cut, "
                    "so an inflation model fitted through it is fitting a trade policy decision",
        notes="two instruments moving at once -- the policy rate and the reserve requirement -- "
              "which makes attribution to either difficult"),
    era("PH-R5", start="2025-09-01", end=None,
        label="import suspension and the farmer-versus-consumer reversal",
        what_changed="rice imports were suspended to defend collapsing farmgate prices, which is "
                     "the OPPOSITE policy to the 2024 tariff cut for the same commodity inside "
                     "eighteen months",
        invalidates="the sign of the policy reaction reversed; a rice policy model fitted on the "
                    "2024 direction predicts exactly the wrong action here, which is why PH-E "
                    "conditions on WHICH constituency the policy is defending",
        notes="the current regime and what a live candidate is actually trading"),
)

# --------------------------------------------------------------------------- assembly
MISSION = (
    "mine the Philippines to exhaustion on the most institutionally dated forced flows in this "
    "department -- a December remittance peak reinforced by a statutory bonus, a semi-monthly BPO "
    "payroll conversion, the world's largest rice import programme, and a nickel ore seasonal "
    "governed by the monsoon -- none of which can be traded in the peso, because USDPHP is not on "
    "this broker's registry, and all of which reach symbols that are")
NOTES = (
    "NO PHILIPPINE INSTRUMENT IS EXECUTABLE. USDPHP, the PSEi, the BAP reference rate, the RTB "
    "programme and every Philippine rice or nickel contract are named in this module's "
    "TRANSMISSION_TARGETS. The BSP remittance series has a forty-five-day lag and the December "
    "peak does not exist until mid-February, which is the point-in-time trap of this pack; the "
    "BAP reference rate is published after the session it describes, which is the other one.")


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
    """The Philippines' pack: `CountryPack` when the framework has landed, else the same fields as
    a dict."""
    return build_pack(**fields())
