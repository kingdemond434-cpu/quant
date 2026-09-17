"""GEORGIA: published remittances, auctioned interventions, and a country that is mostly a pipe.

WHAT GEORGIA IS AS A MARKET MECHANISM. Four things belong to this economy and to no other in the
desk's book:

  1. THE HOUSEHOLD FLOW IS PUBLISHED, MONTHLY, BY ORIGIN COUNTRY. The National Bank publishes
     money transfers into Georgia split by sending country, free, on a fixed calendar. In an
     economy this small that flow is a large share of external receipts, and the 2022-2023 surge
     in transfers from Russia is the single largest identified shock in the series. Most packs in
     this department must INFER a flow from a price; Georgia publishes the flow. GE-C is built on
     that and is the pack's flagship domain.

  2. INTERVENTION IS A PUBLIC AUCTION WITH A PUBLISHED RESULT. The National Bank buys and sells
     on the trading platform through announced auctions and publishes the volume the same day. A
     central bank whose intervention is a dated, sized, public event -- rather than a residual
     inferred from monthly reserve changes -- is rare and is worth a domain of its own.

  3. THE COUNTRY IS A PIPE, AND THAT LINKS THREE OTHER PACKS. BTC crude and the Southern Gas
     Corridor cross Georgia from Azerbaijan to Turkey; the Middle Corridor freight route runs
     through it from the Caspian. Georgian transit is where the Azerbaijani, Turkish and Kazakh
     packs physically meet, and a disruption in Georgia is a supply event for all three.

  4. TOURISM AND CAR RE-EXPORT ARE THE OTHER EXTERNAL LEGS. Both are monthly, both published, and
     both re-based completely between 2020 and 2023 -- so any pooled seasonal across that window
     is meaningless and GE-E splits it explicitly.

WHAT IS EXECUTABLE. Nothing Georgian. GEL is ABSENT from `data/universe/universe.json`, as are
the Georgian Stock Exchange and every Georgian bond. This pack is TRANSMISSION-ONLY by
construction: every domain terminates in USDTRY, USDRUB, XBRUSD, XNGUSD, XCUUSD, XAUUSD or
USDCNH, and that is stated once here and enforced in every instrument tuple below.

THE CALENDAR IS ORTHODOX AND THE CLOCK DOES NOT MOVE. Georgia keeps Christmas on 7 January and
Easter on the Julian reckoning: 2026 Orthodox Easter is 12 April against the Western 5 April, a
week apart. Tbilisi is UTC+4 with no seasonal change, so Georgian event minutes in UTC are stable
all year -- one of only three countries in this department where that is true.

LANGUAGES. Georgian is the language of the primary sources and uses its own script, which no
Latin- or Cyrillic-trained screen will match. Russian is the working language of much of the
practitioner web and of the remittance corridor itself. Both are in `TERMINOLOGY`.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

# ruff: noqa: RUF001
# RUF001 flags Cyrillic characters that resemble Latin ones. The rule guards IDENTIFIERS
# against homoglyph attacks; this file carries Georgian and Russian terminology as DATA,
# because a screen that cannot match მონეტარული or денежные переводы cannot find the
# National Bank's own headline. No identifier in this module is non-ASCII.

# --------------------------------------------------------------------------- identity
CODE = "GE"
NAME = "Georgia"
REGION_COMMAND = "russia_cis"
REGION_DESK = "CAUCASUS"
CURRENCY = "GEL"
FISCAL_YEAR_END = "12-31"
NATIVE_LANGUAGES: tuple[str, ...] = ("ka", "ru")

#: TRANSMISSION-ONLY. No Georgian instrument is quoted here; every symbol is a foreign one a
#: Georgian mechanism reaches. Nothing here is an equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDTRY",                      # Turkey is the largest trade partner and the BTC terminus
    "USDRUB",                      # the remittance and re-export corridor
    "XBRUSD", "XTIUSD",            # BTC transit crude
    "XNGUSD",                      # the Southern Gas Corridor transit
    "XCUUSD",                      # RMG copper concentrate, the largest mineral export
    "XAUUSD", "XAGUSD",            # NBG reserves and the regional safe-haven reflex
    "USDCNH",                      # the Middle Corridor freight link
    "WHEAT",                       # a wheat importer: the food-price channel runs the other way
    "USDX", "EURUSD",              # the dollar factor and the EU trade agreement
    "EUSTX50", "GER40",            # the European end of the transit corridor
    "US500", "UST10Y",             # global risk and duration controls
)

#: Everything Georgian. Each names the universe symbols its mechanism reaches.
TRANSMISSION_TARGETS: tuple[dict[str, Any], ...] = (
    {"name": "USDGEL (ლარი / lari)", "venue": "interbank and the NBG trading platform",
     "why": "ABSENT from data/universe/universe.json. The lari is a freely floating currency in a "
            "very small open economy, driven by remittances, tourism and transit rather than by "
            "a commodity",
     "proxies": ("USDTRY", "USDRUB", "XBRUSD")},
    {"name": "NBG monetary policy rate (მონეტარული პოლიტიკის განაკვეთი)", "venue": "NBG",
     "why": "the policy rate; no Georgian rate instrument is quoted here",
     "proxies": ("USDTRY", "USDRUB")},
    {"name": "NBG money transfers by sending country (ფულადი გზავნილები)", "venue": "NBG",
     "why": "THE PACK'S FLAGSHIP SERIES: a monthly, free, country-split household flow into a "
            "small open economy. The 2022-2023 Russian surge is the largest identified shock in it",
     "proxies": ("USDRUB", "USDTRY")},
    {"name": "NBG FX auctions and their published results", "venue": "NBG trading platform",
     "why": "intervention as a dated, sized, PUBLIC auction rather than a residual inferred from "
            "reserves; the announcement and the result are two separate objects",
     "proxies": ("USDTRY", "USDRUB")},
    {"name": "Baku-Tbilisi-Ceyhan (BTC) crude transit", "venue": "BTC Co.",
     "why": "Azeri Light crosses Georgia to the Turkish Mediterranean; a transit interruption is "
            "a physical supply event that reaches Brent and links this pack to the Azerbaijani one",
     "proxies": ("XBRUSD", "XTIUSD")},
    {"name": "South Caucasus Pipeline and the Southern Gas Corridor transit",
     "venue": "SCP / TANAP / TAP",
     "why": "Shah Deniz gas crosses Georgia to Turkey and on to Italy; Europe's only non-Russian "
            "pipeline route from the Caspian",
     "proxies": ("XNGUSD", "EUSTX50", "GER40")},
    {"name": "Georgian international visitor arrivals", "venue": "Georgian National Tourism Admin",
     "why": "tourism is one of the largest external receipts; monthly, published, and completely "
            "re-based between 2020 and 2023",
     "proxies": ("USDTRY", "USDRUB")},
    {"name": "Motor vehicle re-export through Poti and Batumi", "venue": "customs statistics",
     "why": "a large post-2022 trade channel: vehicles imported from Europe and the US and "
            "re-exported to Central Asia and Azerbaijan; it is a pure FRICTION trade and it "
            "steps with enforcement",
     "proxies": ("USDRUB", "USDCNH")},
    {"name": "RMG copper concentrate and Georgian ferroalloys", "venue": "company disclosure",
     "why": "the largest mineral exports; small globally but the dominant Georgian export good",
     "proxies": ("XCUUSD",)},
    {"name": "Enguri hydropower and the seasonal electricity balance",
     "venue": "Georgian State Electrosystem",
     "why": "hydropower-dominated generation with a strong seasonal swing; Georgia imports power "
            "in winter from Turkey, Azerbaijan and Russia and exports in spring",
     "proxies": ("USDTRY", "XNGUSD")},
    {"name": "Georgian Stock Exchange and Georgian sovereign eurobonds", "venue": "GSE / LSE",
     "why": "the domestic equity market is very small; the sovereign eurobond spread is the only "
            "liquid Georgian credit observable and it is not quoted here",
     "proxies": ("UST10Y", "US500")},
)

# --------------------------------------------------------------------------- the central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "National Bank of Georgia (საქართველოს ეროვნული ბანკი)",
    "short": "NBG",
    "framework": "inflation_targeter",
    "committee": "Monetary Policy Committee",
    "policy_instrument": "the monetary policy rate (მონეტარული პოლიტიკის განაკვეთი), the "
                         "one-week refinancing rate",
    "corridor": "standing deposit and standing loan facilities either side of the policy rate; "
                "the overnight interbank rate (TIBR) is the operating target",
    "mandate": "price stability with a 3% medium-term inflation target",
    "decision_rule": "eight scheduled decisions a year, on WEDNESDAYS, with a press release and a "
                     "summary of discussion; a Monetary Policy Report is published quarterly",
    "announce_local": "15:00 Asia/Tbilisi",
    "announce_utc": "11:00",
    "announce_utc_dst": "11:00",
    "dst_rule": "NONE. Georgia abolished seasonal clock changes in 2005 and Tbilisi is a fixed "
                "UTC+4. Georgian event minutes in UTC are stable all year -- one of only three "
                "countries in this department where that is true",
    "presser_utc": "12:00",
    "minutes_lag_days": 0,
    "consensus_proxy": "NONE reachable. Georgia has no liquid short-rate curve and no survey the "
                       "desk can lawfully and reliably obtain; a policy surprise here is "
                       "UNMEASURED and must be reported as such",
    "consensus_proxy_trap": "the Bank intervenes by AUCTION in the same weeks it decides, so a "
                            "currency reaction attributed to a rate decision may be the auction. "
                            "The auction calendar is published and must be a second conditioner",
    "distinctive": "INTERVENTION IS A PUBLIC AUCTION. The Bank announces an auction, participants "
                   "bid, and the volume and rate are published the same day. Almost every other "
                   "central bank in this department intervenes opaquely and lets the market infer "
                   "it from reserves; Georgia publishes both the intent and the result",
    "balance_sheet_history": (
        "a long-running de-dollarisation programme, including a larisation package in 2017 that "
        "restricted small foreign-currency lending",
        "reserve accumulation through 2022-2023 as remittances and tourism surged"),
    "off_cycle": "unscheduled decisions are rare; each would be its own class",
    "other_clocks": (
        {"what": "monthly money transfers by sending country",
         "when_local": "mid-month", "when_utc": "10:00", "reference_lag_days": 15},
        {"what": "monthly CPI from Geostat", "when_local": "the first days of the month",
         "when_utc": "06:00", "reference_lag_days": 3},
        {"what": "FX auction announcements and results",
         "when_local": "announced ahead, result the same day", "when_utc": "11:00",
         "reference_lag_days": 0},
        {"what": "quarterly Monetary Policy Report", "when_local": "15:00 Tbilisi",
         "when_utc": "11:00", "reference_lag_days": 0},
    ),
    "root": "https://nbg.gov.ge",
}

# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "Official GEL exchange rate",
     "local": "the weighted average of the day's interbank trades, published in the afternoon and "
              "EFFECTIVE THE NEXT BUSINESS DAY",
     "time_utc": "12:00", "time_utc_dst": "12:00", "dst_rule": "none (Tbilisi is fixed UTC+4)",
     "instruments": (), "window_minutes": 60, "confidence": "DECLARED, VERIFY against nbg.gov.ge",
     "why": "every lari contract and tax liability is struck at this rate. The NEXT-DAY effective "
            "date is the same trap as in the Russian and Kazakh packs"},
    {"name": "NBG FX auction on the trading platform",
     "local": "announced ahead; conducted and published the same day",
     "time_utc": "11:00", "time_utc_dst": "11:00", "dst_rule": "none",
     "instruments": ("USDTRY", "USDRUB"), "window_minutes": 60, "confidence": "DECLARED",
     "why": "the intervention is a dated, sized, public event; the ANNOUNCEMENT and the RESULT "
            "are two separate objects and conflating them loses the more informative one"},
    {"name": "Brent dated, the reference for BTC transit crude",
     "local": "the London afternoon assessment", "time_utc": "16:30", "time_utc_dst": "15:30",
     "dst_rule": "GMT/BST", "instruments": ("XBRUSD", "XTIUSD"), "window_minutes": 30,
     "confidence": "SETTLED",
     "why": "Azeri Light loading at Ceyhan prices against Brent with a quality premium; the "
            "transit fee Georgia earns is volume-linked rather than price-linked, which is why "
            "Georgian transit revenue is a VOLUME story and not a price story"},
    {"name": "LBMA gold price",
     "local": "15:00 Europe/London", "time_utc": "15:00", "time_utc_dst": "14:00",
     "dst_rule": "GMT/BST", "instruments": ("XAUUSD", "XAGUSD"), "window_minutes": 15,
     "confidence": "SETTLED",
     "why": "the regional household safe-haven reflex runs into physical gold, and Georgia is a "
            "transit point for it as well as a consumer"},
    {"name": "Istanbul close, the nearest liquid regional equity reference",
     "local": "18:00 Europe/Istanbul", "time_utc": "15:00", "time_utc_dst": "15:00",
     "dst_rule": "none (Istanbul is fixed UTC+3)", "instruments": ("USDTRY",),
     "window_minutes": 10, "confidence": "SETTLED",
     "why": "Turkey is Georgia's largest trade partner and the nearest market with real depth; "
            "Georgian risk sentiment is read through Turkish assets because there is no Georgian "
            "market to read it in"},
)

SETTLEMENT_CONVENTIONS: tuple[dict[str, Any], ...] = (
    {"name": "remittance receipt cycle", "kind": "month_end",
     "convention": "money transfers are published monthly, mid-month, for the preceding month",
     "rollover_utc": "10:00", "instruments": ("USDRUB", "USDTRY"),
     "why": "the flow itself arrives continuously but is OBSERVED monthly; the publication is the "
            "event and the flow is the mechanism, and the two are 15 to 45 days apart"},
    {"name": "Georgian tax calendar", "kind": "day_of_month",
     "convention": "monthly declarations and payments by the 15th",
     "rollover_utc": "10:00", "instruments": (),
     "why": "a domestic lari demand on a fixed date; there is no instrument on which to measure "
            "it, which is stated rather than worked around"},
    {"name": "tourism season", "kind": "quarter_end",
     "convention": "the summer peak runs June to September with a secondary winter ski season",
     "rollover_utc": "", "instruments": ("USDTRY", "USDRUB"),
     "why": "the largest seasonal in the Georgian external accounts, and it RE-BASED completely "
            "between 2020 and 2023, so a pooled seasonal across that window is meaningless"},
    {"name": "electricity balance season", "kind": "quarter_end",
     "convention": "hydropower surplus in spring, import dependence in winter",
     "rollover_utc": "", "instruments": ("USDTRY", "XNGUSD"),
     "why": "winter import bills are a seasonal external drain and they are priced against "
            "Turkish and regional power, not against a global benchmark"},
    {"name": "budget year", "kind": "fiscal_year_end", "convention": "31 December",
     "rollover_utc": "", "instruments": (),
     "why": "the budget law is passed in December; Georgia runs an IMF-anchored fiscal rule with "
            "published deficit ceilings"},
    {"name": "GEL spot value date", "kind": "weekday", "convention": "T+0/T+1 domestically",
     "rollover_utc": "", "instruments": (),
     "why": "the domestic market settles same-day or next-day; a forward point implied from a "
            "domestic quote is not comparable with an offshore T+2 one"},
)

EXCHANGES: tuple[dict[str, Any], ...] = (
    {"name": "Georgian Stock Exchange (GSE)",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "17:00", "open_utc": "06:00", "close_utc": "13:00",
     "dst_rule": "none (Tbilisi is fixed UTC+4)", "auction": "call auctions",
     "expiry_rule": "n/a",
     "holidays": "the Georgian national calendar",
     "notes": "very small and rarely traded. Listed so the absence is named: there is no Georgian "
              "equity observable worth mining and the pack says so rather than implying one"},
    {"name": "NBG trading platform (Bloomberg-based interbank FX)",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "17:00", "open_utc": "06:00", "close_utc": "13:00",
     "dst_rule": "none", "auction": "the NBG's FX auctions are conducted here",
     "expiry_rule": "n/a",
     "holidays": "the Georgian national calendar",
     "notes": "this is where the official rate is formed and where intervention happens. The desk "
              "has no access; every observable here is a transmission target"},
    {"name": "Borsa Istanbul, the nearest liquid regional venue",
     "index_symbols": (),
     "open_local": "10:00", "close_local": "18:00", "open_utc": "07:00", "close_utc": "15:00",
     "dst_rule": "none (Istanbul is fixed UTC+3)", "auction": "closing auction 18:00-18:10",
     "expiry_rule": "see the Turkish pack",
     "holidays": "the Turkish calendar, which differs from the Georgian one",
     "notes": "listed because Georgian risk is read through Turkish assets; the two calendars "
              "differ, so there are days when the proxy is shut and the economy is not"},
)


# --------------------------------------------------------------------------- holidays
def _orthodox_easter(year: int) -> date:
    """Meeus's Julian algorithm, converted to the Gregorian calendar. Exact for 1900-2099."""
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month, day = divmod(d + e + 114, 31)
    return date(year, month, day + 1) + timedelta(days=13)


