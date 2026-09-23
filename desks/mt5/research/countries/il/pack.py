"""THE ISRAEL COUNTRY PACK -- a floating shekel, a hedging rule, and NASDAQ in disguise.

WHY ISRAEL IS THE OPPOSITE OF THE GULF AND BELONGS IN THE SAME CIVILIZATION. Saudi Arabia and the
Emirates reach this desk through oil, liquidity and a peg that makes their policy rate the Fed's.
Israel reaches it through a CURRENCY THE BROKER ACTUALLY QUOTES. USDILS and EURILS are both in the
registry, the shekel floats, and the Bank of Israel has a genuine reaction function with eight
dated decisions a year and published minutes. Everything the Gulf packs must express through gold
and crude, this pack can express directly.

THE MECHANISM THIS PACK EXISTS FOR, AND IT IS A RULE RATHER THAN A MOOD. Israeli institutional
investors -- the pension, provident and study funds -- hold a very large foreign equity portfolio
and hedge its currency exposure. When global equities RISE, the value of the hedged asset rises,
the hedge must be topped up, and topping it up means SELLING DOLLARS FOR SHEKELS. When equities
fall, the flow reverses. That gives USDILS a mechanical, documented negative relationship to the
S&P 500 and to NASDAQ which is driven by a REBALANCING RULE, not by sentiment or carry. It is the
cleanest forced-flow story anywhere in the Middle East civilization, and unlike every Gulf
mechanism it terminates in an instrument the box can quote.

FOUR MORE THINGS THAT ARE ISRAEL'S AND NOBODY ELSE'S HERE:

  * A TECHNOLOGY SECTOR LARGE ENOUGH TO BE AN FX ACTOR. Exit proceeds, venture inflows and the
    monthly dollar conversion for local payroll are a structural shekel bid, and their cycle is
    NASDAQ's rather than the Middle East's.
  * A CENTRAL BANK THAT INTERVENES ON ANNOUNCED PROGRAMMES. The 2008-2013 purchase era, the 2021
    pre-announced 30-billion-dollar annual purchase plan, and the October 2023 SALE programme --
    the first in its history -- are dated regime boundaries, not a continuous reaction function.
  * AN ECONOMY INDEXED TO ITS OWN CPI. The מדד governs index-linked bonds, mortgages and many
    contracts, so the monthly CPI print at 18:30 local is a bigger event in Israel than a CPI
    print is almost anywhere else.
  * A SUNDAY SESSION AND A DAYLIGHT-SAVING CLOCK. TASE trades SUNDAY TO THURSDAY, so Israel prices
    weekend news before the desk's venue reopens -- the Gulf asymmetry again, in a market whose
    own currency the desk can trade. And unlike the Gulf, Israel OBSERVES DAYLIGHT SAVING, on its
    own dates, so every broker-hour mapping here moves twice a year and not in step with the US.

WHAT THIS PACK MAY NOT DO. Israeli single names -- the technology exporters above all -- are
observables and never hypotheses (two-lane order, 2026-09-06); TA-35 is absent from the registry
and is named in `ABSENT_INSTRUMENTS` with what carries it. No crypto-exchange ground is hunted
(mandate 2026-08-18).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from countries import (
    DATASET_FIELDS,
    actor,
    build_pack,
    dataset,
    domain,
    edge,
    era,
    holiday_table,
    miner,
    resolve,
)
from countries.sa.pack import (
    LAYERS,
    absent_layer,
    check_sources,
    layer_counts,
    me_source,
)

CODE = "il"
NAME = "Israel"
REGION_COMMAND = "MIDDLE_EAST"
CURRENCY = "ILS"
NATIVE_LANGUAGES = ("he", "en")

__all__ = ["LAYERS", "absent_layer", "check_sources", "has_hebrew", "hebrew_terms", "holidays",
           "instrument_report", "layer_counts", "me_source", "pack"]

#: Hebrew, as Unicode sees it: the base block plus the presentation forms a PDF or a copy-paste
#: from a Hebrew newspaper often carries. The parent package's `has_script` knows han, hangul and
#: kana only -- see the note in `countries.sa.pack` -- so the Middle East packs carry their own
#: detectors and the tests assert on them. A miner searching for `שער יציג` finds the Bank of
#: Israel's own page; one searching for "representative rate" finds an English summary of it.
HEBREW_RANGES: tuple[tuple[int, int], ...] = ((0x0590, 0x05FF), (0xFB1D, 0xFB4F))


def has_hebrew(text: str) -> bool:
    """True when `text` carries at least one Hebrew codepoint."""
    return any(any(lo <= ord(ch) <= hi for lo, hi in HEBREW_RANGES) for ch in str(text))


def hebrew_terms(terminology: dict[str, tuple[str, ...]]) -> list[str]:
    """Every term in a terminology table actually written in Hebrew script."""
    return [t for terms in terminology.values() for t in terms if has_hebrew(t)]


#: Israel's OWN price, and it is real: the only Middle East currency this broker quotes, in two
#: crosses. That single fact is why this pack can test its own mechanisms directly.
OWN_PRICE: tuple[str, ...] = ("USDILS", "EURILS")

#: What the IL department may place an order in. Every one is in the broker's registry and none is
#: a single-name equity.
EXECUTABLE_INSTRUMENTS: tuple[str, ...] = (
    "USDILS", "EURILS", "NAS100", "US500", "US30", "US2000", "GER40", "XAUUSD", "USDX", "EURUSD",
    "USDJPY", "UST05Y", "UST10Y")

ABSENT_INSTRUMENTS: tuple[dict[str, str], ...] = (
    {"instrument": "TA-35 (and the TA-125), or their futures",
     "why": "no Israeli equity index CFD in desks/mt5/data/universe/universe.json",
     "carried_by": "NAS100 for the technology beta, US500 for the global risk leg and USDILS for "
                   "the flow leg -- and the flow leg is the one that carries the actual Israeli "
                   "mechanism, so the missing index costs less here than it would elsewhere"},
    {"instrument": "Israeli government bonds (shekel and CPI-linked), and makam",
     "why": "no Israeli rates instrument is quoted",
     "carried_by": "UST05Y and UST10Y as the global duration leg; the Israeli term premium, the "
                   "CPI-linked breakeven and the makam curve are UNMEASURED by name"},
    {"instrument": "USDILS options and the implied volatility surface",
     "why": "the broker quotes spot only",
     "carried_by": "nothing. Hedging-flow intensity is inferred from spot behaviour and from "
                   "published institutional exposure, and the pack says so rather than assuming "
                   "a vol series it does not hold"},
    {"instrument": "Israeli natural gas (Leviathan, Tamar) and the Egyptian export contracts",
     "why": "no regional gas instrument is quoted",
     "carried_by": "XNGUSD as a global gas proxy with the basis named as UNMEASURED; the Egyptian "
                   "leg belongs to the Africa civilization and is read from an `eg` pack when one "
                   "exists"},
)

TRANSMISSION_TARGETS: tuple[str, ...] = ("USDILS", "EURILS", "NAS100", "US500", "US2000",
                                         "XAUUSD", "USDX", "UST10Y")


# --------------------------------------------------------------------------- central bank
CENTRAL_BANK: dict[str, Any] = {
    "name": "Bank of Israel",
    "native_name": "בנק ישראל",
    "committee": "the Monetary Committee (הוועדה המוניטרית): the Governor, two more Bank members "
                 "and three external members. A REAL COMMITTEE with a published vote -- the only "
                 "one in this civilization, and the reason Israel is the only Middle East country "
                 "where a dissent count is an observable.",
    "policy_rate": "ריבית בנק ישראל, the Bank of Israel rate",
    "meetings_per_year": 8,
    "schedule_rule": (
        "EIGHT scheduled decisions a year, dates published a year ahead. The decision is "
        "announced at 16:00 Israel time -- 14:00 UTC in winter, 13:00 UTC in summer -- with the "
        "Governor's press conference following. That is INSIDE the London afternoon and before "
        "the New York close, so unlike a Gulf announcement it lands while the desk's own tape is "
        "at its most liquid. The decision and the press conference are two events in one session "
        "and must be studied as two."),
    "minutes_rule": "the discussion summary is published about two weeks after each decision, "
                    "with the VOTE SPLIT. A dissent is an observable here in a way it is nowhere "
                    "else in the region.",
    "timezone": "ISRAEL OBSERVES DAYLIGHT SAVING: IST = UTC+2 in winter, IDT = UTC+3 in summer, "
                "on ISRAEL'S OWN transition dates (the Friday before the last Sunday of March, "
                "and the Sunday of the fast of Gedaliah in the autumn) which match NEITHER the "
                "EU's nor the US's. So the UTC time of a 16:00 decision moves twice a year, on "
                "dates no other pack in this civilization shares, and a study that hard-codes one "
                "offset is wrong for part of every year.",
    "fx_operations": (
        "The Bank has intervened on ANNOUNCED PROGRAMMES rather than continuously, and the "
        "programmes are the regimes: 2008-2013 purchases (including a published daily purchase "
        "rule at the start); 2013-2020 a gas-offset purchase programme; 2021 a PRE-ANNOUNCED "
        "30-billion-dollar annual purchase plan -- the first time the size was set in advance; "
        "and October 2023 a SALE programme of up to 30 billion dollars plus swap lines, the first "
        "sale programme in the Bank's history, announced within days of the war's outbreak. "
        "Reserves are the meter and the announcements are the dates."),
    "balance_sheet": "reserves rose from roughly 30 billion dollars in 2008 to well over 200 "
                     "billion by 2022 through those programmes -- one of the largest reserve "
                     "accumulations relative to GDP in the world, and the accumulated result of a "
                     "rule rather than of a surplus",
    "other_instruments": "מק\"ם (makam), the Bank's own short-term bills, are the domestic "
                         "liquidity instrument and their curve is the local money-market read",
    "falsifier": "the Bank changes its rate three times running on dates outside the published "
                 "schedule with no emergency, and the 'eight dated decisions' structure this pack "
                 "relies on is dead.",
}


# --------------------------------------------------------------------------- conventions
FIXING_CONVENTIONS: dict[str, Any] = {
    "representative_rate": {
        "name": "שער יציג -- the representative rate",
        "publisher": "Bank of Israel",
        "published_local": "about 15:15 Israel time each business day",
        "published_utc": "13:15 UTC in winter, 12:15 UTC in summer",
        "definition": "a reference rate set from the interbank market around the fixing window, "
                      "used for contracts, accounting and index-linkage across the economy",
        "why_it_matters": "a large share of domestic contracts references it, so there is a "
                          "genuine flow INTO the fixing window. That makes the fifteen minutes "
                          "around 15:15 local a microstructure object, and a daily-bar study "
                          "cannot see it.",
    },
    "float": {
        "regime": "a free float since 2005, with ANNOUNCED intervention programmes rather than a "
                  "band or a target",
        "what_a_regime_change_looks_like": "the Bank announces a programme with a SIZE and "
                                           "sometimes a DAILY RATE. That is a dated, quantified "
                                           "policy event -- the opposite of the Gulf's pegs, "
                                           "where the policy is a constant and only the stress "
                                           "is observable.",
    },
    "makam": {
        "name": "מק\"ם -- Bank of Israel short-term bills",
        "what": "the domestic money-market instrument; its curve is the local rate expectation",
        "why_it_matters": "the makam curve is the only Israeli rate curve that is public, daily "
                          "and continuous, and it is how a policy-expectation surprise is "
                          "measured without an OIS market",
    },
    "cpi_index": {
        "name": "מדד המחירים לצרכן -- the consumer price index",
        "publisher": "the Central Bureau of Statistics",
        "published_local": "the 15th of each month at 18:30 Israel time, for the preceding month",
        "why_it_matters": "Israel is an INDEXED economy: CPI-linked government bonds, mortgages "
                          "and many commercial contracts settle on this number, so the print "
                          "moves the local curve and the shekel more than a CPI print does in "
                          "most economies. The release is also AFTER the local close, so its "
                          "first price expression is in USDILS offshore.",
    },
    "dst": "ISRAEL OBSERVES DST, on its own dates. This is the only pack in the Middle East "
           "civilization where the local-to-UTC mapping moves at all, and it moves out of step "
           "with both the EU and the US -- so there are short windows each year when the Israeli "
           "offset relative to New York or London is one hour different from the rest of the year.",
}

SETTLEMENT_CONVENTIONS: dict[str, Any] = {
    "spot_fx": "T+2 for the shekel",
    "equity_settlement": "T+1 at TASE, which Israel has run for far longer than most markets "
                         "(DECLARED: confirm against the exchange's current rulebook before any "
                         "settlement-sensitive study)",
    "trading_week": "SUNDAY TO THURSDAY, with Friday and Saturday closed. The SUNDAY session is "
                    "SHORT and is the only Israeli session with no overlap with any major market "
                    "-- so weekend news is priced in Tel Aviv, in shekels, before the desk's own "
                    "tape reopens. Israel shares this asymmetry with Saudi Arabia, Qatar and "
                    "Kuwait and NOT with the UAE, which moved to a Monday-to-Friday week in 2022.",
    "month_end": "institutional rebalancing clusters at month end, which is when the foreign-"
                 "equity hedging flow is largest and most mechanical",
    "index_linkage": "CPI linkage settles on the מדד print, so the fifteenth of the month is a "
                     "genuine domestic settlement event and not only a data release",
    "holiday_density": "the Tishrei cluster (Rosh Hashanah, Yom Kippur, Sukkot, Simchat Torah) "
                       "removes a large fraction of September-October trading sessions in some "
                       "years. A monthly seasonal estimated without conditioning on the Hebrew "
                       "calendar is estimating a different number of sessions each year and "
                       "calling it a month.",
}

EXCHANGES: dict[str, Any] = {
    "cash": {
        "name": "Tel Aviv Stock Exchange (TASE, הבורסה לניירות ערך בתל אביב)",
        "week": "Sunday to Thursday",
        "hours_local": "Sunday is a SHORT session; Monday to Thursday run longer, with an opening "
                       "phase, continuous trading and a closing auction",
        "hours_utc": "roughly 07:00-14:30 UTC in winter and 06:00-13:30 UTC in summer, moving "
                     "with Israel's own DST dates -- DECLARED from the exchange's published "
                     "schedule and not verified on this box",
        "indices": "TA-35 (ת\"א 35) and TA-125; the index is dominated by banks and technology, "
                   "which is why it reads as a levered mix of local rates and NASDAQ",
        "dual_listing": "many large Israeli names are dual-listed in New York, so the Tel Aviv "
                        "session prices the New York close and the New York session prices the "
                        "Tel Aviv one. The dual-listing loop is a genuine information channel and "
                        "no single name in it is ever a hypothesis here.",
    },
    "derivatives": {
        "name": "the TASE derivatives market (מעו\"ף)",
        "products": "TA-35 options and futures, shekel-dollar options, weekly and monthly series",
        "expiry_rule": "DECLARED, NOT VERIFIED on this box: the monthly TA-35 series settles in "
                       "the final week of the contract month against an average of the index over "
                       "a published window, and weekly series expire on Thursdays. Any expiry "
                       "study must read the current contract specification first and is "
                       "UNMEASURED until it does.",
        "why_it_matters": "the shekel-dollar option market is where hedging demand is priced, and "
                          "the desk holds NO volatility series -- so hedging intensity is "
                          "inferred and the inference is labelled.",
    },
    "foreign_access": {
        "status": "fully open; Israel is in the MSCI and FTSE developed-market indices, which "
                  "means its foreign flow behaves like a developed market's and not like the "
                  "Gulf's emerging-market inclusion flows",
        "note": "the 2010 MSCI upgrade from emerging to developed was a dated, forced-flow event "
                "with the OPPOSITE sign to Saudi Arabia's 2019 inclusion -- emerging-market funds "
                "had to sell",
    },
}

FISCAL_YEAR_END: dict[str, str] = {
    "government": "31 December. Israel has repeatedly operated under a CONTINUATION BUDGET when "
                  "no budget passed (2020-2021 most notably), which is a fiscal regime of its own "
                  "and not a normal year",
    "corporate": "31 December",
    "war_financing": "the 2023-2024 war was financed by a large supplementary deficit and heavy "
                     "issuance, both domestic and international; the deficit path is a dated "
                     "series and is the fiscal-impulse variable for that era",
    "budget_cycle": "the budget is legislated by the Knesset; a failure to pass triggers the "
                    "continuation budget and, historically, an election -- so Israeli fiscal "
                    "events carry a POLITICAL hazard that has no Gulf equivalent",
}


# --------------------------------------------------------------------------- holidays
#: THE HEBREW CALENDAR PROBLEM, STATED ONCE. Israeli market closures are HEBREW-CALENDAR dates,
#: and the Hebrew calendar is LUNISOLAR with a fixed nineteen-year intercalation cycle: it is
#: fully COMPUTABLE (unlike the Hijri calendar, which waits on a sighting) but it does not map to
#: a Gregorian weekday rule, so the tables below are anchored on the Hebrew year and written out.
#: Festivals drift within a roughly four-week Gregorian window and the Tishrei cluster can remove
#: a large share of the September-October sessions.
_IL_HOLIDAYS: dict[int, dict[str, str]] = {
    2024: {
        "2024-03-24": "פורים Purim (14 Adar II 5784)",
        "2024-04-22": "ערב פסח Passover eve",
        "2024-04-23": "פסח Passover, first day (15 Nisan 5784)",
        "2024-04-29": "שביעי של פסח seventh day of Passover",
        "2024-05-13": "יום הזיכרון Memorial Day",
        "2024-05-14": "יום העצמאות Independence Day (5 Iyar 5784)",
        "2024-06-11": "ערב שבועות Shavuot eve",
        "2024-06-12": "שבועות Shavuot (6 Sivan 5784)",
        "2024-08-13": "תשעה באב Tisha B'Av (9 Av 5784)",
        "2024-10-02": "ערב ראש השנה Rosh Hashanah eve",
        "2024-10-03": "ראש השנה Rosh Hashanah (1 Tishrei 5785)",
        "2024-10-04": "ראש השנה Rosh Hashanah, second day",
        "2024-10-11": "ערב יום כיפור Yom Kippur eve",
        "2024-10-12": "יום כיפור Yom Kippur (10 Tishrei 5785, a Saturday)",
        "2024-10-16": "ערב סוכות Sukkot eve",
        "2024-10-17": "סוכות Sukkot, first day (15 Tishrei 5785)",
        "2024-10-24": "שמחת תורה Simchat Torah",
    },
    2025: {
        "2025-03-14": "פורים Purim (14 Adar 5785, a Friday -- TASE is closed Fridays anyway)",
        "2025-04-12": "ערב פסח Passover eve",
        "2025-04-13": "פסח Passover, first day (15 Nisan 5785)",
        "2025-04-19": "שביעי של פסח seventh day of Passover",
        "2025-04-30": "יום הזיכרון Memorial Day",
        "2025-05-01": "יום העצמאות Independence Day (5 Iyar 5785)",
        "2025-06-01": "ערב שבועות Shavuot eve",
        "2025-06-02": "שבועות Shavuot (6 Sivan 5785)",
        "2025-08-03": "תשעה באב Tisha B'Av (9 Av 5785)",
        "2025-09-22": "ערב ראש השנה Rosh Hashanah eve",
        "2025-09-23": "ראש השנה Rosh Hashanah (1 Tishrei 5786)",
        "2025-09-24": "ראש השנה Rosh Hashanah, second day",
        "2025-10-01": "ערב יום כיפור Yom Kippur eve",
        "2025-10-02": "יום כיפור Yom Kippur (10 Tishrei 5786)",
        "2025-10-06": "ערב סוכות Sukkot eve",
        "2025-10-07": "סוכות Sukkot, first day (15 Tishrei 5786)",
        "2025-10-14": "שמחת תורה Simchat Torah",
    },
    2026: {
        "2026-03-03": "פורים Purim (14 Adar 5786)",
        "2026-04-01": "ערב פסח Passover eve",
        "2026-04-02": "פסח Passover, first day (15 Nisan 5786)",
        "2026-04-08": "שביעי של פסח seventh day of Passover",
        "2026-04-21": "יום הזיכרון Memorial Day",
        "2026-04-22": "יום העצמאות Independence Day (5 Iyar 5786)",
        "2026-05-21": "ערב שבועות Shavuot eve",
        "2026-05-22": "שבועות Shavuot (6 Sivan 5786, a Friday)",
        "2026-07-23": "תשעה באב Tisha B'Av (9 Av 5786)",
        "2026-09-11": "ערב ראש השנה Rosh Hashanah eve",
        "2026-09-12": "ראש השנה Rosh Hashanah (1 Tishrei 5787, a Saturday)",
        "2026-09-13": "ראש השנה Rosh Hashanah, second day (a Sunday -- a REAL closure, because "
                      "Sunday is a trading day in Israel)",
        "2026-09-20": "ערב יום כיפור Yom Kippur eve",
        "2026-09-21": "יום כיפור Yom Kippur (10 Tishrei 5787)",
        "2026-09-25": "ערב סוכות Sukkot eve",
        "2026-09-26": "סוכות Sukkot, first day (15 Tishrei 5787, a Saturday)",
        "2026-10-03": "שמחת תורה Simchat Torah (a Saturday)",
    },
}

HOLIDAYS_RULE: dict[str, Any] = {
    "rule": (
        "Israeli market closures are HEBREW-CALENDAR dates and the Hebrew calendar is LUNISOLAR "
        "and FULLY COMPUTABLE -- a nineteen-year cycle with seven leap years, in which an extra "
        "month (אדר ב) is inserted. That is the decisive difference from the Hijri tables in the "
        "Saudi and UAE packs: those wait on a crescent SIGHTING and can move by a day after the "
        "fact, while these are known exactly, years ahead. "
        "THE CLOSURES: פורים (14 Adar), פסח with its eve and its seventh day (15 and 21 Nisan), "
        "יום הזיכרון and יום העצמאות (4-5 Iyar, with a published postponement rule when they fall "
        "adjacent to Shabbat), שבועות (6 Sivan), תשעה באב (9 Av), and the Tishrei cluster: ראש "
        "השנה (1-2 Tishrei), יום כיפור (10 Tishrei), סוכות (15 Tishrei) and שמחת תורה (22 "
        "Tishrei), each normally with its eve closed or shortened. "
        "TWO THINGS A NON-ISRAELI STUDY GETS WRONG. First, the WEEKEND is Friday and Saturday, so "
        "a festival that falls on a Saturday costs no session while one that falls on a SUNDAY "
        "does -- the opposite of the intuition a Monday-to-Friday market brings. Second, the "
        "Tishrei cluster removes a large and VARYING number of September-October sessions, so a "
        "monthly seasonal estimated across years is estimating a different denominator each year."),
    "authority": "the Hebrew calendar, the Knesset's holiday legislation and TASE's own published "
                 "trading calendar",
    "table": _IL_HOLIDAYS,
    "status": {
        2024: "COMPUTED AND PUBLISHED -- Hebrew years 5784 and 5785",
        2025: "COMPUTED AND PUBLISHED -- Hebrew years 5785 and 5786",
        2026: "COMPUTED -- Hebrew years 5786 and 5787. The Hijri rows in the Saudi and UAE packs "
              "wait on a moon sighting; this one does not: יום כיפור 5787 falls on 2026-09-21 by "
              "the calendar itself. Confirm the exchange's own trading calendar for eve-session "
              "hours, which are a TASE decision rather than a calendrical one.",
    },
    "market_effect": (
        "USDILS keeps trading offshore through every Israeli closure, so a closure is a LIQUIDITY "
        "regime for the shekel rather than an absence of price -- and the Yom Kippur closure is "
        "the most complete stop in the developed world, with the whole country's trading, "
        "broadcasting and road traffic halted for about 25 hours. The reopening after the Tishrei "
        "cluster prices a fortnight of accumulated news, and the 1973 precedent is the reason "
        "every Israeli risk desk treats that particular date as a tail event rather than as a "
        "holiday."),
    "callable": "countries.il.pack:holidays",
}


def holidays(year: int) -> dict[str, str]:
    """The Israeli closure table for one year, `{"YYYY-MM-DD": name}`. `{}` if untabulated."""
    return holiday_table(HOLIDAYS_RULE, year)


def tishrei_cluster(year: int) -> dict[str, Any]:
    """The September-October closure cluster for one year, and how many sessions it removes.

    Code rather than a note because the COUNT is the object: the cluster's Gregorian position and
    its session cost both move with the Hebrew year, and a monthly seasonal that does not
    condition on the count is comparing months with different numbers of trading days.
    """
    table = holidays(year)
    rows = [(iso, name) for iso, name in sorted(table.items())
            if any(k in name for k in ("ראש השנה", "יום כיפור", "סוכות", "שמחת תורה"))]
    weekday_cost = [iso for iso, _ in rows
                    if date.fromisoformat(iso).weekday() not in (4, 5)]   # Fri=4, Sat=5
    return {"year": int(year), "n_closures": len(rows), "closures": tuple(rows),
            "sessions_lost": len(weekday_cost), "sessions_lost_dates": tuple(weekday_cost),
            "rule": "a closure that falls on Friday or Saturday costs NO session, because the "
                    "Israeli weekend is Friday-Saturday; one that falls on Sunday does, because "
                    "Sunday is a trading day",
            "why": "the cluster's session cost varies year to year, and a September-October "
                   "seasonal that ignores it is measuring the calendar rather than the market"}


def boi_decision_window(day: date) -> dict[str, Any]:
    """The UTC window a Bank of Israel decision lands in on `day`, DST-aware.

    Israel's daylight-saving dates match neither the EU's nor the US's, so the UTC time of a
    16:00 local announcement moves on dates no other pack in this civilization shares. Returning
    the window as code rather than as a constant is the only way an event study anchored on a
    decision is aligned in every year of its sample.
    """
    #: Israel's DST: begins the Friday before the last Sunday of March; ends on the Sunday of
    #: the fast of Gedaliah, which falls in late September or October and is tabulated because it
    #: is a Hebrew-calendar date rather than a Gregorian rule.
    dst_end = {2024: date(2024, 10, 27), 2025: date(2025, 10, 26), 2026: date(2026, 10, 25)}
    march_last_sunday = max(d for d in (date(day.year, 3, x) for x in range(25, 32))
                            if d.weekday() == 6)
    dst_start = march_last_sunday - timedelta(days=2)
    end = dst_end.get(day.year)
    summer = end is not None and dst_start <= day < end
    return {"date": day.isoformat(), "offset": "UTC+3" if summer else "UTC+2",
            "announcement_local": "16:00", "announcement_utc": "13:00" if summer else "14:00",
            "dst_start": dst_start.isoformat(), "dst_end": end.isoformat() if end else None,
            "status": "COMPUTED" if end else "UNMEASURED -- no DST end tabulated for this year, "
                                             "and it is a Hebrew-calendar date rather than a "
                                             "Gregorian rule, so it is not derived here",
            "note": "the decision lands inside the London afternoon in both regimes, which is "
                    "why Israeli policy events are tradable on this desk's own tape and Gulf "
                    "ones mostly are not"}


CUSTOM_MINERS: tuple[dict[str, Any], ...] = (
    miner("il_tishrei_session_counter",
          domain_ids=("il_hebrew_calendar_sessions", "il_sunday_session_lead"),
          kind="calendar",
          entry="countries.il.pack:tishrei_cluster",
          cadence_s=86400.0,
          steerable=False,
          notes="A fixed cost. Any Israeli monthly or seasonal study must take the session count "
                "from here first, because September and October have a different number of "
                "sessions every year and a miner that assumes otherwise produces a confident "
                "wrong seasonal."),
    miner("il_policy_window_router",
          domain_ids=("il_policy_decisions", "il_cpi_index_linkage"),
          kind="calendar",
          entry="countries.il.pack:boi_decision_window",
          cadence_s=86400.0,
          steerable=False,
          notes="Resolves the UTC window of a 16:00 local announcement, DST-aware on ISRAEL'S own "
                "transition dates. An event study that hard-codes one offset is misaligned for "
                "part of every year of its sample."),
)


# --------------------------------------------------------------------------- positioning
POSITIONING_SOURCES: tuple[dict[str, Any], ...] = (
    {"id": "cot_ils_unusable",
     "name": "CFTC Commitments of Traders -- the shekel contract exists and is NOT usable",
     "covers": "a CME Israeli shekel futures contract does appear in the currency report, but its "
               "open interest is negligible and it is not where shekel risk is taken",
     "frequency": "weekly", "lag": "Friday for Tuesday", "root": "cftc.gov",
     "licence": "free, public",
     "note": "DECLARED PRECISELY, because this is the one Middle East currency for which a COT "
             "row is not simply absent. Present-but-negligible is a WORSE trap than absent: a "
             "study that reads it as 'speculative shekel positioning' is reading a handful of "
             "contracts as if it were the market. Treated as UNMEASURED and named, not used."},
    {"id": "boi_institutional_exposure",
     "name": "Bank of Israel and Capital Market Authority data on institutional foreign exposure "
             "and hedging",
     "covers": "the pension, provident and study funds' foreign asset holdings and their currency "
               "hedge ratios -- THE positioning series for this pack",
     "frequency": "monthly and quarterly", "lag": "weeks to a quarter",
     "root": "boi.org.il, gov.il capital market authority", "licence": "free, public",
     "note": "This is the substitute for a COT report and it is BETTER for the mechanism that "
             "matters: it measures the size of the pool whose rebalancing rule drives USDILS, "
             "rather than the speculative float on top of it."},
    {"id": "tase_foreign_flow",
     "name": "TASE non-resident activity and holdings",
     "covers": "non-resident net purchase and holdings in Israeli equities and bonds",
     "frequency": "monthly", "lag": "weeks", "root": "tase.co.il, boi.org.il",
     "licence": "free, public",
     "note": "A risk-appetite state for Israel specifically; the war era makes this series a "
             "regime indicator rather than a flow indicator."},
    {"id": "boi_reserves_and_programmes",
     "name": "Bank of Israel reserve levels and announced intervention programmes",
     "covers": "monthly reserves, plus the dated announcements that define each intervention era",
     "frequency": "monthly", "lag": "days", "root": "boi.org.il",
     "licence": "free, public",
     "note": "Reserves are the meter and the ANNOUNCEMENTS are the dates. A model of the Bank's "
             "reaction function estimated across programme boundaries is averaging a buyer, a "
             "non-participant and a seller."},
)


# --------------------------------------------------------------------------- terminology
TERMINOLOGY: dict[str, tuple[str, ...]] = {
    "core": ("בנק ישראל", "ריבית", "שער הדולר", "שער יציג", "שקל", "דולר", "אינפלציה", "מדד",
             "התערבות", "יתרות מטח"),
    "il_policy_decisions": ("ריבית בנק ישראל", "הוועדה המוניטרית", "החלטת ריבית", "נגיד בנק ישראל",
                            "העלאת ריבית", "הורדת ריבית", "פרוטוקול", "תחזית המקרו",
                            "יעד האינפלציה", "מק\"ם"),
    "il_fx_intervention": ("התערבות בשוק המט\"ח", "רכישות דולרים", "מכירת דולרים", "יתרות המטבע",
                           "תוכנית רכישה", "ייסוף", "פיחות", "שער החליפין", "מטבע חוץ"),
    "il_institutional_hedging": ("גופים מוסדיים", "קרנות הפנסיה", "קופות גמל", "קרנות השתלמות",
                                 "חשיפה מטבעית", "גידור מטבעי", "שיעור הגידור", "נכסים בחו\"ל",
                                 "איזון תיק", "חשיפה למניות חו\"ל"),
    "il_tech_cycle": ("היי-טק", "הייטק", "גיוסי הון", "אקזיט", "חברות סטארט-אפ", "הנפקה",
                      "משקיעי הון סיכון", "נאסד\"ק", "המרת דולרים", "משכורות בדולרים",
                      "ענף הטכנולוגיה"),
    "il_cpi_index_linkage": ("מדד המחירים לצרכן", "המדד", "צמוד מדד", "אג\"ח צמודות",
                             "ציפיות אינפלציה", "משכנתאות", "הצמדה", "הלשכה המרכזית לסטטיסטיקה"),
    "il_equity_market": ("הבורסה לניירות ערך", "הבורסה בתל אביב", "ת\"א 35", "ת\"א 125",
                         "מחזורי המסחר", "מדד הבנקים", "נעילה", "מסחר ראשון", "משקיעים זרים",
                         "רישום כפול"),
    "il_rates_curve": ("תשואות", "אג\"ח ממשלתי", "עקום התשואות", "ריבית ריאלית", "מרווח",
                       "פרמיית סיכון", "דירוג אשראי", "הנפקות אוצר"),
    "il_war_risk": ("מלחמה", "מבצע", "מילואים", "פרמיית הסיכון", "אי ודאות ביטחונית",
                    "הורדת דירוג", "חרבות ברזל", "גיוס חירום", "תקציב מלחמה"),
    "il_energy_gas": ("גז טבעי", "לווייתן", "תמר", "יצוא גז", "מצרים", "ירדן", "הסכם יצוא",
                      "תמלוגים", "קרן העושר"),
    "il_hebrew_calendar_sessions": ("ראש השנה", "יום כיפור", "סוכות", "שמחת תורה", "פסח", "שבועות",
                                    "פורים", "תשעה באב", "יום העצמאות", "ערב חג", "חול המועד"),
    "il_retail_vernacular": ("השקעות", "תיק השקעות", "תשואה", "סוחרים", "ירידות", "עליות",
                             "תיקון", "שורט", "לונג", "מכפיל", "בועה", "הזדמנות קנייה"),
    "il_macro_activity": ("הצמיחה", "התוצר", "אבטלה", "משרות פנויות", "מדד המחירים ליצרן",
                          "יצוא שירותים", "גירעון", "החשב הכללי", "תקציב המדינה"),
}


# --------------------------------------------------------------------------- source classes
#: The ten-layer depth rule (principal, 2026-09-17), with HEBREW queries. The layer set, the
#: builder and the validator come from `countries.sa.pack` so the three Middle East packs cannot
#: drift apart on the rule that binds all of them. A query here is the Hebrew a crawler types:
#: searching for "Bank of Israel interest rate decision" finds an English summary, and searching
#: for `החלטת ריבית בנק ישראל` finds the decision.
SOURCE_CLASSES: tuple[dict[str, Any], ...] = (
    me_source("il_official_cb", "Bank of Israel: statistics, the SDMX API and the decisions",
              layer="official",
              roots=("boi.org.il", "edge.boi.gov.il (the SDMX data API with metadata)",
                     "the Monetary Committee decision and discussion-summary pages",
                     "the reserves and intervention-programme announcements"),
              languages=("he", "en"),
              licence="free, public; the SDMX API is documented and needs NO key -- the only "
                      "keyless lane in this civilization",
              access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
              queries=("החלטת ריבית בנק ישראל", "שער יציג", "יתרות מטבע חוץ",
                       "התערבות בשוק המט\"ח", "תחזית חטיבת המחקר", "מק\"ם הנפקות",
                       "חשיפת הגופים המוסדיים לחו\"ל"),
              notes="The institutional foreign-exposure and hedge-ratio data here is the "
                    "positioning series this pack actually needs, and it is better than a COT "
                    "report for the mechanism that matters."),
    me_source("il_official_stats", "The Central Bureau of Statistics and the fiscal authorities",
              layer="official",
              roots=("cbs.gov.il", "gov.il ministry of finance and the Accountant General",
                     "the Capital Market, Insurance and Savings Authority",
                     "data.gov.il open data"),
              languages=("he", "en"), licence="free, public",
              access_label="OPEN_DATA", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
              queries=("מדד המחירים לצרכן", "הלשכה המרכזית לסטטיסטיקה הודעה לתקשורת",
                       "נתוני תעסוקה", "גירעון תקציבי", "הנפקות אג\"ח ממשלתיות",
                       "נתוני סחר חוץ"),
              notes="The CPI release at 18:30 on the fifteenth is the domestic settlement event "
                    "this economy indexes to, and it lands AFTER the local close."),
    me_source("il_institutional_exchange", "TASE, the ISA and the rating agencies' public actions",
              layer="institutional",
              roots=("tase.co.il", "isa.gov.il", "maya.tase.co.il (the disclosure system)",
                     "public rating-action announcements for the sovereign"),
              languages=("he", "en"),
              licence="free, public; TASE market data carries redistribution terms and bulk "
                      "history is treated as LICENSED until they are read",
              access_label="PUBLIC_WITH_TERMS", credibility="AUTHORITATIVE",
              predictive_state="UNTESTED",
              queries=("לוח המסחר בבורסה", "ימי מסחר מקוצרים", "פקיעת אופציות מעו\"ף",
                       "מחזורי מסחר", "החזקות תושבי חוץ"),
              notes="Maya is read for EVENT context only; the two-lane order forbids hunting a "
                    "single Israeli name statistically, and the technology names are exactly "
                    "where that temptation is strongest."),
    me_source("il_institutional_research", "Israeli sell-side and the multilaterals",
              layer="institutional",
              roots=("public research pages from the Israeli banks' research departments",
                     "imf.org Article IV for Israel", "oecd.org economic surveys of Israel",
                     "the Bank of Israel's own Financial Stability Report"),
              languages=("he", "en"),
              licence="public research pages only; never a paywalled terminal, never a licensed "
                      "feed redistributed",
              access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
              predictive_state="NARRATIVE_FEATURE",
              queries=("סקירה מאקרו כלכלית", "תחזית ריבית", "דוח היציבות הפיננסית",
                       "המלצות אנליסטים", "תחזית שער הדולר"),
              notes="The Financial Stability Report is where the institutional hedge ratio is "
                    "discussed with numbers that appear nowhere else."),
    me_source("il_academic", "Israeli economic and finance literature",
              layer="academic",
              roots=("boi.org.il research department discussion papers",
                     "papers.ssrn.com (shekel, hedging-flow and Israeli microstructure work)",
                     "the Taub Center and the Israel Democracy Institute economic programmes",
                     "Hebrew University, Tel Aviv University and IDC working papers"),
              languages=("he", "en"),
              licence="mixed: discussion papers free, journal full text often licensed; never "
                      "scrape a paywall",
              access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
              predictive_state="UNTESTED",
              queries=("מאמר מחקר בנק ישראל", "שער החליפין מודל", "גידור מטבעי מוסדיים",
                       "השפעת ההתערבות", "shekel hedging flows"),
              notes="The Bank's own discussion papers are where the hedging-flow mechanism was "
                    "quantified; this pack's flagship edge came out of that literature and is "
                    "labelled MEASURED_ELSEWHERE because of it."),
    me_source("il_practitioner", "Israeli market professionals writing in public",
              layer="practitioner",
              roots=("public columns by Israeli fund managers and strategists in the financial "
                     "press", "public LinkedIn posts by Israeli treasury and hedging "
                     "professionals", "public conference and podcast transcripts from Israeli "
                     "capital-market events"),
              languages=("he",),
              licence="public web; VERBATIM CLAIMS only, no personal data, no private groups",
              access_label="PUBLIC_SOCIAL", credibility="UNRELIABLE",
              predictive_state="NARRATIVE_FEATURE", evidence_weight=0.4,
              queries=("אסטרטגיית השקעה", "חשיפה לשקל", "מה יקרה לדולר", "תיק ההשקעות המומלץ",
                       "ניתוח טכני שקל דולר"),
              notes="Israeli hedging practitioners describe the rebalancing mechanics in public "
                    "more openly than their equivalents anywhere in the Gulf, which makes this "
                    "layer unusually informative here."),
    me_source("il_retail_ecology", "The Hebrew retail investor ecology",
              layer="retail_ecology",
              roots=("bizportal.co.il and globes.co.il talkback threads",
                     "public Hebrew investing communities and forums",
                     "public X/Twitter and Telegram broadcast channels in Hebrew",
                     "Hebrew finance YouTube comment sections"),
              languages=("he",),
              licence="public web; VERBATIM CLAIMS only, no personal data, no private groups",
              access_label="PUBLIC_SOCIAL", credibility="FRINGE", predictive_state="UNTESTED",
              evidence_weight=0.2,
              queries=("קרן השתלמות מסלול", "לאן הולך הדולר", "להעביר את הכסף לחו\"ל",
                       "מסלול מנייתי", "האם כדאי לקנות דולרים", "בועה בשוק"),
              notes="FRINGE AND KEPT. Israeli retail savers move between savings-track allocations "
                    "in size, and the chatter about switching tracks is the retail surface of the "
                    "same foreign-exposure flow the institutions run. A wrong claim there is "
                    "still evidence about the behaviour. Low weight, never dropped."),
    me_source("il_app_ecosystem", "The Israeli financial app surface",
              layer="app_ecosystem",
              roots=("public app-store listings and review corpora for Israeli brokerage, savings "
                     "and payment apps (bank trading apps, Bit, Paybox, investment platforms)",
                     "publishers' own public release notes and status pages"),
              languages=("he", "en"),
              licence="app-store terms forbid bulk machine extraction of listings and reviews",
              access_label="ACCESS_UNCLEAR", credibility="UNKNOWN", predictive_state="UNTESTED",
              machine_use_allowed=True, evidence_weight=0.3,
              queries=("אפליקציית מסחר", "תקלה באפליקציה", "עדכון גרסה מסחר"),
              notes="REGISTERED AND NEVER SCRAPED. Retail platform outages and track-switching "
                    "features date the retail flow, and the terms forbid machine extraction -- so "
                    "the row exists, machine_use_allowed is False, and no crawler runs."),
    me_source("il_media", "Hebrew financial press",
              layer="media",
              roots=("globes.co.il", "themarker.com", "calcalist.co.il", "bizportal.co.il",
                     "ynet economy section"),
              languages=("he",),
              licence="public headlines and article text; several outlets forbid bulk text and "
                      "data mining in their terms -- those are registered and not crawled",
              access_label="PUBLIC_WITH_TERMS", credibility="RELIABLE",
              predictive_state="NARRATIVE_FEATURE",
              queries=("בנק ישראל הותיר את הריבית", "הדולר נחלש", "הבורסה בתל אביב ננעלה",
                       "גיוס הון היי-טק", "דירוג האשראי של ישראל"),
              notes="Globes, TheMarker and Calcalist carry the institutional-flow story in Hebrew "
                    "before any English wire does, and Bizportal is the fastest on the shekel."),
    me_source("il_archive", "The archived record",
              layer="archive",
              roots=("web.archive.org captures of boi.org.il and tase.co.il",
                     "Bank of Israel annual report and Financial Stability Report archives",
                     "captures of the 2021 purchase-plan and October 2023 sale-programme "
                     "announcements", "the CBS release archive"),
              languages=("he", "en"), licence="public archive; respect each archive's terms",
              access_label="PUBLIC_ARCHIVE", credibility="AUTHORITATIVE",
              predictive_state="UNTESTED",
              queries=("הודעת בנק ישראל 2023 מכירת דולרים", "תוכנית רכישת מט\"ח 2021",
                       "דוח בנק ישראל ארכיון"),
              notes="The intervention programmes are the era boundaries of this pack, and the "
                    "announcement TEXT -- with its size and its date -- is what the archive "
                    "preserves when a page is later rewritten."),
    me_source("il_physical_economy", "Gas, exports and the real economy",
              layer="physical_economy",
              roots=("the Ministry of Energy's gas production and export reporting",
                     "CBS goods and services export data, with the technology-services split",
                     "the Israel Ports Company and Haifa and Ashdod throughput",
                     "electricity demand reporting"),
              languages=("he", "en"), licence="free, public",
              access_label="PUBLIC", credibility="AUTHORITATIVE", predictive_state="UNTESTED",
              queries=("הפקת גז טבעי", "יצוא גז למצרים", "נמל אשדוד תנועת מכולות",
                       "יצוא שירותי היי-טק", "צריכת חשמל שיא"),
              notes="The gas exports to Egypt and Jordan are the physical link between this pack "
                    "and the Africa civilization: Israeli gas is liquefied in Egypt and re-"
                    "exported, so a disruption on either side is one event with two national "
                    "readings."),
    me_source("il_source_graph", "Who carries what first, and the code that speaks SDMX",
              layer="source_graph",
              roots=("which Hebrew outlet carries a Bank of Israel statement first, and who "
                     "merely repeats it", "github.com SDMX clients and Israeli market-data "
                     "wrappers", "Hebrew Wikipedia and Wikidata entries for Israeli financial "
                     "institutions", "the citation graph around Bank of Israel discussion papers"),
              languages=("he", "en"),
              licence="per-source; repositories are per-repository licensed and never vendored "
                      "without one",
              access_label="PUBLIC", credibility="UNKNOWN", predictive_state="UNTESTED",
              evidence_weight=0.5,
              queries=("על פי הודעת בנק ישראל", "כפי שדווח בגלובס", "BOI SDMX api",
                       "sdmx json python", "tase api github"),
              notes="The SDMX client graph is load-bearing for this civilization: the Israeli "
                    "lane speaks SDMX-JSON and the parser is the one piece of the data plane the "
                    "Gulf lanes do not need."),
    me_source("il_refused", "Grounds this pack refuses on purpose",
              layer="source_graph",
              roots=("(none -- this row records a refusal, which is a decision rather than an "
                     "oversight)",),
              languages=("he", "en"), licence="n/a",
              access_label="ACCESS_UNCLEAR", credibility="UNKNOWN", predictive_state="UNTESTED",
              machine_use_allowed=True, evidence_weight=0.0,
              refused_reason="crypto-exchange venues and feeds are refused under the MT5 universe "
                             "mandate (2026-08-18); paywalled terminals are refused as "
                             "redistribution; single-name Israeli equities -- above all the "
                             "technology names and the dual-listed ones -- are refused as "
                             "statistical hypothesis ground (two-lane order 2026-09-06); private "
                             "groups are refused because they are not public sources; and NO "
                             "security-sensitive, operational or personal material is collected "
                             "at any time, whatever its access label",
              queries=("(none -- this row is never queried)",),
              notes="The last clause is this pack's own addition to the standing refusals: a war "
                    "era generates material that is public, tempting and none of this desk's "
                    "business, and the refusal is written down so no later session has to "
                    "re-decide it."),
)

#: Every layer is sourced for Israel. The tuple is kept rather than omitted because an empty
#: declaration and a missing one are different statements.
ABSENT_LAYERS: tuple[dict[str, Any], ...] = ()


# --------------------------------------------------------------------------- datasets
DATASETS: tuple[dict[str, Any], ...] = (
    dataset("boi_exchange_rates",
            source="Bank of Israel SDMX API, exchange-rate dataflow",
            coverage="the representative rate against the dollar, the euro and the basket, daily",
            frequency="daily",
            publication_lag_days=0.4,
            revisions="none once fixed",
            licence="free, public, NO KEY; attribution per the Bank's terms",
            history_from="1990-01",
            pit_feasible=True,
            assets=("USDILS", "EURILS", "USDX"),
            mechanism_families=("fixing_flow", "policy_state", "fx_state"),
            how_to_fetch="the SDMX v2 data endpoint with format=sdmx-json; the representative "
                         "rate is set about 15:15 Israel time, which moves in UTC with Israel's "
                         "own DST dates"),
    dataset("boi_policy_rate",
            source="Bank of Israel SDMX API, interest-rate dataflow, plus the decision pages",
            coverage="the Bank of Israel rate, its decision dates and the discussion summaries "
                     "with the vote split",
            frequency="eight decisions a year, with a daily rate series",
            publication_lag_days=0.1,
            revisions="none",
            licence="free, public, no key",
            history_from="1994-01",
            pit_feasible=True,
            assets=("USDILS", "EURILS", "UST10Y"),
            mechanism_families=("policy_surprise", "policy_state", "carry"),
            how_to_fetch="the SDMX rate dataflow for the series and the decision page for the "
                         "16:00 local timestamp; store BOTH, because the series carries the level "
                         "and only the page carries the minute"),
    dataset("boi_reserves",
            source="Bank of Israel foreign-exchange reserves",
            coverage="the monthly reserve level and its change, alongside the announced "
                     "intervention programmes that explain it",
            frequency="monthly",
            publication_lag_days=7.0,
            revisions="rare",
            licence="free, public",
            history_from="1990-01",
            pit_feasible=True,
            assets=("USDILS", "EURILS", "XAUUSD"),
            mechanism_families=("intervention", "sovereign_flow", "fx_state"),
            how_to_fetch="the SDMX reserves dataflow; a reserve change is only interpretable "
                         "against the programme in force, so the programme table is stored with "
                         "it"),
    dataset("cbs_cpi",
            source="Central Bureau of Statistics consumer price index",
            coverage="headline and core CPI, the housing component, and the index used for "
                     "contract linkage",
            frequency="monthly",
            publication_lag_days=15.0,
            revisions="rare; the index itself is not revised because contracts settle on it",
            licence="free, public",
            history_from="1950-01",
            pit_feasible=True,
            assets=("USDILS", "EURILS", "UST10Y"),
            mechanism_families=("inflation_surprise", "index_linkage", "real_rate"),
            how_to_fetch="the CBS release on the fifteenth at 18:30 Israel time -- AFTER the "
                         "local close, so the first price expression is offshore in USDILS"),
    dataset("boi_institutional_exposure",
            source="Bank of Israel and Capital Market Authority institutional-investor data",
            coverage="the pension, provident and study funds' foreign asset holdings and their "
                     "currency hedge ratios",
            frequency="monthly and quarterly",
            publication_lag_days=45.0,
            revisions="restated; vintages are kept",
            licence="free, public",
            history_from="2004-01",
            pit_feasible=True,
            assets=("USDILS", "EURILS", "US500", "NAS100"),
            mechanism_families=("hedging_flow", "forced_flow", "risk_appetite"),
            how_to_fetch="the Bank's statistics pages and the Capital Market Authority's "
                         "reporting. THE positioning series for this pack's flagship mechanism"),
    dataset("tase_market_data",
            source="Tel Aviv Stock Exchange",
            coverage="index levels, turnover, the trading calendar and non-resident activity",
            frequency="daily and monthly",
            publication_lag_days=0.5,
            revisions="none",
            licence="public pages; bulk market-data history carries redistribution terms and is "
                    "treated as LICENSED until they are read",
            history_from="1992-01",
            pit_feasible=True,
            assets=("NAS100", "US500", "USDILS"),
            mechanism_families=("risk_appetite", "session_lead", "foreign_flow"),
            how_to_fetch="tase.co.il market data pages; the TRADING CALENDAR is the part this "
                         "pack depends on most, because the Hebrew-calendar session count varies"),
    dataset("il_tech_funding",
            source="public venture and exit reporting for the Israeli technology sector",
            coverage="capital raised, exit proceeds and the count of rounds, quarterly",
            frequency="quarterly",
            publication_lag_days=30.0,
            revisions="frequently restated as deals are disclosed late; VINTAGES MATTER",
            licence="public summaries; several trackers are LICENSED products and only their "
                    "public headline figures are used",
            history_from="2010-Q1",
            pit_feasible=False,
            assets=("USDILS", "NAS100"),
            mechanism_families=("tech_cycle", "structural_flow"),
            how_to_fetch="public quarterly summaries. pit_feasible is FALSE: the late-disclosure "
                         "restatement is large enough that the first print and the final differ "
                         "materially, and no public vintage archive exists -- so cells built on "
                         "this series are NOT_PIT_SAFE and are labelled so"),
    dataset("mof_deficit_issuance",
            source="Ministry of Finance and the Accountant General",
            coverage="the monthly fiscal deficit, government issuance and the debt path",
            frequency="monthly",
            publication_lag_days=20.0,
            revisions="restated within the year",
            licence="free, public",
            history_from="2000-01",
            pit_feasible=True,
            assets=("USDILS", "UST10Y", "US500"),
            mechanism_families=("fiscal_impulse", "issuance", "risk_premium"),
            how_to_fetch="gov.il Accountant General monthly reports; the war-era deficit path is "
                         "the fiscal-impulse variable for that regime"),
    dataset("il_gas_exports",
            source="Ministry of Energy gas production and export reporting",
            coverage="production from the offshore fields and pipeline exports to Egypt and Jordan",
            frequency="monthly to quarterly",
            publication_lag_days=45.0,
            revisions="minor",
            licence="free, public",
            history_from="2013-01",
            pit_feasible=True,
            assets=("XAUUSD", "USDILS"),
            mechanism_families=("energy_export", "external_balance", "regional_link"),
            how_to_fetch="the ministry's reporting. THE EGYPT LEG belongs to the Africa "
                         "civilization: Israeli gas is liquefied in Egypt and re-exported, so a "
                         "disruption is one event with two national readings, and the Egyptian "
                         "half is read from an `eg` pack when one exists -- UNMEASURED by name "
                         "until then"),
    dataset("il_sovereign_rating_actions",
            source="public sovereign rating actions and outlook changes",
            coverage="rating, outlook and the published rationale",
            frequency="irregular",
            publication_lag_days=0.1,
            revisions="n/a",
            licence="public announcements only; the agencies' full reports are LICENSED and are "
                    "never redistributed",
            history_from="2000-01",
            pit_feasible=True,
            assets=("USDILS", "UST10Y", "US500"),
            mechanism_families=("risk_premium", "event_shock"),
            how_to_fetch="the agencies' public action announcements, with the timestamp; the "
                         "2023-2024 downgrades are the dated risk-premium events of the war era"),
)


# --------------------------------------------------------------------------- actors
ACTORS: tuple[dict[str, Any], ...] = (
    actor("the Israeli institutional investor (pension, provident and study funds)",
          holds="a very large foreign equity portfolio held against shekel liabilities, with a "
                "target currency hedge ratio",
          forced_to=("top up the hedge when foreign equities rise, which means SELLING dollars",
                     "reduce the hedge when they fall, which means buying dollars",
                     "rebalance towards policy weights on a schedule"),
          when="continuously, with a pronounced month-end concentration",
          information=("the value of the foreign portfolio", "the policy hedge ratio",
                       "member flows between savings tracks"),
          constraints=("a mandated or board-approved hedge ratio",
                       "a liability book denominated in shekels",
                       "a portfolio too large to move without price impact"),
          instruments=("USDILS forwards and spot", "foreign equities"),
          counterparties=("banks' FX desks", "global equity markets"),
          observables=("published foreign-asset holdings and hedge ratios",
                       "the S&P 500 and NASDAQ levels themselves",
                       "month-end shekel behaviour"),
          impact="a MECHANICAL negative relationship between USDILS and global equities -- the "
                 "clearest rules-driven forced flow in this whole civilization",
          persistence="structural: it is a rebalancing rule, not a view, so it does not learn and "
                      "does not stop",
          falsifier="USDILS stops responding negatively to a large S&P move over a three-year "
                    "window with the hedge ratio unchanged",
          notes="THE actor this pack exists for."),
    actor("the Bank of Israel intervention desk",
          holds="over two hundred billion dollars of reserves accumulated through announced "
                "programmes",
          forced_to=("execute an announced programme once it is announced",
                     "sell dollars under the October 2023 programme when the shekel is under "
                     "stress",
                     "publish the reserve level monthly"),
          when="by programme; the era boundaries are the announcements",
          information=("the shekel's level and volatility", "the inflation forecast",
                       "financial-stability conditions"),
          constraints=("an inflation target", "a stated preference for a floating rate",
                       "the reputational cost of an announced programme not executed"),
          instruments=("spot FX purchases and sales", "swap lines", "makam"),
          counterparties=("the local banks", "institutional investors"),
          observables=("monthly reserves", "the programme announcements themselves",
                       "shekel behaviour at stress levels"),
          impact="a level-dependent, announced, size-known intervention flow -- the opposite of "
                 "the Gulf's silent peg defence",
          persistence="programme-bounded: a model fitted across programmes averages a buyer, a "
                      "non-participant and a seller",
          falsifier="an announced programme runs its stated size with no measurable effect on "
                    "the shekel's path against a matched control period",
          notes="The eras in POLICY_ERAS are literally this actor's programme list."),
    actor("the Israeli technology exporter",
          holds="dollar revenue against a shekel cost base dominated by payroll",
          forced_to=("convert dollars to shekels every month to pay salaries",
                     "convert exit and funding proceeds when they land"),
          when="monthly for payroll; lumpy and event-driven for raises and exits",
          information=("its own revenue and headcount", "the funding environment",
                       "the shekel's level"),
          constraints=("payroll is a legal obligation with a date",
                       "hedging policies vary and many smaller firms do not hedge at all"),
          instruments=("spot USDILS conversion", "forward hedges"),
          counterparties=("banks' corporate desks",),
          observables=("venture funding and exit totals", "technology-services exports in the "
                       "trade data", "employment in the sector"),
          impact="a structural, recurring shekel bid whose SIZE follows the NASDAQ funding cycle "
                 "with a lag of one to three quarters",
          persistence="structural while the sector's share of exports holds",
          falsifier="technology-services exports stop leading the shekel's trend over a "
                    "three-year window",
          notes="The sector enters as an OBSERVABLE. No Israeli technology name is ever a "
                "hypothesis here (two-lane order)."),
    actor("the foreign venture and acquisition buyer",
          holds="dollars committed to Israeli companies",
          forced_to=("convert a portion into shekels at closing",
                     "close on an agreed date regardless of the rate"),
          when="deal-driven and lumpy, clustered in the NASDAQ funding cycle",
          information=("deal pipelines", "valuations"),
          constraints=("signed deal terms with closing dates",),
          instruments=("spot conversion at closing",),
          counterparties=("Israeli sellers", "banks"),
          observables=("announced deals and their sizes", "quarterly venture totals"),
          impact="an episodic shekel bid that amplifies the technology cycle",
          persistence="cyclical with global technology funding",
          falsifier="quarters with very large announced proceeds show no shekel effect against a "
                    "matched control",
          notes="Deal totals are restated as late disclosures arrive, which is why the dataset is "
                "pit_feasible=False and says so."),
    actor("the CPI-linked borrower and bondholder",
          holds="mortgages and bonds whose principal is linked to the מדד",
          forced_to=("accept a principal adjustment on every CPI print",
                     "hedge or accept the inflation exposure"),
          when="monthly, on the fifteenth at 18:30 local",
          information=("the CPI print", "inflation expectations from the linked curve"),
          constraints=("contractual linkage that cannot be renegotiated",),
          instruments=("CPI-linked government bonds", "linked mortgages"),
          counterparties=("the government as issuer", "banks"),
          observables=("the CPI print", "the linked-versus-nominal breakeven"),
          impact="a CPI surprise moves the whole domestic curve and the shekel more than it would "
                 "in an unindexed economy",
          persistence="structural: linkage is embedded in the contract stock",
          falsifier="a CPI surprise stops moving the shekel and the breakeven over three years",
          notes="This is why an Israeli CPI print is a bigger market event than its "
                "size suggests."),
    actor("the Ministry of Finance debt manager",
          holds="the sovereign's domestic and international issuance programme",
          forced_to=("fund a deficit that grew sharply in the war era",
                     "issue in both shekel and dollar markets on a published plan"),
          when="a monthly domestic calendar and opportunistic international deals",
          information=("the realised deficit", "global credit conditions", "rating actions"),
          constraints=("a published issuance plan", "a debt-to-GDP path stated as policy"),
          instruments=("shekel nominal and CPI-linked bonds", "USD bonds"),
          counterparties=("local institutions", "international credit investors"),
          observables=("monthly issuance results", "the deficit path", "the sovereign spread"),
          impact="issuance drains domestic liquidity and the spread carries the risk premium",
          persistence="policy-driven while the deficit persists",
          falsifier="a heavy issuance quarter leaves the domestic curve and the spread unmoved, "
                    "twice running",
          notes="The war-era deficit is the fiscal-impulse variable of the 2023 era."),
    actor("the non-resident investor in Israeli assets",
          holds="Israeli equities and bonds within a developed-market mandate",
          forced_to=("mark exposure to a country with an elevated geopolitical risk premium",
                     "rebalance on index reviews"),
          when="continuous, with reviews and shock-driven episodes",
          information=("the index weights", "rating actions", "the security situation"),
          constraints=("developed-market benchmark tracking since the 2010 MSCI upgrade",),
          instruments=("Israeli equities and bonds", "the shekel leg beneath them"),
          counterparties=("local institutions",),
          observables=("non-resident holdings and net purchase", "the sovereign spread"),
          impact="a risk-appetite state for Israel that is DIFFERENT from the global one and "
                 "separable from it",
          persistence="structural, with episodic shocks",
          falsifier="non-resident flow stops separating from global emerging and developed flows "
                    "over a three-year window",
          notes="The 2010 developed-market upgrade was a forced flow with the OPPOSITE sign to "
                "Saudi Arabia's 2019 emerging-market inclusion."),
    actor("the war-risk premium payer",
          holds="Israeli assets and the shekel through a security shock",
          forced_to=("reprice risk within hours of an event, often on a Sunday when only Tel Aviv "
                     "is open",
                     "hedge or reduce exposure when reserves are mobilised"),
          when="event-driven; the October 2023 episode is the reference case",
          information=("official announcements", "the Hebrew news cycle",
                       "the Bank's response"),
          constraints=("thin weekend liquidity", "a domestic investor base that cannot exit "
                       "en masse"),
          instruments=("the shekel", "Israeli equities and bonds", "the sovereign spread"),
          counterparties=("the Bank of Israel, which announced a sale programme within days",
                          "global macro investors"),
          observables=("the Sunday Tel Aviv session", "the shekel's offshore reaction",
                       "rating actions", "reserve changes"),
          impact="a risk premium that the Tel Aviv Sunday session prices before the desk's own "
                 "tape reopens",
          persistence="episodic, with a documented mean-reversion once the policy response lands",
          falsifier="three consecutive security shocks in which the Sunday session carries no "
                    "information about the following week's shekel path",
          notes="The pack studies the MARKET response only. No security-sensitive, operational or "
                "personal material is collected, ever."),
    actor("the Israeli household saver",
          holds="a savings-track allocation inside pension and study funds, switchable online",
          forced_to=("choose a track, and in aggregate to chase past returns between tracks",
                     "accept the fund's hedge policy that comes with the track"),
          when="continuously, with switching surges after large market moves",
          information=("published track returns", "the Hebrew financial press",
                       "retail chatter about moving money abroad"),
          constraints=("switching rules and timing", "tax treatment"),
          instruments=("track allocations that translate into institutional foreign exposure",),
          counterparties=("the institutional managers above",),
          observables=("published track flows", "retail search and forum activity"),
          impact="changes the SIZE of the pool whose rebalancing rule drives USDILS, with a lag",
          persistence="behavioural and persistent",
          falsifier="track-switching flows stop leading changes in aggregate foreign exposure",
          notes="The retail_ecology source layer is where this actor is visible before the "
                "official file shows it."),
    actor("the natural gas producer and the Egyptian export route",
          holds="offshore gas production with pipeline export contracts to Egypt and Jordan",
          forced_to=("deliver on contract", "route through infrastructure that has been "
                     "interrupted by regional events"),
          when="continuous, with dated interruptions",
          information=("field production", "Egyptian liquefaction demand", "regional security"),
          constraints=("contract terms", "pipeline capacity", "the security situation"),
          instruments=("pipeline gas", "the Egyptian LNG re-export chain"),
          counterparties=("Egyptian and Jordanian buyers", "global LNG markets"),
          observables=("production and export volumes",
                       "Egyptian LNG export volumes, which are the Africa civilization's series",
                       "interruption announcements"),
          impact="a small but real external-balance contribution for Israel and a MATERIAL one "
                 "for Egypt's gas balance -- one event, two national readings",
          persistence="structural since 2020, with episodic interruptions",
          falsifier="an Israeli export interruption shows no effect in Egyptian LNG exports "
                    "within the same quarter",
          notes="THE EGYPT LINK. The Egyptian half is read from an `eg` pack in the Africa "
                "civilization when one exists, and is UNMEASURED by name until then."),
    actor("the Tel Aviv market maker in the Sunday session",
          holds="inventory through a session with no international overlap",
          forced_to=("quote into weekend news with no offsetting market open",
                     "widen when the weekend carried a shock"),
          when="every Sunday, the short session",
          information=("weekend news", "Friday's New York close", "offshore shekel quotes"),
          constraints=("no hedging venue open", "a short session"),
          instruments=("Israeli equities", "TA-35 derivatives"),
          counterparties=("local institutions and retail",),
          observables=("the Sunday session's return, range and turnover",
                       "the Monday gap in USDILS and in global risk"),
          impact="the Sunday session is a genuine information event about the coming week, priced "
                 "with unusually little liquidity",
          persistence="structural while the Sunday-to-Thursday week holds",
          falsifier="the Sunday session stops carrying information about the Monday open over a "
                    "three-year sample",
          notes="Israel shares this with Saudi Arabia, Qatar and Kuwait and NOT with the UAE."),
    actor("the shekel option and hedging desk",
          holds="a book of shekel-dollar options written largely for corporate and institutional "
                "hedgers",
          forced_to=("hedge the book dynamically, which amplifies spot moves at barriers",
                     "quote wider when the geopolitical premium rises"),
          when="continuous, with stress episodes",
          information=("hedging demand", "realised and implied volatility"),
          constraints=("risk limits", "a market with limited depth in stress"),
          instruments=("USDILS options and forwards",),
          counterparties=("technology exporters", "institutional investors"),
          observables=("the implied-volatility surface, which THIS DESK DOES NOT HOLD",
                       "spot behaviour around round levels"),
          impact="an amplifier of the flows above rather than an independent driver",
          persistence="structural, stronger in stress",
          falsifier="spot behaviour around hedging-relevant levels is indistinguishable from "
                    "behaviour elsewhere in the distribution",
          notes="Named with its observable explicitly UNMEASURED: the desk has no vol series, so "
                "this actor's intensity is inferred and the inference is labelled."),
)


# --------------------------------------------------------------------------- domains
DOMAINS: tuple[dict[str, Any], ...] = (
    domain("il_institutional_hedging_flow", "The rebalancing rule that links USDILS to NASDAQ",
           objects=("institutional foreign holdings and hedge ratios",
                    "the S&P 500 and NASDAQ path", "month-end shekel behaviour",
                    "the size of the pool"),
           conditions=("the size of the equity move", "month end versus mid-month",
                       "the published hedge ratio's level"),
           instruments=("USDILS", "EURILS", "NAS100", "US500"),
           controls=("other developed-market currencies' response to the same equity move, so a "
                     "global risk-on effect is not read as an Israeli hedging effect",
                     "matched non-month-end windows",
                     "periods when the hedge ratio was materially different"),
           notes="THE flagship domain. The claim is specifically that the relationship is "
                 "MECHANICAL and conditional on the pool's size, which is testable and is not "
                 "the same claim as 'the shekel is a risk currency'."),
    domain("il_policy_decisions", "Eight dated decisions, a real vote, and a tradable timestamp",
           objects=("the decision at 16:00 local", "the press conference",
                    "the discussion summary and its vote split two weeks later",
                    "the makam curve's prior expectation"),
           conditions=("the DST regime, which moves the UTC window",
                       "the inflation regime", "the war era"),
           instruments=("USDILS", "EURILS", "UST10Y", "NAS100"),
           controls=("the makam-implied expectation as the SURPRISE basis, so the level is not "
                     "mistaken for the deviation",
                     "matched non-decision days at the same hour",
                     "the press conference window separated from the decision window"),
           notes="The only Middle East central bank whose decision lands inside the desk's most "
                 "liquid hours, and the only one with a vote to be surprised by."),
    domain("il_cpi_index_linkage", "An indexed economy's monthly settlement event",
           objects=("the CPI print at 18:30 on the fifteenth", "the linked-nominal breakeven",
                    "mortgage and bond linkage"),
           conditions=("the inflation regime", "the housing cycle",
                       "the fact that the release is AFTER the local close"),
           instruments=("USDILS", "EURILS", "UST10Y"),
           controls=("the expectation from the linked curve as the surprise basis",
                     "matched non-release days",
                     "US CPI in the same window as the global-inflation control"),
           notes="The after-close timing means the first price expression is offshore, which "
                 "makes this a clean overnight-response study rather than an intraday one."),
    domain("il_intervention_programmes", "Announced programmes as regime boundaries",
           objects=("the 2008-2013, 2013-2020, 2021 and October 2023 programmes",
                    "monthly reserves", "the announcements themselves"),
           conditions=("which programme is in force", "the shekel's level",
                       "the security situation"),
           instruments=("USDILS", "EURILS", "XAUUSD"),
           controls=("the programme table as the regime variable -- never pooled",
                     "matched windows within the same programme",
                     "other small open economies' currencies as the common factor"),
           notes="A reaction function estimated across programmes averages a buyer, a "
                 "non-participant and a seller, which is why the eras exist."),
    domain("il_tech_cycle_transmission", "A technology funding cycle expressed in a currency",
           objects=("venture and exit proceeds", "technology-services exports",
                    "the monthly payroll conversion", "NASDAQ's own cycle"),
           conditions=("the global funding environment", "the quarter",
                       "the restatement problem in the funding data"),
           instruments=("USDILS", "NAS100", "US2000"),
           controls=("NASDAQ's own move partialled out, so the currency effect is separated from "
                     "the beta",
                     "the funding series' first print used, never the restated one -- and the "
                     "cells labelled NOT_PIT_SAFE because no vintage archive exists",
                     "a placebo on a currency with no technology sector"),
           notes="The restatement problem is the binding constraint here and it is labelled "
                 "rather than assumed away."),
    domain("il_sunday_session_lead", "Tel Aviv's Sunday as a read on the coming week",
           objects=("the Sunday session return, range and turnover",
                    "weekend news arriving before the FX open",
                    "the Monday open in USDILS and in global risk"),
           conditions=("whether the weekend carried a shock", "the size of the Sunday move",
                       "the Hebrew calendar"),
           instruments=("USDILS", "NAS100", "US500", "XAUUSD"),
           controls=("Sundays with no weekend event, matched by season",
                     "the ordinary Friday-to-Monday gap distribution as the baseline",
                     "the Saudi Sunday session as the regional sibling -- a move in both is "
                     "regional, a move in one is national"),
           notes="Shared with the Gulf packs, and the sibling control is what separates an "
                 "Israel-specific shock from a Middle East one."),
    domain("il_war_risk_premium", "A geopolitical risk premium with dated events",
           objects=("security-shock dates", "the sovereign spread and rating actions",
                    "the shekel's path and the Bank's response",
                    "the October 2023 sale programme"),
           conditions=("whether a policy response was announced",
                       "the reserve level available", "the global risk regime"),
           instruments=("USDILS", "EURILS", "XAUUSD", "US500"),
           controls=("matched non-event windows in the same global risk regime",
                     "gold as the generic geopolitical-premium control, so an Israel-specific "
                     "premium is separated from a global one",
                     "the decay profile of prior episodes"),
           notes="MARKET RESPONSE ONLY. No security-sensitive, operational or personal material "
                 "is collected at any time, and the source layer records that refusal."),
    domain("il_hebrew_calendar_sessions", "A varying session count, and what it does to seasonals",
           objects=("the Tishrei cluster", "Passover", "the eve sessions",
                    "the number of sessions each month actually has"),
           conditions=("the Hebrew year", "which weekday a festival falls on",
                       "the Friday-Saturday weekend"),
           instruments=("USDILS", "NAS100", "XAUUSD"),
           controls=("the session count from `tishrei_cluster` as an explicit regressor",
                     "the same Gregorian weeks in years when the cluster fell elsewhere",
                     "a placebo instrument with no Israeli exposure"),
           notes="Like the Hijri drift in the Saudi pack, the Hebrew calendar's Gregorian drift "
                 "supplies its own control for free."),
    domain("il_rates_curve_and_makam", "The only public Israeli rate curve",
           objects=("the makam curve", "government bond yields",
                    "the linked-nominal breakeven", "the policy expectation"),
           conditions=("the policy regime", "the fiscal path", "the war era"),
           instruments=("USDILS", "UST10Y", "UST05Y"),
           controls=("the US curve partialled out, since the global factor dominates",
                     "matched non-decision windows",
                     "the CPI-linkage effect separated from the nominal one"),
           notes="No Israeli rates instrument is quoted here, so this domain produces STATE "
                 "variables for the FX and risk domains rather than tradable cells of its own."),
    domain("il_foreign_flow_state", "Non-resident participation as an Israel-specific risk state",
           objects=("non-resident holdings and net purchase", "index review dates",
                    "the 2010 developed-market upgrade"),
           conditions=("the global risk regime", "rating actions", "the war era"),
           instruments=("USDILS", "US500", "NAS100"),
           controls=("global developed-market flows as the common factor",
                     "non-review windows matched by season",
                     "a placebo on a developed market with no Israeli weight"),
           notes="Separable from the global risk state, which is the only reason it is worth "
                 "measuring."),
    domain("il_gas_export_egypt_link", "One pipeline, two national readings",
           objects=("Israeli gas production and pipeline exports",
                    "Egyptian liquefaction and LNG re-export",
                    "interruption events"),
           conditions=("regional security", "Egyptian domestic demand",
                       "the global LNG price regime"),
           instruments=("XAUUSD", "USDILS"),
           controls=("global LNG prices as the common factor",
                     "matched non-interruption periods",
                     "the Egyptian series when an `eg` pack exists -- UNMEASURED by name until "
                     "then, and NOT proxied"),
           notes="The explicit hand-off to the Africa civilization. Naming the missing leg is "
                 "what keeps this domain honest rather than half-measured."),
    domain("il_fixing_window_microstructure", "The representative rate as a flow magnet",
           objects=("the 15:15 local fixing window", "contract and linkage demand into it",
                    "the fifteen minutes either side"),
           conditions=("the DST regime", "month end", "the size of the day's move"),
           instruments=("USDILS", "EURILS"),
           controls=("matched non-fixing windows at the same time of day",
                     "days with no month-end or linkage concentration",
                     "a placebo window one hour earlier"),
           notes="A microstructure object that a daily-bar study cannot see, and one of the few "
                 "in this civilization that lives in an instrument the desk can quote."),
)


# --------------------------------------------------------------------------- transmission seeds
TRANSMISSION_EDGES_SEED: tuple[dict[str, Any], ...] = (
    edge("il_equity_rally_to_shekel",
         source="a large move in the S&P 500 or NASDAQ, conditioned on the institutional foreign-"
                "asset pool and its hedge ratio",
         mechanism="hedge rebalancing: a rise in the foreign portfolio forces institutions to SELL "
                   "dollars against shekels to restore the hedge ratio, and a fall reverses it",
         targets=("USDILS", "EURILS"),
         sign="equities up -> USDILS down (shekel stronger); equities down -> USDILS up",
         horizon="1 to 10 sessions, concentrated at month end",
         lag="same session to a few sessions",
         control="other developed currencies' response to the same equity move, so a global "
                 "risk-on effect is not attributed to Israeli hedging",
         evidence="MEASURED_ELSEWHERE",
         notes="MEASURED_ELSEWHERE because the Bank of Israel's own research has quantified the "
               "channel; the desk has not reproduced it, and the seed says so."),
    edge("il_policy_surprise_to_shekel",
         source="the Bank of Israel decision at 16:00 local against the makam-implied expectation",
         mechanism="a real committee with a real vote produces a genuine surprise component, "
                   "unlike the Gulf's pegged policy rates",
         targets=("USDILS", "EURILS", "UST10Y"),
         sign="a hawkish surprise -> shekel stronger",
         horizon="minutes to 5 sessions",
         lag="none; the decision has a timestamp",
         control="the makam-implied expectation as the surprise basis; matched non-decision days "
                 "at the same hour; the press conference separated from the decision",
         evidence="HYPOTHESIS"),
    edge("il_cpi_surprise_to_curve_and_shekel",
         source="the CPI print at 18:30 local against the linked-curve expectation",
         mechanism="in an INDEXED economy the CPI settles contracts as well as informing policy, "
                   "so the print moves the curve and the currency more than its size suggests",
         targets=("USDILS", "EURILS", "UST10Y"),
         sign="an upside surprise -> shekel stronger and the linked breakeven wider",
         horizon="the overnight session and the following 1-3 sessions",
         lag="the release is AFTER the local close, so the first expression is offshore",
         control="the linked-curve expectation as the basis; US CPI as the global-inflation "
                 "control; matched non-release days",
         evidence="HYPOTHESIS"),
    edge("il_intervention_announcement_to_shekel",
         source="an announced Bank of Israel intervention programme, with its size",
         mechanism="an announced, size-known official flow in a market of this depth is a level "
                   "shift in the supply of dollars, not a signal about intent",
         targets=("USDILS", "EURILS"),
         sign="an announced SALE programme -> shekel stronger; a PURCHASE programme -> weaker",
         horizon="weeks to quarters -- this is a regime, not a trade",
         lag="hours from the announcement",
         control="the programme table as the regime variable, never pooled; other small open "
                 "economies as the common factor",
         evidence="MEASURED_ELSEWHERE",
         notes="The October 2023 sale programme is the reference case and is publicly documented."),
    edge("il_tech_funding_to_shekel_trend",
         source="technology-services exports and venture and exit proceeds",
         mechanism="dollar revenue converted for a shekel payroll is a structural, recurring bid "
                   "whose size follows the NASDAQ funding cycle with a lag",
         targets=("USDILS", "NAS100"),
         sign="an accelerating funding cycle -> shekel-supportive with a one-to-three-quarter lag",
         horizon="1 to 4 quarters",
         lag="30 days for the public summary, and the series is restated -- so cells are "
             "NOT_PIT_SAFE and are labelled",
         control="NASDAQ's own move partialled out; a placebo currency with no technology sector",
         evidence="HYPOTHESIS"),
    edge("il_war_risk_to_gold_and_shekel",
         source="a dated Israeli security shock, with the Bank's response as a conditioner",
         mechanism="a geopolitical risk premium prices in the shekel and in gold together, and the "
                   "two decay differently once a policy response lands",
         targets=("USDILS", "XAUUSD", "US500"),
         sign="a shock -> USDILS up and gold up; an announced policy response -> USDILS retraces "
              "faster than gold",
         horizon="1 to 20 sessions",
         lag="hours, and the first price is often the Tel Aviv Sunday session",
         control="gold as the generic geopolitical-premium control; matched non-event windows in "
                 "the same global risk regime; prior episodes' decay profiles",
         evidence="MEASURED_ELSEWHERE"),
    edge("il_sunday_session_to_monday_open",
         source="the Tel Aviv Sunday session return and range",
         mechanism="Israel trades Sunday and the desk's tape does not, so weekend information is "
                   "priced in Tel Aviv first and must arrive at the FX open as a gap",
         targets=("USDILS", "NAS100", "US500", "XAUUSD"),
         sign="the direction of the Sunday move -> the sign of the Monday gap",
         horizon="the first 4 hours of the week",
         lag="hours between the Tel Aviv close and the FX open",
         control="Sundays with no weekend event matched by season; the Saudi Sunday session as "
                 "the regional sibling; the ordinary weekend gap distribution as the baseline",
         evidence="HYPOTHESIS",
         notes="A CALENDAR fact rather than a behavioural claim, which is why it is worth testing "
               "in both this pack and the Saudi one."),
    edge("il_hedge_ratio_to_risk_beta",
         source="the published institutional hedge ratio, as a level",
         mechanism="the hedge ratio sets the GAIN of the equity-to-shekel channel: a higher ratio "
                   "means a larger dollar flow per unit of equity move",
         targets=("USDILS", "EURILS"),
         sign="a higher hedge ratio -> a larger USDILS response per unit of S&P move",
         horizon="a conditioning variable rather than a horizon",
         lag="45 days for the published series",
         control="periods with materially different ratios compared directly; the pool size "
                 "partialled out",
         evidence="HYPOTHESIS",
         notes="A CONDITIONING edge, not a directional one -- it says when the flagship edge "
               "should be strong, which is a sharper claim than the edge itself."),
    edge("il_tishrei_sessions_to_seasonal",
         source="the Tishrei cluster's session count for the year",
         mechanism="the number of September-October sessions varies with the Hebrew year, so a "
                   "monthly seasonal estimated without it compares different denominators",
         targets=("USDILS", "NAS100"),
         sign="not directional: this edge exists to CONDITION other seasonals and to kill false "
              "ones",
         horizon="monthly",
         lag="none; the calendar is known years ahead",
         control="the same Gregorian weeks in years when the cluster fell elsewhere",
         evidence="HYPOTHESIS",
         notes="An edge whose value is preventing a confident wrong answer, which this desk has "
               "decided is worth a seed of its own."),
    edge("il_fiscal_and_rating_to_spread",
         source="the monthly deficit path and public sovereign rating actions",
         mechanism="a widening deficit with a rating action attached is a dated risk-premium "
                   "event in a market that is otherwise a developed-market name",
         targets=("USDILS", "UST10Y", "US500"),
         sign="a downgrade or outlook cut -> shekel weaker and the risk premium wider",
         horizon="1 to 10 sessions",
         lag="the announcement has a timestamp; the deficit has a 20-day lag",
         control="matched non-announcement windows; other developed sovereigns' rating actions as "
                 "the common factor",
         evidence="HYPOTHESIS"),
)


# --------------------------------------------------------------------------- policy eras
POLICY_ERAS: tuple[dict[str, Any], ...] = (
    era("il_2008_13_purchase_programme", start="2008-03-01", end="2013-12-31",
        label="the first intervention era",
        what_changed="the Bank began buying dollars, initially on a published daily rule, and "
                     "reserves rose from about 30 billion dollars towards 80; the global crisis "
                     "and its recovery dominate the sample",
        invalidates="an intervention-free model of the shekel does not describe this era, and a "
                    "model fitted here does not describe the 2023 sale era"),
    era("il_2013_20_gas_offset", start="2014-01-01", end="2020-12-31",
        label="the gas-offset programme and the developed-market decade",
        what_changed="purchases were framed partly as offsetting the current-account effect of "
                     "gas production; Israel was already in the developed-market indices after "
                     "the 2010 upgrade; the technology sector's share of exports grew sharply",
        invalidates="the composition of the shekel's drivers changed within this era; the "
                    "hedging channel grew with the institutional pool and is not constant across "
                    "it"),
    era("il_2021_announced_plan", start="2021-01-01", end="2023-10-06",
        label="the pre-announced purchase plan and the judicial-overhaul episode",
        what_changed="the Bank pre-announced a 30-billion-dollar annual purchase amount for the "
                     "first time; the 2023 judicial-overhaul debate produced a domestic risk "
                     "premium with no security component, which is a rare clean experiment in "
                     "separating political risk from war risk",
        invalidates="the 2023 political-risk episode is NOT a war episode and pooling the two "
                    "measures a mixture of two different premia"),
    era("il_2023_war_era", start="2023-10-07", end="2024-12-31",
        label="the war era and the first sale programme in the Bank's history",
        what_changed="a large security shock; the Bank announced a sale programme of up to 30 "
                     "billion dollars plus swaps within days; sovereign rating downgrades "
                     "followed; the deficit and issuance rose sharply; the shekel weakened "
                     "sharply and then recovered",
        invalidates="EVERY relationship in this pack behaves differently here. The hedging channel "
                    "still operates but sits under a much larger risk premium, and a model fitted "
                    "across this boundary attributes the premium to whatever regressor happened to "
                    "move"),
    era("il_2025_onward_normalisation", start="2025-01-01", end=None,
        label="normalisation, with the risk premium decaying",
        what_changed="the security premium decayed, the currency recovered, and the institutional "
                     "hedging channel reasserted itself as the dominant flow",
        invalidates="a war-era risk-premium model over-predicts in this era, and the flagship "
                    "hedging edge should be STRONGER here than in 2023-2024 -- which is itself a "
                    "testable prediction rather than a caveat"),
)


# --------------------------------------------------------------------------- the pack
#: THE PACK AS THIS DEPARTMENT WROTE IT, before any framework touches it. See the same note in
#: `countries.sa.pack`: `country_lab.CountryPack` coerces rows into its own shape and is being
#: rewritten by a sibling builder, so the department's own vocabulary is kept here, the tests
#: validate THIS, and `pack()` returns whatever the framework gives the scheduler.
FIELDS: dict[str, Any] = {
    "code": CODE,
    "name": NAME,
    "region_command": REGION_COMMAND,
    "currency": CURRENCY,
    "executable_instruments": EXECUTABLE_INSTRUMENTS,
    "central_bank": CENTRAL_BANK,
    "fixing_conventions": FIXING_CONVENTIONS,
    "settlement_conventions": SETTLEMENT_CONVENTIONS,
    "exchanges": EXCHANGES,
    "holidays_rule": HOLIDAYS_RULE,
    "fiscal_year_end": FISCAL_YEAR_END,
    "positioning_sources": POSITIONING_SOURCES,
    "native_languages": NATIVE_LANGUAGES,
    "terminology": TERMINOLOGY,
    "source_classes": SOURCE_CLASSES,
    "datasets": DATASETS,
    "actors": ACTORS,
    "domains": DOMAINS,
    "custom_miners": CUSTOM_MINERS,
    "transmission_edges_seed": TRANSMISSION_EDGES_SEED,
    "policy_eras": POLICY_ERAS,
}


def pack() -> Any:
    """The Israel country pack. `CountryPack` when the framework has landed, else a dict."""
    return build_pack(**FIELDS)


def instrument_report(path: Any = None) -> dict[str, Any]:
    """What this pack can trade, what carries its economics, and what is missing -- measured."""
    split = resolve(EXECUTABLE_INSTRUMENTS, path)
    return {"code": CODE, "own_price": OWN_PRICE, "executable": tuple(split["tradable"]),
            "equities_refused": tuple(split["equities"]),
            "absent_from_universe": tuple(split["absent"]),
            "transmission_targets": TRANSMISSION_TARGETS,
            "named_absent_instruments": ABSENT_INSTRUMENTS,
            "dataset_fields": DATASET_FIELDS}