def _western_easter(year: int) -> date:
    """The anonymous Gregorian computus, carried here ONLY so the two can be compared: Georgia
    uses the Orthodox reckoning and the two dates differ by up to five weeks."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


#: Georgia's fixed public holidays. The religious dates follow the ORTHODOX calendar: Christmas
#: is 7 January and Epiphany 19 January, not 25 December and 6 January.
FIXED_NATIONAL: tuple[tuple[int, int, str], ...] = (
    (1, 1, "ახალი წელი (New Year), day 1"),
    (1, 2, "ახალი წელი (New Year), day 2"),
    (1, 7, "შობა (Orthodox Christmas)"),
    (1, 19, "ნათლისღება (Epiphany)"),
    (3, 3, "დედის დღე (Mother's Day)"),
    (3, 8, "ქალთა საერთაშორისო დღე (International Women's Day)"),
    (4, 9, "ეროვნული ერთიანობის დღე (Day of National Unity)"),
    (5, 9, "ფაშიზმზე გამარჯვების დღე (Victory over Fascism Day)"),
    (5, 12, "წმინდა ანდრია პირველწოდებულის დღე (St Andrew the First-Called)"),
    (5, 26, "დამოუკიდებლობის დღე (Independence Day)"),
    (8, 28, "მარიამობა (Assumption of the Virgin)"),
    (10, 14, "სვეტიცხოვლობა (Svetitskhovloba)"),
    (11, 23, "გიორგობა (St George's Day)"),
)


def national_holidays(year: int) -> dict[date, str]:
    """Georgia's public holidays for `year`, computed from the fixed dates plus the ORTHODOX
    Easter cycle.

    The movable feasts are Good Friday, Great Saturday, Easter Sunday and Easter Monday, all
    reckoned from the Julian Easter. In 2026 Orthodox Easter is 12 April against the Western
    5 April -- a week apart -- and a screen using the Western date will place the whole Georgian
    Easter block in the wrong week.

    There is NO Mondayisation in Georgian law: a holiday falling on a weekend is simply absorbed.
    That is stated rather than assumed, because the neighbouring Russian and Kazakh packs BOTH
    transfer and importing their rule here would invent days that do not exist.
    """
    out: dict[date, str] = {}
    easter = _orthodox_easter(year)
    out[easter - timedelta(days=2)] = "წითელი პარასკევი (Good Friday, Orthodox)"
    out[easter - timedelta(days=1)] = "დიდი შაბათი (Great Saturday)"
    out[easter] = "აღდგომა (Orthodox Easter)"
    out[easter + timedelta(days=1)] = "შავი ორშაბათი (Easter Monday)"
    for month, day, label in FIXED_NATIONAL:
        out[date(year, month, day)] = label
    return dict(sorted(out.items()))


def market_holidays(year: int) -> dict[date, str]:
    """The Georgian Stock Exchange and the NBG platform follow the national calendar."""
    return national_holidays(year)


def easter_divergence(year: int) -> dict[str, date]:
    """The Orthodox and Western Easter dates side by side, and the gap between them. Georgia uses
    the first; Turkey's market calendar is secular and uses neither; the European venues Georgian
    transit reaches use the second."""
    orth = _orthodox_easter(year)
    west = _western_easter(year)
    return {"orthodox": orth, "western": west,
            "orthodox_good_friday": orth - timedelta(days=2),
            "western_good_friday": west - timedelta(days=2)}


def is_market_holiday(day: date) -> bool:
    return day in market_holidays(day.year)


HOLIDAYS_RULE: dict[str, Any] = {
    "kind": "computed_from_rules_orthodox",
    "authority": "the Labour Code of Georgia for the fixed dates; the Georgian Orthodox Church's "
                 "Julian reckoning for the movable feasts",
    "years": (2024, 2025, 2026),
    "weekend": "Saturday and Sunday",
    "fixed_rule": "1-2 January, 7 January (Orthodox Christmas), 19 January (Epiphany), 3 March, "
                  "8 March, 9 April, 9 May, 12 May, 26 May, 28 August, 14 October and 23 November",
    "movable_rule": "Good Friday, Great Saturday, Easter Sunday and Easter Monday on the ORTHODOX "
                    "(Julian) reckoning",
    "mondayisation_rule": "NONE. Georgian law does not transfer a holiday that falls on a "
                          "weekend; it is absorbed. Stated explicitly because the neighbouring "
                          "Russian and Kazakh packs both transfer, and importing their rule here "
                          "would invent days that do not exist",
    "known_dates": {
        "2024-05-05": "აღდგომა, Orthodox Easter (Western Easter was 31 March, five weeks earlier)",
        "2025-04-20": "აღდგომა, Orthodox Easter (the same day as Western Easter in 2025)",
        "2026-04-12": "აღდგომა, Orthodox Easter -- Western Easter is 5 April, a WEEK EARLIER. A "
                      "screen using the Western date puts the whole Georgian Easter block in the "
                      "wrong week",
        "2026-04-10": "წითელი პარასკევი, Orthodox Good Friday",
        "2026-01-07": "შობა, Orthodox Christmas",
        "2026-11-23": "გიორგობა, St George's Day, a Monday",
    },
    "fn": market_holidays,
    "national_fn": national_holidays,
    "easter_fn": easter_divergence,
}

# --------------------------------------------------------------------------- positioning
COT_CURRENCY = ""
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"name": "CFTC Commitments of Traders for GEL", "root": "", "fields": (), "frequency": "n/a",
     "snapshot": "", "publish_utc": "", "lag_days": 0, "licence": "", "available": False,
     "why": "no CME lari contract exists and none ever has",
     "pit_warning": "DOES NOT EXIST. Lari positioning is permanently UNMEASURED and no other "
                    "currency's COT may be substituted"},
    {"name": "NBG money transfers by sending country",
     "root": "https://nbg.gov.ge/en/statistics/statistics-data",
     "fields": ("month", "total_usd", "by_country_usd", "russia_share", "eu_share",
                "usa_share", "israel_share"),
     "frequency": "monthly", "snapshot": "month", "publish_utc": "10:00", "lag_days": 15,
     "licence": "free, public", "available": True,
     "why": "THE PACK'S BEST SERIES. A cross-border household flow, by origin country, monthly, "
            "free, in an economy where it is a large share of external receipts",
     "pit_warning": "published mid-month for the preceding month, so it is 15 to 45 days stale "
                    "when it arrives; the flow happened before the observation and a same-month "
                    "conditioner is a look-ahead"},
    {"name": "NBG FX auction announcements and results",
     "root": "https://nbg.gov.ge/en/monetary-policy/fx-interventions",
     "fields": ("auction_date", "announced_amount_usd", "allotted_amount_usd", "cut_off_rate",
                "direction", "participants"),
     "frequency": "event-driven", "snapshot": "auction", "publish_utc": "11:00", "lag_days": 0,
     "licence": "free, public", "available": True,
     "why": "intervention as a dated, sized, public event rather than a residual inferred from "
            "monthly reserves",
     "pit_warning": "the ANNOUNCEMENT and the RESULT are separate; using the result as if it were "
                    "known at announcement is a look-ahead of several hours"},
    {"name": "NBG international reserves",
     "root": "https://nbg.gov.ge/en/statistics/statistics-data",
     "fields": ("month", "gross_reserves_usd", "change"), "frequency": "monthly",
     "snapshot": "month end", "publish_utc": "10:00", "lag_days": 7, "licence": "free, public",
     "available": True,
     "why": "the cumulative record of intervention; it CONFIRMS the auction series rather than "
            "substituting for it",
     "pit_warning": "revised; and reserve changes include valuation effects that are not "
                    "intervention"},
    {"name": "Geostat external trade and visitor arrivals",
     "root": "https://www.geostat.ge/en", "fields": ("month", "exports", "imports", "re_exports",
                                                     "visitor_arrivals"),
     "frequency": "monthly", "snapshot": "month", "publish_utc": "06:00", "lag_days": 25,
     "licence": "free, public", "available": True,
     "why": "the car re-export channel shows up here as a divergence between imports and "
            "re-exports; tourism shows up as arrivals",
     "pit_warning": "revised; the re-export classification changed as the channel grew"},
)

# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "GE-A": ("მონეტარული პოლიტიკის განაკვეთი", "ეროვნული ბანკი", "ინფლაცია",
             "монетарная политика", "ставка рефинансирования", "инфляция"),
    "GE-B": ("ინტერვენცია", "აუქციონი", "ოფიციალური კურსი", "ლარი",
             "интервенция", "аукцион", "официальный курс", "лари"),
    "GE-C": ("ფულადი გზავნილები", "გზავნილები", "ემიგრანტები", "რუსეთი",
             "денежные переводы", "переводы", "мигранты", "Россия"),
    "GE-D": ("ტრანზიტი", "მილსადენი", "ბაქო-თბილისი-ჯეიჰანი", "ბაქო-თბილისი-ერზურუმი",
             "транзит", "трубопровод", "БТД"),
    "GE-E": ("ტურიზმი", "ვიზიტორები", "სასტუმრო", "სეზონი",
             "туризм", "туристы", "сезон"),
    "GE-F": ("რეექსპორტი", "ავტომობილები", "ფოთი", "ბათუმი",
             "реэкспорт", "автомобили", "Поти", "Батуми"),
    "GE-G": ("სპილენძი", "ფეროშენადნობები", "მადანი", "ექსპორტი",
             "медь", "ферросплавы", "руда", "экспорт"),
    "GE-H": ("ელექტროენერგია", "ჰიდროელექტროსადგური", "ენგური", "იმპორტი",
             "электроэнергия", "ГЭС", "Ингури", "импорт"),
    "GE-I": ("დოლარიზაცია", "ლარიზაცია", "დეპოზიტები", "სესხები",
             "долларизация", "ларизация", "депозиты", "кредиты"),
    "GE-J": ("ბიუჯეტი", "ფისკალური წესი", "საგარეო ვალი", "ევრობონდი",
             "бюджет", "фискальное правило", "внешний долг"),
    "GE-K": ("აღდგომა", "შობა", "ნათლისღება", "გიორგობა", "სვეტიცხოვლობა",
             "Пасха", "Рождество", "праздник"),
    "GE-L": ("საქართველოს საფონდო ბირჟა", "ევრობონდი", "სპრედი",
             "фондовая биржа", "еврооблигации", "спред"),
}

# --------------------------------------------------------------------------- sources
#: THE TEN SOURCE LAYERS (principal's per-country depth rule, 2026-09-17). Every source carries
#: EXACTLY ONE, and this pack must name at least one source in each layer or declare the layer
#: ABSENT with a reason. A country is never "covered" by five obvious sources: five official
#: roots is one layer done and nine layers missing, and the missing nine are where a mechanism
#: nobody has tested is still lying around.
SOURCE_LAYERS: tuple[str, ...] = (
    "official", "institutional", "academic", "practitioner", "retail_ecology", "app_ecosystem",
    "media", "archive", "physical_economy", "source_graph")

#: How the desk is allowed to reach a source. Three INDEPENDENT labels travel with every source
#: and this is the first: what the terms permit, which is a legal fact and not a quality one.
ACCESS_LABELS: tuple[str, ...] = (
    "PUBLIC", "PUBLIC_WITH_TERMS", "LICENSED", "OPEN_DATA", "PUBLIC_ARCHIVE", "PUBLIC_SOCIAL",
    "USER_SUBMITTED", "ACCESS_UNCLEAR", "PRIVATE", "CONFIDENTIAL_MNPI", "STOLEN_UNAUTHORIZED")

#: The second label: how much the desk believes the source, independent of what it may read.
#: FRINGE and CONTRADICTED material is KEPT as an evidence object at low weight and never
#: dropped -- a claim that looks false is still a dated, testable claim, and deleting it destroys
#: the only record that it was ever made.
CREDIBILITY_LABELS: tuple[str, ...] = (
    "AUTHORITATIVE", "RELIABLE", "UNRELIABLE", "FRINGE", "CONTRADICTED", "UNKNOWN")

#: The third label, and the only one the desk can EARN: whether anything from this source has
#: ever predicted anything. UNTESTED is the honest default and is not a criticism.
#: NARRATIVE_FEATURE means the text conditions usefully even though its claims do not forecast.
PREDICTIVE_STATES: tuple[str, ...] = (
    "UNTESTED", "PREDICTIVE", "NOT_PREDICTIVE", "NARRATIVE_FEATURE")


def _seq(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(str(v) for v in values)


def source_class(sid: str, label: str, *, layer: str, roots: Iterable[str],
                 queries: Iterable[str], languages: Iterable[str], access_label: str,
                 credibility: str, predictive_state: str, licence: str,
                 machine_use_allowed: bool = True, notes: str = "") -> dict[str, Any]:
    """One class of source, with the roots a crawler can start from and its three labels.

    `queries` are NATIVE-SCRIPT search terms and slang, never translated English: a miner that
    searches an English phrase on a Russian, Kazakh, Georgian, Azerbaijani or Turkish ground
    finds the small English-speaking corner of that ground and then reports the result as if it
    were the ground.

    `machine_use_allowed=False` registers a source whose terms forbid machine extraction. It is
    NEVER scraped and NEVER omitted: the row stays so the desk knows the ground exists, knows it
    was considered, and knows exactly why it is not being read.
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"source {sid}: layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    if access_label not in ACCESS_LABELS:
        raise ValueError(f"source {sid}: access_label {access_label!r} not one of "
                         f"{list(ACCESS_LABELS)}")
    if credibility not in CREDIBILITY_LABELS:
        raise ValueError(f"source {sid}: credibility {credibility!r} not one of "
                         f"{list(CREDIBILITY_LABELS)}")
    if predictive_state not in PREDICTIVE_STATES:
        raise ValueError(f"source {sid}: predictive_state {predictive_state!r} not one of "
                         f"{list(PREDICTIVE_STATES)}")
    return {"id": sid, "label": label, "layer": layer, "roots": _seq(roots),
            "queries": _seq(queries), "languages": _seq(languages),
            "access_label": access_label, "credibility": credibility,
            "predictive_state": predictive_state,
            "machine_use_allowed": bool(machine_use_allowed), "licence": licence, "notes": notes}


def absent_layer(layer: str, reason: str) -> dict[str, Any]:
    """A layer this country has nothing in, declared BY NAME with the reason.

    A blank layer and an absent layer look identical in a table and mean opposite things: one is
    work not done, the other is a measurement. This row makes the second one visible (L1.28a).
    """
    if layer not in SOURCE_LAYERS:
        raise ValueError(f"absent layer {layer!r} not one of {list(SOURCE_LAYERS)}")
    return {"id": f"absent_{layer}", "label": f"NO SOURCE IN THIS LAYER: {layer}", "layer": layer,
            "roots": (), "queries": (), "languages": (), "access_label": "ACCESS_UNCLEAR",
            "credibility": "UNKNOWN", "predictive_state": "UNTESTED",
            "machine_use_allowed": False, "licence": "n/a",
            "notes": f"DECLARED ABSENT, NOT BLANK: {reason}"}


def layer_counts(classes: Iterable[Mapping[str, Any]] | None = None) -> dict[str, int]:
    """How many real sources this pack names in each of the ten layers. A zero is a hole, and an
    `absent_*` row does not count toward it -- declaring a layer absent is honest, not coverage.
    """
    rows = SOURCE_CLASSES if classes is None else classes
    out = dict.fromkeys(SOURCE_LAYERS, 0)
    for sc in rows:
        layer = str(sc.get("layer") or "")
        if layer in out and not str(sc.get("id") or "").startswith("absent_"):
            out[layer] += 1
    return out


def layer_terms() -> dict[str, tuple[str, ...]]:
    """The native-script query vocabulary this pack carries, grouped by layer. Derived from the
    sources themselves so it can never drift from what a crawler would actually search."""
    out: dict[str, list[str]] = {layer: [] for layer in SOURCE_LAYERS}
    for sc in SOURCE_CLASSES:
        layer = str(sc.get("layer") or "")
        if layer not in out:
            continue
        for q in sc.get("queries", ()):
            if q not in out[layer]:
                out[layer].append(q)
    return {k: tuple(v) for k, v in out.items()}


def source_layer_coverage() -> dict[str, Any]:
    """Sources per layer, every empty layer named, and the two numbers that must stay at zero.

    `unexplained_missing` is a layer with no source AND no reason -- the exact shape of a pack
    that stopped at the five obvious official feeds. `machine_use_forbidden` is not a defect: it
    is the register of ground the desk knows about and deliberately does not scrape.
    """
    counts = layer_counts()
    missing = {layer: str(LAYER_ABSENCES.get(layer, "")) for layer, n in counts.items() if not n}
    return {"code": CODE, "layer_counts": counts,
            "n_layers_covered": sum(1 for n in counts.values() if n),
            "n_sources": len([s for s in SOURCE_CLASSES
                              if not str(s["id"]).startswith("absent_")]),
            "missing": missing,
            "unexplained_missing": sorted(k for k, why in missing.items() if not why.strip()),
            "machine_use_forbidden": [str(s["id"]) for s in SOURCE_CLASSES
                                      if not s.get("machine_use_allowed", True)],
            "low_weight_kept": [str(s["id"]) for s in SOURCE_CLASSES
                                if s.get("credibility") in ("FRINGE", "UNRELIABLE",
                                                            "CONTRADICTED")],
            "rule": "ten layers, each carrying a source or named ABSENT with a reason; fringe "
                    "and contradicted PUBLIC material is kept as a low-weight evidence object "
                    "and never dropped; a page whose terms forbid machine extraction is "
                    "registered machine_use_allowed=false, never scraped and never omitted"}


#: GEORGIA'S TEN LAYERS, in GEORGIAN AND RUSSIAN. Georgian uses its own script, which no Latin-
#: or Cyrillic-trained screen will match: "მონეტარული პოლიტიკის განაკვეთი" has no transliteration
#: that finds the National Bank's own headline. Russian is the working language of much of the
#: practitioner web and of the remittance corridor itself, so both are carried on every row.
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    source_class(
        "ge_nbg", "National Bank of Georgia", layer="official",
        roots=("https://nbg.gov.ge/en/monetary-policy/monetary-policy-decisions",
               "https://nbg.gov.ge/en/statistics/statistics-data",
               "https://nbg.gov.ge/en/monetary-policy/fx-interventions"),
        queries=("მონეტარული პოლიტიკის განაკვეთი", "ეროვნული ბანკი", "ინფლაცია",
                 "ფულადი გზავნილები", "ინტერვენცია", "აუქციონი", "ოფიციალური კურსი",
                 "ლარიზაცია", "დოლარიზაცია", "монетарная политика", "денежные переводы",
                 "интервенция", "официальный курс"),
        languages=("ka", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (CC BY)",
        notes="THE MONEY-TRANSFER SERIES WITH ITS COUNTRY SPLIT IS THE PACK'S BEST GROUND: a "
              "monthly, free, by-origin household flow. It is 15 to 45 days stale on arrival, so "
              "a same-month conditioner is a look-ahead"),
    source_class(
        "ge_geostat", "Geostat, the national statistics office", layer="official",
        roots=("https://www.geostat.ge/en", "https://www.geostat.ge/en/modules/categories/"),
        queries=("სამომხმარებლო ფასების ინდექსი", "ინფლაცია", "საგარეო ვაჭრობა",
                 "რეექსპორტი", "იმპორტი", "ექსპორტი", "внешняя торговля", "реэкспорт",
                 "индекс потребительских цен"),
        languages=("ka", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="Creative Commons BY 4.0",
        notes="THE RE-EXPORT CLASSIFICATION CHANGED as the vehicle channel grew -- a silent break "
              "in any long trade panel unless the classification version is carried per row"),
    source_class(
        "ge_treasury_sanctions", "Ministry of Finance and the sanctions lists touching Georgia",
        layer="official",
        roots=("https://www.mof.ge/en/", "https://ofac.treasury.gov/sanctions-list-service",
               "https://www.sanctionsmap.eu/"),
        queries=("ბიუჯეტი", "ფისკალური წესი", "საგარეო ვალი", "ევრობონდი",
                 "re-export", "circumvention", "dual-use", "реэкспорт", "обход санкций"),
        languages=("ka", "en", "ru"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public (government data)",
        notes="SANCTIONS ARE OFFICIAL PUBLIC DATA AND ARE USED AS DATA: the enforcement dates are "
              "the steps GE-F's vehicle re-export channel moves on"),
    source_class(
        "ge_gse_bank_regulator", "Georgian Stock Exchange and the NBG as market regulator",
        layer="institutional",
        roots=("https://gse.ge/", "https://nbg.gov.ge/en/page/securities-market"),
        queries=("საფონდო ბირჟა", "ლისტინგი", "ობლიგაცია", "фондовая биржа", "листинг"),
        languages=("ka", "ru"), access_label="PUBLIC", credibility="AUTHORITATIVE",
        predictive_state="NOT_PREDICTIVE", licence="free headline",
        notes="the domestic equity market is very small and rarely traded. NOT_PREDICTIVE is a "
              "measured verdict: there is no Georgian equity observable worth mining, and saying "
              "so is more useful than implying one exists"),
    source_class(
        "ge_multilateral", "IMF, World Bank, EBRD and ADB Georgia coverage",
        layer="institutional",
        roots=("https://www.imf.org/en/Countries/GEO",
               "https://www.worldbank.org/en/country/georgia",
               "https://www.ebrd.com/georgia.html"),
        queries=("Article IV", "programme review", "remittances", "external position",
                 "fiscal rule", "პროგრამის მიმოხილვა"),
        languages=("en", "ka"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="IMF Article IV reports are the best single free description of the Georgian fiscal "
              "rule and external position, and the review DATES are the events GE-J trades"),
    source_class(
        "ge_tourism_admin", "Georgian National Tourism Administration", layer="institutional",
        roots=("https://gnta.ge/statistics/",),
        queries=("ვიზიტორები", "ტურიზმი", "საერთაშორისო მოგზაურები", "туристы",
                 "visitor arrivals", "average spend"),
        languages=("ka", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the series RE-BASED between 2020 and 2023; a pooled seasonal across that window "
              "is meaningless, which is why GE-E splits it explicitly"),
    source_class(
        "ge_nbg_research", "NBG working papers and the Monetary Policy Report", layer="academic",
        roots=("https://nbg.gov.ge/en/publications/working-papers",),
        queries=("სამუშაო ნაშრომი", "ტრანსმისიის მექანიზმი", "გაცვლითი კურსი",
                 "рабочий доклад", "трансмиссионный механизм"),
        languages=("ka", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Bank writes on its own intervention practice, which is the direct evidence "
              "GE-B needs and which almost no other central bank in this department publishes"),
    source_class(
        "ge_academic", "ISET, the Georgian universities and the regional literature",
        layer="academic",
        roots=("https://iset-pi.ge/en/", "https://cyberleninka.ru/", "https://ideas.repec.org/"),
        queries=("remittances and exchange rate", "dollarisation Georgia", "larisation",
                 "ფულადი გზავნილები კვლევა", "денежные переводы исследование"),
        languages=("ka", "ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="per-paper; bulk download restricted",
        notes="ISET's policy institute publishes the only regular independent Georgian "
              "macroeconomic analysis and its remittance work is the literature GE-C sits in"),
    source_class(
        "ge_bank_research", "TBC and Bank of Georgia research and LSE disclosure",
        layer="practitioner",
        roots=("https://www.tbcbank.ge/", "https://bankofgeorgia.ge/",
               "https://www.londonstockexchange.com/"),
        queries=("quarterly results", "non-resident deposits", "deposit dollarisation",
                 "არარეზიდენტების დეპოზიტები", "депозиты нерезидентов"),
        languages=("ka", "en", "ru"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the two large banks are LSE-listed, so their disclosure is unusually detailed for "
              "the region and is the best free read on where the relocation flow actually landed. "
              "EVENT LANE ONLY for the single names"),
    source_class(
        "ge_telegram_analysts", "Georgian and Russian-language macro Telegram channels",
        layer="practitioner",
        roots=("https://t.me/s/",),
        queries=("ლარის კურსი", "ეროვნული ბანკი", "курс лари", "переводы из России",
                 "релоканты", "интервенция ЕБ"),
        languages=("ka", "ru"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=False,
        licence="public channels; automated extraction restricted",
        notes="the relocation wave created a large Russian-language commentary layer inside "
              "Georgia; a conditioning variable, never evidence"),
    source_class(
        "ge_comment_threads", "interpressnews, bm.ge and Civil.ge comment sections",
        layer="retail_ecology",
        roots=("https://bm.ge/", "https://www.interpressnews.ge/", "https://civil.ge/"),
        queries=("ლარის გაუფასურება", "ფასების ზრდა", "ბინის ქირა", "обесценивание лари",
                 "аренда квартиры", "цены выросли"),
        languages=("ka", "ru"), access_label="PUBLIC_SOCIAL", credibility="FRINGE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=False,
        licence="public comment sections; automated extraction restricted",
        notes="rent and price complaints are the highest-frequency read on the relocation "
              "wave's local impact. FRINGE AND KEPT: frequently wrong, and the only daily signal "
              "on a quarterly phenomenon"),
    source_class(
        "ge_relocant_communities", "Relocant forums, Facebook groups and Reddit",
        layer="retail_ecology",
        roots=("https://www.reddit.com/r/Sakartvelo/",
               "https://www.reddit.com/r/georgiarelocation/"),
        queries=("релокация", "ВНЖ Грузия", "открыть счёт", "перевод денег", "SWIFT",
                 "карта иностранного банка", "комиссия за перевод"),
        languages=("ru", "en"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="public social; API terms govern automated access",
        notes="the relocation flow's own participants describing the PAYMENT CHANNEL in real "
              "time -- which corridor works this week, at what cost. That is the mechanism behind "
              "GE-C and it is invisible in any official series"),
    source_class(
        "ge_car_trade_forums", "Vehicle re-export trade communities", layer="retail_ecology",
        roots=("https://www.myauto.ge/", "https://t.me/s/"),
        queries=("ავტო იმპორტი", "განბაჟება", "ფოთი", "ბათუმი", "растаможка", "Поти",
                 "авто из США", "аукцион копарт"),
        languages=("ka", "ru"), access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public marketplace and channels; automated extraction restricted",
        notes="the vehicle re-export channel is a real trade flow with real participants who "
              "discuss customs treatment and destination demand openly; it steps with enforcement "
              "and this is where the step is visible first"),
    source_class(
        "ge_broker_apps", "Georgian banking and brokerage apps", layer="app_ecosystem",
        roots=("https://www.tbcbank.ge/", "https://bankofgeorgia.ge/",
               "https://galtandtaggart.com/"),
        queries=("საბროკერო", "ინვესტიცია", "საკომისიო", "брокерский счёт", "комиссия",
                 "мобильное приложение"),
        languages=("ka", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public product pages; account data is PRIVATE and is never sought",
        notes="what Georgian retail can actually reach. NO ACCOUNT-LEVEL DATA is sought"),
    source_class(
        "ge_metatrader", "MetaTrader and TradingView as used in the Caucasus",
        layer="app_ecosystem",
        roots=("https://www.mql5.com/ru/market", "https://www.mql5.com/ru/code",
               "https://ru.tradingview.com/scripts/"),
        queries=("ალგორითმული ვაჭრობა", "სავაჭრო რობოტი", "алготрейдинг", "торговый робот",
                 "советник", "MQL5", "кодобаза", "стакан", "скальпинг", "арбитраж",
                 "тестер стратегий", "Pine Script"),
        languages=("ka", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="public with terms",
        notes="Georgia has no domestic algorithmic ecosystem of its own; its retail algo culture "
              "is the RUSSIAN-LANGUAGE MetaTrader ground shared with the RU and KZ packs, which "
              "is a finding about the region rather than a gap in this pack"),
    source_class(
        "ge_crypto_adjacent_apps", "Payment and remittance apps used in the corridor",
        layer="app_ecosystem",
        roots=("https://www.tbcbank.ge/", "https://www.moneygram.com/",
               "https://www.westernunion.com/"),
        queries=("გზავნილის საკომისიო", "комиссия за перевод", "курс перевода",
                 "лимит перевода", "SWIFT перевод"),
        languages=("ka", "ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public pricing pages; terms restrict automated extraction",
        notes="TRANSFER COST BY CORRIDOR is the price variable behind the volume series GE-C "
              "measures; published on pricing pages and nowhere else"),
    source_class(
        "ge_press", "BM.ge, Interpressnews, Civil.ge and the business press", layer="media",
        roots=("https://bm.ge/", "https://www.interpressnews.ge/", "https://civil.ge/",
               "https://bpn.ge/"),
        queries=("ეროვნული ბანკი", "განაკვეთი", "ლარი", "გზავნილები", "ტურიზმი",
                 "Национальный банк", "ставка", "лари", "переводы"),
        languages=("ka", "ru", "en"), access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
        predictive_state="NARRATIVE_FEATURE", machine_use_allowed=False,
        licence="public web; automated extraction restricted",
        notes="Civil.ge is the most reliable English-language record and BM.ge the fastest "
              "Georgian-language business wire; read and cited, never scraped"),
    source_class(
        "ge_jam_rferl", "JAMnews, OC Media and RFE/RL Caucasus coverage", layer="media",
        roots=("https://jam-news.net/", "https://oc-media.org/",
               "https://www.rferl.org/georgia"),
        queries=("Caucasus economy", "Georgia Russia trade", "remittances surge",
                 "экономика Грузии", "торговля с Россией"),
        languages=("en", "ru", "ka"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="cross-border Caucasus coverage that the national outlets do not carry; the "
              "regional view GE-F and the Azerbaijani pack both need"),
    source_class(
        "ge_wayback", "Internet Archive captures of nbg.gov.ge and geostat.ge", layer="archive",
        roots=("https://web.archive.org/web/*/nbg.gov.ge*",
               "https://web.archive.org/web/*/geostat.ge*"),
        queries=("არქივი", "первоначальная публикация", "архив страницы",
                 "изменение классификации", "superseded release"),
        languages=("ka", "ru", "en"), access_label="PUBLIC_ARCHIVE", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Geostat re-export RECLASSIFICATION is visible only by comparing captures; "
              "without the archive the break reads as a trade shock that never happened"),
    source_class(
        "ge_national_archive", "National Parliamentary Library and the Georgian press archive",
        layer="archive",
        roots=("http://www.nplg.gov.ge/",),
        queries=("არქივი", "ისტორიული სტატისტიკა", "1998 კრიზისი", "архив",
                 "историческая статистика"),
        languages=("ka", "ru"), access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", machine_use_allowed=False,
        licence="public archive; reading-room and site terms govern reuse",
        notes="Georgia's currency history includes a hyperinflation and two regional shocks; the "
              "contemporaneous record is how an era is read on its own terms"),
    source_class(
        "ge_transit_physical", "BTC, SCP operator disclosure and port throughput",
        layer="physical_economy",
        roots=("https://www.bp.com/en_az/azerbaijan/home.html",
               "https://www.tanap.com/", "https://www.apmterminalspoti.ge/"),
        queries=("მილსადენი", "ტრანზიტი", "ფოთის პორტი", "ბათუმის პორტი", "транзит",
                 "трубопровод", "перевалка", "порт Поти", "throughput"),
        languages=("ka", "ru", "en"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="Georgian transit revenue is VOLUME-linked, not price-linked, which is the claim "
              "GE-D tests and the reason Georgia's exposure is the mirror of Azerbaijan's"),
    source_class(
        "ge_power_hydro", "Georgian State Electrosystem and the seasonal power balance",
        layer="physical_economy",
        roots=("https://www.gse.com.ge/en", "https://www.esco.ge/"),
        queries=("ელექტროენერგია", "ჰიდროელექტროსადგური", "ენგური", "იმპორტი", "ექსპორტი",
                 "электроэнергия", "ГЭС", "импорт электроэнергии"),
        languages=("ka", "ru"), access_label="OPEN_DATA", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="free, public",
        notes="a hydro-dominated system that imports in winter and exports in spring; the "
              "seasonal is HYDROLOGY, not the calendar, which is GE-H's falsifier"),
    source_class(
        "ge_mining_agri", "RMG, ferroalloy producers and the agricultural export mix",
        layer="physical_economy",
        roots=("https://www.rmg.ge/", "https://www.geostat.ge/en"),
        queries=("სპილენძის კონცენტრატი", "ფეროშენადნობი", "ღვინო", "თხილი",
                 "медный концентрат", "ферросплавы", "вино", "фундук"),
        languages=("ka", "ru"), access_label="PUBLIC", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the goods leg against this pack's three services legs; small globally and "
              "dominant domestically"),
    source_class(
        "ge_citation_graph", "OpenAlex, RePEc and CyberLeninka citation graphs",
        layer="source_graph",
        roots=("https://openalex.org/", "https://ideas.repec.org/", "https://cyberleninka.ru/"),
        queries=("cited by", "remittances literature", "цитирование", "кто цитирует"),
        languages=("en", "ru", "ka"), access_label="OPEN_DATA", credibility="RELIABLE",
        predictive_state="UNTESTED", licence="free, public",
        notes="the Georgian remittance literature is small enough that the citation graph shows "
              "immediately whether a finding is replicated or is one paper repeated"),
    source_class(
        "ge_code_graph", "GitHub clients for NBG and Geostat data", layer="source_graph",
        roots=("https://github.com/search?q=nbg.gov.ge+api",
               "https://github.com/search?q=geostat+georgia"),
        queries=("nbg api", "geostat api", "georgia exchange rate api", "форк"),
        languages=("en", "ru"), access_label="PUBLIC_WITH_TERMS", credibility="UNRELIABLE",
        predictive_state="UNTESTED", licence="per-repository; check each, never vendor code",
        notes="the existence of a public NBG rate client is itself information about which "
              "Georgian series practitioners consider worth automating"),
    source_class(
        "ge_desk_registry", "The desk's own source registry and coverage map",
        layer="source_graph",
        roots=("desks/mt5/data/data_universe_map.json",
               "desks/mt5/data/deep_forest_sources.json"),
        queries=("coverage map", "source registry", "already mined", "duplicate ground"),
        languages=("en",), access_label="PRIVATE", credibility="AUTHORITATIVE",
        predictive_state="UNTESTED", licence="desk-owned",
        notes="Georgia shares its app ecosystem with Russia; the registry stops that shared "
              "ground being counted twice as two countries' coverage"),
)

#: All ten layers are populated, with one honest caveat recorded in the app_ecosystem rows:
#: Georgia has no domestic algorithmic-trading ecosystem, and its retail algo culture is the
#: Russian-language MetaTrader ground shared with the RU and KZ packs. That is a finding about
#: the region, not a hole in this pack, and it is why `source_graph` exists.
LAYER_ABSENCES: dict[str, str] = {}

# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    {"name": "NBG monetary policy rate decisions", "source": "National Bank of Georgia",
     "coverage": "2008 onward", "frequency": "8 per year", "publication_lag_days": 0.0,
     "revisions": "never revised", "licence": "free, public", "history_from": "2008-02",
     "pit_feasible": True, "assets": ("USDTRY", "USDRUB"),
     "fields": ("decision_date", "policy_rate_pct", "change_bp", "statement_text"),
     "pit_fields": ("release_ts_utc",),
     "mechanism_families": ("event_reaction", "policy_surprise"),
     "how_to_fetch": "nbg.gov.ge monetary policy decisions; Wednesdays, 15:00 Tbilisi = 11:00 UTC "
                     "all year"},
    {"name": "NBG money transfers by sending country", "source": "National Bank of Georgia",
     "coverage": "2011 onward", "frequency": "monthly", "publication_lag_days": 15.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2011-01",
     "pit_feasible": True, "assets": ("USDRUB", "USDTRY"),
     "fields": ("month", "total_usd", "russia_usd", "eu_usd", "usa_usd", "israel_usd",
                "turkey_usd"),
     "pit_fields": ("publish_ts_utc", "reference_month"),
     "mechanism_families": ("institutional_flow", "macro_condition"),
     "how_to_fetch": "nbg.gov.ge statistics. THE PACK'S BEST SERIES: a country-split household "
                     "flow, monthly and free. The 2022-2023 Russian surge is the largest "
                     "identified shock in it"},
    {"name": "NBG FX auction announcements and results", "source": "National Bank of Georgia",
     "coverage": "2009 onward", "frequency": "event-driven", "publication_lag_days": 0.0,
     "revisions": "final", "licence": "free, public", "history_from": "2009-01",
     "pit_feasible": True, "assets": ("USDTRY", "USDRUB"),
     "fields": ("auction_date", "direction", "announced_usd", "allotted_usd", "cut_off_rate"),
     "pit_fields": ("announcement_ts_utc", "result_ts_utc"),
     "mechanism_families": ("sovereign_flow", "event_reaction"),
     "how_to_fetch": "nbg.gov.ge FX interventions. Keep BOTH timestamps: using the result as if "
                     "known at announcement is a look-ahead of several hours"},
    {"name": "Geostat consumer price index", "source": "Geostat", "coverage": "1996 onward",
     "frequency": "monthly", "publication_lag_days": 3.0, "revisions": "revised",
     "licence": "free, public", "history_from": "1996-01", "pit_feasible": True,
     "assets": ("USDTRY",),
     "fields": ("reference_month", "cpi_mom", "cpi_yoy", "core", "food", "utilities"),
     "pit_fields": ("release_ts_utc", "vintage"),
     "mechanism_families": ("event_reaction", "macro_condition"),
     "how_to_fetch": "geostat.ge price statistics"},
    {"name": "Geostat external merchandise trade", "source": "Geostat", "coverage": "1995 onward",
     "frequency": "monthly", "publication_lag_days": 25.0,
     "revisions": "revised; the re-export classification changed as the vehicle channel grew",
     "licence": "free, public", "history_from": "1995-01", "pit_feasible": True,
     "assets": ("USDRUB", "USDTRY", "XCUUSD"),
     "fields": ("month", "exports", "imports", "re_exports", "vehicles", "copper_ore",
                "partner_country"),
     "pit_fields": ("release_ts_utc", "vintage", "classification_version"),
     "mechanism_families": ("macro_condition", "policy_shock"),
     "how_to_fetch": "geostat.ge external trade; the car re-export channel is the "
                     "imports-minus-re-exports divergence"},
    {"name": "International visitor arrivals",
     "source": "Georgian National Tourism Administration", "coverage": "2011 onward",
     "frequency": "monthly", "publication_lag_days": 15.0, "revisions": "revised",
     "licence": "free, public", "history_from": "2011-01", "pit_feasible": True,
     "assets": ("USDTRY", "USDRUB"),
     "fields": ("month", "arrivals_total", "arrivals_russia", "arrivals_turkey",
                "arrivals_eu", "average_spend"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("macro_condition",),
     "how_to_fetch": "gnta.ge statistics. THE SERIES RE-BASED between 2020 and 2023; a pooled "
                     "seasonal across that window is meaningless"},
    {"name": "BTC and SCP transit volumes", "source": "operator disclosure and Geostat",
     "coverage": "2006 onward", "frequency": "monthly to annual",
     "publication_lag_days": 30.0, "revisions": "revised", "licence": "free, public",
     "history_from": "2006-06", "pit_feasible": True, "assets": ("XBRUSD", "XNGUSD"),
     "fields": ("period", "btc_throughput_kbd", "scp_throughput_bcm", "transit_fee_usd"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("terms_of_trade", "supply_shock"),
     "how_to_fetch": "operator reports and Geostat services trade; Georgian transit revenue is "
                     "VOLUME-linked, not price-linked, which is why it is a volume story"},
    {"name": "NBG international reserves", "source": "National Bank of Georgia",
     "coverage": "2000 onward", "frequency": "monthly", "publication_lag_days": 7.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2000-01",
     "pit_feasible": True, "assets": ("XAUUSD",),
     "fields": ("month", "gross_reserves_usd", "change", "valuation_effect"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("sovereign_flow",),
     "how_to_fetch": "nbg.gov.ge statistics; reserve changes include valuation and are NOT a "
                     "clean intervention series -- the auction data is"},
    {"name": "Deposit and loan dollarisation ratios", "source": "National Bank of Georgia",
     "coverage": "2003 onward", "frequency": "monthly", "publication_lag_days": 20.0,
     "revisions": "revised", "licence": "free, public", "history_from": "2003-01",
     "pit_feasible": True, "assets": ("USDRUB", "USDTRY"),
     "fields": ("month", "deposit_dollarisation_pct", "loan_dollarisation_pct"),
     "pit_fields": ("publish_ts_utc",),
     "mechanism_families": ("macro_condition",),
     "how_to_fetch": "nbg.gov.ge statistics; the larisation programme of 2017 is a policy break "
                     "in the series and must be modelled"},
    {"name": "Desk MT5 regional tape", "source": "the desk's own Fusion tape",
     "coverage": "2018 onward", "frequency": "tick to daily", "publication_lag_days": 0.0,
     "revisions": "append-only", "licence": "desk-owned", "history_from": "2018-01",
     "pit_feasible": True, "assets": ("USDTRY", "USDRUB", "XBRUSD", "XCUUSD"),
     "fields": ("time", "open", "high", "low", "close", "tick_volume", "spread"),
     "pit_fields": ("time",), "mechanism_families": ("all",),
     "how_to_fetch": "desks/mt5/data/universe/<SYMBOL>_<TF>.parquet -- the only place a Georgian "
                     "mechanism is executable on this box"},
)

# --------------------------------------------------------------------------- the actors
ACTORS: tuple[dict[str, Any], ...] = (
    {
        "name": "National Bank of Georgia as monetary authority",
        "holds": "the policy rate, a standing-facility corridor, and reserves accumulated through "
                 "published auctions",
        "forced_to": ("decide at eight scheduled Wednesday meetings and publish the same day",
                      "publish every FX auction's announcement and result",
                      "publish the money-transfer series monthly with its country split"),
        "when": "15:00 Tbilisi = 11:00 UTC all year; Georgia has no seasonal clock change",
        "information": ("bank-level FX and deposit flow through its own reporting",
                        "the remittance data before publication"),
        "constraints": ("a 3% medium-term inflation target",
                        "an IMF programme relationship that constrains reserve policy",
                        "a very small domestic market, so intervention moves the rate directly"),
        "instruments": ("USDTRY", "USDRUB"),
        "counterparties": ("the domestic banks, principally the two large ones",
                           "the Ministry of Finance"),
        "observables": ("the decision press release",
                        "the auction announcement and the auction result",
                        "monthly reserves and dollarisation ratios"),
        "impact": "the rate transmits through deposit dollarisation and bank lending rather than "
                  "portfolio flow; there is no Georgian instrument on this box to measure it on",
        "persistence": "the framework has been stable since 2009; the larisation package of 2017 "
                       "is the one structural policy break in the transmission channel",
        "falsifier": "the auction calendar as a second control. A currency move on a decision day "
                     "that ALSO has an auction is not attributable to the decision, and this "
                     "confound is the main reason GE-A is hard rather than merely unmeasured",
        "notes": "",
    },
    {
        "name": "The NBG's FX auction as a public intervention",
        "holds": "the intervention book, conducted entirely through announced auctions",
        "forced_to": ("announce an auction before conducting it",
                      "publish the allotted volume and cut-off rate the same day",
                      "intervene when the rate moves faster than the Bank's smoothing tolerance"),
        "when": "event-driven; announcements precede results by hours",
        "information": ("interbank order flow it sees as the platform operator"),
        "constraints": ("a declared free float, so intervention must be justified as smoothing",
                        "reserve adequacy under the IMF programme",
                        "the auction format itself, which makes the size public"),
        "instruments": ("USDTRY", "USDRUB"),
        "counterparties": ("the domestic banks bidding in the auction"),
        "observables": ("the announced amount", "the allotted amount", "the cut-off rate",
                        "the gap between announcement and allotment, which measures demand"),
        "impact": "a dated, sized, public official flow. Almost every other central bank in this "
                  "department intervenes opaquely; Georgia publishes intent AND result, which "
                  "makes it the department's best test of whether public intervention works",
        "persistence": "the auction format has been in place since 2009 and has survived several "
                       "stress episodes",
        "falsifier": "auctions where the allotted amount is far below the announced amount. If "
                     "the currency moves the same whether or not the auction cleared, the "
                     "mechanism is the ANNOUNCEMENT and not the flow -- which is itself a finding",
        "notes": "the announcement-versus-result distinction is the whole research object here",
    },
    {
        "name": "Georgian migrant workers sending money home",
        "holds": "earnings abroad against family obligations at home",
        "forced_to": ("remit on a household calendar -- rent, school fees, seasonal obligations "
                      "-- rather than on an exchange-rate view",
                      "use whatever channel remains open when a corridor is disrupted"),
        "when": "continuous, with published monthly observation; seasonal peaks around holidays",
        "information": ("their own earnings; nothing market-relevant"),
        "constraints": ("payment-channel availability, which changed sharply for the Russian "
                        "corridor after 2022",
                        "transfer costs, which differ by corridor",
                        "their own employment abroad"),
        "instruments": ("USDRUB", "USDTRY"),
        "counterparties": ("Georgian households", "money transfer operators and banks"),
        "observables": ("the NBG monthly money transfer series, SPLIT BY SENDING COUNTRY",
                        "the Russian share, which surged in 2022-2023",
                        "transfer costs by corridor"),
        "impact": "the largest identified external household flow into the economy; a corridor "
                  "disruption is a measurable external shock with a published magnitude",
        "persistence": "the flow is structural and decades old; the CORRIDOR MIX is not, and the "
                       "2022-2023 Russian surge is a level shift rather than a trend",
        "falsifier": "the country split is the falsifier built into the data. A shock attributed "
                     "to the Russian corridor must appear in the RUSSIAN column and not in the "
                     "total alone; if it appears in the total but not the column, it is something "
                     "else",
        "notes": "the data's 15-to-45-day publication lag means the flow happened before the "
                 "observation; a same-month conditioner is a look-ahead",
    },
    {
        "name": "Russian relocatees and their deposits in Georgian banks",
        "holds": "deposits and businesses established in Georgia after 2022",
        "forced_to": ("bank somewhere, and Georgia was visa-free and reachable",
                      "convert to lari for local spending"),
        "when": "concentrated in 2022 and 2023; the stock persists and the flow has slowed",
        "information": ("their own intentions to stay or leave"),
        "constraints": ("Georgian banking compliance, which tightened as the flow grew",
                        "sanctions compliance on the banks' side",
                        "residence and business registration rules"),
        "instruments": ("USDRUB", "USDTRY"),
        "counterparties": ("the Georgian banks", "the domestic property and rental market"),
        "observables": ("non-resident deposit growth in NBG banking statistics",
                        "company registrations by foreign founders",
                        "the money transfer series' Russian column",
                        "rental and property price indices"),
        "impact": "a one-off level shift in deposits, domestic demand and the currency; it is the "
                  "clearest example in this department of a POPULATION flow moving a price",
        "persistence": "the stock has persisted better than most observers expected; the FLOW has "
                       "normalised, so the effect is a level and not a trend",
        "falsifier": "the same statistic for Armenia, which received a comparable flow in the "
                     "same period. A Georgian effect absent in Armenia is Georgian; one present "
                     "in both is the relocation itself",
        "notes": "",
    },
    {
        "name": "BTC and SCP as transit infrastructure across Georgia",
        "holds": "the crude and gas pipelines that cross Georgia from Azerbaijan to Turkey",
        "forced_to": ("run to nomination; the pipelines have no storage of consequence",
                      "publish throughput and announce interruptions"),
        "when": "continuous; maintenance is scheduled and interruptions are not",
        "information": ("their own pipeline status"),
        "constraints": ("physical capacity and Azerbaijani upstream supply",
                        "Georgian transit agreements, which are volume-linked",
                        "regional security, which is the tail risk"),
        "instruments": ("XBRUSD", "XTIUSD", "XNGUSD"),
        "counterparties": ("Azerbaijani producers upstream", "Turkish and European buyers"),
        "observables": ("BTC and SCP throughput",
                        "interruption announcements",
                        "Georgian services-trade transit receipts"),
        "impact": "Georgian transit revenue is VOLUME-linked, so the Georgian economy is exposed "
                  "to throughput and not to price -- the opposite exposure to the Azerbaijani "
                  "pack next door, which is the interesting part",
        "persistence": "structural since 2006; volumes have declined as the ACG field matured and "
                       "risen as Southern Gas Corridor volumes grew",
        "falsifier": "regress Georgian transit receipts on volume and on price separately. If "
                     "price is significant, the transit agreements are not what this pack says",
        "notes": "this actor is where the Georgian, Azerbaijani and Turkish packs physically meet",
    },
    {
        "name": "The vehicle re-export trade through Poti and Batumi",
        "holds": "an import-and-re-export business in used vehicles from Europe and the US to "
                 "Central Asia and Azerbaijan",
        "forced_to": ("route through Georgia because the direct channels are closed or costlier",
                      "adapt quickly when enforcement changes the rules"),
        "when": "continuous; the channel grew sharply after 2022 and steps with enforcement",
        "information": ("their own order books"),
        "constraints": ("enforcement on re-export of sanctioned categories",
                        "port and customs capacity",
                        "destination-market demand and tariffs"),
        "instruments": ("USDRUB", "USDCNH"),
        "counterparties": ("European and US auction sellers",
                           "Central Asian and Azerbaijani buyers"),
        "observables": ("the imports-minus-re-exports divergence in Geostat trade data",
                        "vehicle import values by origin",
                        "enforcement announcements"),
        "impact": "a pure FRICTION trade: it exists because a direct route is closed, and it "
                  "steps rather than drifts. The same shape as the Kazakh and Turkish corridors",
        "persistence": "it has survived several enforcement rounds and re-routed each time",
        "falsifier": "the Kazakh and Turkish corridors at the same enforcement dates. A step in "
                     "all three is enforcement; a step in one is a local story",
        "notes": "the re-export classification in Geostat CHANGED as the channel grew, which is a "
                 "silent break in any long trade panel",
    },
    {
        "name": "Georgian tourism operators and inbound visitors",
        "holds": "an export industry whose customers arrive physically and convert currency",
        "forced_to": ("price a season ahead of knowing the exchange rate",
                      "accept a concentrated summer peak"),
        "when": "the June-September peak and a secondary winter ski season",
        "information": ("forward bookings ahead of the published arrivals"),
        "constraints": ("physical accommodation and aviation capacity",
                        "visa policy and regional security, both outside their control"),
        "instruments": ("USDTRY", "USDRUB"),
        "counterparties": ("Russian, Turkish, Israeli and EU visitors"),
        "observables": ("monthly visitor arrivals by origin",
                        "average spend per visitor",
                        "aviation seat capacity"),
        "impact": "a large seasonal external receipt; it matters to this pack mainly as a CONTROL "
                  "on the remittance channel, because the two have different seasonals and "
                  "different origin mixes",
        "persistence": "the seasonal is structural; the LEVEL broke completely in 2020-2022 and "
                       "the recovery is its own regime",
        "falsifier": "the arrivals series and the remittance series should have DIFFERENT "
                     "seasonals. If a claimed remittance effect follows the tourism seasonal, it "
                     "is tourism",
        "notes": "",
    },
    {
        "name": "The two large Georgian banks (TBC and Bank of Georgia)",
        "holds": "most of the domestic banking system, both listed in London",
        "forced_to": ("comply with sanctions screening as the relocation and re-export flows grew",
                      "meet NBG capital and larisation requirements"),
        "when": "continuous; compliance tightened stepwise as the flows grew",
        "information": ("their own deposit and transaction flow, before anyone else"),
        "constraints": ("NBG prudential requirements and the larisation programme",
                        "correspondent banking relationships, withdrawable at short notice",
                        "London listing obligations, which make their disclosure unusually good"),
        "instruments": ("USDRUB", "USDTRY"),
        "counterparties": ("Georgian households and businesses", "non-resident depositors",
                           "international correspondent banks"),
        "observables": ("their own quarterly disclosure, which is unusually detailed for the "
                        "region because of the London listing",
                        "NBG banking statistics",
                        "deposit dollarisation ratios"),
        "impact": "the transmission channel for the policy rate and the observation point for the "
                  "relocation flow; their disclosure is the best free description of Georgian "
                  "household behaviour available",
        "persistence": "structural; the concentration of the system in two banks is stable",
        "falsifier": "their disclosure should show the relocation flow in non-resident deposits. "
                     "If it does not, the flow went somewhere the desk is not looking",
        "notes": "the single names are ACTORS only; no share CFD appears in this pack",
    },
    {
        "name": "RMG and the Georgian mineral export complex",
        "holds": "copper concentrate and gold from Bolnisi, plus ferroalloy capacity",
        "forced_to": ("ship concentrate to smelters abroad, because there is no domestic smelting "
                      "of consequence",
                      "sell against LME benchmarks with a concentrate treatment charge"),
        "when": "continuous production; shipment is rail- and port-constrained",
        "information": ("their own grades and output"),
        "constraints": ("treatment and refining charges, which are set globally",
                        "rail and port capacity",
                        "environmental and community constraints, which have bound"),
        "instruments": ("XCUUSD", "XAUUSD"),
        "counterparties": ("international smelters and traders"),
        "observables": ("Geostat export values for copper ore and ferroalloys",
                        "LME copper and the concentrate treatment charge"),
        "impact": "the dominant Georgian export GOOD, though small globally; it matters as the "
                  "goods leg against the services legs of remittances, tourism and transit",
        "persistence": "structural; output is mature",
        "falsifier": "regress Georgian export values on the LME price and on volume. If volume "
                     "adds nothing, Georgia is a pure price-taker and this actor is not separately "
                     "informative",
        "notes": "",
    },
    {
        "name": "The Georgian electricity balance and Enguri",
        "holds": "a hydropower-dominated generation system with a strong seasonal swing",
        "forced_to": ("import power in winter when hydro output falls",
                      "export or spill in spring when it peaks"),
        "when": "the winter import season and the spring surplus",
        "information": ("reservoir levels ahead of publication"),
        "constraints": ("hydrology, which is weather",
                        "interconnection capacity with Turkey, Azerbaijan and Russia",
                        "gas-fired backup, which links the power balance to gas prices"),
        "instruments": ("USDTRY", "XNGUSD"),
        "counterparties": ("Turkish, Azerbaijani and Russian power exporters",
                           "gas suppliers for the backup fleet"),
        "observables": ("monthly generation and import/export volumes",
                        "reservoir levels",
                        "regional power prices"),
        "impact": "a seasonal external drain in winter that is priced against regional power and "
                  "gas rather than a global benchmark; a small but genuinely separate channel",
        "persistence": "structural; new hydro capacity has been slow to arrive",
        "falsifier": "the seasonal should track HYDROLOGY, not the calendar. A dry spring that "
                     "does not produce winter imports falsifies the mechanism",
        "notes": "",
    },
    {
        "name": "Geostat as the publisher of the trade and price series",
        "holds": "the official statistics and a published release calendar",
        "forced_to": ("publish CPI in the first days of the month and trade with a 25-day lag",
                      "reclassify when a trade channel grows enough to need its own category -- "
                      "which is what happened to vehicle re-exports"),
        "when": "monthly, on a published calendar",
        "information": ("the number before publication"),
        "constraints": ("the statistics law and the calendar",
                        "a trade classification that had to be revised as the re-export channel "
                        "grew"),
        "instruments": ("USDTRY", "USDRUB"),
        "counterparties": ("the whole market at once", "the National Bank"),
        "observables": ("the CPI release", "the trade release",
                        "the classification version, which is the silent break"),
        "impact": "the observation point for two of this pack's four external legs; there is no "
                  "Georgian instrument on which to measure a release reaction, which is stated",
        "persistence": "permanent as a class",
        "falsifier": "THERE IS NO FALSIFIER AVAILABLE ON THIS BOX, and that is the finding "
                     "rather than an omission: with no Georgian instrument quoted there is no "
                     "series on which a release reaction could be measured, so the effect is "
                     "UNMEASURED BY NAME (L1.28a) rather than assumed to be zero",
        "notes": "the re-export reclassification is a break that will silently corrupt any long "
                 "trade panel that does not carry the classification version",
    },
    {
        "name": "The Ministry of Finance under the fiscal rule",
        "holds": "the budget and a sovereign eurobond curve, under an IMF-anchored fiscal rule "
                 "with published deficit and debt ceilings",
        "forced_to": ("keep the deficit inside the legislated ceiling",
                      "refinance eurobonds on a known maturity schedule"),
        "when": "the budget in December; eurobond maturities on a known schedule",
        "information": ("budget execution before publication"),
        "constraints": ("the fiscal rule's ceilings",
                        "the IMF programme relationship",
                        "a small investor base for domestic paper"),
        "instruments": ("UST10Y", "US500"),
        "counterparties": ("international eurobond investors", "the IMF", "domestic banks"),
        "observables": ("the sovereign eurobond spread",
                        "budget execution against the ceiling",
                        "IMF programme reviews and their outcomes"),
        "impact": "the credit channel; the eurobond spread is the only liquid Georgian price a "
                  "foreign investor can see, and it moves on programme reviews as much as on macro",
        "persistence": "the fiscal rule has held; programme relationships have varied",
        "falsifier": "the spread against a matched regional peer around IMF review dates. If it "
                     "does not move on reviews, the programme is not the mechanism",
        "notes": "",
    },
)

# --------------------------------------------------------------------------- the domains
DOMAINS: tuple[dict[str, Any], ...] = (
    {
        "id": "GE-A", "title": "Policy decisions confounded by the auction calendar",
        "objects": ("the eight scheduled Wednesday decisions at 11:00 UTC",
                    "the quarterly Monetary Policy Report",
                    "the FX auction calendar running alongside"),
        "conditions": ("the AUCTION CALENDAR as a mandatory second conditioner, because the Bank "
                       "is intervening in the same weeks it is deciding",
                       "no consensus proxy exists, so the surprise is UNMEASURED and the study is "
                       "about the DECISION, not the surprise",
                       "the fixed UTC+4 clock, which at least does not move"),
        "instruments": ("USDTRY", "USDRUB"),
        "controls": ("decision days WITHOUT an auction, versus decision days with one",
                     "the eight nearest non-meeting Wednesdays",
                     "USDTRY and USDRUB, which share the regional factor but not the decision",
                     "auction days without a decision, the fourth cell of the two-by-two"),
        "notes": "the two-by-two of decision and auction is the design; without it this domain "
                 "cannot separate the two and would report one as the other",
    },
    {
        "id": "GE-B", "title": "Public intervention: announcement versus result",
        "objects": ("the auction announcement with its size",
                    "the auction result: allotted amount and cut-off rate",
                    "the gap between announced and allotted, which measures demand",
                    "the monthly reserve change, which confirms rather than measures"),
        "conditions": ("announcement and result kept as SEPARATE events hours apart",
                       "the allotment ratio as the demand signal",
                       "reserve changes net of valuation effects"),
        "instruments": ("USDTRY", "USDRUB"),
        "controls": ("auctions where allotment fell far short of the announcement",
                     "announcement-only windows, before the result",
                     "non-auction days at the same UTC minute",
                     "the reserve series as an independent confirmation"),
        "notes": "the department's best test of whether PUBLIC intervention works, because almost "
                 "every other central bank here intervenes opaquely",
    },
    {
        "id": "GE-C", "title": "Remittances by sending country as a published external shock",
        "objects": ("the NBG monthly money transfer series with its country split",
                    "the Russian column and its 2022-2023 surge",
                    "the EU, US, Israeli and Turkish columns",
                    "transfer costs by corridor"),
        "conditions": ("the 15-to-45-day publication lag -- the flow happened BEFORE the "
                       "observation, so a same-month conditioner is a look-ahead",
                       "the country split used as the falsifier, not just as detail",
                       "the corridor's payment-channel availability, which changed in 2022"),
        "instruments": ("USDRUB", "USDTRY"),
        "controls": ("the non-Russian columns over the same months",
                     "Armenia's comparable series, which received a similar flow",
                     "the tourism series, whose seasonal differs",
                     "a placebo country split"),
        "notes": "THE PACK'S FLAGSHIP DOMAIN. Most countries in this book force the desk to infer "
                 "a flow from a price; Georgia publishes the flow, by origin, monthly and free",
    },
    {
        "id": "GE-D", "title": "Transit: a volume exposure, not a price exposure",
        "objects": ("BTC crude throughput", "SCP gas throughput",
                    "Georgian transit receipts in the services account",
                    "interruption announcements"),
        "conditions": ("VOLUME entered separately from PRICE -- the transit agreements are "
                       "volume-linked and that is the whole claim",
                       "interruptions as events with their own timestamps",
                       "the link to the Azerbaijani upstream, which is the supply constraint"),
        "instruments": ("XBRUSD", "XTIUSD", "XNGUSD"),
        "controls": ("the price term, which should NOT be significant if the claim is right",
                     "Azerbaijani production over the same period",
                     "months with no interruption",
                     "the Turkish terminus, where the same barrels arrive"),
        "notes": "Georgia's exposure is the OPPOSITE of Azerbaijan's next door: Georgia earns on "
                 "volume and Azerbaijan on price, which makes the pair a natural experiment",
    },
    {
        "id": "GE-E", "title": "Tourism and the broken sample",
        "objects": ("monthly visitor arrivals by origin",
                    "average spend per visitor",
                    "aviation seat capacity",
                    "the 2020-2022 collapse and the recovery"),
        "conditions": ("the sample SPLIT at the collapse; a pooled seasonal across it is "
                       "meaningless",
                       "origin mix, since Russian, Turkish and EU visitors have different seasons",
                       "seat capacity as the leading variable"),
        "instruments": ("USDTRY", "USDRUB"),
        "controls": ("the remittance series, whose seasonal differs",
                     "the pre-2020 and post-2022 samples tested separately",
                     "Armenia and Turkey's tourism series over the same window"),
        "notes": "included principally as a CONTROL on GE-C: an effect that follows both the "
                 "tourism and the remittance seasonal is southern-summer, not remittances",
    },
    {
        "id": "GE-F", "title": "The vehicle re-export corridor as a friction trade",
        "objects": ("the imports-minus-re-exports divergence in Geostat trade data",
                    "vehicle import values by origin",
                    "enforcement announcements",
                    "the Geostat re-export RECLASSIFICATION"),
        "conditions": ("enforcement as STEPS, not a continuous variable",
                       "the classification version carried on every observation, because the "
                       "reclassification is a silent break",
                       "the destination split, which reveals where the friction is"),
        "instruments": ("USDRUB", "USDCNH", "USDTRY"),
        "controls": ("the Kazakh and Turkish corridors at the same enforcement dates -- a step in "
                     "all three is enforcement and not geography",
                     "the pre-2022 sample",
                     "non-vehicle trade categories"),
        "notes": "the same mechanism as KZ-I and the Turkish corridor; measuring all three "
                 "together is the strongest available evidence",
    },
    {
        "id": "GE-G", "title": "The mineral export complex",
        "objects": ("copper concentrate and gold exports",
                    "ferroalloy exports",
                    "LME benchmarks and the concentrate treatment charge"),
        "conditions": ("volume and price entered separately, to ask whether Georgia is a pure "
                       "price-taker",
                       "the treatment charge, which is set globally and is the margin",
                       "rail and port constraints"),
        "instruments": ("XCUUSD", "XAUUSD"),
        "controls": ("the LME price alone as the null",
                     "a matched small producer country",
                     "months with a known shipping constraint"),
        "notes": "the goods leg against this pack's three services legs; small but genuinely "
                 "separate",
    },
    {
        "id": "GE-H", "title": "The seasonal electricity balance",
        "objects": ("monthly generation, imports and exports",
                    "reservoir levels",
                    "the gas-fired backup fleet",
                    "interconnection capacity with three neighbours"),
        "conditions": ("HYDROLOGY rather than the calendar as the driver -- a dry year changes "
                       "the seasonal",
                       "regional power prices, not a global benchmark",
                       "the gas link, which prices the backup"),
        "instruments": ("USDTRY", "XNGUSD"),
        "controls": ("wet years versus dry years",
                     "the calendar seasonal alone, which should be WEAKER than the hydrology one",
                     "regional power prices over the same months"),
        "notes": "",
    },
    {
        "id": "GE-I", "title": "Dollarisation and the larisation programme",
        "objects": ("deposit and loan dollarisation ratios",
                    "the 2017 larisation package",
                    "the policy rate and the real rate differential",
                    "the relocation-driven non-resident deposit growth"),
        "conditions": ("the 2017 policy break modelled explicitly",
                       "the real rather than nominal rate differential",
                       "resident and non-resident deposits kept apart, since the relocation flow "
                       "moves only one of them"),
        "instruments": ("USDRUB", "USDTRY"),
        "controls": ("the pre-2017 sample",
                     "Armenia's dollarisation series over the same period",
                     "periods of low real rate differential"),
        "notes": "",
    },
    {
        "id": "GE-J", "title": "Sovereign credit, the fiscal rule and the programme",
        "objects": ("the Georgian sovereign eurobond spread",
                    "the legislated deficit and debt ceilings",
                    "IMF programme review dates and outcomes",
                    "the eurobond maturity schedule"),
        "conditions": ("programme review dates as events",
                       "the spread measured against a matched regional peer, not in levels",
                       "global EM credit spreads removed as a factor"),
        "instruments": ("UST10Y", "US500"),
        "controls": ("a matched regional sovereign",
                     "global EM credit spreads",
                     "non-review months",
                     "budget execution months with no review"),
        "notes": "",
    },
    {
        "id": "GE-K", "title": "The Orthodox calendar and the one-week Easter divergence",
        "objects": ("Orthodox Christmas on 7 January and Epiphany on 19 January",
                    "the Julian Easter cycle: Good Friday, Great Saturday, Easter, Easter Monday",
                    "the absence of any Mondayisation rule",
                    "the divergence from Western Easter, up to five weeks"),
        "conditions": ("the ORTHODOX reckoning, always -- 2026 Orthodox Easter is 12 April and "
                       "Western Easter is 5 April",
                       "no Mondayisation: Georgian law absorbs a weekend holiday rather than "
                       "transferring it, unlike Russia and Kazakhstan next door",
                       "the fixed UTC+4 clock"),
        "instruments": ("USDTRY", "USDRUB"),
        "controls": ("the Western Easter dates as the deliberate wrong answer, to demonstrate the "
                     "size of the error",
                     "the Russian calendar, which shares Orthodox Christmas but transfers "
                     "weekend holidays",
                     "the Turkish calendar, which is secular and shares neither"),
        "notes": "a screen using Western Easter places the entire Georgian Easter block in the "
                 "wrong week in most years, and by five weeks in 2024",
    },
    {
        "id": "GE-L", "title": "The absent domestic market as a NAMED GAP",
        "objects": ("the Georgian Stock Exchange, very small and rarely traded",
                    "the absence of any GEL quote on this broker",
                    "the absence of any Georgian rate instrument",
                    "the sovereign eurobond as the only liquid Georgian price"),
        "conditions": ("this domain is DECLARED UNMEASURED and exists to say so",
                       "the eurobond spread as the single available Georgian observable",
                       "Turkish assets as the regional risk proxy, with their different calendar"),
        "instruments": ("USDTRY", "UST10Y"),
        "controls": ("Turkish assets on days when Turkey is shut and Georgia is not",
                     "regional peers' credit spreads"),
        "notes": "recorded rather than omitted (L1.28a): a country whose prices the desk cannot "
                 "see is a named gap, and naming it is a verdict",
    },
)

# --------------------------------------------------------------------------- miners
CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    {"name": "ge_remittance_country_split", "domain_ids": ("GE-C",), "kind": "flow",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ge.miners:remittance_country_split",
     "needs": ("NBG money transfers by sending country", "USDRUB and USDTRY D1 bars"),
     "notes": "uses the country split as the falsifier: a shock attributed to the Russian "
              "corridor must appear in the Russian column, not only in the total"},
    {"name": "ge_auction_announcement_vs_result", "domain_ids": ("GE-B",), "kind": "event",
     "cadence_s": 86400.0, "steerable": True, "wired": False,
     "entry": "countries.ge.miners:auction_announcement_vs_result",
     "needs": ("NBG auction announcements and results with both timestamps",
               "USDTRY and USDRUB M15 bars"),
     "notes": "keeps the two timestamps apart; an under-allotted auction is the key control"},
    {"name": "ge_decision_auction_two_by_two", "domain_ids": ("GE-A",), "kind": "event",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.ge.miners:decision_auction_two_by_two",
     "needs": ("NBG decision dates", "auction calendar", "USDTRY and USDRUB M15 bars"),
     "notes": "builds the four-cell design explicitly; a decision-only estimate is refused "
              "because it is known in advance to be confounded"},
    {"name": "ge_transit_volume_vs_price", "domain_ids": ("GE-D",), "kind": "macro",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ge.miners:transit_volume_vs_price",
     "needs": ("BTC and SCP throughput", "Georgian services trade", "XBRUSD D1 bars"),
     "notes": "the price term is the control and should be insignificant if the pack is right"},
    {"name": "ge_reexport_enforcement_steps", "domain_ids": ("GE-F",), "kind": "policy",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ge.miners:reexport_enforcement_steps",
     "needs": ("Geostat trade with classification version", "enforcement dates",
               "USDRUB and USDTRY D1 bars"),
     "notes": "carries the classification version on every observation; measures alongside the "
              "Kazakh and Turkish corridors"},
    {"name": "ge_tourism_seasonal_split", "domain_ids": ("GE-E",), "kind": "calendar",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ge.miners:tourism_seasonal_split",
     "needs": ("GNTA arrivals by origin", "USDTRY D1 bars"),
     "notes": "splits at the 2020 collapse; exists chiefly as a control for the remittance miner"},
    {"name": "ge_orthodox_calendar", "domain_ids": ("GE-K",), "kind": "calendar",
     "cadence_s": 86400.0, "steerable": False, "wired": False,
     "entry": "countries.ge.miners:orthodox_calendar",
     "needs": ("the Georgian holiday calendar", "USDTRY and USDRUB H1 bars"),
     "notes": "runs the Western-Easter version deliberately as the wrong answer, to publish the "
              "size of the error a Western-calendar screen would make"},
    {"name": "ge_sovereign_spread_reviews", "domain_ids": ("GE-J",), "kind": "event",
     "cadence_s": 604800.0, "steerable": True, "wired": False,
     "entry": "countries.ge.miners:sovereign_spread_reviews",
     "needs": ("IMF review dates", "a Georgian eurobond spread series if obtainable",
               "UST10Y D1 bars"),
     "notes": "reports UNMEASURED when no spread series can be sourced, rather than substituting "
              "a regional index"},
)

# --------------------------------------------------------------------------- transmission edges
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    {"source": "NBG money transfers from Russia (monthly, country split)", "target": "USDRUB",
     "sign": "-",
     "mechanism": "a large household flow out of Russia into a small neighbouring economy; the "
                  "rouble side is a genuine outflow and the series measures it directly",
     "horizon": "20 to 90 sessions",
     "condition": "the 15-to-45-day publication lag means the flow precedes the observation; a "
                  "same-month conditioner is a look-ahead",
     "control": "the non-Russian columns of the same series, and Armenia's comparable series",
     "falsifier": "a total-transfer shock with no movement in the Russian column, which would "
                  "mean the flow came from somewhere else"},
    {"source": "NBG FX auction announcement", "target": "USDTRY", "sign": "two_sided",
     "mechanism": "a dated, sized, public official flow in a small open economy; the regional "
                  "proxy carries whatever spillover exists because the lari is not quoted here",
     "horizon": "0 to 3 sessions",
     "condition": "the ANNOUNCEMENT, separately from the result; and this edge is declared WEAK "
                  "because the target is a proxy",
     "control": "under-allotted auctions, and non-auction days at the same minute",
     "falsifier": "no measurable spillover, which would confirm that Georgian official flow is "
                  "unmeasurable on this box"},
    {"source": "BTC crude transit interruption across Georgia", "target": "XBRUSD", "sign": "+",
     "mechanism": "Azeri Light crossing Georgia to the Turkish Mediterranean; an interruption is "
                  "a physical supply event on a route with no storage of consequence",
     "horizon": "0 to 10 sessions",
     "condition": "the interruption's duration sizes the loss; upstream Azerbaijani supply must "
                  "be available or the interruption is not binding",
     "control": "XTIUSD, which shares the global price but not the route",
     "falsifier": "an equal XTIUSD response, which would make it a global price move"},
    {"source": "South Caucasus Pipeline throughput", "target": "XNGUSD", "sign": "-",
     "mechanism": "Shah Deniz gas crossing Georgia to Turkey and Italy -- Europe's only "
                  "non-Russian pipeline route from the Caspian",
     "horizon": "20 to 90 sessions",
     "condition": "the desk's gas quote is HENRY HUB, not European; this edge is declared WEAK "
                  "for that reason and every cell using it must say so",
     "control": "EUSTX50 and GER40, where the European industrial-margin channel is measurable",
     "falsifier": "no European equity response to a corridor interruption, which would mean the "
                  "volumes are small relative to European supply"},
    {"source": "Georgian vehicle re-export enforcement", "target": "USDRUB", "sign": "two_sided",
     "mechanism": "a friction trade that exists because a direct route is closed; enforcement "
                  "steps the channel's cost and narrows the flow",
     "horizon": "5 to 60 sessions",
     "condition": "enforcement dates as steps; the Geostat classification version carried",
     "control": "the Kazakh and Turkish corridors at the same dates",
     "falsifier": "no step in any of the three corridors at enforcement dates"},
    {"source": "Georgian copper concentrate exports", "target": "XCUUSD", "sign": "-",
     "mechanism": "a small producer shipping concentrate against LME benchmarks; the question is "
                  "whether the volume is large enough to matter at all",
     "horizon": "20 to 90 sessions",
     "condition": "volume entered separately from price; the null is pure price-taking",
     "control": "the LME price alone",
     "falsifier": "no separate significance for Georgian volume, the expected outcome"},
    {"source": "Georgian winter power imports", "target": "USDTRY", "sign": "+",
     "mechanism": "a hydropower system that imports in winter from Turkey and neighbours; the "
                  "import bill is a seasonal external drain priced regionally",
     "horizon": "the winter season",
     "condition": "conditioned on HYDROLOGY, not on the calendar",
     "control": "wet years versus dry years",
     "falsifier": "a winter effect in a wet year, which would make it the calendar and not the "
                  "water"},
    {"source": "Russian relocatee deposits in Georgian banks", "target": "USDRUB", "sign": "-",
     "mechanism": "a population flow moving capital across a border; deposits, domestic demand "
                  "and the currency all shift together as a level rather than a trend",
     "horizon": "60 to 250 sessions",
     "condition": "the 2022-2023 window; the flow has since normalised and the effect is a level",
     "control": "Armenia, which received a comparable flow in the same period",
     "falsifier": "a Georgian effect absent in Armenia is Georgian; one present in both is the "
                  "relocation itself and not a Georgian mechanism"},
    {"source": "Georgian policy rate decision", "target": "USDTRY", "sign": "-",
     "mechanism": "the regional policy factor; Georgia and Turkey share a trade relationship and "
                  "a risk classification, so a Georgian tightening carries weak regional news",
     "horizon": "0 to 3 sessions",
     "condition": "the auction calendar as a mandatory second conditioner",
     "control": "the eight nearest non-meeting Wednesdays; and decision days without an auction",
     "falsifier": "an equal move on auction-only days, which would attribute the effect to the "
                  "auction rather than the decision"},
    {"source": "Georgian Orthodox Easter block", "target": "USDTRY", "sign": "two_sided",
     "mechanism": "a four-day domestic closure with no Mondayisation, a week later than Western "
                  "Easter in 2026; the regional book is one-sided for those sessions",
     "horizon": "the Easter block",
     "condition": "the ORTHODOX date; the Western date is the deliberate wrong answer",
     "control": "the Western Easter dates run as the wrong answer, and days when both are open",
     "falsifier": "no difference between the Orthodox and Western windows, which would mean the "
                  "Georgian closure is irrelevant to the proxy -- itself a useful finding"},
    {"source": "Georgian international visitor arrivals", "target": "USDTRY", "sign": "-",
     "mechanism": "tourism receipts are a large external leg; Turkish visitors and Turkish "
                  "aviation capacity are a substantial share of it",
     "horizon": "the summer season",
     "condition": "the sample split at the 2020 collapse; origin mix carried",
     "control": "the remittance series, whose seasonal differs",
     "falsifier": "an effect that follows both the tourism and the remittance seasonal, which "
                  "would make it southern-summer and neither"},
    {"source": "Georgian sovereign eurobond spread around IMF reviews", "target": "UST10Y",
     "sign": "two_sided",
     "mechanism": "programme reviews are scheduled credit events for a small frontier sovereign; "
                  "the spread moves on the review outcome as much as on macro",
     "horizon": "0 to 10 sessions",
     "condition": "measured against a matched regional peer, not in levels; declared WEAK because "
                  "the Georgian spread itself may not be obtainable",
     "control": "a matched regional sovereign; global EM credit spreads",
     "falsifier": "no spread move on review dates, which would mean the programme is priced "
                  "continuously rather than at reviews"},
)

# --------------------------------------------------------------------------- eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    {"name": "inflation targeting and the floating lari", "start": "2009-01-01",
     "end": "2016-12-31",
     "regime": "a formal inflation target with a floating lari and auction-based intervention; a "
               "sharp depreciation in 2015 as regional currencies fell together",
     "markers": ("2015 the regional depreciation",),
     "why_it_matters": "the baseline regime; every Georgian relationship that is stable at all is "
                       "stable here",
     "status": "SETTLED"},
    {"name": "the larisation programme", "start": "2017-01-01", "end": "2020-02-29",
     "regime": "a policy package restricting small foreign-currency lending and pushing deposit "
               "and loan dollarisation down",
     "markers": ("2017 the larisation package",),
     "why_it_matters": "a deliberate structural break in the monetary transmission channel; GE-I "
                       "is built on this boundary and a dollarisation series pooled across it "
                       "describes two different systems",
     "status": "SETTLED"},
    {"name": "the pandemic and the closed border", "start": "2020-03-01", "end": "2022-02-23",
     "regime": "tourism and remittances collapsed together; heavy fiscal and external support",
     "markers": ("2020-03 the border closure",),
     "why_it_matters": "both of this pack's largest external legs went to zero at once, so the "
                       "sample is unusable for any seasonal estimate and GE-E splits here",
     "status": "SETTLED"},
    {"name": "the relocation and remittance surge", "start": "2022-02-24", "end": "2023-12-31",
     "regime": "a large inflow of Russian relocatees and remittances, a booming re-export trade, "
               "sharp lari appreciation and rapid reserve accumulation",
     "markers": ("2022 the relocation wave", "the Russian remittance column multiplying",
                 "the vehicle re-export channel opening"),
     "why_it_matters": "the largest identified shock in Georgian external accounts and the reason "
                       "GE-C is this pack's flagship domain; nothing before it is comparable",
     "status": "SETTLED"},
    {"name": "normalisation and enforcement", "start": "2024-01-01", "end": "2099-12-31",
     "regime": "the relocation flow normalising, enforcement rounds narrowing the re-export "
               "channel, the policy rate easing from its peak",
     "markers": ("enforcement rounds on re-export categories",),
     "why_it_matters": "UNVERIFIED TAIL. Anything this pack asserts about 2025-2026 Georgian "
                       "policy or flows must be re-read from nbg.gov.ge and geostat.ge before a "
                       "study conditions on it",
     "status": "UNVERIFIED_TAIL"},
)

# --------------------------------------------------------------------------- access constraints
ACCESS_CONSTRAINTS: tuple[dict[str, Any], ...] = (
    {"constraint": "no Georgian instrument is quoted by this broker",
     "measured": "GEL, the Georgian Stock Exchange and every Georgian bond are absent from "
                 "data/universe/universe.json",
     "consequence": "TRANSMISSION-ONLY by construction. Every domain terminates in a foreign "
                    "symbol, and GE-L exists to declare the domestic market UNMEASURED"},
    {"constraint": "no consensus proxy exists for the policy rate",
     "measured": "Georgia has no liquid short-rate curve the desk can reach and no reliably "
                 "obtainable survey",
     "consequence": "a Georgian policy SURPRISE is UNMEASURED. GE-A studies the DECISION, not the "
                    "surprise, and says so rather than manufacturing an expectation"},
    {"constraint": "the decision and the intervention share a calendar",
     "measured": "NBG FX auctions are conducted in the same weeks as policy decisions",
     "consequence": "any currency reaction on a decision day that also carries an auction is "
                    "confounded. GE-A requires the four-cell design and refuses a decision-only "
                    "estimate"},
    {"constraint": "the remittance series is 15 to 45 days stale on arrival",
     "measured": "NBG publishes mid-month for the preceding month",
     "consequence": "the flow happened before the observation. A same-month conditioner is a "
                    "look-ahead, and the publication is a separate event from the flow"},
    {"constraint": "the Geostat re-export classification changed as the vehicle channel grew",
     "measured": "the trade classification was revised when re-exports became material",
     "consequence": "a silent break in any long trade panel. Every observation must carry the "
                    "classification version or the break will be read as a trade shock"},
    {"constraint": "no lari positioning series exists anywhere",
     "measured": "no CME contract has ever existed for GEL",
     "consequence": "lari positioning is permanently UNMEASURED; cot_currency is deliberately "
                    "empty and no substitute is permitted"},
    {"constraint": "the desk's gas quote is Henry Hub, not European",
     "measured": "XNGUSD is a US benchmark",
     "consequence": "the Southern Gas Corridor edge is declared WEAK, and the European industrial-"
                    "margin channel is measured on EUSTX50 and GER40 instead, which the desk can "
                    "actually see"},
)

# --------------------------------------------------------------------------- assembly
_PACK_FIELDS: tuple[str, ...] = (
    "code", "name", "region_command", "currency", "executable_instruments", "central_bank",
    "fixing_conventions", "settlement_conventions", "exchanges", "holidays_rule",
    "fiscal_year_end", "positioning_sources", "native_languages", "terminology", "source_classes",
    "datasets", "actors", "domains", "custom_miners", "transmission_edges_seed", "policy_eras")


def as_dict() -> dict[str, Any]:
    """The pack as a plain mapping, carrying the transmission targets and access constraints
    alongside the frozen fields."""
    return {
        "code": CODE, "name": NAME, "region_command": REGION_COMMAND, "currency": CURRENCY,
        "executable_instruments": EXECUTABLE_INSTRUMENTS, "central_bank": CENTRAL_BANK,
        "fixing_conventions": FIXING_CONVENTIONS,
        "settlement_conventions": SETTLEMENT_CONVENTIONS, "exchanges": EXCHANGES,
        "holidays_rule": HOLIDAYS_RULE, "fiscal_year_end": FISCAL_YEAR_END,
        "positioning_sources": POSITIONING_SOURCES, "native_languages": NATIVE_LANGUAGES,
        "terminology": TERMINOLOGY, "source_classes": SOURCE_CLASSES,
        "datasets": DATASETS, "source_layers": SOURCE_LAYERS,
        "layer_absences": LAYER_ABSENCES, "layer_terms": layer_terms(),
        "source_layer_coverage": source_layer_coverage(),
        "actors": ACTORS, "domains": DOMAINS, "custom_miners": CUSTOM_MINERS,
        "transmission_edges_seed": TRANSMISSION_EDGES_SEED, "policy_eras": POLICY_ERAS,
        "transmission_targets": TRANSMISSION_TARGETS, "access_constraints": ACCESS_CONSTRAINTS,
        "region_desk": REGION_DESK, "cot_currency": COT_CURRENCY,
    }


def pack() -> Any:
    """`libs.research.country_lab.CountryPack` when that module has landed, else this mapping."""
    data = as_dict()
    try:
        from libs.research import country_lab
    except ImportError:
        return data
    cls = getattr(country_lab, "CountryPack", None)
    if cls is None:
        return data
    try:
        return cls(**{k: v for k, v in data.items() if k in _PACK_FIELDS})
    except (TypeError, ValueError):
        return data
